#!/usr/bin/env python3
"""Contract tests for the local-model L1 pass, including its concurrency."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m4_triage_local as LOC
import m4_triage_l1 as L1
import m4_triage_pack as PK


class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m4-local-test-")
        self.results = Path(self.temp.name) / "l1_results.jsonl"
        self.calls = []
        self.peak = 0
        self.live = 0
        self.guard = threading.Lock()
        self._saved = (L1.RESULTS, PK.pending, LOC.call, LOC.system_prompt,
                       L1.prepare, L1.finalize, L1.proposed_name)
        L1.RESULTS = self.results
        LOC.system_prompt = lambda: "system"
        L1.prepare = lambda item: {"rel": item["rel"], "suffix": ".pdf", "size": 1000,
                                   "preview": "preview text", "meta": {}, "level": "p",
                                   "needs_model": item.get("needs_model", True),
                                   "sha256": item["sha256"]}
        L1.finalize = lambda rec, v, judge, err: {"sha256": rec["sha256"], "rel": rec["rel"],
                                                  "score": (v or {}).get("score", 0),
                                                  "status": "error" if err else "ok",
                                                  "error": err}
        L1.proposed_name = lambda row: "name.pdf"
        LOC.call = self.fake_call

    def tearDown(self):
        (L1.RESULTS, PK.pending, LOC.call, LOC.system_prompt,
         L1.prepare, L1.finalize, L1.proposed_name) = self._saved
        self.temp.cleanup()

    def fake_call(self, system, user, timeout=180):
        with self.guard:
            self.live += 1
            self.peak = max(self.peak, self.live)
            self.calls.append(user)
        try:
            time.sleep(0.02)  # long enough for overlap to be observable
            return self.verdict()
        finally:
            with self.guard:
                self.live -= 1

    @staticmethod
    def verdict():
        return {"score": 5, "module": "M09", "title": "t", "org": "o", "year": "2025",
                "keep_original_name": True, "doc_type": "report", "language": "zh",
                "rationale": "source evidence", "evidence": "preview text", "confidence": "medium"}

    def items(self, n, needs_model=True):
        return [{"sha256": "%064d" % i, "rel": "f%d.pdf" % i, "suffix": ".pdf",
                 "size": 10, "needs_model": needs_model} for i in range(n)]

    def run_cmd(self, items, workers=1, limit=0):
        PK.pending = lambda: list(items)
        LOC.cmd_run(types.SimpleNamespace(workers=workers, limit=limit))
        return [json.loads(line) for line in
                self.results.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_every_pending_file_is_scored_once(self):
        rows = self.run_cmd(self.items(12), workers=4)
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({r["sha256"] for r in rows}), 12)
        self.assertEqual(len(self.calls), 12)

    def test_workers_actually_overlap(self):
        self.run_cmd(self.items(12), workers=4)
        self.assertGreater(self.peak, 1, "requests never overlapped")
        self.assertLessEqual(self.peak, 4)

    def test_single_worker_never_overlaps(self):
        self.run_cmd(self.items(6), workers=1)
        self.assertEqual(self.peak, 1)

    def test_limit_counts_only_files_that_reach_the_model(self):
        items = self.items(4, needs_model=False) + self.items(20)
        rows = self.run_cmd(items, workers=4, limit=5)
        judged = [r for r in rows if r["score"] == 5]
        self.assertLessEqual(len(self.calls), 5)
        self.assertGreaterEqual(len(judged), 1)
        # Files needing no model are written without spending the budget.
        self.assertEqual(len([r for r in rows if r["score"] == 0 and not r["error"]]), 4)

    def test_a_model_failure_is_recorded_and_does_not_stop_the_run(self):
        def flaky(system, user, timeout=180):
            if "f3.pdf" in user:
                raise RuntimeError("model_identity_unverified")
            return self.verdict()
        LOC.call = flaky
        rows = self.run_cmd(self.items(6), workers=3)
        self.assertEqual(len(rows), 6)
        failed = [r for r in rows if r["status"] == "error"]
        self.assertEqual(len(failed), 1)
        self.assertIn("model_identity_unverified", failed[0]["error"])

    def test_rows_are_whole_lines_under_concurrency(self):
        self.run_cmd(self.items(30), workers=8)
        for line in self.results.read_text(encoding="utf-8").splitlines():
            json.loads(line)  # a torn write would raise here

    def test_worker_count_is_bounded(self):
        for workers in (0, -1, LOC.MAX_WORKERS + 1):
            with self.assertRaises(SystemExit):
                self.run_cmd(self.items(1), workers=workers)


if __name__ == "__main__":
    unittest.main()
