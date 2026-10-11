"""Verify a daily HTML + private sources/evidence delivery, then index it on Spark."""
import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from inresearch.adapters.acquisition import Collector, data_root, hash_file, now
from inresearch.materials import daily_events, daily_sources
from inresearch.paths import project_root
from inresearch.storage.files import locked, write_json
from inresearch.workflow.research_match import ingest, match_pages


def verified(folder):
    folder=Path(folder).resolve()
    manifest=folder/'research-delivery.json'
    if manifest.is_symlink() or manifest.stat().st_size>1024*1024:
        raise ValueError('invalid_daily_manifest')
    raw=manifest.read_bytes(); value=json.loads(raw)
    if not isinstance(value,dict) or value.get('schema_version')!=1 or value.get('producer')!='inews_geluoke' or not isinstance(value.get('report_date'),str) or not re.fullmatch(r'20\d\d-\d\d-\d\d',value['report_date']):
        raise ValueError('invalid_daily_manifest')
    from datetime import date
    date.fromisoformat(value['report_date'])
    files=value.get('files')
    if not isinstance(files,list) or not 2<=len(files)<=100:
        raise ValueError('invalid_daily_manifest_files')
    seen=set(); total=0
    for row in files:
        if not isinstance(row,dict) or not isinstance(row.get('path'),str):raise ValueError('invalid_daily_manifest_file')
        rel=row.get('path',''); path=folder/rel
        if (not rel or Path(rel).is_absolute() or '..' in Path(rel).parts or rel in seen
                or path.is_symlink() or not path.resolve().is_relative_to(folder) or not path.is_file()
                or row.get('role') not in ('html','sources','validation','evidence','research','research_view')
                or type(row.get('bytes')) is not int or not 0<row['bytes']<=64*1024*1024
                or path.stat().st_size!=row['bytes'] or hash_file(path)!=row.get('sha256')):
            raise ValueError('daily_delivery_integrity')
        seen.add(rel);total+=row['bytes']
    if total>256*1024*1024 or sum(r['role']=='sources' for r in files)!=1 or not 1<=sum(r['role']=='html' for r in files)<=8 or sum(r['role']=='research' for r in files)>1:
        raise ValueError('invalid_daily_delivery_scope')
    source=next(folder/r['path'] for r in files if r['role']=='sources')
    daily_sources.load(source)  # Validate the sidecar before opening any input.
    for row in files:
        if row['role']=='html' and Path(row['path']).suffix.lower() not in ('.html','.htm'):
            raise ValueError('daily_html_required')
    research=next((r for r in files if r['role']=='research'),None)
    if research:
        from inresearch.materials.daily_research import load
        html=[r for r in files if r['role']=='html']
        if len(html)!=1:raise ValueError('research_sidecar_requires_one_html_identity')
        load(folder/research['path'],html[0]['sha256'],{r['path']:r for r in files})
    return value,hashlib.sha256(raw).hexdigest(),source


def receive(folder, data, root):
    folder=Path(folder);data=Path(data);root=Path(root)
    manifest,bundle_id,source=verified(folder)
    receipt=data/'material-reviews/daily-deliveries'/(bundle_id+'.json')
    members=[{k:row[k] for k in ('sha256','role','path')} for row in manifest['files']]
    source_sha=next(row['sha256'] for row in manifest['files'] if row['role']=='sources')
    with locked(receipt):
        received_at = now()  # Verified bundle arrival, before indexing work.
        prior_receipt = json.loads(receipt.read_text()) if receipt.exists() else None
        if prior_receipt is not None and (not isinstance(prior_receipt, dict)
                or prior_receipt.get('bundle_id') != bundle_id or prior_receipt.get('producer') != 'inews_geluoke'
                or prior_receipt.get('status') not in ('indexed_candidate','verified_arrival_pending_index')):
            raise ValueError('daily_receipt_identity_changed')
        pending = prior_receipt is not None and prior_receipt['status']=='verified_arrival_pending_index'
        if pending:
            try:
                first=datetime.fromisoformat(prior_receipt['first_received_at'].replace('Z','+00:00'))
                valid_time=first.tzinfo is not None and first.utcoffset() is not None
            except (KeyError,TypeError,AttributeError,ValueError):
                valid_time=False
            if (not valid_time or prior_receipt.get('schema_version')!=1
                    or prior_receipt.get('report_date')!=manifest['report_date']
                    or prior_receipt.get('source_sha256')!=source_sha or prior_receipt.get('members')!=members
                    or prior_receipt.get('files')!=len(manifest['files'])
                    or prior_receipt.get('receipt_timing_version')!=1
                    or prior_receipt.get('received_at')!=prior_receipt.get('first_received_at')
                    or prior_receipt.get('received_at_basis')!='first_verified_bundle_receipt'
                    or prior_receipt.get('reindex_count')!=0 or type(prior_receipt.get('reindex_count')) is not int
                    or prior_receipt.get('reindex_count_basis')!='complete_since_first_index'
                    or prior_receipt.get('last_indexed_at') is not None):
                raise ValueError('daily_arrival_marker_identity_changed')
        if prior_receipt is None:
            timing = {'receipt_timing_version': 1, 'received_at': received_at,
                      'first_received_at': received_at,
                      'received_at_basis': 'first_verified_bundle_receipt',
                      'reindex_count': 0, 'reindex_count_basis': 'complete_since_first_index'}
            # This durable arrival marker cannot authorize delivery: consumers
            # require indexed_candidate, which is written only after all indexes.
            write_json(receipt,{'schema_version':1,'bundle_id':bundle_id,'producer':'inews_geluoke',
                'report_date':manifest['report_date'],'source_sha256':source_sha,
                'files':len(manifest['files']),'members':members,**timing,'last_indexed_at':None,
                'status':'verified_arrival_pending_index'})
        elif prior_receipt.get('receipt_timing_version') == 1:
            timing = {key: prior_receipt[key] for key in ('receipt_timing_version', 'received_at', 'first_received_at',
                'received_at_basis', 'reindex_count_basis')}
            if type(prior_receipt.get('reindex_count')) is not int or prior_receipt['reindex_count'] < 0:
                raise ValueError('daily_receipt_invalid_reindex_count')
            timing['reindex_count'] = prior_receipt['reindex_count'] + (0 if pending else 1)
            if 'legacy_received_at' in prior_receipt:
                timing['legacy_received_at'] = prior_receipt['legacy_received_at']
        else:
            # Old receive() rewrote this timestamp on every replay. Preserve
            # the last recorded value without claiming the first receipt time.
            timing = {'receipt_timing_version': 1, 'received_at': prior_receipt.get('received_at'),
                      'first_received_at': None,
                      'received_at_basis': 'legacy_last_recorded_index',
                      'legacy_received_at': prior_receipt.get('received_at'),
                      'reindex_count': 1, 'reindex_count_basis': 'since_timestamp_tracking'}
        # Replay safely reindexes against today's task book without re-reading.
        c=Collector(data)
        try:
            for row in manifest['files']:
                if row['role']=='html': continue
                path=folder/row['path']
                ident=c.item('fetchreports','daily-support:'+row['sha256'],'daily_support','',path.name,
                             {'producer':'inews_geluoke','role':row['role'],'bundle_id':bundle_id,'report_date':manifest['report_date']})
                sha=c.archive_file(ident,path,path.suffix.lower(),{'bundle_id':bundle_id,'role':row['role'],'relative_path':row['path']})
                if sha!=row['sha256']: raise ValueError('daily_delivery_changed_during_archive')
        finally:c.close()
        documents=[]
        for row in manifest['files']:
            if row['role']!='html':continue
            title=Path(row['path']).name
            if manifest['report_date'] not in title:title=manifest['report_date']+'-'+title
            document=ingest(folder/row['path'],data,root,title=title,daily_sources=source)
            if document['sha256']!=row['sha256']:raise ValueError('daily_delivery_changed_during_index')
            documents.append(document)
        ledger_path=data/'acquisition/daily-events.json'
        event_ids={i for d in documents for i in d['daily_event_ids']}
        with locked(ledger_path):
            ledger=json.loads(ledger_path.read_text())
            research=next((r for r in manifest['files'] if r['role']=='research'),None)
            if research:
                from inresearch.materials.daily_research import load,attach
                available={r['path']:r for r in manifest['files']}
                value=load(folder/research['path'],documents[0]['sha256'],available)
                enriched=attach([ledger['records'][i] for i in event_ids],value,research['sha256'],available,folder)
                for event in enriched:ledger['records'][event['id']]=event
            for ident in event_ids:
                event=ledger['records'][ident]
                matches,_=match_pages([event['title']+'\n'+event['body']],root)
                previous=event.get('demand_matches')
                if previous is not None and previous!=matches:
                    event.setdefault('demand_history',[]).append({'targets_sha256':event.get('targets_sha256'),'matches':previous})
                event.update(demand_matches=matches,targets_sha256=hash_file(root/'framework/tco_targets.json'))
            write_json(ledger_path,ledger)
        indexed_at = now()
        timing['last_indexed_at'] = indexed_at
        result={'schema_version':1,'bundle_id':bundle_id,'producer':'inews_geluoke','report_date':manifest['report_date'],
                **timing,'status':'indexed_candidate','files':len(manifest['files']),'members':members,
                'documents':[{'sha256':d['sha256'],'title':d['title'],'event_ids':d['daily_event_ids']} for d in documents],
                'events':len(event_ids),'events_with_sources':sum(any(s['urls'] for s in ledger['records'][i]['sources']) for i in event_ids),
                'source_sha256':source_sha,'targets_sha256':hash_file(root/'framework/tco_targets.json'),
                'structured_research':bool(research),
                'reading':'existing_reader_queue','formal_capacity_updates':0,
                'scope':'来源链接和需求匹配已登记；园区身份、逐数字口径及 C3 采用分别核验。'}
        write_json(receipt,result)
    # Research work can start event-by-event; receiving a bundle never adopts.
    from inresearch.workflow.project_review import prepare
    try:
        result['project_review_queue'] = prepare(data, root)['counts']
    except (OSError, ValueError, KeyError):
        result['project_review_queue'] = {'status':'needs_retry'}
    return {**result,'receipt':str(receipt)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--data-root',type=Path,default=data_root())
    args=parser.parse_args()
    try:result=receive(args.input,args.data_root,project_root())
    except (OSError,ValueError) as exc:
        print(json.dumps({'status':'failed','error':str(exc)},ensure_ascii=False));return 1
    print(json.dumps(result,ensure_ascii=False));return 0
