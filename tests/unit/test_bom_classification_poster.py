"""The poster must retain the actual BOM hierarchy and a portable, editable master."""
import base64
import hashlib
import json
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
NS = {'s': 'http://www.w3.org/2000/svg'}


class ClassificationPosterTests(unittest.TestCase):
    def test_current_categories_and_subcategories_are_in_one_image(self):
        bom = json.loads((ROOT/'framework/bom.json').read_text())
        svg = ET.parse(ROOT/'web/assets/bom-classification/overview-v1.svg').getroot()
        for sid, system in bom['systems'].items():
            label = svg.find(f".//s:g[@id='category-{sid}']", NS) if not system['parent'] else svg.find(f".//s:text[@data-system-id='{sid}']", NS)
            if sid in ['memory', 'storage']:
                self.assertIn(system['name'].replace('IT · ', ''), ''.join(svg.itertext()))
            else:
                self.assertIsNotNone(label, sid)
                self.assertIn(system['name'].replace('IT · ', ''), ''.join(label.itertext()))
        self.assertIn(' / '.join(g['name'] for g in bom['systems']['compute']['processor_groups']), ''.join(svg.itertext()))
        self.assertIn('配套：服务器、整机柜、BMC', ''.join(svg.itertext()))

    def test_self_contained_master_and_public_whole_image(self):
        assets = ROOT/'web/assets/bom-classification'
        svg = ET.parse(assets/'overview-v1.svg').getroot()
        native = (assets/'cutaway-v1.png').read_bytes()
        self.assertEqual(base64.b64decode(svg.find('s:image', NS).get('href').split(',')[1]), native)
        self.assertEqual([1536, 1800], list(struct.unpack('>II', (assets/'overview-v1.png').read_bytes()[16:24])))
        self.assertIn('data:font/woff2;base64,', svg.find('s:style', NS).text)
        self.assertIn('SIL OPEN FONT LICENSE', svg.find("s:metadata[@id='embedded-font-licenses']", NS).text)
        manifest = json.loads((ROOT/'docs/design/bom-classification/manifest-v1.json').read_text())
        for name, digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest)
        routes = json.loads((ROOT/'web/routes.json').read_text())
        for name in ['overview-v1.png', 'overview-v1.svg']:
            self.assertEqual(routes['/assets/bom-classification/'+name], 'web/assets/bom-classification/'+name)


if __name__ == '__main__':
    unittest.main()
