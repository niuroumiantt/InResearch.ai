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
interrupted run resumes unchanged files and retries changed or failed paths.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import itertools
import uuid
import json
import os
from pathlib import Path
import sys
import threading
import time

import m4_paths
from file_moves import digest
from jsonl_store import JsonlStore, atomic_write, read_rows
from m4_records import bucket, inventory_record, load_inventory

DEFAULT_ROOT = m4_paths.source()
DEFAULT_OUT = m4_paths.data()
MAX_WORKERS = 16

def walk(root: Path):
    """Yield files under root. Symlinks are recorded, never followed."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not Path(dirpath, d).is_symlink())
        for name in sorted(filenames):
            yield Path(dirpath, name)


ROW_KEYS = {"sha256", "size_bytes", "suffix", "original_rel", "original_name",
            "l0_bucket", "route"}


def foreign_row(row):
    """True when a row was not written by this tool's inventory format."""
    if not isinstance(row, dict):
        return True
    if "error" in row:
        return "original_rel" not in row
    return not ROW_KEYS.issubset(row)


def check_format(out_file: Path):
    for number, row in enumerate(read_rows(out_file), 1):
        if foreign_row(row):
            raise SystemExit(
                '%s line %d uses a different format. Run migrate-inventory on this '
                'out-dir before inventory; migration preserves a backup.' % (out_file, number))


def migrate_inventory(out_dir):
    """Explicit schema migration; preserve every historical observation and raw bytes."""
    path = out_dir / 'inventory.jsonl'
    if not path.exists():
        raise SystemExit('no inventory yet: %s' % path)
    with JsonlStore(path).locked():
        rows = list(read_rows(path))
        normalized = [inventory_record(row) for row in rows]
        if normalized == rows:
            return {'migrated': 0}
        backup = path.with_name(path.name + '.before-migration-' + uuid.uuid4().hex)
        atomic_write(backup, path.read_bytes())
        atomic_write(path, ''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                   for row in normalized).encode('utf-8'))
    return {'migrated': len(rows), 'backup': str(backup)}


def inventory(root: Path, out_dir: Path, workers: int, limit=None):
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError('workers must be between 1 and %d' % MAX_WORKERS)
    if not root.is_dir():
        raise SystemExit('source root not found: %s' % root)
    if out_dir.resolve() == root.resolve() or root.resolve() in out_dir.resolve().parents:
        raise SystemExit('output must live outside the source tree: %s' % out_dir)
    started = time.monotonic()
    out_file = out_dir / 'inventory.jsonl'
    counts = Counter()
    lock = threading.Lock()
    with JsonlStore(out_file).locked() as store:
        check_format(out_file)
        binding = out_dir / 'inventory.meta.json'
        identity = {'schema_version': 1, 'source_root': str(root.resolve())}
        if binding.exists() and json.loads(binding.read_text()) != identity:
            raise ValueError('inventory_source_root_changed: use a different dataset')
        if not binding.exists():
            atomic_write(binding, (json.dumps(identity) + '\n').encode())
        done = {row['original_rel']: row for row in load_inventory(out_file)}

        def record(path):
            rel = str(path.relative_to(root))
            previous = done.get(rel, {})
            try:
                info = path.lstat()
                signature = {'size_bytes': info.st_size, 'mtime_ns': info.st_mtime_ns,
                             'ctime_ns': info.st_ctime_ns, 'device': info.st_dev, 'inode': info.st_ino}
                if not previous.get('error') and all(previous.get(k) == v for k, v in signature.items()):
                    with lock:
                        counts['skipped_already_recorded'] += 1
                    return
                if path.is_symlink():
                    row = {'original_rel': rel, 'error': 'symlink_not_followed'}
                else:
                    sha = digest(path)
                    after = path.lstat()
                    if (info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino, info.st_dev) != (
                            after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_ino, after.st_dev):
                        raise ValueError('inventory_file_changed')
                    row = inventory_record({'original_rel': rel, 'sha256': sha, **signature,
                                            'hashed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
            except (OSError, ValueError) as exc:
                row = {'original_rel': rel, 'error': type(exc).__name__}
            with lock:
                store.append(row)
                counts['errors' if 'error' in row else 'hashed'] += 1
                counts['bytes'] += row.get('size_bytes', 0)
                total = counts['hashed'] + counts['errors']
                if total % 500 == 0:
                    sys.stderr.write('  %d files, %.1f GB\n' % (total, counts['bytes'] / 1e9))

        paths = walk(root)
        if limit:
            paths = itertools.islice(paths, limit)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for _ in pool.map(record, paths):
                pass
    return {'root': str(root), 'inventory': str(out_file), 'workers': workers,
            'hashed': counts['hashed'], 'errors': counts['errors'],
            'skipped_already_recorded': counts['skipped_already_recorded'],
            'bytes': counts['bytes'], 'elapsed_seconds': round(time.monotonic() - started, 1)}


def summary(out_dir: Path):
    out_file = out_dir / 'inventory.jsonl'
    if not out_file.exists():
        raise SystemExit('no inventory yet: %s' % out_file)
    rows = load_inventory(out_file, strict=False)
    by_sha = defaultdict(list)
    buckets, routes, errors = Counter(), Counter(), Counter()
    for row in rows:
        if row.get('error'):
            errors[row['error']] += 1
        else:
            by_sha[row['sha256']].append(row)
            buckets[row['l0_bucket']] += 1
            routes[row['route']] += 1
    groups = [group for group in by_sha.values() if len(group) > 1]
    return {'rows': len(rows), 'unique_sha256': len(by_sha),
            'bytes': sum(row.get('size_bytes', 0) for row in rows if not row.get('error')),
            'duplicate_groups': len(groups), 'duplicate_extra_copies': sum(len(g) - 1 for g in groups),
            'duplicate_reclaimable_bytes': sum((len(g) - 1) * g[0]['size_bytes'] for g in groups),
            'l0_buckets': dict(buckets.most_common()), 'routes': dict(routes.most_common()),
            'errors': dict(errors.most_common())}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.environ.get("M4_TRIAGE_ROOT", str(m4_paths.source())))
    ap.add_argument("--out-dir", default=os.environ.get("M4_TRIAGE_OUT", str(m4_paths.data())))
    sub = ap.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory", help="hash and bucket every file (read-only, resumable)")
    inv.add_argument("--workers", type=int, default=8, help="hashing threads (1..%d)" % MAX_WORKERS)
    inv.add_argument("--limit", type=int, help="stop after this many files, for a trial run")
    sub.add_parser("migrate-inventory", help="normalize legacy records with an intact backup")
    sub.add_parser("summary", help="report buckets and duplicates from the inventory")
    args = ap.parse_args(argv)
    out_dir = Path(args.out_dir).expanduser()
    if args.command == "inventory":
        if not 1 <= args.workers <= MAX_WORKERS:
            ap.error("workers must be 1..%d" % MAX_WORKERS)
        result = inventory(Path(args.root).expanduser(), out_dir, args.workers, args.limit)
    elif args.command == "migrate-inventory":
        result = migrate_inventory(out_dir)
    else:
        result = summary(out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
