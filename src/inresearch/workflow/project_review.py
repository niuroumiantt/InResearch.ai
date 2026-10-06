"""Explicit event review → curated project write. Receiver/Reader never adopt.

The queue is a projection of existing events and formal receipts, not a second
facts database. Missing evidence stays queued; a named review is required.
"""
import argparse
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from inresearch.paths import project_root
from inresearch.storage.files import locked, write_json
from inresearch.workflow.daily_dispatch import read_events, receipt_documents, bound_urls
from inresearch.knowledge.industry import LEVELS, public_url, number


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def event_identity(event):
    # Reader/dispatch annotations do not change the source version.
    return digest({k: event.get(k) for k in ('id', 'body', 'document_refs', 'editorial_event', 'sources')})


def deliveries(root):
    rows = json.loads((Path(root)/'data/projects.json').read_text())['records']
    return [{'site_id': p['site_id'], 'name': p['name'], 'verified_date': p['verified_date'],
             'event_id': p['adoption']['event_id'], 'review_id': p['adoption']['review_id'],
             'fields': p['adoption']['fields'], 'scope': p['adoption']['scope']}
            for p in rows if p.get('adoption')]


def queue(data, root):
    adopted = {r['event_id']: r for r in deliveries(root)}
    accepted = receipt_documents(data)
    targets = {r['id'] for r in json.loads((Path(root)/'framework/tco_targets.json').read_text())['targets']}
    rows = []
    for event in read_events(data):
        authored = event.get('editorial_event') or {}
        project = authored.get('project') or {}
        goals = [r.get('target_id') for r in event.get('demand_matches', []) if r.get('target_id') in targets]
        state = 'needs_binding' if any(public_url(u) for s in event.get('sources', []) for u in s.get('urls', [])) else 'needs_source'
        if bound_urls(event, accepted):
            state = 'needs_identity'
            if all(project.get(k) for k in ('name', 'country', 'city', 'phase')):
                state = 'needs_evidence'
                if event.get('structured_evidence_status') == 'quotes_verified' and goals:
                    state = 'ready_for_review'
        if event['id'] in adopted:
            state = 'adopted' if adopted[event['id']]['review_id'].startswith(event_identity(event)[:16]) else 'changed_source'
        rows.append({'event_id': event['id'], 'title': event['title'], 'state': state,
                     'source_version': event_identity(event), 'target_ids': sorted(set(goals)),
                     'executor': 'Codex research review',
                     'site_id': adopted.get(event['id'], {}).get('site_id')})
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


def apply(root, data, proposal):
    root, data = Path(root), Path(data)
    events = {e['id']: e for e in read_events(data)}
    event = events[proposal['event_id']]
    if proposal.get('source_version') != event_identity(event):
        raise ValueError('event_changed_since_review')
    review = proposal.get('review') or {}
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
    review_id = event_identity(event)[:16]+'-'+digest(proposal)[:16]
    if review['tier'] == 'B' and int(event_identity(event)[:8], 16) % 10 == 0:
        sample = review.get('sample_review') or {}
        if not sample.get('by') or sample.get('decision') != 'confirmed':
            raise ValueError('deterministic_sample_review_required')
    p = proposal['project']
    if p.get('disputed') or p.get('sensitive') or proposal.get('replaces_record_ids'):
        raise ValueError('owner_decision_required_for_conflict_or_replacement')
    for key in ('site_id', 'name', 'country', 'location', 'region', 'notes'):
        if not isinstance(p.get(key), str) or not p[key].strip():
            raise ValueError('project_identity_required:'+key)
    if p.get('status') not in LEVELS or p.get('verified_date') != review['at'][:10]:
        raise ValueError('invalid_project_stage_or_review_date')
    accepted = receipt_documents(data)
    urls = set(bound_urls(event, accepted))
    if not urls or not p.get('sources') or any(s.get('url') not in urls for s in p['sources']):
        raise ValueError('source_not_bound_to_received_event')
    if not proposal.get('target_ids') or not set(proposal['target_ids']) <= {
            r['id'] for r in json.loads((root/'framework/tco_targets.json').read_text())['targets']}:
        raise ValueError('current_demand_required')
    assertions = proposal.get('assertions') or []
    if not assertions:
        raise ValueError('source_assertions_required')
    archived = {c['source_sha256'] for c in (event.get('editorial_event') or {}).get('evidence_checks', [])}
    checked = []
    for assertion in assertions:
        sha, quote = assertion.get('source_sha256'), assertion.get('quote')
        if sha not in archived or not assertion.get('locator') or not isinstance(quote, str) or not quote.strip():
            raise ValueError('assertion_source_not_in_received_evidence')
        source = checked_source(data, sha)
        if ''.join(quote.split()) not in ''.join(source.split()):
            raise ValueError('quote_not_in_archived_original')
        if assertion.get('value') is not None:
            import re
            units = {'MW': 1, 'GW': 1000}
            pairs = [(float(n.replace(',', '')) * units[u.upper()]) for n,u in
                     re.findall(r'(\d[\d,]*(?:\.\d+)?)\s*(MW|GW)\b', quote, re.I)]
            if not number(assertion['value']) or assertion.get('unit') not in units or assertion['value']*units[assertion['unit']] not in pairs:
                raise ValueError('quantity_not_in_original_quote')
        checked.append(assertion)
    parts = p.get('capacity_it_mw_by_status') or {}
    if len(parts) > 1:
        raise ValueError('multiple_phase_aggregation_requires_separate_relation_review')
    if p.get('capacity_it_mw') is not None and parts:
        raise ValueError('capacity_headline_and_breakdown_overlap')
    def backed(value, basis, scope=None):
        return any(a.get('value') == value and a.get('basis') == basis and a.get('unit') == 'MW'
                   and (scope is None or a.get('scope') == scope) for a in checked)
    if p.get('capacity_it_mw') is not None and not backed(p['capacity_it_mw'], 'it'):
        raise ValueError('it_capacity_not_supported')
    for level, value in parts.items():
        if level not in LEVELS or not backed(value, 'it', 'aggregate'):
            raise ValueError('capacity_aggregation_not_reviewed')
    if p.get('capacity_facility_mw') is not None and not backed(p['capacity_facility_mw'], 'facility'):
        raise ValueError('facility_capacity_not_supported')
    for k in ('capacity_it_mw', 'capacity_facility_mw'):
        if p.get(k) is not None and not number(p[k]): raise ValueError('invalid_capacity_value')
    companies = {r['company_id'] for r in json.loads((root/'data/companies.json').read_text())['records']} if (root/'data/companies.json').exists() else set()
    if companies and not set(p.get('developer', [])+p.get('tenant', [])) <= companies:
        raise ValueError('unknown_project_actor')
    # Phase observations remain separate from the aggregate; parent/child MW never summed.
    p = dict(p, adoption={'event_id': event['id'], 'review_id': review_id,
                         'source_version': event_identity(event), 'review': review,
                         'target_ids': proposal['target_ids'], 'assertions': checked,
                         'document_refs': event['document_refs'], 'fields': proposal['fields'],
                         'scope': proposal['scope']})
    path = root/'data/projects.json'
    replay = False
    with locked(path):
        value = json.loads(path.read_text())
        old = next((r for r in value['records'] if r['site_id'] == p['site_id']), None)
        if old:
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
               'event_id': event['id'], 'source_version': event_identity(event),
               'scope': 'Not a deployment receipt; merge, publish and verify the web separately.'}
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
