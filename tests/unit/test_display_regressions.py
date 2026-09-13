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


if __name__ == "__main__":
    unittest.main()
