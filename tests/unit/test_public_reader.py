"""公开只读（reader）：白名单是默认拒绝的，账本的公开视图只有基准预设与校准锚，过滤在服务端。"""
import http.client
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from inresearch.interfaces import auth, http as serve, public
from inresearch.knowledge import economics

ROOT = Path(__file__).resolve().parents[2]


class PublicViewTests(unittest.TestCase):
    def test_allowed_is_a_whitelist(self):
        for path in ('/', '/index.html', '/node.html', '/ledger.html', '/bom.html', '/bom3d.html', '/rack3d.html', '/product-catalog.html',
                     '/report.html', '/data/dashboard.json', '/data/tco_targets.json', '/data/datacenter_model.json', '/api/whoami',
                     '/api/report', '/assets/datacenter-model.js', '/assets/models/x.glb', '/login'):
            self.assertTrue(public.allowed(path), path)
        for path in ('/supply.html', '/team.html', '/materials.html', '/nvidia-pilot.html', '/ops.html', '/company.html', '/doc.html',
                     '/research.html', '/admin/product/index.html', '/data/facts.json', '/data/users.json', '/framework/part_fetch.json',
                     '/framework/research_graph.json', '/api/tasks', '/api/supply', '/api/users', '/api/research', '/api/add-price',
                     '/reports/workorders.json', '/docs/DECISIONS.md'):
            self.assertFalse(public.allowed(path), path)

    def test_public_model_keeps_baseline_and_calibration_anchors_only(self):
        spec = json.loads((ROOT / 'data/datacenter_model.json').read_text(encoding='utf-8'))
        view = public.public_model(spec)
        anchors = {c['preset'] for c in spec['calibration'].values()}
        self.assertEqual(set(view['presets']), {'baseline'} | anchors)
        self.assertLess(len(view['presets']), len(spec['presets']), 'regional and scenario presets stay behind login')
        self.assertEqual(set(view['regions']), {spec['assumptions']['site']} | {p['changes'].get('site', spec['assumptions']['site']) for p in view['presets'].values()})
        self.assertEqual(view['public_view'], 'reader')
        for key in ('inputs', 'evidence', 'assumptions', 'calibration', 'groups'):
            self.assertEqual(view[key], spec[key], key)
        for preset in view['presets']:  # the anchors still reproduce on the public view
            self.assertEqual(economics.with_preset(view, preset), economics.with_preset(spec, preset), preset)
        self.assertEqual(economics.compute(economics.with_preset(view, 'baseline'), view)['roic'],
                         economics.compute(economics.with_preset(spec, 'baseline'), spec)['roic'])


class PublicReaderHTTPTests(unittest.TestCase):
    """Real server on the repository root with login required; the session is faked per role."""

    def setUp(self):
        self.server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=2)))
        self.auth_on = patch.object(serve, 'AUTH_ON', True)
        self.auth_on.start()
        self.addCleanup(self.auth_on.stop)

    def request(self, method, path, body=None):
        con = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            con.request(method, path, body, {'Content-Type': 'application/json'} if body else {})
            response = con.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            con.close()

    def test_anonymous_visitor_is_a_reader(self):
        with patch.object(auth, 'session_user', return_value=None):
            status, _, body = self.request('GET', '/api/whoami')
            self.assertEqual((status, json.loads(body)), (200, {'ok': True, 'user': None, 'role': 'reader'}))
            for path in ('/', '/node.html', '/ledger.html', '/bom.html', '/report.html', '/data/dashboard.json', '/data/tco_targets.json'):
                self.assertEqual(self.request('GET', path)[0], 200, path)
                self.assertEqual(self.request('HEAD', path)[0], 200, path)
            status, _, body = self.request('GET', '/data/datacenter_model.json')
            model = json.loads(body)
            self.assertEqual(status, 200)
            self.assertEqual(model['public_view'], 'reader')
            self.assertIn('baseline', model['presets'])
            self.assertNotIn('ai_texas_own', model['presets'])
            self.assertNotIn('us_texas', model['regions'])
            for path in ('/supply.html', '/team.html', '/ops.html', '/materials.html', '/company.html', '/data/facts.json', '/framework/part_fetch.json'):
                status, headers, _ = self.request('GET', path)
                self.assertEqual((status, headers.get('Location')), (302, '/login'), path)
            for path in ('/api/tasks', '/api/supply', '/api/users'):
                self.assertEqual(self.request('GET', path)[0], 401, path)
            for path in ('/api/add-price', '/api/supply', '/api/run', '/api/users', '/api/assign'):
                self.assertEqual(self.request('POST', path, b'{}')[0], 401, path)

    def test_member_sees_the_whole_model(self):
        with patch.object(auth, 'session_user', return_value='m'), patch.object(auth, 'user_role', return_value='member'):
            status, _, body = self.request('GET', '/api/whoami')
            self.assertEqual(json.loads(body)['role'], 'member')
            model = json.loads(self.request('GET', '/data/datacenter_model.json')[2])
            self.assertNotIn('public_view', model)
            self.assertIn('ai_texas_own', model['presets'])
            self.assertEqual(self.request('GET', '/supply.html')[0], 200)

    def test_intern_gets_public_content_and_the_public_ledger(self):
        with patch.object(auth, 'session_user', return_value='i'), patch.object(auth, 'user_role', return_value='intern'):
            status, headers, _ = self.request('GET', '/team.html')
            self.assertEqual((status, headers.get('Location')), (302, '/supply.html#tasks'), 'the team board merged into the acquisition page')
            self.assertEqual(self.request('GET', '/ledger.html')[0], 200, 'what the public can read, a logged-in intern can read')
            model = json.loads(self.request('GET', '/data/datacenter_model.json')[2])
            self.assertEqual(model['public_view'], 'reader')
            self.assertEqual(self.request('GET', '/supply.html')[0], 200, 'the acquisition page is the intern entry (own target rows)')
            self.assertEqual(self.request('GET', '/data/facts.json')[0], 403)
            self.assertEqual(self.request('GET', '/api/supply')[0], 403, 'the supply ledger stays members-only')
            status, headers, _ = self.request('GET', '/')
            self.assertEqual((status, headers.get('Location')), (302, '/supply.html#targets'))


if __name__ == '__main__':
    unittest.main()
