"""Provider outages and bounded, evidence-preserving OCR rescue."""
import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from inresearch.adapters import codex_inference, models
from inresearch.workflow.reading_stages import ReadingStages
from inresearch.materials.reader_contracts import Blocked, Deferred, IntegrityError


class FailureTests(unittest.TestCase):
    def test_relay_busy_hint_is_distinct_from_transport_outage(self):
        import io,os,urllib.error
        profile=models.ModelProfile(backend='codex_cli',url='http://127.0.0.1:37261',model='gpt-6.1-sol',api_key_env='TEST_CODEX_KEY')
        for reason,expected in [('relay_busy','model_relay_busy'),(None,'model_relay_unavailable')]:
            failure={'error':'model_relay_unavailable'}
            if reason:failure['reason']=reason
            error=urllib.error.HTTPError(profile.url,503,'Unavailable',{},io.BytesIO(json.dumps(failure).encode()))
            with mock.patch.dict(os.environ,{'TEST_CODEX_KEY':'private-test'}),mock.patch.object(codex_inference.urllib.request,'build_opener') as opener:
                opener.return_value.open.side_effect=error
                with self.assertRaises(models.InferenceError) as caught:
                    models.JsonModelClient(profile).generate('system','supplied text')
            self.assertEqual(caught.exception.code,expected)

    def test_failure_diagnostics_classify_waits_without_raw_secrets(self):
        for text, code in [('unexpected status 503: upstream unavailable','model_relay_unavailable'),
                           ('stream disconnected before completion','model_relay_unavailable'),
                           ('HTTP 429','model_quota_wait'),('unauthorized','model_cli_authentication_failed'),
                           ('unknown failure with PRIVATE-DOCUMENT','model_cli_failed')]:
            exc=codex_inference.cli_failure(1,[{'type':'turn.failed','error':{'message':text}}],'',2)
            self.assertEqual(exc.code,code)
            self.assertNotIn('PRIVATE-DOCUMENT',json.dumps(exc.diagnostics))
            self.assertEqual(len(exc.diagnostics['diagnostic_sha256']),64)

    def test_stderr_tail_is_seen_after_long_startup_warnings(self):
        profile=models.ModelProfile(backend='codex_cli',url='',model='gpt-6.1-sol',command='codex')
        def fail(command,**kw):
            kw['stdout'].write(b'{"type":"turn.failed"}\n')
            kw['stderr'].write(b'warning\n'*3000+b'HTTP 503 server unavailable\n')
            return SimpleNamespace(returncode=1)
        with mock.patch.object(codex_inference.subprocess,'run',side_effect=fail):
            with self.assertRaises(models.InferenceError) as caught:
                models.JsonModelClient(profile).generate('system','private data')
        self.assertEqual(caught.exception.code,'model_relay_unavailable')

    def test_process_timeout_classifies_observed_network_failure_without_persisting_text(self):
        import subprocess
        profile=models.ModelProfile(backend='codex_cli',url='',model='gpt-6.1-sol',command='codex')
        for detail,expected in [(b'stream disconnected: request timed out PRIVATE-DOCUMENT','model_relay_unavailable'),
                                (b'HTTP 429 private quota message','model_quota_wait'),
                                (b'no provider failure detail','model_cli_timeout')]:
            def timeout(command,**kw):
                kw['stderr'].write(detail)
                raise subprocess.TimeoutExpired(command,600)
            with mock.patch.object(codex_inference.subprocess,'run',side_effect=timeout):
                with self.assertRaises(models.InferenceError) as caught:
                    models.JsonModelClient(profile).generate('system','private data')
            self.assertEqual(caught.exception.code,expected)
            self.assertNotIn('PRIVATE-DOCUMENT',str(getattr(caught.exception,'diagnostics',{})))

    def test_scope_discloses_unread_pages_from_verified_current_reports(self):
        from inresearch.workflow.reader_scope import gap_counts
        with tempfile.TemporaryDirectory() as folder:
            data=Path(folder);path=data/'report.json'
            path.write_text(json.dumps({'coverage':{'gap_pages':[2,4]}}))
            row={'state':'complete','report_rel':'report.json','report_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(gap_counts(data,[row],{}),{'complete_with_gaps':1,'unread_gap_pages':2})
            with self.assertRaises(IntegrityError):gap_counts(data,[{**row,'report_sha256':'bad'}],{})

    def test_timeout_stdout_terminal_events_classify_transport_quota_and_auth(self):
        import subprocess
        profile=models.ModelProfile(backend='codex_cli',url='',model='gpt-6.1-sol',command='codex')
        for detail,expected in [('stream disconnected PRIVATE-TOKEN','model_relay_unavailable'),
                                ('HTTP 429 PRIVATE-DOCUMENT','model_quota_wait'),
                                ('HTTP 401 unauthorized PRIVATE-TOKEN','model_cli_authentication_failed')]:
            def timeout(command,**kw):
                kw['stdout'].write(json.dumps({'type':'error','message':detail}).encode()+b'\n')
                raise subprocess.TimeoutExpired(command,600)
            with mock.patch.object(codex_inference.subprocess,'run',side_effect=timeout):
                with self.assertRaises(models.InferenceError) as caught:
                    models.JsonModelClient(profile).generate('system','private data')
            self.assertEqual(caught.exception.code,expected)
            self.assertTrue(caught.exception.diagnostics['process_timeout'])
            self.assertEqual(caught.exception.diagnostics['terminal_events'],1)
            self.assertNotIn('PRIVATE-',json.dumps(caught.exception.diagnostics))

    def test_timeout_ignores_model_text_partial_json_and_oversize_records(self):
        import io
        cases=[json.dumps({'type':'item.completed','item':{'type':'agent_message',
                    'text':'HTTP 429 stream disconnected PRIVATE-DOCUMENT'}}).encode()+b'\n',
               b'{"type":"error","message":"HTTP 429"}',
               json.dumps({'type':'error','message':'HTTP 429 '+('x'*100000)}).encode()+b'\n']
        for raw in cases:
            exc=codex_inference.timeout_failure(io.BytesIO(raw),io.BytesIO(),600)
            self.assertEqual(exc.code,'model_cli_timeout')
            self.assertEqual(str(exc),'model_cli_timeout')
            self.assertEqual(exc.diagnostics['terminal_events'],0)
            self.assertEqual(exc.diagnostics['failure_kind'],'unclassified')
            self.assertNotIn('PRIVATE-',json.dumps(exc.diagnostics))

    def test_timeout_reads_bounded_slices_and_finds_error_after_large_output(self):
        import io
        class Bounded(io.BytesIO):
            def read(self,size=-1):
                self.assert_bounded(size)
                return super().read(size)
            def assert_bounded(self,size):
                if not 0<=size<=65536:raise AssertionError('unbounded diagnostic read')
        stdout=Bounded(b'x'*200000+b'\n'+b'{"type":"turn.failed","error":{"message":"HTTP 503"}}\n')
        stderr=Bounded(b'warning\n'*20000)
        exc=codex_inference.timeout_failure(stdout,stderr,601.23456)
        self.assertEqual(exc.code,'model_relay_unavailable')
        self.assertTrue(exc.diagnostics['stdout_truncated'])
        self.assertTrue(exc.diagnostics['stderr_truncated'])
        self.assertEqual(exc.diagnostics['terminal_events'],1)
        self.assertEqual(exc.diagnostics['elapsed_seconds'],601.235)

    def test_timeout_stderr_head_survives_long_warning_tail(self):
        import io
        exc=codex_inference.timeout_failure(io.BytesIO(),
            io.BytesIO(b'HTTP 401 unauthorized PRIVATE-TOKEN\n'+b'warning\n'*3000),600)
        self.assertEqual(exc.code,'model_cli_authentication_failed')
        self.assertTrue(exc.diagnostics['stderr_truncated'])
        self.assertNotIn('PRIVATE-',json.dumps(exc.diagnostics))


class RescueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);ident='doc-'+'a'*64
        self.doc={'doc_id':ident,'sha256':'a'*64,'revision_id':'rev-test','artifact_rel':'artifacts/'+ident+'/revisions/rev-test'}

    def run_page(self,reads,allow_gaps=False):
        model=SimpleNamespace(ocr_model='requested-model',vision_rescue=object(),allow_ocr_gaps=allow_gaps,ocr=mock.Mock(side_effect=reads))
        stages=ReadingStages(self.root,model,20,1150)
        stages._command=mock.Mock(return_value='Page 1 size: 612 x 792 pts')
        with mock.patch('inresearch.workflow.reading_stages.shutil.which',return_value='/tool'):
            return stages._ocr_page(self.doc,self.root/'original.pdf',1)

    @staticmethod
    def read(text,unreadable=False):
        return {'text':text,'blank':False,'unreadable':unreadable,'_model':{'requested':'model','actual':None}}

    def test_rescue_keeps_failed_reads_and_accepts_only_an_agreeing_pair(self):
        page=self.run_page([self.read('300 W'),self.read('800 W'),self.read('400 W'),self.read('500 W'),self.read('400 W')])
        self.assertEqual(page['text'],'400 W');self.assertEqual(page['text_second_pass'],'400 W')
        self.assertEqual(page['render_scale'],3200)
        history=json.loads(next(self.root.rglob('ocr-attempts/*.json')).read_text())
        self.assertEqual(history['initial_reason'],'ocr_numbers_disagree')
        self.assertEqual(len(history['normal_reads']),2);self.assertEqual(len(history['rescue_reads']),3)
        self.assertEqual(history['content_sha256'],self.doc['sha256'])

    def test_unreadable_or_disagreeing_rescue_still_blocks(self):
        for reads in ([self.read('300 W'),self.read('800 W'),self.read('1 W'),self.read('2 W'),self.read('3 W')],
                      [self.read('',True)]*5):
            with self.subTest(reads=reads):
                with self.assertRaises(Blocked):self.run_page(reads)
        self.assertTrue(list(self.root.rglob('ocr-attempts/*.json')))

    def test_codex_extraction_yields_after_one_new_vision_page(self):
        raw=b'%PDF-test';source=self.root/'original.pdf';source.write_bytes(raw)
        doc={**self.doc,'sha256':hashlib.sha256(raw).hexdigest(),'original_rel':'original.pdf',
             'extracted_rel':'extracted/'+self.doc['doc_id']+'/revisions/rev-test','suffix':'.pdf','priority':1}
        model=SimpleNamespace(backend='codex_cli',ocr_model='model',ocr=mock.Mock(return_value=self.read('300 W')))
        stages=ReadingStages(self.root,model,20,1150)
        def command(args,*a,**kw):
            if args[0]=='pdfimages':return '1 0 image 500 500\n2 1 image 500 500'
            if args[0]=='pdfinfo':return 'Pages: 2\nPage 1 size: 612 x 792 pts'
            if args[0]=='pdftotext':return 'Body text'
            return ''
        stages._command=mock.Mock(side_effect=command)
        with mock.patch('inresearch.workflow.reading_stages.shutil.which',return_value='/tool'):
            with self.assertRaises(Deferred) as caught:stages._extract(doc)
        self.assertEqual(caught.exception.code,'ocr_checkpoint_yield')
        self.assertEqual(model.ocr.call_count,2)
        page=json.loads((self.root/doc['extracted_rel']/'pages/000001.json').read_text())
        self.assertEqual(page['text'],'300 W')

    def test_opted_in_gap_is_empty_and_preserves_failed_evidence(self):
        page=self.run_page([self.read('',True)]*5,allow_gaps=True)
        self.assertTrue(page['gap']);self.assertEqual(page['method'],'vision_ocr_gap')
        self.assertEqual(page['text'],'');self.assertEqual(page['text_second_pass'],'')
        history=json.loads((self.root/page['attempts_rel']).read_text())
        self.assertEqual(history['outcome'],'explicit_gap')
        self.assertEqual(len(history['rescue_reads']),3)


if __name__=='__main__':unittest.main()
