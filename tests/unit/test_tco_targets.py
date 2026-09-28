"""The five-variable-class target list is generated; it must equal its inputs, reference only things that exist,
route every row to a registered team and host, and cover every non-user TCO input."""
import json
import unittest
from pathlib import Path

from inresearch.knowledge import targets as targets_mod

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class TcoTargetListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load('framework/tco_targets.json')
        cls.targets = cls.doc['targets']
        cls.factors = {f['id']: f for f in load('framework/tco_factors.json')['factors']}
        cls.parts = {p['id']: p for p in load('framework/bom.json')['parts']}
        cls.rights = {r['id']: r for r in load('framework/site_rights.json')['rights']}
        cls.series = {r['series_id'] for r in load('data/prices.json')['records']}
        cls.indicators = {i['id'] for i in load('framework/indicators.json')['indicators']}
        model = load('data/datacenter_tco_model.json')
        cls.inputs = set(model['inputs'])
        cls.evidence = model['evidence']
        contract = load('framework/supply_contract.json')
        cls.providers = {p['id'] for p in contract['providers']}
        cls.hosts = {p['host'] for p in contract['execution_policy'].values() if isinstance(p, dict) and 'host' in p}

    def test_file_is_generated_from_its_inputs(self):
        built = targets_mod.build(ROOT, self.doc['updated'])
        self.assertEqual(targets_mod.render(built), (ROOT / targets_mod.TARGETS).read_text(encoding='utf-8'),
                         'framework/tco_targets.json is stale; run python3 manage.py targets --refresh')

    def test_ids_unique_and_fields_complete(self):
        ids = [t['id'] for t in self.targets]
        self.assertEqual(len(ids), len(set(ids)))
        for t in self.targets:
            self.assertIn(t['variable_class'], (1, 2, 3, 4, 5), t['id'])
            self.assertEqual(t['layer'], t['variable_class'], t['id'])  # layer is the compatibility name
            self.assertIn(t['origin'], ('factor', 'part', 'software', 'archetype', 'site_right'), t['id'])
            self.assertTrue(t['id'].startswith({'factor': 'F.', 'site_right': 'S.'}.get(t['origin'], 'P.')), t['id'])
            self.assertIn(t['data_class'], self.doc['data_classes'], t['id'])
            self.assertIn(t['mechanism'], self.doc['mechanisms'], t['id'])
            self.assertIn(t['status'], ('sourced', 'assumed', 'needed'), t['id'])
            for key in ('disclosure_type', 'publisher_category', 'calendar', 'next_due'):
                self.assertTrue(t.get(key), f"{t['id']} missing {key}")
            self.assertTrue(t['instances'], t['id'])

    def test_every_part_and_right_is_covered(self):
        by_part = {}
        for t in self.targets:
            if t['part_id']:
                by_part.setdefault(t['part_id'], set()).add(t['id'].rsplit('.', 1)[1])
        for pid, p in self.parts.items():
            want = {'part': {'spec', 'price', 'lead_time'}, 'software': {'spec', 'price'}, 'archetype': {'spec'}}[p['kind']]
            if p['kind'] == 'part' and p['status'] != 'mature':
                want = want | {'news'}
            self.assertEqual(by_part.get(pid), want, pid)
        for rid, r in self.rights.items():
            classes = {t['variable_class'] for t in self.targets if t['site_right_id'] == rid}
            self.assertEqual(classes, set(r['variable_classes']), rid)
        self.assertEqual(self.doc['counts']['total'], len(self.targets))

    def test_part_rows_carry_curated_sources(self):
        # 第 4 步的人工部分：每个物理部件的规格、价格、交期三行都有登记的出版方、实例与日历（framework/part_fetch.json）
        for t in self.targets:
            if t['origin'] == 'part' and t['id'].rsplit('.', 1)[1] in ('spec', 'price', 'lead_time'):
                self.assertTrue(t['curated'], f"{t['id']} still uses template sources")
                self.assertTrue(t['instances'] and t['publisher_category'] and t['calendar'], t['id'])

    def test_references_exist(self):
        for t in self.targets:
            self.assertTrue(t['factor_ids'] or t['origin'] != 'factor', t['id'])
            for fid in t['factor_ids']:
                self.assertIn(fid, self.factors, f"{t['id']} → factor {fid}")
            self.assertEqual(t['factor_id'], t['factor_ids'][0] if t['factor_ids'] else None, t['id'])
            if t['part_id']:
                self.assertIn(t['part_id'], self.parts, t['id'])
            if t['site_right_id']:
                self.assertIn(t['site_right_id'], self.rights, t['id'])
            for key in t['model_inputs']:
                self.assertIn(key, self.inputs, f"{t['id']} → input {key}")
            for sid in t['series']:
                self.assertIn(sid, self.series, f"{t['id']} → series {sid}")
            for sid in t['planned_series']:
                self.assertNotIn(sid, self.series, f"{t['id']} planned series already exists: {sid}")
            for iid in t['indicators']:
                self.assertIn(iid, self.indicators, f"{t['id']} → indicator {iid}")

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
                self.assertTrue(t['series'] or t['indicators'] or t['data_class'] == 'reference', t['id'])
            if t['origin'] != 'factor' and not (t['series'] or t['indicators']):
                self.assertEqual(t['status'], 'needed', f"{t['id']} generated row without data must stay needed")


if __name__ == '__main__':
    unittest.main()
