import io
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch
from inresearch.materials import inbox as m

class IntakeTests(unittest.TestCase):
    def test_complete_duplicate_and_ack(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'INRESEARCH_INTAKE_ROOT':d}):
            a=m.receive(io.BytesIO(b'hello'),5,{'name':'../../报告.txt','topic':'泰国'},'tester')
            b=m.receive(io.BytesIO(b'hello'),5,{'name':'报告.txt'},'tester')
            self.assertNotEqual(a['id'],b['id'])
            self.assertEqual(a['sha256'],b['sha256'])
            self.assertEqual(a['name'],'报告.txt')
            with self.assertRaises(ValueError):m.acknowledge(a['id'],'wrong')
            with self.assertRaises(PermissionError):m.acknowledge(a['id'],a['sha256'])
            self.assertEqual(m.pending(),[])
            a=m.mutate({'id':a['id'],'sha256':a['sha256'],'expected_revision':0,
                'operation_id':str(uuid.uuid4()),'action':'approve'},'admin','admin')
            self.assertEqual(len(m.pending()),1)
            self.assertEqual(m.acknowledge(a['id'],a['sha256'])['status'],'archived')
            self.assertEqual(m.load(b['id'])['status'],'pending_approval')
    def test_public_receipt_owner_and_feedback_gate(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'INRESEARCH_INTAKE_ROOT':d,'INRESEARCH_MATERIAL_APPROVER':'owner'}):
            a,token=m.receive(io.BytesIO(b'raw'),3,
                {'name':'test.xlsx','submitter':'employee','project_name':'project'},'anonymous',public=True)
            self.assertNotIn('receipt_hash',a)
            self.assertEqual(m.receipt_view(a['id'],token)['id'],a['id'])
            with self.assertRaises(PermissionError):m.receipt_view(a['id'],'wrong')
            self.assertEqual(m.snapshot('some-user','member')['items'],[])
            self.assertEqual(m.snapshot('anonymous','member')['items'],[])
            base={'id':a['id'],'sha256':a['sha256'],'expected_revision':0,'operation_id':str(uuid.uuid4())}
            with self.assertRaises(PermissionError):m.mutate({**base,'action':'feedback','result':'revision_required','text':'fix'},'analysis-worker','worker',worker=True)
            with self.assertRaises(PermissionError):m.mutate({**base,'action':'approve'},'other-admin','admin')
            approved=m.mutate({**base,'action':'approve'},'owner','admin')
            self.assertEqual(approved['status'],'approved')
            self.assertNotIn('receipt_hash',m.pending()[0])
            with self.assertRaises(m.Conflict):m.mutate({**base,'operation_id':str(uuid.uuid4()),'action':'reject','note':'x'},'owner','admin')
            feedback=m.mutate({'id':a['id'],'sha256':a['sha256'],'expected_revision':1,
                'operation_id':str(uuid.uuid4()),'action':'feedback','result':'revision_required','text':'补齐来源'},'analysis-worker','worker',worker=True)
            self.assertEqual(feedback['feedback'][0]['text'],'补齐来源')
            self.assertEqual(m.receipt_view(a['id'],token)['feedback'][0]['result'],'revision_required')
    def test_public_submission_requires_name_and_project(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'INRESEARCH_INTAKE_ROOT':d}):
            with self.assertRaisesRegex(ValueError,'姓名和项目名称'):
                m.receive(io.BytesIO(b'x'),1,{'name':'a.txt','submitter':'员工甲'},'anonymous',public=True)
            self.assertEqual(m.records(),[])
    def test_unreviewable_original_ends_queue_after_visible_repair_task(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {
                'INRESEARCH_INTAKE_ROOT':d,'INRESEARCH_MATERIAL_APPROVER':'owner'}):
            item,receipt=m.receive(io.BytesIO(b'bad xlsx'),8,
                {'name':'bad.xlsx','submitter':'员工甲','project_name':'园区普查'},
                'anonymous',public=True)
            m.mutate({'id':item['id'],'sha256':item['sha256'],'expected_revision':0,
                'operation_id':str(uuid.uuid4()),'action':'approve_and_analyze'},'owner','admin')
            m.acknowledge(item['id'],item['sha256'])
            self.assertEqual(len(m.analysis_pending()),1)
            with self.assertRaisesRegex(ValueError,'先登记可见'):
                m.set_analysis_progress(item['id'],item['sha256'],0,0,'source_error')
            current=m.load(item['id'])
            m.mutate({'id':item['id'],'sha256':item['sha256'],
                'expected_revision':current['revision'],'operation_id':str(uuid.uuid4()),
                'action':'feedback','result':'revision_required','text':'重新导出有效工作簿'},
                'analysis-worker','worker',worker=True)
            m.set_analysis_progress(item['id'],item['sha256'],0,0,'source_error')
            self.assertEqual(m.analysis_pending(),[])
            self.assertEqual(m.receipt_view(item['id'],receipt)['analysis_progress']['state'],'source_error')
            self.assertEqual(m.receipt_view(item['id'],receipt)['feedback'][0]['text'],'重新导出有效工作簿')
            with self.assertRaises(m.Conflict):
                m.set_analysis_progress(item['id'],item['sha256'],0,1,'running')
    def test_previous_system_task_requires_verified_receipt_chain(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'INRESEARCH_INTAKE_ROOT':d,'INRESEARCH_MATERIAL_APPROVER':'owner'}):
            first,token=m.receive(io.BytesIO(b'raw'),3,
                {'name':'first.md','submitter':'员工甲','project_name':'项目甲'},'anonymous',public=True)
            m.mutate({'id':first['id'],'sha256':first['sha256'],'expected_revision':0,
                'operation_id':str(uuid.uuid4()),'action':'approve_and_analyze'},'owner','admin')
            m.acknowledge(first['id'],first['sha256'])
            m.finish_analysis(first['id'],first['sha256'],str(uuid.uuid4()),
                {'published':[],'held':[],'findings':[]},'系统给出的下一版任务')
            linked,_=m.receive(io.BytesIO(b'new'),3,
                {'name':'next.md','submitter':'员工甲','project_name':'项目甲',
                 'continuation_id':first['id'],'continuation_receipt':token},'anonymous',public=True)
            self.assertEqual(m.previous_system_task(linked)['task'],'系统给出的下一版任务')
            same_name,_=m.receive(io.BytesIO(b'new'),3,
                {'name':'unlinked.md','submitter':'员工甲','project_name':'项目甲'},'anonymous',public=True)
            self.assertIsNone(m.previous_system_task(same_name))
            with self.assertRaisesRegex(ValueError,'姓名和项目一致'):
                m.receive(io.BytesIO(b'new'),3,{'name':'stolen.md','submitter':'员工乙',
                    'project_name':'项目甲','continuation_id':first['id'],'continuation_receipt':token},
                    'anonymous',public=True)
            with self.assertRaises(PermissionError):
                m.receive(io.BytesIO(b'new'),3,{'name':'forged.md','submitter':'员工甲',
                    'project_name':'项目甲','continuation_id':first['id'],'continuation_receipt':'wrong'},
                    'anonymous',public=True)
    def test_partial_not_visible(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'INRESEARCH_INTAKE_ROOT':d}):
            with self.assertRaises(ValueError):m.receive(io.BytesIO(b'x'),5,{},'tester')
            self.assertEqual(m.records(),[])
            with self.assertRaises(ValueError):m.record_path('../escape')
            with self.assertRaises(ValueError):m.receive(io.BytesIO(),m.MAX_BYTES+1,{},'tester')
    def test_legacy_archive_and_changed_bytes_never_enter_worker(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'INRESEARCH_INTAKE_ROOT':d}):
            old=m.receive(io.BytesIO(b'old'),3,{'name':'legacy.txt'},'tester')
            path=m.record_path(old['id'])/'record.json'
            record=m.load(old['id']);record['status']='archived';m.atomic(path,record)
            self.assertEqual(m.pending(),[])
            with self.assertRaises(PermissionError):m.worker_record(old['id'])
            new=m.receive(io.BytesIO(b'new'),3,{'name':'changed.txt'},'tester')
            operation={'id':new['id'],'sha256':new['sha256'],'expected_revision':0,
                'operation_id':str(uuid.uuid4()),'action':'approve'}
            first=m.mutate(operation,'admin','admin')
            self.assertEqual(m.mutate(operation,'admin','admin')['revision'],first['revision'])
            (m.record_path(new['id'])/'content').write_bytes(b'bad')
            with self.assertRaises(ValueError):m.worker_record(new['id'])
if __name__=='__main__':unittest.main()
