"""Published releases and runtime writes must never shadow or overwrite each other."""
import hashlib
from datetime import datetime, timezone
import http.cookiejar
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from inresearch.storage import layout
from inresearch.storage.files import atomic_write, locked
from inresearch.interfaces.static import source_path

REPO = Path(__file__).resolve().parents[2]


def initialize_process(root, runtime):
    layout.initialize_runtime(root, runtime)


def library_writer(index, plan, ready, proceed):
    with locked(index):
        atomic_write(index, b'{"records": []}')
        ready.set()
        if not proceed.wait(10): raise TimeoutError('fixture not released')
        with locked(plan):
            atomic_write(plan, b'library update')


class StorageLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root, self.runtime = (Path(self.tmp.name).resolve() / p for p in ('source', 'runtime'))
        self.contract = json.loads((REPO / 'framework/storage_contract.json').read_text())
        for relative in ['framework/storage_contract.json', 'web/routes.json'] + [
                p for p, rule in self.contract['files'].items() if rule.get('seed')]:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / relative, target)
        self.env = patch.dict(os.environ, INRESEARCH_RUNTIME_ROOT=str(self.runtime))
        self.env.start(); self.addCleanup(self.env.stop)

    def initialize(self):
        return layout.initialize_runtime(self.root)

    def test_queries_do_not_create_a_store_and_published_files_ignore_old_copies(self):
        self.assertFalse(layout.check_runtime(self.root)['initialized'])
        self.assertFalse(self.runtime.exists())
        self.assertEqual(source_path('/data/facts.json', self.root), self.root / 'data/facts.json')
        self.assertFalse(self.runtime.exists())
        old = self.runtime / 'data/facts.json'; old.parent.mkdir(parents=True); old.write_text('old')
        current = self.root / 'data/facts.json'; current.write_text('new')
        self.assertEqual(source_path('/data/facts.json', self.root).read_text(), 'new')
        self.assertEqual(old.read_text(), 'old')

    def test_initialization_preserves_state_and_never_reseeds_on_a_new_release(self):
        self.initialize()
        price = self.runtime / 'data/prices.json'
        price.write_text('runtime observation')
        (self.root / 'data/prices.json').write_text('different release seed')
        self.initialize()
        self.assertEqual(price.read_text(), 'runtime observation')
        self.assertEqual(source_path('/data/prices.json', self.root), price)
        guide = self.root / 'reports/HOW_TO_OUTPUT.md'; guide.parent.mkdir(exist_ok=True); guide.write_text('new guide')
        (self.runtime / 'reports/HOW_TO_OUTPUT.md').write_text('old guide')
        self.assertEqual(source_path('/reports/HOW_TO_OUTPUT.md', self.root).read_text(), 'new guide')

    def test_seed_write_failure_is_resumable_without_erasing_existing_records(self):
        commit = layout.atomic_write
        def fail(path, body):
            if path.name == 'prices.json':
                raise OSError('simulated seed failure')
            return commit(path, body)
        with patch.object(layout, 'atomic_write', side_effect=fail):
            with self.assertRaises(OSError):
                self.initialize()
        state = self.runtime / 'data/.storage-layout.json'
        self.assertEqual(json.loads(state.read_text())['state'], 'initializing')
        self.assertTrue(self.initialize()['initialized'])

    def test_incomplete_initialization_cannot_silently_change_seed_version(self):
        with patch.object(layout, 'atomic_write', side_effect=OSError('failure')):
            with self.assertRaises(OSError):
                self.initialize()
        (self.root / 'data/prices.json').write_text('new seed')
        with self.assertRaisesRegex(layout.LayoutError, 'resume_original'):
            layout.check_runtime(self.root)
        with self.assertRaisesRegex(layout.LayoutError, 'resume_original'):
            self.initialize()

    def test_missing_committed_state_is_not_replaced_but_a_projection_can_rebuild(self):
        self.initialize()
        projection = self.runtime / 'reports/verify_queue.md'; projection.unlink()
        self.initialize(); self.assertTrue(projection.exists())
        price = self.runtime / 'data/prices.json'; price.unlink()
        with self.assertRaisesRegex(layout.LayoutError, 'runtime_state_missing'):
            self.initialize()
        self.assertFalse(price.exists())

    def test_concurrent_first_initializers_share_one_store(self):
        ctx = multiprocessing.get_context('spawn')
        processes = [ctx.Process(target=initialize_process, args=(self.root, self.runtime)) for _ in range(3)]
        try:
            for process in processes: process.start()
            for process in processes:
                process.join(15); self.assertEqual(process.exitcode, 0)
            self.assertTrue(layout.check_runtime(self.root)['initialized'])
            self.assertEqual((self.runtime / 'data/prices.json').read_bytes(), (self.root / 'data/prices.json').read_bytes())
        finally:
            for process in processes:
                if process.is_alive(): process.terminate(); process.join()

    def test_layout_changes_require_migration_and_aliases_cannot_share_a_write_lock(self):
        self.initialize()
        file = self.root / 'framework/storage_contract.json'
        self.contract['files']['data/prices.json']['runtime'] = 'data/new-prices.json'
        file.write_text(json.dumps(self.contract))
        with self.assertRaisesRegex(layout.LayoutError, 'migration_required'):
            self.initialize()
        self.contract['files']['data/prices.json']['runtime'] = 'data/assignments.json'
        file.write_text(json.dumps(self.contract))
        with self.assertRaisesRegex(layout.LayoutError, 'invalid_storage_rule'):
            self.initialize()

    def test_initialization_does_not_invert_the_library_transaction_lock_order(self):
        ctx = multiprocessing.get_context('spawn')
        ready, proceed = ctx.Event(), ctx.Event()
        plan, index = self.runtime / 'data/product_docs_plan.csv', self.runtime / 'data/product_library_index.json'
        writer = ctx.Process(target=library_writer, args=(index, plan, ready, proceed))
        initializer = ctx.Process(target=initialize_process, args=(self.root, self.runtime))
        try:
            writer.start(); self.assertTrue(ready.wait(5)); initializer.start()
            for _ in range(100):
                if plan.exists(): break
                time.sleep(.02)
            self.assertTrue(plan.exists())
            proceed.set()
            for process in (writer, initializer):
                process.join(10); self.assertEqual(process.exitcode, 0)
            self.assertEqual(plan.read_text(), 'library update')
        finally:
            proceed.set()
            for process in (writer, initializer):
                if process.is_alive(): process.terminate(); process.join()

    def test_existing_release_requires_both_admin_store_and_unchanged_session_key(self):
        self.initialize()
        with self.assertRaisesRegex(layout.LayoutError, 'admin_store'): layout.check_runtime(self.root, require_auth=True)
        (self.runtime / 'data/users.json').write_text('{"users":{"owner":{"role":"admin"}}}')
        with self.assertRaisesRegex(layout.LayoutError, 'session_key'): layout.check_runtime(self.root, require_auth=True)
        secret = self.runtime / 'data/.hub_secret'; secret.write_bytes(b's' * 32)
        self.assertTrue(layout.check_runtime(self.root, require_auth=True)['initialized'])
        self.assertEqual(secret.read_bytes(), b's' * 32)

    def test_private_roots_traversal_and_symlink_escape_never_become_static_routes(self):
        self.initialize()
        for relative in ('data/raw/original.txt', 'data/.material-intake/file.txt', 'data/research_runtime.json', 'data/users.json'):
            self.assertEqual(source_path('/' + relative, self.root), self.root / '.not-served')
        with self.assertRaises(layout.LayoutError): layout.workspace_path('../source/data/facts.json', self.root)
        target = self.runtime / 'data/prices.json'; target.unlink(); target.symlink_to(self.root / 'data/prices.json')
        self.assertEqual(source_path('/data/prices.json', self.root), self.root / '.not-served')
        with self.assertRaises(layout.LayoutError): self.initialize()

    def test_authoring_mode_remains_an_explicit_checkout_and_requires_no_contract(self):
        with patch.dict(os.environ, INRESEARCH_RUNTIME_ROOT=''):
            self.assertEqual(layout.workspace_path('data/prices.json', self.root), self.root / 'data/prices.json')
            self.assertEqual(layout.initialize_runtime(self.root)['mode'], 'authoring')
        self.assertFalse(self.runtime.exists())

    def test_runtime_cannot_be_inside_or_above_the_published_source(self):
        for runtime in (self.root, self.root.parent, self.root / 'runtime', Path('relative')):
            with self.subTest(runtime=runtime):
                with self.assertRaisesRegex(layout.LayoutError, 'separate'):
                    layout.check_runtime(self.root, runtime)

    def test_two_release_roots_and_rollback_keep_runtime_writes_current(self):
        self.initialize()
        other = Path(self.tmp.name) / 'release-b'; shutil.copytree(self.root, other)
        (self.root / 'data/facts.json').write_text('version-a')
        (other / 'data/facts.json').write_text('version-b')
        price = self.runtime / 'data/prices.json'; price.write_text('first runtime write')
        self.assertEqual(source_path('/data/facts.json', other).read_text(), 'version-b')
        layout.initialize_runtime(other)
        with locked(price): atomic_write(price, b'second runtime write')
        self.assertEqual(source_path('/data/facts.json', self.root).read_text(), 'version-a')
        self.initialize()
        self.assertEqual(source_path('/data/prices.json', self.root).read_text(), 'second runtime write')

    def test_event_review_suggestions_preserve_formal_research_bytes(self):
        from inresearch.adapters import historical_brief
        doc = self.root / 'research/M01.md'; doc.parent.mkdir()
        body = '## M01-F01 Example\n- **状态**：current ｜ **修订**：2026-01-01 ｜ entity:example\n'
        doc.write_text(body)
        signals = [{'company': 'example', 'date': '2026-06-01', 'form': '10-Q', 'url': 'https://example.test/filing'}]
        with patch.object(historical_brief, 'ROOT', self.root):
            result = historical_brief.review_suggestions(signals)
        self.assertEqual(doc.read_text(), body)
        self.assertEqual(result[0]['status'], 'review_suggested')
        self.assertEqual(result[0]['signals'], signals)


class RuntimeHTTPTests(unittest.TestCase):
    def test_http_cli_and_generated_outputs_share_runtime_without_changing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            env = dict(os.environ, INRESEARCH_RUNTIME_ROOT=str(runtime), INRESEARCH_PROJECT_ROOT=str(REPO),
                       PYTHONPATH=str(REPO / 'src'), PYTHONDONTWRITEBYTECODE='1', HUB_AUTH='on', HUB_HOST='127.0.0.1')
            if (REPO / '.git').exists():
                tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=REPO).decode().strip('\0').split('\0')
            else:
                # Production images intentionally exclude Git and its credentials.
                tracked = [str(p.relative_to(REPO)) for p in REPO.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
            before = {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in tracked}
            setup = "from inresearch.interfaces import auth; assert auth.add_user('fixture', 'fixture-password-123', 'admin')[0]"
            subprocess.run([sys.executable, '-c', setup], env=env, check=True, capture_output=True)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            log = (runtime / 'server.log').open('w')
            process = subprocess.Popen([sys.executable, str(REPO / 'manage.py'), 'serve', str(port)], env=env, stdout=log, stderr=log)
            try:
                cookies = http.cookiejar.CookieJar()
                client = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(cookies))
                base = 'http://127.0.0.1:' + str(port)
                for _ in range(100):
                    try:
                        with client.open(base + '/login', timeout=1): break
                    except OSError:
                        if process.poll() is not None: self.fail((runtime / 'server.log').read_text())
                        time.sleep(.05)
                def request(path, payload=None, headers=None):
                    data = json.dumps(payload).encode() if isinstance(payload, dict) else payload
                    req = urllib.request.Request(base + path, data=data, headers=headers or {'Content-Type': 'application/json'})
                    with client.open(req, timeout=30) as response:
                        return json.loads(response.read())
                self.assertTrue(request('/api/login', {'username': 'fixture', 'password': 'fixture-password-123'})['ok'])
                # The production TLS proxy forwards this Secure cookie to HTTP.
                # Reproduce that forwarding without weakening the cookie policy.
                self.assertTrue(all(cookie.secure for cookie in cookies))
                client.addheaders = [('Cookie', '; '.join(cookie.name + '=' + cookie.value for cookie in cookies))]
                self.assertEqual(request('/api/whoami')['role'], 'admin')
                price = {'series_id': 'storage-layout-fixture', 'as_of': '2026-09-13', 'value': 1.25, 'unit': '$/hr',
                         'grade': 'media', 'source_url': 'https://example.test/fixture', 'category': 'gpu-rental', 'module': 'M13'}
                self.assertTrue(request('/api/add-price', price)['ok'])
                self.assertEqual(sum(r['series_id'] == price['series_id'] for r in request('/data/prices.json')['records']), 1)
                retry = subprocess.run([sys.executable, str(REPO / 'manage.py'), 'add-price'], input=json.dumps(price),
                                       env=env, text=True, capture_output=True)
                self.assertEqual(json.loads(retry.stdout)['status'], 409)
                task = request('/api/tasks')['orders'][0]['wid']
                self.assertTrue(request('/api/assign', {'workorder_id': task, 'assignee': 'fixture', 'status': '已派'})['ok'])
                self.assertTrue(any(r.get('assignee') == 'fixture' for r in request('/data/assignments.json')['records']))
                uploaded = request('/api/materials', b'isolated original', {'X-Requested-With': 'material-intake'})
                self.assertEqual((runtime / 'data/.material-intake' / uploaded['item']['id'] / 'content').read_bytes(), b'isolated original')
                from test_research import adopted_knowledge
                token = 'isolated-reader-' + 'a' * 48
                (runtime / 'data/.reader_sync_token').write_text(token)
                payload = dict(generated=datetime.now(timezone.utc).isoformat(), knowledge=adopted_knowledge(),
                               graph_version=json.loads((REPO / 'framework/research_graph.json').read_text())['version'],
                               questions_version=json.loads((REPO / 'framework/research_questions.json').read_text())['version'])
                self.assertTrue(request('/api/reader-snapshot', payload, {'Authorization': 'Bearer ' + token})['ok'])
                stored = (runtime / 'data/research_runtime.json').read_bytes()
                self.assertEqual(json.loads(stored)['knowledge']['answers'][0]['status'], 'candidate')
                retry = subprocess.run([sys.executable, str(REPO / 'manage.py'), 'receive-snapshot'], input=json.dumps(payload),
                                       env=env, text=True, capture_output=True)
                self.assertEqual(retry.returncode, 0)
                self.assertTrue(json.loads(retry.stdout)['replayed'])
                self.assertEqual((runtime / 'data/research_runtime.json').read_bytes(), stored)
                for path in ('/data/users.json', '/data/research_runtime.json', '/data/raw/source.txt', '/runtime/data/users.json'):
                    with self.assertRaises(urllib.error.HTTPError) as error: request(path)
                    self.assertEqual(error.exception.code, 404)
                for command in ('indicators', 'verify', 'reading-queue', 'coverage', 'workorders', 'historical-brief', 'export', 'map', 'submissions'):
                    run = subprocess.run([sys.executable, str(REPO / 'manage.py'), command], env=env, text=True, capture_output=True, timeout=60)
                    self.assertEqual(run.returncode, 0, command + '\n' + run.stderr[-2000:])
                self.assertTrue((runtime / 'data/projections/indicators.json').is_file())
                self.assertTrue((runtime / 'reports/verify_queue.md').is_file())
                self.assertEqual(before, {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in before})
            finally:
                process.terminate(); process.wait(timeout=10); log.close()
