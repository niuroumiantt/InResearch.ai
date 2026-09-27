"""Reference implementation of the four-ledger data center economics model.

Mirrors web/components/datacenter-economics.js. Reads the versioned spec in
data/datacenter_economics_model.json, computes every preset, asserts the
calibration points quoted from the Morgan Stanley AI Guidebook (Sept 2026)
and the disclosed powered-shell / China colocation figures, and writes
results.json next to this file. USD; illustrative research assumptions only.
"""
from pathlib import Path
import json, math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPEC = json.loads((ROOT / 'data/datacenter_economics_model.json').read_text(encoding='utf-8'))
HOURS = 8760


def crf(r, n):
    return 1 / n if r == 0 else r * (1 + r) ** n / ((1 + r) ** n - 1)


def irr(flows, lo=-0.99, hi=10.0):
    def npv(r):
        return sum(f / (1 + r) ** t for t, f in enumerate(flows))
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def compute(a):
    mw = a['it_mw']
    gpus = mw * a['gpus_per_mw']
    paid_hours = gpus * HOURS * a['utilization']
    energy_kwh = mw * 1000 * a['power_load'] * a['pue'] * HOURS
    energy = energy_kwh * a['power_price']
    other = a['other_opex_per_mw'] * mw * 1e6
    it_capex = a['it_capex_per_mw'] * mw * 1e6
    shell_capex = (a['shell_capex_per_mw'] + a['btm_capex_per_mw']) * mw * 1e6
    land = a['land_per_mw'] * mw * 1e6
    mode = a['facility_mode']
    rent = a['shell_rent_per_mw'] * mw * 1e6
    facility_cost = rent if mode == 'lease' else (a['colo_rate'] * mw * 1000 * 12 if mode == 'colo' else 0)
    own = mode == 'own'

    # Ledger 2: compute operator
    revenue = paid_hours * a['gpu_price']
    opex = energy + other + facility_cost
    ebitda = revenue - opex
    dep_it = it_capex / a['it_life']
    dep_shell = shell_capex / a['shell_life'] if own else 0
    ebit = ebitda - dep_it - dep_shell
    nopat = ebit * (1 - a['tax'])
    invested = it_capex + (shell_capex + land if own else 0)
    capital_charge = it_capex * crf(a['wacc'], a['it_life']) + ((shell_capex * crf(a['wacc'], a['shell_life']) + land * a['wacc']) if own else 0)
    unit_cost = (capital_charge + opex) / paid_hours
    cash = nopat + dep_it + dep_shell
    residual = (shell_capex * max(0, 1 - a['it_life'] / a['shell_life']) + land) if own else 0
    flows = [-invested]
    debt_c = it_capex * a['compute_ltc']
    ads_c = debt_c * crf(a['compute_debt_rate'], a['it_life']) if debt_c else 0
    equity_c = invested - debt_c
    lev_flows = [-equity_c]
    balance = debt_c
    for t in range(a['it_life']):
        rev_t = revenue * (1 + a['price_change']) ** t
        ebitda_t = rev_t - opex
        ebit_t = ebitda_t - dep_it - dep_shell
        flows.append(ebit_t * (1 - a['tax']) + dep_it + dep_shell)
        interest = balance * a['compute_debt_rate']
        principal = ads_c - interest if debt_c else 0
        balance -= principal
        tax_t = max(0, ebit_t - interest) * a['tax']
        lev_flows.append(ebitda_t - ads_c - tax_t)
    flows[-1] += residual
    lev_flows[-1] += residual
    compute_ledger = dict(gpus=gpus, paid_hours=paid_hours, revenue=revenue, energy=energy, other=other, facility_cost=facility_cost,
                          opex=opex, ebitda=ebitda, dep_it=dep_it, dep_shell=dep_shell, ebit=ebit, nopat=nopat, invested=invested,
                          roic=nopat / invested if invested else None, ebitda_margin=ebitda / revenue if revenue else None,
                          ebit_margin=ebit / revenue if revenue else None, unit_cost=unit_cost, breakeven_price=unit_cost,
                          surplus_per_hour=a['gpu_price'] - unit_cost, payback=invested / cash if cash > 0 else None,
                          irr=irr(flows), capex_total=it_capex + shell_capex + land,
                          debt=debt_c, equity=equity_c, debt_service=ads_c, irr_levered=irr(lev_flows) if equity_c > 0 else None,
                          equity_multiple=sum(lev_flows[1:]) / equity_c if equity_c > 0 else None,
                          revenue_path=[revenue * (1 + a['price_change']) ** t for t in range(a['it_life'])])

    # Ledger 1: landlord (powered shell), always evaluated on the shell inputs
    shell_invested = shell_capex + land
    noi = rent * a['noi_margin']
    term = a['lease_term']
    esc = a['escalator']
    rents = [rent * (1 + esc) ** t for t in range(term)]
    nois = [r * a['noi_margin'] for r in rents]
    debt = shell_invested * a['shell_ltc']
    ads = debt * crf(a['debt_rate'], term)
    equity = shell_invested - debt
    residual_value = shell_capex * a['residual_share']
    unlev = [-shell_invested] + nois[:]
    unlev[-1] += residual_value
    lev = [-equity] + [n - ads for n in nois]
    lev[-1] += residual_value
    # cash taxes on the landlord: (NOI - depreciation - interest) x tax, amortising debt
    dep_s = shell_capex / a['shell_life']
    balance = debt
    after_tax = [-equity]
    for n in nois:
        interest = balance * a['debt_rate']
        principal = ads - interest if debt else 0
        balance -= principal
        after_tax.append(n - ads - max(0, n - dep_s - interest) * a['tax'])
    after_tax[-1] += residual_value
    # renewal options: probability-weighted NOI beyond the base term
    opt_years = a['renewal_options'] * a['renewal_years']
    opt_nois = [rent * (1 + esc) ** (term + t) * a['noi_margin'] for t in range(opt_years)]
    with_opt = [-shell_invested] + nois[:] + [n * a['renewal_probability'] for n in opt_nois]
    with_opt[-1] += residual_value
    tax_y1 = max(0, noi - dep_s - debt * a['debt_rate']) * a['tax']
    shell_ledger = dict(invested=shell_invested, rent_y1=rent, noi_y1=noi, yield_on_cost=noi / shell_invested if shell_invested else None,
                        contract_value=sum(rents), contract_value_with_options=sum(rents) + sum(rent * (1 + esc) ** (term + t) for t in range(opt_years)),
                        debt=debt, equity=equity, debt_service=ads,
                        dscr=noi / ads if ads else None, cash_on_cash=(noi - ads) / equity if equity else None,
                        cash_on_cash_after_tax=(noi - ads - tax_y1) / equity if equity else None, tax_y1=tax_y1,
                        payback=shell_invested / noi if noi else None, irr_unlevered=irr(unlev), irr_levered=irr(lev) if equity > 0 else None,
                        irr_levered_after_tax=irr(after_tax) if equity > 0 else None, irr_with_options=irr(with_opt), option_years=opt_years)

    # Ledger 3: model / API company
    m_hours = paid_hours * a['monetized_share']
    tokens = m_hours * 3600 * a['tokens_per_gpu_sec']
    m_revenue = tokens / 1e6 * a['price_per_m_tokens']
    if a['compute_source'] == 'own':
        own_opex = energy + other + (facility_cost if not own else 0)
        own_dep_shell = shell_capex / a['shell_life'] if own else 0
        m_cost = own_opex + dep_it + own_dep_shell
        m_invested = invested
    else:
        m_cost = m_hours * a['rent_price']
        m_invested = 0
    m_ebit = m_revenue - m_cost
    m_nopat = m_ebit * (1 - a['tax'])
    model_ledger = dict(tokens=tokens, revenue=m_revenue, cost=m_cost, ebit=m_ebit, nopat=m_nopat,
                        nopat_margin=m_nopat / m_revenue if m_revenue else None, revenue_per_gpu_hour=m_revenue / m_hours if m_hours else None,
                        invested=m_invested, roic=m_nopat / m_invested if m_invested else None)

    # Ledger 0: chip vendor
    chip_gp = it_capex * a['accelerator_share'] * a['chip_gross_margin']
    chip_ledger = dict(accelerator_capex=it_capex * a['accelerator_share'], gross_profit=chip_gp, gross_profit_per_year=chip_gp / a['it_life'])

    split = dict(chip=chip_gp / a['it_life'], landlord=noi if mode == 'lease' else 0,
                 compute=0 if a['compute_source'] == 'own' else nopat,
                 model=m_nopat)
    return dict(inputs=a, compute=compute_ledger, shell=shell_ledger, model=model_ledger, chip=chip_ledger, split=split,
                capex_stack=dict(accelerators=it_capex * a['accelerator_share'], other_it=it_capex * (1 - a['accelerator_share']),
                                 shell=a['shell_capex_per_mw'] * mw * 1e6, btm=a['btm_capex_per_mw'] * mw * 1e6, land=land))


def with_preset(base, preset):
    a = dict(base)
    ch = dict(preset['changes'])
    if 'generation' in ch:
        g = SPEC['generations'][ch['generation']]
        for k in ('gpus_per_mw', 'it_capex_per_mw', 'shell_capex_per_mw', 'btm_capex_per_mw'):
            a[k] = g[k]
    a.update(ch)
    return a


def main():
    base = SPEC['assumptions']
    out = {}
    for pid, p in SPEC['presets'].items():
        out[pid] = compute(with_preset(base, p))
    per_gw = 10  # presets are 100 MW
    ms = out['ms_hyperscaler_gb300']['compute']
    assert abs(ms['revenue'] * per_gw - 22.9e9) < 0.05e9, ms['revenue']
    assert abs(ms['nopat'] * per_gw - 12.1e9) < 0.1e9, ms['nopat']
    assert abs(ms['roic'] - 0.31) < 0.006, ms['roic']
    assert abs(ms['ebit_margin'] - 0.67) < 0.01, ms['ebit_margin']
    own = out['model_api_own']['model']
    assert abs(own['revenue'] * per_gw - 30.4e9) < 0.2e9, own['revenue']
    assert abs(own['nopat'] * per_gw - 18.0e9) < 0.3e9, own['nopat']
    assert abs(own['roic'] - 0.46) < 0.01, own['roic']
    rent = out['model_api_rent']['model']
    assert abs(rent['revenue'] * per_gw - 40.5e9) < 0.3e9, rent['revenue']
    assert abs(rent['nopat'] * per_gw - 10.0e9) < 0.3e9, rent['nopat']
    assert abs(rent['nopat_margin'] - 0.25) < 0.01, rent['nopat_margin']
    shell = out['shell_three_net']['shell']
    assert abs(shell['yield_on_cost'] - 0.19) < 0.001, shell['yield_on_cost']
    cn = out['china_colo_gds']['shell']
    assert abs(cn['yield_on_cost'] - 0.11) < 0.001, cn['yield_on_cost']
    (HERE / 'results.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=lambda x: None) + '\n', encoding='utf-8')
    nc = out['neocloud_h100_2026']['compute']
    assert nc['debt'] > 0 and nc['revenue_path'][1] < nc['revenue_path'][0] and nc['equity_multiple'] is not None
    sh = out['shell_three_net']['shell']
    assert sh['option_years'] == 15 and sh['irr_with_options'] > sh['irr_unlevered'] and sh['cash_on_cash_after_tax'] < sh['cash_on_cash']
    for pid, r in out.items():
        c, s, m = r['compute'], r['shell'], r['model']
        print(f"{pid:24s} compute ROIC {c['roic']*100:6.1f}%  unit ${c['unit_cost']:.2f}/h  payback {c['payback'] or 0:5.1f}y  | shell yield {s['yield_on_cost']*100:5.1f}% CoC {(s['cash_on_cash'] or 0)*100:5.1f}% DSCR {s['dscr'] or 0:4.2f} | model margin {(m['nopat_margin'] or 0)*100:5.1f}%")


if __name__ == '__main__':
    main()
