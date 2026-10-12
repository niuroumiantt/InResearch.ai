"""Source statements register immediately; identity is stable, truth is not certified.

Append to the existing site timeline. No C3 score, full reading, model demand,
webpage URL or special supplier sidecar is required for ordinary registration.
"""
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from inresearch.storage.files import locked, write_json
from inresearch.knowledge import observation_time, site_register, site_timeline
from inresearch.workflow.object_review import source


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def apply(root, data, statement):
    root,data=Path(root),Path(data)
    if isinstance(statement, dict) and 'object' in statement:
        return apply_object(root, data, statement)
    if not isinstance(statement,dict) or statement.get('version')!=1:
        raise ValueError('source_statement_version_required')
    site_id=statement.get('site_id')
    if not isinstance(site_id,str) or not re.fullmatch('[a-z0-9][a-z0-9_.-]{0,159}',site_id):
        raise ValueError('stable_site_id_required')
    fields=statement.get('fields')
    if not isinstance(fields,dict) or not fields or set(fields)-site_timeline.FIELDS:
        raise ValueError('source_statement_fields_required')
    evidence=statement.get('source') or {}
    sha=evidence.get('sha256')
    # Byte identity and actual receiver provenance are technical bookkeeping,
    # not a semantic verdict about the source's claims.
    _,url,first,archive=source(data,sha,with_provenance=True)
    published=evidence.get('published_at');effective=statement.get('effective_at')
    for stamp in (published,effective):observation_time.precision(stamp)
    stamp=datetime.now(timezone.utc).isoformat()
    normalized=copy.deepcopy(fields)
    if set(site_timeline.IT_BUNDLE)&normalized.keys():
        for key in site_timeline.IT_BUNDLE:normalized.setdefault(key,{} if key=='capacity_it_mw_by_status' else None)
    binding={'version':1,'site_id':site_id,'fields':sorted(normalized),'scope':statement.get('scope','whole_site')}
    site_timeline.check_object_binding(binding)
    payload={k:statement.get(k) for k in ('site_id','effective_at','kind','basis','assumptions','identity')}
    payload.update(fields=normalized,source={'sha256':sha,'published_at':published,'locator':evidence.get('locator')},scope=binding['scope'])
    key='statement-'+digest(payload)
    entry={'schema_version':3,'id':key,'recorded_at':stamp,'effective_at':effective,
           'kind':statement.get('kind','reported'),'scope':binding['scope'],
           'basis':statement.get('basis') or '来源陈述 · 基础登记待查',
           'assumptions':statement.get('assumptions',[]),'fields':normalized,
           'registration':{'status':'unverified','registered_by':statement.get('registered_by') or 'source-intake','at':stamp},
           'source_versions':[{'source_sha256':sha,'published_at':published,
             'published_at_precision':observation_time.precision(published),
             'published_at_provenance':'source_supplied_not_fact_checked' if published else 'unknown',
             'first_received_at':first,'first_received_at_precision':observation_time.precision(first),
             'first_received_at_provenance':'actual_receiver_catalog'}],
           'sources':[{'url':url,'grade':'source_statement','source_sha256':sha}],
           'adoption':{'registration_id':key,'source_kind':'source_statement','source_id':sha,
             'source_version':digest({'sha256':sha,'archive':archive,'url':url}),
             'document_refs':[{'source_sha256':sha,'source_url':url,'archive':archive,'locator':evidence.get('locator')}],
             'target_ids':[],'object_binding':binding}}
    path=root/'data/projects.json'
    with locked(path):
        register=json.loads(path.read_text());old=next((r for r in register['records'] if r['site_id']==site_id),None)
        if old and (old.get('duplicate_of') or old.get('identity_scope') in ('cluster','portfolio') or 'portfolio' in site_id):
            raise ValueError('unique_physical_site_required')
        if old:
            prior=next((r for r in old.get('observations',[]) if r['id']==key),None)
            if prior:
                entry['recorded_at']=prior['recorded_at'];entry['registration']=prior['registration']
                # Keep the first frozen receiver clock on an identical replay.
                entry['source_versions']=prior['source_versions']
        else:
            identity=statement.get('identity')
            site_register.check_initial_identity(identity)
            if identity['site_id']!=site_id or normalized.get('name',identity['name'])!=identity['name']:
                raise ValueError('initial_site_identity_mismatch')
            names={str(n).casefold() for p in register['records'] for n in [p.get('name'),*(p.get('aliases') or [])] if n}
            if identity['name'].casefold() in names:raise ValueError('possible_duplicate_project_identity')
            address = identity.get('street_address')
            if address and any(r.get('country') == identity['country'] and
                    str(r.get('street_address') or '').casefold() == address.casefold()
                    for r in register['records']):
                raise ValueError('possible_duplicate_project_address')
            old={k:v for k,v in identity.items() if k not in ('version','native_name','basis')}
            old.update(status=normalized.get('status'),notes='基础登记待查',verified_date=None,
                       capacity_it_mw=None,capacity_facility_mw=None,capacity_planned_it_mw=None,
                       capacity_it_mw_by_status={},sources=entry['sources'],identity_registration=identity)
        if statement.get('identity'):
            site_register.check_initial_coordinates(statement['identity'])
            for k in ('site_id','country','region','location','province','city','district','street_address',
                      'coordinates','coordinate_source'):
                if k in statement['identity'] and statement['identity'][k]!=old.get(k):raise ValueError('physical_site_identity_changed:'+k)
            if statement['identity'].get('coordinate_source'):
                point_source = statement['identity']['coordinate_source']
                _, point_url, _, _ = source(data, point_source['source_sha256'], with_provenance=True)
                if point_url is not None and point_url != point_source['url']:
                    raise ValueError('coordinate_source_url_mismatch')
        updated,replay=site_timeline.append(old,entry)
        if not replay:
            index=next((i for i,r in enumerate(register['records']) if r['site_id']==site_id),None)
            if index is None:register['records'].append(updated)
            else:register['records'][index]=updated
            write_json(path,register)
    return {'state':'already_registered' if replay else 'registered_in_checkout','site_id':site_id,'statement_id':key,'status':'unverified','fields':sorted(normalized),'truth_checked':False}


def apply_object(root, data, statement):
    """Register a typed claim with actual source provenance, without C3 or a target."""
    from inresearch.knowledge import object_observations as ledger
    if statement.get('version') != 1:
        raise ValueError('source_statement_version_required')
    obj = statement['object']
    ledger.identity(obj)
    ledger.check_claim(statement)
    evidence = statement.get('source') or statement.get('evidence') or {}
    sha = evidence.get('sha256')
    _, url, first, archive = source(data, sha, with_provenance=True)
    if not isinstance(evidence.get('locator'), str) or not evidence['locator'].strip():
        raise ValueError('source_locator_required')
    if not isinstance(evidence.get('quote'), str) or not evidence['quote'].strip():
        raise ValueError('source_excerpt_required')
    observation_time.precision(evidence.get('published_at'))
    native = {k:copy.deepcopy(statement.get(k)) for k in ('metric','value','unit','kind','scope','effective_at','valid_until','period_start','period_end','basis','assumptions')}
    native.update(object_id=obj['id'], target_ids=[], source={'sha256':sha,'url':url,'archive':archive,
                  'locator':evidence['locator'],'quote':evidence['quote'],
                  'context_sha256':digest({'locator':evidence['locator'],'quote':evidence['quote']}),
                  'published_at':evidence.get('published_at'),'first_received_at':first})
    key = 'source-object-'+digest(native)
    stamp = datetime.now(timezone.utc).isoformat()
    native.update(id=key,recorded_at=stamp,reviewed_at=None,
                  registration={'status':'unverified','registered_by':statement.get('registered_by') or 'source-intake','at':stamp})
    path = Path(root)/ledger.PATH
    with locked(path):
        # Authoring writes the checkout ledger; runtime import is a separate command.
        doc = json.loads(path.read_text()) if path.exists() else ledger.empty()
        old = next((v for v in doc['records'] if v['id'] == key), None)
        if old:
            if doc['objects'].get(obj['id']) != obj: raise ValueError('immutable_object_identity_collision')
            return {'state':'already_registered','object_id':obj['id'],'statement_id':key,'truth_checked':False}
        if obj['id'] in doc['objects'] and doc['objects'][obj['id']] != obj:
            raise ValueError('immutable_object_identity_collision')
        if obj['type'] == 'company':
            known = json.loads((Path(root)/'data/companies.json').read_text())['records']
            known += [{'company_id':o['identity']['company_id'],'name':o['name']} for o in doc['objects'].values() if o['type']=='company']
            if any(c['company_id'] != obj['identity']['company_id'] and
                   str(c.get('name','')).casefold() == obj['name'].casefold() for c in known):
                raise ValueError('possible_duplicate_company_identity')
        doc['objects'][obj['id']] = copy.deepcopy(obj)
        doc['records'].append(native)
        ledger.check(doc, root)
        write_json(path,doc)
    return {'state':'registered_in_checkout','object_id':obj['id'],'statement_id':key,'status':'unverified','truth_checked':False}


def apply_batch(root, data, statements):
    """One failed identity must not block unrelated registrations."""
    import time
    started = time.monotonic()
    receipts = []
    for index, item in enumerate(statements):
        try:
            receipt = apply(root, data, item)
        except (ValueError, TypeError, KeyError, FileNotFoundError) as exc:
            receipt = {'state': 'held_as_clue', 'error': str(exc)}
        receipts.append({'index': index, **receipt})
    return {'receipts': receipts,
            'registered': sum(r['state'] == 'registered_in_checkout' for r in receipts),
            'replayed': sum(r['state'] == 'already_registered' for r in receipts),
            'held': sum(r['state'] == 'held_as_clue' for r in receipts),
            'seconds': round(time.monotonic() - started, 6), 'published': False}


def main(argv=None):
    import argparse
    from inresearch.paths import project_root
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=project_root())
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--input', type=Path, required=True, help='JSON array or JSONL statements')
    ap.add_argument('--receipt', type=Path, required=True, help='Private receipt retains held clues')
    args = ap.parse_args(argv)
    text = args.input.read_text()
    statements = json.loads(text) if text.lstrip().startswith('[') else [json.loads(line) for line in text.splitlines() if line.strip()]
    if not isinstance(statements, list):
        ap.error('input must be a statement array or JSONL')
    result = apply_batch(args.root, args.data, statements)
    result['held_statements'] = [{'index': r['index'], 'statement': statements[r['index']], 'error': r['error']}
                                 for r in result['receipts'] if r['state'] == 'held_as_clue']
    write_json(args.receipt, result)
    print(json.dumps({key: result[key] for key in ('registered','replayed','held','seconds','published')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
