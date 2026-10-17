"""Unified economic model v3: the Python engine reproduces the three calibration anchors, the model file is
consistent (every input has a spec, an evidence row with a variable class, and a group), presets and regions only
touch registered inputs, and the browser mirror computes the same numbers as the Python reference."""
import json
import math
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
        self.assertEqual(len(l['years']), math.ceil(l['preconstruction_years']) + base['construction_years'] + base['horizon_years'])
        self.assertTrue(all(r['revenue'] == 0 for r in l['years'] if r['phase'] != 'operation'))

    def test_permit_schedule_changes_real_payment_and_revenue_times(self):
        a = ec.with_preset(self.spec, 'baseline')
        before = ec.lifecycle(dict(a, permit_months=0), self.spec)
        after = ec.lifecycle(dict(a, permit_months=3), self.spec)
        self.assertEqual(after['lead_months'] - before['lead_months'], 3)
        first = next(r for r in after['years'] if r['phase'] == 'operation')
        self.assertEqual(first['start_year'], 3.25)
        self.assertEqual(first['end_year'], 4.25)
        self.assertEqual(next(r for r in after['years'] if r['phase'] == 'construction')['start_year'], 1.25)
        # No carrying costs are invented: delaying every nonzero flow discounts the same nominal amounts.
        shift = (1 + a['wacc']) ** -.25
        self.assertAlmostEqual(after['npv'], before['npv'] * shift, places=4)
        self.assertAlmostEqual(after['pv_total'], before['pv_total'] * shift, places=4)
        self.assertAlmostEqual(after['levelised'], before['levelised'], places=4)
        self.assertAlmostEqual(after['irr'], before['irr'], places=10)
        parallel = ec.lifecycle(dict(a, permit_months=3, permit_timing='parallel_with_gate'), self.spec)
        self.assertEqual(parallel['lead_months'], 36)
        self.assertAlmostEqual(parallel['npv'], before['npv'], places=4)
        long_permit = ec.lifecycle(dict(a, permit_months=18, permit_timing='parallel_with_gate'), self.spec)
        self.assertEqual(long_permit['lead_months'], 42)
        self.assertEqual(sum(r['duration_years'] for r in long_permit['years']), 18.5)

    def test_irr_uses_elapsed_years_including_fractional_stages(self):
        self.assertAlmostEqual(ec.irr([-100, 121], [0, 2]), .1, places=10)
        self.assertAlmostEqual(ec.irr([-100, 121], [2.25, 4.25]), .1, places=10)
        a = dict(ec.with_preset(self.spec, 'baseline'), permit_months=7)
        life = ec.lifecycle(a, self.spec)
        self.assertAlmostEqual(sum(r['net'] / (1 + life['irr']) ** r['end_year'] for r in life['years']), 0, delta=.01)

    def test_depreciation_does_not_change_replacement_or_capital_recovery(self):
        a = ec.with_preset(self.spec, 'baseline')
        old, new = ec.compute(a, self.spec), ec.compute(dict(a, it_depreciation_years=2), self.spec)
        self.assertNotEqual(old['dep_it'], new['dep_it'])
        self.assertEqual(old['capital_charge'], new['capital_charge'])
        self.assertEqual(ec.lifecycle(a, self.spec), ec.lifecycle(dict(a, it_depreciation_years=2), self.spec))
        it_charges = [d - ec.depreciation(new['facility_capex'], a['horizon_years'], t)
                      for t, d in enumerate(new['depreciation_path'])]
        self.assertAlmostEqual(sum(it_charges), new['it_capex'], places=4)
        self.assertTrue(all(abs(d) < .001 for d in it_charges[2:]))
        longer = ec.compute(dict(a, it_depreciation_years=10), self.spec)
        self.assertAlmostEqual(longer['terminal_book_value_assumption'] - old['terminal_book_value_assumption'], old['it_capex'] / 2, places=4)
        self.assertIn('not_market_price', longer['terminal_value_basis'])
        changed = ec.lifecycle(dict(a, it_refresh_years=3), self.spec)
        self.assertEqual([r['year'] for r in changed['years'] if r['capex_it']], [1, 4, 7, 10, 13])
        self.assertEqual(ec.compute(dict(a, it_refresh_years=3), self.spec)['dep_it'], old['dep_it'])

    def test_debt_terms_stop_service_and_deduct_remaining_principal(self):
        a = dict(ec.with_preset(self.spec, 'baseline'), compute_ltc=.6)
        c = ec.compute(a, self.spec)
        short = ec.compute(dict(a, compute_debt_years=2), self.spec)
        long = ec.compute(dict(a, compute_debt_years=8), self.spec)
        self.assertEqual(c['ebit'], short['ebit'])
        self.assertEqual(c['nopat'], long['nopat'])
        self.assertTrue(all(x < .001 for x in short['debt_service_path'][2:]))
        self.assertEqual(short['debt_principal_at_exit'], 0)
        principal = long['debt'] * (1 + a['compute_debt_rate']) ** a['it_refresh_years'] - long['debt_service'] * (((1 + a['compute_debt_rate']) ** a['it_refresh_years'] - 1) / a['compute_debt_rate'])
        self.assertAlmostEqual(long['debt_principal_at_exit'], principal, places=4)
        taxable = long['revenue_path'][-1] - long['opex'] - long['depreciation_path'][-1] - long['interest_path'][-1]
        expected = (long['revenue_path'][-1] - long['opex'] - long['debt_service_path'][-1]
                    - ec.income_tax(a, taxable) + long['terminal_book_value_assumption'] - principal)
        self.assertAlmostEqual(long['equity_cashflows'][-1], expected, places=4)
        shell = ec.ledgers(dict(a, lease_term=10, shell_debt_years=15), self.spec)['shell']
        self.assertGreater(shell['debt_principal_at_exit'], 0)
        shell_short = ec.ledgers(dict(a, lease_term=10, shell_debt_years=5), self.spec)['shell']
        self.assertTrue(all(x < .001 for x in shell_short['debt_service_path'][5:]))
        self.assertEqual(shell_short['debt_principal_at_exit'], 0)

    def test_contractual_maturity_settles_principal_exactly_at_zero_and_low_rates(self):
        base = dict(ec.with_preset(self.spec, 'baseline'), compute_ltc=.6)
        for rate in [0, .0001, .1]:
            for term in [1, 2, 5]:
                with self.subTest(rate=rate, term=term):
                    a = dict(base, compute_debt_rate=rate, debt_rate=rate,
                             compute_debt_years=term, shell_debt_years=term)
                    ledgers = ec.ledgers(a, self.spec)
                    for key in ['compute', 'shell']:
                        ledger = ledgers[key]
                        self.assertEqual(ledger['debt_principal_at_exit'], 0)
                        self.assertTrue(all(x == 0 for x in ledger['debt_service_path'][term:]))
                        self.assertGreater(ledger['debt_service_path'][term - 1], 0)
            # A loan maturing after the asset holding period is still outstanding on exit.
            longer = ec.compute(dict(base, compute_debt_rate=rate, compute_debt_years=8), self.spec)
            self.assertGreater(longer['debt_principal_at_exit'], 0)
            if rate == 0:
                self.assertEqual(longer['debt_principal_at_exit'], longer['debt'] * 3 / 8)
        self.assertEqual(ec.debt_payment(100, .1, 110, True, final_period=True), (110, 10, 0))

    def test_loss_tax_benefit_requires_explicit_usable_scenario(self):
        a = dict(ec.with_preset(self.spec, 'baseline'), price_gpu_hour=0, price_per_m_tokens=0)
        c = ec.compute(a, self.spec)
        self.assertLess(c['ebit'], 0)
        self.assertEqual(c['nopat'], c['ebit'])
        self.assertAlmostEqual(c['asset_cashflows'][1], c['revenue'] - c['opex'], places=4)
        usable = ec.compute(dict(a, loss_tax_shield='usable'), self.spec)
        self.assertAlmostEqual(usable['nopat'], usable['ebit'] * (1 - a['tax']), places=4)
        self.assertGreater(usable['asset_cashflows'][1], c['asset_cashflows'][1])
        m = ec.ledgers(a, self.spec)['model']
        self.assertEqual(m['nopat'], m['ebit'])

    def test_tco_basis_excludes_income_tax_and_financing(self):
        a = ec.with_preset(self.spec, 'baseline')
        life = ec.lifecycle(a, self.spec)
        altered = dict(a, tax=.5, compute_ltc=.8, compute_debt_years=3, shell_debt_years=4, loss_tax_shield='usable')
        self.assertEqual(ec.lifecycle(altered, self.spec), life)
        self.assertEqual(life['cashflow_basis'], 'before_income_tax_unfinanced')
        self.assertEqual(life['gpu_hours_basis'], 'billed_coverage_not_mfu')
        self.assertEqual(ec.compute(a, self.spec)['paid_hours_basis'], 'billed_coverage_not_mfu')
        self.assertIn('not_measured', ec.ledgers(a, self.spec)['model']['token_basis'])
        self.assertIn('working_capital', life['excluded_cashflows'])
        construction = [row for row in life['years'] if row['phase'] == 'construction']
        operation = [row for row in life['years'] if row['phase'] == 'operation']
        self.assertEqual(len(construction), a['construction_years'])
        self.assertTrue(all(row['capex_facility'] == life['facility_capex'] / a['construction_years'] for row in construction))
        self.assertEqual(operation[0]['capex_it'], life['it_capex'])
        self.assertNotEqual(ec.compute(altered, self.spec)['nopat'], ec.compute(a, self.spec)['nopat'])

    def test_browser_engine_matches_the_python_reference(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node not installed')
        cases = {pid: ec.with_preset(self.spec, pid) for pid in self.spec['presets']}
        base = ec.with_preset(self.spec, 'baseline')
        cases['fractional_sequential'] = dict(base, permit_months=7)
        cases['zero_rate_contract_maturity'] = dict(base, compute_ltc=.6, compute_debt_rate=0, debt_rate=0, compute_debt_years=2, shell_debt_years=5)
        cases['low_rate_contract_maturity'] = dict(base, compute_ltc=.6, compute_debt_rate=.0001, debt_rate=.0001, compute_debt_years=5, shell_debt_years=15)
        cases['low_rate_loan_still_outstanding'] = dict(base, compute_ltc=.6, compute_debt_rate=.0001, debt_rate=.0001, compute_debt_years=8, shell_debt_years=20)
        cases['fractional_parallel'] = dict(base, permit_months=19, permit_timing='parallel_with_gate')
        cases['short_depreciation_long_debt'] = dict(base, it_depreciation_years=2, compute_ltc=.6, compute_debt_years=8, shell_debt_years=20)
        cases['long_depreciation_short_debt'] = dict(base, it_depreciation_years=10, compute_ltc=.6, compute_debt_years=2, shell_debt_years=4)
        cases['loss_without_tax_benefit'] = dict(base, price_gpu_hour=0, price_per_m_tokens=0)
        cases['explicit_usable_tax_benefit'] = dict(cases['loss_without_tax_benefit'], loss_tax_shield='usable')
        script = ("const M=require(process.argv[1]);const spec=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));"
                  "const cases=JSON.parse(process.argv[3]),out={};for(const [id,a] of Object.entries(cases)){const r=M.run(a,spec);delete r.inputs;out[id]=r;}"
                  "process.stdout.write(JSON.stringify(out));")
        res = subprocess.run([node, '-e', script, str(ROOT / 'web/components/datacenter-model.js'), str(ROOT / MODEL), json.dumps(cases)],
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
        for pid, assumptions in cases.items():
            r = ec.run(assumptions, self.spec)
            r.pop('inputs')
            walk(pid, r, js[pid])
        self.assertGreater(count, 5000)
        self.assertEqual(mismatches[:5], [], f'{len(mismatches)} numbers differ between the JS mirror and the Python engine')


if __name__ == '__main__':
    unittest.main()
