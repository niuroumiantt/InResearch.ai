"""Real HTTP authentication, authorization and shared mutation round trips."""
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from inresearch.interfaces import auth, http
from inresearch.storage.files import write_json


class HTTPWorkflow(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.root = root
        for module, key, value in ((http, 'ROOT', root), (http, 'AUTH_ON', True),
                                   (auth, 'USERS_FILE', root/'data/users.json'),
                                   (auth, 'SECRET_FILE', root/'data/.hub_secret'),
                                   (auth, '_fails', {})):
            self.stack.enter_context(patch.object(module, key, value))
        write_json(root/'data/prices.json', {'records': []})
        write_json(root/'web/routes.json', {})
        self.password = 'Only-a-temporary-test-983'
        self.assertTrue(auth.add_user('admin', self.password, 'admin')[0])
        self.assertTrue(auth.add_user('intern', self.password, 'intern')[0])
        server = http.ThreadingHTTPServer(('127.0.0.1', 0), http.Handler)
        self.server = server
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), thread.join(), server.server_close()))

    def request(self, path, payload=None, cookie=None):
        connection = HTTPConnection('127.0.0.1', self.server.server_port)
        headers = {'Content-Type': 'application/json'}
        if cookie:
            headers['Cookie'] = cookie
        connection.request('POST' if payload is not None else 'GET', path,
                           json.dumps(payload) if payload is not None else None, headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_login_write_retry_role_and_password_round_trip(self):
        status, _, page = self.request('/login')
        self.assertEqual(status, 200)
        self.assertIn(b'data-auth-form', page)
        self.assertEqual(self.request('/api/login', {'username':1, 'password':False})[0], 400)
        self.assertEqual(self.request('/api/login', {'username':'admin', 'password':'wrong'})[0], 401)
        status, headers, _ = self.request('/api/login', {'username':'admin', 'password':self.password})
        self.assertEqual(status, 200)
        cookie = headers['Set-Cookie'].split(';')[0]
        with patch.object(http, 'ROOT', Path(__file__).resolve().parents[2]):
            page = self.request('/admin/product/index.html', cookie=cookie)
            self.assertEqual(page[0], 200)
            for alias in ('/admin/product', '/admin/product/'):
                self.assertEqual(self.request(alias, cookie=cookie)[2], page[2])
            status, _, body = self.request('/api/admin/product-coverage', cookie=cookie)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['totals']['lines'], 175)
        rec = dict(series_id='flow', as_of='2026-09-13', value=7, unit='USD',
                   grade='company', category='gpu', module='M06', source_url='https://example.test')
        self.assertEqual(self.request('/api/add-price', rec)[0], 401)
        self.assertEqual(self.request('/api/add-price', rec, cookie)[0], 200)
        self.assertEqual(self.request('/api/add-price', rec, cookie)[0], 409)
        self.assertEqual(self.request('/api/add-price', {**rec, 'value':True}, cookie)[0], 400)
        self.assertEqual(len(json.loads((self.root/'data/prices.json').read_text())['records']), 1)
        _, headers, _ = self.request('/api/login', {'username':'intern', 'password':self.password})
        self.assertEqual(self.request('/api/add-price', rec, headers['Set-Cookie'].split(';')[0])[0], 403)
        self.assertEqual(self.request('/api/admin/product-coverage', cookie=headers['Set-Cookie'].split(';')[0])[0], 403)
        self.assertEqual(self.request('/api/admin/product-coverage')[0], 401)
        for secret in ('/data/users.json', '/data/%2ehub_secret', '/src/inresearch/interfaces/auth.py'):
            self.assertEqual(self.request(secret, cookie=cookie)[0], 404)
        new_password = 'Another-temporary-test-738'
        self.assertEqual(self.request('/api/passwd', {'old_password':self.password,
                                                     'new_password':new_password}, cookie)[0], 200)
        self.assertEqual(self.request('/api/login', {'username':'admin', 'password':self.password})[0], 401)
        self.assertEqual(self.request('/api/login', {'username':'admin', 'password':new_password})[0], 200)
