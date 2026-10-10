"""Generate the five-variable-class target list (framework/tco_targets.json).

The list is not written by hand. It is the cross product of three registered things:

* the factor tree's fetch entries (framework/tco_factors.json) — one target per entry,
  carrying the factor's model inputs;
* the BOM parts (framework/bom.json) × the data classes a part has by construction
  (the 2026-09-28 recut rule: every part has its own price, supplier list and lead time),
  plus a news watch for parts that are not mature;
* the site rights (framework/site_rights.json) × the variable classes each right is
  registered under.

``--refresh`` rewrites the file, ``--check`` fails when the file differs from what the
inputs produce. Status never becomes ``sourced`` unless a price series, a valued indicator
or the model's evidence already backs the row. Since 2026-09-28 a fourth state, ``delivered``,
marks rows a team has delivered into a Git-registered carrier (product docs plan, event cards,
price records carrying ``target_id``) that is not yet a series; nothing that lives only in a
runtime store counts. Rows of teams that are not connected carry no due date.
"""
import argparse
from inresearch.knowledge.skeleton import system_path, system_key
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGETS = 'framework/tco_targets.json'
FACTORS = 'framework/tco_factors.json'
PART_FETCH = 'framework/part_fetch.json'  # 人工登记的部件级来源与日历
DOCS_PLAN = 'data/product_docs_plan.csv'    # 规格交付的 Git 载体：doc_id / source_url
EVENT_CARDS = 'data/event_cards.json'       # 事件卡快照（inews 交付的 Git 载体，可缺席）
STATUSES = {'sourced': '已有序列、已录值指标或模型证据', 'assumed': '因子行的模型输入仍为作者假设',
            'delivered': '队已交付到 Git 内载体（资料计划的 doc_id / source_url、带 origin_pointer 的事件卡、带 target_id 的价格记录），尚未成为序列',
            'needed': '缺'}

VARIABLE_CLASSES = {'1': '构成', '2': '运行', '3': '价格', '4': '时间', '5': '主体'}
DATA_CLASSES = {'reference': '参照数据，按版本改', 'observation': '观测数据，按时点追加（series_id + as_of）',
                'material': '材料档案，交由 Spark 提取后再入事实'}
MECHANISMS = {'api': '公开 API 或固定表格下载', 'table': '固定网页表格', 'pdf_free': '可直接下载的 PDF',
              'pdf_registered': '需注册下载的 PDF（macmini）', 'edgar': 'EDGAR 与 IR 站',
              'vendor_page': '厂商产品页与规格文件', 'rss': '新闻 RSS、API 与页面监控',
              'js_page': '需浏览器渲染或登录的页面（macmini）'}
ASSISTED = ('pdf_registered', 'js_page')
PRINCIPLES = ['需求只来自本清单，各队不自定抓什么', '一个来源只属一个队、一台主执行机；换主机等于结束旧任务开新任务',
              '交付在供应中心汇总；Fetchspec 使用原件包，inews 使用只读事件 feed，正式采用另验', '给 inresearch 的采集默认不翻译；挑选在先，翻译在后']
# fetch.kind → defaults for entries that carry no explicit routing
KIND_DEFAULTS = {
    'product': dict(variable_class=1, data_class='reference', mechanism='vendor_page', team='fetchspec'),
    'data': dict(variable_class=3, data_class='observation', mechanism='api', team='fetchstat'),
    'report': dict(variable_class=2, data_class='observation', mechanism='pdf_free', team='fetchreports'),
    'news': dict(variable_class=5, data_class='material', mechanism='rss', team='inews'),
}
DUE_DAYS = {'reference': 90, 'observation': 30, 'material': 7}
PART_STATUS_RANK = {'tight': 2, 'transition': 3, 'emerging': 3, 'mature': 4}
OPERATION_MATCH = ('pue', 'wue', 'utilization', 'penetration', 'density')
PART_ROWS = {  # data class a physical part has by construction → routing
    'spec': dict(variable_class=1, data_class='reference', mechanism='vendor_page', team='fetchspec',
                 disclosure_type='产品规格、数据手册与参考设计', publisher_category='厂商、ODM', calendar='每代际发布'),
    'operation': dict(variable_class=2, data_class='reference', mechanism='vendor_page', team='fetchspec',
                      disclosure_type='额定功率与功率份额、效率曲线或 PUE 贡献、寿命与 MTBF、上架与利用率', publisher_category='厂商数据手册、实测与运营披露', calendar='每代际发布'),
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
    part_fetch = load(root, PART_FETCH)['parts'] if (root / PART_FETCH).exists() else {}
    products = load(root, 'data/products.json')['records']
    companies = {}
    for r in load(root, 'data/companies.json')['records']:
        cn = r.get('name_cn') or ''
        companies[r['company_id']] = (r.get('name') or cn or r['company_id']) if cn.startswith('（') else (cn or r.get('name') or r['company_id'])
    prices = load(root, 'data/prices.json')['records']
    series_ids = {r['series_id'] for r in prices}
    lead_series = {r['series_id'] for r in prices if r.get('category') == 'lead-time'}
    eff_series = {r['series_id'] for r in prices if r.get('category') == 'efficiency'}
    indicators = {i['id']: i for i in load(root, 'framework/indicators.json')['indicators']}
    model = load(root, 'data/datacenter_model.json')
    evidence = model.get('evidence', {})
    # every model input carries its variable class (data/datacenter_model.json evidence.variable_class)
    input_class = {k: v.get('variable_class') for k, v in evidence.items()}
    missing = [k for k in model['inputs'] if input_class.get(k) not in (1, 2, 3, 4, 5)]
    if missing:
        raise ValueError('model inputs without a variable_class: ' + ', '.join(missing))
    contract = load(root, 'framework/supply_contract.json')
    providers = {p['id']: p for p in contract['providers']}
    # Git-registered delivery carriers (a runtime store never counts)
    delivered_parts, card_parts, card_rights, card_targets = set(), set(), set(), set()
    if (root / DOCS_PLAN).is_file():
        with open(root / DOCS_PLAN, encoding='utf-8-sig', newline='') as fh:
            for r in csv.DictReader(fh):
                if (r.get('status') or 'todo') != 'todo' and (r.get('doc_id') or r.get('source_url')):
                    delivered_parts.add(r.get('bom_part'))
    if (root / EVENT_CARDS).is_file():
        for c in load(root, EVENT_CARDS).get('records', []):
            if not c.get('origin_pointer'):
                continue
            if c.get('target_id'):
                # a card bound to one target row delivers exactly that row; its part/right
                # only widen legacy target-less cards (a spec card must not mark the part's news row)
                card_targets.add(c['target_id'])
                continue
            if c.get('part_id'):
                card_parts.add(c['part_id'])
            if c.get('site_right_id'):
                card_rights.add(c['site_right_id'])
            if c.get('target_id'):
                card_targets.add(c['target_id'])
    price_targets = {r['target_id'] for r in prices if r.get('target_id')}
    hosts = {k: v['host'] for k, v in contract['execution_policy'].items() if isinstance(v, dict) and 'host' in v}
    as_of = as_of or max(factors_doc.get('updated', ''), bom.get('schedule_updated', bom.get('updated', '')))
    base_day = dt.date.fromisoformat(as_of)

    factors = {f['id']: f for f in factors_doc['factors']}
    part_factors, right_factors = {}, {}
    for f in factors_doc['factors']:
        for pid in f.get('bom_parts', []):
            part_factors.setdefault(pid, []).append(f['id'])
        for rid in f.get('site_rights', []):
            right_factors.setdefault(rid, []).append(f['id'])

    def host_for(mechanism, team):
        # assisted 机制永远在 macmini；其余按供应方登记的 host_default（fetchspec 2026-09-29 对齐为 macmini），缺省 continuous
        if mechanism in ASSISTED:
            return hosts['assisted']
        default = providers.get(team, {}).get('host_default', hosts['continuous'])
        if default not in hosts.values():
            raise ValueError(f'{team}: host_default {default} is not a registered execution host')
        return default

    def team_meta(team):
        p = providers[team]
        return {'name': p.get('name', team), 'repository': p.get('repository', ''),
                'mechanism_family': p.get('mechanism_family', ''), 'host_default': p.get('host_default', hosts['continuous'])}

    def delivered(target_id, kind, part_id, right_id):
        if target_id in price_targets or target_id in card_targets:
            return True
        if kind in ('spec', 'operation') and part_id in delivered_parts:
            return True
        if kind == 'news' and part_id in card_parts:
            return True
        return kind == 'holders' and right_id in card_rights

    def status_for(data_class, series, indicator_ids, inputs, origin, target_id=None, kind=None, part_id=None, right_id=None):
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
        return 'delivered' if delivered(target_id, kind, part_id, right_id) else 'needed'

    def due(entry_due, data_class):
        return entry_due or (base_day + dt.timedelta(days=DUE_DAYS[data_class])).isoformat()

    def row(**kw):
        mechanism = kw['mechanism']
        connected = providers.get(kw['team'], {}).get('connection', 'not_connected') != 'not_connected'
        status = status_for(kw['data_class'], kw['series'], kw.get('indicators', []), kw['model_inputs'], kw['origin'],
                            target_id=kw['id'], kind=kw.get('kind'), part_id=kw.get('part_id'), right_id=kw.get('site_right_id'))
        out = {
            'id': kw['id'], 'variable_class': kw['variable_class'],
            'origin': kw['origin'], 'factor_ids': kw['factor_ids'], 'factor_id': kw['factor_ids'][0] if kw['factor_ids'] else None,
            'part_id': kw.get('part_id'), 'site_right_id': kw.get('site_right_id'),
            'model_inputs': kw['model_inputs'], 'series': kw['series'], 'planned_series': kw.get('planned_series', []),
            'indicators': kw.get('indicators', []), 'data_class': kw['data_class'],
            'disclosure_type': kw['disclosure_type'], 'publisher_category': kw['publisher_category'],
            'instances': kw['instances'], 'mechanism': mechanism, 'team': kw['team'], 'host': host_for(mechanism, kw['team']),
            'calendar': kw['calendar'], 'team_state': 'connected' if connected else 'not_connected',
            'next_due': due(kw.get('next_due'), kw['data_class']) if connected else None,
            'status': status, 'sourced_by': {'sourced': 'registry', 'delivered': 'delivery'}.get(status),
            'sensitivity_rank': kw['sensitivity_rank'], 'notes': kw.get('notes', ''), 'curated': kw.get('curated', False),
            'chain': kw.get('chain'), 'chain_order': kw.get('chain_order'), 'stage': kw.get('stage'),
        }
        return out

    targets = []
    # 1. factor targets: one per registered fetch entry
    for f in factors_doc['factors']:
        for entry in f.get('fetch', []):
            d = {**KIND_DEFAULTS[entry['kind']], **{k: v for k, v in entry.items() if v is not None}}
            slug = entry.get('slug') or entry['kind']
            targets.append(row(
                id=f"F.{f['id']}.{slug}", variable_class=d['variable_class'], origin='factor', kind=entry['kind'], factor_ids=[f['id']],
                model_inputs=list(entry.get('model_inputs') or f.get('model_inputs') or []),
                series=list(entry.get('series') or []), planned_series=list(entry.get('planned_series') or []),
                indicators=list(entry.get('indicators') or []), data_class=d['data_class'],
                disclosure_type=entry.get('disclosure_type') or entry['what'],
                publisher_category=entry.get('publisher_category') or '、'.join(entry['sources']),
                instances=list(entry.get('instances') or entry['sources']), mechanism=d['mechanism'], team=d['team'],
                calendar=entry.get('calendar') or entry['cadence'], next_due=entry.get('next_due'),
                sensitivity_rank=entry.get('sensitivity_rank', 3), notes=entry.get('notes', entry['what'])))
    # 2. part targets: data classes a part has by construction; rows walk each system's chain from upstream
    systems = bom.get('systems', {})
    def sys_rank(p):
        return system_key(systems, p['system'])
    chain_pos = {}
    for sid, s in systems.items():
        if isinstance(s, dict):
            for i, c in enumerate(s.get('chains', [])):
                chain_pos[(sid, c)] = i
    for p in sorted(bom['parts'], key=lambda p: (sys_rank(p), chain_pos.get((p['system'], p.get('chain')), 99), p.get('chain_order', 99))):
        lines = [f"{companies.get(r['company_id'], r['company_id'])} · {r['product_line']}"
                 for r in products if p['id'] in (r.get('bom_parts') or [])]
        names = [companies.get(c, c) for c in p['companies']]
        instances = (lines or names or [p['name']])[:12]
        fids = part_factors.get(p['id'], [])
        pool = sorted({k for fid in fids for k in factors[fid].get('model_inputs', [])})
        rank = PART_STATUS_RANK.get(p['status'], 4)
        kinds = ['spec', 'operation', 'price', 'lead_time'] if p['kind'] == 'part' else ['spec', 'price'] if p['kind'] == 'software' else ['spec']
        if p['kind'] == 'part' and p['status'] != 'mature':
            kinds.append('news')
        for kind in kinds:
            spec = {**PART_ROWS[kind]}
            reg = part_fetch.get(p['id'], {}).get(kind)
            if reg:  # 人工登记覆盖模板：出版方类别、实例、日历、机制、队
                spec.update({k: reg[k] for k in ('publisher_category', 'calendar', 'mechanism', 'team') if k in reg})
            if kind == 'operation':  # 运行行：效率序列与运行指标（PUE、利用率、渗透率、密度）
                series = [s for s in p.get('series', []) if s in eff_series]
                inds = [i for i in p.get('indicators', []) if any(m in i for m in OPERATION_MATCH)]
            else:
                series = [s for s in p.get('series', []) if (s in lead_series) == (kind == 'lead_time') and s not in eff_series] if kind in ('price', 'lead_time') else []
                inds = [i for i in p.get('indicators', []) if ('lead_time' in i or 'backlog' in i) == (kind == 'lead_time') and not any(m in i for m in OPERATION_MATCH)] if kind in ('price', 'lead_time') else []
            sysname = bom['systems'][p['system']]['name'] if isinstance(bom['systems'][p['system']], dict) else bom['systems'][p['system']]
            notes = {'spec': f"{p['name']}：规格与供应商名单（{sysname} · {p.get('chain', '')}，{p['scale'] or p['kind']}）",
                     'operation': f"{p['name']}：运行参数——额定功率与份额、效率或 PUE 贡献、寿命与 MTBF、上架与利用率（{bom['stages'][[s['id'] for s in bom['stages']].index(p['stage'])]['name'] if p.get('stage') else ''} 阶段）",
                     'price': f"{p['name']}：自己的价格——重切规则的第一条件", 'lead_time': f"{p['name']}：自己的交期——重切规则的第三条件",
                     'news': f"{p['name']}：{p['status']} 状态部件的供应事件"}[kind]
            if p['kind'] == 'software' and kind == 'price':
                notes = f"{p['name']}：订阅价与许可价（软件条目进目标表，用户 2026-09-28 决定）"
            inputs = [k for k in pool if input_class.get(k) == spec['variable_class']]
            targets.append(row(
                id=f"P.{p['id']}.{kind}", variable_class=spec['variable_class'], origin=p['kind'], kind=kind, factor_ids=fids,
                part_id=p['id'], model_inputs=inputs, series=series, indicators=inds, data_class=spec['data_class'],
                disclosure_type=spec['disclosure_type'], publisher_category=spec['publisher_category'],
                instances=(list(reg['instances']) if reg and reg.get('instances') else instances),
                mechanism=spec['mechanism'], team=spec['team'], calendar=spec['calendar'], sensitivity_rank=rank, notes=notes,
                curated=bool(reg), chain=p.get('chain'), chain_order=p.get('chain_order'), stage=p.get('stage')))
    # 3. site-right targets: one per registered variable class
    for r in rights:
        fids = right_factors.get(r['id'], [])
        pool = sorted({k for fid in fids for k in factors[fid].get('model_inputs', [])})
        for vc in r['variable_classes']:
            spec = RIGHT_ROWS[vc]
            inputs = [k for k in pool if input_class.get(k) == vc]
            instances = [companies.get(c, c) for c in r.get('companies', [])] or [r['name']]
            targets.append(row(
                id=f"S.{r['id']}.{spec['slug']}", variable_class=vc, origin='site_right', kind=spec['slug'], factor_ids=fids,
                site_right_id=r['id'], model_inputs=inputs, series=list(r.get('series', [])),
                indicators=list(r.get('indicators', [])) if vc != 5 else [], data_class=spec['data_class'],
                disclosure_type=spec['disclosure_type'], publisher_category=spec['publisher_category'], instances=instances,
                mechanism=spec['mechanism'], team=spec['team'], calendar=spec['calendar'], sensitivity_rank=2,
                notes=f"{r['name']}：{r['desc']}", stage=r.get('stage')))
    for t in targets:
        for sid in t['series']:
            if sid not in series_ids:
                raise ValueError(f"{t['id']}: unknown series {sid}")
        for k in t['model_inputs']:
            if k not in model['inputs']:
                raise ValueError(f"{t['id']}: unknown model input {k}")
    # 主行（2026-09-29）：一个模型输入可以由多行喂（因子行 + 部件行），但账本的可信边界只回链一行——
    # 因子树登记的抓取条目是主行（列表里因子行在前，先到先得）；没有因子行的输入由第一条部件 / 权利行承担。
    primary = {}
    for t in targets:
        for k in t['model_inputs']:
            primary.setdefault(k, t['id'])
    for t in targets:
        t['feeds_primary'] = [k for k in t['model_inputs'] if primary[k] == t['id']]
    counts = {'factor': 0, 'part': 0, 'software': 0, 'archetype': 0, 'site_right': 0}
    by_status = {s: 0 for s in STATUSES}
    for t in targets:
        counts[t['origin']] += 1
        by_status[t['status']] += 1
    teams = sorted({t['team'] for t in targets})
    return {
        'version': '2.1.0', 'updated': as_of, 'title': '五类变量目标清单',
        'note': ('六队采集分队的唯一任务来源，由 python3 manage.py targets --refresh 生成，不手写：'
                 '因子树登记的抓取条目（framework/tco_factors.json fetch，带因子的模型输入键）各成一行；'
                 '每个物理部件按"自己的价格、供应商名单、交期"各成规格、价格、交期三行，非成熟部件再加一行新闻事件；'
                 '软件条目成规格与订阅价两行，设施基型只成规格一行；站点权利按登记的变量类各成一行。2026-09-28 骨架补齐：每个物理部件再加一行运行（operation，变量类 2：额定功率与份额、效率或 PUE 贡献、寿命与 MTBF、上架与利用率）；因子树的 time.build 生成工期、排队与审批行；部件级与权利级行带建设阶段 stage。'
                 '部件级行的出版方、实例、日历、机制与队优先取 framework/part_fetch.json 的人工登记（curated=true），没有登记的沿用模板。'
                 '每一行写明变量类（构成、运行、价格、时间、主体；2026-09-29 起不再带 layer 兼容键，尺度与变量类彻底分开）、汇到哪些因子、喂模型的哪些输入、'
                 '已有序列与指标、披露类型 × 出版方类别 × 日历、实例、机制、主责队与主执行机；feeds_primary 列出这一行作为主行的模型输入（一个输入只有一条主行，因子行优先），账本可信边界只回链主行。'
                 'status 只在已有序列、已录值指标或模型证据支持时为 sourced；2026-09-28 起加第四态 delivered：队已交付到 Git 内载体'
                 '（资料计划的 doc_id / source_url、带 origin_pointer 的事件卡、带 target_id 的价格记录）但尚未成为序列；只在运行库有的不算。'
                 'sourced_by 写明 sourced 来自人工登记的序列（registry）还是队交付（delivery）；team_state 写明主责队是否已接入，'
                 '未接入的队不排到期（next_due 为空，页面显示"待建队"）。公司只是实例，随时可换。'),
        'generated_from': {'tco_factors': factors_doc.get('version'), 'bom': bom.get('version'),
                           'site_rights': load(root, 'framework/site_rights.json').get('version'),
                           'rule': '因子抓取条目 + 部件 × 数据类别 + 站点权利 × 变量类'},
        'counts': {**counts, 'total': len(targets), 'by_status': by_status},
        'statuses': STATUSES,
        'carriers': {'spec': DOCS_PLAN + '（status ≠ todo 且有 doc_id 或 source_url）', 'news / holders': EVENT_CARDS + '（带 origin_pointer 的事件卡）',
                     'observation': 'data/prices.json（带 target_id 的记录）'},
        'principles': PRINCIPLES, 'variable_classes': VARIABLE_CLASSES,
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
