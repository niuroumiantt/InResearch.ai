"""第二个站:Bloomberg,仅栏目页召回。

9-02 站长的思路转向:「一个确定性比不确定性更方便……我有 10 个页面,每个页面
找到最优路径,最快找到文章就好了」。Bloomberg 是这个思路的实验组 —— **不配
关键词、不搜索,只爬官方 AI 栏目页**;FT 保持混合召回当对照组,跑一周比产出。

钉住的性质:
- 编排层认「站点词汇表」而不是 ft 这个名字 —— 加站不改 run/cli 的逻辑;
- Bloomberg 只收带日期的正稿链接,newsletters(拼盘简报)在地址上就被挡掉;
- 栏目页没有分页,翻页靠「没有新的」停 —— 这是声明,不是缺陷;
- 专题线专属标签不参与「仅提及」判定 —— 编辑判定轮不到我们再数词;
- 档位 manual:可见窗口,和 FT 同一档;域名早已在契约表里,不扩「能读谁」。
"""
from __future__ import annotations

import pytest

from inews import archive
from inews import ledger as ledger_store
from inews import run, runlog, sites, stats
from inews.browser import contract, tiers
from inews.sites import bloomberg, cnbc, ft, wsj


def test_the_registry_serves_all_sites_and_refuses_strangers():
    assert sites.get("ft") is ft
    assert sites.get("bloomberg") is bloomberg
    assert sites.get("cnbc") is cnbc
    assert sites.get("wsj") is wsj
    with pytest.raises(KeyError) as caught:
        sites.get("nikkei")
    assert all(
        name in str(caught.value) for name in ("ft", "bloomberg", "cnbc", "wsj")
    )


def test_bloomberg_article_id_is_date_plus_slug():
    url = "https://www.bloomberg.com/news/articles/2026-09-01/openai-strikes-landmark-data-deal"
    assert bloomberg.article_id(url) == "2026-09-01-openai-strikes-landmark-data-deal"
    # 不是文章的路径不发身份
    assert bloomberg.article_id("https://www.bloomberg.com/ai") == ""


_HUB_HTML = """
<html><body>
<nav><a href="/markets">Markets</a><a href="/ai">AI</a></nav>
<div class="card">
  <a href="/news/articles/2026-09-01/openai-strikes-landmark-data-deal">
    OpenAI strikes landmark data deal with publishers</a>
  <time datetime="2026-09-01T10:00:00Z"></time>
</div>
<div class="card">
  <a href="/news/features/2026-08-30/inside-anthropic-safety-lab">
    Inside Anthropic&#x27;s safety lab, engineers race ahead</a>
</div>
<a href="/news/newsletters/2026-09-01/five-things-to-start-your-day">
  Five Things to Start Your Day: AI edition roundup</a>
<a href="/news/articles/2026-09-01/openai-strikes-landmark-data-deal">Read</a>
</body></html>
"""


def test_parse_keeps_dated_articles_and_drops_newsletters():
    rows = bloomberg.parse_search_results(
        _HUB_HTML, bloomberg.TOPIC_LABEL, bloomberg.hub_url("ai")
    )
    ids = [row["article_id"] for row in rows]
    assert ids == [
        "2026-09-01-openai-strikes-landmark-data-deal",
        "2026-08-30-inside-anthropic-safety-lab",
    ]
    first = rows[0]
    assert first["keywords"] == [bloomberg.TOPIC_LABEL]
    assert first["published_at"] == "2026-09-01T10:00:00Z"
    assert first["url"].startswith("https://www.bloomberg.com/news/articles/")
    # 拼盘简报在地址上就被挡掉 —— newsletters 是路径事实,不是质量评价
    assert not any("five-things" in row["article_id"] for row in rows)


def test_bloomberg_scrolls_its_listing_and_ft_does_not():
    """列表页要不要边滚边收,由站点词汇表声明,编排层不表态。
    Bloomberg 的栏目页是懒加载的河(9-02 实测,见 test_listing_probe);
    FT 搜索页有真分页,不滚。"""
    assert bloomberg.LISTING_SCROLLS is True
    assert ft.LISTING_SCROLLS is False


def test_the_listing_fetcher_passes_the_scroll_declaration(monkeypatch):
    """接线用例:声明要真的流进浏览器层,否则词汇表说破天也没人滚。"""
    import inews.browser as browser_pkg

    captured: dict[str, object] = {}

    def fake(url, **kwargs):
        captured.update(kwargs)
        return "<html></html>", url

    monkeypatch.setattr(browser_pkg, "fetch_rendered_listing", fake)
    run._listing_fetcher_for(bloomberg)("https://www.bloomberg.com/ai")
    assert captured.get("scroll_listing") is True
    run._listing_fetcher_for(ft)("https://www.ft.com/search?q=AI")
    assert captured.get("scroll_listing") is False


def test_hub_pages_do_not_pretend_to_paginate():
    """Bloomberg 栏目页是无限滚动,?page=N 不存在 —— 第 2 页就是第 1 页,
    翻页循环靠「没有新的」自然停下。假装有分页只会白开窗口。"""
    assert bloomberg.hub_url("ai", 2) == bloomberg.hub_url("ai", 1)


def test_collect_walks_hubs_only_for_bloomberg():
    seen_urls: list[str] = []

    def fake(url: str) -> tuple[str, str]:
        seen_urls.append(url)
        return _HUB_HTML, url

    rows, _notes, sources = run.collect(
        [], site=bloomberg, fetch_listing=fake, pace_seconds=0
    )
    assert seen_urls and all("/ai" in url for url in seen_urls)
    assert [row["found_via"] for row in rows] == ["ai", "ai"]
    assert all(source["kind"] == "hub" for source in sources)


def test_bloomberg_topic_rows_are_editorial_not_mention_only():
    row = {
        "keywords": [bloomberg.TOPIC_LABEL],
        "title_en": "Inside Anthropic's safety lab",
        "body": "正文" * 400,
    }
    assert stats.is_mention_only(row) is False


def test_bloomberg_rides_the_manual_tier_and_the_existing_domain():
    assert tiers.tier_of("bloomberg") == tiers.MANUAL_TIER
    assert contract.site_for_url(
        "https://www.bloomberg.com/news/articles/2026-09-01/some-story"
    ) == "bloomberg"


_RELATIVE_TIME_HTML = """
<html><body>
<div class="card">
  <a href="/news/articles/2026-09-01/baidu-releases-new-ai-model-for-search">
    Baidu Releases New AI Model for Search</a>
  <time>2 hours ago</time>
</div>
</body></html>
"""


def test_a_relative_time_label_yields_to_the_url_date():
    """9-02 二轮实测:十篇文件名里带着日期的稿子仍进了 undated/ —— 卡片上
    有 <time>,但只有「Sep 1」「2 hours ago」这类相对文字,非空却解析不出时刻。
    判据要换成「解析得出」:解析不出就读路径里的日期(站方发的结构性事实)。"""
    rows = bloomberg.parse_search_results(
        _RELATIVE_TIME_HTML, bloomberg.TOPIC_LABEL, bloomberg.hub_url("ai")
    )
    assert rows[0]["published_at"] == "2026-09-01"


_CREDIT_CARD_HTML = """
<html><body>
<div class="card">
  <a href="/news/articles/2026-09-01/robots-learn-from-workers">
    <img src="/img/robots.jpg"><span>Andrey Rudakov/Bloomberg</span>
  </a>
  <a href="/news/articles/2026-09-01/robots-learn-from-workers">
    Workers Are Teaching AI-Powered Robots to Take Over Their Jobs</a>
</div>
<div class="card">
  <a href="/news/articles/2026-09-01/photo-essay-data-centers">
    <img src="/img/dc.jpg"><span>Juuso Westerlund for Bloomberg Businessweek</span>
  </a>
</div>
</body></html>
"""


def test_a_photo_credit_anchor_never_names_the_article():
    """9-02 第二轮实测:清单里出现「Andrey Rudakov/Bloomberg」这类「标题」——
    那是图片署名。同一张卡片对同一篇文章常有两个锚点:包着 <img> 的那个,
    文字是图注/署名;正题在不包图的锚点里。锚点包不包图是结构性事实。"""
    rows = bloomberg.parse_search_results(
        _CREDIT_CARD_HTML, bloomberg.TOPIC_LABEL, bloomberg.hub_url("ai")
    )
    titles = {row["article_id"]: row["title_en"] for row in rows}
    assert (
        titles["2026-09-01-robots-learn-from-workers"]
        == "Workers Are Teaching AI-Powered Robots to Take Over Their Jobs"
    )
    # 只有图锚点的那篇**不丢**:署名标题难看,漏抓更糟 —— 召回优先。
    assert "2026-09-01-photo-essay-data-centers" in titles


_LEAKY_AI_PAGE_HTML = """
<html><body>
<a href="/news/articles/2026-09-04/softbank-group-prices-1-trillion-retail-bond-at-4-75">
  SoftBank Group Prices ¥1 Trillion Retail Bond at 4.75%</a>
<a href="/news/articles/2026-09-04/nvidia-prices-3-billion-bond">
  Nvidia Prices $3 Billion Bond</a>
<a href="/news/articles/2026-09-03/mediatek-shares-soar-after-nvidia-investment">
  MediaTek Shares Soar 10% After Blockbuster Nvidia Investment</a>
<a href="/news/articles/2026-09-03/dell-boosts-sales-forecast-on-ai-server-demand">
  Dell Boosts Annual Sales Forecast on AI Server Demand; Shares Rise</a>
<a href="/news/articles/2026-09-03/cxmt-sales-soar-amid-memory-crunch">
  Chinese Chipmaker CXMT's Sales Soar Amid Memory Crunch</a>
<a href="/news/articles/2026-09-03/huawei-profit-decline-after-memory-crunch">
  Huawei Profit Decline Widens After Memory Crunch Takes Toll</a>
<a href="/news/articles/2026-09-03/hpe-sales-forecast-on-ai-server-networking-demand">
  HPE Lifts Sales Forecast on AI Demand for Servers, Networking</a>
<a href="/news/articles/2026-09-03/softbank-seeks-loan-for-openai-stake-funding">
  SoftBank Seeks Another $10 Billion Loan for OpenAI Stake Funding</a>
<a href="/news/articles/2026-09-03/asia-data-center-debt-binge-hits-bank-limits">
  Asia Data Center Debt Binge Hitting Banks' Limits, Barclays Says</a>
<a href="/news/articles/2026-09-03/crusoe-raises-funding-at-30-billion-valuation">
  Crusoe Raises Over $3 Billion in Funding at $30 Billion Valuation</a>
<a href="/news/articles/2026-09-03/pimco-says-ai-debt-is-stoking-bond-yields">
  Pimco Says AI Debt Is Stoking Bond Yields</a>
<a href="/news/articles/2026-09-03/investor-frenzy-ai-convertible-bonds">
  Investor Frenzy for AI Strips Safeguards From Convertible Bonds</a>
<a href="/news/articles/2026-09-03/asia-economies-fiscal-buffers-ai-boom">
  Asia's Economies Avert Energy Shock Via Fiscal Buffers, AI Boom</a>
<a href="/news/articles/2026-09-03/us-trade-gap-widens-on-ai-push">
  US Trade Gap Widens to Largest Since Early 2025 on AI Push</a>
<a href="/news/articles/2026-09-03/homeowners-make-money-with-ai-and-batteries">
  Almost Anyone Can Make Money Selling Electricity With AI and Batteries</a>
</body></html>
"""


def test_bloomberg_rechecks_ai_relevance_before_opening_articles():
    """9-04 现场回归：/ai HTML 会夹带全站侧栏，栏目标签不能无条件放行。"""
    rows = bloomberg.parse_search_results(
        _LEAKY_AI_PAGE_HTML, bloomberg.TOPIC_LABEL, bloomberg.hub_url("ai")
    )
    ids = {row["article_id"] for row in rows}
    assert "2026-09-04-softbank-group-prices-1-trillion-retail-bond-at-4-75" not in ids
    # 即使是 GPU 厂商，普通公司债没有说明 AI/算力用途，也不是产业融资。
    assert "2026-09-04-nvidia-prices-3-billion-bond" not in ids
    assert "2026-09-03-mediatek-shares-soar-after-nvidia-investment" not in ids
    assert "2026-09-03-dell-boosts-sales-forecast-on-ai-server-demand" not in ids
    assert "2026-09-03-pimco-says-ai-debt-is-stoking-bond-yields" not in ids
    assert "2026-09-03-investor-frenzy-ai-convertible-bonds" not in ids
    assert "2026-09-03-asia-economies-fiscal-buffers-ai-boom" not in ids
    assert "2026-09-03-us-trade-gap-widens-on-ai-push" not in ids
    assert "2026-09-03-homeowners-make-money-with-ai-and-batteries" not in ids
    assert ids == {
        "2026-09-03-cxmt-sales-soar-amid-memory-crunch",
        "2026-09-03-huawei-profit-decline-after-memory-crunch",
        "2026-09-03-hpe-sales-forecast-on-ai-server-networking-demand",
        "2026-09-03-softbank-seeks-loan-for-openai-stake-funding",
        "2026-09-03-asia-data-center-debt-binge-hits-bank-limits",
        "2026-09-03-crusoe-raises-funding-at-30-billion-valuation",
    }
    assert {row["admission_reason"] for row in rows} <= {
        "ai_article", "core_infrastructure"
    }


@pytest.mark.parametrize("title", [
    "Nvidia Launches Open-Source Model",
    "Google Makes Gemma Model Open Source",
    "Meta Releases Closed-Source Model",
])
def test_open_and_closed_model_news_is_admitted(title):
    assert bloomberg.admission_reason(title) == "ai_article"


@pytest.mark.parametrize("title", [
    "Nvidia Signs Supply Deal With TSMC",
    "Samsung Wins Nvidia Memory Supply Contract",
])
def test_component_vendor_supply_deals_are_admitted(title):
    assert bloomberg.admission_reason(title) == "core_infrastructure"


def test_existing_ledger_noise_is_hidden_consistently_across_every_view(tmp_path):
    """独立来源页、跨库摘要和统一后台必须使用同一份存量准入名单。"""
    bad_id = "2026-09-04-softbank-group-prices-1-trillion-retail-bond-at-4-75"
    good_id = "2026-09-03-anthropic-credit-facility"
    entries = {
        bad_id: {
            "url": f"https://www.bloomberg.com/news/articles/2026-09-04/{bad_id[11:]}",
            "title": "SoftBank Group Prices ¥1 Trillion Retail Bond at 4.75%",
            "published_at": "2026-09-04", "body_status": "ok",
            "keywords": [bloomberg.TOPIC_LABEL],
        },
        good_id: {
            "url": f"https://www.bloomberg.com/news/articles/2026-09-03/{good_id[11:]}",
            "title": "Anthropic Nears Finalizing $15 Billion Pre-IPO Credit Facility",
            "published_at": "2026-09-03", "body_status": "failed",
            "keywords": [bloomberg.TOPIC_LABEL],
        },
    }
    base = tmp_path / bloomberg.OUT_DIR
    ledger_store.save(ledger_store.path_for(base), entries)
    archive.save(base, [
        {"article_id": bad_id, "body": "坏" * 100},
        {"article_id": good_id, "body": "好" * 250},
    ])
    runlog.record(runlog.path_for(base), {
        "finished_at": "2026-09-04T09:20:00+08:00", "ok": True, "new": 0,
    })

    source_rows = run.library_rows(entries, [], site=bloomberg)
    summaries = run.library_summaries(base)
    summary = next(item for item in summaries if item["key"] == bloomberg.KEY)
    snapshots = run.library_snapshots(tmp_path)
    snapshot = next(item for item in snapshots if item["site"] is bloomberg)

    assert [row["article_id"] for row in source_rows] == [good_id]
    assert summary["articles"] == 1
    assert summary["with_body"] == 0 and summary["failed"] == 1
    assert [row["article_id"] for row in snapshot["rows"]] == [good_id]
    assert snapshot["summary"]["articles"] == 1
    assert run._library_body_chars(base, source_rows) == 250


def test_same_url_title_revision_survives_the_real_incremental_ledger_flow():
    """Bloomberg 改标题不改 URL：seen 行刷新，正文保留，错配译文清空。"""
    article = "2026-09-02-mediatek-shares-soar-after-nvidia-investment"
    url = f"https://www.bloomberg.com/news/articles/2026-09-02/{article[11:]}"
    entries = {
        article: {
            "url": url,
            "title": "MediaTek Shares Soar 10% After Nvidia Investment",
            "title_zh": "联发科股价上涨",
            "published_at": "",
            "section": "Markets",
            "body_status": "ok",
            "crawled_at": "2026-09-02T10:00:00Z",
            "keywords": [bloomberg.TOPIC_LABEL],
        }
    }
    current = {
        "article_id": article,
        "url": url,
        "title_en": "Nvidia Mega-Deal Ushers MediaTek Into Top AI Chipmaker Club",
        "published_at": "2026-09-02T12:30:00Z",
        "section": "Technology",
        "keywords": [bloomberg.TOPIC_LABEL],
    }

    assert ledger_store.merge_discovery(entries, [current]) == 1
    fresh, seen = ledger_store.split_new(entries, [current])
    visible = run.library_rows(entries, fresh, site=bloomberg)
    archived = {
        **current,
        "title_en": "MediaTek Shares Soar 10% After Nvidia Investment",
        "title_zh": "联发科股价上涨",
        "body": "完整正文",
    }
    render_only_visible = run.library_rows(entries, [archived], site=bloomberg)

    assert fresh == [] and seen == [current]
    assert entries[article]["title"] == current["title_en"]
    assert entries[article]["published_at"] == "2026-09-02T12:30:00Z"
    assert entries[article]["section"] == "Technology"
    assert entries[article]["body_status"] == "ok"
    assert entries[article]["title_zh"] == ""
    assert [row["article_id"] for row in visible] == [article]
    assert render_only_visible[0]["title_en"] == current["title_en"]
    assert render_only_visible[0]["title_zh"] == ""
    assert render_only_visible[0]["body"] == "完整正文"
    assert archived["title_en"] == current["title_en"]
    assert archived["title_zh"] == ""


def test_same_article_id_with_a_different_url_is_still_new():
    """通用标题刷新不能破坏 ledger 原有的“同 id 换链接按新稿”保证。"""
    entries = {
        "same": {
            "url": "https://www.ft.com/content/old",
            "title": "Old title",
            "title_zh": "旧标题",
            "body_status": "ok",
            "keywords": [],
        }
    }
    row = {
        "article_id": "same",
        "url": "https://www.ft.com/content/new",
        "title_en": "New title",
        "published_at": "2026-09-04",
        "keywords": [],
    }

    ledger_store.merge_discovery(entries, [row])
    fresh, seen = ledger_store.split_new(entries, [row])

    assert fresh == [row] and seen == []
    assert entries["same"]["url"] == "https://www.ft.com/content/old"
    assert entries["same"]["title"] == "Old title"
    assert entries["same"]["title_zh"] == "旧标题"


def test_a_card_without_a_time_tag_takes_the_date_from_the_url():
    """9-02 首轮实测:/ai 页的卡片上没有 <time>,九十多篇全进了 undated/。
    可日期就编码在文章路径里(/news/articles/2026-08-30/…)—— 那是站方发的
    结构性事实,读它不是猜时间。有 <time> 时仍以 <time> 为准(更精确)。"""
    rows = bloomberg.parse_search_results(
        _HUB_HTML, bloomberg.TOPIC_LABEL, bloomberg.hub_url("ai")
    )
    with_time, without_time = rows[0], rows[1]
    assert with_time["published_at"] == "2026-09-01T10:00:00Z"
    assert without_time["published_at"] == "2026-08-30"


def test_bloomberg_declares_its_load_more_button_and_ft_has_none():
    """要不要点「Load more」由站点词汇表声明,浏览器层不替站点表态。"""
    assert bloomberg.LOAD_MORE_TEXT == "load more"
    assert ft.LOAD_MORE_TEXT == ""


def test_the_listing_fetcher_passes_the_load_more_declaration(monkeypatch):
    """接线用例:声明要真的流进浏览器层,否则词汇表说破天也没人点。"""
    import inews.browser as browser_pkg

    captured: dict[str, object] = {}

    def fake(url, **kwargs):
        captured.update(kwargs)
        return "<html></html>", url

    monkeypatch.setattr(browser_pkg, "fetch_rendered_listing", fake)
    run._listing_fetcher_for(bloomberg)("https://www.bloomberg.com/ai")
    assert captured.get("load_more_text") == "load more"
    run._listing_fetcher_for(ft)("https://www.ft.com/search?q=AI")
    assert captured.get("load_more_text") == ""
