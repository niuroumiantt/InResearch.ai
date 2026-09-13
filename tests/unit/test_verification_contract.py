import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from inresearch.interfaces import governance
from inresearch.interfaces.verification import CONTRACT, verification_errors


class VerificationContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        files = {'framework/current.md': 'candidate is not adopted',
                 'tests/unit/test_case.py': 'class Case:\n def test_adoption(self): pass\n',
                 'tests/run_browser.cjs': "const defaults = ['ui'];",
                 'tests/ui.cjs': '// browser test'}
        for name, body in files.items():
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(body)
        policy = {'id': 'data', 'source': 'framework/current.md', 'scope': 'project', 'status': 'current'}
        self.state = {'version': '1', 'policies': [policy]}
        self.map = {'version': '1', 'reviewed_files': {
            name: hashlib.sha256((self.root / name).read_bytes()).hexdigest() for name in files},
            'policies': [{'policy': 'data', 'source': policy['source'], 'scope': 'project',
                          'checked_requirement': 'candidate cannot close questions',
                          'tests': ['tests/unit/test_case.py::Case.test_adoption', 'tests/ui.cjs'],
                          'not_verified': ['independent source truth requires review']}]}

    def errors(self):
        (self.root / CONTRACT).write_text(json.dumps(self.map))
        return verification_errors(self.state, self.root)

    def test_changed_rule_cannot_be_approved_by_inventory_refresh(self):
        self.assertEqual([], self.errors())
        (self.root / 'framework/current.md').write_text('new rule')
        self.assertTrue(any('review required' in e for e in self.errors()))
        (self.root / 'docs').mkdir()
        before = (self.root / CONTRACT).read_bytes()
        self.state.update(entrypoints=[], retired_entrypoints=[], known_retired_patterns=[])
        self.state['policies'][0].update(effective_at='2026-09-13', reason='test policy', supersedes=[])
        (self.root / 'framework/current_state.json').write_text(json.dumps(self.state))
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        result = subprocess.run([sys.executable, '-m', 'inresearch.interfaces.governance', '--refresh'],
                                env={**os.environ, 'INRESEARCH_PROJECT_ROOT': str(self.root)},
                                capture_output=True, text=True, check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('changed reviewed file; review required', result.stdout, result.stderr)
        self.assertEqual(before, (self.root / CONTRACT).read_bytes())

    def test_renamed_test_is_rejected_even_when_file_hash_is_updated(self):
        path = self.root / 'tests/unit/test_case.py'
        path.write_text('class Case:\n def test_something_else(self): pass\n')
        self.map['reviewed_files']['tests/unit/test_case.py'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertTrue(any('test case missing' in e for e in self.errors()))

    def test_missing_policy_and_unexecuted_browser_suite_are_detected(self):
        self.state['policies'].append({**self.state['policies'][0], 'id': 'other', 'scope': 'm4'})
        self.assertTrue(any('every current' in e for e in self.errors()))
        self.state['policies'].pop()
        (self.root / 'tests/run_browser.cjs').write_text('const defaults = [];')
        self.assertTrue(any('not in default runner' in e for e in self.errors()))

    def test_gaps_must_remain_explicit_and_guides_are_not_candidates(self):
        self.map['policies'][0]['not_verified'] = []
        self.assertTrue(any('coverage limits required' in e for e in self.errors()))
        state = copy.deepcopy(self.state)
        name = 'docs/inbox/submissions/README.md'
        state.update(entrypoints=[], retired_entrypoints=[], operational_guides=[name])
        self.assertEqual('supporting_document', governance.classify(name, state))


if __name__ == '__main__':
    unittest.main()
