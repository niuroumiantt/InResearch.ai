import json
import unittest
from unittest import mock

import test_continuous_reader as fixtures
from inresearch.materials import reader_contracts
from inresearch.materials.reading_artifacts import ReadingArtifacts
from inresearch.workflow import reader as cr


class M4GapPageTests(fixtures.ReaderTests):
    """A page M4 could not read even after its rescue pass is an explicit, capped gap."""

    def scan(self, pages, gaps, reason="model_output_truncated", name="scan.pdf"):
        doc = self.register(name, "%PDF-test-scanned-" + name)
        for i in range(1, pages + 1):
            if i in gaps:
                self.offload_result(doc, i, method="m4_vision_ocr_gap", gap=True, gap_reason=reason,
                                    text="", text_second_pass="", unreadable=True,
                                    verification="page_not_read_after_rescue")
            else:
                self.offload_result(doc, i, text="第%d页 功率 %d W" % (i, i * 100),
                                    text_second_pass="第%d页 功率 %d W" % (i, i * 100))
        command = lambda a, timeout: "Pages: %d\n" % pages if a[0] == "pdfinfo" else ""
        with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), \
             mock.patch.object(self.reader.stages, "_command", side_effect=command):
            self.run_reader()
        return doc

    def report(self):
        path = next(self.reader.data.rglob("report.json"))
        return json.loads(path.read_text(encoding="utf-8"))

    def test_gap_page_is_listed_and_the_rest_of_the_document_is_read(self):
        self.scan(pages=21, gaps={3})
        self.assertEqual(self.first_doc()["state"], "complete")
        coverage = self.report()["coverage"]
        self.assertEqual((coverage["gap_pages"], coverage["pages_read"], coverage["pages_total"]), ([3], 21, 21))
        self.assertIn("Pages 3 could not be read", self.report()["warning"])

    def test_too_many_gaps_block_the_document(self):
        self.scan(pages=4, gaps={1, 3})
        row = self.reader.conn.execute("SELECT state,error_code FROM jobs WHERE stage='extract'").fetchone()
        self.assertEqual((row["state"], row["error_code"]), ("blocked", "ocr_gap_pages_exceed_limit"))
        self.assertIn("ocr_gap_pages_exceed_limit", reader_contracts.OCR_BLOCK_CODES)
        self.assertEqual([reader_contracts.max_gap_pages(n) for n in (1, 20, 21, 46, 84)], [1, 1, 1, 2, 4])

    def test_document_without_gaps_reports_no_gap_field(self):
        self.scan(pages=2, gaps=set())
        self.assertNotIn("gap_pages", self.report()["coverage"])

    def test_malformed_gap_is_an_integrity_error(self):
        doc = self.register("bad.pdf", "%PDF-test-bad-gap")
        for override in ({"gap": False}, {"gap_reason": "page_render_failed"}):
            self.offload_result(doc, 1, **{"method": "m4_vision_ocr_gap", "gap": True, "gap_reason": "model_failure", **override})
            with mock.patch.object(cr.shutil, "which", return_value="/fake/tool"), \
                 mock.patch.object(self.reader.stages, "_command", return_value=""):
                with self.assertRaises(reader_contracts.IntegrityError):
                    self.reader.stages._ocr_page(doc, self.reader.data / doc["original_rel"], 1)

    def test_a_tampered_gap_list_fails_report_validation(self):
        doc = self.scan(pages=21, gaps={3})
        row = self.reader.conn.execute("SELECT * FROM execution_readings WHERE doc_id=?", (doc["doc_id"],)).fetchone()
        ReadingArtifacts(self.reader.data).validate_report(dict(row))   # the untouched report is valid
        path = next(self.reader.data.rglob("report.json"))
        report = json.loads(path.read_text(encoding="utf-8"))
        report["coverage"]["gap_pages"] = []
        path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaises(reader_contracts.IntegrityError):
            ReadingArtifacts(self.reader.data).validate_report(dict(row))


if __name__ == "__main__":
    unittest.main()
