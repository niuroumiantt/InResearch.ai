#!/usr/bin/env python3
"""Failure-injection tests: no network, production models, user data or service writes."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

import continuous_reader as cr


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value

    def advance(self, seconds=1000):
        self.value += seconds


class Model:
    ocr_model = ""
    identity = {"backend": "injected_test", "model": cr.MODEL, "context": cr.CONTEXT, "ocr_model": ""}

    def __init__(self):
        self.calls = []
        self.fail_stage = None
        self.bad_quote = False
        self.bad_mapping = False

    def generate(self, stage, payload):
        self.calls.append((stage, payload))
        if stage == self.fail_stage:
            raise cr.ModelError()
        allowed = payload.get("allowed_ids", {"objects": [], "questions": []})
        ids = {"object_ids": [allowed["objects"][0]["id"]] if allowed["objects"] else [],
               "question_ids": [allowed["questions"][0]["id"]] if allowed["questions"] else []}
        if self.bad_mapping:
            ids["object_ids"] = ["invented-object"]
        if stage == "triage":
            out = {"classification": {"title": "测试资料", "org": "样本", "year": "2026", "module_id": "M11"},
                   "importance": 6, "rationale": "与测试问题相关", **ids}
        elif stage == "read":
            out = {"chunk_sha256": payload["chunk_sha256"], "summary": "逐段读取：" + payload["text"][:100], **ids,
                   "claims": [{"text": "文中有可定位的内容", "kind": "author_claim", **ids,
                               "evidence": [{"quote": "FABRICATED QUOTE" if self.bad_quote else payload["text"].strip()[:70]}]}]}
        else:
            out = {"summary": "综合所有章节的候选摘要", "key_points": ["尚未经过采用审阅"]}
        return {**out, "_model": {"backend": "injected_test", "actual": cr.MODEL, "requested": cr.MODEL}}


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="inresearch-reader-test-")
        self.base = Path(self.temp.name)
        self.clock = Clock()
        self.model = Model()
        self.reader = self.make_reader()

    def tearDown(self):
        self.reader.close()
        self.temp.cleanup()

    def make_reader(self, stable=0, chunks=200, model=None, state=None):
        return cr.Reader(self.base / "data", state or self.base / "state", self.base / "repo",
                         model or self.model, stable, chunks, self.clock).initialize()

    def put(self, name="paper.txt", text="服务器功率为 300 W。\n这是完整正文与注释。\n"):
        p = self.reader.data / "raw-materials" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def first_doc(self):
        return dict(self.reader.conn.execute("SELECT * FROM documents ORDER BY created,doc_id LIMIT 1").fetchone())

    def run_reader(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.reader.run(once=True, **kwargs)

    def register(self, name="paper.txt", text="服务器功率为 300 W。\n这是完整正文与注释。\n"):
        self.put(name, text)
        self.reader.scan()
        return self.first_doc()

    def install_registry(self):
        p = self.base / "repo/framework"
        p.mkdir(parents=True)
        cr.atomic_json(p / "research_graph.json", {"version": "2.0.0", "objects": [{"id": "obj-server", "name": "服务器"}]})
        cr.atomic_json(p / "research_questions.json", {"version": "2.0.0", "records": [{"id": "q-power", "text": "服务器功率是什么？"}]})

    def test_full_text_coverage_candidate_and_view(self):
        self.install_registry()
        text = ("服务器功率为 300 W。表格及注释应完整保留。\n" * 41) + "唯一末尾 END"
        raw = self.put(text=text)
        result = self.run_reader()
        self.assertEqual(result["counts"], {"complete": 1})
        doc = self.first_doc()
        report = cr.read_json(self.reader.artifact_path(doc["doc_id"], "report.json"))
        self.assertTrue(report["coverage"]["complete"])
        self.assertEqual(report["coverage"]["characters_read"], len(text))
        reads = [p["text"] for stage, p in self.model.calls if stage == "read"]
        self.assertEqual("".join(reads), text)
        self.assertEqual(report["acceptance"], "candidate")
        self.assertFalse(raw.exists())
        receipt = self.reader.conn.execute("SELECT receipt_rel FROM intake_operations WHERE state='committed'").fetchone()[0]
        self.assertEqual((self.reader.data / receipt).read_text(), text)
        self.assertEqual((self.reader.data / doc["original_rel"]).read_text(), text)
        self.assertEqual((self.reader.data / doc["library_rel"]).resolve(), self.reader.data / doc["original_rel"])
        self.assertEqual(report["claims"][0]["object_ids"], ["obj-server"])
        self.assertEqual(report["evidence"][0]["question_ids"], ["q-power"])

    def test_duplicate_sources_and_version_chain_keep_bytes(self):
        raw = self.put("a/paper.txt", "内容 A")
        self.put("b/paper.txt", "内容 A")
        result = self.reader.scan()
        self.assertEqual((result["registered"], result["duplicates"]), (1, 1))
        first = self.first_doc()
        raw.write_text("内容 B", encoding="utf-8")
        self.reader.scan()
        self.assertEqual(self.reader.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 2)
        versions = list(self.reader.conn.execute("SELECT * FROM sources WHERE source_key='a/paper.txt' ORDER BY version_seq"))
        self.assertEqual([r["version_seq"] for r in versions], [1, 2])
        self.assertEqual(versions[1]["previous_doc_id"], first["doc_id"])
        self.assertEqual((self.reader.data / first["original_rel"]).read_text(), "内容 A")
        before = len(self.model.calls)
        self.run_reader()
        calls = len(self.model.calls)
        self.run_reader()
        self.assertGreater(calls, before)
        self.assertEqual(len(self.model.calls), calls)

    def test_repeat_delivery_and_rename_preserve_provenance(self):
        raw = self.put(text="内容 A")
        self.reader.scan()
        raw.write_text("内容 A", encoding="utf-8")
        self.reader.scan()
        raw.rename(raw.with_name("renamed.txt"))
        self.reader.scan()
        self.assertEqual(self.reader.status()["documents_total"], 1)
        self.assertEqual(self.reader.status()["sources_total"], 3)

    def test_stability_partial_symlinks_and_read_race(self):
        self.reader.stable_seconds = 60
        good = self.put()
        self.put("upload.pdf.partial", "unfinished")
        self.put(".hidden/paper.txt", "hidden")
        (good.parent / "linked.txt").symlink_to(good)
        self.assertEqual(self.reader.scan()["waiting"], 1)
        self.clock.advance(59)
        self.assertEqual(self.reader.scan()["registered"], 0)
        self.clock.advance(1)
        self.assertEqual(self.reader.scan()["registered"], 1)
        self.assertEqual(self.reader.status()["documents_total"], 1)
        other = self.put("racing.txt", "变化中")
        expected = cr.signature(other)
        with mock.patch.object(cr, "signature", side_effect=[expected, "changed"]):
            with self.assertRaises(cr.IntegrityError):
                self.reader._register(other, "racing.txt", expected)
        self.assertEqual(self.reader.status()["documents_total"], 1)
        self.assertEqual(list((self.reader.data / "originals/.receiving").iterdir()), [])

    def test_safe_paths_and_library_collision_do_not_touch_external_files(self):
        for relative in ("../outside", "/outside", "library/../../outside", "library\\outside"):
            with self.assertRaises(cr.UnsafePath):
                cr.safe_path(self.reader.data, relative)
        outside = self.base / "outside"
        outside.mkdir()
        (self.reader.data / "library/escape").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(cr.UnsafePath):
            cr.safe_path(self.reader.data, "library/escape/value")
        self.register()
        self.run_reader(max_jobs=4)
        doc = self.first_doc()
        target = self.reader.data / self.reader._link_target(doc)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("用户现有文件", encoding="utf-8")
        self.run_reader()
        self.assertEqual(target.read_text(), "用户现有文件")
        self.assertEqual(self.first_doc()["state"], "blocked")
        self.assertEqual((self.reader.data / doc["original_rel"]).read_text(), self.put().read_text())

    def test_restart_uses_persisted_chunk_without_second_model_call(self):
        self.register()
        self.run_reader(max_jobs=2)
        with self.reader.worker_session():
            job = self.reader.claim()
            self.assertEqual(job["stage"], "read")
            result = self.reader._read_chunk(self.first_doc(), job["chunk"])
            self.assertIn("summary", result)
            # Simulate death after durable artifact but before SQLite completion.
        calls = len(self.model.calls)
        self.reader.close()
        self.reader = self.make_reader()
        self.run_reader()
        self.assertEqual(sum(stage == "read" for stage, _ in self.model.calls), 1)
        self.assertEqual(len(self.model.calls), calls + 1)  # synthesis only
        self.assertEqual(self.first_doc()["state"], "complete")

    def test_single_catalog_worker_lock_even_with_another_state_root(self):
        other = self.make_reader(state=self.base / "state2")
        try:
            with self.reader.worker_session():
                with self.assertRaises(BlockingIOError):
                    with other.worker_session():
                        pass
        finally:
            other.close()

    def test_model_failure_finite_retry_no_report_no_rearchive(self):
        self.register()
        original = self.first_doc()["original_rel"]
        self.model.fail_stage = "read"
        for _ in range(4):
            self.run_reader()
            self.clock.advance()
        doc = self.first_doc()
        self.assertEqual(doc["state"], "failed")
        self.assertEqual(doc["original_rel"], original)
        self.assertIsNone(doc["report_rel"])
        self.assertEqual(sum(stage == "read" for stage, _ in self.model.calls), 3)
        self.assertEqual(self.reader.status()["sources_total"], 1)
        self.model.fail_stage = None
        self.assertEqual(self.reader.retry(doc["doc_id"])["retried"], 1)
        self.run_reader()
        self.assertEqual(self.first_doc()["state"], "complete")

    def test_failed_chunk_does_not_allow_other_chunks_to_clear_failure(self):
        self.register(text="长篇正文与注释。" * 100)
        self.run_reader(max_jobs=2)
        job = self.reader.claim()
        self.reader.conn.execute("UPDATE jobs SET state='failed',error_code='test_failure' WHERE job_id=?", (job["job_id"],))
        self.reader.conn.execute("UPDATE documents SET state='running' WHERE doc_id=?", (job["doc_id"],))
        with self.reader.worker_session():
            self.assertIsNone(self.reader.claim())
        self.assertEqual(self.first_doc()["state"], "failed")

    def test_scanned_pdf_and_office_block_without_fake_coverage(self):
        self.put("scan.pdf", "%PDF-test-scanned-page")
        self.put("office.docx", "unsupported")
        def fake_command(args, timeout):
            return "Pages: 1\n" if args[0] == "pdfinfo" else ""
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), mock.patch.object(self.reader, "_command", side_effect=fake_command):
            self.run_reader()
        docs = list(self.reader.conn.execute("SELECT * FROM documents"))
        self.assertEqual({d["error_code"] for d in docs}, {"scanned_page_requires_ocr", "unsupported_format_docx"})
        self.assertTrue(all(d["report_rel"] is None for d in docs))
        self.assertEqual(self.model.calls, [])

    def test_ocr_can_be_enabled_after_block_and_retains_double_pass(self):
        self.register("scan.pdf", "%PDF-test-scanned-page")
        self.model.ocr_model = "qwen3-vl:8b"
        self.model.ocr = mock.Mock(return_value={"text": "扫描正文 300 W", "blank": False, "unreadable": False,
                                               "_model": {"actual": "qwen3-vl:8b"}})
        def fake_command(args, timeout):
            return "Pages: 1\n" if args[0] == "pdfinfo" else ""
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), mock.patch.object(self.reader, "_command", side_effect=fake_command):
            self.run_reader()
            # First encounter of an OCR page steps aside without spending an attempt.
            self.assertEqual(self.first_doc()["error_code"], "ocr_deferred_behind_text_documents")
            self.assertEqual(self.model.ocr.call_count, 0)
            self.clock.advance(cr.OCR_DEFER_SECONDS + 1)
            self.run_reader()
        self.assertEqual(self.first_doc()["state"], "complete")
        self.assertEqual(self.model.ocr.call_count, 2)
        page = cr.read_json(self.reader.data / "extracted" / self.first_doc()["doc_id"] / "pages/000001.json")
        self.assertEqual(page["text_second_pass"], "扫描正文 300 W")

    def ocr_ready(self, **ocr_kwargs):
        self.model.ocr_model = "qwen3-vl:8b"
        self.model.ocr = mock.Mock(**(ocr_kwargs or {"return_value": {"text": "扫描正文 300 W", "blank": False, "unreadable": False,
                                                                     "_model": {"actual": "qwen3-vl:8b"}}}))

    def test_scanned_pdf_defers_behind_text_documents(self):
        self.ocr_ready()
        self.put("scan.pdf", "%PDF-test-scanned-page")
        self.reader.scan()
        self.clock.advance(5)
        self.put("later.txt")
        self.reader.scan()
        def fake_command(args, timeout):
            return "Pages: 1\n" if args[0] == "pdfinfo" else ""
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), mock.patch.object(self.reader, "_command", side_effect=fake_command):
            self.run_reader()
            docs = {d["suffix"]: dict(d) for d in self.reader.conn.execute("SELECT * FROM documents")}
            self.assertEqual(docs[".txt"]["state"], "complete")
            self.assertEqual((docs[".pdf"]["state"], docs[".pdf"]["error_code"], docs[".pdf"]["priority"]),
                             ("queued", "ocr_deferred_behind_text_documents", cr.OCR_DEFERRED_PRIORITY))
            job = self.reader.conn.execute("SELECT attempts,state FROM jobs WHERE doc_id=? AND stage='extract'", (docs[".pdf"]["doc_id"],)).fetchone()
            self.assertEqual(tuple(job), (0, "pending"))
            self.clock.advance(cr.OCR_DEFER_SECONDS + 1)
            self.run_reader()
        docs = {d["suffix"]: dict(d) for d in self.reader.conn.execute("SELECT * FROM documents")}
        self.assertEqual(docs[".pdf"]["state"], "complete")
        self.assertEqual(self.model.ocr.call_count, 2)

    def test_ocr_page_budget_blocks_without_fake_coverage(self):
        self.ocr_ready()
        self.reader.ocr_max_pages = 1
        self.register("scan.pdf", "%PDF-test-two-scanned-pages")
        def fake_command(args, timeout):
            return "Pages: 2\n" if args[0] == "pdfinfo" else ""
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), mock.patch.object(self.reader, "_command", side_effect=fake_command):
            self.run_reader()
            self.clock.advance(cr.OCR_DEFER_SECONDS + 1)
            self.run_reader()
        doc = self.first_doc()
        self.assertEqual((doc["state"], doc["error_code"]), ("blocked", "ocr_page_budget_exceeded"))
        self.assertEqual(self.model.ocr.call_count, 2)
        self.assertIsNone(doc["report_rel"])

    def test_large_format_page_blocks_before_any_ocr(self):
        self.ocr_ready()
        doc = self.register("drawing.pdf", "%PDF-test-a1-drawing")
        self.reader.conn.execute("UPDATE documents SET priority=?", (cr.OCR_DEFERRED_PRIORITY,))
        self.reader.conn.commit()
        def fake_command(args, timeout):
            if args[0] == "pdfinfo" and "-f" in args:
                return "Page    1 size: 2384 x 1684 pts (A1)\n"
            return "Pages: 1\n" if args[0] == "pdfinfo" else ""
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), mock.patch.object(self.reader, "_command", side_effect=fake_command):
            self.run_reader()
        doc = self.first_doc()
        self.assertEqual((doc["state"], doc["error_code"]), ("blocked", "large_format_page_requires_drawing_workflow"))
        self.assertEqual(self.model.ocr.call_count, 0)

    def test_ocr_invalid_output_blocks_once_instead_of_three_retries(self):
        self.ocr_ready(side_effect=cr.ModelOutputError())
        self.register("scan.pdf", "%PDF-test-scanned-page")
        self.reader.conn.execute("UPDATE documents SET priority=?", (cr.OCR_DEFERRED_PRIORITY,))
        self.reader.conn.commit()
        def fake_command(args, timeout):
            return "Pages: 1\n" if args[0] == "pdfinfo" else ""
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), mock.patch.object(self.reader, "_command", side_effect=fake_command):
            self.run_reader()
        doc = self.first_doc()
        self.assertEqual((doc["state"], doc["error_code"]), ("blocked", "ocr_output_invalid"))
        self.assertEqual(self.model.ocr.call_count, 1)
        self.assertEqual(self.reader.conn.execute("SELECT attempts FROM jobs WHERE stage='extract'").fetchone()[0], 1)

    def test_ocr_disagreement_blocks(self):
        self.model.ocr_model = "qwen3-vl:8b"
        self.model.ocr = mock.Mock(side_effect=[{"text": "300 W", "blank": False, "unreadable": False},
                                                {"text": "800 W", "blank": False, "unreadable": False}])
        doc = self.register("scan.pdf", "%PDF-test")
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), mock.patch.object(self.reader, "_command", return_value=""):
            with self.assertRaises(cr.Blocked) as exc:
                self.reader._ocr_page(doc, self.reader.data / doc["original_rel"], 1)
        self.assertEqual(exc.exception.code, "ocr_numbers_disagree")

    def test_bad_quotes_and_unknown_ids_are_rejected(self):
        self.register()
        self.run_reader(max_jobs=2)
        self.model.bad_quote = True
        with self.assertRaises(cr.ModelOutputError):
            self.reader._read_chunk(self.first_doc(), 0)
        self.model.bad_quote = False
        self.model.bad_mapping = True
        with self.assertRaises(cr.ModelOutputError):
            self.reader._read_chunk(self.first_doc(), 0)
        self.assertIsNone(self.first_doc()["report_rel"])

    def test_tampered_or_missing_chunks_cannot_synthesize(self):
        self.register()
        self.run_reader(max_jobs=2)
        with self.assertRaises(cr.IntegrityError):
            self.reader._synthesize(self.first_doc())
        extraction = cr.read_json(self.reader.artifact_path(self.first_doc()["doc_id"], "extraction.json"))
        (self.reader.data / extraction["chunks"][0]["text_rel"]).write_text("篡改")
        with self.assertRaises(cr.IntegrityError):
            self.reader._read_chunk(self.first_doc(), 0)

    def test_view_crash_recovery_rollback_and_rebuild(self):
        self.register()
        self.run_reader(max_jobs=4)
        doc = self.first_doc()
        real_apply = self.reader._apply_link
        def crash_after_link(operation):
            real_apply(operation)
            self.reader.conn.execute("UPDATE operations SET state='prepared' WHERE operation_id=?", (operation["operation_id"],))
            raise RuntimeError("simulated process death")
        with mock.patch.object(self.reader, "_apply_link", side_effect=crash_after_link):
            with self.assertRaises(RuntimeError):
                self.run_reader()
        self.reader.close()
        self.reader = self.make_reader()
        self.run_reader()
        doc = self.first_doc()
        link = self.reader.data / doc["library_rel"]
        self.assertTrue(link.is_symlink())
        link.unlink()  # Lost derived library after restore is rebuildable.
        with self.reader.worker_session():
            pass
        self.assertTrue(link.is_symlink())
        result = self.reader.rollback(doc["doc_id"])
        self.assertTrue(result["source_preserved"])
        self.assertFalse(link.is_symlink())
        with self.reader.worker_session():
            pass
        self.assertFalse(link.is_symlink())  # A rollback is not silently undone.

    def test_export_candidate_projection_and_removed_ids(self):
        self.install_registry()
        self.put()
        self.run_reader()
        dest = self.base / "snapshot.json"
        self.reader.export(dest)
        payload = cr.read_json(dest)
        self.assertEqual(payload["graph_version"], "2.0.0")
        self.assertEqual(payload["knowledge"]["answers"], [])
        self.assertEqual(payload["knowledge"]["statements"][0]["object_ids"], ["obj-server"])
        self.assertEqual(payload["knowledge"]["evidence"][0]["document_id"], self.first_doc()["doc_id"])
        self.assertTrue(all(row["acceptance"] == "candidate" for rows in payload["knowledge"].values() for row in rows))
        cr.atomic_json(self.base / "repo/framework/research_graph.json", {"version": "3.0.0", "objects": []})
        payload = self.reader.export_snapshot()
        self.assertEqual(payload["knowledge"]["statements"][0]["object_ids"], [])
        self.assertEqual(payload["knowledge"]["documents"][0]["mapping_status"], "needs_review")
        self.assertEqual(cr.read_json(self.reader.artifact_path(self.first_doc()["doc_id"], "report.json"))["graph_version"], "2.0.0")
        self.assertEqual(cr.read_json(self.reader.data / "candidates/mapping-proposals.json")["records"][0]["unknown_ids"]["object_ids"], ["obj-server"])
        with self.assertRaises(cr.UnsafePath):
            self.reader.export(self.reader.data / "originals/forbidden.json")

    def test_backup_catalog_originals_and_artifacts_verified(self):
        self.put()
        self.run_reader()
        dest = self.base / "backup"
        self.reader.backup(dest)
        manifest = cr.read_json(dest / "manifest.json")
        self.assertFalse((dest / "backup.partial.json").exists())
        for entry in manifest["files"]:
            self.assertEqual(cr.digest_file(dest / entry["path"]), entry["sha256"])
        with sqlite3.connect(str(dest / "catalog.sqlite")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sources").fetchone()[0], 1)
        with self.assertRaises(cr.UnsafePath):
            self.reader.backup(self.reader.data / "backup")

    def test_intake_crash_recovery_preserves_new_same_path_delivery(self):
        raw = self.put(text="版本 A")
        self.run_reader(max_jobs=5)  # Read and library committed; receipt is pending.
        doc = self.first_doc()
        real_rename = cr.durable_rename
        def crash_after_quarantine(source, target):
            real_rename(source, target)
            raise RuntimeError("death after first rename")
        with mock.patch.object(cr, "durable_rename", side_effect=crash_after_quarantine):
            with self.assertRaises(RuntimeError):
                self.run_reader()
        self.assertFalse(raw.exists())
        raw.write_text("版本 B 新投料", encoding="utf-8")
        self.reader.close()
        self.reader = self.make_reader()
        with self.reader.worker_session():
            pass
        self.assertEqual(raw.read_text(), "版本 B 新投料")
        op = self.reader.conn.execute("SELECT * FROM intake_operations").fetchone()
        self.assertEqual(op["state"], "committed")
        self.assertEqual((self.reader.data / op["receipt_rel"]).read_text(), "版本 A")
        self.reader.scan()
        versions = list(self.reader.conn.execute("SELECT * FROM sources ORDER BY version_seq"))
        self.assertEqual(versions[-1]["previous_doc_id"], doc["doc_id"])
        self.run_reader()
        self.assertEqual(self.reader.status()["counts"], {"complete": 2})
        self.assertEqual(self.reader.conn.execute("SELECT COUNT(*) FROM intake_operations WHERE state='committed'").fetchone()[0], 2)

    def test_intake_modified_during_rename_restored_without_deleting_bytes(self):
        raw = self.put(text="版本 A")
        self.run_reader(max_jobs=5)
        real_rename = cr.durable_rename
        def changed_then_crash(source, target):
            real_rename(source, target)
            target.write_text("变化后的新字节", encoding="utf-8")
            raise RuntimeError("upload changed during relocation")
        with mock.patch.object(cr, "durable_rename", side_effect=changed_then_crash):
            with self.assertRaises(RuntimeError):
                self.run_reader()
        with self.reader.worker_session():
            pass
        self.assertEqual(raw.read_text(), "变化后的新字节")
        self.assertEqual((self.reader.data / self.first_doc()["original_rel"]).read_text(), "版本 A")
        self.assertEqual(self.reader.conn.execute("SELECT state FROM intake_operations").fetchone()[0], "changed_restored")

    def test_same_bytes_redelivered_after_completion_need_no_model_re_read(self):
        self.put(text="重复材料")
        self.run_reader()
        calls = len(self.model.calls)
        self.put(text="重复材料")
        self.run_reader()
        self.assertEqual(len(self.model.calls), calls)
        self.assertEqual(self.reader.status()["documents_total"], 1)
        self.assertEqual(self.reader.status()["sources_total"], 2)
        self.assertEqual(self.reader.conn.execute("SELECT COUNT(*) FROM intake_operations WHERE state='committed'").fetchone()[0], 2)

    def test_long_document_hierarchical_synthesis_covers_all_chunks(self):
        self.reader.chunk_chars = 100
        text = "服务器数据与完整注释。" * 1600
        self.put(text=text)
        self.run_reader()
        doc = self.first_doc()
        report = cr.read_json(self.reader.artifact_path(doc["doc_id"], "report.json"))
        self.assertEqual(report["coverage"]["characters_read"], len(text))
        self.assertTrue(report["coverage"]["complete"])
        self.assertGreater(sum(stage == "synthesize" for stage, _ in self.model.calls), 1)
        levels = list(self.reader.artifact_path(doc["doc_id"], "synthesis").glob("l001-*.json"))
        self.assertTrue(levels)
        chunks = [payload["chunk_index"] for stage, payload in self.model.calls if stage == "read"]
        self.assertEqual(chunks, list(range(len(chunks))))

    def test_backup_restores_catalog_and_views_under_new_root(self):
        self.put()
        self.run_reader()
        backup = self.base / "restore-backup"
        self.reader.backup(backup)
        restored_root = self.base / "restored-data"
        (restored_root / "catalog").mkdir(parents=True)
        shutil.copyfile(str(backup / "catalog.sqlite"), str(restored_root / "catalog/catalog.sqlite"))
        for row in cr.read_json(backup / "manifest.json")["files"]:
            target = restored_root / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(backup / row["path"]), str(target))
        restored = cr.Reader(restored_root, self.base / "restored-state", self.base / "repo", self.model, 0, 200, self.clock).initialize()
        try:
            with restored.worker_session():
                pass
            doc = restored.doc(self.first_doc()["doc_id"])
            self.assertTrue((restored_root / doc["library_rel"]).is_symlink())
            self.assertEqual((restored_root / doc["library_rel"]).resolve(), (restored_root / doc["original_rel"]).resolve())
            self.assertEqual(restored.status()["counts"], {"complete": 1})
            self.assertEqual(restored.status()["sources_total"], 1)
        finally:
            restored.close()

    def test_long_unicode_filename_remains_within_filesystem_limits(self):
        name = "非常长的研究资料名称" * 7 + ".txt"
        self.put(name, "名称测试")
        self.run_reader()
        doc = self.first_doc()
        self.assertEqual(doc["state"], "complete")
        self.assertEqual(doc["original_name"], name)
        self.assertLessEqual(len(Path(doc["original_rel"]).name.encode()), 255)

    def test_english_cold_plate_retrieves_object_and_related_questions(self):
        framework = self.base / "repo/framework"
        framework.mkdir(parents=True)
        objects = [{"id": "part:coldplate", "name": "冷板", "aliases": ["cold plate", "direct-to-chip liquid cooling"]}]
        objects += [{"id": "part:other%03d" % i, "name": "其他对象%d" % i} for i in range(60)]
        questions = [{"id": "M01-Q%03d" % i, "text": "无关的一般研究问题%d" % i, "object_ids": ["part:other000"]} for i in range(200)]
        questions.append({"id": "OBJ-coldplate-performance", "text": "冷板性能如何验证？", "object_ids": ["part:coldplate"]})
        cr.atomic_json(framework / "research_graph.json", {"version": "2.0.0", "objects": objects})
        cr.atomic_json(framework / "research_questions.json", {"version": "2.0.0", "records": questions})
        doc = self.register(text="A copper cold plate transfers heat to circulating coolant.")
        context = self.reader._context(doc, "A copper cold plate transfers heat to circulating coolant.")
        self.assertEqual(context["objects"][0]["id"], "part:coldplate")
        self.assertEqual(context["questions"][0]["id"], "OBJ-coldplate-performance")
        self.assertEqual(context["questions"][0]["match"], "related_object")
        self.assertLessEqual(len(cr.encoded(context).encode()), 4800)
        # ID English words still bridge the spaced compound without aliases.
        path = self.reader.artifact_path(doc["doc_id"], "context.json")
        snapshot = cr.read_json(path)
        snapshot["objects"][0].pop("aliases")
        cr.atomic_json(path, snapshot)
        context = self.reader._context(doc, "A cold plate transfers heat.")
        self.assertEqual(context["objects"][0]["id"], "part:coldplate")

    def test_zero_match_context_reserves_room_for_objects(self):
        framework = self.base / "repo/framework"
        framework.mkdir(parents=True)
        cr.atomic_json(framework / "research_graph.json", {"version": "2.0.0", "objects": [{"id": "part:cooling", "name": "冷却对象"}]})
        cr.atomic_json(framework / "research_questions.json", {"version": "2.0.0", "records": [
            {"id": "M01-Q%03d" % i, "text": "一般研究问题%d" % i} for i in range(500)]})
        doc = self.register(text="zzzzz")
        context = self.reader._context(doc, "zzzzz")
        self.assertEqual(context["objects"][0]["id"], "part:cooling")
        self.assertTrue(context["questions"])
        self.assertTrue(all(row["match"] == "needs_review" for rows in context.values() for row in rows))
        self.assertLessEqual(len(cr.encoded(context).encode()), 4800)

    def test_oldest_job_receives_one_in_four_slots(self):
        self.register("old.txt", "旧资料")
        old = self.first_doc()["doc_id"]
        self.clock.advance()
        for n in range(5):
            self.put("new%d.txt" % n, "新资料 %d" % n)
        self.reader.scan()
        self.reader.conn.execute("UPDATE documents SET priority=9 WHERE doc_id!=?", (old,))
        self.reader.conn.execute("UPDATE documents SET priority=1 WHERE doc_id=?", (old,))
        self.reader.conn.execute("UPDATE meta SET value='1' WHERE key='dispatch_count'")
        first = [self.reader.claim()["doc_id"] for _ in range(4)]
        self.assertNotIn(old, first[:3])
        self.assertEqual(first[3], old)

    def test_split_utf8_is_lossless_bounded_and_backend_never_fakes(self):
        text = "复杂文本🙂" * 5000
        chunks = list(cr.split_text(text))
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(c) <= 6000 and len(c.encode()) <= 12000 for c in chunks))
        with self.assertRaises(ValueError):
            cr.ModelClient(model="different-model")
        client = cr.ModelClient(timeout=1)
        with mock.patch.object(cr.urllib.request, "urlopen", side_effect=OSError("private response must not leak")):
            with self.assertRaises(cr.ModelError):
                client.generate("synthesize", {"sections": []})

    def offload_result(self, doc, i=1, **override):
        result = {"doc_id": doc["doc_id"], "content_sha256": doc["sha256"], "page_index": i,
                  "method": "m4_vision_ocr_double_pass", "text": "M4 读出 300 W", "text_second_pass": "M4 读出 300 W",
                  "ocr_model": {"actual": "qwen3-vl:8b", "host": "m4"}, "blank": False, "unreadable": False,
                  "verification": "candidate_ocr_agreement_not_accuracy_certification", **override}
        cr.atomic_json(self.reader.data / ("offload/m4/results/%s/pages/%06d.json" % (doc["doc_id"], i)), result)

    def test_m4_offload_result_is_used_without_local_ocr_deferral_or_budget(self):
        self.ocr_ready()
        self.reader.ocr_max_pages = 0
        doc = self.register("scan.pdf", "%PDF-test-scanned-page")
        self.offload_result(doc)
        def fake_command(args, timeout):
            return "Pages: 1\n" if args[0] == "pdfinfo" else ""
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), mock.patch.object(self.reader, "_command", side_effect=fake_command):
            self.run_reader()
        doc = self.first_doc()
        self.assertEqual(doc["state"], "complete")
        self.assertEqual(self.model.ocr.call_count, 0)
        page = cr.read_json(self.reader.data / "extracted" / doc["doc_id"] / "pages/000001.json")
        self.assertEqual((page["method"], page["text"]), ("m4_vision_ocr_double_pass", "M4 读出 300 W"))

    def test_m4_offload_result_bound_to_content_hash_and_agreement(self):
        self.ocr_ready()
        doc = self.register("scan.pdf", "%PDF-test-scanned-page")
        source = self.reader.data / doc["original_rel"]
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), mock.patch.object(self.reader, "_command", return_value=""):
            self.offload_result(doc, content_sha256="0" * 64)
            with self.assertRaises(cr.IntegrityError):
                self.reader._ocr_page(doc, source, 1)
            self.offload_result(doc, text_second_pass="M4 读出 800 W")
            with self.assertRaises(cr.Blocked) as exc:
                self.reader._ocr_page(doc, source, 1)
            self.assertEqual(exc.exception.code, "m4_offload_numbers_disagree")
        self.assertEqual(self.model.ocr.call_count, 0)

    def test_ollama_vision_request_disables_thinking_and_accepts_json_from_thinking(self):
        client = cr.ModelClient(timeout=1, ocr_model="qwen3-vl:8b")
        seen = {}
        class Response:
            def __init__(self, body):
                self.body = body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, n):
                return self.body
        def fake_urlopen(req, timeout):
            seen["body"] = json.loads(req.data)
            return Response(json.dumps({"model": "qwen3-vl:8b", "message": {"content": "", "thinking": '{"text":"页面文字 12 kW","blank":false,"unreadable":false}'}}).encode())
        image = self.base / "page.png"
        image.write_bytes(b"png")
        with mock.patch.object(cr.urllib.request, "urlopen", side_effect=fake_urlopen):
            out = client.ocr(image)
        self.assertIs(seen["body"]["think"], False)
        self.assertEqual((out["text"], out["blank"], out["unreadable"]), ("页面文字 12 kW", False, False))


class WorkerThreadTests(ReaderTests):
    """Several worker threads in one process must reach the single-worker result."""

    def test_parallel_workers_complete_every_document_without_double_claim(self):
        self.install_registry()
        for i in range(6):
            self.put("paper-%d.txt" % i, "服务器功率为 %d0 W。\n这是完整正文与注释。\n" % (i + 3))
        result = self.run_reader(workers=4)
        states = [row[0] for row in self.reader.conn.execute("SELECT state FROM documents")]
        self.assertEqual(states, ["complete"] * 6)
        jobs = list(self.reader.conn.execute("SELECT state,attempts FROM jobs"))
        self.assertTrue(all(job["state"] == "succeeded" for job in jobs))
        # A job claimed twice would show a second attempt.
        self.assertTrue(all(job["attempts"] == 1 for job in jobs))
        self.assertEqual(result["processed"], len(jobs))

    def test_worker_count_is_bounded(self):
        for workers in (0, -1, cr.MAX_WORKERS + 1, 1.5, True):
            with self.assertRaises(ValueError):
                self.reader.run(once=True, workers=workers)

    def test_worker_failure_stops_the_run(self):
        self.register()
        self.reader.process = lambda job: (_ for _ in ()).throw(RuntimeError("worker crash"))
        with self.assertRaises(RuntimeError):
            self.run_reader(workers=3)


if __name__ == "__main__":
    unittest.main()
