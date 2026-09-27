import base64
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from inresearch.adapters import models, ocr_worker

SHA = "a" * 64


class FakeSpark:
    """Stands in for ssh/scp/pdfinfo/pdftoppm; records every uploaded page name."""
    def __init__(self, pages, done=(), upload_fails=False):
        self.pages, self.done, self.upload_fails = pages, done, upload_fails
        self.uploaded = []

    def __call__(self, args, timeout=300, input=None):
        ok = mock.Mock(returncode=0, stdout="", stderr="")
        if args[0] == "pdfinfo":
            ok.stdout = "Pages: %d\n" % self.pages
        elif args[0] == "pdftoppm":
            Path(args[-1] + ".png").write_bytes(b"png")
        elif args[0] == "ssh" and "python3 -c" in args[-1]:
            ok.stdout = "".join("%d\n" % i for i in self.done)
        elif args[0] == "scp" and args[-1].endswith("/pages/"):
            if self.upload_fails:
                return mock.Mock(returncode=1, stdout="", stderr="lost")
            self.uploaded += [Path(p).name for p in args[2:-1]]
        return ok


def ocr_failing_on(bad_page):
    def ocr(image):
        page = int(re.search(r"page-(\d+)", str(image)).group(1))
        if page == bad_page:
            raise models.InferenceError("model_output_truncated")
        return {"text": "第%d页 300 W" % page, "blank": False, "unreadable": False, "_model": "m"}
    return ocr


class ResumeTests(unittest.TestCase):
    doc = {"doc_id": "doc-a", "revision_id": "rev-a", "sha256": SHA, "original_rel": "o/a.pdf", "state": "blocked"}

    def process(self, spark, bad_page=None):
        with mock.patch.object(ocr_worker, "run", spark), \
             mock.patch.object(ocr_worker.hashlib, "sha256", return_value=mock.Mock(hexdigest=lambda: SHA)), \
             mock.patch.object(Path, "read_bytes", return_value=b""), \
             mock.patch.object(ocr_worker, "ocr", side_effect=ocr_failing_on(bad_page)) as ocr:
            ocr_worker.process(self.doc)
        return ocr

    def test_failed_page_keeps_the_pages_before_it_and_names_the_page(self):
        spark = FakeSpark(pages=4)
        with self.assertRaises(RuntimeError) as caught:
            self.process(spark, bad_page=3)
        self.assertEqual(spark.uploaded, ["000001.json", "000002.json"])
        self.assertIn("model_output_truncated@page3/4", str(caught.exception))
        self.assertIn("kept 2 new pages", str(caught.exception))

    def test_rerun_skips_pages_spark_already_holds(self):
        spark = FakeSpark(pages=4, done=(1, 2))
        ocr = self.process(spark)
        self.assertEqual(spark.uploaded, ["000003.json", "000004.json"])
        self.assertEqual(ocr.call_count, 4)  # two passes each for pages 3 and 4 only

    def test_nothing_left_to_read_uploads_nothing(self):
        spark = FakeSpark(pages=2, done=(1, 2))
        ocr = self.process(spark)
        self.assertEqual((spark.uploaded, ocr.call_count), ([], 0))

    def test_failed_upload_after_a_failed_page_says_nothing_was_kept(self):
        spark = FakeSpark(pages=3, upload_fails=True)
        with self.assertRaises(RuntimeError) as caught:
            self.process(spark, bad_page=2)
        self.assertIn("@page2/3; kept 0 new pages (result_upload_failed)", str(caught.exception))


class DonePagesTests(unittest.TestCase):
    def test_only_well_named_pages_for_the_same_bytes_count(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "pages"
            target.mkdir()
            page = lambda i, sha=SHA: json.dumps({"page_index": i, "content_sha256": sha})
            (target / "000001.json").write_text(page(1))
            (target / "000002.json").write_text(page(2, "b" * 64))   # other bytes
            (target / "000009.json").write_text(page(3))             # wrong name
            (target / "000004.json").write_text("{not json")
            (target / "000005.json").write_text(page(5))
            seen = {}

            def fake_run(args, timeout=300, input=None):
                code = base64.b64decode(re.search(r"b64decode\('([^']+)'\)", args[-1]).group(1)).decode()
                import contextlib, io
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    exec(code, {})
                seen["args"] = args
                return mock.Mock(returncode=0, stdout=out.getvalue(), stderr="")
            with mock.patch.object(ocr_worker, "run", fake_run):
                done = ocr_worker.remote_done_pages({"sha256": SHA}, str(target))
            self.assertEqual(done, {1, 5})
            self.assertEqual(seen["args"][:3], ["ssh", "-o", "BatchMode=yes"])

    def test_missing_directory_or_ssh_failure_means_redo_everything(self):
        with mock.patch.object(ocr_worker, "run", return_value=mock.Mock(returncode=255, stdout="1\n2\n", stderr="")):
            self.assertEqual(ocr_worker.remote_done_pages({"sha256": SHA}, "/nope"), set())


if __name__ == "__main__":
    unittest.main()
