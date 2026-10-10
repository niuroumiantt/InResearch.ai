"""No-HTTP original conservation and source-display identity checks.
These are not WebGL, browser, appearance or upstream provenance verification.
"""
import base64,hashlib,json,struct,unittest
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
class PanelSourceAssetTests(unittest.TestCase):
 def test_five_originals_and_linked_svg_conserve_full_native_image(self):
  ns={'s':'http://www.w3.org/2000/svg'}
  for n in range(30,35):
   d=ROOT/f'docs/design/technical-atlas/TA-{n}'
   baseline=json.loads((d/'baseline-v1.json').read_text())
   record=json.loads((d/'acceptance-v1.json').read_text())
   raw=(ROOT/record['original']).read_bytes()
   with self.subTest(figure=n):
    self.assertEqual(hashlib.sha256(raw).hexdigest(),baseline['provenance']['sha256'])
    self.assertEqual(struct.unpack('>II',raw[16:24]),tuple(record['source_pixels']))
    svg=ET.parse(ROOT/record['display']).getroot()
    image=svg.find('s:image',ns)
    self.assertEqual(base64.b64decode(image.get('href').split(',',1)[1]),raw)
    self.assertEqual(image.get('preserveAspectRatio'),'xMidYMid meet')
    self.assertEqual([float(x) for x in svg.get('viewBox').split()], [0,0,2300,735 if n<=32 else 399])
    meta=json.loads(svg.find('s:metadata',ns).text)
    self.assertEqual(meta['figure_id'],f'TA-{n}')
    self.assertEqual(meta['source_sha256'],hashlib.sha256(raw).hexdigest())
    self.assertTrue(meta['not_static_master_or_cad'])
    routes=json.loads((ROOT/'web/routes.json').read_text())
    self.assertEqual(routes['/assets/panels/display/'+Path(record['display']).name],record['display'])

 def test_defaults_keep_all_adopted_geometry_and_render_recipe(self):
  baseline=json.loads((ROOT/'docs/design/technical-atlas/TA-29/baseline-v1.json').read_text())
  for row in baseline['unchanged_reuse']:
   self.assertEqual(hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest(),row['sha256'])
  for n in [11,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28]:
   record=json.loads((ROOT/f'docs/design/technical-atlas/TA-{n}/acceptance-v1.json').read_text())
   for row in record['artifacts']:
    self.assertEqual(hashlib.sha256((ROOT/row['file']).read_bytes()).hexdigest(),row['sha256'])

 def test_review_is_per_source_and_does_not_claim_public_acceptance(self):
  q=json.loads((ROOT/'framework/visual_atlas_migration.json').read_text())
  for row in q['items']:
   if row['id'] not in {f'TA-{n}' for n in range(30,35)}:continue
   record=json.loads((ROOT/row['acceptance_record']).read_text())
   self.assertEqual(record['scope'],'retained_source_display_only')
   self.assertEqual(record['figure_id'],row['id'])
   self.assertEqual(record['object_id'],row['object_id'])
   self.assertFalse(record['source_display']['not_static_master_or_cad'] is False)
   if row['status']=='review':
    self.assertEqual(record['publication_status'],'not_published')
    self.assertFalse(record['actual_new_public_execution'])
   elif row['status'] in ('accepted','published'):
    self.assertTrue(record['actual_new_public_execution'])
    self.assertTrue(record['actual_public_receipt'])
if __name__=='__main__':unittest.main()
