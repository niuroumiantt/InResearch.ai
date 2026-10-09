"""TA19 integrity checks only: no HTTP/server/browser/product JS execution."""
import base64,hashlib,json,math,re,struct,unittest
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
D=ROOT/'docs/design/technical-atlas/TA-19'
NS={'s':'http://www.w3.org/2000/svg'}
class CampusExplodedAtlasAssetsTests(unittest.TestCase):
 def test_native_bytes_editable_labels_and_routes(self):
  m=json.loads((D/'asset-manifest-v1.json').read_text());routes=json.loads((ROOT/'web/routes.json').read_text())
  for a in m['assets']:
   b=(ROOT/a['file']).read_bytes();self.assertEqual(len(b),a['bytes']);self.assertEqual(hashlib.sha256(b).hexdigest(),a['sha256']);self.assertEqual(routes['/assets/technical-atlas/'+Path(a['file']).name],a['file'])
  png=(ROOT/m['assets'][0]['file']).read_bytes();self.assertEqual(struct.unpack('>II',png[16:24]),(1536,1024));self.assertEqual(hashlib.sha256(png).hexdigest(),m['native_original_sha256'])
  svg=ET.parse(ROOT/m['assets'][1]['file']).getroot();self.assertEqual(svg.get('viewBox'),'0 0 1536 1024');self.assertEqual(base64.b64decode(svg.find('s:image',NS).get('href').split(',')[1]),png)
  self.assertEqual(len(svg.findall('.//s:text',NS)),39)
  labels=json.loads((D/'labels-v1.json').read_text())['labels'];paths=svg.findall('.//s:g[@class="callout"]/s:path',NS);self.assertEqual(len(labels),12);self.assertEqual(len(paths),12)
  for a,p in zip(labels,paths):
   scale,dx,dy=a['affine'];self.assertEqual(a['instance'].split('/')[0],'campus')
   for j,t in enumerate([dx,dy]):self.assertAlmostEqual(a['display_anchor'][j],a['source_anchor'][j]*scale+t)
   xy=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',p.get('d'))))
   for x,y in zip(xy[-2:],a['display_anchor']):self.assertAlmostEqual(x,y,places=3)
 def test_native_proof_preserves_geometry_and_rigid_guides(self):
  p=json.loads((D/'native-render-proof-v3.json').read_text());self.assertEqual(p['pixels'],[1536,1024]);self.assertEqual(p['origin'],'https://inresearch.ai');self.assertFalse(p['page_errors']);self.assertEqual(len(p['instances']),32)
  self.assertEqual(len({i['id']for i in p['instances']}),32);self.assertEqual(sum(i['packing']['drawMeshes']for i in p['geometry']),152);self.assertEqual(sum(i['packing']['inputVertices']for i in p['geometry']),194916);self.assertEqual(sum(i['packing']['packedVertices']for i in p['geometry']),194916)
  for source in p['source']:
   f=ROOT/'web/components'/Path(source['url']).name;self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(),source['sha256'])
  byid={i['id']:i for i in p['instances']};self.assertEqual(sum(any(i['axis'])for i in p['instances']),20);self.assertEqual(len(p['guideRecords']),42);self.assertEqual(p['emptyHomeOutlines'],17)
  for g in p['guideRecords']:
   i=byid[g['instance']]
   for j in range(3):self.assertAlmostEqual(g['moved'][j]-g['home'][j],i['axis'][j]);self.assertAlmostEqual(g['home'][j],i['home'][j]+g['local'][j])
  for edge in ['left','top']:self.assertGreater(p['boundsPixels'][edge],50)
  self.assertLess(p['boundsPixels']['right'],1486);self.assertLess(p['boundsPixels']['bottom'],974)
 def test_TA18_factory_and_legacy_geometry_are_preserved(self):
  m=json.loads((D/'asset-manifest-v1.json').read_text());b=m['raw_baseline'];self.assertEqual(hashlib.sha256((ROOT/b['file']).read_bytes()).hexdigest(),b['sha256'])
  old=(ROOT/b['file']).read_text();new=(ROOT/'web/pages/bom3d.html').read_text();start=old.index('/* ─────────── 建筑');end=old.index(' } // Retained legacy layout;')
  self.assertIn(old[start:end],new)
  g=json.loads((D/'generation-native-v3.json').read_text());self.assertEqual(hashlib.sha256((ROOT/'web/components/campus-assembly.js').read_bytes()).hexdigest(),g['TA18_factory_unchanged_sha256'])
  self.assertEqual(json.loads((ROOT/'framework/visual_atlas_migration.json').read_text())['primary_plan']['total'],35)
