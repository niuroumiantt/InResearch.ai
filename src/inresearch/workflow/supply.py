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
    from inresearch.knowledge import registry
    from inresearch.workflow.project_review import deliveries as project_deliveries
    runtime = registry._snapshot_inputs(root)[-1]
    reader = registry._reader_state(runtime)
    matched = (reader.get('acquisition') or {}).get('material_matches') or {'records': [], 'total': 0, 'status': 'not_connected'}
    needed = [t for t in target_document['targets'] if t['status'] in ('needed', 'assumed', 'delivered')]
    candidates = matched.get('by_target') or {}
    demand_queue = [{k: t.get(k) for k in ('id','team','host','team_state','status','variable_class','part_id','site_right_id','model_inputs','feeds_primary','disclosure_type')}
                    | {'candidate_documents': candidates.get(t['id'], 0),
                       'dispatch_state': 'reading_candidate' if candidates.get(t['id']) else 'awaiting_material' if t['team_state']=='connected' else 'awaiting_team'}
                    for t in needed]
    demand_queue.sort(key=lambda t: (-t['candidate_documents'], not bool(t['feeds_primary']), t['id']))
    project_updates = project_deliveries(root)
    ecosystem_updates = [dict(contract_id=r['contract_id'], event_id=r['adoption']['event_id'],
                              name=r['summary'], parties=r['parties'], node=r.get('node'),
                              scope=r['adoption']['scope'])
                         for r in json.loads((root/'data/contracts.json').read_text())['records']
                         if r.get('adoption', {}).get('review', {}).get('decision') == 'adopted']
    daily_events = (reader.get('acquisition') or {}).get('daily_events') or {'records': [], 'total': 0}
    daily_events = dict(daily_events, records=[dict(e, adoption_updates=[p for p in project_updates if p['event_id'] == e['id']])
                                             for e in daily_events.get('records', [])])
    return {'catalog': catalog(root), 'revision': state['revision'],
            'daily_events': daily_events,
            'daily_delivery': (reader.get('acquisition') or {}).get('daily_delivery') or {'records':[],'total':0,'news_total':0},
            'research_verification': reader.get('research_verification') or {'state':'not_started','candidates':{}},
            'research_matching': matched, 'demand_queue': demand_queue,
            'reading_deliveries': reading_deliveries(runtime.get('knowledge') or {}, matched),
            'project_updates': project_updates,
            'ecosystem_updates': ecosystem_updates,
            'matching_reader': {k: reader.get(k) for k in ('received_at','stale','status','execution_scope')},
            'demands': state['demands'], 'tasks': state['tasks'],
            'questions': [{'id': q['id'], 'text': q['text'], 'node':q.get('node'),
                           'variable_class':q.get('variable_class'), 'object_ids': q.get('object_ids', [])} for q in questions],
            'target_registry': {'version': target_document['version'], 'records': target_document['targets']},
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


def reading_deliveries(reader, matched):
    """Received reading results only; retain candidate scope and omit raw paths."""
    wanted = {r.get('sha256') for r in matched.get('records', [])}
    truncated = matched.get('truncated') is True
    outputs = []
    for doc in reader.get('documents', []):
        # The bounded match index is not the authority for received readings.
        # Once truncated, absence from it cannot mean absence of a delivery.
        if (not truncated and doc.get('content_sha256') not in wanted) or doc.get('read_status') != 'complete':
            continue
        ident = doc.get('doc_id') or doc.get('id')
        claims = [r.get('text', '') for r in reader.get('statements', []) if r.get('document_id') == ident]
        quotes = [{k: r.get(k) for k in ('quote', 'page_index')}
                  for r in reader.get('evidence', []) if r.get('document_id') == ident]
        outputs.append({'title': doc.get('title'), 'sha256': doc['content_sha256'],
                        'claims': claims[:6], 'quotes': quotes[:3],
                        'coverage': doc.get('coverage') or {}, 'acceptance': 'candidate_only'})
    return outputs


def _attach_reader_status(deliveries):
    """Read-only projection from the existing Reader catalog; never initializes it."""
    data = Path(os.environ.get('READER_DATA_ROOT', Path.home() / '.local/share/inresearch.ai')).expanduser()
    catalog_path = data / 'catalog/catalog.sqlite'
    wanted = {item.get('sha256') for delivery in deliveries for item in delivery.get('items', [])
              if isinstance(item, dict) and isinstance(item.get('sha256'), str)}
    states = {}
    catalog_state = 'unavailable'
    if wanted and catalog_path.is_file() and not catalog_path.is_symlink():
        try:
            db = sqlite3.connect(catalog_path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
            db.row_factory = sqlite3.Row
            try:
                db.execute('BEGIN')
                rows = []
                ordered = sorted(wanted)
                for offset in range(0, len(ordered), 500):
                    subset = ordered[offset:offset+500]
                    placeholders = ','.join('?' for _ in subset)
                    rows.extend(db.execute('''SELECT sha256,doc_id,state,phase,pages_total,chunks_total,
                        chunks_read,report_sha256,manifest_sha256 FROM current_readings
                        WHERE sha256 IN (''' + placeholders + ')', subset).fetchall())
                for row in rows:
                    if row['state'] in {'ready', 'complete'} and row['manifest_sha256'] and row['report_sha256']:
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
                catalog_state = 'observed'
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
                reading = {'status': ('not_registered' if catalog_state == 'observed' else 'reader_status_unavailable')
                           if item.get('reader_handoff') == 'eligible' else 'extractor_required'}
            readings.append(reading)
        delivery['reading'] = {'items': readings,
            'candidate_ready': sum(row['status'] == 'candidate_ready' for row in readings),
            'blocked': sum(row['status'] in {'blocked', 'failed'} for row in readings),
            'not_registered': sum(row['status'] == 'not_registered' for row in readings),
            'status_unavailable': sum(row['status'] == 'reader_status_unavailable' for row in readings),
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
        if not policy or (mode == 'assisted' and host != policy['host']):
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
        targets = json.loads((root / 'framework/tco_targets.json').read_text())
        registered = {row['id']: row for row in targets['targets']}
        if action == 'create':
            target_id = text(payload, 'target_id', 200)
            target = registered.get(target_id)
            if not target:
                raise ValueError('请选择现行目标行；研究问题不能另建采集任务轴')
            question_id = payload.get('question_id') or None
            questions = json.loads((root / 'framework/research_questions.json').read_text())['records']
            question = next((q for q in questions if q['id'] == question_id), None)
            if question_id is not None and not question:
                raise ValueError('研究问题不存在')
            if question and (question.get('node') != target.get('request', {}).get('node') or
                             question.get('variable_class') != target['variable_class']):
                raise ValueError('研究问题与目标节点或变量类不一致；跨范围研究先修订需求关联')
            from inresearch.knowledge.target_request_contract import target_node
            demand = {'id': 'demand-' + operation_id, 'target_id': target_id,
                      'target_version': targets['version'], 'question_id': question_id,
                      'object_ids': [target_node(target)],
                      'title': text(payload, 'title', 300), 'scope': text(payload, 'scope', 3000),
                      'acceptance': text(payload, 'acceptance', 3000),
                      'created_at': now, 'created_by': actor}
            state['demands'].append(demand)
        else:
            demand = next((d for d in state['demands'] if d['id'] == payload.get('demand_id')), None)
            if not demand:
                raise ValueError('需求不存在')
            target = registered.get(demand.get('target_id'))
            if not target:
                raise ValueError('旧需求未绑定现行目标行；保留记录，请从目标行新建细化需求')
        if provider:
            if provider != target['team'] or host != target['host']:
                raise ValueError('供应方与主执行机必须服从目标行；变更归属先更新目标规则')
            if any(t['demand_id'] == demand['id'] and t['provider_id'] == provider for t in state['tasks']):
                raise Conflict('该供应方已有本需求任务')
            state['tasks'].append({'id': 'task-' + operation_id, 'demand_id': demand['id'], 'target_id': target['id'],
                                   'provider_id': provider, 'execution_mode': mode,
                                   'execution_host': host, 'status': 'planned',
                                   'created_at': now, 'created_by': actor})
        state['revision'] += 1
        state['operations'].append({'id': operation_id, 'request': fingerprint, 'actor': actor, 'at': now})
        write_json(ledger_path(root), state)
        return {'ok': True, 'revision': state['revision']}
