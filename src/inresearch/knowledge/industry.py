"""Public industry views. One capacity calculation for maps, cards and drilldowns."""
import json
import copy
from functools import lru_cache
import math
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from inresearch.knowledge import site_timeline, site_quantity, site_register, observation_time
from inresearch.knowledge.object_observations import public_updates

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


def capacity_scalar(value):
    # Legacy invalid values stay unknown; reviewed observations validate upstream.
    try:
        return site_quantity.scalar_mw(value)
    except (ValueError, TypeError):
        return None


def bucket(level):
    if level not in LEVELS: return None
    return 'operating' if int(level[1:]) >= 8 else 'construction' if int(level[1:]) >= 6 else 'planning'


def project(row):
    original = row
    row = site_timeline.current(row)
    result = {k: row.get(k) for k in ('site_id', 'name', 'country', 'region', 'location', 'developer', 'tenant',
              'status', 'verified_date', 'duplicate_of', 'deduplication_note', 'type', 'disputed', 'notes', 'power_status', 'utility', 'capacity_facility_mw')}
    result['registration_status'] = 'unverified' if any(v.get('registration_status') == 'unverified' for v in row['tracking']['fields'].values()) else 'reviewed'
    result['tracking'] = row['tracking']
    result['geography'] = site_register.geography(row)
    result['participants'] = site_register.participants(row)
    result['capacity_register'] = site_register.capacities(row)
    from . import site_metrics
    result['resource_metrics'] = {key: copy.deepcopy(row['quantity_fields'][key])
                                  for key in site_metrics.FIELDS if key in row.get('quantity_fields', {})}
    result['observations'] = site_timeline.public_timeline(original)
    result['lifecycle'] = row.get('lifecycle', 'active')
    result['relationships'] = {k: row.get(k, []) for k in ('owner', 'operator', 'builder')}
    # Public project receipt: reviewed scope and quoted claims, never private paths.
    receipts = site_timeline.adoptions(row)
    if receipts:
        a = max(receipts, key=lambda r:(r.get('review') or {}).get('at',''))
        result['adoption'] = {k:a.get(k) for k in ('event_id','fields','scope','target_ids')}
        result['adoption']['assertions'] = [{k:x.get(k) for k in ('quote','url','basis','phase','value','unit','scope')}
                                           for x in a.get('assertions', [])]
    result['developer'] = row.get('developer') or []
    result['tenant'] = row.get('tenant') or []
    result['portfolio'] = 'portfolio' in row['site_id']
    result['stage_label'] = LEVELS.get(row.get('status'), '阶段待核实')
    inactive_label = {'paused':'暂停', 'cancelled':'取消', 'closed':'关闭'}.get(result['lifecycle'])
    if inactive_label:
        result['stage_label'] += ' · ' + inactive_label + '（不计活跃容量）'
    quantities = copy.deepcopy(row.get('quantity_fields') or {})
    result['quantity_fields'] = quantities
    native_parts = quantities.get('capacity_it_mw_by_status') or row.get('capacity_it_mw_by_status') or {}
    # Exact phases and source intervals remain separate; a range has no midpoint.
    parts = {k: capacity_scalar(v) for k, v in native_parts.items()
             if bucket(k) and capacity_scalar(v) is not None}
    headline = quantities.get('capacity_it_mw', row.get('capacity_it_mw'))
    if not native_parts and bucket(row.get('status')) and capacity_scalar(headline) is not None:
        parts = {row['status']: capacity_scalar(headline)}
    ranges = []
    candidates = [('capacity_it_mw_by_status', k, v) for k, v in native_parts.items() if bucket(k)]
    if not native_parts:
        candidates.append(('capacity_it_mw', row.get('status'), headline))
    for field, level, value in candidates:
        if isinstance(value, dict) and 'value_range' in value:
            ranges.append({'field': field, 'level': level, 'stage': bucket(level), **copy.deepcopy(value)})
    result['capacity_ranges'] = ranges
    result['capacity_ranged'] = bool(ranges)
    result['phases'] = [{'level': k, 'label': LEVELS[k], 'stage': bucket(k), 'mw': v} for k, v in parts.items()]
    result['capacity'] = {s: sum(p['mw'] for p in result['phases'] if p['stage'] == s) for s in STAGES}
    result['capacity_known'] = bool(parts)
    assessment = row.get('capacity_assessment') or {}
    result['capacity_assessment'] = {k: assessment.get(k) for k in
        ('kind', 'status', 'as_of', 'recorded_at', 'reviewed_at', 'basis_note', 'assumptions', 'missing_conditions')}
    result['capacity_estimated'] = assessment.get('kind') in ('estimate', 'legacy_estimate')
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
    sites = [p for p in rows if not p['portfolio'] and not p.get('duplicate_of')]
    active = [p for p in sites if p.get('lifecycle', 'active') == 'active']
    return {**{s: round(sum(p['capacity'][s] for p in active), 6) for s in STAGES},
            'inactive_sites': len(sites)-len(active),
            'estimated': {s: round(sum(p['capacity'][s] for p in active if p['capacity_estimated']), 6) for s in STAGES},
            'estimated_sites': sum(p['capacity_estimated'] for p in sites),
            'sites': len(sites), 'unknown': sum(not p['capacity_known'] and not p.get('capacity_ranged') for p in sites),
            'ranged_sites': sum(bool(p.get('capacity_ranged')) for p in sites),
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


@lru_cache(maxsize=8)
def _selected_benchmarks(path, signature):
    records=json.loads(Path(path).read_text())['records']
    ids=('hsbc2026-global-it-load-2025','hsbc2026-global-it-load-2030e')
    return [{k:r.get(k) for k in ('fact_id','value','unit','as_of','asserter','caliber','corroboration')} |
            {'source':r.get('evidence',{}).get('originator'),'locator':r.get('evidence',{}).get('locator')}
            for ident in ids for r in records if r.get('fact_id')==ident]


def benchmarks(root):
    """Explicitly selected, comparable report estimates; never called live operating GW."""
    path=Path(root)/'data/facts.json'
    if not path.exists(): return []
    stat=path.stat()
    return copy.deepcopy(_selected_benchmarks(str(path),(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)))


def capacity_audit(rows, records):
    """Global comparison uses the full registry, independently of UI filters."""
    count = totals(rows)
    dates = sorted(p['verified_date'] for p in rows if not p['portfolio'] and p.get('verified_date'))
    return {**count, 'known': count['sites'] - count['unknown'],
            'duplicates_excluded': sum(bool(p.get('duplicate_of')) for p in records),
            'oldest_verified': dates[0] if dates else None, 'latest_verified': dates[-1] if dates else None,
            'comparability': '两个集合不是同年、同定义、同覆盖范围。不能用 95 GW 减样本容量推算未追踪容量，也不能据此计算覆盖率；不编造差额。',
            'definition': '95 GW 原文称 IT 工作量，登记为全部负载的 IT 负载，非 AI 专属、设施总功率或当下已投运普查。报告底层统计边界与去重方法尚未取得。样本含已标记参考估算，estimated 分列其份额，不是全部已实测；按登记 IT MW 与分期汇总：L8–9 投运、L6–7 建设、L1–5 筹备；不叠加总值、设施 MW 或新闻容量。',
            'deduplication': '按已审阅物理身份归一；Frontier 两个 ID 引用同一官方 1.4 GW 公告，保留原记录，合计只取主记录分期。多主体关系不重加全球容量，公司卡不能相加。仅同坐标或同城市不自动合并。',
            'coverage': '样本偏向已登记大型园区与云厂商，含跨园区集群，不能称全球唯一物理园区普查；未知容量不是零，未定位记录仍可计入样本。',
            'unresolved': '既有 IT 字段未全部重新核实铭牌/实际负载定义或当前运营状态，95 GW 仍待交叉验证。阿布扎比既有 4 GW 是 5 GW 园区减单列 1 GW 子项目的推导余额，并非独立披露或已投运容量；仍需核实 IT/设施定义与分期。集群边界及全部潜在重叠未完成逐址核验。'}


def snapshot(root, params=None):
    root = Path(root); params = params or {}
    if set(params) - {'c', 'region', 'stage', 'relation', 'scope', 'role', 'site', 'overview', 'country', 'province', 'address'}: raise ValueError('unknown filter')
    if params.get('overview','') not in ('','0','1'): raise ValueError('invalid overview')
    overview=params.get('overview')=='1'
    params={k:v for k,v in params.items() if k!='overview'}
    for k, allowed in {'stage': {'', *STAGES, 'unknown'}, 'relation': {'', 'developer', 'tenant'},
                       'scope': {'', 'ai'}, 'role': {'', *ROLE_GROUPS}}.items():
        if params.get(k, '') not in allowed: raise ValueError('invalid '+k)
    companies = [{k: c.get(k) for k in ('company_id', 'name', 'name_cn', 'roles', 'profile')} for c in json.loads((root/'data/companies.json').read_text())['records']]
    by_id = {c['company_id']: c for c in companies}
    if params.get('c') and params['c'] not in by_id: raise LookupError('company not found')
    raw_rows = json.loads((root/'data/projects.json').read_text())['records']
    all_records = [project(p) for p in raw_rows]
    all_rows = [p for p in all_records if not p.get('duplicate_of')]
    # Identity joins retain relationships and evidence, never add duplicate capacity or overwrite stages.
    for p in all_rows:
        aliases = [a for a in all_records if a.get('duplicate_of') == p['site_id']]
        for key in ('developer', 'tenant'):
            if key not in p['tracking']['fields']:
                p[key] = list(dict.fromkeys(p[key] + [i for a in aliases for i in a[key]]))
        p['duplicate_records'] = [{'site_id': a['site_id'], 'note': a['deduplication_note']} for a in aliases]
        for a in aliases:
            for source in a['sources']:
                if source not in p['sources']: p['sources'].append(source)
    if params.get('region') and params['region'] not in {p['region'] for p in all_rows}: raise ValueError('invalid region')
    def matches(p):
        relations = [params['relation']] if params.get('relation') else ['developer', 'tenant']
        ids = {i for relation in relations for i in p[relation]}
        return ((not params.get('c') or params['c'] in ids)
                and (not params.get('region') or p['region'] == params['region'])
                and (not params.get('country') or p['country'] == params['country'])
                and (not params.get('province') or p['geography']['province'] == params['province'])
                and (not params.get('address') or p['geography']['regional_address'] == params['address'])
                and (not params.get('scope') or p['ai_tagged'])
                and (not params.get('role') or any(set(by_id.get(i, {}).get('roles') or []) & ROLE_GROUPS[params['role']] for i in ids)))
    cohort = [p for p in all_rows if matches(p)]
    stage = params.get('stage')
    rows = [p for p in cohort if not stage or (not p['capacity_known'] and not p['capacity_ranged'] if stage == 'unknown'
            else p['capacity'][stage] > 0 or any(r['stage'] == stage for r in p['capacity_ranges'])
            or not p['capacity_known'] and not p['capacity_ranged'] and bucket(p['status']) == stage)]
    detail = next((p for p in all_records if p['site_id'] == params.get('site')), None)
    if params.get('site') and detail is None: raise LookupError('project not found')
    leaders = []
    for c in companies:
        related = [p for p in cohort if c['company_id'] in p['developer'] + p['tenant'] and not p['portfolio']]
        if related: leaders.append({**c, 'totals': totals(related)})
    leaders.sort(key=lambda c: (-sum(c['totals'][s] for s in STAGES), c['company_id']))
    regional = [{'id': r, 'name': REGIONS.get(r, r), 'totals': totals([p for p in cohort if p['region'] == r])} for r in sorted({p['region'] for p in cohort})]
    dates = sorted(p['verified_date'] for p in cohort if p.get('verified_date'))
    changes = [{'site_id': p['site_id'], 'name': p['name'], **observation}
               for p in cohort if not p['portfolio'] for observation in p['observations']]
    # A newly recovered historical observation is a new reader update, not a
    # newly occurring event. Keep its effective time visible and unchanged.
    changes.sort(key=lambda r: (observation_time.bounds(r['recorded_at'])[0],
                               r['effective_at'] or '', r['id']), reverse=True)
    tracking = {'observations': sum(p['tracking']['observations'] for p in cohort),
                'sites_with_timeline': sum(bool(p['observations']) for p in cohort),
                'conflicting_sites': sum(bool(p['tracking']['conflicts']) for p in cohort),
                'review_overdue_sites': sum(bool(p['tracking']['review_due_fields']) for p in cohort),
                'changes': changes[:20], 'changes_truncated': len(changes)>20}
    audit=capacity_audit(all_rows,all_records)
    geographic_filters = {} if overview else {
        'countries': sorted({p['country'] for p in all_rows if p['country']}),
        'provinces': sorted({p['geography']['province'] for p in all_rows
                            if p['geography']['province'] and (not params.get('country') or p['country'] == params['country'])}),
        'addresses': sorted({p['geography']['regional_address'] for p in all_rows
                            if p['geography']['regional_address']
                            and (not params.get('country') or p['country'] == params['country'])
                            and (not params.get('province') or p['geography']['province'] == params['province'])})}
    if overview:
        row_keys=('site_id','name','country','region','location','developer','tenant','status','stage_label',
                  'verified_date','portfolio','duplicate_of','adoption','ai_tagged','lifecycle','capacity','capacity_known','capacity_ranged','capacity_ranges','quantity_fields','capacity_estimated','capacity_assessment','total_mw','coordinates')
        rows=[{key:row[key] for key in row_keys if key in row} | {
               'verification_status':'adopted_fields' if row.get('adoption') else 'registered'} for row in rows]
        for row in rows:
            if row.get('adoption'): row['adoption']={key:row['adoption'].get(key) for key in ('event_id','fields','scope')}
            # Match the upstream public assessment allowlist, with bounded homepage prose.
            assessment=row.get('capacity_assessment') or {}
            row['capacity_assessment']={key:(value[:240] if isinstance(value,str) else
                [text[:160] for text in value[:3] if isinstance(text,str)] if isinstance(value,list) else value)
                for key,value in assessment.items() if key in
                ('kind','status','as_of','recorded_at','reviewed_at','basis_note','assumptions','missing_conditions')}
        company_keys=('company_id','name','name_cn','roles')
        companies=[{key:c.get(key) for key in company_keys} for c in companies]
        leaders=[{key:c.get(key) for key in (*company_keys,'totals')} for c in leaders]
        audit={key:audit[key] for key in ('operating','construction','planning','estimated','estimated_sites','sites','known','unknown','ranged_sites','unlocated',
               'portfolios_excluded','duplicates_excluded','oldest_verified','latest_verified')}
    return {'overview':overview,'schema_version': 1, 'generated_at': date.today().isoformat(), 'filters': params,
            'coverage': {'label': '已追踪项目 · 非全球普查', 'oldest_verified': dates[0] if dates else None,
                         'latest_verified': dates[-1] if dates else None},
            'totals': totals(cohort), 'rows': rows, 'detail': detail, 'companies': companies,
            'tracking': tracking, 'geographic_filters': geographic_filters,
            'research_updates': public_updates(root, company=params.get('c')),
            'leaders': leaders, 'regions': [{'id': r, 'name': REGIONS.get(r, r)} for r in sorted({p['region'] for p in all_rows})],
            'regional': regional, 'market': market(root), 'benchmarks': benchmarks(root),
            'capacity_audit': audit,
            'stages': STAGES, 'company': next((c for c in companies if c['company_id']==params.get('c')),None),
            'basis': '仅汇总已披露 IT 负载的确定值 MW，容量区间单列且不取中点；公司视图为相关园区容量，并非持有或租用份额。组合记录不参加容量合计。'}
