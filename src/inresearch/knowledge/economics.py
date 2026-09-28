"""Compute-operator ledger of the datacenter economics model (data/datacenter_economics_model.json).

Same arithmetic as web/components/datacenter-economics.js compute(): revenue from paid GPU hours,
energy from IT load × PUE, straight-line depreciation, NOPAT and ROIC on invested capital. The
dashboard's root account is derived here so the snapshot is reproducible and testable; the
registered preset note holds the check values (revenue, NOPAT, ROIC for the baseline)."""
HOURS = 8760


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
    own = mode == 'own'
    rent = a['shell_rent_per_mw'] * mw * 1e6
    facility_cost = rent if mode == 'lease' else a['colo_rate'] * mw * 1000 * 12 if mode == 'colo' else 0
    revenue = paid_hours * a['gpu_price']
    opex = energy + other + facility_cost
    ebitda = revenue - opex
    dep_it = it_capex / a['it_life']
    dep_shell = shell_capex / a['shell_life'] if own else 0
    ebit = ebitda - dep_it - dep_shell
    nopat = ebit * (1 - a['tax'])
    invested = it_capex + (shell_capex + land if own else 0)
    annual_cost = opex + dep_it + dep_shell + (ebit - nopat)
    return dict(
        gpus=gpus, paid_hours=paid_hours, revenue=revenue, energy=energy, other=other, facility_cost=facility_cost,
        opex=opex, ebitda=ebitda, dep_it=dep_it, dep_shell=dep_shell, ebit=ebit, nopat=nopat, invested=invested,
        roic=nopat / invested if invested else None, capex_total=it_capex + shell_capex + land,
        annual_cost=annual_cost,
        capex_per_mw=(it_capex + shell_capex + land) / mw / 1e6, revenue_per_mw=revenue / mw / 1e6,
        cost_per_mw=annual_cost / mw / 1e6, nopat_per_mw=nopat / mw / 1e6,
    )
