import base64
import contextlib
import importlib
import io
import os
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from inresearch.adapters import ocr_worker


def remote_code(command):
    return base64.b64decode(re.search(r"b64decode\('([^']+)'\)", command).group(1)).decode()


class NamedDocumentTests(unittest.TestCase):
    def query_rows(self, doc_ids, rows):
        """Run the generated remote query against a stand-in catalog view."""
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "catalog.sqlite"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE execution_readings (doc_id,sha256,original_rel,original_name,revision_id,state,suffix,error_code,updated)")
            conn.executemany("INSERT INTO execution_readings VALUES (?,?,?,?,?,?,?,?,?)", rows)
            conn.commit(); conn.close()
            seen = {}

            def fake_run(args, timeout=300, input=None):
                code = remote_code(args[-1]).replace("/home/spark/.local/share/inresearch.ai/catalog/catalog.sqlite", str(db))
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    exec(code, {})
                seen["code"] = code
                return mock.Mock(returncode=0, stdout=out.getvalue(), stderr="")
            with mock.patch.object(ocr_worker, "run", fake_run):
                return ocr_worker.remote_candidates(1, doc_ids), seen["code"]

    def test_named_documents_include_queued_deferred_pdfs_only(self):
        rows = [("doc-a", "a" * 64, "o/a.pdf", "a.pdf", "rev-a", "queued", ".pdf", "ocr_deferred_behind_text_documents", 1),
                ("doc-b", "b" * 64, "o/b.pdf", "b.pdf", "rev-b", "complete", ".pdf", None, 2),
                ("doc-c", "c" * 64, "o/c.txt", "c.txt", "rev-c", "queued", ".txt", None, 3),
                ("doc-d", "d" * 64, "o/d.pdf", "d.pdf", "rev-d", "queued", ".pdf", None, 4)]
        found, code = self.query_rows(("doc-a", "doc-b", "doc-c"), rows)
        self.assertEqual([r["doc_id"] for r in found], ["doc-a"])
        self.assertEqual(found[0]["state"], "queued")
        self.assertIn("mode=ro", code)

    def test_without_names_only_blocked_ocr_errors_are_offered(self):
        rows = [("doc-a", "a" * 64, "o/a.pdf", "a.pdf", "rev-a", "queued", ".pdf", "ocr_deferred_behind_text_documents", 1),
                ("doc-e", "e" * 64, "o/e.pdf", "e.pdf", "rev-e", "blocked", ".pdf", "scanned_page_requires_ocr", 5)]
        found, _ = self.query_rows((), rows)
        self.assertEqual([r["doc_id"] for r in found], ["doc-e"])

    def test_queued_document_is_not_retried_and_every_named_one_is_processed(self):
        a, f = "doc-" + "a" * 64, "doc-" + "f" * 64
        docs = [{"doc_id": a, "revision_id": "rev-a", "state": "queued"},
                {"doc_id": f, "revision_id": "rev-f", "state": "queued"}]
        with mock.patch.object(ocr_worker.models, "configured_client"), \
             mock.patch.object(ocr_worker, "remote_candidates", return_value=docs) as candidates, \
             mock.patch.object(ocr_worker, "claim", return_value=True), \
             mock.patch.object(ocr_worker, "process") as process, \
             mock.patch("sys.argv", ["ocr-worker", "--doc-id", a, "--doc-id", f]), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            ocr_worker.main()
        candidates.assert_called_once_with(1, (a, f))
        self.assertEqual([c.args[0]["doc_id"] for c in process.call_args_list], [a, f])
        self.assertEqual([json.loads(l)["outcome"] for l in out.getvalue().splitlines()], ["submitted", "submitted"])

    def test_worker_never_asks_spark_to_retry(self):
        calls = []

        def fake_run(args, timeout=300, input=None):
            calls.append(args)
            return mock.Mock(returncode=0, stdout="Pages: 1\n", stderr="")
        for state in ("queued", "blocked"):
            calls.clear()
            doc = {"doc_id": "doc-a", "revision_id": "rev-a", "sha256": "x", "original_rel": "o/a.pdf", "state": state}
            with mock.patch.object(ocr_worker, "run", fake_run), \
                 mock.patch.object(ocr_worker.hashlib, "sha256", return_value=mock.Mock(hexdigest=lambda: "x")), \
                 mock.patch.object(Path, "read_bytes", return_value=b""), \
                 mock.patch.object(Path, "is_file", return_value=True), \
                 mock.patch.object(ocr_worker, "ocr", return_value={"text": "1", "blank": False, "unreadable": False, "_model": "m"}):
                ocr_worker.process(doc)
            self.assertFalse(any("retry" in a for a in calls), state)
            self.assertTrue(any(a[0] == "scp" and a[-1].endswith("/pages/") for a in calls), state)

    def test_malformed_doc_id_is_refused_before_any_remote_call(self):
        for bad in ("doc-a", "doc-" + "A" * 64, "doc-" + "a" * 63, "rev-" + "a" * 64, "doc-" + "a" * 64 + ";ls"):
            with mock.patch.object(ocr_worker, "run") as run, \
                 mock.patch.object(ocr_worker.models, "configured_client") as client, \
                 mock.patch("sys.argv", ["ocr-worker", "--doc-id", bad]), \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
                ocr_worker.main()
            self.assertEqual(stop.exception.code, 2, bad)
            run.assert_not_called()
            client.assert_not_called()

    def test_remote_alias_can_be_overridden(self):
        try:
            with mock.patch.dict(os.environ, {"INRESEARCH_SPARK_HOST": "spark"}):
                self.assertEqual(importlib.reload(ocr_worker).REMOTE, "spark")
            with mock.patch.dict(os.environ, {"INRESEARCH_SPARK_HOST": ""}):
                self.assertEqual(importlib.reload(ocr_worker).REMOTE, "spark-lan")
            env = {k: v for k, v in os.environ.items() if k != "INRESEARCH_SPARK_HOST"}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(importlib.reload(ocr_worker).REMOTE, "spark-lan")
        finally:
            importlib.reload(ocr_worker)


if __name__ == "__main__":
    unittest.main()
