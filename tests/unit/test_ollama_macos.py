import json
import unittest
from unittest.mock import patch
from inresearch.adapters import ollama_macos as m, ollama_token_budget as b
from inresearch.adapters.models import InferenceError

class MacRuntimeTests(unittest.TestCase):
    def test_explicit_runtime_only(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertFalse(m.enabled())
        with patch.dict('os.environ', {'INRESEARCH_CAMPUS_RUNTIME':m.RUNTIME}):
            self.assertTrue(m.enabled())
        with patch.object(m.sys, 'platform', 'linux'):
            with self.assertRaises(InferenceError): m._require_host()

    def test_tokenizer_sends_raw_utf8_not_json(self):
        class Response:
            status=200
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def geturl(self): return 'http://127.0.0.1:54321/v1/tokenize'
            def read(self,n): return b'[101789,99449]'
        with patch.object(m.urllib.request,'build_opener') as factory:
            factory.return_value.open.return_value=Response()
            self.assertEqual(m.tokenize({'port':54321},'园区测试'),[101789,99449])
            request=factory.return_value.open.call_args.args[0]
            self.assertEqual(request.data,'园区测试'.encode())
            self.assertEqual(request.full_url,'http://127.0.0.1:54321/v1/tokenize')

    def test_resources_fail_closed_and_busy_waits(self):
        good='No thermal warning level has been recorded\nNo performance warning level has been recorded'
        with patch.object(m,'_require_host'),patch.object(m.subprocess,'check_output') as command:
            command.side_effect=[good,'"Device Utilization %"=37']
            self.assertEqual(m.resource_ready(),(False,'campus_waiting_for_gpu'))
            command.side_effect=[good,'"Device Utilization %"=2']
            self.assertEqual(m.resource_ready(),(True,''))
            command.side_effect=['thermal warning', '']
            self.assertEqual(m.resource_ready(),(False,'campus_waiting_for_temperature'))
            command.side_effect=[good,'no device']
            self.assertEqual(m.resource_ready(),(False,'campus_gpu_status_unavailable'))

    def test_process_uid_and_start_identity(self):
        with patch.object(m.os,'getuid',return_value=501),patch.object(m.subprocess,'check_output') as command:
            command.return_value='501 1237 Sat Oct 17 21:31:36 2026 '+m.EXECUTABLE+' runner --model qwen3.8:27b --port 50567'
            row=m._process(42)
            self.assertEqual(row['started'],'Sat Oct 17 21:31:36 2026')
            self.assertEqual(row['ppid'],1237)
            command.return_value='502 1237 Sat Oct 17 21:31:36 2026 '+m.EXECUTABLE+' serve'
            with self.assertRaises(InferenceError): m._process(42)

    def test_revalidation_rejects_changed_macos_model(self):
        with patch.object(b,'_model_identity',return_value={'runtime':m.RUNTIME,'manifest_sha256':'changed'}):
            from types import SimpleNamespace
            client=SimpleNamespace(profile=SimpleNamespace(url='http://127.0.0.1:11434'))
            with self.assertRaises(InferenceError):
                b.revalidate(client,{'model_binding':{'runtime':m.RUNTIME,'manifest_sha256':m.MANIFEST_SHA}})

    def test_disjoint_assignment_and_sha_change(self):
        from inresearch.materials.review_worker import campus_assignment
        item={'id':'a'*32,'sha256':'b'*64}
        with patch.dict('os.environ',{'INRESEARCH_INTAKE_ALLOW':json.dumps({item['id']:item['sha256']})},clear=True):
            self.assertTrue(campus_assignment(item))
            self.assertFalse(campus_assignment({'id':'c'*32,'sha256':'d'*64}))
            with self.assertRaises(ValueError): campus_assignment({**item,'sha256':'c'*64})
        with patch.dict('os.environ',{'INRESEARCH_INTAKE_EXCLUDE':json.dumps({item['id']:item['sha256']})},clear=True):
            self.assertFalse(campus_assignment(item))
            self.assertTrue(campus_assignment({'id':'c'*32,'sha256':'d'*64}))

    def test_runner_requires_exact_parent_and_loopback_listener(self):
        proc={'pid':42,'uid':501,'ppid':1237,'started':'fixed','command':m.EXECUTABLE+' runner --model qwen3.8:27b --port 54321'}
        parent={'pid':1237,'uid':501,'ppid':1,'started':'fixed','command':m.EXECUTABLE+' serve'}
        listing='42 '+proc['command']+'\n'
        status={'Status':0,'Progress':100,'ContextLength':262144}
        loaded={'models':[{'name':'qwen3.8:27b','digest':m.MANIFEST_SHA}]}
        with patch.object(m,'_require_host'),patch.object(m,'_process',side_effect=[proc,parent]),patch.object(m.subprocess,'check_output',side_effect=[listing,'p42\nn127.0.0.1:54321\n']),patch.object(b,'_call',side_effect=[status,loaded]):
            self.assertEqual(m.runner_identity({'manifest_sha256':m.MANIFEST_SHA})['port'],54321)
        with patch.object(m,'_require_host'),patch.object(m,'_process',side_effect=[proc,parent]),patch.object(m.subprocess,'check_output',side_effect=[listing,'p42\nn*:54321\n']):
            with self.assertRaises(InferenceError):m.runner_identity({'manifest_sha256':m.MANIFEST_SHA})
        with patch.object(m,'_require_host'),patch.object(m,'_process',side_effect=[proc,{**parent,'command':'unrelated serve'}]),patch.object(m.subprocess,'check_output',return_value=listing):
            with self.assertRaises(InferenceError):m.runner_identity({'manifest_sha256':m.MANIFEST_SHA})
