import contextlib
import io
import os
import time
import unittest
from unittest import mock

import test_continuous_reader as fixtures
from inresearch.materials import artifacts, reader_contracts
from inresearch.workflow import reader as cr


class OffloadPageRuleTests(fixtures.ReaderTests):
    """M4 page results follow the same blank-page rules as local OCR."""

    def ocr_page(self, **override):
        doc = self.register("scan.pdf", "%PDF-test-scanned-page")
        self.offload_result(doc, **override)
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), \
             mock.patch.object(self.reader.stages, "_command", return_value=""):
            return self.reader.stages._ocr_page(doc, self.reader.data / doc["original_rel"], 1)

    def blocked(self, **override):
        with self.assertRaises(reader_contracts.Blocked) as exc:
            self.ocr_page(**override)
        return exc.exception.code

    def test_blank_page_with_empty_passes_is_accepted(self):
        page = self.ocr_page(blank=True, text="", text_second_pass=" ")
        self.assertEqual((page["blank"], page["text"]), (True, ""))

    def test_blank_page_with_text_or_nonblank_without_text_is_blocked(self):
        self.assertEqual(self.blocked(blank=True, text="残留 1", text_second_pass="残留 1"), "ocr_blank_has_text")
        self.assertEqual(self.blocked(blank=False, text=" ", text_second_pass=""), "ocr_empty_nonblank_page")

    def test_unreadable_or_missing_blank_flag_is_still_blocked(self):
        self.assertEqual(self.blocked(unreadable=True), "m4_offload_page_unreadable")
        self.assertEqual(self.blocked(blank=None), "m4_offload_page_unreadable")


class OffloadRequeueTests(fixtures.ReaderTests):
    """A running reader requeues OCR-blocked extractions when M4 pages arrive."""

    def blocked_scan(self):
        doc = self.register("scan.pdf", "%PDF-test-scanned-page")
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), \
             mock.patch.object(self.reader.stages, "_command", side_effect=lambda a, timeout: "Pages: 1\n" if a[0] == "pdfinfo" else ""):
            self.run_reader()
        row = self.reader.conn.execute("SELECT * FROM jobs WHERE doc_id=? AND stage='extract'", (doc["doc_id"],)).fetchone()
        self.assertEqual((row["state"], row["error_code"]), ("blocked", "scanned_page_requires_ocr"))
        return doc, row

    def page_file(self, doc):
        return self.reader.data / ("offload/m4/results/%s/pages/000001.json" % doc["doc_id"])

    def test_new_results_requeue_once_and_the_document_completes(self):
        doc, row = self.blocked_scan()
        self.offload_result(doc)
        os.utime(self.page_file(doc), (row["finished"] + 5, row["finished"] + 5))
        with self.reader.worker_session():
            self.assertEqual(self.reader.requeue_offloaded(), 1)
            self.assertEqual(self.reader.requeue_offloaded(), 0)
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), \
             mock.patch.object(self.reader.stages, "_command", side_effect=lambda a, timeout: "Pages: 1\n" if a[0] == "pdfinfo" else ""):
            self.run_reader()
        self.assertEqual(self.first_doc()["state"], "complete")

    def test_results_older_than_the_last_attempt_do_not_requeue(self):
        doc, row = self.blocked_scan()
        self.offload_result(doc)
        os.utime(self.page_file(doc), (row["finished"] - 5, row["finished"] - 5))
        with self.reader.worker_session():
            self.assertEqual(self.reader.requeue_offloaded(), 0)

    def test_other_block_reasons_and_missing_results_are_left_alone(self):
        doc, row = self.blocked_scan()
        with self.reader.worker_session():
            self.assertEqual(self.reader.requeue_offloaded(), 0)
            with self.reader.transaction():
                self.reader.conn.execute("UPDATE jobs SET error_code='parked_derived_artifact' WHERE job_id=?", (row["job_id"],))
        self.offload_result(doc)
        os.utime(self.page_file(doc), (row["finished"] + 5, row["finished"] + 5))
        with self.reader.worker_session():
            self.assertEqual(self.reader.requeue_offloaded(), 0)


if __name__ == "__main__":
    unittest.main()
