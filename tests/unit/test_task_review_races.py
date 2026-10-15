"""Publication compare-and-swap and worker retry gates for approved tasks."""
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid
from unittest.mock import patch
from urllib.error import HTTPError

from inresearch.delivery import source_publication
from inresearch.materials import inbox, review_context, review_worker, task_analysis
from inresearch.paths import project_root
from inresearch.storage.files import write_json
from inresearch.storage.layout import workspace_path
from tests.unit.test_xlsx_document import workbook_bytes


class TaskReviewRaceTests(unittest.TestCase):
    def test_worker_recognizes_task_and_site_context_rejection(self):
        for reason in ('analysis_task_context_changed_retry_with_current_task',
                       'analysis_site_context_changed_retry_with_current_task'):
            error=HTTPError('https://example.invalid',409,'stale',{},
                            io.BytesIO(json.dumps({'error':reason}).encode()))
            self.assertTrue(review_worker._stale_context_response(error))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'repo'
        (self.root/'data').mkdir(parents=True)
        (self.root/'framework').mkdir()
        for name in ('storage_contract.json','research_publication.json','research_task_plan.json'):
            shutil.copyfile(project_root()/'framework'/name,self.root/'framework'/name)
        write_json(self.root/'data/projects.json',{'records':[]})
        write_json(self.root/'data/companies.json',{'records':[]})
        env=patch.dict(os.environ,{'INRESEARCH_RUNTIME_ROOT':str(Path(self.temp.name)/'runtime'),
            'INRESEARCH_INTAKE_ROOT':str(Path(self.temp.name)/'intake'),
            'INRESEARCH_MATERIAL_APPROVER':'owner'})
        env.start();self.addCleanup(env.stop)

    def test_source_publication_rejects_changed_runtime_under_lock(self):
        original=source_publication.state(self.root)
        expected=source_publication.digest(original)
        changed={**original,'receipts':{'other-worker':{'state':'published'}}}
        path=workspace_path(source_publication.PATH,self.root)
        path.parent.mkdir(parents=True,exist_ok=True)
        write_json(path,changed)
        payload={'version':1,'sites':[],'objects':{},'records':[]}
        with self.assertRaisesRegex(ValueError,'source_publication_context_changed'):
            source_publication.install(self.root,payload,expected_state_sha=expected)
        self.assertEqual(source_publication.state(self.root),changed)

    def test_analysis_rejects_task_hash_from_previous_system_state(self):
        raw=workbook_bytes()
        item,_=inbox.receive(io.BytesIO(raw),len(raw),
            {'name':'研究.xlsx','submitter':'甲','project_name':'园区普查',
             'package_id':'dc-census-cn'},'anonymous',public=True)
        inbox.mutate({'id':item['id'],'sha256':item['sha256'],'expected_revision':0,
            'operation_id':str(uuid.uuid4()),'action':'approve_and_analyze'},'owner','admin')
        inbox.acknowledge(item['id'],item['sha256'])
        record=inbox.worker_record(item['id'])
        task,_=review_context.current(self.root,record)
        stale={**review_context.provenance(task),'sha256':'0'*64}
        payload={'id':item['id'],'sha256':item['sha256'],'analysis_id':str(uuid.uuid4()),
            'summary':'测试','findings':[],'candidates':[],
            'model':{'backend':'codex_cli','requested':'gpt-6.1-sol','actual':None,
                     'executor':'codex-cli','identity_source':'explicit_cli_request_not_provider_reported',
                     'prompt_sha256':'a'*64,'input_sha256':'b'*64},
            'task_provenance':stale}
        with self.assertRaisesRegex(inbox.Conflict,'analysis_task_context_changed'):
            task_analysis.complete(self.root,payload)
        self.assertEqual(inbox.load(item['id']).get('analysis_reports'),None)
        self.assertEqual(source_publication.state(self.root),source_publication.empty())

    def test_worker_archives_stale_delivery_and_next_run_refreshes_task(self):
        archive=Path(self.temp.name)/'spark'
        key='a'*32;sha='b'*64
        folder=archive/key;folder.mkdir(parents=True)
        (folder/'original').write_bytes(b'approved original')
        revision=[1]
        submitted=[]
        def item():
            return {'id':key,'sha256':sha,'name':'作业.xlsx','status':'archived',
                    'approval':{'by':'owner','at':1,'sha256':sha},
                    'assigned_task':{'task_revision':revision[0],
                                     'mission_goal':'核对园区缺口'}}
        def request(endpoint,payload=None):
            if endpoint=='analysis-pending':
                return io.BytesIO(json.dumps({'items':[item()]}).encode())
            if endpoint=='analysis' and revision[0]==1:
                raise HTTPError('https://example.invalid',409,'stale',{},
                                io.BytesIO(b'{"error":"analysis_task_context_changed_retry_with_current_task"}'))
            if endpoint=='analysis':
                submitted.append(payload['analysis_id'])
                return io.BytesIO(b'{"ok":true,"report":{"published":[]}}')
            raise AssertionError(endpoint)
        ids=[]
        def proposed(row,original,progress,on_progress=None):
            ident=review_worker.analysis_identity(row,row['assigned_task'])
            ids.append(ident)
            return {'id':key,'sha256':sha,'analysis_id':ident}
        with patch('inresearch.materials.review_worker.proposal',side_effect=proposed):
            self.assertEqual(review_worker.run(archive,request),0)
            self.assertFalse((folder/'analysis-proposal.json').exists())
            self.assertEqual(len(list(folder.glob('analysis-proposal.json.stale-*'))),1)
            revision[0]=2
            self.assertEqual(review_worker.run(archive,request),1)
        self.assertNotEqual(ids[0],ids[1])
        self.assertEqual(submitted,[ids[1]])


if __name__=='__main__':unittest.main()
