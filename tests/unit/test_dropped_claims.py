import json
import unittest
from unittest import mock

import test_continuous_reader as fixtures
import inresearch.materials.artifacts as artifacts
import inresearch.materials.reader_contracts as reader_contracts


class DroppedClaimTests(unittest.TestCase):
    """A quote still wrong after the one correction costs that claim, not the chunk or the document."""
    setUp, tearDown = fixtures.ReaderTests.setUp, fixtures.ReaderTests.tearDown
    make_reader, put = fixtures.ReaderTests.make_reader, fixtures.ReaderTests.put
    first_doc, run_reader = fixtures.ReaderTests.first_doc, fixtures.ReaderTests.run_reader

    def mixed(self):
        original = self.model.generate

        def generate(stage, payload, retry_instruction=None):
            out = original(stage, payload, retry_instruction=retry_instruction)
            if stage == "read":
                bad = {**out["claims"][0], "text": "跨侧栏的句子", "evidence": [{"quote": "侧栏插进来的句子"}]}
                out["claims"] = [bad] + out["claims"]
            return out
        return mock.patch.object(self.model, "generate", side_effect=generate)

    def test_the_verified_claim_is_kept_and_the_document_completes(self):
        self.put()
        with self.mixed():
            result = self.run_reader()
        self.assertEqual(result["counts"], {"complete": 1})
        doc = self.first_doc()
        report = artifacts.read_json(artifacts.safe_path(self.reader.data, doc["report_rel"]))
        self.assertEqual(report["coverage"]["dropped_claims"], 1)
        self.assertIn("1 claims were dropped", report["warning"])
        self.assertEqual([c["text"] for c in report["claims"]], ["文中有可定位的内容"])
        self.assertEqual(report["claims"][0]["id"].rsplit(":", 1)[1], "0")
        self.assertTrue(all(e["quote"] != "侧栏插进来的句子" for e in report["evidence"]))
        chunk = artifacts.read_json(self.reader.artifact_path(doc["doc_id"], "chunks/000000.json"))
        self.assertEqual(chunk["dropped_claims"][0]["unverified_quotes"], ["侧栏插进来的句子"])
        self.assertEqual(len(self.model.retry_instructions), 1)

    def test_a_report_that_hides_a_dropped_claim_fails_the_seal_check(self):
        self.put()
        with self.mixed():
            self.run_reader()
        doc = self.first_doc()
        path = artifacts.safe_path(self.reader.data, doc["report_rel"])
        report = json.loads(path.read_text(encoding="utf-8"))
        del report["coverage"]["dropped_claims"]
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(reader_contracts.IntegrityError):
            self.reader.stages.validate_report(doc)

    def test_clean_reads_carry_no_dropped_field(self):
        self.put()
        self.run_reader()
        report = artifacts.read_json(artifacts.safe_path(self.reader.data, self.first_doc()["report_rel"]))
        self.assertNotIn("dropped_claims", report["coverage"])
        self.assertNotIn("dropped", report["warning"])


if __name__ == "__main__":
    unittest.main()
