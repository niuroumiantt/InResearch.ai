import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import test_continuous_reader as fixtures
from inresearch.materials import reader_contracts
from inresearch.workflow import reader as cr

LONG = "".join("第%d段：服务器功率为 %d W，机柜密度与散热方式说明。\n" % (i, 300 + i) for i in range(60))


class ReadingDepthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="inresearch-depth-test-")
        self.base = Path(self.temp.name)
        self.model = fixtures.Model()          # triage importance is 6
        self.reader = cr.Reader(self.base / "data", self.base / "state", self.base / "repo", self.model,
                                0, 200, fixtures.Clock(), full_read_min_priority=7).initialize()

    def tearDown(self):
        self.reader.close()
        self.temp.cleanup()

    def put(self, name, text):
        p = self.reader.data / "raw-materials" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        with self.reader.worker_session():
            self.reader.scan()
        return self.reader.conn.execute("SELECT * FROM reading_runs ORDER BY created DESC LIMIT 1").fetchone()

    def run_once(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.reader.run(once=True)

    def reads(self):
        return [c for c in self.model.calls if c[0] == "read"]

    def run_row(self, revision):
        return self.reader.conn.execute("SELECT * FROM reading_runs WHERE revision_id=?", (revision,)).fetchone()

    def test_below_threshold_reads_first_middle_last_and_stops_summarized(self):
        run = self.put("long.txt", LONG)
        self.run_once()
        row = self.run_row(run["revision_id"])
        self.assertGreater(row["chunks_total"], 3)
        self.assertEqual((row["state"], row["phase"], row["chunks_read"]), ("summarized", "summary", 3))
        self.assertEqual(sorted(c[1]["chunk_index"] for c in self.reads()),
                         sorted({0, row["chunks_total"] // 2, row["chunks_total"] - 1}))
        self.assertFalse([c for c in self.model.calls if c[0] == "synthesize"])
        doc = self.reader.conn.execute("SELECT current_revision_id FROM documents WHERE doc_id=?", (run["doc_id"],)).fetchone()
        self.assertIsNone(doc["current_revision_id"])
        self.assertEqual(self.reader.status()["counts"], {"summarized": 1})

    def test_priority_set_before_triage_keeps_full_reading(self):
        run = self.put("named.txt", LONG)
        with self.reader.transaction():
            self.reader.conn.execute("UPDATE reading_runs SET priority=9 WHERE revision_id=?", (run["revision_id"],))
        self.run_once()
        row = self.run_row(run["revision_id"])
        self.assertEqual((row["state"], row["priority"]), ("complete", 9))
        self.assertEqual(len(self.reads()), row["chunks_total"])

    def test_short_document_is_read_in_full_even_below_threshold(self):
        run = self.put("short.txt", "服务器功率为 300 W。\n这是完整正文与注释。\n")
        self.run_once()
        self.assertEqual(self.run_row(run["revision_id"])["state"], "complete")

    def test_deepen_continues_to_full_without_rereading_sampled_chunks(self):
        run = self.put("long.txt", LONG)
        self.run_once()
        with self.reader.worker_session():
            out = self.reader.deepen([run["doc_id"], "doc-absent"])
        self.assertEqual(out["deepened"], [run["doc_id"]])
        self.assertEqual(out["skipped"], [{"doc_id": "doc-absent", "state": "absent"}])
        self.run_once()
        row = self.run_row(run["revision_id"])
        self.assertEqual(row["state"], "complete")
        self.assertEqual(sorted(c[1]["chunk_index"] for c in self.reads()), list(range(row["chunks_total"])))

    def test_park_plans_then_blocks_and_retry_revives(self):
        run = self.put("junk.txt", LONG)
        sha = run["doc_id"][4:]
        with self.reader.worker_session():
            plan = self.reader.park([sha, "f" * 64])
        self.assertEqual(plan, {"plan": {"park": 1, "absent": 1, "already_done": 0, "already_parked": 0,
                                         "already_blocked": 0}, "reason": reader_contracts.PARKED_BY_TRIAGE, "committed": False})
        self.assertEqual(self.run_row(run["revision_id"])["state"], "queued")
        with self.reader.worker_session():
            self.reader.park([sha], commit=True)
        self.run_once()
        self.assertEqual(self.model.calls, [])
        row = self.run_row(run["revision_id"])
        self.assertEqual((row["state"], row["error_code"]), ("blocked", reader_contracts.PARKED_BY_TRIAGE))
        with self.reader.worker_session():
            self.assertEqual(self.reader.park([sha])["plan"]["already_parked"], 1)
            self.reader.retry(error_code=reader_contracts.PARKED_BY_TRIAGE)
        self.run_once()
        self.assertEqual(self.run_row(run["revision_id"])["state"], "summarized")

    def test_derived_artifacts_park_under_their_own_code_and_unknown_reason_is_refused(self):
        run = self.put("copy.txt", LONG)
        code = reader_contracts.PARK_REASONS["derived_artifact"]
        with self.reader.worker_session():
            self.reader.park([run["doc_id"][4:]], commit=True, code=code)
            with self.assertRaises(ValueError):
                self.reader.park([run["doc_id"][4:]], code="anything_else")
        self.assertEqual(self.run_row(run["revision_id"])["error_code"], code)

    def test_threshold_must_be_in_range(self):
        for bad in (0, 11, 7.0, True):
            with self.assertRaises(ValueError):
                cr.Reader(self.base / "d2", self.base / "s2", self.base / "repo", self.model, 0, 200,
                          fixtures.Clock(), full_read_min_priority=bad)


if __name__ == "__main__":
    unittest.main()
