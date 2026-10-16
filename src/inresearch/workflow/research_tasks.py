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



def package_scope_revision(state, package_id):
    """Global ledger revision of the latest substantive edit to this package."""
    operations=state.get('operations',[])
    offset=state.get('revision',len(operations))-len(operations)
    revisions=[]
    for index,operation in enumerate(operations,1):
        before,after=operation.get('before'),operation.get('after')
        if (operation.get('package_id')==package_id and isinstance(before,dict) and isinstance(after,dict)
                and any(before.get(key)!=after.get(key) for key in ('title','region','scope','sources'))):
            revisions.append(offset+index)
    return max(revisions,default=0)


def _review_round(entry, record):
    """Joint members share one feedback round; later attempts retain their own identity."""
    report=entry.get('report') or {}
    joint=report.get('batch_review')
    if isinstance(joint,dict) and isinstance(joint.get('id'),str):
        identity=(report.get('task_provenance') or {}).get('sha256') or (
            report.get('model') or {}).get('input_sha256') or ''
        return 'batch:'+joint['id']+':'+identity
    return 'report:'+record.get('id','')+':'+str(entry.get('id') or entry.get('at') or '')



def _has_content_review(report):
    """A source-format error is feedback, not a completed model review.

    Sampled reports still count as bounded reviews; their explicit scope keeps
    the source's unread content separate from whole-document completion.
    """
    return isinstance(report,dict) and (report.get('publication') or {}).get('state')!='source_error'


def _round_summary(rows, manual=None):
    """Public, server-authored instructions contain no raw private model or owner text."""
    if manual is not None:
        result=manual.get('result')
        if result=='sampled_incomplete' or manual.get('_coverage')=='sampled':
            return ('负责人已登记本轮反馈；抽样原件全表仍待审，0 条上线不能推定全表无合格条目。',
                    '按当前数据库与工作包继续补齐未完成证据；未完整交模型的内容保持未审，不以人工反馈替代全表原文核验。',
                    'sampled_incomplete')
        if manual.get('_coverage')=='source_error':
            return ('负责人已登记本轮反馈；无法安全解析的原件仍未完成内容审阅。',
                    '修复原件后按当前数据库与工作包核对尚未完成的证据；此前可读材料的实际成果保留。',
                    'source_error')
        if result=='accepted':
            return ('负责人已登记本轮验收通过；此前反馈仅供追溯。',
                    '先对照当前数据库确认已完成部分；继续补当前工作包尚未覆盖的具名园区、字段与可回查来源。',
                    'manual_feedback')
        if result=='blocked':
            return ('负责人已登记本轮受阻；此前反馈仅供追溯。',
                    '先核对当前工作包与数据库中的待核部分，补齐可定位原件与来源后再继续。',
                    'manual_feedback')
        if result=='ineligible':
            return ('负责人已登记本轮材料不符合当前任务范围；此前反馈仅供追溯。',
                    '按现行工作包重新整理可核查证据包；已入库部分保留，未知与缺口留明。',
                    'manual_feedback')
        return ('负责人已登记本轮需要修改；此前反馈仅供追溯。',
                '先对照当前数据库与工作包核对尚未完成的园区身份、来源、时点和字段口径，再提交定位明确的补证材料。',
                'manual_feedback')
    reports=[row['report'] for _,row in rows]
    sampled=any(isinstance(report.get('review_scope'),dict)
                and report['review_scope'].get('mode')=='sampled_native_cells' for report in reports)
    source_error=any((report.get('publication') or {}).get('state')=='source_error' for report in reports)
    published={row.get('statement_id'):row for report in reports for row in report.get('published',[])
               if isinstance(row,dict) and row.get('statement_id')}
    held=[row for report in reports for row in report.get('held',[]) if isinstance(row,dict)]
    findings=[row for report in reports for row in report.get('findings',[]) if isinstance(row,dict)]
    if sampled:
        return ('抽样反馈、全表待审；0 条上线不能据此判定全表无合格条目。',
                '先对照当前数据库补齐尚缺的唯一园区身份、地点、字段口径、时点和来源定位；将未完整审阅的大表整理成可核查的小证据包。',
                'sampled_incomplete')
    if source_error:
        return ('本轮含无法安全解析的原件；未读内容不能算已完成审核。',
                '修正无法读取的原件，并对照当前工作包和数据库继续补齐尚未完成的证据；可读材料的实际入库结果保留。',
                'source_error')
    reconfirmed=sum(row.get('registration_kind')=='reconfirmation' for row in published.values())
    duplicate=sum(row.get('classification')=='duplicate' for row in held)
    conflicts=sum(row.get('classification')=='conflict' for row in held)
    new=sum(row.get('registration_kind','new') not in ('reconfirmation','replay') for row in published.values())
    replay=sum(row.get('registration_kind')=='replay' for row in published.values())
    summary=(f'本轮新登记 {new} 条、同值再次核验 {reconfirmed} 条；'
             f'无增量重复 {duplicate} 条、冲突 {conflicts} 条、'
             f'其他未上线 {len(held)-duplicate-conflicts} 条、定位问题 {len(findings)} 处。'
             +(f'复用既有来源 {replay} 条。' if replay else ''))
    action=('先核对冲突双方的原件、来源时点和园区/容量口径；继续补未覆盖园区与分期。' if conflicts else
            '先补未上线条目的园区身份、来源、时点与口径；继续补未覆盖园区与分期。' if len(held)>duplicate or findings else
            '本轮合格来源已登记；先对照当前数据库确认已完成部分，继续补本工作包尚未覆盖的具名园区、分期和可回查来源。' if published else
            '本轮未新增来源登记；对照当前数据库继续补本工作包尚未覆盖的具名园区、字段与可回查来源。')
    return summary,action,'reviewed'


def package_workflow(package, records, visible_sites=(), task_edits=(), *, task_scope_revision=0):
    """One live execution anchor per work package; old evidence stays historical."""
    from inresearch.materials import inbox
    visible=set(visible_sites)
    approved=[];sites=set();statements=set();rounds={};file_history={}
    for record in records:
        if record.get('package_id') != package['id']: continue
        try: inbox.require_approved(record)
        except (PermissionError,KeyError,TypeError): continue
        approved.append(record)
        reports=[row for row in record.get('analysis_reports',[])
                 if isinstance(row,dict) and isinstance(row.get('report'),dict)]
        for entry in reports:
            key=_review_round(entry,record)
            group=rounds.setdefault(key,{'at':0,'rows':[],'expected':None,'manual':None})
            group['at']=max(group['at'],entry.get('at') or 0)
            group['rows'].append((record,entry))
            joint=entry['report'].get('batch_review')
            if isinstance(joint,dict) and isinstance(joint.get('members'),list):
                group['expected']={row['id'] for row in joint['members'] if isinstance(row,dict) and row.get('id')}
            file_history.setdefault(record['id'],[]).append((entry.get('at') or 0,key))
            for row in entry['report'].get('published',[]):
                if not isinstance(row,dict): continue
                if row.get('site_id') in visible: sites.add(row['site_id'])
                if isinstance(row.get('statement_id'),str) and row['statement_id']: statements.add(row['statement_id'])
        report_ids={row.get('id') for row in reports if row.get('id')}
        for feedback in record.get('feedback',[]):
            if (not isinstance(feedback,dict) or feedback.get('sha256') != record.get('sha256')
                    or feedback.get('by') not in (inbox.approver(),'analysis-worker')
                    or feedback.get('id') in report_ids
                    or feedback.get('result') not in ('revision_required','accepted','blocked','ineligible','sampled_incomplete')):
                continue
            key='feedback:'+record['id']+':'+str(feedback.get('id') or feedback.get('at') or '')
            rounds[key]={'at':feedback.get('at') or 0,'rows':[],'expected':None,
                         'manual':feedback,'manual_source_id':record['id']}
            file_history.setdefault(record['id'],[]).append((feedback.get('at') or 0,key))
    complete={key:group for key,group in rounds.items()
              if group['expected'] is None or group['expected']=={record['id'] for record,_ in group['rows']}}
    def compatible(group):
        if group['manual'] is not None:
            return not task_edits or group['at']>=max(task_edits)
        return not task_scope_revision or all(
            type((entry['report'].get('task_provenance') or {}).get('revision')) is int
            and entry['report']['task_provenance']['revision']>=task_scope_revision
            for _,entry in group['rows'])
    # A later instruction cannot change evidence of what was actually read.
    for group in complete.values():
        if group['manual'] is None: continue
        prior=max((candidate for candidate in complete.values() if candidate['rows']
                   and any(record['id']==group['manual_source_id'] for record,_ in candidate['rows'])
                   and candidate['at']<=group['at'] and compatible(candidate)),
                  key=lambda candidate:candidate['at'],default=None)
        if prior:
            scopes=[entry['report'] for _,entry in prior['rows']]
            coverage=('sampled' if any(isinstance(report.get('review_scope'),dict) and
                                      report['review_scope'].get('mode')=='sampled_native_cells' for report in scopes) else
                      'source_error' if any((report.get('publication') or {}).get('state')=='source_error' for report in scopes) else None)
            if coverage: group['manual']={**group['manual'],'_coverage':coverage}
    eligible={key:group for key,group in complete.items() if compatible(group)}
    latest_key=max(eligible,key=lambda key:(eligible[key]['at'],key),default=None)
    latest=complete.get(latest_key)
    latest_at=latest['at'] if latest else 0
    scope_changed=bool(task_edits and max(task_edits)>latest_at)
    current_key=None if scope_changed else latest_key
    default='按当前工作包范围，先对照当前数据库确认已完成部分，补尚缺的具名物理园区和可回查来源；未知项明确留空。'
    if latest and not scope_changed:
        summary,action,_=_round_summary(latest['rows'],latest['manual'])
    else:
        summary=('工作范围已更新；此前反馈仅供追溯，按现行范围与数据库继续核对。' if scope_changed else
                 '尚无本工作包的完整反馈轮次；按当前范围与数据库开始补证。')
        action=default
    remaining=[action,'先核对当前数据库，避免重复派发已完成事项；覆盖分母与未核实字段未知时保持未知，不推算全行业缺口。']
    task={'version':len(complete)+len(task_edits)+1,
          'updated_at':max([latest_at,*task_edits]) or None,'scope':package['scope'],
          'next_action':action,'basis':'current_database_and_latest_package_feedback',
          'feedback_at':latest_at if latest and not scope_changed else None,
          'feedback_summary':summary,'scope_revision':task_scope_revision,
          'completed':{'published_sites':len(sites),'published_statements':len(statements),
                       'reviewed_rounds':sum(any(_has_content_review(entry['report'])
                                                for _,entry in group['rows']) for group in complete.values()),
                       'feedback_rounds':len(complete)},
          'remaining':remaining}
    events=[]
    for record in approved:
        reports=[row for row in record.get('analysis_reports',[]) if isinstance(row,dict) and isinstance(row.get('report'),dict)]
        last_report=max(reports,key=lambda row:row.get('at') or 0,default=None)
        own=max(file_history.get(record['id'],[]),default=None)
        key=own[1] if own else None
        group=rounds.get(key)
        if group:
            feedback,next_action,outcome=_round_summary(group['rows'],group['manual'])
        else:
            progress=record.get('analysis_progress') or {}
            outcome=('source_error' if progress.get('state')=='source_error' else 'blocked' if progress.get('state')=='blocked' else 'awaiting_review')
            feedback=('原件处理失败；历史记录保留。' if outcome=='source_error' else
                      '分析暂时受阻，原件与历史记录保留。' if outcome=='blocked' else '负责人已确认原件；分析尚未完成。')
            next_action=''
        received=record.get('created') if isinstance(record.get('created'),(int,float)) else None
        name=str(record.get('name') or '')
        kind={'.xlsx':'Excel 表格','.xls':'Excel 表格','.csv':'CSV 数据','.tsv':'TSV 数据','.pdf':'PDF 文档',
              '.docx':'Word 文档','.txt':'文本资料','.md':'Markdown 文档','.json':'JSON 数据','.html':'网页资料','.htm':'网页资料'}.get(Path(name).suffix.lower(),'附件')
        report=last_report['report'] if last_report else {}
        is_current=bool(key and key==current_key and key in complete)
        events.append({'_record_id':record.get('id',''),'received_at':received,
            'reviewed_at':last_report.get('at') if last_report and _has_content_review(report) else None,
            'feedback_at':own[0] if own else None,
            'last_activity_at':own[0] if own else (record.get('approval') or {}).get('at') or received,
            'submitter':re.sub(r'[\x00-\x1f\x7f]+',' ',str(record.get('submitter') or '未留姓名')).strip()[:120],
            'material':kind,'outcome':outcome,'feedback':feedback,'next_action':'',
            'published_statements':len(report.get('published',[])),'held':len(report.get('held',[])),
            'findings':len(report.get('findings',[])),'is_current_feedback':is_current,
            'feedback_state':'current' if is_current else 'superseded' if own and key in complete else 'history'})
    events.sort(key=lambda row:(row['received_at'] or 0,row['_record_id']),reverse=True)
    for event in events: del event['_record_id']
    return {'published_sites':len(sites),'published_statements':len(statements),
            'reviewed_files':sum(any(_has_content_review(entry.get('report'))
                                      for entry in record.get('analysis_reports',[])) for record in approved),
            'confirmed_files':len(events),'target':None,'current_task':task,'events':events[:50]}


def snapshot(root, actor='', role='reader'):
    state = read(root)
    # Use exactly the map's existing projection and deduplication rules. These are
    # observed database totals, not a claim about worldwide coverage or live ACK.
    from inresearch.knowledge import industry
    view = industry.cached_task_progress(root)
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
                                                        package_task_edits(state, package['id']),
                                                        task_scope_revision=package_scope_revision(state,package['id']))
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
                              'reviewed_reports': sum(_has_content_review(entry['report']) for entry in reports),
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
