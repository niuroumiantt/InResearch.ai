"""Thread-local SQLite connections and the durable catalog schema."""
from __future__ import annotations
import sqlite3, threading
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
 doc_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, original_name TEXT NOT NULL,
 original_rel TEXT NOT NULL, suffix TEXT NOT NULL, size_bytes INTEGER NOT NULL,
 recipe TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
 state TEXT NOT NULL DEFAULT 'queued', phase TEXT NOT NULL DEFAULT 'extract',
 priority INTEGER NOT NULL DEFAULT 5, pages_total INTEGER NOT NULL DEFAULT 0,
 chunks_total INTEGER NOT NULL DEFAULT 0, chunks_read INTEGER NOT NULL DEFAULT 0,
 report_rel TEXT, library_rel TEXT, error_code TEXT
);
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
CREATE TABLE IF NOT EXISTS jobs (
 job_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, stage TEXT NOT NULL, chunk INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 3, available REAL NOT NULL, created REAL NOT NULL,
 started REAL, finished REAL, error_code TEXT, result_rel TEXT,
 FOREIGN KEY(doc_id) REFERENCES documents(doc_id)
);
CREATE INDEX IF NOT EXISTS job_pending ON jobs(state,available,created);
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

class Catalog:
    def __init__(self, path):
        self._db = path
        self._local = threading.local()
        self._conns = []
        self._conns_lock = threading.Lock()

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
            self.conn.execute("ROLLBACK")
            raise
