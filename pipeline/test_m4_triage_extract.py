#!/usr/bin/env python3
"""Contract tests for digest extraction concurrency and the throughput measure."""
from contextlib import redirect_stdout
import calendar
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m4_triage_extract as EX
import m4_triage_pack as PK
import m4_triage_l1 as L1


def stamp(text):
    return calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ"))


class WorkingRateTests(unittest.TestCase):
    def test_idle_nights_do_not_drag_the_rate_down(self):
        # Two bursts of one file every 6 seconds, 20 hours apart.
        burst = [stamp("2026-09-09T01:00:00Z") + 6 * i for i in range(20)]
        later = [stamp("2026-09-09T21:00:00Z") + 6 * i for i in range(20)]
        rate = PK.working_rate(burst + later)
        self.assertAlmostEqual(rate, 10.0, places=1)  # 6s per file is 10/min

    def test_too_few_or_unusable_stamps_report_nothing(self):
        self.assertIsNone(PK.working_rate([]))
        self.assertIsNone(PK.working_rate([stamp("2026-09-09T01:00:00Z")]))
        far = [stamp("2026-09-09T01:00:00Z"), stamp("2026-09-09T09:00:00Z")]
        self.assertIsNone(PK.working_rate(far))  # only an idle gap: nothing measured

    def test_stamps_are_read_from_digest_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "digests.jsonl"
            path.write_text(
                json.dumps({"sha256": "a", "at": "2026-09-09T01:00:00Z"}) + "\n"
                + json.dumps({"sha256": "b"}) + "\n"          # older row, no stamp
                + "not json\n"
                + json.dumps({"sha256": "c", "at": "2026-09-09T01:00:05Z"}) + "\n",
                encoding="utf-8")
            self.assertEqual(len(PK.digest_stamps([path])), 2)


class ExtractRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m4-extract-test-")
        base = Path(self.temp.name)
        self.digests = base / "digests.jsonl"
        self.results = base / "l1_results.jsonl"
        self.results.write_text("", encoding="utf-8")
        self.peak = self.live = 0
        self.guard = threading.Lock()
        self._saved = (EX.DIGESTS, L1.RESULTS, PK.pending, EX.extract,
                       EX.done_digests, L1.prepare, L1.finalize, L1.proposed_name)
        EX.DIGESTS = self.digests
        L1.RESULTS = self.results
        EX.done_digests = lambda: set()
        L1.prepare = lambda item: {"rel": item["rel"], "suffix": ".pdf", "size": 10,
                                   "preview": "p", "meta": {}, "level": "p",
                                   "needs_model": item.get("needs_model", True),
                                   "sha256": item["sha256"]}
        L1.finalize = lambda rec, v, j, e: {"sha256": rec["sha256"], "rel": rec["rel"]}
        L1.proposed_name = lambda row: "n.pdf"
        EX.extract = self.fake_extract

    def tearDown(self):
        (EX.DIGESTS, L1.RESULTS, PK.pending, EX.extract,
         EX.done_digests, L1.prepare, L1.finalize, L1.proposed_name) = self._saved
        self.temp.cleanup()

    def fake_extract(self, rec):
        with self.guard:
            self.live += 1
            self.peak = max(self.peak, self.live)
        try:
            time.sleep(0.02)
            return {"sha256": rec["sha256"], "rel": rec["rel"], "title": "t"}
        finally:
            with self.guard:
                self.live -= 1

    def items(self, n, needs_model=True):
        return [{"sha256": "%064x" % i, "rel": "f%d.pdf" % i, "needs_model": needs_model}
                for i in range(1, n + 1)]

    def out_path(self, shard):
        if not shard:
            return self.digests
        index = int(shard.split("/")[0])
        return self.digests.with_name("digests.part%d.jsonl" % index)

    def run_cmd(self, items, workers=1, limit=0, shard=None):
        PK.pending = lambda cohort='new', shas=None: list(items)
        EX.cmd_run(types.SimpleNamespace(workers=workers, limit=limit, shard=shard))
        path = self.out_path(shard)
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def test_every_pending_file_is_extracted_once(self):
        rows = self.run_cmd(self.items(12), workers=4)
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({r["sha256"] for r in rows}), 12)

    def test_workers_actually_overlap(self):
        self.run_cmd(self.items(12), workers=4)
        self.assertGreater(self.peak, 1)
        self.assertLessEqual(self.peak, 4)

    def test_limit_is_not_overshot_by_concurrent_workers(self):
        rows = self.run_cmd(self.items(40), workers=8, limit=5)
        self.assertEqual(len(rows), 5)

    def test_sharding_partitions_without_overlap(self):
        items = self.items(40)
        first = {r["sha256"] for r in self.run_cmd(items, workers=4, shard="0/2")}
        second = {r["sha256"] for r in self.run_cmd(items, workers=4, shard="1/2")}
        self.assertFalse(first & second)
        self.assertEqual(len(first | second), 40)

    def test_extraction_failure_is_recorded_and_does_not_stop_the_run(self):
        def flaky(rec):
            if rec["rel"] == "f3.pdf":
                raise RuntimeError("model_identity_unverified")
            return {"sha256": rec["sha256"], "rel": rec["rel"], "title": "t"}
        EX.extract = flaky
        rows = self.run_cmd(self.items(6), workers=3)
        self.assertEqual(len(rows), 6)
        self.assertEqual(len([r for r in rows if r.get("error")]), 1)

    def test_files_needing_no_model_go_to_results_not_digests(self):
        rows = self.run_cmd(self.items(4, needs_model=False), workers=2)
        self.assertEqual(rows, [])
        written = [json.loads(x) for x in
                   self.results.read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertEqual(len(written), 4)

    def test_worker_count_is_bounded(self):
        for workers in (0, -1, EX.MAX_WORKERS + 1):
            with self.assertRaises(SystemExit):
                self.run_cmd(self.items(1), workers=workers)




class PackTests(unittest.TestCase):
    """Preview extraction runs in parallel without changing which files are picked."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m4-pack-test-")
        base = Path(self.temp.name)
        self.results = base / "l1_results.jsonl"
        self.results.write_text("", encoding="utf-8")
        self.peak = self.live = 0
        self.guard = threading.Lock()
        self._saved = (L1.RESULTS, PK.BATCH_DIR, PK.pending, L1.prepare,
                       L1.finalize, L1.proposed_name)
        L1.RESULTS = self.results
        PK.BATCH_DIR = base / "batches"
        L1.prepare = self.fake_prepare
        L1.finalize = lambda rec, v, j, e: {"sha256": rec["sha256"], "rel": rec["rel"]}
        L1.proposed_name = lambda row: "n.pdf"

    def tearDown(self):
        (L1.RESULTS, PK.BATCH_DIR, PK.pending, L1.prepare,
         L1.finalize, L1.proposed_name) = self._saved
        self.temp.cleanup()

    def fake_prepare(self, item):
        if item.get("boom"):
            raise RuntimeError("pdftotext failed")
        with self.guard:
            self.live += 1
            self.peak = max(self.peak, self.live)
        try:
            time.sleep(0.02)
            return {"sha256": item["sha256"], "rel": item["rel"], "suffix": ".pdf",
                    "size": 2048, "preview": "preview " + item["rel"], "meta": {},
                    "level": "p", "needs_model": item.get("needs_model", True)}
        finally:
            with self.guard:
                self.live -= 1

    def items(self, n, **extra):
        return [{"sha256": "%064x" % i, "rel": "f%d.pdf" % i, **extra} for i in range(1, n + 1)]

    def run_pack(self, items, limit=5, workers=4):
        PK.pending = lambda cohort='new', shas=None: list(items)
        PK.cmd_pack(types.SimpleNamespace(limit=limit, workers=workers, out=None))
        text = (PK.BATCH_DIR / "batch.txt").read_text(encoding="utf-8")
        return [line for line in text.splitlines() if line and not line.startswith("#")]

    def test_batch_holds_the_first_files_in_priority_order(self):
        lines = self.run_pack(self.items(20), limit=5, workers=4)
        self.assertEqual(len(lines), 5)
        self.assertEqual([line.split("|")[5] for line in lines],
                         ["f1.pdf", "f2.pdf", "f3.pdf", "f4.pdf", "f5.pdf"])

    def test_thread_count_does_not_change_the_selection(self):
        one = self.run_pack(self.items(20), limit=5, workers=1)
        eight = self.run_pack(self.items(20), limit=5, workers=8)
        self.assertEqual(one, eight)

    def test_previews_are_extracted_in_parallel(self):
        self.run_pack(self.items(20), limit=8, workers=4)
        self.assertGreater(self.peak, 1)
        self.assertLessEqual(self.peak, 4)

    def test_an_unreadable_file_does_not_kill_the_batch(self):
        items = self.items(3) + [{"sha256": "f" * 64, "rel": "bad.pdf", "boom": True}] + self.items(3)
        lines = self.run_pack(items, limit=5, workers=4)
        self.assertEqual(len(lines), 5)
        self.assertNotIn("bad.pdf", "\n".join(lines))

    def test_files_needing_no_model_are_written_and_do_not_fill_the_batch(self):
        items = self.items(3, needs_model=False) + self.items(4)
        lines = self.run_pack(items, limit=4, workers=4)
        self.assertEqual(len(lines), 4)
        written = [x for x in self.results.read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertEqual(len(written), 3)

    def test_worker_count_is_bounded(self):
        for workers in (0, -1, PK.MAX_WORKERS + 1):
            with self.assertRaises(SystemExit):
                self.run_pack(self.items(2), limit=1, workers=workers)



class PackRemainingTests(unittest.TestCase):
    """The remaining count must be measured with the queue that was packed."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m4-remaining-test-")
        base = Path(self.temp.name)
        self.results = base / "l1_results.jsonl"
        self.results.write_text("", encoding="utf-8")
        self._saved = (L1.RESULTS, PK.BATCH_DIR, PK.pending, L1.prepare,
                       L1.finalize, L1.proposed_name)
        L1.RESULTS = self.results
        PK.BATCH_DIR = base / "batches"
        L1.prepare = lambda item: {"sha256": item["sha256"], "rel": item["rel"],
                                   "suffix": ".xlsx", "size": 10, "preview": "text here",
                                   "meta": {}, "level": "p", "needs_model": True}
        L1.finalize = lambda rec, v, j, e: {"sha256": rec["sha256"], "rel": rec["rel"]}
        L1.proposed_name = lambda row: "n.xlsx"

    def tearDown(self):
        (L1.RESULTS, PK.BATCH_DIR, PK.pending, L1.prepare,
         L1.finalize, L1.proposed_name) = self._saved
        self.temp.cleanup()

    def report(self, limit, cohort=None, redo=False):
        out = io.StringIO()
        with redirect_stdout(out):
            PK.cmd_pack(types.SimpleNamespace(limit=limit, workers=2, out=None,
                                              redo=redo, cohort=cohort, sha=None))
        return json.loads(out.getvalue().splitlines()[0])

    def test_redo_remaining_counts_the_redo_queue(self):
        """Every redo file is already scored, so the plain queue reports zero."""
        redo_items = [{"sha256": "%064x" % i, "rel": "f%d.xlsx" % i} for i in range(10)]
        PK.pending = lambda cohort='new', shas=None: list(redo_items) if cohort == 'blind' else []
        report = self.report(limit=4, cohort='blind')
        self.assertEqual(report["packed"], 4)
        self.assertEqual(report["remaining_after"], 6)

    def test_the_plain_queue_still_reports_its_own_remainder(self):
        items = [{"sha256": "%064x" % i, "rel": "f%d.xlsx" % i} for i in range(7)]
        PK.pending = lambda cohort='new', shas=None: list(items) if cohort == 'new' else []
        report = self.report(limit=3)
        self.assertEqual(report["remaining_after"], 4)

    def test_the_old_redo_flag_still_means_the_blind_cohort(self):
        """--redo predates --cohort and is still what the runbooks say."""
        items = [{"sha256": "%064x" % i, "rel": "f%d.xlsx" % i} for i in range(5)]
        PK.pending = lambda cohort='new', shas=None: list(items) if cohort == 'blind' else []
        report = self.report(limit=2, redo=True)
        self.assertEqual((report["cohort"], report["packed"]), ('blind', 2))

    def test_an_unknown_cohort_is_refused_rather_than_silently_emptied(self):
        PK.pending = lambda cohort='new', shas=None: []
        with self.assertRaises(SystemExit):
            self.report(limit=1, cohort='typo')




class StatusCountsTests(unittest.TestCase):
    """A re-judged file must be counted once, at its current score.

    record appends, so l1_results.jsonl keeps every superseded row.  Counting
    lines reported the old score beside the new one: after the Office re-read
    put 773 files through a second judgement, the 8-and-above bucket read 288
    when the true figure was 282, and every category the re-read moved was
    inflated by its own stale row.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m4-status-test-")
        base = Path(self.temp.name)
        self.results = base / "l1_results.jsonl"
        self._saved = (L1.RESULTS, L1.DATA, L1.load_inventory, L1.done_keys, L1.route)
        L1.RESULTS = self.results
        L1.DATA = base
        L1.load_inventory = lambda: [{"sha256": "%064x" % i, "suffix": ".pdf",
                                      "all_excluded": False} for i in range(3)]
        L1.done_keys = lambda: {"%064x" % i for i in range(3)}
        L1.route = lambda suffix: "text"

    def tearDown(self):
        (L1.RESULTS, L1.DATA, L1.load_inventory, L1.done_keys, L1.route) = self._saved
        self.temp.cleanup()

    def write(self, rows):
        self.results.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    def status(self):
        out = io.StringIO()
        with redirect_stdout(out):
            PK.cmd_status(types.SimpleNamespace())
        lines = out.getvalue().splitlines()
        head = json.loads(lines[0])
        scores = json.loads(lines[-1].split(": ", 1)[1]) if "分数分布" in lines[-1] else {}
        return head, scores, lines

    def test_a_superseded_score_is_not_counted_again(self):
        sha = "%064x" % 0
        self.write([
            {"sha256": sha, "score": 9, "category": "M10", "status": "ok"},   # old
            {"sha256": sha, "score": 3, "category": "M03", "status": "ok"},   # current
        ])
        head, scores, lines = self.status()
        self.assertEqual(scores, {"3": 1}, "the old score was counted alongside the new one")
        self.assertEqual(head["被覆盖的旧判定行"], 1)
        self.assertTrue(any("M03" in line for line in lines))
        self.assertFalse(any("M10" in line for line in lines),
                         "the old category was counted too")

    def test_files_judged_once_are_unaffected(self):
        self.write([{"sha256": "%064x" % i, "score": 8, "category": "M06", "status": "ok"}
                    for i in range(3)])
        head, scores, _ = self.status()
        self.assertEqual(scores, {"8": 3})
        self.assertEqual(head["被覆盖的旧判定行"], 0)

    def test_a_file_without_a_score_is_left_out_of_the_distribution(self):
        self.write([{"sha256": "%064x" % 0, "category": "_drawings_unread", "status": "l0"},
                    {"sha256": "%064x" % 1, "score": 7, "category": "M04", "status": "ok"}])
        _, scores, _ = self.status()
        self.assertEqual(scores, {"7": 1})



class CellsCohortTests(unittest.TestCase):
    """Workbooks judged while the reader could not see a single value.

    Both spreadsheet readers returned labels only until the extractor was
    fixed, so every score on a workbook came from its headers.  The cohort is
    defined by the evidence rather than by a date: a stored meta with no
    `cells` count is a verdict made before a cell could be read.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-cells-')
        self.results = Path(self.temp.name) / 'l1_results.jsonl'
        self._saved = (L1.RESULTS, PK.BATCH_DIR, PK.pending, L1.prepare,
                       L1.finalize, L1.proposed_name)
        L1.RESULTS = self.results
        PK.BATCH_DIR = Path(self.temp.name) / 'batches'

    def tearDown(self):
        (L1.RESULTS, PK.BATCH_DIR, PK.pending, L1.prepare,
         L1.finalize, L1.proposed_name) = self._saved
        self.temp.cleanup()

    def write(self, rows):
        self.results.write_text(
            '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n',
            encoding='utf-8')

    def row(self, sha, suffix='.xlsx', meta=None, **over):
        return {'sha256': sha, 'rel': 'a/%s%s' % (sha[:6], suffix), 'suffix': suffix,
                'score': 6, 'status': 'ok', 'meta': {'sheets': 2, 'shared_strings': 40}
                if meta is None else meta, **over}

    def test_a_workbook_judged_before_the_fix_is_in_the_cohort(self):
        self.write([self.row('a' * 64)])
        self.assertEqual(PK.judged_without_cells(), {'a' * 64})

    def test_a_workbook_judged_after_the_fix_is_not(self):
        self.write([self.row('b' * 64, meta={'sheets': 1, 'cells': 0})])
        self.assertEqual(PK.judged_without_cells(), set())

    def test_documents_that_never_lost_anything_are_left_alone(self):
        """A .pdf and a .ppt were always read whole; only spreadsheets regressed."""
        self.write([self.row('c' * 64, suffix='.pdf'),
                    self.row('d' * 64, suffix='.ppt'),
                    self.row('e' * 64, suffix='.docx')])
        self.assertEqual(PK.judged_without_cells(), set())

    def test_the_newest_row_decides(self):
        """record appends; a file already re-judged must not come back."""
        self.write([self.row('f' * 64),
                    self.row('f' * 64, meta={'sheets': 1, 'cells': 12})])
        self.assertEqual(PK.judged_without_cells(), set())

    # -- the queue has to drain -------------------------------------------

    def pack(self, meta, limit=5):
        sha = 'a' * 64
        self.write([self.row(sha, score=6, org='某院')])
        L1.prepare = lambda item: {'sha256': sha, 'rel': 'a/x.xlsx', 'suffix': '.xlsx',
                                   'size': 10, 'preview': '一些表头', 'meta': meta,
                                   'level': 'p', 'needs_model': True}
        PK.pending = lambda cohort='new', shas=None: (
            [{'sha256': sha, 'rel': 'a/x.xlsx'}] if cohort == 'cells' else [])
        out = io.StringIO()
        with redirect_stdout(out):
            PK.cmd_pack(types.SimpleNamespace(limit=limit, workers=1, out=None,
                                              redo=False, cohort='cells', sha=None))
        return json.loads(out.getvalue().splitlines()[0])

    def test_a_workbook_with_cells_is_packed_for_judging(self):
        report = self.pack({'sheets': 1, 'cells': 124})
        self.assertEqual(report['packed'], 1)
        self.assertEqual(report['unchanged_carried_forward'], 0)

    def test_a_workbook_that_still_has_no_cells_is_not_judged_again(self):
        report = self.pack({'sheets': 1, 'cells': 0})
        self.assertEqual(report['packed'], 0)
        self.assertEqual(report['unchanged_carried_forward'], 1)

    def test_and_it_leaves_the_cohort_so_the_queue_drains(self):
        """Otherwise it sits at the head of every future pack, forever."""
        self.pack({'sheets': 1, 'cells': 0})
        self.assertEqual(PK.judged_without_cells(), set())

    def test_the_carried_row_keeps_the_old_verdict_and_says_why(self):
        self.pack({'sheets': 1, 'cells': 0})
        rows = [json.loads(l) for l in self.results.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['score'], 6)            # unchanged, not re-scored
        self.assertEqual(rows[1]['org'], '某院')
        self.assertEqual(rows[1]['rechecked']['verdict'], 'unchanged')
        self.assertEqual(rows[1]['meta']['cells'], 0)

    def test_a_failed_read_is_retried_rather_than_written_off(self):
        """A stale path is transient; a chart-only workbook is not."""
        report = self.pack({'extract_error': 'FileNotFoundError: ...'})
        self.assertEqual(report['unchanged_carried_forward'], 0)
        self.assertEqual(report['packed'], 1)


class RepeatedPackTests(unittest.TestCase):
    """Packing twice without recording rebuilds the same batch, silently.

    A file leaves its cohort when `record` writes a verdict, not when `pack`
    writes the batch.  Run four times in a row, pack printed four identical
    lines - packed 200, remaining_after 560 - and nothing had advanced.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-repeat-')
        base = Path(self.temp.name)
        self.results = base / 'l1_results.jsonl'
        self.results.write_text('', encoding='utf-8')
        self._saved = (L1.RESULTS, PK.BATCH_DIR, PK.pending, L1.prepare,
                       L1.finalize, L1.proposed_name)
        L1.RESULTS = self.results
        PK.BATCH_DIR = base / 'batches'
        L1.prepare = lambda item: {'sha256': item['sha256'], 'rel': item['rel'],
                                   'suffix': '.xlsx', 'size': 10, 'preview': '表头',
                                   'meta': {'cells': 9}, 'level': 'p', 'needs_model': True}
        # The batch id is sha256[:12], so the hashes have to differ in their
        # FIRST twelve characters.  '%064x' % i pads on the left: f0 through f3
        # all carry the id '000000000000' and every overlap count comes out
        # wrong.  Two earlier fixtures in this repo were bitten the same way.
        self.items = [{'sha256': '%03d' % i + 'a' * 61, 'rel': 'f%d.xlsx' % i}
                      for i in range(10)]
        PK.pending = lambda cohort='new', shas=None: list(self.items) if cohort == 'cells' else []

    def tearDown(self):
        (L1.RESULTS, PK.BATCH_DIR, PK.pending, L1.prepare,
         L1.finalize, L1.proposed_name) = self._saved
        self.temp.cleanup()

    def pack(self, limit=4):
        out = io.StringIO()
        with redirect_stdout(out):
            PK.cmd_pack(types.SimpleNamespace(limit=limit, workers=1, out=None,
                                              redo=False, cohort='cells', sha=None))
        return json.loads(out.getvalue().splitlines()[0])

    def test_the_first_pack_says_nothing_about_repeats(self):
        first = self.pack()
        self.assertEqual(first['packed'], 4)
        self.assertNotIn('与上一批重复', first)

    def test_the_second_pack_says_it_is_the_same_batch(self):
        self.pack()
        second = self.pack()
        self.assertEqual(second['与上一批重复'], 4)
        self.assertIn('record', second['note'])

    def test_a_partly_overlapping_batch_reports_the_overlap_without_the_note(self):
        """Still worth showing, but it is not the stuck case."""
        self.pack(limit=4)
        self.items = self.items[2:]          # the first two got recorded
        second = self.pack(limit=4)
        self.assertEqual(second['与上一批重复'], 2)
        self.assertNotIn('note', second)


class PartialRecordTests(unittest.TestCase):
    """A verdicts file still being written reads exactly like a finished one.

    The judging session appends as it goes.  Recording against it mid-write
    printed {"recorded": 28, "rejected": 0} - nothing wrong with any row, and
    no sign that 172 of the batch were simply not in the file yet.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-partial-')
        base = Path(self.temp.name)
        self.results = base / 'l1_results.jsonl'
        self.results.write_text('', encoding='utf-8')
        self.batch_dir = base / 'batches'
        self.batch_dir.mkdir()
        self._saved = (L1.RESULTS, PK.BATCH_DIR, L1.load_inventory,
                       L1.finalize, L1.proposed_name)
        L1.RESULTS = self.results
        PK.BATCH_DIR = self.batch_dir
        # Ids are sha256[:12], so the hashes must differ in their first twelve.
        self.shas = ['%03d' % i + 'b' * 61 for i in range(5)]
        L1.load_inventory = lambda: [{'sha256': sha, 'rel': 'f%d.xlsx' % i,
                                      'suffix': '.xlsx', 'size': 10,
                                      'paths': ['f%d.xlsx' % i], 'copies': 1}
                                     for i, sha in enumerate(self.shas)]
        L1.finalize = lambda rec, parsed, judge, err: {**rec, **parsed}
        L1.proposed_name = lambda row: 'n.xlsx'
        (self.batch_dir / 'batch.json').write_text(json.dumps(
            [{'id': sha[:12], 'path': 'f%d.xlsx' % i, 'level': 'p',
              'preview': '表头', 'meta': {'cells': 9}}
             for i, sha in enumerate(self.shas)]), encoding='utf-8')

    def tearDown(self):
        (L1.RESULTS, PK.BATCH_DIR, L1.load_inventory,
         L1.finalize, L1.proposed_name) = self._saved
        self.temp.cleanup()

    def record(self, count):
        path = Path(self.temp.name) / 'verdicts.txt'
        path.write_text('\n'.join(
            '%s|6|M10|dataset|2016|某院|表 %d|1|h|理由' % (self.shas[i][:12], i)
            for i in range(count)), encoding='utf-8')
        out = io.StringIO()
        with redirect_stdout(out):
            PK.cmd_record(types.SimpleNamespace(verdicts=str(path), batch=None,
                                                digests=False))
        return json.loads(out.getvalue().splitlines()[0])

    def test_a_partly_written_file_says_how_much_is_missing(self):
        report = self.record(2)
        self.assertEqual((report['recorded'], report['rejected']), (2, 0))
        self.assertEqual(report['batch_size'], 5)
        self.assertEqual(report['未判的'], 3)
        self.assertIn('record', report['note'])

    def test_a_complete_batch_carries_no_warning(self):
        report = self.record(5)
        self.assertEqual(report['recorded'], 5)
        self.assertNotIn('未判的', report)
        self.assertNotIn('note', report)

    def test_recording_the_same_file_again_is_safe(self):
        """The fix for a partial record is to re-run it, so it must be idempotent."""
        self.record(2)
        report = self.record(5)
        self.assertEqual(report['recorded'], 5)
        rows = [json.loads(l) for l in self.results.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows), 7)              # 2 superseded + 5 current
        newest = {}
        for r in rows:
            newest[r['sha256']] = r
        self.assertEqual(len(newest), 5)


class NamedRejudgeTests(unittest.TestCase):
    """The way back when a later batch shows an earlier verdict was wrong.

    Round two of the re-judge caught round one calling an AMD platform 国产化,
    one round after that verdict was recorded.  Every selector here answers
    "what is owed"; none of them could answer "this one, again".
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-named-')
        base = Path(self.temp.name)
        self.results = base / 'l1_results.jsonl'
        self._saved = (L1.RESULTS, PK.BATCH_DIR, L1.load_inventory, L1.prepare,
                       L1.finalize, L1.proposed_name)
        L1.RESULTS = self.results
        PK.BATCH_DIR = base / 'batches'
        self.shas = ['%03d' % i + 'c' * 61 for i in range(4)]
        self.results.write_text('\n'.join(json.dumps(
            {'sha256': sha, 'rel': 'f%d.xlsx' % i, 'suffix': '.xlsx', 'score': 6,
             'status': 'ok', 'meta': {'cells': 9}})
            for i, sha in enumerate(self.shas)) + '\n', encoding='utf-8')
        L1.load_inventory = lambda: [{'sha256': sha, 'rel': 'f%d.xlsx' % i,
                                      'suffix': '.xlsx', 'size': 10,
                                      'paths': ['f%d.xlsx' % i], 'copies': 1}
                                     for i, sha in enumerate(self.shas)]
        L1.prepare = lambda item: {'sha256': item['sha256'], 'rel': item['rel'],
                                   'suffix': '.xlsx', 'size': 10, 'preview': '表头',
                                   'meta': {'cells': 9}, 'level': 'p', 'needs_model': True}

    def tearDown(self):
        (L1.RESULTS, PK.BATCH_DIR, L1.load_inventory, L1.prepare,
         L1.finalize, L1.proposed_name) = self._saved
        self.temp.cleanup()

    def pack(self, sha=None, cohort='cells'):
        out = io.StringIO()
        with redirect_stdout(out):
            PK.cmd_pack(types.SimpleNamespace(limit=50, workers=1, out=None,
                                              redo=False, cohort=cohort, sha=sha))
        return json.loads(out.getvalue().splitlines()[0])

    def ids(self):
        rows = json.loads((PK.BATCH_DIR / 'batch.json').read_text(encoding='utf-8'))
        return sorted(r['id'] for r in rows)

    def test_one_named_file_is_packed_alone(self):
        report = self.pack(sha=self.shas[2][:6])
        self.assertEqual(report['packed'], 1)
        self.assertEqual(self.ids(), [self.shas[2][:12]])

    def test_several_can_be_named_at_once(self):
        self.pack(sha='%s,%s' % (self.shas[0][:6], self.shas[3][:6]))
        self.assertEqual(self.ids(), sorted([self.shas[0][:12], self.shas[3][:12]]))

    def test_an_already_recorded_file_is_reachable(self):
        """Every one of these has a verdict; the cohort selectors would skip it."""
        self.assertEqual(self.pack(sha=self.shas[1][:6])['packed'], 1)

    def test_an_ambiguous_prefix_is_refused(self):
        with self.assertRaises(SystemExit):
            self.pack(sha='0')

    def test_a_prefix_matching_nothing_is_refused(self):
        with self.assertRaises(SystemExit):
            self.pack(sha='zzz')

    def test_without_sha_the_cohort_still_decides(self):
        report = self.pack(cohort='new')
        self.assertEqual(report['packed'], 0)      # every file already judged

if __name__ == '__main__':
    unittest.main()
