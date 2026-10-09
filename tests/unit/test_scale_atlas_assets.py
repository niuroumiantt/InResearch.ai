"""TA17 explicit category reuse and scale inventory; visual/runtime checks are separate."""
import base64
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
NS={'s':'http://www.w3.org/2000/svg'}

class ScaleAtlasAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bom=json.loads((ROOT/'framework/bom.json').read_text())
        cls.manifest=json.loads((ROOT/'docs/design/technical-atlas/TA-17/scale-asset-bindings-v1.json').read_text())
        cls.rows=cls.manifest['items']
        cls.routes=json.loads((ROOT/'web/routes.json').read_text())

    def test_every_physical_category_has_exactly_its_registered_scale_and_assets(self):
        physical={p['id']:p for p in self.bom['parts'] if p.get('kind','part')=='part'}
        self.assertEqual(len(self.rows),61)
        self.assertEqual(len({r['id'] for r in self.rows}),61)
        self.assertEqual({r['id'] for r in self.rows},set(physical))
        self.assertEqual(Counter(r['scale'] for r in self.rows),{'S1':12,'S2':3,'S3':12,'S4':13,'S5':21})
        for r in self.rows:
            self.assertEqual((r['scale'],r['system']),(physical[r['id']]['scale'],physical[r['id']]['system']))
            for key in ('image','preview','master','thumbnail'):
                raw=(ROOT/self.routes[r[key]]).read_bytes()
                self.assertEqual(len(raw),r[key+'_bytes'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(),r[key+'_sha256'])
        self.assertEqual(len({r['master_sha256'] for r in self.rows}),60,'CPU and DRAM intentionally share one assembly context')
        self.assertFalse({'dcim','modular-dc'} & {r['id'] for r in self.rows})

    def test_reused47_are_identical_to_adopted_system_library_and_unknown_boundaries(self):
        source=(ROOT/'web/components/system-atlas.js').read_text()
        items=json.loads(source[source.index('{'):source.rindex('}')+1])
        by_id={r['id']:r for r in self.rows}
        self.assertEqual(len(items),47)
        for pid,item in items.items():
            r=by_id[pid]
            self.assertEqual(r['figure_id'],item['id'])
            self.assertEqual(r['title'],item['title'])
            self.assertEqual(r['note'],item['note'])
            for key in ('image','preview','master'):
                self.assertEqual(r[key],item[key])
            self.assertTrue(item['note'])

    def test_new_overview_reuses_original_pngs_and_embeds_native_composition(self):
        scope=ROOT/'docs/design/technical-atlas/TA-17'
        composition=json.loads((scope/'overview-composition-v1.json').read_text())
        self.assertEqual(composition['style_reference']['id'],'R1')
        self.assertEqual(hashlib.sha256((ROOT/composition['style_reference']['file']).read_bytes()).hexdigest(),composition['style_reference']['sha256'])
        original=ET.parse(scope/'scale-overview-composition-source-v1.svg').getroot()
        images=original.findall('s:image',NS)
        self.assertEqual(len(images),5)
        for image,row in zip(images,composition['references']):
            raw=(ROOT/row['path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            self.assertEqual(base64.b64decode(image.get('href').split(',',1)[1]),raw)
            self.assertEqual(tuple(map(float,[image.get(k) for k in ('x','y','width','height')])),tuple(row['placement']))
        native=(ROOT/'web/assets/technical-atlas/scale-overview-v1.png').read_bytes()
        self.assertEqual(struct.unpack('>II',native[16:24]),(1536,1024))
        full=ET.parse(ROOT/'web/assets/technical-atlas/scale-overview-v1.svg').getroot()
        self.assertEqual(full.get('viewBox'),'0 0 1536 1024')
        self.assertEqual(base64.b64decode(full.find('s:image',NS).get('href').split(',',1)[1]),native)
        texts=full.findall("s:g[@id='editable-labels']/s:text",NS)
        self.assertEqual(len(texts),14)
        alltext=' '.join(''.join(x.itertext()) for x in texts)
        for sid in ('S1','S2','S3','S4','S5'):
            self.assertIn(sid,alltext)
        self.assertIn('不证明真实尺寸',alltext)
        self.assertIn('不画成物理零件',alltext)

if __name__=='__main__':unittest.main()
