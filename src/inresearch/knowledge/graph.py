"""研究图谱 3.0：由骨架生成，不手写（00「机器执行入口」、提案 §7，2026-09-28）。

对象只有六种：根、系统（五个顶层，IT 三分、存储再分内存与持久存储）、链路、部件（61 + 软件 + 基型）、站点权利、主体（公司）。
来源是 ``framework/bom.json``、``framework/site_rights.json``、``data/companies.json``；``python3 manage.py graph --refresh``
重生成 ``framework/research_graph.json``，并给 ``framework/research_questions.json`` 的每条问题打 ``node`` 与
``variable_class``（问题 ID 不变，M4 的深读按问题 ID 回写不失效）。``--check`` 核对两个文件与生成结果一致。

退役的对象家族（scope:M01–M15、ecosystem、arch、tech、workload、demand、activity、space、system:safety）与
被重切的旧部件 ID 在 ``LEGACY_NODES`` 与 bom.json 的 aliases 里登记去处：接收端拿旧快照时按这张表折算到骨架节点，
旧 ID 不再是对象。五视角、导航树、生态目录、九主题不再存在。
"""
import argparse
from inresearch.knowledge.skeleton import system_path, system_key
import json
from pathlib import Path

from inresearch.paths import project_root

ROOT = project_root()
GRAPH = 'framework/research_graph.json'
QUESTIONS = 'framework/research_questions.json'
VERSION = '3.0.0'
KINDS = {'root': '数据中心（根）', 'system': '系统（五个顶层，IT 三分、存储再分两类）', 'chain': '系统内的能量流链路', 'part': '部件（含软件条目与设施基型）',
         'site_right': '站点权利（园区之外并列的六条）', 'actor': '主体（公司）'}
RELATIONS = {'part_of': '骨架的包含关系：部件 → 链路 → 系统 → 根；权利 → 根；子系统 → 父系统',
             'supplies': '主体供应部件（bom.json companies）', 'holds': '主体持有站点权利（site_rights.companies，登记数）'}
# 退役对象家族 → 骨架节点。旧问题表与旧快照里的 ID 按此折算；旧部件 ID 另按 bom.json aliases。
LEGACY_NODES = {
    'system:safety': 'system:facility', 'space:site': 'system:facility', 'space:building': 'system:facility', 'space:hall': 'system:facility',
    'space:row': 'system:facility',
    'ecosystem:facility': 'system:facility', 'ecosystem:power': 'system:power', 'ecosystem:thermal': 'system:thermal',
    'ecosystem:compute': 'system:compute', 'ecosystem:memory': 'system:memory', 'ecosystem:storage': 'system:storage',
    'ecosystem:network': 'system:network', 'ecosystem:control': 'system:control',
    'arch:x86': 'part:cpu', 'arch:arm': 'part:cpu', 'arch:risc-v': 'part:cpu', 'arch:other-cpu': 'part:cpu',
    'arch:nvidia-gpu': 'part:gpu', 'arch:amd-gpu': 'part:gpu', 'arch:other-gpu': 'part:gpu', 'arch:hopper': 'part:gpu',
    'arch:blackwell': 'part:gpu', 'arch:cdna': 'part:gpu', 'arch:rdna': 'part:gpu', 'tech:gpu-memory': 'part:hbm',
    'part:ssd-drive': 'part:ssd', 'part:nand': 'part:ssd', 'part:ssd-controller': 'part:ssd', 'part:ssd-board': 'part:ssd',
    'software:ssd-firmware': 'part:ssd', 'tech:nand-cell': 'part:ssd', 'tech:nand-process': 'part:ssd',
    'tech:storage-access': 'part:storage-array', 'tech:storage-protocol': 'part:storage-array', 'software:storage': 'part:storage-array',
    'part:lpddr': 'part:dram', 'part:gddr': 'system:memory', 'part:gpu-device': 'part:gpu', 'part:immersion': 'part:immersion',
    'part:dcim': 'part:dcim',
}
LEGACY_ROOT_PREFIXES = ('scope:', 'workload:', 'demand:', 'activity:')   # 兼容模块、工作负载、需求、活动：挂根，作收入侧的属性
# 问题的变量类：先看文本关键词（顺序即优先级），没有命中的是构成（1）。可在 QUESTION_CLASS_OVERRIDES 逐条改。
CLASS_KEYWORDS = [
    ((' 价格', '价格', '成本', '造价', '租金', '电价', '费率', '资本开支', '单价', '估值', '利润', '营收', '收入', '融资', '回报', '账', '定价', '溢价', '折旧'), 3),
    (('交期', '年限', '周期', '工期', '寿命', '排队', '时长', '何时', '多久', '时间表', '节奏', '几年'), 4),
    (('谁', '厂商', '供应商', '份额', '持有', '格局', '竞争', '客户', '买家', '主体', '集中度', '玩家', '阵营', '进入者', '租户'), 5),
    (('PUE', 'WUE', '利用率', '效率', '功耗', '运行', '故障', '负载', '上架', '爬坡', '吞吐', '可用性', '能耗', '用电量'), 2),
]
QUESTION_CLASS_OVERRIDES = {}


def _load(root, rel):
    return json.loads((Path(root) / rel).read_text(encoding='utf-8'))


def _dump(path, doc):
    Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def node_for(object_id, bom):
    """任一（新或旧）对象 ID → 骨架节点 ID；无法折算时返回 None。"""
    parts = {p['id'] for p in bom['parts']}
    systems = {k for k, v in bom['systems'].items() if isinstance(v, dict)}
    kind, _, ident = object_id.partition(':')
    if object_id == 'root' or object_id.startswith(LEGACY_ROOT_PREFIXES):
        return 'root'
    if object_id in LEGACY_NODES:
        return LEGACY_NODES[object_id]
    if kind == 'part':
        if ident in parts:
            return object_id
        alias = bom.get('aliases', {}).get(ident)
        if alias:
            return alias if alias.startswith('site:') else 'part:' + alias
        return None
    if kind == 'system':
        return object_id if ident in systems else None
    if kind in ('site', 'actor', 'chain'):
        return object_id
    return None


def question_class(record):
    if record['id'] in QUESTION_CLASS_OVERRIDES:
        return QUESTION_CLASS_OVERRIDES[record['id']]
    text = record.get('text') or ''
    for keys, cls in CLASS_KEYWORDS:
        if any(k in text for k in keys):
            return cls
    return 1


def question_node(record, bom, rights):
    """最具体的骨架引用胜出：部件 > 权利 > 系统 > 根。"""
    nodes = [node_for(o, bom) for o in record.get('object_ids', [])]
    nodes = [n for n in nodes if n]
    for prefix in ('part:', 'site:', 'system:'):
        hit = [n for n in nodes if n.startswith(prefix)]
        if hit:
            return sorted(hit)[0]
    return 'root'


def build(root=ROOT):
    bom = _load(root, 'framework/bom.json')
    rights = _load(root, 'framework/site_rights.json')['rights']
    companies = _load(root, 'data/companies.json')['records']
    systems = {k: v for k, v in bom['systems'].items() if isinstance(v, dict)}
    names = {c['company_id']: c.get('name_cn') or c.get('name') or c['company_id'] for c in companies}
    objects, relations = [], []

    def rel(kind, source, target, **extra):
        relations.append({'id': f'{kind}:{source}>{target}', 'type': kind, 'source': source, 'target': target, 'representation': 'conceptual', **extra})

    objects.append({'id': 'root', 'name': '一座 AI 数据中心', 'kind': 'root', 'parent': None, 'representation': 'conceptual',
                    'description': '树的根：五个系统与站点权利是第一层分叉；三级账挂在这里。'})
    aliases_of = {}
    for old, target in bom.get('aliases', {}).items():
        aliases_of.setdefault(target if target.startswith('site:') else 'part:' + target, []).append('part:' + old)
    for old, target in LEGACY_NODES.items():
        if old != target:
            aliases_of.setdefault(target, []).append(old)
    top = sorted((s for s in systems if not systems[s].get('parent')), key=lambda s: systems[s]['order'])
    kids = lambda s: sorted((k for k in systems if systems[k].get('parent') == s), key=lambda k: systems[k]['order'])
    for sid in sorted(systems, key=lambda sid: system_key(systems, sid)):
        parent = 'system:' + systems[sid]['parent'] if systems[sid].get('parent') else 'root'
        objects.append({'id': 'system:' + sid, 'name': systems[sid]['name'], 'kind': 'system', 'parent': parent, 'order': systems[sid]['order'],
                        'chains': systems[sid].get('chains', []), 'children': ['system:' + k for k in kids(sid)],
                        'aliases': sorted(aliases_of.get('system:' + sid, [])), 'representation': 'conceptual'})
        rel('part_of', 'system:' + sid, parent)
    for sid, s in systems.items():
        for i, chain in enumerate(s.get('chains', []), 1):
            cid = f'chain:{sid}/{i}'
            objects.append({'id': cid, 'name': chain, 'kind': 'chain', 'parent': 'system:' + sid, 'order': i, 'system': sid, 'representation': 'conceptual'})
            rel('part_of', cid, 'system:' + sid)
    chain_id = {(sid, c): f'chain:{sid}/{i}' for sid, s in systems.items() for i, c in enumerate(s.get('chains', []), 1)}
    def part_key(p):  # 顺序 = 系统顺序 × 链路顺序 × chain_order（子系统排在父系统的序号下）
        return (system_key(systems, p['system']), systems[p['system']].get('chains', []).index(p.get('chain')) if p.get('chain') in systems[p['system']].get('chains', []) else 99, p.get('chain_order') or 0)
    for p in sorted(bom['parts'], key=part_key):
        oid = 'part:' + p['id']
        cid = chain_id.get((p['system'], p.get('chain')))
        objects.append({'id': oid, 'name': p['name'], 'kind': 'part', 'parent': cid or 'system:' + p['system'], 'part_kind': p['kind'],
                        'system': p['system'], 'chain': p.get('chain'), 'chain_order': p.get('chain_order'), 'stage': p.get('stage'),
                        'scale': p.get('scale'), 'status': p['status'], 'legacy_module': p.get('legacy_module'),
                        'aliases': sorted(aliases_of.get(oid, [])), 'representation': 'conceptual', 'description': p.get('desc', '')})
        rel('part_of', oid, cid or 'system:' + p['system'])
        for c in p.get('companies', []):
            rel('supplies', 'actor:' + c, oid)
    for r in rights:
        oid = 'site:' + r['id']
        objects.append({'id': oid, 'name': r['name'], 'kind': 'site_right', 'parent': 'root', 'scale': r.get('scale'), 'stage': r.get('stage'),
                        'variable_classes': r.get('variable_classes', []), 'status': r.get('status'), 'legacy_module': r.get('legacy_module'),
                        'aliases': sorted(aliases_of.get(oid, [])), 'representation': 'conceptual', 'description': r.get('desc', '')})
        rel('part_of', oid, 'root')
        for c in r.get('companies', []):
            rel('holds', 'actor:' + c, oid, basis='registered')
    linked = {r['source'] for r in relations if r['type'] in ('supplies', 'holds')}
    for c in sorted(companies, key=lambda c: c['company_id']):
        oid = 'actor:' + c['company_id']
        objects.append({'id': oid, 'name': names[c['company_id']], 'kind': 'actor', 'parent': None, 'roles': c.get('roles', []),
                        'legacy_module': (c.get('modules') or [None])[0], 'linked': oid in linked, 'representation': 'conceptual'})
    graph = {
        'version': VERSION, 'updated': bom.get('updated'), 'kinds': KINDS, 'relation_types': RELATIONS, 'legacy_nodes': LEGACY_NODES,
        'legacy_root_prefixes': list(LEGACY_ROOT_PREFIXES),
        'note': '由 python3 manage.py graph --refresh 从 bom.json、site_rights.json、companies.json 生成，不手写。对象只有六种，退役的对象家族按 legacy_nodes 折算；'
                '五视角、导航树、生态目录与九主题不再存在。问题挂骨架节点与变量类，ID 不变。',
        'policy': {'containment_types': ['part_of'], 'representation': ['conceptual', 'reference', 'actual'],
                   'actual_assets': '目前无经核验的真实场址配置；现有 3D 为概念模板。',
                   'identity': '对象集合 = 骨架节点集合（bom.json systems / chains / parts + site_rights + companies）；顺序 = 系统顺序 × 链路顺序 × chain_order。'},
        'objects': objects, 'relations': relations,
    }
    questions = _load(root, QUESTIONS)
    retagged = []
    for q in questions['records']:
        rec = {k: v for k, v in q.items() if k not in ('views', 'topic_id', 'module_id', 'node', 'variable_class', 'legacy_module', 'legacy_object_ids')}
        legacy_ids = [o for o in q.get('object_ids', []) if node_for(o, bom) != o]
        rec['legacy_module'] = q.get('legacy_module') or q.get('module_id')
        rec['node'] = question_node(q, bom, rights)
        rec['variable_class'] = question_class(q)
        rec['object_ids'] = sorted({node_for(o, bom) or 'root' for o in q.get('object_ids', [])}) or ['root']
        if legacy_ids or q.get('legacy_object_ids'):
            rec['legacy_object_ids'] = sorted(set(q.get('legacy_object_ids', [])) | set(legacy_ids))
        retagged.append(rec)
    qdoc = {**questions, 'version': VERSION, 'updated': bom.get('updated'), 'records': retagged,
            'policy': 'ID 固定；每条问题挂骨架节点（node）与变量类（variable_class），object_ids 只允许骨架 ID，旧 ID 留在 legacy_object_ids；'
                      'module_id 改 legacy_module。对象专属问题不通过同模块材料或父节点材料自动关闭。'}
    return graph, qdoc


def validate(graph, bom=None, root=ROOT):
    """骨架校验：对象集合 = 骨架节点集合，顺序 = 系统顺序 × 链路顺序 × chain_order，包含关系无环、单亲。"""
    errors = []
    bom = bom or _load(root, 'framework/bom.json')
    objects = {o['id']: o for o in graph.get('objects', [])}
    if len(objects) != len(graph.get('objects', [])):
        errors.append('duplicate object ids')
    if graph.get('version', '') < '3':
        errors.append('graph must be version 3.x (generated from the skeleton)')
    expected_parts = {'part:' + p['id'] for p in bom['parts']}
    if {o for o, v in objects.items() if v['kind'] == 'part'} != expected_parts:
        errors.append('part objects must equal bom.json parts')
    systems = {k for k, v in bom['systems'].items() if isinstance(v, dict)}
    if {o[7:] for o, v in objects.items() if v['kind'] == 'system'} != systems:
        errors.append('system objects must equal bom.json systems')
    for o in objects.values():
        if o.get('kind') not in KINDS:
            errors.append(f"{o['id']}: unknown kind {o.get('kind')}")
        if o.get('representation') not in ('conceptual', 'reference', 'actual'):
            errors.append(f"{o['id']}: representation required")
        if o['kind'] not in ('root', 'actor') and o.get('parent') not in objects:
            errors.append(f"{o['id']}: parent must be a skeleton node")
    parent = {}
    for r in graph.get('relations', []):
        if r.get('source') not in objects or r.get('target') not in objects:
            errors.append(f"{r.get('id')}: dangling relation")
        if r.get('type') not in RELATIONS:
            errors.append(f"{r.get('id')}: unknown relation type")
        if r.get('type') == 'part_of':
            if r['source'] in parent:
                errors.append(f"{r['source']}: multiple parents")
            parent[r['source']] = r['target']
    for start in parent:
        seen, at = set(), start
        while at in parent:
            if at in seen:
                errors.append(f'containment cycle at {at}')
                break
            seen.add(at)
            at = parent[at]
    order = [(o['system'], o.get('chain'), o.get('chain_order')) for o in graph.get('objects', []) if o.get('kind') == 'part']
    sys_order = {k: system_key(bom['systems'], k) for k in systems}
    chain_pos = {(k, c): i for k in systems for i, c in enumerate(bom['systems'][k].get('chains', []))}
    keys = [(sys_order[s], chain_pos.get((s, c), 99), n or 0) for s, c, n in order]
    if keys != sorted(keys):
        errors.append('parts must be ordered by system order × chain order × chain_order')
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--refresh', action='store_true', help='rewrite the graph and retag the questions')
    ap.add_argument('--check', action='store_true', help='fail when the files differ from their generation (default)')
    args = ap.parse_args(argv)
    graph, qdoc = build(ROOT)
    errors = validate(graph)
    if errors:
        for e in errors:
            print('ERROR: ' + e)
        return 1
    if args.refresh:
        _dump(ROOT / GRAPH, graph)
        _dump(ROOT / QUESTIONS, qdoc)
    else:
        for rel, doc in ((GRAPH, graph), (QUESTIONS, qdoc)):
            path = ROOT / rel
            if not path.exists() or json.loads(path.read_text(encoding='utf-8')) != doc:
                print(f'ERROR: {rel}: stale or missing; run manage.py graph --refresh')
                return 1
    kinds = {}
    for o in graph['objects']:
        kinds[o['kind']] = kinds.get(o['kind'], 0) + 1
    print(f"Graph {VERSION} @ {graph['updated']}: {len(graph['objects'])} objects {kinds}, {len(graph['relations'])} relations; "
          f"{len(qdoc['records'])} questions retagged")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
