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
    def __init__(self, pages, done=(), upload_fails=False, render_fails=None):
        self.pages, self.done, self.upload_fails, self.render_fails = pages, done, upload_fails, render_fails
        self.uploaded = []

    def __call__(self, args, timeout=300, input=None):
        ok = mock.Mock(returncode=0, stdout="", stderr="")
        if args[0] == "pdfinfo":
            ok.stdout = "Pages: %d\n" % self.pages
        elif args[0] == "pdftoppm":
            if int(args[2]) == self.render_fails:
                return mock.Mock(returncode=1, stdout="", stderr="bad page")
            Path(args[-1] + ".png").write_bytes(b"png")
        elif args[0] == "ssh" and "python3 -c" in args[-1]:
            ok.stdout = "".join("%d\n" % i for i in self.done)
        elif args[0] == "scp" and args[-1].endswith("/pages/"):
            if self.upload_fails:
                return mock.Mock(returncode=1, stdout="", stderr="lost")
            self.uploaded += [Path(p).name for p in args[2:-1]]
        return ok


def ocr_failing_on(bad_page, code="model_output_truncated", rescue_fixes=False):
    def ocr(image, rescue=False):
        page = int(re.search(r"page-(\d+)", str(image)).group(1))
        if page == bad_page and not (rescue and rescue_fixes):
            raise models.InferenceError(code)
        return {"text": "第%d页 300 W" % page, "blank": False, "unreadable": False, "_model": "m"}
    return ocr


class ResumeTests(unittest.TestCase):
    doc = {"doc_id": "doc-a", "revision_id": "rev-a", "sha256": SHA, "original_rel": "o/a.pdf", "state": "blocked"}

    def process(self, spark, bad_page=None, **failure):
        client = mock.Mock(profile=mock.Mock(identity={"model": "qwen3-vl:8b"}))
        with mock.patch.object(ocr_worker, "run", spark), \
             mock.patch.object(ocr_worker.models, "configured_client", return_value=client), \
             mock.patch.object(ocr_worker.hashlib, "sha256", return_value=mock.Mock(hexdigest=lambda: SHA)), \
             mock.patch.object(Path, "read_bytes", return_value=b""), \
             mock.patch.object(ocr_worker, "ocr", side_effect=ocr_failing_on(bad_page, **failure)) as ocr:
            self.gaps = ocr_worker.process(self.doc)
        return ocr

    def test_failed_page_keeps_the_pages_before_it_and_names_the_page(self):
        spark = FakeSpark(pages=4, render_fails=3)
        with self.assertRaises(RuntimeError) as caught:
            self.process(spark)
        self.assertEqual(spark.uploaded, ["000001.json", "000002.json"])
        self.assertIn("page_render_failed@page3/4", str(caught.exception))
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
        spark = FakeSpark(pages=3, upload_fails=True, render_fails=2)
        with self.assertRaises(RuntimeError) as caught:
            self.process(spark)
        self.assertIn("@page2/3; kept 0 new pages (result_upload_failed)", str(caught.exception))


class RescueAndGapTests(ResumeTests):
    def test_page_the_rescue_read_fixes_is_an_ordinary_page(self):
        spark = FakeSpark(pages=3)
        ocr = self.process(spark, bad_page=2, rescue_fixes=True)
        self.assertEqual((spark.uploaded, self.gaps), (["000001.json", "000002.json", "000003.json"], []))
        self.assertTrue(any(c.args[1] is True for c in ocr.call_args_list if len(c.args) > 1))

    def test_page_that_still_fails_is_uploaded_as_a_gap_and_the_rest_are_read(self):
        written = {}
        real_write = Path.write_text

        def capture(path, text, *a, **k):
            written[path.name] = json.loads(text)
            return real_write(path, text, *a, **k)
        spark = FakeSpark(pages=4)
        with mock.patch.object(Path, "write_text", capture):
            self.process(spark, bad_page=3)
        self.assertEqual(self.gaps, [3])
        self.assertEqual(spark.uploaded, ["000001.json", "000002.json", "000003.json", "000004.json"])
        gap = written["000003.json"]
        self.assertEqual((gap["method"], gap["gap"], gap["gap_reason"], gap["text"]),
                         ("m4_vision_ocr_gap", True, "model_output_truncated", ""))
        self.assertEqual(written["000004.json"]["method"], "m4_vision_ocr_double_pass")

    def test_errors_that_are_not_page_properties_never_become_gaps(self):
        spark = FakeSpark(pages=3)
        with self.assertRaises(RuntimeError) as caught:
            self.process(spark, bad_page=2, code="input_exceeds_context_budget")
        self.assertIn("input_exceeds_context_budget@page2/3", str(caught.exception))


class RescueProfileTests(unittest.TestCase):
    def test_rescue_read_uses_the_stronger_penalty_and_the_raised_output_limit(self):
        import io as _io
        root = Path(__file__).resolve().parents[2]
        profile = models.ModelProfile(**json.loads((root / "deploy/models.json").read_text(encoding="utf-8"))["profiles"]["spark_ocr"])
        self.assertEqual((profile.context, profile.max_output_tokens), (16384, 8192))
        sent = []

        def urlopen(req, timeout=None):
            sent.append(json.loads(req.data)["options"])
            reply = {"model": profile.model, "done_reason": "stop",
                     "message": {"content": '{"text":"x","blank":false,"unreadable":false}'}}
            response = _io.BytesIO(json.dumps(reply).encode())
            response.__enter__ = lambda *a: response
            response.__exit__ = lambda *a: False
            return response
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / "page.png"
            image.write_bytes(b"png")
            with mock.patch.object(ocr_worker.models, "configured_client", return_value=models.JsonModelClient(profile)), \
                 mock.patch.object(models.urllib.request, "urlopen", side_effect=urlopen):
                normal = ocr_worker.ocr(image)
                rescued = ocr_worker.ocr(image, rescue=True)
        self.assertEqual([(o["repeat_penalty"], o["repeat_last_n"]) for o in sent], [(1.1, 256), (1.3, 512)])
        self.assertEqual(sent[1]["num_predict"], 8192)
        self.assertEqual(rescued["_model"]["repeat_penalty"], 1.3)
        self.assertEqual(normal["_model"]["repeat_penalty"], 1.1)


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
