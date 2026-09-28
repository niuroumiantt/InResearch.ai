
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
from unittest.mock import patch

from inresearch.delivery import publish as publish_reader


class PublisherTests(unittest.TestCase):
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
