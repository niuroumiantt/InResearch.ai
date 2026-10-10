"""Protect adopted visual originals and the completeness of the migration queue.

These checks do not claim that an image looks right or has correct engineering.
"""
import hashlib
import base64
import json
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


class VisualAtlasTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / 'framework/visual_atlas.json').read_text())
        self.queue = json.loads((ROOT / 'framework/visual_atlas_migration.json').read_text())

    def test_adopted_reference_bytes_and_actual_dimensions_match(self):
        references = self.profile['references']
        self.assertEqual({r['id'] for r in references}, {f'R{i}' for i in range(1, 15)})
        for row in references:
            path = (ROOT / row['file']).resolve()
            self.assertTrue(path.is_relative_to(ROOT))
            raw = path.read_bytes()
            self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'], row['id'])
            self.assertEqual(struct.unpack('>II', raw[16:24]), (row['width'], row['height']))
            self.assertFalse(row['technical_evidence'])

    def test_all_existing_render_and_panel_assets_have_individual_queue_rows(self):
        actual = {p.relative_to(ROOT).as_posix()
                  for folder in ('renders', 'panels')
                  for p in (ROOT / 'web/assets' / folder).glob('*.png')}
        queued = {p for row in self.queue['items'] for p in row['source_paths']
                  if p.startswith(('web/assets/renders/', 'web/assets/panels/')) and p.endswith('.png')}
        self.assertEqual(actual, queued, 'retained assets must not disappear from the migration inventory')
        for row in self.queue['items']:
            for source in row['source_paths']:
                self.assertTrue((ROOT / source).is_file(), row['id'] + ': ' + source)

    def test_reference_links_dependency_order_and_completion_receipts_are_valid(self):
        self.assertEqual(self.queue['style_id'], self.profile['style_id'])
        rows = self.queue['items']
        self.assertEqual(len({r['id'] for r in rows}), len(rows))
        by_id = {r['id']: r for r in rows}
        refs = {r['id'] for r in self.profile['references']}
        active = []
        for row in rows:
            self.assertTrue(set(row['reference']) <= refs)
            self.assertIn(row['status'], self.queue['states'])
            for dependency in row['depends_on']:
                self.assertLess(by_id[dependency]['order'], row['order'], row['id'])
            if row['status'] in ('drafting', 'review'):
                active.append(row['id'])
            if row['status'] in ('accepted', 'published'):
                self.assertTrue(row['acceptance_record'], row['id'] + ': no acceptance receipt')
            if row['status'] == 'published':
                self.assertTrue(row['published_revision'], row['id'] + ': no publication receipt')
        execution=self.queue['execution']
        batches=execution['source_pr_batches'];expected=[['TA-21'],['TA-22','TA-23'],['TA-24','TA-25','TA-26','TA-27'],['TA-28'],['TA-29'],['TA-30','TA-31','TA-32','TA-33','TA-34'],['TA-35']]
        self.assertEqual(batches,expected);self.assertIn(execution['current_source_batch'],batches)
        self.assertEqual(execution['max_concurrent_drafting'],1)
        self.assertLessEqual(sum(r['status']=='drafting'for r in rows),1)
        self.assertTrue(set(active)<=set(execution['current_source_batch']))
        for row in rows:
            if row['status']=='review':
                evidence=json.loads((ROOT/row['source_review_record']).read_text())
                self.assertEqual(evidence['figure_id'],row['id']);self.assertEqual(evidence['decision'],'source_ready_public_pending')
                if row['kind']=='shared':
                    self.assertTrue(evidence['source_reviewed']);self.assertTrue(evidence['reviewed_sources'])
                    for artifact in evidence['reviewed_sources']:self.assertEqual(hashlib.sha256((ROOT/artifact['file']).read_bytes()).hexdigest(),artifact['sha256'])
                else:
                    self.assertTrue(evidence['original_viewed']);self.assertTrue(evidence['artifacts'])
                    for artifact in evidence['artifacts']:self.assertEqual(hashlib.sha256((ROOT/artifact['file']).read_bytes()).hexdigest(),artifact['sha256'])
        self.assertEqual(self.queue['primary_plan']['published'],sum(r['status']=='published'for r in rows if r['id']in self.queue['primary_plan']['items']))

    def test_completed_illustrations_bind_master_labels_and_retained_baseline(self):
        ns = {'s': 'http://www.w3.org/2000/svg'}
        for row in self.queue['items']:
            if row['status'] not in ('accepted', 'published') or row['kind'] not in ('existing', 'new_illustration', 'new_view'):
                continue
            receipt = json.loads((ROOT / row['acceptance_record']).read_text())
            self.assertEqual(receipt['figure_id'], row['id'])
            self.assertEqual(receipt['object_id'], row['object_id'])
            self.assertEqual(receipt['style_id'], self.queue['style_id'])
            for artifact in receipt['artifacts']:
                raw = (ROOT / artifact['file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), artifact['sha256'])
            master = ROOT / receipt['master']
            self.assertEqual(struct.unpack('>II', master.read_bytes()[16:24]), tuple(receipt['pixels']))
            svg = ET.parse(ROOT / receipt['labelled']).getroot()
            embedded = svg.find('s:image', ns).get('href').split(',', 1)[1]
            self.assertEqual(base64.b64decode(embedded), master.read_bytes(), 'label export must embed the unchanged master')
            self.assertGreater(len(svg.findall("s:g[@id='editable-labels']/s:text", ns)), 0)
            if receipt.get('preview'):
                preview = ROOT / receipt['preview']['file']
                self.assertLess(preview.stat().st_size, 512 * 1024, 'dossier preview must stay lightweight')
                self.assertEqual(len(ET.parse(preview).getroot().findall("s:g[@id='editable-labels']/s:text", ns)),
                                 len(svg.findall("s:g[@id='editable-labels']/s:text", ns)))
            if row['kind'] == 'existing':
                baseline = row['baseline_asset']
                self.assertEqual(hashlib.sha256((ROOT / baseline['file']).read_bytes()).hexdigest(), baseline['sha256'], 'retain old assets')
            else:
                self.assertRegex(row['baseline_revision'], r'^[a-f0-9]{40}$', 'new illustration must retain its source-page baseline')

    def test_shared_recipe_receipt_keeps_geometry_and_export_scope_explicit(self):
        for row in self.queue['items']:
            if row['kind'] != 'shared' or row['status'] not in ('accepted', 'published'):
                continue
            receipt = json.loads((ROOT / row['acceptance_record']).read_text())
            self.assertEqual(receipt['figure_id'], row['id'])
            self.assertEqual(receipt['style_id'], self.queue['style_id'])
            self.assertIn(receipt['scope'], ('shared_render_and_export_only', 'shared_part_preview_only'))
            self.assertFalse(receipt['individual_geometry_migration_complete'])
            self.assertFalse(receipt['export']['is_static_master_or_cad'])
            self.assertEqual(receipt['export']['pixels'], 'actual_current_canvas')
            by_ref = {ref['id']: ref for ref in self.profile['references']}
            for ref in receipt['references']:
                self.assertEqual(ref['sha256'], by_ref[ref['id']]['sha256'])
            for artifact in receipt['implementation_at_review']:
                self.assertTrue((ROOT / artifact['file']).is_file())
                self.assertRegex(artifact['sha256'], r'^[a-f0-9]{64}$')
            if receipt['scope'] == 'shared_part_preview_only':
                self.assertEqual(row['id'], 'TA-29')
                self.assertIn('tests/shared_part_preview.cjs', receipt['browser_checks'])
                self.assertTrue(receipt['geometry_and_original_art_conserved'])
                self.assertEqual(receipt['publication_status'], 'published')
                self.assertTrue(receipt['actual_public_receipt'])
            else:
                self.assertIn('tests/scene_atlas.cjs', receipt['browser_checks'])
            self.assertTrue(receipt['remaining_work'])
