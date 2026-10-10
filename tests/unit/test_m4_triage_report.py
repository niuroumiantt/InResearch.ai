#!/usr/bin/env python3
"""The progress report must agree with the ledgers it reads, and only read."""
import json
from pathlib import Path
import tempfile
import time
import unittest

from inresearch.workflow import triage_progress as RP
from inresearch.materials import triage as L1


def stamp(offset_seconds):
    base = time.mktime(time.strptime("2026-09-10T01:00:00Z", "%Y-%m-%dT%H:%M:%SZ"))
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + offset_seconds))


def write(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m4-report-test-")
        base = Path(self.temp.name)
        self.inventory = base / "inventory.jsonl"
        self.results = base / "l1_results.jsonl"
        self.moves = base / "moves.jsonl"
        self._saved = (L1.INVENTORY, L1.RESULTS, RP.MOVES)
        L1.INVENTORY, L1.RESULTS, RP.MOVES = self.inventory, self.results, self.moves

    def tearDown(self):
        L1.INVENTORY, L1.RESULTS, RP.MOVES = self._saved
        self.temp.cleanup()

    def build(self, judged=30, auto=8, failed=2, unique=100, extra_paths=20, gap_after=None):
        rows = [{"rel": "报告/f%d.pdf" % i, "sha256": "%064d" % i, "size": 1000}
                for i in range(unique)]
        rows += [{"rel": "副本/f%d.pdf" % i, "sha256": "%064d" % i, "size": 1000}
                 for i in range(extra_paths)]
        write(self.inventory, rows)
        results = []
        for i in range(judged):
            offset = 6 * i + (20 * 3600 if gap_after is not None and i >= gap_after else 0)
            results.append({"status": "ok", "sha256": "%064d" % i, "rel": "报告/f%d.pdf" % i,
                            "score": i % 9, "category": "M01", "at": stamp(offset)})
        for i in range(judged, judged + auto):
            results.append({"status": "l0", "sha256": "%064d" % i, "rel": "报告/f%d.dwg" % i,
                            "category": "_drawings_unread"})
        for i in range(judged + auto, judged + auto + failed):
            results.append({"status": "error", "sha256": "%064d" % i, "rel": "报告/f%d.pdf" % i,
                            "error": "boom"})
        write(self.results, results)

    def test_counts_match_the_ledgers(self):
        self.build()
        snapshot = RP.collect()
        self.assertEqual(snapshot["unique_files"], 100)
        self.assertEqual(snapshot["inventory_paths"], 120)
        self.assertEqual((snapshot["judged"], snapshot["auto_filed"], snapshot["failed"]),
                         (30, 8, 2))
        self.assertEqual(snapshot["remaining"], 100 - 38)
        self.assertEqual(snapshot["percent_done"], 38.0)

    def test_moves_count_successes_minus_reverts(self):
        self.build()
        write(self.moves,
              [{"event": "move", "from": "raw/%d" % i, "to": "dup/%d" % i, "sha256": str(i), "stage": "duplicates", "ok": True} for i in range(10)]
              + [{"sha256": "x", "stage": "duplicates", "ok": False}]
              + [{"event": "revert", "from": "dup/0", "to": "raw/0", "sha256": "0", "ok": True}])
        snapshot = RP.collect()
        self.assertEqual(snapshot["moved"], 9)
        self.assertEqual(snapshot["reverted"], 1)
        self.assertEqual(snapshot["by_stage"], {"duplicates": 9})

    def test_no_move_log_yet_is_zero_not_a_crash(self):
        self.build()
        self.assertEqual(RP.collect()["moved"], 0)

    def test_an_idle_night_does_not_change_the_rate(self):
        self.build(judged=60, gap_after=30)  # 6s per file, with 20 idle hours in the middle
        self.assertAlmostEqual(RP.collect()["rate_per_minute"], 10.0, places=1)

    def test_too_few_timestamps_report_no_rate_instead_of_a_wrong_one(self):
        self.build(judged=1, auto=0, failed=0)
        snapshot = RP.collect()
        self.assertIsNone(snapshot["rate_per_minute"])
        self.assertIsNone(snapshot["eta_hours"])
        self.assertIn("样本不足", RP.render(snapshot))

    def test_a_torn_line_is_skipped_not_fatal(self):
        self.build()
        with self.results.open("a", encoding="utf-8") as handle:
            handle.write('{"status": "ok", "sha')
        self.assertEqual(RP.collect()["judged"], 30)

    def test_successful_reading_survives_failed_retry_without_inflating_progress(self):
        self.build(judged=1, auto=0, failed=0, unique=2, extra_paths=0)
        with self.results.open('a') as stream:
            stream.write(json.dumps({'sha256': '%064d' % 0, 'status': 'error'}) + '\n')
        snapshot = RP.collect()
        self.assertEqual(snapshot['judged'], 1)
        self.assertEqual(snapshot['failed'], 0)
        self.assertEqual(snapshot['remaining'], 1)

    def test_reporting_never_writes(self):
        self.build()
        write(self.moves, [{"event": "move", "from": "a", "to": "b", "sha256": "0", "stage": "duplicates", "ok": True}])
        before = {p: p.read_bytes() for p in (self.inventory, self.results, self.moves)}
        RP.render(RP.collect())
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_repeat_interval_has_a_floor(self):
        with self.assertRaises(SystemExit):
            RP.main(["--every", "5"])


if __name__ == "__main__":
    unittest.main()
