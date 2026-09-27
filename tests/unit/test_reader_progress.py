import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import test_continuous_reader as fixtures
from inresearch.delivery import reader_progress as progress
from inresearch.workflow import reader as cr


def journal(lines):
    return lambda since: lines


class ProgressPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="inresearch-progress-test-")
        base = Path(self.temp.name)
        self.data = base / "data"
        reader = cr.Reader(self.data, base / "state", base / "repo", fixtures.Model(), 0, 200, fixtures.Clock()).initialize()
        raw = self.data / "raw-materials"
        raw.mkdir(parents=True, exist_ok=True)
        (raw / "paper.txt").write_text("服务器功率为 300 W。\n这是完整正文与注释。\n", encoding="utf-8")
        (raw / "other.txt").write_text("机柜功率为 40 kW。\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            reader.run(once=True)
        self.doc = reader.conn.execute("SELECT doc_id,current_revision_id FROM documents WHERE original_name='paper.txt'").fetchone()
        reader.conn.execute("UPDATE reading_runs SET priority=9 WHERE doc_id=?", (self.doc[0],))
        reader.conn.commit()
        reader.close()
        pages = self.data / "offload/m4/results" / self.doc[0] / "pages"
        pages.mkdir(parents=True)
        for i in (1, 2):
            (pages / ("%06d.json" % i)).write_text("{}")
        (self.data / "offload/m4/claims" / self.doc[1]).mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def collect(self, lines=()):
        return progress.collect(self.data, journal=journal(list(lines)), service=lambda: "active", celsius=lambda: 71.5)

    def test_priority_documents_m4_pages_and_claims_are_shown(self):
        s = self.collect()
        self.assertEqual([r["original_name"] for r in s["priority"]], ["paper.txt"])
        self.assertEqual(s["priority"][0]["m4_pages"], 2)
        self.assertEqual([c["name"] for c in s["claims"]], ["paper.txt"])
        self.assertEqual(s["documents"].get("complete"), 2)
        page = progress.render(s)
        self.assertIn("paper.txt", page)
        self.assertNotIn("other.txt", page)       # below the priority floor
        self.assertIn('http-equiv="refresh"', page)
        self.assertIn("71.5 ℃", page)

    def test_heat_share_comes_from_the_reader_journal(self):
        lines = [json.dumps({"thermal": "pause", "celsius": c, "seconds": 120.0}) for c in (86.7, 84.1, 87.2)]
        lines += ["not json", json.dumps({"stage": "read", "outcome": "succeeded"})]
        h = self.collect(lines)["heat"]
        self.assertEqual((h["pauses"], h["paused_seconds"], h["peak_c"]), (3, 360.0, 87.2))
        self.assertAlmostEqual(h["share"], 0.1)
        self.assertIsNone(progress.heat(None, 3600))

    def test_page_never_writes_to_the_catalog(self):
        catalog = self.data / "catalog" / "catalog.sqlite"
        rows = lambda: [tuple(r) for r in sqlite3.connect(catalog).execute(
            "SELECT revision_id,state,priority,updated FROM reading_runs ORDER BY 1")]
        before = catalog.read_bytes(), rows()
        progress.render(self.collect())
        # A WAL reader may create -wal/-shm beside the file; the catalog itself is untouched.
        self.assertEqual((catalog.read_bytes(), rows()), before)
        with self.assertRaises(sqlite3.OperationalError):
            conn = sqlite3.connect("file:%s?mode=ro" % catalog, uri=True)
            try:
                conn.execute("UPDATE reading_runs SET priority=1")
            finally:
                conn.close()

    def test_a_recovered_error_is_hidden_and_a_blocking_one_shown(self):
        conn = sqlite3.connect(self.data / "catalog" / "catalog.sqlite")
        conn.execute("UPDATE reading_runs SET state='running',error_code='model_output_invalid' WHERE doc_id=?", (self.doc[0],))
        conn.commit()
        self.assertNotIn("model_output_invalid", progress.render(self.collect()))
        conn.execute("UPDATE reading_runs SET state='blocked',error_code='model_output_truncated' WHERE doc_id=?", (self.doc[0],))
        conn.commit(); conn.close()
        self.assertIn("model_output_truncated", progress.render(self.collect()))

    def test_claim_floor_is_shown(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"READER_CLAIM_MIN_PRIORITY": "7"}):
            page = progress.render(self.collect())
        self.assertIn("只读优先级 ≥ 7 的文档", page)
        self.assertIn("读取全部排队文档", progress.render(self.collect()))

    def test_names_are_escaped(self):
        conn = sqlite3.connect(self.data / "catalog" / "catalog.sqlite")
        conn.execute("UPDATE documents SET original_name='<script>x</script>.txt' WHERE doc_id=?", (self.doc[0],))
        conn.commit(); conn.close()
        page = progress.render(self.collect())
        self.assertNotIn("<script>x", page)
        self.assertIn("&lt;script&gt;x", page)

    def test_missing_catalog_is_reported_not_created(self):
        with tempfile.TemporaryDirectory() as d:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(progress.main(["--data-root", d]), 1)
            self.assertIn("catalog_missing", err.getvalue())
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_html_file_is_written_whole(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "progress.html"
            snapshot, original = self.collect(), progress.collect
            progress.collect = lambda data, floor: snapshot
            try:
                self.assertEqual(progress.main(["--data-root", str(self.data), "--html", str(target)]), 0)
            finally:
                progress.collect = original
            self.assertTrue(target.read_text(encoding="utf-8").startswith("<!doctype html>"))
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["progress.html"])


if __name__ == "__main__":
    unittest.main()
