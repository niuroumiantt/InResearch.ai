"""TA16 asset identity/byte and topology contracts. Visual and web review remain separate."""
import base64
import hashlib
import json
from pathlib import Path
import re
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
NS = {'s': 'http://www.w3.org/2000/svg'}
LEGACY = {'shell', 'fire', 'security', 'rack-frame', 'server', 'gpu', 'cpu', 'hbm', 'dram', 'ssd', 'nic', 'coldplate', 'psu', 'server-fan'}


def system_metadata():
    source = (ROOT / 'web/components/system-atlas.js').read_text()
    return json.loads(source[source.index('{'):source.rindex('}') + 1])


class SystemAtlasAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bom = json.loads((ROOT / 'framework/bom.json').read_text())
        cls.items = system_metadata()
        cls.routes = json.loads((ROOT / 'web/routes.json').read_text())
        cls.manifest = json.loads((ROOT / 'docs/design/technical-atlas/TA-16/candidate-asset-manifest-v2.json').read_text())

    def test_category_scope_excludes_software_archetypes_and_legacy_bindings(self):
        physical = {p['id'] for p in self.bom['parts'] if p.get('kind', 'part') == 'part'}
        self.assertEqual(len(physical), 61)
        self.assertEqual(set(self.items), physical - LEGACY)
        self.assertEqual(len(self.items), 47)
        self.assertFalse(set(self.items) & LEGACY)
        self.assertNotIn('dcim', self.items)
        self.assertNotIn('modular-dc', self.items)

    def test_registered_chain_topology_keeps_control_separate(self):
        systems = self.bom['systems']
        self.assertEqual(len([s for s in systems.values() if not s.get('parent')]), 5)
        leaves = [(sid, s) for sid, s in systems.items() if not any(x.get('parent') == sid for x in systems.values())]
        chains = [(sid, chain) for sid, s in leaves for chain in s['chains']]
        self.assertEqual(len(chains), 17)
        physical = [p for p in self.bom['parts'] if p.get('kind', 'part') == 'part']
        active = {(p['system'], p['chain']) for p in physical}
        self.assertEqual(len(active), 16)
        self.assertFalse(any(sid == 'control' for sid, chain in active))
        self.assertTrue(active <= set(chains))
        self.assertEqual(len(json.loads((ROOT / 'framework/site_rights.json').read_text())['rights']), 6)

    def test_manifest_covers_all_system_only_artwork_once(self):
        reference = self.manifest['style_reference']
        self.assertEqual(reference['id'], 'R1')
        self.assertFalse(reference['technical_evidence'])
        self.assertEqual(hashlib.sha256((ROOT / reference['file']).read_bytes()).hexdigest(), reference['sha256'])
        ids = [x['id'] for x in self.manifest['items']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(self.items), 'all47 detailed candidates must be registered; partial draft does not pass')
        for row in self.manifest['items']:
            self.assertTrue(row['sources'], row['id'] + ': missing category source')
            self.assertTrue(row['unknown'], row['id'] + ': unknown boundaries required')
            self.assertTrue((ROOT / 'docs/design/technical-atlas/TA-16/categories' / (row['id'] + '-prompt.txt')).is_file())
            self.assertTrue((ROOT / 'docs/design/technical-atlas/TA-16/categories' / (row['id'] + '-generation.json')).is_file())

    def test_master_full_svg_and_lightweight_labels_have_correct_identity(self):
        by_id = {row['id']: row for row in self.manifest['items']}
        for pid, item in self.items.items():
            row = by_id[pid]
            paths = {}
            for field in ('image', 'preview', 'master', 'tile'):
                public = item[field]
                self.assertIn(public, self.routes)
                paths[field] = ROOT / self.routes[public]
                self.assertTrue(paths[field].is_file(), pid + ': ' + public)
            native = paths['master'].read_bytes()
            self.assertEqual(hashlib.sha256(native).hexdigest(), row['native']['sha256'], pid)
            self.assertEqual(struct.unpack('>II', native[16:24]), (1536, 1024))
            self.assertEqual(struct.unpack('>II', paths['tile'].read_bytes()[16:24]), (480, 320))
            full_text, preview_text = paths['image'].read_text(), paths['preview'].read_text()
            self.assertEqual(hashlib.sha256(full_text.encode()).hexdigest(), row['svg']['sha256'])
            full, preview = ET.fromstring(full_text), ET.fromstring(preview_text)
            self.assertEqual(full.get('viewBox'), '0 0 1536 1024')
            actual_title = full.find("s:g[@id='editable-labels']/s:text[@class='title']", NS)
            self.assertEqual(''.join(actual_title.itertext()), item['title'], pid + ': visible title identity')
            images = full.findall('s:image', NS)
            self.assertEqual(len(images), 1)
            self.assertEqual(base64.b64decode(images[0].get('href').split(',', 1)[1]), native)
            labels = [e.text for e in full.findall("s:g[@id='editable-labels']/s:text[@class='label']", NS)]
            self.assertEqual(len(labels), len(item['labels']))
            for text, label in zip(labels, item['labels']):
                self.assertTrue(text.endswith(label), pid + ': label identity')
            self.assertLess(paths['preview'].stat().st_size, 512 * 1024)
            # Display derivative may compress pixels, but must preserve every editable label/path.
            normalize = lambda s: re.sub(r'data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=]+', 'DISPLAY_IMAGE', s)
            self.assertEqual(normalize(full_text), normalize(preview_text), pid)
            self.assertEqual(item['note'], ' '.join(row['notes']))
            self.assertTrue(item['note'])


if __name__ == '__main__':
    unittest.main()
