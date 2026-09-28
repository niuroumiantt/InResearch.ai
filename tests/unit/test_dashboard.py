"""The dashboard is generated from registered rules; its account reproduces the economics model's check values."""
import json
import unittest
from pathlib import Path

from inresearch.knowledge import dashboard, economics

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load('data/dashboard.json')
        cls.rules = load('framework/dashboard_rules.json')
        cls.series = {r['series_id'] for r in load('data/prices.json')['records']}
        cls.indicators = {i['id'] for i in load('framework/indicators.json')['indicators']}
        cls.model = load('data/datacenter_economics_model.json')
        cls.bom = load('framework/bom.json')

    def test_snapshot_is_generated_from_its_inputs(self):
        built = dashboard.build(ROOT, self.doc['updated'])
        self.assertEqual(dashboard.render(built), (ROOT / dashboard.SNAPSHOT).read_text(encoding='utf-8'),
                         'data/dashboard.json is stale; run python3 manage.py dashboard --refresh')

    def test_account_matches_registered_check_values(self):
        # presets note: 收入 22.9 亿、NOPAT 12.1 亿、ROIC 31% for the 100 MW GB300 baseline
        out = economics.compute(self.model['assumptions'])
        self.assertAlmostEqual(out['revenue'] / 1e8, 22.9, delta=0.05)
        self.assertAlmostEqual(out['nopat'] / 1e8, 12.1, delta=0.1)  # 登记值按亿取整
        self.assertAlmostEqual(out['roic'], 0.31, delta=0.005)
        rows = {r['key']: r['value'] for r in self.doc['root']['account']['rows']}
        self.assertEqual(set(rows), {'cost_per_mw', 'revenue_per_mw', 'roic'}, '三级：成本、收入、回报；回报不是一列')

    def test_rules_reference_existing_sources(self):
        for col, specs in self.rules['root']['cells'].items():
            self.assertIn(col, self.rules['columns'])
            for spec in specs:
                if spec['source'] == 'model_input':
                    self.assertIn(spec['key'], self.model['assumptions'], spec)
                elif spec['source'] == 'model_output':
                    self.assertIn(spec['key'], economics.compute(self.model['assumptions']), spec)
                elif spec['source'] == 'indicator':
                    self.assertIn(spec['key'], self.indicators, spec)
        for sys_id, spec in self.rules['ecosystem']['2']['by_ecosystem'].items():
            self.assertIn(sys_id, self.bom['systems'])
            self.assertIn(spec['series'], self.series, sys_id)
        for sys_id, spec in self.rules['ecosystem']['3']['by_ecosystem'].items():
            self.assertIn(sys_id, self.bom['systems'])
            self.assertIn(spec['basis'], self.model['assumptions'])
            if 'share_series' in spec:
                self.assertIn(spec['share_series'], self.series, sys_id)
            else:
                self.assertIn(spec['share_input'], self.model['assumptions'])

    def test_tree_and_matrix_shape(self):
        self.assertEqual([e['id'] for e in self.doc['ecosystems']], list(self.bom['systems']))
        self.assertEqual(self.doc['site']['id'], 'site')
        for row in self.doc['ecosystems'] + [self.doc['site']]:
            self.assertEqual(set(row['cells']), {'1', '2', '3', '4', '5'}, row['id'])
            for c in row['cells'].values():
                self.assertIn(c['status'], ('sourced', 'assumed', 'needed'))
                self.assertEqual(c['status'] == 'sourced', any(i['value'] is not None for i in c['items']), row['id'])
        self.assertEqual(set(self.doc['parts']), {p['id'] for p in self.bom['parts']})
        self.assertEqual(set(self.doc['rights']), {r['id'] for r in load('framework/site_rights.json')['rights']})

    def test_critical_path_is_max_part_lead_time(self):
        power = next(e for e in self.doc['ecosystems'] if e['id'] == 'power')
        lead = [i['value'] for p in power['parts'] for i in self.doc['parts'][p['id']]['cells']['4']['items'] if isinstance(i['value'], (int, float))]
        self.assertTrue(lead)
        self.assertEqual(power['cells']['4']['items'][0]['value'], max(lead))
        self.assertEqual(power['cells']['4']['items'][0]['source']['type'], 'max')

    def test_no_forecast_points_in_changes(self):
        for p in self.doc['changes']['series_points']:
            self.assertLessEqual(p['as_of'], self.doc['updated'], p['series_id'])


if __name__ == '__main__':
    unittest.main()
