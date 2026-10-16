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


def _strict_pairs(items):
    value = {}
    for key, item in items:
        if key in value: raise ValueError('duplicate_json_key')
        value[key] = item
    return value


def _nonfinite(_):
    raise ValueError('nonfinite_json')


_STRICT_DECODER = json.JSONDecoder(object_pairs_hook=_strict_pairs, parse_constant=_nonfinite)


def strict_json(text):
    return _STRICT_DECODER.decode(text)


def empty():
    return {'version': 1, 'sites': {}, 'objects': {}, 'records': [], 'receipts': {}}


def state(root):
    path = workspace_path(PATH, root)
    return strict_json(path.read_text()) if path.exists() else empty()


def site_state(root):
    """Read the small leading site projection without parsing unrelated claims.

    ``write_json`` preserves the registry's top-level order, where ``version``
    and ``sites`` precede the much larger object-record ledger.  The task page
    only needs published site histories.  Decode those two values strictly and
    stop before objects/records so a progress request does not parse tens of
    thousands of unrelated statements.
    """
    path = workspace_path(PATH, root)
    if not path.exists():
        return {'version': 1, 'sites': {}}
    buffer = ''
    position = 0
    eof = False
    with path.open(encoding='utf-8') as stream:
        def fill():
            nonlocal buffer, eof
            block = stream.read(65536)
            if block:
                buffer += block
            else:
                eof = True

        def skip_space():
            nonlocal position
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position < len(buffer) or eof:
                    return
                fill()

        def expect(character):
            nonlocal position
            skip_space()
            if position >= len(buffer) or buffer[position] != character:
                raise ValueError('source_publication_prefix_invalid')
            position += 1

        def decode_value():
            nonlocal position
            while True:
                skip_space()
                try:
                    value, position = _STRICT_DECODER.raw_decode(buffer, position)
                    return value
                except json.JSONDecodeError as exc:
                    if eof:
                        raise ValueError('source_publication_prefix_invalid') from exc
                    fill()

        fill()
        expect('{')
        version_key = decode_value()
        expect(':')
        version = decode_value()
        expect(',')
        sites_key = decode_value()
        expect(':')
        sites = decode_value()
    if version_key != 'version' or version != 1 or sites_key != 'sites' or not isinstance(sites, dict):
        raise ValueError('source_publication_prefix_invalid')
    return {'version': 1, 'sites': sites}


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
    from inresearch.knowledge import site_register
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
        if baseline is not None:
            site_register.check_initial_identity(baseline['identity_registration'], row)
        row['observations'] = _merge_rows(row.get('observations', []), addition['observations'])
    return doc


def projects(root, runtime=None):
    return _projects(root, state(root) if runtime is None else runtime)


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


def companies(root, runtime=None):
    """New company identities share the directory; observations stay in their timeline."""
    from inresearch.knowledge import object_observations as ledger
    doc = strict_json((Path(root)/'data/companies.json').read_text())
    known = {c['company_id'] for c in doc['records']}
    native = Path(root)/ledger.PATH
    base = strict_json(native.read_text()) if native.exists() else ledger.empty()
    runtime = state(root) if runtime is None else runtime
    identities = _objects({'version':1, 'objects':base['objects'], 'records':[]},
                          {'objects':runtime['objects'], 'records':[]})['objects']
    notes = {}
    for rows in (base['records'], runtime['records']):
        for row in rows:
            if not row.get('registration_correction'): continue
            if row['id'] in notes and notes[row['id']] != row:
                raise ValueError('immutable_record_collision')
            notes.setdefault(row['id'], row)
    held = ledger.quarantined_objects({'records':notes.values()})
    for object_id, obj in identities.items():
        if object_id in held: continue
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
                          'baseline': {k:v for k,v in row.items() if k != 'observations'} if row.get('identity_registration') and row.get('verified_date') is None and row.get('observations', [{}])[0].get('schema_version') == 3 else None,
                          'observations': additions})
    doc = ledger.load(root)
    records = [r for r in doc['records'] if r.get('registration', {}).get('status') == 'unverified']
    ids = {r['object_id'] for r in records}
    return {'version': 1, 'sites': sites, 'objects': {i:doc['objects'][i] for i in ids}, 'records': records}


def install(root, payload, *, expected_state_sha=None):
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
    # An approved anonymous upload is a private receiver source, not a public
    # URL. Recheck its actual bytes and owner approval at the publication edge.
    from inresearch.materials import inbox as material_intake
    for site in payload['sites']:
        for row in site.get('observations', []):
            for ref in row.get('adoption', {}).get('document_refs', []):
                archive = ref.get('archive') or {}
                if archive.get('kind') != 'approved_task_upload':
                    continue
                received = material_intake.worker_record(archive['submission_id'])
                from datetime import datetime as _datetime, timezone as _timezone
                created = _datetime.fromtimestamp(received['created'], _timezone.utc).isoformat()
                approved = _datetime.fromtimestamp(received['approval']['at'], _timezone.utc).isoformat()
                if (received['sha256'] != ref['source_sha256']
                        or archive['sha256'] != received['sha256']
                        or archive['received_at'] != created
                        or archive['approved_at'] != approved):
                    raise ValueError('approved_task_upload_provenance_changed')
    path = workspace_path(PATH, root)
    with locked(path):
        previous = state(root)
        if key in previous['receipts']:
            return {**previous['receipts'][key], 'state':'already_published', 'new_records':0,
                    'seconds':round(time.monotonic()-started,6)}
        if expected_state_sha is not None and digest(previous) != expected_state_sha:
            raise ValueError('source_publication_context_changed')
        updated = copy.deepcopy(previous)
        # Validate the combined typed identities before using company IDs in a
        # site's roles. Runtime and same-batch ordinary companies share one
        # directory; neither an unreferenced identity nor a malformed claim is
        # authority to introduce a participant.
        for row in payload['records']:
            if row.get('registration', {}).get('status') != 'unverified': raise ValueError('ordinary_source_only')
        used = {r['object_id'] for r in payload['records']}
        if set(payload['objects']) != used: raise ValueError('unreferenced_object_identity')
        native_path = Path(root)/ledger.PATH
        native = strict_json(native_path.read_text()) if native_path.exists() else ledger.empty()
        old_objects = _objects(native, previous)
        candidate = _objects(old_objects, payload)
        ledger.check(candidate, root)
        before_projects = _projects(root, previous)
        by_id = {r['site_id']:r for r in before_projects['records']}
        known_companies = strict_json((Path(root)/'data/companies.json').read_text())['records']
        names_by_id, ids_by_name = {}, {}
        for company in known_companies:
            names_by_id.setdefault(company['company_id'], set()).add(company.get('name'))
            ids_by_name.setdefault(str(company.get('name','')).casefold(), set()).add(company['company_id'])
        for obj in candidate['objects'].values():
            if obj['type'] != 'company': continue
            ident, name = obj['identity']['company_id'], obj['name']
            if names_by_id.get(ident, set()) - {name}:
                raise ValueError('immutable_company_identity_collision')
            # Same case-folded name is the existing ordinary intake's duplicate
            # identity rule. Apply it across code, runtime and this whole batch.
            if ids_by_name.get(name.casefold(), set()) - {ident}:
                raise ValueError('possible_duplicate_company_identity')
            known_companies.append({'company_id':ident,'name':name})
            names_by_id.setdefault(ident, set()).add(name)
            ids_by_name.setdefault(name.casefold(), set()).add(ident)
        companies = {c['company_id'] for c in known_companies}
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
                if old:
                    site_register.check_initial_identity(identity, old)
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
