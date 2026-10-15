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
    if not 0 < size <= MAX_BYTES:
        raise ValueError('单份资料须为 1 字节至 64 MiB')
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
    record = dict(id=key, name=name, size=size, sha256=digest.hexdigest(), user=user,
                  topic=str(metadata.get('topic', ''))[:300], source=str(metadata.get('source', ''))[:2000],
                  note=str(metadata.get('note', ''))[:4000],
                  submitter=str(metadata.get('submitter', ''))[:120],
                  package_id=str(metadata.get('package_id', ''))[:100],
                  created=time.time(), status='pending_approval', revision=0,
                  feedback=[], operations=[])
    if receipt:
        record['receipt_hash'] = hashlib.sha256(receipt.encode()).hexdigest()
    atomic(folder / 'record.json', record)
    return (public_view(record), receipt) if public else public_view(record)


def public_view(record):
    """Never expose receipt verifiers or operation bodies in an API response."""
    return {k: v for k, v in record.items() if k not in ('receipt_hash', 'operations', 'analysis_reports')}


def owner_view(record):
    return {k: v for k, v in record.items() if k not in ('receipt_hash', 'operations')}


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
    """Only an archived, owner-approved XLSX can enter automatic review."""
    result = []
    for record in records():
        if (record.get('status') != 'archived' or not record.get('analysis_requested_at')
                or record.get('analysis_reports') or not record['name'].lower().endswith('.xlsx')):
            continue
        try:
            require_approved(record)
        except PermissionError:
            continue
        result.append(public_view(record))
    return result


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
        record.setdefault('feedback', []).append({'id':analysis_id, 'by':'analysis-worker',
            'at':now, 'sha256':sha,
            'result':'accepted' if published and not owner_report.get('held') and not owner_report.get('findings') else 'revision_required',
            'text':employee_task})
        record['analysis_state'] = 'completed'
        total = record.get('analysis_progress', {}).get('total', 0)
        record['analysis_progress'] = {'state':'completed', 'completed':total,
                                       'total':total, 'at':now}
        record['revision'] = record.get('revision', 0) + 1
        atomic(path, record)
    return owner_view(record)


def set_analysis_progress(key, sha, completed, total, state='running'):
    if (type(completed) is not int or type(total) is not int or not 0 <= completed <= total <= 200
            or state not in ('running', 'blocked')):
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
        record['analysis_progress'] = {'state':state, 'completed':completed,
                                       'total':total, 'at':time.time()}
        atomic(path, record)
    return public_view(record)


def mutate(payload, actor, role, *, worker=False):
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
        for previous in record.get('operations', []):
            if previous['id'] == operation:
                if previous['request'] != payload or previous['by'] != actor:
                    raise Conflict('重复操作的内容或操作者不一致')
                return public_view(record)
        if revision != record.get('revision', 0) or payload.get('sha256') != record['sha256']:
            raise Conflict('文件版本或状态已变化，请刷新后重试')
        now = time.time()
        before = record['status']
        if action in ('approve', 'approve_and_analyze', 'reject'):
            if before not in ('pending_approval', 'queued') or record.get('approval'):
                raise Conflict('该文件已处理；新版文件须重新上传批准')
            note = payload.get('note', '')
            if not isinstance(note, str) or len(note) > 4000:
                raise ValueError('审批备注最多4000字')
            if action == 'reject' and not note.strip():
                raise ValueError('请填写退回原因')
            if action == 'approve_and_analyze' and not record['name'].lower().endswith('.xlsx'):
                raise ValueError('自动分析目前仅支持 .xlsx')
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
        elif action == 'start_analysis':
            require_approved(record)
            if not record['name'].lower().endswith('.xlsx'):
                raise ValueError('自动分析目前仅支持 .xlsx')
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
        record.setdefault('operations', []).append({'id':operation, 'by':actor, 'at':now,
            'before':before, 'after':record['status'], 'request':payload})
        atomic(path, record)
    return public_view(record)
