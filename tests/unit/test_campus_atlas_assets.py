"""TA18 source integrity, not runtime or visual acceptance. No HTTP or JS execution."""
import base64,hashlib,json,re,struct,unittest
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
D=ROOT/'docs/design/technical-atlas/TA-18'
NS={'s':'http://www.w3.org/2000/svg'}
class CampusAtlasAssetsTests(unittest.TestCase):
 def test_native_identity_and_editable_geometry_labels(self):
  m=json.loads((D/'asset-manifest-v1.json').read_text());routes=json.loads((ROOT/'web/routes.json').read_text())
  for a in m['assets']:
   raw=(ROOT/a['file']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),a['sha256']);self.assertEqual(len(raw),a['bytes']);self.assertEqual(routes['/assets/technical-atlas/'+Path(a['file']).name],a['file'])
  native=(ROOT/m['assets'][0]['file']).read_bytes();self.assertEqual(struct.unpack('>II',native[16:24]),(1536,1024));self.assertEqual(hashlib.sha256(native).hexdigest(),m['native_original_sha256'])
  svg=ET.fromstring((ROOT/m['assets'][1]['file']).read_bytes());img=svg.find('s:image',NS);href=img.get('href')or img.get('{http://www.w3.org/1999/xlink}href');self.assertEqual(base64.b64decode(href.split(',')[1]),native)
  self.assertEqual(svg.get('viewBox'),'0 0 1536 1024');self.assertEqual(len(svg.findall('.//s:text',NS)),21)
  labels=json.loads((D/'labels-v1.json').read_text());self.assertEqual(len(labels['labels']),9)
  for label in labels['labels']:
   scale,dx,dy=label['affine']
   for k in ('anchor','marker'):
    self.assertEqual(len(label['source_'+k]),2)
    for j,t in enumerate((dx,dy)):self.assertAlmostEqual(label['display_'+k][j],label['source_'+k][j]*scale+t)
  paths=svg.findall('.//s:path',NS);self.assertEqual(len(paths),9)
  for label,path in zip(labels['labels'],paths):
   xy=[float(x)for x in re.findall(r'-?\d+(?:\.\d+)?',path.get('d'))]
   for a,b in zip(xy[-2:],label['display_anchor']):self.assertAlmostEqual(a,b,places=2)
 def test_old_geometry_is_preserved_and_nonphysical_scope_is_separate(self):
  old=(D/'bom3d-before-v1.html').read_text();new=(ROOT/'web/pages/bom3d.html').read_text()
  start=old.index('/* ─────────── 建筑');end=old.index('/* ─────────── 分解阶段说明')
  self.assertIn(old[start:end],new,'Retained legacy geometry block must remain raw-identical')
  m=json.loads((D/'asset-manifest-v1.json').read_text());b=m['raw_baseline'];raw=(ROOT/b['file']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),b['sha256'])
  counts=m['counts'];self.assertEqual(counts['rack_rows']*counts['racks_per_row'],counts['rack_cabinets']);self.assertEqual(counts['rack_cabinets'],8)
  actual={p['id']:p for p in json.loads((ROOT/'framework/bom.json').read_text())['parts']}
  categories={'shell','rack-frame','room-cooling','cdu','ups','cabling','chiller','transformer','backup-power','bess'}
  self.assertTrue(all(actual[p].get('kind','part')=='part'for p in categories));self.assertNotIn('dcim',categories)
  rights=json.loads((ROOT/'framework/site_rights.json').read_text());rows=rights.get('rights',rights.get('site_rights',[]));self.assertEqual(len(rows),6)
