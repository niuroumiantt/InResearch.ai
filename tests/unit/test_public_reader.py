"""Homepage and task guide anonymous projections; all other role grants stay separate."""
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
        for path in ('/', '/index.html', '/api/whoami', '/login', '/healthz', '/robots.txt',
                     '/tasks.html', '/api/research-tasks', '/api/research-task-examples',
                     '/assets/research-tasks.js', '/assets/research-tasks.css',
                     '/api/research-task-examples/equinix-sg3-20261012/files/source-1',
                     '/assets/site-skin.js', '/assets/industry.js', '/assets/fonts/fonts.css',
                     '/assets/world.geo.json', '/assets/world-detail.geo.json', '/assets/map-admin1-11.geo.json',
                     '/api/industry?overview=1', '/api/news?overview=1'):
            self.assertTrue(public.allowed(path), path)
        for path in ('/industry.html', '/projects.html', '/node.html', '/ledger.html', '/bom.html', '/report.html',
                     '/supply.html', '/company.html', '/product-catalog.html', '/logout',
                     '/data/dashboard.json', '/data/datacenter_model.json', '/framework/bom.json',
                     '/api/industry', '/api/news', '/api/observations', '/api/report', '/api/product-catalog/nvidia',
                     '/assets/models/x.glb', '/assets/part-dossier.js', '/assets/technical-atlas/rack-atlas-v1.png',
                     '/api/news?overview=1&company=nvidia', '/api/industry?overview=1&site=secret',
                     '/api/industry?overview=1&overview=0', '/api/news?overview=', '/api/news?overview=0',
                     '/api/news?overview=1&export=', '/api/industry?overview=1&site='):
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

    def test_customer_model_preserves_every_registered_control_without_internal_demands(self):
        spec = json.loads((ROOT / 'data/datacenter_model.json').read_text())
        view = public.customer_model(spec)
        self.assertEqual(set(view['assumptions']), set(spec['assumptions']))
        self.assertEqual(set(view['inputs']), set(spec['inputs']))
        for key in ['permit_timing', 'it_depreciation_years', 'compute_debt_years', 'shell_debt_years', 'loss_tax_shield']:
            self.assertEqual(view['assumptions'][key], spec['assumptions'][key])
        self.assertNotIn('input_governance', view)
        self.assertFalse(any('fetch_what' in row for row in view['evidence'].values()))


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

    def request(self, method, path, body=None, headers=None):
        con = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            con.request(method, path, body, {**({'Content-Type': 'application/json'} if body else {}), **(headers or {})})
            response = con.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            con.close()

    def test_anonymous_homepage_works_but_every_other_page_requires_login(self):
        routes = json.loads((ROOT / 'web/routes.json').read_text())
        with patch.object(auth, 'session_user', return_value=None):
            status, _, body = self.request('GET', '/api/whoami')
            self.assertEqual((status, json.loads(body)), (200, {'ok': True, 'user': None, 'role': 'reader'}))
            for method in ('GET', 'HEAD'):
                for path in ('/', '/index.html', '/assets/industry.js', '/assets/fonts/fonts.css', '/healthz', '/api/industry?overview=1', '/api/news?overview=1'):
                    status, _, body = self.request(method, path)
                    self.assertEqual(status, 200, (method, path))
                    if method == 'HEAD': self.assertEqual(body, b'')
                for path, source in routes.items():
                    if not source.endswith('.html') or path in public.READER_PAGES: continue
                    status, headers, _ = self.request(method, path)
                    self.assertEqual((status, headers.get('Location')), (302, '/login'), (method, path))
                    self.assertEqual(headers.get('Cache-Control'), 'private, no-store', path)
            status, _, body = self.request('GET', '/robots.txt')
            self.assertEqual(status, 200)
            self.assertIn(b'Disallow: /', body)
            self.assertNotIn(b'Allow: /report.html', body)

    def test_session_dependent_public_mechanisms_are_never_shared_cached(self):
        for user in (None, 'member'):
            with patch.object(auth, 'session_user', return_value=user), patch.object(auth, 'user_role', return_value='member'):
                for method in ('GET', 'HEAD'):
                    for path in ('/api/whoami', '/login', '/login?from=tasks'):
                        status, headers, _ = self.request(method, path)
                        self.assertEqual(status, 302 if user and path.startswith('/login') else 200)
                        self.assertEqual(headers.get('Cache-Control'), 'private, no-store', (method, path, user))
                        self.assertEqual(headers.get('Vary'), 'Cookie', (method, path, user))
        with patch.object(auth, 'session_user', return_value=None), patch.object(auth, 'throttled', return_value=False), patch.object(auth, 'load_users', return_value={}):
            status, headers, _ = self.request('POST', '/api/login', b'{"username":"member","password":"test"}')
            self.assertEqual(status, 503)
            self.assertEqual(headers.get('Cache-Control'), 'private, no-store')
            self.assertEqual(headers.get('Vary'), 'Cookie')

    def test_private_files_apis_queries_and_encoded_aliases_cannot_bypass_gate(self):
        with patch.object(auth, 'session_user', return_value=None):
            for method in ('GET', 'HEAD'):
                for path in ('/research/data-centers-2026-project-ledger.json', '/research/data-centers-2026-chart-data.json',
                             '/data/dashboard.json', '/data/datacenter_model.json', '/framework/bom.json',
                             '/docs/DECISIONS.md', '/assets/technical-atlas/chip-package-v1.svg', '/assets/models/test.glb',
                             '/projects.html?overview=1', '/%70rojects.html', '/assets/%2e%2e/ledger.html',
                             '/assets/fonts/../../data/dashboard.json', '/%64ata/dashboard.json', '/ledger.html/',
                             '/assets%5c..%5cdata%5cdashboard.json'):
                    status, headers, _ = self.request(method, path)
                    self.assertEqual((status, headers.get('Location')), (302, '/login'), (method, path))
                    self.assertEqual(headers.get('Cache-Control'), 'private, no-store', path)
                for path in ('/api/industry', '/api/news', '/api/observations?object=company:nvidia',
                             '/api/product-catalog/nvidia?export=specs', '/api/report', '/api/tasks', '/api/users',
                             '/api/industry?overview=1&site=secret', '/api/news?overview=1&company=nvidia',
                             '/api/industry?overview=1&overview=0', '/api/news?overview=1&export=',
                             '/%61pi/news', '/assets/../api/report'):
                    status, headers, _ = self.request(method, path)
                    self.assertEqual(status, 401, (method, path))
                    self.assertIn('private, no-store', headers.get('Cache-Control', ''), path)
            for path in ('/api/add-price', '/api/supply', '/api/run', '/api/users', '/api/assign', '/assets/industry.js'):
                status, _, _ = self.request('POST', path, b'{}')
                self.assertIn(status, (302, 401), path)

    def test_research_downloads_remain_available_to_members(self):
        with patch.object(auth, 'session_user', return_value='member'), patch.object(auth, 'user_role', return_value='member'):
            path = '/research/data-centers-2026-project-ledger.json'
            status, headers, body = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertEqual(headers.get('Cache-Control'), 'private, no-store')
            ledger = json.loads(body)
            self.assertEqual(len({row['id'] for row in ledger['records']}), 168)
            self.assertFalse(ledger['aggregation_allowed'])
            self.assertFalse(ledger['formal_database_ingested'])

    def test_task_api_has_public_projection_but_writes_recheck_login_and_intern_ownership(self):
        from inresearch.workflow import research_tasks
        endpoint = '/api/research-tasks'
        with patch.object(auth, 'session_user', return_value=None), patch.object(research_tasks, 'snapshot', return_value={'role': 'reader'}) as snapshot:
            status, headers, body = self.request('GET', endpoint)
            self.assertEqual((status, json.loads(body)), (200, {'role': 'reader'}))
            self.assertEqual(headers['Cache-Control'], 'private, no-store')
            self.assertEqual(self.request('POST', endpoint, b'{}')[0], 401)
            snapshot.assert_called_once_with(serve.ROOT, actor='local', role='reader')
        with patch.object(auth, 'session_user', return_value='intern'), patch.object(auth, 'user_role', return_value='intern'):
            with patch.object(research_tasks, 'snapshot', return_value={'role': 'intern'}) as snapshot:
                status, headers, body = self.request('GET', endpoint)
                self.assertEqual((status, json.loads(body)), (200, {'role': 'intern'}))
                self.assertEqual(headers.get('Cache-Control'), 'private, no-store')
                snapshot.assert_called_once_with(serve.ROOT, actor='intern', role='intern')
            with patch.object(research_tasks, 'mutate', side_effect=research_tasks.Forbidden('other owner')) as mutate:
                self.assertEqual(self.request('POST', endpoint, b'{}')[0], 403)
                mutate.assert_not_called()
                status, _, _ = self.request('POST', endpoint, b'{}', {'X-Requested-With': 'research-tasks'})
                self.assertEqual(status, 403)
                mutate.assert_called_once_with(serve.ROOT, {}, 'intern', 'intern')
            for error, expected in ((research_tasks.Conflict('stale'), 409), (ValueError('bad payload'), 400), (OSError('disk'), 503)):
                with patch.object(research_tasks, 'mutate', side_effect=error):
                    status, headers, _ = self.request('POST', endpoint, b'{}', {'X-Requested-With': 'research-tasks'})
                    self.assertEqual(status, expected)
                    self.assertEqual(headers.get('Cache-Control'), 'private, no-store')

    def test_member_sees_the_whole_model(self):
        with patch.object(auth, 'session_user', return_value='m'), patch.object(auth, 'user_role', return_value='member'):
            status, _, body = self.request('GET', '/api/whoami')
            self.assertEqual(json.loads(body)['role'], 'member')
            model = json.loads(self.request('GET', '/data/datacenter_model.json')[2])
            self.assertNotIn('public_view', model)
            self.assertIn('ai_texas_own', model['presets'])
            self.assertEqual(self.request('GET', '/supply.html')[0], 200)

    def test_intern_retains_existing_restricted_research_access(self):
        with patch.object(auth, 'session_user', return_value='i'), patch.object(auth, 'user_role', return_value='intern'):
            status, headers, _ = self.request('GET', '/team.html')
            self.assertEqual((status, headers.get('Location')), (302, '/supply.html#tasks'), 'the team board merged into the acquisition page')
            self.assertEqual(self.request('GET', '/ledger.html')[0], 200, 'closing anonymous access preserves the intern role grant')
            model = json.loads(self.request('GET', '/data/datacenter_model.json')[2])
            self.assertEqual(model['public_view'], 'reader')
            self.assertEqual(self.request('GET', '/supply.html')[0], 200, 'the acquisition page is the intern entry (own target rows)')
            self.assertEqual(self.request('GET', '/data/facts.json')[0], 403)
            self.assertEqual(self.request('GET', '/api/supply')[0], 403, 'the supply ledger stays members-only')
            status, headers, _ = self.request('GET', '/')
            self.assertEqual((status, headers.get('Location')), (302, '/supply.html#targets'))


if __name__ == '__main__':
    unittest.main()
