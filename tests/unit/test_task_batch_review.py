"""Exact-member batch authorization, joint inference and durable per-source recovery."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid
from unittest.mock import patch

from inresearch.adapters import models
from inresearch.delivery import source_publication
from inresearch.materials import batch_review, inbox, review_context, review_worker, task_analysis
from inresearch.paths import project_root
from tests.unit.test_xlsx_document import workbook_bytes
from tests.unit.test_task_analysis import SHEET


MODEL={'backend':'codex_cli','requested':'gpt-6.1-sol','actual':None,
       'executor':'codex-cli','identity_source':'explicit_cli_request_not_provider_reported',
       'prompt_sha256':'a'*64,'input_sha256':'b'*64}


class BatchReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'repo';(self.root/'data').mkdir(parents=True)
        (self.root/'framework').mkdir()
        for name in ('storage_contract.json','research_publication.json','research_task_plan.json'):
            shutil.copyfile(project_root()/'framework'/name,self.root/'framework'/name)
        (self.root/'data/projects.json').write_text('{"records":[]}')
        (self.root/'data/companies.json').write_text('{"records":[]}')
        self.archive=Path(self.temp.name)/'archive';self.archive.mkdir()
        env=patch.dict(os.environ,{'INRESEARCH_RUNTIME_ROOT':str(Path(self.temp.name)/'runtime'),
            'INRESEARCH_INTAKE_ROOT':str(Path(self.temp.name)/'intake'),'INRESEARCH_MATERIAL_APPROVER':'owner'})
        env.start();self.addCleanup(env.stop)
        self.batch_id=str(uuid.uuid4());self.receipts=[]

    def upload(self, raw='园区证据'.encode(), name='evidence.txt', *, index=0, total=2, package='dc-census-cn', token=None):
        item,token=inbox.receive(io.BytesIO(raw),len(raw),{'name':name,'submitter':'员工甲',
            'project_name':'本轮补证','package_id':package,'batch_id':self.batch_id,
            'batch_total':total,'batch_index':index,**({'batch_token':token} if token else {})},'anonymous',public=True)
        self.receipts.append({'id':item['id'],'receipt':token})
        folder=self.archive/item['id'];folder.mkdir();(folder/'original').write_bytes(raw)
        return item

    def seal(self):
        return batch_review.seal({'batch_id':self.batch_id,'items':self.receipts})

    def approval(self,items):
        return {'operation_id':str(uuid.uuid4()),'action':'approve_and_analyze','note':'核对整批原件',
                'items':[{'id':item['id'],'sha256':item['sha256'],'expected_revision':item['revision']} for item in items]}

    def approve(self,items):
        self.seal();request=self.approval(items)
        batch_review.approve(request,'owner','admin')
        for item in items: inbox.acknowledge(item['id'],item['sha256'])
        result=[]
        for item in items:
            row=inbox.worker_record(item['id'])
            row['assigned_task'],row['known_sites']=review_context.current(self.root,row)
            result.append(row)
        return result

    def model_output(self,items,*,candidates=False):
        outputs=[]
        for item in items:
            xlsx=item['name'].endswith('.xlsx')
            outputs.append({'id':item['id'],'sha256':item['sha256'],'summary':'按当前任务补齐来源',
                'findings':[],'candidates':([self.candidate(item)] if candidates and xlsx else [])})
        return {'summary':'两件相互参照，分别保留来源','relationships':[],'files':outputs,'_model':MODEL}

    def candidate(self,item):
        from inresearch.adapters.xlsx_document import Workbook
        book=review_worker.native_book(inbox.record_path(item['id'])/'content')
        value=lambda cell:book.sheets[0]['cells'][cell]['value']
        loc=lambda cell:f'xlsx:sheet:1:cell:{cell}:context:A1:D1'
        return {'site_id':'','site_name':value('A1'),'name_locator':loc('A1'),
            'location':value('B1'),'location_locator':loc('B1'),'field':'capacity_planned_it_mw',
            'value':10,'unit':'MW','unit_locator':'','locator':loc('C1')}

    def propose(self,items,*,candidates=False,result=None):
        class Client:
            calls=0
            def generate(client,system,prompt,**kwargs):
                client.calls+=1;client.prompt=json.loads(prompt)
                return result or self.model_output(items,candidates=candidates)
        client=Client()
        with patch.object(review_worker,'local_client',return_value=client):
            payloads=review_worker.batch_proposal(items,self.archive,self.archive/'progress.json')
        return payloads,client

    def stage(self,payloads):
        commits=[]
        for payload in payloads:
            raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
            parts=[raw[start:start+3000] for start in range(0,len(raw),3000)]
            for index,part in enumerate(parts):
                task_analysis.stage_part({'id':payload['id'],'sha256':payload['sha256'],
                    'analysis_id':payload['analysis_id'],'index':index,'total':len(parts),
                    'data':base64.b64encode(part).decode()})
            commits.append({'id':payload['id'],'sha256':payload['sha256'],'analysis_id':payload['analysis_id'],
                'total':len(parts),'payload_sha256':hashlib.sha256(raw).hexdigest()})
        return {'batch_id':payloads[0]['batch_review']['id'],'items':commits}

    def projection(self,root,params):
        row=next((row for row in source_publication.projects(root)['records'] if row['site_id']==params['site']),None)
        return {'detail':{'observations':row['observations']} if row else None}

    def test_partial_upload_seal_exact_receipts_and_late_upload_rejected(self):
        a=self.upload(index=0,total=3);b=self.upload(index=1,total=3)
        with self.assertRaises(inbox.Conflict):
            batch_review.seal({'batch_id':self.batch_id,'items':self.receipts[:1]})
        bad=[{**row,'receipt':'wrong'} for row in self.receipts]
        with self.assertRaises(PermissionError):batch_review.seal({'batch_id':self.batch_id,'items':bad})
        state=self.seal();self.assertEqual((state['expected'],state['received'],state['sealed']),(3,2,True))
        self.assertEqual(self.seal(),state)
        self.assertNotIn('member_ids',inbox.receipt_view(a['id'],self.receipts[0]['receipt'])['upload_batch'])
        with self.assertRaises(inbox.Conflict):self.upload(index=2,total=3)

    def test_batch_index_metadata_unsealed_and_permission_gates(self):
        a=self.upload()
        with self.assertRaises(inbox.Conflict):self.upload()
        with self.assertRaises(inbox.Conflict):self.upload(index=1,package='dc-census-na')
        b=self.upload(index=1)
        request=self.approval([a,b])
        with self.assertRaises(inbox.Conflict):batch_review.approve(request,'owner','admin')
        self.seal()
        with self.assertRaises(PermissionError):batch_review.approve(request,'other-admin','admin')
        self.assertTrue(all(row['status']=='pending_approval' for row in inbox.records()))

    def test_approval_checks_all_bytes_before_granting_any_permission(self):
        a=self.upload();b=self.upload(index=1);self.seal()
        (inbox.record_path(b['id'])/'content').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'原件内容已变化'):
            batch_review.approve(self.approval([a,b]),'owner','admin')
        self.assertEqual(inbox.pending(),[])
        self.assertTrue(all(not row.get('approval') for row in inbox.records()))

    def test_prepared_approval_is_inert_and_exact_replay_recovers(self):
        a=self.upload();b=self.upload(index=1);self.seal();request=self.approval([a,b])
        original=inbox.atomic;writes=0
        def crash(path,value):
            nonlocal writes
            if Path(path).name=='record.json':
                writes+=1
                if writes==2:raise OSError('simulated interruption')
            return original(path,value)
        with patch.object(inbox,'atomic',side_effect=crash):
            with self.assertRaises(OSError):batch_review.approve(request,'owner','admin')
        self.assertEqual(inbox.pending(),[])
        result=batch_review.approve(request,'owner','admin')
        self.assertEqual(len(result['items']),2)
        self.assertEqual(batch_review.approve(request,'owner','admin')['batch'],result['batch'])
        inbox.acknowledge(a['id'],a['sha256']);self.assertEqual(inbox.analysis_pending(),[])
        inbox.acknowledge(b['id'],b['sha256']);self.assertEqual(len(inbox.analysis_pending()),2)
        with self.assertRaises(inbox.Conflict):batch_review.approve({**request,'note':'changed'},'owner','admin')

    def test_joint_prompt_one_current_anchor_and_no_personal_history(self):
        a=self.upload('表格来源\\n待补链接'.encode());b=self.upload('说明版本\\n支持表格'.encode(),index=1)
        items=self.approve([a,b]);result=self.model_output(items)
        for item in items:
            item['assigned_task']={**item['assigned_task'],
                'previous_system_task':{'task':'PRIVATE OLD '+item['id']},'continuity':'verified_receipt'}
        result['relationships']=[{'source_id':a['id'],'source_locator':'line:1',
            'target_id':b['id'],'target_locator':'line:1','kind':'support','description':'说明补充原始来源'}]
        payloads,client=self.propose(items,result=result)
        self.assertEqual(client.calls,1);self.assertIn('task',client.prompt)
        self.assertNotIn('PRIVATE OLD',json.dumps(client.prompt))
        self.assertNotIn('previous_system_task',json.dumps(client.prompt))
        self.assertNotIn('assigned_task',client.prompt['files'][0])
        self.assertEqual(len(payloads),2)
        results=batch_review.complete_staged(self.root,self.stage(payloads))
        self.assertEqual(len(results),2)
        self.assertEqual(results[0]['report']['batch_review']['relationships'],result['relationships'])
        self.assertEqual(inbox.analysis_pending(),[])

    def test_cross_file_locator_and_sha_substitution_rejected_before_any_report(self):
        a=self.upload(b'only line');b=self.upload(b'first\nsecond',index=1)
        items=self.approve([a,b]);result=self.model_output(items)
        result['files'][0]['findings']=[{'sheet':'','cell':'','locator':'line:2','priority':'P0',
            'issue':'问题','action':'补证','acceptance':'可定位'}]
        with self.assertRaisesRegex(ValueError,'batch_finding_source_invalid'):
            self.propose(items,result=result)
        (self.archive/'model-output.json').unlink()
        payloads,_=self.propose(items)
        payloads[0]['sha256']=payloads[1]['sha256']
        with self.assertRaises(ValueError):batch_review.complete_staged(self.root,self.stage(payloads))
        self.assertTrue(all(not row.get('analysis_reports') for row in inbox.records()))

    def test_server_rejects_relationship_locator_outside_actual_source(self):
        a=self.upload();b=self.upload(index=1);items=self.approve([a,b])
        payloads,_=self.propose(items)
        relation={'source_id':a['id'],'source_locator':'line:999','target_id':b['id'],
                  'target_locator':'line:1','kind':'support','description':'forged locator'}
        for payload in payloads:payload['batch_review']['relationships']=[relation]
        with self.assertRaisesRegex(ValueError,'relationship_outside_source'):
            batch_review.complete_staged(self.root,self.stage(payloads))
        self.assertTrue(all(not row.get('analysis_reports') for row in inbox.records()))

    def xlsx_items(self):
        a=self.upload(workbook_bytes(sheet=SHEET),name='first.xlsx')
        second=SHEET.replace('测试园区甲','测试园区乙').replace('河北省张家口市','河北省承德市')
        b=self.upload(workbook_bytes(sheet=second),name='second.xlsx',index=1)
        return self.approve([a,b])

    def test_joint_native_publication_does_not_invalidate_later_member(self):
        items=self.xlsx_items();payloads,client=self.propose(items,candidates=True)
        commit=self.stage(payloads)
        with patch('inresearch.knowledge.industry.cached_snapshot',side_effect=self.projection):
            results=batch_review.complete_staged(self.root,commit)
            replay=batch_review.complete_staged(self.root,commit)
        self.assertEqual(client.calls,1)
        self.assertEqual([len(row['report']['published']) for row in results],[1,1])
        self.assertEqual(len(source_publication.projects(self.root)['records']),2)
        self.assertEqual([row['report'] for row in replay],[row['report'] for row in results])
        self.assertTrue(all(len(inbox.load(item['id'])['analysis_reports'])==1 for item in items))
        self.assertTrue(all(len(inbox.load(item['id'])['feedback'])==1 for item in items))

    def test_partial_report_write_recovers_without_new_inference(self):
        items=self.xlsx_items();payloads,client=self.propose(items,candidates=True);commit=self.stage(payloads)
        original=inbox.finish_analysis;crashed=False
        def crash(*args,**kwargs):
            nonlocal crashed
            result=original(*args,**kwargs)
            if not crashed:
                crashed=True;raise OSError('simulated lost write response')
            return result
        with patch('inresearch.knowledge.industry.cached_snapshot',side_effect=self.projection):
            with patch.object(inbox,'finish_analysis',side_effect=crash):
                with self.assertRaises(OSError):batch_review.complete_staged(self.root,commit)
            results=batch_review.complete_staged(self.root,commit)
        self.assertEqual(client.calls,1);self.assertEqual(len(results),2)
        self.assertEqual(len(source_publication.projects(self.root)['records']),2)
        self.assertTrue(all(len(inbox.load(item['id'])['analysis_reports'])==1 for item in items))
        self.assertTrue(all(len(inbox.load(item['id'])['feedback'])==1 for item in items))

    def test_partial_commit_rejects_external_state_change(self):
        items=self.xlsx_items();payloads,_=self.propose(items,candidates=True);commit=self.stage(payloads)
        original=inbox.finish_analysis
        def crash(*args,**kwargs):original(*args,**kwargs);raise OSError('interrupted')
        with patch('inresearch.knowledge.industry.cached_snapshot',side_effect=self.projection):
            with patch.object(inbox,'finish_analysis',side_effect=crash):
                with self.assertRaises(OSError):batch_review.complete_staged(self.root,commit)
        state=source_publication.state(self.root);state['receipts']['external']={'state':'published'}
        from inresearch.storage.layout import workspace_path
        inbox.atomic(workspace_path(source_publication.PATH,self.root),state)
        with self.assertRaisesRegex(inbox.Conflict,'analysis_site_context_changed'):
            batch_review.complete_staged(self.root,commit)
        self.assertEqual(sum(bool(inbox.load(item['id']).get('analysis_reports')) for item in items),1)

    def test_bad_workbook_isolated_from_readable_sibling(self):
        a=self.upload(b'invalid xlsx',name='broken.xlsx');b=self.upload(index=1)
        items=self.approve([a,b]);payloads,client=self.propose(items)
        self.assertEqual(client.calls,1);self.assertIn('source_error',payloads[0])
        results=batch_review.complete_staged(self.root,self.stage(payloads))
        self.assertEqual(len(results),2)
        self.assertEqual(inbox.load(a['id'])['analysis_progress']['state'],'source_error')
        self.assertEqual(inbox.load(b['id'])['analysis_state'],'completed')
        self.assertEqual(inbox.analysis_pending(),[])
        from inresearch.workflow import research_tasks
        package=next(row for row in research_tasks.read(self.root)['packages'] if row['id']=='dc-census-cn')
        shared=research_tasks.package_workflow(package,inbox.records())
        self.assertEqual(shared['current_task']['completed']['feedback_rounds'],1)
        self.assertEqual(shared['current_task']['completed']['reviewed_rounds'],1)
        self.assertIsNotNone(shared['current_task']['feedback_at'])
        self.assertIn('未读内容',shared['current_task']['feedback_summary'])

    def test_all_bad_workbooks_skip_model(self):
        a=self.upload(b'broken',name='broken.xlsx');b=self.upload(b'broken2',name='broken2.xlsx',index=1)
        items=self.approve([a,b])
        with patch.object(review_worker,'local_client',side_effect=AssertionError('must not infer')):
            payloads=review_worker.batch_proposal(items,self.archive,self.archive/'progress.json')
        results=batch_review.complete_staged(self.root,self.stage(payloads))
        self.assertTrue(all(row['report']['model'] is None for row in results))

    def test_truncated_joint_inference_preserves_retry_without_serial_fallback(self):
        items=self.approve([self.upload(),self.upload(index=1)])
        class Client:
            calls=0
            def generate(client,*args,**kwargs):
                client.calls+=1;raise models.InferenceError('model_output_truncated')
        client=Client()
        def request(endpoint,payload=None):
            if endpoint=='analysis-progress':return io.BytesIO(b'{"ok":true}')
            raise AssertionError(endpoint)
        with patch.object(review_worker,'local_client',return_value=client):
            self.assertEqual(review_worker._run_batch(items,self.archive,request),0)
            self.assertEqual(review_worker._run_batch(items,self.archive,request),0)
        self.assertEqual(client.calls,1)
        self.assertFalse((self.archive/'.review-batches'/items[0]['review_batch_id']/'proposal.json').exists())


    def test_lost_upload_response_restored_with_private_token_and_replay_same_bytes(self):
        token=str(uuid.uuid4());a=self.upload(token=token)
        recovered=batch_review.recover_upload({'batch_id':self.batch_id,'batch_token':token})
        self.assertEqual(recovered['items'][0]['id'],a['id'])
        self.assertEqual(recovered['items'][0]['receipt'],self.receipts[0]['receipt'])
        self.assertNotIn('batch_token_hash',inbox.receipt_view(a['id'],self.receipts[0]['receipt']))
        raw='园区证据'.encode()
        same,receipt=inbox.receive(io.BytesIO(raw),len(raw),{'name':'evidence.txt','submitter':'员工甲',
            'project_name':'本轮补证','package_id':'dc-census-cn','batch_id':self.batch_id,
            'batch_total':2,'batch_index':0,'batch_token':token},'anonymous',public=True)
        self.assertEqual(same['id'],a['id']);self.assertEqual(receipt,self.receipts[0]['receipt'])
        self.assertEqual(len(inbox.records()),1)
        with self.assertRaises(PermissionError):
            batch_review.recover_upload({'batch_id':self.batch_id,'batch_token':str(uuid.uuid4())})
        self.assertEqual(batch_review.recover_upload({'batch_id':str(uuid.uuid4()),'batch_token':token}),
                         {'items':[],'batch':None})

    def test_record_to_upload_manifest_interruption_recovers_by_batch_token(self):
        token=str(uuid.uuid4());original=inbox.atomic
        def crash(path,state):
            if Path(path).parent.name=='.upload-batches' and state['items']:
                raise OSError('manifest interrupted after record committed')
            return original(path,state)
        with patch.object(inbox,'atomic',side_effect=crash):
            with self.assertRaises(OSError):self.upload(token=token)
        self.assertEqual(len(inbox.records()),1)
        recovered=batch_review.recover_upload({'batch_id':self.batch_id,'batch_token':token})
        self.assertEqual(recovered['batch']['received'],1)
        self.assertEqual(inbox.receipt_view(recovered['items'][0]['id'],recovered['items'][0]['receipt'])['status'],
                         'pending_approval')
        batch_review.seal({'batch_id':self.batch_id,'items':[
            {key:recovered['items'][0][key] for key in ('id','receipt')}]})

    def test_joint_members_cannot_submit_old_single_worker_results(self):
        items=self.approve([self.upload(),self.upload(index=1)])
        payloads,_=self.propose(items)
        payload={key:value for key,value in payloads[0].items() if key != 'batch_review'}
        with self.assertRaisesRegex(ValueError,'joint_analysis_requires_batch_commit'):
            task_analysis.complete(self.root,payload)
        self.assertFalse(inbox.load(items[0]['id']).get('analysis_reports'))

    def test_invalid_model_output_is_durable_and_not_regenerated(self):
        items=self.approve([self.upload(),self.upload(index=1)])
        output=self.model_output(items);output['files'][0]['sha256']='0'*64
        class Client:
            calls=0
            def generate(client,*args,**kwargs):client.calls+=1;return output
        client=Client()
        with patch.object(review_worker,'local_client',return_value=client):
            for _ in range(2):
                with self.assertRaisesRegex(ValueError,'batch_model_source_invalid'):
                    review_worker.batch_proposal(items,self.archive,self.archive/'progress.json')
        self.assertEqual(client.calls,1)
        self.assertTrue((self.archive/'model-output.json').exists())

    def test_pending_response_preserves_entire_batch_at_nominal_limit(self):
        singles=[{'id':str(index)} for index in range(25)]
        batch=[{'id':'batch-'+str(index),'review_batch_id':'joint'} for index in range(20)]
        with patch.object(inbox,'analysis_pending',return_value=singles+batch):
            selected=inbox.bounded_analysis_pending(40)
        self.assertEqual(len(selected),45)
        self.assertEqual({row['id'] for row in selected if row.get('review_batch_id')},
                         {row['id'] for row in batch})

    def test_prepared_recovery_request_visible_only_to_owner(self):
        a=self.upload();b=self.upload(index=1);self.seal();request=self.approval([a,b])
        original=inbox.atomic
        def crash(path,state):
            if Path(path).name=='record.json':
                original(path,state);raise OSError('interrupted')
            return original(path,state)
        with patch.object(inbox,'atomic',side_effect=crash):
            with self.assertRaises(OSError):batch_review.approve(request,'owner','admin')
        partial=next(row for row in inbox.records() if row.get('review_batch_id'))
        self.assertEqual(inbox.owner_view(partial)['review_batch_recovery'],request)
        self.assertNotIn('review_batch_recovery',inbox.public_view(partial))
        batch_review.approve(inbox.owner_view(partial)['review_batch_recovery'],'owner','admin')
        self.assertEqual(len(inbox.pending()),2)

    def test_rejected_member_excluded_explicitly_but_pending_omission_refused(self):
        a=self.upload(index=0,total=3);b=self.upload(index=1,total=3);c=self.upload(index=2,total=3);self.seal()
        request=self.approval([a,b])
        with self.assertRaises(inbox.Conflict):batch_review.approve(request,'owner','admin')
        inbox.mutate({'id':c['id'],'sha256':c['sha256'],'expected_revision':0,
            'operation_id':str(uuid.uuid4()),'action':'reject','note':'不属于这次补证'},'owner','admin')
        result=batch_review.approve(request,'owner','admin')
        manifest=batch_review.load_review(result['batch']['id'])
        self.assertEqual(manifest['excluded'][0]['id'],c['id'])
        self.assertEqual(inbox.load(c['id'])['status'],'rejected')

    def test_new_batch_requires_seal_and_multifile_single_analysis_refused(self):
        a=self.upload();b=self.upload(index=1)
        request={'id':a['id'],'sha256':a['sha256'],'expected_revision':0,
                 'operation_id':str(uuid.uuid4()),'action':'approve_and_analyze'}
        with self.assertRaisesRegex(inbox.Conflict,'封存'):inbox.mutate(request,'owner','admin')
        self.seal()
        with self.assertRaisesRegex(inbox.Conflict,'整批确认'):inbox.mutate(request,'owner','admin')
        inbox.mutate({'id':b['id'],'sha256':b['sha256'],'expected_revision':0,
            'operation_id':str(uuid.uuid4()),'action':'reject','note':'不适合材料'},'owner','admin')
        accepted=inbox.mutate(request,'owner','admin')
        self.assertEqual(accepted['status'],'approved')
        self.assertEqual(inbox.load(a['id'])['batch_excluded'][0]['id'],b['id'])

    def test_batch_rejects_different_packages_even_with_same_upload_id(self):
        a=self.upload();b=self.upload(index=1);self.seal()
        record=inbox.load(b['id']);record['package_id']='dc-census-na'
        inbox.atomic(inbox.record_path(b['id'])/'record.json',record)
        with self.assertRaisesRegex(ValueError,'同一工作包'):
            batch_review.approve(self.approval([a,b]),'owner','admin')
        self.assertTrue(all(not row.get('approval') for row in inbox.records()))

    def test_large_workbook_scope_recomputed_per_file_and_no_candidates(self):
        rows=''.join(f'<row r="{index}"><c r="A{index}" t="inlineStr"><is><t>园区记录{index}</t></is></c></row>'
                     for index in range(1,330))
        sheet='<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+rows+'</sheetData></worksheet>'
        a=self.upload(workbook_bytes(sheet=sheet),name='large.xlsx')
        b=self.upload(index=1);items=self.approve([a,b]);payloads,client=self.propose(items)
        self.assertEqual(client.calls,1)
        self.assertEqual(payloads[0]['review_scope']['total_nonblank_cells'],329)
        self.assertLess(payloads[0]['review_scope']['excerpted_cells'],329)
        self.assertEqual(payloads[0]['candidates'],[])
        import copy
        forged=copy.deepcopy(payloads);forged[0]['analysis_id']=str(uuid.uuid4())
        forged[0]['review_scope']['excerpted_cells']+=1
        with self.assertRaisesRegex(ValueError,'sampled_review_scope_required'):
            batch_review.complete_staged(self.root,self.stage(forged))
        results=batch_review.complete_staged(self.root,self.stage(payloads))
        self.assertEqual(results[0]['item']['analysis_state'],'sampled_incomplete')
        self.assertEqual(results[0]['report']['review_scope'],payloads[0]['review_scope'])

    def test_lost_batch_ack_reuses_persisted_joint_proposal(self):
        items=self.approve([self.upload(),self.upload(index=1)])
        output=self.model_output(items)
        class Client:
            calls=0
            def generate(client,*args,**kwargs):client.calls+=1;return output
        client=Client();lost=True
        def response(value):return io.BytesIO(json.dumps(value).encode())
        def request(endpoint,payload=None):
            nonlocal lost
            if endpoint=='analysis-progress':return response({'ok':True})
            if endpoint=='analysis-part':task_analysis.stage_part(payload);return response({'ok':True})
            if endpoint=='analysis-batch-commit':
                results=batch_review.complete_staged(self.root,payload)
                if lost:lost=False;raise OSError('response lost after complete')
                return response({'ok':True,'results':results})
            raise AssertionError(endpoint)
        with patch.object(review_worker,'local_client',return_value=client):
            with self.assertRaises(OSError):review_worker._run_batch(items,self.archive,request)
            self.assertEqual(review_worker._run_batch(items,self.archive,request),2)
        self.assertEqual(client.calls,1)
        self.assertTrue(all(len(inbox.load(item['id'])['analysis_reports'])==1 for item in items))
        self.assertTrue(all(len(inbox.load(item['id'])['feedback'])==1 for item in items))


    def test_one_joint_correction_then_operator_terminal_and_changed_task_new_attempt(self):
        items=self.approve([self.upload(),self.upload(index=1)])
        invalid=self.model_output(items);invalid['files'][0]['sha256']='0'*64
        valid=self.model_output(items)
        class Client:
            calls=0
            def generate(client,*args,**kwargs):
                client.calls+=1
                return invalid if client.calls<=2 else valid
        client=Client()
        def response(value):return io.BytesIO(json.dumps(value).encode())
        def request(endpoint,payload=None):
            if endpoint=='analysis-progress':
                inbox.set_analysis_progress(payload['id'],payload['sha256'],payload['completed'],
                    payload['total'],payload['state'],error_code=payload.get('error_code'))
                return response({'ok':True})
            if endpoint=='analysis-part':task_analysis.stage_part(payload);return response({'ok':True})
            if endpoint=='analysis-batch-commit':return response({'ok':True,'results':[]})
            raise AssertionError(endpoint)
        with patch.object(review_worker,'local_client',return_value=client):
            with patch.object(review_worker.time,'time',return_value=1000):
                self.assertEqual(review_worker._run_batch(items,self.archive,request),0)
            with patch.object(review_worker.time,'time',return_value=2801):
                self.assertEqual(review_worker._run_batch(items,self.archive,request),0)
            self.assertEqual(client.calls,2)
            for _ in range(3):self.assertEqual(review_worker._run_batch(items,self.archive,request),0)
            self.assertEqual(client.calls,2)
            self.assertTrue(all(inbox.load(item['id'])['analysis_progress']['error_code']==
                                'joint_model_output_invalid_requires_operator' for item in items))
            raw=self.archive/'.review-batches'/items[0]['review_batch_id']/'model-output.json'
            self.assertEqual(json.loads(raw.read_text())['corrections'],1)
            self.assertEqual(len(list(raw.parent.glob('model-output.json.stale-*'))),1)
            for item in items:item['assigned_task']={**item['assigned_task'],'task_revision':999}
            review_worker._run_batch(items,self.archive,request)
            self.assertEqual(client.calls,3)
            self.assertGreaterEqual(len(list(raw.parent.glob('model-output.json.stale-*'))),2)

    def test_progress_only_persists_whitelisted_operator_code(self):
        items=self.approve([self.upload(),self.upload(index=1)])
        item=items[0]
        row=inbox.set_analysis_progress(item['id'],item['sha256'],0,1,'blocked',error_code='untrusted_other_code')
        self.assertNotIn('error_code',row['analysis_progress'])
        row=inbox.set_analysis_progress(item['id'],item['sha256'],0,1,'blocked',
            error_code='joint_model_output_invalid_requires_operator')
        self.assertEqual(row['analysis_progress']['error_code'],'joint_model_output_invalid_requires_operator')
        row=inbox.set_analysis_progress(item['id'],item['sha256'],0,1,'running')
        self.assertNotIn('error_code',row['analysis_progress'])

    def test_new_attempt_preserves_already_registered_baseline_observations(self):
        items=self.xlsx_items();payloads,_=self.propose(items,candidates=True)
        with patch('inresearch.knowledge.industry.cached_snapshot',side_effect=self.projection):
            batch_review.complete_staged(self.root,self.stage(payloads))
            for item in items:
                item['assigned_task'],item['known_sites']=review_context.current(self.root,inbox.load(item['id']))
            new,_=self.propose(items,candidates=True)
            result=batch_review.complete_staged(self.root,self.stage(new))
        self.assertEqual(len(result),2)
        self.assertEqual(len(source_publication.projects(self.root)['records']),2)
        self.assertTrue(all(len(inbox.load(item['id'])['analysis_reports'])==2 for item in items))


    def test_batch_approval_rechecks_current_package_before_permission(self):
        a=self.upload();b=self.upload(index=1);self.seal();request=self.approval([a,b])
        with self.assertRaisesRegex(ValueError,'工作包已失效'):
            batch_review.approve(request,'owner','admin',valid_package_ids={'dc-census-na'})
        self.assertTrue(all(not row.get('approval') for row in inbox.records()))
        result=batch_review.approve(request,'owner','admin',valid_package_ids={'dc-census-cn'})
        self.assertEqual(len(result['items']),2)


if __name__=='__main__':unittest.main()
