"""The homepage and task guide have explicit anonymous read projections.

All other pages, research files, APIs and assets require a session. The former
reader grants remain explicit intern grants; hiding navigation never authorizes
a request. URL paths are decoded/normalized by the HTTP adapter before checking.
"""
import json
import math
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from inresearch.workflow.product_catalog import COMPANIES

# 目录三项 + 账本，及它们的子页（爆炸图的 3D、芯片级镜头与规格库入口）。
INTERN_RESEARCH_PAGES = ('/', '/industry.html', '/projects.html', '/project.html', '/regions.html', '/market.html', '/index.html', '/node.html', '/ledger.html', '/bom.html', '/bom3d.html', '/rack3d.html', '/server-plan.html', '/campus-plan.html', '/facility-atlas.html', '/power-atlas.html', '/thermal-atlas.html', '/compute-atlas.html', '/control-atlas.html', '/cross-scale-atlas.html', '/network-atlas.html', '/storage-atlas.html', '/memory-atlas.html', '/rack-atlas.html', '/rack-exploded.html', '/chip-atlas.html',
                '/product-catalog.html', '/compute-catalog.html', '/report.html',
                '/research/data-centers-2026.html',
                '/research/data-centers-2026-us.html',
                '/research/data-centers-2026-sea.html',
                '/research/data-centers-2026-cn.html',
                '/research/data-centers-2026-projects.html')
# 这些页面读的登记与生成物。目标表的行不含来源 URL（来源登记在 part_fetch.json，不公开）。
INTERN_RESEARCH_DATA = ('/data/dashboard.json', '/data/dashboard_rules.json', '/data/tco_targets.json', '/data/tco_factors.json',
               '/data/datacenter_model.json', '/data/prices.json', '/data/companies.json',
               '/research/data-centers-2026-project-ledger.json', '/research/data-centers-2026-chart-data.json',
               '/framework/bom.json', '/framework/site_rights.json', '/framework/indicators.json', '/framework/modules.json',
               '/framework/tco_factors.json', '/framework/tco_targets.json')
# 只读接口。写接口、任务板、供应台账、用户管理不在内。规格库每家登记公司一条（GET 只读；POST 接收端仍要机器凭证）。
INTERN_RESEARCH_API = ('/api/industry', '/api/observations', '/api/whoami', '/api/report', '/api/news', '/api/company-window', '/api/company-quote', '/api/targets/backflow', '/api/model-assets',
              *('/api/product-catalog/' + company for company in COMPANIES))
# Login, homepage and task resources are individually declared, never all /assets/.
READER_PAGES = ('/', '/index.html', '/tasks.html', '/marketing.html')
READER_API = ('/api/whoami', '/api/research-tasks', '/api/research-task-examples')
READER_ASSETS = ('/assets/project-work.js', '/assets/project-access.css', '/assets/theme-state.js', '/assets/site-skin.js', '/assets/site-skin.css',
                 '/assets/brand/inresearch-ai/icon-orange.svg', '/assets/brand/inresearch-ai/wordmark-primary.svg',
                 '/assets/brand/inresearch-ai/wordmark-reverse.svg',
                 '/assets/auth-form.js', '/assets/auth.css', '/assets/industry.js',
                 '/assets/industry.css', '/assets/datacenter-news.js', '/assets/datacenter-news.css',
                 '/assets/world.geo.json', '/assets/world-detail.geo.json',
                 '/assets/research-tasks.js', '/assets/research-tasks.css',
                 '/assets/task-uploads.js', '/assets/task-uploads.css',
                 *('/assets/map-admin1-' + str(i) + '.geo.json' for i in range(12)))
READER_PREFIXES = ('/assets/fonts/', '/assets/marketing/')
READER_AUTH = ('/login',)
# A health probe discloses no runtime files or research content.
READER_PROBE = ('/healthz', '/robots.txt')
HOME_DATA_API = ('/api/industry', '/api/news')
CUSTOMER_WRITES = ('/api/login', '/api/passwd', '/api/feedback')
CUSTOMER_PROJECTED_API = ('/api/navigation', '/api/site-search',
                          '/api/whoami', '/api/observations', '/api/research-tasks',
                          '/api/research-task-examples', '/api/report')
# These endpoints already construct bounded product/publication views. Raw
# research/operational APIs deliberately have no customer entry here.
CUSTOMER_DELIVERY_API = ('/api/industry', '/api/news', '/api/company-window', '/api/company-quote',
                         *('/api/product-catalog/' + company for company in COMPANIES))
CUSTOMER_PROJECTED_DATA = ('/data/datacenter_model.json', '/data/tco_targets.json',
                           '/framework/tco_targets.json', '/data/prices.json', '/data/companies.json',
                           '/data/dashboard.json', '/research/data-centers-2026-project-ledger.json',
                           '/research/data-centers-2026-chart-data.json', '/framework/bom.json',
                           '/framework/site_rights.json', '/framework/indicators.json')
BOM_SYSTEMS = ('facility', 'power', 'thermal', 'it', 'compute', 'memory', 'storage',
               'network', 'control', 'storage-group')
BOM_INDICATORS = frozenset('''btm_operational_mw interconnection_queue_years region_pipeline_share
zoning_denial_count cowos_capacity_wpm gpu_lead_time rack_density_shipping ethernet_ai_share optics_800g_price
cdu_lead_time liquid_cooling_penetration gas_turbine_backlog_years genset_lead_time transformer_lead_time
construction_duration_months gpu_hourly_rate_spot gpu_rate_term_spread'''.split())
MODEL_PARAMETERS = frozenset('''it_mw redundancy construction_years horizon_years ramp_year1 ramp_year2 site
power_price demand_rate power_escalation land_per_mw labor_index property_tax_rate water_price cooling pue wue
it_class it_capex_per_kw load_factor it_refresh_years refresh_cost_factor gpus_per_mw gpu_utilization facility_mode
shell_rent_per_mw colo_rate capex_building capex_electrical capex_mechanical capex_fitout soft_cost_pct contingency_pct
fte_per_mw cost_per_fte maint_pct_facility maint_pct_it software_per_mw insurance_pct bandwidth_per_mw other_opex_per_mw
opex_escalation decommission_pct wacc business_model price_gpu_hour price_colo_kw_month accelerator_share shell_capex_per_mw
btm_capex_per_mw tax lease_term escalator noi_margin shell_ltc debt_rate residual_share chip_gross_margin compute_source
rent_price tokens_per_gpu_sec price_per_m_tokens monetized_share renewal_options renewal_years renewal_probability
price_change compute_ltc compute_debt_rate capex_basis energy_quota_mw tenancy util_year1 util_year2 price_path gate
gate_wait_years permit_months permit_timing it_depreciation_years compute_debt_years shell_debt_years loss_tax_shield bot_term_years bot_service_rate tenant_credit target_roic roic_basis'''.split())


def allowed(path, query=''):
    """Allow explicit GET/HEAD dependencies of the homepage, tasks and login.

    The query is checked separately from the normalized path: overview must be
    the only parameter and exactly 1, so company/detail/export queries stay private.
    """
    parsed = urlsplit(path)
    path = parsed.path
    query = query or parsed.query
    if path == '/api/navigation':
        return True
    if path in HOME_DATA_API:
        return parse_qs(query, keep_blank_values=True) == {'overview': ['1']}
    if path.startswith('/api/research-task-examples/'):
        import re
        return not query and bool(re.fullmatch(r'/api/research-task-examples/equinix-sg3-20261012/files/[A-Za-z0-9][A-Za-z0-9._-]{0,99}', path))
    if path in ('/api/research-tasks', '/api/research-task-examples') and query:
        return False
    return (path in READER_PAGES or path in READER_API or path in READER_ASSETS
            or path in READER_AUTH or path in READER_PROBE
            or any(path.startswith(prefix) for prefix in READER_PREFIXES))


def intern_research_allowed(path):
    """Retain the logged-in intern's existing read grants after closing public pages."""
    return path in INTERN_RESEARCH_PAGES or path in INTERN_RESEARCH_DATA or path in INTERN_RESEARCH_API


def customer_allowed(root, path, query='', method='GET'):
    """Deny by default; delivery resources are registered with the site directory.

    Existing public projections retain their field boundary. Internal research,
    operational APIs and arbitrary static files never inherit customer access.
    """
    if method not in ('GET', 'HEAD'):
        return method == 'POST' and path in CUSTOMER_WRITES
    params = parse_qs(query, keep_blank_values=True)
    if path == '/api/model-assets':
        return params in ({'page': ['bom3d']}, {'page': ['rack3d']})
    if path in ('/search.html', '/api/site-search') and params.get('scope', ['delivery']) != ['delivery']:
        return False
    if path in ('/product-catalog.html', '/company.html') and 'research' in params.get('view', []):
        return False
    if path in ('/report.html', '/api/report') and 'legacy' in params:
        return False
    if path in ('/api/research-tasks', '/api/research-task-examples') and params:
        return False
    if path.startswith('/api/research-task-examples/'):
        return allowed(path, query)
    if path in CUSTOMER_PROJECTED_API or path in CUSTOMER_DELIVERY_API or path in ('/account', '/login', '/logout', '/healthz', '/robots.txt'):
        return True
    if path in HOME_DATA_API:
        return allowed(path, query)
    try:
        access = json.loads((Path(root) / 'framework/site_navigation.json').read_text())['access']['customer']
    except (OSError, ValueError, TypeError, KeyError):
        return False
    if path in ('/workspace.html', '/api/workspace'):
        section = params.get('section', [])
        if section and (len(section) != 1 or section[0] not in access.get('sections', [])):
            return False
        if path == '/api/workspace':
            return bool(section)
    if path == '/guide.html' and params.get('view', ['help']) not in [[v] for v in
            ('method', 'sources', 'help', 'feedback', 'about', 'updates', 'privacy', 'terms')]:
        return False
    return (path in access.get('pages', []) or path in access.get('data', [])
            or any(path == asset or asset.endswith('/') and path.startswith(asset)
                   for asset in access.get('assets', [])))


def customer_model(spec):
    """Calculation inputs, scenarios and source status; no internal acquisition instructions."""
    def fields(row, keys):
        return {key: row[key] for key in keys if key in row and
                (row[key] is None or isinstance(row[key], (str, bool, int)) or
                 isinstance(row[key], float) and math.isfinite(row[key]))}
    def rows(name, keys):
        return [fields(row, keys) for row in spec.get(name, [])]
    out = fields(spec, ('schema_version', 'model_id', 'as_of', 'currency', 'status', 'summary', 'model_note'))
    out['evidence_note'] = '输入区分用户给定、已有来源、作者假设和待获取；地区缺项分别标明。来源状态不自动证明每个情景适用。'
    out['assumptions'] = fields(spec.get('assumptions', {}), MODEL_PARAMETERS)
    out['inputs'] = {}
    for key, row in spec.get('inputs', {}).items():
        if key not in MODEL_PARAMETERS:
            continue
        item = fields(row, ('display', 'label', 'max', 'min', 'note', 'options', 'step', 'type', 'unit'))
        if 'choices' in row:
            item['choices'] = [list(pair) for pair in row['choices']
                               if isinstance(pair, list) and len(pair) == 2 and all(isinstance(v, str) for v in pair)]
        out['inputs'][key] = item
    out['groups'] = [{**fields(row, ('id', 'label', 'hint', 'variable_class')),
                      'inputs': [key for key in _publication_strings(row.get('inputs', [])) if key in MODEL_PARAMETERS]}
                     for row in spec.get('groups', [])]
    for name in ('regions', 'coolings', 'it_classes', 'tenancies', 'price_paths', 'tenant_credits'):
        out[name] = {key: fields(row, MODEL_PARAMETERS | {'label', 'source', 'evidence_class'})
                     for key, row in spec.get(name, {}).items()}
        for key, row in spec.get(name, {}).items():
            if name == 'regions' and 'gaps' in row:
                out[name][key]['gaps'] = _publication_strings(row['gaps'])
            if name == 'it_classes' and isinstance(row.get('density_basis'), dict):
                basis = fields(row['density_basis'], ('rack_kw', 'units_per_rack', 'unit', 'rack_share_of_it_power',
                                                     'source', 'url', 'evidence_class'))
                if basis.get('url') and not _customer_public_url(basis['url']):
                    basis.pop('url')
                out[name][key]['density_basis'] = basis
    out['redundancy_factors'] = {key: fields(row, ('label', 'electrical', 'mechanical'))
                                for key, row in spec.get('redundancy_factors', {}).items()}
    out['density_rule'] = fields(spec.get('density_rule', {}), ('rack_share_of_it_power', 'text'))
    metrics = ('revenue_per_gw', 'nopat_per_gw', 'roic', 'required_revenue_per_gw',
               'ebit_margin', 'nopat_margin', 'annualised', 'unit_cost')
    out['presets'] = {key: {**fields(row, ('label', 'group', 'note')),
                           'changes': fields(row.get('changes', {}), MODEL_PARAMETERS),
                           **({'check': fields(row['check'], metrics)} if 'check' in row else {})}
                      for key, row in spec.get('presets', {}).items()}
    out['calibration'] = {key: fields(row, ('preset', 'source', *metrics))
                          for key, row in spec.get('calibration', {}).items()}
    out['grid'] = {key: [value for value in values if type(value) in (int, float) and math.isfinite(value)]
                   for key in ('capex_per_gw', 'price_factors', 'utilization')
                   if isinstance((values := spec.get('grid', {}).get(key)), list)}
    out['anchors'] = rows('anchors', ('capex_per_gw', 'label', 'price_factor', 'roic', 'utilization'))
    out['sensitivity_drivers'] = rows('sensitivity_drivers', ('delta', 'delta_abs', 'key', 'label'))
    out['benchmark_series'] = rows('benchmark_series', ('group', 'label', 'series_id'))
    out['evidence_legend'] = fields(spec.get('evidence_legend', {}), ('sourced', 'assumed', 'needed', 'input'))
    out['evidence'] = {key: fields(row, ('status', 'variable_class', 'note'))
                       for key, row in spec.get('evidence', {}).items() if key in MODEL_PARAMETERS}
    return out


def customer_targets(doc):
    """Public coverage shape, without assignments, machines, schedules or source receipts."""
    keys = ('version', 'updated', 'title', 'counts', 'statuses', 'variable_classes', 'data_classes')
    out = {key: doc[key] for key in keys if key in doc}
    row_keys = ('id', 'variable_class', 'origin', 'factor_id', 'factor_ids', 'part_id', 'site_right_id',
                'model_inputs', 'series', 'indicators', 'data_class', 'disclosure_type', 'status',
                'chain', 'chain_order', 'stage')
    out.update(targets=[{key: row[key] for key in row_keys if key in row} for row in doc.get('targets', [])],
               teams={}, mechanisms={})
    return out


def customer_prices(doc):
    keys = ('series_id', 'category', 'as_of', 'value', 'unit', 'region', 'assumptions',
            'grade', 'source_url', 'node', 'variable_class', 'frequency')
    return {'records': [{key: row[key] for key in keys if key in row and
                         (row[key] is None or isinstance(row[key], (str, bool, int)) or
                          isinstance(row[key], float) and math.isfinite(row[key]))}
                        for row in doc.get('records', []) if not row.get('sensitive')
                        and _customer_public_url(row.get('source_url'))]}


def _customer_public_url(value):
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        credentials = {'token', 'access_token', 'api_key', 'password', 'secret', 'authorization'}
        return (url.scheme in ('https', 'http') and bool(url.hostname) and not url.username and not url.password
                and not credentials.intersection(key.casefold() for key in parse_qs(url.query, keep_blank_values=True)))
    except ValueError:
        return False


def customer_companies(doc):
    keys = ('company_id', 'name', 'name_cn', 'ticker', 'cik', 'roles', 'hq_country', 'profile',
            'website', 'ir_url', 'entity_type', 'identity_scope', 'parent_company_id', 'registration_status',
            'legal_name', 'founded_year', 'hq_address', 'employees', 'employees_as_of', 'ceo',
            'profile_source', 'profile_as_of', 'verified_date')
    return {'records': [{**_publication_fields(row, keys), 'roles': _publication_strings(row.get('roles', []))}
                         for row in doc.get('records', [])]}


def _customer_cells(cells, company_ids):
    fields = _publication_fields
    result = {}
    for col in ('1', '2', '3', '4', '5'):
        if col not in cells:
            continue
        row = cells[col]
        item = fields(row, ('status',))
        item['items'] = [fields(value, ('label', 'value', 'unit', 'as_of', 'kind'))
                         for value in row.get('items', [])]
        item['coverage'] = fields(row.get('coverage', {}), ('sourced', 'assumed', 'delivered', 'needed'))
        if 'instances' in row:
            item['instances'] = _publication_strings(row['instances'])
        if isinstance(row.get('instance_ids'), list):
            item['instance_ids'] = [value if isinstance(value, str) and value in company_ids else None
                                     for value in row['instance_ids']]
        result[col] = item
    return result


def customer_dashboard(doc, root):
    """Node explanation: published categories, physical values and declared model inputs."""
    from inresearch.delivery.source_publication import companies
    fields = _publication_fields
    company_ids = {row['company_id'] for row in companies(root)['records']}
    bom = customer_bom(json.loads((Path(root) / 'framework/bom.json').read_text()))
    rights = customer_site_rights(json.loads((Path(root) / 'framework/site_rights.json').read_text()))
    part_ids = {row['id'] for row in bom['parts']}
    right_ids = {row['id'] for row in rights['rights']}
    cells = lambda value: _customer_cells(value, company_ids)
    out = fields(doc, ('version', 'updated', 'title'))
    out['stages'] = [fields(row, ('id', 'name', 'order', 'desc')) for row in doc.get('stages', [])]
    out['columns'] = fields(doc.get('columns', {}), ('1', '2', '3', '4', '5'))
    out['formulas'] = fields(doc.get('formulas', {}), ('revenue', 'cost', 'time'))
    out['systems'] = _customer_systems(doc.get('systems', {}))
    base = doc.get('root', {})
    out['root'] = {**fields(base, ('id', 'name')), 'cells': cells(base.get('cells', {}))}
    account = base.get('account', {})
    out['root']['account'] = fields(account, ('scenario',))
    out['root']['account']['rows'] = [{**fields(row, ('key', 'label', 'value', 'unit', 'note')),
        'evidence': fields(row.get('evidence', {}), ('inputs', 'sourced', 'assumed', 'input'))}
        for row in account.get('rows', []) if row.get('key') in ('cost_per_mw', 'revenue_per_mw', 'roic')]
    def readable(href):
        if not isinstance(href, str):
            return False
        url = urlsplit(href)
        return not url.scheme and not url.netloc and customer_allowed(root, '/' + url.path.lstrip('/'), url.query)
    out['root']['account']['readings'] = [fields(row, ('id', 'label', 'hint', 'href'))
                                         for row in account.get('readings', []) if readable(row.get('href'))]
    out['root']['account']['links'] = [[row[0], row[1]] for row in account.get('links', [])
        if isinstance(row, list) and len(row) == 2 and isinstance(row[0], str) and readable(row[1])]
    summary = ('id', 'name', 'kind', 'scale', 'chain', 'chain_order', 'stage', 'supply_status')
    for key in ('system_nodes', 'parent_systems'):
        out[key] = []
        for row in doc.get(key, []):
            if row.get('id') not in BOM_SYSTEMS:
                continue
            item = fields(row, ('id', 'node_id', 'name', 'parent', 'order'))
            item['chains'] = _publication_strings(row.get('chains', []))
            if 'children' in row:
                item['children'] = [ident for ident in _publication_strings(row['children']) if ident in BOM_SYSTEMS]
            item['parts'] = [fields(part, summary) for part in row.get('parts', []) if part.get('id') in part_ids]
            item['cells'] = cells(row.get('cells', {}))
            out[key].append(item)
    site = doc.get('site', {})
    out['site'] = {**fields(site, ('id', 'node_id', 'name')), 'cells': cells(site.get('cells', {})),
        'rights': [{**fields(row, ('id', 'name', 'stage', 'supply_status')),
                    'variable_classes': [v for v in row.get('variable_classes', []) if type(v) is int and 1 <= v <= 5]}
                   for row in site.get('rights', []) if row.get('id') in right_ids]}
    out['parts'] = {ident: {**fields(row, (*summary, 'system', 'desc')), 'cells': cells(row.get('cells', {}))}
                    for ident, row in doc.get('parts', {}).items() if ident in part_ids}
    out['rights'] = {ident: {**fields(row, ('id', 'name', 'scale', 'supply_status', 'desc')),
                             'variable_classes': [v for v in row.get('variable_classes', []) if type(v) is int and 1 <= v <= 5],
                             'cells': cells(row.get('cells', {}))}
                     for ident, row in doc.get('rights', {}).items() if ident in right_ids}
    out['factors'] = [{**fields(row, ('id', 'label', 'side', 'parent', 'unit', 'formula')),
                      'model_inputs': [ident for ident in _publication_strings(row.get('model_inputs', [])) if ident in MODEL_PARAMETERS],
                      'bom_parts': [ident for ident in _publication_strings(row.get('bom_parts', [])) if ident in part_ids],
                      'site_rights': [ident for ident in _publication_strings(row.get('site_rights', [])) if ident in right_ids]}
                     for row in doc.get('factors', [])]
    return out


def customer_news(doc):
    feed = doc.get('feed')
    if not isinstance(feed, dict):
        return {'schema_version': 1, 'feed': None}
    keys = ('title_zh', 'title', 'url', 'domain', 'published_at', 'editorial_pick', 'event_type', 'object_ids')
    projection = _publication_fields(feed, ('status', 'exported_at'))
    projection['items'] = []
    for row in feed.get('items', []):
        item = _publication_fields(row, keys)
        if 'object_ids' in row:
            item['object_ids'] = _publication_strings(row['object_ids'])
        projection['items'].append(item)
    return {'schema_version': 1, 'feed': projection}


def _publication_fields(row, keys):
    """Fixed scalar leaves: new nested objects cannot become published metadata."""
    return {key: row[key] for key in keys if key in row and
            (row[key] is None or isinstance(row[key], (str, int, float, bool)))}


def _publication_strings(values):
    return [value for value in values if isinstance(value, str)] if isinstance(values, list) else []


def _customer_systems(systems):
    result = {}
    for ident in BOM_SYSTEMS:
        if ident not in systems:
            continue
        row = systems[ident]
        item = _publication_fields(row, ('name', 'parent', 'order'))
        item['chains'] = _publication_strings(row.get('chains', []))
        if ident == 'compute':
            item['processor_groups'] = [{**_publication_fields(group, ('id', 'name')),
                                         'parts': _publication_strings(group.get('parts', []))}
                                        for group in row.get('processor_groups', [])]
            item['support_parts'] = _publication_strings(row.get('support_parts', []))
        result[ident] = item
    return result


def customer_bom(doc):
    """Published classification and category descriptions, without construction/audit history."""
    out = _publication_fields(doc, ('version', 'updated'))
    out['kinds'] = _publication_fields(doc.get('kinds', {}), ('part', 'software', 'archetype'))
    out['systems'] = _customer_systems(doc.get('systems', {}))
    out['scales'] = [_publication_fields(row, ('id', 'name', 'en', 'desc')) for row in doc.get('scales', [])]
    out['stages'] = [_publication_fields(row, ('id', 'name', 'order', 'desc')) for row in doc.get('stages', [])]
    keys = ('id', 'name', 'kind', 'system', 'scale', 'chain', 'chain_order', 'stage', 'status', 'desc')
    out['parts'] = [{**_publication_fields(row, keys),
        **{key: _publication_strings(row.get(key, [])) for key in ('companies', 'series', 'indicators', 'upstream')}}
        for row in doc.get('parts', [])]
    ids = {row['id'] for row in out['parts'] if 'id' in row}
    rights = {'site:land', 'site:water-rights', 'site:grid', 'site:gas-supply', 'site:network-access', 'site:permits'}
    out['aliases'] = {key: value for key, value in doc.get('aliases', {}).items()
                      if isinstance(value, str) and value in ids | rights}
    return out


def customer_site_rights(doc):
    out = _publication_fields(doc, ('version', 'updated'))
    keys = ('id', 'name', 'desc', 'scale', 'stage', 'status')
    out['rights'] = [{**_publication_fields(row, keys),
        'variable_classes': [v for v in row.get('variable_classes', []) if type(v) is int and 1 <= v <= 5],
        **{key: _publication_strings(row.get(key, [])) for key in ('companies', 'series', 'indicators')}}
        for row in doc.get('rights', [])]
    return out


def customer_indicators(doc):
    out = _publication_fields(doc, ('version', 'updated'))
    out['note'] = '类别指标按原记录时点展示；空值表示未披露或待核实。来源归因不自动取得事实核实或研究采用资格。'
    out['indicators'] = [_publication_fields(row, ('id', 'name', 'value', 'unit', 'as_of', 'source'))
                         for row in doc.get('indicators', [])
                         if row.get('id') in BOM_INDICATORS and not row.get('sensitive')]
    return out


def customer_project_ledger(doc):
    """The fixed 2026 published table, not formal registry or reading receipts."""
    if doc.get('schema') != 'source-reported-project-ledger-v1':
        raise ValueError('Unrecognized published project ledger')
    out = _publication_fields(doc, ('schema', 'publication_date', 'scope',
                                    'formal_database_ingested', 'aggregation_allowed'))
    if out.get('formal_database_ingested') is not False or out.get('aggregation_allowed') is not False:
        raise ValueError('Published project ledger boundary changed')
    keys = ('id', 'name', 'region', 'country_code', 'country_label', 'public_location',
            'stage_and_date', 'boundary', 'evidence_date_text')
    out['records'] = []
    for row in doc.get('records', []):
        item = _publication_fields(row, keys)
        item['roles'] = _publication_fields(row.get('roles', {}),
                                            ('developer_or_builder', 'operator', 'disclosed_user'))
        item['capacity'] = _publication_fields(row.get('capacity', {}), ('quoted_text',))
        item['sources'] = [url for url in row.get('sources', []) if isinstance(url, str)
                           and urlsplit(url).scheme in ('http', 'https') and urlsplit(url).hostname
                           and not urlsplit(url).username and not urlsplit(url).password]
        out['records'].append(item)
    return out


def customer_chart_data(doc):
    """Fixed report figures; units, periods and interpretation boundaries travel with values."""
    fields = _publication_fields
    out = fields(doc, ('cutoff',))
    global_model = doc.get('global_installed_model', {})
    out['global_installed_model'] = fields(global_model, ('source', 'year', 'unit'))
    out['global_installed_model']['global'] = fields(global_model.get('global', {}), ('it', 'facility_total'))
    out['global_installed_model']['regions'] = [fields(row, ('name', 'it', 'facility_total', 'derived'))
                                               for row in global_model.get('regions', [])]
    pipeline = doc.get('cw_h1_2026_pipeline', {})
    out['cw_h1_2026_pipeline'] = fields(pipeline, ('unit', 'scope', 'capacity_angle'))
    out['cw_h1_2026_pipeline']['rows'] = [fields(row, ('region', 'operational', 'operational_lower_bound',
                                                        'construction', 'planned'))
                                         for row in pipeline.get('rows', [])]
    out['cw_h1_2026_pipeline']['aggregate_rounded'] = fields(pipeline.get('aggregate_rounded', {}),
        ('operational_approx', 'construction_approx', 'planned_approx'))
    sea = doc.get('sea_six_markets', {})
    out['sea_six_markets'] = fields(sea, ('source', 'unit', 'scope', 'capacity_angle'))
    out['sea_six_markets']['rows'] = [fields(row, ('country', 'operational', 'construction', 'planned'))
                                    for row in sea.get('rows', [])]
    out['sea_six_markets']['total'] = fields(sea.get('total', {}), ('operational', 'construction', 'planned'))
    out['project_record_counts'] = fields(doc.get('project_record_counts', {}),
        ('us', 'southeast_asia', 'china_mainland', 'hong_kong', 'total', 'note'))
    return out


def customer_report(report, root):
    """Calculation and classification snapshot, with every nested delivery field declared."""
    if report.get('schema_version') != 2 or report.get('kind') != 'datacenter_snapshot':
        raise ValueError('Unrecognized delivery snapshot')
    fields = _publication_fields
    ids = ('q1', 'q2', 'q3', 'q4')
    chapters = {}
    for row in report.get('chapters', []):
        if row.get('id') in ids:
            if row['id'] in chapters:
                raise ValueError('Duplicate snapshot chapter')
            chapters[row['id']] = row
    if set(chapters) != set(ids):
        raise ValueError('Incomplete delivery snapshot')
    columns = ('1', '2', '3', '4', '5')
    def strings(values):
        return [value for value in values if isinstance(value, str)]
    def chapter(ident):
        return fields(chapters[ident], ('id', 'title'))
    result = fields(report, ('schema_version', 'kind', 'title', 'as_of', 'data_revision', 'acceptance'))
    boundary = report.get('boundary', {})
    result['boundary'] = fields(boundary, ('scenario',))
    result['boundary']['model_inputs'] = fields(boundary.get('model_inputs', {}), ('sourced', 'assumed', 'input', 'total'))
    result['boundary']['registries'] = fields(boundary.get('registries', {}), ('dashboard', 'bom', 'model'))
    q1 = chapter('q1')
    q1['account'] = []
    for row in chapters['q1'].get('account', []):
        if row.get('key') not in ('cost_per_mw', 'revenue_per_mw', 'roic'):
            continue
        item = fields(row, ('key', 'label', 'value', 'unit', 'note'))
        item['evidence'] = fields(row.get('evidence', {}), ('inputs', 'sourced', 'assumed', 'input'))
        q1['account'].append(item)
    q1['columns'] = {}
    for col in columns:
        row = chapters['q1'].get('columns', {}).get(col, {})
        q1['columns'][col] = {**fields(row, ('name', 'status')),
            'items': [fields(item, ('label', 'value', 'unit', 'as_of')) for item in row.get('items', [])]}
    source_labels = {'ms': '摩根士丹利 2026-09《AI 指南》p22–27',
                     'gs': '高盛 2026-09-24《Sizing the AI Economy》Exhibit 7',
                     'ours_2026_09_14': '本站历史成本基准（2026-09-14）'}
    metrics = ('revenue_per_gw', 'nopat_per_gw', 'roic', 'required_revenue_per_gw',
               'ebit_margin', 'nopat_margin', 'annualised', 'unit_cost')
    q1['calibration'] = [{**fields(row, ('id', 'preset', 'label')), 'source': source_labels[row['id']],
                          'anchors': fields(row.get('anchors', {}), metrics)}
                         for row in chapters['q1'].get('calibration', []) if row.get('id') in source_labels]
    q1['readings'] = []
    for row in chapters['q1'].get('readings', []):
        href = row.get('href')
        if not isinstance(href, str):
            continue
        url = urlsplit(href)
        path = '/' + url.path.lstrip('/')
        if not url.scheme and not url.netloc and customer_allowed(root, path, url.query):
            q1['readings'].append({**fields(row, ('id', 'label', 'hint')), 'href': href})
    q2 = chapter('q2')
    q2['systems'] = [{**fields(row, ('id', 'name', 'parent', 'parts')),
        'chains': strings(row.get('chains', [])), 'cells': fields(row.get('cells', {}), columns)}
        for row in chapters['q2'].get('systems', [])]
    q2['parent_systems'] = [{**fields(row, ('id', 'name')), 'children': strings(row.get('children', [])),
        'cells': fields(row.get('cells', {}), columns)} for row in chapters['q2'].get('parent_systems', [])]
    site = chapters['q2'].get('site', {})
    q2['site'] = {'cells': fields(site.get('cells', {}), columns), 'rights': []}
    for row in site.get('rights', []):
        q2['site']['rights'].append({**fields(row, ('id', 'name', 'stage')),
            'variable_classes': [v for v in row.get('variable_classes', []) if type(v) is int and 1 <= v <= 5],
            'cells': fields(row.get('cells', {}), ('3', '4', '5'))})
    q2['stages'] = [{**fields(row, ('id', 'name', 'order')), 'parts': strings(row.get('parts', [])),
                     'rights': strings(row.get('rights', []))} for row in chapters['q2'].get('stages', [])]
    q2['counts'] = fields(chapters['q2'].get('counts', {}), ('parts', 'software', 'archetype', 'rights', 'chains'))
    q3 = chapter('q3')
    q3['formulas'] = fields(chapters['q3'].get('formulas', {}), ('revenue', 'cost', 'time'))
    q3['factors'] = [fields(row, ('id', 'label', 'side', 'parent', 'unit', 'formula',
                                 'model_inputs', 'bom_parts', 'site_rights'))
                     for row in chapters['q3'].get('factors', [])]
    q4 = chapter('q4')
    result['chapters'] = [q1, q2, q3, q4]
    return result


def public_model(spec):
    """账本的实习生受限视图：只留基准预设与校准锚引用的预设，地区表只留这些预设用到的地区。

    其余键原样保留——输入、证据、口径与公式是模型的可信边界，保留在受限视图；地区预设与情景预设
    是我们的研究工作，member 以上才有。"""
    presets = spec.get('presets') or {}
    keep = {'baseline'} | {c.get('preset') for c in (spec.get('calibration') or {}).values() if c.get('preset') in presets}
    kept = {k: v for k, v in presets.items() if k in keep}
    sites = {spec.get('assumptions', {}).get('site')} | {(p.get('changes') or {}).get('site') for p in kept.values()}
    regions = {k: v for k, v in (spec.get('regions') or {}).items() if k in sites}
    return {**spec, 'presets': kept, 'regions': regions, 'public_view': 'reader'}
