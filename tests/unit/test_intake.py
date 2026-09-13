import copy
import unittest
from inresearch.workflow import submissions as intake


class IntakeEvidenceTests(unittest.TestCase):
    def item(self):
        return dict(file='test.pdf', title='Interface definition', org='Test', year='2026',
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


if __name__ == '__main__':
    unittest.main()
