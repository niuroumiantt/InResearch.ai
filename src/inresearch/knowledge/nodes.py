"""登记表的两列：node 与 variable_class（03「骨架的三个补充」第 3 条，2026-09-28）。

每张登记表的每条记录都要说清它挂在骨架的哪个节点（root / system:x / part:x / site:x / actor:x）、
属五类变量的哪一类（1 构成 2 运行 3 价格 4 时间 5 主体）。两列由这里从骨架与登记派生，不手写：
``python3 manage.py nodes --refresh`` 回填六张表，``--check``（``validate --strict`` 也跑）核对存储值与派生值
一致。派生规则改了，回填一次即可；规则本身就是登记，改规则须改这里并留记录。

覆盖：价格库（按序列归部件 / 权利 / 根）、指标表（逐条登记的变量类）、指标定义表 metrics（指标同名者同源，
其余按名称与单位判类，挂根）、事实库（随其指标）、产品库（第一个 bom_part 派生 node、system、chain）、公司库（主体）。
知识库（问题、证据、陈述）随图谱 3.0 的问题表挂节点，不在这里。
"""
import argparse
import json
from pathlib import Path

from inresearch.paths import project_root
from inresearch.storage.files import atomic_write

ROOT = project_root()
NODE_KINDS = ('root', 'system', 'part', 'site', 'actor')
REGISTRIES = {  # path → (collection key, record kind, indent the file is kept in)
    'data/prices.json': ('records', 'price', 2),
    'framework/indicators.json': ('indicators', 'indicator', 2),
    'framework/metrics.json': ('metrics', 'metric', 2),
    'data/facts.json': ('records', 'fact', 2),
    'data/products.json': ('records', 'product', 1),
    'data/companies.json': ('records', 'company', 1),
}

# 指标表逐条登记（44 条，新指标不登记这里就过不了校验）。
INDICATOR_CLASS = {
    'benchmark_spread': 3, 'dc_rent_index_na': 3, 'global_operational_gw': 1, 'pipeline_conversion_rate': 2, 'vacancy_rate_na': 2,
    'hyperscaler_lease_ratio': 5, 'neocloud_funded_gw': 1, 'top10_pipeline_share': 5, 'capex_guidance_delta': 3, 'circular_deal_exposure': 5,
    'mega_contract_backlog': 3, 'btm_operational_mw': 1, 'interconnection_queue_years': 4, 'ppa_price_index': 3, 'region_pipeline_share': 1,
    'zoning_denial_count': 4, 'cowos_capacity_wpm': 1, 'gpu_lead_time': 4, 'rack_density_shipping': 1, 'ethernet_ai_share': 1,
    'optics_800g_price': 3, 'cdu_lead_time': 4, 'cooling_capex_per_mw': 3, 'liquid_cooling_penetration': 2, 'gas_turbine_backlog_years': 4,
    'genset_lead_time': 4, 'transformer_lead_time': 4, 'construction_duration_months': 4, 'electrician_wage_premium': 3, 'dc_reit_premium': 3,
    'gpu_abs_spread': 3, 'price_per_mw_operational': 3, 'ai_revenue_capex_ratio': 3, 'inference_unit_margin': 3, 'token_price_flagship': 3,
    'gpu_hourly_rate_spot': 3, 'gpu_rate_term_spread': 3, 'used_gpu_price_index': 3, 'aidc_utilization_channel': 2, 'domestic_gpu_shipment': 1,
    'east_west_rack_rate': 3, 'project_cancellation_count': 5, 'capex_guidance_downgrade': 5, 'gpu_spot_drawdown': 3,
}
# 价格库按序列判类：先看序列名里的关键词，再看类别里语义固定的两类，再看单位，最后按类别兜底。
SERIES_KEYWORDS = [('lead-time', 4), ('build-time', 4), ('useful-life', 4), ('duration', 4), ('queue', 4),
                   ('utilization', 2), ('vacancy', 2), ('occupancy', 2), ('penetration', 2), ('-pue', 2), ('-wue', 2)]
CATEGORY_CLASS = {'lead-time': 4, 'efficiency': 2, 'market': 2, 'benchmark': 3, 'capex': 3, 'opex': 3, 'rent': 3, 'gpu-rental': 3,
                  'token-price': 3, 'power-price': 3, 'hardware': 3, 'used-gpu': 3, 'asset-deal': 3, 'ppa': 3, 'labor': 3,
                  'credit-spread': 3, 'valuation': 3}
TIME_UNITS = {'月', '年', '天', '周', '个月', '季度', 'months', 'years', 'days', 'weeks'}
MONEY_MARKS = ('$', '¥', '€', '£', '¢', '元', '美元', '美分', '欧分', 'index', '指数', 'bp', 'SOFR')
CAPACITY_MARKS = ('GW', 'MW', 'kW', '张', '台', '颗', '套', '个', '只', 'EB', 'TB', 'PB', 'wpm', '㎡', 'm²')
# metrics 按名称判类（指标同名者优先用指标表的登记）。
NAME_KEYWORDS = [('交期', 4), ('工期', 4), ('年限', 4), ('周期', 4), ('寿命', 4), ('排队', 4), ('时长', 4), ('折旧年', 4),
                 ('PUE', 2), ('WUE', 2), ('利用率', 2), ('上架', 2), ('渗透', 2), ('空置', 2), ('负载', 2), ('效率', 2), ('故障', 2),
                 ('持有', 5), ('股东', 5), ('租户', 5), ('客户集中', 5), ('评级', 5), ('信用', 5),
                 ('容量', 1), ('规模', 1), ('数量', 1), ('出货', 1), ('装机', 1), ('功率', 1), ('密度', 1), ('面积', 1), ('机柜数', 1),
                 ('造价', 3), ('价格', 3), ('租金', 3), ('电价', 3), ('费率', 3), ('资本开支', 3), ('营收', 3), ('利润', 3), ('成本', 3),
                 ('估值', 3), ('收入', 3), ('单价', 3), ('毛利', 3)]


def _load(root, rel):
    return json.loads((Path(root) / rel).read_text(encoding='utf-8'))


def unit_class(unit):
    """单位能定的类：时间单位 → 4；PUE/WUE → 2；带货币或指数 → 3；人 → 2（人员是运行）；容量与数量 → 1；其余不定。"""
    u = (unit or '').strip()
    if not u:
        return None
    if u in TIME_UNITS:
        return 4
    if u.startswith(('PUE', 'WUE', 'L/kWh')):
        return 2
    if any(m in u for m in MONEY_MARKS):
        return 3
    if u == '人' or u.startswith('人/'):
        return 2
    if any(m in u for m in CAPACITY_MARKS):
        return 1
    return None


def price_class(rec):
    sid = rec.get('series_id') or ''
    for key, cls in SERIES_KEYWORDS:
        if key in sid:
            return cls
    if rec.get('category') in ('lead-time', 'efficiency'):
        return CATEGORY_CLASS[rec['category']]
    return unit_class(rec.get('unit')) or CATEGORY_CLASS.get(rec.get('category'), 3)


def metric_class(metric):
    if metric.get('metric_id') in INDICATOR_CLASS:
        return INDICATOR_CLASS[metric['metric_id']]
    name = metric.get('name') or ''
    for key, cls in NAME_KEYWORDS:
        if key in name:
            return cls
    return unit_class(metric.get('unit')) or 3


def build_index(root=ROOT):
    """序列与指标挂在哪个节点：部件登记优先，其次站点权利，其余归根。缺登记文件时是空索引（临时根目录也能录价）。"""
    idx = {'parts': {}, 'systems': {}, 'rights': set(), 'actors': set(), 'series': {}, 'indicators': {}}
    root = Path(root)
    if (root / 'framework/bom.json').exists():
        bom = _load(root, 'framework/bom.json')
        idx['parts'] = {p['id']: p for p in bom['parts']}
        idx['systems'] = {k: v for k, v in bom.get('systems', {}).items() if isinstance(v, dict)}
        for p in bom['parts']:
            for s in p.get('series', []):
                idx['series'].setdefault(s, 'part:' + p['id'])
            for i in p.get('indicators', []):
                idx['indicators'].setdefault(i, 'part:' + p['id'])
    if (root / 'framework/site_rights.json').exists():
        for r in _load(root, 'framework/site_rights.json')['rights']:
            idx['rights'].add(r['id'])
            for s in r.get('series', []):
                idx['series'].setdefault(s, 'site:' + r['id'])
            for i in r.get('indicators', []):
                idx['indicators'].setdefault(i, 'site:' + r['id'])
    if (root / 'data/companies.json').exists():
        idx['actors'] = {c['company_id'] for c in _load(root, 'data/companies.json')['records']}
    return idx


def valid_node(node, idx):
    if node == 'root':
        return True
    kind, _, ident = (node or '').partition(':')
    pool = {'system': idx['systems'], 'part': idx['parts'], 'site': idx['rights'], 'actor': idx['actors']}.get(kind)
    return bool(ident) and pool is not None and ident in pool


def series_fields(rec, idx):
    """一条价格记录的两列（录价接口也用它，录入者不填）。"""
    return {'node': idx['series'].get(rec.get('series_id'), 'root'), 'variable_class': price_class(rec)}


def indicator_fields(rec, idx):
    cls = INDICATOR_CLASS.get(rec.get('id'))
    return {'node': idx['indicators'].get(rec.get('id'), 'root'), 'variable_class': cls}


def product_fields(rec, idx):
    parts = [p for p in (rec.get('bom_parts') or []) if p in idx['parts']]
    first = idx['parts'].get(parts[0]) if parts else None
    return {'node': ('part:' + first['id']) if first else 'root', 'nodes': ['part:' + p for p in parts],
            'system': first['system'] if first else None, 'chain': first.get('chain') if first else None, 'variable_class': 1}


def fields_for(kind, rec, idx, metrics=None):
    if kind == 'price':
        return series_fields(rec, idx)
    if kind == 'indicator':
        return indicator_fields(rec, idx)
    if kind == 'metric':
        node = idx['indicators'].get(rec.get('metric_id'), 'root') if rec.get('metric_id') in INDICATOR_CLASS else 'root'
        return {'node': node, 'variable_class': metric_class(rec)}
    if kind == 'fact':
        m = (metrics or {}).get(rec.get('metric_id'))
        return fields_for('metric', m, idx) if m else {'node': 'root', 'variable_class': None}
    if kind == 'product':
        return product_fields(rec, idx)
    if kind == 'company':
        return {'node': 'actor:' + str(rec.get('company_id')), 'variable_class': 5}
    raise ValueError(kind)


def derive(root=ROOT):
    """每张表：(文档, 记录键, 变化的记录数, 问题列表)。不写文件。"""
    root = Path(root)
    idx = build_index(root)
    metrics = {m['metric_id']: m for m in _load(root, 'framework/metrics.json')['metrics']} if (root / 'framework/metrics.json').exists() else {}
    out = {}
    for rel, (key, kind, indent) in REGISTRIES.items():
        if not (root / rel).exists():
            continue
        doc = _load(root, rel)
        changed, problems = 0, []
        for rec in doc[key]:
            want = fields_for(kind, rec, idx, metrics)
            ident = rec.get('series_id') or rec.get('id') or rec.get('metric_id') or rec.get('fact_id') or rec.get('company_id') or '?'
            if kind == 'product':
                ident = f"{rec.get('company_id')}/{rec.get('product_line')}"
            if want.get('variable_class') not in (1, 2, 3, 4, 5):
                problems.append(f'{rel}[{ident}]: 变量类无法派生（指标须登记在 knowledge.nodes.INDICATOR_CLASS，事实须有指标定义）')
            if not valid_node(want['node'], idx):
                problems.append(f"{rel}[{ident}]: node 不在骨架里: {want['node']}")
            if any(rec.get(k) != v for k, v in want.items()):
                changed += 1
                problems.append(f'{rel}[{ident}]: node / variable_class 与派生值不一致，运行 python3 manage.py nodes --refresh')
                rec.update(want)
        out[rel] = (doc, key, changed, problems, indent)
    return out


def problems(root=ROOT, limit=8):
    found = []
    for rel, (_doc, _key, changed, rows, _indent) in derive(root).items():
        found.extend(rows[:limit])
        if len(rows) > limit:
            found.append(f'{rel}: 另有 {len(rows) - limit} 条同类问题')
    return found


def refresh(root=ROOT):
    written = {}
    for rel, (doc, _key, changed, _rows, indent) in derive(root).items():
        if changed:
            atomic_write(Path(root) / rel, (json.dumps(doc, ensure_ascii=False, allow_nan=False, indent=indent) + '\n').encode('utf-8'))
        written[rel] = changed
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--refresh', action='store_true', help='backfill node / variable_class on every registry')
    ap.add_argument('--check', action='store_true', help='fail when a stored value differs from its derivation (default)')
    args = ap.parse_args(argv)
    if args.refresh:
        for rel, n in refresh(ROOT).items():
            print(f'{rel}: {n} records updated')
        return 0
    found = problems(ROOT)
    for line in found:
        print('ERROR: ' + line)
    if found:
        return 1
    print('nodes: every registry record carries node and variable_class consistent with the skeleton')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
