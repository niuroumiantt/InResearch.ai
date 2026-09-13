"""Business replacement, failure recovery and independent-process races."""
import contextlib
import multiprocessing
import io
import shutil
import sqlite3
import unittest
from pathlib import Path
from unittest import mock
import test_continuous_reader as fixtures
from inresearch.delivery import reader_export
from inresearch.materials.artifacts import read_json, atomic_json
from inresearch.materials.reader_contracts import Blocked, IntegrityError
from inresearch.workflow.reader import Reader
from inresearch.adapters import ocr_worker


def revision_process(base, action, args, gate, replies):
    reader = Reader(Path(base)/'data',Path(base)/'state',Path(base)/'repo',fixtures.Model(),0,200,fixtures.Clock()).initialize()
    try:
        gate.wait(15)
        replies.put(getattr(reader.revisions,action)(*args))
    except Exception as exc:
        replies.put({'error':getattr(exc,'code',type(exc).__name__)})
    finally:
        reader.close()


class ReadingRevisionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ReaderTests()
        self.f.setUp()
        self.f.install_registry()
        self.f.put(text=('服务器功率 300 W，条件须保留。\n' * 21) + '独立尾段 END')
        self.f.run_reader()
        self.r = self.f.reader
        self.old = self.r.doc(self.f.first_doc()['doc_id'])
        self.old_bytes = (self.r.data/self.old['report_rel']).read_bytes()

    def tearDown(self):
        self.f.tearDown()

    def request(self, key='review-1'):
        return self.r.revisions.request(self.old['doc_id'],self.old['revision_id'],key,'重新核对完整正文')['revision_id']

    def ready(self, key='review-1'):
        revision = self.request(key)
        self.f.run_reader()
        self.assertEqual(self.r.doc(self.old['doc_id'],revision)['state'],'ready')
        return self.r.revisions.inspect(revision)

    def activation_args(self, run):
        return (run['revision_id'],run['base_revision_id'],run['report_sha256'],'reviewer','已核对正文、尾段、定位与覆盖；仍为候选')

    def assert_old_current(self):
        doc = self.r.doc(self.old['doc_id'])
        self.assertEqual(doc['revision_id'],self.old['revision_id'])
        self.assertEqual(doc['state'],'complete')
        self.assertEqual((self.r.data/self.old['report_rel']).read_bytes(),self.old_bytes)
        snapshot = self.r.export_snapshot()['knowledge']
        self.assertEqual(len(snapshot['documents']),1)
        self.assertEqual(snapshot['documents'][0]['reading_revision_id'],self.old['revision_id'])

    def test_full_reread_review_switch_retains_history_and_single_current(self):
        run = self.ready()
        self.assert_old_current()
        original = (self.r.data/self.old['original_rel']).read_bytes()
        self.assertEqual(run['report']['coverage']['characters_read'],len(original.decode()))
        old_ids = {r['id'] for r in read_json(self.r.data/self.old['report_rel'])['evidence']}
        new_ids = {r['id'] for r in run['report']['evidence']}
        self.assertFalse(old_ids & new_ids)
        result = self.r.revisions.activate(*self.activation_args(run))
        self.assertTrue(result['current'])
        self.assertTrue(self.r.revisions.activate(*self.activation_args(run))['replayed'])
        snapshot = self.r.export_snapshot()['knowledge']
        self.assertEqual(len(snapshot['documents']),1)
        self.assertEqual(snapshot['documents'][0]['reading_revision_id'],run['revision_id'])
        self.assertEqual({e['id'] for e in snapshot['evidence']},new_ids)
        self.assertTrue(all(e['acceptance']=='candidate' for e in snapshot['evidence']))
        self.assertEqual((self.r.data/self.old['report_rel']).read_bytes(),self.old_bytes)
        self.assertEqual((self.r.data/self.old['original_rel']).read_bytes(),original)
        self.assertEqual(self.r.conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0],1)
        self.assertEqual(self.r.conn.execute('SELECT COUNT(*) FROM intake_operations').fetchone()[0],1)
        self.assertEqual(sum(row['current'] for row in self.r.revisions.list(self.old['doc_id'])),1)

    def test_failed_reread_retry_keeps_current_and_frozen_model(self):
        revision = self.request()
        self.f.model.fail_stage = 'read'
        for _ in range(3):
            self.f.clock.advance(); self.f.run_reader()
        self.assertEqual(self.r.doc(self.old['doc_id'],revision)['state'],'failed')
        self.assert_old_current()
        self.f.model.fail_stage = None
        frozen = self.f.model.identity
        self.f.model.identity = {**frozen,'model':'changed-after-request'}
        self.r.retry(self.old['doc_id'],revision); self.f.run_reader()
        self.assertEqual(self.r.doc(self.old['doc_id'],revision)['error_code'],'execution_model_changed_requires_new_recipe')
        self.assert_old_current()
        self.f.model.identity = frozen
        self.r.retry(self.old['doc_id'],revision); self.f.run_reader()
        self.assertEqual(self.r.doc(self.old['doc_id'],revision)['state'],'ready')
        self.assertEqual(self.r.conn.execute('SELECT COUNT(*) FROM reading_runs').fetchone()[0],2)
        self.assertEqual(self.r.conn.execute('SELECT COUNT(*) FROM jobs WHERE revision_id=? AND stage=?',(revision,'triage')).fetchone()[0],1)

    def test_changed_default_used_only_by_new_explicit_revision(self):
        identity = self.f.model.identity
        self.f.model.identity = {**identity,'model':'larger-future-model'}
        calls = len(self.f.model.calls)
        self.f.run_reader(); self.assertEqual(len(self.f.model.calls),calls)
        revision = self.request()
        doc = self.r.doc(self.old['doc_id'],revision)
        self.assertEqual(read_json(self.r.data/doc['artifact_rel']/'recipe.json')['model']['model'],'larger-future-model')
        self.f.run_reader(); self.assertEqual(self.r.doc(self.old['doc_id'],revision)['state'],'ready')
        self.assert_old_current()

    def test_report_or_checkpoint_change_and_wrong_review_hash_cannot_activate(self):
        run = self.ready()
        args = self.activation_args(run)
        with self.assertRaises(Blocked):
            self.r.revisions.activate(*(args[:2]+('0'*64,)+args[3:]))
        chunk = next((self.r.data/run['artifact_rel']/'chunks').glob('*.json'))
        original = chunk.read_bytes(); chunk.write_bytes(original+b' ')
        with self.assertRaises(IntegrityError):
            self.r.revisions.activate(*args)
        self.assert_old_current()

    def test_incomplete_report_never_reaches_ready(self):
        revision = self.request()
        synth = self.r.stages._synthesize
        def incomplete(doc):
            report = synth(doc)
            report['coverage']['complete'] = False
            atomic_json(self.r.stages.artifact_path(doc,'report.json'),report)
            return report
        with mock.patch.object(self.r.stages,'_synthesize',incomplete):
            self.f.run_reader()
        self.assertEqual(self.r.doc(self.old['doc_id'],revision)['state'],'blocked')
        self.assert_old_current()

    def test_reject_and_late_activation_do_not_resurrect_or_overwrite(self):
        first = self.ready()
        self.r.revisions.reject(first['revision_id'],'reviewer','未通过内容核对')
        second = self.ready('review-2')
        self.r.revisions.activate(*self.activation_args(second))
        with self.assertRaises(Blocked):
            self.r.revisions.activate(*self.activation_args(first))
        self.assertEqual(self.r.doc(self.old['doc_id'])['revision_id'],second['revision_id'])
        replay = self.r.revisions.request(self.old['doc_id'],self.old['revision_id'],'review-1','重新核对完整正文')
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['state'],'rejected')
        with self.assertRaises(Blocked):
            self.r.revisions.request(self.old['doc_id'],self.old['revision_id'],'review-3','迟到请求')

    def test_activation_transaction_failure_rolls_back_then_replays(self):
        run = self.ready(); transaction = self.r.catalog.transaction
        @contextlib.contextmanager
        def fail_before_commit():
            with transaction():
                yield
                raise sqlite3.OperationalError('injected commit failure')
        with mock.patch.object(self.r.catalog,'transaction',fail_before_commit):
            with self.assertRaises(sqlite3.OperationalError):
                self.r.revisions.activate(*self.activation_args(run))
        self.assert_old_current()
        self.assertIsNone(self.r.doc(self.old['doc_id'],run['revision_id'])['review_json'])
        self.r.revisions.activate(*self.activation_args(run))

    def parallel(self, action, args):
        ctx = multiprocessing.get_context('spawn'); gate=ctx.Event(); replies=ctx.Queue()
        workers=[ctx.Process(target=revision_process,args=(str(self.f.base),action,args,gate,replies)) for _ in range(2)]
        for p in workers:p.start()
        gate.set()
        try:
            results=[replies.get(timeout=20) for _ in workers]
            for p in workers:p.join(20);self.assertEqual(p.exitcode,0)
            return results
        finally:
            for p in workers:
                if p.is_alive():p.terminate();p.join()
            replies.close()

    def test_independent_process_requests_and_activations_are_idempotent(self):
        results=self.parallel('request',(self.old['doc_id'],self.old['revision_id'],'parallel-request','并发重放'))
        self.assertEqual(sorted(r.get('replayed') for r in results),[False,True])
        self.assertEqual(len({r['revision_id'] for r in results}),1)
        self.f.run_reader();run=self.r.revisions.inspect(results[0]['revision_id'])
        results=self.parallel('activate',self.activation_args(run))
        self.assertEqual(sorted(r.get('replayed') for r in results),[False,True])
        self.assertEqual(sum(row['current'] for row in self.r.revisions.list(self.old['doc_id'])),1)

    def test_export_holds_one_snapshot_while_other_process_activates(self):
        run=self.ready();ctx=multiprocessing.get_context('spawn');gate=ctx.Event();replies=ctx.Queue()
        worker=ctx.Process(target=revision_process,args=(str(self.f.base),'activate',self.activation_args(run),gate,replies));worker.start()
        original=reader_export.read_report
        def during_switch(data,doc):
            self.assertTrue(self.r.conn.in_transaction)
            gate.set();result=replies.get(timeout=20);self.assertNotIn('error',result)
            return original(data,doc)
        try:
            with mock.patch.object(reader_export,'read_report',during_switch):
                snapshot=self.r.export_snapshot()['knowledge']
            self.assertEqual(snapshot['documents'][0]['reading_revision_id'],self.old['revision_id'])
            self.assertEqual({e['reading_revision_id'] for e in snapshot['evidence']},{self.old['revision_id']})
            self.assertEqual(self.r.export_snapshot()['knowledge']['documents'][0]['reading_revision_id'],run['revision_id'])
            worker.join(20);self.assertEqual(worker.exitcode,0)
        finally:
            if worker.is_alive():worker.terminate();worker.join()
            replies.close()

    def test_directory_export_manifest_names_immutable_versions(self):
        destination=self.f.base/'export'
        self.r.export(destination);before=read_json(destination/'manifest.json')['reports'][0]
        old=(destination/before['file']).read_bytes()
        run=self.ready();self.r.revisions.activate(*self.activation_args(run));self.r.export(destination)
        after=read_json(destination/'manifest.json')['reports'][0]
        self.assertNotEqual(before['file'],after['file'])
        self.assertEqual((destination/before['file']).read_bytes(),old)
        self.assertEqual(after['reading_revision_id'],run['revision_id'])

    def test_backup_restores_current_and_historical_revisions_without_inference(self):
        run=self.ready();self.r.revisions.activate(*self.activation_args(run))
        backup=self.f.base/'backup';self.r.backup(backup)
        restored=self.f.base/'restored';shutil.copytree(backup,restored)
        (restored/'catalog').mkdir();shutil.copyfile(restored/'catalog.sqlite',restored/'catalog/catalog.sqlite')
        model=fixtures.Model()
        reader=Reader(restored,self.f.base/'restore-state',self.f.base/'repo',model,0,200,self.f.clock).initialize()
        try:
            with contextlib.redirect_stdout(io.StringIO()):reader.run(once=True)
            self.assertEqual(model.calls,[])
            self.assertEqual(reader.doc(self.old['doc_id'])['revision_id'],run['revision_id'])
            self.assertEqual(reader.revisions.inspect(self.old['revision_id'])['report_sha256'],self.old['report_sha256'])
            self.assertEqual(reader.revisions.inspect(run['revision_id'])['report_sha256'],run['report_sha256'])
            self.assertEqual(reader.conn.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:reader.close()

    def test_ocr_failure_releases_the_same_revision_claim(self):
        doc={'doc_id':self.old['doc_id'],'revision_id':'rev-ocr-fixture'}
        with mock.patch.object(ocr_worker.models,'configured_client'), mock.patch.object(ocr_worker,'remote_candidates',return_value=[doc]), \
             mock.patch.object(ocr_worker,'claim',return_value=True), mock.patch.object(ocr_worker,'process',side_effect=RuntimeError('fixture failure')), \
             mock.patch.object(ocr_worker,'run') as command, mock.patch('sys.argv',['ocr-worker']), contextlib.redirect_stdout(io.StringIO()):
            ocr_worker.main()
        self.assertEqual(command.call_args[0][0][-1],ocr_worker.DATA+'/offload/m4/claims/'+doc['revision_id'])
