#!/usr/bin/env python3
"""M4 triage step 1: read-only inventory of the local raw-material tree.

Walks the source tree, records size and SHA-256 for every file, assigns an L0
bucket from path and suffix only, and reports byte-identical duplicates.

This command never renames, moves, writes into or deletes anything under the
source root: it opens files read-only and refuses an output path inside the
tree. Renaming and moving belong to a later step that writes its operation log
before it touches a file.

Hashing runs in a thread pool; hashlib releases the GIL for large updates, so
several threads keep the disk busy. The output is append-only JSONL, so an
interrupted run resumes by skipping paths already recorded.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

DEFAULT_ROOT = "/Users/m4/Downloads/所有raw materials"
DEFAULT_OUT = Path.home() / ".local/share/inresearch.ai/m4-triage"
CHUNK = 4 * 1024 * 1024
MAX_WORKERS = 16

# L0 buckets come from the adopted task card. They are provisional by
# construction: a bucket assigned from a suffix is never evidence of reading.
DRAWING = {".dwg", ".dxf", ".dwf", ".dgn", ".rvt", ".rfa", ".ifc", ".skp", ".3dm",
           ".step", ".stp", ".iges", ".igs", ".obj", ".fbx", ".max", ".blend", ".sat"}
OFFICE = {".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".pages",
          ".numbers", ".key", ".odt", ".ods", ".odp", ".rtf", ".wps", ".et", ".dps"}
TEXT = {".pdf", ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".htm", ".html"}
IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif",
         ".webp", ".svg", ".psd", ".ai", ".eps", ".raw", ".cr2", ".nef"}
ARCHIVE = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".iso"}
INSTALLER = {".dmg", ".pkg", ".exe", ".msi", ".app", ".deb", ".rpm", ".apk", ".jar"}
MEDIA = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".mp3", ".wav", ".m4a", ".aac"}
# Files the operating system writes next to real material; never research content.
NOISE_NAMES = {".ds_store", "thumbs.db", "desktop.ini", ".localized"}
PARTIAL_SUFFIXES = (".part", ".partial", ".tmp", ".crdownload", ".download", ".filepart")


def bucket(rel: str, suffix: str) -> tuple[str, str]:
    """Return (l0_bucket, route). route says which reading level comes next."""
    name = Path(rel).name.lower()
    if name in NOISE_NAMES or name.endswith(PARTIAL_SUFFIXES):
        return "_noise", "l0_name_only"
    if suffix in DRAWING:
        return "_drawings_unread", "l0_name_only"
    if suffix in OFFICE:
        return "_office_pending", "l0_name_only"
    if suffix in TEXT:
        return "text_candidate", "l1_preview"
    if suffix in IMAGE:
        return "image", "l0_name_only"
    if suffix in ARCHIVE:
        return "archive", "l0_name_only"
    if suffix in INSTALLER:
        return "installer", "l0_name_only"
    if suffix in MEDIA:
        return "media", "l0_name_only"
    return "other", "l0_name_only"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def walk(root: Path):
    """Yield files under root. Symlinks are recorded, never followed."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not Path(dirpath, d).is_symlink())
        for name in sorted(filenames):
            yield Path(dirpath, name)


def load_done(out_file: Path) -> set[str]:
    """Relative paths already recorded, so an interrupted run resumes."""
    done = set()
    if not out_file.exists():
        return done
    with out_file.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["original_rel"])
            except (ValueError, KeyError):
                continue  # a torn final line from a killed run is re-hashed
    return done


def inventory(root: Path, out_dir: Path, workers: int, limit=None):
    if not root.is_dir():
        raise SystemExit("source root not found: %s" % root)
    try:
        out_dir.resolve().relative_to(root.resolve())
        raise SystemExit("output must live outside the source tree: %s" % out_dir)
    except ValueError:
        pass
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "inventory.jsonl"
    done = load_done(out_file)
    started = time.monotonic()
    lock = threading.Lock()
    counts = Counter()
    handle = out_file.open("a", encoding="utf-8")

    def record(path: Path):
        rel = str(path.relative_to(root))
        if rel in done:
            counts["skipped_already_recorded"] += 1
            return
        try:
            info = path.lstat()
            if path.is_symlink():
                row = {"original_rel": rel, "error": "symlink_not_followed"}
            else:
                suffix = path.suffix.lower()
                l0, route = bucket(rel, suffix)
                row = {"sha256": digest(path), "size_bytes": info.st_size,
                       "suffix": suffix, "original_rel": rel,
                       "original_name": path.name, "l0_bucket": l0, "route": route,
                       "mtime": int(info.st_mtime),
                       "hashed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        except OSError as exc:
            row = {"original_rel": rel, "error": type(exc).__name__}
        line = json.dumps(row, ensure_ascii=False)
        with lock:
            handle.write(line + "\n")
            counts["errors" if "error" in row else "hashed"] += 1
            counts["bytes"] += row.get("size_bytes", 0)
            total = counts["hashed"] + counts["errors"]
            if total % 500 == 0:
                handle.flush()
                elapsed = time.monotonic() - started
                sys.stderr.write("  %d files, %.1f GB, %.0f files/s\n" % (
                    total, counts["bytes"] / 1e9, total / max(elapsed, 0.001)))
                sys.stderr.flush()

    try:
        paths = walk(root)
        if limit:
            paths = (p for i, p in enumerate(paths) if i < limit)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(record, paths))
    finally:
        handle.close()
    return {"root": str(root), "inventory": str(out_file), "workers": workers,
            "hashed": counts["hashed"], "errors": counts["errors"],
            "skipped_already_recorded": counts["skipped_already_recorded"],
            "bytes": counts["bytes"],
            "elapsed_seconds": round(time.monotonic() - started, 1)}


def summary(out_dir: Path):
    out_file = out_dir / "inventory.jsonl"
    if not out_file.exists():
        raise SystemExit("no inventory yet: %s" % out_file)
    by_sha = defaultdict(list)
    buckets, routes, errors = Counter(), Counter(), Counter()
    total_bytes = 0
    rows = 0
    with out_file.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            rows += 1
            if "error" in row:
                errors[row["error"]] += 1
                continue
            by_sha[row["sha256"]].append(row["original_rel"])
            buckets[row["l0_bucket"]] += 1
            routes[row["route"]] += 1
            total_bytes += row["size_bytes"]
    # Byte-identical copies: one kept, the rest are duplicates to review.
    dup_groups = {sha: paths for sha, paths in by_sha.items() if len(paths) > 1}
    dup_extra = sum(len(paths) - 1 for paths in dup_groups.values())
    reclaimable = 0
    with out_file.open(encoding="utf-8") as handle:
        seen = set()
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            sha = row.get("sha256")
            if sha in dup_groups:
                if sha in seen:
                    reclaimable += row["size_bytes"]
                seen.add(sha)
    return {"rows": rows, "unique_sha256": len(by_sha), "bytes": total_bytes,
            "duplicate_groups": len(dup_groups), "duplicate_extra_copies": dup_extra,
            "duplicate_reclaimable_bytes": reclaimable,
            "l0_buckets": dict(buckets.most_common()),
            "routes": dict(routes.most_common()), "errors": dict(errors.most_common())}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.environ.get("M4_TRIAGE_ROOT", DEFAULT_ROOT))
    ap.add_argument("--out-dir", default=os.environ.get("M4_TRIAGE_OUT", str(DEFAULT_OUT)))
    sub = ap.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory", help="hash and bucket every file (read-only, resumable)")
    inv.add_argument("--workers", type=int, default=8, help="hashing threads (1..%d)" % MAX_WORKERS)
    inv.add_argument("--limit", type=int, help="stop after this many files, for a trial run")
    sub.add_parser("summary", help="report buckets and duplicates from the inventory")
    args = ap.parse_args(argv)
    out_dir = Path(args.out_dir).expanduser()
    if args.command == "inventory":
        if not 1 <= args.workers <= MAX_WORKERS:
            ap.error("workers must be 1..%d" % MAX_WORKERS)
        result = inventory(Path(args.root).expanduser(), out_dir, args.workers, args.limit)
    else:
        result = summary(out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
