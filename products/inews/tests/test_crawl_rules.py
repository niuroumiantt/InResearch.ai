"""每个库的清单页顶上写明自己的抓取规则。

9-02 站长:「请把每个页面的爬取规则放在每个页面的上面」。规则是站点词汇表的
一部分(``RULES``),清单页在头部照实列出 —— 读的人不该去猜这一页是怎么来的,
也不该去翻仓库源码。规则文本只写**已被测试钉住的事实**,不写愿望。
"""
from __future__ import annotations

from pathlib import Path

from inews import render, run
from inews.sites import bloomberg, ft


def test_every_site_declares_its_rules_in_the_vocabulary():
    """规则随站点声明:FT 说清双线召回,Bloomberg 说清只走栏目页、不搜索。"""
    assert ft.RULES and bloomberg.RULES
    assert any("关键词" in line for line in ft.RULES)
    assert any("专题页" in line for line in ft.RULES)
    assert any("栏目页" in line for line in bloomberg.RULES)
    assert any("不搜索" in line for line in bloomberg.RULES)


def test_the_index_prints_the_rules_at_the_top():
    """规则在清单页头部、稿件流之前 —— 「放在每个页面的上面」。"""
    html = render.render_index(
        [],
        keywords=[],
        generated_at="now",
        rules=bloomberg.RULES,
        site_label="BLOOMBERG.COM",
        tagline="AI 栏目清单",
    )
    assert "抓取规则" in html
    for line in bloomberg.RULES:
        assert line in html
    assert html.index("抓取规则") < html.index("本轮没有命中")


def test_write_site_wires_each_sites_own_rules(tmp_path: Path):
    """接线用例:write_site 把站点自己的 RULES 交给清单页 —— 2026-08-19 的
    教训,单测各喂各的参数时,接线错误全程隐形。"""
    ft_index = run.write_site(
        [], tmp_path / "ft", keywords=["AI chip"], generated_at="now", site=ft
    )
    bb_index = run.write_site(
        [], tmp_path / "bb", keywords=[], generated_at="now", site=bloomberg
    )
    ft_text = ft_index.read_text(encoding="utf-8")
    bb_text = bb_index.read_text(encoding="utf-8")
    assert ft.RULES[0] in ft_text and bloomberg.RULES[0] not in ft_text
    assert bloomberg.RULES[0] in bb_text and ft.RULES[0] not in bb_text
