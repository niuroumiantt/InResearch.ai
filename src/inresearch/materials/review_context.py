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
        if (not row.get('site_id') or not row.get('name') or row.get('duplicate_of')
                or row.get('identity_scope') in ('cluster','portfolio')):
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
        package, task_records, {row['site_id'] for row in index}, task_edits=research_tasks.package_task_edits(task_state, package_id),
        task_scope_revision=research_tasks.package_scope_revision(task_state,package_id))['current_task']
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
        'current_task': shared_task,
        'execution_policy': 'live_work_package_feedback_v2',
    }


def current(root, record, *, runtime=None, task_records=None):
    state = research_tasks.read(root)
    mission = research_tasks.plan(root)['mission']
    if runtime is None:
        runtime, source_state_sha256 = source_publication.site_context(root)
    else:
        source_state_sha256 = source_publication.digest(runtime)
    registered = source_publication.projects(root, runtime=runtime)['records']
    index = site_index(registered)
    task = assigned_task(record, state, mission, index, inbox.records() if task_records is None else task_records,
                         source_state_sha256)
    return task, index[:500]


def execution_task(task):
    """Old receipt-linked task prose is evidence history, never live instructions."""
    return {key:value for key,value in task.items() if key not in ('previous_system_task','continuity')}


def provenance(task):
    return {'revision': task['task_revision'],
            'sha256': hashlib.sha256(json.dumps(execution_task(task), ensure_ascii=False, sort_keys=True,
                                               separators=(',', ':')).encode()).hexdigest(),
            'previous_submission_id': None}


def before_batch_results(records, analysis_ids):
    """Pure comparison view of the pre-batch context; never write or mutate stored history.

    Both immutable report and matching receipt feedback remain in the authoritative
    inbox. Only this freshly constructed task snapshot omits this attempt's own
    additions, allowing the existing CAS to distinguish external changes.
    """
    return [{**record,
             'analysis_reports':[entry for entry in record.get('analysis_reports',[])
                                 if entry.get('id') != analysis_ids.get(record['id'])],
             'feedback':[entry for entry in record.get('feedback',[])
                         if entry.get('id') != analysis_ids.get(record['id'])]}
            if record['id'] in analysis_ids else dict(record) for record in records]


CAMPUS_CONTEXT_POLICY = 'independent-campus-context-v1'


def campus_descriptor(record, task_state, mission, registered, task_records):
    """Server-owned dependencies, separate from the shared progress dashboard.

    Include every identity (also duplicates/parents) in the matching inventory.
    Bind complete records, not only the small fields shown in model prompts.
    Manual owner feedback remains a common dependency until explicitly scoped.
    """
    from inresearch.materials.native_review_contract import digest
    package_id = record.get('package_id')
    package = next((r for r in task_state['packages'] if r['id'] == package_id), None)
    feedback = []
    for row in task_records:
        if row.get('package_id') != package_id:
            continue
        report_ids = {r.get('id') for r in row.get('analysis_reports', [])}
        for entry in row.get('feedback', []):
            if entry.get('id') not in report_ids and entry.get('by') == inbox.approver():
                feedback.append({'submission_id': row['id'], 'feedback': entry})
    identities = []
    for row in registered:
        if not row.get('site_id'):
            continue
        projection = site_index([{**row, 'duplicate_of': None, 'identity_scope': 'site'}])
        if not projection:
            continue
        identities.append({**projection[0], 'aliases': row.get('aliases') or [],
                           'record_sha256': digest(row)})
    return {'policy': CAMPUS_CONTEXT_POLICY,
            'task_revision': research_tasks.package_scope_revision(task_state, package_id),
            'mission_title': mission['title'], 'mission_goal': mission['goal'],
            'package': ({k: package.get(k) for k in ('id','title','region','scope','sources')}
                        if package else None),
            'owner_feedback': sorted(feedback, key=lambda r: (r['submission_id'], digest(r['feedback']))),
            'identities': sorted(identities, key=lambda r: r['site_id'])}


def campus_task(descriptor, packet):
    """Recompute the same complete native-packet dependencies on both ends."""
    from inresearch.materials.review_worker import matching_sites
    from inresearch.materials.native_review_contract import digest
    if descriptor.get('policy') != CAMPUS_CONTEXT_POLICY:
        raise ValueError('campus_context_policy_unknown')
    identities = descriptor['identities']
    # No 500-row input cap or 25-match dependency cap: newly added matching
    # identities and aliases must invalidate an in-flight result too.
    matches = matching_sites(identities, (c['value'] for c in packet['cells']),
                             limit=len(identities))
    task = {k: v for k, v in descriptor.items() if k != 'identities'}
    task.update(execution_policy=CAMPUS_CONTEXT_POLICY,
                package_id=packet['package_id'],
                identity_dependencies=[{'site_id': r['site_id'], 'sha256': r['record_sha256']}
                                       for r in matches])
    task['identity_dependencies_sha256'] = digest(task['identity_dependencies'])
    return task, [{k:v for k,v in r.items() if k != 'record_sha256'} for r in matches[:25]]
