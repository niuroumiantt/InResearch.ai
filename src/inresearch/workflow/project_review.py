"""Explicit event review → curated project write. Receiver/Reader never adopt.

The queue is a projection of existing events and formal receipts, not a second
facts database. Missing evidence stays queued; a named review is required.
"""
import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from inresearch.paths import project_root
from inresearch.storage.files import locked, write_json
from inresearch.workflow.daily_dispatch import read_events, receipt_documents, bound_urls
from inresearch.knowledge.industry import LEVELS, public_url, number
from inresearch.knowledge import site_timeline, site_quantity, observation_time


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def event_identity(event):
    # Reader/dispatch annotations do not change the source version.
    return digest({k: event.get(k) for k in ('id', 'body', 'document_refs', 'editorial_event', 'sources')})


def deliveries(root):
    rows = json.loads((Path(root)/'data/projects.json').read_text())['records']
    return [{'site_id': p['site_id'], 'name': p['name'],
             'verified_date': a['review']['at'][:10], 'event_id': a['event_id'],
             'review_id': a['review_id'], 'fields': a['fields'], 'scope': a['scope']}
            for p in rows for a in site_timeline.adoptions(p) if a.get('event_id')]


def queue(data, root):
    adopted = {r['event_id']: r for r in deliveries(root)}
    accepted = receipt_documents(data)
    targets = {r['id'] for r in json.loads((Path(root)/'framework/tco_targets.json').read_text())['targets']}
    known_sites = {r['site_id'] for r in json.loads((Path(root)/'data/projects.json').read_text())['records']
                   if not r.get('duplicate_of') and 'portfolio' not in r['site_id']
                   and r.get('identity_scope') not in ('cluster', 'portfolio')}
    rows = []
    for event in read_events(data):
        authored = event.get('editorial_event') or {}
        project = authored.get('project') or {}
        goals = [r.get('target_id') for r in event.get('demand_matches', []) if r.get('target_id') in targets]
        known_identity = event.get('identity_review') == 'resolved' and event.get('matched_site_id') in known_sites
        state = 'needs_binding' if any(public_url(u) for s in event.get('sources', []) for u in s.get('urls', [])) else 'needs_source'
        if bound_urls(event, accepted):
            state = 'needs_identity'
            if known_identity or all(project.get(k) for k in ('name', 'country', 'city', 'phase')):
                state = 'needs_evidence'
                if event.get('structured_evidence_status') == 'quotes_verified' and (goals or known_identity):
                    state = 'ready_for_review'
        if event['id'] in adopted:
            if adopted[event['id']]['review_id'].startswith(event_identity(event)[:16]):
                state = 'adopted'
            elif state != 'ready_for_review':
                state = 'changed_source'
        rows.append({'event_id': event['id'], 'title': event['title'], 'state': state,
                     'source_version': event_identity(event), 'target_ids': sorted(set(goals)),
                     'executor': 'Codex research review',
                     'previous_review_id': adopted.get(event['id'], {}).get('review_id'),
                     'site_id': adopted.get(event['id'], {}).get('site_id') or
                                (event.get('matched_site_id') if known_identity else None)})
    rows.sort(key=lambda r: (r['state'] != 'ready_for_review', r['state'], r['event_id']))
    return {'records': rows, 'counts': dict(Counter(r['state'] for r in rows)),
            'scope': '逐事件核验；就绪不等于已审核，正式结果以项目登记及发布验收为准。'}


def prepare(data, root):
    value = queue(data, root)
    directory = Path(data)/'material-reviews/project-review'
    events = {e['id']: e for e in read_events(data)}
    for row in value['records']:
        if row['state'] != 'ready_for_review':
            continue
        path = directory/(row['source_version']+'.json')
        if not path.exists():
            write_json(path, {'schema_version': 1, 'event': events[row['event_id']],
                              'source_version': row['source_version'], 'target_ids': row['target_ids'],
                              'required': ['named C3 review', 'source bytes and quotes', 'identity and scope',
                                           'conflicts and overlap', 'formal write', 'web verification']})
    write_json(directory/'queue.json', value)
    return {'counts': value['counts'], 'directory': str(directory)}


def checked_source(data, sha):
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('invalid_source_sha256')
    paths = list((Path(data)/'acquisition/blobs'/sha[:2]).glob(sha+'.*'))
    if len(paths) != 1 or paths[0].is_symlink() or hashlib.sha256(paths[0].read_bytes()).hexdigest() != sha:
        raise ValueError('source_archive_missing_or_changed')
    return paths[0].read_text(encoding='utf-8')


def quantity_supported(assertion, pairs):
    """Exact, explicitly rounded, or reproducibly derived MW; never fuzzy units."""
    units = {'MW': 1, 'GW': 1000}
    if 'value_range' in assertion:
        if 'value' in assertion or not assertion.get('range_basis'):
            return False
        try:
            quantity = {k: assertion[k] for k in ('value_range', 'unit')}
            quantity['basis'] = assertion['range_basis']
            wanted_range = site_quantity.bounds_mw(quantity)
        except (KeyError, TypeError, ValueError):
            return False
        method = assertion.get('derivation')
        if method is None:
            return wanted_range in site_quantity.literal_ranges_mw(assertion.get('quote', ''))
        if not isinstance(method, dict) or method.get('operation') != 'scale_range' or not method.get('basis'):
            return False
        inputs, factors = method.get('inputs'), method.get('factor_range')
        if (not isinstance(inputs, list) or len(inputs) != 1 or not number(inputs[0]) or inputs[0] not in pairs
                or not isinstance(factors, list) or len(factors) != 2 or not all(number(n) and n > 0 for n in factors)
                or factors[0] > factors[1]):
            return False
        expected = tuple(inputs[0] * n for n in factors)
        return all(number(n) for n in expected) and all(abs(a-b) <= 1e-9*max(1,abs(a),abs(b)) for a,b in zip(wanted_range,expected))
    value, unit = assertion.get('value'), assertion.get('unit')
    if not number(value) or unit not in units:
        return False
    wanted = value * units[unit]
    method = assertion.get('derivation')
    if method is not None:
        if not isinstance(method, dict) or not isinstance(method.get('basis'), str) or not method['basis'].strip():
            return False
        inputs = method.get('inputs')
        if not isinstance(inputs, list) or not inputs or any(not number(n) or n not in pairs for n in inputs):
            return False
        if any(inputs.count(n) > pairs.count(n) for n in set(inputs)):
            return False
        op = method.get('operation')
        if op == 'sum':
            expected = sum(inputs)
        elif op == 'difference' and len(inputs) == 2:
            expected = inputs[0] - inputs[1]
        elif op == 'scale' and len(inputs) == 1 and number(method.get('factor')) and method['factor'] > 0:
            expected = inputs[0] * method['factor']
        else:
            return False
        if not number(expected):
            return False
        pairs = [expected]
    if 'decimal_places' in assertion:
        precision = assertion['decimal_places']
        if type(precision) is not int or not 0 <= precision <= 6 or not assertion.get('approximation_basis'):
            return False
        if round(value, precision) != value:
            return False
        tolerance = .5 * 10 ** (-precision) * units[unit]
        return any(abs(wanted-n) <= tolerance + 1e-9 for n in pairs)
    return any(abs(wanted-n) <= 1e-9 * max(1,abs(n)) for n in pairs)


def _catalog_first_received(data, shas):
    result = {}
    path = Path(data)/'acquisition/catalog.sqlite'
    if not path.is_file() or path.is_symlink() or not shas:
        return result
    connection = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    try:
        marks = ','.join('?' for _ in shas)
        rows = connection.execute('SELECT sha256, observed_at FROM observations WHERE sha256 IN ('+marks+')', sorted(shas))
        for sha, stamp in rows:
            if observation_time.precision(stamp) != 'timestamp':
                continue
            if sha not in result or observation_time.bounds(stamp)[0] < observation_time.bounds(result[sha]['at'])[0]:
                result[sha] = {'at': stamp, 'provenance': 'local_archive_first_observed_at'}
    finally:
        connection.close()
    return result


def _daily_first_received(data, shas):
    result = _catalog_first_received(data, shas)
    for path in (Path(data)/'material-reviews/daily-deliveries').glob('*.json'):
        if path.is_symlink() or path.stat().st_size > 1024*1024:
            continue
        try:
            receipt = json.loads(path.read_text())
            if (receipt.get('producer') != 'inews_geluoke' or receipt.get('status') != 'indexed_candidate'
                    or observation_time.precision(receipt.get('first_received_at')) != 'timestamp'):
                continue
            stamp = receipt['first_received_at']
            # Only completed receipts with exact member identity can establish this source's arrival.
            members = {r.get('sha256') for r in receipt.get('members', [])+receipt.get('documents', []) if isinstance(r, dict)}
            for sha in shas & members:
                if sha not in result or observation_time.bounds(stamp)[0] < observation_time.bounds(result[sha]['at'])[0]:
                    result[sha] = {'at': stamp, 'provenance': 'indexed_bundle_first_verified_arrival'}
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return result


def _daily_context(data, proposal):
    events = {e['id']: e for e in read_events(data)}
    event = events[proposal['event_id']]
    accepted = receipt_documents(data)
    shas = {c['source_sha256'] for c in (event.get('editorial_event') or {}).get('evidence_checks', [])}
    texts = {}
    for assertion in proposal.get('assertions') or []:
        sha = assertion.get('source_sha256')
        if sha not in shas:
            raise ValueError('assertion_source_not_in_received_evidence')
        texts[sha] = checked_source(data, sha)
    return {'source_id': event['id'], 'source_version': event_identity(event),
            'document_refs': event['document_refs'], 'urls': bound_urls(event, accepted),
            'source_texts': texts, 'first_received': _daily_first_received(data, set(texts)),
            'publication_metadata': {},
            'matched_site_id': event.get('matched_site_id') if event.get('identity_review') == 'resolved' else None}


def _source_versions(observation, context):
    supplied = observation.get('source_versions', [])
    if not isinstance(supplied, list):
        raise ValueError('invalid_observation_source_versions')
    requested = {}
    for row in supplied:
        if not isinstance(row, dict) or set(row) - {'source_sha256', 'published_at', 'publication_evidence'}:
            raise ValueError('source_times_must_be_derived_from_evidence')
        sha = row.get('source_sha256')
        if sha not in context['source_texts'] or sha in requested:
            raise ValueError('source_time_not_bound_to_assertion')
        requested[sha] = row
    result = []
    for sha, text in sorted(context['source_texts'].items()):
        item = requested.get(sha, {})
        metadata = context.get('publication_metadata', {}).get(sha, {})
        if metadata.get('published_at') is not None and 'published_at' in item and item['published_at'] != metadata['published_at']:
            raise ValueError('publication_time_disagrees_with_bound_metadata')
        published = item.get('published_at', metadata.get('published_at'))
        if published is None and item.get('publication_evidence'):
            raise ValueError('publication_evidence_without_known_time')
        publication_origin = 'unknown_not_established_by_native_source'
        if published is not None:
            observation_time.precision(published)
            if metadata.get('published_at') == published and metadata.get('provenance') and not item.get('publication_evidence'):
                publication_origin = metadata['provenance']
            else:
                proof = item.get('publication_evidence') or {}
                if not isinstance(proof, dict):
                    raise ValueError('publication_time_not_supported_by_source_version')
                quote = proof.get('quote')
                if (proof.get('kind') != 'original_quote' or not proof.get('locator') or not proof.get('basis')
                        or not isinstance(quote, str) or not observation_time.native_date_matches(published, quote)
                        or ''.join(quote.split()) not in ''.join(text.split())):
                    raise ValueError('publication_time_not_supported_by_source_version')
                if context.get('source_kind') in ('reader_report', 'targeted_excerpt', 'object_excerpt'):
                    import re
                    prefix = 'reader' if context['source_kind'] == 'reader_report' else 'excerpt'
                    location = re.fullmatch(prefix+r':page:([1-9]\d*)', proof['locator'])
                    pages = context.get('source_pages', {}).get(sha, {})
                    page = pages.get(int(location[1]), pages.get(location[1])) if location else None
                    if not isinstance(page, str) or ''.join(quote.split()) not in ''.join(page.split()):
                        raise ValueError('publication_quote_not_at_sealed_reader_page')
                publication_origin = 'reviewed_native_publication_quote'
        received = context.get('first_received', {}).get(sha, {})
        received_at = received.get('at')
        if received_at is not None and observation_time.precision(received_at) != 'timestamp':
            raise ValueError('first_received_timestamp_required')
        if published is not None and received_at is not None and observation_time.definitely_after(published, received_at):
            raise ValueError('publication_after_first_receipt')
        row = {'source_sha256': sha, 'published_at': published,
                       'published_at_precision': observation_time.precision(published),
                       'published_at_provenance': publication_origin,
                       'first_received_at': received_at,
                       'first_received_at_precision': observation_time.precision(received_at),
                       'first_received_at_provenance': received.get('provenance') or 'unknown_no_first_receipt_for_this_sha'}
        if item.get('publication_evidence'):
            row['publication_evidence'] = item['publication_evidence']
            row['publication_date_parser'] = 'native-date-v1'
        result.append(row)
    return result


def apply(root, data, proposal):
    root, data = Path(root), Path(data)
    source_kind = proposal.get('source_kind', 'daily_event')
    if source_kind == 'daily_event':
        context = _daily_context(data, proposal)
    elif source_kind in ('targeted_excerpt', 'object_excerpt'):
        if not proposal.get('observation'):
            raise ValueError('targeted_excerpt_requires_site_observation')
        from inresearch.workflow import targeted_research
        context = targeted_research.resolve(root, data, proposal)
    elif source_kind == 'reader_report':
        if not isinstance(proposal.get('observation'), dict):
            raise ValueError('reader_report_requires_site_observation')
        from inresearch.workflow.project_review_reader import resolve
        context = resolve(root, data, proposal)
    else:
        raise ValueError('unsupported_project_review_source_kind')
    context['source_kind'] = source_kind
    source_id, source_version = context['source_id'], context['source_version']
    if proposal.get('source_version') != source_version:
        raise ValueError('event_changed_since_review')
    review = proposal.get('review') or {}
    if not isinstance(review, dict):
        raise ValueError('named_semantic_review_required')
    score = review.get('score')
    if (review.get('decision') != 'adopted' or not review.get('by') or not review.get('at')
            or type(score) is not int or not 5 <= score <= 10 or not review.get('rationale')):
        raise ValueError('named_semantic_review_required')
    date.fromisoformat(review['at'][:10])
    if review.get('tier') != ('A' if score >= 8 else 'B'):
        raise ValueError('c3_tier_mismatch')
    if review['tier'] == 'A' and review.get('authority') != 'owner' and not (
            review.get('authority') == 'delegated_reviewer' and review.get('delegation')):
        raise ValueError('c3_a_delegation_required')
    review_id = source_version[:16]+'-'+digest(proposal)[:16]
    if review['tier'] == 'B' and int(source_version[:8], 16) % 10 == 0:
        sample = review.get('sample_review') or {}
        if not sample.get('by') or sample.get('decision') != 'confirmed':
            raise ValueError('deterministic_sample_review_required')
    p = proposal['project']
    initial = proposal.get('initial_identity')
    if initial is not None:
        from inresearch.knowledge.site_register import check_initial_identity
        check_initial_identity(initial, p)
        if proposal.get('target_ids') != [] or not isinstance(proposal.get('observation'), dict):
            raise ValueError('initial_identity_requires_targetless_observation')
    if context.get('matched_site_id') and context['matched_site_id'] != p.get('site_id'):
        raise ValueError('reviewed_event_site_mismatch')
    if p.get('disputed') or p.get('sensitive') or proposal.get('replaces_record_ids'):
        raise ValueError('owner_decision_required_for_conflict_or_replacement')
    for key in ('site_id', 'name', 'country', 'location', 'region', 'notes'):
        if not isinstance(p.get(key), str) or not p[key].strip():
            raise ValueError('project_identity_required:'+key)
    if p.get('status') not in LEVELS or p.get('verified_date') != review['at'][:10]:
        raise ValueError('invalid_project_stage_or_review_date')
    urls = set(context['urls'])
    if not urls or not p.get('sources') or any(s.get('url') not in urls for s in p['sources']):
        raise ValueError('source_not_bound_to_received_event')
    object_only = proposal.get('target_ids') == [] and isinstance(proposal.get('observation'), dict)
    if object_only:
        site_timeline.check_object_binding(proposal.get('object_binding'), site_id=p['site_id'],
            fields=proposal.get('fields'), scope=proposal['observation'].get('scope'))
    elif not proposal.get('target_ids') or not set(proposal['target_ids']) <= {
            r['id'] for r in json.loads((root/'framework/tco_targets.json').read_text())['targets']}:
        raise ValueError('current_demand_required')
    if context.get('bound_target_ids') is not None and not set(proposal['target_ids']) <= set(context['bound_target_ids']):
        raise ValueError('reader_current_demand_binding_required')
    assertions = proposal.get('assertions') or []
    if not assertions:
        raise ValueError('source_assertions_required')
    archived = set(context['source_texts'])
    checked = []
    for assertion in assertions:
        sha, quote = assertion.get('source_sha256'), assertion.get('quote')
        if sha not in archived or not assertion.get('locator') or not isinstance(quote, str) or not quote.strip():
            raise ValueError('assertion_source_not_in_received_evidence')
        source = context['source_texts'][sha]
        if ''.join(quote.split()) not in ''.join(source.split()):
            raise ValueError('quote_not_in_archived_original')
        if assertion.get('metric') is not None:
            from inresearch.knowledge import site_metrics
            key = assertion['metric']
            if key not in site_metrics.FIELDS or not site_metrics.supported(key, assertion.get('quantity'), quote):
                raise ValueError('resource_metric_not_in_original_quote')
            if assertion.get('quantity') is None:
                raise ValueError('resource_metric_assertion_quantity_required')
        if assertion.get('value') is not None or 'value_range' in assertion:
            from inresearch.materials.daily_research import power_quantities
            units = {'MW': 1, 'GW': 1000}
            pairs = [n * units[u] for n, u in power_quantities(quote)]
            if not quantity_supported(assertion, pairs):
                raise ValueError('quantity_not_in_original_quote')
        checked.append(assertion)
    if initial is not None and not any(''.join(initial['native_name'].split()) in ''.join(a['quote'].split()) for a in checked):
        raise ValueError('initial_native_identity_not_in_reviewed_quote')
    if any(a.get('derivation') for a in checked):
        meta = proposal.get('observation') or {}
        if meta.get('kind') not in ('derived', 'estimated', 'forecast') or not meta.get('assumptions'):
            raise ValueError('derived_capacity_requires_estimated_observation')
    observation = proposal.get('observation')
    if observation is not None and not isinstance(observation, dict):
        raise ValueError('invalid_observation_metadata')
    withdrawal = observation is not None and (observation.get('revision') or {}).get('action') == 'withdraw'
    changed_fields = set(proposal.get('fields') or []) if observation is not None else set(p)
    from inresearch.knowledge import site_metrics
    for key in site_metrics.FIELDS & changed_fields:
        site_metrics.check(key, p.get(key))
        if not withdrawal and p.get(key) is not None and not any(
                a.get('metric') == key and site_metrics.canonical(key, a.get('quantity')) == site_metrics.canonical(key, p[key])
                for a in checked):
            raise ValueError('resource_metric_not_supported:' + key)
    parts = (p.get('capacity_it_mw_by_status') or {}) if 'capacity_it_mw_by_status' in changed_fields else {}
    if len(parts) > 1 and observation is None:
        raise ValueError('multiple_phase_aggregation_requires_separate_relation_review')
    if p.get('capacity_it_mw') is not None and parts:
        raise ValueError('capacity_headline_and_breakdown_overlap')
    def backed(value, basis, scope=None, phase=None):
        for assertion in checked:
            if (assertion.get('basis') != basis or scope is not None and assertion.get('scope') != scope
                    or phase is not None and assertion.get('phase') != phase):
                continue
            try:
                native = {k: assertion[k] for k in ('value', 'value_range', 'unit') if k in assertion}
                native['basis'] = assertion.get('range_basis', 'reviewed literal quantity')
                if site_quantity.canonical(value) == site_quantity.canonical(native):
                    return True
            except (ValueError, TypeError):
                continue
        return False
    if not withdrawal and 'capacity_it_mw' in changed_fields and p.get('capacity_it_mw') is not None and not backed(p['capacity_it_mw'], 'it'):
        raise ValueError('it_capacity_not_supported')
    if not withdrawal and 'capacity_planned_it_mw' in changed_fields and p.get('capacity_planned_it_mw') is not None and not backed(p['capacity_planned_it_mw'], 'it', 'planned_whole_site'):
        raise ValueError('planned_it_capacity_not_supported')
    for level, value in ({} if withdrawal else parts).items():
        supported = backed(value, 'it', 'aggregate') if len(parts) == 1 else backed(value, 'it', 'nonoverlapping_phase', level)
        if level not in LEVELS or not supported:
            raise ValueError('capacity_aggregation_not_reviewed')
    if not withdrawal and 'capacity_facility_mw' in changed_fields and p.get('capacity_facility_mw') is not None and not backed(p['capacity_facility_mw'], 'facility'):
        raise ValueError('facility_capacity_not_supported')
    for k in ('capacity_it_mw', 'capacity_facility_mw', 'capacity_planned_it_mw'):
        if p.get(k) is not None:
            if observation is not None:
                site_quantity.check(p[k])
            elif not number(p[k]):
                raise ValueError('invalid_capacity_value')
    companies = {r['company_id'] for r in json.loads((root/'data/companies.json').read_text())['records']} if (root/'data/companies.json').exists() else set()
    from inresearch.knowledge import site_register
    if companies and not {v for k in site_register.ACTOR_ROLES for v in p.get(k, [])} <= companies:
        raise ValueError('unknown_project_actor')
    # Phase observations remain separate from the aggregate; parent/child MW never summed.
    p = dict(p, adoption={'source_kind': source_kind, 'source_id': source_id, 'review_id': review_id,
                         'source_version': source_version, 'review': review,
                         'target_ids': proposal['target_ids'], 'assertions': checked,
                         'document_refs': context['document_refs'], 'fields': proposal['fields'],
                         'scope': proposal['scope']})
    if source_kind == 'daily_event':
        p['adoption']['event_id'] = source_id
    if object_only:
        p['adoption']['object_binding'] = proposal['object_binding']
    path = root/'data/projects.json'
    replay = False
    with locked(path):
        value = json.loads(path.read_text())
        old = next((r for r in value['records'] if r['site_id'] == p['site_id']), None)
        if observation is not None:
            registering = old is None and initial is not None
            if registering:
                # Only the reviewed first observation may introduce mutable facts.
                if any(k in p for k in ('observations', 'adoption_history', 'identity_registration')):
                    raise ValueError('initial_site_cannot_inject_history')
                if any(p.get(k) not in (None, {}) for k in ('capacity_it_mw', 'capacity_planned_it_mw', 'capacity_facility_mw', 'capacity_it_mw_by_status', 'capacity_assessment')):
                    raise ValueError('initial_site_requires_empty_capacity_baseline')
                if any(p.get(k) for k in site_register.ACTOR_ROLES if k not in changed_fields):
                    raise ValueError('initial_site_actor_requires_reviewed_field')
                if not {'name', 'status'} <= changed_fields:
                    raise ValueError('initial_site_requires_reviewed_name_and_status')
                for existing in value['records']:
                    names = {str(x).casefold() for x in [existing.get('name'), *(existing.get('aliases') or [])]}
                    if p['name'].casefold() in names or (p['country'] == existing.get('country') and
                            set(p.get('aliases') or []) & set(existing.get('aliases') or [])):
                        raise ValueError('possible_duplicate_project_identity')
                old = {k:v for k,v in p.items() if k != 'adoption'}
                old['identity_registration'] = initial
            if not old:
                raise ValueError('observation_requires_registered_physical_site')
            if old.get('duplicate_of') or 'portfolio' in old['site_id']:
                raise ValueError('observation_requires_canonical_physical_site')
            if object_only and old.get('identity_scope') in ('cluster', 'portfolio'):
                raise ValueError('object_excerpt_requires_unique_physical_site')
            if not isinstance(observation, dict) or set(observation) - {'effective_at', 'valid_until', 'kind', 'basis', 'assumptions', 'scope', 'source_versions', 'revision'}:
                raise ValueError('invalid_observation_metadata')
            if not changed_fields or changed_fields - site_timeline.FIELDS:
                raise ValueError('observation_cannot_relocate_or_merge_site')
            for key in ('country', 'location', 'region', 'coordinates', 'duplicate_of'):
                if key in p and p.get(key) != old.get(key):
                    raise ValueError('physical_site_identity_changed:' + key)
            if not changed_fields <= p.keys():
                raise ValueError('observation_field_missing')
            prior = next((r for r in old.get('observations', []) if r['id'] == review_id), None)
            versions = _source_versions(observation, context)
            metadata = {k: v for k, v in observation.items() if k != 'source_versions'}
            entry = dict(metadata, schema_version=2, id=review_id,
                         recorded_at=prior['recorded_at'] if prior else now(), reviewed_at=review['at'], source_versions=versions,
                         fields={k:p[k] for k in changed_fields}, adoption=p['adoption'], sources=p['sources'])
            if prior and prior.get('schema_version') != 2:
                # A protocol upgrade cannot turn an exact historic replay into a new write.
                legacy = dict(metadata, id=review_id, recorded_at=review['at'], fields=entry['fields'],
                              adoption={k: v for k, v in p['adoption'].items() if k not in ('source_kind', 'source_id')}, sources=p['sources'])
                if prior != legacy:
                    raise ValueError('site_observation_id_conflict')
                entry = prior
            elif prior:
                if [(v['source_sha256'], v['published_at']) for v in versions] != [(v['source_sha256'], v['published_at']) for v in prior['source_versions']]:
                    raise ValueError('site_observation_id_conflict')
                entry['source_versions'] = prior['source_versions']
            # Replay precedes the optimistic baseline guard, as with other writes.
            updated, replay = site_timeline.append(old, entry)
            if not replay and not registering and proposal.get('baseline_sha256') != digest(old):
                raise ValueError('existing_project_requires_explicit_change_review')
            if not replay:
                if registering:
                    value['records'].append(updated)
                else:
                    value['records'][value['records'].index(old)] = updated
        elif old:
            if old == p or (old.get('adoption') or {}).get('review_id') == review_id:
                replay = True
            else:
                # Supplement missing fields and append history; preserve all existing values.
                if proposal.get('baseline_sha256') != digest(old):
                    raise ValueError('existing_project_requires_explicit_change_review')
                before = {k:v for k,v in old.items() if k not in ('adoption','adoption_history','verified_date')}
                for k, previous in before.items():
                    candidate = p.get(k)
                    if k in ('sources','status_history'):
                        if any(v not in (candidate or []) for v in previous):
                            raise ValueError('existing_history_must_be_preserved')
                    elif previous not in (None, '', [], {}) and candidate != previous:
                        raise ValueError('owner_decision_required_for_existing_conclusion')
                p['adoption_history'] = [*old.get('adoption_history', []), *([old['adoption']] if old.get('adoption') else [])]
                value['records'][value['records'].index(old)] = p
        else:
            for existing in value['records']:
                names = {str(x).casefold() for x in [existing.get('name'), *(existing.get('aliases') or [])]}
                if p['name'].casefold() in names or (p['country']==existing.get('country') and
                        set(p.get('aliases') or []) & set(existing.get('aliases') or [])):
                    raise ValueError('possible_duplicate_project_identity')
            value['records'].append(p)
        if not replay: write_json(path, value)
    # Main commit is recoverable from the project itself if receipt writing fails.
    receipt = {'state': 'already_applied' if replay else 'applied_in_checkout', 'site_id': p['site_id'], 'review_id': review_id,
               'source_kind': source_kind, 'source_id': source_id, 'source_version': source_version,
               'scope': 'Not a deployment receipt; merge, publish and verify the web separately.'}
    if source_kind == 'daily_event':
        receipt['event_id'] = source_id
    write_json(data/'material-reviews/project-review/receipts'/(review_id+'.json'), receipt)
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('prepare', 'apply'))
    ap.add_argument('--data-root', type=Path, required=True)
    ap.add_argument('--root', type=Path, default=project_root())
    ap.add_argument('--input', type=Path)
    args = ap.parse_args()
    result = prepare(args.data_root, args.root) if args.action == 'prepare' else apply(
        args.root, args.data_root, json.loads(args.input.read_text()))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
