"""Supply planning authority; no collector execution or evidence adoption here."""
import json
import uuid
from datetime import datetime, timezone
from inresearch.storage.layout import workspace_path
from inresearch.storage.files import locked, write_json


class Conflict(ValueError):
    pass


def catalog(root):
    return json.loads((root / 'framework/supply_contract.json').read_text())


def ledger_path(root):
    # Already-declared private runtime prefix; no storage migration or new seed.
    return workspace_path('data/raw/supply-center/ledger.json', root)


def read(root):
    path = ledger_path(root)
    if not path.exists():
        return {'version': 1, 'revision': 0, 'demands': [], 'tasks': [], 'operations': []}
    value = json.loads(path.read_text())
    if (value.get('version') != 1 or type(value.get('revision')) is not int
            or any(not isinstance(value.get(k), list) for k in ('demands', 'tasks', 'operations'))):
        raise ValueError('供应台账损坏，请修复；不会重建或覆盖')
    return value


def snapshot(root):
    state = read(root)
    questions = json.loads((root / 'framework/research_questions.json').read_text())['records']
    return {'catalog': catalog(root), 'revision': state['revision'],
            'demands': state['demands'], 'tasks': state['tasks'],
            'questions': [{'id': q['id'], 'text': q['text'], 'object_ids': q.get('object_ids', [])} for q in questions],
            'delivery_connection': 'not_connected'}


def text(payload, key, limit):
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('字段缺失或过长：' + key)
    return value.strip()


def mutate(root, payload, actor):
    operation_id = text(payload, 'operation_id', 36)
    try:
        uuid.UUID(operation_id)
    except ValueError:
        raise ValueError('无效操作身份') from None
    if type(payload.get('expected_revision')) is not int:
        raise ValueError('缺少台账版本')
    action = payload.get('action')
    if action not in ('create', 'assign'):
        raise ValueError('不支持的供应操作')
    providers = {p['id'] for p in catalog(root)['providers']}
    provider = payload.get('provider_id', '')
    if not isinstance(provider, str) or (provider and provider not in providers):
        raise ValueError('供应方不存在')
    if action == 'assign' and not provider:
        raise ValueError('请选择供应方')
    fingerprint = json.dumps({k:v for k,v in payload.items() if k != 'expected_revision'}, sort_keys=True, ensure_ascii=False)
    with locked(ledger_path(root)):
        state = read(root)
        previous = next((x for x in state['operations'] if x['id'] == operation_id), None)
        if previous:
            if previous['request'] != fingerprint or previous['actor'] != actor:
                raise Conflict('操作身份已用于其他请求')
            return {'ok': True, 'replayed': True, 'revision': state['revision']}
        if payload['expected_revision'] != state['revision']:
            raise Conflict('台账已变化，请刷新后再提交')
        now = datetime.now(timezone.utc).isoformat()
        if action == 'create':
            question_id = text(payload, 'question_id', 120)
            questions = json.loads((root / 'framework/research_questions.json').read_text())['records']
            question = next((q for q in questions if q['id'] == question_id), None)
            if not question:
                raise ValueError('请选择已登记研究问题')
            demand = {'id': 'demand-' + operation_id, 'question_id': question_id,
                      'object_ids': question.get('object_ids', []),
                      'title': text(payload, 'title', 300), 'scope': text(payload, 'scope', 3000),
                      'acceptance': text(payload, 'acceptance', 3000),
                      'created_at': now, 'created_by': actor}
            state['demands'].append(demand)
        else:
            demand = next((d for d in state['demands'] if d['id'] == payload.get('demand_id')), None)
            if not demand:
                raise ValueError('需求不存在')
        if provider:
            if any(t['demand_id'] == demand['id'] and t['provider_id'] == provider for t in state['tasks']):
                raise Conflict('该供应方已有本需求任务')
            state['tasks'].append({'id': 'task-' + operation_id, 'demand_id': demand['id'],
                                   'provider_id': provider, 'status': 'planned',
                                   'created_at': now, 'created_by': actor})
        state['revision'] += 1
        state['operations'].append({'id': operation_id, 'request': fingerprint, 'actor': actor, 'at': now})
        write_json(ledger_path(root), state)
        return {'ok': True, 'revision': state['revision']}
