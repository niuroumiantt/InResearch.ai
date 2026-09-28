import unittest
from unittest import mock

import test_continuous_reader as fixtures
import inresearch.materials.reader_contracts as reader_contracts
from inresearch.materials.artifacts import is_placeholder


class PlaceholderTextTests(unittest.TestCase):
    """The stand-in answers Sonnet wrote on 2026-09-27, and real text that must pass."""

    SEEN = ["测试", "测试摘要。", "测试摘要", "测试摘要内容。", "测试摘要，用于诊断key_points参数解析问题。",
            "测试摘要，内容围绕智能算力产业发展白皮书候选阅读材料。", "测试要点一", "测试要点二"]
    REAL = ["该测试将柴油发电机和UPS机组作为后备电源，在用户供电断开的瞬间同时启动UPS和柴油发电机。",
            "测试结果显示 PUE 为 1.2。", "本块为目录页，列出第 1–5 章。", "示例项目位于重庆。"]

    def test_seen_placeholders_are_caught_and_real_text_is_not(self):
        self.assertEqual([t for t in self.SEEN if not is_placeholder(t)], [])
        self.assertEqual([t for t in self.REAL if is_placeholder(t)], [])
        self.assertTrue(is_placeholder("Test summary"))


class PlaceholderReadTests(unittest.TestCase):
    setUp, tearDown = fixtures.ReaderTests.setUp, fixtures.ReaderTests.tearDown
    make_reader, put = fixtures.ReaderTests.make_reader, fixtures.ReaderTests.put
    first_doc, run_reader = fixtures.ReaderTests.first_doc, fixtures.ReaderTests.run_reader
    register = fixtures.ReaderTests.register

    def with_text(self, stage, **fields):
        original = self.model.generate

        def generate(s, payload, retry_instruction=None):
            out = original(s, payload, retry_instruction=retry_instruction)
            return {**out, **fields} if s == stage else out
        return mock.patch.object(self.model, "generate", side_effect=generate)

    def test_a_placeholder_chunk_summary_is_rejected(self):
        self.register()
        self.run_reader(max_jobs=2)
        with self.with_text("read", summary="测试"), self.assertRaises(reader_contracts.ModelPlaceholderError) as caught:
            self.reader.stages._read_chunk(self.first_doc(), 0)
        self.assertEqual(caught.exception.code, "model_output_placeholder")

    def test_a_placeholder_synthesis_never_becomes_a_report(self):
        self.put()
        with self.with_text("synthesize", summary="测试摘要，用于诊断key_points参数解析问题。"):
            self.run_reader()
        doc = self.first_doc()
        self.assertIsNone(doc["report_rel"])
        row = self.reader.conn.execute("SELECT error_code FROM jobs WHERE revision_id=? AND error_code IS NOT NULL",
                                       (doc["revision_id"],)).fetchone()
        self.assertEqual(row["error_code"], "model_output_placeholder")

    def test_placeholder_key_points_are_rejected(self):
        self.put()
        with self.with_text("synthesize", key_points=["测试要点一", "测试要点二"]):
            self.run_reader()
        self.assertIsNone(self.first_doc()["report_rel"])


if __name__ == "__main__":
    unittest.main()
