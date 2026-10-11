"""Time-ordered site observations in the existing project register.

The stored project remains the legacy baseline. Observations append evidence;
this projection never rewrites that baseline or uses ingestion time as event time.
"""
import copy
import json
import re
from datetime import date
from urllib.parse import urlsplit
from inresearch.knowledge.data_rules import FRESH_DAYS

FIELDS = frozenset(('name', 'developer', 'tenant', 'owner', 'operator', 'builder',
                    'status', 'lifecycle', 'power_status', 'utility', 'notes',
                    'capacity_it_mw', 'capacity_it_mw_by_status',
                    'capacity_facility_mw', 'capacity_assessment'))
KINDS = frozenset(('disclosed', 'reported', 'estimated', 'derived', 'forecast'))


def check(observation):
    """Check structure; source/C3 review is enforced by the writing workflow."""
    if not isinstance(observation, dict):
        raise ValueError('invalid_site_observation')
    for key in ('id', 'recorded_at', 'basis'):
        if not isinstance(observation.get(key), str) or not observation[key].strip():
            raise ValueError('site_observation_required:' + key)
    if 'effective_at' not in observation:
        raise ValueError('site_observation_required:effective_at')
    effective = observation['effective_at']
    if effective is not None:
        if not isinstance(effective, str) or not re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?', effective):
            raise ValueError('invalid_observation_effective_time')
        date.fromisoformat(effective + ('-01-01' if len(effective) == 4 else '-01' if len(effective) == 7 else ''))
    date.fromisoformat(observation['recorded_at'][:10])
    if observation.get('kind') not in KINDS or observation.get('scope') != 'whole_site':
        raise ValueError('site_observation_kind_or_scope')
    fields = observation.get('fields')
    if not isinstance(fields, dict) or not fields or set(fields) - FIELDS:
        raise ValueError('site_observation_fields')
    assumptions = observation.get('assumptions', [])
    if not isinstance(assumptions, list) or any(not isinstance(v,str) or not v.strip() for v in assumptions):
        raise ValueError('site_estimate_assumptions_invalid')
    if observation['kind'] in ('estimated', 'derived') and not assumptions:
        raise ValueError('site_estimate_assumptions_required')
    if fields.get('status') is not None and fields['status'] not in {'L'+str(i) for i in range(1, 10)}:
        raise ValueError('site_observation_stage')
    if 'lifecycle' in fields and fields['lifecycle'] not in ('active', 'paused', 'cancelled', 'closed'):
        raise ValueError('site_observation_lifecycle')
    for key in ('developer', 'tenant', 'owner', 'operator', 'builder'):
        if key in fields and (not isinstance(fields[key], list) or
                              any(not isinstance(v, str) or not v for v in fields[key])):
            raise ValueError('site_observation_actor')
    for key in ('capacity_it_mw', 'capacity_facility_mw'):
        if key in fields and fields[key] is not None:
            _number(fields[key])
    parts = fields.get('capacity_it_mw_by_status')
    if parts is not None:
        if not isinstance(parts, dict) or set(parts) - {'L'+str(i) for i in range(1, 10)}:
            raise ValueError('site_observation_capacity_parts')
        for value in parts.values():
            _number(value)
    # IT headline and phase breakdown form one bundle: explicit clearing prevents
    # a later headline from accidentally adding to a legacy phase breakdown.
    if {'capacity_it_mw', 'capacity_it_mw_by_status', 'capacity_assessment'} & fields.keys():
        if not {'capacity_it_mw', 'capacity_it_mw_by_status', 'capacity_assessment'} <= fields.keys():
            raise ValueError('site_observation_capacity_bundle_required')
        if fields['capacity_it_mw'] is not None and fields['capacity_it_mw_by_status']:
            raise ValueError('site_observation_capacity_overlap')
    if not isinstance(observation.get('adoption'), dict) or not observation['adoption'].get('review_id'):
        raise ValueError('site_observation_review_required')
    return observation


def _number(value):
    import math
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError('site_observation_capacity_value')


def append(project, observation):
    check(observation)
    result = copy.deepcopy(project)
    rows = result.setdefault('observations', [])
    prior = next((r for r in rows if r['id'] == observation['id']), None)
    if prior is not None:
        if prior != observation:
            raise ValueError('site_observation_id_conflict')
        return result, True
    rows.append(copy.deepcopy(observation))
    return result, False


def adoptions(project):
    return ([project['adoption']] if project.get('adoption') else []) + [
        row['adoption'] for row in project.get('observations', [])]


def current(project, today=None):
    """Latest effective observation per field; future forecasts stay separate.

    Equal-time disagreement is visible and does not pick a winner by arrival
    order. Unknown-time legacy values are only the fallback, never invented dates.
    """
    today = today or date.today().isoformat()
    result = copy.deepcopy(project)
    observations = project.get('observations', [])
    grouped, conflicts, selected = {}, [], {}
    forecasts, imprecise = [], []
    for row in observations:
        check(row)
        if row['kind'] == 'forecast':
            forecasts.append(row)
            continue
        if row.get('effective_at') is None or len(row['effective_at']) != 10:
            imprecise.append(row)
            continue
        if row['effective_at'] > today:
            forecasts.append(row)
            continue
        for field in row['fields']:
            group = 'it_capacity_bundle' if field in ('capacity_it_mw', 'capacity_it_mw_by_status', 'capacity_assessment') else field
            if row not in grouped.setdefault(group, []):
                grouped[group].append(row)
    for group, rows in grouped.items():
        fields = ('capacity_it_mw', 'capacity_it_mw_by_status', 'capacity_assessment') if group == 'it_capacity_bundle' else (group,)
        chosen = None
        for latest in sorted({r['effective_at'] for r in rows}, reverse=True):
            peers = [r for r in rows if r['effective_at'] == latest]
            variants = {json.dumps({f: r['fields'].get(f) for f in fields}, sort_keys=True, ensure_ascii=False) for r in peers}
            if len(variants) != 1:
                conflicts.append({'field': group, 'effective_at': latest,
                                  'observation_ids': sorted(r['id'] for r in peers)})
                continue
            chosen = min(peers, key=lambda r: r['id'])
            break
        if chosen is None:
            continue
        for field in fields:
            result[field] = copy.deepcopy(chosen['fields'].get(field))
            selected[field] = {'effective_at': latest, 'observation_id': chosen['id'],
                               'kind': chosen['kind'], 'recorded_at': chosen['recorded_at'],
                               'reviewed_at': max(r['recorded_at'] for r in peers)}
        if group == 'it_capacity_bundle' and chosen['kind'] in ('estimated', 'derived'):
            result['capacity_assessment'] = {
                'kind':'estimate', 'status':'reviewed', 'as_of':chosen['effective_at'],
                'recorded_at':chosen['recorded_at'][:10], 'basis_note':chosen['basis'],
                'assumptions':chosen['assumptions'], 'missing_conditions':[]}
    limit = FRESH_DAYS['project_late' if result.get('status') in ('L6','L7','L8','L9') else 'project_early']
    due = []
    for field in FIELDS:
        if result.get(field) in (None, '', [], {}):
            continue
        reviewed = selected[field]['reviewed_at'][:10] if field in selected else project.get('verified_date')
        age = _age(reviewed, today)
        if age is None or age > limit:
            due.append(field)
    result['tracking'] = {'fields': selected, 'conflicts': conflicts,
                          'review_due_fields': sorted(due),
                          'observations': len(observations), 'forecasts': len(forecasts),
                          'imprecise_times': len(imprecise),
                          'latest_effective_at': max((r['effective_at'] for r in selected.values()), default=None),
                          'baseline_reviewed_at': project.get('verified_date'),
                          'baseline_review_age_days': _age(project.get('verified_date'), today)}
    return result


def _age(value, today):
    try:
        return max(0, (date.fromisoformat(today) - date.fromisoformat(value)).days)
    except (ValueError, TypeError):
        return None


def public_timeline(project):
    """Public source URLs and semantic history; never private archive paths."""
    return [{'id': r['id'], 'effective_at': r['effective_at'], 'recorded_at': r['recorded_at'],
             'kind': r['kind'], 'basis': r['basis'], 'fields': copy.deepcopy(r['fields']),
             'assumptions': r.get('assumptions', []),
             'sources': [{k:s.get(k) for k in ('url', 'date', 'grade', 'note')}
                         for s in r.get('sources', []) if _safe_url(s.get('url'))]}
            for r in sorted(project.get('observations', []), key=lambda r: (r.get('effective_at') or '', r['id']), reverse=True)]


def _safe_url(value):
    try:
        url = urlsplit(value)
        return url.scheme in ('http', 'https') and url.hostname and not url.username and not url.password
    except (TypeError, ValueError, AttributeError):
        return False
