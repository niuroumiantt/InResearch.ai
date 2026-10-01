"""Supply planning authority; no collector execution or evidence adoption here."""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
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
    target_document = json.loads((root / 'framework/tco_targets.json').read_text())
    fetchspec_targets = [row for row in target_document['targets'] if row.get('team') == 'fetchspec']
    receipts_path = workspace_path('data/raw/supply-center/receipts.json', root)
    receipts = json.loads(receipts_path.read_text()) if receipts_path.exists() else {'version': 1, 'deliveries': {}}
    if receipts.get('version') != 1 or not isinstance(receipts.get('deliveries'), dict):
        raise ValueError('供应回执台账损坏，请修复；不会重建或覆盖')
    deliveries = list(receipts['deliveries'].values())
    _attach_reader_status(deliveries)
    return {'catalog': catalog(root), 'revision': state['revision'],
            'demands': state['demands'], 'tasks': state['tasks'],
            'questions': [{'id': q['id'], 'text': q['text'], 'object_ids': q.get('object_ids', [])} for q in questions],
            'generated_targets': {
                'source': 'framework/tco_targets.json',
                'provider_id': 'fetchspec',
                'total': len(fetchspec_targets),
                'sourced': sum(row['status'] == 'sourced' for row in fetchspec_targets),
                'assumed': sum(row['status'] == 'assumed' for row in fetchspec_targets),
                'delivered': sum(row['status'] == 'delivered' for row in fetchspec_targets),
                'needed': sum(row['status'] == 'needed' for row in fetchspec_targets),
                'records': fetchspec_targets,
            },
            'deliveries': deliveries,
            'delivery_connection': 'connected' if receipts['deliveries'] else 'awaiting_first_delivery'}


def _attach_reader_status(deliveries):
    """Read-only projection from the existing Reader catalog; never initializes it."""
    data = Path(os.environ.get('READER_DATA_ROOT', Path.home() / '.local/share/inresearch.ai')).expanduser()
    catalog_path = data / 'catalog/catalog.sqlite'
    wanted = {item.get('sha256') for delivery in deliveries for item in delivery.get('items', [])
              if isinstance(item, dict) and isinstance(item.get('sha256'), str)}
    states = {}
    if wanted and catalog_path.is_file() and not catalog_path.is_symlink():
        try:
            db = sqlite3.connect(catalog_path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
            db.row_factory = sqlite3.Row
            try:
                placeholders = ','.join('?' for _ in wanted)
                rows = db.execute('''SELECT d.sha256,d.doc_id,r.state,r.phase,r.pages_total,r.chunks_total,
                                    r.chunks_read,r.report_sha256,r.manifest_sha256
                                    FROM documents d LEFT JOIN reading_runs r
                                    ON r.doc_id=d.doc_id AND r.base_revision_id IS NULL
                                    WHERE d.sha256 IN (''' + placeholders + ')', tuple(sorted(wanted))).fetchall()
                for row in rows:
                    if row['state'] == 'ready' and row['manifest_sha256']:
                        status = 'candidate_ready'
                    elif row['state'] in {'blocked', 'failed'}:
                        status = row['state']
                    elif row['state']:
                        status = row['state']
                    else:
                        status = 'registered'
                    states[row['sha256']] = {'status': status, 'doc_id': row['doc_id'],
                        'phase': row['phase'], 'pages_total': row['pages_total'],
                        'chunks_total': row['chunks_total'], 'chunks_read': row['chunks_read'],
                        'candidate_report': bool(row['report_sha256'])}
            finally:
                db.close()
        except sqlite3.Error:
            states = {}
    for delivery in deliveries:
        readings = []
        for item in delivery.get('items', []):
            if not isinstance(item, dict):
                continue
            reading = states.get(item.get('sha256'))
            if reading is None:
                reading = {'status': 'not_registered' if item.get('reader_handoff') == 'eligible'
                           else 'extractor_required'}
            readings.append(reading)
        delivery['reading'] = {'items': readings,
            'candidate_ready': sum(row['status'] == 'candidate_ready' for row in readings),
            'blocked': sum(row['status'] in {'blocked', 'failed'} for row in readings),
            'not_registered': sum(row['status'] == 'not_registered' for row in readings),
            'adoption': 'not_inferred'}


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
    contract = catalog(root)
    providers = {p['id'] for p in contract['providers']}
    provider = payload.get('provider_id', '')
    if not isinstance(provider, str) or (provider and provider not in providers):
        raise ValueError('供应方不存在')
    if action == 'assign' and not provider:
        raise ValueError('请选择供应方')
    mode = payload.get('execution_mode', '')
    host = payload.get('execution_host', '')
    if provider:
        policy = contract['execution_policy'].get(mode)
        if not policy or host != policy['host']:
            raise ValueError('执行方式与主机不符合供应策略')
    elif mode or host:
        raise ValueError('未分配供应方时不能指定执行方式')
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
                                   'provider_id': provider, 'execution_mode': mode,
                                   'execution_host': host, 'status': 'planned',
                                   'created_at': now, 'created_by': actor})
        state['revision'] += 1
        state['operations'].append({'id': operation_id, 'request': fingerprint, 'actor': actor, 'at': now})
        write_json(ledger_path(root), state)
        return {'ok': True, 'revision': state['revision']}
