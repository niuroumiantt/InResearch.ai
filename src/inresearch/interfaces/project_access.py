"""Project membership, separate from site administration and source access.

Only the deployment's owner grants access. The current mission is the project
catalog; private account records hold grants, immutable identities and audit.
"""
from datetime import datetime, timezone
import copy
import time

from inresearch.interfaces import auth, public
from inresearch.paths import project_root


def catalog(root=None):
    from inresearch.workflow import research_tasks
    root = root or project_root()
    return research_tasks.plan(root)['mission'], research_tasks.read(root)['packages']


def is_owner(actor):
    from inresearch.materials import inbox
    return bool(actor) and auth.user_role(actor) == 'admin' and actor == inbox.approver()


def grant(actor, root=None):
    mission, _ = catalog(root)
    user = auth.load_users().get(actor, {})
    value = user.get('projects', {}).get(mission['id'], {})
    if not user or user.get('disabled') or user.get('must_change_password') or not value.get('enabled'):
        return {}
    expiry = value.get('expires_at')
    if expiry:
        try:
            end = datetime.fromisoformat(expiry)
            if end.tzinfo is None or end.timestamp() <= time.time():
                return {}
        except (ValueError, TypeError):
            return {}
    return value


def member(actor, root=None):
    return bool(actor) and (auth.user_role(actor) in ('admin', 'member', 'intern') or bool(grant(actor, root)))


def can_submit(actor, package_id, root=None):
    if not actor or not package_id:
        return False
    role = auth.user_role(actor)
    _, packages = catalog(root)
    package = next((p for p in packages if p['id'] == package_id), None)
    if not package:
        return False
    if role in ('admin', 'member'):
        return True
    if role == 'intern':
        from inresearch.workflow.research_tasks import assigned_members
        return actor in assigned_members(package['assignee'])
    return package_id in grant(actor, root).get('submit_packages', [])


def owns(actor, record):
    user = auth.load_users().get(actor, {})
    # Old anonymous names never establish account identity.
    return bool(user.get('id')) and record.get('owner_id') == user['id']


def can_review(actor, record=None, root=None):
    if not actor:
        return False
    value = grant(actor, root)
    if record is None:
        return is_owner(actor) or bool(value.get('approve_packages'))
    if owns(actor, record):
        return False
    if is_owner(actor):
        return True
    mission, _ = catalog(root)
    return (record.get('project_id') == mission['id']
            and record.get('package_id') in value.get('approve_packages', []))


def readable(actor, role, record):
    if can_review(actor, record):
        return True
    if owns(actor, record):
        mission, _ = catalog()
        return member(actor) and record.get('project_id') == mission['id']
    return (role in ('admin', 'member', 'intern') and not record.get('owner_id')
            and not record.get('receipt_hash') and record.get('user') == actor)


def allowed(actor, path, query='', method='GET'):
    """Collaborators never inherit the broad member or admin route grants."""
    if method == 'POST':
        return path in ('/api/passwd', '/api/logout', '/api/task-uploads',
                        '/api/task-uploads/receipt', '/api/task-uploads/batch',
                        '/api/task-uploads/batch-status',
                        '/api/materials/review', '/api/materials/review-batch')
    if method not in ('GET', 'HEAD'):
        return False
    if public.allowed(path, query) or path in ('/account', '/logout', '/api/project-work', '/api/navigation'):
        return True
    if path in ('/api/materials', '/task-reviews.html', '/assets/task-reviews.js', '/assets/task-reviews.css'):
        return member(actor) and (path != '/task-reviews.html' or can_review(actor))
    if path.startswith('/api/materials/content/'):
        return member(actor)
    if path in ('/assets/project-work.js', '/assets/project-access.css'):
        return True
    # The first project's frontstage is its campus directory and detail views.
    if not grant(actor).get('frontend'):
        return False
    if path in ('/industry.html', '/projects.html', '/regions.html', '/project.html'):
        return True
    if path in ('/api/industry', '/api/observations', '/api/news', '/data/companies.json'):
        return public.customer_allowed(project_root(), path, query, method)
    return (path.startswith('/assets/') and public.customer_allowed(project_root(), path, query, method))


def settings(root=None):
    mission, packages = catalog(root)
    return {'project': mission, 'packages': [{'id':p['id'], 'title':p['title']} for p in packages],
            'users': [{'name':name, 'id':u.get('id'), 'role':u.get('role', 'member'),
                       'disabled':bool(u.get('disabled')), 'display_name':u.get('display_name', name),
                       'revision':u.get('access_revision', 0),
                       'grant':u.get('projects', {}).get(mission['id'], {})}
                      for name,u in sorted(auth.load_users().items())]}


@auth.user_write
def update(payload, actor, root=None):
    if not is_owner(actor):
        raise PermissionError('仅项目所有者可设置成员和审批授权')
    if not isinstance(payload, dict) or set(payload) != {'username', 'expected_revision', 'display_name', 'disabled', 'project_id', 'grant'}:
        raise ValueError('成员授权字段无效')
    mission, packages = catalog(root)
    if payload['project_id'] != mission['id']:
        raise ValueError('未知项目')
    users = auth.load_users()
    user = users.get(payload['username'])
    if not user or user.get('role') != 'collaborator':
        raise ValueError('此入口仅管理项目协作者；既有内部账号由账号管理维护')
    if type(payload['expected_revision']) is not int or payload['expected_revision'] != user.get('access_revision', 0):
        raise ValueError('成员权限已变化，请刷新后再保存')
    value = copy.deepcopy(payload['grant'])
    if not isinstance(value, dict) or set(value) != {'enabled', 'expires_at', 'frontend', 'submit_packages', 'approve_packages'}:
        raise ValueError('项目授权字段无效')
    if any(type(v) is not bool for v in (payload['disabled'], value['enabled'], value['frontend'])):
        raise ValueError('授权开关无效')
    valid = {p['id'] for p in packages}
    for key in ('submit_packages', 'approve_packages'):
        rows = value[key]
        if not isinstance(rows, list) or any(not isinstance(v, str) or v not in valid for v in rows) or len(rows) != len(set(rows)):
            raise ValueError('请选择当前有效工作包')
    expiry = value['expires_at']
    if expiry:
        end = datetime.fromisoformat(expiry)
        if end.tzinfo is None:
            raise ValueError('授权到期时间须带时区')
        value['expires_at'] = end.astimezone(timezone.utc).isoformat()
    elif expiry is not None:
        raise ValueError('到期时间无效')
    name = payload['display_name']
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise ValueError('姓名须为1至120字')
    before = {'grant':user.get('projects', {}).get(mission['id'], {}), 'disabled':bool(user.get('disabled')),
              'display_name':user.get('display_name', payload['username'])}
    user.setdefault('projects', {})[mission['id']] = value
    user.update(display_name=name.strip(), disabled=payload['disabled'], access_revision=user.get('access_revision', 0)+1)
    # Removing/changing access invalidates all old sessions, including copied cookies.
    user['session_version'] = user.get('session_version', 0)+1
    user.setdefault('access_history', []).append({'by':actor, 'at':time.time(), 'project_id':mission['id'],
                                                 'before':before, 'after':copy.deepcopy(payload)})
    auth.save_users(users)
    return {'ok':True, 'revision':user['access_revision']}


def workbench(actor, root=None):
    from inresearch.materials import inbox
    mission, packages = catalog(root)
    user = auth.load_users().get(actor, {})
    # Existing signed-in users may still have a pre-migration cookie. Upgrade
    # identity before exposing per-account recovery storage keys, without logout.
    if user and not user.get('id'):
        user['id'] = auth.ensure_identity(actor)
    access = member(actor, root)
    mine = []
    if access:
        for row in inbox.records():
            if not owns(actor, row) or row.get('project_id') != mission['id']:
                continue
            item = {k:row.get(k) for k in ('id','name','package_id','created','status','analysis_state','analysis_scope','analysis_progress','decision')}
            # Historical feedback is context only; current next action is the shared package task.
            item['feedback'] = row.get('feedback', [])[-1:]
            item['published_sources'] = len({p['statement_id'] for report in row.get('analysis_reports', [])
                                            for p in report.get('report', {}).get('published', []) if p.get('statement_id')})
            mine.append(item)
    mine.sort(key=lambda r:r['created'], reverse=True)
    return {'ok':True, 'user':actor, 'display_name':user.get('display_name', actor), 'user_id':user.get('id'),
            'project':mission, 'member':access, 'can_manage':is_owner(actor), 'can_approve':can_review(actor),
            'frontend':bool(grant(actor, root).get('frontend')) or auth.user_role(actor) in ('admin','member','intern'),
            'expires_at':grant(actor, root).get('expires_at'),
            'packages':[{'id':p['id'], 'title':p['title'], 'status':p['status'],
                         'can_submit':can_submit(actor,p['id'],root)} for p in packages] if access else [],
            'items':mine}
