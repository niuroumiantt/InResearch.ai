"""Unified datacenter economic model v3 (data/datacenter_model.json): the one reference implementation.

One input table, three ways of asking, four ledgers out. web/components/datacenter-model.js mirrors this
file line for line and tests/unit/test_model.py holds the two together and pins the calibration anchors:

* Morgan Stanley 1 GW GB300 lease-out (revenue 22.9 / NOPAT 12.1 / ROIC 31%, on total capex),
* Goldman Sachs 15% ROIC hurdle (11.6 bn/GW full-load revenue, 34.7% EBIT margin, on average annual capex),
* our own 2026-09-14 all-in cost baseline (1,167,777,119.40 a year, 4.10 per effective device hour).

Public functions all take the flat assumptions dict (after presets and tables are applied) and the model
spec for its tables:

    compute(a, spec)    steady-state operator ledger (one full year at the steady utilization)
    ledgers(a, spec)    the four ledgers: chip vendor, landlord, compute operator, model company
    lifecycle(a, spec)  pre-income-tax unfinanced schedule over permits + wait + construction + horizon
    inverse(a, spec)    given the target ROIC: required revenue, price, utilization or capex ceiling
    grid(a, spec)       capex/GW × price × utilization → ROIC, with the two report anchors
    run(a, spec)        everything above in one dict
"""
import math

HOURS = 8760
CATS = ['capex_facility', 'capex_it', 'energy', 'demand', 'water', 'staff', 'maintenance', 'maintenance_it',
        'software', 'insurance_tax', 'bandwidth', 'other', 'lease', 'decommission']
OPEX_CATS = CATS[2:]
IT_ONLY = ['capex_it', 'maintenance_it']
REDUNDANCY = {'n': {'electrical': 0.85, 'mechanical': 0.85}, 'n_plus_1': {'electrical': 1.0, 'mechanical': 1.0},
              '2n': {'electrical': 1.35, 'mechanical': 1.2}}
TABLES = [('site', 'regions'), ('cooling', 'coolings'), ('it_class', 'it_classes'), ('tenancy', 'tenancies'),
          ('price_path', 'price_paths'), ('tenant_credit', 'tenant_credits')]
OWNER_PARTS = {'own': ['building', 'electrical', 'mechanical', 'fitout'], 'bot': ['building', 'fitout'],
               'lease': ['fitout'], 'colo': []}
PARTNER_PARTS = {'bot': ['electrical', 'mechanical']}


def crf(r, n):
    """Capital recovery factor: the level annual payment that repays 1 over n years at rate r."""
    return 1 / n if r == 0 else r * (1 + r) ** n / ((1 + r) ** n - 1)


def irr(flows, times=None):
    """Annual IRR; optional elapsed-year times retain fractional schedule periods."""
    times = list(range(len(flows))) if times is None else times
    if len(times) != len(flows):
        raise ValueError('IRR cash flows and times must have equal lengths')
    # A common shift does not change IRR; normalize to avoid extreme exponents during long waits.
    origin = min(times) if times else 0
    def npv(r):
        return sum(f / (1 + r) ** (t - origin) for f, t in zip(flows, times))
    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def income_tax(a, taxable):
    """Simplified current-period tax; losses yield no immediate benefit unless explicitly usable.

    This scenario switch does not model tax-loss carryforwards, eligibility or refund timing.
    """
    base = taxable if a['loss_tax_shield'] == 'usable' else max(0.0, taxable)
    return base * a['tax']


def depreciation(basis, life, year):
    """Straight-line annual charge, capped at the remaining depreciable basis."""
    return basis * max(0.0, min(1.0, life - year)) / life


def debt_payment(balance, rate, payment, active, final_period=False):
    """Annual service and principal; settle the full contractual balance at maturity."""
    if not active or balance <= 0:
        return 0.0, 0.0, balance
    interest = balance * rate
    principal = balance if final_period else min(balance, max(0.0, payment - interest))
    return interest + principal, interest, max(0.0, balance - principal)


def apply_table(a, key, spec):
    """Copy the selected table record's numbers into the assumptions (only keys that are inputs)."""
    table = dict(TABLES).get(key)
    rec = (spec.get(table) or {}).get(a.get(key)) if table else None
    if not rec:
        return a
    for k, v in rec.items():
        if k in a and k != key:
            a[k] = v
    return a


def with_preset(spec, preset_id=None):
    """Baseline assumptions with a preset applied: table selections first, then the explicit overrides."""
    a = dict(spec['assumptions'])
    p = (spec.get('presets') or {}).get(preset_id) if preset_id else None
    if not p:
        return a
    changes = dict(p.get('changes') or {})
    for key, _table in TABLES:
        if key in changes:
            a[key] = changes[key]
            apply_table(a, key, spec)
    a.update(changes)
    return a


def effective_mw(a):
    """The energy quota (SemiAnalysis: the binding cap in China) caps the capacity that can be built."""
    quota = a.get('energy_quota_mw') or 0
    mw = a['it_mw']
    return min(mw, quota) if quota > 0 else mw


def capex(a, spec=None):
    """Facility capex per MW ($M) split by part and by who pays it under the facility mode."""
    red = ((spec or {}).get('redundancy_factors') or REDUNDANCY).get(a['redundancy']) or REDUNDANCY['n_plus_1']
    if a['capex_basis'] == 'generation':
        # the generation table's all-in shell number: building and fit-out as registered, the rest is M&E
        me = max(0.0, a['shell_capex_per_mw'] - a['capex_building'] - a['capex_fitout'])
        em = a['capex_electrical'] + a['capex_mechanical']
        e_share = a['capex_electrical'] / em if em > 0 else 0.6
        hard = {'building': a['capex_building'], 'electrical': me * e_share, 'mechanical': me * (1 - e_share),
                'fitout': a['capex_fitout']}
        soft_pct = cont_pct = 0.0
    else:
        hard = {'building': a['capex_building'], 'electrical': a['capex_electrical'] * red['electrical'],
                'mechanical': a['capex_mechanical'] * red['mechanical'], 'fitout': a['capex_fitout']}
        soft_pct, cont_pct = a['soft_cost_pct'], a['contingency_pct']
    mode = a['facility_mode']
    btm = a['btm_capex_per_mw'] if mode in ('own', 'bot') else 0.0
    owner_hard = sum(hard[k] for k in OWNER_PARTS.get(mode, [])) + btm
    soft, cont = owner_hard * soft_pct, owner_hard * cont_pct
    partner = sum(hard[k] for k in PARTNER_PARTS.get(mode, [])) * (1 + soft_pct + cont_pct)
    all_hard = sum(hard.values()) + a['btm_capex_per_mw']
    return dict(hard=hard, btm=btm, soft=soft, contingency=cont, owner_hard=owner_hard,
                facility=owner_hard + soft + cont, partner=partner,
                land=a['land_per_mw'] if mode in ('own', 'bot') else 0.0,
                all_in=all_hard * (1 + soft_pct + cont_pct), it=a['it_capex_per_kw'] / 1000,
                landlord=(all_hard - hard['fitout']) * (1 + soft_pct + cont_pct))


def _opyear(a, cap, mw, ramp, util, esc_p, esc_o, price_mult, fee_on):
    """One operating year's cost categories and revenue. ramp scales the IT load, util the paid hours."""
    it_kw = mw * 1000
    colo_bm = a['business_model'] == 'colo'
    it_capex = 0.0 if colo_bm else a['it_capex_per_kw'] * it_kw
    facility_capex = cap['facility'] * mw * 1e6
    owner_hard = cap['owner_hard'] * mw * 1e6
    owned = a['facility_mode'] in ('own', 'bot')
    it_kwh = it_kw * a['load_factor'] * ramp * HOURS
    r = {k: 0.0 for k in CATS}
    r['it_kwh'] = it_kwh
    r['energy'] = it_kwh * a['pue'] * a['power_price'] * esc_p
    r['demand'] = it_kw * a['pue'] * ramp * a['demand_rate'] * 12 * esc_p
    r['water'] = it_kwh * a['wue'] / 1000 * a['water_price'] * esc_o
    r['staff'] = a['fte_per_mw'] * mw * a['cost_per_fte'] * a['labor_index'] * esc_o
    r['maintenance'] = owner_hard * a['maint_pct_facility'] * esc_o
    r['maintenance_it'] = it_capex * a['maint_pct_it'] * esc_o
    r['software'] = a['software_per_mw'] * mw * 1e6 * esc_o
    r['insurance_tax'] = facility_capex * (a['insurance_pct'] + (a['property_tax_rate'] if owned else 0)) * esc_o
    r['bandwidth'] = a['bandwidth_per_mw'] * mw * 1e6 * esc_o
    r['other'] = a['other_opex_per_mw'] * mw * 1e6 * esc_o
    mode = a['facility_mode']
    if mode == 'lease':
        r['lease'] = a['shell_rent_per_mw'] * mw * 1e6 * esc_o
    elif mode == 'colo':
        r['lease'] = a['colo_rate'] * it_kw * 12 * esc_o
    elif mode == 'bot' and fee_on:
        # the M&E partner recovers its capex through a fixed service contract; no escalation
        r['lease'] = cap['partner'] * mw * 1e6 * crf(a['bot_service_rate'], a['bot_term_years'])
    r['gpu_hours'] = 0.0 if colo_bm else mw * a['gpus_per_mw'] * HOURS * util
    if a['business_model'] == 'gpu_rental':
        r['revenue'] = r['gpu_hours'] * a['price_gpu_hour'] * price_mult
    elif colo_bm:
        r['revenue'] = a['price_colo_kw_month'] * it_kw * 12 * ramp * price_mult
    else:
        r['revenue'] = 0.0
    r['opex'] = sum(r[k] for k in OPEX_CATS)
    return r


def _roic_denominator(a, invested):
    if a['roic_basis'] == 'avg_annual_capex':
        return invested / max(1, a['construction_years'])
    return invested


def compute(a, spec=None):
    """Steady-state operator ledger: one full year at the steady utilization, no ramp, no escalation."""
    cap = capex(a, spec)
    mw = effective_mw(a)
    y = _opyear(a, cap, mw, 1.0, a['gpu_utilization'], 1.0, 1.0, 1.0, True)
    it_kw = mw * 1000
    it_capex = 0.0 if a['business_model'] == 'colo' else a['it_capex_per_kw'] * it_kw
    facility_capex = cap['facility'] * mw * 1e6
    land = cap['land'] * mw * 1e6
    invested = it_capex + facility_capex + land
    it_life, shell_life = a['it_refresh_years'], a['horizon_years']
    dep_it = it_capex / a['it_depreciation_years']
    dep_shell = facility_capex / shell_life
    revenue, opex = y['revenue'], y['opex']
    ebitda = revenue - opex
    ebit = ebitda - dep_it - dep_shell
    nopat = ebit - income_tax(a, ebit)
    denominator = _roic_denominator(a, invested)
    capital_charge = it_capex * crf(a['wacc'], it_life) + facility_capex * crf(a['wacc'], shell_life) + land * a['wacc']
    annualised = capital_charge + opex
    paid_hours = y['gpu_hours']
    unit_cost = annualised / paid_hours if paid_hours else None
    cash = nopat + dep_it + dep_shell
    # Simplified operating-period cash flows; terminal book values are scenario exit assumptions.
    residual = (facility_capex * max(0.0, 1 - it_life / shell_life)
                + it_capex * max(0.0, 1 - it_life / a['it_depreciation_years']) + land)
    debt = it_capex * a['compute_ltc']
    ads = debt * crf(a['compute_debt_rate'], a['compute_debt_years']) if debt else 0.0
    equity = invested - debt
    flows, lev_flows, revenue_path, balance = [-invested], [-equity], [], debt
    dep_path, service_path, interest_path = [], [], []
    for t in range(it_life):
        rev_t = revenue * (1 + a['price_change']) ** t
        revenue_path.append(rev_t)
        dep_t = depreciation(it_capex, a['it_depreciation_years'], t) + depreciation(facility_capex, shell_life, t)
        dep_path.append(dep_t)
        ebit_t = rev_t - opex - dep_t
        flows.append(rev_t - opex - income_tax(a, ebit_t))
        service, interest, balance = debt_payment(balance, a['compute_debt_rate'], ads, t < a['compute_debt_years'],
                                                  t + 1 >= a['compute_debt_years'])
        service_path.append(service)
        interest_path.append(interest)
        lev_flows.append(rev_t - opex - service - income_tax(a, ebit_t - interest))
    flows[-1] += residual
    lev_flows[-1] += residual - balance
    price = a['price_gpu_hour'] if a['business_model'] == 'gpu_rental' else None
    per_mw = lambda v: v / mw / 1e6 if mw else None
    return dict(
        mw=mw, gpus=mw * a['gpus_per_mw'], paid_hours=paid_hours, paid_hours_basis='billed_coverage_not_mfu', revenue=revenue, energy=y['energy'],
        other=y['other'], facility_cost=y['lease'], opex=opex, opex_by=dict((k, y[k]) for k in OPEX_CATS),
        ebitda=ebitda, dep_it=dep_it, dep_shell=dep_shell, ebit=ebit, nopat=nopat,
        it_capex=it_capex, facility_capex=facility_capex, land=land, invested=invested,
        roic_denominator=denominator, roic=nopat / denominator if denominator else None,
        ebitda_margin=ebitda / revenue if revenue else None, ebit_margin=ebit / revenue if revenue else None,
        nopat_margin=nopat / revenue if revenue else None,
        capital_charge=capital_charge, annualised=annualised, unit_cost=unit_cost,
        surplus_per_hour=(price - unit_cost) if price is not None and unit_cost is not None else None,
        coverage=revenue / annualised if annualised else None,
        payback=invested / cash if cash > 0 else None, irr=irr(flows), debt=debt, equity=equity, debt_service=ads,
        irr_levered=irr(lev_flows) if equity > 0 else None, revenue_path=revenue_path,
        asset_cashflows=flows, equity_cashflows=lev_flows, depreciation_path=dep_path,
        debt_service_path=service_path, interest_path=interest_path, debt_principal_at_exit=balance, debt_principal_basis='outstanding_contractual_principal_not_net_carrying_amount',
        cashflow_basis='simplified_after_income_tax_asset_and_equity_period', terminal_book_value_assumption=residual,
        terminal_value_basis='remaining_asset_book_value_plus_land_assumption_not_market_price',
        capex_total=invested, annual_cost=opex + dep_it + dep_shell + (ebit - nopat),
        capex_per_mw=per_mw(invested), revenue_per_mw=per_mw(revenue),
        cost_per_mw=per_mw(opex + dep_it + dep_shell + (ebit - nopat)), nopat_per_mw=per_mw(nopat),
        capex_per_gw=invested / mw * 1000 if mw else None, revenue_per_gw=revenue / mw * 1000 if mw else None,
        it_kwh=y['it_kwh'], water_m3=y['it_kwh'] * a['wue'] / 1000,
        capex_split=dict(it=cap['it'], facility=cap['facility'], land=cap['land'], partner=cap['partner'],
                         hard=cap['hard'], btm=cap['btm'], soft=cap['soft'], contingency=cap['contingency']),
    )


def ledgers(a, spec=None):
    """Four ledgers on one project: chip vendor, landlord, compute operator, model company."""
    c = compute(a, spec)
    mw = c['mw']
    cap = capex(a, spec)
    # Ledger 1: the landlord who builds the shell and leases it at shell_rent_per_mw
    shell_capex = cap['landlord'] * mw * 1e6
    land = a['land_per_mw'] * mw * 1e6
    invested = shell_capex + land
    rent = a['shell_rent_per_mw'] * mw * 1e6
    term = a['lease_term']
    rents = [rent * (1 + a['escalator']) ** t for t in range(term)]
    nois = [r * a['noi_margin'] for r in rents]
    noi = rent * a['noi_margin']
    debt = invested * a['shell_ltc']
    ads = debt * crf(a['debt_rate'], a['shell_debt_years']) if debt else 0.0
    equity = invested - debt
    residual = shell_capex * a['residual_share']
    unlev = [-invested] + nois
    unlev[-1] += residual
    lev, after_tax, service_path = [-equity], [-equity], []
    bal = debt
    for t, n in enumerate(nois):
        service, interest, bal = debt_payment(bal, a['debt_rate'], ads, t < a['shell_debt_years'],
                                              t + 1 >= a['shell_debt_years'])
        service_path.append(service)
        dep_t = depreciation(shell_capex, a['horizon_years'], t)
        lev.append(n - service)
        after_tax.append(n - service - income_tax(a, n - dep_t - interest))
    lev[-1] += residual - bal
    after_tax[-1] += residual - bal
    opt_years = a['renewal_options'] * a['renewal_years']
    opt_rents = [rent * (1 + a['escalator']) ** (term + t) for t in range(opt_years)]
    with_opt = [-invested] + nois + [r * a['noi_margin'] * a['renewal_probability'] for r in opt_rents]
    with_opt[-1] += residual
    tax_y1 = income_tax(a, noi - shell_capex / a['horizon_years'] - debt * a['debt_rate'])
    shell = dict(invested=invested, rent_y1=rent, noi_y1=noi, yield_on_cost=noi / invested if invested else None,
                 contract_value=sum(rents), contract_value_with_options=sum(rents) + sum(opt_rents),
                 option_years=opt_years, debt=debt, equity=equity, debt_service=ads,
                 debt_service_path=service_path, debt_principal_at_exit=bal, debt_principal_basis='outstanding_contractual_principal_not_net_carrying_amount',
                 equity_cashflows_before_tax=lev, equity_cashflows_after_tax=after_tax,
                 dscr=noi / ads if ads else None, cash_on_cash=(noi - ads) / equity if equity > 0 else None,
                 cash_on_cash_after_tax=(noi - ads - tax_y1) / equity if equity > 0 else None, tax_y1=tax_y1,
                 payback=invested / noi if noi > 0 else None, irr_unlevered=irr(unlev),
                 irr_levered=irr(lev) if equity > 0 else None,
                 irr_levered_after_tax=irr(after_tax) if equity > 0 else None, irr_with_options=irr(with_opt))
    # Ledger 3: the model company turning GPU hours into tokens
    m_hours = c['paid_hours'] * a['monetized_share']
    tokens = m_hours * 3600 * a['tokens_per_gpu_sec']
    m_revenue = tokens / 1e6 * a['price_per_m_tokens']
    if a['compute_source'] == 'own':
        m_cost, m_invested = c['opex'] + c['dep_it'] + c['dep_shell'], c['invested']
    else:
        m_cost, m_invested = m_hours * a['rent_price'], 0.0
    m_ebit = m_revenue - m_cost
    m_nopat = m_ebit - income_tax(a, m_ebit)
    model = dict(token_basis='illustrative_billed_hours_times_share_and_throughput_not_measured', tokens=tokens, revenue=m_revenue, cost=m_cost, ebit=m_ebit, nopat=m_nopat,
                 nopat_margin=m_nopat / m_revenue if m_revenue else None,
                 revenue_per_gpu_hour=m_revenue / m_hours if m_hours else None, invested=m_invested,
                 roic=m_nopat / m_invested if m_invested else None)
    # Ledger 0: the chip vendor's gross profit inside the IT capex
    chip_gp = c['it_capex'] * a['accelerator_share'] * a['chip_gross_margin']
    chip = dict(accelerator_capex=c['it_capex'] * a['accelerator_share'], gross_profit=chip_gp,
                gross_profit_per_year=chip_gp / a['it_refresh_years'])
    split = dict(chip=chip['gross_profit_per_year'], landlord=noi if a['facility_mode'] == 'lease' else 0.0,
                 compute=0.0 if a['compute_source'] == 'own' else c['nopat'], model=m_nopat)
    stack = dict(accelerators=c['it_capex'] * a['accelerator_share'], other_it=c['it_capex'] * (1 - a['accelerator_share']),
                 facility=c['facility_capex'], partner=cap['partner'] * mw * 1e6, land=c['land'])
    return dict(compute=c, shell=shell, model=model, chip=chip, split=split, capex_stack=stack)


def lifecycle(a, spec=None):
    """Pre-income-tax, unfinanced cost/revenue schedule; annual settlement with exact stage times.

    Permits are sequential with the gate wait or explicitly parallel with it. Neither mode
    permits construction before both finish. Waiting-period carrying costs are not assumed.
    """
    cap = capex(a, spec)
    mw = effective_mw(a)
    it_kw = mw * 1000
    C, W, H = a['construction_years'], a['gate_wait_years'], a['horizon_years']
    permit = a['permit_months'] / 12
    if a['permit_timing'] not in ('sequential', 'parallel_with_gate'):
        raise ValueError('Unknown permit timing')
    prebuild = max(W, permit) if a['permit_timing'] == 'parallel_with_gate' else W + permit
    lead = prebuild + C
    it_capex = 0.0 if a['business_model'] == 'colo' else a['it_capex_per_kw'] * it_kw
    facility_capex = (cap['facility'] + cap['land']) * mw * 1e6
    years = []
    waiting = math.ceil(prebuild)
    def row_at(phase, year, start, end):
        row = {k: 0.0 for k in CATS}
        row.update(phase=phase, year=year, start_year=start, end_year=end,
                   duration_years=end - start, it_kwh=0.0, gpu_hours=0.0, revenue=0.0)
        return row
    for t in range(waiting):
        years.append(row_at('wait', t - waiting - C + 1, t, min(t + 1, prebuild)))
    for t in range(C):
        row = row_at('construction', t - C + 1, prebuild + t, prebuild + t + 1)
        row['capex_facility'] = facility_capex / C
        years.append(row)
    for t in range(H):
        row = row_at('operation', t + 1, lead + t, lead + t + 1)
        ramp = a['ramp_year1'] if t == 0 else a['ramp_year2'] if t == 1 else 1.0
        util = a['util_year1'] if t == 0 else a['util_year2'] if t == 1 else a['gpu_utilization']
        row.update(_opyear(a, cap, mw, ramp, util, (1 + a['power_escalation']) ** t, (1 + a['opex_escalation']) ** t,
                          (1 + a['price_change']) ** t, t < a['bot_term_years']))
        if t == 0:
            row['capex_it'] = it_capex
        elif a['it_refresh_years'] and t % a['it_refresh_years'] == 0:
            row['capex_it'] = it_capex * a['refresh_cost_factor']
        if t == H - 1:
            row['decommission'] = cap['facility'] * mw * 1e6 * a['decommission_pct']
        years.append(row)
    for r in years:
        r['total'] = sum(r[k] for k in CATS)
        r['capex'] = r['capex_facility'] + r['capex_it']
        r['opex'] = r['total'] - r['capex']
        r['net'] = r['revenue'] - r['total']
    rate = a['wacc']
    disc = lambda time: 1 / (1 + rate) ** time
    pv = {k: sum(r[k] * disc(r['end_year']) for r in years) for k in CATS}
    pv_total = sum(pv.values())
    nominal_total = sum(r['total'] for r in years)
    pv_it_kwh = sum(r['it_kwh'] * disc(r['end_year']) for r in years)
    pv_gpu_hours = sum(r['gpu_hours'] * disc(r['end_year']) for r in years)
    pv_revenue = sum(r['revenue'] * disc(r['end_year']) for r in years)
    annuity = sum(disc(lead + t + 1) for t in range(H))
    levelised = pv_total / annuity
    lev = {k: pv[k] / annuity for k in CATS}
    facility_levelised = levelised - sum(lev[k] for k in IT_ONLY)
    out = dict(
        years=years, pv=pv, pv_total=pv_total, nominal_total=nominal_total, pv_revenue=pv_revenue,
        npv=pv_revenue - pv_total, irr=irr([r['net'] for r in years], [r['end_year'] for r in years]),
        cashflow_basis='before_income_tax_unfinanced', settlement_basis='period_end', gpu_hours_basis='billed_coverage_not_mfu',
        excluded_cashflows=['income_tax', 'debt_draws', 'debt_service', 'working_capital', 'waiting_carrying_costs', 'asset_disposals'],
        annuity=annuity, levelised=levelised, lev=lev,
        facility_levelised=facility_levelised, lead_years=lead, lead_months=lead * 12,
        preconstruction_years=prebuild, permit_timing=a['permit_timing'],
        capex_per_mw=dict(cap['hard'], btm=cap['btm'], soft=cap['soft'], contingency=cap['contingency'],
                          land=cap['land'], facility=cap['facility'], partner=cap['partner'], it=cap['it']),
        facility_capex=facility_capex, it_capex=it_capex,
        per_mw_year=levelised / mw, per_kw_month=levelised / it_kw / 12, per_kw_month_facility=facility_levelised / it_kw / 12,
        per_it_kwh=pv_total / pv_it_kwh if pv_it_kwh else None, per_gpu_hour=pv_total / pv_gpu_hours if pv_gpu_hours else None,
        capex_share=(pv['capex_facility'] + pv['capex_it']) / pv_total if pv_total else None,
    )
    bm = a['business_model']
    market = cost = unit = None
    if bm == 'gpu_rental' and out['per_gpu_hour']:
        market, cost, unit = a['price_gpu_hour'], out['per_gpu_hour'], '$/GPU·h'
    elif bm == 'colo':
        market, cost, unit = a['price_colo_kw_month'], out['per_kw_month_facility'], '$/kW·月'
    out['benchmark'] = dict(model=bm, market=market, cost=cost, unit=unit,
                            margin=(market - cost) / market if market else None)
    return out


def inverse(a, spec=None):
    """Goldman Sachs' question: at the target ROIC, what revenue, price, utilization or capex is needed."""
    c = compute(a, spec)
    mw = c['mw']
    t = a['tax']
    target = a['target_roic']
    nopat = target * c['roic_denominator']
    ebit = nopat / (1 - t)
    dep = c['dep_it'] + c['dep_shell']
    revenue = ebit + dep + c['opex']
    full_hours = c['gpus'] * HOURS
    price = revenue / c['paid_hours'] if c['paid_hours'] else None
    utilization = revenue / (full_hours * a['price_gpu_hour']) if full_hours and a['price_gpu_hour'] else None
    s = capex_scale_for_target(a, spec, target)
    return dict(target_roic=target, roic_basis=a['roic_basis'], denominator=c['roic_denominator'],
                required_nopat=nopat, required_ebit=ebit, required_revenue=revenue,
                required_revenue_per_gw=revenue / mw * 1000 if mw else None,
                ebit_margin=ebit / revenue if revenue else None, nopat_margin=nopat / revenue if revenue else None,
                required_price=price, required_utilization=utilization,
                capex_scale=s, capex_ceiling=c['invested'] * s if s is not None else None,
                capex_ceiling_per_gw=c['invested'] * s / mw * 1000 if s is not None and mw else None,
                current_roic=c['roic'], current_revenue=c['revenue'], gap=revenue - c['revenue'])


CAPITAL_KEYS = ['it_capex_per_kw', 'shell_capex_per_mw', 'btm_capex_per_mw', 'capex_building', 'capex_electrical',
                'capex_mechanical', 'capex_fitout', 'land_per_mw']


def scale_capital(a, s):
    b = dict(a)
    for k in CAPITAL_KEYS:
        b[k] = a[k] * s
    return b


def capex_scale_for_target(a, spec, target):
    """The factor on every capital line at which the current revenue just clears the target ROIC (bisection:
    maintenance, insurance and tax move with capex, so there is no closed form). None when even zero capex fails."""
    def roic(s):
        r = compute(scale_capital(a, s), spec)['roic']
        return r if r is not None else -1.0
    lo, hi = 1e-6, 1.0
    if roic(lo) < target:
        return None
    while roic(hi) > target and hi < 1e6:
        hi *= 2
    for _ in range(80):
        mid = (lo + hi) / 2
        if roic(mid) >= target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def scaled_capex(a, capex_per_gw, spec=None):
    """Assumptions with every capital line scaled so total invested capex per GW hits the given $bn."""
    c = compute(a, spec)
    if not c['capex_per_gw']:
        return dict(a)
    return scale_capital(a, capex_per_gw * 1e9 / c['capex_per_gw'])


def grid(a, spec=None):
    """capex/GW × price × utilization → ROIC. The two anchors mark where the reports sit."""
    g = (spec or {}).get('grid') or {}
    capex_axis = g.get('capex_per_gw') or [34, 38, 42.4, 46, 51]
    price_factors = g.get('price_factors') or [0.6, 0.8, 1.0, 1.2, 1.4]
    util_axis = g.get('utilization') or [0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
    cells = []
    for u in util_axis:
        plane = []
        for cpg in capex_axis:
            b = scaled_capex(a, cpg, spec)
            row = []
            for f in price_factors:
                bb = dict(b, gpu_utilization=u, price_gpu_hour=a['price_gpu_hour'] * f)
                row.append(compute(bb, spec)['roic'])
            plane.append(row)
        cells.append(plane)
    return dict(capex_per_gw=capex_axis, price_factors=price_factors,
                prices=[a['price_gpu_hour'] * f for f in price_factors], utilization=util_axis, roic=cells,
                anchors=(spec or {}).get('anchors') or [])


def sensitivity(a, spec=None):
    """Single-factor swings on ROIC and on the levelised cost per kW·month."""
    base_c, base_l = compute(a, spec), lifecycle(a, spec)
    rows = []
    for d in (spec or {}).get('sensitivity_drivers') or []:
        lo, hi = dict(a), dict(a)
        if d.get('delta_abs'):
            lo[d['key']] = max(0.0, a[d['key']] - d['delta_abs'])
            hi[d['key']] = a[d['key']] + d['delta_abs']
        else:
            lo[d['key']] = a[d['key']] * (1 - d['delta'])
            hi[d['key']] = a[d['key']] * (1 + d['delta'])
        cl, ch = compute(lo, spec), compute(hi, spec)
        ll, lh = lifecycle(lo, spec), lifecycle(hi, spec)
        rows.append(dict(key=d['key'], label=d['label'], delta=d.get('delta'), delta_abs=d.get('delta_abs'),
                         roic_lo=(cl['roic'] or 0) - (base_c['roic'] or 0), roic_hi=(ch['roic'] or 0) - (base_c['roic'] or 0),
                         kw_lo=ll['per_kw_month'] - base_l['per_kw_month'], kw_hi=lh['per_kw_month'] - base_l['per_kw_month']))
    return rows


def readiness(a, spec=None):
    """Calculation inputs are scenarios, never evidence of a project approval."""
    spec = spec or {}
    governance = spec.get('input_governance', {})
    evidence = spec.get('evidence', {})
    unverified = sorted(k for k in governance if evidence.get(k, {}).get('status') not in ('sourced', 'input'))
    return {'status': 'scenario_only', 'project_feasibility': 'not_verified',
            'capacity_basis': 'scenario_limit_not_approval' if a.get('energy_quota_mw', 0) > 0 else 'unknown_or_unset',
            'unverified_inputs': unverified,
            'scope': 'Global source registration does not validate preset overrides or project/workload applicability.'}


def run(a, spec=None):
    return dict(inputs=a, ledgers=ledgers(a, spec), lifecycle=lifecycle(a, spec), inverse=inverse(a, spec),
                grid=grid(a, spec), sensitivity=sensitivity(a, spec), readiness=readiness(a, spec))
