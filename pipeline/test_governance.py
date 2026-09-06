"""Regression checks for replacement integrity, file drift and historical isolation."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import governance as g
from data_policy import price_series_freq, price_series_limit


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        for name in ['framework/live.md', 'docs/archive/old.md']:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('old forbidden assertion')
        self.state = {'version': 'test', 'entrypoints': [], 'retired_entrypoints': [],
                      'known_retired_patterns': ['forbidden assertion'], 'policies': [
            {'id': 'new', 'topic': 'data', 'scope': 'project', 'status': 'current',
             'source': 'framework/live.md', 'effective_at': '2026-09-06', 'reason': 'adopted update',
             'supersedes': ['old']},
            {'id': 'old', 'topic': 'data', 'scope': 'project', 'status': 'superseded',
             'source': 'docs/archive/old.md', 'supersedes': [], 'superseded_by': 'new'}]}

    def test_replacement_valid_then_parallel_current_rejected(self):
        self.assertEqual(g.policy_errors(self.state, self.root), [])
        another = copy.deepcopy(self.state['policies'][0])
        another.update(id='parallel', supersedes=[])
        self.state['policies'].append(another)
        self.assertTrue(any('multiple current' in e for e in g.policy_errors(self.state, self.root)))

    def test_broken_replacement_and_archive_source_rejected(self):
        self.state['policies'][1]['superseded_by'] = 'missing'
        self.state['policies'][1]['source'] = 'framework/live.md'
        errors = g.policy_errors(self.state, self.root)
        self.assertTrue(any('backlink' in e for e in errors))
        self.assertTrue(any('archived' in e for e in errors))
        self.assertTrue(any('inconsistent replacement' in e for e in errors))

    def test_replacement_cycle_rejected(self):
        self.state['policies'][1]['supersedes'] = ['new']
        self.assertTrue(any('cycle' in e for e in g.policy_errors(self.state, self.root)))

    def test_inventory_detects_added_and_modified_records_excludes_ignored(self):
        (self.root / '.gitignore').write_text('private/\n')
        (self.root / 'private').mkdir()
        (self.root / 'private/secret.txt').write_text('not inventoried')
        before = g.build_manifest(self.state, self.root)
        (self.root / 'records.csv').write_text('id,value\na,1\nb,2\n')
        (self.root / 'framework/live.md').write_text('current rule')
        after = g.build_manifest(self.state, self.root)
        self.assertNotEqual(before, after)
        rows = {row['path']: row for row in after['files']}
        self.assertNotIn('private/secret.txt', rows)
        self.assertEqual(rows['records.csv']['collections'][0]['count'], 2)
        self.assertEqual(rows['framework/live.md']['sha256'], hashlib.sha256(b'current rule').hexdigest())
        self.assertEqual(after, g.build_manifest(self.state, self.root))

    def test_retired_rule_blocks_current_but_preserves_history(self):
        errors = g.retired_errors(g.build_manifest(self.state, self.root), self.state, self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn('framework/live.md', errors[0])
        (self.root / 'framework/live.md').write_text('current replacement')
        self.assertEqual(g.retired_errors(g.build_manifest(self.state, self.root), self.state, self.root), [])

    def test_price_frequency_explicit_override_and_legacy_defaults(self):
        cases = [('gpu-hourly-x', None, 'quarterly', 150), ('gpu-hourly-x', 'spot', 'spot', 30),
                 ('construction-cost-annual', None, 'annual', 455), ('x-lead-time', None, 'quarterly', 150),
                 ('unclassified', None, 'default', 365), ('x', 'monthly', 'monthly', 45)]
        for sid, frequency, expected, days in cases:
            with self.subTest(sid=sid, frequency=frequency):
                record = {'series_id': sid, 'frequency': frequency}
                self.assertEqual(price_series_freq(record), expected)
                self.assertEqual(price_series_limit(record), days)


if __name__ == '__main__':
    unittest.main()
