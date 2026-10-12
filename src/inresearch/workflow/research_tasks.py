"""Durable project coordination, separate from collection execution and adoption.

The published plan creates the mission and its unassigned work packages. Runtime
changes are private, revisioned and audited; HTTP callers cannot certify research
adoption or map publication through a coordination status.
"""
import copy
from datetime import date, datetime, timezone
import json
from pathlib import Path
import uuid

from inresearch.storage.files import locked, write_json
from inresearch.storage.layout import workspace_path

STATUSES = ('unassigned', 'ready', 'in_progress', 'blocked', 'delivered')
FIELDS = ('title', 'region', 'scope', 'sources', 'assignee', 'machine', 'model',
          'due', 'status', 'delivery_pointer', 'note')
LIMITS = {'title': 180, 'region': 200, 'scope': 3000, 'sources': 2000,
          'assignee': 100, 'machine': 200, 'model': 200, 'due': 10,
          'status': 30, 'delivery_pointer': 2000, 'note': 3000}


class Conflict(ValueError):
    pass


class Forbidden(ValueError):
    pass


def plan(root):
    return json.loads((Path(root) / 'framework/research_task_plan.json').read_text())


def ledger_path(root):
    return workspace_path('data/raw/research-tasks/ledger.json', root)


def read(root):
    path = ledger_path(root)
    if not path.exists():
        return {'version': 1, 'revision': 0, 'packages': copy.deepcopy(plan(root)['packages']),
                'operations': []}
    state = json.loads(path.read_text())
    if (not isinstance(state, dict) or state.get('version') != 1 or type(state.get('revision')) is not int
            or not isinstance(state.get('packages'), list)
            or not isinstance(state.get('operations'), list)
            or any(not isinstance(p, dict) or not isinstance(p.get('id'), str)
                   or not p['id'] for p in state['packages'])
            or len({p['id'] for p in state['packages']}) != len(state['packages'])
            or any(not isinstance(o, dict) or any(not isinstance(o.get(k), str)
                   for k in ('id', 'request', 'actor', 'at', 'package_id'))
                   for o in state['operations'])):
        raise ValueError('任务台账损坏；请修复，不会重建或覆盖')
    for package in state['packages']:
        _fields(package)
    return state


def snapshot(root, actor='', role='reader'):
    state = read(root)
    # Use exactly the map's existing projection and deduplication rules. These are
    # observed database totals, not a claim about worldwide coverage or live ACK.
    from inresearch.knowledge import industry
    view = industry.snapshot(root, {'overview': '1'})
    projection = {k: v for k, v in state.items() if k != 'operations'}
    if role == 'reader':
        projection = {k: state[k] for k in ('version', 'revision')}
        projection['packages'] = [{k: p.get(k) for k in ('id', 'title', 'region', 'scope', 'sources', 'status')}
                                  for p in state['packages']]
    return {**projection, 'mission': plan(root)['mission'], 'actor': actor if role != 'reader' else '', 'role': role,
            'public_view': role == 'reader',
            'can_create': role in ('admin', 'member'),
            'map_register': {'status': 'observed', 'counts': view['capacity_audit'],
                'basis': view['basis'], 'coverage': view['coverage'],
                'publication_ack': 'not_checked'}}


def _fields(payload, current=None):
    values = {}
    for key in FIELDS:
        value = payload.get(key, (current or {}).get(key, ''))
        if not isinstance(value, str) or len(value) > LIMITS[key]:
            raise ValueError('字段缺失或过长：' + key)
        values[key] = value.strip()
    if not all(values[k] for k in ('title', 'region', 'scope', 'sources')):
        raise ValueError('请填写工作包名称、地区、范围与来源方向')
    if values['status'] not in STATUSES:
        raise ValueError('无效协调状态；正式采用与地图发布由既有流程登记')
    if values['due']:
        try:
            if date.fromisoformat(values['due']).isoformat() != values['due']:
                raise ValueError()
        except ValueError:
            raise ValueError('截止日期必须是 YYYY-MM-DD') from None
    if values['status'] == 'unassigned' and values['assignee']:
        raise ValueError('已有负责人时请选择待开始或后续状态')
    if values['status'] != 'unassigned' and not values['assignee']:
        raise ValueError('请先填写实际负责人')
    if values['status'] == 'delivered' and not values['delivery_pointer']:
        raise ValueError('已交付需要可回查的交付地址或接收回执')
    if values['status'] == 'blocked' and not values['note']:
        raise ValueError('受阻时请说明缺项或阻塞原因')
    return values


def mutate(root, payload, actor, role='reader'):
    if role not in ('admin', 'member', 'intern'):
        raise Forbidden('当前角色只能查看任务')
    if not isinstance(actor, str) or not actor:
        raise Forbidden('缺少已登录的操作者')
    operation_id = payload.get('operation_id')
    try:
        if not isinstance(operation_id, str) or len(operation_id) != 36:
            raise ValueError()
        uuid.UUID(operation_id)
    except ValueError:
        raise ValueError('无效操作身份') from None
    if type(payload.get('expected_revision')) is not int:
        raise ValueError('缺少任务台账版本')
    action = payload.get('action')
    if action not in ('create', 'update'):
        raise ValueError('不支持的任务操作')
    if set(payload) - set(FIELDS) - {'action', 'operation_id', 'expected_revision', 'package_id'}:
        raise ValueError('不支持的任务字段')
    if role == 'intern' and action != 'update':
        raise Forbidden('实习生成员只能更新分配给自己的状态、交付与备注')
    fingerprint = json.dumps({k: v for k, v in payload.items() if k != 'expected_revision'},
                             sort_keys=True, ensure_ascii=False, allow_nan=False)
    with locked(ledger_path(root)):
        state = read(root)
        previous = next((o for o in state['operations'] if o['id'] == operation_id), None)
        if previous:
            if previous['request'] != fingerprint or previous['actor'] != actor:
                raise Conflict('操作身份已用于其他请求')
            return {'ok': True, 'replayed': True, 'revision': state['revision']}
        if payload['expected_revision'] != state['revision']:
            raise Conflict('其他成员已更新任务；请刷新后再保存')
        now = datetime.now(timezone.utc).isoformat()
        if action == 'create':
            values = _fields(payload)
            package = {'id': 'work-' + operation_id, **values,
                       'created_at': now, 'created_by': actor}
            state['packages'].append(package)
            before = None
        else:
            package = next((p for p in state['packages'] if p['id'] == payload.get('package_id')), None)
            if package is None:
                raise ValueError('工作包不存在')
            if role == 'intern':
                if package.get('assignee') != actor:
                    raise Forbidden('只能更新分配给自己的工作包')
                if any(k in payload and payload[k] != package.get(k, '')
                       for k in FIELDS if k not in ('status', 'delivery_pointer', 'note')):
                    raise Forbidden('实习生成员不能修改范围、负责人、机器或模型')
            values = _fields(payload, package)
            before = copy.deepcopy(package)
            package.update(values)
        package.update(updated_at=now, updated_by=actor)
        state['revision'] += 1
        state['operations'].append({'id': operation_id, 'request': fingerprint,
            'actor': actor, 'role': role, 'at': now, 'package_id': package['id'],
            'before': before, 'after': copy.deepcopy(package)})
        write_json(ledger_path(root), state)
        return {'ok': True, 'revision': state['revision'], 'package_id': package['id']}
