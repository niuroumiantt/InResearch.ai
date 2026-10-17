"""Independent readers retain results; relevant identity and owner changes invalidate."""
import copy
import json
import unittest
from unittest.mock import patch

from inresearch.materials import review_context as context, inbox, native_review_contract as contract, task_analysis
from inresearch.delivery import source_publication
from inresearch.workflow import research_tasks
from tests.unit import test_task_full_review as fixture
from tests.unit import test_full_review_worker as worker_fixture
from inresearch.materials import full_review_worker as worker


class ParallelContextTests(unittest.TestCase):
    def setUp(self):
        self.state = {'revision': 7, 'operations': [], 'packages': [
            {'id':'p','title':'园区','region':'CN','scope':'逐园区核验','sources':[]}]}
        self.record = {'id':'r','package_id':'p'}
        self.mission = {'title':'研究','goal':'核对原件'}
        self.rows = [{'site_id':'a','name':'园区甲','country':'CN','location':'河北省'},
                     {'site_id':'b','name':'园区乙','country':'CN','location':'贵州省'}]
        self.packet = {'package_id':'packet-a','cells':[{'value':'园区甲'}]}

    def task(self, rows=None, records=None):
        with patch.object(inbox, 'approver', return_value='owner'):
            descriptor = context.campus_descriptor(self.record,self.state,self.mission,
                self.rows if rows is None else rows, records or [])
        return context.campus_task(descriptor,self.packet)[0]

    def test_other_campus_publication_and_report_do_not_invalidate(self):
        before = self.task()
        self.rows[1]['notes'] = '独立园区的新事实'
        records = [{'id':'other','package_id':'p','analysis_reports':[{'id':'result'}],
                    'feedback':[{'id':'result','by':'owner','text':'自动回执'}]}]
        self.state['revision'] += 1
        self.assertEqual(before,self.task(records=records))

    def test_any_matching_record_change_invalidates(self):
        before=self.task()
        self.rows[0]['notes']='原上下文未展示的身份说明'
        self.assertNotEqual(before,self.task())

    def test_new_alias_parent_duplicate_and_inventory_tail_invalidate(self):
        before=self.task()
        rows=self.rows+[{'site_id':str(n),'name':'无关'+str(n)} for n in range(600)]
        self.assertEqual(before,self.task(rows))
        rows.append({'site_id':'z','name':'另一个名字','aliases':['园区甲'],
                     'duplicate_of':'a','identity_scope':'cluster'})
        self.assertNotEqual(before,self.task(rows))

    def test_owner_feedback_and_common_brief_still_invalidate(self):
        before=self.task()
        self.assertNotEqual(before,self.task(records=[{'id':'r','package_id':'p',
            'feedback':[{'id':'manual','by':'owner','text':'更正研究要求'}]}]))
        self.state['packages'][0]['scope']='新边界'
        self.assertNotEqual(before,self.task())


class ParallelReceiverTests(fixture.FullNativeReviewTests):
    # Reuse the real native workbook/inbox/publisher fixture, not a mocked receiver.
    def scoped_payload(self,packet=None,candidates=True):
        packet=packet or self.campus
        payload=self.payload(packet,candidates)
        record=inbox.load(self.item['id'])
        descriptor=context.campus_descriptor(record,research_tasks.read(self.root),
            research_tasks.plan(self.root)['mission'],source_publication.projects(self.root)['records'],inbox.records())
        task,_=context.campus_task(descriptor,packet)
        provenance=context.provenance(task)
        payload['task_provenance']=provenance
        attempt=record['full_analysis']['attempt_id']
        payload['analysis_id']=contract.analysis_id(attempt,packet['package_id'],provenance['sha256'])
        payload['review_scope']=contract.make_scope(self.manifest,packet,attempt,provenance['sha256'])
        return payload

    def test_precomputed_other_campus_survives_real_publication_and_progress(self):
        self.start()
        second=next(p for p in self.manifest['packets'] if p['campus_key']=='P-002')
        first=self.scoped_payload()
        concurrent=self.scoped_payload(second,False)
        # Projection dependencies are tested elsewhere; retain the real publisher.
        with patch('inresearch.knowledge.industry.cached_snapshot', side_effect=lambda *a, **k: {'detail': {'observations': [o for r in source_publication.projects(self.root)['records'] for o in r.get('observations',[])]}}):
            result=task_analysis.complete(self.root,first)
        self.assertTrue(result['report']['published'])
        inbox.mutate(self.request('continue_full_analysis',attempt_id=inbox.load(self.item['id'])['full_analysis']['attempt_id'],reason='首包验收通过'),'owner','admin')
        received=task_analysis.complete(self.root,concurrent)
        self.assertEqual(received['report']['task_provenance'],concurrent['task_provenance'])
        replay=task_analysis.complete(self.root,concurrent)
        self.assertEqual(received['report'],replay['report'])

    def test_relevant_new_identity_rejects_precomputed_result(self):
        self.start()
        payload=self.scoped_payload()
        original=source_publication.projects
        def changed(*a,**kw):
            result=copy.deepcopy(original(*a,**kw))
            result['records'].append({'site_id':'new-match','name':'测试园区甲','country':'CN'})
            return result
        with patch.object(source_publication,'projects',side_effect=changed):
            with self.assertRaisesRegex(inbox.Conflict,'analysis_task_context_changed'):
                task_analysis.complete(self.root,payload)


class ParallelWorkerTests(worker_fixture.FullReviewWorkerTests):
    def descriptor(self):
        return {'policy':context.CAMPUS_CONTEXT_POLICY,'task_revision':0,
                'mission_goal':'完整核对园区身份及来源','owner_feedback':[],
                'package':{'id':'dc-census-cn'},'identities':[]}

    def test_resume_reuses_success_after_unrelated_shared_progress_changes(self):
        self.item['campus_context']=self.descriptor()
        client=worker_fixture.FakeClient()
        worker.proposal(self.item,self.original,self.folder,client)
        first_call=copy.deepcopy(client.calls[0])
        self.item['assigned_task']['task_revision']+=1
        self.item['assigned_task']['source_state_sha256']='unrelated-publication'
        worker.proposal(self.item,self.original,self.folder,client)
        self.assertEqual(len(client.calls),2)
        self.assertEqual(first_call['task'],client.calls[1]['task'])
        self.assertNotEqual(first_call['native_fragments'],client.calls[1]['native_fragments'])

    def test_started_legacy_package_keeps_old_context_and_success(self):
        client=worker_fixture.FakeClient()
        worker.proposal(self.item,self.original,self.folder,client)
        first=copy.deepcopy(client.calls[0])
        self.item['campus_context']=self.descriptor()
        worker.proposal(self.item,self.original,self.folder,client)
        self.assertEqual(first['task'],client.calls[1]['task'])
        self.assertNotEqual(first['native_fragments'],client.calls[1]['native_fragments'])
