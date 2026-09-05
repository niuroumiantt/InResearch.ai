"""inews → inresearch 内容接口的验收测试。

守住手册第 3 节的边界: 两个产品是平行产品, 账号、会员与授权各自管理。
研究侧采用新闻内容, 但**身份一个字段都不能跟着过来**。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import inews_adoption as ia


def package(items=None, **over):
    items = items if items is not None else [{
        "item_id": "a1", "title": "T", "published_at": "2026-09-05T00:00:00Z",
        "origin_url": "https://example.com/a", "origin_domain": "example.com",
        "summary": "s", "topics": ["ai"], "language": "en",
    }]
    p = {"schema_version": 1, "source": "inews.today",
         "produced_at": "2026-09-05T00:00:00Z", "items": items,
         "package_version": ia.compute_version(items)}
    p.update(over)
    return p


class TestIdentityFirewall(unittest.TestCase):
    """最重要的一组:身份不得跨产品流动。"""

    def test_top_level_identity_field_is_refused(self):
        for key in ("user", "account_id", "email", "session", "token", "member_id"):
            with self.subTest(key=key):
                p = package()
                p[key] = "x"
                p["package_version"] = ia.compute_version(p["items"])
                with self.assertRaises(ia.AdoptionError) as cm:
                    ia.validate_package(p)
                self.assertIn("身份字段", str(cm.exception))

    def test_identity_nested_inside_an_item_is_refused(self):
        items = [{"item_id": "a1", "title": "T", "published_at": "2026-09-05T00:00:00Z",
                  "origin_url": "https://e.com/a", "submitted_by": {"email": "x@y.z"}}]
        with self.assertRaises(ia.AdoptionError):
            ia.validate_package(package(items))

    def test_identity_deep_inside_a_list_is_refused(self):
        items = [{"item_id": "a1", "title": "T", "published_at": "2026-09-05T00:00:00Z",
                  "origin_url": "https://e.com/a",
                  "topics": [{"tag": "ai", "meta": [{"subscriber": 7}]}]}]
        with self.assertRaises(ia.AdoptionError):
            ia.validate_package(package(items))

    def test_membership_words_are_all_covered(self):
        """会员相关的词要全覆盖 —— 漏一个就是一条泄漏通路。"""
        for key in ("membership", "subscription", "subscriber", "credential", "api_key"):
            with self.subTest(key=key):
                items = [{"item_id": "a1", "title": "T",
                          "published_at": "2026-09-05T00:00:00Z",
                          "origin_url": "https://e.com/a", key: "x"}]
                with self.assertRaises(ia.AdoptionError):
                    ia.validate_package(package(items))

    def test_a_clean_package_is_accepted(self):
        self.assertEqual(len(ia.validate_package(package())["items"]), 1)


class TestVersionPinning(unittest.TestCase):
    """引用固定版本, 不引用「最新」。"""

    def test_version_is_derived_from_content(self):
        items = package()["items"]
        self.assertEqual(ia.compute_version(items), ia.compute_version(list(items)))

    def test_changing_content_changes_the_version(self):
        a = package()
        b = package([dict(a["items"][0], title="changed")])
        self.assertNotEqual(a["package_version"], b["package_version"])

    def test_tampered_content_is_refused(self):
        """内容在产出后被改过, 「引用固定版本」就失效了 —— 必须拒绝。"""
        p = package()
        p["items"][0]["title"] = "silently changed"
        with self.assertRaises(ia.AdoptionError) as cm:
            ia.validate_package(p)
        self.assertIn("与内容不符", str(cm.exception))

    def test_adoption_record_pins_the_version(self):
        p = package()
        rec = ia.adopt(p, now="2026-09-05T12:00:00Z")
        self.assertEqual(rec["package_version"], p["package_version"])
        self.assertEqual(rec["source"], "inews.today")
        self.assertEqual(rec["adopted_item_ids"], ["a1"])

    def test_adoption_record_carries_no_identity(self):
        rec = ia.adopt(package(), now="2026-09-05T12:00:00Z")
        self.assertIsNone(ia.find_identity_key(rec))

    def test_cannot_adopt_items_not_in_the_package(self):
        with self.assertRaises(ia.AdoptionError):
            ia.adopt(package(), adopted_item_ids=["a1", "not-there"])


class TestPackageValidation(unittest.TestCase):
    def test_wrong_source_is_refused(self):
        with self.assertRaises(ia.AdoptionError):
            ia.validate_package(package(source="somewhere-else"))

    def test_unsupported_schema_is_refused(self):
        with self.assertRaises(ia.AdoptionError):
            ia.validate_package(package(schema_version=99))

    def test_duplicate_item_id_is_refused(self):
        item = {"item_id": "a1", "title": "T", "published_at": "2026-09-05T00:00:00Z",
                "origin_url": "https://e.com/a"}
        with self.assertRaises(ia.AdoptionError):
            ia.validate_package(package([item, dict(item)]))

    def test_non_http_origin_is_refused(self):
        items = [{"item_id": "a1", "title": "T", "published_at": "2026-09-05T00:00:00Z",
                  "origin_url": "javascript:alert(1)"}]
        with self.assertRaises(ia.AdoptionError):
            ia.validate_package(package(items))

    def test_missing_required_field_is_refused(self):
        items = [{"item_id": "a1", "title": "T"}]
        with self.assertRaises(ia.AdoptionError):
            ia.validate_package(package(items))

    def test_load_from_disk(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pkg.json"
            p.write_text(json.dumps(package()), encoding="utf-8")
            self.assertEqual(len(ia.load_package(p)["items"]), 1)


class TestProductsStayIndependent(unittest.TestCase):
    """目录层面的独立性 —— 两个产品不得互相 import。"""

    PRODUCTS = HERE.parent.parent

    def test_inresearch_does_not_import_inews_code(self):
        offenders = []
        for path in (self.PRODUCTS / "inresearch").rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")) and "inews" in stripped:
                    # 采用层自己叫 inews_adoption, 那是本地模块名, 不是跨产品导入。
                    if "inews_adoption" in stripped:
                        continue
                    offenders.append(f"{path.name}: {stripped}")
        self.assertEqual(offenders, [], f"研究侧直接导入了 inews 的代码: {offenders}")

    def test_each_product_has_its_own_identity_implementation(self):
        """手册: 不建统一账号中心。两个产品各自有一套, 就是这个意思。"""
        self.assertTrue((self.PRODUCTS / "inews" / "src" / "auth" / "store.js").is_file())
        self.assertTrue((self.PRODUCTS / "inresearch" / "pipeline" / "auth.py").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
