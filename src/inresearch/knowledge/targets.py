"""Generate the five-variable-class target list (framework/tco_targets.json).

The list is not written by hand. It is the cross product of three registered things:

* the factor tree's fetch entries (framework/tco_factors.json) — one target per entry,
  carrying the factor's TCO model inputs;
* the BOM parts (framework/bom.json) × the data classes a part has by construction
  (the 2026-09-28 recut rule: every part has its own price, supplier list and lead time),
  plus a news watch for parts that are not mature;
* the site rights (framework/site_rights.json) × the variable classes each right is
  registered under.

``--refresh`` rewrites the file, ``--check`` fails when the file differs from what the
inputs produce. Status never becomes ``sourced`` unless a price series, a valued indicator
or the TCO model's evidence already backs the row.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGETS = 'framework/tco_targets.json'
FACTORS = 'framework/tco_factors.json'

VARIABLE_CLASSES = {'1': '构成', '2': '运行', '3': '价格', '4': '时间', '5': '主体'}
DATA_CLASSES = {'reference': '参照数据，按版本改', 'observation': '观测数据，按时点追加（series_id + as_of）',
                'material': '材料档案，交由 Spark 提取后再入事实'}
MECHANISMS = {'api': '公开 API 或固定表格下载', 'table': '固定网页表格', 'pdf_free': '可直接下载的 PDF',
              'pdf_registered': '需注册下载的 PDF（macmini）', 'edgar': 'EDGAR 与 IR 站',
              'vendor_page': '厂商产品页与规格文件', 'rss': '新闻 RSS、API 与页面监控',
              'js_page': '需浏览器渲染或登录的页面（macmini）'}
ASSISTED = ('pdf_registered', 'js_page')
PRINCIPLES = ['需求只来自本清单，各队不自定抓什么', '一个来源只属一个队、一台主执行机；换主机等于结束旧任务开新任务',
              '交付只走供应中心一个入口，按 fetchspec 包格式', '给 inresearch 的采集默认不翻译；挑选在先，翻译在后']
# fetch.kind → defaults for entries that carry no explicit routing
KIND_DEFAULTS = {
    'product': dict(variable_class=1, data_class='reference', mechanism='vendor_page', team='fetchspec'),
    'data': dict(variable_class=3, data_class='observation', mechanism='api', team='fetchstat'),
    'report': dict(variable_class=2, data_class='observation', mechanism='pdf_free', team='fetchreports'),
    'news': dict(variable_class=5, data_class='material', mechanism='rss', team='inews'),
}
DUE_DAYS = {'reference': 90, 'observation': 30, 'material': 7}
# which of a factor's TCO inputs a generated part / right row can feed, by variable class
CLASS_INPUTS = {
    1: lambda k: k in {'gpus_per_mw', 'it_class', 'pue', 'wue', 'load_factor', 'redundancy', 'cooling'},
    2: lambda k: k in {'pue', 'wue', 'load_factor', 'gpu_utilization', 'fte_per_mw', 'maint_pct_facility', 'maint_pct_it'},
    3: lambda k: k != 'gpus_per_mw' and (k.startswith(('capex_', 'price_')) or k.endswith(('_price', '_rate', '_per_kw', '_per_mw', '_pct')) or k in {'refresh_cost_factor', 'cost_per_fte', 'labor_index'}),
    4: lambda k: k in {'construction_years', 'it_refresh_years', 'horizon_years', 'ramp_year1', 'ramp_year2', 'power_escalation', 'opex_escalation'},
    5: lambda k: k in {'wacc', 'property_tax_rate', 'shell_rent_per_mw', 'colo_rate', 'land_per_mw'},
}
PART_STATUS_RANK = {'tight': 2, 'transition': 3, 'emerging': 3, 'mature': 4}
PART_ROWS = {  # data class a physical part has by construction → routing
    'spec': dict(variable_class=1, data_class='reference', mechanism='vendor_page', team='fetchspec',
                 disclosure_type='产品规格、数据手册与参考设计', publisher_category='厂商、ODM', calendar='每代际发布'),
    'price': dict(variable_class=3, data_class='observation', mechanism='js_page', team='fetchquotes',
                  disclosure_type='挂牌价、报价与成交价', publisher_category='厂商价目、分销商、研报 BOM', calendar='月'),
    'lead_time': dict(variable_class=4, data_class='observation', mechanism='pdf_free', team='fetchreports',
                      disclosure_type='交期、订单簿与产能', publisher_category='研报、财报电话会、行业协会', calendar='季度'),
    'news': dict(variable_class=5, data_class='material', mechanism='rss', team='inews',
                 disclosure_type='供应商、合同、产能与技术切换事件', publisher_category='行业媒体、公司新闻稿', calendar='持续'),
}
RIGHT_ROWS = {
    3: dict(slug='price', data_class='observation', mechanism='api', team='fetchstat',
            disclosure_type='价格与费率（地价、租金、接入费）', publisher_category='交易公告、政府统计、监管机构', calendar='季度'),
    4: dict(slug='timeline', data_class='observation', mechanism='pdf_free', team='fetchstat',
            disclosure_type='排队年限、许可期限与审批时长', publisher_category='电网运营商、监管机构、地方政府', calendar='季度'),
    5: dict(slug='holders', data_class='material', mechanism='rss', team='inews',
            disclosure_type='权利持有方、合同与许可事件', publisher_category='监管机构、公司公告、行业媒体', calendar='持续'),
}


def load(root, rel):
    return json.loads((Path(root) / rel).read_text(encoding='utf-8'))


def _slug(text):
    return ''.join(c if c.isalnum() else '_' for c in text.lower()).strip('_')


def build(root=ROOT, as_of=None):
    root = Path(root)
    factors_doc = load(root, FACTORS)
    bom = load(root, 'framework/bom.json')
    rights = load(root, 'framework/site_rights.json')['rights']
    products = load(root, 'data/products.json')['records']
    companies = {}
    for r in load(root, 'data/companies.json')['records']:
        cn = r.get('name_cn') or ''
        companies[r['company_id']] = (r.get('name') or cn or r['company_id']) if cn.startswith('（') else (cn or r.get('name') or r['company_id'])
    prices = load(root, 'data/prices.json')['records']
    series_ids = {r['series_id'] for r in prices}
    lead_series = {r['series_id'] for r in prices if r.get('category') == 'lead-time'}
    indicators = {i['id']: i for i in load(root, 'framework/indicators.json')['indicators']}
    tco = load(root, 'data/datacenter_tco_model.json')
    evidence = tco.get('evidence', {})
    contract = load(root, 'framework/supply_contract.json')
    providers = {p['id']: p for p in contract['providers']}
    hosts = {k: v['host'] for k, v in contract['execution_policy'].items() if isinstance(v, dict) and 'host' in v}
    as_of = as_of or max(factors_doc.get('updated', ''), bom.get('updated', ''))
    base_day = dt.date.fromisoformat(as_of)

    factors = {f['id']: f for f in factors_doc['factors']}
    part_factors, right_factors = {}, {}
    for f in factors_doc['factors']:
        for pid in f.get('bom_parts', []):
            part_factors.setdefault(pid, []).append(f['id'])
        for rid in f.get('site_rights', []):
            right_factors.setdefault(rid, []).append(f['id'])

    def host_for(mechanism):
        return hosts['assisted'] if mechanism in ASSISTED else hosts['continuous']

    def team_meta(team):
        p = providers[team]
        return {'name': p.get('name', team), 'repository': p.get('repository', ''),
                'mechanism_family': p.get('mechanism_family', ''), 'host_default': p.get('host_default', hosts['continuous'])}

    def status_for(data_class, series, indicator_ids, inputs, origin):
        ev = {evidence[k]['status'] for k in inputs if k in evidence}
        valued = [i for i in indicator_ids if indicators.get(i, {}).get('value') is not None]
        # a reference row registered on a factor counts as sourced when the model's evidence already cites it;
        # a generated part row does not: its spec sheet has to be in the product library first
        has_data = bool(series or valued) or (data_class == 'reference' and origin == 'factor' and 'sourced' in ev)
        if has_data and 'sourced' in ev:
            return 'sourced'
        # a factor row whose inputs the model still assumes is 'assumed'; a generated row without data is simply needed
        if has_data or (origin == 'factor' and ev and ev <= {'assumed', 'input'}):
            return 'assumed'
        return 'needed'

    def due(entry_due, data_class):
        return entry_due or (base_day + dt.timedelta(days=DUE_DAYS[data_class])).isoformat()

    def row(**kw):
        mechanism = kw['mechanism']
        out = {
            'id': kw['id'], 'variable_class': kw['variable_class'], 'layer': kw['variable_class'],
            'origin': kw['origin'], 'factor_ids': kw['factor_ids'], 'factor_id': kw['factor_ids'][0] if kw['factor_ids'] else None,
            'part_id': kw.get('part_id'), 'site_right_id': kw.get('site_right_id'),
            'model_inputs': kw['model_inputs'], 'series': kw['series'], 'planned_series': kw.get('planned_series', []),
            'indicators': kw.get('indicators', []), 'data_class': kw['data_class'],
            'disclosure_type': kw['disclosure_type'], 'publisher_category': kw['publisher_category'],
            'instances': kw['instances'], 'mechanism': mechanism, 'team': kw['team'], 'host': host_for(mechanism),
            'calendar': kw['calendar'], 'next_due': due(kw.get('next_due'), kw['data_class']),
            'status': status_for(kw['data_class'], kw['series'], kw.get('indicators', []), kw['model_inputs'], kw['origin']),
            'sensitivity_rank': kw['sensitivity_rank'], 'notes': kw.get('notes', ''),
        }
        return out

    targets = []
    # 1. factor targets: one per registered fetch entry
    for f in factors_doc['factors']:
        for entry in f.get('fetch', []):
            d = {**KIND_DEFAULTS[entry['kind']], **{k: v for k, v in entry.items() if v is not None}}
            slug = entry.get('slug') or entry['kind']
            targets.append(row(
                id=f"F.{f['id']}.{slug}", variable_class=d['variable_class'], origin='factor', factor_ids=[f['id']],
                model_inputs=list(entry.get('tco_inputs') or f.get('tco_inputs') or []),
                series=list(entry.get('series') or []), planned_series=list(entry.get('planned_series') or []),
                indicators=list(entry.get('indicators') or []), data_class=d['data_class'],
                disclosure_type=entry.get('disclosure_type') or entry['what'],
                publisher_category=entry.get('publisher_category') or '、'.join(entry['sources']),
                instances=list(entry.get('instances') or entry['sources']), mechanism=d['mechanism'], team=d['team'],
                calendar=entry.get('calendar') or entry['cadence'], next_due=entry.get('next_due'),
                sensitivity_rank=entry.get('sensitivity_rank', 3), notes=entry.get('notes', entry['what'])))
    # 2. part targets: data classes a part has by construction
    for p in bom['parts']:
        lines = [f"{companies.get(r['company_id'], r['company_id'])} · {r['product_line']}"
                 for r in products if p['id'] in (r.get('bom_parts') or [])]
        names = [companies.get(c, c) for c in p['companies']]
        instances = (lines or names or [p['name']])[:12]
        fids = part_factors.get(p['id'], [])
        pool = sorted({k for fid in fids for k in factors[fid].get('tco_inputs', [])})
        rank = PART_STATUS_RANK.get(p['status'], 4)
        kinds = ['spec', 'price', 'lead_time'] if p['kind'] == 'part' else ['spec', 'price'] if p['kind'] == 'software' else ['spec']
        if p['kind'] == 'part' and p['status'] != 'mature':
            kinds.append('news')
        for kind in kinds:
            spec = PART_ROWS[kind]
            series = [s for s in p.get('series', []) if (s in lead_series) == (kind == 'lead_time')] if kind in ('price', 'lead_time') else []
            inds = [i for i in p.get('indicators', []) if ('lead_time' in i or 'backlog' in i) == (kind == 'lead_time')] if kind in ('price', 'lead_time') else []
            notes = {'spec': f"{p['name']}：规格与供应商名单（{bom['systems'][p['system']]}，{p['layer'] or p['kind']}）",
                     'price': f"{p['name']}：自己的价格——重切规则的第一条件", 'lead_time': f"{p['name']}：自己的交期——重切规则的第三条件",
                     'news': f"{p['name']}：{p['status']} 状态部件的供应事件"}[kind]
            if p['kind'] == 'software' and kind == 'price':
                notes = f"{p['name']}：订阅价与许可价（软件条目进目标表，用户 2026-09-28 决定）"
            inputs = [k for k in pool if CLASS_INPUTS[spec['variable_class']](k)]
            targets.append(row(
                id=f"P.{p['id']}.{kind}", variable_class=spec['variable_class'], origin=p['kind'], factor_ids=fids,
                part_id=p['id'], model_inputs=inputs, series=series, indicators=inds, data_class=spec['data_class'],
                disclosure_type=spec['disclosure_type'], publisher_category=spec['publisher_category'], instances=instances,
                mechanism=spec['mechanism'], team=spec['team'], calendar=spec['calendar'], sensitivity_rank=rank, notes=notes))
    # 3. site-right targets: one per registered variable class
    for r in rights:
        fids = right_factors.get(r['id'], [])
        pool = sorted({k for fid in fids for k in factors[fid].get('tco_inputs', [])})
        for vc in r['variable_classes']:
            spec = RIGHT_ROWS[vc]
            inputs = [k for k in pool if CLASS_INPUTS[vc](k)]
            instances = [companies.get(c, c) for c in r.get('companies', [])] or [r['name']]
            targets.append(row(
                id=f"S.{r['id']}.{spec['slug']}", variable_class=vc, origin='site_right', factor_ids=fids,
                site_right_id=r['id'], model_inputs=inputs, series=list(r.get('series', [])),
                indicators=list(r.get('indicators', [])) if vc != 5 else [], data_class=spec['data_class'],
                disclosure_type=spec['disclosure_type'], publisher_category=spec['publisher_category'], instances=instances,
                mechanism=spec['mechanism'], team=spec['team'], calendar=spec['calendar'], sensitivity_rank=2,
                notes=f"{r['name']}：{r['desc']}"))
    for t in targets:
        for sid in t['series']:
            if sid not in series_ids:
                raise ValueError(f"{t['id']}: unknown series {sid}")
        for k in t['model_inputs']:
            if k not in tco['inputs']:
                raise ValueError(f"{t['id']}: unknown TCO input {k}")
    counts = {'factor': 0, 'part': 0, 'software': 0, 'archetype': 0, 'site_right': 0}
    for t in targets:
        counts[t['origin']] += 1
    teams = sorted({t['team'] for t in targets})
    return {
        'version': '2.0.0', 'updated': as_of, 'title': '五类变量目标清单',
        'note': ('六队采集分队的唯一任务来源，由 python3 manage.py targets --refresh 生成，不手写：'
                 '因子树登记的抓取条目（framework/tco_factors.json fetch，带因子的 TCO 模型输入键）各成一行；'
                 '每个物理部件按"自己的价格、供应商名单、交期"各成规格、价格、交期三行，非成熟部件再加一行新闻事件；'
                 '软件条目成规格与订阅价两行，设施基型只成规格一行；站点权利按登记的变量类各成一行。'
                 '每一行写明变量类（构成、运行、价格、时间、主体；layer 键为兼容名）、汇到哪些因子、喂模型的哪些输入、'
                 '已有序列与指标、披露类型 × 出版方类别 × 日历、实例、机制、主责队与主执行机。'
                 'status 只在已有序列、已录值指标或模型证据支持时为 sourced；公司只是实例，随时可换。'),
        'generated_from': {'tco_factors': factors_doc.get('version'), 'bom': bom.get('version'),
                           'site_rights': load(root, 'framework/site_rights.json').get('version'),
                           'rule': '因子抓取条目 + 部件 × 数据类别 + 站点权利 × 变量类'},
        'counts': {**counts, 'total': len(targets)},
        'principles': PRINCIPLES, 'layers': VARIABLE_CLASSES, 'variable_classes': VARIABLE_CLASSES,
        'data_classes': DATA_CLASSES, 'mechanisms': MECHANISMS,
        'teams': {t: team_meta(t) for t in teams}, 'targets': targets,
    }


def render(doc):
    return json.dumps(doc, ensure_ascii=False, indent=2) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--refresh', action='store_true', help='rewrite ' + TARGETS)
    ap.add_argument('--check', action='store_true', help='fail when ' + TARGETS + ' differs from its inputs')
    ap.add_argument('--as-of', help='date stamped as updated; defaults to the newest input file date')
    args = ap.parse_args(argv)
    doc = build(ROOT, args.as_of)
    text = render(doc)
    path = ROOT / TARGETS
    if args.refresh:
        path.write_text(text, encoding='utf-8')
    else:  # --check is the default
        if not path.exists() or path.read_text(encoding='utf-8') != text:
            print(f'ERROR: {TARGETS}: stale or missing; run manage.py targets --refresh')
            return 1
    c = doc['counts']
    print(f"Targets {doc['version']} @ {doc['updated']}: {c['total']} rows "
          f"(factor {c['factor']}, part {c['part']}, software {c['software']}, archetype {c['archetype']}, site_right {c['site_right']})")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
