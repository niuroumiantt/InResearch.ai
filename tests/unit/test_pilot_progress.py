import json
import os
import tempfile
import unittest
from pathlib import Path

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
        snapshot = json.loads(Path('/tmp/inresearch-m5-nvidia-pilot.14cpTZ/exports/nvidia-three-complete-candidate.json').read_text())
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


if __name__ == '__main__':
    unittest.main()
