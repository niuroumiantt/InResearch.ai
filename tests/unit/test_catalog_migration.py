"""Upgrade the actual legacy table shape without moving original/artifact bytes."""
import hashlib
import fcntl
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import test_continuous_reader as fixtures
from inresearch.storage.catalog import Catalog
from inresearch.workflow.reader import Reader
from inresearch.materials.artifacts import atomic_json


LEGACY_SCHEMA = """
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


class CatalogMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='inresearch-catalog-migration-')
        self.base=Path(self.temp.name); self.data=self.base/'data';self.db=self.data/'catalog/catalog.sqlite'
        self.db.parent.mkdir(parents=True)
        self.text='原始材料：功率 300 W。独立尾段 END。'
        self.sha=hashlib.sha256(self.text.encode()).hexdigest();self.doc_id='doc-'+self.sha
        self.original='originals/'+self.sha+'/source.txt';original=self.data/self.original
        original.parent.mkdir(parents=True);original.write_text(self.text)
        self.report_rel='artifacts/'+self.doc_id+'/report.json'
        self.report={'_recipe':'old-recipe','_marker':'report','doc_id':self.doc_id,'content_sha256':self.sha,
                     'classification':{'title':'旧报告','module_id':'M11','org':'样本','year':'2026'},
                     'coverage':{'complete':True,'pages_total':1,'pages_read':1,'chunks_total':1,'chunks_read':1,
                                 'characters_total':len(self.text),'characters_read':len(self.text)},
                     'summary':'历史完整阅读候选；未做本轮语义审阅','evidence':[],'claims':[],'object_ids':[],'question_ids':[],
                     'model':fixtures.Model.identity,'acceptance':'candidate'}
        atomic_json(self.data/self.report_rel,self.report)
        atomic_json(self.data/'artifacts'/self.doc_id/'recipe.json',{'recipe':'old-recipe','version':'continuous-reader-v1','model':fixtures.Model.identity,'chunk_chars':200})
        with sqlite3.connect(str(self.db)) as conn:
            conn.executescript(LEGACY_SCHEMA)
            conn.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (self.doc_id,self.sha,'source.txt',self.original,'.txt',len(self.text.encode()),'old-recipe',10,20,'complete','complete',6,1,1,1,self.report_rel,None,None))
            conn.execute('INSERT INTO sources VALUES(1,?,?,1,NULL,?,10)',('source.txt',self.doc_id,'old-signature'))
            conn.execute("INSERT INTO jobs(job_id,doc_id,stage,state,attempts,available,created,started,finished) VALUES('old-job',?,'synthesize','succeeded',2,10,10,12,20)",(self.doc_id,))
            conn.execute("INSERT INTO meta VALUES('dispatch_count','7')")
        self.bytes=(self.data/self.report_rel).read_bytes()
        self.reader=None

    def tearDown(self):
        if self.reader:self.reader.close()
        self.temp.cleanup()

    def initialize(self):
        self.reader=Reader(self.data,self.base/'state',self.base/'repo',fixtures.Model(),0,200).initialize()
        return self.reader

    def test_legacy_backup_upgrade_preserves_records_paths_and_attempts(self):
        reader=self.initialize()
        self.assertEqual(reader.conn.execute('PRAGMA user_version').fetchone()[0],2)
        self.assertEqual(reader.conn.execute('PRAGMA foreign_key_check').fetchall(),[])
        doc=reader.doc(self.doc_id)
        self.assertEqual(doc['report_rel'],self.report_rel)
        self.assertEqual(doc['artifact_rel'],'artifacts/'+self.doc_id)
        self.assertEqual(doc['state'],'complete')
        self.assertEqual(json.loads(doc['review_json'])['quality'],'unverified')
        history=reader.revisions.inspect(doc['revision_id'])
        self.assertTrue(history['legacy_unverified'])
        self.assertEqual(history['report'],self.report)
        self.assertEqual((self.data/self.report_rel).read_bytes(),self.bytes)
        self.assertEqual((self.data/self.original).read_text(),self.text)
        self.assertEqual(reader.conn.execute('SELECT attempts FROM jobs WHERE job_id=?',('old-job',)).fetchone()[0],2)
        self.assertEqual(reader.conn.execute("SELECT value FROM meta WHERE key='dispatch_count'").fetchone()[0],'7')
        backups=list(self.db.parent.glob('before-reading-revisions-*.sqlite'));self.assertEqual(len(backups),1)
        with sqlite3.connect(str(backups[0])) as conn:
            self.assertIn('recipe',[r[1] for r in conn.execute('PRAGMA table_info(documents)')])
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM sources').fetchone()[0],1)
        self.assertNotIn('recipe',[r[1] for r in reader.conn.execute('PRAGMA table_info(documents)')])
        self.assertEqual(reader.export_snapshot()['knowledge']['documents'][0]['reading_revision_id'],doc['revision_id'])
        reader.close();self.reader=None
        self.initialize();self.assertEqual(len(list(self.db.parent.glob('before-reading-revisions-*.sqlite'))),1)

    def test_failure_inside_schema_change_rolls_back_with_backup_retained(self):
        original=Catalog._migrate_legacy
        def fail(catalog):
            original(catalog)
            raise sqlite3.OperationalError('migration interruption before commit')
        with mock.patch.object(Catalog,'_migrate_legacy',fail):
            with self.assertRaises(sqlite3.OperationalError):
                self.initialize()
        # A failed initialize still owns a connection; close it explicitly.
        with sqlite3.connect(str(self.db)) as conn:
            self.assertIn('recipe',[r[1] for r in conn.execute('PRAGMA table_info(documents)')])
            self.assertEqual(conn.execute('SELECT attempts FROM jobs').fetchone()[0],2)
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],0)
        self.assertEqual((self.data/self.report_rel).read_bytes(),self.bytes)
        self.initialize();self.assertEqual(self.reader.conn.execute('PRAGMA user_version').fetchone()[0],2)

    def test_upgraded_complete_reading_can_be_replaced_without_rereading_history(self):
        reader=self.initialize();old=reader.doc(self.doc_id)
        revision=reader.revisions.request(self.doc_id,old['revision_id'],'upgrade-reread','按新模型重新完整阅读')['revision_id']
        import contextlib,io
        with contextlib.redirect_stdout(io.StringIO()):reader.run(once=True)
        candidate=reader.revisions.inspect(revision)
        self.assertEqual(candidate['state'],'ready')
        reader.revisions.activate(revision,old['revision_id'],candidate['report_sha256'],'reviewer','核对完整正文和尾段')
        self.assertEqual(reader.doc(self.doc_id)['revision_id'],revision)
        self.assertEqual((self.data/self.report_rel).read_bytes(),self.bytes)

    def test_orphan_job_is_not_silently_dropped_during_upgrade(self):
        with sqlite3.connect(str(self.db)) as conn:
            conn.execute("INSERT INTO jobs(job_id,doc_id,stage,available,created) VALUES('orphan','missing-doc','read',10,10)")
        with self.assertRaisesRegex(ValueError,'orphan jobs'):
            self.initialize()
        with sqlite3.connect(str(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],2)
            self.assertIn('recipe',[r[1] for r in conn.execute('PRAGMA table_info(documents)')])

    def test_active_old_worker_prevents_schema_upgrade(self):
        with (self.db.parent/'reader.worker.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.initialize()
        with sqlite3.connect(str(self.db)) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],0)
        self.assertEqual(list(self.db.parent.glob('before-reading-revisions-*.sqlite')),[])

