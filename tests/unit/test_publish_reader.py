
from inresearch.paths import project_root
import contextlib
import io
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from inresearch.delivery import publish as publish_reader


class PublisherTests(unittest.TestCase):
    def test_invalid_manifest_route_rejects_before_reader_or_private_token_access(self):
        for endpoint in ['http://receiver.test/api/reader-snapshot','https://user:secret@receiver.test/api/reader-snapshot',
                         'https://receiver.test/api/reader-snapshot?token=private','https://receiver.test/other',
                         'https://receiver.test/api/reader-snapshot#fragment']:
            with self.subTest(endpoint=endpoint),patch.dict(os.environ,{'READER_PUBLISH_MANIFEST_URL':endpoint}),patch.object(publish_reader,'Reader') as reader:
                with self.assertRaisesRegex(ValueError,'manifest requires'):publish_reader.main([])
                reader.assert_not_called()

    def test_transient_deployment_errors_retry_identical_snapshot_without_waiting_for_timer(self):
        request = publish_reader.urllib.request.Request('https://receiver.example.test/api/reader-snapshot', data=b'fixed-body')
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.headers = {}
        response.__enter__.return_value.read.return_value = b'{"ok":true,"received_at":"original-commit","replayed":true}'
        errors = [urllib.error.HTTPError(request.full_url, code, 'deployment', {}, io.BytesIO(b'')) for code in (502,503)]
        with patch.object(publish_reader.urllib.request,'build_opener') as opener, patch.object(publish_reader.time,'sleep') as sleep:
            opener.return_value.open.side_effect = [*errors,response]
            reply, attempts = publish_reader.post_snapshot(request)
            self.assertEqual(attempts,3)
            self.assertTrue(reply['replayed'])
            self.assertEqual([call.args[0] for call in opener.return_value.open.call_args_list],[request]*3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list],[1,3])

    def test_transient_retry_is_bounded_and_validation_failures_are_not_retried(self):
        request = publish_reader.urllib.request.Request('https://receiver.example.test/api/reader-snapshot', data=b'fixed-body')
        for code, count in [(503,3),(400,1),(401,1),(409,1)]:
            with self.subTest(code=code),patch.object(publish_reader.urllib.request,'build_opener') as opener,patch.object(publish_reader.time,'sleep'):
                opener.return_value.open.side_effect = urllib.error.HTTPError(request.full_url,code,'failure',{},io.BytesIO(b''))
                with self.assertRaisesRegex(ValueError,'HTTP '+str(code)):
                    publish_reader.post_snapshot(request)
                self.assertEqual(opener.return_value.open.call_count,count)

    def test_slow_receipt_uses_one_decreasing_deadline_and_stops_after_budget(self):
        request=publish_reader.urllib.request.Request('https://receiver.example.test/api/reader-snapshot',data=b'fixed-body')
        response=unittest.mock.MagicMock()
        response.__enter__.return_value.headers={}
        response.__enter__.return_value.read.return_value=b'{"ok":true}'
        with patch.object(publish_reader.urllib.request,'build_opener') as opener, \
             patch.object(publish_reader.time,'monotonic',side_effect=[0,0,130,131]), \
             patch.object(publish_reader.time,'sleep'):
            opener.return_value.open.side_effect=[TimeoutError('slow validated receipt'),response]
            reply,attempts=publish_reader.post_snapshot(request)
            self.assertTrue(reply['ok']);self.assertEqual(attempts,2)
            budgets=[call.kwargs['timeout'] for call in opener.return_value.open.call_args_list]
            self.assertGreater(budgets[0],120)
            self.assertEqual(budgets[0]-budgets[1],131)  # Retry never resets the total budget.
        with patch.object(publish_reader.urllib.request,'build_opener') as opener, \
             patch.object(publish_reader.time,'monotonic',side_effect=[0,0,241]), \
             patch.object(publish_reader.time,'sleep') as sleep:
            opener.return_value.open.side_effect=TimeoutError('budget consumed')
            with self.assertRaisesRegex(ValueError,'retry budget exhausted'):
                publish_reader.post_snapshot(request)
            self.assertEqual(opener.return_value.open.call_count,1)
            sleep.assert_not_called()

    def test_gzip_manifest_is_decoded_with_wire_and_inflated_bounds(self):
        request=publish_reader.urllib.request.Request('https://receiver.example.test/api/reader-snapshot',data=b'{}')
        body=json.dumps({'ok':True,'document_hashes':{'doc-a':'a'*64}}).encode()
        wire=gzip.compress(body)
        response=unittest.mock.MagicMock()
        response.__enter__.return_value.headers={'Content-Encoding':'gzip','Content-Length':str(len(wire))}
        response.__enter__.return_value.read.return_value=wire
        with patch.object(publish_reader.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value=response
            value,attempts=publish_reader.post_snapshot(request,max_response_bytes=1024)
        self.assertEqual(value,json.loads(body));self.assertEqual(attempts,1)
        self.assertEqual(request.get_header('Accept-encoding'),'gzip')
        response.__enter__.return_value.read.assert_called_once_with(1025)

    def test_gzip_bomb_corruption_trailing_data_and_unknown_encoding_are_rejected(self):
        request=publish_reader.urllib.request.Request('https://receiver.example.test/api/reader-snapshot',data=b'{}')
        cases=[(gzip.compress(b'x'*10000),'gzip','inflated'),
               (b'not-gzip','gzip','corrupt'),
               (gzip.compress(b'{}')+b'trailing','gzip','trailing'),
               (b'{}','br','unsupported')]
        for wire,encoding,expected in cases:
            response=unittest.mock.MagicMock();response.__enter__.return_value.headers={'Content-Encoding':encoding}
            response.__enter__.return_value.read.return_value=wire
            with self.subTest(expected=expected),patch.object(publish_reader.urllib.request,'build_opener') as opener:
                opener.return_value.open.return_value=response
                with self.assertRaisesRegex(ValueError,expected):publish_reader.post_snapshot(request,max_response_bytes=128)
                self.assertEqual(opener.return_value.open.call_count,1)

    def test_truncated_manifest_retries_same_request_and_oversize_header_does_not_read(self):
        request=publish_reader.urllib.request.Request('https://receiver.example.test/api/reader-snapshot',data=b'{}')
        truncated=unittest.mock.MagicMock();truncated.__enter__.return_value.headers={'Content-Length':'100'}
        truncated.__enter__.return_value.read.return_value=b'{'
        complete=unittest.mock.MagicMock();complete.__enter__.return_value.headers={}
        complete.__enter__.return_value.read.return_value=b'{"ok":true}'
        with patch.object(publish_reader.urllib.request,'build_opener') as opener,patch.object(publish_reader.time,'sleep'):
            opener.return_value.open.side_effect=[truncated,complete]
            result,attempts=publish_reader.post_snapshot(request)
            self.assertTrue(result['ok']);self.assertEqual(attempts,2)
            self.assertEqual([c.args[0] for c in opener.return_value.open.call_args_list],[request,request])
        truncated.__enter__.return_value.headers={'Content-Encoding':'gzip'}
        truncated.__enter__.return_value.read.return_value=gzip.compress(b'{}')[:-4]
        with patch.object(publish_reader.urllib.request,'build_opener') as opener,patch.object(publish_reader.time,'sleep'):
            opener.return_value.open.side_effect=[truncated,complete]
            self.assertEqual(publish_reader.post_snapshot(request)[1],2)
        from http.client import IncompleteRead
        truncated.__enter__.return_value.read.side_effect=IncompleteRead(b'{',100)
        with patch.object(publish_reader.urllib.request,'build_opener') as opener,patch.object(publish_reader.time,'sleep'):
            opener.return_value.open.side_effect=[truncated,complete]
            self.assertEqual(publish_reader.post_snapshot(request)[1],2)
        complete.__enter__.return_value.headers={'Content-Length':'129'}
        complete.__enter__.return_value.read.reset_mock()
        with patch.object(publish_reader.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value=complete
            with self.assertRaisesRegex(ValueError,'bounded'):publish_reader.post_snapshot(request,max_response_bytes=128)
        complete.__enter__.return_value.read.assert_not_called()

    def test_unchanged_poll_skips_export_and_keeps_last_acknowledgement(self):
        with tempfile.TemporaryDirectory() as temp:
            state=Path(temp);token=state/'reader-sync.token';token.write_text('private-test-'*4);token.chmod(0o600)
            marker={'readings':[1,1,100,2]}
            (state/'publish-trigger.json').write_text(json.dumps({'marker':marker,'acknowledged_at':publish_reader.time.time()}))
            status=state/'publish-status.json';status.write_text('{"status":"ok","received_at":"previous"}')
            with patch.dict(os.environ,{'READER_STATE_ROOT':str(state)}),patch.object(publish_reader,'change_marker',return_value=marker),patch.object(publish_reader,'Reader') as reader,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(publish_reader.main(['--if-changed']),0)
                reader.assert_not_called()
            self.assertEqual(json.loads(status.read_text())['received_at'],'previous')

    def publish(self, worker_code=0, external=None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / 'state'
            state.mkdir()
            if external is not None:
                (state / 'external-snapshots').mkdir()
                (state / 'external-snapshots' / 'm4.json').write_text(json.dumps(external))
            token = state / 'reader-sync.token'
            token.write_text('test-credential-' * 4)
            token.chmod(0o600)
            env = {'READER_DATA_ROOT': str(root / 'data'), 'READER_STATE_ROOT': str(state),
                   'READER_BACKEND': 'ollama', 'READER_URL': 'http://127.0.0.1:11434',
                   'READER_MODEL': 'configured-test-model',
                   'READER_OCR_MODEL': 'qwen3-vl:8b',
                   'READER_PUBLISH_URL': 'https://receiver.example.test/api/reader-snapshot'}
            with patch.dict(os.environ, env), patch.object(publish_reader.subprocess, 'run') as run, \
                    patch.object(publish_reader.urllib.request, 'build_opener') as opener, \
                    contextlib.redirect_stdout(io.StringIO()):
                run.return_value.returncode = worker_code
                response = opener.return_value.open.return_value.__enter__.return_value
                response.headers = {}
                response.read.return_value = b'{"ok":true,"received_at":"2026-09-06T00:00:00Z"}'
                self.assertEqual(0, publish_reader.main([]))
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual('Bearer ' + token.read_text(), request.get_header('Authorization'))
                self.assertEqual('ok', json.loads((state / 'publish-status.json').read_text())['status'])
                self.assertEqual("gzip", request.get_header("Content-encoding"))
                return json.loads(gzip.decompress(request.data))

    def test_published_model_configuration_matches_worker_environment(self):
        snapshot = self.publish()
        self.assertEqual('qwen3-vl:8b', snapshot['reader']['backend']['ocr_model'])
        self.assertEqual('configured-test-model', snapshot['reader']['backend']['model'])
        self.assertEqual(json.loads((project_root() / 'framework/research_graph.json').read_text())['version'], snapshot['graph_version'])
        self.assertEqual([], snapshot['knowledge']['answers'])

    def test_readings_from_another_worker_are_overlaid_on_every_publish(self):
        entry = {'doc_id': 'doc-m4', 'id': 'doc-m4', 'coverage': {'complete': True}, 'acceptance': 'candidate'}
        statement = {'id': 'doc-m4:s0', 'document_id': 'doc-m4', 'acceptance': 'candidate'}
        external = {'schema_version': 1, 'generated': '2026-09-28T05:00:00Z', 'acceptance': 'candidate',
                    'knowledge': {'documents': [entry], 'evidence': [], 'statements': [statement], 'answers': []}}
        snapshot = self.publish(external=external)
        self.assertEqual([d['projection_source'] for d in snapshot['knowledge']['documents'] if d['doc_id'] == 'doc-m4'],
                         ['external:m4.json'])
        self.assertIn(statement, snapshot['knowledge']['statements'])
        self.assertEqual(snapshot['reader']['external_overlay'], {'added': 1, 'kept_spark_reading': 0, 'dropped_unknown_ids': 0, 'files': ['m4.json']})
        self.assertEqual(self.publish()['reader']['external_overlay'], {'added': 0, 'kept_spark_reading': 0, 'dropped_unknown_ids': 0, 'files': []})

    def test_a_refused_publish_reports_the_receivers_reason(self):
        import urllib.error
        refusal = urllib.error.HTTPError('https://receiver.example.test/api/reader-snapshot', 400, 'Bad Request', {},
                                         io.BytesIO('{"ok": false, "error": "reader graph_version does not match deployed framework"}'.encode()))
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            token = state / 'reader-sync.token'
            token.write_text('test-credential-' * 4)
            token.chmod(0o600)
            env = {'READER_DATA_ROOT': str(state / 'data'), 'READER_STATE_ROOT': str(state),
                   'READER_BACKEND': 'ollama', 'READER_URL': 'http://127.0.0.1:11434', 'READER_MODEL': 'm',
                   'READER_PUBLISH_URL': 'https://receiver.example.test/api/reader-snapshot'}
            with patch.dict(os.environ, env), patch.object(publish_reader.subprocess, 'run') as run, \
                    patch.object(publish_reader.urllib.request, 'build_opener') as opener:
                run.return_value.returncode = 0
                opener.return_value.open.side_effect = refusal
                with self.assertRaisesRegex(ValueError, 'HTTP 400 .*graph_version does not match'):
                    publish_reader.main([])

    def test_stopped_worker_is_not_reported_as_healthy_idle(self):
        snapshot = self.publish(worker_code=3)
        self.assertEqual('degraded', snapshot['reader']['status'])
        self.assertEqual('worker_service_inactive', snapshot['reader']['recent_failures'][-1]['error_code'])

    def test_external_snapshot_relay_uses_spark_token_without_opening_reader(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / 'state'
            state.mkdir()
            token = state / 'reader-sync.token'
            token.write_text('spark-only-credential-' * 3)
            token.chmod(0o600)
            candidate = root / 'candidate.json'
            payload = {'reader': {'status': 'ok'}, 'knowledge': {'documents': [
                {'id': 'nvidia:a100', 'acceptance': 'candidate', 'coverage': {'complete': True}}]}}
            candidate.write_text(json.dumps(payload))
            env = {'READER_STATE_ROOT': str(state),
                   'READER_PUBLISH_URL': 'https://receiver.example.test/api/reader-snapshot'}
            with patch.dict(os.environ, env), patch.object(sys, 'argv', ['publish', '--snapshot', str(candidate)]), \
                    patch.object(publish_reader, 'Reader') as reader, \
                    patch.object(publish_reader, 'ModelClient') as model, \
                    patch.object(publish_reader.urllib.request, 'build_opener') as opener, \
                    contextlib.redirect_stdout(io.StringIO()):
                response = opener.return_value.open.return_value.__enter__.return_value
                response.headers = {}
                response.read.return_value = b'{"ok":true,"received_at":"2026-09-27T00:00:00Z"}'
                self.assertEqual(0, publish_reader.main())
                reader.assert_not_called()
                model.assert_not_called()
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual('Bearer ' + token.read_text(), request.get_header('Authorization'))
                self.assertEqual(payload, json.loads(gzip.decompress(request.data)))
                result = json.loads((state / 'publish-relay-status.json').read_text())
                self.assertEqual('external_candidate_snapshot', result['source'])

    def test_external_snapshot_relay_rejects_non_candidate_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / 'state'
            state.mkdir()
            token = state / 'reader-sync.token'
            token.write_text('spark-only-credential-' * 3)
            token.chmod(0o600)
            candidate = root / 'candidate.json'
            candidate.write_text(json.dumps({'knowledge': {'documents': [
                {'id': 'promoted', 'acceptance': 'adopted', 'coverage': {'complete': True}}]}}))
            with patch.dict(os.environ, {'READER_STATE_ROOT': str(state)}), \
                    patch.object(sys, 'argv', ['publish', '--snapshot', str(candidate)]), \
                    self.assertRaisesRegex(ValueError, 'candidates only'):
                publish_reader.main()

    def test_external_snapshot_relay_rejects_incomplete_reading(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / 'state'
            state.mkdir()
            token = state / 'reader-sync.token'
            token.write_text('spark-only-credential-' * 3)
            token.chmod(0o600)
            candidate = root / 'candidate.json'
            candidate.write_text(json.dumps({'knowledge': {'documents': [
                {'id': 'incomplete', 'acceptance': 'candidate', 'coverage': {'complete': False}}]}}))
            with patch.dict(os.environ, {'READER_STATE_ROOT': str(state)}), \
                    patch.object(sys, 'argv', ['publish', '--snapshot', str(candidate)]), \
                    self.assertRaisesRegex(ValueError, 'complete reading coverage'):
                publish_reader.main()


if __name__ == '__main__':
    unittest.main()
