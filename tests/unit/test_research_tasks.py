"""Project work packages persist, conflict safely and never certify adoption."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from inresearch.paths import project_root
from inresearch.workflow import research_tasks as tasks


class ResearchTaskTests(unittest.TestCase):
    def setUp(self):
        self.root = project_root()
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT': self.temp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def request(self, **changes):
        result = {'operation_id': str(uuid.uuid4()), 'expected_revision': 0,
                  'action': 'update', 'package_id': 'dc-census-na',
                  'assignee': 'alice', 'machine': 'm4', 'model': '实际模型版本',
                  'status': 'in_progress', 'note': '先核运营商园区表'}
        result.update(changes)
        return result

    def test_seed_is_real_unassigned_plan_and_read_does_not_write(self):
        state = tasks.read(self.root)
        self.assertEqual(state['revision'], 0)
        self.assertEqual(len(state['packages']), 6)
        self.assertTrue(all(p['status'] == 'unassigned' and not p['assignee']
                            and not p['delivery_pointer'] for p in state['packages']))
        self.assertFalse(tasks.ledger_path(self.root).exists())
        self.assertIn('待校准', tasks.plan(self.root)['mission']['scale_note'])

    def test_site_progress_counts_actual_published_unique_sites_against_admin_target(self):
        request={'action':'set_target','expected_revision':0,'operation_id':str(uuid.uuid4()),
                 'target_site_count':250,'target_site_basis':'按去重的运营商地点清单初步盘点'}
        with self.assertRaises(tasks.Forbidden):
            tasks.mutate(self.root,request,'editor','member')
        tasks.mutate(self.root,request,'owner','admin')
        self.assertEqual(tasks.read(self.root)['target_site_count'],250)
        self.assertEqual(tasks.read(self.root)['target_site_basis'],request['target_site_basis'])
        projection={'capacity_audit':{'sites':9},'basis':'map','coverage':{},'rows':[
            {'site_id':'site-a','portfolio':False},{'site_id':'site-b','portfolio':False},
            {'site_id':'site-portfolio','portfolio':True}]}
        records=[{'analysis_reports':[{'report':{'published':[
            {'site_id':'site-a','field':'name','statement_id':'s1'},
            {'site_id':'site-a','field':'notes','statement_id':'s2'},
            {'site_id':'site-b','field':'name','statement_id':'s3'},
            {'site_id':'site-portfolio','field':'name','statement_id':'s4'},
            {'site_id':'removed-site','field':'name','statement_id':'s5'}]}}]},
            {'analysis_reports':[{'report':{'published':[
            {'site_id':'site-a','field':'name','statement_id':'s1'}]}}]}]
        with patch('inresearch.knowledge.industry.cached_snapshot',return_value=projection), \
             patch('inresearch.materials.inbox.records',return_value=records):
            public=tasks.snapshot(self.root,role='reader')
        self.assertEqual(public['site_progress']['published_sites'],2)
        self.assertEqual(public['site_progress']['target'],250)
        self.assertEqual(public['site_progress']['target_basis'],request['target_site_basis'])
        self.assertTrue(public['site_progress']['target_set_at'])
        self.assertEqual(public['site_progress']['reviewed_reports'],2)
        self.assertEqual(public['site_progress']['published_statements'],5)
        self.assertNotIn('analysis_reports',public)

    def test_target_remains_unset_until_research_basis_is_entered(self):
        projection={'capacity_audit':{'sites':0},'basis':'map','coverage':{},'rows':[]}
        with patch('inresearch.knowledge.industry.cached_snapshot',return_value=projection), \
             patch('inresearch.materials.inbox.records',return_value=[]):
            public=tasks.snapshot(self.root,role='reader')
        self.assertIsNone(public['site_progress']['target'])
        self.assertEqual(public['site_progress']['published_sites'],0)
        self.assertEqual(public['site_progress']['published_statements'],0)
        self.assertEqual(public['site_progress']['reviewed_reports'],0)
        missing_basis={'action':'set_target','expected_revision':0,'operation_id':str(uuid.uuid4()),
                       'target_site_count':250}
        with self.assertRaises(ValueError):
            tasks.mutate(self.root,missing_basis,'owner','admin')
        self.assertFalse(tasks.ledger_path(self.root).exists())

    def test_package_handoff_uses_approved_reports_without_leaking_private_feedback(self):
        package=next(p for p in tasks.plan(self.root)['packages'] if p['id']=='dc-census-cn')
        approved={'id':'approved-file','package_id':package['id'],'status':'archived',
                  'sha256':'approved-sha','approval':{'by':'owner','at':110,'sha256':'approved-sha'},
                  'created':100,'submitter':'甲','name':'private-company-name.xlsx',
                  'analysis_reports':[{'at':200,'report':{
                      'published':[{'site_id':'cn-a','statement_id':'source-a'}],
                      'held':[{'reason':'PRIVATE HELD REASON'}],
                      'findings':[{'issue':'PRIVATE CELL FINDING'}]},
                      'employee_task':'PRIVATE RECEIPT-ONLY TASK'}]}
        unapproved={'id':'unapproved-file','package_id':package['id'],'status':'pending_approval',
                    'sha256':'unapproved-sha','created':300,'submitter':'乙',
                    'name':'secret.pdf','analysis_reports':[]}
        other={**approved,'id':'other-package','package_id':'dc-census-na','submitter':'丙'}
        result=tasks.package_workflow(package,[approved,unapproved,other],{'cn-a'})
        self.assertEqual((result['published_sites'],result['published_statements']),(1,1))
        self.assertEqual((result['reviewed_files'],result['confirmed_files']),(1,1))
        self.assertEqual(result['current_task']['version'],2)
        self.assertEqual((result['events'][0]['received_at'],result['events'][0]['reviewed_at']),(100,200))
        self.assertEqual(result['events'][0]['submitter'],'甲')
        self.assertIn('其他未上线 1 条',result['events'][0]['feedback'])
        self.assertIn('先补未上线条目的园区身份',result['current_task']['next_action'])
        public=json.dumps(result,ensure_ascii=False)
        for private in ('PRIVATE','private-company-name','unapproved-file','secret.pdf','乙','丙'):
            self.assertNotIn(private,public)
        newer={**approved,'id':'newer-upload','created':150,'submitter':'乙',
               'analysis_reports':[{'at':190,'report':{'published':[], 'held':[], 'findings':[]}}]}
        ordered=tasks.package_workflow(package,[approved,newer],{'cn-a'})['events']
        self.assertEqual([(event['submitter'],event['received_at']) for event in ordered],
                         [('乙',150),('甲',100)])

    def test_shared_task_version_advances_for_scope_or_completed_review(self):
        package=next(p for p in tasks.plan(self.root)['packages'] if p['id']=='dc-census-cn')
        base=tasks.read(self.root)
        self.assertEqual(tasks.package_workflow(package,[])['current_task']['version'],1)
        status={'package_id':package['id'],'before':{**package},'after':{**package,'status':'ready'},
                'at':'2026-10-15T10:00:00+00:00'}
        scope={'package_id':package['id'],'before':{**package},'after':{**package,'scope':'补来源'},
               'at':'2026-10-15T11:00:00+00:00'}
        base['operations']=[status,scope]
        edits=tasks.package_task_edits(base,package['id'])
        self.assertEqual(len(edits),1)
        self.assertEqual(tasks.package_workflow(package,[],task_edits=edits)['current_task']['version'],2)

    def test_durable_update_replay_and_audit(self):
        request = self.request()
        result = tasks.mutate(self.root, request, 'editor', 'member')
        self.assertEqual(result['revision'], 1)
        # A second independent read observes the persisted owner and machine.
        state = tasks.read(self.root)
        first = state['packages'][0]
        self.assertEqual((first['assignee'], first['machine']), ('alice', 'm4'))
        self.assertEqual(state['operations'][0]['before']['status'], 'unassigned')
        self.assertEqual(state['operations'][0]['after']['status'], 'in_progress')
        self.assertTrue(tasks.mutate(self.root, request, 'editor', 'member')['replayed'])
        self.assertEqual(tasks.read(self.root)['revision'], 1)
        with self.assertRaises(tasks.Conflict):
            tasks.mutate(self.root, {**request, 'note': 'different'}, 'editor', 'member')
        with self.assertRaises(tasks.Conflict):
            tasks.mutate(self.root, request, 'other-editor', 'member')

    def test_concurrent_edit_has_one_winner(self):
        requests = [self.request(assignee=name) for name in ('alice', 'bob')]
        def save(request):
            try:
                tasks.mutate(self.root, request, 'editor', 'admin')
                return 'saved'
            except tasks.Conflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(save, requests)), ['saved', 'conflict'])
        self.assertEqual(tasks.read(self.root)['revision'], 1)

    def test_intern_can_only_update_own_status_delivery_and_note(self):
        tasks.mutate(self.root, self.request(), 'editor', 'member')
        own = self.request(expected_revision=1, status='delivered',
                           delivery_pointer='private/delivery-a/receipt.json')
        for key in ('assignee', 'machine', 'model'):
            own.pop(key)
        with self.assertRaises(tasks.Forbidden):
            tasks.mutate(self.root, own, 'bob', 'intern')
        with self.assertRaises(tasks.Forbidden):
            tasks.mutate(self.root, {**own, 'assignee': 'bob'}, 'alice', 'intern')
        tasks.mutate(self.root, own, 'alice', 'intern')
        self.assertEqual(tasks.read(self.root)['packages'][0]['status'], 'delivered')
        self.assertEqual(tasks.read(self.root)['packages'][0]['assignee'], 'alice')
        with self.assertRaises(tasks.Forbidden):
            tasks.mutate(self.root, self.request(action='create'), 'alice', 'intern')
        with self.assertRaises(tasks.Forbidden):
            tasks.mutate(self.root, self.request(), 'reader', 'reader')

    def test_multiple_assigned_members_share_one_package_without_name_based_upload_identity(self):
        tasks.mutate(self.root, self.request(assignee='alice, bob、carol'), 'editor', 'member')
        self.assertEqual(tasks.assigned_members(tasks.read(self.root)['packages'][0]['assignee']),
                         {'alice','bob','carol'})
        update = self.request(expected_revision=1,status='delivered',
                              delivery_pointer='private/shared/receipt.json')
        for key in ('assignee','machine','model'):
            update.pop(key)
        with self.assertRaises(tasks.Forbidden):
            tasks.mutate(self.root,update,'dave','intern')
        tasks.mutate(self.root,update,'bob','intern')
        self.assertEqual(tasks.read(self.root)['packages'][0]['status'],'delivered')

    def test_delivery_requires_pointer_and_does_not_allow_adoption_status(self):
        for changes in ({'status': 'delivered'}, {'status': 'adopted'},
                        {'status': 'blocked', 'note': ''}, {'due': '2026-02-30'},
                        {'adopted_gw': 90}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                tasks.mutate(self.root, self.request(**changes), 'editor', 'member')
        self.assertFalse(tasks.ledger_path(self.root).exists())

    def test_create_new_package_without_inventing_owner(self):
        result = tasks.mutate(self.root, self.request(action='create', title='补城市级位置',
            region='欧洲', scope='核对官方地点与园区地址', sources='运营商地点页',
            assignee='', machine='', model='', status='unassigned'), 'editor', 'member')
        package = tasks.read(self.root)['packages'][-1]
        self.assertEqual(package['id'], result['package_id'])
        self.assertEqual(package['assignee'], '')
        self.assertEqual(len(tasks.read(self.root)['packages']), 7)

    def test_snapshot_reuses_map_projection_without_exposing_audit(self):
        tasks.mutate(self.root, self.request(), 'editor', 'member')
        projection = {'capacity_audit': {'sites': 9, 'operating': 150},
                      'basis': 'existing map basis', 'coverage': {'label': '非全球普查'}}
        with patch('inresearch.knowledge.industry.snapshot', return_value=projection) as source:
            view = tasks.snapshot(self.root, 'alice', 'intern')
        source.assert_called_once_with(self.root, {'overview': '1'})
        self.assertEqual(view['map_register']['counts'], projection['capacity_audit'])
        self.assertEqual(view['map_register']['publication_ack'], 'not_checked')
        self.assertNotIn('operations', view)
        self.assertFalse(view['can_create'])

    def test_public_task_projection_excludes_actual_people_execution_and_delivery(self):
        tasks.mutate(self.root, self.request(assignee='secret-owner', machine='secret-host',
            model='secret-model', note='secret-note', delivery_pointer='private/secret-receipt.json'), 'editor', 'member')
        path = tasks.ledger_path(self.root)
        state = json.loads(path.read_text())
        state['internal_runtime_note'] = 'secret-top-level'
        path.write_text(json.dumps(state))
        projection = {'capacity_audit': {'sites': 9, 'operating': 150},
                      'basis': 'existing map basis', 'coverage': {'label': '非全球普查'}}
        with patch('inresearch.knowledge.industry.snapshot', return_value=projection):
            view = tasks.snapshot(self.root, 'must-not-be-echoed', 'reader')
        self.assertTrue(view['public_view'])
        self.assertEqual(view['actor'], '')
        self.assertEqual(set(view['packages'][0]), {'id', 'title', 'region', 'scope', 'sources', 'status'})
        self.assertEqual(view['packages'][0]['status'], 'in_progress')
        self.assertNotIn('secret-', json.dumps(view))
        self.assertNotIn('internal_runtime_note', view)

    def test_corruption_is_never_overwritten(self):
        path = tasks.ledger_path(self.root)
        path.parent.mkdir(parents=True)
        path.write_text('{broken')
        with self.assertRaises(ValueError):
            tasks.mutate(self.root, self.request(), 'editor', 'admin')
        self.assertEqual(path.read_text(), '{broken')

    def test_malformed_json_shapes_fail_with_valueerror_without_overwrite(self):
        path = tasks.ledger_path(self.root)
        path.parent.mkdir(parents=True)
        for value in ([], None, {'version': 1, 'revision': 0, 'packages': [], 'operations': [None]},
                      {'version': 1, 'revision': 0, 'packages': [{'id': ['bad']}], 'operations': []}):
            text = json.dumps(value)
            path.write_text(text)
            with self.subTest(value=value), self.assertRaises(ValueError):
                tasks.mutate(self.root, self.request(), 'editor', 'admin')
            self.assertEqual(path.read_text(), text)


if __name__ == '__main__':
    unittest.main()
