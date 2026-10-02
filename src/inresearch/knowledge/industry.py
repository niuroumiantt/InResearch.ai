"""Public industry views. One capacity calculation for maps, cards and drilldowns."""
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

STAGES = {'operating': '已投运', 'construction': '建设中', 'planning': '筹备机会'}
LEVELS = dict(zip(['L'+str(i) for i in range(1, 10)],
                  ['新闻线索', '官宣', '土地', '电力申请', '电力确定', '开工', '机电施工', '通电', '满载']))
REGIONS = {'north-america': '北美', 'europe': '欧洲', 'china': '中国', 'apac': '亚太', 'mena': '中东与北非', 'latam': '拉美', 'africa': '非洲', 'india': '印度'}
ROLE_GROUPS = {'demand': {'hyperscaler', 'ai-lab', 'neocloud', 'sovereign'},
               'operator': {'colo'}, 'capital': {'capital'}, 'energy': {'utility'},
               'supplier': {'chip', 'storage', 'network', 'cooling', 'electrical', 'server-odm', 'facility', 'construction'}}


def public_url(value):
    if not isinstance(value, str): return None
    try:
        u = urlsplit(value)
        if u.scheme in ('https', 'http') and u.hostname and not u.username and not u.password:
            return value
    except ValueError:
        pass
    return None


def number(value):
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


def bucket(level):
    if level not in LEVELS: return None
    return 'operating' if int(level[1:]) >= 8 else 'construction' if int(level[1:]) >= 6 else 'planning'


def project(row):
    result = {k: row.get(k) for k in ('site_id', 'name', 'country', 'region', 'location', 'developer', 'tenant',
              'status', 'verified_date', 'type', 'disputed', 'notes', 'power_status', 'utility', 'capacity_facility_mw')}
    result['developer'] = row.get('developer') or []
    result['tenant'] = row.get('tenant') or []
    result['portfolio'] = 'portfolio' in row['site_id']
    result['stage_label'] = LEVELS.get(row.get('status'), '阶段待核实')
    parts = row.get('capacity_it_mw_by_status') or {}
    # Breakdown is authoritative when supplied; never add a headline total twice.
    parts = {k: v for k, v in parts.items() if bucket(k) and number(v)}
    if not parts and bucket(row.get('status')) and number(row.get('capacity_it_mw')):
        parts = {row['status']: row['capacity_it_mw']}
    result['phases'] = [{'level': k, 'label': LEVELS[k], 'stage': bucket(k), 'mw': v} for k, v in parts.items()]
    result['capacity'] = {s: sum(p['mw'] for p in result['phases'] if p['stage'] == s) for s in STAGES}
    result['capacity_known'] = bool(parts)
    result['total_mw'] = sum(result['capacity'].values())
    result['coordinates'] = None
    try:
        lat, lon = [float(x) for x in row.get('coordinates', '').split(',')]
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            result['coordinates'] = [lat, lon]
    except (AttributeError, ValueError, TypeError):
        pass
    result['sources'] = [{k: s.get(k) for k in ('url', 'grade', 'date', 'note')} for s in row.get('sources', []) if public_url(s.get('url'))]
    result['history'] = [{k: h.get(k) for k in ('status', 'date', 'source_url')} for h in row.get('status_history', []) if public_url(h.get('source_url'))]
    # This is an explicit type filter, not a claim that all cloud projects are AI.
    result['ai_tagged'] = row.get('type') in ('ai-lab-selfbuild', 'aidc-cn', 'neocloud')
    return result


def totals(rows):
    sites = [p for p in rows if not p['portfolio']]
    return {**{s: round(sum(p['capacity'][s] for p in sites), 6) for s in STAGES},
            'sites': len(sites), 'unknown': sum(not p['capacity_known'] for p in sites),
            'unlocated': sum(p['coordinates'] is None for p in sites),
            'portfolios_excluded': sum(p['portfolio'] for p in rows)}


def market(root):
    rows = json.loads((Path(root)/'data/prices.json').read_text())['records']
    series = []
    for r in rows:
        if r.get('series_id') != 'delloro-capex-total' or r.get('unit') != '$B' or not number(r.get('value')): continue
        series.append({'year': r['as_of'][:4], 'value': r['value'], 'unit': '$B',
                       'forecast': '预测' in r.get('assumptions', ''),
                       'source_url': public_url(r.get('source_url')),
                       'source': 'Dell’Oro · Data Center IT Capex Forecast · 2026-07',
                       'assumptions': r.get('assumptions', ''),
                       'availability': 'external' if public_url(r.get('source_url')) else 'internal_reference'})
    return {'title': '全球数据中心 IT 资本开支', 'scope': '年度 IT 投资；不等于设施建设总投资或运营服务收入。',
            'series': sorted(series, key=lambda r: r['year']),
            'revenue_available': False, 'forecast_note': '2026 年起为机构预测，非已实现收入；原报告为内部登记引用。'}


def benchmarks(root):
    """Explicitly selected, comparable report estimates; never called live operating GW."""
    ids = ('hsbc2026-global-it-load-2025', 'hsbc2026-global-it-load-2030e')
    path = Path(root)/'data/facts.json'
    records = json.loads(path.read_text())['records'] if path.exists() else []
    return [{k: r.get(k) for k in ('fact_id', 'value', 'unit', 'as_of', 'asserter', 'caliber', 'corroboration')} |
            {'source': r.get('evidence', {}).get('originator'), 'locator': r.get('evidence', {}).get('locator')}
            for ident in ids for r in records if r.get('fact_id') == ident]


def snapshot(root, params=None):
    root = Path(root); params = params or {}
    if set(params) - {'c', 'region', 'stage', 'relation', 'scope', 'role', 'site'}: raise ValueError('unknown filter')
    for k, allowed in {'stage': {'', *STAGES, 'unknown'}, 'relation': {'', 'developer', 'tenant'},
                       'scope': {'', 'ai'}, 'role': {'', *ROLE_GROUPS}}.items():
        if params.get(k, '') not in allowed: raise ValueError('invalid '+k)
    companies = [{k: c.get(k) for k in ('company_id', 'name', 'name_cn', 'roles')} for c in json.loads((root/'data/companies.json').read_text())['records']]
    by_id = {c['company_id']: c for c in companies}
    if params.get('c') and params['c'] not in by_id: raise LookupError('company not found')
    all_rows = [project(p) for p in json.loads((root/'data/projects.json').read_text())['records']]
    if params.get('region') and params['region'] not in {p['region'] for p in all_rows}: raise ValueError('invalid region')
    def matches(p):
        relations = [params['relation']] if params.get('relation') else ['developer', 'tenant']
        ids = {i for relation in relations for i in p[relation]}
        return ((not params.get('c') or params['c'] in ids)
                and (not params.get('region') or p['region'] == params['region'])
                and (not params.get('scope') or p['ai_tagged'])
                and (not params.get('role') or any(set(by_id.get(i, {}).get('roles') or []) & ROLE_GROUPS[params['role']] for i in ids)))
    cohort = [p for p in all_rows if matches(p)]
    stage = params.get('stage')
    rows = [p for p in cohort if not stage or (not p['capacity_known'] if stage == 'unknown'
            else p['capacity'][stage] > 0 or not p['capacity_known'] and bucket(p['status']) == stage)]
    detail = next((p for p in all_rows if p['site_id'] == params.get('site')), None)
    if params.get('site') and detail is None: raise LookupError('project not found')
    leaders = []
    for c in companies:
        related = [p for p in cohort if c['company_id'] in p['developer'] + p['tenant'] and not p['portfolio']]
        if related: leaders.append({**c, 'totals': totals(related)})
    leaders.sort(key=lambda c: (-sum(c['totals'][s] for s in STAGES), c['company_id']))
    regional = [{'id': r, 'name': REGIONS.get(r, r), 'totals': totals([p for p in cohort if p['region'] == r])} for r in sorted({p['region'] for p in cohort})]
    dates = sorted(p['verified_date'] for p in cohort if p.get('verified_date'))
    return {'schema_version': 1, 'generated_at': date.today().isoformat(), 'filters': params,
            'coverage': {'label': '已追踪项目 · 非全球普查', 'oldest_verified': dates[0] if dates else None,
                         'latest_verified': dates[-1] if dates else None},
            'totals': totals(cohort), 'rows': rows, 'detail': detail, 'companies': companies,
            'leaders': leaders, 'regions': [{'id': r, 'name': REGIONS.get(r, r)} for r in sorted({p['region'] for p in all_rows})],
            'regional': regional, 'market': market(root), 'benchmarks': benchmarks(root),
            'stages': STAGES, 'company': by_id.get(params.get('c')),
            'basis': '仅汇总已披露 IT 负载 MW；公司视图为相关园区容量，并非持有或租用份额。组合记录不参加容量合计。'}
