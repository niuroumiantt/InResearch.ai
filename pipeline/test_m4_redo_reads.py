#!/usr/bin/env python3
"""Re-reading a filed corpus must follow the ledger, not the inventory.

The inventory records where a file was found; the move step then renamed it
into the library.  `prepare` kept opening the inventory path, every extraction
raised FileNotFoundError, and `extract_preview` turned that into an empty
string rather than an exception - so `pack --redo` reported success while
silently degrading into a second filename-only pass.  On the real corpus that
was 0 of 200 previews; nothing in the suite noticed, because every test until
now put its files where the inventory said.
"""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import types
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m4_office_text as OFFICE
import m4_triage_l1 as L1
import m4_triage_pack as PK


def write(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                    encoding='utf-8')


def workbook(path: Path, sheets, strings):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook>' + ''.join(
            '<sheet name="%s"/>' % s for s in sheets) + '</workbook>')
        z.writestr('xl/sharedStrings.xml', '<sst>' + ''.join(
            '<si><t>%s</t></si>' % s for s in strings) + '</sst>')


class ReadablePathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-redo-test-')
        base = Path(self.temp.name)
        self.source = base / 'source'; self.library = base / 'library'
        self.state = base / 'state'
        for d in (self.source, self.library, self.state):
            d.mkdir(parents=True)
        self._saved = (L1.SOURCE, L1.LIBRARY, L1.MOVES, L1._moved)
        L1.SOURCE, L1.LIBRARY = self.source, self.library
        L1.MOVES = self.state / 'moves.jsonl'
        L1._moved = None

    def tearDown(self):
        L1.SOURCE, L1.LIBRARY, L1.MOVES, L1._moved = self._saved
        self.temp.cleanup()

    def sha(self, i):
        return format(i, 'x').ljust(64, '0')

    def ledger(self, rows):
        write(L1.MOVES, rows)
        L1._moved = None

    def item(self, sha, rel, size=4000):
        return {'sha256': sha, 'rel': rel, 'suffix': Path(rel).suffix, 'size': size}

    # --- the bug itself ----------------------------------------------------

    def test_a_filed_workbook_is_still_readable(self):
        sha = self.sha(1)
        filed = self.library / 'M03/09p_capex.xlsx'
        filed.parent.mkdir(parents=True)
        workbook(filed, ['Demand Chart', 'Source_Data'],
                 ['MFG Revenue ($M)', 'Top 4 US Cloud'] + ['行 %d' % i for i in range(60)])
        self.ledger([{'event': 'move', 'sha256': sha, 'from': 'raw/capex.xlsx',
                      'to': 'M03/09p_capex.xlsx', 'ok': True}])
        record = L1.prepare(self.item(sha, 'raw/capex.xlsx'))
        self.assertEqual(record['level'], 'p', 'the preview came back empty again')
        self.assertIn('Demand Chart', record['preview'])
        self.assertEqual(record['meta'].get('read_from'), 'library')

    def test_a_file_still_at_its_source_path_costs_no_ledger_lookup(self):
        sha = self.sha(2)
        src = self.source / 'raw/plain.txt'
        src.parent.mkdir(parents=True)
        src.write_text('内容 ' * 200, encoding='utf-8')
        self.ledger([])
        record = L1.prepare(self.item(sha, 'raw/plain.txt'))
        self.assertEqual(record['level'], 'p')
        self.assertNotIn('read_from', record['meta'])

    def test_a_file_that_is_nowhere_reports_the_source_path(self):
        sha = self.sha(3)
        self.ledger([])
        path, moved = L1.readable_path(self.item(sha, 'raw/gone.pdf'))
        self.assertFalse(moved)
        self.assertEqual(path, self.source / 'raw/gone.pdf')

    # --- the ledger replay -------------------------------------------------

    def test_the_last_move_wins_after_a_rename(self):
        sha = self.sha(4)
        final = self.library / '_drawings_unread/proj/__n_proj_x.dwg'
        final.parent.mkdir(parents=True)
        final.write_text('x', encoding='utf-8')
        self.ledger([
            {'event': 'move', 'sha256': sha, 'from': 'raw/x.dwg',
             'to': '_drawings_unread/__n_x.dwg', 'ok': True},
            {'event': 'move', 'sha256': sha, 'from': '_drawings_unread/__n_x.dwg',
             'to': '_drawings_unread/proj/__n_proj_x.dwg', 'ok': True},
        ])
        path, moved = L1.readable_path(self.item(sha, 'raw/x.dwg'))
        self.assertTrue(moved)
        self.assertEqual(path, final)

    def test_an_intent_row_without_an_outcome_is_not_followed(self):
        """The ledger writes intent before the move; only `ok` rows happened."""
        sha = self.sha(5)
        self.ledger([{'event': 'move', 'sha256': sha, 'from': 'raw/x.pdf',
                      'to': 'M10/x.pdf', 'ok': False}])
        path, moved = L1.readable_path(self.item(sha, 'raw/x.pdf'))
        self.assertFalse(moved)
        self.assertEqual(path, self.source / 'raw/x.pdf')

    def test_a_ledger_entry_pointing_nowhere_falls_back(self):
        sha = self.sha(6)
        self.ledger([{'event': 'move', 'sha256': sha, 'from': 'raw/x.pdf',
                      'to': 'M10/never-written.pdf', 'ok': True}])
        path, moved = L1.readable_path(self.item(sha, 'raw/x.pdf'))
        self.assertFalse(moved)
        self.assertEqual(path, self.source / 'raw/x.pdf')


class NoTextLayerTests(unittest.TestCase):
    """Visio has no text stream; re-reading it forever buys nothing."""

    def test_the_extractor_flags_it_in_a_field_not_in_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'diagram.vsd'
            path.write_bytes(OFFICE.OLE_MAGIC + b'\0' * 600)
            _, meta = OFFICE.extract(path)
            self.assertTrue(meta.get('no_text_layer') or meta.get('extract_error'),
                            'a broken container must say something')

    def test_a_flagged_file_leaves_the_redo_queue(self):
        self.assertTrue(PK.opened_and_empty({'meta': {'no_text_layer': True}}))

    def test_a_file_never_opened_stays_in_the_queue(self):
        self.assertFalse(PK.opened_and_empty({'meta': {}}))
        self.assertFalse(PK.opened_and_empty({}))

    def test_a_transient_failure_stays_in_the_queue(self):
        """The stale-path bug produced exactly this, and must not be permanent."""
        stale = {'meta': {'extract_error': 'FileNotFoundError: raw/x.xlsx'}}
        self.assertFalse(PK.opened_and_empty(stale))

    def test_a_successful_read_that_found_nothing_leaves_the_queue(self):
        self.assertTrue(PK.opened_and_empty({'meta': {'sheets': 0, 'shared_strings': 0}}))


class PreviewBudgetTests(unittest.TestCase):
    """A workbook opens with its sheet names; 400 characters can end there."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-budget-test-')
        base = Path(self.temp.name)
        self.results = base / 'l1_results.jsonl'
        self.results.write_text('', encoding='utf-8')
        self._saved = (L1.RESULTS, PK.BATCH_DIR, PK.pending, L1.prepare)
        L1.RESULTS = self.results
        PK.BATCH_DIR = base / 'batches'
        L1.prepare = self.fake_prepare

    def tearDown(self):
        (L1.RESULTS, PK.BATCH_DIR, PK.pending, L1.prepare) = self._saved
        self.temp.cleanup()

    def fake_prepare(self, item):
        return {'sha256': item['sha256'], 'rel': item['rel'], 'suffix': item['suffix'],
                'size': 1000, 'preview': '数' * 3000, 'meta': {}, 'level': 'p',
                'needs_model': True}

    def packed(self, suffix):
        items = [{'sha256': '%064x' % 1, 'rel': 'f' + suffix, 'suffix': suffix}]
        PK.pending = lambda redo=False: list(items)
        out = io.StringIO()
        with redirect_stdout(out):
            PK.cmd_pack(types.SimpleNamespace(limit=1, workers=1, out=None, redo=True))
        rows = json.loads((PK.BATCH_DIR / 'batch.json').read_text(encoding='utf-8'))
        return rows[0]['preview']

    def test_office_gets_the_wider_window(self):
        self.assertEqual(len(self.packed('.xlsx')), PK.OFFICE_PREVIEW_CHARS)

    def test_everything_else_keeps_the_narrow_one(self):
        self.assertEqual(len(self.packed('.pdf')), PK.PREVIEW_CHARS)

    def test_the_wider_window_is_actually_wider(self):
        self.assertGreater(PK.OFFICE_PREVIEW_CHARS, PK.PREVIEW_CHARS)


if __name__ == '__main__':
    unittest.main()
