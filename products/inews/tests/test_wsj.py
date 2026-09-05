"""WSJ B 路线：只读官方 AI 真分页，先结构性剔除污染再抓付费正文。"""
from __future__ import annotations

import json

import pytest

from inews import cookies, fetch, sites
from inews.browser import contract, profile, tiers
from inews.sites import bloomberg, cnbc, ft, wsj


def _article(
    title: str,
    *,
    identifier: str = "f12622f1",
    summary: str = "",
    path: str = "tech/ai",
    **extra,
) -> dict[str, object]:
    row: dict[str, object] = {
        "type": "article",
        "articleUrl": (
            f"https://www.wsj.com/{path}/"
            f"example-ai-story-{identifier}?mod=ai_more_article_pos1"
        ),
        "headline": title,
        "summary": summary,
        "timestamp": "2026-09-04T01:02:03Z",
        "isVideo": False,
        "isOpinion": False,
    }
    row.update(extra)
    return row


def _next_data(
    articles: list[dict[str, object]],
    *,
    page: int = 1,
    page_props: dict[str, object] | None = None,
    props: dict[str, object] | None = None,
) -> str:
    actual_page_props: dict[str, object] = {
        "pageNumber": page,
        "lastPage": 20,
        "moreInArticles": articles,
        **(page_props or {}),
    }
    payload = {
        "props": {
            "pageProps": actual_page_props,
            **(props or {}),
        }
    }
    return (
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script>"
    )


def _body_html(
    body: str,
    *,
    declared_words: int | None = None,
    declared_by: str = "property",
) -> str:
    if declared_words is None:
        count_meta = ""
    elif declared_by == "name":
        count_meta = (
            '<meta name="cXenseParse:wsj-word-count" '
            f'content="{declared_words}">'
        )
    else:
        count_meta = (
            '<meta property="article:word_count" '
            f'content="{declared_words}">'
        )
    return f"""
    <html><head>
      <meta property="og:title" content="WSJ AI article">
      {count_meta}
    </head><body>
      <article>
        <div class="crawler">
          <section><p data-type="paragraph">{body}</p></section>
        </div>
      </article>
      <section aria-label="Videos"><p>Embedded video recommendations.</p></section>
      <section aria-label="Further Reading"><p>Unrelated recommendations.</p></section>
    </body></html>
    """


def test_registry_and_official_hub_use_real_ai_pagination():
    assert sites.get("wsj") is wsj
    assert wsj.HUBS == ("tech/ai",)
    assert wsj.hub_url("tech/ai", 1) == "https://www.wsj.com/tech/ai?page=1"
    assert wsj.hub_url("tech/ai", 2) == "https://www.wsj.com/tech/ai?page=2"
    assert wsj.hub_url("tech/ai", 20) == "https://www.wsj.com/tech/ai?page=20"
    assert wsj.LOAD_MORE_TEXT == ""
    assert wsj.LISTING_SCROLLS is False
    assert wsj.HUB_TIERS == {"tech/ai": "ai"}
    with pytest.raises(RuntimeError, match="WSJ|search|搜索"):
        wsj.search_url("AI", 1)


def test_parser_reads_only_next_data_more_in_articles_not_visible_or_sidebar_links():
    main = _article(
        "OpenAI releases a new reasoning model",
        identifier="11111111",
        summary="The frontier model is available this week.",
    )
    sidebar = _article(
        "Anthropic signs a $35 billion AI cloud deal",
        identifier="22222222",
        summary="Nvidia will supply chips to a Texas data center.",
    )
    next_data = _next_data(
        [main],
        page=2,
        page_props={
            "mostPopularArticles": [sidebar],
            "relatedOpinion": [sidebar],
            "whatsNews": [sidebar],
            "advertisements": [sidebar],
        },
        props={"anotherArticleArray": [sidebar]},
    )
    html = f"""
      <main><a href="{sidebar['articleUrl']}">A visible but untrusted card</a></main>
      <aside data-module="most-popular">
        <a href="{sidebar['articleUrl']}">Most Popular in Technology</a>
      </aside>
      {next_data}
    """
    rows = wsj.parse_search_results(html, wsj.TOPIC_LABEL, wsj.hub_url("tech/ai", 2))
    assert [row["article_id"] for row in rows] == ["11111111"]


@pytest.mark.parametrize(
    "page_props,page_url",
    [
        (
            {"pageNumber": 1, "lastPage": 20, "moreInArticles": []},
            "https://www.wsj.com/tech/ai?page=2",
        ),
        ({"lastPage": 20, "moreInArticles": []}, "https://www.wsj.com/tech/ai?page=1"),
        ({"pageNumber": 1, "lastPage": 20}, "https://www.wsj.com/tech/ai?page=1"),
    ],
)
def test_missing_or_mismatched_next_data_contract_fails_closed(page_props, page_url):
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps({"props": {"pageProps": page_props}})
        + "</script>"
    )
    with pytest.raises(
        RuntimeError,
        match="pageNumber|moreInArticles|页码|列表|请求第.*返回第",
    ):
        wsj.parse_search_results(html, wsj.TOPIC_LABEL, page_url)


def test_antibot_or_malformed_page_never_masquerades_as_an_empty_news_day():
    for html in (
        "<html><body>Please enable JS and disable any ad blocker</body></html>",
        '<script id="__NEXT_DATA__" type="application/json">not-json</script>',
        "<html><body><h1>Artificial Intelligence</h1></body></html>",
    ):
        with pytest.raises(RuntimeError, match="NEXT_DATA|WSJ|列表|解析"):
            wsj.parse_search_results(
                html, wsj.TOPIC_LABEL, wsj.hub_url("tech/ai", 1)
            )


@pytest.mark.parametrize(
    "changes",
    [
        {"type": "ad"},
        {"type": "collection"},
        {"type": "video"},
        {"isVideo": True},
        {"isOpinion": True},
        {
            "articleUrl": (
                "https://www.wsj.com/video/openai-model-demo-33333333"
            )
        },
        {
            "articleUrl": (
                "https://www.wsj.com/opinion/openai-model-policy-44444444"
            )
        },
    ],
)
def test_non_articles_ads_video_and_opinion_are_rejected_before_body(changes):
    item = _article(
        "OpenAI releases a new reasoning model",
        identifier="33333333",
        summary="The frontier model is available this week.",
        **changes,
    )
    html = _next_data([item], page=1)
    assert wsj.parse_search_results(
        html, wsj.TOPIC_LABEL, wsj.hub_url("tech/ai", 1)
    ) == []


def test_an_article_with_an_embedded_video_field_remains_a_text_article():
    item = _article(
        "OpenAI releases a new reasoning model",
        identifier="55555555",
        summary="The frontier model is available this week.",
        video={"id": "embedded-clip", "duration": 42},
    )
    rows = wsj.parse_search_results(
        _next_data([item]), wsj.TOPIC_LABEL, wsj.hub_url("tech/ai", 1)
    )
    assert [row["article_id"] for row in rows] == ["55555555"]


def test_article_identity_accepts_real_sections_but_not_foreign_or_media_pages():
    assert wsj.article_id(
        "https://www.wsj.com/tech/ai/anthropic-cloud-deal-f12622f1?mod=ai_lead"
    ) == "f12622f1"
    assert wsj.article_id(
        "https://www.wsj.com/tech/openai-lawsuit-c0d34f44"
    ) == "c0d34f44"
    assert wsj.article_id(
        "https://www.wsj.com/cio-journal/new-ai-models-937bb2aa"
    ) == "937bb2aa"
    assert wsj.article_id("https://www.wsj.com/tech/ai") == ""
    assert wsj.article_id("https://example.com/tech/ai/story-f12622f1") == ""
    assert wsj.article_id("https://www.wsj.com/video/story-f12622f1") == ""
    assert wsj.article_id("https://www.wsj.com/opinion/story-f12622f1") == ""


def test_rows_deduplicate_by_stable_id_and_keep_timestamp_and_canonical_url():
    first = _article(
        "Anthropic signs a $35 billion AI cloud deal backed by Nvidia",
        identifier="f12622f1",
        summary="Nvidia will supply chips to a Texas data center.",
    )
    duplicate = {
        **first,
        "articleUrl": str(first["articleUrl"]).replace("pos1", "pos9") + "#comments",
    }
    rows = wsj.parse_search_results(
        _next_data([first, duplicate], page=3),
        wsj.TOPIC_LABEL,
        wsj.hub_url("tech/ai", 3),
    )
    assert len(rows) == 1
    assert rows[0]["article_id"] == "f12622f1"
    assert rows[0]["published_at"] == "2026-09-04T01:02:03Z"
    assert rows[0]["url"].endswith("example-ai-story-f12622f1")
    assert "?" not in rows[0]["url"] and "#" not in rows[0]["url"]
    assert rows[0]["keywords"] == [wsj.TOPIC_LABEL]


@pytest.mark.parametrize(
    "title,summary",
    [
        (
            "Nvidia Agrees to Buy AI Platform Hugging Face for $13 Billion",
            "The deal promotes open-weight AI models and model infrastructure.",
        ),
        (
            "New Google AI Model Said to Narrow Gap on Coding Ability",
            "Gemini 3.8 Flash is scheduled for release this week.",
        ),
        (
            "OpenAI to Restrict Astra Model After Rating It 'Critical' Cyber Risk",
            "Added safeguards follow tests of the frontier model's capabilities.",
        ),
        (
            "See the New Building Techniques Turbocharging the Data-Center Boom",
            "Hyperscalers are adopting faster construction products and techniques.",
        ),
        (
            "Anthropic Signs $35 Billion Cloud Deal Backed by Nvidia",
            "Nvidia will supply chips to a Texas data center and hold the lease.",
        ),
        (
            "Nvidia to Invest $2 Billion in Both Lumentum and Coherent",
            "The agreements accelerate advanced optics for AI infrastructure.",
        ),
        (
            "Amazon Pledges $40 Billion to Expand AI Data-Center Infrastructure",
            "The company will add data-center capacity in Spain.",
        ),
        (
            "Startup Making AI Chips More Power-Efficient Raises $500 Million",
            "Ayar Labs replaces copper interconnects with fiber optics.",
        ),
        (
            "Why Big Tech's AI Spending Is $3 Trillion Higher Than It Seems",
            "Data-center leases and chip commitments sit off balance sheets.",
        ),
        (
            "Hyperscalers' Off-Grid Power Push Comes With Risks",
            "Data centers' huge fluctuating power demand is testing power systems.",
        ),
        (
            "U.S. Government Backs OpenAI in Copyright Fight With Publishers",
            "The Justice Department filed a statement in the pending court case.",
        ),
        (
            "EU Subjects ChatGPT to Stricter Digital Services Act Scrutiny",
            "The Commission formally designated ChatGPT under the DSA.",
        ),
        (
            "Chipmaker shares rise as it builds $80 billion AI data-center capacity",
            "Construction starts this year and includes new GPU racks.",
        ),
    ],
)
def test_core_ai_model_and_infrastructure_items_are_admitted(title, summary):
    assert wsj.admission_reason(_article(title, summary=summary))


@pytest.mark.parametrize(
    "title,summary",
    [
        (
            "Soitec Shares Jump After Guidance Upgrade on Strong AI Demand",
            "The stock rose after a quarterly revenue forecast.",
        ),
        (
            "China's Moonshot AI Confidentially Files for Hong Kong IPO",
            "The listing documents do not describe a new model or compute project.",
        ),
        (
            "AI Startup Wonderful Hits $5 Billion Valuation",
            "The company plans to expand its workforce to 1,000 people.",
        ),
        (
            "OpenAI's Head of Data Centers Has Left the Company",
            "The executive joins a string of high-level departures.",
        ),
        (
            "Adobe Names Anil Chakravarthy as Chief Executive Amid AI Transformation",
            "The software company is changing leaders while adopting AI tools.",
        ),
        (
            "Apple to Give New CEO $3 Million Salary",
            "The executive will also receive an annual stock award.",
        ),
        (
            "Tech CEOs Ask G-20 to Adopt Pro-AI Policies",
            "Executives said and argued that governments should regulate less.",
        ),
        (
            "What CEOs Can Learn From the AI Backlash",
            "An opinion column offers management advice.",
        ),
        (
            "The AI Boom May Resemble Social Media More Than Telecom",
            "A columnist considers two competing analogies.",
        ),
        (
            "Tech, Media & Telecom Roundup: Market Talk",
            "Find insight on Nvidia and Broadcom in the latest Market Talks.",
        ),
        (
            "Nvidia and CrowdStrike Develop New Cybersecurity AI Models",
            "Plus, models from Anthropic, Google and World Labs in the Morning Download.",
        ),
        (
            "Can Evan Spiegel Sell the World on $2,195 Smart Glasses?",
            "Snap is doubling down on a consumer hardware play.",
        ),
        (
            "When AI Is Your Second Teacher",
            "Families describe using a chatbot for homework help.",
        ),
        (
            "Nothing Makes Humans Happier Than Watching Robots Fail",
            "The videos deliver physical comedy and entertainment.",
        ),
        (
            "I Let Google's Personal Intelligence Access My Life",
            "A first-person review of a consumer AI assistant.",
        ),
        (
            "Should You Use AI for Mental Health?",
            "A podcast producer discusses consumer therapy chatbots.",
        ),
        (
            "Fervo Secures Its Largest-Ever Geothermal Power Deal With Google",
            "The company counts Bill Gates as a backer and recently held an IPO.",
        ),
    ],
)
def test_stock_personnel_chatter_newsletters_and_consumer_edges_are_rejected(
    title, summary
):
    assert wsj.admission_reason(_article(title, summary=summary)) == ""


def test_body_requires_both_the_character_floor_and_150_words():
    assert wsj.MIN_BODY_CHARS >= 900
    assert wsj.MIN_BODY_WORDS == 150

    many_short_tokens = "a " * 200
    short_by_characters = fetch._body_from_html(
        _body_html(many_short_tokens, declared_words=200),
        "https://www.wsj.com/tech/ai/story-11111111",
        "WSJ AI article",
        wsj,
    )
    assert short_by_characters["body"] == ""

    teaser = "infrastructure " * 149
    short_by_words = fetch._body_from_html(
        _body_html(teaser, declared_words=149),
        "https://www.wsj.com/tech/ai/story-22222222",
        "WSJ AI article",
        wsj,
    )
    assert len(teaser) >= wsj.MIN_BODY_CHARS
    assert short_by_words["body"] == ""
    assert short_by_words["longest"] >= wsj.MIN_BODY_CHARS


@pytest.mark.parametrize("declared_by", ["property", "name"])
def test_body_must_cover_at_least_70_percent_of_wsjs_declared_word_count(declared_by):
    assert wsj.MIN_BODY_COVERAGE == pytest.approx(0.70)
    url = "https://www.wsj.com/tech/ai/story-33333333"

    teaser = "infrastructure " * 180
    incomplete = fetch._body_from_html(
        _body_html(teaser, declared_words=300, declared_by=declared_by),
        url,
        "WSJ AI article",
        wsj,
    )
    assert incomplete["body"] == ""

    complete = "infrastructure " * 210
    accepted = fetch._body_from_html(
        _body_html(complete, declared_words=300, declared_by=declared_by),
        url,
        "WSJ AI article",
        wsj,
    )
    assert accepted["body"]
    assert accepted["extractor"] == "站点容器"


def test_missing_declared_word_count_falls_back_to_absolute_body_floors():
    complete = "infrastructure " * 170
    result = fetch._body_from_html(
        _body_html(complete),
        "https://www.wsj.com/tech/ai/story-44444444",
        "WSJ AI article",
        wsj,
    )
    assert result["body"]


@pytest.mark.parametrize(
    "words,declared_words,accepted",
    [
        (210, 300, False),
        (607, 625, True),
    ],
)
def test_raw_paywall_marker_uses_the_strict_recovery_gate(
    words, declared_words, accepted
):
    assert wsj.RAW_HTML_REJECT_PATTERNS == (
        r"\bPaywalledContentContainer\b",
    )
    assert contract.RAW_HTML_RECOVERY_COVERAGE == pytest.approx(0.90)
    html = _body_html(
        "infrastructure " * words,
        declared_words=declared_words,
    ).replace(
        "<article>",
        '<div class="PaywalledContentContainer"></div><article>',
    )
    result = fetch._body_from_html(
        html,
        "https://www.wsj.com/tech/ai/story-55555555",
        "WSJ AI article",
        wsj,
    )
    assert bool(result["body"]) is accepted
    assert result["declared_words"] == declared_words
    assert result["raw_html_marker"] is True
    assert result["most_words"] == words


def test_raw_paywall_marker_without_a_declared_word_count_is_not_proven_restored():
    html = _body_html("infrastructure " * 607).replace(
        "<article>",
        '<div class="PaywalledContentContainer"></div><article>',
    )
    result = fetch._body_from_html(
        html,
        "https://www.wsj.com/tech/ai/story-56565656",
        "WSJ AI article",
        wsj,
    )
    assert result["body"] == ""
    assert result["declared_words"] == 0
    assert result["raw_html_marker"] is True


def test_direct_failure_diagnostic_prints_declared_words_and_raw_marker():
    reason = fetch._short_body_reason(
        "<html></html>",
        3100,
        210,
        300,
        True,
        "https://www.cnbc.com/2026/09/04/example.html",
        cnbc,
    )
    assert "declared=300" in reason
    assert "rawMarker=true" in reason


def test_fetch_body_passes_the_site_raw_html_gate_to_the_browser(monkeypatch):
    captured: dict[str, object] = {}
    html = _body_html("infrastructure " * 170, declared_words=170)
    url = "https://www.wsj.com/tech/ai/story-66666666"

    class EmptyCookieStore:
        domain = "wsj.com"

        @staticmethod
        def header():
            return ""

        @staticmethod
        def status():
            return {"ok": True, "note": "browser session"}

    def browser_fetch(requested_url: str, **kwargs):
        captured.update(kwargs)
        return html, requested_url

    monkeypatch.setattr(fetch.cookies, "store_for", lambda _key: EmptyCookieStore())
    monkeypatch.setattr(fetch, "fetch_article", browser_fetch)
    result = fetch.fetch_body({"url": url, "title_en": "WSJ AI article"}, site=wsj)
    assert result["body"]
    assert captured["reject_patterns"] == wsj.RAW_HTML_REJECT_PATTERNS


def test_daily_chrome_tests_raw_reject_patterns_against_the_full_page_html(
    monkeypatch,
):
    from inews.browser import daily_chrome

    captured: dict[str, object] = {}

    def fake_run(url: str, **kwargs):
        captured.update(kwargs)
        return "<html></html>", url

    monkeypatch.setattr(daily_chrome, "run_with_daily_chrome", fake_run)
    daily_chrome.fetch_page(
        "https://www.wsj.com/tech/ai/story-77777777",
        min_chars=wsj.MIN_BODY_CHARS,
        min_words=wsj.MIN_BODY_WORDS,
        min_coverage=wsj.MIN_BODY_COVERAGE,
        timeout_seconds=15,
        selectors=wsj.BODY_SELECTORS,
        paragraph_selectors=wsj.BODY_PARAGRAPH_SELECTORS,
        reject_patterns=wsj.RAW_HTML_REJECT_PATTERNS,
    )
    script = str(captured["check_script"])
    assert "document.documentElement?.outerHTML" in script
    assert "new RegExp(p,'is').test(pageHtml)" in script
    assert "new RegExp(p,'is').test(best)" not in script
    assert (
        "const markerRecovered=rawMarker&&declaredWords>0&&"
        "words.length>=declaredWords*0.9"
    ) in script
    assert "const enoughCoverage=rawMarker?markerRecovered" in script
    assert "declared='+declaredWords+',rawMarker='+rawMarker" in script


@pytest.mark.parametrize(
    "words,declared_words,accepted",
    [
        (210, 300, False),
        (607, 625, True),
    ],
)
def test_playwright_uses_the_same_strict_marker_recovery_gate(
    words, declared_words, accepted
):
    from inews.browser.playwright import BrowserWorker

    body = "infrastructure " * words

    class Locator:
        def __init__(self, *, content="", parts=()):
            self.content = content
            self.parts = tuple(parts)

        @property
        def first(self):
            return self

        def count(self):
            return len(self.parts) or bool(self.content)

        def get_attribute(self, _name, timeout=0):
            return self.content

        def locator(self, _selector):
            return Locator(parts=self.parts)

        def all_inner_texts(self):
            return list(self.parts)

        def inner_text(self, timeout=0):
            return "\n\n".join(self.parts)

    class MarkedPage:
        url = "https://www.wsj.com/tech/ai/story-88888888"

        @staticmethod
        def content():
            return (
                '<html><aside class="PaywalledContentContainer"></aside>'
                "<article><div class='crawler'><section>"
                f"<p data-type='paragraph'>{body}</p>"
                "</section></div></article></html>"
            )

        @staticmethod
        def locator(selector):
            if selector == "meta[property='article:word_count']":
                return Locator(content=str(declared_words))
            if selector == wsj.BODY_SELECTORS[0]:
                return Locator(parts=(body,))
            return Locator()

    diagnostic: dict[str, object] = {}
    result = BrowserWorker._article_html(
        MarkedPage(),
        wsj.MIN_BODY_CHARS,
        wsj.MIN_BODY_WORDS,
        wsj.MIN_BODY_COVERAGE,
        wsj.BODY_SELECTORS,
        wsj.BODY_PARAGRAPH_SELECTORS,
        wsj.RAW_HTML_REJECT_PATTERNS,
        diagnostic,
    )
    assert bool(result) is accepted
    assert diagnostic == {
        "chars": len(body.strip()),
        "words": words,
        "declared": declared_words,
        "raw_marker": True,
    }


def test_playwright_diagnostic_prints_declared_words_and_raw_marker():
    from inews.browser.playwright import BrowserWorker

    class EmptyLocator:
        @property
        def first(self):
            return self

        @staticmethod
        def count():
            return 0

    class Page:
        @staticmethod
        def title():
            return "WSJ AI article"

        @staticmethod
        def locator(_selector):
            return EmptyLocator()

    diagnostic = BrowserWorker._diagnostic(
        Page(),
        "HTTP 200",
        {"chars": 3100, "words": 210, "declared": 300, "raw_marker": True},
    )
    assert "declared=300" in diagnostic
    assert "rawMarker=true" in diagnostic


def test_existing_sites_keep_their_empty_raw_html_gate_defaults():
    assert ft.RAW_HTML_REJECT_PATTERNS == ()
    assert bloomberg.RAW_HTML_REJECT_PATTERNS == ()
    assert cnbc.RAW_HTML_REJECT_PATTERNS == ()


def test_wsj_uses_its_subscription_cookie_and_the_explicit_manual_tier():
    assert cookies.store_for("wsj") is cookies.WSJ
    assert cookies.WSJ.domain == "wsj.com"
    assert cookies.STORES["wsj"] is cookies.WSJ
    assert wsj.REQUIRES_AUTH is True
    assert wsj.ALLOW_TRAFILATURA is False
    assert tiers.tier_of("wsj") == tiers.MANUAL_TIER
    assert contract.site_for_url(
        "https://www.wsj.com/tech/ai/openai-model-f12622f1"
    ) == "wsj"
    assert "wsj.com" in profile._cookie_scope()
