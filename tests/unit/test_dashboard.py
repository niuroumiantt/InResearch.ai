"""The dashboard is generated from registered rules; its account reads the unified model's baseline preset."""
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
        cls.model = load('data/datacenter_model.json')
        cls.bom = load('framework/bom.json')

    def test_snapshot_is_generated_from_its_inputs(self):
        built = dashboard.build(ROOT, self.doc['updated'])
        self.assertEqual(dashboard.render(built), (ROOT / dashboard.SNAPSHOT).read_text(encoding='utf-8'),
                         'data/dashboard.json is stale; run python3 manage.py dashboard --refresh')

    def test_account_matches_the_baseline_preset(self):
        out = economics.compute(economics.with_preset(self.model, 'baseline'), self.model)
        rows = {r['key']: r['value'] for r in self.doc['root']['account']['rows']}
        self.assertAlmostEqual(rows['roic'], out['roic'], places=3)
        self.assertAlmostEqual(rows['revenue_per_mw'], out['revenue_per_mw'], places=3)
        self.assertEqual(self.doc['root']['account']['scenario'], self.model['presets']['baseline']['label'])
        self.assertEqual(set(rows), {'cost_per_mw', 'revenue_per_mw', 'roic'}, '三级：成本、收入、回报；回报不是一列')

    def test_root_readings_and_account_evidence(self):
        readings = self.doc['root']['account']['readings']
        self.assertEqual([r['id'] for r in readings], ['build', 'compose', 'operate', 'earn'])
        for r in readings:
            self.assertTrue(r['href'] and r['label'] and r['hint'], r['id'])
        for row in self.doc['root']['account']['rows']:
            ev = row['evidence']
            self.assertEqual(set(ev), {'sourced', 'assumed', 'input', 'inputs'}, row['key'])
            self.assertGreater(ev['inputs'], 0, row['key'])
            self.assertLessEqual(ev['sourced'] + ev['assumed'] + ev['input'], ev['inputs'], row['key'])

    def test_rules_reference_existing_sources(self):
        for col, specs in self.rules['root']['cells'].items():
            self.assertIn(col, self.rules['columns'])
            for spec in specs:
                if spec['source'] == 'model_input':
                    self.assertIn(spec['key'], self.model['assumptions'], spec)
                elif spec['source'] == 'model_output':
                    self.assertIn(spec['key'], economics.compute(self.model['assumptions'], self.model), spec)
                elif spec['source'] == 'indicator':
                    self.assertIn(spec['key'], self.indicators, spec)
        for sys_id, spec in self.rules['system']['2']['by_system'].items():
            self.assertIn(sys_id, self.bom['systems'])
            self.assertIn(spec['series'], self.series, sys_id)
        for sys_id, spec in self.rules['system']['3']['by_system'].items():
            self.assertIn(sys_id, self.bom['systems'])
            self.assertIn(spec['basis'], self.model['assumptions'])
            if 'share_series' in spec:
                self.assertIn(spec['share_series'], self.series, sys_id)
            else:
                self.assertIn(spec['share_input'], self.model['assumptions'])

    def test_tree_and_matrix_shape(self):
        leaf = [s for s, d in self.bom['systems'].items() if not any(x.get('parent') == s for x in self.bom['systems'].values())]
        self.assertEqual(sorted(e['id'] for e in self.doc['system_nodes']), sorted(leaf))
        self.assertEqual([e['id'] for e in self.doc['system_nodes']][:3], ['facility', 'power', 'thermal'], '五个系统的骨架顺序')
        self.assertEqual([p['id'] for p in self.doc['parent_systems']], ['it'])
        self.assertEqual(self.doc['parent_systems'][0]['children'], ['compute', 'memory', 'storage', 'network'])
        power = next(e for e in self.doc['system_nodes'] if e['id'] == 'power')
        self.assertEqual([p['chain'] for p in power['parts']][:3], ['电网接入', '变电', '变电'], '电力系统的部件按链路从电网走到板级')
        self.assertEqual(self.doc['site']['id'], 'site')
        for row in self.doc['system_nodes'] + [self.doc['site']]:
            self.assertEqual(set(row['cells']), {'1', '2', '3', '4', '5'}, row['id'])
            for c in row['cells'].values():
                self.assertIn(c['status'], ('sourced', 'assumed', 'delivered', 'registered', 'needed'))
                self.assertEqual(c['status'] == 'sourced', any(i['value'] is not None and i.get('kind') != 'count' for i in c['items']),
                                 f"{row['id']}: sourced only for non-count values")
                self.assertEqual(set(c['coverage']), {'sourced', 'assumed', 'delivered', 'needed'}, row['id'])
        # honesty: the part count we registered ourselves is 'registered', never 'sourced'; a team delivery
        # into the same cell lifts it to 'delivered' (the count still does not make it 'sourced')
        cell = self.doc['system_nodes'][0]['cells']['1']
        self.assertEqual(cell['status'], 'delivered' if cell['coverage']['delivered'] else 'registered')
        self.assertEqual(set(self.doc['root']['targets']), {'sourced', 'assumed', 'delivered', 'needed', 'not_connected'})
        self.assertEqual(set(self.rules['cell_status']), {'sourced', 'assumed', 'delivered', 'registered', 'needed'})
        self.assertEqual(set(self.doc['parts']), {p['id'] for p in self.bom['parts']})
        self.assertEqual([s['id'] for s in self.doc['stages']], [s['id'] for s in self.bom['stages']], '建设阶段随骨架进快照')
        for p in self.doc['parts'].values():
            self.assertIn(p['stage'], {s['id'] for s in self.bom['stages']}, p['id'])
        for r in self.doc['site']['rights']:
            self.assertIn(r['stage'], {s['id'] for s in self.bom['stages']}, r['id'])
        self.assertEqual(set(self.doc['rights']), {r['id'] for r in load('framework/site_rights.json')['rights']})

    def test_critical_path_is_max_part_lead_time(self):
        power = next(e for e in self.doc['system_nodes'] if e['id'] == 'power')
        lead = [i['value'] for p in power['parts'] for i in self.doc['parts'][p['id']]['cells']['4']['items'] if isinstance(i['value'], (int, float))]
        self.assertTrue(lead)
        self.assertEqual(power['cells']['4']['items'][0]['value'], max(lead))
        self.assertEqual(power['cells']['4']['items'][0]['source']['type'], 'max')

    def test_no_forecast_points_in_changes(self):
        for p in self.doc['changes']['series_points']:
            self.assertLessEqual(p['as_of'], self.doc['updated'], p['series_id'])


if __name__ == '__main__':
    unittest.main()
