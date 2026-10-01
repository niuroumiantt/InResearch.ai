"""派工按目标行 ID：/api/targets 在服务端按角色过滤（实习生只见自己的行），assign 与 register_delivery 只写派工文件。"""
import http.client
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from inresearch.interfaces import auth, http as serve
from inresearch.storage.files import write_json
from inresearch.workflow import commands, dispatch

ROOT = Path(__file__).resolve().parents[2]


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inresearch-dispatch-')
        self.root = Path(self.temp.name)
        (self.root / 'framework').mkdir()
        for rel in ('framework/tco_targets.json', 'framework/bom.json', 'framework/research_questions.json', 'framework/modules.json'):
            shutil.copy(ROOT / rel, self.root / rel)
        (self.root / 'data').mkdir()
        write_json(self.root / 'data/research_knowledge.json', json.loads((ROOT / 'data/research_knowledge.json').read_text(encoding='utf-8')))
        write_json(self.root / 'data/assignments.json', {'version': '1.0', 'records': []})
        write_json(self.root / 'web/routes.json', {})
        self.first = dispatch.target_doc(self.root)['targets'][0]['id']

    def tearDown(self):
        self.temp.cleanup()

    def test_assign_by_target_id_and_intern_limits(self):
        self.assertEqual(commands.assign(self.root, {'target_id': self.first, 'assignee': 'ann', 'status': '已派'}, by='boss', role='admin')['ok'], True)
        rec = dispatch.assignments(self.root)['records'][0]
        self.assertEqual((rec['target_id'], rec['assignee'], rec['status']), (self.first, 'ann', '已派'))
        with self.assertRaisesRegex(commands.Rejected, '不在当前目标表'):
            commands.assign(self.root, {'target_id': 'P.nope.spec', 'assignee': 'ann'}, by='boss', role='admin')
        with self.assertRaises(commands.Rejected):  # interns only update their own rows
            commands.assign(self.root, {'target_id': self.first, 'status': '进行中'}, by='bob', role='intern')
        self.assertTrue(commands.assign(self.root, {'target_id': self.first, 'status': '进行中'}, by='ann', role='intern')['ok'])

    def test_register_delivery_is_a_runtime_pointer_not_a_git_carrier(self):
        commands.assign(self.root, {'target_id': self.first, 'assignee': 'ann'}, by='boss', role='admin')
        out = dispatch.register_delivery(self.root, {'target_id': self.first, 'evidence_path': 'docs/inbox/x.pdf', 'note': 'first'}, by='ann', role='intern')
        self.assertIn('Git 内载体', out['msg'])
        rec = dispatch.assignments(self.root)['records'][0]
        self.assertEqual(rec['status'], '已交付')
        self.assertEqual(rec['delivery']['evidence_path'], 'docs/inbox/x.pdf')
        with self.assertRaisesRegex(dispatch.Rejected, '相对路径'):
            dispatch.register_delivery(self.root, {'target_id': self.first, 'evidence_path': '../secret'}, by='ann', role='admin')
        with self.assertRaises(dispatch.Rejected):
            dispatch.register_delivery(self.root, {'target_id': self.first, 'evidence_path': 'docs/y.pdf'}, by='bob', role='intern')
        # the target table itself is untouched: delivered status still needs a Git carrier
        row = next(t for t in dispatch.target_doc(self.root)['targets'] if t['id'] == self.first)
        self.assertNotEqual(row['status'], 'delivered')

    def test_targets_view_carries_event_cards_and_their_values(self):
        card = {'target_id': self.first, 'origin_pointer': 'https://www.micron.com/x', 'pointer_kind': 'url', 'delivered_at': '2026-10-01',
                'note': 'internal ids', 'parameters': [{'parameter_name': 'hbm.stack_capacity', 'value': '36GB'}]}
        write_json(self.root / 'data/event_cards.json', {'version': '1.0', 'records': [card]})
        rows = {r['id']: r for r in dispatch.targets_view(self.root, 'boss', 'admin')['targets']}
        self.assertEqual(rows[self.first]['cards'], [{k: card[k] for k in ('origin_pointer', 'pointer_kind', 'delivered_at', 'parameters')}])
        self.assertTrue(all(r['cards'] == [] for i, r in rows.items() if i != self.first))

    def test_targets_view_filters_by_role_and_node(self):
        commands.assign(self.root, {'target_id': 'P.transformer.price', 'assignee': 'ann'}, by='boss', role='admin')
        everything = dispatch.targets_view(self.root, 'boss', 'admin')
        self.assertEqual(len(everything['targets']), everything['total'])
        self.assertFalse(everything['mine'])
        mine = dispatch.targets_view(self.root, 'ann', 'intern')
        self.assertTrue(mine['mine'])
        self.assertEqual([t['id'] for t in mine['targets']], ['P.transformer.price'])
        self.assertEqual(dispatch.targets_view(self.root, 'bob', 'intern')['targets'], [])
        self.assertEqual([t['id'] for t in dispatch.targets_view(self.root, 'boss', 'member', {'mine': '1'})['targets']], [])
        node = dispatch.targets_view(self.root, 'boss', 'member', {'node': 'part:transformer', 'col': '4'})
        self.assertEqual([t['id'] for t in node['targets']], ['P.transformer.lead_time'])
        system = dispatch.targets_view(self.root, 'boss', 'member', {'node': 'system:it', 'col': '2'})
        self.assertTrue(system['targets'] and all(t['variable_class'] == 2 and t['part_id'] for t in system['targets']))
        self.assertTrue(all(t['node'].startswith('site:') for t in dispatch.targets_view(self.root, 'boss', 'member', {'node': 'site:grid'})['targets']))


class DispatchHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inresearch-dispatch-http-')
        self.root = Path(self.temp.name)
        (self.root / 'framework').mkdir(); (self.root / 'data').mkdir()
        for rel in ('framework/tco_targets.json', 'framework/bom.json', 'framework/research_questions.json', 'framework/modules.json'):
            shutil.copy(ROOT / rel, self.root / rel)
        write_json(self.root / 'data/research_knowledge.json', json.loads((ROOT / 'data/research_knowledge.json').read_text(encoding='utf-8')))
        write_json(self.root / 'data/assignments.json', {'version': '1.0', 'records': [{'target_id': 'P.gpu.spec', 'assignee': 'ann', 'status': '已派'}]})
        write_json(self.root / 'web/routes.json', {})
        self.patches = [patch.object(serve, 'ROOT', self.root), patch.object(serve, 'AUTH_ON', True)]
        for p in self.patches:
            p.start()
        self.server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=2)))

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp.cleanup()

    def call(self, method, path, body=None):
        con = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            con.request(method, path, json.dumps(body) if body is not None else None, {'Content-Type': 'application/json'})
            r = con.getresponse()
            body = r.read()
            try:
                return r.status, json.loads(body or b'{}')
            except ValueError:
                return r.status, {}
        finally:
            con.close()

    def test_targets_api_is_role_filtered_on_the_server(self):
        with patch.object(auth, 'session_user', return_value=None):
            self.assertEqual(self.call('GET', '/api/targets')[0], 401, 'targets and dispatch are not public')
        with patch.object(auth, 'session_user', return_value='boss'), patch.object(auth, 'user_role', return_value='member'):
            status, doc = self.call('GET', '/api/targets')
            self.assertEqual((status, doc['mine'], len(doc['targets'])), (200, False, doc['total']))
            status, doc = self.call('GET', '/api/targets?mine=1')
            self.assertEqual((status, doc['targets']), (200, []))
        with patch.object(auth, 'session_user', return_value='ann'), patch.object(auth, 'user_role', return_value='intern'):
            status, doc = self.call('GET', '/api/targets')
            self.assertEqual((status, doc['mine'], [t['id'] for t in doc['targets']]), (200, True, ['P.gpu.spec']))
            self.assertNotEqual(self.call('GET', '/supply.html')[0], 403, 'the acquisition page is the intern entry (not served from a temp root, but not forbidden)')
            status, out = self.call('POST', '/api/deliver', {'target_id': 'P.gpu.spec', 'evidence_path': 'docs/inbox/gpu.pdf'})
            self.assertEqual((status, out['ok']), (200, True))
            status, out = self.call('POST', '/api/deliver', {'target_id': 'P.cpu.spec', 'evidence_path': 'docs/inbox/cpu.pdf'})
            self.assertEqual(status, 403)
            status, headers_doc = self.call('GET', '/')
            self.assertEqual(status, 302)


if __name__ == '__main__':
    unittest.main()
