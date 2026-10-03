"""Repository diagrams require real admin sessions for documents and embedded data."""
from contextlib import ExitStack
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from inresearch.interfaces import auth, http, repository_pages
from inresearch.paths import project_root

ROOT = project_root()


class RepositoryPageTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temp = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for module, name, value in ((http, 'AUTH_ON', True),
                                    (auth, 'USERS_FILE', temp / 'users.json'),
                                    (auth, 'SECRET_FILE', temp / '.hub_secret')):
            self.stack.enter_context(patch.object(module, name, value))
        self.cookies = {}
        for role in ('admin', 'member', 'intern'):
            self.assertTrue(auth.add_user(role, 'Only-test-architecture-8391', role)[0])
            self.cookies[role] = auth.make_cookie(role).split(';')[0]
        self.server = http.ThreadingHTTPServer(('127.0.0.1', 0), http.Handler)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), thread.join(), self.server.server_close()))
        self.paths = sorted(repository_pages.PAGES | set(repository_pages.ALIASES)) + [
            '/admin/repo-content/infra.html', '/admin/repo-content/fetchspec.html',
            '/admin/repo-content/manifest.json', '/admin/%69nfrarepo.html?download=1',
            '/assets/../admin/infrarepo.html', '/admin/repo-content%2Finfra.html',
            '/admin/repo-content/../infrarepo.html', '/admin%5Crepo-content%5Cinfra.html']

    def request(self, method, path, role=None):
        connection = HTTPConnection(*self.server.server_address, timeout=5)
        try:
            headers = {'Cookie': self.cookies[role]} if role else {}
            connection.request(method, path, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_every_document_requires_admin_even_in_local_mode(self):
        for auth_on in (True, False):
            with patch.object(http, 'AUTH_ON', auth_on):
                for method in ('GET', 'HEAD'):
                    for path in self.paths:
                        with self.subTest(auth_on=auth_on, method=method, path=path):
                            code, headers, body = self.request(method, path)
                            self.assertEqual((code, headers.get('Location')), (302, '/login'))
                            self.assertEqual(headers.get('Cache-Control'), 'private, no-store')
                            for role in ('member', 'intern'):
                                self.assertEqual(self.request(method, path, role)[0], 403)

    def test_admin_can_read_pages_and_old_link_redirects(self):
        for method in ('GET', 'HEAD'):
            for path in self.paths:
                code, headers, body = self.request(method, path, 'admin')
                if path in repository_pages.ALIASES:
                    self.assertEqual((code, headers.get('Location')), (302, '/admin/fetchspecrepo.html'))
                else:
                    self.assertEqual(code, 200, path)
                    if method == 'GET':
                        self.assertTrue(body, path)
                self.assertEqual(headers.get('Cache-Control'), 'private, no-store')
        for path in ('/web/pages/admin/repo-content/infra.html', '/scripts/sync_repo_pages.py'):
            self.assertEqual(self.request('GET', path, 'admin')[0], 404)
        self.assertEqual(self.request('GET', '/')[0], 200)

    def test_snapshot_provenance_and_navigation_are_complete(self):
        routes = json.loads((ROOT / 'web/routes.json').read_text())
        manifest = json.loads((ROOT / 'web/pages/admin/repo-content/manifest.json').read_text())
        self.assertEqual(set(manifest), {'infra', 'inews', 'fetchspec', 'inresearch'})
        for name, record in manifest.items():
            self.assertEqual(record['kind'], 'architecture_snapshot')
            self.assertTrue(record['sources'])
            for source in record['sources']:
                self.assertRegex(source['sha256'], r'^[0-9a-f]{64}$')
            html = (ROOT / routes[f'/admin/{name}repo.html']).read_text()
            self.assertIn('/admin/repos.html', html)
            self.assertIn(record['synced_at'], html)
        news = (ROOT / routes['/admin/inewsrepo.html']).read_text()
        self.assertIn('实时计数未同步', news)
        self.assertIn('https://inews.today/admin/reporg.html', news)
        infra = manifest['infra']['sources'][0]
        self.assertEqual(hashlib.sha256((ROOT / routes['/admin/repo-content/infra.html']).read_bytes()).hexdigest(),
                         infra['sha256'])


if __name__ == '__main__':
    unittest.main()
