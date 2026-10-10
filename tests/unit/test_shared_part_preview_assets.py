"""No-HTTP conservation and scope checks for the shared preview migration.
Actual WebGL/UI behavior is separately verified by the explicit public fixture.
"""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / 'docs/design/technical-atlas/TA-29'

class SharedPartPreviewAssetTests(unittest.TestCase):
    def test_adopted_art_and_untouched_geometry_remain_exact(self):
        baseline = json.loads((RECORD / 'baseline-v1.json').read_text())
        for row in baseline['unchanged_reuse']:
            with self.subTest(source=row['source']):
                self.assertEqual(hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest(), row['sha256'])
        for figure in [11,13,14,15,18,19,28]:
            accepted = json.loads((ROOT / f'docs/design/technical-atlas/TA-{figure}/acceptance-v1.json').read_text())
            for row in accepted['artifacts']:
                with self.subTest(figure=figure,source=row['file']):
                    self.assertEqual(hashlib.sha256((ROOT / row['file']).read_bytes()).hexdigest(),row['sha256'])

    def test_installed_rack_identity_change_does_not_alter_geometry(self):
        old = (RECORD / 'rack-assembly-before-v1.js').read_text()
        new = (ROOT / 'web/components/rack-assembly.js').read_text()
        self.assertEqual(new.replace("g.userData.instanceId='rack/'+name;", "if(exploded)g.userData.instanceId='rack/'+name;"), old)

    def test_mode_inventory_uses_registered_categories_and_excludes_nonphysical(self):
        inv=json.loads((RECORD / 'preview-inventory-v1.json').read_text())['inventory']
        bom=json.loads((ROOT/'framework/bom.json').read_text())
        parts={p['id']:p for p in bom['parts']}
        campus=inv['campus'];self.assertEqual(len(campus['physical_part_ids']),10)
        self.assertEqual(len(campus['stable_instance_ids']),32)
        self.assertEqual(len(set(campus['stable_instance_ids'])),32)
        for pid in campus['physical_part_ids']:
            self.assertIn(pid,parts);self.assertNotIn(parts[pid].get('kind'),['software','site_right'])
        self.assertEqual(len(inv['server']['source_part_ids']),8)
        self.assertEqual(len(inv['rack']['source_part_ids']),4)
        self.assertEqual(inv['chip']['part_ids'],['gpu','hbm'])
        self.assertNotIn('dcim',campus['physical_part_ids'])
        self.assertNotIn('modular-dc',campus['physical_part_ids'])
        queue=json.loads((ROOT/'framework/visual_atlas_migration.json').read_text())
        self.assertEqual(queue['primary_plan']['published'],29)
        self.assertEqual(next(i for i in queue['items']if i['id']=='TA-28')['published_revision'],'1c1a024a900df6f10d50a8b5b4d8416acd6129b6')

if __name__=='__main__': unittest.main()
