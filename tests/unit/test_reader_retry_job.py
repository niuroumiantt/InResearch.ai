"""Single-job online CAS retry: fixtures only, no services or real models."""
import contextlib
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock

from inresearch.interfaces import reader as cli
from inresearch.materials.reader_contracts import ReaderError, TransientModelError
from inresearch.workflow.reader import Reader
from inresearch.workflow import reader_retry_job as retry
from test_continuous_reader import Model, Clock


class ReaderRetryJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name); self.clock = Clock()
        self.reader = Reader(self.base/'data', self.base/'state', self.base/'repo', Model(),
                             0, 200, self.clock, read_batch_chunks=1).initialize()
        text = ''.join('section%03d ' % i + 'bounded source text ' * 8 + '\n' for i in range(154))
        (self.reader.data/'raw-materials/source.txt').write_text(text)
        with contextlib.redirect_stdout(io.StringIO()):
            self.reader.run(once=True, max_jobs=64)
        self.doc = dict(self.reader.conn.execute('SELECT * FROM current_readings').fetchone())
        self.assertEqual(62, self.doc['chunks_read'])
        self.assertEqual(154, self.doc['chunks_total'])
        with self.reader.transaction():
            self.reader.conn.execute("UPDATE jobs SET state='failed',attempts=3,error_code='model_cli_failed',started=900,finished=990 WHERE revision_id=? AND stage='read' AND chunk=63", (self.doc['revision_id'],))
            self.reader.conn.execute("UPDATE reading_runs SET state='failed',phase='read',error_code='model_cli_failed' WHERE revision_id=?", (self.doc['revision_id'],))
            # Prove the explicit retry can be claimed next without changing
            # available in production. This is only a local fixture arrangement.
            self.reader.conn.execute("UPDATE jobs SET available=2000 WHERE revision_id=? AND stage='read' AND chunk=62", (self.doc['revision_id'],))
        self.args = dict(doc_id=self.doc['doc_id'], revision_id=self.doc['revision_id'], stage='read',
                         chunk_index=63, error_code='model_cli_failed', expected_attempts=3,
                         expected_recipe=self.doc['recipe'], expected_recipe_sha256=hashlib.sha256((self.reader.data/self.doc['artifact_rel']/'recipe.json').read_bytes()).hexdigest(),
                         request_id='fixture-jlarc-001',
                         by='fixture operator', reason='one explicit retry after recorded real recovery')
        self.cache = {p.name: p.read_bytes() for p in (self.reader.data/self.doc['artifact_rel']/'chunks').iterdir()}

    def tearDown(self):
        self.reader.close(); self.temp.cleanup()

    def call(self, **changes):
        return retry.retry_job(self.reader.data, **{**self.args, **changes})

    def table(self, name):
        return [dict(r) for r in self.reader.conn.execute('SELECT * FROM ' + name + ' ORDER BY 1')]

    def failed_job(self):
        return dict(self.reader.conn.execute("SELECT * FROM jobs WHERE revision_id=? AND stage='read' AND chunk=63", (self.doc['revision_id'],)).fetchone())

    def test_online_lock_held_only_two_rows_and_marker_change_with_durable_backup(self):
        before = {name:self.table(name) for name in ('documents','jobs','reading_runs','meta','operations','intake_operations')}
        with self.reader.worker_session():
            result = self.call()
        self.assertEqual('applied', result['status']); self.assertTrue(result['receipt_written'])
        after = {name:self.table(name) for name in before}
        for name in ('documents','operations','intake_operations'):
            self.assertEqual(before[name], after[name])
        changed = [(a,b) for a,b in zip(before['jobs'],after['jobs']) if a!=b]
        self.assertEqual(1,len(changed)); old,new=changed[0]
        self.assertEqual({**old,'state':'pending','error_code':None},new)
        self.assertEqual(3,new['attempts']); self.assertEqual(old['available'],new['available'])
        self.assertEqual({**before['reading_runs'][0],'state':'queued','error_code':None},after['reading_runs'][0])
        self.assertEqual(1,len(after['meta'])-len(before['meta']))
        for p in (self.reader.data/self.doc['artifact_rel']/'chunks').iterdir():
            self.assertEqual(self.cache[p.name],p.read_bytes())
        directory=self.reader.data/'catalog/reader-job-retries'/self.args['request_id']
        backup=directory/'catalog-before.sqlite';self.assertEqual(0o600,backup.stat().st_mode & 0o777)
        with sqlite3.connect(backup) as db:
            self.assertEqual('delete',db.execute('PRAGMA journal_mode').fetchone()[0])
            self.assertEqual(('failed',3),db.execute("SELECT state,attempts FROM jobs WHERE stage='read' AND chunk=63").fetchone())
        self.assertEqual(3,json.loads((directory/'before.json').read_text())['snapshot']['job']['attempts'])

    def test_preserved_exhausted_attempts_claim_to_four_and_failure_is_terminal(self):
        self.call(); job=self.reader.claim()
        self.assertEqual(63,job['chunk']);self.assertEqual(4,job['attempts'])
        with mock.patch.object(self.reader.model,'generate',side_effect=TransientModelError('model_cli_failed')):
            self.assertEqual('failed',self.reader.process(job))
        self.assertEqual(('failed',4),(self.failed_job()['state'],self.failed_job()['attempts']))
        self.assertIsNone(self.reader.claim())
        self.assertEqual('already_applied',self.call()['status'])
        self.assertEqual(4,self.failed_job()['attempts'])

    def test_dry_run_does_not_write_db_audit_or_cache(self):
        before={t:self.table(t) for t in ('jobs','reading_runs','meta')}
        result=self.call(dry_run=True)
        self.assertEqual('eligible',result['status']);self.assertEqual(62,result['successful_read_chunks_preserved'])
        self.assertFalse((self.reader.data/'catalog/reader-job-retries').exists())
        self.assertEqual(before,{t:self.table(t) for t in before})

    def test_bad_inputs_and_nonwhitelisted_errors_reject_without_audit(self):
        for bad in ({'stage':'triage'},{'error_code':'model_cli_timeout'},{'expected_attempts':True},
                    {'doc_id':'doc-invalid'},{'request_id':'../unsafe'},{'by':' '},{'reason':' padded '}):
            with self.subTest(bad=bad),self.assertRaises(ReaderError):self.call(**bad)
        self.assertFalse((self.reader.data/'catalog/reader-job-retries').exists())

    def test_cas_wrong_attempt_recipe_chunk_or_error_has_zero_queue_effect(self):
        before=self.table('jobs')
        for n,bad in enumerate(({'expected_attempts':4},{'expected_recipe':'0'*24},{'chunk_index':62})):
            with self.subTest(bad=bad),self.assertRaises(ReaderError):
                self.call(request_id='fixture-bad-%03d'%n,**bad)
        self.assertEqual(before,self.table('jobs'))

    def test_current_revision_drift_and_extra_failed_or_running_job_refuse(self):
        self.reader.conn.execute("UPDATE documents SET current_revision_id=? WHERE doc_id=?", (self.doc['revision_id'],self.doc['doc_id']))
        # A valid pointer to this same initial revision remains acceptable.
        self.assertEqual('eligible',self.call(dry_run=True)['status'])
        self.reader.conn.execute("INSERT INTO meta VALUES(?,?)",('execution_root:'+self.doc['doc_id'],'rev-'+'f'*32))
        self.reader.conn.execute('UPDATE documents SET current_revision_id=NULL')
        with self.assertRaisesRegex(ReaderError,''):self.call(dry_run=True)
        self.reader.conn.execute('DELETE FROM meta WHERE key=?',('execution_root:'+self.doc['doc_id'],))
        for state in ('failed','blocked','running'):
            self.reader.conn.execute("UPDATE jobs SET state=? WHERE stage='read' AND chunk=64",(state,))
            with self.subTest(state=state),self.assertRaises(ReaderError):self.call(dry_run=True)
        self.assertEqual('failed',self.failed_job()['state'])

    def test_missing_and_old_catalogs_never_create_or_migrate(self):
        with self.assertRaises(ReaderError):retry.retry_job(self.base/'missing',**self.args)
        old=self.base/'old/catalog';old.mkdir(parents=True)
        with sqlite3.connect(old/'catalog.sqlite') as db:db.execute('PRAGMA user_version=1')
        with self.assertRaises(ReaderError):retry.retry_job(old.parent,**self.args)
        with sqlite3.connect(old/'catalog.sqlite') as db:self.assertEqual(1,db.execute('PRAGMA user_version').fetchone()[0])
        self.assertFalse((old/'reader-job-retries').exists())

    def test_replay_and_request_id_mismatch_or_tampered_audit_fail_closed(self):
        self.call();before=self.table('jobs')
        self.assertEqual('already_applied',self.call()['status'])
        with self.assertRaises(ReaderError):self.call(reason='different intent')
        directory=self.reader.data/'catalog/reader-job-retries'/self.args['request_id']
        with (directory/'catalog-before.sqlite').open('ab') as f:f.write(b'tamper')
        with self.assertRaises(ReaderError):self.call()
        self.assertEqual(before,self.table('jobs'))

    def test_prepare_audit_failure_never_requeues(self):
        with mock.patch.object(retry,'atomic_write',side_effect=OSError('fixture fsync failure')):
            with self.assertRaises(OSError):self.call()
        self.assertEqual('failed',self.failed_job()['state'])
        self.assertFalse(any(r['key'].startswith('reader_retry_job:') for r in self.table('meta')))
        before={t:self.table(t) for t in ('jobs','reading_runs','meta')}
        abandoned=self.reader.data/'catalog/reader-job-retries'/self.args['request_id']
        backup=(abandoned/'catalog-before.sqlite').read_bytes()
        # An incomplete prepare is preserved, never silently repaired or reused.
        with self.assertRaises(ReaderError) as error:self.call()
        self.assertEqual('retry_request_incomplete',error.exception.code)
        self.assertEqual(before,{t:self.table(t) for t in before})
        self.assertEqual(backup,(abandoned/'catalog-before.sqlite').read_bytes())
        self.assertFalse((abandoned/'before.json').exists())
        # A separately reviewed key can retry a failure that never committed;
        # this is distinct from adding another claim after a committed retry.
        self.assertEqual('applied',self.call(request_id='fixture-prepare-recovery-002')['status'])
        self.assertEqual(backup,(abandoned/'catalog-before.sqlite').read_bytes())

    def test_context_snapshot_and_frozen_recipe_binding_are_verified(self):
        path = self.reader.data/self.doc['artifact_rel']/'context.json'
        original = path.read_bytes()
        context = json.loads(original)
        context['injected'] = 'changed after freezing'
        path.write_text(json.dumps(context))
        with self.assertRaises(ReaderError) as error:
            self.call(dry_run=True)
        self.assertEqual('retry_frozen_context_changed', error.exception.code)
        context['snapshot_hash'] = hashlib.sha256(retry.encoded({k:v for k,v in context.items() if k!='snapshot_hash'}).encode()).hexdigest()
        path.write_text(json.dumps(context))
        with self.assertRaises(ReaderError) as error:
            self.call()
        self.assertEqual('retry_frozen_recipe_changed', error.exception.code)
        self.assertEqual('failed', self.failed_job()['state'])
        path.write_bytes(original)
        self.assertEqual('eligible', self.call(dry_run=True)['status'])

    def test_failed_target_cache_is_preserved_and_refused(self):
        directory = self.reader.data/self.doc['artifact_rel']/'chunks'
        value = json.loads((directory/'000000.json').read_bytes())
        value['_marker'] = 'read:63'
        path = directory/'000063.json'
        path.write_text(json.dumps(value))
        before = path.read_bytes()
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run), self.assertRaises(ReaderError) as error:
                self.call(dry_run=dry_run)
            self.assertEqual('retry_failed_chunk_cache_exists', error.exception.code)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual('failed', self.failed_job()['state'])
        self.assertFalse(any(r['key'].startswith('reader_retry_job:') for r in self.table('meta')))

    def test_success_cache_page_and_character_coverage_are_verified(self):
        path = self.reader.data/self.doc['artifact_rel']/'chunks/000000.json'
        original = path.read_bytes()
        for field in ('chunk_index', 'page_index', 'characters'):
            value = json.loads(original)
            value[field] = 9999
            path.write_text(json.dumps(value))
            with self.subTest(field=field), self.assertRaises(ReaderError) as error:
                self.call(dry_run=True)
            self.assertEqual('retry_success_cache_changed', error.exception.code)
        self.assertEqual('failed', self.failed_job()['state'])

    def test_replay_refuses_nonprivate_audit_directory(self):
        self.call()
        directory = self.reader.data/'catalog/reader-job-retries'/self.args['request_id']
        directory.chmod(0o777)
        try:
            with self.assertRaises(ReaderError) as error:
                self.call()
            self.assertEqual('retry_audit_not_private', error.exception.code)
        finally:
            directory.chmod(0o700)

    def test_post_commit_receipt_failure_keeps_marker_and_never_requeues_twice(self):
        real=retry.atomic_write
        def write(path,data,**kw):
            if path.name=='receipt.json':raise OSError('fixture receipt failure')
            return real(path,data,**kw)
        with mock.patch.object(retry,'atomic_write',side_effect=write):result=self.call()
        self.assertEqual('applied',result['status']);self.assertFalse(result['receipt_written'])
        job=self.reader.claim();self.assertEqual(4,job['attempts'])
        self.assertEqual('already_applied',self.call()['status'])
        self.assertEqual('running',self.failed_job()['state'])

    def test_commit_before_and_after_visibility_are_distinguished(self):
        with mock.patch.object(retry,'_commit',side_effect=sqlite3.OperationalError('fixture before commit')):
            with self.assertRaises(sqlite3.Error):self.call()
        self.assertEqual('failed',self.failed_job()['state'])
        def visible(conn):conn.commit();raise sqlite3.OperationalError('fixture after commit')
        with mock.patch.object(retry,'_commit',side_effect=visible):result=self.call()
        self.assertEqual('applied',result['status']);self.assertEqual('pending',self.failed_job()['state'])
        self.assertEqual('already_applied',self.call()['status'])

    def test_two_concurrent_requests_can_requeue_only_once(self):
        def run(n):
            try:return self.call(request_id='concurrent-retry-%d'%n)['status']
            except ReaderError:return 'refused'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,(1,2)))
        self.assertCountEqual(['applied','refused'],results)
        self.assertEqual(1,sum(r['key'].startswith('reader_retry_job:') for r in self.table('meta')))
        self.assertEqual(3,self.failed_job()['attempts'])

    def test_concurrent_claim_waits_for_transaction_and_claims_once(self):
        entered=threading.Event();release=threading.Event();real=retry._commit
        def commit(conn):entered.set();self.assertTrue(release.wait(5));real(conn)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool,mock.patch.object(retry,'_commit',side_effect=commit):
            updating=pool.submit(self.call);self.assertTrue(entered.wait(5))
            def claim():
                try:return self.reader.claim()
                finally:self.reader.catalog._close_thread()
            claiming=pool.submit(claim);release.set()
            self.assertEqual('applied',updating.result(5)['status']);job=claiming.result(5)
        self.assertEqual(63,job['chunk']);self.assertEqual(4,job['attempts'])
        self.assertEqual('already_applied',self.call()['status'])

    def test_snapshot_drift_and_cache_corruption_refuse(self):
        real=retry._files;calls=0
        def drifting(data,snapshot,recipe_sha):
            nonlocal calls
            calls+=1
            if calls==2:return {'changed':'0'*64}
            return real(data,snapshot,recipe_sha)
        with mock.patch.object(retry,'_files',side_effect=drifting),self.assertRaises(ReaderError):self.call()
        self.assertEqual('failed',self.failed_job()['state'])
        p=self.reader.data/self.doc['artifact_rel']/'chunks/000000.json';value=json.loads(p.read_text());value['_recipe']='wrong';p.write_text(json.dumps(value))
        with self.assertRaises(ReaderError):self.call(dry_run=True)

    def test_other_document_running_state_is_not_recovered(self):
        (self.reader.data/'raw-materials/other.txt').write_text('unrelated document')
        self.reader.scan()
        other=self.reader.conn.execute('SELECT doc_id,revision_id FROM reading_runs WHERE doc_id<>?',(self.doc['doc_id'],)).fetchone()
        self.reader.conn.execute("UPDATE jobs SET state='running',attempts=1 WHERE doc_id=?",(other['doc_id'],))
        self.reader.conn.execute("UPDATE reading_runs SET state='running' WHERE doc_id=?",(other['doc_id'],))
        before=[dict(r) for r in self.reader.conn.execute('SELECT * FROM jobs WHERE doc_id=?',(other['doc_id'],))]
        self.call()
        self.assertEqual(before,[dict(r) for r in self.reader.conn.execute('SELECT * FROM jobs WHERE doc_id=?',(other['doc_id'],))])
        self.assertEqual('running',self.reader.conn.execute('SELECT state FROM reading_runs WHERE doc_id=?',(other['doc_id'],)).fetchone()[0])

    def test_busy_writer_fails_closed_and_keeps_failure_history(self):
        blocker=sqlite3.connect(self.reader.data/'catalog/catalog.sqlite',isolation_level=None)
        blocker.execute('BEGIN IMMEDIATE')
        try:
            with self.assertRaises(sqlite3.OperationalError):self.call()
        finally:blocker.rollback();blocker.close()
        self.assertEqual(('failed',3),(self.failed_job()['state'],self.failed_job()['attempts']))

    def test_original_replacement_and_nonprivate_audit_reject(self):
        path=self.reader.data/self.doc['original_rel'];original=path.read_bytes();path.chmod(0o600);path.write_bytes(b'changed source')
        with self.assertRaises(ReaderError):self.call(dry_run=True)
        path.write_bytes(original);self.call()
        before=self.reader.data/'catalog/reader-job-retries'/self.args['request_id']/'before.json';before.chmod(0o644)
        with self.assertRaises(ReaderError):self.call()

    def test_model_wait_keeps_read_blocked_and_receipts_eligible_with_scope_floor_unchanged(self):
        from inresearch.workflow.reader_scope import DocumentScope
        scope=self.base/'scope.json';scope.write_text(json.dumps({'schema_version':1,'doc_ids':[self.doc['doc_id']]}))
        environment=self.base/'reader.env';environment.write_text('READER_CLAIM_MIN_PRIORITY=5\nREADER_DOCUMENT_SCOPE='+str(scope)+'\n')
        self.reader.document_scope=DocumentScope(scope,self.reader.data)
        self.reader.claim_min_priority=5
        with self.reader.transaction():
            self.reader.conn.execute("INSERT OR REPLACE INTO meta VALUES('model_wait_until',?)",(str(self.clock()+600),))
            self.reader.conn.execute("INSERT OR REPLACE INTO meta VALUES('model_wait_reason','model_relay_unavailable')")
        waiting=[tuple(r) for r in self.reader.conn.execute("SELECT key,value FROM meta WHERE key LIKE 'model_wait_%' ORDER BY key")]
        pending62=dict(self.reader.conn.execute("SELECT * FROM jobs WHERE stage='read' AND chunk=62").fetchone())
        priority=self.reader.conn.execute('SELECT priority FROM reading_runs').fetchone()[0]
        scope_bytes=scope.read_bytes();environment_bytes=environment.read_bytes()
        self.assertLessEqual(self.failed_job()['available'],self.clock())
        self.assertGreaterEqual(priority,self.reader.claim_min_priority)
        self.call()
        self.assertEqual(waiting,[tuple(r) for r in self.reader.conn.execute("SELECT key,value FROM meta WHERE key LIKE 'model_wait_%' ORDER BY key")])
        self.assertEqual(pending62,dict(self.reader.conn.execute("SELECT * FROM jobs WHERE stage='read' AND chunk=62").fetchone()))
        self.assertEqual(priority,self.reader.conn.execute('SELECT priority FROM reading_runs').fetchone()[0])
        self.assertEqual(5,self.reader.claim_min_priority);self.assertEqual(scope_bytes,scope.read_bytes());self.assertEqual(environment_bytes,environment.read_bytes())
        # This read is otherwise due, in scope and above floor. PR520's actual
        # claim() still blocks it while the original global model wait is active.
        self.assertIsNone(self.reader.claim())
        self.assertEqual('pending',self.failed_job()['state'])
        self.reader.catalog.enqueue(self.doc,'receipt',self.clock(),999)
        receipt=self.reader.claim()
        self.assertEqual('receipt',receipt['stage'])
        self.assertEqual(waiting,[tuple(r) for r in self.reader.conn.execute("SELECT key,value FROM meta WHERE key LIKE 'model_wait_%' ORDER BY key")])
        self.assertEqual('pending',self.failed_job()['state'])
        self.assertEqual(scope_bytes,scope.read_bytes());self.assertEqual(environment_bytes,environment.read_bytes())

    def test_cli_early_branch_never_constructs_reader_model_or_lifecycle(self):
        argv=['--data-root',str(self.reader.data),'retry-job']
        flags={'doc-id':'doc_id','revision-id':'revision_id','stage':'stage','chunk-index':'chunk_index',
               'expected-error':'error_code','expected-attempts':'expected_attempts','expected-recipe':'expected_recipe','expected-recipe-sha256':'expected_recipe_sha256',
               'request-id':'request_id','by':'by','reason':'reason'}
        for flag,key in flags.items():argv+=['--'+flag,str(self.args[key])]
        with (mock.patch('inresearch.workflow.reader.Reader',side_effect=AssertionError('no Reader')),
              mock.patch('inresearch.adapters.reader_model.ModelClient',side_effect=AssertionError('no model')),
              contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(0,cli.main(argv+['--dry-run']))
        self.assertEqual('failed',self.failed_job()['state'])


if __name__=='__main__':unittest.main()
