"""Receipt-sealed uploads and owner-approved, exact-member review batches."""
from contextlib import ExitStack
import hashlib
import json
import re
import time
import uuid

from inresearch.materials import inbox
from inresearch.storage.files import locked


def batch_path(kind, key):
    if not isinstance(key, str) or not re.fullmatch(r'[a-f0-9-]{36}', key):
        raise ValueError('invalid batch id')
    uuid.UUID(key)
    return inbox.root() / ('.'+kind+'-batches') / (key+'.json')


def upload_view(record, *, owner=False):
    key = record.get('batch_id')
    if not key or not record.get('batch_total'):
        return None
    path = batch_path('upload', key)
    if not path.exists():
        return {'id':key,'sealed':False,'expected':record['batch_total'],'received':0}
    state = json.loads(path.read_text())
    result = {'id':key,'sealed':state.get('sealed',False),
              'expected':state['expected'],'received':len(state['items'])}
    if owner:
        result['member_ids'] = [row['id'] for row in state['items']]
    return result




def receipt_for(token, key):
    import hmac
    return hmac.new(token.encode(),('task-upload:'+key).encode(),hashlib.sha256).hexdigest()


def recover_upload(payload):
    """A client-held batch secret restores lost upload responses without storing receipts."""
    import hmac
    if not isinstance(payload,dict) or set(payload) != {'batch_id','batch_token'}:
        raise ValueError('upload batch credential required')
    token=payload['batch_token']
    if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9-]{36}',token):
        raise PermissionError('invalid upload batch credential')
    path=batch_path('upload',payload['batch_id'])
    with locked(path):
        if not path.exists(): return {'items':[],'batch':None}
        state=json.loads(path.read_text())
        supplied=hashlib.sha256(token.encode()).hexdigest()
        if not state.get('token_hash') or not hmac.compare_digest(state['token_hash'],supplied):
            raise PermissionError('invalid upload batch credential')
        known={row['id'] for row in state['items']}
        # Recover the narrow gap after record durability but before manifest durability.
        for record in inbox.records():
            if (record.get('batch_id') != payload['batch_id'] or record.get('batch_token_hash') != supplied
                    or record['id'] in known): continue
            if state['sealed']:
                raise inbox.Conflict('sealed batch has an unclaimed durable upload; owner repair required')
            if any(row['index']==record['batch_index'] for row in state['items']):
                raise inbox.Conflict('upload batch index collision')
            state['items'].append({'id':record['id'],'sha256':record['sha256'],'index':record['batch_index']})
        state['items'].sort(key=lambda row:row['index'])
        inbox.atomic(path,state)
        items=[]
        for row in state['items']:
            record=inbox.load(row['id'])
            items.append({'id':row['id'],'receipt':receipt_for(token,row['id']),
                          'batch_index':row['index'],'name':record['name']})
        projection={'id':state['id'],'sealed':state['sealed'],'expected':state['expected'],
                    'received':len(items),'member_ids':[row['id'] for row in items]}
        return {'items':items,'batch':projection}

def seal(payload):
    if not isinstance(payload,dict) or set(payload) != {'batch_id','items'}:
        raise ValueError('batch receipt list required')
    rows = payload['items']
    if (not isinstance(rows,list) or not 1 <= len(rows) <= 20
            or any(not isinstance(row,dict) or set(row) != {'id','receipt'} for row in rows)
            or len({row['id'] for row in rows}) != len(rows)):
        raise ValueError('batch receipt list required')
    path = batch_path('upload',payload['batch_id'])
    with locked(path):
        state = json.loads(path.read_text())
        expected = {row['id'] for row in state['items']}
        if {row['id'] for row in rows} != expected:
            raise inbox.Conflict('batch received members changed; refresh receipts before sealing')
        for row in rows:
            item = inbox.receipt_view(row['id'],row['receipt'])
            if item.get('batch_id') != payload['batch_id']:
                raise PermissionError('invalid batch receipt')
        if not state.get('sealed'):
            state.update(sealed=True,sealed_at=time.time())
            inbox.atomic(path,state)
    return upload_view(inbox.load(rows[0]['id']),owner=True)


def load_review(key):
    return json.loads(batch_path('review',key).read_text())


def review_ready(record):
    key = record.get('review_batch_id')
    if not key:
        return True
    try:
        state = load_review(key)
    except (ValueError,OSError):
        return False
    return (state.get('state') == 'approved'
            and any(row['id'] == record['id'] and row['sha256'] == record['sha256']
                    for row in state['request']['items']))


def approve(payload, actor, role, *, valid_package_ids=None):
    """Validate every original first; durable prepare prevents partial worker release."""
    if not inbox.can_approve(actor,role):
        raise PermissionError('仅指定负责人可以批准整批作业')
    if (not isinstance(payload,dict)
            or set(payload) != {'operation_id','action','note','items'}
            or payload['action'] != 'approve_and_analyze'
            or not isinstance(payload['note'],str) or len(payload['note']) > 4000):
        raise ValueError('batch approval required')
    rows = payload['items']
    if (not isinstance(rows,list) or not 2 <= len(rows) <= 20
            or any(not isinstance(row,dict) or set(row) != {'id','sha256','expected_revision'} for row in rows)
            or len({row['id'] for row in rows}) != len(rows)):
        raise ValueError('请选择同批的2至20份原件')
    path = batch_path('review',payload['operation_id'])
    with locked(path), ExitStack() as locks:
        saved = json.loads(path.read_text()) if path.exists() else None
        if saved and (saved['request'] != payload or saved['by'] != actor):
            raise inbox.Conflict('batch approval replay changed')
        records = []
        for row in sorted(rows,key=lambda row:row['id']):
            target = inbox.record_path(row['id'])/'record.json'
            locks.enter_context(locked(target))
            record = json.loads(target.read_text())
            own = record.get('review_batch_id') == payload['operation_id']
            if (record['sha256'] != row['sha256']
                    or not own and (record.get('revision',0) != row['expected_revision']
                                    or record['status'] not in ('pending_approval','queued')
                                    or record.get('approval') or record.get('review_batch_id'))):
                raise inbox.Conflict('批次文件版本或审批状态已变化，请刷新')
            if not inbox.reviewable(record['name']):
                raise ValueError('批次含不支持自动审阅的附件，请单独处理')
            content = target.parent/'content'
            with content.open('rb') as stream:
                digest = hashlib.sha256()
                for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
                actual = digest.hexdigest()
            if content.stat().st_size != record['size'] or actual != record['sha256']:
                raise ValueError('原件内容已变化，不能批准')
            records.append(record)
        packages = {record.get('package_id') for record in records}
        batches = {record.get('batch_id') for record in records}
        if len(packages) != 1 or not next(iter(packages)) or len(batches) != 1 or not next(iter(batches)):
            raise ValueError('仅可联合批准同一上传批次、同一工作包的附件')
        if valid_package_ids is not None and not packages <= set(valid_package_ids):
            raise ValueError('工作包已失效，请刷新后绑定现行工作包')
        if any(record.get('continuation_of') in {row['id'] for row in records} for record in records):
            raise ValueError('同批成员不能互作上一轮系统回执')
        upload = upload_view(records[0],owner=True)
        excluded=[]
        if upload:
            selected={row['id'] for row in rows}
            omitted=[inbox.load(key) for key in upload['member_ids'] if key not in selected]
            if (not upload['sealed'] or not selected <= set(upload['member_ids'])
                    or any(row['status'] != 'rejected' for row in omitted)):
                raise inbox.Conflict('请等待上传批次封存，并选择全部未退回的附件')
            excluded=[{'id':row['id'],'sha256':row['sha256'],'decision':row.get('decision')} for row in omitted]
        if saved and saved['state'] == 'approved':
            return {'items':[inbox.owner_view(record) for record in records],
                    'batch':{'id':payload['operation_id'],'member_ids':[r['id'] for r in rows],'state':'approved'}}
        state = saved or {'id':payload['operation_id'],'by':actor,'at':time.time(),
                          'request':payload,'excluded':excluded,'state':'prepared'}
        inbox.atomic(path,state)
        for record in records:
            if record.get('review_batch_id') == payload['operation_id']:
                continue
            before = record['status']
            record.update(status='approved',review_batch_id=payload['operation_id'],
                          approval={'by':actor,'at':state['at'],'sha256':record['sha256']},
                          decision={'by':actor,'at':state['at'],'action':'approve_and_analyze','note':payload['note']},
                          analysis_requested_at=state['at'],revision=record.get('revision',0)+1)
            record.setdefault('operations',[]).append({'id':payload['operation_id'],'by':actor,'at':state['at'],
                'before':before,'after':'approved','request':payload})
            inbox.atomic(inbox.record_path(record['id'])/'record.json',record)
        state['state'] = 'approved'
        inbox.atomic(path,state)
    return {'items':[inbox.owner_view(record) for record in records],
            'batch':{'id':state['id'],'member_ids':[row['id'] for row in rows],'state':'approved'}}



def _without_batch_publications(root, runtime, payloads, checkpoint):
    """Subtract only exact server-created outbox additions, never an entire source/name."""
    from inresearch.delivery import source_publication
    from inresearch.materials import task_analysis
    state = json.loads(json.dumps(runtime))
    baseline_sites=set(checkpoint['baseline_sites'])
    baseline_receipts=set(checkpoint.get('baseline_receipts',[]))
    baseline_observations=checkpoint.get('baseline_observations',{})
    for payload in payloads:
        outbox = task_analysis._analysis_outbox(payload['id'],payload['analysis_id'])
        if not outbox.exists(): continue
        saved = json.loads(outbox.read_text())
        publication = saved['publication_batch']
        receipt_id=source_publication.digest(publication)
        if receipt_id not in baseline_receipts: state['receipts'].pop(receipt_id,None)
        for row in publication['sites']:
            target = state['sites'].get(row['site_id'])
            if target is None: continue
            own = {observation['id'] for observation in row['observations']} - set(
                baseline_observations.get(row['site_id'],[]))
            target['observations'] = [observation for observation in target['observations']
                                      if observation['id'] not in own]
            if not target['observations'] and row['site_id'] not in baseline_sites:
                del state['sites'][row['site_id']]
    return state


def _validate_joint(payloads, manifest):
    from pathlib import Path
    from inresearch.adapters.xlsx_document import Workbook
    from inresearch.materials import review_worker
    expected = {row['id']:row['sha256'] for row in manifest['request']['items']}
    if len(payloads) != len(expected) or {row['id']:row['sha256'] for row in payloads} != expected:
        raise ValueError('joint_analysis_members_changed')
    joint = payloads[0].get('batch_review')
    models=[row.get('model') for row in payloads if 'source_error' not in row]
    if (not isinstance(joint,dict) or set(joint) != {'id','members','summary','relationships'}
            or joint['id'] != manifest['id'] or not isinstance(joint['members'],list)
            or len(joint['members']) != len(expected)
            or {row.get('id'):row.get('sha256') for row in joint['members']} != expected
            or not isinstance(joint['summary'],str) or len(joint['summary']) > 1200
            or not isinstance(joint['relationships'],list) or len(joint['relationships']) > 20
            or any(row.get('batch_review') != joint for row in payloads)
            or any(model != models[0] for model in models)):
        raise ValueError('joint_analysis_receipt_invalid')
    allowed={}
    budget=max(600,30000//len(payloads))
    for payload in payloads:
        record=inbox.worker_record(payload['id'])
        if (record.get('review_batch_id') != manifest['id'] or record['sha256'] != payload['sha256']
                or record['status'] != 'archived' or not record.get('analysis_requested_at')):
            raise PermissionError('joint_analysis_unapproved_member')
        original=inbox.record_path(record['id'])/'content'
        if Path(record['name']).suffix.lower()=='.xlsx':
            if 'source_error' in payload:
                if set(payload) != {'id','sha256','analysis_id','source_error','task_provenance','batch_review'}:
                    raise ValueError('joint_source_error_invalid')
                try:
                    book=review_worker.native_book(original)
                    chunks=review_worker.batches(book)
                    if not chunks or len(chunks)>200:
                        raise ValueError('xlsx_review_scope_exceeds_200_batches')
                except ValueError as exc:
                    if str(exc)[:120] != payload['source_error']:
                        raise ValueError('joint_source_error_changed') from exc
                else:
                    raise ValueError('joint_source_error_not_reproduced')
                allowed[record['id']]=set()
                continue
            book=review_worker.native_book(original)
            scope=payload.get('review_scope')
            if scope:
                actual={**review_worker.digest_scope(book,review_worker.digest_book(book,budget=budget,compact=True)),
                        'excerpt_budget':budget}
                if scope != actual or payload['candidates']:
                    raise ValueError('sampled_review_scope_required_no_publication')
                allowed[record['id']]={sheet+'!'+cell for sheet,cell in actual['reviewed_locators']}
            else:
                if sum(len(sheet['cells']) for sheet in book.sheets)>300:
                    raise ValueError('sampled_review_scope_required_no_publication')
                locations=set()
                for index,sheet in enumerate(book.sheets,1):
                    for address,cell in sheet['cells'].items():
                        if cell['value'] in (None,''): continue
                        a,b=review_worker.context(sheet,address)
                        locations.add(f'xlsx:sheet:{index}:cell:{address}:context:{a}:{b}')
                        locations.add(sheet['name']+'!'+address)
                allowed[record['id']]=locations
            if any(finding.get('sheet','')+'!'+finding.get('cell','') not in allowed[record['id']]
                   for finding in payload['findings']):
                raise ValueError('joint_analysis_finding_outside_source')
        else:
            if 'source_error' in payload: raise ValueError('unexpected_source_error')
            _,allowed[record['id']]=review_worker._batch_document_packet(record,original,budget)
            if payload['candidates'] or any(finding.get('locator') not in allowed[record['id']]
                                           for finding in payload['findings']):
                raise ValueError('joint_analysis_finding_outside_source')
    for relation in joint['relationships']:
        if (not isinstance(relation,dict) or set(relation) !=
                {'source_id','source_locator','target_id','target_locator','kind','description'}
                or relation.get('source_id') not in allowed or relation.get('target_id') not in allowed
                or relation['source_id']==relation['target_id']
                or relation['source_locator'] not in allowed[relation['source_id']]
                or relation['target_locator'] not in allowed[relation['target_id']]
                or relation.get('kind') not in ('revision','support','conflict','duplicate')
                or not isinstance(relation.get('description'),str) or len(relation['description'])>700):
            raise ValueError('joint_analysis_relationship_outside_source')
    return expected


def complete_staged(root, payload):
    """Freeze all contexts once, then keep per-original publication and crash recovery."""
    from inresearch.delivery import source_publication
    from inresearch.materials import review_context, task_analysis
    from inresearch.workflow import research_tasks
    if not isinstance(payload,dict) or set(payload) != {'batch_id','items'}:
        raise ValueError('joint_analysis_commit_required')
    manifest=load_review(payload['batch_id'])
    if manifest['state'] != 'approved': raise PermissionError('joint_analysis_unapproved_batch')
    if not isinstance(payload['items'],list) or not 2 <= len(payload['items']) <= 20:
        raise ValueError('joint_analysis_commit_required')
    payloads=[task_analysis.read_staged(row) for row in payload['items']]
    input_sha=source_publication.digest(payloads)
    path=inbox.root()/'.review-batch-results'/manifest['id']/(input_sha+'.json')
    with locked(research_tasks.ledger_path(root)):
        _validate_joint(payloads,manifest)
        checkpoint=json.loads(path.read_text()) if path.exists() else None
        runtime=source_publication.state(root)
        if checkpoint is None:
            contexts={row['id']:review_context.provenance(review_context.current(root,inbox.load(row['id']),runtime=runtime)[0])
                      for row in payloads}
            if any(row.get('task_provenance') != contexts[row['id']] for row in payloads):
                raise inbox.Conflict('analysis_task_context_changed_retry_with_current_task')
            checkpoint={'input_sha256':input_sha,'contexts':contexts,
                        'source_sha256':source_publication.digest(runtime),
                        'baseline_sites':list(runtime['sites']),
                        'baseline_receipts':list(runtime['receipts']),
                        'baseline_observations':{key:[row['id'] for row in value['observations']]
                                                 for key,value in runtime['sites'].items()},'results':{}}
            inbox.atomic(path,checkpoint)
        normalized=_without_batch_publications(root,runtime,payloads,checkpoint)
        if source_publication.digest(normalized) != checkpoint['source_sha256']:
            raise inbox.Conflict('analysis_site_context_changed_retry_with_current_task')
        task_records=inbox.records()
        ids={row['id']:row['analysis_id'] for row in payloads}
        for record in task_records:
            if record['id'] in ids:
                record['analysis_reports']=[row for row in record.get('analysis_reports',[])
                                            if row['id'] != ids[record['id']]]
        for row in payloads:
            task,_=review_context.current(root,inbox.load(row['id']),runtime=normalized,task_records=task_records)
            if review_context.provenance(task) != checkpoint['contexts'][row['id']]:
                raise inbox.Conflict('analysis_task_context_changed_retry_with_current_task')
        results=[]
        for row in payloads:
            live=source_publication.state(root)
            if source_publication.digest(_without_batch_publications(root,live,payloads,checkpoint)) != checkpoint['source_sha256']:
                raise inbox.Conflict('analysis_site_context_changed_retry_with_current_task')
            if 'source_error' in row:
                result=_finish_source_error(row)
            else:
                result=task_analysis._complete_with_task_lock(root,row,expected_task=checkpoint['contexts'][row['id']],
                    expected_source_sha=source_publication.digest(live))
            checkpoint['results'][row['id']]=result
            inbox.atomic(path,checkpoint)
            results.append(result)
        manifest=load_review(payload['batch_id'])
        manifest.update(analysis_complete=True,analysis_input_sha256=input_sha)
        inbox.atomic(batch_path('review',manifest['id']),manifest)
        return results



def _finish_source_error(payload):
    """Keep a bad attachment terminal without blocking readable batch siblings."""
    from inresearch.delivery import source_publication
    from inresearch.materials import review_worker
    record=inbox.worker_record(payload['id'])
    input_sha=source_publication.digest(payload)
    prior=next((row for row in inbox.load(record['id']).get('analysis_reports',[])
                if row['id']==payload['analysis_id']),None)
    if prior:
        if prior['report'].get('input_sha256') != input_sha:
            raise inbox.Conflict('analysis replay changed')
        return {'report':prior['report'],'item':inbox.owner_view(inbox.load(record['id']))}
    report={'summary':'原件无法安全解析，未调用模型审阅其内容；请重新导出。',
            'model':None,'published':[],'held':[],'findings':[],
            'publication':{'state':'source_error','new_records':0},
            'source_sha256':record['sha256'],'input_sha256':input_sha,
            'task_provenance':payload['task_provenance'],'batch_review':payload['batch_review']}
    task=review_worker._unreviewable_feedback(record,review_worker.UnreviewableSource(payload['source_error']))
    inbox.finish_analysis(record['id'],record['sha256'],payload['analysis_id'],report,task)
    return {'report':report,'item':inbox.owner_view(inbox.load(record['id']))}
