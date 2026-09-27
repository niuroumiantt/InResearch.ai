import base64
import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from inresearch.adapters import gap_ocr, models
from inresearch.materials.artifacts import atomic_json, digest_file, read_json

ROOT = Path(__file__).resolve().parents[2]


class CliImageTests(unittest.TestCase):
    """The Claude CLI sees the page as an image block on stdin; tools stay off."""

    def test_image_goes_in_as_one_stream_json_message(self):
        profile = models.ModelProfile(backend="claude_cli", url="", model="claude-test", capabilities=("vision_json",))
        seen = {}

        def fake(command, **kwargs):
            seen["command"], seen["input"] = command, kwargs["input"]
            events = [{"type": "assistant", "message": {"model": "claude-test"}},
                      {"type": "result", "is_error": False, "structured_output": {"text": "300 W", "blank": False, "unreadable": False}}]
            kwargs["stdout"].write("\n".join(json.dumps(e) for e in events).encode())
            return SimpleNamespace(returncode=0)
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / "page.png"
            image.write_bytes(b"\x89PNG fake")
            with mock.patch.object(models.subprocess, "run", side_effect=fake):
                value = models.JsonModelClient(profile).generate("sys", "read it", image_path=image, json_schema=gap_ocr.SCHEMA)
        command = seen["command"]
        self.assertEqual(command[command.index("--input-format") + 1], "stream-json")
        self.assertEqual(command[command.index("--tools") + 1], "")
        message = json.loads(seen["input"])
        self.assertEqual(message["type"], "user")
        image_block, text_block = message["message"]["content"]
        self.assertEqual(base64.b64decode(image_block["source"]["data"]), b"\x89PNG fake")
        self.assertEqual(text_block, {"type": "text", "text": "read it"})
        self.assertEqual(value["text"], "300 W")
        self.assertEqual(len(value["_model"]["image_sha256"]), 64)

    def test_text_calls_are_unchanged(self):
        profile = models.ModelProfile(backend="claude_cli", url="", model="claude-test")
        seen = {}

        def fake(command, **kwargs):
            seen["command"], seen["input"] = command, kwargs["input"]
            events = [{"type": "assistant", "message": {"model": "claude-test"}}, {"type": "result", "result": '{"a":1}'}]
            kwargs["stdout"].write("\n".join(json.dumps(e) for e in events).encode())
            return SimpleNamespace(returncode=0)
        with mock.patch.object(models.subprocess, "run", side_effect=fake):
            value = models.JsonModelClient(profile).generate("sys", "plain text")
        self.assertNotIn("--input-format", seen["command"])
        self.assertEqual(seen["input"], "plain text")
        self.assertNotIn("image_sha256", value["_model"])

    def test_the_shipped_gap_role_is_a_claude_vision_profile(self):
        profile = models.load_profile("gap_ocr", ROOT / "deploy/models.json")
        self.assertEqual((profile.backend, profile.capabilities), ("claude_cli", ("vision_json",)))
        with self.assertRaises(ValueError):
            models.ModelProfile(backend="gateway", url="http://x", model="m", capabilities=("vision_json",))


class Reads:
    """A stand-in vision client: pages listed in ``fail`` disagree between reads."""

    def __init__(self, fail=()):
        self.fail, self.calls = set(fail), []

    def generate(self, system, user, image_path=None, json_schema=None):
        page = int(Path(image_path).stem.split("-")[1])
        self.calls.append(page)
        number = page * 100 + (len(self.calls) if page in self.fail else 0)
        return {"text": "第%d页 %d W" % (page, number), "blank": False, "unreadable": False, "_model": {"actual": "claude-test"}}


class FillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        original = self.data / "originals/a.pdf"
        original.parent.mkdir(parents=True)
        original.write_bytes(b"%PDF fake")
        self.sha = digest_file(original)
        (self.data / "catalog").mkdir()
        conn = sqlite3.connect(self.data / "catalog/catalog.sqlite")
        conn.execute("CREATE TABLE current_readings (doc_id,sha256,original_rel,extracted_rel)")
        conn.execute("INSERT INTO current_readings VALUES ('doc-a',?,'originals/a.pdf','extracted/doc-a')", (self.sha,))
        conn.commit(); conn.close()
        self.pages = self.data / "offload/m4/results/doc-a/pages"
        for i in (1, 2, 3):
            gap = i != 1
            atomic_json(self.pages / ("%06d.json" % i), {
                "doc_id": "doc-a", "content_sha256": self.sha, "page_index": i,
                "method": "m4_vision_ocr_gap" if gap else "m4_vision_ocr_double_pass",
                "gap": gap, "gap_reason": "model_output_truncated", "text": "" if gap else "p1", "text_second_pass": ""})
            atomic_json(self.data / ("extracted/doc-a/pages/%06d.json" % i), {"page_index": i, "gap": gap})

    def tearDown(self):
        self.temp.cleanup()

    def render(self, source, index, directory):
        image = Path(directory) / ("page-%06d.png" % index)
        image.write_bytes(b"png")
        return image

    def test_agreeing_reads_fill_the_gap_and_drop_only_its_cached_page(self):
        client = Reads(fail={3})
        with mock.patch.object(gap_ocr, "render", side_effect=self.render):
            result = gap_ocr.fill(self.data, "doc-a", client)
        self.assertEqual(result["filled_pages"], [2])
        self.assertEqual(result["still_gaps"], [{"page": 3, "reason": "ocr_numbers_disagree"}])
        self.assertEqual(sorted(set(client.calls)), [2, 3])            # page 1 was never a gap
        page = read_json(self.pages / "000002.json")
        self.assertEqual((page["method"], page["text"], page["replaces_gap_reason"]),
                         (gap_ocr.METHOD, "第2页 200 W", "model_output_truncated"))
        self.assertEqual(read_json(self.data / "offload/m4/gap-history/doc-a/000002.json")["method"], "m4_vision_ocr_gap")
        self.assertFalse((self.data / "extracted/doc-a/pages/000002.json").exists())
        self.assertTrue((self.data / "extracted/doc-a/pages/000001.json").exists())
        self.assertTrue((self.data / "extracted/doc-a/pages/000003.json").exists())
        self.assertEqual(read_json(self.pages / "000003.json")["method"], "m4_vision_ocr_gap")

    def test_a_rerun_after_an_interrupted_fill_drops_the_stale_cache(self):
        with mock.patch.object(gap_ocr, "render", side_effect=self.render), \
             mock.patch.object(gap_ocr, "drop_cached_gap"):            # crash before the cache went
            gap_ocr.fill(self.data, "doc-a", Reads(fail={3}))
        self.assertTrue((self.data / "extracted/doc-a/pages/000002.json").exists())
        client = Reads(fail={3})
        with mock.patch.object(gap_ocr, "render", side_effect=self.render):
            result = gap_ocr.fill(self.data, "doc-a", client)
        self.assertEqual((result["filled_pages"], sorted(set(client.calls))), ([], [3]))
        self.assertFalse((self.data / "extracted/doc-a/pages/000002.json").exists())

    def test_changed_original_is_refused_before_any_model_call(self):
        (self.data / "originals/a.pdf").write_bytes(b"%PDF other")
        client = Reads()
        with self.assertRaisesRegex(RuntimeError, "source_hash_mismatch"):
            gap_ocr.fill(self.data, "doc-a", client)
        self.assertEqual(client.calls, [])

    def test_dry_run_lists_gaps_without_reading(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(gap_ocr.main(["--data-root", str(self.data), "--doc-id", "doc-a", "--dry-run"]), 0)
        self.assertEqual(json.loads(out.getvalue()), {"doc_id": "doc-a", "gap_pages": [2, 3]})
        self.assertTrue((self.data / "extracted/doc-a/pages/000002.json").exists())

    def test_the_reader_accepts_the_filled_page(self):
        from inresearch.workflow.reading_stages import ReadingStages
        with mock.patch.object(gap_ocr, "render", side_effect=self.render):
            gap_ocr.fill(self.data, "doc-a", Reads())
        stages = ReadingStages(self.data, SimpleNamespace(ocr_model=""), 10, 10_000)
        doc = {"doc_id": "doc-a", "sha256": self.sha}
        page = stages._ocr_page(doc, None, 2)
        self.assertEqual((page["method"], page["text"]), (gap_ocr.METHOD, "第2页 200 W"))


if __name__ == "__main__":
    unittest.main()
