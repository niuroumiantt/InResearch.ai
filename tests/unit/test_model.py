"""Unified economic model v3: the Python engine reproduces the three calibration anchors, the model file is
consistent (every input has a spec, an evidence row with a variable class, and a group), presets and regions only
touch registered inputs, and the browser mirror computes the same numbers as the Python reference."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from inresearch.knowledge import economics as ec

ROOT = Path(__file__).resolve().parents[2]
MODEL = 'data/datacenter_model.json'


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class ModelFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load(MODEL)

    def test_inputs_evidence_groups_and_assumptions_agree(self):
        s = self.spec
        keys = set(s['assumptions'])
        self.assertEqual(keys, set(s['inputs']), 'every assumption has an input spec and vice versa')
        self.assertEqual(keys, set(s['evidence']), 'every input has an evidence row')
        grouped = [k for g in s['groups'] for k in g['inputs']]
        self.assertEqual(sorted(grouped), sorted(keys), 'every input sits in exactly one variable-class group')
        for g in s['groups']:
            for k in g['inputs']:
                self.assertEqual(s['evidence'][k]['variable_class'], g['variable_class'], k)
        for k, ev in s['evidence'].items():
            self.assertIn(ev['status'], s['evidence_legend'], k)
            self.assertIn(ev['variable_class'], (1, 2, 3, 4, 5), k)

    def test_tables_presets_and_regions_only_touch_registered_inputs(self):
        s = self.spec
        keys = set(s['assumptions'])
        for key, table in ec.TABLES:
            self.assertIn(s['assumptions'][key], s[table], f'baseline {key} must be a {table} record')
            for rid, rec in s[table].items():
                for k in rec:
                    if k in ('label', 'source', 'evidence_class', 'density_basis', 'gaps'):
                        continue
                    self.assertIn(k, keys, f'{table}.{rid}.{k} is not an input')
        for rid, r in s['regions'].items():
            for k in r.get('gaps', []):
                self.assertIn(k, keys, f'region {rid} gap {k}')
        for pid, p in s['presets'].items():
            for k in p['changes']:
                self.assertIn(k, keys, f'preset {pid} changes {k}')
        self.assertEqual(list(s['regions']), ['us_virginia', 'us_texas', 'cn_inner_mongolia', 'malaysia_johor'], '四个地区预设')
        self.assertTrue(s['regions']['malaysia_johor']['gaps'], '柔佛的数据先标缺')
        self.assertEqual(s['assumptions']['roic_basis'], 'total_capex', '默认用摩根士丹利的总资本开支口径')

    def test_baseline_uses_sourced_values(self):
        a = self.spec['assumptions']
        self.assertEqual(a['pue'], self.spec['coolings'][a['cooling']]['pue'], 'PUE 由冷却方式的登记值决定')
        self.assertEqual(a['power_price'], self.spec['regions']['us_virginia']['power_price'])
        latest = max((r for r in load('data/prices.json')['records'] if r['series_id'] == 'industrial-power-price-us-va'), key=lambda r: r['as_of'])
        self.assertAlmostEqual(a['power_price'], latest['value'] / 100, places=4, msg='电价取价格库弗州工业电价最新点')
        self.assertEqual(a['demand_rate'], 14.5)
        self.assertEqual(a['land_per_mw'], 1.2)


class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load(MODEL)

    def test_morgan_stanley_1gw_gb300(self):
        cal = self.spec['calibration']['ms']
        c = ec.compute(ec.with_preset(self.spec, cal['preset']), self.spec)
        self.assertAlmostEqual(c['revenue_per_gw'] / 1e8, cal['revenue_per_gw'] / 1e8, delta=0.5)   # 229 亿
        self.assertAlmostEqual(c['nopat_per_mw'] * 1000 / 1e2, cal['nopat_per_gw'] / 1e8, delta=1.0)  # 121 亿，登记值按亿取整
        self.assertAlmostEqual(c['roic'], cal['roic'], delta=0.005)                                    # 31%

    def test_goldman_15pct_hurdle(self):
        cal = self.spec['calibration']['gs']
        a = ec.with_preset(self.spec, cal['preset'])
        self.assertEqual(a['roic_basis'], 'avg_annual_capex')
        inv = ec.inverse(a, self.spec)
        self.assertAlmostEqual(inv['required_revenue_per_gw'] / 1e9, cal['required_revenue_per_gw'] / 1e9, delta=0.1)  # 11.6 bn/GW
        self.assertAlmostEqual(inv['ebit_margin'], cal['ebit_margin'], delta=0.005)     # 34.7%
        self.assertAlmostEqual(inv['nopat_margin'], cal['nopat_margin'], delta=0.005)   # 27.4%
        c = ec.compute(a, self.spec)
        self.assertAlmostEqual(c['capex_per_gw'] / 1e9, 42.4, places=6)

    def test_our_2026_09_14_cost_baseline(self):
        cal = self.spec['calibration']['ours_2026_09_14']
        c = ec.compute(ec.with_preset(self.spec, cal['preset']), self.spec)
        self.assertAlmostEqual(c['annualised'], cal['annualised'], places=2)   # 1,167,777,119.40
        self.assertAlmostEqual(c['unit_cost'], cal['unit_cost'], delta=0.005)  # 4.10 per effective device hour
        self.assertAlmostEqual(c['it_kwh'] * 1.25 / 1e6, 766.5, places=1)
        self.assertAlmostEqual(c['water_m3'] / 1e3, 490.6, places=1)

    def test_inverse_and_grid_are_consistent_with_the_forward_run(self):
        a = ec.with_preset(self.spec, 'baseline')
        inv = ec.inverse(a, self.spec)
        # pricing at the required price hits the target exactly
        b = dict(a, price_gpu_hour=inv['required_price'])
        self.assertAlmostEqual(ec.compute(b, self.spec)['roic'], a['target_roic'], places=9)
        # so does the required utilization, and the capex ceiling at unchanged revenue
        b = dict(a, gpu_utilization=inv['required_utilization'])
        self.assertAlmostEqual(ec.compute(b, self.spec)['roic'], a['target_roic'], places=9)
        b = ec.scaled_capex(a, inv['capex_ceiling_per_gw'] / 1e9, self.spec)
        self.assertAlmostEqual(ec.compute(b, self.spec)['roic'], a['target_roic'], places=6)
        g = ec.grid(a, self.spec)
        self.assertEqual((len(g['roic']), len(g['roic'][0]), len(g['roic'][0][0])), (len(g['utilization']), len(g['capex_per_gw']), len(g['prices'])))
        for plane in g['roic']:
            for row in plane:
                self.assertEqual(row, sorted(row), 'ROIC rises with price')

    def test_modes_gate_and_quota(self):
        spec = self.spec
        base = ec.with_preset(spec, 'baseline')
        own, bot, lease, colo = [ec.compute(dict(base, facility_mode=m), spec) for m in ('own', 'bot', 'lease', 'colo')]
        self.assertGreater(own['invested'], bot['invested'])
        self.assertGreater(bot['invested'], lease['invested'])
        self.assertGreater(lease['invested'], colo['invested'])
        self.assertGreater(bot['facility_cost'], 0, 'BOT pays the partner a service fee')
        self.assertGreater(ec.lifecycle(base, spec)['lead_months'], ec.lifecycle(dict(base, gate_wait_years=0), spec)['lead_months'])
        capped = ec.compute(dict(base, energy_quota_mw=40), spec)
        self.assertEqual(capped['mw'], 40, 'the energy quota caps the buildable capacity')
        l = ec.lifecycle(base, spec)
        self.assertEqual(len(l['years']), base['gate_wait_years'] + base['construction_years'] + base['horizon_years'])
        self.assertEqual([r['revenue'] > 0 for r in l['years'][:base['gate_wait_years'] + base['construction_years']]], [False] * (base['gate_wait_years'] + base['construction_years']))

    def test_browser_engine_matches_the_python_reference(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node not installed')
        script = ("const M=require(process.argv[1]);const spec=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));"
                  "const out={};for(const id of Object.keys(spec.presets)){const r=M.run(M.withPreset(spec,id),spec);delete r.inputs;out[id]=r;}"
                  "process.stdout.write(JSON.stringify(out));")
        res = subprocess.run([node, '-e', script, str(ROOT / 'web/components/datacenter-model.js'), str(ROOT / MODEL)],
                             capture_output=True, text=True, check=True)
        js = json.loads(res.stdout)
        mismatches, count = [], 0

        def walk(path, x, y):
            nonlocal count
            if isinstance(x, dict):
                if set(x) != set(y):
                    mismatches.append((path, 'keys', sorted(set(x) ^ set(y))))
                    return
                for k in x:
                    walk(f'{path}.{k}', x[k], y[k])
            elif isinstance(x, list):
                if len(x) != len(y):
                    mismatches.append((path, 'len', len(x), len(y)))
                    return
                for i, (p, q) in enumerate(zip(x, y)):
                    walk(f'{path}[{i}]', p, q)
            else:
                count += 1
                if x is None or y is None or isinstance(x, str):
                    if x != y:
                        mismatches.append((path, x, y))
                elif abs(x - y) > 1e-9 * max(1.0, abs(x)):
                    mismatches.append((path, x, y))
        for pid in self.spec['presets']:
            r = ec.run(ec.with_preset(self.spec, pid), self.spec)
            r.pop('inputs')
            walk(pid, r, js[pid])
        self.assertGreater(count, 5000)
        self.assertEqual(mismatches[:5], [], f'{len(mismatches)} numbers differ between the JS mirror and the Python engine')


if __name__ == '__main__':
    unittest.main()
