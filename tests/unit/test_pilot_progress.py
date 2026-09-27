import json
import os
import tempfile
import unittest
from pathlib import Path
import contextlib
import io
from unittest.mock import patch

from inresearch.delivery import publish_pilot_progress
from inresearch.workflow import pilot_progress


class PilotProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'framework').mkdir()
        source = Path(__file__).resolve().parents[2] / 'framework'
        for name in ('research_graph.json', 'research_questions.json'):
            (self.root / 'framework' / name).write_bytes((source / name).read_bytes())
        self.target = self.root / 'pilot.json'
        self.old = os.environ.get('INRESEARCH_NVIDIA_PILOT_PROGRESS')
        os.environ['INRESEARCH_NVIDIA_PILOT_PROGRESS'] = str(self.target)
        # Built from the checked-in framework, not a file left in M5's /tmp (absent in CI).
        snapshot = {'graph_version': json.loads((self.root / 'framework/research_graph.json').read_text())['version'],
                    'questions_version': json.loads((self.root / 'framework/research_questions.json').read_text())['version'],
                    'generated': '2026-09-27T06:00:00Z', 'knowledge': {}, 'reader': {}}
        # Unit fixture with no dependency on M5's ephemeral temporary directory.
        snapshot['knowledge']['documents'] = [{
            'id': 'doc-' + 'a' * 64, 'content_sha256': 'a' * 64,
            'title': 'NVIDIA A100 datasheet', 'acceptance': 'candidate',
            'coverage': {'complete': True, 'pages_read': 3, 'pages_total': 3,
                'chunks_read': 1, 'chunks_total': 1, 'characters_read': 100, 'characters_total': 100},
            'sources': [], 'question_ids': [], 'object_ids': []}]
        for key in ('answers', 'evidence', 'statements'):
            snapshot['knowledge'][key] = []
        self.payload = {'schema_version': 1, 'status': {'acceptance': 'candidate_only',
            'backend': {'backend': 'claude_cli'}, 'generated': '2026-09-27T06:00:00Z',
            'counts': {'complete': 1, 'blocked': 0, 'failed': 0}, 'documents_total': 1},
            'snapshot': snapshot}

    def tearDown(self):
        if self.old is None:
            os.environ.pop('INRESEARCH_NVIDIA_PILOT_PROGRESS', None)
        else:
            os.environ['INRESEARCH_NVIDIA_PILOT_PROGRESS'] = self.old
        self.tmp.cleanup()

    def test_receive_projects_candidate_only_status_and_is_idempotently_rejected(self):
        result = pilot_progress.receive(self.root, self.payload)
        self.assertTrue(result['ok'])
        page = pilot_progress.public_snapshot(self.root)
        self.assertEqual(page['acceptance'], 'candidate_only')
        self.assertEqual(page['counts']['complete'], 1)
        self.assertNotIn('knowledge', page)
        with self.assertRaisesRegex(ValueError, 'stale or repeated'):
            pilot_progress.receive(self.root, self.payload)

    def test_rejects_incomplete_or_non_claude_payload(self):
        bad = json.loads(json.dumps(self.payload))
        bad['status']['backend']['backend'] = 'spark_reader'
        with self.assertRaisesRegex(ValueError, 'M5 Claude'):
            pilot_progress.receive(self.root, bad)

    def test_receiver_credential_resolves_inside_deployed_runtime(self):
        runtime = self.root / 'runtime'
        with patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT': str(runtime)}, clear=False):
            os.environ.pop('INRESEARCH_PILOT_TOKEN_FILE', None)
            self.assertEqual(runtime / 'data/.nvidia_pilot_token', pilot_progress.token_path(self.root))


class PilotPublisherTests(unittest.TestCase):
    def test_publisher_posts_with_private_token_and_requires_receiver_ack(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            status = root / 'status.json'
            snapshot = root / 'candidate.json'
            token = root / 'pilot.token'
            status.write_text(json.dumps({'generated': '2026-09-27T07:34:17Z'}))
            snapshot.write_text(json.dumps({'knowledge': {'documents': [{'title': 'A100'}]}}))
            token.write_text('test-pilot-credential-' * 2)
            token.chmod(0o600)
            env = {'INRESEARCH_PILOT_TOKEN_FILE': str(token),
                   'INRESEARCH_PILOT_PROGRESS_URL': 'https://receiver.example.test/api/pilot-progress/nvidia'}
            with patch.dict(os.environ, env), \
                    patch.object(publish_pilot_progress.urllib.request, 'build_opener') as build_opener, \
                    contextlib.redirect_stdout(io.StringIO()):
                response = build_opener.return_value.open.return_value.__enter__.return_value
                response.read.return_value = b'{"ok":true,"received_at":"2026-09-27T07:35:00Z"}'
                self.assertEqual(0, publish_pilot_progress.main([
                    '--status', str(status), '--snapshot', str(snapshot)]))
                build_opener.assert_called_once_with(publish_pilot_progress.NoRedirect)
                request = build_opener.return_value.open.call_args.args[0]
                self.assertEqual('Bearer ' + token.read_text(), request.get_header('Authorization'))
                self.assertEqual('https://receiver.example.test/api/pilot-progress/nvidia', request.full_url)
                self.assertEqual('POST', request.get_method())
                self.assertEqual({'generated': '2026-09-27T07:34:17Z'}, json.loads(request.data)['status'])


if __name__ == '__main__':
    unittest.main()
