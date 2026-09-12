from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import TestCase, main, mock
import json
import os
import subprocess
import sys
import tempfile

import auth


class UserTransactionTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'users.json'
        patch = mock.patch.object(auth, 'USERS_FILE', self.path)
        patch.start()
        self.addCleanup(patch.stop)
        auth.add_user('admin', 'test-password')

    def test_concurrent_deletions_do_not_restore_accounts(self):
        for i in range(12):
            auth.add_user(f'user{i}', 'test-password')
        with ThreadPoolExecutor(6) as pool:
            results = list(pool.map(auth.remove_user, [f'user{i}' for i in range(12)]))
        self.assertTrue(all(ok for ok, _ in results))
        self.assertEqual(['admin'], list(auth.load_users()))
        self.assertEqual(0o600, self.path.stat().st_mode & 0o777)

    def test_last_admin_protection_survives_concurrent_processes(self):
        auth.add_user('admin2', 'test-password', 'admin')
        code = ('import auth,sys; from pathlib import Path; auth.USERS_FILE=Path(sys.argv[1]); '
                'print(auth.remove_user(sys.argv[2])[0])')
        env = {**os.environ, 'PYTHONPATH': str(Path(auth.__file__).parent)}
        processes = [subprocess.Popen([sys.executable, '-c', code, str(self.path), name],
                                      env=env, stdout=subprocess.PIPE, text=True)
                     for name in ('admin', 'admin2')]
        results = [p.communicate(timeout=10)[0].strip() for p in processes]
        self.assertEqual(['False', 'True'], sorted(results))
        self.assertEqual(1, len(auth.load_users()))

    def test_failed_replace_preserves_complete_existing_table(self):
        before = self.path.read_bytes()
        with mock.patch.object(auth.os, 'replace', side_effect=OSError('simulated crash')):
            with self.assertRaises(OSError):
                auth.add_user('new-user', 'test-password')
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([], list(self.path.parent.glob('.users-*')))

    def test_corrupt_existing_table_is_never_bootstrapped_as_empty(self):
        self.path.write_text('{broken')
        with self.assertRaisesRegex(RuntimeError, 'user_store_unavailable'):
            auth.add_user('replacement-admin', 'test-password')
        self.assertEqual('{broken', self.path.read_text())


if __name__ == '__main__':
    main()
