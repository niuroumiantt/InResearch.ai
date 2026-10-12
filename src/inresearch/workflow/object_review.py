"""Review source-backed company/product/statistic/quote claims without model targets.

Extraction and validation are local deterministic operations. Named semantic C3
review is a separate explicit input; this command never creates its own approval.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from inresearch.knowledge import object_observations as ledger, observation_time
from inresearch.knowledge.registry import review_valid
from inresearch.materials.artifacts import safe_path
from inresearch.storage.files import locked, write_json
from inresearch.workflow.project_review_reader import digest, _readonly, _first_received


def pointer(value, path):
    if not isinstance(path, str) or not path.startswith('/'):
        raise ValueError('native_json_pointer_required')
    for part in path[1:].split('/'):
        key = part.replace('~1','/').replace('~0','~')
        value = value[int(key)] if isinstance(value,list) else value[key]
    return value


def source(data, sha, *, with_provenance=False):
    """Resolve receiver provenance, bytes and earliest *receiver* receipt."""
    if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):
        raise ValueError('source_hash_required')
    data=Path(data); acquisition=data/'acquisition/catalog.sqlite'
    rows=[]; archive=None
    if acquisition.is_file():
        with _readonly(acquisition) as db:
            rows=db.execute('SELECT * FROM product_documents WHERE sha256=? ORDER BY received_at', (sha,)).fetchall()
    if rows:
        urls={r['source_url'] for r in rows}
        if len(urls)!=1: raise ValueError('source_url_ambiguous_select_separate_context')
        r=min(rows,key=lambda r: observation_time.bounds(r['received_at'])[0]); path=safe_path(data,'acquisition/blobs/'+sha[:2]+'/'+sha+'.'+r['format'])
        first=r['received_at']; url=r['source_url']
    else:
        from inresearch.delivery.reader_export import supplied_sources
        with _readonly(data/'catalog/catalog.sqlite') as db:
            row=db.execute('SELECT doc_id,original_rel FROM documents WHERE sha256=?',(sha,)).fetchone()
            if not row: raise ValueError('received_source_required')
            receipts=db.execute('SELECT id,source_key,received FROM sources WHERE doc_id=? ORDER BY id',(row['doc_id'],)).fetchall()
        supplied=supplied_sources(data,sha).get(sha)
        path=safe_path(data,row['original_rel']);url=(supplied or {}).get('source_url')
        received=min((r['received'] for r in receipts if r['received'] is not None),default=None)
        first=datetime.fromtimestamp(received,timezone.utc).isoformat() if received is not None else None
        if not url:
            if (row['doc_id']!='doc-'+sha or not receipts or
                    any(not r['source_key'] or r['received'] is None for r in receipts)):
                raise ValueError('actual_archive_import_required')
            # Source paths stay in the runtime catalog. Freeze only their hashes
            # in Git; importing a local original does not invent a webpage URL.
            archive={'kind':'catalog_import','doc_id':row['doc_id'],'receipts':[
                {'id':r['id'],'source_key_sha256':hashlib.sha256(r['source_key'].encode()).hexdigest(),
                 'received_at':datetime.fromtimestamp(r['received'],timezone.utc).isoformat()} for r in receipts]}
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    if h.hexdigest()!=sha: raise ValueError('source_bytes_changed')
    if (url is None and archive is None) or (url is not None and not url.startswith('https://')): raise ValueError('public_source_url_required')
    if first is not None and observation_time.precision(first)!='timestamp': raise ValueError('invalid_receiver_receipt')
    return (path,url,first,archive) if with_provenance else (path,url,first)


def prepare(root,data,claims):
    if not isinstance(claims,list) or not 1<=len(claims)<=500:
        raise ValueError('bounded_claim_batch_required')
    cached={}; contexts=[]
    for claim in claims:
        ledger.identity(claim['object'],root);ledger.check_claim(claim)
        evidence=claim['evidence'];sha=evidence['sha256']
        if sha not in cached:
            path,url,first,archive=source(data,sha,with_provenance=True)
            if path.suffix.lower()=='.xlsx':
                from inresearch.adapters.xlsx_document import Workbook
                native=Workbook(path);mode='xlsx'
            elif path.suffix=='.json':
                native=json.loads(path.read_text(encoding='utf-8')); mode='json'
            else:
                from inresearch.workflow.research_match import pages
                native=pages(path);mode='pages'
            cached[sha]=(native,mode,url,first,path,archive)
        native,mode,url,first,path,archive=cached[sha];loc=evidence['locator']
        if mode=='xlsx':
            from inresearch.adapters.xlsx_document import matches_value
            cell,context=native.select(loc)
            if not matches_value(cell,claim['value']): raise ValueError('native_xlsx_value_mismatch')
            quoted=cell['value']
            if evidence.get('quote',quoted)!=quoted: raise ValueError('native_xlsx_quote_mismatch')
        elif mode=='json':
            observed=pointer(native,loc)
            # Native scalar extraction cannot silently change the source value.
            if observed!=claim['value'] or type(observed)!=type(claim['value']): raise ValueError('native_json_value_mismatch')
            quoted=str(observed)
            context=json.dumps(native,ensure_ascii=False,sort_keys=True,allow_nan=False)
        else:
            frame=re.fullmatch('html:srcdoc:([1-9][0-9]*)',str(loc))
            if frame:
                from inresearch.adapters.html_document import srcdoc
                context=srcdoc(path,int(frame[1]))
            else:
                match=re.fullmatch('excerpt:page:([1-9][0-9]*)',str(loc))
                if not match or int(match[1])>len(native): raise ValueError('native_page_locator_required')
                context=native[int(match[1])-1]
            quoted=evidence.get('quote')
            if not isinstance(quoted,str) or not quoted.strip() or ''.join(quoted.split()) not in ''.join(context.split()):
                raise ValueError('quote_not_in_native_context')
        if len(context)>2_000_000: raise ValueError('source_context_requires_smaller_selection')
        published=claim.get('published_at');observation_time.precision(published)
        if published is not None:
            date_quote=evidence.get('publication_quote')
            if (not date_quote or ''.join(date_quote.split()) not in ''.join(context.split())
                    or not observation_time.native_date_matches(published,date_quote)):
                raise ValueError('publication_time_requires_native_evidence')
        contexts.append({'sha256':sha,'url':url,'locator':loc,'quote':quoted,
                         'context_sha256':hashlib.sha256(context.encode()).hexdigest(),
                         'published_at':published,'first_received_at':first})
        if archive is not None: contexts[-1]['archive']=archive
    return {'version':digest({'claims':claims,'sources':contexts}),'sources':contexts}


def apply(root,data,proposal):
    root=Path(root);claims=proposal['claims'];context=prepare(root,data,claims)
    if proposal.get('source_version')!=context['version']: raise ValueError('source_or_identity_changed_since_review')
    review=proposal.get('review') or {};score=review.get('score')
    if (not review_valid({'review':review}) or type(score)!=int or not 5<=score<=10
            or review.get('tier')!=('A' if score>=8 else 'B') or not review.get('rationale')):
        raise ValueError('actual_named_c3_review_required')
    if review['tier']=='B' and int(context['version'][:8],16)%10==0:
        sample=review.get('sample_review') or {}
        if not sample.get('by') or sample.get('decision')!='confirmed': raise ValueError('deterministic_sample_required')
    key=digest(proposal);path=root/ledger.PATH
    with locked(path):
        doc=ledger.check(ledger.load(root),root)
        existing=[r for r in doc['records'] if r.get('proposal_sha256')==key]
        if existing: return {'state':'already_applied','records':len(existing),'proposal_sha256':key}
        known={r['claim_sha256'] for r in doc['records']}
        if all(digest(c) in known for c in claims):
            return {'state':'already_applied','records':len(claims),'proposal_sha256':key}
        if proposal.get('baseline_sha256')!=digest(doc): raise ValueError('observation_ledger_changed_since_review')
        at=datetime.now(timezone.utc).isoformat();added=[]
        for index,(claim,evidence) in enumerate(zip(claims,context['sources'])):
            if digest(claim) in known: continue
            obj=claim['object'];ident=obj['id'];old=doc['objects'].get(ident)
            if old and old!=obj: raise ValueError('immutable_object_identity_or_label_changed')
            doc['objects'][ident]=obj
            row={k:claim[k] for k in ('metric','scope','value','unit','kind','basis','effective_at','valid_until','period_start','period_end','assumptions','revision') if k in claim}
            row.update(id='observation:'+digest({'proposal':key,'index':index})[:32],object_id=ident,
                       source=evidence,target_ids=[],review=review,reviewed_at=review['at'],recorded_at=at,proposal_sha256=key,claim_sha256=digest(claim))
            if row.get('revision'): row['replaces_record_ids']=[row['revision']['of']]
            doc['records'].append(row);added.append(row['id'])
            known.add(digest(claim))
        ledger.check(doc,root)
        new_conflicts={i for group in ledger.current(doc) for i in group['conflicts']} & set(added)
        if new_conflicts and review['tier']!='A': raise ValueError('conflict_requires_c3_a_review')
        write_json(path,doc)
        return {'state':'applied','records':len(added),'ids':added,'proposal_sha256':key,'recorded_at':at}


def main(argv=None):
    from inresearch.paths import project_root
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['prepare','apply'])
    ap.add_argument('--input',type=Path,required=True);ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--output',type=Path);args=ap.parse_args(argv)
    value=json.loads(args.input.read_text());root=project_root()
    if args.action=='prepare':
        c=prepare(root,args.data,value);result={'source_version':c['version'],'baseline_sha256':digest(ledger.load(root)), 'claims':value}
        if not args.output: ap.error('prepare requires --output for the private review proposal')
        write_json(args.output,result);print(json.dumps({'claims':len(value),'source_version':c['version'],'model_calls':0}))
    else:
        result=apply(root,args.data,value);print(json.dumps(result))
