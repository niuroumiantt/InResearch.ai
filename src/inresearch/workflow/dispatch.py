"""派工按目标行 ID（03「协作」、06、提案 §5，2026-09-28）。

目标表 ``framework/tco_targets.json`` 是唯一任务书；这里只做两件事：按角色与筛选把目标行连同派工状态投影给
采集页（``/api/targets``，实习生只见分配给自己的行——在服务端过滤，不只在前端隐藏），以及把"谁领了、交付了什么"
登记到 ``data/assignments.json``（``assign`` 带 ``target_id``；``register_delivery`` 记交付指针）。交付指针只是
运行库里的登记，一行进不进 ``delivered`` 由 Git 内载体决定（``knowledge/targets.py``），页面标"运行库有 / Git 无"。
"""
import json
from datetime import date
from pathlib import Path

from inresearch.knowledge import deliveries
from inresearch.storage.files import json_transaction
from inresearch.storage.layout import workspace_path

TARGETS = 'framework/tco_targets.json'
ASSIGNMENTS = 'data/assignments.json'


class Rejected(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def target_doc(root):
    return json.loads((Path(root) / TARGETS).read_text(encoding='utf-8'))


def target_ids(root):
    return {t['id'] for t in target_doc(root)['targets']}


def assignments(root):
    path = workspace_path(ASSIGNMENTS, root)
    if not path.exists():
        return {'records': []}
    return json.loads(path.read_text(encoding='utf-8'))


def node_of(row):
    if row.get('part_id'):
        return 'part:' + row['part_id']
    if row.get('site_right_id'):
        return 'site:' + row['site_right_id']
    return 'root'


def targets_view(root, user, role, params=None):
    """目标行 + 派工状态。实习生强制 mine；筛选：team、node（部件、权利或系统）、col（变量类）、status、q。"""
    params = params or {}
    root = Path(root)
    doc = target_doc(root)
    by_target = {r['target_id']: r for r in assignments(root)['records'] if r.get('target_id')}
    cards = {}
    for c in deliveries.load_cards(root).get('records', []):
        if c.get('target_id') and c.get('origin_pointer'):
            cards.setdefault(c['target_id'], []).append({k: c.get(k) for k in ('origin_pointer', 'pointer_kind', 'delivered_at',
                                                                               'delivered_by', 'parameters') if c.get(k)})
    mine = params.get('mine') == '1' or role == 'intern'
    systems = {}
    bom_path = root / 'framework/bom.json'
    if bom_path.exists():
        bom = json.loads(bom_path.read_text(encoding='utf-8'))
        for p in bom['parts']:
            s = bom['systems'].get(p['system'], {})
            systems[p['id']] = [p['system']] + ([s['parent']] if isinstance(s, dict) and s.get('parent') else [])
    want_node = params.get('node') or ''
    rows = []
    for t in doc['targets']:
        row = dict(t)
        row['node'] = node_of(t)
        row['assignment'] = by_target.get(t['id'])
        row['cards'] = cards.get(t['id'], [])          # Git 内交付载体：原件指针与随交付带来的已审阅参数原文
        if mine and not (row['assignment'] and row['assignment'].get('assignee') == user):
            continue
        if params.get('team') and t['team'] != params['team']:
            continue
        if params.get('col') and str(t['variable_class']) != str(params['col']):
            continue
        if params.get('status') and t['status'] != params['status']:
            continue
        if want_node:
            if want_node.startswith('system:'):
                if want_node[7:] not in systems.get(t.get('part_id') or '', []):
                    continue
            elif want_node != row['node']:
                continue
        rows.append(row)
    return {'version': doc['version'], 'updated': doc['updated'], 'teams': doc['teams'], 'statuses': doc['statuses'],
            'counts': doc['counts'], 'total': len(doc['targets']), 'mine': mine, 'user': user or None, 'role': role,
            'targets': rows}


def register_delivery(root, rec, by='', role='admin'):
    """登记一次交付：目标行 ID + 证据路径（仓库内相对路径或 URL）。只写运行库的派工文件，不改目标表。"""
    tid = str(rec.get('target_id') or '').strip()
    path = str(rec.get('evidence_path') or '').strip()
    if not tid:
        raise Rejected('缺 target_id')
    if not path or '..' in path.split('/') or path.startswith('/'):
        raise Rejected('evidence_path 须是仓库内相对路径或 URL')
    if tid not in target_ids(root):
        raise Rejected(tid + ' 不在当前目标表里，请刷新', 404)
    today = date.today().isoformat()
    with json_transaction(workspace_path(ASSIGNMENTS, root)) as doc:
        doc.setdefault('records', [])
        row = next((r for r in doc['records'] if r.get('target_id') == tid), None)
        if role == 'intern':
            if not by or not row or row.get('assignee') != by:
                raise Rejected('只能登记分配给自己的目标行的交付', 403)
        if row is None:
            row = {'target_id': tid, 'assignee': by or None, 'assigned': today}
            doc['records'].append(row)
        row['status'] = '已交付'
        row['delivery'] = {'evidence_path': path, 'at': today, 'by': by or None, 'note': str(rec.get('note') or '')[:500]}
        row['updated'] = today
        if by:
            row['by'] = by
        doc['updated'] = today
    return {'ok': True, 'msg': f'{tid} 已登记交付：{path}。这是运行库的指针；进入 delivered 要有 Git 内载体（资料计划、事件卡或带 target_id 的价格记录）。'}
