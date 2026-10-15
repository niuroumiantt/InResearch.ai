"""Durable project coordination, separate from collection execution and adoption.

The published plan creates the mission and its unassigned work packages. Runtime
changes are private, revisioned and audited; HTTP callers cannot certify research
adoption or map publication through a coordination status.
"""
import copy
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
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


def assigned_members(value):
    """Existing text field permits several explicit login names without a migration."""
    return {part.strip() for part in re.split(r'[,，、;；\n]+',value or '') if part.strip()}


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
            or (state.get('target_site_count') is not None and
                (type(state['target_site_count']) is not int or not 1 <= state['target_site_count'] <= 1000000))
            or not isinstance(state.get('target_site_basis', ''), str)
            or len(state.get('target_site_basis', '')) > 500
            or not isinstance(state.get('target_site_set_at', ''), str)
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


def package_task_edits(state, package_id):
    """Only changes to the common task brief advance its shared version."""
    result = []
    for operation in state.get('operations', []):
        if operation.get('package_id') != package_id:
            continue
        before, after = operation.get('before'), operation.get('after')
        if not isinstance(before, dict) or not isinstance(after, dict):
            continue
        if any(before.get(key) != after.get(key)
               for key in ('title', 'region', 'scope', 'sources')):
            try:
                result.append(datetime.fromisoformat(operation['at']).timestamp())
            except (KeyError, TypeError, ValueError):
                result.append(0)
    return result


def package_workflow(package, records, visible_sites=(), task_edits=()):
    """A public, package-scoped handoff made only from owner-approved records.

    Raw files, personal revision instructions and model prose stay behind their
    existing owner/receipt gates. The shared next action is server-authored from
    the verified outcome, so a later worker never inherits an upload's claims.
    """
    from inresearch.materials import inbox
    visible = set(visible_sites)
    events, sites, statements, completed = [], set(), set(), []
    for record in records:
        if record.get('package_id') != package['id']:
            continue
        try:
            inbox.require_approved(record)
        except (PermissionError, KeyError, TypeError):
            continue
        reports = [row for row in record.get('analysis_reports', [])
                   if isinstance(row, dict) and isinstance(row.get('report'), dict)]
        latest = max(reports, key=lambda row: row.get('at') or 0, default=None)
        report = latest['report'] if latest else {}
        published = [row for row in report.get('published', []) if isinstance(row, dict)]
        held = [row for row in report.get('held', []) if isinstance(row, dict)]
        findings = [row for row in report.get('findings', []) if isinstance(row, dict)]
        scope = report.get('review_scope') or {}
        sampled = isinstance(scope, dict) and scope.get('mode') == 'sampled_native_cells'
        for entry in reports:
            completed.append((entry.get('at') or 0, record.get('id', ''), entry))
            for row in entry['report'].get('published', []):
                if not isinstance(row, dict):
                    continue
                if isinstance(row.get('site_id'), str) and row['site_id'] in visible:
                    sites.add(row['site_id'])
                if isinstance(row.get('statement_id'), str) and row['statement_id']:
                    statements.add(row['statement_id'])
        if sampled:
            feedback = ('抽样反馈、全表待审；已定位问题请按个人回执修订，'
                        '未完整审阅的内容仍需按当前任务继续提交较小证据包。')
            next_action = ('先补齐唯一园区身份、地点、字段口径、时点和来源定位；'
                           '将尚未完整审阅的大表拆成可核查的小包。')
            outcome = 'sampled_incomplete'
        elif latest:
            reconfirmed = sum(row.get('registration_kind') == 'reconfirmation' for row in published)
            duplicate = sum(row.get('classification') == 'duplicate' for row in held)
            conflicts = sum(row.get('classification') == 'conflict' for row in held)
            feedback = (f'本轮新登记 {len(published)-reconfirmed} 条、同值再次核验 {reconfirmed} 条；'
                        f'无增量重复 {duplicate} 条、冲突 {conflicts} 条、'
                        f'其他未上线 {len(held)-duplicate-conflicts} 条、定位问题 {len(findings)} 处。'
                        '逐项修改要求请凭本人回执查看。')
            next_action = ('先核对冲突双方的原件、来源时点和园区/容量口径；'
                           '继续补未覆盖园区与分期。') if conflicts else (
                           '先补未上线条目的园区身份、来源、时点与口径；'
                           '继续补未覆盖园区与分期。') if len(held) > duplicate or findings else (
                           '本轮合格来源已登记；继续补本工作包尚未覆盖的具名园区、'
                           '分期和可回查来源，提交前对照最新台账。')
            outcome = 'reviewed'
        else:
            progress = record.get('analysis_progress') or {}
            outcome = ('source_error' if progress.get('state') == 'source_error' else
                       'blocked' if progress.get('state') == 'blocked' else 'awaiting_review')
            feedback = ('原件处理失败；提交者请按个人回执查看修订要求。' if outcome == 'source_error' else
                        '分析暂时受阻，原件已保留，研究端将重试。' if outcome == 'blocked' else
                        '负责人已确认原件；分析尚未完成。')
            next_action = ''
        submitter = re.sub(r'[\x00-\x1f\x7f]+', ' ', str(record.get('submitter') or '未留姓名')).strip()[:120]
        name = str(record.get('name') or '')
        kind = {'.xlsx':'Excel 表格', '.xls':'Excel 表格', '.csv':'CSV 数据',
                '.tsv':'TSV 数据', '.pdf':'PDF 文档', '.docx':'Word 文档',
                '.txt':'文本资料', '.md':'Markdown 文档', '.json':'JSON 数据',
                '.html':'网页资料', '.htm':'网页资料'}.get(Path(name).suffix.lower(), '附件')
        received_at = record.get('created') if isinstance(record.get('created'), (int, float)) else None
        reviewed_at = latest.get('at') if latest else None
        events.append({'_record_id':record.get('id', ''),
                       'received_at':received_at, 'reviewed_at':reviewed_at,
                       'last_activity_at':reviewed_at or (record.get('approval') or {}).get('at') or received_at,
                       'submitter':submitter, 'material':kind, 'outcome':outcome,
                       'feedback':feedback, 'next_action':next_action,
                       'published_statements':len(published), 'held':len(held),
                       'findings':len(findings)})
    completed.sort(key=lambda row:(row[0], row[1]))
    latest_completed = completed[-1] if completed else None
    latest_event = next((row for row in events if row['_record_id'] == latest_completed[1]
                         and row['reviewed_at'] == latest_completed[0]
                         and row['reviewed_at'] is not None), None) if latest_completed else None
    scope_changed_after_review = bool(task_edits and max(task_edits) >
                                      (latest_completed[0] if latest_completed else 0))
    task = {'version':len(completed) + len(task_edits) + 1,
            'updated_at':max([latest_completed[0] if latest_completed else 0, *task_edits]) or None,
            'scope':package['scope'],
            'next_action':latest_event['next_action'] if latest_event and not scope_changed_after_review else
                           '按当前工作包范围，先找具名物理园区和可回查来源；未知项明确留空。'}
    events.sort(key=lambda row:row['last_activity_at'] or 0, reverse=True)
    for event in events:
        del event['_record_id']
    return {'published_sites':len(sites), 'published_statements':len(statements),
            'reviewed_files':len(completed), 'confirmed_files':len(events),
            'target':None, 'current_task':task, 'events':events[:50]}


def snapshot(root, actor='', role='reader'):
    state = read(root)
    # Use exactly the map's existing projection and deduplication rules. These are
    # observed database totals, not a claim about worldwide coverage or live ACK.
    from inresearch.knowledge import industry
    view = industry.cached_snapshot(root, {'overview': '1'})
    from inresearch.materials import inbox
    records = inbox.records()
    reports = [entry for record in records
               for entry in record.get('analysis_reports', [])
               if isinstance(entry, dict) and isinstance(entry.get('report'), dict)]
    published_rows = [row for entry in reports for row in entry['report'].get('published', [])
                      if isinstance(row, dict)]
    # A historical receipt alone does not prove that a site remains visible.
    # The overview projection already excludes duplicate aliases; exclude portfolio
    # aggregates as well so the main progress bar counts physical sites only.
    visible_sites = {row.get('site_id') for row in view.get('rows', [])
                     if isinstance(row, dict) and isinstance(row.get('site_id'), str)
                     and row['site_id'] and not row.get('portfolio')}
    published_sites = {row['site_id'] for row in published_rows
                       if isinstance(row.get('site_id'), str) and row['site_id'] in visible_sites}
    published_statements = {row['statement_id'] for row in published_rows
                            if isinstance(row.get('statement_id'), str) and row['statement_id']}
    package_progress = {package['id']:package_workflow(package, records, visible_sites,
                                                        package_task_edits(state, package['id']))
                        for package in state['packages']}
    projection = {k: v for k, v in state.items() if k != 'operations'}
    if role == 'reader':
        projection = {k: state[k] for k in ('version', 'revision')}
        projection['target_site_count'] = state.get('target_site_count')
        projection['target_site_basis'] = state.get('target_site_basis', '')
        projection['target_site_set_at'] = state.get('target_site_set_at', '')
        projection['packages'] = [{k: p.get(k) for k in ('id', 'title', 'region', 'scope', 'sources', 'status')}
                                  for p in state['packages']]
    return {**projection, 'mission': plan(root)['mission'],
            'package_progress':package_progress,
            'site_progress': {'target': state.get('target_site_count'),
                              'target_basis': state.get('target_site_basis', ''),
                              'target_set_at': state.get('target_site_set_at', ''),
                              'published_sites': len(published_sites),
                              'reviewed_reports': len(reports),
                              'published_statements': len(published_statements),
                              'basis': '负责人确认后模型审阅、发布，且当前园区台账仍可见的去重园区；同园区多字段只计一次'},
            'actor': actor if role != 'reader' else '', 'role': role,
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
    if action not in ('create', 'update', 'set_target'):
        raise ValueError('不支持的任务操作')
    if action == 'set_target':
        if role != 'admin': raise Forbidden('只有管理员可以设置园区目标条数')
        if (set(payload) != {'action','operation_id','expected_revision','target_site_count','target_site_basis'}
                or type(payload['target_site_count']) is not int
                or not 1 <= payload['target_site_count'] <= 1000000
                or not isinstance(payload['target_site_basis'], str)
                or not 5 <= len(payload['target_site_basis'].strip()) <= 500):
            raise ValueError('暂定目标须填写 1 至 1000000 的园区条数与初步研究依据（5 至 500 字）')
    elif set(payload) - set(FIELDS) - {'action', 'operation_id', 'expected_revision', 'package_id'}:
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
        if action == 'set_target':
            before = {'count': state.get('target_site_count'), 'basis': state.get('target_site_basis', ''),
                      'set_at': state.get('target_site_set_at', '')}
            state['target_site_count'] = payload['target_site_count']
            state['target_site_basis'] = payload['target_site_basis'].strip()
            state['target_site_set_at'] = now
            state['revision'] += 1
            state['operations'].append({'id':operation_id,'request':fingerprint,'actor':actor,
                'role':role,'at':now,'package_id':'mission-target','before':before,
                'after':{'count':state['target_site_count'],'basis':state['target_site_basis'],
                         'set_at':state['target_site_set_at']}})
            write_json(ledger_path(root),state)
            return {'ok':True,'revision':state['revision'],'target_site_count':state['target_site_count'],
                    'target_site_basis':state['target_site_basis']}
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
                if actor not in assigned_members(package.get('assignee')):
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
