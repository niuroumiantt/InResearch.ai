import json
import os
import tempfile
import unittest
from pathlib import Path

from inresearch.adapters import gap_ocr
from inresearch.delivery import snapshot_overlay as overlay


def doc(doc_id, complete=True, claims=1):
    return {"documents": [{"doc_id": doc_id, "id": doc_id, "coverage": {"complete": complete}, "acceptance": "candidate"}],
            "evidence": [{"id": doc_id + ":ev", "document_id": doc_id, "acceptance": "candidate"}],
            "statements": [{"id": "%s:s%d" % (doc_id, n), "document_id": doc_id, "acceptance": "candidate"} for n in range(claims)]}


def snapshot(*parts, generated="2026-09-28T05:00:00Z"):
    knowledge = {"documents": [], "evidence": [], "statements": [], "answers": []}
    for part in parts:
        for kind, rows in part.items():
            knowledge[kind].extend(rows)
    return {"schema_version": 1, "generated": generated, "knowledge": knowledge, "acceptance": "candidate"}


class OverlayTests(unittest.TestCase):
    def test_external_documents_join_and_spark_complete_readings_win(self):
        spark = snapshot(doc("doc-a"), doc("doc-b", complete=False))
        m4 = snapshot(doc("doc-a", claims=5), doc("doc-b", claims=3), doc("doc-c", claims=2))
        result = overlay.overlay(spark, [("m4.json", overlay.validate_external(m4))])
        k = spark["knowledge"]
        self.assertEqual(result, {"added": 2, "kept_spark_reading": 1, "files": ["m4.json"]})
        self.assertEqual(sorted(d["doc_id"] for d in k["documents"]), ["doc-a", "doc-b", "doc-c"])
        by_doc = lambda d: [s for s in k["statements"] if s["document_id"] == d]
        self.assertEqual((len(by_doc("doc-a")), len(by_doc("doc-b")), len(by_doc("doc-c"))), (1, 3, 2))
        sources = {d["doc_id"]: d.get("projection_source") for d in k["documents"]}
        self.assertEqual(sources, {"doc-a": None, "doc-b": "external:m4.json", "doc-c": "external:m4.json"})
        self.assertEqual(len([e for e in k["evidence"] if e["document_id"] == "doc-b"]), 1)

    def test_incomplete_or_non_candidate_or_orphan_rows_are_refused(self):
        with self.assertRaisesRegex(ValueError, "complete reading coverage"):
            overlay.validate_external(snapshot(doc("doc-x", complete=False)))
        adopted = snapshot(doc("doc-x"))
        adopted["knowledge"]["statements"][0]["acceptance"] = "adopted"
        with self.assertRaisesRegex(ValueError, "candidates only"):
            overlay.validate_external(adopted)
        orphan = snapshot(doc("doc-x"))
        orphan["knowledge"]["evidence"][0]["document_id"] = "doc-y"
        with self.assertRaisesRegex(ValueError, "belong to its documents"):
            overlay.validate_external(orphan)

    def test_directory_is_read_oldest_first_and_links_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "b.json").write_text(json.dumps(snapshot(doc("doc-a", claims=1), generated="2026-09-28T01:00:00Z")))
            (d / "a.json").write_text(json.dumps(snapshot(doc("doc-a", claims=4), generated="2026-09-28T09:00:00Z")))
            spark = snapshot()
            overlay.overlay(spark, overlay.load_directory(d))
            self.assertEqual(len(spark["knowledge"]["statements"]), 4)          # newer a.json wins
            os.symlink(d / "a.json", d / "c.json")
            with self.assertRaisesRegex(ValueError, "regular file"):
                overlay.load_directory(d)
        self.assertEqual(overlay.load_directory("/nonexistent-dir"), [])


class DecorationPromptTests(unittest.TestCase):
    def test_gap_reads_are_told_to_leave_out_binary_decoration(self):
        self.assertIn("binary digits (0/1)", gap_ocr.PROMPT)


if __name__ == "__main__":
    unittest.main()
