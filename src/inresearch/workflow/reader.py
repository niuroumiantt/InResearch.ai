#!/usr/bin/env python3
"""Persistent research reader; one queue owner, optionally several worker threads. Source bytes and candidate artifacts never expire.

No core facts are written. Production inference uses a configured Claude CLI, Ollama
model or gateway route; tests inject a Python model object instead of a fake CLI mode.

One process owns the queue (an exclusive lock on the catalog), so interrupted-job
recovery and reconciliation still happen exactly once. Inside that process the
worker loop may run in several threads: each thread owns its own SQLite connection
and claims its own job, and SQLite's BEGIN IMMEDIATE keeps a job from being claimed
twice. Throughput past a couple of threads needs the Ollama server to serve requests
in parallel (OLLAMA_NUM_PARALLEL); otherwise the requests only queue there instead.
"""
from __future__ import annotations

from inresearch.paths import project_root

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time

from inresearch.materials.reader_contracts import ReaderError, Blocked, Deferred, UnsafePath, IntegrityError, RECIPE_VERSION, OCR_DEFERRED_PRIORITY, OCR_MAX_PAGES, OCR_DEFER_SECONDS, LARGE_FORMAT_POINTS, MAX_WORKERS, MODULES, THERMAL_LIMIT_C, THERMAL_PAUSE_SECONDS, THERMAL_SAMPLE_SECONDS, PARKED_BY_TRIAGE, PARK_REASONS, OCR_BLOCK_CODES, CLAIM_MIN_PRIORITY
from inresearch.materials.artifacts import now_iso, encoded, digest_bytes, digest_file, private_dir, safe_path, atomic_json, durable_rename, read_json, clean_name, signature, is_partial
from inresearch.adapters.reader_model import ModelClient
from inresearch.storage.catalog import Catalog
from inresearch.workflow.reading_revisions import ReadingRevisions
from inresearch.workflow.reading_stages import ReadingStages
from inresearch.delivery import reader_export as reader_delivery
from inresearch.adapters import models

MODEL = models.load_profile(path=models.DEFAULT_CONFIG).model
CONTEXT = models.load_profile(path=models.DEFAULT_CONFIG).context
# OCR is the expensive path (render + two vision passes per page). Scanned documents
# are read after text-layer documents, capped per document, and large-format pages
# (engineering drawings) are left to a dedicated drawing workflow instead of OCR.


class Reader:
    def __init__(self, data_root=None, state_root=None, repo_root=None, model=None,
                 stable_seconds=60, chunk_chars=6000, clock=time.time, temperature=None,
                 full_read_min_priority=1, claim_min_priority=0):
        self.data = Path(data_root or Path.home() / ".local/share/inresearch.ai").expanduser().resolve()
        self.state = Path(state_root or Path.home() / ".local/state/inresearch.ai").expanduser().resolve()
        self.repo = Path(repo_root or project_root()).expanduser().resolve()
        self.model = model or ModelClient()
        self.stable_seconds, self.chunk_chars, self.clock = stable_seconds, chunk_chars, clock
        self.ocr_max_pages, self.ocr_defer_seconds, self.large_format_points = OCR_MAX_PAGES, OCR_DEFER_SECONDS, LARGE_FORMAT_POINTS
        # temperature() -> Celsius or None. Without a sensor source the guard is off.
        self.temperature, self.thermal_limit, self.thermal_pause = temperature, THERMAL_LIMIT_C, THERMAL_PAUSE_SECONDS
        self.thermal = {"limit_c": THERMAL_LIMIT_C, "last_c": None, "paused_since": None, "pauses": 0}
        self._thermal_lock, self._thermal_cool_until = threading.Lock(), 0.0
        # Below this effective priority a document is read at summary depth. The
        # library default (1) reads everything in full; `reader run` passes the
        # configured threshold.
        if type(full_read_min_priority) is not int or not 1 <= full_read_min_priority <= 10:
            raise ValueError("full_read_min_priority must be an integer 1..10")
        self.full_read_min_priority = full_read_min_priority
        if type(claim_min_priority) is not int or not 0 <= claim_min_priority <= 10:
            raise ValueError("claim_min_priority must be an integer 0..10")
        self.claim_min_priority = claim_min_priority
        if stable_seconds < 0 or not 1 <= chunk_chars <= 6000:
            raise ValueError("invalid scan stability or chunk size")
        self.catalog = None
        self.stages = ReadingStages(self.data, self.model, self.ocr_max_pages, self.large_format_points)

    @property
    def conn(self):
        return self.catalog.conn if self.catalog else None

    def transaction(self):
        return self.catalog.transaction()

    def close(self):
        if self.catalog:
            self.catalog.close()

    def artifact_path(self, doc_id, name):
        return self.stages.artifact_path(self.doc(doc_id), name)

    def export(self, dest, doc_ids=None):
        with self.catalog.read_snapshot():
            return reader_delivery.export(dest, self.conn, self.data, self.snapshot(), self.status(), doc_ids=doc_ids)

    def export_snapshot(self, verify=None, doc_ids=None):
        # The projection cache lives beside the other state; it is rebuildable,
        # so it stays out of the catalog and out of any backup contract.
        # verify=True re-reads and re-verifies every report's digest.
        with self.catalog.read_snapshot():
            return reader_delivery.export_snapshot(self.conn, self.data, self.snapshot(), self.status(),
                                                   cache_root=self.state, verify=verify, doc_ids=doc_ids)

    def backup(self, dest):
        return reader_delivery.backup(dest, self.conn, self.data, self.state)

    def initialize(self):
        for p in (self.data, self.state):
            private_dir(p)
        for name in ("raw-materials", "originals", "library", "extracted", "artifacts", "candidates", "indexes", "catalog", "intake-receipts"):
            private_dir(safe_path(self.data, name))
        db = safe_path(self.data, "catalog/catalog.sqlite")
        fd = os.open(str(db), os.O_CREAT | os.O_RDWR, 0o600)
        os.fchmod(fd, 0o600)
        os.close(fd)
        self.catalog = Catalog(db)
        try:
            self.catalog.initialize()
        except BaseException:
            self.catalog.close()
            raise
        from inresearch.workflow.research_match import reading_objective
        self.revisions = ReadingRevisions(self.catalog, self.stages, self.snapshot, self.chunk_chars, self.clock,
                                         objective=lambda sha: reading_objective(self.data, self.repo, sha))
        return self


    @contextmanager
    def worker_session(self):
        # The lock follows the catalog even if a caller selects a different log root.
        lock_path = safe_path(self.data, "catalog/reader.worker.lock")
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.transaction():
                self.conn.execute("UPDATE jobs SET state=CASE WHEN attempts>=max_attempts THEN 'failed' ELSE 'pending' END, error_code='worker_interrupted',available=? WHERE state='running'", (self.clock(),))
                self.conn.execute("UPDATE reading_runs SET state='queued' WHERE state='running'")
                self._refresh_failures()
            self.reconcile_operations()
            self.reconcile_intake()
            yield
        finally:
            os.close(fd)

    def doc(self, doc_id, revision_id=None):
        return self.catalog.reading(doc_id, revision_id)

    def _refresh_failures(self, doc_id=None):
        rows = self.conn.execute("SELECT revision_id,state,error_code FROM jobs WHERE state IN ('blocked','failed') AND (? IS NULL OR doc_id=?) ORDER BY CASE state WHEN 'blocked' THEN 1 ELSE 0 END", (doc_id, doc_id)).fetchall()
        for row in rows:
            self.conn.execute("UPDATE reading_runs SET state=?,error_code=? WHERE revision_id=?", (row["state"], row["error_code"], row["revision_id"]))

    def snapshot(self):
        out = {"graph_version": None, "questions_version": None, "objects": [], "questions": [], "legacy_root_prefixes": []}
        for fn, records, target, version in (("research_graph.json", "objects", "objects", "graph_version"),
                                             ("research_questions.json", "records", "questions", "questions_version")):
            p = self.repo / "framework" / fn
            try:
                value = read_json(p)
                if not isinstance(value.get(records), list):
                    continue
                out[target] = [r for r in value[records] if not (target == "objects" and r.get("navigation_hidden"))]
                out[version] = value.get("version")
                if target == "objects":
                    out["legacy_root_prefixes"] = [p for p in (value.get("legacy_root_prefixes") or []) if isinstance(p, str)]
            except (OSError, ValueError, AttributeError):
                continue
        out["snapshot_hash"] = digest_bytes(encoded(out).encode())
        return out

    def _enqueue(self, doc, stage, chunk=0):
        self.catalog.enqueue(doc, stage, self.clock(), chunk)

    def _register(self, source, rel, sig):
        # Stage the bytes first, then verify source metadata before archiving them.
        if shutil.disk_usage(self.data).free < source.stat().st_size + 128 * 1024 * 1024:
            raise Blocked("insufficient_archive_space")
        staging = private_dir(safe_path(self.data, "originals/.receiving"))
        fd, temp_name = tempfile.mkstemp(prefix="incoming-", suffix=".partial", dir=str(staging))
        tmp = Path(temp_name)
        h = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as dest:
                before = signature(source)
                if before != sig or source.is_symlink():
                    raise IntegrityError()
                with source.open("rb") as src:
                    for block in iter(lambda: src.read(1024 * 1024), b""):
                        h.update(block)
                        dest.write(block)
                    dest.flush()
                    os.fsync(dest.fileno())
            if signature(source) != before:
                raise IntegrityError()
            sha = h.hexdigest()
            if digest_file(source) != sha or signature(source) != before:
                raise IntegrityError()
            doc_id = "doc-" + sha
            existing = self.conn.execute("SELECT * FROM documents WHERE sha256=?", (sha,)).fetchone()
            orig_rel = existing["original_rel"] if existing else "originals/%s/%s/%s" % (sha[:2], sha, clean_name(source.name, 180))
            target = safe_path(self.data, orig_rel)
            private_dir(target.parent)
            if target.exists():
                if digest_file(target) != sha:
                    raise IntegrityError()
            else:
                durable_rename(tmp, target)
                os.chmod(target, 0o400)
            with self.transaction():
                self.conn.execute("INSERT OR IGNORE INTO documents(doc_id,sha256,original_name,original_rel,suffix,size_bytes,created) VALUES(?,?,?,?,?,?,?)",
                                  (doc_id, sha, source.name, orig_rel, source.suffix.lower(), target.stat().st_size, self.clock()))
                if not existing:
                    identity = dict(self.conn.execute('SELECT * FROM documents WHERE doc_id=?',(doc_id,)).fetchone())
                    self.revisions.create(identity)
                else:
                    prior_run = self.doc(doc_id)
                    if prior_run['state']=='queued' and prior_run['phase'] in ('extract','triage'):
                        objective = self.revisions.objective(sha)
                        floor = objective.get('demand_priority',5)
                        if floor>=7 and floor>prior_run['priority']:
                            self.conn.execute('UPDATE reading_runs SET priority=? WHERE revision_id=?',(floor,prior_run['revision_id']))
                            key='research-demand-priority:'+prior_run['revision_id']
                            audit=self.conn.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
                            history=json.loads(audit['value']) if audit else []
                            history.append({'at':now_iso(),'previous':prior_run['priority'],'priority':floor,
                                            'targets_sha256':objective['targets_sha256'],
                                            'target_ids':[t['id'] for t in objective['research_demands']],
                                            'reason':'new supplied material matches current demand; frozen reading recipe retained'})
                            self.conn.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(key,encoded(history)))
                prior = self.conn.execute("SELECT * FROM sources WHERE source_key=? ORDER BY version_seq DESC LIMIT 1", (rel,)).fetchone()
                if not prior or prior["signature"] != sig:
                    self.conn.execute("INSERT INTO sources(source_key,doc_id,version_seq,previous_doc_id,signature,received) VALUES(?,?,?,?,?,?)",
                                      (rel, doc_id, prior["version_seq"] + 1 if prior else 1, prior["doc_id"] if prior else None, sig, self.clock()))
                self.conn.execute("UPDATE observations SET registered_signature=? WHERE source_key=?", (sig, rel))
                if existing and self.doc(doc_id)["report_rel"] and existing["library_rel"]:
                    self._queue_receipts(self.doc(doc_id))
            return not bool(existing)
        finally:
            if tmp.exists():
                tmp.unlink()

    def scan(self, max_register=32):
        raw = safe_path(self.data, "raw-materials")
        counts = {"seen": 0, "registered": 0, "duplicates": 0, "waiting": 0, "errors": 0}
        for base, dirs, files in os.walk(str(raw), followlinks=False):
            dirs[:] = [d for d in sorted(dirs) if not is_partial(d) and not (Path(base) / d).is_symlink()]
            for name in sorted(files):
                p = Path(base) / name
                rel = p.relative_to(raw).as_posix()
                if is_partial(rel) or p.is_symlink() or not p.is_file():
                    continue
                counts["seen"] += 1
                try:
                    safe_path(raw, rel)
                    sig = signature(p)
                    seen = self.conn.execute("SELECT * FROM observations WHERE source_key=?", (rel,)).fetchone()
                    if not seen or seen["signature"] != sig:
                        self.conn.execute("INSERT INTO observations(source_key,signature,stable_since) VALUES(?,?,?) ON CONFLICT(source_key) DO UPDATE SET signature=excluded.signature,stable_since=excluded.stable_since,registered_signature=NULL", (rel, sig, self.clock()))
                        if self.stable_seconds > 0:
                            counts["waiting"] += 1
                            continue
                        seen = self.conn.execute("SELECT * FROM observations WHERE source_key=?", (rel,)).fetchone()
                    if seen["registered_signature"] == sig:
                        continue
                    if self.clock() - seen["stable_since"] < self.stable_seconds:
                        counts["waiting"] += 1
                        continue
                    if counts["registered"] + counts["duplicates"] >= max_register:
                        counts["waiting"] += 1
                        continue
                    added = self._register(p, rel, sig)
                    counts["registered" if added else "duplicates"] += 1
                except (OSError, ReaderError):
                    counts["errors"] += 1
        self.conn.execute("INSERT OR REPLACE INTO meta VALUES ('last_scan',?)", (encoded({"at": now_iso(), **counts}),))
        return counts


    def _link_target(self, doc):
        report = read_json(self.stages.artifact_path(doc, "report.json"))
        cls = report["classification"]
        node = cls.get('node')
        module = ('by-node/'+clean_name(node.replace(':','-'),100)) if node else (cls["module_id"] if cls["module_id"] in MODULES else "_unmapped")
        name = "_".join(clean_name(cls.get(k), n) for k, n in (("year", 8), ("org", 25), ("title", 55)))
        name = clean_name(name, 180)
        name += "__" + doc["sha256"][:16] + doc["suffix"]
        return "library/%s/%s" % (module, name)

    def _apply_link(self, operation):
        source = safe_path(self.data, operation["source_rel"])
        target = safe_path(self.data, operation["target_rel"], leaf_link=True)
        if not operation["target_rel"].startswith("library/") or not operation["source_rel"].startswith("originals/"):
            raise UnsafePath()
        if digest_file(source) != self.doc(operation["doc_id"])["sha256"]:
            raise IntegrityError()
        private_dir(target.parent)
        if target.is_symlink():
            if target.resolve() != source.resolve():
                raise UnsafePath()
        elif target.exists():
            raise UnsafePath()
        else:
            os.symlink(os.path.relpath(str(source), str(target.parent)), str(target))
        if target.resolve() != source.resolve():
            raise IntegrityError()
        with self.transaction():
            self.conn.execute("UPDATE operations SET state='committed',updated=? WHERE operation_id=?", (self.clock(), operation["operation_id"]))
            self.conn.execute("UPDATE documents SET library_rel=? WHERE doc_id=?", (operation["target_rel"], operation["doc_id"]))

    def place_in_library(self, doc_id, original_rel, relative, op_id):
        """Journal one library view link and commit it through the verified path.

        The caller decides where the document belongs; this decides nothing and
        verifies everything, so a placement imported from another machine gets
        the same digest check, the same journal and the same rollback as one
        this reader derived itself. None means the operation was rolled back.
        """
        self.conn.execute("INSERT OR IGNORE INTO operations VALUES(?,?,?,?,?,?,?)",
                          (op_id, doc_id, relative, original_rel, "prepared", self.clock(), self.clock()))
        operation = dict(self.conn.execute("SELECT * FROM operations WHERE operation_id=?", (op_id,)).fetchone())
        if operation["state"] == "rolled_back":
            return None
        self._apply_link(operation)
        return relative

    def _organize(self, doc):
        relative = self._link_target(doc)
        op_id = "organize:" + doc["doc_id"] + ":" + doc["recipe"]
        placed = self.place_in_library(doc["doc_id"], doc["original_rel"], relative, op_id)
        if placed is None:
            return {"library_rel": None, "state": "rolled_back"}
        return {"library_rel": relative, "state": "committed"}

    def reconcile_operations(self):
        for row in self.conn.execute("SELECT * FROM operations WHERE state IN ('prepared','committed')").fetchall():
            try:
                if row["state"] == "committed":
                    target = safe_path(self.data, row["target_rel"], leaf_link=True)
                    source = safe_path(self.data, row["source_rel"])
                    if target.is_symlink() and target.resolve() == source.resolve() and source.is_file():
                        continue
                self._apply_link(dict(row))
            except (OSError, ReaderError):
                self.conn.execute("UPDATE operations SET state='needs_review',updated=? WHERE operation_id=?", (self.clock(), row["operation_id"]))
                self.conn.execute("UPDATE reading_runs SET state='blocked',error_code='organize_recovery_requires_review' WHERE doc_id=? AND base_revision_id IS NULL", (row["doc_id"],))
                self.conn.execute("UPDATE jobs SET state='blocked',error_code='organize_recovery_requires_review' WHERE doc_id=? AND stage='organize'", (row["doc_id"],))

    def rollback(self, doc_id):
        doc = self.doc(doc_id)
        for row in self.conn.execute("SELECT * FROM operations WHERE doc_id=? AND state='committed'", (doc_id,)).fetchall():
            target = safe_path(self.data, row["target_rel"], leaf_link=True)
            source = safe_path(self.data, row["source_rel"])
            if not row["target_rel"].startswith("library/"):
                raise UnsafePath()
            if target.is_symlink() and target.resolve() == source.resolve():
                target.unlink()  # Only our verified view link, never source bytes.
            elif target.exists() or target.is_symlink():
                raise UnsafePath()
            with self.transaction():
                self.conn.execute("UPDATE operations SET state='rolled_back',updated=? WHERE operation_id=?", (self.clock(), row["operation_id"]))
                self.conn.execute("UPDATE documents SET library_rel=NULL WHERE doc_id=?", (doc_id,))
        return {"doc_id": doc_id, "view_rolled_back": True, "source_preserved": safe_path(self.data, doc["original_rel"]).exists()}

    def _queue_receipts(self, doc):
        doc = dict(self.conn.execute('SELECT * FROM execution_readings WHERE doc_id=? AND base_revision_id IS NULL',(doc['doc_id'],)).fetchone())
        for row in self.conn.execute("SELECT id FROM sources WHERE doc_id=?", (doc["doc_id"],)).fetchall():
            self._enqueue(doc, "receipt", row["id"])

    def _receipt(self, doc, source_id):
        source = self.conn.execute("SELECT * FROM sources WHERE id=? AND doc_id=?", (source_id, doc["doc_id"])).fetchone()
        if not source:
            raise IntegrityError()
        if not self.conn.execute("SELECT 1 FROM operations WHERE doc_id=? AND state='committed'", (doc["doc_id"],)).fetchone():
            raise Blocked("receipt_requires_committed_library")
        op_id = "intake:%d" % source_id
        quarantine = "raw-materials/.reader-intake/%d-%s.partial" % (source_id, doc["sha256"])
        receipt = "intake-receipts/received/%s/%d-%s" % (doc["sha256"], source_id, clean_name(Path(source["source_key"]).name, 160))
        self.conn.execute("INSERT OR IGNORE INTO intake_operations VALUES(?,?,?,?,?,?,?,?,?,?,NULL)",
                          (op_id, source_id, doc["doc_id"], "raw-materials/" + source["source_key"], quarantine, receipt,
                           source["signature"], "prepared", self.clock(), self.clock()))
        operation = dict(self.conn.execute("SELECT * FROM intake_operations WHERE operation_id=?", (op_id,)).fetchone())
        return self._apply_receipt(operation)

    def _intake_state(self, operation, state, error=None):
        self.conn.execute("UPDATE intake_operations SET state=?,updated=?,error_code=? WHERE operation_id=?",
                          (state, self.clock(), error, operation["operation_id"]))
        return {"source_id": operation["source_id"], "state": state, "receipt_rel": operation["receipt_rel"] if state == "committed" else None}

    def _apply_receipt(self, operation):
        """Move only the verified receiving copy. Every byte remains in originals or receipts.

        prepared -> hidden quarantine -> hash/stat check -> permanent receipt. The
        recorded paths make every rename recoverable, including a concurrent upload.
        """
        if operation["state"] in {"committed", "superseded", "source_missing", "changed_restored"}:
            return {"source_id": operation["source_id"], "state": operation["state"]}
        if operation["state"] == "needs_review":
            raise Blocked("intake_changed_bytes_retained_requires_review")
        for field, prefix in (("source_rel", "raw-materials/"), ("quarantine_rel", "raw-materials/.reader-intake/"),
                              ("receipt_rel", "intake-receipts/received/")):
            if not operation[field].startswith(prefix):
                raise UnsafePath()
        raw = safe_path(self.data, operation["source_rel"])
        quarantine = safe_path(self.data, operation["quarantine_rel"])
        receipt = safe_path(self.data, operation["receipt_rel"])
        doc = self.doc(operation["doc_id"])
        original = safe_path(self.data, doc["original_rel"])
        if digest_file(original) != doc["sha256"]:
            raise IntegrityError()
        if receipt.exists():
            if digest_file(receipt) != doc["sha256"] or quarantine.exists():
                raise IntegrityError()
            return self._intake_state(operation, "committed")
        if not quarantine.exists():
            if not raw.exists():
                return self._intake_state(operation, "source_missing")
            if signature(raw) != operation["expected_signature"] or digest_file(raw) != doc["sha256"]:
                return self._intake_state(operation, "superseded")
            private_dir(quarantine.parent)
            durable_rename(raw, quarantine)
            self._intake_state(operation, "quarantined")
        before = signature(quarantine)
        matches = digest_file(quarantine) == doc["sha256"] and signature(quarantine) == before
        if not matches:
            if not raw.exists() and not raw.is_symlink():
                durable_rename(quarantine, raw)
                return self._intake_state(operation, "changed_restored", "receiving_copy_changed")
            self._intake_state(operation, "needs_review", "changed_bytes_retained_in_quarantine")
            raise Blocked("intake_changed_bytes_retained_requires_review")
        private_dir(receipt.parent)
        durable_rename(quarantine, receipt)
        os.chmod(receipt, 0o400)
        if digest_file(receipt) != doc["sha256"]:
            self._intake_state(operation, "needs_review", "changed_bytes_retained_in_receipt")
            raise Blocked("intake_changed_bytes_retained_requires_review")
        return self._intake_state(operation, "committed")

    def reconcile_intake(self):
        for row in self.conn.execute("SELECT * FROM intake_operations WHERE state IN ('prepared','quarantined')").fetchall():
            try:
                self._apply_receipt(dict(row))
            except (OSError, ReaderError):
                # Keep all bytes and the operation for an explicit retry/review.
                self.conn.execute("UPDATE reading_runs SET state='blocked',error_code='intake_recovery_requires_review' WHERE doc_id=? AND base_revision_id IS NULL", (row["doc_id"],))
                self.conn.execute("UPDATE jobs SET state='blocked',error_code='intake_recovery_requires_review' WHERE doc_id=? AND stage='receipt' AND chunk=?", (row["doc_id"], row["source_id"]))

    def claim(self):
        # Independent news service share. This is an ordering hint, never a
        # coverage shortcut, recipe rewrite, importance/C3 score or extra worker.
        from inresearch.workflow.daily_dispatch import fast_reading_shas
        try: fast = fast_reading_shas(self.data)
        except (OSError, ValueError, KeyError, TypeError): fast = []
        with self.transaction():
            n = int(self.conn.execute("SELECT value FROM meta WHERE key='dispatch_count'").fetchone()[0])
            # Every fourth dispatch serves the oldest eligible job, independently of new priorities.
            order = "j.created,j.doc_id,j.chunk,j.job_id" if n % 4 == 0 else "d.priority DESC,j.created,j.doc_id,j.chunk,j.job_id"
            # The oldest-first turn also respects the floor: held documents wait, they do not starve the rest.
            base = "SELECT j.* FROM jobs j JOIN reading_runs d ON d.revision_id=j.revision_id JOIN documents original ON original.doc_id=d.doc_id WHERE j.state='pending' AND j.available<=? AND d.state NOT IN ('blocked','failed') AND d.priority>=?"
            params = (self.clock(), self.claim_min_priority)
            row = None
            lane = 'oldest' if n % 4 == 0 else 'priority'
            if n % 4 == 1:
                row = self.conn.execute(base + " AND j.stage IN ('synthesize','organize','receipt') ORDER BY CASE j.stage WHEN 'receipt' THEN 0 WHEN 'organize' THEN 1 ELSE 2 END,d.priority DESC,j.created,j.job_id LIMIT 1", params).fetchone()
                if row: lane = 'finish'
            if row is None and n % 4 in (1, 2) and fast:
                placeholders = ','.join('?' for _ in fast)
                row = self.conn.execute(base + " AND original.suffix IN ('.html','.htm') AND original.sha256 IN (" + placeholders + ") ORDER BY CASE WHEN d.chunks_total>0 THEN MAX(0,d.chunks_total-d.chunks_read) ELSE 100000 END,j.created,j.doc_id,j.chunk,j.job_id LIMIT 1", (*params, *fast)).fetchone()
                if row: lane = 'news'
            if row is None:
                row = self.conn.execute(base + " ORDER BY " + order + " LIMIT 1", params).fetchone()
            if not row:
                return None
            self.conn.execute("UPDATE jobs SET state='running',attempts=attempts+1,started=?,error_code=NULL WHERE job_id=?", (self.clock(), row["job_id"]))
            self.conn.execute("UPDATE reading_runs SET state='running',phase=?,updated=? WHERE revision_id=?", (row["stage"], self.clock(), row["revision_id"]))
            self.conn.execute("UPDATE meta SET value=? WHERE key='dispatch_count'", (str(n + 1),))
            self.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('last_dispatch',?)", (json.dumps({'lane':lane,'job_id':row['job_id'],'doc_id':row['doc_id'],'at':now_iso()}),))
            return dict(self.conn.execute("SELECT * FROM jobs WHERE job_id=?", (row["job_id"],)).fetchone())

    def _finish(self, job, result):
        doc = self.doc(job["doc_id"], job["revision_id"])
        stage = job["stage"]
        with self.transaction():
            cur = self.conn.execute("UPDATE jobs SET state='succeeded',finished=? WHERE job_id=? AND state='running' AND attempts=?", (self.clock(), job["job_id"], job["attempts"]))
            if cur.rowcount != 1:
                raise IntegrityError()
            self.conn.execute("UPDATE reading_runs SET state='queued',error_code=NULL,updated=? WHERE revision_id=?", (self.clock(), doc["revision_id"]))
            if stage == "extract":
                self.conn.execute("UPDATE reading_runs SET pages_total=?,chunks_total=? WHERE revision_id=?", (result["pages_total"], result["chunks_total"], doc["revision_id"]))
                self._enqueue(doc, "triage")
            elif stage == "triage":
                # A higher priority set before triage (M4 L1, apply-triage, a named
                # document) is not lowered by the reader's own coarse preview.
                effective = max(doc["priority"], result["importance"])
                self.conn.execute("UPDATE reading_runs SET priority=? WHERE revision_id=?", (effective, doc["revision_id"]))
                for i in self.read_plan(doc["chunks_total"], effective):
                    self._enqueue(doc, "read", i)
            elif stage == "read":
                done = self.conn.execute("SELECT COUNT(*) FROM jobs WHERE revision_id=? AND stage='read' AND state='succeeded'", (doc["revision_id"],)).fetchone()[0]
                planned = self.conn.execute("SELECT COUNT(*) FROM jobs WHERE revision_id=? AND stage='read'", (doc["revision_id"],)).fetchone()[0]
                self.conn.execute("UPDATE reading_runs SET chunks_read=? WHERE revision_id=?", (done, doc["revision_id"]))
                if done == doc["chunks_total"]:
                    self._enqueue(doc, "synthesize")
                elif done == planned:
                    # Summary depth: the sampled chunks are read. No report, no current
                    # full-text result; `deepen` continues to a full reading.
                    self.conn.execute("UPDATE reading_runs SET state='summarized',phase='summary' WHERE revision_id=?", (doc["revision_id"],))
            elif stage == "synthesize":
                seal = result['_seal']
                self.conn.execute("UPDATE reading_runs SET report_rel=?,report_sha256=?,manifest_sha256=? WHERE revision_id=?",
                                  (seal['report_rel'],seal['report_sha256'],seal['manifest_sha256'],doc['revision_id']))
                if doc['base_revision_id'] is None:
                    self.conn.execute('UPDATE documents SET current_revision_id=? WHERE doc_id=? AND current_revision_id IS NULL',(doc['revision_id'],doc['doc_id']))
                    self.conn.execute("UPDATE reading_runs SET activated=?,review_json=? WHERE revision_id=?",(self.clock(),encoded({'kind':'initial_candidate_not_C3'}),doc['revision_id']))
                    self._enqueue(doc, "organize")
                else:
                    self.conn.execute("UPDATE reading_runs SET state='ready',phase='review' WHERE revision_id=?",(doc['revision_id'],))
            elif stage == "organize":
                self._queue_receipts(doc)
            elif stage == "receipt":
                remaining = self.conn.execute("SELECT COUNT(*) FROM jobs WHERE revision_id=? AND stage='receipt' AND state!='succeeded'", (doc["revision_id"],)).fetchone()[0]
                if not remaining:
                    self.conn.execute("UPDATE reading_runs SET state='complete',phase='complete' WHERE revision_id=?", (doc["revision_id"],))
            self._refresh_failures(doc["doc_id"])

    def process(self, job):
        doc = self.doc(job["doc_id"], job["revision_id"])
        # No silent backend/model change during a document's frozen execution recipe.
        try:
            recipe = read_json(self.stages.artifact_path(doc, "recipe.json"))
            # OCR availability may be added on retry; the actual OCR models are
            # captured per page. The configured reading identity stays frozen.
            identity = models.reading_identity
            if job["stage"] not in {"organize", "receipt"} and (identity(recipe["model"]) != identity(self.model.identity) or recipe["version"] != RECIPE_VERSION):
                raise Blocked("execution_model_changed_requires_new_recipe")
            funcs = {"extract": self.stages._extract, "triage": self.stages._triage, "synthesize": self.stages._synthesize, "organize": self._organize}
            if job["stage"] == "read":
                result = self.stages._read_chunk(doc, job["chunk"])
            elif job["stage"] == "receipt":
                result = self._receipt(doc, job["chunk"])
            else:
                result = funcs[job["stage"]](doc)
            if job["stage"] == "synthesize":
                result = {**result, "_seal": self.stages.seal(doc)}
            self._finish(job, result)
            self.write_status()
            return "succeeded"
        except (ReaderError, OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError) as exc:
            error = exc
        code = error.code if isinstance(error, ReaderError) else type(error).__name__
        if isinstance(error, Deferred):
            with self.transaction():
                cur = self.conn.execute("UPDATE jobs SET state='pending',attempts=attempts-1,available=?,error_code=? WHERE job_id=? AND state='running' AND attempts=?",
                                        (self.clock() + self.ocr_defer_seconds, code, job["job_id"], job["attempts"]))
                if cur.rowcount != 1:
                    raise IntegrityError()
                self.conn.execute("UPDATE reading_runs SET state='queued',priority=?,error_code=?,updated=? WHERE revision_id=?", (OCR_DEFERRED_PRIORITY, code, self.clock(), doc["revision_id"]))
            self.write_status()
            return "deferred"
        blocked = isinstance(error, (Blocked, UnsafePath, IntegrityError))
        terminal = blocked or job["attempts"] >= job["max_attempts"]
        state = "blocked" if blocked else ("failed" if terminal else "pending")
        delay = min(3600, 30 * 2 ** (job["attempts"] - 1))
        with self.transaction():
            cur = self.conn.execute("UPDATE jobs SET state=?,available=?,finished=?,error_code=? WHERE job_id=? AND state='running' AND attempts=?",
                                    (state, self.clock() + delay, self.clock() if terminal else None, code, job["job_id"], job["attempts"]))
            if cur.rowcount != 1:
                raise IntegrityError()
            self.conn.execute("UPDATE reading_runs SET state=?,error_code=?,updated=? WHERE revision_id=?", ("blocked" if blocked else ("failed" if terminal else "queued"), code, self.clock(), doc["revision_id"]))
            self._refresh_failures(doc["doc_id"])
        self.write_status()
        return state

    def requeue_offloaded(self):
        """Requeue OCR-blocked extractions that received M4 page results after their last attempt.

        Runs on the queue-owning thread, so M4 never needs the queue lock. A document
        is requeued once per new batch of results: a renewed block sets a later
        finish time than the uploaded pages."""
        root = safe_path(self.data, "offload/m4/results")
        if not root.is_dir():
            return 0
        placeholders = ",".join("?" * len(OCR_BLOCK_CODES))
        requeued = 0
        for directory in sorted(root.iterdir()):
            pages = directory / "pages"
            if directory.is_symlink() or not pages.is_dir():
                continue
            newest = max((p.stat().st_mtime for p in pages.glob("*.json")), default=None)
            if newest is None:
                continue
            row = self.conn.execute("SELECT revision_id,finished FROM jobs WHERE doc_id=? AND stage='extract' AND state='blocked' AND error_code IN (%s)" % placeholders,
                                    (directory.name, *OCR_BLOCK_CODES)).fetchone()
            if row is not None and newest > (row["finished"] or 0):
                requeued += self.retry(directory.name, row["revision_id"])["retried"]
        return requeued

    def read_plan(self, chunks_total, priority):
        """Chunk indexes to read: all of them, or the first, middle and last."""
        sample = sorted({0, chunks_total // 2, chunks_total - 1}) if chunks_total else []
        if priority >= self.full_read_min_priority or len(sample) >= chunks_total:
            return list(range(chunks_total))
        return sample

    def deepen(self, doc_ids):
        """Continue summary-depth readings to full coverage; cached chunks are reused."""
        out = {"deepened": [], "skipped": []}
        with self.transaction():
            for doc_id in doc_ids:
                row = self.conn.execute("SELECT * FROM reading_runs WHERE doc_id=? AND base_revision_id IS NULL", (doc_id,)).fetchone()
                if row is None or row["state"] != "summarized":
                    out["skipped"].append({"doc_id": doc_id, "state": row["state"] if row else "absent"})
                    continue
                run = dict(row)
                for i in range(run["chunks_total"]):
                    self._enqueue(run, "read", i)
                self.conn.execute("UPDATE reading_runs SET state='queued',phase='read',updated=? WHERE revision_id=?", (self.clock(), run["revision_id"]))
                out["deepened"].append(doc_id)
        return out

    def park(self, sha256s, commit=False, code=PARKED_BY_TRIAGE):
        """Park documents a triage judged unrelated (L1 score 0); nothing is deleted.

        Their pending work is blocked with PARKED_BY_TRIAGE, so the reader skips
        them and `retry --error-code` revives them. Finished, summarized, running
        and already-blocked readings are left alone. Without commit only the plan
        is returned."""
        if code not in PARK_REASONS.values():
            raise ValueError("unknown park reason")
        plan = {"park": 0, "absent": 0, "already_done": 0, "already_parked": 0, "already_blocked": 0}
        targets = []
        for sha in sha256s:
            row = self.conn.execute("SELECT * FROM reading_runs WHERE doc_id=? AND base_revision_id IS NULL", ("doc-" + sha,)).fetchone()
            if row is None:
                plan["absent"] += 1
            elif row["state"] in ("complete", "summarized", "ready", "running"):
                plan["already_done"] += 1
            elif row["error_code"] in PARK_REASONS.values():
                plan["already_parked"] += 1
            elif row["state"] == "blocked":
                # Keep the existing block reason (drawings, unsupported formats...).
                plan["already_blocked"] += 1
            else:
                plan["park"] += 1
                targets.append(row["revision_id"])
        if commit:
            with self.transaction():
                for revision in targets:
                    self.conn.execute("UPDATE jobs SET state='blocked',error_code=? WHERE revision_id=? AND state IN ('pending','failed')", (code, revision))
                    self.conn.execute("UPDATE reading_runs SET state='blocked',error_code=?,updated=? WHERE revision_id=?", (code, self.clock(), revision))
        return {"plan": plan, "reason": code, "committed": bool(commit)}

    def retry(self, doc_id=None, revision_id=None, error_code=None):
        """Re-queue failed or blocked work; every filter given must match.

        error_code exists because a code fix retires one class of block, not
        all of them. On 2026-09-18 this catalog held 10,101 blocked documents,
        of which 6,501 were CAD and large-format drawings that are blocked *by
        design* and would re-render, re-block and burn days on the way. An
        unfiltered retry after fixing one parser is therefore not thorough, it
        is a way to spend a week re-proving what the catalog already knows.
        """
        if doc_id:
            self.doc(doc_id, revision_id)
        selector = ("state IN ('failed','blocked') AND (? IS NULL OR doc_id=?)"
                    " AND (? IS NULL OR revision_id=?) AND (? IS NULL OR error_code=?)")
        where = (doc_id, doc_id, revision_id, revision_id, error_code, error_code)
        with self.transaction():
            rows = self.conn.execute("SELECT DISTINCT doc_id,revision_id FROM jobs WHERE " + selector, where).fetchall()
            cur = self.conn.execute("UPDATE jobs SET state='pending',attempts=0,available=?,error_code=NULL WHERE " + selector, (self.clock(),) + where)
            for row in rows:
                self.conn.execute("UPDATE reading_runs SET state='queued',error_code=NULL WHERE revision_id=?",(row['revision_id'],))
                self.conn.execute("UPDATE intake_operations SET state='prepared',error_code=NULL WHERE doc_id=? AND state='needs_review'",(row['doc_id'],))
        return {"retried": cur.rowcount}

    def status(self):
        counts = {row[0]: row[1] for row in self.conn.execute("SELECT state,COUNT(*) FROM current_readings GROUP BY state")}
        stages = [{"stage": r[0], "state": r[1], "count": r[2]} for r in self.conn.execute("SELECT stage,state,COUNT(*) FROM jobs GROUP BY stage,state ORDER BY stage,state")]
        failures = [dict(r) for r in self.conn.execute("SELECT doc_id,revision_id,original_name,phase,error_code FROM execution_readings WHERE error_code IS NOT NULL AND state!='rejected' ORDER BY updated DESC LIMIT 20")]
        pending = self.conn.execute("SELECT MIN(created) FROM jobs WHERE state='pending'").fetchone()[0]
        active = self.conn.execute("SELECT COUNT(*) FROM jobs WHERE state='running'").fetchone()[0]
        last_scan = self.conn.execute("SELECT value FROM meta WHERE key='last_scan'").fetchone()
        scan = json.loads(last_scan[0]) if last_scan else {}
        return {"schema_version": 1, "generated": now_iso(), "status": "degraded" if failures or scan.get("errors") else ("running" if active else "idle"),
                "counts": counts, "documents_total": sum(counts.values()),
                "reading_revisions": {r[0]:r[1] for r in self.conn.execute("SELECT state,COUNT(*) FROM reading_runs WHERE base_revision_id IS NOT NULL GROUP BY state")},
                "sources_total": self.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
                "stage_counts": stages, "oldest_pending_seconds": max(0, self.clock() - pending) if pending is not None else None,
                "oldest_pending": datetime.fromtimestamp(pending, timezone.utc).isoformat() if pending is not None else None,
                "recent_failures": failures, "backend": self.model.identity,
                "last_scan": scan, "thermal": dict(self.thermal),
                "claim_floor": {"min_priority": self.claim_min_priority,
                                "held_documents": self.conn.execute("SELECT COUNT(DISTINCT j.revision_id) FROM jobs j JOIN reading_runs d ON d.revision_id=j.revision_id WHERE j.state='pending' AND d.state NOT IN ('blocked','failed') AND d.priority<?", (self.claim_min_priority,)).fetchone()[0]},
                "roots": {"data": str(self.data), "state": str(self.state)},
                "acceptance": "candidate_only", "free_bytes": shutil.disk_usage(self.data).free}

    def write_status(self):
        status = self.status()
        atomic_json(safe_path(self.state, "status.json"), status)
        return status

    def cool_down(self, stop):
        """Hold the next claim while the machine is hotter than the limit.

        A job already running is never interrupted; the pause only gates the next
        claim. An unreadable sensor does not hold the queue."""
        if self.temperature is None or not self.thermal_limit > 0:
            return
        while not stop.is_set():
            with self._thermal_lock:
                # A cool reading stands for a few seconds so fast jobs do not each spawn nvidia-smi.
                if time.monotonic() < self._thermal_cool_until:
                    return
                celsius = self.temperature()
                hot = celsius is not None and celsius > self.thermal_limit
                self.thermal.update(limit_c=self.thermal_limit, last_c=celsius)
                if hot:
                    self.thermal["pauses"] += 1
                    self.thermal["paused_since"] = self.thermal["paused_since"] or now_iso()
                else:
                    self.thermal["paused_since"] = None
                    self._thermal_cool_until = time.monotonic() + THERMAL_SAMPLE_SECONDS
            if not hot:
                return
            print(encoded({"at": now_iso(), "thermal": "pause", "celsius": celsius,
                           "limit_c": self.thermal_limit, "seconds": self.thermal_pause}), flush=True)
            self.write_status()
            stop.wait(self.thermal_pause)

    def run(self, once=False, max_jobs=None, poll_seconds=10, workers=1):
        """One process owns the queue; `workers` threads claim and process jobs.

        Scanning stays on the owning thread so intake keeps its single writer.
        A worker's failure stops the others and is re-raised, as it would have
        ended the single-threaded loop."""
        if not isinstance(workers, int) or isinstance(workers, bool) or not 1 <= workers <= MAX_WORKERS:
            raise ValueError("workers must be an integer 1..%d" % MAX_WORKERS)
        counter = {"processed": 0, "idle": 0, "error": None}
        guard = threading.Lock()
        stop = threading.Event()

        def exhausted():
            return max_jobs is not None and counter["processed"] >= max_jobs

        def loop():
            try:
                while not stop.is_set():
                    with guard:
                        if exhausted():
                            stop.set()
                            break
                    self.cool_down(stop)
                    if stop.is_set():
                        break
                    # BEGIN IMMEDIATE inside claim() serializes the claim, so two
                    # threads never take the same job.
                    job = self.claim()
                    if job is None:
                        self.write_status()
                        with guard:
                            counter["idle"] += 1
                            # A running job still enqueues its next stage, so an
                            # empty queue only ends the drain once every worker
                            # is idle.
                            drained = counter["idle"] >= workers
                        if once and drained:
                            stop.set()
                            break
                        stop.wait(0.05 if once else poll_seconds)
                        with guard:
                            counter["idle"] -= 1
                        continue
                    self.write_status()
                    outcome = self.process(job)
                    print(encoded({"at": now_iso(), "doc_id": job["doc_id"], "stage": job["stage"],
                                   "chunk": job["chunk"], "outcome": outcome}), flush=True)
                    with guard:
                        counter["processed"] += 1
                        if exhausted():
                            stop.set()
            except BaseException as exc:  # noqa: BLE001 - reported to the owning thread
                with guard:
                    if counter["error"] is None:
                        counter["error"] = exc
                stop.set()
            finally:
                self.catalog._close_thread()

        with self.worker_session():
            self.requeue_offloaded()
            self.scan()
            threads = [threading.Thread(target=loop, name="reader-worker-%d" % i, daemon=True)
                       for i in range(workers)]
            for thread in threads:
                thread.start()
            try:
                if once:
                    # Workers stop themselves once the queue drains; setting the
                    # stop flag here would end them before they claim anything.
                    for thread in threads:
                        thread.join()
                else:
                    while not stop.wait(poll_seconds):
                        self.requeue_offloaded()
                        self.scan()
            finally:
                stop.set()
                for thread in threads:
                    thread.join()
            if counter["error"] is not None:
                raise counter["error"]
        return {"processed": counter["processed"], **self.write_status()}
