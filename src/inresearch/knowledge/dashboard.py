"""Generate the dashboard snapshot (data/dashboard.json): one tree, five columns, four questions.

Tree: datacenter root → five systems (IT expands into four) → chains → parts; site rights alongside. Every node carries the five
variable classes (构成 运行 价格 时间 主体) as cells whose sources are registered in
framework/dashboard_rules.json. The page (web/pages/node.html) reads this snapshot and the target
list; it aggregates nothing itself. ``--refresh`` rewrites the snapshot, ``--check`` (default) fails
when it differs from what the inputs produce.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from inresearch.knowledge import economics

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = 'data/dashboard.json'
RULES = 'framework/dashboard_rules.json'
RIGHTS_ROW = {'id': 'site', 'name': '站点权利'}


def load(root, rel):
    return json.loads((Path(root) / rel).read_text(encoding='utf-8'))


def _fmt_input(key, value, unit):
    if unit == '%' and isinstance(value, (int, float)):
        return round(value * 100, 1)
    if isinstance(value, float):
        return round(value, 3)
    return value


def build(root=ROOT, as_of=None):
    root = Path(root)
    rules = load(root, RULES)
    bom = load(root, 'framework/bom.json')
    rights = load(root, 'framework/site_rights.json')['rights']
    factors_doc = load(root, 'framework/tco_factors.json')
    targets_doc = load(root, 'framework/tco_targets.json')
    products = load(root, 'data/products.json')['records']
    companies = {r['company_id']: (r.get('name_cn') or r.get('name') or r['company_id']) for r in load(root, 'data/companies.json')['records']}
    prices = load(root, 'data/prices.json')['records']
    indicators = {i['id']: i for i in load(root, 'framework/indicators.json')['indicators']}
    model = load(root, 'data/datacenter_model.json')
    graph = load(root, 'framework/research_graph.json')
    as_of = as_of or max(bom.get('updated', ''), targets_doc.get('updated', ''), rules.get('updated', ''))
    base_day = dt.date.fromisoformat(as_of)

    latest = {}
    for r in sorted(prices, key=lambda r: r.get('as_of') or ''):
        latest[r['series_id']] = r
    series_cat = {sid: r.get('category') for sid, r in latest.items()}

    def series_cell(sid, label=None):
        r = latest.get(sid)
        if not r or r.get('value') is None:
            return None
        note = (r.get('note') or '').split('；')[0].split(';')[0].strip()
        return {'label': label or (note[:28] if note else sid), 'value': r['value'], 'unit': r.get('unit'), 'as_of': r.get('as_of'),
                'source': {'type': 'series', 'key': sid}}

    def indicator_cell(iid, label=None):
        i = indicators.get(iid)
        if not i or i.get('value') is None:
            return None
        return {'label': label or i.get('name'), 'value': i['value'], 'unit': i.get('unit'), 'as_of': i.get('as_of'),
                'source': {'type': 'indicator', 'key': iid}}

    # ---- root: the account and its five columns
    a = economics.with_preset(model, 'baseline')
    out = economics.compute(a, model)
    # 三级账角标：每级账的模型输入按证据状态计数（成本侧 / 收入侧 / 回报取全部，按因子树的 side）
    side_inputs = {}
    for f in factors_doc['factors']:
        pool = side_inputs.setdefault(f['side'], set())
        pool.update(f.get('model_inputs', []))
        for e in f.get('fetch', []):
            pool.update(e.get('model_inputs') or [])
    ACCOUNT_SIDES = {'cost_per_mw': ('cost',), 'revenue_per_mw': ('revenue',), 'roic': ('cost', 'revenue', 'capital', 'time')}
    def evidence_of(keys):
        counts = {'sourced': 0, 'assumed': 0, 'input': 0}
        for k in keys:
            s = model.get('evidence', {}).get(k, {}).get('status')
            if s in counts:
                counts[s] += 1
        return {**counts, 'inputs': len(keys)}
    account = {'scenario': model['presets']['baseline']['label'], 'model': rules['root']['account']['model'],
               'rows': [{**row, 'value': round(out[row['key']], 3),
                         'evidence': evidence_of(sorted(set().union(*(side_inputs.get(s, set()) for s in ACCOUNT_SIDES.get(row['key'], ())))))}
                        for row in rules['root']['account']['rows']],
               'links': rules['root']['account']['links'], 'readings': rules['root'].get('readings', [])}
    root_cells = {}
    for col, specs in rules['root']['cells'].items():
        items = []
        for spec in specs:
            if spec['source'] == 'model_input':
                value = a.get(spec['key'])
                items.append({'label': spec['label'], 'value': _fmt_input(spec['key'], value, spec.get('unit')), 'unit': spec.get('unit'),
                              'as_of': model.get('as_of'), 'source': {'type': 'model_input', 'key': spec['key']}})
            elif spec['source'] == 'model_output':
                items.append({'label': spec['label'], 'value': round(out[spec['key']], 3), 'unit': spec.get('unit'),
                              'as_of': model.get('as_of'), 'source': {'type': 'model_output', 'key': spec['key']}})
            elif spec['source'] == 'indicator':
                cell = indicator_cell(spec['key'], spec['label'])
                items.append(cell or {'label': spec['label'], 'value': None, 'unit': spec.get('unit'), 'as_of': None,
                                      'source': {'type': 'indicator', 'key': spec['key']}})
        # a root cell is only as good as the evidence behind its model inputs
        ev = model.get('evidence', {})
        statuses = set()
        for i in items:
            if i['value'] is None:
                continue
            if i['source']['type'] == 'model_input':
                statuses.add(ev.get(i['source']['key'], {}).get('status', 'assumed'))
            else:
                statuses.add('sourced')
        root_cells[col] = {'items': items, 'status': ('sourced' if 'sourced' in statuses else 'assumed' if 'assumed' in statuses
                                                      else 'registered' if 'input' in statuses else 'needed')}

    # ---- targets coverage per (owner node, column)
    coverage = {}
    for t in targets_doc['targets']:
        keys = []
        if t['part_id']:
            keys.append('part:' + t['part_id'])
        if t['site_right_id']:
            keys.append('site:' + t['site_right_id'])
        if t['origin'] == 'factor':
            keys.append('root')
        for k in keys:
            coverage.setdefault((k, str(t['variable_class'])), {'sourced': 0, 'assumed': 0, 'delivered': 0, 'needed': 0})[t['status']] += 1

    def cov_sum(keys, col):
        total = {'sourced': 0, 'assumed': 0, 'delivered': 0, 'needed': 0}
        for k in keys:
            for s, n in coverage.get((k, col), {}).items():
                total[s] += n
        return total

    def status_of(items, cov):
        """Honesty rule: counts registered by us (parts, product lines, suppliers) are 'registered', never 'sourced'."""
        if any(i['value'] is not None and i.get('kind') != 'count' for i in items):
            return 'sourced'
        if cov['sourced'] or cov['assumed']:
            return 'assumed'
        if cov['delivered']:
            return 'delivered'
        return 'registered' if any(i.get('kind') == 'count' and i['value'] for i in items) else 'needed'

    # ---- parts
    prod_lines = {}
    for r in products:
        for pid in r.get('bom_parts') or []:
            prod_lines.setdefault(pid, []).append(f"{companies.get(r['company_id'], r['company_id'])} · {r['product_line']}")
    pr = rules['part']
    parts = {}
    for p in bom['parts']:
        cells = {}
        lines = prod_lines.get(p['id'], [])
        cells['1'] = {'items': [{'label': pr['1']['label'], 'value': len(lines), 'unit': pr['1']['unit'], 'as_of': bom.get('updated'),
                                 'source': {'type': 'bom', 'key': p['id']}, 'kind': 'count'},
                                {'label': '尺度', 'value': p['layer'] or p['kind'], 'unit': None, 'as_of': bom.get('updated'), 'source': {'type': 'bom', 'key': 'layer'}}],
                      'instances': lines[:12]}
        run_items = [c for c in (indicator_cell(i) for i in p['indicators'] if any(m in i for m in pr['2']['match'])) if c]
        cells['2'] = {'items': run_items}
        price_items = [c for c in (series_cell(s) for s in p['series'] if series_cat.get(s) not in pr['3']['exclude_categories']) if c]
        price_items += [c for c in (indicator_cell(i) for i in p['indicators'] if any(m in i for m in pr['3']['indicator_match'])) if c]
        cells['3'] = {'items': price_items}
        lead_items = [c for c in (series_cell(s) for s in p['series'] if series_cat.get(s) in pr['4']['categories']) if c]
        lead_items += [c for c in (indicator_cell(i) for i in p['indicators'] if any(m in i for m in pr['4']['indicator_match'])) if c]
        cells['4'] = {'items': lead_items}
        cells['5'] = {'items': [{'label': pr['5']['label'], 'value': len(p['companies']), 'unit': pr['5']['unit'], 'as_of': bom.get('updated'),
                                 'source': {'type': 'bom', 'key': 'companies'}, 'kind': 'count'}],
                      'instances': [companies.get(c, c) for c in p['companies']][:12]}
        for col in cells:
            cov = cov_sum(['part:' + p['id']], col)
            cells[col]['coverage'] = cov
            cells[col]['status'] = status_of(cells[col]['items'], cov)
        parts[p['id']] = {'id': p['id'], 'name': p['name'], 'kind': p['kind'], 'layer': p['layer'], 'system': p['system'],
                          'chain': p.get('chain'), 'chain_order': p.get('chain_order'),
                          'stage': p.get('stage'), 'module': p['module'], 'supply_status': p['status'], 'desc': p['desc'], 'cells': cells}

    # ---- site rights
    sr = rules['site_right']
    rights_out = {}
    for r in rights:
        cells = {}
        for col in ('3', '4', '5'):
            if col == '3':
                items = [c for c in (series_cell(s) for s in r.get('series', [])) if c]
            elif col == '4':
                items = [c for c in (indicator_cell(i) for i in r.get('indicators', []) if any(m in i for m in sr['4']['match'])) if c]
            else:
                items = [{'label': sr['5']['label'], 'value': len(r.get('companies', [])), 'unit': sr['5']['unit'], 'as_of': as_of,
                          'source': {'type': 'site_rights', 'key': 'companies'}, 'kind': 'count'}]
            cov = cov_sum(['site:' + r['id']], col)
            cells[col] = {'items': items, 'coverage': cov, 'status': status_of(items, cov),
                          'instances': [companies.get(c, c) for c in r.get('companies', [])] if col == '5' else []}
        rights_out[r['id']] = {'id': r['id'], 'name': r['name'], 'scale': r['scale'], 'module': r['module'], 'variable_classes': r['variable_classes'],
                               'supply_status': r['status'], 'desc': r['desc'], 'cells': cells}

    # ---- systems (aggregate over their parts)
    er = rules['system']
    system_nodes = []
    systems = bom['systems']
    def sysname(sid):
        s = systems[sid]; return s['name'] if isinstance(s, dict) else s
    leaf_ids = [sid for sid, s in systems.items() if not any(isinstance(x, dict) and x.get('parent') == sid for x in systems.values())]
    def sys_key(sid):
        s = systems[sid]
        if not isinstance(s, dict):
            return (99, 0)
        return (systems[s['parent']]['order'], s['order']) if s.get('parent') else (s['order'], 0)
    def chain_key(p):
        s = systems.get(p['system'], {})
        chains = s.get('chains', []) if isinstance(s, dict) else []
        return (chains.index(p['chain']) if p.get('chain') in chains else 99, p.get('chain_order', 99))
    for sys_id in sorted(leaf_ids, key=sys_key):
        sys_name = sysname(sys_id)
        sdef = systems[sys_id] if isinstance(systems[sys_id], dict) else {}
        members = sorted([p for p in bom['parts'] if p['system'] == sys_id], key=chain_key)
        physical = [p for p in members if p['kind'] == 'part']
        keys = ['part:' + p['id'] for p in members]
        cells = {}
        cells['1'] = {'items': [{'label': er['1']['label'], 'value': len(physical), 'unit': er['1']['unit'], 'as_of': bom.get('updated'),
                                 'source': {'type': 'count', 'key': 'parts'}, 'kind': 'count'}]}
        spec = er['2']['by_system'].get(sys_id)
        cells['2'] = {'items': [c for c in [series_cell(spec['series'], spec['label']) if spec else None] if c]}
        spec = er['3']['by_system'].get(sys_id)
        items = []
        if spec:
            basis = a.get(spec['basis'])
            if basis is not None:
                basis = basis * spec.get('scale', 1)   # e.g. IT capex is registered in $/kW, the column reads $M/MW
            share = None
            if 'share_series' in spec and latest.get(spec['share_series']):
                share = latest[spec['share_series']]['value'] / 100
                src = {'type': 'sum_share', 'key': f"{spec['basis']} × {spec['share_series']}"}
                when = latest[spec['share_series']].get('as_of')
            elif 'share_input' in spec:
                share = a.get(spec['share_input'])
                src = {'type': 'sum_share', 'key': f"{spec['basis']} × {spec['share_input']}"}
                when = model.get('as_of')
            if basis is not None and share is not None:
                items.append({'label': er['3']['label'], 'value': round(basis * share, 2), 'unit': er['3']['unit'], 'as_of': when, 'source': src})
        cells['3'] = {'items': items}
        lead = [(i['value'], i, p['id']) for p in members for i in parts[p['id']]['cells']['4']['items'] if isinstance(i['value'], (int, float))]
        if lead:
            v, i, pid = max(lead, key=lambda x: x[0])
            cells['4'] = {'items': [{'label': er['4']['label'] + '（' + parts[pid]['name'] + '）', 'value': v, 'unit': i['unit'], 'as_of': i['as_of'],
                                     'source': {'type': 'max', 'key': i['source']['key']}}]}
        else:
            cells['4'] = {'items': []}
        suppliers = {c for p in members for c in p['companies']}
        single = [p['name'] for p in physical if len(p['companies']) <= 1]
        cells['5'] = {'items': [{'label': er['5']['label'], 'value': len(suppliers), 'unit': er['5']['unit'], 'as_of': bom.get('updated'),
                                 'source': {'type': 'count', 'key': 'companies'}, 'kind': 'count'},
                                {'label': '单一来源部件', 'value': len(single), 'unit': '个', 'as_of': bom.get('updated'),
                                 'source': {'type': 'count', 'key': 'single_source'}, 'kind': 'count'}],
                      'instances': single[:12]}
        for col in cells:
            cov = cov_sum(keys, col)
            cells[col]['coverage'] = cov
            cells[col]['status'] = status_of(cells[col]['items'], cov)
        system_nodes.append({'id': sys_id, 'name': sys_name, 'node_id': 'system:' + sys_id,
                           'parent': sdef.get('parent'), 'chains': sdef.get('chains', []),
                           'cells': cells, 'parts': [{'id': p['id'], 'name': p['name'], 'kind': p['kind'], 'layer': p['layer'], 'supply_status': p['status'],
                                                      'chain': p.get('chain'), 'chain_order': p.get('chain_order'), 'stage': p.get('stage')} for p in members]})
    # parent systems (IT): one aggregate row over their children, so the matrix can show five systems and expand IT into four
    parents = []
    for pid, pdef in systems.items():
        if not isinstance(pdef, dict) or pid in leaf_ids:
            continue
        kids = [e for e in system_nodes if e['parent'] == pid]
        cells = {}
        for col in ('1', '2', '3', '4', '5'):
            items = []
            if col == '1':
                items = [{'label': '部件数', 'value': sum(i['value'] for e in kids for i in e['cells']['1']['items'] if i['label'] == '部件数'), 'unit': '个', 'as_of': bom.get('updated'), 'source': {'type': 'count', 'key': 'parts'}, 'kind': 'count'}]
            elif col == '3':
                vals = [i for e in kids for i in e['cells']['3']['items'] if isinstance(i['value'], (int, float))]
                if vals:
                    items = [{'label': '每 MW 造价（子系统之和）', 'value': round(sum(i['value'] for i in vals), 2), 'unit': vals[0]['unit'], 'as_of': max(i['as_of'] or '' for i in vals), 'source': {'type': 'sum', 'key': 'children'}}]
            elif col == '4':
                vals = [i for e in kids for i in e['cells']['4']['items'] if isinstance(i['value'], (int, float))]
                if vals:
                    top = max(vals, key=lambda i: i['value']); items = [{**top, 'source': {'type': 'max', 'key': 'children'}}]
            elif col == '5':
                sup = {c for e in kids for p in bom['parts'] if p['system'] == e['id'] for c in p['companies']}
                items = [{'label': '供应商数', 'value': len(sup), 'unit': '家', 'as_of': bom.get('updated'), 'source': {'type': 'count', 'key': 'companies'}, 'kind': 'count'}]
            else:
                items = [i for e in kids for i in e['cells']['2']['items']][:1]
            cov = {'sourced': 0, 'assumed': 0, 'delivered': 0, 'needed': 0}
            for e in kids:
                for s, n in e['cells'][col]['coverage'].items():
                    cov[s] += n
            cells[col] = {'items': items, 'coverage': cov, 'status': status_of(items, cov)}
        parents.append({'id': pid, 'name': pdef['name'], 'node_id': 'system:' + pid, 'parent': None, 'order': pdef['order'], 'chains': [],
                        'children': [e['id'] for e in kids], 'cells': cells})
    # site rights row, alongside the systems
    keys = ['site:' + r['id'] for r in rights]
    site_cells = {}
    for col in ('1', '2', '3', '4', '5'):
        items = []
        if col == '1':
            items = [{'label': '权利条目', 'value': len(rights), 'unit': '条', 'as_of': as_of, 'source': {'type': 'count', 'key': 'rights'}, 'kind': 'count'}]
        elif col in ('3', '4'):
            items = [i for r in rights for i in rights_out[r['id']]['cells'][col]['items']]
            if col == '4' and items:
                top = max((i for i in items if isinstance(i['value'], (int, float))), key=lambda i: i['value'], default=None)
                items = [top] if top else []
        elif col == '5':
            holders = {c for r in rights for c in r.get('companies', [])}
            items = [{'label': '登记持有方', 'value': len(holders), 'unit': '家', 'as_of': as_of, 'source': {'type': 'count', 'key': 'companies'}, 'kind': 'count'}]
        cov = cov_sum(keys, col)
        site_cells[col] = {'items': items, 'coverage': cov, 'status': status_of(items, cov)}
    site_row = {**RIGHTS_ROW, 'node_id': 'site', 'cells': site_cells,
                'rights': [{'id': r['id'], 'name': r['name'], 'supply_status': r['status'], 'variable_classes': r['variable_classes'], 'stage': r.get('stage')} for r in rights]}

    for col in root_cells:
        root_cells[col]['coverage'] = cov_sum(['root'], col)

    # ---- changes: newest series points and targets due soon
    n_points = rules['changes']['series_points']
    # forecast points (as_of in the future) are not 'what changed'
    newest = sorted((r for r in latest.values() if (r.get('as_of') or '') <= as_of), key=lambda r: r.get('as_of') or '', reverse=True)[:n_points]
    due_limit = (base_day + dt.timedelta(days=rules['changes']['due_within_days'])).isoformat()
    due = sorted((t for t in targets_doc['targets'] if t.get('next_due') and t['next_due'] <= due_limit and t['status'] not in ('sourced', 'delivered')),
                 key=lambda t: (t['next_due'], t['id']))
    changes = {'series_points': [{'series_id': r['series_id'], 'value': r.get('value'), 'unit': r.get('unit'), 'as_of': r.get('as_of'), 'module': r.get('module')} for r in newest],
               'due_targets': [{'id': t['id'], 'team': t['team'], 'next_due': t['next_due'], 'status': t['status'], 'variable_class': t['variable_class']} for t in due[:40]],
               'due_total': len(due)}

    # factor index for panel 3
    factors = [{'id': f['id'], 'label': f['label'], 'side': f['side'], 'parent': f['parent'], 'unit': f.get('unit'), 'formula': f.get('formula'),
                'bom_parts': f.get('bom_parts', []), 'site_rights': f.get('site_rights', []), 'model_inputs': f.get('model_inputs', [])}
               for f in factors_doc['factors']]
    totals = {'sourced': 0, 'assumed': 0, 'delivered': 0, 'needed': 0}
    for t in targets_doc['targets']:
        totals[t['status']] += 1
    totals['not_connected'] = sum(1 for t in targets_doc['targets'] if t.get('team_state') == 'not_connected')
    return {
        'version': '1.0', 'updated': as_of, 'title': '数据中心 dashboard 快照',
        'stages': bom.get('stages', []),
        'note': '由 python3 manage.py dashboard --refresh 生成，规则见 framework/dashboard_rules.json；页面 node.html 只读本文件与目标清单，不做聚合。',
        'generated_from': {'rules': rules['version'], 'bom': bom.get('version'), 'targets': targets_doc.get('version'), 'factors': factors_doc.get('version'),
                           'model_as_of': model.get('as_of')},
        'columns': rules['columns'], 'formulas': factors_doc.get('formulas', {}),
        'root': {'id': 'root', 'name': '一座 AI 数据中心', 'account': account, 'cells': root_cells, 'targets': totals},
        'systems': {sid: (s if isinstance(s, dict) else {'name': s}) for sid, s in systems.items()},
        'system_nodes': system_nodes, 'parent_systems': sorted(parents, key=lambda x: x['order']), 'site': site_row, 'parts': parts, 'rights': rights_out, 'factors': factors, 'changes': changes,
    }


def render(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--refresh', action='store_true', help='rewrite ' + SNAPSHOT)
    ap.add_argument('--check', action='store_true', help='fail when ' + SNAPSHOT + ' differs from its inputs (default)')
    ap.add_argument('--as-of')
    args = ap.parse_args(argv)
    doc = build(ROOT, args.as_of)
    text = render(doc)
    path = ROOT / SNAPSHOT
    if args.refresh:
        path.write_text(text, encoding='utf-8')
    elif not path.exists() or path.read_text(encoding='utf-8') != text:
        print(f'ERROR: {SNAPSHOT}: stale or missing; run manage.py dashboard --refresh')
        return 1
    acct = {r['label']: r['value'] for r in doc['root']['account']['rows']}
    print(f"Dashboard {doc['version']} @ {doc['updated']}: {len(doc['system_nodes'])} systems + site, {len(doc['parts'])} parts, "
          f"{len(doc['rights'])} rights; account {acct}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
