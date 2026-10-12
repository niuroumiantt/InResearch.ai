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
