"""交付回执进 Git 载体的唯一通道：运行库 assignments.json → data/event_cards.json → 目标表 delivered。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from inresearch.knowledge import deliveries, targets as targets_mod

ROOT = Path(__file__).resolve().parents[2]


class DeliveriesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / 'framework').mkdir()
        (self.tmp / 'data').mkdir()
        shutil.copy(ROOT / 'framework/tco_targets.json', self.tmp / 'framework/tco_targets.json')
        self.targets = json.loads((ROOT / 'framework/tco_targets.json').read_text())['targets']
        self.news = next(t for t in self.targets if t['team'] == 'inews' and t['part_id'])
        self.right = next(t for t in self.targets if t['site_right_id'])

    def runtime(self, records):
        path = self.tmp / 'assignments.json'
        path.write_text(json.dumps({'version': 1, 'records': records}))
        return path

    def test_import_makes_cards_only_for_known_targets_with_usable_pointers(self):
        result = deliveries.import_assignments(self.tmp, self.runtime([
            {'target_id': self.news['id'], 'assignee': 'lee', 'delivery': {'evidence_path': 'https://example.com/press/1', 'at': '2026-09-29', 'by': 'lee'}},
            {'target_id': self.right['id'], 'delivery': {'evidence_path': 'docs/research/2026-09-29/permits.md', 'at': '2026-09-29'}},
            {'target_id': 'F.nope.x', 'delivery': {'evidence_path': 'https://example.com/2'}},
            {'target_id': self.news['id'], 'delivery': {'evidence_path': '/etc/passwd'}},
            {'target_id': self.news['id'], 'assignee': 'lee'},
        ]), by='tester', today='2026-09-29')
        self.assertEqual(len(result['imported']), 2)
        self.assertEqual([s['reason'] for s in result['skipped']], ['unknown target', 'no usable evidence_path', 'no usable evidence_path'])
        cards = json.loads((self.tmp / 'data/event_cards.json').read_text())['records']
        self.assertEqual([c['pointer_kind'] for c in cards], ['url', 'repo_path'])
        self.assertEqual(cards[0]['part_id'], self.news['part_id'])
        self.assertEqual(cards[0]['object_ids'], ['part:' + self.news['part_id']])
        self.assertEqual(cards[1]['site_right_id'], self.right['site_right_id'])
        self.assertEqual(cards[0]['imported_by'], 'tester')
        again = deliveries.import_assignments(self.tmp, self.runtime([
            {'target_id': self.news['id'], 'delivery': {'evidence_path': 'https://example.com/press/1'}}]), today='2026-09-30')
        self.assertEqual((len(again['imported']), again['skipped'][0]['reason'], again['cards']), (0, 'already imported', 2))
        self.assertEqual(deliveries.check(self.tmp), [])

    def test_object_binding_cannot_disagree_with_target(self):
        deliveries.import_assignments(self.tmp, self.runtime([
            {'target_id':self.news['id'],'delivery':{'evidence_path':'https://example.org/original'}}]))
        path=self.tmp/'data/event_cards.json'
        doc=json.loads(path.read_text());doc['records'][0]['object_ids']=['part:not-the-target']
        path.write_text(json.dumps(doc))
        self.assertEqual(deliveries.check(self.tmp),[f"event card {self.news['id']}: object binding differs from target"])

    def observation(self, **change):
        o = {'product_id': 'micron-x', 'parameter_name': 'hbm.stack_capacity', 'value': '36GB', 'unit': 'GB',
             'condition': '12-high HBM3E', 'source_url': 'https://www.micron.com/x', 'source_sha256': 'a' * 64,
             'observed_at': '2026-10-01T00:00:00+00:00'}
        o.update(change)
        return o

    def test_fetchspec_values_ride_on_the_card_and_fill_cards_imported_before(self):
        rec = {'target_id': self.news['id'], 'delivery': {'evidence_path': 'https://www.micron.com/x', 'at': '2026-10-01'}}
        first = deliveries.import_assignments(self.tmp, self.runtime([rec]), today='2026-10-01')
        self.assertNotIn('parameters', first['imported'][0])                 # an import from before values travelled
        values = [self.observation(), self.observation(parameter_name='hbm.data_rate', value='9.2GTPS', unit='GT/s')]
        again = deliveries.import_assignments(self.tmp, self.runtime([{**rec, 'fetchspec': {'observations': values}}]), today='2026-10-02')
        self.assertEqual((len(again['imported']), len(again['updated']), again['cards']), (0, 1, 1))
        card = json.loads((self.tmp / 'data/event_cards.json').read_text())['records'][0]
        self.assertEqual([(p['parameter_name'], p['value'], p['unit']) for p in card['parameters']],
                         [('hbm.stack_capacity', '36GB', 'GB'), ('hbm.data_rate', '9.2GTPS', 'GT/s')])
        self.assertEqual(deliveries.import_assignments(self.tmp, self.runtime([{**rec, 'fetchspec': {'observations': values}}]))['updated'], [])
        self.assertEqual(deliveries.check(self.tmp), [])

    def test_malformed_values_reject_the_record_instead_of_storing_part_of_it(self):
        for bad in ([self.observation(source_url='javascript:alert(1)')], [self.observation(source_sha256='x')],
                    [self.observation(extra='1')], [self.observation(value='')], 'not a list',
                    [self.observation()] * (deliveries.MAX_PARAMETERS + 1)):
            rec = {'target_id': self.news['id'], 'delivery': {'evidence_path': 'https://www.micron.com/x'}, 'fetchspec': {'observations': bad}}
            result = deliveries.import_assignments(self.tmp, self.runtime([rec]))
            self.assertEqual(result['skipped'][0]['reason'], 'malformed fetchspec observations', bad)
        self.assertFalse(json.loads((self.tmp / 'data/event_cards.json').read_text())['records'])
        (self.tmp / 'data/event_cards.json').write_text(json.dumps({'version': '1.0', 'records': [
            {'target_id': self.news['id'], 'origin_pointer': 'https://www.micron.com/x', 'parameters': [{'value': '1'}]}]}))
        self.assertEqual(deliveries.check(self.tmp), [f"event card {self.news['id']}: parameters malformed"])

    def test_check_flags_unknown_targets_bad_pointers_and_duplicates(self):
        (self.tmp / 'data/event_cards.json').write_text(json.dumps({'version': '1.0', 'records': [
            {'target_id': 'F.nope.x', 'origin_pointer': 'https://example.com/a'},
            {'target_id': self.news['id'], 'origin_pointer': ''},
            {'target_id': self.news['id'], 'origin_pointer': 'https://example.com/b'},
            {'target_id': self.news['id'], 'origin_pointer': 'https://example.com/b'}]}))
        errors = deliveries.check(self.tmp)
        self.assertEqual(len(errors), 3)
        self.assertTrue(any('unknown target' in e for e in errors) and any('unusable' in e for e in errors) and any('duplicate' in e for e in errors))

    def test_repository_cards_are_consistent_and_the_generator_reads_them(self):
        self.assertEqual(deliveries.check(ROOT), [])
        self.assertEqual(targets_mod.EVENT_CARDS, deliveries.EVENT_CARDS)
        self.assertTrue((ROOT / deliveries.EVENT_CARDS).is_file(), 'the carrier file must exist in Git even when empty')


if __name__ == '__main__':
    unittest.main()
