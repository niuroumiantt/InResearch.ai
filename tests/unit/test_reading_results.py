"""Shared result authority across reader and terminal fact processing."""
import contextlib
import hashlib
import io
import json
import multiprocessing
import os
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import test_continuous_reader as fixtures
from deep_read_fixtures import METRICS, fact
from test_reading_revisions import revision_process
from inresearch.interfaces import reader as reader_cli, deep_read as l2_cli
from inresearch.materials.artifacts import read_json, atomic_json
from inresearch.materials.reader_contracts import IntegrityError
from inresearch.storage.catalog import Catalog
from inresearch.workflow.deep_read import DeepRead
from inresearch.workflow.reading_results import ReadingResults


class ReadingResultsTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ReaderTests(); self.f.setUp(); self.addCleanup(self.f.tearDown)
        self.f.install_registry()
        self.text = '服务器功率为 300 W，估计边界不可丢失。\n' * 13 + '唯一末段 END'
        self.f.put(text=self.text); self.f.run_reader()
        self.reader = self.f.reader; self.doc = self.f.first_doc(); self.sha = self.doc['sha256']
        base = self.f.base
        self.source = base/'m4-source.txt'; self.source.write_text(self.text)
        material = SimpleNamespace(RESULTS=base/'l1.jsonl',MAX_PREVIEW_CHARS=6000,
                                   readable_path=lambda row:(self.source,False))
        material.RESULTS.write_text(json.dumps(dict(sha256=self.sha,rel='m4-source.txt',suffix='.txt',
            status='ok',score=7,category='M11',org='测试',year='2026',size=self.source.stat().st_size))+'\n')
        (base/'repo/data').mkdir(exist_ok=True)
        atomic_json(base/'repo/data/facts.json', {'records':[]})
        atomic_json(base/'repo/framework/metrics.json', {'metrics':list(METRICS.values())})
        self.app = DeepRead(base/'repo',base/'l2-state',base/'packets',material,
                            reader_data_root=self.reader.data)
        self.results = self.app.readings

    def quantities(self):
        return {table:self.reader.conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                for table in ('documents','reading_runs','jobs')}

    def ready(self):
        revision = self.reader.revisions.request(self.doc['doc_id'],self.doc['revision_id'],
                                                'new-reading','完整重新核对')['revision_id']
        self.f.run_reader()
        return self.reader.revisions.inspect(revision)

    def activation(self, run):
        return (run['revision_id'],self.doc['revision_id'],run['report_sha256'],'test-reviewer','正文与末段均已核对')

    def test_reader_and_l2_current_cli_return_same_verified_revision_without_model(self):
        outputs=[]
        for cli,args in ((reader_cli,['--data-root',str(self.reader.data),'current','--sha',self.sha]),
                         (l2_cli,['--reader-data-root',str(self.reader.data),'current','--sha',self.sha])):
            stream=io.StringIO()
            with mock.patch('inresearch.adapters.reader_model.ModelClient',side_effect=AssertionError('no model')), \
                 contextlib.redirect_stdout(stream):
                self.assertEqual(cli.main(args),0)
            outputs.append(json.loads(stream.getvalue()))
        self.assertEqual(outputs[0],outputs[1])
        self.assertEqual(outputs[0]['reading_revision_id'],self.doc['revision_id'])
        self.assertEqual(outputs[0]['acceptance'],'candidate_only')

    def test_current_pack_reuses_full_text_and_report_without_extractor_or_new_reading(self):
        before=self.quantities(); calls=len(self.f.model.calls)
        with mock.patch.object(self.app,'extractor',side_effect=AssertionError('do not re-extract')):
            result=self.app.pack(self.sha)
        self.assertEqual(Path(result['text']).read_text(),self.text)
        self.assertEqual(result['read_from'],'reader_current_result')
        reference=result['reading_result']
        self.assertEqual(reference['reading_revision_id'],self.doc['revision_id'])
        self.assertEqual(hashlib.sha256(Path(reference['report_path']).read_bytes()).hexdigest(),reference['report_sha256'])
        self.assertEqual(read_json(Path(result['manifest']))['reading_result'],reference)
        self.assertIn('本包不创建第二份阅读结果',Path(result['brief']).read_text())
        self.assertEqual(self.quantities(),before); self.assertEqual(len(self.f.model.calls),calls)

    def test_record_skip_and_again_only_change_processing_not_current_reading(self):
        before=self.quantities(); report=(self.reader.data/self.doc['report_rel']).read_bytes()
        incoming=fact(evidence=dict(sha256=self.sha,locator='第 1 页',grade='S2'))
        first=self.app.record([incoming],self.sha)
        self.assertEqual(first['accepted'],1)
        self.assertTrue(self.app.record([incoming],self.sha)['receipt_replayed'])
        self.app.skip(self.sha,['缺少另一指标'])
        self.assertEqual(self.app.status()['documents_processed'],1)
        self.assertEqual(self.app.status()['reading']['catalog_current_results'],1)
        self.assertEqual(self.app.pack(self.sha)['packed'],0)
        self.assertEqual(self.app.pack(self.sha,again=True)['packed'],1)
        self.assertEqual(self.quantities(),before)
        self.assertEqual(self.reader.doc(self.doc['doc_id'])['revision_id'],self.doc['revision_id'])
        self.assertEqual((self.reader.data/self.doc['report_rel']).read_bytes(),report)
        self.assertEqual(self.source.read_text(),self.text)

    def test_zero_fact_and_legacy_receipts_do_not_create_full_reading_proof(self):
        self.app.readings=ReadingResults(self.f.base/'missing-reader')
        self.app.record([],self.sha)
        status=self.app.status()
        self.assertEqual(status['documents_processed'],1)
        self.assertNotIn('documents_read',status)
        self.assertEqual(status['reading']['catalog_current_results'],0)
        self.assertEqual(self.app.current(self.sha)['status'],'catalog_missing')
        # Historical rows remain usable for processing progress, never promotion.
        self.app.receipt_log.write_text(json.dumps({'sha256':self.sha,'facts':3})+'\n')
        before=self.app.receipt_log.read_bytes()
        self.assertEqual(self.app.processed_documents(),{self.sha})
        self.assertEqual(self.app.status()['reading']['catalog_current_results'],0)
        self.assertEqual(self.app.receipt_log.read_bytes(),before)

    def test_missing_catalog_query_does_not_create_directories_or_initialize(self):
        root=self.f.base/'absent-data'
        service=ReadingResults(root)
        with mock.patch.object(Catalog,'initialize',side_effect=AssertionError('no migration')):
            self.assertEqual(service.current(self.sha)['status'],'catalog_missing')
            self.assertEqual(service.status()['catalog_current_results'],0)
        self.assertFalse(root.exists())

    def test_query_uses_explicit_root_or_shared_environment_not_another_catalog(self):
        with mock.patch.dict(os.environ,{'READER_DATA_ROOT':str(self.reader.data)}):
            self.assertEqual(ReadingResults().current(self.sha)['reading_revision_id'],self.doc['revision_id'])
            self.assertEqual(ReadingResults(self.f.base/'different').current(self.sha)['status'],'catalog_missing')
        self.assertEqual(self.results.current('a'*64)['status'],'not_registered')
        for invalid in (self.sha[:16],None,'../file','A'*64):
            with self.assertRaises(ValueError):self.results.current(invalid)

    def test_pending_initial_is_not_current_and_falls_back_to_explicit_task_input(self):
        self.reader.conn.execute('UPDATE documents SET current_revision_id=NULL')
        self.assertEqual(self.results.current(self.sha)['status'],'no_current_result')
        with mock.patch.object(self.app,'extractor',return_value=(self.text,{'method':'test-extract'})) as extract:
            packed=self.app.pack(self.sha)
        extract.assert_called_once()
        self.assertEqual(packed['reading_result']['status'],'no_current_result')
        self.assertIn('不证明全文完成',Path(packed['brief']).read_text())

    def test_legacy_unsealed_result_never_promoted_or_rewritten(self):
        self.reader.conn.execute('UPDATE reading_runs SET manifest_sha256=NULL WHERE revision_id=?',(self.doc['revision_id'],))
        report=(self.reader.data/self.doc['report_rel']).read_bytes()
        result=self.results.current(self.sha)
        self.assertEqual(result['status'],'legacy_unverified'); self.assertNotIn('report',result)
        self.assertEqual(self.results.status()['legacy_unverified_results'],1)
        self.assertEqual((self.reader.data/self.doc['report_rel']).read_bytes(),report)

    def test_old_or_new_catalog_refuses_without_migration_or_backup(self):
        db=self.reader.data/'catalog/catalog.sqlite'
        for version in (1,3):
            self.reader.conn.execute('PRAGMA user_version='+str(version))
            before=list(db.parent.iterdir())
            with self.assertRaisesRegex(ValueError,'explicit_upgrade'):
                self.results.current(self.sha)
            self.assertEqual(set(db.parent.iterdir()),set(before))
            self.assertEqual(self.reader.conn.execute('PRAGMA user_version').fetchone()[0],version)
        self.reader.conn.execute('PRAGMA user_version=2')

    def test_read_only_catalog_cannot_write_even_through_connection(self):
        catalog=Catalog(self.reader.data/'catalog/catalog.sqlite',read_only=True)
        self.addCleanup(catalog.close)
        with self.assertRaises(ValueError):catalog.initialize()
        with self.assertRaises(ValueError):
            with catalog.transaction():pass
        with self.assertRaises(sqlite3.OperationalError):catalog.conn.execute('DELETE FROM documents')
        self.assertEqual(self.quantities()['documents'],1)

    def test_corrupt_current_never_silently_reextracts_and_retry_uses_original(self):
        report=self.reader.data/self.doc['report_rel']; original=report.read_bytes()
        before=self.quantities(); report.write_text('{}')
        with mock.patch.object(self.app,'extractor',side_effect=AssertionError('must refuse')):
            with self.assertRaises(IntegrityError):self.app.pack(self.sha)
        self.assertFalse(self.app.packet_dir.exists())
        report.write_bytes(original)
        self.assertEqual(self.app.pack(self.sha)['reading_result']['status'],'available')
        self.assertEqual(self.quantities(),before)

    def test_changed_original_or_chunk_is_detected_by_both_consumers(self):
        extraction=read_json(self.reader.data/self.doc['artifact_rel']/'extraction.json')
        for path in (self.reader.data/self.doc['original_rel'],self.reader.data/extraction['chunks'][0]['text_rel']):
            path.chmod(0o600); before=path.read_bytes(); path.write_bytes(before+b' changed')
            with self.assertRaises(IntegrityError):self.results.current(self.sha)
            path.write_bytes(before)
        self.assertEqual(self.results.current(self.sha)['status'],'available')

    def test_report_reference_cannot_point_outside_the_sealed_artifact(self):
        for path in ('different-report.json',None):
            self.reader.conn.execute('UPDATE reading_runs SET report_rel=? WHERE revision_id=?',
                                     (path,self.doc['revision_id']))
            with self.assertRaises(IntegrityError):self.results.current(self.sha)
        stderr=io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(reader_cli.main(['--data-root',str(self.reader.data),'current','--sha',self.sha]),1)
        self.assertEqual(json.loads(stderr.getvalue())['error'],'integrity_mismatch')

    def test_packet_publication_failure_preserves_authority_and_retries_without_inference(self):
        before=self.quantities(); calls=len(self.f.model.calls)
        with mock.patch('inresearch.delivery.reading_packet.publish',side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):self.app.pack(self.sha)
        self.assertEqual(self.app.pack(self.sha)['packed'],1)
        self.assertEqual(self.quantities(),before);self.assertEqual(len(self.f.model.calls),calls)

    def test_ready_failed_retry_and_changed_model_do_not_change_shared_current(self):
        run=self.ready()
        self.assertEqual(self.results.current(self.sha)['reading_revision_id'],self.doc['revision_id'])
        self.f.model.identity={**self.f.model.identity,'model':'larger-future-model'}
        self.reader.retry(self.doc['doc_id'],run['revision_id'])
        self.assertEqual(self.app.current(self.sha)['reading_revision_id'],self.doc['revision_id'])
        self.reader.revisions.activate(*self.activation(run))
        self.assertEqual(self.app.current(self.sha)['reading_revision_id'],run['revision_id'])

    def test_pack_keeps_one_snapshot_during_independent_process_activation(self):
        run=self.ready(); args=self.activation(run)
        ctx=multiprocessing.get_context('spawn');gate=ctx.Event();replies=ctx.Queue()
        child=ctx.Process(target=revision_process,args=(str(self.f.base),'activate',args,gate,replies))
        child.start()
        original=self.results.artifacts.verify_seal
        def activate_during_read(doc):
            gate.set(); answer=replies.get(timeout=20)
            self.assertTrue(answer.get('current'),answer)
            return original(doc)
        try:
            with mock.patch.object(self.results.artifacts,'verify_seal',side_effect=activate_during_read):
                packed=self.app.pack(self.sha)
            child.join(20);self.assertEqual(child.exitcode,0)
        finally:
            if child.is_alive():child.terminate();child.join(5)
            replies.close();replies.join_thread()
        self.assertEqual(packed['reading_result']['reading_revision_id'],self.doc['revision_id'])
        self.assertEqual(self.app.current(self.sha)['reading_revision_id'],run['revision_id'])
        self.assertEqual(read_json(Path(packed['manifest']))['reading_result']['reading_revision_id'],self.doc['revision_id'])
        self.assertEqual(self.quantities()['documents'],1)

    def test_multipage_text_keeps_page_boundaries_and_blank_pages(self):
        # The shared text view consumes checked chunks; it never drops empty page identity.
        with mock.patch.object(self.results.artifacts,'_cached',return_value={'pages_total':3,'chunks':[
            {'page_index':1,'text':'first'}, {'page_index':3,'text':'last END'}]}), \
             mock.patch.object(self.results.artifacts,'_chunk_text',side_effect=lambda chunk:chunk['text']):
            text=self.results.artifacts.full_text(self.doc)
        self.assertEqual(text,'[第 1 页]\nfirst\n\n[第 2 页]\n\n\n[第 3 页]\nlast END')


if __name__ == '__main__':
    unittest.main()
