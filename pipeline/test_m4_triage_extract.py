#!/usr/bin/env python3
"""Contract tests for digest extraction concurrency and the throughput measure."""
import calendar
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
        PK.pending = lambda: list(items)
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


if __name__ == "__main__":
    unittest.main()


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
        PK.pending = lambda: list(items)
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
