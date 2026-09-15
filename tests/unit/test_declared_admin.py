"""Deployment-declared admin: idempotent alignment, other accounts untouched, value never printed."""
import http.cookiejar
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from inresearch.interfaces import auth

REPO = Path(__file__).resolve().parents[2]


class DeclaredAdminTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Path(directory.name) / 'data/users.json'
        for key, value in (('USERS_FILE', self.store), ('SECRET_FILE', self.store.with_name('.hub_secret'))):
            patcher = patch.object(auth, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_blank_declaration_never_touches_the_store(self):
        self.assertIsNone(auth.apply_declared_admin({}))
        self.assertIsNone(auth.apply_declared_admin({'HUB_ADMIN_USERNAME': 'admin', 'HUB_ADMIN_PASSWORD': ''}))
        self.assertFalse(self.store.exists())
        self.assertTrue(auth.add_user('admin', 'web-chosen-secret-1', 'admin')[0])
        before = self.store.read_bytes()
        self.assertIsNone(auth.apply_declared_admin({'HUB_ADMIN_PASSWORD': ''}))
        self.assertEqual(self.store.read_bytes(), before)
        self.assertTrue(auth.verify_password('admin', 'web-chosen-secret-1'))

    def test_declaration_creates_then_stays_idempotent_then_wins_over_later_resets(self):
        env = {'HUB_ADMIN_PASSWORD': 'declared-secret-1'}
        self.assertEqual(auth.apply_declared_admin(env), 'created')
        self.assertTrue(auth.verify_password('admin', 'declared-secret-1'))
        self.assertEqual(auth.user_role('admin'), 'admin')
        before = self.store.read_bytes()
        self.assertEqual(auth.apply_declared_admin(env), 'unchanged')
        self.assertEqual(self.store.read_bytes(), before)   # no rewrite, no salt churn
        # A random CLI reset or a web reset happened since: the declaration wins on next start.
        ok, _, random_password = auth.reset_password('admin')
        self.assertTrue(ok)
        self.assertTrue(auth.verify_password('admin', random_password))
        self.assertFalse(auth.verify_password('admin', 'declared-secret-1'))
        self.assertEqual(auth.apply_declared_admin(env), 'password')
        self.assertTrue(auth.verify_password('admin', 'declared-secret-1'))
        self.assertFalse(auth.verify_password('admin', random_password))

    def test_named_account_is_promoted_and_other_accounts_are_untouched(self):
        self.assertTrue(auth.add_user('owner', 'owner-secret-1', 'admin')[0])
        self.assertTrue(auth.add_user('ops', 'ops-secret-1', 'intern')[0])
        self.assertEqual(auth.apply_declared_admin({'HUB_ADMIN_USERNAME': 'ops', 'HUB_ADMIN_PASSWORD': 'ops-secret-1'}), 'role')
        self.assertEqual(auth.user_role('ops'), 'admin')
        self.assertEqual(auth.apply_declared_admin({'HUB_ADMIN_USERNAME': 'ops', 'HUB_ADMIN_PASSWORD': 'ops-secret-2'}), 'password')
        self.assertTrue(auth.verify_password('ops', 'ops-secret-2'))
        self.assertTrue(auth.verify_password('owner', 'owner-secret-1'))
        self.assertEqual(auth.user_role('owner'), 'admin')
        self.assertEqual(auth.apply_declared_admin({'HUB_ADMIN_USERNAME': 'new', 'HUB_ADMIN_PASSWORD': 'new-secret-1'}), 'created')
        self.assertEqual(sorted(auth.load_users()), ['new', 'ops', 'owner'])
        self.assertEqual(auth.load_users()['new']['role'], 'admin')

    def test_invalid_username_is_rejected_before_any_write(self):
        for name in ('Admin', 'a', 'root user', '../x'):
            with self.assertRaises(ValueError):
                auth.apply_declared_admin({'HUB_ADMIN_USERNAME': name, 'HUB_ADMIN_PASSWORD': 'x-secret-1'})
        self.assertFalse(self.store.exists())


class DeclaredAdminServerTests(unittest.TestCase):
    def test_serve_aligns_the_runtime_store_and_never_logs_the_value(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            # Unbuffered so the startup line reaches server.log before terminate(); CI does not set it.
            env = dict(os.environ, INRESEARCH_RUNTIME_ROOT=str(runtime), INRESEARCH_PROJECT_ROOT=str(REPO),
                       PYTHONPATH=str(REPO / 'src'), PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1',
                       HUB_AUTH='on', HUB_HOST='127.0.0.1',
                       HUB_ADMIN_USERNAME='admin', HUB_ADMIN_PASSWORD='declared-only-for-this-test-4')
            # The store already exists with a different admin password, as after a stray reset.
            stale = "from inresearch.interfaces import auth; assert auth.add_user('admin', 'stale-secret-1', 'admin')[0]"
            subprocess.run([sys.executable, '-c', stale], env=env, check=True, capture_output=True)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            log_path = runtime / 'server.log'
            log = log_path.open('w')
            process = subprocess.Popen([sys.executable, str(REPO / 'manage.py'), 'serve', str(port)], env=env, stdout=log, stderr=log)
            try:
                client = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                     urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                base = 'http://127.0.0.1:' + str(port)
                for _ in range(200):
                    try:
                        with client.open(base + '/login', timeout=1):
                            break
                    except OSError:
                        if process.poll() is not None:
                            self.fail(log_path.read_text())
                        time.sleep(.05)
                # The alignment is recorded before the server binds; task_auth.log keeps
                # only the latest event, so read it before any login overwrites it.
                self.assertIn('部署声明的管理员 admin：password', (runtime / 'logs/task_auth.log').read_text())

                def login(password):
                    body = json.dumps({'username': 'admin', 'password': password}).encode()
                    request = urllib.request.Request(base + '/api/login', data=body, headers={'Content-Type': 'application/json'})
                    try:
                        with client.open(request, timeout=30) as response:
                            return response.status
                    except urllib.error.HTTPError as error:
                        return error.code
                self.assertEqual(login('stale-secret-1'), 401)
                self.assertEqual(login('declared-only-for-this-test-4'), 200)
            finally:
                process.terminate()
                process.wait(timeout=10)
                log.close()
            stored = json.loads((runtime / 'data/users.json').read_text())['users']
            self.assertEqual(sorted(stored), ['admin'])
            self.assertEqual(stored['admin']['role'], 'admin')
            written = log_path.read_text() + (runtime / 'logs/task_auth.log').read_text()
            self.assertIn('部署声明的管理员 admin：password', log_path.read_text())
            self.assertNotIn('declared-only-for-this-test-4', written)
            self.assertNotIn('declared-only-for-this-test-4', (runtime / 'data/users.json').read_text())


if __name__ == '__main__':
    unittest.main()
