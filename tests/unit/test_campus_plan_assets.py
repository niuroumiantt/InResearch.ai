"""TA20 static integrity only: no HTTP/server/browser/productJS execution."""
import base64,hashlib,json,math,re,struct,unittest
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];D=ROOT/'docs/design/technical-atlas/TA-20';NS={'s':'http://www.w3.org/2000/svg'}
def load(name):return json.loads((D/name).read_text())
class CampusPlanAtlasAssetsTests(unittest.TestCase):
 def test_native_bytes_editable_labels_and_routes(self):
  m=load('asset-manifest-v1.json');routes=json.loads((ROOT/'web/routes.json').read_text())
  for a in m['assets']:
   b=(ROOT/a['file']).read_bytes();self.assertEqual(len(b),a['bytes']);self.assertEqual(hashlib.sha256(b).hexdigest(),a['sha256']);self.assertEqual(routes['/assets/technical-atlas/'+Path(a['file']).name],a['file'])
  png=(ROOT/m['assets'][0]['file']).read_bytes();self.assertEqual(struct.unpack('>II',png[16:24]),(1536,1024));self.assertEqual(hashlib.sha256(png).hexdigest(),m['native_original_sha256'])
  svg=ET.parse(ROOT/m['assets'][1]['file']).getroot();self.assertEqual(svg.get('viewBox'),'0 0 1536 1024');self.assertEqual(base64.b64decode(svg.find('s:image',NS).get('href').split(',')[1]),png)
  self.assertEqual(len(svg.findall('.//s:text',NS)),39);labels=load('labels-v1.json')['labels'];paths=svg.findall('.//s:g[@class="callout"]/s:path',NS);self.assertEqual(len(paths),12)
  for a,p in zip(labels,paths):
   scale,dx,dy=a['affine'];xy=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',p.get('d'))))
   for k,offset in enumerate([dx,dy]):self.assertAlmostEqual(a['source_anchor'][k]*scale+offset,a['display_anchor'][k]);self.assertAlmostEqual(xy[-2+k],a['display_anchor'][k],places=3)
  self.assertLess((ROOT/m['assets'][3]['file']).stat().st_size,512*1024)
 def test_strict_orthographic_geometry_and_actual_homes(self):
  p=load('native-render-proof-v2.json');self.assertEqual(p['pixels'],[1536,1024]);self.assertEqual(p['origin'],'https://inresearch.ai');self.assertEqual(p['page_errors'],[]);c=p['camera'];self.assertEqual(c['type'],'OrthographicCamera')
  for x,y in zip(c['direction'],[0,-1,0]):self.assertAlmostEqual(x,y,places=12)
  self.assertEqual(c['up'],[0,0,-1]);self.assertEqual(len(p['instances']),32);self.assertEqual(len(set(i['id']for i in p['instances'])),32)
  for i in p['instances']:self.assertEqual(i['position'],i['home'])
  self.assertEqual(sum(i['packing']['drawMeshes']for i in p['geometry']),152);self.assertEqual(sum(i['packing']['packedVertices']for i in p['geometry']),194916)
  self.assertEqual(set(p['omittedInstances']),{'campus/building-frame','campus/retained-roof-sections','campus/overhead-service-trays'});self.assertEqual(p['visiblePhysicalMeshes'],142)
  tl,tr,br,bl=p['orthographicRectangle'];self.assertAlmostEqual(tl[1],tr[1]);self.assertAlmostEqual(bl[1],br[1]);self.assertAlmostEqual(tl[0],bl[0]);self.assertAlmostEqual(tr[0],br[0]);self.assertAlmostEqual(tr[0]-tl[0],br[0]-bl[0])
  byid={i['id']:i for i in p['instances']}
  for a in load('labels-v1.json')['labels']:
   world=[a['local'][n]+byid[a['instance']]['home'][n]for n in range(3)];self.assertEqual(world,a['world']);q=[world[n]-c['target'][n]for n in range(3)];dot=lambda v:sum(q[n]*v[n]for n in range(3));pixel=[(dot(c['screenRight'])-c['left'])/(c['right']-c['left'])*1536,(c['top']-dot(c['screenUp']))/(c['top']-c['bottom'])*1024]
   for x,y in zip(pixel,a['source_anchor']):self.assertAlmostEqual(x,y,places=8)
  current={a['num']:a for a in load('labels-v1.json')['labels']};self.assertEqual(current['05']['local'],[-1,3.3125,0]);self.assertEqual(next(a for a in p['anchors']if a['num']=='05')['local'],[-1,3.3,0]);self.assertEqual([n for n,a in current.items()if a['anchor_role'].startswith('derived')],['10','11'])
 def test_projection_not_new_physical_topology(self):
  p=load('native-render-proof-v2.json');self.assertEqual(len(p['sourceColumnFootprints']),10);self.assertTrue(all(not f['physical']for f in p['sourceColumnFootprints']));self.assertEqual({tuple(f['center'])for f in p['sourceColumnFootprints']},{(x,.59,z)for x in[-15.6,-8,0,8,15.6]for z in[-10.6,10.6]})
  svg=ET.parse(ROOT/'web/assets/technical-atlas/campus-plan-v1.svg').getroot();projections=svg.findall('.//s:path[@class="tray-projection"]',NS);self.assertEqual(len(projections),4);self.assertTrue(all(x.get('data-physical')=='false'and x.get('data-source-instance')=='campus/overhead-service-trays'for x in projections))
  scan=load('offline-label-scan-v1.json');self.assertEqual(scan['external'],[]);self.assertEqual(scan['hits'],[]);self.assertEqual(scan['outside'],[]);self.assertTrue(scan['fontsReady'])
 def test_existing_interactions_and_default_art_preserved(self):
  m=load('asset-manifest-v1.json');old=(ROOT/m['raw_baseline']['file']).read_text();new=(ROOT/'web/pages/bom3d.html').read_text();self.assertEqual(new.replace('<a href="/campus-plan.html">园区正交平面图</a> · ',''),old);self.assertEqual(hashlib.sha256((ROOT/'web/components/campus-assembly.js').read_bytes()).hexdigest(),load('generation-native-v2.json')['TA18_factory_unchanged_sha256'])
  src=(ROOT/'web/components/technical-atlas.js').read_text();self.assertIn("partId === 'campus-overview' && view === 'plan' ? campusPlan",src);self.assertIn("partId === 'server' && view === 'plan' ? serverPlan",src);page=(ROOT/'web/pages/campus-plan.html').read_text();self.assertIn("'campus-overview',{view:'plan'}",page);self.assertIn('main>nav{',page);self.assertNotIn('}nav{',page);self.assertIn('/bom3d.html?x=70',page)
  routes=json.loads((ROOT/'web/routes.json').read_text());self.assertEqual(routes['/campus-plan.html'],'web/pages/campus-plan.html');self.assertEqual(json.loads((ROOT/'framework/visual_atlas_migration.json').read_text())['primary_plan']['total'],35)

 def test_new_page_declared_resources_have_actual_routes(self):
  page=(ROOT/"web/pages/campus-plan.html").read_text();routes=json.loads((ROOT/"web/routes.json").read_text());declared=re.findall(r"<(?:script|link)[^>]+(?:src|href)=\"([^\"]+)\"",page)
  self.assertEqual(declared.count("/assets/site-skin.js"),1);self.assertNotIn("/assets/site-shell.js",declared)
  for url in declared:
   self.assertIn(url,routes);self.assertTrue((ROOT/routes[url]).is_file())
