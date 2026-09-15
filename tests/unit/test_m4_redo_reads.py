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
import hashlib
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
import zipfile

from inresearch.adapters import office as OFFICE
import inresearch.adapters.office_container as office_container
from inresearch.materials import triage as L1
from inresearch.workflow import terminal_batch as PK
from inresearch.workflow import l1_batch as L1B


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
        sha = hashlib.sha256(filed.read_bytes()).hexdigest()
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
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        self.ledger([])
        record = L1.prepare(self.item(sha, 'raw/plain.txt'))
        self.assertEqual(record['level'], 'p')
        self.assertNotIn('read_from', record['meta'])

    def test_changed_bytes_cannot_be_read_under_an_old_inventory_hash(self):
        from unittest.mock import patch
        source = self.source / 'paper.txt'
        source.write_text('版本一 ' * 100)
        item = self.item(hashlib.sha256(source.read_bytes()).hexdigest(), 'paper.txt')
        source.write_text('版本二 ' * 100)
        with self.assertRaisesRegex(ValueError, 'refresh_inventory'):
            L1.prepare(item)
        item['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()

        def replace_while_extracting(path, suffix):
            source.write_text('版本三 ' * 100)
            return '旧版本抽取文本 ' * 100, {}

        with patch.object(L1, 'extract_preview', side_effect=replace_while_extracting):
            with self.assertRaisesRegex(ValueError, 'during_read'):
                L1.prepare(item)

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
            path.write_bytes(office_container.OLE_MAGIC + b'\0' * 600)
            _, meta = OFFICE.extract(path)
            self.assertTrue(meta.get('no_text_layer') or meta.get('extract_error'),
                            'a broken container must say something')

    def test_a_flagged_file_leaves_the_redo_queue(self):
        self.assertTrue(PK.opened_and_empty({'meta': {'no_text_layer': True}}))

    def test_the_flag_alone_decides_regardless_of_the_wording(self):
        """The verdict must not depend on matching prose in extract_error.

        Two rounds of merges have already put the string match back; a test
        that only ever passes a bare flag cannot tell the implementations
        apart, because both accept it.  This one changes the wording, so a
        reader that greps the message fails here.
        """
        reworded = {'meta': {'no_text_layer': True,
                             'extract_error': 'OLE2 container has no text stream'}}
        self.assertTrue(PK.opened_and_empty(reworded),
                        'the verdict is being read out of the error message')

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
        self._saved = (L1.RESULTS, PK.BATCH_DIR, L1B.pending, L1.prepare)
        L1.RESULTS = self.results
        PK.BATCH_DIR = base / 'batches'
        L1.prepare = self.fake_prepare

    def tearDown(self):
        (L1.RESULTS, PK.BATCH_DIR, L1B.pending, L1.prepare) = self._saved
        self.temp.cleanup()

    def fake_prepare(self, item):
        return {'sha256': item['sha256'], 'rel': item['rel'], 'suffix': item['suffix'],
                'size': 1000, 'preview': '数' * 3000, 'meta': {}, 'level': 'p',
                'needs_model': True}

    def packed(self, suffix):
        items = [{'sha256': '%064x' % 1, 'rel': 'f' + suffix, 'suffix': suffix}]
        L1B.pending = lambda cohort='new', shas=None: list(items)
        out = io.StringIO()
        with redirect_stdout(out):
            PK.cmd_pack(types.SimpleNamespace(limit=1, workers=1, out=None, redo=True))
        rows = json.loads((PK.BATCH_DIR / 'batch.json').read_text(encoding='utf-8'))
        return rows[0]['preview']

    def test_office_gets_the_wider_window(self):
        self.assertEqual(len(self.packed('.xlsx')), L1B.OFFICE_PREVIEW_CHARS)

    def test_everything_else_keeps_the_narrow_one(self):
        self.assertEqual(len(self.packed('.pdf')), L1B.PREVIEW_CHARS)

    def test_the_wider_window_is_actually_wider(self):
        self.assertGreater(L1B.OFFICE_PREVIEW_CHARS, L1B.PREVIEW_CHARS)


class MovedIndexConcurrencyTests(unittest.TestCase):
    """pack builds previews on a thread pool; a half-built index is invisible.

    The first version assigned the empty dict to the global and filled it
    afterwards, so every other thread saw "not None", took the partial index,
    missed, fell back to the path the file had already left, and produced an
    empty preview without raising.  On the real corpus the same command
    returned 118 to 174 previews out of 200, differing run to run - which is
    why single-threaded tests, including the ones added with the fix itself,
    all passed.
    """

    ROWS = 400
    WORKERS = 8

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-index-concurrency-')
        self._saved = (L1.MOVES, L1._moved, L1.read_rows)
        L1.MOVES = Path(self.temp.name) / 'moves.jsonl'
        write(L1.MOVES, [
            {'event': 'move', 'sha256': '%064x' % i,
             'from': 'raw/f%d.pdf' % i, 'to': 'M10/f%d.pdf' % i, 'ok': True}
            for i in range(self.ROWS)])
        original = L1.read_rows
        self.builds = 0

        def slow_rows(path):
            self.builds += 1
            for row in original(path):
                time.sleep(0.0004)
                yield row

        L1.read_rows = slow_rows
        L1._moved = None

    def tearDown(self):
        L1.MOVES, L1._moved, L1.read_rows = self._saved
        self.temp.cleanup()

    def test_every_thread_sees_a_complete_index(self):
        seen, errors = [], []
        barrier = threading.Barrier(self.WORKERS)

        def worker():
            try:
                barrier.wait(timeout=5)
                seen.append(len(L1.moved_index()))
            except Exception as exc:            # noqa: BLE001 - reported below
                errors.append(repr(exc))

        threads = [threading.Thread(target=worker) for _ in range(self.WORKERS)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=30)

        self.assertEqual(errors, [])
        self.assertEqual(len(seen), self.WORKERS)
        self.assertEqual(set(seen), {self.ROWS},
                         'a thread took a half-built index: %s' % sorted(set(seen)))

    def test_the_index_is_built_once_not_once_per_thread(self):
        threads = [threading.Thread(target=L1.moved_index) for _ in range(self.WORKERS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(self.builds, 1, 'the ledger was re-read per thread')

    def test_appended_revert_refreshes_the_cached_index(self):
        self.assertEqual(len(L1.moved_index()), self.ROWS)
        with L1.MOVES.open('a') as stream:
            stream.write(json.dumps({'event': 'revert', 'from': 'M10/f0.pdf',
                                      'to': 'raw/f0.pdf', 'sha256': '%064x' % 0, 'ok': True}) + '\n')
        self.assertNotIn('%064x' % 0, L1.moved_index())
        self.assertEqual(self.builds, 2)


if __name__ == '__main__':
    unittest.main()
