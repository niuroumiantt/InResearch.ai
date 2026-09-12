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
from unittest.mock import patch

import m4_records
import m4_triage_l1 as L1
import m4_triage_apply as APPLY
import m4_inventory as LEGACY

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

    def test_inventory_written_by_another_tool_is_not_appended_to(self):
        # A different tool's inventory at the same path: appending would mix two
        # schemas, re-hash everything, and break the summary.
        self.put("a.pdf")
        self.out.mkdir(parents=True)
        (self.out / "inventory.jsonl").write_text(
            json.dumps({"sha256": "0" * 64, "path": "a.pdf", "bytes": 7}) + "\n",
            encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            self.run_inventory()
        self.assertIn("different format", str(caught.exception))
        # The foreign file is left exactly as it was.
        self.assertEqual(len((self.out / "inventory.jsonl").read_text().splitlines()), 1)

    def test_summary_reports_unrecognized_rows_instead_of_crashing(self):
        self.put("a.pdf")
        self.run_inventory()
        with (self.out / "inventory.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"sha256": "0" * 64, "path": "b.pdf"}) + "\n")
        report = mt.summary(self.out)
        self.assertEqual(report["errors"]["row_format_unrecognized"], 1)
        self.assertEqual(report["unique_sha256"], 1)

    def test_changed_content_is_rehashed_and_summary_counts_current_path_once(self):
        path = self.put('a.txt', b'old evidence')
        self.run_inventory()
        path.write_bytes(b'new evidence')
        result = self.run_inventory()
        self.assertEqual(result['hashed'], 1)
        self.assertEqual(len(self.rows()), 2, 'historical observation was overwritten')
        self.assertEqual(mt.summary(self.out)['rows'], 1)
        current = m4_records.load_inventory(self.out / 'inventory.jsonl')
        self.assertEqual(current[0]['sha256'], hashlib.sha256(b'new evidence').hexdigest())

    def test_failed_path_is_retried_when_it_becomes_readable(self):
        target = self.put('target.txt')
        link = self.root / 'link.txt'
        link.symlink_to(target)
        self.run_inventory()
        link.unlink()
        link.write_bytes(b'recovered file')
        result = self.run_inventory()
        self.assertEqual(result['hashed'], 1)
        self.assertEqual(mt.summary(self.out)['errors'], {})

    def test_one_dataset_cannot_silently_change_its_source(self):
        self.put('a.txt')
        self.run_inventory()
        another = self.base / 'another'
        another.mkdir()
        with self.assertRaisesRegex(ValueError, 'source_root_changed'):
            mt.inventory(another, self.out, 1)

    def test_torn_tail_is_preserved_and_resume_recovers_the_file(self):
        self.put('a.txt')
        self.run_inventory()
        self.put('b.txt')
        partial = b'{"original_rel":"b.txt","sha256":'
        with (self.out / 'inventory.jsonl').open('ab') as stream:
            stream.write(partial)
        self.assertEqual(self.run_inventory()['hashed'], 1)
        self.assertEqual(mt.summary(self.out)['rows'], 2)
        self.assertEqual(next(self.out.glob('*.partial-*')).read_bytes(), partial)

    def test_legacy_migration_preserves_bytes_and_all_consumers_agree(self):
        content = b'the same research source'
        sha = hashlib.sha256(content).hexdigest()
        self.put('a.txt', content)
        self.put('b.txt', content)
        self.out.mkdir()
        path = self.out / 'inventory.jsonl'
        legacy = [{'rel': rel, 'sha256': sha, 'size': len(content)} for rel in ('a.txt', 'b.txt')]
        path.write_text(''.join(json.dumps(row) + '\n' for row in legacy))
        original = path.read_bytes()
        with self.assertRaises(SystemExit):
            self.run_inventory()
        result = mt.migrate_inventory(self.out)
        self.assertEqual(Path(result['backup']).read_bytes(), original)
        with patch.object(L1, 'INVENTORY', path), patch.object(APPLY, 'INVENTORY', path):
            self.assertEqual(L1.load_inventory()[0]['paths'], ['a.txt', 'b.txt'])
            self.assertEqual(len(APPLY.load_inventory()[sha]), 2)
            self.assertEqual(len(APPLY.plan_duplicates()), 1)
        self.assertEqual(mt.summary(self.out)['duplicate_extra_copies'], 1)
        self.assertEqual(self.run_inventory()['hashed'], 2)  # Add precise stat signature once.
        self.assertEqual(self.run_inventory()['hashed'], 0)

    def test_failed_migration_leaves_original_intact(self):
        self.out.mkdir()
        path = self.out / 'inventory.jsonl'
        original = b'{"unrecognized":"unique evidence"}\n'
        path.write_bytes(original)
        with self.assertRaises(ValueError):
            mt.migrate_inventory(self.out)
        self.assertEqual(path.read_bytes(), original)

    def test_legacy_command_uses_the_same_writer_and_dataset(self):
        self.put('a.txt')
        with patch.object(mt.m4_paths, 'source', return_value=self.root), \
             patch.object(mt.m4_paths, 'data', return_value=self.out), \
             contextlib.redirect_stdout(io.StringIO()):
            LEGACY.main(['--workers', '1'])
        self.assertIn('original_rel', self.rows()[0])
        self.assertNotIn('rel', self.rows()[0])

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
