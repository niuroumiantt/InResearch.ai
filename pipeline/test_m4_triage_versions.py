#!/usr/bin/env python3
"""Finding one report issued more than once, from judged rows."""
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m4_triage_pack as PK
import m4_triage_l1 as L1

# Filenames taken verbatim from a real M4 batch.
LIQUID = [
    "20250925-国信证券-化工行业·数据中心及AI服务器液冷冷却液行业分析框架(40页).pdf",
    "20250927-国信化工·数据中心及AI服务器液冷冷却液行业分析框架(40页).pdf",
    "20250929-国信证券-国信证券-化工行业·数据中心及AI服务器液冷冷却液行业分析框架(40页).pdf",
    "20251003-国信证券：行业分析框架：国信化工：数据中心及AI服务器液冷冷却液(40页).pdf",
]
COOLING_TOWER = [
    "20251016-中泰证券-中泰证券-机械设备行业冷却塔专题报告：冷却塔行业多场景共振，数据中心场景打开成长空间(34页).pdf",
    "20251019-中泰证券：冷却塔专题报告：冷却塔行业多场景共振，数据中心场景打开成长空间(34页).pdf",
]
DISTINCT = [
    "20250818-2025年全球数据中心投资者意向调查报告(32页).pdf",
    "20250722-高力国际-美国研究报告：2025数据中心市场-(英)(54页).pdf",
    "20250927-ODCC开放数据中心委员会：2025年400G BR4光模块技术规范(37页).pdf",
    "20250927-ODCC开放数据中心委员会：2025年ETH-X Scale Up 协议测试报告(39页).pdf",
    "20250927-ODCC开放数据中心委员会：2025年NVME SSD的写放大研究(41页).pdf",
]


def row(name, pages=10, score=6, size=1000, status="ok", folder="报告"):
    rel = "%s/%s" % (folder, name)
    return {"status": status, "sha256": rel, "rel": rel, "score": score,
            "size": size, "meta": {"pages": pages}}


def names(group):
    return {Path(m["rel"]).name for m in [group["keep"]] + group["extra"]}


class SimilarityTests(unittest.TestCase):
    def test_publication_date_and_page_count_are_not_part_of_the_name(self):
        self.assertEqual(PK.name_key("报告/20250925-液冷白皮书(40页).pdf"),
                         PK.name_key("报告/液冷白皮书.pdf"))

    def test_copies_of_one_report_score_above_the_threshold(self):
        grams = [PK.trigrams(PK.name_key(n)) for n in LIQUID]
        pairs = [PK.similarity(grams[i], grams[j])
                 for i in range(len(grams)) for j in range(i + 1, len(grams))]
        self.assertGreaterEqual(min(pairs), PK.SIM_THRESHOLD)

    def test_unrelated_reports_score_below_the_threshold(self):
        grams = [PK.trigrams(PK.name_key(n)) for n in DISTINCT]
        pairs = [PK.similarity(grams[i], grams[j])
                 for i in range(len(grams)) for j in range(i + 1, len(grams))]
        self.assertLess(max(pairs), PK.SIM_THRESHOLD)


class VersionGroupTests(unittest.TestCase):
    def test_real_batch_groups_every_copy_and_splits_the_rest(self):
        rows = [row(n) for n in LIQUID + COOLING_TOWER + DISTINCT]
        groups = PK.version_groups(rows)
        self.assertEqual(len(groups), 2)
        self.assertEqual(names(groups[0]), set(LIQUID))
        self.assertEqual(names(groups[1]), set(COOLING_TOWER))

    def test_a_small_set_still_finds_its_duplicates(self):
        # Regression: capping common trigrams by share alone dropped the cap to
        # two rows on a small set and discarded the identifying features.
        groups = PK.version_groups([row(n) for n in LIQUID])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["extra"]), 3)

    def test_the_fullest_copy_is_kept(self):
        rows = [row(LIQUID[0], pages=20), row(LIQUID[2], pages=44, size=9000)]
        self.assertEqual(Path(PK.version_groups(rows)[0]["keep"]["rel"]).name, LIQUID[2])

    def test_a_copy_under_the_excluded_tree_is_never_the_keeper(self):
        rows = [row(LIQUID[0], pages=90, folder="要删/reader"), row(LIQUID[2], pages=10)]
        self.assertEqual(PK.version_groups(rows)[0]["keep"]["rel"], "报告/" + LIQUID[2])

    def test_a_report_seen_once_is_not_a_group(self):
        self.assertEqual(PK.version_groups([row(LIQUID[0])]), [])

    def test_min_score_filters_before_grouping(self):
        rows = [row(n, score=2) for n in LIQUID]
        self.assertEqual(len(PK.version_groups(rows, min_score=0)), 1)
        self.assertEqual(PK.version_groups(rows, min_score=5), [])

    def test_a_stricter_threshold_splits_the_looser_copies(self):
        rows = [row(n) for n in LIQUID]
        self.assertEqual(len(PK.version_groups(rows, threshold=0.99)), 0)

    def test_only_judged_rows_are_read(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "l1_results.jsonl"
            path.write_text(
                json.dumps(row(LIQUID[0]), ensure_ascii=False) + "\n"
                + json.dumps(row(LIQUID[1], status="l0"), ensure_ascii=False) + "\n"
                + json.dumps({"status": "ok"}, ensure_ascii=False) + "\n"
                + "not json\n", encoding="utf-8")
            saved, L1.RESULTS = L1.RESULTS, path
            try:
                self.assertEqual(len(PK.scored_rows()), 1)
            finally:
                L1.RESULTS = saved

    def test_the_report_reads_but_never_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "l1_results.jsonl"
            body = "".join(json.dumps(row(n), ensure_ascii=False) + "\n" for n in LIQUID)
            path.write_text(body, encoding="utf-8")
            saved, L1.RESULTS = L1.RESULTS, path
            try:
                PK.cmd_versions(types.SimpleNamespace(
                    min_score=0, show=0, threshold=PK.SIM_THRESHOLD))
            finally:
                L1.RESULTS = saved
            self.assertEqual(path.read_text(encoding="utf-8"), body)


if __name__ == "__main__":
    unittest.main()
