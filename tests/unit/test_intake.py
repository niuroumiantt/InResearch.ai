import copy
import unittest
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from inresearch.workflow import submissions as intake


class IntakeEvidenceTests(unittest.TestCase):
    def item(self):
        return dict(file='test.pdf', title='Interface definition', org='Test', year=2026,
                    modules=['M09'], claimed_importance=7, confidence='B', summary='x' * 220,
                    key_statements=[dict(kind='interface', text='Test interface definition',
                                         quote='Original interface wording', locator='page 2, section 1')])

    def test_nonnumeric_evidence_enters_candidate_intake(self):
        self.assertEqual([], intake.check_item(self.item(), set(), set(), 'M09')[0])
        row = intake.to_batch_rows([('tester', '', self.item(), [], [], [], None)], '2026-09-12')[0]
        self.assertIn('Original interface wording', row['summary'])
        self.assertIn('page 2, section 1', row['summary'])
        self.assertIn('尚未经我们审计', row['summary'])

    def test_empty_or_untraceable_nonnumeric_evidence_is_rejected(self):
        for field in ('quote', 'text', 'locator', 'kind'):
            item = copy.deepcopy(self.item())
            item['key_statements'][0].pop(field)
            self.assertTrue(intake.check_item(item, set(), set(), 'M09')[0], field)
        item = self.item()
        item.pop('key_statements')
        self.assertIn('NO_EVIDENCE', intake.check_item(item, set(), set(), 'M09')[0])

    def test_same_filename_new_edition_is_candidate_not_duplicate(self):
        item = self.item()
        bad, warnings = intake.check_item(item, {'test.pdf'}, {item['title'].lower()}, 'M09')
        self.assertEqual([], bad)
        self.assertTrue(any('SHA' in warning for warning in warnings))

    def test_B_requires_current_matching_workorder_and_A_takes_priority(self):
        item = self.item()
        sub = {'module': 'M09', 'workorder': 'Q-M09-Q01'}
        tasks = {sub['workorder']: {'mid': 'M09'}}
        self.assertEqual('待匹配', intake.tier(item, [], []))
        self.assertTrue(intake.matched_workorder(sub, item, tasks))
        self.assertEqual('B', intake.tier(item, [], [], matched=True))
        for workorders in ({}, {'Q-M09-Q01': {'mid': 'M08'}},
                           {'Q-M09-Q01': {'mid': 'M09', 'assignment': {'status': '已合并'}}}):
            self.assertFalse(intake.matched_workorder(sub, item, workorders))
        for change in ({'sensitive': True}, {'claimed_importance': 8},
                       {'replaces_record_ids': ['statement:old']}):
            self.assertEqual('A', intake.tier({**item, **change}, [], [], matched=True))
        self.assertEqual('A', intake.tier(item, [], ['conflict']))
        self.assertEqual('C', intake.tier({**item, 'claimed_importance': 4}, [], []))

    def test_malformed_evidence_and_types_fail_without_crashing(self):
        mutations = [{'year': '2026'}, {'year': True}, {'modules': [None]},
                     {'sensitive': 'false'}, {'key_numbers': 'not a list'},
                     {'key_numbers': [None]}, {'key_statements': [None]},
                     {'replaces_record_ids': [False]}, {'key_numbers': [dict(
                         what='price', value=float('nan'), unit='USD', locator='p1')]},
                     {'key_numbers': [dict(what='price', value=True, unit='USD', locator='p1')]}]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertIn('BAD_FIELD', intake.check_item({**self.item(), **mutation}, set(), set(), 'M09')[0])
        self.assertEqual(['BAD_FIELD'], intake.check_item(None, set(), set(), 'M09')[0])

    def test_candidate_export_retry_preserves_other_batches_and_never_adopts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root/'submissions/tester'; source.mkdir(parents=True)
            batches = root/'batches'
            item = {**self.item(), 'claimed_importance': 4}
            sub = {'contributor': 'tester', 'submitted': '2026-09-13', 'module': 'M09', 'items': [item]}
            original = root/'knowledge.json'; original.write_text('unchanged authority')
            def run():
                (source/'submission.json').write_text(json.dumps(sub))
                with patch.object(intake, 'ROOT', root), patch.object(intake, 'SUBS', root/'submissions'), \
                     patch.object(intake, 'OUT', root/'review.md'), patch.object(intake, 'BATCHES', batches), \
                     patch.object(intake, 'load_facts', return_value={}), \
                     patch.object(intake, 'load_library', return_value=(set(), set())), \
                     patch.object(intake, 'current_tasks', return_value=[]), \
                     patch('sys.argv', ['submissions', '--accept']), patch('sys.stdout', io.StringIO()):
                    self.assertEqual(0, intake.main())
            run()
            first = next(batches.glob('*.csv')); before = first.read_bytes()
            with patch.object(intake, 'datetime') as clock:
                clock.now.return_value.astimezone.return_value.date.return_value.isoformat.return_value = '2026-09-14'
                run()
            self.assertEqual(1, len(list(batches.glob('*.csv'))))
            self.assertEqual(before, first.read_bytes())
            sub['items'][0]['title'] = 'Another candidate'
            run()
            self.assertEqual(2, len(list(batches.glob('*.csv'))))
            self.assertEqual(before, first.read_bytes())
            self.assertEqual('unchanged authority', original.read_text())
            self.assertIn('尚未经我们审计', before.decode())
            sub['items'][0]['claimed_importance'] = 7
            run()
            self.assertEqual(2, len(list(batches.glob('*.csv'))))
            self.assertIn('候选待匹配工单', (root/'review.md').read_text())


if __name__ == '__main__':
    unittest.main()
