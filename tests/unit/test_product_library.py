"""Regression coverage for real file adoption and response MIME detection.

Run with: python3 tests/unit/test_product_library.py
All files and catalog writes stay in a system temporary directory.
"""
import hashlib
import io
import tempfile
import unittest
from argparse import Namespace
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from inresearch.materials import library as library


class ProductLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inresearch-product-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / 'product'
        for path in library.dirs(self.store):
            path.mkdir(parents=True)
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name, value in [('ROOT', self.root), ('LINK', self.store),
                            ('PLAN', self.root / 'data/product_docs_plan.csv'),
                            ('INDEX', self.root / 'data/product_library_index.json')]:
            stack.enter_context(patch.object(library, name, value))

    def row(self, model, status='todo'):
        row = {key: '' for key in library.PLAN_COLS}
        row.update(company_id='test-vendor', company_en='Test Vendor', sheet='测试环节',
                   product_line='测试产品线', model=model, bom_part='server', doc_type='DS',
                   source_url='https://example.test/manual', lang='en', status=status,
                   note='保留人工说明')
        return row

    def test_non_pdf_mime_is_text_and_pdf_magic_stays_authoritative(self):
        path = self.root / 'response.part'
        cases = [
            (b'%PDF-1.7\n', 'text/html', '.pdf'),
            (b'login required', 'text/html; charset=UTF-8', '.html'),
            (b'<html>', '', '.html'),
            (b'PK\x03\x04payload', 'application/zip', '.zip'),
            (b'readme', 'text/plain; charset=utf-8', '.txt'),
            (b'unknown', None, '.bin'),
        ]
        for data, mime, expected in cases:
            with self.subTest(mime=mime, expected=expected):
                path.write_bytes(data)
                self.assertEqual(expected, library.ext_of(path, mime))

    def test_adopt_persists_plan_and_index_without_changing_other_jobs(self):
        target, other = self.row('Model A'), self.row('Model B', 'needs_manual')
        library.save_plan([target, other])
        source = self.root / 'downloaded.pdf'
        contents = b'%PDF-1.7\nmanual fixture bytes\n'
        source.write_bytes(contents)

        with redirect_stdout(io.StringIO()):
            library.cmd_adopt(Namespace(row=library.rowkey(target), file=str(source)))

        rows = library.load_plan()
        index = library.load_index()
        self.assertEqual('downloaded', rows[0]['status'])
        self.assertEqual('人工下载', rows[0]['note'])
        self.assertEqual(other, rows[1])
        self.assertEqual(1, len(index['records']))
        record = index['records'][0]
        self.assertEqual(record['doc_id'], rows[0]['doc_id'])
        self.assertEqual(hashlib.sha256(contents).hexdigest(), record['sha256'])
        self.assertEqual(contents, (self.store / record['file_path']).read_bytes())
        self.assertEqual(contents, source.read_bytes())

    def test_sidecar_batch_persists_each_adopted_row(self):
        import json
        rows = [self.row('Model A'), self.row('Model B')]
        library.save_plan(rows)
        for number, row in enumerate(rows):
            path = self.store / '_inbox' / f'manual-{number}.pdf'
            path.write_bytes(b'%PDF-1.7\n' + row['model'].encode())
            path.with_suffix('.pdf.meta.json').write_text(json.dumps(row))
        with redirect_stdout(io.StringIO()):
            library.cmd_adopt(Namespace(row=None, file=None))
        saved = library.load_plan()
        records = library.load_index()['records']
        self.assertEqual(['downloaded', 'downloaded'], [r['status'] for r in saved])
        self.assertEqual([r['doc_id'] for r in records], [r['doc_id'] for r in saved])
        self.assertEqual(2, len(set(r['doc_id'] for r in saved)))
        self.assertTrue(all((self.store / r['file_path']).is_file() for r in records))

    def test_adopt_recovers_before_index_and_after_index_without_duplicates(self):
        for crash_at in ('save_index', 'save_plan'):
            with self.subTest(crash_at=crash_at):
                row = self.row('Recover ' + crash_at)
                library.save_plan([row])
                source = self.root / (crash_at + '.pdf')
                contents = b'%PDF-1.7 recovery ' + crash_at.encode()
                source.write_bytes(contents)
                args = Namespace(row=library.rowkey(row), file=str(source))
                with patch.object(library, crash_at, side_effect=OSError('injected power loss')):
                    with self.assertRaises(OSError), redirect_stdout(io.StringIO()):
                        library.cmd_adopt(args)
                self.assertTrue(library.admission_path().exists())
                self.assertEqual(contents, source.read_bytes())
                with redirect_stdout(io.StringIO()):
                    library.cmd_adopt(args)
                    library.cmd_adopt(args)
                matches = [r for r in library.load_index()['records']
                           if r['sha256'] == hashlib.sha256(contents).hexdigest()]
                self.assertEqual(len(matches), 1)
                self.assertEqual(library.load_plan()[0]['doc_id'], matches[0]['doc_id'])
                self.assertFalse(library.admission_path().exists())

    def test_changed_source_during_recovery_never_becomes_an_indexed_fact(self):
        row = self.row('Changing source')
        library.save_plan([row])
        source = self.root / 'changing.pdf'
        source.write_bytes(b'%PDF-1.7 first')
        args = Namespace(row=library.rowkey(row), file=str(source))
        with patch.object(library.os, 'link', side_effect=OSError('interrupted placement')):
            with self.assertRaises(OSError), redirect_stdout(io.StringIO()):
                library.cmd_adopt(args)
        source.write_bytes(b'%PDF-1.7 replacement')
        with self.assertRaisesRegex(ValueError, 'source_changed'):
            library.cmd_adopt(args)
        self.assertEqual(library.load_index()['records'], [])
        self.assertTrue(library.admission_path().exists())
        self.assertEqual(source.read_bytes(), b'%PDF-1.7 replacement')


if __name__ == '__main__':
    unittest.main()
