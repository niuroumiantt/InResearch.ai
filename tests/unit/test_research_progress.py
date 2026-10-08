import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone

from inresearch.knowledge import registry
from inresearch.workflow.research_publish import Publisher
from inresearch.workflow import supply
from inresearch.paths import project_root


class ResearchProgressTests(unittest.TestCase):
    def test_receiver_counts_reach_supply_without_changing_research_authority(self):
        root = project_root()
        graph = json.loads((root/'framework/research_graph.json').read_text())
        questions = json.loads((root/'framework/research_questions.json').read_text())
        progress = {'state': 'observed', 'active_batches': 1, 'candidates': {'queued': 12, 'published': 1}}
        payload = {'generated': datetime.now(timezone.utc).isoformat(), 'graph_version': graph['version'],
                   'questions_version': questions['version'], 'reader': {'research_verification': progress},
                   'knowledge': {k: [] for k in registry.COLLECTIONS}}
        received = registry.candidate_snapshot(payload, graph, questions)
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT': td}), \
             patch.object(registry, '_snapshot_inputs', return_value=[received]):
            result = supply.snapshot(root)
        self.assertEqual(result['research_verification']['candidates'], progress['candidates'])
        self.assertEqual(result['research_verification']['active_batches'], 1)
        self.assertTrue(all(not rows for rows in received['knowledge'].values()))

    def test_invalid_measurements_are_unavailable_without_fabricated_zero(self):
        for value in (None, {'state': 'published'},
                      {'state': 'observed', 'candidates': {'queued': True}, 'active_batches': 0},
                      {'state': 'observed', 'candidates': {'published': -1}, 'active_batches': 0},
                      {'state': 'observed', 'candidates': {}, 'active_batches': '2'},
                      {'state': 'observed', 'candidates': {}, 'active_batches': 0, 'generated': 'yesterday'}):
            self.assertEqual(registry._research_verification(value), {'state': 'unavailable', 'candidates': {}})

    def test_only_allowed_counts_cross_receiver_boundary(self):
        value = {'state': 'observed', 'candidates': {'published': 1, '/private/raw': 'SECRET'},
                 'active_batches': 0, 'raw_quote': 'SECRET', 'unit': 'GW'}
        result = registry._research_verification(value)
        self.assertEqual(result['candidates'], {'published': 1})
        self.assertEqual(result['unit'], 'candidate statements, not materials or GW')
        self.assertNotIn('SECRET', json.dumps(result))

    def test_existing_publication_journal_does_not_depend_on_new_queue_poll(self):
        with tempfile.TemporaryDirectory() as td:
            publisher = Publisher({'repo': td, 'state': td})
            directory = Path(td)/'a';directory.mkdir()
            journal = {'state': 'merged', 'batch_id': 'a'*64}
            (directory/'journal.json').write_text(json.dumps(journal))
            with patch.object(publisher, 'remote', side_effect=RuntimeError('Spark unavailable')), \
                 patch.object(publisher, 'advance', return_value={'state': 'published'}) as advance:
                self.assertEqual(publisher.tick(), {'state': 'published'})
                advance.assert_called_once_with(directory, journal)

    def test_source_sync_fetches_only_main_and_preserves_dirty_checkout(self):
        with tempfile.TemporaryDirectory() as td:
            publisher = Publisher({'repo': td, 'state': td})
            with patch.object(publisher, 'ssh') as ssh:
                ssh.return_value.stdout = ''
                publisher.sync_source()
                self.assertEqual(ssh.call_args_list[1].args[0],
                                 ['env', 'GIT_TERMINAL_PROMPT=0', 'git', '-C', publisher.spark_root, 'fetch', 'origin', 'main'])
                ssh.reset_mock();ssh.return_value.stdout = ' M active.py'
                with self.assertRaisesRegex(ValueError, 'dirty_preserve'):publisher.sync_source()
                self.assertEqual(ssh.call_count, 1)
