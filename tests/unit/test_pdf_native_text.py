"""User-selected native text reading: zero OCR, explicit omissions, frozen history."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import test_continuous_reader as fixtures
from inresearch.adapters.pdf_text import extract_pdf, export_file
from inresearch.materials.artifacts import read_json, atomic_json
from inresearch.materials.reader_contracts import IntegrityError


class PdfNativeTextTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ReaderTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.r = self.f.reader
        self.r.stages.pdf_mode = 'native_text_only'
        self.f.model.ocr = mock.Mock(side_effect=AssertionError('native reading called OCR'))
        self.f.put('paper.pdf', '%PDF-original bytes retained')
        self.texts = ['First: 60MW IT, 75MW power.\n', '', 'Last: 160MW IT; 230MW power.\n']

    def command(self, args, **kw):
        if args[0] == 'pdfinfo': return 'Pages: 3\n'
        if args[0] == 'pdfimages': return '1 0 image 500 500\n2 1 image 600 600\n3 2 image 20 20\n'
        if args[0] == 'pdftotext': return '\f'.join(self.texts) + '\f'
        raise AssertionError(args)

    def test_new_reader_defaults_to_text_only_without_changing_frozen_legacy_recipe(self):
        from inresearch.workflow.reader import Reader
        with mock.patch.dict('os.environ', {}, clear=True):
            reader = Reader(self.r.data, self.r.state, self.r.repo, self.f.model)
        self.assertEqual(reader.stages.pdf_mode, 'native_text_only')

    def run_reader(self):
        with mock.patch('inresearch.workflow.reading_stages.shutil.which', return_value='/tool'), \
                mock.patch.object(self.r.stages, '_command', side_effect=self.command):
            self.f.run_reader()
        return self.r.doc(self.f.first_doc()['doc_id'])

    def test_mixed_pdf_delivers_text_and_quotes_without_ocr_or_false_visual_completion(self):
        self.r.stages.ocr_max_pages = 0
        doc = self.run_reader()
        self.assertEqual(doc['state'], 'complete')
        report = self.r.stages.verify_seal(doc)
        c = report['coverage']
        self.assertEqual(c['scope'], 'pdf_native_text_only')
        self.assertTrue(c['complete'])
        self.assertFalse(c['full_document_complete'])
        self.assertFalse(c['visual_review_performed'])
        self.assertEqual(c['skipped_image_pages'], [1, 2, 3])
        self.assertEqual(c['text_layer_empty_pages'], [2])
        self.assertEqual(c['native_text_pages_read'], 2)
        self.assertEqual(c['characters_read'], sum(map(len, self.texts)))
        self.f.model.ocr.assert_not_called()
        self.assertIn('230MW', self.r.stages.full_text(doc))
        self.assertEqual({q['page_index'] for q in report['evidence']}, {1, 3})
        snapshot = self.r.export_snapshot()
        self.assertEqual(snapshot['knowledge']['documents'][0]['coverage'], c)

    def test_no_native_text_stays_blocked_not_a_fake_completed_report(self):
        self.texts = ['', '', '']
        doc = self.run_reader()
        self.assertEqual(doc['state'], 'blocked')
        self.assertEqual(doc['error_code'], 'image_only_requires_user_text')
        self.assertFalse(doc['report_rel'])
        self.f.model.ocr.assert_not_called()

    def test_scope_and_skipped_page_tampering_are_rejected(self):
        doc = self.run_reader()
        path = self.r.stages.artifact_path(doc, 'report.json')
        original = read_json(path)
        for mutate in (lambda c: c.pop('scope'), lambda c: c.update(visual_review_performed=True),
                       lambda c: c.update(skipped_image_pages=[]), lambda c: c.update(text_layer_empty_pages=[])):
            changed = json.loads(json.dumps(original))
            mutate(changed['coverage']); atomic_json(path, changed)
            with self.assertRaises(IntegrityError): self.r.stages.validate_report(doc)
        atomic_json(path, original)
        self.r.stages.verify_seal(doc)

    def test_new_text_recipe_retains_ocr_attempt_and_original_under_same_document_identity(self):
        self.r.stages.pdf_mode = 'full_visual'
        self.f.model.ocr_model = ''
        with mock.patch('inresearch.workflow.reading_stages.shutil.which', return_value='/tool'), \
                mock.patch.object(self.r.stages, '_command', side_effect=self.command):
            self.f.run_reader()
        old = self.r.doc(self.f.first_doc()['doc_id'])
        self.assertEqual(old['state'], 'blocked')
        recipe_path = self.r.stages.artifact_path(old, 'recipe.json')
        old_recipe = recipe_path.read_bytes()
        raw = (self.r.data / old['original_rel']).read_bytes()
        self.r.stages.pdf_mode = 'native_text_only'
        new = self.r.revisions.restart_unfinished(old['doc_id'], old['revision_id'], 'skip-images', 'User selected native PDF text')
        # Changing live configuration afterwards cannot change the frozen mode.
        self.r.stages.pdf_mode = 'full_visual'
        doc = self.run_reader()
        self.assertEqual(doc['revision_id'], new['revision_id'])
        self.assertNotEqual(doc['recipe'], old['recipe'])
        self.assertEqual(doc['state'], 'complete')
        self.assertEqual(recipe_path.read_bytes(), old_recipe)
        self.assertEqual((self.r.data / old['original_rel']).read_bytes(), raw)
        self.assertEqual(self.r.conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0], 1)
        self.assertEqual(self.r.conn.execute('SELECT state FROM reading_runs WHERE revision_id=?', (old['revision_id'],)).fetchone()[0], 'superseded')
        self.assertEqual(self.r.stages.verify_seal(doc)['coverage']['scope'], 'pdf_native_text_only')
        self.assertFalse(any(r['revision_id'] == old['revision_id'] for r in self.r.status()['recent_failures']))

    def test_batch_progress_separates_body_completion_from_unread_images(self):
        from inresearch.workflow.reader_scope import gap_counts
        doc = self.run_reader()
        counts = gap_counts(self.r.data, [doc], {})
        self.assertEqual(counts['native_text_only_complete'], 1)
        self.assertEqual(counts['skipped_image_pages'], 3)
        self.assertEqual(counts['text_layer_empty_pages'], 1)
        self.assertEqual(counts['unread_gap_pages'], 0)


class PdfExportTests(unittest.TestCase):
    def test_page_mismatch_fails_instead_of_silently_dropping_tail(self):
        def command(args, **kw):
            return 'Pages: 2\n' if args[0] == 'pdfinfo' else 'single page\f'
        with self.assertRaisesRegex(ValueError, 'page_count_mismatch'):
            extract_pdf(Path('original.pdf'), run=command)

    def test_export_keeps_dollar_unicode_names_and_hashes_without_altering_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / '$12B 原件.pdf'; source.write_bytes(b'%PDF-unchanged')
            meta = {'pages_total': 1, 'scope': 'pdf_native_text_only', 'text_layer_empty_pages': [], 'ocr_calls': 0}
            with mock.patch('inresearch.adapters.pdf_text.extract_pdf', return_value=(['Native 4GW text'], meta)):
                record = export_file(source, Path(source.name), root / 'derived')
            self.assertEqual(source.read_bytes(), b'%PDF-unchanged')
            text = (root / 'derived' / record['text_relative']).read_text()
            self.assertIn('$12B 原件.pdf', text)
            self.assertIn('=== PAGE 1 / 1 ===\nNative 4GW text', text)
            self.assertEqual(record['acceptance'], 'extraction_only_not_read_or_adopted')
