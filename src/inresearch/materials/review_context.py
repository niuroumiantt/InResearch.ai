"""Server-owned task and current publication context for approved submissions."""
import hashlib
import json

from inresearch.delivery import source_publication
from inresearch.knowledge import site_timeline
from inresearch.materials import inbox
from inresearch.workflow import research_tasks


def site_index(records):
    fields = ('status', 'power_status', 'utility', 'capacity_it_mw',
              'capacity_facility_mw', 'capacity_planned_it_mw')
    result = []
    for row in records:
        if not row.get('site_id') or not row.get('name'):
            continue
        current = site_timeline.current(row)
        selected = current.get('tracking', {}).get('fields', {})
        facts = {}
        for field in fields:
            value = current.get('quantity_fields', {}).get(field, current.get(field))
            if value in (None, '', [], {}):
                continue
            pointer = selected.get(field, {})
            facts[field] = {'value': value, 'observation_id': pointer.get('observation_id'),
                            'as_of': pointer.get('effective_at'),
                            'recorded_at': pointer.get('recorded_at'),
                            'registration_status': pointer.get('registration_status')}
        result.append({'site_id': row['site_id'], 'name': row['name'],
                       'aliases': (row.get('aliases') or [])[:5],
                       'country': row.get('country'), 'location': row.get('location'),
                       'current_fields': facts})
    return sorted(result, key=lambda row: row['site_id'])


def shared_progress(records, package_id):
    rows = []
    for record in records:
        if package_id and record.get('package_id') != package_id:
            continue
        for entry in record.get('analysis_reports', []):
            for published in entry.get('report', {}).get('published', []):
                if isinstance(published, dict) and published.get('site_id') and published.get('statement_id'):
                    rows.append({'at': entry.get('at'), 'site_id': published['site_id'],
                                 'field': published.get('field'),
                                 'statement_id': published['statement_id'],
                                 'registration_kind': published.get('registration_kind', 'new')})
    latest = {}
    for row in rows:
        ident = row['statement_id']
        if ident not in latest or (row.get('at') or 0) > (latest[ident].get('at') or 0):
            latest[ident] = row
    return {'scope': 'work_package' if package_id else 'mission',
            'published_statements': len(latest),
            'recent': sorted(latest.values(), key=lambda row: row.get('at') or 0, reverse=True)[:25]}


def assigned_task(record, task_state, mission, index, task_records, source_state_sha256):
    package = next((row for row in task_state['packages']
                    if row['id'] == record.get('package_id')), None)
    package_id = package['id'] if package else None
    index_sha = hashlib.sha256(json.dumps(index, ensure_ascii=False,
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    shared_task = (research_tasks.package_workflow(
        package, task_records, task_edits=research_tasks.package_task_edits(task_state, package_id))['current_task']
                   if package else None)
    return {
        'task_revision': task_state['revision'],
        'mission_title': mission['title'], 'mission_goal': mission['goal'],
        'source_state_sha256': source_state_sha256,
        'site_index_sha256': index_sha,
        'site_index_total': len(index),
        'site_index_sent': min(len(index), 500),
        'package': ({key: package.get(key) for key in
                     ('id', 'title', 'region', 'scope', 'sources')} if package else None),
        'shared_progress': shared_progress(task_records, package_id),
        'shared_next_task': shared_task,
        'previous_system_task': inbox.previous_system_task(record),
        'continuity': ('verified_receipt' if record.get('continuation_of')
                       else 'new_or_unlinked'),
    }


def current(root, record, *, runtime=None, task_records=None):
    state = research_tasks.read(root)
    mission = research_tasks.plan(root)['mission']
    if runtime is None:
        runtime = source_publication.state(root)
    registered = source_publication.projects(root, runtime=runtime)['records']
    index = site_index(registered)
    task = assigned_task(record, state, mission, index, inbox.records() if task_records is None else task_records,
                         source_publication.digest(runtime))
    return task, index[:500]


def provenance(task):
    return {'revision': task['task_revision'],
            'sha256': hashlib.sha256(json.dumps(task, ensure_ascii=False, sort_keys=True,
                                               separators=(',', ':')).encode()).hexdigest(),
            'previous_submission_id': (task.get('previous_system_task') or {}).get('submission_id')}
