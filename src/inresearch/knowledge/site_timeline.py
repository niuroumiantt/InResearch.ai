"""Time-ordered site observations in the existing project register.

The stored project remains the legacy baseline. Observations append evidence;
this projection never rewrites that baseline or uses ingestion time as event time.
"""
import copy
import hashlib
import json
import re
from datetime import date, datetime, timezone
from urllib.parse import urlsplit
from inresearch.knowledge.data_rules import FRESH_DAYS
from inresearch.knowledge import observation_time, site_quantity

FIELDS = frozenset(('name', 'developer', 'tenant', 'owner', 'operator', 'builder',
                    'status', 'lifecycle', 'power_status', 'utility', 'notes',
                    'capacity_it_mw', 'capacity_it_mw_by_status',
                    'capacity_facility_mw', 'capacity_assessment'))
KINDS = frozenset(('disclosed', 'reported', 'estimated', 'derived', 'forecast'))
IT_BUNDLE = ('capacity_it_mw', 'capacity_it_mw_by_status', 'capacity_assessment')


def revision_payload(row):
    """The concrete after-value an owner decision must approve, without audit clocks."""
    return {key: row.get(key) for key in ('effective_at', 'valid_until', 'scope', 'kind', 'basis', 'assumptions', 'fields')}


def revision_digest(row):
    return hashlib.sha256(json.dumps(revision_payload(row), ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def _scope(value):
    return value == 'whole_site' or isinstance(value, str) and re.fullmatch(r'phase:[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value)


def check(observation):
    """Check structure; source/C3 review is enforced by the writing workflow."""
    if not isinstance(observation, dict):
        raise ValueError('invalid_site_observation')
    for key in ('id', 'recorded_at', 'basis'):
        if not isinstance(observation.get(key), str) or not observation[key].strip():
            raise ValueError('site_observation_required:' + key)
    if 'effective_at' not in observation:
        raise ValueError('site_observation_required:effective_at')
    observation_time.validate_period(observation['effective_at'], observation.get('valid_until'))
    if observation.get('schema_version') != 2:
        if (observation.get('scope') != 'whole_site'
                or any(k in observation for k in ('valid_until', 'revision', 'source_versions', 'reviewed_at'))
                or observation_time.precision(observation['effective_at']) == 'timestamp'):
            raise ValueError('site_observation_v2_required_for_new_metadata')
    observation_time.precision(observation['recorded_at'])
    if observation.get('kind') not in KINDS or not _scope(observation.get('scope')):
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
            site_quantity.check(fields[key])
    parts = fields.get('capacity_it_mw_by_status')
    if parts is not None:
        if not isinstance(parts, dict) or set(parts) - {'L'+str(i) for i in range(1, 10)}:
            raise ValueError('site_observation_capacity_parts')
        for value in parts.values():
            if value is None:
                raise ValueError('site_observation_capacity_value')
            site_quantity.check(value)
    if observation.get('schema_version') != 2 and any(isinstance(q, dict) for q in (
            fields.get('capacity_it_mw'), fields.get('capacity_facility_mw'), *(parts or {}).values())):
        raise ValueError('site_observation_v2_required_for_new_metadata')
    # IT headline and phase breakdown form one bundle: explicit clearing prevents
    # a later headline from accidentally adding to a legacy phase breakdown.
    if {'capacity_it_mw', 'capacity_it_mw_by_status', 'capacity_assessment'} & fields.keys():
        if not {'capacity_it_mw', 'capacity_it_mw_by_status', 'capacity_assessment'} <= fields.keys():
            raise ValueError('site_observation_capacity_bundle_required')
        if fields['capacity_it_mw'] is not None and fields['capacity_it_mw_by_status']:
            raise ValueError('site_observation_capacity_overlap')
    if not isinstance(observation.get('adoption'), dict) or not observation['adoption'].get('review_id'):
        raise ValueError('site_observation_review_required')
    if observation.get('schema_version') == 2:
        from inresearch.knowledge.registry import review_valid
        review = observation['adoption'].get('review') or {}
        if not isinstance(review, dict):
            raise ValueError('site_observation_valid_c3_review_required')
        score = review.get('score')
        delegation = review.get('delegation')
        if (not review_valid({'review': review}) or type(score) is not int or not 5 <= score <= 10
                or review.get('tier') != ('A' if score >= 8 else 'B')
                or not isinstance(review.get('rationale'), str) or not review['rationale'].strip()
                or review.get('authority') == 'delegated_reviewer' and isinstance(delegation, dict)
                and delegation.get('granted_by') == review.get('by')
                or observation.get('reviewed_at') != review.get('at')):
            raise ValueError('site_observation_valid_c3_review_required')
        if observation_time.precision(observation['recorded_at']) != 'timestamp':
            raise ValueError('site_observation_recording_timestamp_required')
        if observation_time.precision(observation.get('reviewed_at')) == 'unknown':
            raise ValueError('site_observation_reviewed_at_required')
        versions = observation.get('source_versions')
        if not isinstance(versions, list) or not versions:
            raise ValueError('site_observation_source_versions_required')
        seen = set()
        for source in versions:
            sha = source.get('source_sha256') if isinstance(source, dict) else None
            if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha) or sha in seen:
                raise ValueError('site_observation_source_version_identity')
            seen.add(sha)
            for key in ('published_at', 'first_received_at'):
                if key not in source:
                    raise ValueError('site_observation_source_time_required')
                actual_precision = observation_time.precision(source[key])
                if key == 'first_received_at' and actual_precision not in ('timestamp', 'unknown'):
                    raise ValueError('first_received_timestamp_required')
                if source.get(key + '_precision') != actual_precision:
                    raise ValueError('site_observation_source_time_precision_mismatch')
                if not isinstance(source.get(key + '_provenance'), str) or not source[key + '_provenance'].strip():
                    raise ValueError('site_observation_source_time_provenance_required')
        adoption = observation['adoption']
        assertions = adoption.get('assertions')
        if (adoption.get('source_kind') not in ('daily_event', 'reader_report')
                or not isinstance(adoption.get('source_id'), str) or not adoption['source_id'].strip()
                or not re.fullmatch('[0-9a-f]{64}', str(adoption.get('source_version', '')))
                or not isinstance(adoption.get('document_refs'), list) or not adoption['document_refs']
                or not isinstance(adoption.get('target_ids'), list) or not adoption['target_ids']
                or any(not isinstance(t, str) or not t.strip() for t in adoption['target_ids'])
                or not isinstance(assertions, list) or not assertions
                or any(not isinstance(a, dict) or a.get('source_sha256') not in seen
                       or not isinstance(a.get('quote'), str) or not a['quote'].strip()
                       or not isinstance(a.get('locator'), str) or not a['locator'].strip() for a in assertions)):
            raise ValueError('site_observation_support_chain_required')
    if observation.get('revision') is not None:
        revision = observation['revision']
        if not isinstance(revision, dict) or revision.get('action') not in ('replace', 'withdraw'):
            raise ValueError('invalid_site_revision')
        targets = revision.get('observation_ids')
        if not isinstance(targets, list) or not targets or any(not isinstance(i, str) or not i for i in targets) or len(set(targets)) != len(targets):
            raise ValueError('site_revision_targets_required')
        if revision['action'] == 'withdraw' and len(targets) != 1:
            raise ValueError('site_withdrawal_requires_one_target')
        decision = revision.get('owner_decision') or {}
        review = observation['adoption'].get('review') or {}
        if (not isinstance(decision, dict) or review.get('tier') != 'A' or review.get('authority') != 'owner'
                or not decision.get('by') or decision['by'] != review.get('by')
                or decision.get('decision') != 'approved' or decision.get('action') != revision['action']
                or decision.get('observation_ids') != targets or decision.get('after_sha256') != revision_digest(observation)
                or not isinstance(decision.get('rationale'), str) or not decision['rationale'].strip()
                or not isinstance(decision.get('evidence_reference'), str) or not decision['evidence_reference'].strip()):
            raise ValueError('specific_owner_revision_decision_required')
        if observation_time.precision(decision.get('at')) not in ('day', 'timestamp'):
            raise ValueError('specific_owner_revision_decision_required')
    return observation


def _validate_chain(rows):
    prior, suppressed = {}, set()
    for row in rows:
        check(row)
        if row['id'] in prior:
            raise ValueError('site_observation_id_conflict')
        revision = row.get('revision')
        if revision:
            for ident in revision['observation_ids']:
                old = prior.get(ident)
                if old is None or ident in suppressed or (old.get('revision') or {}).get('action') == 'withdraw':
                    raise ValueError('site_revision_target_not_active')
                if old['scope'] != row['scope'] or old['effective_at'] != row['effective_at'] or set(old['fields']) != set(row['fields']):
                    raise ValueError('site_revision_scope_time_or_fields_mismatch')
                if revision['action'] == 'withdraw' and old['fields'] != row['fields']:
                    raise ValueError('site_withdrawal_must_preserve_target_values')
                suppressed.add(ident)
        prior[row['id']] = row
    return suppressed


def check_history(project):
    """Validate references as well as individual records for strict checkout validation."""
    return _validate_chain(project.get('observations', []))


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
    _validate_chain(rows)
    return result, False


def adoptions(project):
    return ([project['adoption']] if project.get('adoption') else []) + [
        row['adoption'] for row in project.get('observations', [])]


def current(project, today=None):
    """Latest effective observation per field; future forecasts stay separate.

    Equal-time disagreement is visible and does not pick a winner by arrival
    order. Unknown-time legacy values are only the fallback, never invented dates.
    """
    from zoneinfo import ZoneInfo
    explicit_day = today is not None
    clock = datetime.now(timezone.utc)
    today = today or clock.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    result = copy.deepcopy(project)
    observations = project.get('observations', [])
    grouped, conflicts, selected = {}, [], {}
    suppressed = _validate_chain(observations)
    forecasts, imprecise = [], []
    expired, scoped = [], {}
    for row in observations:
        if row['id'] in suppressed or (row.get('revision') or {}).get('action') == 'withdraw':
            continue
        if row['kind'] == 'forecast':
            forecasts.append(row)
            continue
        effective_precision = observation_time.precision(row['effective_at'])
        if effective_precision == 'unknown' or (row.get('schema_version') != 2 and effective_precision != 'day'):
            imprecise.append(row)
            continue
        if (not observation_time.certainly_past(row['effective_at'], today)
                or not explicit_day and effective_precision == 'timestamp' and observation_time.bounds(row['effective_at'])[1] > clock):
            forecasts.append(row)
            continue
        if row.get('valid_until') is not None and observation_time.definitely_after(today, row['valid_until']):
            expired.append(row)
        if row['scope'] != 'whole_site':
            scoped.setdefault(row['scope'], []).append(row)
            continue
        for field in row['fields']:
            group = 'it_capacity_bundle' if field in ('capacity_it_mw', 'capacity_it_mw_by_status', 'capacity_assessment') else field
            if row not in grouped.setdefault(group, []):
                grouped[group].append(row)
    for group, rows in grouped.items():
        fields = ('capacity_it_mw', 'capacity_it_mw_by_status', 'capacity_assessment') if group == 'it_capacity_bundle' else (group,)
        chosen = None
        remaining = list(rows)
        while remaining:
            latest_rows = [r for r in remaining if not any(observation_time.definitely_after(other['effective_at'], r['effective_at']) for other in remaining)]
            # Any overlapping candidate belongs to the same unresolved frontier.
            peers = list(latest_rows)
            while True:
                expanded = [r for r in remaining if r in peers or any(observation_time.overlaps(r['effective_at'], p['effective_at']) for p in peers)]
                if len(expanded) == len(peers):
                    break
                peers = expanded
            variants = {json.dumps({'fields': _comparison_fields(r['fields'], fields),
                                    'valid_until': r.get('valid_until'), 'kind': r['kind'],
                                    'estimate_basis': r['basis'] if r['kind'] in ('estimated', 'derived') else None,
                                    'assumptions': r.get('assumptions', [])}, sort_keys=True, ensure_ascii=False) for r in peers}
            if len(variants) != 1:
                conflicts.append({'field': group, 'effective_at': max(r['effective_at'] for r in peers), 'scope': 'whole_site',
                                  'observation_ids': sorted(r['id'] for r in peers)})
                remaining = [r for r in remaining if r not in peers]
                continue
            chosen = min(latest_rows, key=lambda r: r['id'])
            latest = chosen['effective_at']
            break
        if chosen is None:
            continue
        projected, quantities = site_quantity.project_fields({f: chosen['fields'].get(f) for f in fields})
        is_expired = chosen in expired
        if is_expired:
            projected = {field: {} if field == 'capacity_it_mw_by_status' else None for field in fields}
            quantities = {field: projected[field] for field in quantities}
        result.setdefault('quantity_fields', {}).update(quantities)
        for field in fields:
            result[field] = copy.deepcopy(projected[field])
            selected[field] = {'effective_at': latest, 'observation_id': chosen['id'],
                               'kind': chosen['kind'], 'recorded_at': chosen['recorded_at'],
                               'reviewed_at': max((r.get('reviewed_at', r['recorded_at']) for r in peers), key=lambda stamp: observation_time.bounds(stamp)[1]),
                               'valid_until': chosen.get('valid_until'), 'expired': is_expired,
                               'supporting_observation_ids': sorted(r['id'] for r in peers)}
        if not is_expired and group == 'it_capacity_bundle' and chosen['kind'] in ('estimated', 'derived'):
            result['capacity_assessment'] = {
                'kind':'estimate', 'status':'reviewed', 'as_of':chosen['effective_at'],
                'recorded_at':chosen['recorded_at'][:10], 'basis_note':chosen['basis'],
                'assumptions':chosen['assumptions'], 'missing_conditions':[]}
    limit = FRESH_DAYS['project_late' if result.get('status') in ('L6','L7','L8','L9') else 'project_early']
    due = []
    for field in FIELDS:
        native = result.get('quantity_fields', {}).get(field)
        if result.get(field) in (None, '', [], {}) and native in (None, '', [], {}):
            continue
        reviewed = selected[field]['reviewed_at'][:10] if field in selected else project.get('verified_date')
        age = _age(reviewed, today)
        if age is None or age > limit:
            due.append(field)
    result['tracking'] = {'fields': selected, 'conflicts': conflicts,
                          'review_due_fields': sorted(due),
                          'observations': len(observations), 'forecasts': len(forecasts),
                          'imprecise_times': len(imprecise), 'expired_observations': len(expired),
                          'superseded_observation_ids': sorted(suppressed),
                          'latest_effective_at': max((r['effective_at'] for r in selected.values()), key=lambda stamp: observation_time.bounds(stamp)[1], default=None),
                          'baseline_reviewed_at': project.get('verified_date'),
                          'baseline_review_age_days': _age(project.get('verified_date'), today)}
    result['scope_views'] = {}
    for scope, rows in scoped.items():
        # A scoped quantity never supplies missing whole-site values or joins totals.
        local = dict(observations=[{k: v for k, v in dict(row, scope='whole_site').items() if k != 'revision'} for row in rows])
        view = current(local, today)
        result['scope_views'][scope] = {k: v for k, v in view.items() if k in FIELDS or k in ('quantity_fields', 'tracking')}
    return result


def _comparison_fields(values, fields):
    result = {f: values.get(f) for f in fields}
    for field in ('capacity_it_mw', 'capacity_facility_mw'):
        if field in result:
            result[field] = site_quantity.canonical(result[field])
    if 'capacity_it_mw_by_status' in result:
        result['capacity_it_mw_by_status'] = {k: site_quantity.canonical(v) for k, v in (result['capacity_it_mw_by_status'] or {}).items()}
    return result


def _age(value, today):
    try:
        return max(0, (date.fromisoformat(today) - date.fromisoformat(value)).days)
    except (ValueError, TypeError):
        return None


def public_timeline(project):
    """Public source URLs and semantic history; never private archive paths."""
    return [{'id': r['id'], 'effective_at': r['effective_at'], 'recorded_at': r['recorded_at'],
             'reviewed_at': r.get('reviewed_at', r['recorded_at']), 'scope': r['scope'], 'valid_until': r.get('valid_until'),
             'revision': ({'action': r['revision']['action'], 'observation_ids': r['revision']['observation_ids']} if r.get('revision') else None),
             'source_versions': [{k: s.get(k) for k in ('source_sha256', 'published_at', 'first_received_at', 'published_at_precision', 'first_received_at_precision')}
                                 for s in r.get('source_versions', [])],
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
