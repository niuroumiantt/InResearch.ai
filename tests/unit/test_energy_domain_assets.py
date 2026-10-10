"""TA22/23 source/asset contracts only; zero website/HTTP/server/product JS execution."""
import base64,hashlib,json,re,struct,unittest
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
NS={'s':'http://www.w3.org/2000/svg'}
def sha(b):return hashlib.sha256(b).hexdigest()
def load(d,n):return json.loads((d/n).read_text())
def points(p):return [tuple(map(float,v))for v in re.findall(r'(-?[\d.]+),(-?[\d.]+)',p)]
def on_segment(p,a,b):return abs((p[0]-a[0])*(b[1]-a[1])-(p[1]-a[1])*(b[0]-a[0]))<1e-6 and all(min(a[k],b[k])-1e-6<=p[k]<=max(a[k],b[k])+1e-6 for k in [0,1])
class EnergyDomainAssetsTests(unittest.TestCase):
 def test_native_original_affine_label_and_complete_offline_layout(self):
  routes=json.loads((ROOT/'web/routes.json').read_text())
  for n in ['TA-22','TA-23']:
   with self.subTest(figure=n):
    d=ROOT/'docs/design/technical-atlas'/n;m=load(d,'asset-manifest-v1.json')
    for a in m['assets']:
     b=(ROOT/('docs/design/technical-atlas/bom-source-20260928.json' if a['file']=='framework/bom.json' else a['file'])).read_bytes();self.assertEqual(len(b),a['bytes']);self.assertEqual(sha(b),a['sha256']);self.assertEqual(routes['/assets/technical-atlas/'+Path(a['file']).name],a['file'])
    png=(ROOT/m['assets'][0]['file']).read_bytes();self.assertEqual(struct.unpack('>II',png[16:24]),(1536,1024));s=ET.parse(ROOT/m['assets'][1]['file']).getroot();self.assertEqual(base64.b64decode(s.find('s:image',NS).get('href').split(',')[1]),png)
    cm=load(d,'component-manifest-v1.json');self.assertFalse(cm['originals_modified']);self.assertFalse(cm['public_or_local_product_access'])
    for c in cm['components']:
     b=(ROOT/'web/assets/technical-atlas'/c['file']).read_bytes();self.assertEqual(sha(b),c['sha256']);self.assertEqual(len(b),c['bytes']);self.assertLess(c['affine']['scale'],1)
    paths={p.get('data-label'):p.find('s:path',NS)for p in s.findall('.//s:g[@class="callout"]',NS)};labels=load(d,'labels-v1.json')['labels'];self.assertEqual(len(paths),6);self.assertEqual(len(labels),6)
    for a in labels:
     e=points(paths[a['number']].get('d'))[-1]
     for k in [0,1]:
      v=a['source_anchor'][k]*a['affine']['scale']+a['affine']['translate'][k];self.assertAlmostEqual(v,a['display_anchor'][k]);self.assertAlmostEqual(v,e[k],places=3)
    self.assertLess((ROOT/m['assets'][3]['file']).stat().st_size,512*1024)
    preview=ET.parse(ROOT/m['assets'][3]['file']).getroot();self.assertEqual(len(preview.findall('.//s:text',NS)),len(s.findall('.//s:text',NS)))
    scan=load(d,'offline-label-scan-v1.json');self.assertEqual(scan['external'],[]);self.assertTrue(scan['fontsReady']);self.assertEqual(scan['hits'],[]);self.assertEqual(scan['outside'],[])
    for i,t in enumerate(scan['texts']):
     for q in scan['texts'][i+1:]:self.assertFalse(max(t['x'],q['x'])<min(t['x']+t['w'],q['x']+q['w']) and max(t['y'],q['y'])<min(t['y']+t['h'],q['y']+q['h']),(n,t['text'],q['text']))
 def test_actual_UPS_junctions_and_two_disjoint_closed_fluid_cycles(self):
  svg=ET.parse(ROOT/'web/assets/technical-atlas/power-domain-v1.svg').getroot();f={p.get('data-flow'):points(p.get('d'))for p in svg.findall('.//s:path[@data-flow]',NS)}
  self.assertEqual(len(f),10)
  # Read actual shape bounds and path endpoints, including branch joins lying inside normal segments.
  rects=[r for r in svg.findall('.//s:rect',NS)if r.get('x')];self.assertEqual(len(rects),3)
  rr=[{k:float(r.get(k))for k in ['x','y','width','height']}for r in rects];r1,r2,bat=rr
  for flow,r,startside,endside in [('UPS-normal-1',r1,None,'left'),('UPS-normal-2',r1,'right',None),('UPS-normal-3',r2,'right',None)]:
   if startside:self.assertEqual(f[flow][0][0],r['x']+r['width']);self.assertTrue(r['y']<=f[flow][0][1]<=r['y']+r['height'])
   if endside:self.assertEqual(f[flow][-1][0],r['x']);self.assertTrue(r['y']<=f[flow][-1][1]<=r['y']+r['height'])
  self.assertEqual(f['UPS-normal-2'][-1][0],r2['x'])
  self.assertTrue(on_segment(f['UPS-bypass'][0],*f['UPS-normal-1']));self.assertTrue(on_segment(f['UPS-bypass'][-1],*f['UPS-normal-3']));self.assertTrue(on_segment(f['UPS-battery'][-1],*f['UPS-normal-2']))
  self.assertEqual(f['UPS-battery'][0][1],bat['y']);self.assertTrue(bat['x']<=f['UPS-battery'][0][0]<=bat['x']+bat['width'])
  dots={(float(c.get('cx')),float(c.get('cy')))for c in svg.findall('.//s:circle',NS)}
  for p in [f['UPS-bypass'][0],f['UPS-bypass'][-1],f['UPS-battery'][-1]]:self.assertIn(p,dots)
  # Main-line arrows intentionally do not connect the alternative shelf into A.
  self.assertEqual(len([n for n in f if n.startswith('main-')]),5)
  svg=ET.parse(ROOT/'web/assets/technical-atlas/thermal-domain-v1.svg').getroot();f={p.get('data-flow'):points(p.get('d'))for p in svg.findall('.//s:path[@data-flow]',NS)}
  self.assertEqual(len(f),8)
  for domain,order in [('TCS',['return','HX','supply','load']),('FWS',['return','source','supply','HX'])]:
   seq=[f[domain+'-'+n]for n in order]
   for a,b in zip(seq,seq[1:]+seq[:1]):self.assertEqual(a[-1],b[0],(domain,a,b))
  wall=points(svg.find('.//s:path[@data-separator="fluid-wall"]',NS).get('d'));wx=wall[0][0]
  self.assertLess(max(p[0]for n,v in f.items()if n.startswith('TCS-')for p in v),wx);self.assertGreater(min(p[0]for n,v in f.items()if n.startswith('FWS-')for p in v),wx)
  heat={p.get('data-heat'):points(p.get('d'))for p in svg.findall('.//s:path[@data-heat]',NS)};self.assertLess(heat['TCS-to-FWS'][0][0],wx);self.assertGreater(heat['TCS-to-FWS'][-1][0],wx)
  node={r.get('data-functional-node'):{k:float(r.get(k))for k in ['x','y','width','height']}for r in svg.findall('.//s:rect[@data-functional-node]',NS)}
  c=node['coldplate'];a=heat['chip-to-coldplate'][-1];self.assertEqual(a[1],c['y']+c['height']);self.assertTrue(c['x']<=a[0]<=c['x']+c['width'])
  c=node['outdoor-cold-source'];a=heat['to-outdoor-air'][0];self.assertEqual(a[0],c['x']+c['width']);self.assertTrue(c['y']<=a[1]<=c['y']+c['height'])
 def test_domain_classes_explicit_binding_routes_and_unchanged_geometry(self):
  routes=json.loads((ROOT/'web/routes.json').read_text());m=json.loads((ROOT/'framework/interface_manifest.json').read_text());s=(ROOT/'web/components/technical-atlas.js').read_text();b=(ROOT/'web/pages/bom3d.html').read_text();bom=json.loads((ROOT/'framework/bom.json').read_text())
  self.assertIn("p.system===activeDomain?'system':null",b);self.assertIn("['power','thermal'].includes(activeDomain)",b);self.assertIn('非接线/管线顺序',b)
  for n,domain,total,modelled,instances in [('TA-22','power',19,4,8),('TA-23','thermal',15,3,11)]:
   with self.subTest(figure=n):
    d=ROOT/'docs/design/technical-atlas'/n;g=load(d,'existing-geometry-reference-v1.json');self.assertEqual(sha((ROOT/g['source_factory']['file']).read_bytes()),g['source_factory']['sha256'])
    self.assertEqual(sha(s.split('const serverPlan =')[0].encode()),g['default14_prefix_sha256']);self.assertEqual(sha((ROOT/'web/components/system-atlas.js').read_bytes()),g['system47_sha256'])
    ps=[p for p in bom['parts']if p['system']==domain];self.assertEqual(len(ps),total);ids={p['id']for p in ps};actual=[i for i in g['existing_actual_geometry']['instances']if i['part']in ids];self.assertEqual(len(actual),instances);self.assertEqual(len({i['part']for i in actual}),modelled)
    for i in g['existing_actual_geometry']['instances']:self.assertEqual(i['home'],i['position'])
    self.assertEqual(g['existing_actual_geometry']['mesh'],152)
    self.assertIn(f"partId === '{domain}-domain' && view === 'domain' ? {domain}Domain",s);self.assertIn(f"campusMode && d.key==='{domain}'",b)
    page=domain+'-atlas.html';self.assertEqual(routes['/'+page],'web/pages/'+page);self.assertIn(page,m['static_pages']);self.assertIn(page,m['public_pages']);self.assertIn(page,m['sections']['bom']);p=(ROOT/'web/pages'/page).read_text();self.assertIn(f"'{domain}-domain',{{view:'domain'}}",p)
    urls=re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"',p);self.assertNotIn('/assets/site-shell.js',urls)
    for url in urls:self.assertIn(url,routes);self.assertTrue((ROOT/routes[url]).is_file())
    for src in load(d,'technical-sources-v1.json')['sources']:self.assertEqual(sha((ROOT/('docs/design/technical-atlas/bom-source-20260928.json' if src['file']=='framework/bom.json' else src['file'])).read_bytes()),src['sha256'])
  # The existing non-campus layout and existing facility-only block are retained.
  before=(ROOT/'docs/design/technical-atlas/TA-21/bom3d-before-v1.html').read_text();self.assertIn(before[before.index('/* ─────────── 建筑'):before.index(' } // Retained legacy layout;')],b)
  self.assertIn("campusMode && d.key==='facility'",b);self.assertIn("p.kind==='site_right'",b)
