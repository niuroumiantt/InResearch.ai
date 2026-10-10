"""IT domain asset identity and domain isolation contracts, no product HTTP/JS."""
import base64,hashlib,json,re,struct,unittest
from pathlib import Path
import xml.etree.ElementTree as E
R=Path(__file__).resolve().parents[2];N={'s':'http://www.w3.org/2000/svg'}
def j(p):return json.loads(p.read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
class ITDomainAssetTests(unittest.TestCase):
 def test_adopted_originals_actual_affine_and_font_bounds(self):
  for n in [24,25,26,27]:
   with self.subTest(figure=n):
    d=R/f'docs/design/technical-atlas/TA-{n}';m=j(d/'asset-manifest-v1.json');routes=j(R/'web/routes.json')
    for a in m['assets']:
     b=(R/a['file']).read_bytes();self.assertEqual(len(b),a['bytes']);self.assertEqual(sha(b),a['sha256']);self.assertEqual(routes['/assets/technical-atlas/'+Path(a['file']).name],a['file'])
    raw=(R/m['assets'][0]['file']).read_bytes();self.assertEqual(struct.unpack('>II',raw[16:24]),(1536,1024));s=E.parse(R/m['assets'][1]['file']).getroot();self.assertEqual(base64.b64decode(s.find('s:image',N).get('href').split(',')[1]),raw)
    cm=j(d/'component-manifest-v1.json');self.assertFalse(cm['originals_modified']);self.assertFalse(cm['public_or_local_product_access'])
    for c in cm['components']:
     b=(R/'web/assets/technical-atlas'/c['file']).read_bytes();self.assertEqual(sha(b),c['sha256']);self.assertEqual(len(b),c['bytes'])
    ps={g.get('data-label'):g.find('s:path',N)for g in s.findall('.//s:g[@class="callout"]',N)}
    for l in j(d/'labels-v1.json')['labels']:
     end=list(re.finditer(r'(-?[\d.]+),(-?[\d.]+)',ps[l['number']].get('d')))[-1]
     for k in [0,1]:self.assertAlmostEqual(l['source_anchor'][k]*l['affine']['scale']+l['affine']['translate'][k],float(end.group(k+1)),places=3)
    scan=j(d/'offline-label-scan-v1.json');self.assertEqual(scan['external'],[]);self.assertTrue(scan['fontsReady']);self.assertEqual(scan['hits'],[]);self.assertEqual(scan['outside'],[]);self.assertEqual(scan['text_text_overlaps'],[])
    preview=E.parse(R/m['assets'][3]['file']).getroot();self.assertEqual(len(s.findall('.//s:text',N)),len(preview.findall('.//s:text',N)));self.assertLess((R/m['assets'][3]['file']).stat().st_size,512*1024)
 def test_compute_no_campus_entities_and_explicit_domain_binding(self):
  d=R/'docs/design/technical-atlas/TA-24';bom=j(R/'framework/bom.json');g=j(d/'existing-geometry-reference-v1.json');ids={p['id']for p in bom['parts']if p['system']=='compute'}
  self.assertEqual(ids,{'rack-system','server','general-server','gpu','ai-asic','cpu','fpga','bmc'});self.assertEqual([i for i in g['existing_actual_geometry']['instances']if i['part']in ids],[])
  sf=g['source_factory'];self.assertEqual(sha((R/sf['file']).read_bytes()),sf['sha256']);self.assertEqual(g['existing_actual_geometry']['mesh'],152)
  b=(R/'web/pages/bom3d.html').read_text();a=(R/'web/components/technical-atlas.js').read_text();self.assertIn("['compute','memory','storage','network'].includes(activeDomain)) && p.system===activeDomain?'system':null",b);self.assertIn("campusMode && d.key==='compute'",b);self.assertIn('八类计算对象本场景均未建模',b);self.assertIn("partId === 'compute-domain' && view === 'domain' ? computeDomain",a)
  page='compute-atlas.html';m=j(R/'framework/interface_manifest.json');routes=j(R/'web/routes.json');self.assertEqual(routes['/'+page],'web/pages/'+page)
  for k in ['static_pages','public_pages']:self.assertIn(page,m[k])
  self.assertIn(page,m['sections']['bom']);s=(R/'web/pages'/page).read_text();self.assertIn("'compute-domain',{view:'domain'}",s)
  for u in re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"',s):self.assertIn(u,routes);self.assertTrue((R/routes[u]).is_file())
  self.assertNotIn('/assets/site-shell.js',s);self.assertIn('独立服务器三维示例',s);self.assertIn('独立整柜三维示例',s);self.assertIn('view=rack&amp;x=0&amp;node=part:rack-frame',s);self.assertNotIn('view=overview',s)

 def test_memory_context_and_three_nonserial_relationships(self):
  d=R/'docs/design/technical-atlas/TA-25';g=j(d/'existing-geometry-reference-v1.json');ids={p['id']for p in j(R/'framework/bom.json')['parts']if p['system']=='memory'};self.assertEqual(ids,{'hbm','dram','cxl-memory'});self.assertEqual([i for i in g['existing_actual_geometry']['instances']if i['part']in ids],[])
  labels=j(d/'labels-v1.json')['labels'];cpu=next(l for l in labels if l['number']=='04');self.assertEqual(cpu['part_id'],'cpu');self.assertEqual(cpu['source_component'],'dram');self.assertTrue(cpu['context_only']);self.assertNotIn('cpu',ids)
  m=j(d/'asset-manifest-v1.json');s=E.parse(R/m['assets'][1]['file']).getroot();self.assertEqual(s.find('.//s:g[@data-label="04"]',N).get('data-object'),'cpu');texts=' '.join(e.text for e in s.findall('.//s:text',N));self.assertIn('封装内堆栈',texts);self.assertIn('逻辑裸片旁内存',texts);self.assertIn('不是 HBM→DIMM→CXL 的三级串联',texts);self.assertIn('CPU内存控制器 ↔ RDIMM',texts);self.assertIn('支持CXL的主机 ↔ 扩展设备',texts)
  routes=j(R/'web/routes.json');m=j(R/'framework/interface_manifest.json');page='memory-atlas.html';self.assertEqual(routes['/'+page],'web/pages/'+page)
  for key in ['static_pages','public_pages']:self.assertIn(page,m[key])
  self.assertIn(page,m['sections']['bom']);text=(R/'web/pages'/page).read_text();self.assertIn("'memory-domain',{view:'domain'}",text)
  for u in re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"',text):self.assertIn(u,routes);self.assertTrue((R/routes[u]).is_file())

 def test_storage_system_media_and_alternative_access(self):
  d=R/'docs/design/technical-atlas/TA-26';g=j(d/'existing-geometry-reference-v1.json');self.assertEqual(set(g['domain_geometry']['categories']),{'storage-array','ssd','hdd'});self.assertEqual(g['domain_geometry']['instances'],0)
  m=j(d/'asset-manifest-v1.json');s=E.parse(R/m['assets'][1]['file']).getroot();text=' '.join(t.text for t in s.findall('.//s:text',N));self.assertIn('不是“系统→SSD→HDD”的必经串联',text);self.assertIn('八个前托架仅为外形示例',text);self.assertIn('本地：主机 ↔ 直接连接的SSD/HDD',text);self.assertIn('网络：主机 ↔ 网络 ↔ 存储系统',text)
  labels=j(d/'labels-v1.json')['labels'];self.assertEqual([l['part_id']for l in labels],['storage-array','ssd','ssd','hdd','hdd']);self.assertEqual(labels[4]['source_anchor'],[850,350])

 def test_network_existing_bridge_and_nonserial_role_identity(self):
  d=R/'docs/design/technical-atlas/TA-27';g=j(d/'existing-geometry-reference-v1.json');ids={p['id']for p in j(R/'framework/bom.json')['parts']if p['system']=='network'};self.assertEqual(len(ids),9);self.assertEqual(g['domain_geometry']['modeled_classes'],1);self.assertEqual(g['domain_geometry']['instances'],1);self.assertEqual(g['domain_geometry']['unmodeled_classes'],8)
  self.assertEqual([(i['id'],i['part'])for i in g['existing_actual_geometry']['instances']if i['part']in ids],[('campus/overhead-service-trays','cabling')]);self.assertEqual(sha((R/g['source_factory']['file']).read_bytes()),g['source_factory']['sha256'])
  m=j(d/'asset-manifest-v1.json');s=E.parse(R/m['assets'][1]['file']).getroot();text=' '.join(t.text for t in s.findall('.//s:text',N));self.assertIn('仅cabling类有1组架空桥架示意',text);self.assertIn('非本图四护套线束',text);self.assertIn('其它八类未建模',text);self.assertIn('本图不是CPO集成布局',text);self.assertNotIn('九类在本园区均未建模',text)
  self.assertEqual({l['part_id']for l in j(d/'labels-v1.json')['labels']},ids)

 def test_all_four_declared_page_resources_and_current_scoped_binding(self):
  routes=j(R/'web/routes.json');m=j(R/'framework/interface_manifest.json');b=(R/'web/pages/bom3d.html').read_text()
  for domain in ['compute','memory','storage','network']:
   page=domain+'-atlas.html';self.assertEqual(routes['/'+page],'web/pages/'+page)
   for key in ['static_pages','public_pages']:self.assertIn(page,m[key])
   self.assertIn(page,m['sections']['bom']);s=(R/'web/pages'/page).read_text();self.assertIn("'"+domain+"-domain',{view:'domain'}",s);self.assertIn("campusMode && d.key==='"+domain+"'",b)
   for u in re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"',s):self.assertIn(u,routes);self.assertTrue((R/routes[u]).is_file())
   self.assertNotIn('/assets/site-shell.js',s)
