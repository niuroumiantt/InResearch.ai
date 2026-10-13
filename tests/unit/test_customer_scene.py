"""Scene delivery requires adoption, exact grant and unchanged reviewed bytes together."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from inresearch.interfaces.customer_scene import model_assets

ROOT = Path(__file__).resolve().parents[2]
SCENE_APP_ASSETS = tuple('/assets/' + name + '.js' for name in (
    'campus-assembly', 'campus-exploded-assembly', 'chip-package-assembly', 'model-assets', 'panel-source-viewer',
    'part-dossier', 'part-inspector', 'rack-assembly', 'rack-exploded-view', 'scene-atlas', 'scene-data',
    'scene-motion', 'scene-navigation', 'scene-picking', 'scene-resources', 'scene-view', 'series-summary',
    'server-assembly', 'system-atlas', 'technical-atlas'))
SCENE_VENDOR_ASSETS = tuple('/assets/vendor/' + name + '.js' for name in (
    'BufferGeometryUtils', 'CopyShader', 'EffectComposer', 'GLTFLoader', 'MaskPass', 'OrbitControls',
    'OutputPass', 'OutputShader', 'Pass', 'RenderPass', 'ShaderPass', 'three.module'))
SCENE_IMAGES = tuple('/assets/technical-atlas/' + stem + suffix
                     for stem in ('campus-overview-v1', 'campus-exploded-v1')
                     for suffix in ('.svg', '-preview.svg', '.png')) + tuple(
    path for stem in ('server_nvme', 'server_gpu', 'server_storage', 'switch_tor', 'switch_ib')
    for path in ('/assets/panels/' + stem + '.png', '/assets/panels/display/' + stem + '-contain.svg'))
SCENE_ASSETS = SCENE_APP_ASSETS + SCENE_VENDOR_ASSETS + SCENE_IMAGES


class CustomerSceneProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.models = self.root / 'web/assets/models'; self.models.mkdir(parents=True)
        (self.root / 'framework').mkdir()
        document = {'asset': {'version': '2.0'}, 'scenes': [{'nodes': []}], 'scene': 0}
        body = json.dumps(document).encode(); body += b' ' * (-len(body) % 4)
        self.data = b'glTF' + struct.pack('<II', 2, 20 + len(body)) + struct.pack('<I', len(body)) + b'JSON' + body
        (self.models / 'reviewed.glb').write_bytes(self.data)
        self.row = {'file': 'reviewed.glb', 'page': 'rack3d', 'status': 'adopted',
                    'sha256': hashlib.sha256(self.data).hexdigest(), 'source': 'https://example.org/model',
                    'license': 'CC0', 'decision': 'private-sentinel-review', 'position': [1, 2, 3],
                    'scale': 'auto', 'fitHeight': 5, 'rotationY': 0, 'hideRack': True}
        self.grant(['/assets/models/reviewed.glb'])
        self.save()

    def grant(self, paths):
        (self.root / 'framework/site_navigation.json').write_text(
            json.dumps({'access': {'customer': {'assets': paths}}}))

    def save(self):
        (self.models / 'manifest.json').write_text(json.dumps({'schema_version': 1, 'models': [self.row]}))

    def test_only_published_loader_fields_preserve_content_identity_placement_and_license(self):
        result = model_assets(self.root, 'rack3d')
        self.assertEqual(len(result['models']), 1)
        public = result['models'][0]
        self.assertEqual(set(public), {'file', 'page', 'status', 'sha256', 'source', 'license', 'position',
                                      'scale', 'fitHeight', 'rotationY', 'hideRack', 'url'})
        for key in public.keys() - {'url'}: self.assertEqual(public[key], self.row[key])
        self.assertEqual(public['url'], '/assets/models/reviewed.glb')
        self.assertEqual((self.models / 'reviewed.glb').read_bytes(), self.data)

    def test_future_nested_review_and_machine_metadata_do_not_escape_or_change_public_revision(self):
        expected = model_assets(self.root, 'rack3d')
        secret = '/srv/private-sentinel/model-original.glb'
        self.row.update(note=secret, provenance={'original_path': secret},
                        metadata={'review': {'operator': secret}}, execution_host=secret)
        self.save()
        result = model_assets(self.root, 'rack3d')
        self.assertEqual(result, expected)
        self.assertNotIn('private-sentinel', json.dumps(result))

    def test_rejected_candidate_wrong_scene_and_ungranted_adopted_models_never_distribute(self):
        for status in ('rejected', 'candidate'):
            self.row['status'] = status; self.save()
            self.assertEqual(model_assets(self.root, 'rack3d')['models'], [])
        self.row['status'] = 'adopted'; self.save()
        self.assertEqual(model_assets(self.root, 'bom3d')['models'], [])
        for paths in ([], ['/assets/models/']):
            self.grant(paths)
            self.assertEqual(model_assets(self.root, 'rack3d')['models'], [])

    def test_changed_bytes_or_credential_source_fail_closed(self):
        (self.models / 'reviewed.glb').write_bytes(self.data + b'changed')
        with self.assertRaises(ValueError): model_assets(self.root, 'rack3d')
        (self.models / 'reviewed.glb').write_bytes(self.data)
        for source in ('https://private-sentinel:password@example.org/model',
                       'https://example.org/model?access_token=private-sentinel'):
            self.row['source'] = source; self.save()
            with self.assertRaises(ValueError): model_assets(self.root, 'rack3d')

    def test_one_explicit_scene_is_required_and_actual_rejected_asset_is_not_published(self):
        for page in (None, '', 'all', 'other'):
            with self.assertRaises(ValueError): model_assets(self.root, page)
        for page in ('bom3d', 'rack3d'):
            self.assertEqual(model_assets(ROOT, page)['models'], [])

    def test_exact_scene_resources_are_registered_without_originals_hdr_or_private_modules(self):
        access = json.loads((ROOT / 'framework/site_navigation.json').read_text())['access']['customer']
        routes = json.loads((ROOT / 'web/routes.json').read_text())
        self.assertEqual((len(SCENE_APP_ASSETS), len(SCENE_VENDOR_ASSETS), len(SCENE_IMAGES)), (20, 12, 16))
        for path in SCENE_ASSETS:
            self.assertIn(path, access['assets'])
            self.assertTrue((ROOT / routes[path]).is_file())
        self.assertFalse(any(path.endswith('/') for path in access['assets']))
        for path in ('/assets/models/server_v2_console.glb', '/assets/models/manifest.json',
                     '/assets/hdri/studio.exr', '/assets/hdri/warehouse.exr', '/assets/research-graph.js',
                     '/assets/object-network.js'):
            self.assertNotIn(path, access['assets'])
        pure = (ROOT / routes['/assets/scene-navigation.js']).read_text()
        self.assertNotIn('fetch(', pure)
        self.assertNotIn('import ', pure)
