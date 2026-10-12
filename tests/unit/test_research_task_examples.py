"""Worked-example metadata, real bytes, privacy and download boundaries."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from inresearch.paths import project_root
from inresearch.workflow import research_task_examples as examples
from inresearch.interfaces import auth, http as serve, public


class ExampleFixture(unittest.TestCase):
    def setUp(self):
        self.root = project_root()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.environment = patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT': self.temp.name})
        self.environment.start(); self.addCleanup(self.environment.stop)
        self.directory = Path(self.temp.name) / examples.PREFIX / examples.EXAMPLE_IDS[0]

    def install(self):
        self.directory.mkdir(parents=True)
        artifacts = []
        for ident, content, scope in (('original', b'PUBLIC SYNTHETIC SOURCE\n', 'public'),
                                       ('receipt', b'{"received":true,"synthetic":true}\n', 'public'),
                                       ('internal', b'PRIVATE SYNTHETIC OPERATOR NOTE\n', None)):
            relative = ident + '.txt'
            (self.directory / relative).write_bytes(content)
            row = {'id': ident, 'path': relative, 'sha256': hashlib.sha256(content).hexdigest(),
                   'size': len(content), 'filename': ident + '.txt'}
            if scope is not None: row['access_scope'] = scope
            artifacts.append(row)
        self.manifest = {'version': 1, 'id': examples.EXAMPLE_IDS[0], 'name': 'SYNTHETIC worked example',
            'site_id': 'synthetic-site', 'status': '合成测试，不能用作研究事实', 'processed_at': '2026-10-12T12:00:00+08:00',
            'private_path': '/private/not-for-browser',
            'execution': {'machine': 'private-m4', 'model': 'private-model', 'actor': 'private-operator',
                          'reading_scope': 'targeted; complete=false'},
            'sources': [{'id': 'source-1', 'title': 'Synthetic source', 'url': 'https://example.invalid/source',
                         'artifact_id': 'original', 'locator': 'section 1; synthetic source text'}],
            'facts': [{'id': 'name', 'label': '园区原名', 'value': 'Synthetic site', 'unit': None,
                       'source_ids': ['source-1'], 'locator': 'section 1'}],
            'unknowns': [{'id': 'electricity', 'label': '年度电耗', 'reason': '合成原件没有披露',
                          'next_action': '向运营方报告与公共事业资料补源，不填0'}],
            'stages': [{'id': 'originals', 'title': '原件取得', 'state': 'complete',
                        'result': '仅用于测试的真实字节', 'artifact_ids': ['original']},
                       {'id': 'receive', 'title': '接收', 'state': 'complete',
                        'result': '仅用于测试的接收回执', 'artifact_ids': ['receipt', 'internal']},
                       {'id': 'publish', 'title': '地图回执', 'state': 'pending',
                        'result': '未执行，不能视为已点亮', 'artifact_ids': []}],
            'artifacts': artifacts, 'links': {'project': '/project.html?site=synthetic-site',
                                             'map': '/industry.html?site=synthetic-site'}}
        self.save()

    def save(self):
        (self.directory / 'example.json').write_text(json.dumps(self.manifest, ensure_ascii=False))


class ExampleTests(ExampleFixture):
    def test_absent_package_is_explicit_and_never_created(self):
        result = examples.snapshot(self.root)
        self.assertEqual(result['status'], 'not_installed')
        self.assertEqual(result['examples'], [])
        self.assertFalse(self.directory.exists())

    def test_anonymous_projection_hides_execution_and_private_artifacts(self):
        self.install()
        result = examples.snapshot(self.root)
        sample = result['examples'][0]
        self.assertIsNone(sample['execution']['machine'])
        self.assertIsNone(sample['execution']['model'])
        self.assertEqual({a['id'] for a in sample['artifacts']}, {'original', 'receipt'})
        self.assertEqual(sample['stages'][-1]['state'], 'pending')
        self.assertEqual(sample['stages'][1]['artifact_ids'], ['receipt'])
        self.assertNotIn('private-m4', json.dumps(result))
        self.assertNotIn('private_path', json.dumps(result))
        self.assertNotIn('original.txt', json.dumps(result).split('"filename"')[0])
        self.assertTrue(all('path' not in a for a in sample['artifacts']))
        complete = examples.snapshot(self.root, authenticated=True)['examples'][0]
        self.assertEqual(complete['execution']['machine'], 'private-m4')
        self.assertEqual(len(complete['artifacts']), 3)

    def test_download_checks_exact_bytes_and_default_private_scope(self):
        self.install()
        body = examples.download(self.root, examples.EXAMPLE_IDS[0], 'original')['body']
        self.assertEqual(body, b'PUBLIC SYNTHETIC SOURCE\n')
        with self.assertRaises(examples.PrivateArtifact):
            examples.download(self.root, examples.EXAMPLE_IDS[0], 'internal')
        self.assertIn(b'PRIVATE', examples.download(self.root, examples.EXAMPLE_IDS[0], 'internal', authenticated=True)['body'])
        with self.assertRaises(examples.NotInstalled):
            examples.download(self.root, examples.EXAMPLE_IDS[0], 'not-registered')

    def test_changed_or_missing_artifact_is_not_downloadable(self):
        self.install()
        path = self.directory / 'original.txt'
        path.write_bytes(b'PUBLIC SYNTHETIC CHANGED\n')
        with self.assertRaises(examples.ArtifactUnavailable):
            examples.download(self.root, examples.EXAMPLE_IDS[0], 'original')
        sample = examples.snapshot(self.root)['examples'][0]
        self.assertFalse(sample['artifacts'][0]['available'])
        self.assertIsNone(sample['artifacts'][0]['download_url'])
        self.assertEqual(sample['stages'][0]['state'], 'complete', 'retain original execution history')
        path.unlink()
        self.assertFalse(examples.snapshot(self.root)['examples'][0]['artifacts'][0]['available'])

    def test_symlink_files_and_directories_even_inside_package_are_refused(self):
        self.install()
        path = self.directory / 'original.txt'
        path.unlink(); path.symlink_to(self.directory / 'receipt.txt')
        with self.assertRaises(examples.ArtifactUnavailable):
            examples.download(self.root, examples.EXAMPLE_IDS[0], 'original')
        path.unlink()
        nested = self.directory / 'nested'
        nested.symlink_to(self.directory, target_is_directory=True)
        self.manifest['artifacts'][0]['path'] = 'nested/receipt.txt'; self.save()
        with self.assertRaises(examples.ArtifactUnavailable):
            examples.download(self.root, examples.EXAMPLE_IDS[0], 'original')

    def test_unsafe_allowlist_and_links_are_rejected(self):
        self.install()
        for relative in ('../receipt.txt', '/tmp/receipt.txt', 'nested/../../receipt.txt', 'a\\receipt.txt', '.private'):
            with self.subTest(relative=relative):
                self.manifest['artifacts'][0]['path'] = relative; self.save()
                with self.assertRaises(ValueError): examples.snapshot(self.root)
        self.manifest['artifacts'][0]['path'] = 'original.txt'
        self.manifest['links']['map'] = 'javascript:alert(1)'; self.save()
        with self.assertRaises(ValueError): examples.snapshot(self.root)


class ExampleHTTPTests(ExampleFixture):
    def setUp(self):
        super().setUp()
        self.install()
        auth_patch = patch.object(serve, 'AUTH_ON', True)
        auth_patch.start(); self.addCleanup(auth_patch.stop)
        sessions = patch.object(auth, 'session_user', side_effect=lambda value: value if value in ('member', 'intern') else None)
        sessions.start(); self.addCleanup(sessions.stop)
        roles = patch.object(auth, 'user_role', side_effect=lambda user: 'intern' if user == 'intern' else 'member')
        roles.start(); self.addCleanup(roles.stop)
        self.server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=2)))

    def request(self, method, path, role=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, headers={'Cookie': role} if role else {})
            reply = connection.getresponse()
            return reply.status, dict(reply.getheaders()), reply.read()
        finally:
            connection.close()

    def test_public_metadata_download_and_private_login_boundary(self):
        base = examples.API + '/' + examples.EXAMPLE_IDS[0] + '/files/'
        for method in ('GET', 'HEAD'):
            status, headers, body = self.request(method, examples.API)
            self.assertEqual(status, 200)
            self.assertEqual(headers['Cache-Control'], 'private, no-store')
            self.assertEqual(headers['Vary'], 'Cookie')
            if method == 'GET': self.assertFalse(json.loads(body)['authenticated'])
            else: self.assertEqual(body, b'')
            status, headers, body = self.request(method, base + 'original')
            self.assertEqual(status, 200)
            self.assertIn('attachment;', headers['Content-Disposition'])
            self.assertEqual(headers['X-Content-SHA256'], self.manifest['artifacts'][0]['sha256'])
            if method == 'HEAD': self.assertEqual(body, b'')
            self.assertEqual(self.request(method, base + 'internal')[0], 401)
            for role in ('member', 'intern'):
                self.assertEqual(self.request(method, base + 'internal', role)[0], 200)
        self.assertEqual(self.request('GET', '/api/industry')[0], 401)
        self.assertEqual(self.request('GET', '/ledger.html')[0], 302)
        self.assertEqual(self.request('GET', '/tasks.html')[0], 200)
        self.assertEqual(self.request('POST', examples.API)[0], 401)

    def test_changed_download_and_unregistered_paths_never_leak_local_paths(self):
        base = examples.API + '/' + examples.EXAMPLE_IDS[0] + '/files/'
        (self.directory / 'original.txt').write_bytes(b'changed')
        status, _, body = self.request('GET', base + 'original')
        self.assertEqual(status, 409)
        self.assertNotIn(str(self.directory).encode(), body)
        self.assertEqual(self.request('GET', base + 'missing')[0], 404)
        self.assertFalse(public.allowed(examples.API + '/other-sample/files/original'))
        self.assertFalse(public.allowed(base + 'original?path=../example.json'))

    def assert_sample_unavailable_without_path_disclosure(self):
        download = examples.API + '/' + examples.EXAMPLE_IDS[0] + '/files/original'
        for role in (None, 'member', 'intern'):
            for method in ('GET', 'HEAD'):
                for path, expected in ((examples.API, 503), (download, 409)):
                    with self.subTest(role=role, method=method, path=path):
                        status, headers, body = self.request(method, path, role)
                        self.assertEqual(status, expected)
                        self.assertEqual(headers['Cache-Control'], 'private, no-store')
                        self.assertEqual(headers['Vary'], 'Cookie')
                        self.assertNotIn('Content-Disposition', headers)
                        self.assertNotIn('X-Content-SHA256', headers)
                        if method == 'HEAD':
                            self.assertEqual(body, b'')
                        else:
                            self.assertFalse(json.loads(body)['ok'])
                            self.assertNotIn(str(self.directory).encode(), body)
                            self.assertNotIn(b'PRIVATE SYNTHETIC', body)
                            self.assertNotIn(b'private-operator', body)

    def test_manifest_symlinks_inside_and_outside_package_are_safe_http_errors(self):
        manifest = self.directory / 'example.json'
        original = manifest.read_bytes()
        with tempfile.TemporaryDirectory() as external:
            for target in (self.directory / 'linked-manifest.json', Path(external) / 'example.json'):
                with self.subTest(target=target):
                    target.write_bytes(original)
                    manifest.unlink()
                    manifest.symlink_to(target)
                    try:
                        self.assert_sample_unavailable_without_path_disclosure()
                        self.assertEqual(target.read_bytes(), original)
                    finally:
                        manifest.unlink()
                        manifest.write_bytes(original)

    def test_entire_sample_directory_symlinks_are_refused_for_all_readers(self):
        original_directory = self.directory
        with tempfile.TemporaryDirectory() as external:
            for target in (self.directory.parent / 'relocated-sample', Path(external) / 'sample'):
                with self.subTest(target=target):
                    original_directory.rename(target)
                    original_directory.symlink_to(target, target_is_directory=True)
                    try:
                        self.assert_sample_unavailable_without_path_disclosure()
                        self.assertTrue((target / 'example.json').is_file())
                        self.assertEqual((target / 'original.txt').read_bytes(), b'PUBLIC SYNTHETIC SOURCE\n')
                    finally:
                        original_directory.unlink()
                        target.rename(original_directory)

    def test_malformed_metadata_has_bounded_json_http_errors_and_can_recover(self):
        manifest = self.directory / 'example.json'
        original = manifest.read_bytes()
        wrong_size = json.loads(original)
        wrong_size['artifacts'][0]['size'] = 'PRIVATE SYNTHETIC invalid size'
        cases = {
            'broken-json': b'{"private_path": "' + str(self.directory).encode(),
            'duplicate-key': b'{"version":1,"version":1}',
            'nonfinite-number': b'{"version":NaN}',
            'invalid-utf8': b'\xffPRIVATE SYNTHETIC',
            'wrong-root-type': b'[]',
            'wrong-artifact-type': json.dumps(wrong_size).encode(),
        }
        try:
            for name, body in cases.items():
                with self.subTest(metadata=name):
                    manifest.write_bytes(body)
                    self.assert_sample_unavailable_without_path_disclosure()
                    self.assertEqual(manifest.read_bytes(), body, 'errors must not rebuild metadata')
        finally:
            manifest.write_bytes(original)
        status, _, body = self.request('GET', examples.API)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['status'], 'available')
