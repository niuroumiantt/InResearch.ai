#!/usr/bin/env python3
"""Contract tests for the read-only M4 inventory step."""
import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m4_triage as mt


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m4-triage-test-")
        self.base = Path(self.temp.name)
        self.root = self.base / "raw"
        self.out = self.base / "out"
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def put(self, rel, data=b"payload"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def run_inventory(self, workers=4, limit=None):
        return mt.inventory(self.root, self.out, workers, limit)

    def rows(self):
        text = (self.out / "inventory.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def test_hashes_every_file_and_keeps_the_tree_untouched(self):
        self.put("a/report.pdf", b"\xff report bytes")
        self.put("b/plan.dwg", b"drawing bytes")
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob("*") if p.is_file()}
        result = self.run_inventory()
        self.assertEqual(result["hashed"], 2)
        after = {p.relative_to(self.root): p.read_bytes()
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        rows = {r["original_rel"]: r for r in self.rows()}
        self.assertEqual(rows["a/report.pdf"]["sha256"],
                         hashlib.sha256(b"\xff report bytes").hexdigest())
        self.assertEqual(rows["a/report.pdf"]["route"], "l1_preview")
        self.assertEqual(rows["b/plan.dwg"]["l0_bucket"], "_drawings_unread")
        self.assertEqual(rows["b/plan.dwg"]["route"], "l0_name_only")

    def test_buckets_follow_the_task_card(self):
        cases = {"x.pdf": ("text_candidate", "l1_preview"),
                 "x.docx": ("_office_pending", "l0_name_only"),
                 "x.dxf": ("_drawings_unread", "l0_name_only"),
                 "x.jpg": ("image", "l0_name_only"),
                 "x.zip": ("archive", "l0_name_only"),
                 "x.dmg": ("installer", "l0_name_only"),
                 "x.mp4": ("media", "l0_name_only"),
                 "x.unknownext": ("other", "l0_name_only"),
                 ".DS_Store": ("_noise", "l0_name_only"),
                 "x.pdf.crdownload": ("_noise", "l0_name_only")}
        for name, expected in cases.items():
            self.assertEqual(mt.bucket(name, Path(name).suffix.lower()), expected, name)

    def test_identical_bytes_are_one_sha_with_every_path_recorded(self):
        self.put("one/dup.pdf", b"same")
        self.put("two/dup-copy.pdf", b"same")
        self.put("three/other.pdf", b"different")
        self.run_inventory()
        report = mt.summary(self.out)
        self.assertEqual(report["unique_sha256"], 2)
        self.assertEqual(report["duplicate_groups"], 1)
        self.assertEqual(report["duplicate_extra_copies"], 1)
        self.assertEqual(report["duplicate_reclaimable_bytes"], len(b"same"))
        # Same name, different bytes is not a duplicate.
        self.assertEqual(report["l0_buckets"]["text_candidate"], 3)

    def test_interrupted_run_resumes_without_rehashing(self):
        for i in range(5):
            self.put("f%d.pdf" % i, b"body %d" % i)
        first = self.run_inventory(limit=2)
        self.assertEqual(first["hashed"], 2)
        second = self.run_inventory()
        self.assertEqual(second["skipped_already_recorded"], 2)
        self.assertEqual(second["hashed"], 3)
        self.assertEqual(len({r["original_rel"] for r in self.rows()}), 5)

    def test_output_inside_the_source_tree_is_refused(self):
        self.put("a.pdf")
        with self.assertRaises(SystemExit):
            mt.inventory(self.root, self.root / "inventory", 2)

    def test_symlink_is_recorded_but_not_followed(self):
        target = self.put("real.pdf", b"real")
        os.symlink(target, self.root / "link.pdf")
        result = self.run_inventory()
        rows = {r["original_rel"]: r for r in self.rows()}
        self.assertEqual(rows["link.pdf"]["error"], "symlink_not_followed")
        self.assertNotIn("sha256", rows["link.pdf"])
        self.assertEqual(result["hashed"], 1)

    def test_unreadable_file_is_recorded_as_an_error_not_a_crash(self):
        path = self.put("locked.pdf", b"secret")
        os.chmod(path, 0o000)
        try:
            if os.access(path, os.R_OK):
                self.skipTest("running as a user that ignores file permissions")
            result = self.run_inventory()
        finally:
            os.chmod(path, 0o600)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(self.rows()[0]["error"], "PermissionError")

    def test_missing_root_and_bad_worker_count_are_rejected(self):
        with self.assertRaises(SystemExit):
            mt.inventory(self.base / "absent", self.out, 2)
        self.put("a.pdf")
        for workers in ("0", str(mt.MAX_WORKERS + 1)):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                mt.main(["--root", str(self.root), "--out-dir", str(self.out),
                         "inventory", "--workers", workers])


if __name__ == "__main__":
    unittest.main()
