"""Typed, append-only observations independent of model demand or legacy baselines."""
import copy
import json
import math
import re
from pathlib import Path
from inresearch.knowledge import observation_time
from inresearch.workflow.project_review_reader import digest
from inresearch.knowledge.registry import review_valid

KINDS = {'reported', 'measured', 'estimated', 'calculated', 'forecast', 'offer'}
IDENTITIES = {'company': ('company_id',), 'product': ('company_id', 'model', 'version'),
              'statistic': ('publisher', 'series', 'geography', 'definition'),
              'quote': ('company_id', 'configuration', 'market', 'currency', 'billing_basis')}
PATH = 'data/object_observations.json'


def identity(obj, root=None):
    if not isinstance(obj, dict) or obj.get('type') not in IDENTITIES:
        raise ValueError('unique_typed_object_required')
    keys = IDENTITIES[obj['type']]
    native = obj.get('identity')
    if (not isinstance(native, dict) or set(native) != set(keys)
            or any(not isinstance(native[k], str) or not native[k].strip() for k in keys)):
        raise ValueError('complete_native_identity_required')
    if root is not None and 'company_id' in native:
        ids = {r['company_id'] for r in json.loads((Path(root)/'data/companies.json').read_text())['records']}
        if native['company_id'] not in ids or native['company_id'] in {'multiple', 'unknown'}:
            raise ValueError('registered_unique_company_required')
    expected = obj['type']+':'+digest({'type': obj['type'], 'identity': native})[:32]
    if obj.get('id') != expected or not isinstance(obj.get('name'), str) or not obj['name'].strip():
        raise ValueError('object_identity_digest_mismatch')
    return expected


def object_record(kind, native, name):
    obj = {'type': kind, 'identity': native, 'name': name}
    obj['id'] = kind+':'+digest({'type': kind, 'identity': native})[:32]
    return obj


def check_claim(row):
    if (not isinstance(row.get('metric'), str) or not row['metric'].strip()
            or not isinstance(row.get('scope'), dict) or not row['scope']
            or row.get('kind') not in KINDS or not isinstance(row.get('basis'), str) or not row['basis'].strip()
            or not isinstance(row.get('unit'), str)):
        raise ValueError('metric_scope_kind_basis_required')
    observation_time.validate_period(row.get('effective_at'), row.get('valid_until'))
    observation_time.validate_period(row.get('period_start'), row.get('period_end'))
    value = row.get('value')
    if isinstance(value, dict):
        limits = value.get('value_range')
        if (set(value) != {'value_range'} or not isinstance(limits, list) or len(limits) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in limits) or limits[0] > limits[1]):
            raise ValueError('native_interval_required')
    elif (not isinstance(value, str) and (type(value) not in (int, float) or not math.isfinite(value))) or value == '' or isinstance(value,str) and len(value)>2000:
        raise ValueError('finite_value_or_native_text_required')
    if row['kind'] in {'estimated', 'calculated', 'forecast'} and not row.get('assumptions'):
        raise ValueError('uncertainty_assumptions_required')


def empty():
    return {'version': 1, 'objects': {}, 'records': []}


def load(root):
    p = Path(root)/PATH
    return json.loads(p.read_text()) if p.exists() else empty()


def archived_source_valid(source):
    archive = source.get('archive')
    if (source.get('url') is not None or not isinstance(archive, dict)
            or set(archive) != {'kind', 'doc_id', 'receipts'}
            or archive['kind'] != 'catalog_import'
            or archive['doc_id'] != 'doc-'+source.get('sha256', '')
            or not isinstance(archive['receipts'], list) or not archive['receipts']):
        return False
    seen = set()
    for receipt in archive['receipts']:
        if (not isinstance(receipt, dict) or set(receipt) != {'id', 'source_key_sha256', 'received_at'}
                or type(receipt['id']) != int or receipt['id'] <= 0 or receipt['id'] in seen
                or not isinstance(receipt['source_key_sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', receipt['source_key_sha256'])
                or observation_time.precision(receipt['received_at']) != 'timestamp'):
            return False
        seen.add(receipt['id'])
    return source.get('first_received_at') == min(
        archive['receipts'], key=lambda r: observation_time.bounds(r['received_at'])[0])['received_at']


def check(doc, root=None):
    if doc.get('version') != 1 or not isinstance(doc.get('objects'), dict) or not isinstance(doc.get('records'), list):
        raise ValueError('invalid_object_observation_ledger')
    for ident, obj in doc['objects'].items():
        if identity(obj, root) != ident:
            raise ValueError('object_registry_key_mismatch')
    seen, revised = {}, set()
    for row in doc['records']:
        check_claim(row)
        if row.get('object_id') not in doc['objects'] or row.get('id') in seen or not review_valid(row):
            raise ValueError('observation_identity_or_review_invalid')
        for key in ('recorded_at', 'reviewed_at'):
            if observation_time.precision(row.get(key)) != 'timestamp':
                raise ValueError('actual_review_and_record_times_required')
        source = row.get('source') or {}
        if (not isinstance(source.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}',source['sha256'])
                or not (isinstance(source.get('url'), str) and source['url'].startswith('https://')
                        or archived_source_valid(source)) or not source.get('locator') or not source.get('quote')
                or not source.get('context_sha256') or row.get('target_ids') != []):
            raise ValueError('source_backed_object_observation_required')
        observation_time.precision(source.get('published_at'))
        if source.get('first_received_at') is not None and observation_time.precision(source['first_received_at']) != 'timestamp':
            raise ValueError('actual_first_receipt_required')
        revision = row.get('revision')
        if revision:
            old = seen.get(revision.get('of'))
            if (not old or revision.get('of') in revised or revision.get('action') not in {'correct', 'withdraw'}
                    or any(row.get(k) != old.get(k) for k in ('object_id','metric','scope','effective_at','period_start','period_end','unit'))
                    or row['review'].get('tier') != 'A' or row['review'].get('authority') != 'owner'
                    or not revision.get('reason')):
                raise ValueError('scoped_owner_revision_required')
            revised.add(revision['of'])
        seen[row['id']] = row
    return doc


def current(doc, today=None):
    """Return candidates/conflicts explicitly; overlapping precision is not ordered."""
    from datetime import date
    today = today or date.today().isoformat()
    replaced = {r['revision']['of'] for r in doc['records'] if r.get('revision')}
    groups = {}
    for r in doc['records']:
        if r['id'] in replaced or r.get('revision', {}).get('action') == 'withdraw': continue
        key = digest({k:r.get(k) for k in ('object_id','metric','scope','unit')})
        g = groups.setdefault(key, {'current': [], 'conflicts': [], 'other': []})
        if (r['kind'] == 'forecast' or not observation_time.certainly_past(r.get('effective_at'), today)
                or r.get('valid_until') and observation_time.definitely_after(today, r['valid_until'])):
            g['other'].append(r); continue
        g['current'].append(r)
    for g in groups.values():
        candidates = g['current']
        latest = [r for r in candidates if not any(observation_time.definitely_after(n['effective_at'],r['effective_at']) for n in candidates)]
        g['current'] = latest
        if len({digest(r['value']) for r in latest}) > 1: g['conflicts'] = [r['id'] for r in latest]
    return list(groups.values())


def publication_contract(root):
    path = Path(root)/'framework/research_publication.json'
    return json.loads(path.read_text())


def public_records(root, company=None, object_id=None, kind=None):
    """The same reviewed field allowlist feeds pages and the public API.

    Adoption alone does not grant source redistribution. Ineligible rows do not
    contribute to public totals. Internal audit and original excerpts stay out.
    """
    doc = check(load(root))
    if not doc['records']: return []
    fields = publication_contract(root)['public']
    conflicts = {i for g in current(doc) for i in g['conflicts']}
    result = []
    for row in sorted(doc['records'], key=lambda r: observation_time.bounds(r['recorded_at'])[0], reverse=True):
        obj = doc['objects'][row['object_id']]
        if company and obj['identity'].get('company_id') != company: continue
        if object_id and obj['id'] != object_id: continue
        if kind and obj['type'] != kind: continue
        if row['review'].get('public_fields_reviewed') is not True: continue
        item = {k:copy.deepcopy(row.get(k)) for k in fields['record_fields']}
        if item.get('revision'):
            item['revision'] = {k:item['revision'].get(k) for k in fields['revision_fields']}
        item.update(object={k:copy.deepcopy(obj.get(k)) for k in fields['object_fields']},
                    conflict=row['id'] in conflicts,
                    source={k:row['source'].get(k) for k in fields['source_fields']})
        result.append(item)
    return result


def public_updates(root, limit=36, company=None):
    rows = public_records(root, company=company)
    result, counts = [], {}
    for row in rows:
        ident = row['object_id']
        if counts.get(ident, 0) >= 2: continue
        counts[ident] = counts.get(ident, 0) + 1
        result.append(row)
        if len(result) >= limit: break
    return {'total': len(rows), 'objects': len({r['object_id'] for r in rows}), 'changes': result}


def public_page(root, query):
    if set(query) - {'object', 'type', 'company', 'limit', 'offset'}:
        raise ValueError('unknown observation filter')
    limit, offset = int(query.get('limit', '50')), int(query.get('offset', '0'))
    if not 1 <= limit <= 100 or not 0 <= offset <= 1_000_000:
        raise ValueError('invalid observation page')
    if 'type' in query and query['type'] not in IDENTITIES:
        raise ValueError('invalid object type')
    if any(query.get(k) == '' for k in ('object', 'type', 'company')):
        raise ValueError('empty observation filter')
    rows = public_records(root, company=query.get('company'), object_id=query.get('object'), kind=query.get('type'))
    end = offset + limit
    return {'schema_version': publication_contract(root)['version'], 'audience': 'public',
            'total': len(rows), 'objects': len({r['object_id'] for r in rows}),
            'offset': offset, 'limit': limit, 'next_offset': end if end < len(rows) else None,
            'records': rows[offset:end]}
