import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import publish_reader


class PublisherTests(unittest.TestCase):
    def publish(self, worker_code=0):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / 'state'
            state.mkdir()
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
                self.assertEqual(0, publish_reader.main())
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual('Bearer ' + token.read_text(), request.get_header('Authorization'))
                self.assertEqual('ok', json.loads((state / 'publish-status.json').read_text())['status'])
                return json.loads(request.data)

    def test_published_model_configuration_matches_worker_environment(self):
        snapshot = self.publish()
        self.assertEqual('qwen3-vl:8b', snapshot['reader']['backend']['ocr_model'])
        self.assertEqual('configured-test-model', snapshot['reader']['backend']['model'])
        self.assertEqual(json.loads((Path(__file__).resolve().parents[1] / 'framework/research_graph.json').read_text())['version'], snapshot['graph_version'])
        self.assertEqual([], snapshot['knowledge']['answers'])

    def test_stopped_worker_is_not_reported_as_healthy_idle(self):
        snapshot = self.publish(worker_code=3)
        self.assertEqual('degraded', snapshot['reader']['status'])
        self.assertEqual('worker_service_inactive', snapshot['reader']['recent_failures'][-1]['error_code'])


if __name__ == '__main__':
    unittest.main()
