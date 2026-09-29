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
        self.assertEqual(cards[1]['site_right_id'], self.right['site_right_id'])
        self.assertEqual(cards[0]['imported_by'], 'tester')
        again = deliveries.import_assignments(self.tmp, self.runtime([
            {'target_id': self.news['id'], 'delivery': {'evidence_path': 'https://example.com/press/1'}}]), today='2026-09-30')
        self.assertEqual((len(again['imported']), again['skipped'][0]['reason'], again['cards']), (0, 'already imported', 2))
        self.assertEqual(deliveries.check(self.tmp), [])

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
