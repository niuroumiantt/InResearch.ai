"""Reference implementation of the lifecycle data center TCO model.

Mirrors web/components/datacenter-tco.js. Reads data/datacenter_tco_model.json,
computes every preset, checks internal identities (cash-flow sums, levelised
cost reconciliation, unit conversions) and writes results.json. USD; research
assumptions only. The framework, not the numbers, is the deliverable: every
input carries an evidence status so the page can list what still has to be
fetched.
"""
from pathlib import Path
import json, math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPEC = json.loads((ROOT / 'data/datacenter_tco_model.json').read_text(encoding='utf-8'))
HOURS = 8760

CATEGORIES = ['capex_facility', 'capex_it', 'energy', 'demand', 'water', 'staff', 'maintenance', 'maintenance_it', 'software', 'insurance_tax', 'bandwidth', 'other', 'lease', 'decommission']
IT_ONLY = ['capex_it', 'maintenance_it']


def crf(r, n):
    return 1 / n if r == 0 else r * (1 + r) ** n / ((1 + r) ** n - 1)


def resolve(a):
    """Apply select-driven defaults the way the page does when a preset is chosen."""
    a = dict(a)
    return a


def compute(a):
    mw = a['it_mw']
    it_kw = mw * 1000
    red = SPEC['redundancy_factors'][a['redundancy']]
    C, H = a['construction_years'], a['horizon_years']
    own = a['facility_mode'] == 'own'
    # --- capex per MW ($M) ---
    hard = {
        'building': a['capex_building'] if own else 0,
        'electrical': a['capex_electrical'] * red['electrical'] if own else 0,
        'mechanical': a['capex_mechanical'] * red['mechanical'] if own else 0,
        'fitout': a['capex_fitout'] if a['facility_mode'] != 'colo' else 0,
        'land': a['land_per_mw'] if own else 0,
    }
    hard_sum = sum(hard.values())
    soft = (hard_sum - hard['land']) * a['soft_cost_pct']
    contingency = (hard_sum - hard['land']) * a['contingency_pct']
    facility_capex_per_mw = hard_sum + soft + contingency
    facility_capex = facility_capex_per_mw * mw * 1e6
    facility_hard_ex_land = (hard_sum - hard['land']) * mw * 1e6
    it_capex = a['it_capex_per_kw'] * it_kw
    # --- yearly cash flows ---
    years = []
    total_years = C + H
    for y in range(total_years):
        row = {k: 0.0 for k in CATEGORIES}
        row['year'] = y - C + 1  # construction years are <= 0
        if y < C:
            row['capex_facility'] = facility_capex / C
            years.append(row)
            continue
        t = y - C  # operating year index 0..H-1
        ramp = a['ramp_year1'] if t == 0 else a['ramp_year2'] if t == 1 else 1.0
        esc_o = (1 + a['opex_escalation']) ** t
        esc_p = (1 + a['power_escalation']) ** t
        if t == 0:
            row['capex_it'] = it_capex
        elif a['it_refresh_years'] and t % a['it_refresh_years'] == 0 and t < H:
            row['capex_it'] = it_capex * a['refresh_cost_factor']
        it_load_kw = it_kw * a['load_factor'] * ramp
        it_kwh = it_load_kw * HOURS
        row['it_kwh'] = it_kwh
        row['energy'] = it_kwh * a['pue'] * a['power_price'] * esc_p
        row['demand'] = it_kw * a['pue'] * ramp * a['demand_rate'] * 12 * esc_p
        row['water'] = it_kwh * a['wue'] / 1000 * a['water_price'] * esc_o
        row['staff'] = a['fte_per_mw'] * mw * a['cost_per_fte'] * a['labor_index'] * esc_o
        row['maintenance'] = facility_hard_ex_land * a['maint_pct_facility'] * esc_o
        row['maintenance_it'] = it_capex * a['maint_pct_it'] * esc_o
        row['software'] = a['software_per_mw'] * mw * 1e6 * esc_o
        row['insurance_tax'] = facility_capex * (a['insurance_pct'] + (a['property_tax_rate'] if own else 0)) * esc_o
        row['bandwidth'] = a['bandwidth_per_mw'] * mw * 1e6 * esc_o
        row['other'] = a['other_opex_per_mw'] * mw * 1e6 * esc_o
        if a['facility_mode'] == 'lease':
            row['lease'] = a['shell_rent_per_mw'] * mw * 1e6 * esc_o
        elif a['facility_mode'] == 'colo':
            row['lease'] = a['colo_rate'] * it_kw * 12 * esc_o
        if t == H - 1:
            row['decommission'] = facility_capex * a['decommission_pct']
        row['gpu_hours'] = mw * a['gpus_per_mw'] * HOURS * a['gpu_utilization'] * ramp
        years.append(row)
    for row in years:
        row['total'] = sum(row[k] for k in CATEGORIES)
        row['capex'] = row['capex_facility'] + row['capex_it']
        row['opex'] = row['total'] - row['capex']
    # --- discounting: year index y discounted from the start of construction ---
    r = a['wacc']
    disc = lambda y: 1 / (1 + r) ** (y + 1)
    pv = {k: sum(row[k] * disc(i) for i, row in enumerate(years)) for k in CATEGORIES}
    pv_total = sum(pv.values())
    nominal_total = sum(row['total'] for row in years)
    pv_it_kwh = sum(row.get('it_kwh', 0) * disc(i) for i, row in enumerate(years))
    pv_gpu_hours = sum(row.get('gpu_hours', 0) * disc(i) for i, row in enumerate(years))
    # levelise over operating years (annuity starting after construction)
    annuity = sum(disc(C + t) for t in range(H))
    levelised = pv_total / annuity
    lev_by_cat = {k: pv[k] / annuity for k in CATEGORIES}
    per_mw_year = levelised / mw
    per_kw_month = levelised / it_kw / 12
    facility_levelised = levelised - sum(lev_by_cat[k] for k in IT_ONLY)
    per_kw_month_facility = facility_levelised / it_kw / 12
    per_it_kwh = pv_total / pv_it_kwh if pv_it_kwh else None
    per_gpu_hour = pv_total / pv_gpu_hours if pv_gpu_hours else None
    capex_share = (pv['capex_facility'] + pv['capex_it']) / pv_total
    # --- benchmark against the chosen business model ---
    bm = a['business_model']
    if bm == 'gpu_rental' and per_gpu_hour:
        market, cost = a['price_gpu_hour'], per_gpu_hour
        unit = '$/GPU·h'
    elif bm == 'colo':
        market, cost = a['price_colo_kw_month'], per_kw_month_facility
        unit = '$/kW·月'
    else:
        market, cost, unit = None, None, None
    margin = (market - cost) / market if market else None
    return dict(inputs=a, capex_per_mw=dict(hard, soft=soft, contingency=contingency, facility=facility_capex_per_mw, it=a['it_capex_per_kw'] / 1000),
                facility_capex=facility_capex, it_capex=it_capex, years=years, pv=pv, pv_total=pv_total, nominal_total=nominal_total,
                annuity=annuity, levelised=levelised, lev_by_cat=lev_by_cat, per_mw_year=per_mw_year, per_kw_month=per_kw_month,
                per_it_kwh=per_it_kwh, per_gpu_hour=per_gpu_hour, facility_levelised=facility_levelised, per_kw_month_facility=per_kw_month_facility, capex_share=capex_share, pv_it_kwh=pv_it_kwh, pv_gpu_hours=pv_gpu_hours,
                benchmark=dict(model=bm, market=market, cost=cost, unit=unit, margin=margin))


def with_preset(base, pid):
    a = dict(base)
    ch = dict(SPEC['presets'][pid]['changes'])
    for key, table in (('site', 'sites'), ('cooling', 'coolings'), ('it_class', 'it_classes')):
        if key in ch:
            for k, v in SPEC[table][ch[key]].items():
                if k in a and k not in ('label', 'source'):
                    a[k] = v
    a.update(ch)
    return a


def main():
    base = SPEC['assumptions']
    out = {pid: compute(with_preset(base, pid)) for pid in SPEC['presets']}
    b = out['ai_virginia_own']
    # identities
    assert math.isclose(sum(v for v in b['pv'].values()), b['pv_total'])
    assert math.isclose(b['levelised'] * b['annuity'], b['pv_total'])
    assert math.isclose(b['per_kw_month'] * b['inputs']['it_mw'] * 1000 * 12, b['levelised'])
    assert len(b['years']) == b['inputs']['construction_years'] + b['inputs']['horizon_years']
    assert sum(1 for y in b['years'] if y['capex_it'] > 0) == 1 + (b['inputs']['horizon_years'] - 1) // b['inputs']['it_refresh_years']
    # sanity ranges (illustrative): facility capex 10–20 $M/MW for a liquid-cooled N+1 build; GPU-hour cost 2–6 $
    assert 10 <= b['capex_per_mw']['facility'] <= 20, b['capex_per_mw']['facility']
    assert 2 <= b['per_gpu_hour'] <= 6, b['per_gpu_hour']
    # site effect: Texas power is cheaper than Virginia → lower energy PV, all else equal
    assert out['ai_texas_own']['pv']['energy'] < b['pv']['energy']
    # lease keeps only tenant fit-out capex and adds rent
    lease = out['ai_johor_lease']
    assert lease['pv']['capex_facility'] < 0.3 * b['pv']['capex_facility'] and lease['pv']['lease'] > 0 and lease['capex_per_mw']['building'] == 0
    (HERE / 'results.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=lambda x: None) + '\n', encoding='utf-8')
    for pid, res in out.items():
        print(f"{pid:22s} facility {res['capex_per_mw']['facility']:5.1f} $M/MW | levelised ${res['levelised']/1e6:7.1f}M/yr | {res['per_mw_year']/1e6:5.2f} $M/MW·yr | {res['per_kw_month']:6.0f} $/kW·mo | GPU·h {res['per_gpu_hour'] or 0:5.2f} | capex share {res['capex_share']*100:4.0f}%")


if __name__ == '__main__':
    main()
