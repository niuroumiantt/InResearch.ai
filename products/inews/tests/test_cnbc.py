"""CNBC B 路线：官方 AI 专题、完整 Load More、只收有价值的公开文字稿。"""
from __future__ import annotations

import json

import pytest

from inews import fetch, run, sites
from inews.browser import contract, profile, tiers
from inews.sites import cnbc


def _asset(title: str, **extra):
    row = {
        "id": extra.pop("id", title),
        "type": "cnbcnewsstory",
        "url": "https://www.cnbc.com/2026/09/04/example-ai-story.html",
        "headline": title,
        "description": "",
        "contentClassification": [],
        "premium": False,
        "native": False,
        "datePublished": "2026-09-04T01:00:00Z",
        "section": {"eyebrow": "TECH"},
    }
    row.update(extra)
    return row


def _article_html(text: str, *, embedded_video: bool = False) -> str:
    video = (
        ',"video":{"@type":"VideoObject","name":"embedded clip"}'
        if embedded_video else ""
    )
    return f"""
    <html><head><meta property="og:type" content="article">
      <script type="application/ld+json">
        {{"@type":"NewsArticle","headline":"AI article"{video}}}
      </script>
    </head><body>
      <div class="ArticleBody-articleBody" data-module="ArticleBody">
        <div class="group"><p>{text}</p></div>
      </div>
    </body></html>
    """


def test_registry_hub_and_article_identity_are_explicit():
    assert sites.get("cnbc") is cnbc
    assert cnbc.hub_url("ai-artificial-intelligence", 9) == (
        "https://www.cnbc.com/ai-artificial-intelligence/"
    )
    assert cnbc.article_id(
        "https://www.cnbc.com/2026/09/04/example-ai-story.html"
    ) == "2026-09-04-example-ai-story"
    assert cnbc.article_id("https://www.cnbc.com/video/2026/09/04/clip.html") == ""


def test_listing_fetcher_reads_every_load_more_page(monkeypatch):
    offsets: list[int] = []
    batches = {
        0: [_asset("OpenAI releases a new reasoning model", id="1"),
            _asset("Anthropic launches an AI agent standard", id="2")],
        2: [_asset("Nvidia brings new AI racks online", id="3")],
    }

    def page(offset: int):
        offsets.append(offset)
        return {
            "assets": batches.get(offset, []),
            "pagination": {"totalCount": 3, "pageSize": 2},
        }

    monkeypatch.setattr(cnbc, "_asset_page", page)
    raw, final = cnbc.fetch_listing(cnbc.hub_url(cnbc.HUBS[0]))
    payload = json.loads(raw)
    assert offsets == [0, 2]
    assert payload["raw_loaded"] == payload["total_count"] == 3
    assert len(payload["assets"]) == 3
    assert final == cnbc.hub_url(cnbc.HUBS[0])


@pytest.mark.parametrize("mode", ["missing-total", "early-empty", "duplicate"])
def test_incomplete_load_more_never_pretends_to_be_complete(monkeypatch, mode):
    one = _asset("OpenAI releases a new model", id="1")

    def page(offset: int):
        if mode == "missing-total":
            return {"assets": [one], "pagination": {}}
        if mode == "early-empty":
            return {
                "assets": [one] if offset == 0 else [],
                "pagination": {"totalCount": 2},
            }
        return {
            "assets": [one],
            "pagination": {"totalCount": 2},
        }

    monkeypatch.setattr(cnbc, "_asset_page", page)
    with pytest.raises(RuntimeError, match="totalCount|未展开完整"):
        cnbc.fetch_listing(cnbc.hub_url(cnbc.HUBS[0]))


def test_listing_fetcher_refuses_any_page_other_than_the_official_hub():
    with pytest.raises(RuntimeError, match="只接受官方 AI 专题"):
        cnbc.fetch_listing("https://www.cnbc.com/technology/")


def test_run_uses_the_site_listing_fetcher_instead_of_the_generic_browser():
    assert run._listing_fetcher_for(cnbc) is cnbc.fetch_listing


@pytest.mark.parametrize(
    "changes",
    [
        {"type": "cnbcvideo", "url": "https://www.cnbc.com/video/2026/09/04/x.html"},
        {"type": ""},
        {"native": True},
        {"premium": True},
        {"contentClassification": ["subscriberAlert", "investingClub"]},
        {"contentClassification": ["registeredOnly"]},
        {"contentClassification": "registeredOnly"},
    ],
)
def test_video_native_and_access_limited_assets_are_rejected_before_body(changes):
    asset = _asset("OpenAI releases a new reasoning model", **changes)
    assert cnbc.admission_reason(asset) == ""


@pytest.mark.parametrize(
    "title,description",
    [
        ("Jim Cramer says Nvidia stock is a buy", "The AI chip leader is popular."),
        ("CrowdStrike CEO: AI exposes cyber gaps", "Legacy tools cannot handle them."),
        ("Jensen Huang defends Nvidia's AI investments", "The CEO says risk is low."),
        ("Pa. Gov. Shapiro says data centers don't care", "A survey was released."),
        ("Goldman Sachs partner warns against AI bankers", "AI may weaken reasoning."),
        ("Apple enters John Ternus era as AI challenges intensify", "The iPhone is central."),
        ("UAE official backs a Trump crypto bank", "Its founder once mentioned AI."),
        ("New iPhone adds AI photo recipes", "A consumer device launch."),
    ],
)
def test_stock_chatter_personnel_crypto_and_consumer_noise_is_rejected(title, description):
    assert cnbc.admission_reason(_asset(title, description=description)) == ""


@pytest.mark.parametrize(
    "title,description",
    [
        ("OpenAI releases a new reasoning model", "The frontier model is available today."),
        ("Hugging Face approached Nvidia ahead of acquisition, CEO tells CNBC", "A $12B deal."),
        ("Z.ai shares surge after releasing AI model on Chinese chips", "The model is open."),
        ("Chipmaker earnings rise as it builds $80 billion AI data center capacity", "Construction starts."),
        ("Nvidia says Groq racks will be online this year", "The AI systems follow a purchase."),
    ],
)
def test_concrete_model_and_infrastructure_events_survive_noisy_trailing_context(title, description):
    assert cnbc.admission_reason(_asset(title, description=description))


def test_asset_json_and_rendered_card_parsers_share_the_same_admission_gate():
    payload = {
        "kind": "cnbc-asset-list",
        "assets": [
            _asset("OpenAI releases a new reasoning model", id="one"),
            _asset("Jim Cramer says Nvidia stock is a buy", id="two"),
        ],
    }
    rows = cnbc.parse_search_results(
        json.dumps(payload), cnbc.TOPIC_LABEL, cnbc.hub_url(cnbc.HUBS[0])
    )
    assert [row["article_id"] for row in rows] == ["2026-09-04-example-ai-story"]
    assert rows[0]["admission_reason"] == "ai_article"

    html = """
      <div data-test="Card" class="Card-card">
        <a class="Card-title" href="/2026/09/04/openai-model.html">OpenAI releases model</a>
        <div class="Card-description">A new AI reasoning model.</div>
      </div>
      <div data-test="Card" class="Card-card Card-cnbcvideo">
        <a class="Card-title" href="/video/2026/09/04/openai-clip.html">OpenAI video</a>
      </div>
    """
    rendered = cnbc.parse_search_results(html, cnbc.TOPIC_LABEL)
    assert [row["article_id"] for row in rendered] == ["2026-09-04-openai-model"]


def test_embedded_video_does_not_disqualify_a_substantive_news_body():
    text = "OpenAI released a model for data center operators. " * 25
    result = fetch._body_from_html(
        _article_html(text, embedded_video=True),
        "https://www.cnbc.com/2026/09/04/example-ai-story.html",
        "OpenAI article",
        cnbc,
    )
    assert len(result["body"]) >= cnbc.MIN_BODY_CHARS
    assert result["extractor"] == "站点容器"


def test_hidden_member_text_and_short_pages_cannot_masquerade_as_body():
    hidden = "subscriber-only text " * 100
    html = f"""
      <div class="ArticleBody-articleBody" data-module="ArticleBody">
        <div class="ArticleBody-extraData"><div class="xyz-data"><p>{hidden}</p></div></div>
      </div>
    """
    result = fetch._body_from_html(
        html, "https://www.cnbc.com/2026/09/04/example-ai-story.html", "x", cnbc
    )
    assert result["body"] == ""
    assert result["longest"] == 0


def test_public_direct_fetch_never_asks_for_a_cookie_store(monkeypatch):
    text = "Anthropic released an AI model for data centers. " * 25
    html = _article_html(text)

    def no_cookie(_site):
        raise AssertionError("CNBC must not read the private cookie store")

    monkeypatch.setattr(fetch.cookies, "store_for", no_cookie)
    monkeypatch.setattr(
        fetch,
        "_direct",
        lambda url, cookie: (html, url) if cookie == "" else (_ for _ in ()).throw(AssertionError()),
    )
    result = fetch.fetch_body(
        {"url": "https://www.cnbc.com/2026/09/04/example-ai-story.html", "title_en": "x"},
        site=cnbc,
    )
    assert result["body"]
    assert result["extractor"].startswith("直抓")


def test_cnbc_has_a_public_headless_fallback_without_cookie_mirroring():
    assert tiers.tier_of("cnbc") == tiers.HEADLESS_TIER
    assert contract.site_for_url("https://www.cnbc.com/2026/09/04/x.html") == "cnbc"
    assert "cnbc.com" not in profile._cookie_scope()
    assert "ft.com" in profile._cookie_scope()
    assert cnbc.HUB_TIERS == {"ai-artificial-intelligence": "ai"}
    assert cnbc.REQUIRES_AUTH is False
    assert cnbc.ALLOW_TRAFILATURA is False


def test_cnbc_browser_fallback_uses_plain_headless_not_bpc(monkeypatch):
    import inews.browser as browser

    called: list[str] = []
    monkeypatch.setattr(
        browser._playwright,
        "fetch_public_page_headless",
        lambda url, **_kwargs: (called.append(url) or ("<html>ok</html>", url)),
    )
    monkeypatch.setattr(
        browser._playwright,
        "fetch_paid_page_isolated",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("BPC must not run")),
    )
    url = "https://www.cnbc.com/2026/09/04/example-ai-story.html"
    assert browser.fetch_article(url, site="cnbc") == ("<html>ok</html>", url)
    assert called == [url]
