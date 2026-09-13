"""Thread-local SQLite connections and the durable catalog schema."""
from __future__ import annotations
import fcntl, hashlib, os, sqlite3, threading, uuid
from contextlib import contextmanager

DOCUMENTS = """
CREATE TABLE IF NOT EXISTS documents (
 doc_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, original_name TEXT NOT NULL,
 original_rel TEXT NOT NULL, suffix TEXT NOT NULL, size_bytes INTEGER NOT NULL,
 created REAL NOT NULL, library_rel TEXT, current_revision_id TEXT,
 FOREIGN KEY(doc_id,current_revision_id) REFERENCES reading_runs(doc_id,revision_id)
);
"""
RUNS = """
CREATE TABLE IF NOT EXISTS reading_runs (
 revision_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, base_revision_id TEXT,
 request_id TEXT NOT NULL, request_json TEXT NOT NULL, reason TEXT NOT NULL,
 recipe TEXT NOT NULL, artifact_rel TEXT NOT NULL, extracted_rel TEXT NOT NULL,
 created REAL NOT NULL, updated REAL NOT NULL,
 state TEXT NOT NULL DEFAULT 'queued', phase TEXT NOT NULL DEFAULT 'extract',
 priority INTEGER NOT NULL DEFAULT 5, pages_total INTEGER NOT NULL DEFAULT 0,
 chunks_total INTEGER NOT NULL DEFAULT 0, chunks_read INTEGER NOT NULL DEFAULT 0,
 report_rel TEXT, report_sha256 TEXT, manifest_sha256 TEXT, error_code TEXT, review_json TEXT, activated REAL,
 UNIQUE(doc_id,revision_id), UNIQUE(doc_id,request_id),
 FOREIGN KEY(doc_id) REFERENCES documents(doc_id),
 FOREIGN KEY(doc_id,base_revision_id) REFERENCES reading_runs(doc_id,revision_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_reading ON reading_runs(doc_id)
 WHERE base_revision_id IS NOT NULL AND state IN ('queued','running','blocked','failed','ready');
CREATE UNIQUE INDEX IF NOT EXISTS one_initial_reading ON reading_runs(doc_id) WHERE base_revision_id IS NULL;
"""
JOBS = """
CREATE TABLE IF NOT EXISTS jobs (
 job_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, revision_id TEXT NOT NULL,
 stage TEXT NOT NULL, chunk INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 3, available REAL NOT NULL, created REAL NOT NULL,
 started REAL, finished REAL, error_code TEXT, result_rel TEXT,
 UNIQUE(revision_id,stage,chunk),
 FOREIGN KEY(doc_id,revision_id) REFERENCES reading_runs(doc_id,revision_id)
);
CREATE INDEX IF NOT EXISTS job_pending ON jobs(state,available,created);
"""
AUXILIARY = """
CREATE TABLE IF NOT EXISTS sources (
 id INTEGER PRIMARY KEY, source_key TEXT NOT NULL, doc_id TEXT NOT NULL,
 version_seq INTEGER NOT NULL, previous_doc_id TEXT, signature TEXT NOT NULL,
 received REAL NOT NULL, UNIQUE(source_key,version_seq),
 FOREIGN KEY(doc_id) REFERENCES documents(doc_id)
);
CREATE TABLE IF NOT EXISTS observations (
 source_key TEXT PRIMARY KEY, signature TEXT NOT NULL, stable_since REAL NOT NULL,
 registered_signature TEXT
);
CREATE TABLE IF NOT EXISTS operations (
 operation_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, target_rel TEXT NOT NULL,
 source_rel TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS intake_operations (
 operation_id TEXT PRIMARY KEY, source_id INTEGER NOT NULL UNIQUE, doc_id TEXT NOT NULL,
 source_rel TEXT NOT NULL, quarantine_rel TEXT NOT NULL, receipt_rel TEXT NOT NULL,
 expected_signature TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL,
 updated REAL NOT NULL, error_code TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
"""
READINGS = """SELECT d.sha256,d.original_name,d.original_rel,d.suffix,d.size_bytes,
 d.library_rel,d.current_revision_id,r.* FROM reading_runs r JOIN documents d USING(doc_id)"""
VIEWS = """
CREATE VIEW IF NOT EXISTS execution_readings AS """ + READINGS + ";\n" + """
CREATE VIEW IF NOT EXISTS current_readings AS """ + READINGS + """
 WHERE r.revision_id=COALESCE(d.current_revision_id,
 (SELECT initial.revision_id FROM reading_runs initial
  WHERE initial.doc_id=d.doc_id AND initial.base_revision_id IS NULL
  ORDER BY initial.created,initial.revision_id LIMIT 1));
"""
SCHEMA = DOCUMENTS + RUNS + JOBS + AUXILIARY + VIEWS


def statements(conn, sql):
    # executescript implicitly commits; schema migration must stay one transaction.
    for statement in sql.split(';'):
        if statement.strip():
            conn.execute(statement)

class Catalog:
    def __init__(self, path):
        self._db = path
        self._local = threading.local()
        self._conns = []
        self._conns_lock = threading.Lock()

    def initialize(self):
        version = self.conn.execute('PRAGMA user_version').fetchone()[0]
        if version == 2:
            return
        if version > 2:
            raise ValueError('catalog schema is newer than this reader')
        fd = os.open(str(self._db.parent / 'reader.worker.lock'), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.conn.execute('PRAGMA user_version').fetchone()[0] == 2:
                return
            legacy = bool(self.conn.execute("PRAGMA table_info(documents)").fetchall())
            if legacy:
                self._backup_legacy()
            self.conn.execute('PRAGMA foreign_keys=OFF')
            try:
                with self.transaction():
                    if legacy:
                        self._migrate_legacy()
                    else:
                        statements(self.conn, SCHEMA)
                    if self.conn.execute('PRAGMA foreign_key_check').fetchall():
                        raise ValueError('catalog migration has invalid references')
                    self.conn.execute("INSERT OR IGNORE INTO meta VALUES ('dispatch_count','0')")
                    self.conn.execute('PRAGMA user_version=2')
            finally:
                self.conn.execute('PRAGMA foreign_keys=ON')
        finally:
            os.close(fd)

    def _backup_legacy(self):
        path = self._db.parent / ('before-reading-revisions-' + uuid.uuid4().hex + '.sqlite')
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.close(fd)
        backup = sqlite3.connect(str(path))
        try:
            self.conn.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('legacy catalog backup failed integrity check')
        finally:
            backup.close()
        with path.open('rb') as saved:
            os.fsync(saved.fileno())
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _migrate_legacy(self):
        documents = [dict(r) for r in self.conn.execute('SELECT * FROM documents')]
        statements(self.conn, DOCUMENTS.replace('documents (', 'documents_next (') + RUNS)
        statements(self.conn, JOBS.split('CREATE INDEX')[0].replace('jobs (', 'jobs_next ('))
        for doc in documents:
            revision = 'rev-' + hashlib.sha256((doc['doc_id'] + '\0legacy\0' + doc['recipe']).encode()).hexdigest()[:32]
            self.conn.execute('INSERT INTO documents_next VALUES(?,?,?,?,?,?,?,?,?)',
                              tuple(doc[k] for k in ('doc_id','sha256','original_name','original_rel','suffix','size_bytes','created','library_rel')) +
                              (revision if doc['report_rel'] else None,))
            run = {k: doc[k] for k in ('doc_id','recipe','created','updated','state','phase','priority','pages_total','chunks_total','chunks_read','report_rel','error_code')}
            report = self._db.parent.parent / doc['report_rel'] if doc['report_rel'] else None
            if report:
                report.resolve().relative_to(self._db.parent.parent.resolve())
            run.update(revision_id=revision,request_id='initial',request_json='{}',reason='legacy catalog migration; no quality promotion',
                       artifact_rel='artifacts/' + doc['doc_id'], extracted_rel='extracted/' + doc['doc_id'],
                       report_sha256=hashlib.sha256(report.read_bytes()).hexdigest() if report and report.is_file() else None,
                       review_json='{"kind":"legacy_import","quality":"unverified"}' if report else None,
                       activated=doc['updated'] if report else None)
            self.insert_run(run)
            for job in self.conn.execute('SELECT * FROM jobs WHERE doc_id=?',(doc['doc_id'],)).fetchall():
                values = dict(job); values['revision_id'] = revision
                self.conn.execute('INSERT INTO jobs_next (' + ','.join(values) + ') VALUES (' + ','.join('?' for _ in values) + ')',tuple(values.values()))
        if self.conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] != self.conn.execute('SELECT COUNT(*) FROM jobs_next').fetchone()[0]:
            raise ValueError('legacy catalog has orphan jobs; migration refused')
        self.conn.execute('DROP TABLE jobs')
        self.conn.execute('DROP TABLE documents')
        self.conn.execute('ALTER TABLE documents_next RENAME TO documents')
        self.conn.execute('ALTER TABLE jobs_next RENAME TO jobs')
        statements(self.conn, JOBS + AUXILIARY + VIEWS)

    def insert_run(self, values):
        self.conn.execute('INSERT INTO reading_runs (' + ','.join(values) + ') VALUES (' + ','.join('?' for _ in values) + ')',tuple(values.values()))

    def enqueue(self, reading, stage, now, chunk=0):
        key = '%s:%s:%s' % (reading['revision_id'],stage,chunk)
        self.conn.execute('INSERT OR IGNORE INTO jobs(job_id,doc_id,revision_id,stage,chunk,available,created) VALUES(?,?,?,?,?,?,?)',
                          (key,reading['doc_id'],reading['revision_id'],stage,chunk,now,now))

    def reading(self, doc_id, revision_id=None):
        if revision_id is None:
            row = self.conn.execute('SELECT * FROM current_readings WHERE doc_id=?',(doc_id,)).fetchone()
        else:
            row = self.conn.execute('SELECT * FROM execution_readings WHERE doc_id=? AND revision_id=?',(doc_id,revision_id)).fetchone()
        if row is None:
            raise ValueError('unknown document or reading revision')
        return dict(row)

    @contextmanager
    def read_snapshot(self):
        if self.conn.in_transaction:
            yield
            return
        self.conn.execute('BEGIN')
        try:
            yield
        finally:
            self.conn.execute('ROLLBACK')

    @property
    def conn(self):
        """One connection per thread. Sharing one across threads is unsupported by
        sqlite3 and would interleave two threads' BEGIN IMMEDIATE on one handle."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            if self._db is None:
                return None
            conn = sqlite3.connect(str(self._db), timeout=30, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            self._local.conn = conn
            with self._conns_lock:
                self._conns.append(conn)
        return conn

    def _close_thread(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            self._local.conn = None
            with self._conns_lock:
                if conn in self._conns:
                    self._conns.remove(conn)
            conn.close()

    def close(self):
        with self._conns_lock:
            conns, self._conns = self._conns, []
        for conn in conns:
            conn.close()
        self._local = threading.local()
        self._db = None

    @contextmanager
    def transaction(self):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.conn.execute("COMMIT")
        except BaseException:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
            raise
