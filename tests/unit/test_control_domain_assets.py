"""Control software semantic/asset/source contracts only; no HTTP or product JS."""
import base64, hashlib, json, re, struct, unittest
from pathlib import Path
import xml.etree.ElementTree as E
R=Path(__file__).resolve().parents[2];N={'s':'http://www.w3.org/2000/svg'}
def j(p):return json.loads(p.read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
class ControlDomainAssetTests(unittest.TestCase):
 def test_original_context_native_embedding_and_editable_logical_locators(self):
  d=R/'docs/design/technical-atlas/TA-28';m=j(d/'asset-manifest-v1.json');routes=j(R/'web/routes.json')
  for a in m['assets']:
   b=(R/a['file']).read_bytes();self.assertEqual((len(b),sha(b)),(a['bytes'],a['sha256']));self.assertEqual(routes['/assets/technical-atlas/'+Path(a['file']).name],a['file'])
  raw=(R/m['assets'][0]['file']).read_bytes();self.assertEqual(struct.unpack('>II',raw[16:24]),(1536,1024));s=E.parse(R/m['assets'][1]['file']).getroot();self.assertEqual(base64.b64decode(s.find('s:image',N).get('href').split(',')[1]),raw)
  cm=j(d/'component-manifest-v1.json');self.assertFalse(cm['originals_modified']);self.assertFalse(cm['public_or_local_product_access']);self.assertEqual(cm['software_categories'],['dcim']);self.assertEqual(cm['physical_software_instances'],0)
  c=cm['components'][0];self.assertEqual(c['id'],'campus-context');b=(R/'web/assets/technical-atlas'/c['file']).read_bytes();self.assertEqual((sha(b),len(b)),(c['sha256'],c['bytes']));self.assertIn('no installed telemetry',c['scope'])
  ps={g.get('data-label'):g for g in s.findall('.//s:g[@class="callout"]',N)};labels=j(d/'labels-v1.json')['labels'];self.assertEqual(len(labels),6)
  for l in labels:
   g=ps[l['number']];self.assertEqual(g.get('data-object'),'dcim');end=list(re.finditer(r'(-?[\d.]+),(-?[\d.]+)',g.find('s:path',N).get('d')))[-1];self.assertEqual([float(end.group(k+1))for k in [0,1]],l['display_anchor']);self.assertEqual(l['part_id'],'dcim')
  scan=j(d/'offline-label-scan-v1.json');self.assertEqual(scan['external'],[]);self.assertTrue(scan['fontsReady']);self.assertEqual(scan['hits'],[]);self.assertEqual(scan['outside'],[]);self.assertEqual(scan['text_text_overlaps'],[])
  preview=E.parse(R/m['assets'][3]['file']).getroot();self.assertEqual([t.text for t in s.findall('.//s:text',N)],[t.text for t in preview.findall('.//s:text',N)]);self.assertLess((R/m['assets'][3]['file']).stat().st_size,512*1024)
 def test_one_software_zero_entities_and_parallel_nonphysical_function_semantics(self):
  d=R/'docs/design/technical-atlas/TA-28';bom=j(R/'framework/bom.json');parts=[p for p in bom['parts']if p['system']=='control'];self.assertEqual(len(parts),1);p=parts[0];self.assertEqual((p['id'],p['kind'],p['scale']),('dcim','software',None))
  g=j(d/'existing-geometry-reference-v1.json');self.assertEqual(g['domain_geometry']['physical_instances'],0);self.assertEqual(g['domain_geometry']['physical_meshes'],0);self.assertEqual(g['domain_geometry']['unmodeled_physical_categories'],0);self.assertEqual([i for i in g['existing_actual_geometry']['instances']if i['part']=='dcim'],[]);self.assertEqual(g['existing_actual_geometry']['mesh'],152);self.assertEqual(sha((R/g['source_factory']['file']).read_bytes()),g['source_factory']['sha256'])
  m=j(d/'asset-manifest-v1.json');s=E.parse(R/m['assets'][1]['file']).getroot();text=' '.join(t.text for t in s.findall('.//s:text',N))
  for phrase in ['一个在册软件类别 dcim','不是三跳串联或三套实装','非实体设备、物理线缆','信息关系示意','不新增传感器、网关、控制器或机柜','可选授权操作','读取权限不等于写入权限','非本园区已部署自动闭环','六项站点权利与软件访问权限分开','告警确认不等于故障已排除']:self.assertIn(phrase,text)
  flows=s.findall('.//s:path[@data-flow]',N);self.assertEqual(len(flows),5);self.assertEqual(len([p for p in flows if p.get('stroke-dasharray')]),2)
 def test_control_only_domain_binding_badge_export_and_existing_scope(self):
  b=(R/'web/pages/bom3d.html').read_text();a=(R/'web/components/technical-atlas.js').read_text();self.assertIn("atlasViewFor:p=>campusMode && activeDomain==='control' && p.id==='dcim'?'domain':",b);self.assertIn("(partId === 'control-domain' || partId === 'dcim') && view === 'domain' ? controlDomain",a);self.assertIn("campusMode && d.key==='control'",b);self.assertIn('"network","control"].includes(d.key)',b);self.assertIn("if(p.id==='dcim')return ['控制软件','软件节点，无物理硬件模型']",b)
  self.assertIn("if(campusMode&&activeDomain==='control'&&id==='dcim')return",b);self.assertIn('软件信息上下文，无物理模型；背景设施不证明数据接入或自动控制',b);self.assertIn('不是待建硬件',b);self.assertIn("['compute','memory','storage','network'].includes(activeDomain)) && p.system===activeDomain?'system':null",b)
  self.assertIn("const currentPartMeshes=pid=>campusMode&&campusSelectedMeshes?campusSelectedMeshes:PARTMESH[pid]",b);self.assertIn("id:campusMode&&campusSelectedInstance?campusSelectedInstance:'part:'+id",b);self.assertRegex(b,r'dcim\s*:\s*"control"')
  routes=j(R/'web/routes.json');m=j(R/'framework/interface_manifest.json');page='control-atlas.html';self.assertEqual(routes['/'+page],'web/pages/'+page)
  for k in ['static_pages','public_pages']:self.assertIn(page,m[k])
  self.assertIn(page,m['sections']['bom']);s=(R/'web/pages'/page).read_text();self.assertIn("'control-domain',{view:'domain'}",s);self.assertNotIn('/assets/site-shell.js',s);self.assertNotIn('/campus-atlas.html',s)
  for u in re.findall(r'href="(/[^"]+)"',s):self.assertIn(u.split('#')[0].split('?')[0],routes)
  for u in re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"',s):self.assertIn(u,routes);self.assertTrue((R/routes[u]).is_file())
 def test_public_fixture_has_no_local_fallback_and_visible_software_export_checks(self):
  s=(R/'tests/control_domain.cjs').read_text();self.assertIn('https://inresearch.ai',s);self.assertNotIn('127.0.0.1',s);self.assertNotIn('localhost',s);self.assertIn('无物理模型',s);self.assertIn('part:dcim',s);self.assertIn('object_id',s);self.assertIn('caption',s);self.assertIn('TA-28',s)
