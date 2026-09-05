"""「和 AI 无关」的噪音怎么挡。

8-24 站长看清单页:「有很多文章都和AI无关呀」。查下来两个来源:
1. 泛分类线:HUBS 里的 technology / cyber-security —— FT 编辑对它们的判定是
   「科技稿 / 安全稿」,不是「AI 稿」。
2. 搜索命中正文提及:FT 搜索匹配全文,正文顺嘴提一句 Anthropic 也算命中
   (实例:对冲基金 Saba 接管 Baillie Gifford,挂着 Anthropic/Nvidia)。

处理(站长选定):砍掉两条泛分类线;提及型**降级隐藏**,不删 —— 判据是结构性
事实(词在不在标题、正文出现几次),召回不缩小(台账、存档都在),只是清单页
默认不给看,一个勾选框可展开。
"""
from __future__ import annotations

from typing import Any

from inews import keywords as kw
from inews import ledger as ledger_store
from inews import render, run, stats
from inews.sites import ft


def test_only_editorially_ai_hubs_remain():
    """technology / cyber-security 下架:它们的编辑判定不是「这是 AI 稿」。"""
    assert "artificial-intelligence" in ft.HUBS
    assert "semiconductors" in ft.HUBS
    assert "technology" not in ft.HUBS
    assert "cyber-security" not in ft.HUBS


def _row(**extra: Any) -> dict[str, Any]:
    return {"article_id": "a", "url": "https://www.ft.com/content/a",
            "title_en": "Hedge fund Saba takes on Baillie Gifford",
            "keywords": ["Anthropic"], **extra}


def test_a_keyword_in_the_title_is_not_a_mere_mention():
    row = _row(title_en="Anthropic's best AI model struggles", body="字" * 700)
    assert stats.is_mention_only(row) is False


def test_multiple_topical_paragraphs_including_the_lead_are_topical():
    """分布在导语与多段的命中才是中心主题；同一段机械重复不能冒充中心度。"""
    body = "Anthropic announced a model.\n\nContext.\n\nAnthropic gave details.\n\nAnthropic starts tests."
    assert stats.is_mention_only(_row(body=body)) is False


def test_one_passing_mention_is_demoted():
    assert stats.is_mention_only(_row(body="x " * 300 + "as Anthropic did.")) is True


def test_a_legacy_hub_label_no_longer_bypasses_body_centrality():
    """旧 FT 专题曾把 AI 与半导体混成一类，不能再无条件绕过正文判断。"""
    row = _row(keywords=[kw.TOPIC_LABEL], body="x " * 300)
    assert stats.is_mention_only(row) is True


def test_no_body_means_no_verdict():
    """没有正文就没法数 —— **不判,不降级**。把取正文失败的当提及型藏起来,
    等于用一个技术故障冒充一次编辑判断。"""
    assert stats.is_mention_only(_row()) is False


def test_fetch_bodies_marks_mentions(monkeypatch):
    rows = [_row()]
    run.fetch_bodies(
        rows,
        fetch_body=lambda _row: {"body": "x " * 300 + "Anthropic once.", "extractor": "t"},
    )
    assert rows[0]["mention_only"] is True


def test_the_ledger_remembers_the_verdict():
    """判定进台账:重画页面不该把它抹掉,也不该每轮重数一遍全库。"""
    entries: dict[str, dict[str, Any]] = {}
    ledger_store.record(
        entries, [_row(body="字" * 700, mention_only=True)],
        crawled_at="2026-08-24T00:00:00+08:00",
    )
    assert entries["a"]["mention_only"] is True
    assert ledger_store.rows(entries)[0]["mention_only"] is True


def test_the_page_hides_mentions_by_default_but_keeps_them():
    """默认藏、可展开、总数如实 —— 「我这会儿不想看」不能变成「再也看不到」。"""
    rows = [
        {"article_id": "a", "title_en": "On-topic", "url": "https://www.ft.com/content/a",
         "published_at": "2026-08-20T09:00:00Z", "keywords": ["AI chip"]},
        {"article_id": "b", "title_en": "Mention", "url": "https://www.ft.com/content/b",
         "published_at": "2026-08-20T10:00:00Z", "keywords": ["Anthropic"],
         "mention_only": True},
    ]
    html = render.render_index(rows, keywords=["AI chip"], generated_at="now")
    assert 'data-mention="1"' in html, "提及型的行要带标记,浏览器端才藏得住"
    assert 'id="mentions"' in html, "要有一个勾选框能把它们展开"
    assert "仅提及" in html
    assert html.count('class="row"') == 2, "行还在 HTML 里,只是默认不显示"


def test_render_only_backfills_verdicts_for_the_backlog():
    """存量也要判一次:判定发生在取正文那一刻,而老库存的正文早就取完了。

    正文的正本在存档里 —— `--render-only` 本来就要把存档整个读一遍,顺路把
    还没有判定的补上,写回台账。**已有判定的不重判**:那可能是站长手工改过的。
    """
    entries = {
        "old": {"url": "u", "title": "Hedge fund Saba takes on Baillie Gifford",
                "published_at": "2026-08-20T09:00:00Z", "keywords": ["Anthropic"],
                "body_status": "ok"},
        "done": {"url": "u2", "title": "T2", "published_at": "",
                 "keywords": ["Anthropic"], "body_status": "ok", "mention_only": False},
    }
    stored = [
        {"article_id": "old", "title_en": "Hedge fund Saba takes on Baillie Gifford",
         "url": "u", "keywords": ["Anthropic"], "body": "x " * 300 + "Anthropic once."},
        {"article_id": "done", "title_en": "T2", "url": "u2",
         "keywords": ["Anthropic"], "body": "x " * 300 + "Anthropic once."},
    ]
    changed = run.backfill_mentions(entries, stored)
    assert changed == 1
    assert entries["old"]["mention_only"] is True
    assert entries["done"].get("mention_only") is False, "已有判定的不许被重判盖掉"
