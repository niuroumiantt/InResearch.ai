"""Reuters B 路线：官方 AI 主河、Load more 与严格文字稿准入。"""
from __future__ import annotations

import json

import pytest

from inews import fetch, ledger as ledger_store, run
from inews.browser import contract
from inews.sites import reuters
from inews.sites.protocol import validate


def _story(title: str, **changes) -> dict[str, object]:
    story: dict[str, object] = {
        "type": "article",
        "url": (
            "https://www.reuters.com/technology/artificial-intelligence/"
            "example-ai-story-2026-09-04/"
        ),
        "title": title,
        "description": "",
        "published_time": "2026-09-04T01:02:03Z",
        "section": {"name": "Artificial Intelligence"},
        "primary_media_type": "text",
    }
    story.update(changes)
    return story


def _body_html(body: str, *, marker: str = "") -> str:
    return f"""
      <html><head>
        <meta property="og:title" content="Reuters AI article">
        {marker}
      </head><body><main><article>
        <div data-testid="ArticleBody">
          <div data-testid="paragraph-0"><p>{body}</p></div>
        </div>
        <section data-testid="RelatedStories"><p>Unrelated recommendation.</p></section>
      </article></main></body></html>
    """


def _summary_supported_listing() -> str:
    """标题给动作、摘要给 AI 基建语境：少任一半都不应准入。"""
    return """
      <html><body><main>
        <section aria-label="Latest stories">
          <li data-testid="StoryCard">
            <a data-testid="TitleLink"
               href="/technology/oracle-expands-cloud-capacity-2026-09-04/">
              <span data-testid="TitleHeading">Oracle expands cloud capacity</span>
            </a>
            <p>The company is building an AI data center and GPU cluster.</p>
            <time data-testid="DateLineText"
                  datetime="2026-09-04T01:02:03Z"></time>
          </li>
        </section>
      </main></body></html>
    """


def test_adapter_contract_and_official_b_route_are_explicit():
    validate(reuters)
    assert reuters.SEARCHABLE is False
    assert reuters.LISTING_FETCHER is None
    assert reuters.HUBS == ("technology/artificial-intelligence",)
    assert reuters.hub_url(reuters.HUBS[0], 1) == (
        "https://www.reuters.com/technology/artificial-intelligence/"
    )
    assert reuters.hub_url(reuters.HUBS[0], 9) == reuters.hub_url(
        reuters.HUBS[0], 1
    )
    assert reuters.LISTING_SCROLLS is True
    assert reuters.LOAD_MORE_TEXT == "load more articles"
    with pytest.raises(RuntimeError, match="Reuters|搜索|search"):
        reuters.search_url("AI", 2)


def test_generic_listing_browser_receives_scroll_and_load_more_declarations(
    monkeypatch,
):
    import inews.browser as browser

    captured: dict[str, object] = {}

    def fake(url: str, **kwargs):
        captured.update(kwargs)
        return "<html></html>", url

    monkeypatch.setattr(browser, "fetch_rendered_listing", fake)
    run._listing_fetcher_for(reuters)(reuters.hub_url(reuters.HUBS[0]))
    assert captured["site"] == "reuters"
    assert captured["link_pattern"] == reuters.LINK_PATTERN
    assert captured["scroll_listing"] is True
    assert captured["load_more_text"] == "load more articles"


def test_reuters_domain_is_already_inside_the_browser_safety_boundary():
    assert contract.site_for_url(
        "https://www.reuters.com/technology/openai-model-2026-09-04/"
    ) == "reuters"
    assert contract.site_for_url(
        "https://reuters.com/business/nvidia-chip-deal-2026-09-04/"
    ) == "reuters"


def test_article_identity_accepts_dated_text_stories_across_real_sections():
    assert reuters.article_id(
        "https://www.reuters.com/technology/artificial-intelligence/"
        "openai-launches-model-2026-09-04/?rpc=401&"
    ) == "2026-09-04-openai-launches-model"
    assert reuters.article_id(
        "https://www.reuters.com/business/media-telecom/"
        "nvidia-signs-ai-cloud-deal-2026-09-03/"
    ) == "2026-09-03-nvidia-signs-ai-cloud-deal"
    assert reuters.article_id(
        "https://www.reuters.com/legal/openai-copyright-case-2026-09-02/"
    ) == "2026-09-02-openai-copyright-case"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.reuters.com/technology/artificial-intelligence/",
        "https://example.com/technology/openai-model-2026-09-04/",
        "https://www.reuters.com/video/watch/openai-model-2026-09-04/",
        "https://www.reuters.com/breakingviews/nvidia-ai-2026-09-04/",
        "https://www.reuters.com/opinion/openai-policy-2026-09-04/",
        "https://www.reuters.com/pictures/ai-data-centers-2026-09-04/",
        "https://www.reuters.com/graphics/ai-chip-supply-2026-09-04/",
        "https://www.reuters.com/plus/ai-cloud-partner-2026-09-04/",
    ],
)
def test_non_articles_and_editorial_paths_never_receive_an_identity(url):
    assert reuters.article_id(url) == ""


def test_rendered_parser_reads_heading_cards_but_not_sidebars_or_read_more_links():
    html = """
      <html><body><main>
        <section aria-label="Latest stories">
          <h2>Latest stories</h2>
          <li data-testid="StoryCard">
            <a data-testid="MediaImageLink" href="/technology/artificial-intelligence/openai-releases-new-reasoning-model-2026-09-04/">
              <img alt="Reuters credit">
            </a>
            <a data-testid="TitleLink" href="/technology/artificial-intelligence/openai-releases-new-reasoning-model-2026-09-04/">
              <span data-testid="TitleHeading">OpenAI releases new reasoning model</span>
            </a>
            <p>The frontier AI model is available to developers today.</p>
            <time data-testid="DateLineText" datetime="2026-09-04T01:02:03Z"></time>
            <a href="/technology/artificial-intelligence/openai-releases-new-reasoning-model-2026-09-04/">Read more</a>
          </li>
          <li data-testid="StoryCard">
            <a data-testid="TitleLink" href="/technology/nvidia-shares-surge-ai-demand-2026-09-03/">
              <span data-testid="TitleHeading">Nvidia shares surge on AI demand</span>
            </a>
            <p>Investors sent the stock higher.</p>
          </li>
        </section>
        <section aria-label="Most Read">
          <h2>Most Read</h2>
          <li data-testid="StoryCard">
            <a data-testid="TitleLink" href="/technology/anthropic-launches-agent-2026-09-02/">
              <span data-testid="TitleHeading">Anthropic launches a new AI agent</span>
            </a>
          </li>
        </section>
        <aside>
          <li data-testid="StoryCard">
            <a data-testid="TitleLink" href="/technology/google-builds-ai-data-center-2026-09-01/">
              <span data-testid="TitleHeading">Google builds an AI data center</span>
            </a>
          </li>
        </aside>
      </main></body></html>
    """
    rows = reuters.parse_search_results(
        html, reuters.TOPIC_LABEL, reuters.hub_url(reuters.HUBS[0])
    )
    assert [row["article_id"] for row in rows] == [
        "2026-09-04-openai-releases-new-reasoning-model"
    ]
    assert rows[0]["published_at"] == "2026-09-04T01:02:03Z"
    assert rows[0]["admission_reason"] == "ai_article"


def test_structured_mobile_capture_reads_only_story_blocks_and_deduplicates():
    accepted = _story("OpenAI releases a new reasoning model")
    duplicate = {**accepted, "url": str(accepted["url"]) + "?rpc=401#top"}
    sidebar = _story(
        "Anthropic launches a new AI agent",
        url=(
            "https://www.reuters.com/technology/"
            "anthropic-launches-agent-2026-09-03/"
        ),
    )
    payload = [
        {"type": "story-cluster", "data": {"stories": [accepted, duplicate]}},
        {"type": "most-read", "data": {"stories": [sidebar]}},
    ]
    rows = reuters.parse_search_results(
        json.dumps(payload), reuters.TOPIC_LABEL, reuters.hub_url(reuters.HUBS[0])
    )
    assert len(rows) == 1
    assert rows[0]["article_id"] == "2026-09-04-example-ai-story"
    assert "?" not in rows[0]["url"] and "#" not in rows[0]["url"]


def test_parser_keeps_summary_evidence_when_admitted_rows_rechecks_it():
    rows = reuters.parse_search_results(
        _summary_supported_listing(),
        reuters.TOPIC_LABEL,
        reuters.hub_url(reuters.HUBS[0]),
    )
    assert rows[0]["description"] == (
        "The company is building an AI data center and GPU cluster."
    )
    assert reuters.admitted_rows(rows) == rows


def test_summary_evidence_survives_ledger_record_restore_and_recheck():
    rows = reuters.parse_search_results(
        _summary_supported_listing(),
        reuters.TOPIC_LABEL,
        reuters.hub_url(reuters.HUBS[0]),
    )
    rows[0]["body"] = "正文已取到"
    entries: dict[str, dict] = {}
    ledger_store.record(entries, rows, crawled_at="2026-09-04T02:00:00Z")

    restored = ledger_store.rows(entries)
    assert restored[0]["description"] == rows[0]["description"]
    assert reuters.admitted_rows(restored) == restored


@pytest.mark.parametrize(
    "html",
    [
        "<html><body>Please enable JS and disable any ad blocker</body></html>",
        "<html><body><main><h1>Artificial Intelligence</h1></main></body></html>",
        "<html><body><h1>Artificial Intelligence</h1></body></html>",
        "not-json",
    ],
)
def test_antibot_and_structure_changes_fail_closed_instead_of_reporting_zero(html):
    with pytest.raises(RuntimeError, match="Reuters|DataDome|主河|结构|标题链接"):
        reuters.parse_search_results(
            html, reuters.TOPIC_LABEL, reuters.hub_url(reuters.HUBS[0])
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"type": "video"},
        {"primary_media_type": "video"},
        {"isVideo": True},
        {"is_vertical_video_content": True},
        {"is_live_content": True},
        {"isSponsored": True},
        {"section": {"name": "Breakingviews"}},
        {"badges": [{"label": "AI Weekly"}]},
        {"section": "Reuters Events"},
    ],
)
def test_video_weekly_events_opinion_and_sponsored_assets_are_rejected(changes):
    assert reuters.admission_reason(
        _story("OpenAI releases a new reasoning model", **changes)
    ) == ""


@pytest.mark.parametrize(
    "title,description",
    [
        ("Nvidia shares surge as investors cheer AI demand", "The stock rallied."),
        ("AI startup reaches $50 billion valuation", "Investors funded the round."),
        ("Fed officials say AI may reshape the inflation outlook", "Rates may fall."),
        ("OpenAI CEO says artificial intelligence will transform humanity", "An interview."),
        ("Reuters NEXT: CEOs debate the future of AI", "A conference discussion."),
        ("AI Weekly: Five stories you need to know", "A newsletter roundup."),
        ("Meta names new chief executive for its AI division", "A personnel move."),
        ("Cook hands Apple to Ternus: bigger, but catching up in AI race", "A succession story."),
        ("New AI-powered dating app reaches consumers", "A lifestyle product."),
        ("UK retailer harnesses an AI shopping agent", "Consumers can buy products."),
        ("Bitcoin miners embrace AI trading tokens", "Crypto prices rose."),
        ("Election campaigns turn to generative AI advertising", "Candidates made videos."),
        ("Bull or bear market? AI spurs rethink of traditional market measures", "Investors debated equities."),
        ("Dell again lifts annual forecasts as AI demand powers record results", "The company reported earnings."),
        ("Factory activity bounced as AI fuelled Asian expansion", "A regional economic indicator rose."),
        ("South Korea proposes record budget to supercharge AI investment", "Government spending plans were published."),
        ("OpenAI's ad business hits $1 billion annualized revenue run rate", "Advertising revenue increased."),
        ("At Jackson Hole, central bankers glimpse dystopian AI future", "Officials discussed macroeconomic risks."),
        ("AI-driven cyber risk is top concern for global financial stability", "A watchdog issued its view."),
        ("As AI agents go rogue, cyber insurers adapt their policies", "Insurance firms changed coverage."),
        ("Workday reports revenue rise and flags strong AI uptake", "The HR software firm reported results."),
        ("Nvidia pauses revenue-sharing deals with AI cloud companies", "The financing terms changed."),
        ("Synopsys raises annual forecasts on AI chip design demand", "The software maker reported earnings."),
        ("Salesforce raises annual forecasts and expands Anthropic partnership", "Quarterly guidance rose."),
        ("Adobe offers free access to AI tools in a multibillion-dollar deal", "A consumer distribution program."),
        ("The AI founders who walked away to model the universe", "A profile of former executives."),
    ],
)
def test_market_macro_chatter_personnel_and_peripheral_noise_is_rejected(
    title, description
):
    assert reuters.admission_reason(_story(title, description=description)) == ""


@pytest.mark.parametrize(
    "title,description,reason",
    [
        (
            "OpenAI releases a new reasoning model",
            "The frontier model supports open-weight deployment.",
            "ai_article",
        ),
        (
            "Nvidia launches new AI chips for model inference",
            "The accelerators ship this month.",
            "core_infrastructure",
        ),
        (
            "SK Hynix expands HBM production to ease AI memory shortage",
            "New capacity enters production this year.",
            "core_infrastructure",
        ),
        (
            "Amazon builds AI data center with liquid cooling",
            "The new server racks use a faster network.",
            "core_infrastructure",
        ),
        (
            "EU adopts stricter rules for frontier AI models",
            "The law takes effect next year.",
            "ai_article",
        ),
        (
            "Nvidia CEO says new Blackwell GPUs will ship in May",
            "The AI accelerators enter production this quarter.",
            "core_infrastructure",
        ),
        (
            "Photonics startup raises funds to build AI interconnect factory",
            "Production of optical links expands next year.",
            "core_infrastructure",
        ),
    ],
)
def test_concrete_model_and_infrastructure_events_are_admitted(
    title, description, reason
):
    assert reuters.admission_reason(
        _story(title, description=description)
    ) == reason


def test_invalid_listing_time_falls_back_to_the_date_in_the_article_path():
    payload = {
        "result": {
            "articles": [
                _story(
                    "Anthropic launches a new AI agent standard",
                    published_time="three hours ago",
                )
            ]
        }
    }
    rows = reuters.parse_search_results(json.dumps(payload), reuters.TOPIC_LABEL)
    assert rows[0]["published_at"] == "2026-09-04"


def test_long_text_article_body_passes_exact_container_and_short_video_teaser_does_not():
    body = (
        "Reuters reports that the AI data center supply chain expanded production "
        "of servers, memory and networking equipment this quarter. "
    ) * 18
    result = fetch._body_from_html(
        _body_html(body),
        "https://www.reuters.com/technology/openai-model-2026-09-04/",
        "Reuters AI article",
        reuters,
    )
    assert len(result["body"]) >= reuters.MIN_BODY_CHARS
    assert result["most_words"] >= reuters.MIN_BODY_WORDS
    assert result["extractor"] == "站点容器"

    teaser = "Watch the latest Reuters video about artificial intelligence. " * 5
    short = fetch._body_from_html(
        _body_html(teaser),
        "https://www.reuters.com/technology/openai-video-2026-09-04/",
        "Reuters AI video",
        reuters,
    )
    assert short["body"] == ""


def test_embedded_video_does_not_disqualify_a_substantive_text_story():
    body = "A new AI model uses data center GPUs and high-bandwidth memory. " * 35
    html = _body_html(body).replace(
        '<div data-testid="ArticleBody">',
        '<video controls></video><div data-testid="ArticleBody">',
    )
    result = fetch._body_from_html(
        html,
        "https://www.reuters.com/technology/openai-model-2026-09-04/",
        "Reuters AI article",
        reuters,
    )
    assert result["body"]


def test_datadome_marker_cannot_masquerade_as_a_long_body():
    body = "Artificial intelligence infrastructure text from a challenge page. " * 40
    html = _body_html(
        body,
        marker='<script src="https://ct.captcha-delivery.com/i.js">DataDome</script>',
    )
    result = fetch._body_from_html(
        html,
        "https://www.reuters.com/technology/openai-model-2026-09-04/",
        "Reuters AI article",
        reuters,
    )
    assert result["body"] == ""
    assert result["raw_html_marker"] is True


def test_stored_rows_are_filtered_again_with_the_same_admission_policy():
    good = {
        "url": "https://www.reuters.com/technology/openai-model-2026-09-04/",
        "title_en": "OpenAI releases a new reasoning model",
        "section": "Artificial Intelligence",
    }
    noisy = {
        "url": "https://www.reuters.com/technology/nvidia-stock-2026-09-04/",
        "title_en": "Nvidia shares surge as investors cheer AI demand",
        "section": "Artificial Intelligence",
    }
    assert reuters.admitted_rows([good, noisy]) == [good]
