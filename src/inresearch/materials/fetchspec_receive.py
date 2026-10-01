"""Verify Fetchspec packages and archive immutable, traceable product inputs.

The package is untrusted data. This adapter validates every path and digest,
archives bytes by content identity, preserves each source observation, and only
hands explicitly selected files with a production extractor to the Reader queue.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import tempfile
import zipfile

from inresearch.materials.artifacts import private_dir
from inresearch.storage.files import locked
from inresearch.storage.layout import workspace_path


SHA = re.compile(r"^[a-f0-9]{64}$")
SUPPORTED = {".pdf", ".html", ".htm", ".txt", ".md", ".csv", ".tsv",
             ".docx", ".pptx", ".xlsx", ".xls", ".ppt", ".et", ".wps", ".dps"}
FORMATS = {"pdf", "doc", "docm", "docx", "dot", "dotm", "dotx", "xls", "xlsb", "xlsm", "xlsx",
           "xlt", "xltm", "xltx", "ppt", "pptm", "pptx", "pps", "ppsm", "ppsx", "pot", "potm", "potx",
           "csv", "rtf", "odt", "ods", "odp", "html"}


class PackageError(ValueError):
    pass


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _safe_package_file(package: Path, relative: str) -> Path:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or not rel.parts or any(part in {".", ".."} for part in rel.parts):
        raise PackageError("unsafe_package_path")
    path = package.joinpath(*rel.parts)
    if path.is_symlink() or not path.resolve().is_relative_to(package.resolve()) or not path.is_file():
        raise PackageError("package_file_missing_or_unsafe")
    return path


def _validate_format(path: Path, fmt: str):
    with path.open("rb") as stream:
        head = stream.read(4096)
    if fmt == "pdf":
        valid = head.lstrip().startswith(b"%PDF-")
    elif fmt == "rtf":
        valid = head.lstrip().startswith(b"{\\rtf")
    elif fmt in {"doc", "xls", "ppt"}:
        valid = head.startswith(bytes.fromhex("d0cf11e0a1b11ae1"))
    elif fmt in {"docx", "docm", "dot", "dotm", "dotx", "xlsx", "xlsb", "xlsm", "xlt", "xltx", "xltm",
                 "pptx", "pptm", "pps", "ppsx", "ppsm", "pot", "potx", "potm", "odt", "ods", "odp"}:
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if fmt in {"docx", "docm", "dot", "dotm", "dotx"}:
                    valid = "word/document.xml" in names
                elif fmt in {"xlsx", "xlsb", "xlsm", "xlt", "xltx", "xltm"}:
                    valid = any(name in names for name in ("xl/workbook.xml", "xl/workbook.bin"))
                elif fmt in {"pptx", "pptm", "pps", "ppsx", "ppsm", "pot", "potx", "potm"}:
                    valid = "ppt/presentation.xml" in names
                else:
                    valid = "mimetype" in names or "content.xml" in names
        except (OSError, zipfile.BadZipFile):
            valid = False
    elif fmt == "html":
        valid = b"<" in head and b"\x00" not in head
    elif fmt == "csv":
        try:
            head.decode("utf-8-sig")
            valid = b"\x00" not in head
        except UnicodeError:
            valid = False
    else:
        valid = False
    if not valid:
        raise PackageError("declared_format_does_not_match_bytes")


def _load_package(package: Path, max_items: int = 10000, max_bytes: int = 20 * 1024**3):
    package = package.expanduser().resolve(strict=True)
    manifest_path = _safe_package_file(package, "manifest.json")
    sums_path = _safe_package_file(package, "SHA256SUMS")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise PackageError("manifest_invalid") from None
    if (not isinstance(manifest, dict) or manifest.get("provider_id") != "fetchspec"
            or manifest.get("contract_version") not in {"1.0", "1.1", "2.0"}
            or not isinstance(manifest.get("delivery_id"), str)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,160}", manifest["delivery_id"])
            or not isinstance(manifest.get("items"), list)
            or len(manifest["items"]) > max_items
            or not manifest["items"]
            or manifest.get("files_included") is not True):
        raise PackageError("manifest_contract_invalid_or_files_absent")
    if manifest["contract_version"] == "2.0":
        target_ids = manifest.get("target_ids")
        if (not isinstance(target_ids, list) or not target_ids or len(target_ids) > 500
                or len(set(target_ids)) != len(target_ids)
                or any(not isinstance(value, str) or not value or len(value) > 200 for value in target_ids)):
            raise PackageError("generated_target_ids_invalid")
    entries = {}
    for line in sums_path.read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  (files/[0-9a-f]{2}/[a-f0-9]{64}\.[A-Za-z0-9]{1,12})", line)
        if not match or match.group(2) in entries:
            raise PackageError("checksum_manifest_invalid")
        entries[match.group(2)] = match.group(1)
    item_paths, total = set(), 0
    for item in manifest["items"]:
        if not isinstance(item, dict):
            raise PackageError("item_invalid")
        source = item.get("source")
        allowed_language = {"en", "zh", "en_or_unmarked"}
        if (not isinstance(source, dict)
                or (manifest.get("contract_version") != "1.0"
                    and (source.get("language") not in allowed_language
                         or not isinstance(source.get("categories", []), list)
                         or any(not isinstance(value, str) or len(value) > 160
                                for value in source.get("categories", []))))
                or not isinstance(item.get("access_scope"), dict)
                or item["access_scope"].get("state") != "public"):
            raise PackageError("source_language_or_access_scope_invalid")
        if manifest["contract_version"] == "2.0":
            item_targets = item.get("target_ids")
            if (not isinstance(item_targets, list) or not item_targets
                    or len(set(item_targets)) != len(item_targets)
                    or any(value not in manifest["target_ids"] for value in item_targets)):
                raise PackageError("item_generated_target_ids_invalid")
        sha, relative = item.get("sha256"), item.get("path")
        if (not isinstance(sha, str) or not SHA.fullmatch(sha) or not isinstance(relative, str)
                or not relative.startswith("files/") or not isinstance(item.get("format"), str)
                or item.get("format", "").lower() not in FORMATS
                or not isinstance(item.get("source_item_id"), str) or not item["source_item_id"]
                or not isinstance(item.get("retrieved_at"), str) or not item["retrieved_at"]
                or not isinstance(item.get("source"), dict)
                or not isinstance(item["source"].get("url"), str)
                or not item["source"]["url"].startswith("https://")
                or not isinstance(item.get("completeness"), dict)
                or not isinstance(item.get("access_scope"), dict)
                or not isinstance(item.get("version_relation"), dict)
                or item["version_relation"].get("type") not in {"original", "new_version"}
                or (item["version_relation"].get("type") == "new_version"
                    and not SHA.fullmatch(str(item["version_relation"].get("supersedes_sha256", ""))))):
            raise PackageError("item_contract_invalid")
        if relative in item_paths or entries.get(relative) != sha:
            raise PackageError("manifest_checksum_set_mismatch")
        item_paths.add(relative)
        path = _safe_package_file(package, relative)
        _validate_format(path, item["format"].lower())
        size = path.stat().st_size
        if type(item.get("bytes")) is not int or item["bytes"] != size:
            raise PackageError("item_size_mismatch")
        total += size
        if total > max_bytes or _digest(path) != sha:
            raise PackageError("package_size_limit_or_digest_mismatch")
    if item_paths != set(entries):
        raise PackageError("manifest_checksum_set_mismatch")
    return package, manifest


def _ledger(root: Path):
    logical = "data/raw/supply-center/receipts.json"
    return workspace_path(logical, root)


def _write_json(path: Path, value):
    private_dir(path.parent)
    fd, name = tempfile.mkstemp(prefix=".receipt-", suffix=".partial", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _categories(source: dict) -> list[str]:
    values = source.get("categories") or ["uncategorized"]
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        return ["uncategorized"]
    result = [re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE)[:100] or "uncategorized" for value in values]
    return ["uncategorized" if value in {".", ".."} else value for value in result]


# fetchspec 契约 parameter_observation_fields（supply_contract.json 生成目标契约 2.0）。
OBSERVATION_FIELDS = ("company_id", "product_id", "target_id", "part_id", "parameter_name", "value",
                      "unit", "condition", "source_url", "source_sha256", "observed_at")


def _parameter_observations(item: dict, target_ids: list) -> list:
    """包内人审参数观测（值为厂商原文）。只收字段齐全、目标行属于本项、来源是本项字节的；其余丢弃，不拒包。"""
    kept = []
    for evidence in item.get("product_evidence") or []:
        if not isinstance(evidence, dict):
            continue
        for row in evidence.get("parameter_observations") or []:
            if (isinstance(row, dict) and all(isinstance(row.get(k), str) for k in OBSERVATION_FIELDS if k != "part_id")
                    and row.get("target_id") in target_ids and row.get("source_sha256") == item.get("sha256")
                    and len(row["value"]) <= 2000 and len(row["parameter_name"]) <= 200):
                kept.append({k: row.get(k) for k in OBSERVATION_FIELDS})
            if len(kept) >= 500:
                return kept
    return kept


def _archive_acquisition(package: Path, manifest: dict, data_root: Path, context: dict):
    """Use the shared candidate acquisition catalog and content-addressed blob store."""
    from inresearch.adapters.acquisition import Collector
    collector = Collector(data_root)
    def import_items():
        count = 0
        for item in manifest["items"]:
            fmt = item["format"].lower()
            source = _safe_package_file(package, item["path"])
            metadata = {"delivery_id": manifest["delivery_id"], "task_id_or_discovery": manifest.get("task_id_or_discovery", "discovery"),
                "company_id": manifest.get("company_id"), "source_item_id": item["source_item_id"],
                "source": item["source"], "retrieved_at": item["retrieved_at"], "sha256": item["sha256"],
                "format": fmt, "bytes": item["bytes"], "completeness": item["completeness"],
                "access_scope": item["access_scope"], "version_relation": item["version_relation"],
                "research_context": context, "target_ids": item.get("target_ids", []),
                "parameter_observations": _parameter_observations(item, item.get("target_ids", [])),
                "acceptance": "candidate"}
            title = item.get("title") or item["source"].get("original_filename") or item["source_item_id"]
            question = context["question_ids"][0] if context["question_ids"] else None
            ident = collector.item("fetchspec", item["source_item_id"], "product_document",
                item["source"]["url"], title, metadata, question=question)
            collector.archive_file(ident, source, "." + fmt,
                {"delivery_id": manifest["delivery_id"], "collector_revision": manifest.get("collector_revision"),
                 "version_relation": item["version_relation"]})
            categories = item["source"].get("categories") or ["uncategorized"]
            for question_id in context["question_ids"] or [None]:
                with collector.db:
                    collector.db.execute('''INSERT INTO product_documents
                        (sha256,source_item_id,company_id,first_category,categories_json,format,language,
                         question_id,object_ids_json,task_id,source_url,original_filename,version_relation_json,title,received_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(sha256,source_item_id,question_id) DO UPDATE SET
                        first_category=excluded.first_category,categories_json=excluded.categories_json,
                        format=excluded.format,language=excluded.language,object_ids_json=excluded.object_ids_json,
                        task_id=excluded.task_id,source_url=excluded.source_url,
                        original_filename=excluded.original_filename,version_relation_json=excluded.version_relation_json,
                        title=excluded.title,
                        received_at=excluded.received_at''',
                        (item["sha256"], item["source_item_id"], manifest.get("company_id", ""), categories[0],
                         json.dumps(categories, ensure_ascii=False), fmt,
                         item["source"].get("language", "en_or_unmarked"), question_id or "",
                         json.dumps(context["object_ids"], ensure_ascii=False), context["task_id"],
                         item["source"]["url"], item["source"].get("original_filename"),
                         json.dumps(item["version_relation"], ensure_ascii=False), title,
                         datetime.now(timezone.utc).isoformat()))
            count += 1
        return count
    try:
        return collector.run("fetchspec", import_items)
    finally:
        collector.close()


def _materialized_in(data_root: Path, manifest: dict, reader_hashes=()) -> bool:
    """Only acknowledge replay when this data root still has every durable projection."""
    catalog = data_root / "acquisition" / "catalog.sqlite"
    if not catalog.is_file():
        return False
    try:
        db = sqlite3.connect(catalog.resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
        try:
            checked_inodes = set()
            for item in manifest["items"]:
                sha, suffix = item["sha256"], "." + item["format"].lower()
                safe_categories = _categories(item["source"])
                paths = [data_root / "acquisition" / "blobs" / sha[:2] / (sha + suffix),
                         data_root / "originals" / sha[:2] / sha / (sha + suffix)]
                paths.extend(data_root / "product-library" / "fetchspec" / category / (sha + suffix)
                             for category in safe_categories)
                if suffix in SUPPORTED and sha in reader_hashes:
                    paths.append(data_root / "raw-materials" / "fetchspec" / safe_categories[0] / (sha + suffix))
                for path in paths:
                    if path.is_symlink() or not path.is_file() or path.stat().st_size != item["bytes"]:
                        return False
                    stat = path.stat()
                    inode = (stat.st_dev, stat.st_ino, stat.st_size)
                    if inode not in checked_inodes:
                        if _digest(path) != sha:
                            return False
                        checked_inodes.add(inode)
                row = db.execute("SELECT 1 FROM product_documents WHERE sha256=? AND source_item_id=? LIMIT 1",
                                 (sha, item["source_item_id"])).fetchone()
                if row is None:
                    return False
        finally:
            db.close()
    except sqlite3.Error:
        return False
    return True


def _receive(root: Path, package_path: Path, data_root: Path, reader_sha256=()):
    package, manifest = _load_package(package_path)
    target_ids, part_ids = [], []
    if manifest["contract_version"] == "2.0":
        try:
            target_document = json.loads((root / "framework/tco_targets.json").read_text())
        except (OSError, json.JSONDecodeError):
            raise PackageError("generated_target_registry_unavailable") from None
        registered = {row["id"]: row for row in target_document.get("targets", [])
                      if isinstance(row, dict) and row.get("team") == "fetchspec"}
        target_ids = manifest["target_ids"]
        if any(target_id not in registered for target_id in target_ids):
            raise PackageError("generated_target_not_found_or_wrong_provider")
        part_ids = sorted({registered[target_id]["part_id"] for target_id in target_ids
                           if registered[target_id].get("part_id")})
    requested_reader_hashes = set(reader_sha256 or ())
    items_by_sha = {item["sha256"]: item for item in manifest["items"]}
    if requested_reader_hashes - items_by_sha.keys():
        raise PackageError("reader_handoff_sha256_not_in_delivery")
    if any("." + items_by_sha[sha]["format"].lower() not in SUPPORTED for sha in requested_reader_hashes):
        raise PackageError("reader_handoff_extractor_required")
    receipt_file = _ledger(root)
    if receipt_file.exists():
        ledger = json.loads(receipt_file.read_text())
        if ledger.get("version") != 1 or not isinstance(ledger.get("deliveries"), dict):
            raise PackageError("receipt_ledger_corrupt")
    else:
        ledger = {"version": 1, "deliveries": {}}
    delivery_id = manifest["delivery_id"]
    identity = hashlib.sha256((package / "manifest.json").read_bytes()).hexdigest()
    prior = ledger["deliveries"].get(delivery_id)
    prior_reader_hashes = {
        item.get("sha256") for item in (prior or {}).get("items", [])
        if item.get("reader_handoff") == "eligible"
    }
    reader_hashes = prior_reader_hashes | requested_reader_hashes
    if prior:
        if prior["manifest_sha256"] != identity:
            raise PackageError("delivery_id_reused_with_different_manifest")
        if _materialized_in(Path(data_root).expanduser().resolve(), manifest, reader_hashes):
            return prior

    task_ref = manifest.get("task_id_or_discovery", "discovery")
    research_context = {"task_id": None, "demand_id": None, "question_ids": [], "object_ids": [],
                        "target_ids": target_ids, "part_ids": part_ids}
    if task_ref != "discovery":
        planning_path = workspace_path("data/raw/supply-center/ledger.json", root)
        try:
            planning = json.loads(planning_path.read_text())
        except (OSError, json.JSONDecodeError):
            raise PackageError("supply_task_ledger_unavailable") from None
        task = next((row for row in planning.get("tasks", []) if row.get("id") == task_ref
                     and row.get("provider_id") == "fetchspec"), None)
        if not task:
            raise PackageError("supply_task_not_found_or_wrong_provider")
        demand = next((row for row in planning.get("demands", []) if row.get("id") == task.get("demand_id")), None)
        if not demand:
            raise PackageError("supply_demand_not_found")
        research_context = {"task_id": task_ref, "demand_id": demand["id"],
                            "question_ids": [demand["question_id"]],
                            "object_ids": demand.get("object_ids", []),
                            "target_ids": target_ids, "part_ids": part_ids}

    data_root = Path(data_root).expanduser().resolve()
    _archive_acquisition(package, manifest, data_root, research_context)

    library = data_root / "product-library" / "fetchspec"
    receipts, updates = [], []
    for item in manifest["items"]:
        sha, fmt = item["sha256"], item.get("format", "").lower()
        suffix = "." + fmt
        original = data_root / "originals" / sha[:2] / sha / (sha + suffix)
        private_dir(original.parent)
        if original.exists():
            if _digest(original) != sha:
                raise PackageError("existing_original_digest_mismatch")
        else:
            archive_blob = data_root / "acquisition" / "blobs" / sha[:2] / (sha + suffix)
            if not archive_blob.is_file() or _digest(archive_blob) != sha:
                raise PackageError("acquisition_archive_blob_missing_or_corrupt")
            try:
                os.link(archive_blob, original)
            except OSError:
                shutil.copy2(archive_blob, original)
                if _digest(original) != sha:
                    raise PackageError("staged_original_digest_mismatch")
        safe_categories = _categories(item["source"])
        for category in safe_categories:
            view = library / category / (sha + suffix)
            private_dir(view.parent)
            if not view.exists():
                try:
                    os.link(original, view)
                except OSError:
                    shutil.copy2(original, view)
            if _digest(view) != sha:
                raise PackageError("library_view_digest_mismatch")
        relation = item["version_relation"]
        source_url = item["source"]["url"]
        role = str(item["source"].get("discovery_role", "")).lower()
        if relation.get("type") == "new_version":
            change_type = "pcn" if "pcn" in source_url.lower() or "pcn" in role else "specification_revision"
            updates.append({"change_type": change_type, "source_item_id": item["source_item_id"],
                            "previous_sha256": relation.get("supersedes_sha256"), "current_sha256": sha,
                            "review_required": True, "research_context": research_context})
        if suffix in SUPPORTED and sha in reader_hashes:
            handoff = data_root / "raw-materials" / "fetchspec" / safe_categories[0] / (sha + suffix)
            private_dir(handoff.parent)
            if not handoff.exists():
                try:
                    os.link(original, handoff)
                except OSError:
                    shutil.copy2(original, handoff)
            if _digest(handoff) != sha:
                raise PackageError("reader_handoff_digest_mismatch")
        receipts.append({"sha256": sha, "format": fmt, "target_ids": item.get("target_ids", []),
                         "status": "received" if suffix in SUPPORTED else "needs_supplement",
                         "reader_handoff": ("eligible" if sha in reader_hashes else "held")
                         if suffix in SUPPORTED else "extractor_required"})
    result = {"delivery_id": delivery_id, "manifest_sha256": identity,
              "task_id_or_discovery": task_ref, "research_context": research_context,
              "company_id": manifest.get("company_id"), "known_gaps": manifest.get("known_gaps", []),
              "updates": updates,
              "status": "received" if all(x["status"] == "received" for x in receipts) else "needs_supplement",
              "reader_handoff_count": sum(x["reader_handoff"] == "eligible" for x in receipts),
              "received_items": len(receipts), "items": receipts,
              "next": ("Reader scan registers only explicitly selected files; reader run extracts them. "
                       "All other files remain archived and held. Unsupported formats require a supplement.")}
    ledger["deliveries"][delivery_id] = result
    _write_json(receipt_file, ledger)
    return result


def receive(root: Path, package_path: Path, data_root: Path, reader_sha256=()):
    receipt_file = _ledger(Path(root))
    with locked(receipt_file):
        return _receive(Path(root), package_path, data_root, reader_sha256)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--data-root", type=Path, default=Path.home() / ".local/share/inresearch.ai")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--reader-sha256", action="append", default=[], metavar="SHA256",
                        help="explicitly hand this package item to Reader; repeat for each selected file. Default: archive only")
    args = parser.parse_args(argv)
    try:
        result = receive(args.repo_root.resolve(), args.package, args.data_root, args.reader_sha256)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PackageError, OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"status": "rejected", "error_code": str(exc)[:160]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
