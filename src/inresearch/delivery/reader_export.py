"""Candidate projections and recoverable backups from explicit catalog inputs."""
from __future__ import annotations
import os, shutil, sqlite3
from pathlib import Path
from inresearch.materials.reader_contracts import UnsafePath, IntegrityError
from inresearch.materials.artifacts import now_iso, digest_file, private_dir, safe_path, atomic_bytes, atomic_json, read_json, signature, is_partial

def read_report(data, doc):
    if not doc['report_rel']:
        return {}
    path = safe_path(data, doc['report_rel'])
    if not doc['report_sha256'] or digest_file(path) != doc['report_sha256']:
        raise IntegrityError()
    return read_json(path)


def export(dest, conn, data, registry, status):
    dest = Path(dest).expanduser().resolve()
    for protected in ("originals", "catalog", "raw-materials", "library", "artifacts", "extracted", "intake-receipts"):
        try:
            dest.relative_to(data / protected)
            raise UnsafePath()
        except ValueError:
            pass
    if dest.suffix.lower() == ".json":
        payload = export_snapshot(conn, data, registry, status)
        atomic_json(dest, payload)
        return {"exported": len(payload["knowledge"]["documents"]), "file": str(dest), "status": payload["reader"]["status"]}
    private_dir(dest)
    reports = []
    for row in conn.execute("SELECT * FROM current_readings WHERE report_rel IS NOT NULL ORDER BY created"):
        report = read_report(data, row)
        atomic_json(safe_path(dest, row["revision_id"] + ".json"), report)
        reports.append({"doc_id": row["doc_id"], "file": row["revision_id"] + ".json", "reading_revision_id": row["revision_id"], "acceptance": "candidate"})
    manifest = {"generated": now_iso(), "status": status["status"], "reports": reports, "acceptance": "candidate_only"}
    atomic_json(safe_path(dest, "manifest.json"), manifest)
    atomic_json(safe_path(dest, "status.json"), status)
    return {"exported": len(reports), "directory": str(dest)}

def export_snapshot(conn, data, registry, status):
    """Web is a rebuildable projection; old reading artifacts retain their versions.

    Revalidate the ID projection against the currently installed registry. Unknown
    IDs stay in a local proposal file; they never make a whole web batch invalid.
    """
    allowed = {"object_ids": {r["id"] for r in registry["objects"] if isinstance(r, dict) and "id" in r},
               "question_ids": {r["id"] for r in registry["questions"] if isinstance(r, dict) and "id" in r}}
    knowledge = {"documents": [], "evidence": [], "statements": [], "answers": []}
    proposals = []
    for row in conn.execute("SELECT * FROM current_readings ORDER BY created,doc_id"):
        doc = dict(row)
        report = read_report(data, doc)
        mapped, missing = {}, {}
        for key in allowed:
            mapped[key] = sorted(set(report.get(key, [])) & allowed[key])
            missing[key] = sorted(set(report.get(key, [])) - allowed[key])
        needs_review = any(missing.values()) or not any(mapped.values())
        if needs_review:
            proposals.append({"doc_id": doc["doc_id"], "unknown_ids": missing,
                              "classification": report.get("classification"), "reason": "unmapped_or_registry_changed"})
        sources = [dict(r) for r in conn.execute("SELECT source_key,version_seq,previous_doc_id,received FROM sources WHERE doc_id=? ORDER BY received,id", (doc["doc_id"],))]
        entry = {"id": doc["doc_id"], "doc_id": doc["doc_id"], "content_sha256": doc["sha256"],
                 "title": report.get("classification", {}).get("title") or doc["original_name"],
                 "stored_path": doc["original_rel"], "sources": sources, "library_path": doc["library_rel"],
                 "coverage": report.get("coverage", {"complete": False, "chunks_total": doc["chunks_total"], "chunks_read": doc["chunks_read"]}),
                 "read_status": doc["state"], "mapping_status": "needs_review" if needs_review else "candidate_mapped",
                 "reading_revision_id": doc["revision_id"] if doc["report_rel"] else None,
                 "report_sha256": doc["report_sha256"],
                 "model": report.get("model"), "status": "candidate", "acceptance": "candidate", **mapped}
        knowledge["documents"].append(entry)
        for evidence in report.get("evidence", []):
            ids = {key: sorted(set(evidence.get(key, [])) & allowed[key]) for key in allowed}
            page = evidence.get('page_index')
            # Reader artifact v1 uses PDF page numbers (1..N). The knowledge
            # contract uses array indices (0..N-1). Convert only at this boundary;
            # old immutable reports keep their original locator and numbering.
            if type(page) is not int or not 1 <= page <= report.get('coverage', {}).get('pages_total', 0):
                raise IntegrityError()
            knowledge["evidence"].append({**evidence, "page_index": page - 1, "document_id": doc["doc_id"], **ids,
                                           "status": "candidate", "acceptance": "candidate"})
        for n, claim in enumerate(report.get("claims", [])):
            ids = {key: sorted(set(claim.get(key, [])) & allowed[key]) for key in allowed}
            knowledge["statements"].append({**claim, "id": claim.get("id") or doc["doc_id"] + ":statement:" + str(n),
                                             "document_id": doc["doc_id"], **ids,
                                             "status": "candidate", "acceptance": "candidate"})
    atomic_json(safe_path(data, "candidates/mapping-proposals.json"), {"generated": now_iso(), "acceptance": "candidate", "records": proposals})
    return {"schema_version": 1, "generated": now_iso(), "graph_version": registry["graph_version"],
            "questions_version": registry["questions_version"], "knowledge": knowledge, "reader": status, "acceptance": "candidate"}

def backup(dest, conn, data, state):
    dest = Path(dest).expanduser().resolve()
    for root in (data, state):
        try:
            dest.relative_to(root)
            raise UnsafePath()
        except ValueError:
            pass
    if dest.exists():
        raise ValueError("backup destination must not exist")
    private_dir(dest)
    atomic_json(dest / "backup.partial.json", {"created": now_iso(), "state": "copying"})
    bdb = dest / "catalog.sqlite"
    snapshot = sqlite3.connect(str(bdb))
    conn.backup(snapshot)
    snapshot.row_factory = sqlite3.Row
    manifest = []
    # Originals and artifacts are immutable; SQLite snapshot plus these objects is recoverable.
    for row in snapshot.execute("SELECT doc_id,original_rel,sha256 FROM documents"):
        src = safe_path(data, row["original_rel"])
        if digest_file(src) != row["sha256"]:
            raise IntegrityError()
        target = safe_path(dest, row["original_rel"])
        private_dir(target.parent)
        shutil.copyfile(str(src), str(target))
        os.chmod(target, 0o400)
        if digest_file(target) != row["sha256"]:
            raise IntegrityError()
        manifest.append({"path": row["original_rel"], "sha256": row["sha256"]})
        for name in ("artifacts", "extracted"):
            base = safe_path(data, "%s/%s" % (name, row["doc_id"]))
            if not base.exists():
                continue
            for p in sorted(base.rglob("*")):
                if p.is_symlink():
                    raise UnsafePath()
                if not p.is_file() or is_partial(p.relative_to(base)):
                    continue
                rel = p.relative_to(data).as_posix()
                target = safe_path(dest, rel)
                atomic_bytes(target, p.read_bytes())
                manifest.append({"path": rel, "sha256": digest_file(target)})
    for row in snapshot.execute("SELECT quarantine_rel,receipt_rel FROM intake_operations"):
        for rel in row:
            src = safe_path(data, rel)
            if src.is_file():
                target = safe_path(dest, rel)
                before = signature(src)
                atomic_bytes(target, src.read_bytes())
                if signature(src) != before or digest_file(src) != digest_file(target):
                    raise IntegrityError()
                manifest.append({"path": rel, "sha256": digest_file(target)})
    snapshot.close()
    os.chmod(bdb, 0o600)
    atomic_json(dest / "manifest.json", {"schema_version": 1, "completed": now_iso(), "catalog_sha256": digest_file(bdb),
                                        "files": manifest, "library": "rebuild_from_operations", "state": "complete"})
    (dest / "backup.partial.json").unlink()
    return {"backup": str(dest), "files": len(manifest), "state": "complete"}
