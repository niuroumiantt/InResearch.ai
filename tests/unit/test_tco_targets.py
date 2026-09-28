"""The five-layer target list must only reference things that exist and must cover every non-user TCO input."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class TcoTargetListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load('framework/tco_targets.json')
        cls.targets = cls.doc['targets']
        cls.factors = {f['id'] for f in load('framework/tco_factors.json')['factors']}
        cls.series = {r['series_id'] for r in load('data/prices.json')['records']}
        model = load('data/datacenter_tco_model.json')
        cls.inputs = set(model['inputs'])
        cls.evidence = model['evidence']
        contract = load('framework/supply_contract.json')
        cls.providers = {p['id'] for p in contract['providers']}
        cls.hosts = {p['host'] for p in contract['execution_policy'].values() if isinstance(p, dict) and 'host' in p}

    def test_ids_unique_and_fields_complete(self):
        ids = [t['id'] for t in self.targets]
        self.assertEqual(len(ids), len(set(ids)))
        for t in self.targets:
            self.assertIn(t['layer'], (1, 2, 3, 4, 5), t['id'])
            self.assertTrue(t['id'].startswith(f"L{t['layer']}."), t['id'])
            self.assertIn(t['data_class'], self.doc['data_classes'], t['id'])
            self.assertIn(t['mechanism'], self.doc['mechanisms'], t['id'])
            self.assertIn(t['status'], ('sourced', 'assumed', 'needed'), t['id'])
            for key in ('disclosure_type', 'publisher_category', 'calendar', 'next_due'):
                self.assertTrue(t.get(key), f"{t['id']} missing {key}")
            self.assertTrue(t['instances'], t['id'])

    def test_references_exist(self):
        for t in self.targets:
            self.assertIn(t['factor_id'], self.factors, f"{t['id']} → factor {t['factor_id']}")
            for key in t['model_inputs']:
                self.assertIn(key, self.inputs, f"{t['id']} → input {key}")
            for sid in t['series']:
                self.assertIn(sid, self.series, f"{t['id']} → series {sid}")
            for sid in t['planned_series']:
                self.assertNotIn(sid, self.series, f"{t['id']} planned series already exists: {sid}")

    def test_team_and_host_registered(self):
        for t in self.targets:
            self.assertIn(t['team'], self.providers, f"{t['id']} → team {t['team']}")
            self.assertIn(t['team'], self.doc['teams'], t['id'])
            self.assertIn(t['host'], self.hosts, f"{t['id']} → host {t['host']}")
            # inews only produces event cards and pointers; originals belong to the other teams.
            if t['team'] == 'inews':
                self.assertEqual(t['mechanism'], 'rss', t['id'])
                self.assertEqual(t['data_class'], 'material', t['id'])
            if t['mechanism'] in ('pdf_registered', 'js_page'):
                self.assertEqual(t['host'], 'macmini', f"{t['id']} assisted mechanism must run on macmini")

    def test_every_non_user_input_has_a_target(self):
        covered = {k for t in self.targets for k in t['model_inputs']}
        expected = {k for k, v in self.evidence.items() if v.get('status') != 'input'}
        self.assertEqual(expected - covered, set(), f"inputs without a target: {sorted(expected - covered)}")

    def test_status_is_not_more_optimistic_than_the_model(self):
        for t in self.targets:
            statuses = {self.evidence[k]['status'] for k in t['model_inputs'] if k in self.evidence}
            if t['status'] == 'sourced':
                self.assertIn('sourced', statuses, f"{t['id']} claims sourced but model evidence is {statuses}")


if __name__ == '__main__':
    unittest.main()
