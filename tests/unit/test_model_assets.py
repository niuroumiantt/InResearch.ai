"""Real files/processes and authenticated HTTP exercise the shared asset authority."""
import copy
import hashlib
import http.client
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from unittest.mock import patch

from inresearch.materials import model_assets as assets
from inresearch.storage import files
from inresearch.workflow import model_assets as imports
from inresearch.adapters import asset_download
from inresearch.interfaces import auth, http as serve


def glb(document=None):
    document = document or {'asset': {'version': '2.0'}, 'scenes': [{'nodes': []}], 'scene': 0}
    body = json.dumps(document).encode(); body += b' ' * (-len(body) % 4)
    return b'glTF' + struct.pack('<II', 2, 20 + len(body)) + struct.pack('<I', len(body)) + b'JSON' + body


class ModelAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.directory = assets.model_directory(self.root)
        self.directory.mkdir(parents=True)
        self.manifest = self.directory / 'manifest.json'
        files.write_json(self.manifest, {'schema_version': 1, 'models': []})
        self.data = glb()

    def add(self, name='test.glb', data=None):
        return imports.import_candidate(self.root, name, data or self.data, page='rack3d',
                                       source='https://example.test/source', license='CC0')

    def set_status(self, status):
        value = assets.read_manifest(self.root)
        value['models'][0].update(status=status, decision='fixture review of these bytes', fitHeight=5)
        files.write_json(self.manifest, value)

    def test_candidate_review_rejection_and_version_replacement_have_one_authority(self):
        entry = self.add(); self.assertEqual('candidate', entry['status'])
        self.assertEqual([], assets.snapshot(self.root, 'rack3d')['models'])
        self.set_status('adopted'); approved = assets.snapshot(self.root, 'rack3d')
        self.assertEqual(1, len(approved['models']))
        self.assertEqual([], assets.snapshot(self.root, 'bom3d')['models'])
        retry = self.add(); self.assertEqual(('adopted', 5), (retry['status'], retry['fitHeight']))
        old_bytes = self.manifest.read_bytes()
        changed = glb({'asset': {'version': '2.0', 'generator': 'new version'}})
        with self.assertRaisesRegex(ValueError, 'version_conflict'): self.add(data=changed)
        self.assertEqual(old_bytes, self.manifest.read_bytes())
        self.assertEqual(self.data, (self.directory/'test.glb').read_bytes())
        self.add('test_v2.glb', changed)
        self.assertEqual(1, len(assets.snapshot(self.root, 'rack3d')['models']))
        self.set_status('rejected')
        self.assertEqual([], assets.snapshot(self.root, 'rack3d')['models'])
        self.assertEqual(2, len(assets.snapshot(self.root)['models']))
        self.assertNotEqual(approved['revision'], assets.snapshot(self.root)['revision'])

    def test_independent_processes_import_without_lost_updates_or_duplicate_entries(self):
        code = "from pathlib import Path;from inresearch.workflow.model_assets import import_candidate;import sys;import_candidate(sys.argv[1],sys.argv[2],bytes.fromhex(sys.argv[3]),page='rack3d',source='https://example.test/source',license='CC0')"
        jobs = [subprocess.Popen([sys.executable, '-c', code, str(self.root), name, self.data.hex()],
                env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2]/'src')},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE) for name in ['same.glb']*3+['a.glb','b.glb','c.glb']]
        for job in jobs:
            out, err = job.communicate(timeout=20); self.assertEqual(0, job.returncode, err.decode())
        self.assertEqual({'same.glb','a.glb','b.glb','c.glb'}, {m['file'] for m in assets.read_manifest(self.root, verify_files=True)['models']})

    def test_failed_manifest_commit_keeps_complete_file_and_replay_registers_once(self):
        original = self.manifest.read_bytes()
        with patch.object(imports, 'write_json', side_effect=OSError('before manifest commit')):
            with self.assertRaises(OSError): self.add()
        self.assertEqual(original, self.manifest.read_bytes())
        self.assertEqual(self.data, (self.directory/'test.glb').read_bytes())
        self.add(); self.add()
        self.assertEqual(1, len(assets.read_manifest(self.root, verify_files=True)['models']))

    def test_uncertain_manifest_commit_is_visible_and_retry_preserves_decision(self):
        original = files.write_json
        def uncertain(path, value):
            original(path,value); raise files.CommitUncertain()
        with patch.object(imports, 'write_json', side_effect=uncertain):
            with self.assertRaises(files.CommitUncertain): self.add()
        self.assertEqual(1, len(assets.read_manifest(self.root)['models']))
        self.set_status('rejected'); self.assertEqual('rejected',self.add()['status'])

    def test_exclusive_file_publication_is_atomic_and_never_overwrites(self):
        target = self.directory/'test.glb'
        with patch.object(files.os, 'link', side_effect=OSError('publication failed')):
            with self.assertRaises(OSError): self.add()
        self.assertFalse(target.exists()); self.assertEqual([], list(self.directory.glob('*.tmp-*')))
        with patch.object(files, 'sync_directory', side_effect=OSError('directory sync')):
            with self.assertRaises(files.CommitUncertain): self.add()
        self.assertEqual(self.data, target.read_bytes())
        self.add()
        with self.assertRaises(FileExistsError): files.atomic_write(target,b'replacement',exclusive=True)
        self.assertEqual(self.data, target.read_bytes())

    def test_corrupt_or_external_glb_and_unsafe_target_cannot_change_authority(self):
        before = self.manifest.read_bytes()
        bad = [b'glTF', self.data[:-1], b'bad format',
               glb({'asset':{'version':'2.0'},'images':[{'uri':'../private.png'}]}),
               glb({'asset':None}),glb({'asset':{'version':'2.0'},'buffers':[None]})]
        for data in bad:
            with self.subTest(data=data[:25]),self.assertRaises(ValueError):self.add(data=data)
        for name in ['../escape.glb','/tmp/escape.glb','x.html','.hidden.glb']:
            with self.subTest(name=name), self.assertRaises(ValueError):self.add(name)
        target=self.directory/'link.glb'; target.symlink_to(self.root/'outside')
        with self.assertRaisesRegex(ValueError,'unsafe'):self.add('link.glb')
        self.assertEqual(before,self.manifest.read_bytes())

    def test_registered_content_mutation_and_missing_decision_are_rejected(self):
        self.add(); (self.directory/'test.glb').write_bytes(glb({'asset':{'version':'2.0','generator':'changed'}}))
        with self.assertRaisesRegex(ValueError,'content_changed'): assets.read_manifest(self.root,verify_files=True)
        (self.directory/'test.glb').write_bytes(self.data)
        valid=assets.read_manifest(self.root); row=valid['models'][0]
        for change in [{'scale':0},{'scale':True},{'scale':float('nan')},{'fitHeight':-1},
                       {'rotationY':float('inf')},{'position':[0,1]},{'position':[0,True,0]},
                       {'status':'adopted'},{'status':'adopted','decision':None},
                       {'status':'adopted','decision':3},{'license':'CC-BY-NC'},
                       {'source':'javascript:alert(1)'},{'hideRack':'true'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):assets.validate_entry(dict(row,**change))
        files.write_json(self.manifest,dict(valid,models=[row,row]))
        with self.assertRaisesRegex(ValueError,'duplicate'):assets.read_manifest(self.root)

    def test_static_projection_is_manifest_driven_and_does_not_create_missing_files(self):
        from inresearch.interfaces.static import source_path
        source_root=Path(__file__).resolve().parents[2]
        (self.root/'framework').mkdir();(self.root/'framework/storage_contract.json').write_bytes((source_root/'framework/storage_contract.json').read_bytes())
        (self.root/'web/routes.json').write_text('{}')
        self.add()
        self.assertEqual(self.directory/'test.glb',source_path('/assets/models/test.glb',self.root))
        self.assertEqual(self.root/'.not-served',source_path('/assets/models/unregistered.glb',self.root))
        self.assertEqual(self.root/'.not-served',source_path('/assets/models/../test.glb',self.root))
        missing=self.root/'missing'
        with self.assertRaises(OSError):assets.snapshot(missing)
        self.assertFalse(missing.exists())

    def test_gltf_external_paths_cannot_read_outside_extracted_container(self):
        folder=self.root/'download';folder.mkdir(); source=folder/'scene.gltf'
        (self.root/'private.bin').write_bytes(b'private')
        source.write_text(json.dumps({'buffers':[{'uri':'../private.bin'}]}))
        with self.assertRaisesRegex(ValueError,'external_gltf'):asset_download.gltf_to_glb(str(source))

    def test_download_cli_uses_candidate_import_and_retry_preserves_review(self):
        metadata = {'isDownloadable': True, 'name': 'fixture', 'viewerUrl':'https://example.test/source',
                    'license': {'label':'CC0'}, 'user':{'displayName':'fixture author'}}
        def retrieve(url, target):
            with zipfile.ZipFile(target,'w') as archive: archive.writestr('model.glb',self.data)
        def run():
            with patch.object(asset_download,'ROOT',str(self.root)),patch.object(asset_download,'api_get',side_effect=[metadata,{'gltf':{'url':'https://example.test/archive'}}]),patch.object(asset_download.urllib.request,'urlretrieve',side_effect=retrieve),patch.object(sys,'argv',['asset-download','0'*32,'--name','downloaded','--token','fixture']):
                asset_download.main()
        run();self.assertEqual('candidate',assets.read_manifest(self.root)['models'][0]['status'])
        self.set_status('rejected');run();self.assertEqual('rejected',assets.read_manifest(self.root)['models'][0]['status'])

    def test_download_archive_escape_fails_before_extracting_or_registering(self):
        metadata = {'isDownloadable': True, 'name': 'fixture', 'license': {'label':'CC0'}}
        def retrieve(url, target):
            with zipfile.ZipFile(target,'w') as archive: archive.writestr('../escaped.glb',self.data)
        with patch.object(asset_download,'ROOT',str(self.root)),patch.object(asset_download,'api_get',side_effect=[metadata,{'gltf':{'url':'https://example.test/archive'}}]),patch.object(asset_download.urllib.request,'urlretrieve',side_effect=retrieve),patch.object(sys,'argv',['asset-download','0'*32,'--token','fixture']):
            with self.assertRaisesRegex(ValueError,'unsafe_model_archive_path'):asset_download.main()
        self.assertEqual([],assets.read_manifest(self.root)['models'])

    def test_http_identity_boundary_failure_and_valid_scene_selection(self):
        self.add(); self.set_status('adopted')
        with patch.object(serve,'ROOT',self.root),patch.object(serve,'AUTH_ON',True),patch.object(auth,'session_user',return_value='member') as user,patch.object(auth,'user_role',return_value='member') as role:
            server=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler)
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
            def get(path):
                con=http.client.HTTPConnection(*server.server_address,timeout=5)
                try:con.request('GET',path);r=con.getresponse();return r.status,r.read()
                finally:con.close()
            try:
                code,body=get('/api/model-assets?page=rack3d');self.assertEqual(200,code);self.assertEqual(1,len(json.loads(body)['models']))
                self.assertEqual(400,get('/api/model-assets?page=other')[0])
                self.assertEqual(400,get('/api/model-assets?page=rack3d&page=bom3d')[0])
                self.manifest.write_text('{broken');self.assertEqual(503,get('/api/model-assets')[0])
                # 公开只读（2026-09-28）：3D 页是公开页，匿名 reader 与实习生拿到的登记答案与成员相同；不公开的接口仍分别 401 / 403。
                user.return_value=None;self.assertEqual(503,get('/api/model-assets')[0]);self.assertEqual(401,get('/api/supply')[0])
                user.return_value='intern';role.return_value='intern';self.assertEqual(503,get('/api/model-assets')[0]);self.assertEqual(403,get('/api/supply')[0])
            finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
