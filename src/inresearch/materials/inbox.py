"""Private durable website inbox. Documents are data, never execution instructions."""

from inresearch.storage.layout import workspace_path
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import time
import uuid
from inresearch.storage.files import locked, sync_directory

MAX_BYTES = 64 * 1024 * 1024
REVIEWABLE_SUFFIXES = frozenset({'.xlsx', '.txt', '.md', '.csv', '.tsv', '.json', '.html', '.htm', '.pdf', '.docx'})

def reviewable(name):
    return Path(name).suffix.lower() in REVIEWABLE_SUFFIXES

def root():
    return Path(os.environ.get('INRESEARCH_INTAKE_ROOT', workspace_path('data/.material-intake')))

def record_path(key):
    if not re.fullmatch(r'[a-f0-9]{32}', key):
        raise ValueError('invalid submission id')
    return root() / key

def atomic(path, data):
    from inresearch.storage.files import write_json
    write_json(path, data)

def receive(stream, size, metadata, user, *, public=False):
    if not isinstance(metadata, dict):
        raise ValueError('invalid metadata')
    if 'batch_total' not in metadata and 'batch_index' not in metadata:
        if metadata.get('batch_token'): raise ValueError('upload batch bounds required')
        return _receive(stream,size,metadata,user,public=public)
    from inresearch.materials import batch_review
    total, index = metadata.get('batch_total'), metadata.get('batch_index')
    if (not public or type(total) is not int or not 1 <= total <= 20
            or type(index) is not int or not 0 <= index < total):
        raise ValueError('invalid upload batch bounds')
    path = batch_review.batch_path('upload',metadata.get('batch_id'))
    with locked(path):
        fingerprint = {key:str(metadata.get(key,'')).strip()
                       for key in ('submitter','project_name','package_id')}
        token=metadata.get('batch_token','')
        if token and (not isinstance(token,str) or not re.fullmatch(r'[a-f0-9-]{36}',token)):
            raise ValueError('invalid upload batch token')
        token_hash=hashlib.sha256(token.encode()).hexdigest() if token else None
        state = json.loads(path.read_text()) if path.exists() else {
            'id':metadata['batch_id'],'expected':total,'metadata':fingerprint,
            'items':[],'sealed':False,'token_hash':token_hash}
        if state.get('token_hash') != token_hash:
            raise PermissionError('invalid upload batch credential')
        if state['expected'] != total or state['metadata'] != fingerprint:
            raise Conflict('upload batch metadata changed')
        previous=next((row for row in state['items'] if row['index']==index),None)
        if previous and token:
            if not 0 < size <= MAX_BYTES: raise ValueError('invalid upload size')
            digest=hashlib.sha256();remaining=size
            while remaining:
                chunk=stream.read(min(1024*1024,remaining))
                if not chunk: raise ValueError('上传中断，未接收完整文件')
                remaining-=len(chunk);digest.update(chunk)
            record=load(previous['id'])
            name=str(metadata.get('name','资料.txt')).replace('\\','/').split('/')[-1][:180]
            if record['sha256'] != digest.hexdigest() or record['size'] != size or record['name'] != name:
                raise Conflict('upload batch attachment replay changed')
            return public_view(record),batch_review.receipt_for(token,record['id'])
        if state['sealed'] or previous:
            raise Conflict('upload batch sealed or attachment index already received')
        atomic(path,state)
        item, receipt = _receive(stream,size,metadata,user,public=True)
        state['items'].append({'id':item['id'],'sha256':item['sha256'],'index':index})
        state['items'].sort(key=lambda row:row['index'])
        atomic(path,state)
        return public_view(load(item['id'])),receipt


def _receive(stream, size, metadata, user, *, public=False):
    if not 0 < size <= MAX_BYTES:
        raise ValueError('单份资料须为 1 字节至 64 MiB')
    submitter = str(metadata.get('submitter', '')).strip()
    project_name = str(metadata.get('project_name', '')).strip()
    if public and (not submitter or not project_name):
        raise ValueError('请填写提交人姓名和项目名称')
    if len(submitter) > 120 or len(project_name) > 180:
        raise ValueError('提交人姓名或项目名称过长')
    continuation_id = str(metadata.get('continuation_id', '')).strip()
    continuation_receipt = str(metadata.get('continuation_receipt', '')).strip()
    if continuation_id or continuation_receipt:
        if not public or not continuation_id or not continuation_receipt:
            raise ValueError('连续提交须提供上一份有效回执')
        previous = receipt_view(continuation_id, continuation_receipt)
        if (previous.get('submitter', '').strip() != submitter
                or previous.get('project_name', '').strip() != project_name):
            raise ValueError('连续提交须与上一份的姓名和项目一致')
    batch_id = str(metadata.get('batch_id', ''))
    if batch_id and not re.fullmatch(r'[a-f0-9-]{36}', batch_id):
        raise ValueError('提交批次编号无效')
    root().mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(root()).free < size + 1024**3:
        raise ValueError('接收空间不足，请稍后重试')
    key = uuid.uuid4().hex
    folder = record_path(key)
    folder.mkdir(mode=0o700)
    name = str(metadata.get('name', '资料.txt')).replace('\\', '/').split('/')[-1][:180]
    if not name or name.startswith('.'):
        name = '资料.txt'
    digest = hashlib.sha256()
    remaining = size
    try:
        with (folder / 'content.partial').open('wb') as f:
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError('上传中断，未接收完整文件')
                f.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        shutil.rmtree(folder)
        raise
    os.replace(folder / 'content.partial', folder / 'content')
    sync_directory(folder)
    sync_directory(folder.parent)
    receipt = secrets.token_urlsafe(32) if public else None
    if public and metadata.get('batch_token'):
        from inresearch.materials import batch_review
        receipt=batch_review.receipt_for(metadata['batch_token'],key)
    record = dict(id=key, name=name, size=size, sha256=digest.hexdigest(), user=user,
                  topic=str(metadata.get('topic', ''))[:300], source=str(metadata.get('source', ''))[:2000],
                  note=str(metadata.get('note', ''))[:4000],
                  submitter=submitter, project_name=project_name, batch_id=batch_id,
                  continuation_of=continuation_id or None,
                  package_id=str(metadata.get('package_id', ''))[:100],
                  batch_total=metadata.get('batch_total'), batch_index=metadata.get('batch_index'),
                  batch_token_hash=(hashlib.sha256(metadata['batch_token'].encode()).hexdigest()
                                    if metadata.get('batch_token') else None),
                  created=time.time(), status='pending_approval', revision=0,
                  feedback=[], operations=[])
    if receipt:
        record['receipt_hash'] = hashlib.sha256(receipt.encode()).hexdigest()
    atomic(folder / 'record.json', record)
    return (public_view(record), receipt) if public else public_view(record)


def public_view(record):
    """Never expose receipt verifiers or operation bodies in an API response."""
    result = {k: v for k, v in record.items() if k not in ('receipt_hash', 'batch_token_hash', 'batch_excluded', 'operations', 'analysis_reports')}
    from inresearch.materials import batch_review
    batch = batch_review.upload_view(record)
    if batch is not None: result['upload_batch'] = batch
    return result


def owner_view(record):
    result = {k: v for k, v in record.items() if k not in ('receipt_hash', 'batch_token_hash', 'operations')}
    from inresearch.materials import batch_review
    batch = batch_review.upload_view(record,owner=True)
    if batch is not None: result['upload_batch'] = batch
    if record.get('review_batch_id'):
        manifest=batch_review.load_review(record['review_batch_id'])
        if manifest.get('state') == 'prepared':
            result['review_batch_recovery']=manifest['request']
    return result


def receipt_view(key, receipt):
    if not isinstance(receipt, str) or len(receipt) > 128:
        raise PermissionError('invalid receipt')
    record = load(key)
    expected = record.get('receipt_hash', '')
    supplied = hashlib.sha256(receipt.encode()).hexdigest()
    if not expected or not hmac.compare_digest(expected, supplied):
        raise PermissionError('invalid receipt')
    return public_view(record)

def records():
    return sorted((json.loads(p.read_text()) for p in root().glob('*/record.json')), key=lambda r:r['created'], reverse=True)

def acknowledge(key, sha):
    path = record_path(key) / 'record.json'
    with locked(path):
        record = json.loads(path.read_text())
        if sha != record['sha256']:
            raise ValueError('checksum mismatch')
        require_approved(record)
        if record.get('status') != 'archived':
            record.update(status='archived', archived=time.time(), revision=record.get('revision', 0)+1)
            atomic(path, record)
    return record


class Conflict(ValueError):
    pass


def approver():
    """One deployment-declared owner; other admins cannot approve by role alone."""
    return os.environ.get('INRESEARCH_MATERIAL_APPROVER',
                          os.environ.get('HUB_ADMIN_USERNAME', 'admin')).strip()


def can_approve(actor, role):
    return role == 'admin' and bool(actor) and actor == approver()


def require_approved(record):
    from inresearch.materials import batch_review
    if not batch_review.review_ready(record):
        raise PermissionError('联合审批尚未完整提交，不能分析')
    approval = record.get('approval', {})
    if (record.get('status') not in ('approved', 'archived')
            or not approval.get('by') or not approval.get('at')
            or approval.get('sha256') != record.get('sha256')):
        raise PermissionError('文件尚未经负责人批准，不能分析')


def load(key):
    return json.loads((record_path(key) / 'record.json').read_text())


def worker_record(key):
    record = load(key)
    require_approved(record)
    content = record_path(key) / 'content'
    digest = hashlib.sha256()
    with content.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if content.stat().st_size != record['size'] or digest.hexdigest() != record['sha256']:
        raise ValueError('原件内容已变化，停止分析')
    return public_view(record)


def pending():
    result = []
    for record in records():
        if record.get('status') != 'approved':
            continue
        try:
            require_approved(record)
        except PermissionError:
            continue
        result.append(public_view(record))
    return result


def analysis_pending():
    """Release a batch only when all approved originals are archived; retain replay members."""
    from inresearch.materials import batch_review
    all_records = records()
    by_id = {row['id']:row for row in all_records}
    result, released = [], set()
    for record in all_records:
        if record.get('review_batch_id'):
            key = record['review_batch_id']
            if key in released: continue
            released.add(key)
            try:
                manifest = batch_review.load_review(key)
                members = [by_id[row['id']] for row in manifest['request']['items']]
                if manifest.get('analysis_complete') or any(row['status'] != 'archived' for row in members):
                    continue
                for row in members: require_approved(row)
            except (KeyError,ValueError,OSError,PermissionError):
                continue
            for row in members:
                item = public_view(row)
                item['review_batch_members'] = [dict(id=m['id'],sha256=m['sha256']) for m in members]
                result.append(item)
            continue
        if (record.get('status') != 'archived' or not record.get('analysis_requested_at')
                or record.get('analysis_reports')
                or (record.get('analysis_progress') or {}).get('state') == 'source_error'
                or not reviewable(record['name'])):
            continue
        try: require_approved(record)
        except PermissionError: continue
        result.append(public_view(record))
    return result



def bounded_analysis_pending(limit=40):
    """A response may cross the nominal limit once, but never cuts a review batch."""
    pending=analysis_pending()
    selected=[];seen=set()
    for item in pending:
        if item['id'] in seen: continue
        if len(selected)>=limit: break
        batch_id=item.get('review_batch_id')
        group=([row for row in pending if row.get('review_batch_id')==batch_id]
               if batch_id else [item])
        selected.extend(group);seen.update(row['id'] for row in group)
    return selected


def previous_system_task(record):
    """Follow only a receipt-verified chain; a matching anonymous name is not proof."""
    seen={record['id']}
    prior=record.get('continuation_of')
    for _ in range(100):
        if not prior or prior in seen:break
        seen.add(prior)
        try:previous=load(prior)
        except (ValueError, OSError, json.JSONDecodeError):break
        if (previous.get('submitter', '').strip() != record.get('submitter', '').strip()
                or previous.get('project_name', '').strip() != record.get('project_name', '').strip()):
            break
        reports=previous.get('analysis_reports') or []
        if reports:
            latest=max(reports,key=lambda row:row.get('at',0))
            task=latest.get('employee_task','')
            if isinstance(task,str) and task.strip():
                return {'submission_id':previous['id'],'at':latest.get('at'),
                        'task':task[:12000],'kind':'analysis_task'}
        feedback=[row for row in previous.get('feedback',[])
                  if row.get('by') in ('analysis-worker',approver()) and isinstance(row.get('text'),str)]
        if feedback:
            latest=max(feedback,key=lambda row:row.get('at',0))
            return {'submission_id':previous['id'],'at':latest.get('at'),
                    'task':latest['text'][:12000],'kind':'owner_feedback'}
        prior=previous.get('continuation_of')
    return None


def snapshot(actor, role):
    owner = can_approve(actor, role)
    items = [r for r in records() if owner or (not r.get('receipt_hash') and r['user'] == actor)]
    # Audit request bodies are internal; employees see decisions and feedback only.
    return {'items': [(owner_view(r) if owner else public_view(r)) for r in items[:200]],
            'can_approve': owner, 'can_upload': role in ('admin', 'member', 'intern'),
            'approver': approver() if owner else None}


def finish_analysis(key, sha, analysis_id, owner_report, employee_task):
    """Append one immutable analysis receipt and one public employee task.

    The caller must have completed publication checks first. A retry with the
    same analysis ID is harmless; a changed source cannot inherit this report.
    """
    if not isinstance(analysis_id, str) or not re.fullmatch(r'[a-f0-9-]{36}', analysis_id):
        raise ValueError('analysis_id required')
    uuid.UUID(analysis_id)
    if (not isinstance(owner_report, dict) or len(json.dumps(owner_report, ensure_ascii=False)) > 100000
            or not isinstance(employee_task, str) or not employee_task.strip()
            or len(employee_task) > 20000):
        raise ValueError('analysis report or employee task invalid')
    path = record_path(key) / 'record.json'
    with locked(path):
        record = json.loads(path.read_text())
        require_approved(record)
        if record['sha256'] != sha:
            raise Conflict('analysis source changed')
        existing = next((r for r in record.get('analysis_reports', []) if r['id'] == analysis_id), None)
        if existing:
            if existing['report'] != owner_report or existing['employee_task'] != employee_task:
                raise Conflict('analysis replay changed')
            return owner_view(record)
        now = time.time()
        record.setdefault('analysis_reports', []).append({'id':analysis_id, 'at':now,
            'sha256':sha, 'report':owner_report, 'employee_task':employee_task})
        published = owner_report.get('published', [])
        scope = owner_report.get('review_scope')
        scope = scope if isinstance(scope, dict) else {}
        sampled = scope.get('mode') == 'sampled_native_cells'
        if sampled:
            if published:
                raise ValueError('sampled analysis cannot publish')
            record['analysis_scope'] = {key: scope[key] for key in (
                'mode', 'total_sheets', 'total_nonblank_rows', 'total_nonblank_cells',
                'excerpted_rows', 'excerpted_cells', 'prefix_only_cells',
                'not_excerpted_cells', 'not_fully_seen_cells', 'excerpt_character_limit')}
        record.setdefault('feedback', []).append({'id':analysis_id, 'by':'analysis-worker',
            'at':now, 'sha256':sha,
            'result':('sampled_incomplete' if sampled else 'accepted' if published and not owner_report.get('held')
                      and not owner_report.get('findings') else 'revision_required'),
            'text':employee_task})
        source_error = owner_report.get('publication',{}).get('state') == 'source_error'
        state = 'source_error' if source_error else 'sampled_incomplete' if sampled else 'completed'
        record['analysis_state'] = state
        total = 0 if source_error else record.get('analysis_progress', {}).get('total', 0)
        record['analysis_progress'] = {'state':state, 'completed':total,
                                       'total':total, 'at':now}
        record['revision'] = record.get('revision', 0) + 1
        atomic(path, record)
    return owner_view(record)


def set_analysis_progress(key, sha, completed, total, state='running', *, error_code=None):
    if (type(completed) is not int or type(total) is not int or not 0 <= completed <= total <= 200
            or state not in ('running', 'blocked', 'source_error')):
        raise ValueError('invalid analysis progress')
    path = record_path(key) / 'record.json'
    with locked(path):
        record = json.loads(path.read_text())
        require_approved(record)
        if (record['sha256'] != sha or not record.get('analysis_requested_at')
                or record['status'] != 'archived'):
            raise PermissionError('analysis not requested for this source')
        if record.get('analysis_reports'):
            return public_view(record)
        if ((record.get('analysis_progress') or {}).get('state') == 'source_error'
                and state != 'source_error'):
            raise Conflict('原件需修复并重新提交，不能恢复旧分析')
        if (state == 'source_error' and not any(
                row.get('by') == 'analysis-worker' and row.get('result') == 'revision_required'
                for row in record.get('feedback', []))):
            raise ValueError('原件错误须先登记可见的修改任务')
        record['analysis_progress'] = {'state':state, 'completed':completed,
                                       'total':total, 'at':time.time()}
        if state=='blocked' and error_code=='joint_model_output_invalid_requires_operator':
            record['analysis_progress']['error_code']=error_code
        atomic(path, record)
    return public_view(record)


def mutate(payload, actor, role, *, worker=False, valid_package_ids=None):
    if not isinstance(payload, dict):
        raise ValueError('object required')
    action = payload.get('action')
    if worker:
        if action != 'feedback':
            raise PermissionError('worker cannot approve')
    elif not can_approve(actor, role):
        raise PermissionError('仅指定负责人可以批准或登记分析反馈')
    operation = payload.get('operation_id', '')
    if not isinstance(operation, str) or not re.fullmatch(r'[a-f0-9-]{36}', operation):
        raise ValueError('operation_id required')
    uuid.UUID(operation)
    revision = payload.get('expected_revision')
    if type(revision) is not int or revision < 0:
        raise ValueError('expected_revision required')
    path = record_path(payload.get('id', '')) / 'record.json'
    with locked(path):
        record = json.loads(path.read_text())
        from inresearch.materials import batch_review
        if not batch_review.review_ready(record):
            raise Conflict('联合审批待恢复，请重试原批次操作')
        if record.get('review_batch_id') and action == 'assign_package':
            raise Conflict('联合审批已封存工作包；请完成本轮或重新提交')
        for previous in record.get('operations', []):
            if previous['id'] == operation:
                if previous['request'] != payload or previous['by'] != actor:
                    raise Conflict('重复操作的内容或操作者不一致')
                return public_view(record)
        if revision != record.get('revision', 0) or payload.get('sha256') != record['sha256']:
            raise Conflict('文件版本或状态已变化，请刷新后重试')
        now = time.time()
        before = record['status']
        if record.get('batch_total') and action in ('approve','approve_and_analyze','start_analysis'):
            upload=batch_review.upload_view(record,owner=True)
            if not upload or not upload['sealed']:
                raise Conflict('请先恢复并封存本次上传批次')
            siblings=[load(key) for key in upload['member_ids'] if key != record['id']]
            if action in ('approve_and_analyze','start_analysis') and any(row['status'] != 'rejected' for row in siblings):
                raise Conflict('同批多附件请使用整批确认并关联审阅')
            record['batch_excluded']=[{'id':row['id'],'sha256':row['sha256'],'status':row['status']} for row in siblings]
        if action in ('approve', 'approve_and_analyze', 'reject'):
            if before not in ('pending_approval', 'queued') or record.get('approval'):
                raise Conflict('该文件已处理；新版文件须重新上传批准')
            note = payload.get('note', '')
            if not isinstance(note, str) or len(note) > 4000:
                raise ValueError('审批备注最多4000字')
            if action == 'reject' and not note.strip():
                raise ValueError('请填写退回原因')
            if action == 'approve_and_analyze' and not reviewable(record['name']):
                raise ValueError('该文件格式暂不支持自动分析，请单独批准并人工查看')
            record.update(status='approved' if action in ('approve', 'approve_and_analyze') else 'rejected',
                          decision={'by':actor, 'at':now, 'action':action, 'note':note})
            if action in ('approve', 'approve_and_analyze'):
                # Verify the exact bytes before granting any analysis permission.
                content = path.parent / 'content'
                digest = hashlib.sha256()
                with content.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                if content.stat().st_size != record['size'] or digest.hexdigest() != record['sha256']:
                    raise ValueError('原件内容已变化，不能批准')
                record['approval'] = {'by':actor, 'at':now, 'sha256':record['sha256']}
                if action == 'approve_and_analyze':
                    record['analysis_requested_at'] = now
        elif action == 'assign_package':
            if set(payload) != {'id', 'sha256', 'expected_revision', 'operation_id', 'action', 'package_id'}:
                raise ValueError('工作包绑定请求字段无效')
            package_id = payload['package_id']
            if (not isinstance(package_id, str) or not 1 <= len(package_id) <= 100
                    or package_id not in (valid_package_ids or ())):
                raise ValueError('请选择当前有效的系统工作包')
            if (before == 'rejected' or record.get('analysis_reports')
                    or (record.get('analysis_progress') or {}).get('state') == 'source_error'
                    or any((path.parent / 'analysis-outbox').glob('*.json'))):
                raise Conflict('文件已有分析结果、待恢复发布事务或已终止，不能修改工作包')
            previous_package_id = record.get('package_id', '')
            record['package_id'] = package_id
        elif action == 'start_analysis':
            require_approved(record)
            if not reviewable(record['name']):
                raise ValueError('该文件格式暂不支持自动分析')
            if before != 'archived' or record.get('analysis_requested_at'):
                raise Conflict('分析已启动，或研究端尚未接收')
            record['analysis_requested_at'] = now
        elif action == 'feedback':
            require_approved(record)
            text, result = payload.get('text'), payload.get('result')
            if not isinstance(text, str) or not text.strip() or len(text) > 20000:
                raise ValueError('反馈须为1至20000字')
            if result not in ('revision_required', 'accepted', 'blocked', 'ineligible'):
                raise ValueError('请选择验收结论')
            record.setdefault('feedback', []).append({'id':operation, 'by':actor, 'at':now,
                'sha256':record['sha256'], 'result':result, 'text':text.strip()})
        else:
            raise ValueError('unknown material action')
        record['revision'] = record.get('revision', 0) + 1
        audit = {'id':operation, 'by':actor, 'at':now,
                 'before':before, 'after':record['status'], 'request':payload}
        if action == 'assign_package':
            audit.update(before_package_id=previous_package_id, after_package_id=package_id)
        record.setdefault('operations', []).append(audit)
        atomic(path, record)
    return public_view(record)
