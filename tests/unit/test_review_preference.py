"""Source preference preserves leases, original queue opportunities and sealed-version boundaries."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from inresearch.workflow import research_review as review
from inresearch.workflow.review_preference import load_preferred_sources, MAX_SOURCES

OLD = 'doc-' + 'a' * 64
PREFERRED = 'doc-' + 'b' * 64
UNFINISHED = 'doc-' + 'c' * 64
REPORT = 'd' * 64


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        (self.data/'catalog').mkdir()
        c = sqlite3.connect(self.data/'catalog/catalog.sqlite')
        c.execute('CREATE TABLE documents(doc_id TEXT PRIMARY KEY)')
        c.execute('CREATE TABLE current_readings(doc_id TEXT,revision_id TEXT,report_sha256 TEXT,manifest_sha256 TEXT,state TEXT)')
        for doc in (OLD, PREFERRED, UNFINISHED):
            c.execute('INSERT INTO documents VALUES(?)', (doc,))
            c.execute('INSERT INTO current_readings VALUES(?,?,?,?,?)', (doc, 'rev-'+doc[-4:], REPORT, 'e'*64, 'queued' if doc == UNFINISHED else 'complete'))
        c.commit()
        c.close()
        self.path = self.data/'preference.json'
        self.write([PREFERRED])
        self.store = review.ReviewStore(self.data)
        self.addCleanup(self.store.db.close)

    def write(self, ids, **extra):
        self.path.write_text(json.dumps({'schema_version': 1, 'doc_ids': ids, **extra}))

    def add(self, key, doc, available=0, error='', count=6, report=REPORT):
        self.store.db.execute('INSERT INTO batches VALUES(?,?,?,?,?,?,?,?,?,?)',
                              (key, doc, 'rev-'+doc[-4:], report, 'queued', json.dumps(['candidate-'+key+str(i) for i in range(count)]), 'today', error, 0, available))
        self.store.db.commit()

    def load(self):
        return load_preferred_sources(self.path, self.data)

    def test_scope_validates_exact_registered_ids_and_excludes_unfinished_versions(self):
        self.write([PREFERRED, UNFINISHED])
        preferred = self.load()
        self.assertEqual(preferred.sha256, hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(preferred.doc_ids, (PREFERRED, UNFINISHED))
        self.assertEqual(preferred.eligible_keys, (PREFERRED+'/rev-bbbb/'+REPORT,))
        for ids in ([], [PREFERRED, PREFERRED], ['bad'], ['doc-'+ 'f'*64], [PREFERRED]*(MAX_SOURCES+1)):
            with self.subTest(ids=ids[:2]):
                self.write(ids)
                with self.assertRaises(ValueError): self.load()
        self.write([PREFERRED], include_daily_deliveries=True)
        with self.assertRaises(ValueError): self.load()
        self.path.write_text('[]')
        with self.assertRaises(ValueError): self.load()
        self.path.write_text('{')
        with self.assertRaises(ValueError): self.load()

    def test_missing_symlink_large_or_changed_scope_never_falls_back(self):
        self.path.unlink()
        with self.assertRaises(FileNotFoundError): self.load()
        self.path.symlink_to(self.data/'catalog/catalog.sqlite')
        with self.assertRaises(OSError): self.load()
        self.path.unlink()
        self.path.write_bytes(b' ' * (1024*1024+1))
        with self.assertRaises(ValueError): self.load()
        self.write([OLD])
        changed = self.load()
        self.write([PREFERRED])
        self.assertNotEqual(changed.sha256, self.load().sha256)

    def test_default_preserves_retry_cohort_order_without_scheduler_table(self):
        self.add('old-single', OLD, count=1)
        self.add('preferred-cohort', PREFERRED)
        self.add('real-retry', OLD, error='explicit semantic-values-v3 retry; old audit retained')
        self.assertEqual([self.store.claim()['id'] for _ in range(3)], ['real-retry', 'preferred-cohort', 'old-single'])
        self.assertIsNone(self.store.db.execute("SELECT name FROM sqlite_master WHERE name='review_scheduling'").fetchone())
        self.assertNotIn('last_scheduling', self.store.status())

    def test_three_preferred_then_original_queue_opportunity_survives_restart(self):
        self.add('old', OLD)
        for i in range(5): self.add('preferred'+str(i), PREFERRED)
        preferred = self.load()
        first = [self.store.claim(preferred=preferred) for _ in range(3)]
        self.assertEqual([r['id'] for r in first], ['preferred0', 'preferred1', 'preferred2'])
        other = review.ReviewStore(self.data)
        try:
            fourth = other.claim(preferred=preferred)
            self.assertEqual(fourth['id'], 'old')
            self.assertEqual(fourth['_scheduling']['lane'], 'queue_opportunity')
            self.assertEqual(other.status()['last_scheduling']['preferred_scope_sha256'], preferred.sha256)
        finally: other.db.close()
        self.assertEqual(self.store.claim(preferred=preferred)['id'], 'preferred3')

    def test_available_current_revision_and_native_retry_order_remain_binding(self):
        self.write([PREFERRED, UNFINISHED])
        self.add('ordinary', OLD)
        self.add('not-yet-available', PREFERRED, available=time.time()+3600)
        self.add('unfinished', UNFINISHED)
        self.add('stale-report', PREFERRED, report='f'*64)
        self.add('preferred-normal', PREFERRED)
        self.add('preferred-retry', PREFERRED, error='explicit semantic-values-v2 retry; old audit retained')
        preferred = self.load()
        self.assertEqual(self.store.claim(preferred=preferred)['id'], 'preferred-retry')
        self.assertEqual(self.store.claim(preferred=preferred)['id'], 'preferred-normal')
        result = self.store.claim(preferred=preferred)
        self.assertEqual(result['id'], 'ordinary')
        self.assertEqual(result['_scheduling']['lane'], 'ordinary_fallback')
        future = self.store.db.execute("SELECT attempts,state FROM batches WHERE id='not-yet-available'").fetchone()
        self.assertEqual(tuple(future), (0, 'queued'))

    def test_concurrent_claims_share_one_fairness_counter_and_disjoint_leases(self):
        self.add('old', OLD)
        for i in range(6): self.add('preferred'+str(i), PREFERRED)
        preferred = self.load()
        def claim(_):
            worker = review.ReviewStore(self.data)
            try: return worker.claim(preferred=preferred)
            finally: worker.db.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(claim, range(4)))
        self.assertEqual(len({r['id'] for r in rows}), 4)
        self.assertEqual(sum(r['doc_id']==PREFERRED for r in rows), 3)
        self.assertEqual(sum(r['_scheduling']['lane']=='queue_opportunity' for r in rows), 1)
        self.assertEqual(sum(r['doc_id']==OLD for r in rows), 1)

    def test_scope_byte_changes_cannot_reset_the_fairness_budget(self):
        self.add('old', OLD)
        for i in range(4): self.add('preferred'+str(i), PREFERRED)
        first = self.load()
        for _ in range(3): self.store.claim(preferred=first)
        self.path.write_text(self.path.read_text() + '\n')
        changed = self.load()
        self.assertNotEqual(changed.sha256, first.sha256)
        fourth = self.store.claim(preferred=changed)
        self.assertEqual(fourth['id'], 'old')
        self.assertEqual(fourth['_scheduling']['preferred_scope_sha256'], changed.sha256)

    def test_invalid_cli_preference_is_rejected_before_queue_initialization(self):
        missing = self.data/'missing.json'
        with patch('sys.argv', ['research-review', '--data', str(self.data), 'work', '--scope', str(self.path), '--preferred-sources', str(missing), '--once']), patch.object(review, 'ReviewStore') as constructor:
            with self.assertRaises(FileNotFoundError): review.main()
            constructor.assert_not_called()

    def test_existing_worker_ready_backpressure_prevents_every_preferred_claim(self):
        for i in range(12):
            self.add('ready'+str(i), OLD)
        self.store.db.execute("UPDATE batches SET state='review_ready'")
        self.store.db.commit()
        client = type('Client', (), {'profile': type('Profile', (), {'max_parallel': 2})()})()
        with patch('sys.argv', ['research-review', '--data', str(self.data), 'work', '--scope', str(self.path), '--preferred-sources', str(self.path), '--once']), patch.object(review.ReviewStore, 'discover'), patch.object(review.ReviewStore, 'run_one') as execute, patch.object(review, 'configured_client', return_value=client), patch('builtins.print'):
            review.main()
            execute.assert_not_called()
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM batches WHERE state='review_ready'").fetchone()[0], 12)
        self.assertIsNone(self.store.db.execute("SELECT name FROM sqlite_master WHERE name='review_scheduling'").fetchone())
