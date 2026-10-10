"""TA21 source/asset integrity only. No website, HTTP, server or product JS execution."""
import base64,hashlib,json,re,struct,unittest
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];D=ROOT/'docs/design/technical-atlas/TA-21';NS={'s':'http://www.w3.org/2000/svg'}
def load(n):return json.loads((D/n).read_text())
class FacilityDomainAssetsTests(unittest.TestCase):
 def test_native_composition_and_actual_affine_labels(self):
  m=load('asset-manifest-v1.json');routes=json.loads((ROOT/'web/routes.json').read_text())
  for a in m['assets']:
   b=(ROOT/a['file']).read_bytes();self.assertEqual(len(b),a['bytes']);self.assertEqual(hashlib.sha256(b).hexdigest(),a['sha256']);self.assertEqual(routes['/assets/technical-atlas/'+Path(a['file']).name],a['file'])
  png=(ROOT/m['assets'][0]['file']).read_bytes();self.assertEqual(struct.unpack('>II',png[16:24]),(1536,1024));svg=ET.parse(ROOT/m['assets'][1]['file']).getroot();self.assertEqual(base64.b64decode(svg.find('s:image',NS).get('href').split(',')[1]),png)
  paths=svg.findall('.//s:g[@class="callout"]/s:path',NS);labels=load('labels-v1.json')['labels'];self.assertEqual(len(paths),4)
  for a,p in zip(labels,paths):
   v=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',p.get('d'))));scale,dx,dy=a['affine']
   for k,o in enumerate([dx,dy]):self.assertAlmostEqual(a['source_anchor'][k]*scale+o,a['display_anchor'][k]);self.assertAlmostEqual(v[-2+k],a['display_anchor'][k],places=5)
  self.assertLess((ROOT/m['assets'][3]['file']).stat().st_size,512*1024);scan=load('offline-label-scan-v1.json');self.assertEqual(scan['external'],[]);self.assertEqual(scan['hits'],[]);self.assertEqual(scan['outside'],[]);self.assertTrue(scan['fontsReady'])
 def test_source_identity_homes_actual_surfaces_and_nonphysical_boundary(self):
  p=load('surface-verification-v1.json');self.assertEqual(p['origin'],'https://inresearch.ai');self.assertEqual(p['sourceMeshes'],152);self.assertEqual(p['visibleMeshes'],42);self.assertEqual(len(p['visibleInstances']),12);self.assertEqual(p['errors'],[])
  self.assertEqual(hashlib.sha256((ROOT/'web/components/campus-assembly.js').read_bytes()).hexdigest(),p['source'][0]['sha256'])
  for i in p['sourceInstances']:self.assertEqual(i['position'],i['home'])
  for a in p['anchors']:self.assertLess(a['actual_triangle_distance'],1e-5);self.assertEqual(a['first_visible_hit_instance'],a['instance']);self.assertLess(a['first_hit_distance'],1e-5)
  parts={i['part']for i in p['sourceInstances']if i['id']in p['visibleInstances']};self.assertEqual(parts,{'shell','rack-frame'});self.assertEqual(p['notModeled'],['fire','security'])
  for a in load('technical-sources-v1.json')['sources']:self.assertEqual(hashlib.sha256((ROOT/a['file']).read_bytes()).hexdigest(),a['sha256'])
 def test_explicit_domain_binding_and_confirmed_missing_resource_cleanup(self):
  s=(ROOT/'web/components/technical-atlas.js').read_text();self.assertIn("partId === 'facility-domain' && view === 'domain' ? facilityDomain",s);p=(ROOT/'web/pages/facility-atlas.html').read_text();self.assertIn("'facility-domain',{view:'domain'}",p)
  routes=json.loads((ROOT/'web/routes.json').read_text());self.assertEqual(routes['/facility-atlas.html'],'web/pages/facility-atlas.html')
  for name in ['facility-atlas','server-plan','chip-atlas','rack-atlas','rack-exploded']:
   p=(ROOT/f'web/pages/{name}.html').read_text();urls=re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"',p);self.assertEqual(urls.count('/assets/site-skin.js'),1);self.assertNotIn('/assets/site-shell.js',urls)
   for u in urls:self.assertIn(u,routes);self.assertTrue((ROOT/routes[u]).is_file())
  before=(D/'bom3d-before-v1.html').read_text();now=(ROOT/'web/pages/bom3d.html').read_text();a=before.index('/* ─────────── 建筑');b=before.index(' } // Retained legacy layout;');self.assertIn(before[a:b],now)
  self.assertIn("campusMode && d.key==='facility'",now);self.assertIn("p.kind==='site_right'",now);self.assertIn("['交付模板'",now);self.assertIn("modular-dc'?'微模块是配置与交付模板",now)
  for n in ['site_rights','bom']:
   row=next(s for s in load('technical-sources-v1.json')['sources']if s['file']==f'framework/{n}.json');self.assertEqual(hashlib.sha256((ROOT/row['file']).read_bytes()).hexdigest(),row['sha256'])
