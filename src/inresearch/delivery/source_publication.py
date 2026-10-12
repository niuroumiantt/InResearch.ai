"""Publish ordinary source additions to durable state, independently of Git releases.

Trusted operators import through the local CLI/SSH. This is not an anonymous
upload API. Originals remain at the source; only projections reach public APIs.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

from inresearch.storage.files import locked, write_json
from inresearch.storage.layout import workspace_path

PATH = 'data/raw/source-publication/registry.json'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def strict_json(text):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise ValueError('duplicate_json_key')
            value[key] = item
        return value
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def empty():
    return {'version': 1, 'sites': {}, 'objects': {}, 'records': [], 'receipts': {}}


def state(root):
    path = workspace_path(PATH, root)
    return strict_json(path.read_text()) if path.exists() else empty()


def _merge_rows(old, new):
    result = copy.deepcopy(old)
    index = {r['id']: r for r in result}
    for row in new:
        if row['id'] in index:
            if index[row['id']] != row: raise ValueError('immutable_record_collision')
        else:
            result.append(copy.deepcopy(row)); index[row['id']] = row
    return result


def _projects(root, runtime):
    doc = strict_json((Path(root)/'data/projects.json').read_text())
    by_id = {r['site_id']: r for r in doc['records']}
    for ident, addition in runtime['sites'].items():
        if ident not in by_id:
            baseline = copy.deepcopy(addition['baseline'])
            if baseline is None: raise ValueError('unknown_site_without_identity')
            baseline['observations'] = []
            doc['records'].append(baseline); by_id[ident] = baseline
        row = by_id[ident]
        baseline = addition.get('baseline')
        if baseline is not None and row.get('identity_registration') != baseline['identity_registration']:
            raise ValueError('runtime_identity_conflicts_with_code_baseline')
        row['observations'] = _merge_rows(row.get('observations', []), addition['observations'])
    return doc


def projects(root):
    return _projects(root, state(root))


def _objects(doc, runtime):
    doc = copy.deepcopy(doc)
    for ident, obj in runtime['objects'].items():
        if ident in doc['objects'] and doc['objects'][ident] != obj:
            raise ValueError('immutable_object_identity_collision')
        doc['objects'][ident] = copy.deepcopy(obj)
    doc['records'] = _merge_rows(doc['records'], runtime['records'])
    return doc


def objects(root, doc):
    return _objects(doc, state(root))


def companies(root):
    """New company identities share the directory; observations stay in their timeline."""
    from inresearch.knowledge import object_observations as ledger
    doc = strict_json((Path(root)/'data/companies.json').read_text())
    known = {c['company_id'] for c in doc['records']}
    for obj in ledger.load(root)['objects'].values():
        if obj['type'] == 'company' and obj['identity']['company_id'] not in known:
            ident = obj['identity']['company_id']
            doc['records'].append({'company_id':ident,'name':obj['name'],'name_cn':None,
                                   'roles':[],'profile':None,'registration_status':'unverified'})
            known.add(ident)
    return doc


def bundle(root):
    """Export only ordinary registrations; verified research cannot bypass its queue."""
    from inresearch.knowledge import object_observations as ledger
    sites = []
    for row in projects(root)['records']:
        additions = [v for v in row.get('observations', []) if v.get('schema_version') == 3]
        if additions:
            sites.append({'site_id': row['site_id'],
                          'baseline': {k:v for k,v in row.items() if k != 'observations'} if row.get('identity_registration') else None,
                          'observations': additions})
    doc = ledger.load(root)
    records = [r for r in doc['records'] if r.get('registration', {}).get('status') == 'unverified']
    ids = {r['object_id'] for r in records}
    return {'version': 1, 'sites': sites, 'objects': {i:doc['objects'][i] for i in ids}, 'records': records}


def install(root, payload):
    """Atomic, idempotent append with no network, model or factual verification."""
    from inresearch.knowledge import object_observations as ledger, site_timeline, site_register
    started = time.monotonic()
    if (not isinstance(payload, dict) or set(payload) != {'version','sites','objects','records'}
            or type(payload['version']) is not int or payload['version'] != 1
            or not isinstance(payload['sites'], list) or not isinstance(payload['objects'], dict)
            or not isinstance(payload['records'], list)
            or len(payload['sites']) > 500 or len(payload['records']) > 5000
            or sum(len(s.get('observations', [])) for s in payload['sites']) > 5000):
        raise ValueError('bounded_source_publication_required')
    key = digest(payload)
    path = workspace_path(PATH, root)
    with locked(path):
        previous = state(root)
        if key in previous['receipts']:
            return {**previous['receipts'][key], 'state':'already_published', 'new_records':0,
                    'seconds':round(time.monotonic()-started,6)}
        updated = copy.deepcopy(previous)
        before_projects = _projects(root, previous)
        by_id = {r['site_id']:r for r in before_projects['records']}
        companies = {r['company_id'] for r in strict_json((Path(root)/'data/companies.json').read_text())['records']}
        new_sites = new_records = 0
        seen = set()
        for item in payload['sites']:
            if set(item) != {'site_id','baseline','observations'} or item['site_id'] in seen or not item['observations']:
                raise ValueError('unique_source_site_required')
            ident = item['site_id']; seen.add(ident)
            old = by_id.get(ident)
            if old and (old.get('duplicate_of') or old.get('identity_scope') in ('cluster','portfolio')):
                raise ValueError('unique_physical_site_required')
            baseline = item['baseline']
            if baseline is not None:
                identity = baseline.get('identity_registration')
                site_register.check_initial_identity(identity)
                if identity['site_id'] != ident or baseline.get('verified_date') is not None:
                    raise ValueError('unverified_initial_identity_required')
                if old and old.get('identity_registration') != identity:
                    raise ValueError('immutable_site_identity_collision')
            if old is None:
                if baseline is None: raise ValueError('new_site_identity_required')
                first = item['observations'][0]
                if first['fields'].get('name') != identity['name'] or baseline.get('name') != identity['name']:
                    raise ValueError('initial_name_binding_required')
                expected = {k:v for k,v in identity.items() if k not in ('version','native_name','basis')}
                expected.update(status=first['fields'].get('status'),notes='基础登记待查',verified_date=None,
                                capacity_it_mw=None,capacity_facility_mw=None,capacity_planned_it_mw=None,
                                capacity_it_mw_by_status={},sources=first['sources'],identity_registration=identity)
                if baseline != expected: raise ValueError('initial_baseline_must_be_registration_only')
                if any(str(p.get('name','')).casefold() == identity['name'].casefold() for p in by_id.values()):
                    raise ValueError('possible_duplicate_site_identity')
                if identity.get('street_address') and any(p.get('country') == identity['country'] and
                        str(p.get('street_address','')).casefold() == identity['street_address'].casefold() for p in by_id.values()):
                    raise ValueError('possible_duplicate_site_address')
                old = copy.deepcopy(baseline); old['observations'] = []
                by_id[ident] = old; new_sites += 1
            for row in item['observations']:
                if row.get('schema_version') != 3: raise ValueError('ordinary_source_only')
                site_timeline.check(row)
                site_timeline.check_object_binding(row['adoption']['object_binding'], site_id=ident)
                for role in ('developer','tenant','owner','operator','builder', *site_register.ACTOR_ROLES):
                    if any(i not in companies for i in row['fields'].get(role, [])):
                        raise ValueError('unknown_participant_id')
            merged = _merge_rows(old.get('observations', []), item['observations'])
            new_records += len(merged) - len(old.get('observations', []))
            target = updated['sites'].setdefault(ident, {'baseline':copy.deepcopy(baseline), 'observations':[]})
            target['observations'] = _merge_rows(target['observations'], item['observations'])
        for row in payload['records']:
            if row.get('registration', {}).get('status') != 'unverified': raise ValueError('ordinary_source_only')
        used = {r['object_id'] for r in payload['records']}
        if set(payload['objects']) != used: raise ValueError('unreferenced_object_identity')
        native_path = Path(root)/ledger.PATH
        native = strict_json(native_path.read_text()) if native_path.exists() else ledger.empty()
        old_objects = _objects(native, previous)
        candidate = _objects(old_objects, payload)
        ledger.check(candidate, root)
        new_records += len(candidate['records']) - len(old_objects['records'])
        updated['objects'] = _objects({'version':1,'objects':updated['objects'],'records':[]},
                                     {'objects':payload['objects'],'records':[]})['objects']
        updated['records'] = _merge_rows(updated['records'], payload['records'])
        # Prove the merged site histories before committing the one durable pointer.
        for row in _projects(root, updated)['records']: site_timeline.check_history(row)
        receipt = {'batch_id':key, 'state':'published', 'new_sites':new_sites, 'new_records':new_records,
                   'published_at':datetime.now(timezone.utc).isoformat(), 'truth_checked':False,
                   'seconds':round(time.monotonic()-started,6)}
        updated['receipts'][key] = receipt
        write_json(path, updated)
    return receipt


def main(argv=None):
    from inresearch.paths import project_root
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export','install'))
    parser.add_argument('--root',type=Path,default=project_root())
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args(argv)
    if args.action == 'export':
        result = bundle(args.root)
    else:
        text = args.input.read_text() if args.input else sys.stdin.read(64*1024*1024+1)
        if len(text.encode()) > 64*1024*1024: raise ValueError('publication_too_large')
        result = install(args.root, strict_json(text))
    if args.output: write_json(args.output, result)
    else: print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
