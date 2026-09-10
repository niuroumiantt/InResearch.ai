#!/usr/bin/env python3
"""Grouping the same report issued more than once, from judged rows."""
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m4_triage_pack as PK
import m4_triage_l1 as L1


def row(org, title, rel, pages=10, score=6, size=1000, status="ok"):
    return {"status": status, "sha256": rel, "rel": rel, "title": title, "org": org,
            "score": score, "size": size, "meta": {"pages": pages}}


class TitleKeyTests(unittest.TestCase):
    def test_publication_date_and_page_count_do_not_split_a_report(self):
        a = PK.title_key("20250925 数据中心液冷冷却液行业分析框架(40页)", "国信证券")
        b = PK.title_key("数据中心液冷冷却液行业分析框架", "国信证券")
        self.assertEqual(a, b)

    def test_punctuation_and_case_do_not_split_a_report(self):
        a = PK.title_key("AI 数据中心：规模扩展与架构演进", "OCP")
        b = PK.title_key("AI数据中心, 规模扩展与架构演进", "ocp")
        self.assertEqual(a, b)

    def test_a_desk_prefix_on_one_issue_only_does_not_split_it(self):
        a = PK.title_key("国信化工·数据中心及AI服务器液冷冷却液行业分析框架", "国信证券")
        b = PK.title_key("数据中心及AI服务器液冷冷却液行业分析框架", "国信证券")
        self.assertEqual(a, b)

    def test_a_short_title_is_not_eaten_by_the_prefix_rule(self):
        self.assertNotEqual(PK.title_key("液冷：白皮书", "华为"), PK.title_key("白皮书", "华为"))

    def test_different_publishers_are_never_one_group(self):
        self.assertNotEqual(PK.title_key("数据中心液冷", "国信证券"),
                            PK.title_key("数据中心液冷", "中泰证券"))


class VersionGroupTests(unittest.TestCase):
    def test_the_fullest_copy_is_kept(self):
        rows = [row("信通院", "液冷白皮书", "a.pdf", pages=20),
                row("信通院", "液冷白皮书", "b.pdf", pages=44),
                row("信通院", "液冷白皮书", "c.pdf", pages=44, size=9000)]
        groups = PK.version_groups(rows)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["keep"]["rel"], "c.pdf")
        self.assertEqual({m["rel"] for m in groups[0]["extra"]}, {"a.pdf", "b.pdf"})

    def test_a_copy_under_the_excluded_tree_is_never_the_keeper(self):
        rows = [row("信通院", "液冷白皮书", "要删/reader/a.pdf", pages=90),
                row("信通院", "液冷白皮书", "报告/b.pdf", pages=10)]
        self.assertEqual(PK.version_groups(rows)[0]["keep"]["rel"], "报告/b.pdf")

    def test_a_report_seen_once_is_not_a_group(self):
        self.assertEqual(PK.version_groups([row("信通院", "液冷白皮书", "a.pdf")]), [])

    def test_min_score_filters_before_grouping(self):
        rows = [row("华安证券", "全球科技周报", "a.pdf", score=2),
                row("华安证券", "全球科技周报", "b.pdf", score=2)]
        self.assertEqual(len(PK.version_groups(rows, min_score=0)), 1)
        self.assertEqual(PK.version_groups(rows, min_score=5), [])

    def test_only_judged_rows_are_read(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "l1_results.jsonl"
            path.write_text(
                json.dumps(row("信通院", "液冷白皮书", "a.pdf"), ensure_ascii=False) + "\n"
                + json.dumps(row("信通院", "液冷白皮书", "b.pdf", status="l0"), ensure_ascii=False) + "\n"
                + json.dumps({"status": "ok", "rel": "c.pdf"}, ensure_ascii=False) + "\n"
                + "not json\n", encoding="utf-8")
            saved, L1.RESULTS = L1.RESULTS, path
            try:
                self.assertEqual(len(PK.scored_rows()), 1)
            finally:
                L1.RESULTS = saved

    def test_the_report_reads_but_never_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "l1_results.jsonl"
            body = "".join(json.dumps(row("信通院", "液冷白皮书", n), ensure_ascii=False) + "\n"
                           for n in ("a.pdf", "b.pdf"))
            path.write_text(body, encoding="utf-8")
            saved, L1.RESULTS = L1.RESULTS, path
            try:
                PK.cmd_versions(types.SimpleNamespace(min_score=0, show=0))
            finally:
                L1.RESULTS = saved
            self.assertEqual(path.read_text(encoding="utf-8"), body)


if __name__ == "__main__":
    unittest.main()
