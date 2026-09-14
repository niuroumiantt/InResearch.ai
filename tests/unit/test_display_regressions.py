"""Bounded regressions for public fact formatting and product-library search.

Run: python3 tests/unit/test_display_regressions.py
No real files or services are modified. The search test runs the actual inline
JavaScript helpers with Node when available; it does not reimplement them.
"""

from inresearch.paths import project_root
import json
import shutil
import subprocess
import unittest
from datetime import date
from unittest.mock import patch

from inresearch.knowledge import facts as facts


class PublicFactDisplayTests(unittest.TestCase):
    def record(self, value=None, unit="比值", **changes):
        row = dict(entity={"label": "测试对象"}, value=value, unit=unit,
                   as_of="2025", caliber={"basis": "测试口径"})
        row.update(changes)
        return row

    # -- 分发受限的条目在对外出口就被挡住 --------------------------------
    # 2026-09-13 的 C3 A 档复审发现：sensitive 此前只在内部视图里显示一个 🔒，
    # --public 照样把值打出来。中国联通 IDC 建设标准那 34 条的原件写着「企业内部
    # 资料，严格保密」——金额转区间挡不住这件事，泄露的是「某运营商企标里 2000kW
    # 柴发的概算价位大约在四百万量级」这个事实本身，不是它的第二位有效数字。
    def test_a_restricted_fact_never_shows_its_value(self):
        row = self.record(4000000.0, unit="元/计量单位", sensitive=True,
                          as_of="2013")
        result = facts.public_view(row, {"public_band": {"step": 10000}},
                                   today_year=2026)
        self.assertIn(facts.WITHHELD, result)
        self.assertNotIn("4,000,000", result)
        self.assertNotIn("3,990,000", result)   # 区间下界也不许露
        self.assertIn("2013", result)           # 年份仍然给，它不是秘密

    def test_the_entity_is_still_named(self):
        """实名照旧是用户 2026-08-17 拍板的规则，这次只挡值，不改那一条。"""
        row = self.record(4000000.0, sensitive=True)
        self.assertIn("测试对象",
                      facts.public_view(row, {}, today_year=2026))

    def test_an_unrestricted_money_fact_is_still_banded(self):
        row = self.record(4406.0, unit="元/㎡")
        result = facts.public_view(row, {"public_band": {"step": 500}},
                                   today_year=2026)
        self.assertIn("4,000–4,500", result)
        self.assertNotIn(facts.WITHHELD, result)

    def test_the_gate_is_on_the_only_public_exit(self):
        """门放在唯一出口上，不靠调用方自觉——库里受限的每一条都不能漏。

        不钉条数：受限这一类会随复审增减（2026-09-13 所有者取消了 3 条招标控制价的
        标记，由 37 降到 34），钉住条数只会让测试在正确的改动上报红。
        """
        store = json.loads((project_root() / 'data/facts.json')
                           .read_text(encoding='utf-8'))['records']
        metrics = {m['metric_id']: m for m in json.loads(
            (project_root() / 'framework/metrics.json')
            .read_text(encoding='utf-8'))['metrics']}
        restricted = [f for f in store if facts.restricted(f)]
        self.assertTrue(restricted)
        for f in restricted:
            line = facts.public_view(f, metrics[f['metric_id']], 2026)
            self.assertIn(facts.WITHHELD, line, f['fact_id'])
            if f.get('value') is not None:
                digits = ('%d' % int(f['value']))[:4]
                self.assertNotIn(digits, line.replace(str(f.get('as_of')), ''),
                                 f['fact_id'])

    def test_nonfinancial_precision_and_zero(self):
        for value in [1.63, 1.41, 1.076, 0]:
            with self.subTest(value=value):
                result = facts.public_view(self.record(value), {}, today_year=2026)
                self.assertIn(f"**{value} 比值**", result)
                self.assertNotIn("约 2", result)

    def test_upper_bound_keeps_policy_precision(self):
        result = facts.public_view(self.record(1.25, bound="upper"), {}, today_year=2026)
        self.assertIn("**不高于 1.25 比值**", result)

    def test_disclosed_ranges_are_not_missing(self):
        for lo, hi, unit in [(4, 7, "年"), (200, 300, "MW/年"),
                             (1.05, 1.076, "比值")]:
            with self.subTest(unit=unit):
                result = facts.public_view(self.record(unit=unit, value_range=[lo, hi]), {})
                self.assertIn(f"**{lo}–{hi} {unit}**", result)
                self.assertNotIn("未披露", result)

    def test_public_band_still_redacts_point_amount(self):
        result = facts.public_view(self.record(4406, unit="元/㎡"),
                                   {"public_band": {"step": 500}}, today_year=2026)
        self.assertIn("**4,000–4,500 元/㎡**", result)
        self.assertNotIn("4,406", result)

    def test_fractional_public_band_keeps_endpoints(self):
        result = facts.public_view(self.record(3.25, unit="元/份"),
                                   {"public_band": {"step": 0.5}}, today_year=2026)
        self.assertIn("**3–3.5 元/份**", result)

    def test_unknown_remains_unknown(self):
        result = facts.public_view(self.record(), {}, today_year=2026)
        self.assertIn("未披露（留白）", result)
        self.assertNotIn("**0", result)

    def test_vintage_uses_current_year_unless_overridden(self):
        with patch.object(facts, "date") as mock_date:
            mock_date.today.return_value = date(2031, 1, 1)
            self.assertIn("距今约 6 年", facts.public_view(self.record(1.63), {}))
            self.assertIn("距今约 1 年",
                          facts.public_view(self.record(1.63), {}, today_year=2026))

    def test_existing_range_records_are_preserved(self):
        records, metrics = facts.load()
        ranges = [row for row in records if row.get("value_range") is not None]
        self.assertGreaterEqual(len(ranges), 4)
        for row in ranges:
            with self.subTest(fact_id=row["fact_id"]):
                result = facts.public_view(row, metrics[row["metric_id"]])
                lo, hi = row["value_range"]
                self.assertIn(f"{facts.fmt_value(lo, row['unit'])}–"
                              f"{facts.fmt_value(hi, row['unit'])}", result)
                self.assertNotIn("未披露（留白）", result)


class ProductLibrarySearchTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is required for actual browser JS helpers")
    def test_actual_search_helpers_preserve_chinese_and_model_queries(self):
        root = project_root()
        script = r"""
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const root=process.argv[1],html=fs.readFileSync(root+"/web/pages/admin/product/index.html","utf8");
const start=html.indexOf("const searchNorm ="),end=html.indexOf("function modelTokens(",start);
assert.ok(start>=0 && end>start);
const ctx={};
vm.runInNewContext(html.slice(start,end)+";globalThis.matches=productMatchesQuery;",ctx);
const rows=[
 {company_cn:"华为",company_en:"Huawei",product_line:"液冷 CDU",category:"制冷",representative_models:"FusionCool"},
 {company_cn:"戴尔",company_en:"Dell",product_line:"风冷服务器",category:"计算",representative_models:"H100 SXM 80GB"},
 {company_cn:"维谛",company_en:"Vertiv",product_line:"液冷电源",category:"电源",representative_models:"Power Shelf"}
];
const match=q=>rows.filter(p=>ctx.matches(p,q)).map(p=>p.company_cn);
assert.deepEqual(match("华为"),["华为"]);
assert.deepEqual(match("液冷"),["华为","维谛"]);
assert.deepEqual(match("电源"),["维谛"]);
assert.deepEqual(match("华为 液冷"),["华为"]);
assert.deepEqual(match("液冷 电源"),["维谛"]);
assert.deepEqual(match("无此普通中文词"),[]);
assert.deepEqual(match("！！！"),[]);
assert.equal(match("  ").length,3);
assert.deepEqual(match("Ｈ１００"),["戴尔"]);
assert.deepEqual(match("h100-sxm"),["戴尔"]);
assert.deepEqual(match("h100sxm"),["戴尔"]);
const actual=JSON.parse(fs.readFileSync(root+"/data/products.json")).records;
const counts={};
for(const q of ["华为","液冷","电源"]){
 counts[q]=actual.filter(p=>ctx.matches(p,q)).length;
 assert.ok(counts[q]>0 && counts[q]<actual.length,q+" must narrow the real library");
}
assert.ok(html.includes("&&productMatchesQuery(p,q);"),"render must use the tested search predicate");
console.log(JSON.stringify(counts));
"""
        result = subprocess.run(["node", "-e", script, str(root)],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout))


class SplitAsserterTests(unittest.TestCase):
    """同一家写两种名字就是两家——踩过三次了。

    asserter 进 claim_key，所以两种写法之间的重复、修订、争议**互相看不见**：
    不撞键、也不会被争议分诊捞出来，只会安静地把一家的序列劈成两半。
    """

    def rows(self, *pairs):
        return [{'asserter': name} for name, count in pairs for _ in range(count)]

    def test_two_spellings_of_one_house_are_reported(self):
        found = facts.split_asserters(self.rows(('NVIDIA', 26), ('英伟达', 22)))
        self.assertEqual(found, [('英伟达', [('NVIDIA', 26), ('英伟达', 22)])])

    def test_one_spelling_alone_is_not_a_split(self):
        """只用别名、没有并存，键就没劈开——报它只会变成噪音。"""
        self.assertEqual(facts.split_asserters(self.rows(('NVIDIA', 26))), [])
        self.assertEqual(facts.split_asserters(self.rows(('英伟达', 26))), [])

    def test_unrelated_houses_are_not_merged(self):
        """别名表只收同一法人的不同写法，不收同集团的不同主体。"""
        found = facts.split_asserters(self.rows(('中国移动', 5), ('中移动信息', 3)))
        self.assertEqual(found, [])

    def test_the_worst_split_is_reported_first(self):
        found = facts.split_asserters(
            self.rows(('Google', 2), ('谷歌', 3), ('NVIDIA', 26), ('英伟达', 22)))
        self.assertEqual([canon for canon, _ in found], ['英伟达', '谷歌'])

    def test_the_live_store_has_no_split_left(self):
        stored, _ = facts.load()
        self.assertEqual(facts.split_asserters(stored), [])


class BuriedAsserterTests(unittest.TestCase):
    """「据 X 统计」的 X 就是断言者，别让它留在 locator 的引号里。

    cn-dc-occupancy-2023 就是这样漏掉的：locator 写着「据中国信通院统计」，
    asserter 却是「未注明」，那条数因此既拿不到归属，也进不了与科智那条的争议对。
    """

    def fact(self, locator, asserter="未注明"):
        return {"fact_id": "x", "asserter": asserter,
                "evidence": {"locator": locator}}

    def test_a_named_house_in_the_quote_is_reported(self):
        found = facts.buried_asserters([self.fact("正文「据中国信通院统计，上架率 66.7%」")])
        self.assertEqual([f[0] for f in found], ["x"])

    def test_a_latin_name_is_reported(self):
        self.assertTrue(facts.buried_asserters([self.fact("「根据GTW数据，2024 年新增 58GW」")]))

    def test_data_centre_is_not_a_house(self):
        """「数据中心」会被「据X」的模式误切成「据中心…」。"""
        self.assertEqual(facts.buried_asserters(
            [self.fact("「数据中心项目可行性研究报告」")]), [])

    def test_a_subjectless_phrase_is_not_a_house(self):
        for vague in ("「据公开数据测算」", "「据各厂商官网数据」"):
            self.assertEqual(facts.buried_asserters([self.fact(vague)]), [], vague)

    def test_an_already_named_record_is_not_reported(self):
        self.assertEqual(facts.buried_asserters(
            [self.fact("正文「据中国信通院统计」", asserter="中国信通院")]), [])

    def test_the_live_store_has_none_left(self):
        """全库扫一遍：locator 点了名而字段空着的，应当已经补完。"""
        stored, _ = facts.load()
        self.assertEqual(facts.buried_asserters(stored), [])


if __name__ == "__main__":
    unittest.main()
