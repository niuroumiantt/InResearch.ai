"""Reconciliation of the 2026-09-27 profit study with the cost.html model.

Author's illustrative calculation, USD. Reproduces the Morgan Stanley (Sept 2026 AI
Guidebook, p26-27) 1GW GB300 GPU-leasing example scaled to 100MW, runs it through the
same all-in cost formula as web/components/datacenter-cost.js, and shows how the
calculator's "surplus over cost of capital" relates to the report's NOPAT / ROIC.
Not a forecast, quote or investment advice.
"""
from pathlib import Path
import json, math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SPEC = json.loads((ROOT / 'data/datacenter_cost_model.json').read_text())

def crf(r, n):
    return 1 / n if r == 0 else r * (1 + r) ** n / ((1 + r) ** n - 1)

def calc(a):
    e_it = a['it_mw'] * 1000 * a['power_load'] * 8760
    kwh = e_it * a['pue']
    hours = a['devices'] * 8760 * a['productive']
    c = dict(servers=a['servers'] * crf(a['rate'], a['it_life']),
             network=a['network'] * crf(a['rate'], a['it_life']),
             facility=(a['facility'] + a['utility']) * crf(a['rate'], a['facility_life']),
             land=a['land'] * a['rate'],
             energy=kwh * a['energy_price'],
             demand=a['billed_kw'] * a['demand_rate'] * 12,
             opex=a['fixed_opex'],
             water=e_it * a['site_water_l'] / 1000 * a['water_price'])
    total = sum(c.values())
    rent = a.get('rent_price', 0)
    return dict(components=c, total=total, hours=hours, per_hour=total / hours,
                revenue=rent * hours, surplus_per_hour=rent - total / hours,
                surplus=rent * hours - total, coverage=rent * hours / total if rent else None)

# --- Report inputs (Morgan Stanley AI Guidebook 2026-09, p26-27; 预测估算) ---
MS = dict(gpus_per_gw=410_256, utilization=0.75, price=8.5, it_capex_per_gw=23e9, non_it_capex_per_gw=16e9,
          it_life=5, non_it_life=15, energy_other_per_gw=2.0e9, tax=0.21,
          revenue_per_gw=22.9e9, opex_per_gw=7.6e9, nopat_per_gw=12.1e9, roic=0.31)

def ms_at(price, scale=0.1):
    hours = MS['gpus_per_gw'] * scale * 8760 * MS['utilization']
    revenue = hours * price
    dep_it = MS['it_capex_per_gw'] * scale / MS['it_life']
    dep_non_it = MS['non_it_capex_per_gw'] * scale / MS['non_it_life']
    opex = dep_it + dep_non_it + MS['energy_other_per_gw'] * scale
    ebit = revenue - opex
    nopat = ebit * (1 - MS['tax'])
    capex = (MS['it_capex_per_gw'] + MS['non_it_capex_per_gw']) * scale
    return dict(price=price, hours=hours, revenue=revenue, depreciation_it=dep_it, depreciation_non_it=dep_non_it,
                opex=opex, ebit=ebit, ebit_margin=ebit / revenue, nopat=nopat, capex=capex, roic=nopat / capex)

base = dict(SPEC['assumptions'])
preset = dict(base, **SPEC['presets']['ms_gb300_lease']['changes'])
model = calc(preset)
report = ms_at(8.5)
paths = [ms_at(p) for p in (7.0, 8.0, 8.5, 9.0, 10.0)]
h100 = calc(dict(base, **SPEC['presets']['h100_contract_2026']['changes']))
baseline = calc(base)

# Consistency checks against the report (rounded values quoted in the study).
assert abs(report['revenue'] - 2.29e9) < 0.01e9, report['revenue']
assert abs(report['roic'] - 0.31) < 0.006, report['roic']
assert abs(report['nopat'] - 1.21e9) < 0.02e9, report['nopat']
assert math.isclose(baseline['total'], 1167777119.4007535)  # 2026-09-14 baseline unchanged
assert abs(model['revenue'] - report['revenue']) < 1e6          # same hours x price in both frames

out = dict(
    as_of='2026-09-27',
    status='author_illustrative_calculation',
    note='预设按摩根士丹利 1GW GB300 出租算例折算到 100MW。calculator 一栏是本站全成本模型（资本按 8% 资本成本率与寿命做年化回收）；report 一栏按研报口径（直线折旧、21% 税率、ROIC = NOPAT ÷ 总 capex）。两者收入相同，成本口径不同，不能把“每小时盈余”当成 NOPAT。',
    preset_inputs=preset,
    calculator=model,
    report_frame=report,
    report_price_paths=paths,
    baseline_2026_09_14=dict(total=baseline['total'], per_hour=baseline['per_hour']),
    h100_contract_reference=dict(rent=h100['revenue'] / h100['hours'], per_hour_cost=h100['per_hour'],
                                 surplus_per_hour=h100['surplus_per_hour'], coverage=h100['coverage']),
)
(HERE / 'profit-model-results.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(calculator=dict(total=model['total'], per_hour=model['per_hour'], revenue=model['revenue'],
                                       surplus_per_hour=model['surplus_per_hour'], surplus=model['surplus'], coverage=model['coverage']),
                      report=dict(revenue=report['revenue'], opex=report['opex'], nopat=report['nopat'], roic=report['roic']),
                      h100=out['h100_contract_reference']), ensure_ascii=False, indent=2))
