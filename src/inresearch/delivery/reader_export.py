"""Candidate projections and recoverable backups from explicit catalog inputs."""
from __future__ import annotations
import json, os, re, shutil, sqlite3
from pathlib import Path
from inresearch.materials.reader_contracts import UnsafePath, IntegrityError
from inresearch.materials.artifacts import now_iso, digest_bytes, digest_file, encoded, private_dir, safe_path, atomic_bytes, atomic_json, read_json, signature, is_partial
from inresearch.knowledge.registry import object_resolver
from inresearch.materials.source_provenance import validate as validate_provenance

# Bumped when the projection of one document changes for the same registry and
# report (the cache key otherwise only sees the registry versions).
PROJECTION_VERSION = 3

def read_report(data, doc):
    if not doc['report_rel']:
        return {}
    path = safe_path(data, doc['report_rel'])
    if not doc['report_sha256'] or digest_file(path) != doc['report_sha256']:
        raise IntegrityError()
    return read_json(path)


def export(dest, conn, data, registry, status, doc_ids=None):
    dest = Path(dest).expanduser().resolve()
    for protected in ("originals", "catalog", "raw-materials", "library", "artifacts", "extracted", "intake-receipts"):
        try:
            dest.relative_to(data / protected)
            raise UnsafePath()
        except ValueError:
            pass
    if dest.suffix.lower() == ".json":
        payload = export_snapshot(conn, data, registry, status, doc_ids=doc_ids)
        atomic_json(dest, payload)
        return {"exported": len(payload["knowledge"]["documents"]), "file": str(dest), "status": payload["reader"]["status"]}
    if doc_ids is not None:
        raise ValueError("scoped candidate export requires a JSON snapshot destination")
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

PROJECTION_CACHE = "publish-projection-cache.sqlite"


def projection_cache(cache_root):
    """Derived, disposable and deliberately outside the catalog.

    Losing this file costs one slow export, never a fact: every row is recomputed
    from the catalog and the reports it points at. Keeping it out of
    catalog.sqlite also keeps the publish path a reader of the ledger.
    """
    if cache_root is None:
        return None
    path = Path(cache_root).expanduser().resolve() / PROJECTION_CACHE
    os.close(os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600))
    conn = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS projection "
                 "(doc_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL)")
    return conn


def fingerprint(doc, sources, registry_key, source_metadata=None):
    """Every input the projection reads, report content included via report_sha256.

    Any catalog column, any source row or a registry version change all miss the
    cache, so a stale projection cannot outlive what it was built from.
    """
    stable = {k: (v if isinstance(v, (str, int, float, bool)) or v is None else repr(v))
              for k, v in doc.items()}
    inputs = {"registry": registry_key, "projection": PROJECTION_VERSION, "doc": stable, "sources": sources}
    # Keep cache keys for the other 30,000+ documents unchanged. Only an
    # explicitly received SHA source binding adds a projection input.
    if source_metadata is not None:
        inputs['source_metadata'] = source_metadata
    return digest_bytes(encoded(inputs).encode("utf-8"))


def supplied_sources(data, content_sha256=None):
    """Read only received source fields, not the full matching metadata corpus."""
    path = Path(data) / 'acquisition/catalog.sqlite'
    if not path.is_file() or path.is_symlink():
        return {}
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=30)
    result, sidecars = {}, {}
    try:
        query = """SELECT source_key,url,json_extract(metadata,'$.sha256'),
            json_extract(metadata,'$.source_url'),json_extract(metadata,'$.source_provenance')
            FROM items WHERE source='fetchreports' AND kind='supplied_research'
            AND json_type(metadata,'$.source_provenance')='object'"""
        rows = db.execute(query + (' AND source_key=?' if content_sha256 else ''),
                          (content_sha256,) if content_sha256 else ())
        for sha, url, metadata_sha, metadata_url, value in rows:
            try:
                proof = validate_provenance(json.loads(value), sha, url)
                if metadata_sha != sha or metadata_url != url:
                    continue
                sidecar_sha = proof['sidecar_sha256']
                if sidecar_sha not in sidecars:
                    sidecar = safe_path(data, 'material-reviews/source-sidecars/' + sidecar_sha + '.json')
                    if digest_file(sidecar) != sidecar_sha:
                        raise ValueError('source_sidecar_archive_mismatch')
                    payload = read_json(sidecar)
                    sidecars[sidecar_sha] = (payload.get('batch'), {r.get('sha256'): r for r in payload.get('items', [])})
                batch, selected = sidecars[sidecar_sha]
                supplied = selected.get(sha, {})
                if batch != proof['batch'] or any(supplied.get(k) != proof[k] for k in ('source_id', 'role', 'url')):
                    continue
                if proof['role'] == 'downloaded_original':
                    if supplied.get('original_sha256') != sha:
                        continue
                elif any(supplied.get(k) != proof[k] for k in ('original_bytes_sha256', 'response_sha256', 'derivation')):
                    continue
                result[sha] = {'source_url': url, 'source_provenance': proof}
            except (OSError, ValueError, TypeError, KeyError, IntegrityError, UnsafePath):
                continue
        editorial_query = """SELECT source_key,metadata FROM items WHERE source='fetchreports'
            AND kind='supplied_research' AND json_extract(metadata,'$.source_role')='authored_analysis'"""
        for sha, value in db.execute(editorial_query + (' AND source_key=?' if content_sha256 else ''),
                                     (content_sha256,) if content_sha256 else ()):
            try:
                meta = json.loads(value)
                delivery = meta['editorial_delivery']
                ident, revision = delivery['id'], delivery['revision']
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', ident) or not re.fullmatch(r'[0-9a-f]{64}', revision):
                    continue
                path = safe_path(data, 'incoming/editorial/' + ident + '/' + revision + '/delivery.json')
                item = read_json(path)
                from inresearch.adapters.editorial_sync import validate
                validate(item)
                if (digest_bytes(item['text'].encode()) != sha or item['id'] != ident
                        or digest_bytes(json.dumps(item, ensure_ascii=False, sort_keys=True).encode()) != revision
                        or meta.get('editorial_references') != item.get('references', [])):
                    continue
                result[sha] = {'source_role': 'authored_analysis', 'editorial_references': item.get('references', [])}
                if item.get('url'): result[sha]['source_url'] = item['url']
            except (OSError, ValueError, TypeError, KeyError, IntegrityError, UnsafePath):
                continue
    except sqlite3.OperationalError:
        pass  # Older or absent acquisition catalogs retain the old projection.
    finally:
        db.close()
    return result


def fold_ids(values, allowed_ids, resolve=None):
    """Recorded IDs onto the installed registry: current IDs stay, legacy object IDs
    fold through the registry's own aliases (graph 3.0, never guessed), the rest
    are unknown and go to the mapping proposals. Sorted, so the projection is stable."""
    kept, unknown = set(), set()
    for value in values:
        target = value if value in allowed_ids else (resolve(value) if resolve else None)
        (unknown if target is None else kept).add(value if target is None else target)
    return sorted(kept), sorted(unknown)


def project_document(doc, sources, report, allowed, resolve=None, source_metadata=None):
    """Everything one document contributes to a snapshot, from its inputs alone."""
    resolvers = {key: (resolve if key == "object_ids" else None) for key in allowed}
    mapped, missing = {}, {}
    for key in allowed:
        mapped[key], missing[key] = fold_ids(report.get(key, []), allowed[key], resolvers[key])
    needs_review = any(missing.values()) or not any(mapped.values())
    entry = {"id": doc["doc_id"], "doc_id": doc["doc_id"], "content_sha256": doc["sha256"],
             "title": report.get("classification", {}).get("title") or doc["original_name"],
             "stored_path": doc["original_rel"], "sources": sources, "library_path": doc["library_rel"],
             "coverage": report.get("coverage", {"complete": False, "chunks_total": doc["chunks_total"], "chunks_read": doc["chunks_read"]}),
             "read_status": doc["state"], "mapping_status": "needs_review" if needs_review else "candidate_mapped",
             "reading_revision_id": doc["revision_id"] if doc["report_rel"] else None,
             "report_sha256": doc["report_sha256"],
             "model": report.get("model"), "status": "candidate", "acceptance": "candidate", **mapped}
    if source_metadata is not None:
        entry.update(source_metadata)
    if report.get('published_date') or report.get('classification', {}).get('published_date'):
        entry['published_date'] = report.get('published_date') or report['classification']['published_date']
    evidence_out = []
    for evidence in report.get("evidence", []):
        ids = {key: fold_ids(evidence.get(key, []), allowed[key], resolvers[key])[0] for key in allowed}
        page = evidence.get('page_index')
        # Reader artifact v1 uses PDF page numbers (1..N). The knowledge
        # contract uses array indices (0..N-1). Convert only at this boundary;
        # old immutable reports keep their original locator and numbering.
        if type(page) is not int or not 1 <= page <= report.get('coverage', {}).get('pages_total', 0):
            raise IntegrityError()
        evidence_out.append({**evidence, "page_index": page - 1, "document_id": doc["doc_id"], **ids,
                             "status": "candidate", "acceptance": "candidate"})
    statements = []
    for n, claim in enumerate(report.get("claims", [])):
        ids = {key: fold_ids(claim.get(key, []), allowed[key], resolvers[key])[0] for key in allowed}
        statements.append({**claim, "id": claim.get("id") or doc["doc_id"] + ":statement:" + str(n),
                           "document_id": doc["doc_id"], **ids,
                           "status": "candidate", "acceptance": "candidate"})
    proposal = None
    if needs_review:
        proposal = {"doc_id": doc["doc_id"], "unknown_ids": missing,
                    "classification": report.get("classification"), "reason": "unmapped_or_registry_changed"}
    return {"entry": entry, "evidence": evidence_out, "statements": statements, "proposal": proposal}


def _validate_doc_ids(doc_ids):
    if (not isinstance(doc_ids, (list, tuple)) or not doc_ids
            or any(not isinstance(value, str) or not re.fullmatch(r"doc-[0-9a-f]{64}", value)
                   for value in doc_ids)
            or len(set(doc_ids)) != len(doc_ids)):
        raise ValueError("scoped export requires unique full document IDs")
    return list(doc_ids)


def export_snapshot(conn, data, registry, status, cache_root=None, verify=None, doc_ids=None):
    """Web is a rebuildable projection; old reading artifacts retain their versions.

    Revalidate the ID projection against the currently installed registry. Unknown
    IDs stay in a local proposal file; they never make a whole web batch invalid.

    Each document's contribution depends only on its catalog row, its sources and
    its report; a projection cache keyed by all three lets an unchanged document
    skip re-hashing and re-parsing its report. That is what makes this finish:
    the Spark catalog reached 32,734 documents, and re-reading every report on a
    five-minute timer cannot complete inside the unit's TimeoutStartSec.
    Pass verify=True (or READER_PUBLISH_VERIFY=1) to bypass the cache and
    re-verify every report's digest — see docs/local_reader/SPARK_OPERATIONS.md.
    """
    allowed = {"object_ids": {r["id"] for r in registry["objects"] if isinstance(r, dict) and "id" in r},
               "question_ids": {r["id"] for r in registry["questions"] if isinstance(r, dict) and "id" in r}}
    registry_key = [registry["graph_version"], registry["questions_version"]]
    resolve = object_resolver(registry["objects"], registry.get("legacy_root_prefixes"))
    if verify is None:
        verify = os.environ.get("READER_PUBLISH_VERIFY") == "1"
    if doc_ids is not None:
        doc_ids = _validate_doc_ids(doc_ids)
        placeholders = ",".join("?" for _ in doc_ids)
        rows = conn.execute("SELECT * FROM current_readings WHERE doc_id IN (%s) ORDER BY created,doc_id" % placeholders,
                            tuple(doc_ids)).fetchall()
        if len(rows) != len(doc_ids):
            raise ValueError("scoped export references an unknown current document")
    else:
        rows = conn.execute("SELECT * FROM current_readings ORDER BY created,doc_id").fetchall()
    cache = None if verify else projection_cache(cache_root)
    # One query for every document's sources; the per-document query this replaces
    # was one round trip per row and dominated the export at catalog scale.
    grouped = {}
    for row in conn.execute("SELECT doc_id,source_key,version_seq,previous_doc_id,received "
                            "FROM sources ORDER BY doc_id,received,id"):
        source = dict(row)
        grouped.setdefault(source.pop("doc_id"), []).append(source)
    knowledge = {"documents": [], "evidence": [], "statements": [], "answers": []}
    source_metadata = supplied_sources(data)
    proposals = []
    try:
        for row in rows:
            doc = dict(row)
            sources = grouped.get(doc["doc_id"], [])
            provenance = source_metadata.get(doc['sha256'])
            key = fingerprint(doc, sources, registry_key, provenance)
            piece = None
            if cache is not None:
                hit = cache.execute("SELECT payload FROM projection WHERE doc_id=? AND fingerprint=?",
                                    (doc["doc_id"], key)).fetchone()
                if hit is not None:
                    piece = json.loads(hit[0])
            if piece is None:
                piece = project_document(doc, sources, read_report(data, doc), allowed, resolve, provenance)
                if cache is not None:
                    cache.execute("INSERT OR REPLACE INTO projection VALUES(?,?,?)",
                                  (doc["doc_id"], key, encoded(piece)))
            knowledge["documents"].append(piece["entry"])
            knowledge["evidence"].extend(piece["evidence"])
            knowledge["statements"].extend(piece["statements"])
            if piece["proposal"] is not None:
                proposals.append(piece["proposal"])
    finally:
        if cache is not None:
            cache.close()
    if doc_ids is not None and any(entry.get("coverage", {}).get("complete") is not True
                                   for entry in knowledge["documents"]):
        raise ValueError("scoped candidate export requires complete coverage for every selected document")
    if doc_ids is None:
        atomic_json(safe_path(data, "candidates/mapping-proposals.json"), {"generated": now_iso(), "acceptance": "candidate", "records": proposals})
    from inresearch.workflow.research_review import progress as review_progress
    status['research_verification']=review_progress(data)
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
