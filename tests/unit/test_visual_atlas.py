"""Protect adopted visual originals and the completeness of the migration queue.

These checks do not claim that an image looks right or has correct engineering.
"""
import hashlib
import json
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]


class VisualAtlasTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / 'framework/visual_atlas.json').read_text())
        self.queue = json.loads((ROOT / 'framework/visual_atlas_migration.json').read_text())

    def test_adopted_reference_bytes_and_actual_dimensions_match(self):
        references = self.profile['references']
        self.assertEqual(len({r['id'] for r in references}), 5)
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
        self.assertLessEqual(len(active), 1, 'the adopted plan works on one item at a time')
