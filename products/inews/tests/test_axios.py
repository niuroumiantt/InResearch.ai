"""Axios 固定 Latest 搜索页与 Smart Brevity 正文契约。"""
from __future__ import annotations

import pytest

from inews import fetch, ledger as ledger_store, run
from inews.sites import axios
from inews.sites.protocol import validate


def _card(
    title: str,
    slug: str,
    *,
    summary: str = "",
    section: str = "Technology",
    content_type: str = "",
    date: str = "2026-09-04T01:02:03Z",
) -> str:
    badge = f'<span data-testid="format">{content_type}</span>' if content_type else ""
    return f"""
      <article data-testid="search-result-card">
        <span class="eyebrow">{section}</span>{badge}
        <time datetime="{date}">{date}</time>
        <h2><a href="/2026/09/04/{slug}">{title}</a></h2>
        <p>{summary}</p>
      </article>
    """


def _listing(*cards: str, outside: str = "") -> str:
    return f"""
      <html><head><title>Search results | Axios</title></head><body>
        {outside}
        <main>{''.join(cards)}<button>Show 10 more results</button></main>
      </body></html>
    """


def _item(title: str, *, summary: str = "", **extra: str) -> dict[str, str]:
    item = {
        "title": title,
        "summary": summary,
        "url": "https://www.axios.com/2026/09/04/example-story",
        "section": "Technology",
    }
    item.update(extra)
    return item


def _body_html(body: str, *, before: str = "") -> str:
    return f"""
      <html><body>
        <main>
          <p>{before}</p>
          <div class="gtmView" data-vars-page-type="story">
            <div><div><p>Unrelated first child.</p></div></div>
            <div>
              <div data-chromatic="ignore">
                <p>{body}</p>
              </div>
            </div>
          </div>
        </main>
      </body></html>
    """


def test_adapter_protocol_and_fixed_latest_entry_are_explicit():
    validate(axios)
    assert axios.SEARCHABLE is False
    assert axios.LISTING_FETCHER is None
    assert axios.HUBS == ("artificial-intelligence-latest",)
    assert axios.hub_url(axios.HUBS[0], 99) == (
        "https://www.axios.com/results?q=artificial%20intelligence&sort=2"
    )
    assert axios.LOAD_MORE_TEXT == "show 10 more results"
    assert axios.LISTING_SCROLLS is False
    assert axios.HUB_TIERS == {axios.HUBS[0]: "trusted"}
    with pytest.raises(RuntimeError, match="固定|Latest"):
        axios.search_url("GPU", 1)


def test_shared_browser_receives_the_show_more_contract(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake(url: str, **kwargs: object) -> tuple[str, str]:
        calls.append({"url": url, **kwargs})
        return "<html></html>", url

    monkeypatch.setattr("inews.browser.fetch_rendered_listing", fake)
    listing_fetcher = run._listing_fetcher_for(axios)
    listing_fetcher(axios.LATEST_AI_URL)
    assert calls == [
        {
            "url": axios.LATEST_AI_URL,
            "site": "axios",
            "link_pattern": axios.LINK_PATTERN,
            "scroll_listing": False,
            "load_more_text": "show 10 more results",
        }
    ]


def test_article_identity_is_limited_to_national_text_story_paths():
    assert axios.article_id(
        "https://www.axios.com/2026/09/04/openai-new-model?utm_source=x#top"
    ) == "2026-09-04-openai-new-model"
    assert axios.article_id("https://axios.com/2026/09/04/AI%20chips") == (
        "2026-09-04-ai-chips"
    )
    assert axios.article_id(
        "https://www.axios.com/local/austin/2026/09/04/ai-schools"
    ) == ""
    assert axios.article_id("https://www.axios.com/newsletters/axios-ai") == ""
    assert axios.article_id("https://www.axios.com/podcasts/ai-today") == ""
    assert axios.article_id("https://example.com/2026/09/04/openai-model") == ""


def test_parser_reads_all_cards_appended_by_show_more_and_deduplicates():
    cards = [
        _card(
            f"OpenAI releases reasoning model generation {index}",
            f"openai-reasoning-model-{index}",
            summary="The new frontier AI model is available to developers.",
        )
        for index in range(15)
    ]
    # 图片链接或另一个标题链接可能重复同一篇；稳定 article_id 只能留一条。
    cards.append(cards[0])
    rows = axios.parse_search_results(
        _listing(*cards), axios.TOPIC_LABEL, axios.LATEST_AI_URL
    )
    assert len(rows) == 15
    assert rows[0]["article_id"] == "2026-09-04-openai-reasoning-model-0"
    assert rows[0]["published_at"] == "2026-09-04T01:02:03Z"
    assert rows[0]["admission_reason"] == "ai_model"


def test_parser_reads_real_axios_semantic_headline_without_cta_or_image_link():
    html = """
      <html><head><title>Search results | Axios</title></head><body><main><ul>
        <li class="border-b">
          <div class="gtmView" role="article" data-vars-page-type="searchResults"
               data-vars-headline="OpenAI debuts GPT-6 Astra reasoning model">
            <a data-cy="rubric" aria-label="Technology section">Technology</a>
            <p data-cy="timestamp">7 hours ago</p>
            <a data-cy="story-promo-thumb" aria-hidden="true"
               href="/2026/09/04/openai-gpt-6-astra"><img alt="OpenAI"></a>
            <a data-cy="story-promo-headline"
               href="/2026/09/04/openai-gpt-6-astra">
              <h3><span data-cy="story-headline-openai-gpt-6-astra">
                OpenAI debuts GPT-6 Astra reasoning model
              </span></h3>
              <div><span>Go deeper (1 min. read)</span><span>→</span></div>
            </a>
          </div>
        </li>
      </ul></main></body></html>
    """
    rows = axios.parse_search_results(html, axios.TOPIC_LABEL, axios.LATEST_AI_URL)
    assert len(rows) == 1
    assert rows[0]["title_en"] == "OpenAI debuts GPT-6 Astra reasoning model"
    assert "Go deeper" not in rows[0]["title_en"]
    assert rows[0]["section"] == "Technology"


def test_parser_fails_closed_when_only_dated_image_links_are_recognizable():
    html = """
      <html><head><title>Search results | Axios</title></head><body><main>
        <a data-cy="story-promo-thumb" aria-hidden="true"
           href="/2026/09/04/openai-new-model"><img alt="OpenAI"></a>
      </main></body></html>
    """
    with pytest.raises(RuntimeError, match="标题|DOM"):
        axios.parse_search_results(html, axios.TOPIC_LABEL, axios.LATEST_AI_URL)


def test_parser_uses_main_results_not_unrelated_dated_links_elsewhere():
    outside = (
        '<aside><a href="/2026/09/04/openai-sidebar-model">'
        "OpenAI releases a sidebar model</a></aside>"
    )
    rows = axios.parse_search_results(
        _listing(
            _card(
                "Anthropic launches new Claude reasoning model",
                "anthropic-claude-reasoning-model",
            ),
            outside=outside,
        ),
        axios.TOPIC_LABEL,
        axios.LATEST_AI_URL,
    )
    assert [row["article_id"] for row in rows] == [
        "2026-09-04-anthropic-claude-reasoning-model"
    ]


def test_parser_keeps_summary_evidence_when_admitted_rows_rechecks_it():
    summary = "The deal covers GPUs for artificial intelligence training."
    rows = axios.parse_search_results(
        _listing(
            _card(
                "Nvidia signs a supply contract",
                "nvidia-signs-supply-contract",
                summary=summary,
            )
        ),
        axios.TOPIC_LABEL,
        axios.LATEST_AI_URL,
    )
    assert rows[0]["description"] == summary
    assert axios.admitted_rows(rows) == rows


def test_summary_evidence_survives_ledger_record_restore_and_recheck():
    rows = axios.parse_search_results(
        _listing(
            _card(
                "Nvidia signs a supply contract",
                "nvidia-signs-supply-contract",
                summary="The deal covers GPUs for artificial intelligence training.",
            )
        ),
        axios.TOPIC_LABEL,
        axios.LATEST_AI_URL,
    )
    rows[0]["body"] = "正文已取到"
    entries: dict[str, dict] = {}
    ledger_store.record(entries, rows, crawled_at="2026-09-04T02:00:00Z")

    restored = ledger_store.rows(entries)
    assert restored[0]["description"] == rows[0]["description"]
    assert axios.admitted_rows(restored) == restored


@pytest.mark.parametrize(
    "title,summary,reason",
    [
        (
            "OpenAI releases a new reasoning model",
            "The frontier model is available through the API.",
            "ai_model",
        ),
        (
            "Google makes Gemma model open source",
            "Developers can download the weights.",
            "ai_model",
        ),
        (
            "Nvidia signs HBM supply contract with SK Hynix",
            "The memory will feed AI accelerators.",
            "core_infrastructure",
        ),
        (
            "Data center operator orders new liquid cooling systems",
            "The build supports a large AI training cluster.",
            "core_infrastructure",
        ),
        (
            "New bill cracks down on insecure AI agents",
            "The legislation requires deployment standards.",
            "ai_policy",
        ),
        (
            "Top Pentagon official reaffirms Anthropic blacklist",
            "The procurement restriction remains in effect.",
            "ai_policy",
        ),
        (
            "Widespread AI outage underway",
            "Several leading model providers are unavailable.",
            "ai_model",
        ),
        (
            "California bans AI deepfakes",
            "The enacted restriction takes effect next month.",
            "ai_policy",
        ),
        (
            "California passes landmark AI safety bill",
            "The legislation sets binding requirements.",
            "ai_policy",
        ),
        (
            "Senate introduces bipartisan AI safety bill",
            "The legislation sets model deployment rules.",
            "ai_policy",
        ),
        (
            "OpenAI publishes a new AI scaling law",
            "The research describes model training behavior.",
            "ai_model",
        ),
        (
            "OpenAI publishes new AI scaling laws",
            "The research describes model training behavior.",
            "ai_model",
        ),
        (
            "Startup releases new open-source model",
            "Developers can download and run the model.",
            "ai_model",
        ),
        (
            "Company launches closed-source model",
            "The proprietary model is available through an API.",
            "ai_model",
        ),
        (
            "OpenAI's new model sets the standard for reasoning",
            "The benchmark measures frontier model performance.",
            "ai_model",
        ),
        (
            "Court rules against OpenAI in copyright lawsuit",
            "The judgment concerns model training data.",
            "ai_policy",
        ),
        (
            "FTC opens investigation into OpenAI",
            "The agency formally began an AI competition probe.",
            "ai_policy",
        ),
        (
            "Nvidia ships Blackwell Ultra systems to cloud providers",
            "",
            "core_infrastructure",
        ),
        (
            "California passes AI safety bill as critics warn of risks",
            "The enacted legislation sets binding requirements.",
            "ai_policy",
        ),
        (
            "EU adopts AI law while companies warn of costs",
            "The law has now been formally adopted.",
            "ai_policy",
        ),
        (
            "Court rules against OpenAI and warns other AI labs",
            "The binding judgment applies to model developers.",
            "ai_policy",
        ),
        (
            "FTC opens investigation into OpenAI as experts warn of risks",
            "The agency formally opened its probe.",
            "ai_policy",
        ),
        (
            "US blocks Nvidia H200 exports to China",
            "",
            "core_infrastructure",
        ),
        (
            "White House draws new AI line on China",
            "The administration changed its policy toward model providers.",
            "ai_policy",
        ),
        (
            "White House considers new export controls on AI chips to China",
            "Officials are reviewing restrictions on accelerator shipments.",
            "ai_policy",
        ),
        (
            "Lawmakers unveil bill to speed permits for AI data centers",
            "The measure changes federal permitting rules.",
            "ai_policy",
        ),
        (
            "US strikes light-touch AI regulation accord with G20 members",
            "The governments agreed on a common framework.",
            "ai_policy",
        ),
        (
            "Anthropic wins court challenge to US supply-chain risk label",
            "The judgment changes the company's federal designation.",
            "ai_policy",
        ),
        (
            "Pentagon says its Anthropic ban is on, despite official remarks",
            "The procurement restriction remains in effect.",
            "ai_policy",
        ),
        (
            "Congress wants in on the data center backlash",
            "Lawmakers are examining permits and power demand.",
            "core_infrastructure",
        ),
        (
            "Yotta eyes $20 billion GPU buildout as AI demand soars",
            "The operator plans new accelerator clusters.",
            "core_infrastructure",
        ),
        (
            "Asia data center debt binge hits banks' limits",
            "Project financing is constraining new capacity.",
            "core_infrastructure",
        ),
        (
            "Grid transformer shortage delays new AI data center projects",
            "Power equipment has become a supply-chain bottleneck.",
            "core_infrastructure",
        ),
        (
            "Apollo funds sell data center cooling firm Kelvion to SLB",
            "The acquisition covers liquid-cooling equipment.",
            "core_infrastructure",
        ),
        (
            "SK Hynix weighs Japan memory plant deal to supply AI boom",
            "The project would expand advanced-memory production.",
            "core_infrastructure",
        ),
        (
            "Huawei profit decline widens after memory crunch takes toll",
            "The shortage is disrupting the AI hardware supply chain.",
            "core_infrastructure",
        ),
        (
            "Broadcom cuts AI networking-chip output after packaging shortage",
            "Advanced packaging is limiting production.",
            "core_infrastructure",
        ),
        (
            "Nvidia invests $3.5 billion in chipmaker MediaTek",
            "The transaction expands their AI chip partnership.",
            "core_infrastructure",
        ),
        (
            "Andreessen Horowitz raises $1.1 billion for AI infrastructure fund",
            "The fund will finance compute and data center startups.",
            "core_infrastructure",
        ),
        (
            "CoreWeave raises $3 billion to expand GPU data center capacity",
            "The financing supports new clusters.",
            "core_infrastructure",
        ),
        (
            "Nodal Exchange plans AI compute futures to rival CME",
            "The contracts create a new market for compute capacity.",
            "core_infrastructure",
        ),
        (
            "Anthropic says new Fable AI model is cheaper and better at coding",
            "Benchmarks compare its capability with other frontier models.",
            "ai_model",
        ),
        (
            "OpenAI will limit access to new Astra model cybersecurity features",
            "The lab changed which customers can use the capability.",
            "ai_model",
        ),
        (
            "Saudi AI firm Humain unveils model based on China's MiniMax",
            "The foundation model will be available to developers.",
            "ai_model",
        ),
        (
            "AI startup reaches a $12 billion valuation in new funding round",
            "Investors committed fresh primary capital.",
            "ai_business",
        ),
        (
            "Exclusive: Aslan raises $20.8M for AI undercover agents",
            "The funding round gives the startup a new valuation.",
            "ai_business",
        ),
        (
            "Anthropic finalizes $15 billion pre-IPO credit facility",
            "Banks are financing the model developer's expansion.",
            "ai_business",
        ),
        (
            "SoftBank seeks another $10 billion loan for OpenAI stake funding",
            "The financing is tied to its investment in the AI lab.",
            "ai_business",
        ),
        (
            "Nvidia to buy Hugging Face for $13 billion in open-source push",
            "The acquisition targets the model ecosystem.",
            "ai_business",
        ),
        (
            "OpenAI ends partnership with Cursor after acquisition",
            "The companies changed their model distribution agreement.",
            "ai_business",
        ),
        (
            "Microsoft and OpenAI renegotiate their model licensing pact",
            "The new commercial terms govern access to foundation models.",
            "ai_business",
        ),
        (
            "OpenAI introduces usage-based pricing for enterprise AI agents",
            "The commercial model charges customers by consumption.",
            "ai_business",
        ),
        (
            "Sam Altman reorganizes OpenAI research around post-training",
            "The lab is changing its model development strategy.",
            "ai_business",
        ),
        (
            "Jensen Huang forecasts HBM supply constraints through 2027",
            "The Nvidia CEO gave a production outlook for AI memory.",
            "core_infrastructure",
        ),
        (
            "Anthropic tests new way for Claude to work with scientific tools",
            "The experiment extends the model's tool-use capability.",
            "ai_model",
        ),
        (
            "Anthropic signs $35 billion pact with Nvidia-backed Lambda",
            "The agreement secures compute for model training.",
            "ai_business",
        ),
        (
            "ChatGPT, Reddit and Roblox face tighter EU content rules",
            "The binding moderation rules apply to the AI service.",
            "ai_policy",
        ),
        (
            "Nvidia nears $14 billion Hugging Face deal this week",
            "The acquisition would reshape the open-source model ecosystem.",
            "ai_business",
        ),
        (
            "Napster shifts course to penny-a-minute AI agents via Microsoft",
            "The company adopted a new usage-based business model.",
            "ai_business",
        ),
        (
            "TSMC's chipmaking tool needs almost doubled this year",
            "Demand for semiconductor equipment is tightening supply.",
            "core_infrastructure",
        ),
        (
            "Kepco seeks billions from Samsung and SK Hynix to finance grid",
            "The electricity project will support new chip production.",
            "core_infrastructure",
        ),
        (
            "South Korea's exports gather pace as chip boom powers ahead",
            "Memory and accelerator demand is lifting semiconductor shipments.",
            "core_infrastructure",
        ),
        (
            "AI's environmental impact per task balloons with more complexity",
            "Multi-stage models require exponentially more energy and water.",
            "core_infrastructure",
        ),
        (
            "The UAE bets big on AI",
            "Officials describe a national investment strategy.",
            "ai_business",
        ),
        (
            "Takaichi's $640 billion AI and chip gamble faces a reality check",
            "Japan is testing the limits of its national investment strategy.",
            "ai_business",
        ),
    ],
)
def test_target_industry_models_policy_and_business_survive(title, summary, reason):
    assert axios.admission_reason(_item(title, summary=summary)) == reason


@pytest.mark.parametrize(
    "title,summary,reason",
    [
        (
            "Meta trains Llama 6 on a new post-training recipe",
            "The model improves coding performance.",
            "ai_model",
        ),
        (
            "Researchers release a foundation-model benchmark for agents",
            "The test covers reasoning and tool use.",
            "ai_model",
        ),
        (
            "Kioxia expands SSD output for AI inference systems",
            "Flash storage demand is rising.",
            "core_infrastructure",
        ),
        (
            "TSMC delays 2nm AI chip fab after skilled-worker shortage",
            "Labor constraints threaten capacity.",
            "core_infrastructure",
        ),
        (
            "AI data center buildout pushes household power bills higher",
            "Regulators are reviewing grid costs.",
            "core_infrastructure",
        ),
        (
            "EU AI Act enters into force for frontier-model providers",
            "The law imposes binding obligations.",
            "ai_policy",
        ),
        (
            "California governor vetoes AI safety bill",
            "The proposal will not become law.",
            "ai_policy",
        ),
        (
            "FTC launches antitrust probe into OpenAI cloud deals",
            "The agency is investigating competition.",
            "ai_policy",
        ),
        (
            "UK regulator investigates Anthropic over model safety",
            "The formal inquiry begins this week.",
            "ai_policy",
        ),
        (
            "EU fines Meta under the AI Act",
            "The regulator imposed a penalty.",
            "ai_policy",
        ),
        (
            "Congress holds hearing on AI data-center power demand",
            "Lawmakers question grid regulators.",
            "ai_policy",
        ),
        (
            "Court dismisses AI copyright suit against OpenAI",
            "The judge ended the case.",
            "ai_policy",
        ),
        (
            'Sony, Warner sue Anthropic, alleging "blatant theft" of intellectual property',
            "The complaint targets training and model development.",
            "ai_policy",
        ),
        (
            "Foundation-model startup raises $900 million at $8 billion valuation",
            "Investors are funding model training.",
            "ai_business",
        ),
        (
            "SoftBank to invest $15 billion in OpenAI",
            "The primary investment funds model development.",
            "ai_business",
        ),
        (
            "Anthropic launches a new enterprise subscription plan",
            "Customers pay a fixed monthly fee for Claude.",
            "ai_business",
        ),
        (
            "OpenAI signs a $200 million enterprise AI contract",
            "The agreement covers model access.",
            "ai_business",
        ),
        (
            "Elon Musk details xAI model-training roadmap through 2028",
            "The plan covers Grok scaling and compute.",
            "ai_business",
        ),
        (
            "Lisa Su outlines AMD accelerator roadmap for AI data centers",
            "New GPUs will ship yearly.",
            "core_infrastructure",
        ),
        (
            "Musk says xAI will train Grok 5 on ten times more compute",
            "The model-training plan is a strategic R&D decision.",
            "ai_model",
        ),
        (
            "Dario Amodei forecasts frontier-model scaling costs through 2030",
            "The outlook covers training compute and research.",
            "ai_model",
        ),
        (
            "SK Hynix invests $8 billion in HBM capacity as its shares fall",
            "The capex expands AI memory supply.",
            "core_infrastructure",
        ),
        (
            "TSMC opens an AI chip fab that will hire 3,000 workers",
            "The fab expands advanced-node capacity.",
            "core_infrastructure",
        ),
        (
            "OpenAI releases GPT-7 with mixture-of-experts architecture",
            "Its benchmarks include medical exams among many evaluations.",
            "ai_model",
        ),
        (
            "University researchers release a foundation-model benchmark",
            "The evaluation measures agent reasoning and tool use.",
            "ai_model",
        ),
        (
            "OpenAI launches a new usage-based revenue model",
            "API customers will pay per token.",
            "ai_business",
        ),
        (
            "OpenAI cuts API prices by 50% for reasoning models",
            "The new token pricing changes model economics.",
            "ai_business",
        ),
        (
            "DOJ settles AI competition case against model provider",
            "The consent order changes licensing terms.",
            "ai_policy",
        ),
        (
            "White House issues AI procurement guidance for agencies",
            "The binding guidance governs federal model purchases.",
            "ai_policy",
        ),
    ],
)
def test_adversarial_industry_cases_are_not_lost(title, summary, reason):
    assert axios.admission_reason(_item(title, summary=summary)) == reason


@pytest.mark.parametrize(
    "title,summary,reason",
    [
        (
            "DeepSeek improves reasoning and coding in its flagship model",
            "New evaluations show capability gains.",
            "ai_model",
        ),
        (
            "Alibaba reveals the Qwen architecture for long-context agents",
            "The model uses a new attention design.",
            "ai_model",
        ),
        (
            "Seagate boosts hard-drive output for AI storage",
            "Data-center inference is driving demand.",
            "core_infrastructure",
        ),
        (
            "Vertiv opens a chiller plant for the AI boom",
            "The factory will make data-center cooling equipment.",
            "core_infrastructure",
        ),
        (
            "Equinix signs a PPA for new AI campuses",
            "The power-purchase agreement supports data centers.",
            "core_infrastructure",
        ),
        (
            "AI growth drives record orders for gas turbines",
            "Utilities need generation for data centers.",
            "core_infrastructure",
        ),
        (
            "Google starts volume production of its next TPU",
            "The accelerator will train Gemini.",
            "core_infrastructure",
        ),
        (
            "Samsung wins Nvidia qualification for its new HBM",
            "The approval adds another memory supplier.",
            "core_infrastructure",
        ),
        (
            "TSMC reaches 80% yield on 2nm chips for AI accelerators",
            "The process milestone increases supply.",
            "core_infrastructure",
        ),
        (
            "Cloud provider builds a subsea cable for AI clusters",
            "The network adds training capacity.",
            "core_infrastructure",
        ),
        (
            "Oracle reserves more inference-cluster capacity",
            "The compute will serve foundation models.",
            "core_infrastructure",
        ),
        (
            "FTC subpoenas OpenAI over cloud competition",
            "The demand is part of a formal investigation.",
            "ai_policy",
        ),
        (
            "Regulator publishes a binding model-audit standard",
            "Frontier labs must comply next year.",
            "ai_policy",
        ),
        (
            "EU Parliament delays its vote on the AI liability bill",
            "The legislative timetable changed.",
            "ai_policy",
        ),
        (
            "Commerce Department adds an AI chip firm to the Entity List",
            "The trade restriction blocks accelerator exports.",
            "ai_policy",
        ),
        (
            "Congress requires frontier labs to report safety incidents",
            "The mandate applies to model providers.",
            "ai_policy",
        ),
        (
            "UK government publishes a national AI compute strategy",
            "The plan funds sovereign infrastructure.",
            "ai_policy",
        ),
        (
            "Senate committee issues subpoenas to leading AI labs",
            "The formal oversight proceeding seeks records.",
            "ai_policy",
        ),
        (
            "SoftBank commits $20 billion to OpenAI Stargate",
            "The investment funds new AI infrastructure.",
            "ai_business",
        ),
        (
            "Anthropic wins a $300 million enterprise AI contract",
            "The customer will license Claude.",
            "ai_business",
        ),
        (
            "Mistral rolls out per-request pricing for enterprise models",
            "The commercial model changes API charges.",
            "ai_business",
        ),
        (
            "Groq offers reserved-capacity pricing for inference",
            "The new model sells guaranteed throughput.",
            "ai_business",
        ),
        (
            "OpenAI changes its model-licensing terms with Microsoft",
            "The companies revised commercial rights.",
            "ai_business",
        ),
        (
            "Anthropic spins out a safety-tool startup",
            "The new company will sell model testing software.",
            "ai_business",
        ),
        (
            "Musk maps out xAI GPU procurement through 2029",
            "The plan covers a new compute fleet.",
            "core_infrastructure",
        ),
        (
            "Sam Altman commits OpenAI to building a 10GW compute fleet",
            "The capacity supports model training.",
            "core_infrastructure",
        ),
        (
            "Jensen Huang sets a Rubin production target for 2028",
            "The goal changes Nvidia accelerator supply.",
            "core_infrastructure",
        ),
        (
            "Dario Amodei details the scaling-cost outlook for Claude",
            "The forecast covers future training runs.",
            "ai_model",
        ),
        (
            "Demis Hassabis announces Gemini research agenda",
            "The roadmap focuses on world models.",
            "ai_business",
        ),
        (
            "C. C. Wei forecasts CoWoS expansion through 2029",
            "TSMC plans more advanced-packaging output.",
            "core_infrastructure",
        ),
    ],
)
def test_additional_final_scope_industry_cases_are_admitted(
    title, summary, reason
):
    assert axios.admission_reason(_item(title, summary=summary)) == reason


@pytest.mark.parametrize(
    "title,summary",
    [
        (
            "Restaurant chain launches a pay-as-you-go AI ordering agent",
            "Diners subscribe through a mobile app.",
        ),
        (
            "Real-estate broker introduces a marketplace for AI home agents",
            "Consumers use it to shop for houses.",
        ),
        (
            "OpenAI CEO buys a Manhattan penthouse",
            "The home is a personal purchase.",
        ),
        (
            "Dario Amodei sells his San Francisco home to fund Anthropic",
            "The story centers on his personal property.",
        ),
        (
            "Anthropic signs an office-cleaning contract",
            "The vendor will clean its headquarters.",
        ),
        (
            "xAI buys snacks for its employees",
            "The purchase restocks the office kitchen.",
        ),
        (
            "OpenAI signs a sponsorship agreement with Formula One",
            "The logo will appear at races.",
        ),
        (
            "Anthropic issues employee dress-code rules",
            "The internal policy covers office attire.",
        ),
        (
            "OpenAI bans pets under a new workplace rule",
            "The internal policy applies at headquarters.",
        ),
        (
            "Nvidia gains 8% after the Blackwell launch",
            "The headline describes its share move.",
        ),
        (
            "Nvidia adds $300 billion in value after a GPU release",
            "The market capitalization increased.",
        ),
        (
            "Jensen Huang expects chip demand forever",
            "The speech gave no forecast period or supply data.",
        ),
    ],
)
def test_additional_final_scope_noise_cases_are_rejected(title, summary):
    assert axios.admission_reason(_item(title, summary=summary)) == ""


@pytest.mark.parametrize(
    "title,reason",
    [
        ("U.S. draws a new AI policy line", "ai_policy"),
        ("U.S. considers new rules for frontier models", "ai_policy"),
        ("U.S. bets big on AI", "ai_business"),
        (
            "Anthropic struck a cloud partnership with Amazon",
            "ai_business",
        ),
        (
            "Anthropic is striking a cloud deal with Amazon",
            "ai_business",
        ),
        (
            "OpenAI signs copyright licensing agreement with Disney",
            "ai_business",
        ),
        ("Meta outlines AI model roadmap through 2028", "ai_business"),
        ("Google details Gemini research roadmap", "ai_business"),
        ("Amazon unveils AI investment plan", "ai_business"),
        ("OpenAI launches a new model portfolio", "ai_model"),
        (
            "OpenAI rolls out GPT-6 Astra model with cyber guardrails",
            "ai_model",
        ),
        (
            "Nvidia launches a new model portfolio for enterprises",
            "ai_model",
        ),
    ],
)
def test_policy_business_and_model_word_boundaries(title, reason):
    assert axios.admission_reason(_item(title)) == reason


@pytest.mark.parametrize(
    "title",
    [
        "OpenAI adopts new rules for ChatGPT developers",
        "Data center operator launches scholarship program",
        "Nvidia launches employee cafeteria beside AI chip fab",
        "Nvidia shares plunge 10% after launching a new AI chip",
        "Nvidia stock slumps after unveiling Blackwell Ultra",
        "Nvidia stock hits a record after Blackwell launch",
        "Model training remains too expensive",
        "Why GPT-7 benchmark results matter",
        "Open-source models pose existential threat",
        "Potato chip supply tightens",
        "Open letter warns about AI chip demand",
        "Acme buys an AI chatbot startup for customer service",
    ],
)
def test_static_commentary_and_cross_clause_homonyms_are_rejected(title):
    assert axios.admission_reason(_item(title)) == ""


@pytest.mark.parametrize(
    "title,reason",
    [
        ("Meta is training a new frontier model", "ai_model"),
        ("OpenAI begins foundation-model training run", "ai_model"),
        ("GPT-7 is setting a new benchmark record", "ai_model"),
        ("Anthropic is merging with OpenAI", "ai_business"),
        ("OpenAI makes GPT-7 open source", "ai_model"),
        ("Meta makes Llama 5 open source", "ai_model"),
        ("Google open-sources Gemma 4", "ai_model"),
        ("Anthropic open sources Claude", "ai_model"),
        (
            "Blackstone raises $10 billion data-center real-estate fund",
            "core_infrastructure",
        ),
        (
            "Digital Realty expands AI data center real estate portfolio",
            "core_infrastructure",
        ),
        ("OpenAI publishes a new compute power law", "ai_model"),
        ("Researchers publish new AI capability law", "ai_model"),
        ("OpenAI publishes a new law of AI scaling", "ai_model"),
        ("U.S. AI chip restrictions remain in effect", "ai_policy"),
        ("EU sanctions remain in effect on AI chips", "ai_policy"),
    ],
)
def test_model_lifecycle_real_estate_and_policy_status_boundaries(
    title, reason
):
    assert axios.admission_reason(_item(title)) == reason


@pytest.mark.parametrize(
    "title,summary",
    [
        ("California passes housing law", "A residential measure."),
        ("EU adopts new banking regulation", "It applies to lenders."),
        (
            "Court dismisses copyright lawsuit against Disney",
            "The case is unrelated to AI.",
        ),
        (
            "White House issues procurement guidance for office furniture",
            "Agencies will replace desks.",
        ),
        (
            "Senate committee issues subpoenas to oil companies",
            "The hearing concerns fuel prices.",
        ),
        (
            "Microsoft outlines Windows product roadmap through 2028",
            "The plan concerns desktop features.",
        ),
        (
            "Amazon details investment plan for grocery delivery",
            "The spending targets retail logistics.",
        ),
        (
            "Meta reorganizes virtual reality division",
            "The unit makes consumer headsets.",
        ),
        (
            "Alibaba announces logistics investment plan",
            "The project expands parcel delivery.",
        ),
        (
            "Oracle outlines database product roadmap",
            "The release covers relational databases.",
        ),
        (
            "AI chipmaker wins workplace diversity award",
            "The award concerns human resources.",
        ),
        (
            "Data center operator reaches labor agreement",
            "The contract covers employee benefits.",
        ),
        (
            "Nvidia launches charity beside its AI data center",
            "The initiative funds a neighborhood park.",
        ),
        (
            "Oracle launches charity initiative",
            "The announcement was made at a data center.",
        ),
    ],
)
def test_non_ai_policy_strategy_and_summary_pollution_are_rejected(
    title, summary
):
    assert axios.admission_reason(_item(title, summary=summary)) == ""


@pytest.mark.parametrize(
    "title,reason",
    [
        ("Google upgrades Gemini with a new long-context architecture", "ai_model"),
        ("Anthropic makes Claude 5 generally available after safety testing", "ai_model"),
        ("DeepSeek adds a one-million-token context window to its flagship model", "ai_model"),
        ("Researchers develop a foundation model that reasons over long documents", "ai_model"),
        ("SK Hynix breaks ground on a new HBM fab for AI accelerators", "core_infrastructure"),
        ("Nvidia recalls Blackwell GPUs after an interconnect defect", "core_infrastructure"),
        ("Google connects two AI clusters with a private fiber network", "core_infrastructure"),
        ("Amazon purchases nuclear power for a new AI data center", "core_infrastructure"),
        ("Intel shelves its Falcon Shores AI accelerator", "core_infrastructure"),
        ("Senate advances a binding AI safety bill to a final vote", "ai_policy"),
        ("India mandates disclosure of AI model training data", "ai_policy"),
        ("Canadian parliament adopts a law for frontier AI models", "ai_policy"),
        ("European Commission designates OpenAI a systemic-risk platform", "ai_policy"),
        ("Court grants an injunction in the OpenAI copyright lawsuit", "ai_policy"),
        ("Japanese regulator opens a competition probe into AI model pricing", "ai_policy"),
        ("European Council ratifies the international AI safety accord", "ai_policy"),
        ("China mandates registration of frontier AI models before launch", "ai_policy"),
        ("NIST publishes an AI model evaluation standard for federal suppliers", "ai_policy"),
        ("US tightens export controls on AI accelerators", "ai_policy"),
        ("Federal appeals court stays the AI chip export ban", "ai_policy"),
        ("OpenAI purchases a model-monitoring startup", "ai_business"),
        ("Anthropic takes a minority stake in an inference startup", "ai_business"),
        ("Mistral cancels its cloud partnership with Microsoft", "ai_business"),
        ("Cohere renews its model-distribution agreement with Oracle", "ai_business"),
        ("OpenAI signs a distribution pact with SAP for enterprise models", "ai_business"),
        ("AI chip startup receives $80 million in strategic backing", "ai_business"),
        ("Perplexity begins charging per query for its enterprise AI service", "ai_business"),
        ("OpenAI removes the free tier from its enterprise API", "ai_business"),
        ("Anthropic switches Claude enterprise accounts to seat-based pricing", "ai_business"),
        ("Sam Altman pivots OpenAI research toward continuous-learning models", "ai_business"),
        ("Elon Musk pledges $40 billion for xAI training infrastructure", "core_infrastructure"),
        ("Nvidia divests its legacy networking unit to focus on AI interconnects", "ai_business"),
    ],
)
def test_extended_industry_event_vocabulary(title, reason):
    assert axios.admission_reason(_item(title)) == reason


@pytest.mark.parametrize(
    "title,reason",
    [
        (
            "OpenAI launches its most capable, efficient and safe frontier "
            "reasoning model GPT-10",
            "ai_model",
        ),
        (
            "Anthropic releases an extensively retrained, safer and much "
            "stronger coding version of Claude",
            "ai_model",
        ),
        ("OpenAI releases GPT-10", "ai_model"),
        ("OpenAI updates ChatGPT with stronger reasoning", "ai_model"),
        (
            "Anthropic introduces a new reasoning architecture for Claude",
            "ai_model",
        ),
        ("Google deploys a new reasoning architecture in Gemini", "ai_model"),
        ("Anthropic fine-tunes Claude for stronger coding", "ai_model"),
        ("Google expands Gemini context window", "ai_model"),
        ("Meta modifies Llama model architecture", "ai_model"),
        ("OpenAI redesigns GPT-10 model architecture", "ai_model"),
        ("Nvidia gains 20% more HBM capacity", "core_infrastructure"),
        ("TSMC gains 15% in 2nm chip yield", "core_infrastructure"),
        ("France imposes restrictions on AI chip exports", "ai_policy"),
        ("South Korea tightens HBM export rules", "ai_policy"),
        ("Germany tightens data center permitting rules", "ai_policy"),
        (
            "California passes AI safety bill as critics warn of risks",
            "ai_policy",
        ),
        ("EU adopts AI law while companies warn of costs", "ai_policy"),
        (
            "FTC opens investigation into OpenAI as experts warn of risks",
            "ai_policy",
        ),
    ],
)
def test_substantive_model_infrastructure_and_enacted_policy_events(
    title, reason
):
    assert axios.admission_reason(_item(title)) == reason


@pytest.mark.parametrize(
    "title,summary,reason",
    [
        (
            "OpenAI doubles GPT-6's context window to two million tokens",
            "The update improves long-document reasoning.",
            "ai_model",
        ),
        (
            "DeepSeek's latest model outperforms GPT-7 in reasoning tests",
            "Independent benchmarks confirm the capability gain.",
            "ai_model",
        ),
        (
            "xAI brings 100,000 Rubin GPUs online at its Memphis campus",
            "The cluster expands training capacity.",
            "core_infrastructure",
        ),
        (
            "Microsoft mothballs its Wisconsin data-center project",
            "The cancellation removes planned AI compute capacity.",
            "core_infrastructure",
        ),
        (
            "AMD secures Samsung HBM for MI450 GPUs",
            "The procurement diversifies its memory supply.",
            "core_infrastructure",
        ),
        (
            "FCC adopts a rule requiring labels on AI-generated robocalls",
            "The binding rule applies to telecom carriers.",
            "ai_policy",
        ),
        (
            "FTC closes its antitrust investigation into Nvidia",
            "The agency ended the formal probe.",
            "ai_policy",
        ),
        (
            "BIS expands AI-chip export controls to Southeast Asia",
            "The binding restrictions now cover more accelerators.",
            "ai_policy",
        ),
        (
            "OpenAI converts its nonprofit into a public-benefit corporation",
            "The restructuring changes control and investor rights.",
            "ai_business",
        ),
        (
            "OpenAI tender offer values the company at $500 billion",
            "The transaction establishes a private-company valuation.",
            "ai_business",
        ),
        (
            "Sam Altman steps down as OpenAI chief executive",
            "The key AI lab must choose new leadership.",
            "ai_business",
        ),
        (
            "An AI data-center operator files for bankruptcy protection",
            "The collapse threatens GPU leases and creditors.",
            "ai_business",
        ),
        (
            "Anthropic Signs $35 Billion Pact With Nvidia-Backed Lambda",
            "",
            "ai_business",
        ),
        (
            "Saudi AI Firm Humain Explores $2.5 Billion Fund for Data Centers",
            "",
            "core_infrastructure",
        ),
        (
            "The Big Take Secretive China Chipmaker Is Built to Dodge US "
            "Curbs Founded by a US-trained entrepreneur, CXMT is racing to "
            "catch its rivals and using a largely domestic supplier network "
            "to shield itself from Washington.",
            "",
            "core_infrastructure",
        ),
    ],
)
def test_event_taxonomy_covers_industry_business_and_real_ledger_titles(
    title, summary, reason
):
    assert axios.admission_reason(_item(title, summary=summary)) == reason


@pytest.mark.parametrize(
    "title,summary",
    [
        ("Court may dismiss AI copyright lawsuit", "The outcome is uncertain."),
        (
            "France signs trade deal while AI chip export restrictions remain "
            "under review",
            "The trade pact does not change the proposed controls.",
        ),
        (
            "EU approves budget as proposed AI rules face debate",
            "No AI measure has passed.",
        ),
        (
            "California passes budget after AI bill stalls",
            "The AI proposal did not advance.",
        ),
        ("AI chipmaker signs insurance contract", "The policy covers offices."),
        ("AI chipmaker buys office security firm", "The deal covers guards."),
        ("Data center operator signs audit deal", "It is a routine audit."),
        ("Data center operator buys payroll software", "The tool handles wages."),
        ("GPU maker opens employee gym", "The facility is a workplace perk."),
        (
            "AI chipmaker publishes employee handbook",
            "The document explains leave policy.",
        ),
        (
            "OpenAI publishes annual report on ChatGPT coding usage",
            "The document summarizes employee adoption.",
        ),
        (
            "Google releases Gemini cookbook with coding recipes",
            "The guide is documentation, not a model release.",
        ),
        (
            "Google releases Gemini Mini",
            "The feature edits family photos on Pixel smartphones.",
        ),
        (
            "Samsung raises DRAM shipments for game consoles",
            "The memory supplies consumer entertainment devices.",
        ),
        (
            "Arm leaps 14% as AI-chip demand accelerates",
            "The headline tracks its listed shares.",
        ),
        (
            "Gemini court wins an architecture design award",
            "Court is the name of an office complex.",
        ),
    ],
)
def test_event_signals_cannot_cross_clauses_targets_or_excluded_uses(
    title, summary
):
    assert axios.admission_reason(_item(title, summary=summary)) == ""


@pytest.mark.parametrize(
    "title",
    [
        "Samsung boosts DRAM output for washing machines",
        "TSMC expands foundry capacity for automotive microcontrollers",
        "Intel builds a semiconductor fab for legacy industrial chips",
        "Broadcom ships networking chips for cable television boxes",
        "OpenAI launches a model that diagnoses rare cancers",
        "AI chipmaker Nvidia hits a $6 trillion valuation",
        "AMD becomes a trillion-dollar company on the AI chip boom",
        "Micron's price-to-earnings ratio jumps as HBM demand rises",
        "Nvidia options traders bet on Blackwell demand",
        "Short sellers lose billions as Nvidia GPU orders surge",
        "Nvidia rockets 12% after announcing Rubin shipments",
        "OpenAI buys 10,000 ergonomic office chairs",
        "Anthropic partners with a neighborhood charity",
        "Mistral sells branded T-shirts at its developer conference",
        "OpenAI raises $20 million for disaster-relief donations",
        "Anthropic commits $5 million to a modern-art museum",
        "OpenAI acquires a professional soccer club",
        "Video: OpenAI launches GPT-7 reasoning model",
        "Watch: Jensen Huang unveils the Rubin Ultra GPU",
        "Livestream: Anthropic announces Claude 6",
        "OpenAI launches a consumer subscription tier for family use",
        "Anthropic buys a chain of private fitness clubs",
        "OpenAI launches an AI outage tracker for airline passengers",
        "California AI startup adopts safety rules for its own products",
        "EU startup issues AI rules for customers using its app",
        "OpenAI issues AI rules for government agencies using ChatGPT",
        "Microsoft publishes AI restrictions for White House contractors",
        "House AI introduces a rule-management product",
        "OpenAI releases a role-models report for managers",
        "Anthropic unveils a model employee awards program",
        "OpenAI launches a model-airplane design contest",
        "AI chips away at office morale as demand for overtime grows",
        "Nvidia launches a server-rack furniture collection",
        "OpenAI publishes a guide to ChatGPT for developers",
        "Meta releases Llama documentation for developers",
        "OpenAI trains employees to use ChatGPT safely",
        "OpenAI develops a new office for ChatGPT team",
        "OpenAI retires ChatGPT product manager",
        "AI chipmaker publishes diversity impact report",
        "AI data center company publishes community impact report",
        "EU may approve a binding AI safety law",
        "California could impose AI model audit rules",
        "Governor wants to approve an AI safety bill",
        "Senator hopes to file an AI regulation bill",
        "OpenAI files $10 million bill with Microsoft for AI compute",
    ],
)
def test_extended_non_core_and_homonym_vocabulary_is_rejected(title):
    assert axios.admission_reason(_item(title)) == ""


@pytest.mark.parametrize(
    "title,summary,extra",
    [
        (
            "Exclusive: GOP issues stark warning to AI companies",
            "Lawmakers say labs should be more careful.",
            {"section": "Politics & Policy"},
        ),
        (
            "Trump's AI team fractures over strategy",
            "White House tensions surfaced at a summit.",
            {"section": "Politics & Policy"},
        ),
        (
            "Bernie Sanders floats ban on superintelligent AI",
            "The senator called for a future restriction.",
            {"section": "Politics & Policy"},
        ),
        (
            "How AI explains recent stock market weirdness",
            "Investors are debating the AI trade.",
            {},
        ),
        (
            "Doctors argue their role in the age of AI",
            "Hospitals are testing assistants.",
            {},
        ),
        (
            "Hochul launches AI workforce push with focus on women",
            "The jobs program will train local workers.",
            {},
        ),
        (
            "Axios Live: Florida debates AI data centers",
            "A panel discussed proposed guardrails.",
            {"content_type": "Axios Events"},
        ),
        (
            "The Information launches a weekly AI video show",
            "The program will stream on Mondays.",
            {"content_type": "Video"},
        ),
        (
            "The Information bets bigger on video with new AI show",
            "The media company is expanding its programming.",
            {},
        ),
        (
            "Seattle science powerhouses bet big on AI-designed biology",
            "Researchers are applying models to laboratory work.",
            {},
        ),
        (
            "Brain implants fuel U.S.-China AI bioscience rivalry",
            "Medical researchers are testing implants.",
            {},
        ),
        (
            "Army taps Palantir for 8 AI-fueled TITAN trucks",
            "The military vehicles will be deployed by a brigade.",
            {},
        ),
        (
            "Bill Gates sounds alarm over artificial intelligence",
            "The Microsoft co-founder offered his latest warning.",
            {},
        ),
        (
            "Gates' Epstein-era AI push draws new scrutiny",
            "The story revisits a personal relationship.",
            {},
        ),
        (
            "Gen Z embraces an AI-resistant college renaissance",
            "Students are changing how they choose schools.",
            {},
        ),
        (
            "AI may cure Hepatitis C",
            "Clinical trials are beginning with patients.",
            {},
        ),
        (
            "AI can create dangerous new viruses",
            "Biology researchers tested the model.",
            {},
        ),
        (
            "Union workers seek new AI protections",
            "Labor leaders are negotiating workplace rules.",
            {},
        ),
        (
            "Musk and Zuck plot their AI comebacks",
            "The two executives want renewed attention.",
            {},
        ),
        (
            "Economists issue an AI economic warning",
            "The report discusses inequality and growth.",
            {},
        ),
        (
            "AI widens America's class divide",
            "The social effects differ by income.",
            {},
        ),
        (
            "AI lab musical chairs accelerate",
            "Researchers keep changing employers.",
            {},
        ),
        (
            "States forge ahead with safety-net AI",
            "Agencies are automating benefits programs.",
            {},
        ),
        (
            "Nvidia CEO sees science fiction fear around AI",
            "The executive discussed his outlook in Washington.",
            {},
        ),
        (
            "Nvidia CEO to Washington: Don't fall for \"science fiction\" AI fear",
            "The executive offered an opinion about public anxiety.",
            {},
        ),
        (
            "OpenAI launches its new reasoning model",
            "A short clip demonstrates the system.",
            {"content_type": "Video"},
        ),
        (
            "AI's architects say the next era of human history is here",
            "Industry leaders made predictions.",
            {},
        ),
        (
            "AI optimism fades among young adults",
            "A new public opinion poll tracks attitudes.",
            {},
        ),
        (
            "We're waiting for AI models like they're Taylor Swift albums",
            "The release calendar has become entertainment.",
            {},
        ),
        (
            "Exclusive: OpenAI CFO pitches a new way to measure AI's value",
            "The executive described the idea at a conference.",
            {},
        ),
        (
            "Pro-AI super PAC keeps $31M ready for the midterms",
            "The political group plans campaign spending.",
            {"section": "Politics & Policy"},
        ),
        (
            "AI changes how lawyers write contracts",
            "A legal team describes a productivity workflow.",
            {},
        ),
        (
            "Samsung launches Galaxy S27 with new AI features",
            "",
            {},
        ),
        (
            "Anthropic launches a new school for AI students",
            "The education program teaches young adults.",
            {},
        ),
        (
            "Senator calls for a new AI safety bill",
            "No legislation has been introduced.",
            {"section": "Politics & Policy"},
        ),
        (
            "California considers banning AI deepfakes",
            "Officials are discussing a possible restriction.",
            {"section": "Politics & Policy"},
        ),
        (
            "Senator calls for banning AI models",
            "No measure has been filed.",
            {"section": "Politics & Policy"},
        ),
        (
            "Governor wants to sign AI safety law",
            "The governor described what may happen later.",
            {"section": "Politics & Policy"},
        ),
        (
            "Senator calls on governor to sign AI safety law",
            "The senator requested a future action.",
            {"section": "Politics & Policy"},
        ),
        (
            "Lawmakers ask governor to sign AI safety law",
            "No action has been taken.",
            {"section": "Politics & Policy"},
        ),
        (
            "Canva launches generative AI design tool",
            "",
            {},
        ),
        (
            "Salesforce deploys generative AI sales assistant",
            "",
            {},
        ),
        (
            "OpenAI signs new headquarters lease",
            "",
            {},
        ),
        (
            "OpenAI buys office building in San Francisco",
            "",
            {},
        ),
        (
            "Retailer launches AI agent for shopping",
            "",
            {},
        ),
        (
            "Army launches AI agent for battlefield logistics",
            "",
            {},
        ),
        (
            "Hospital launches AI agent for patient care",
            "",
            {},
        ),
        (
            "OpenAI launches GPT-6 model for hospitals",
            "Doctors will be among the first users.",
            {},
        ),
        (
            "Meta releases open-source Llama model for students",
            "Universities may download the model weights.",
            {},
        ),
        (
            "Nvidia shares soar after analysts raise their price target",
            "The stock rallied in afternoon trading.",
            {},
        ),
        (
            "Five AI stocks to buy and hold forever",
            "The portfolio tracks public equities.",
            {},
        ),
        (
            "AI ETF jumps 12% as investors pile into the trade",
            "Shares rose across the sector.",
            {},
        ),
        (
            "Nvidia raises $5 billion bond for general corporate purposes",
            "The debt will fund general corporate purposes.",
            {},
        ),
        (
            "Musk says AI will change everything",
            "The executive shared a personal prediction.",
            {},
        ),
        (
            "Sam Altman shares his optimism about the future of AI",
            "The OpenAI CEO offered no new product or strategy.",
            {},
        ),
        (
            "New iPhone AI feature organizes personal photos",
            "The consumer feature ships next month.",
            {},
        ),
        (
            "AI assistant plans family vacations and recipes",
            "The personal app targets consumers.",
            {},
        ),
        (
            "Almost anyone can make money selling electricity with AI",
            "Homeowners buy power at low rates and sell it back to utilities.",
            {},
        ),
        (
            "Microsoft seeks to reassure employees about data centers' impact",
            "The internal message addressed staff concerns.",
            {},
        ),
        (
            "AI billionaire-backed group launches pro-data center ad blitz",
            "The publicity campaign promotes new construction.",
            {},
        ),
        (
            "Boehringer signs deal for Owkin AI, joining Astra and Sanofi",
            "The pharmaceutical companies will use it for drug research.",
            {},
        ),
    ],
)
def test_market_media_peripheral_and_chatter_are_rejected(
    title, summary, extra
):
    assert axios.admission_reason(_item(title, summary=summary, **extra)) == ""


@pytest.mark.parametrize(
    "title,summary",
    [
        (
            "OpenAI CEO buys a $50 million mansion",
            "The purchase is Sam Altman's new personal home.",
        ),
        (
            "Data-center REIT valuation jumps on AI demand",
            "Its shares rose in morning trading.",
        ),
        (
            "Reddit bans AI art from a popular forum",
            "Moderators changed community rules.",
        ),
        (
            "Servers see demand double at restaurant chains",
            "The systems run point-of-sale software, not AI.",
        ),
        (
            "Coffee supply chain faces shortage",
            "Roasters are raising prices.",
        ),
        (
            "Power grid demand rises as summer heat hits",
            "Utilities expect record air-conditioning use.",
        ),
        (
            "Ethernet outage hits corporate offices",
            "The network failure affected payroll systems.",
        ),
        (
            "AI deals with uncertainty in the workplace",
            "Executives discussed broad trends.",
        ),
        (
            "AI deals a blow to traditional office culture",
            "The essay contains no transaction.",
        ),
        (
            "ChatGPT passes the girlfriend test",
            "A columnist tried the chatbot for dating advice.",
        ),
        (
            "OpenAI model faces courtroom test",
            "Commentators debated what might happen.",
        ),
        (
            "OpenAI denies reports of a $20 billion deal",
            "No transaction has occurred.",
        ),
        (
            "AI deal talks intensify",
            "No named company has signed an agreement.",
        ),
        (
            "OpenAI valuation worries investors",
            "No funding round or transaction was announced.",
        ),
        (
            "Anthropic partners with a luxury fashion brand",
            "The marketing campaign promotes clothing.",
        ),
        (
            "OpenAI signs a catering deal for its office cafeteria",
            "The contract changes employee lunches.",
        ),
        (
            "Nvidia shares are up 10% after a new AI chip launch",
            "Analysts raised their price target.",
        ),
        (
            "ChatGPT faces oversight questions from industry critics",
            "No regulator or formal process is involved.",
        ),
        (
            "Investment in human cognition and AI accelerates",
            "The word cognition is not a company name.",
        ),
    ],
)
def test_adversarial_homonyms_rumors_and_noise_are_rejected(title, summary):
    assert axios.admission_reason(_item(title, summary=summary)) == ""


def test_local_url_is_rejected_even_when_title_is_core_ai():
    item = _item(
        "OpenAI releases a new model for Austin schools",
        url="https://www.axios.com/local/austin/2026/09/04/openai-schools",
    )
    assert axios.admission_reason(item) == ""


@pytest.mark.parametrize(
    "title,reason",
    [
        (
            "Welcome to the AGI era, OpenAI says as GPT-6 Astra debuts",
            "ai_model",
        ),
        (
            "Sony and Warner sue Anthropic over AI model copyright",
            "ai_policy",
        ),
        (
            "Kimi open-sources a new open-weight reasoning model",
            "ai_model",
        ),
    ],
)
def test_real_latest_core_model_and_concrete_legal_events_survive(title, reason):
    assert axios.admission_reason(_item(title)) == reason


def test_summary_can_support_but_cannot_invent_title_relevance():
    assert axios.admission_reason(
        _item(
            "Oracle expands data center capacity",
            summary="The new clusters will train artificial intelligence models.",
        )
    ) == "core_infrastructure"
    assert axios.admission_reason(
        _item(
            "A company unveils a plan for next year",
            summary="The chief executive mentioned artificial intelligence once.",
        )
    ) == ""


@pytest.mark.parametrize(
    "title,summary,reason",
    [
        (
            "Nvidia unveils B300 accelerator",
            "It targets AI data centers, PCs and automotive customers.",
            "core_infrastructure",
        ),
        (
            "TSMC expands 2nm chip capacity",
            "It serves smartphones as well as AI accelerators.",
            "core_infrastructure",
        ),
        (
            "CoreWeave raises $4B for GPU clusters",
            "Some customers build healthcare apps.",
            "core_infrastructure",
        ),
        (
            "OpenAI raises $20B for model training",
            "Customers include hospitals and retailers.",
            "ai_business",
        ),
        ("New AI data center opens outside Phoenix", "", "core_infrastructure"),
        ("Nvidia's next AI GPU launches in October", "", "core_infrastructure"),
        ("TSMC's newest 2nm fab opens next year", "", "core_infrastructure"),
        (
            "Congress passes a bill while setting limits on frontier models",
            "",
            "ai_policy",
        ),
        (
            "EU adopts new rules while tightening audits for frontier models",
            "",
            "ai_policy",
        ),
        ("OpenAI releases GPT-10 as benchmark accuracy jumps 30%", "", "ai_model"),
        ("Claude benchmark score rises 18% after architecture update", "", "ai_model"),
        ("GPT-10 inference costs fall 45% after distillation", "", "ai_model"),
        ("CoreWeave commissions a 40,000-GPU cluster", "", "core_infrastructure"),
        ("Oracle leases 30,000 Nvidia GPUs", "", "core_infrastructure"),
        ("DOJ appeals ruling in AI copyright case", "", "ai_policy"),
        ("China abolishes model-registration rule", "", "ai_policy"),
        ("xAI absorbs model-monitoring startup", "", "ai_business"),
        ("Mistral shutters after financing collapses", "", "ai_business"),
        ("CoreWeave reprices long-term GPU contracts", "", "ai_business"),
        ("Sam Altman hands OpenAI CEO role to a successor", "", "ai_business"),
        ("SoftBank writes off half its OpenAI investment", "", "ai_business"),
    ],
)
def test_structural_core_events_survive_without_summary_keyword_overreach(
    title, summary, reason
):
    assert axios.admission_reason(_item(title, summary=summary)) == reason


@pytest.mark.parametrize(
    "title,summary",
    [
        ("Cloud provider launches wellness program for data center staff", ""),
        ("Manufacturer opens daycare beside its AI chip fab", ""),
        ("Vendor signs insurance contract for GPU factory workers", ""),
        ("Operator launches apprenticeship at its new data center", ""),
        ("EU approves farm subsidies alongside debate over proposed AI rules", ""),
        ("France signs trade pact following review of AI chip export restrictions", ""),
        ("California passes budget after lawmakers delay AI bill", ""),
        ("Congress passes budget amid controversy over AI data center permits", ""),
        ("Nvidia jumps 9% as HBM capacity concerns ease", ""),
        ("AMD surges 8% after GPU production outlook improves", ""),
        ("AI payroll assistant suffers outage", ""),
        ("AI email-writing tool has vulnerability", ""),
        ("AI photo editor hacked", ""),
        ("AI parking app suffers breach", ""),
        ("Sam Altman becomes CEO of a tourism startup", ""),
        ("Elon Musk returns as CEO of X", ""),
        ("Jensen Huang named leader of neighborhood association", ""),
        ("Anthropic signs catering contract with Google", ""),
        ("Microsoft renews insurance agreement with OpenAI", ""),
        ("Google partners with Anthropic on employee wellness", ""),
        ("OpenAI buys payroll software from Microsoft", ""),
        ("Footage: Nvidia launches Blackwell Ultra", ""),
        ("Webcast: Sam Altman outlines OpenAI's model roadmap", ""),
        ("Audio: Anthropic releases Claude 7 model", ""),
        ("Gallery: Microsoft opens an AI data center", ""),
        ("Transcript: Lisa Su details AMD's accelerator roadmap", ""),
        (
            "OpenAI releases GPT-Med with diagnostic reasoning benchmark gains",
            "Doctors will deploy it in hospitals.",
        ),
        ("Micron builds a DRAM sculpture for its corporate lobby", ""),
        (
            "The Big Take Workers Are Teaching AI-Powered Robots to Take "
            "Over Their Jobs",
            "The story concerns workplace automation, not a company takeover.",
        ),
        (
            "DWS Shifts AI Fund Bets Into Hyperscalers From Chipmakers",
            "The asset manager is rotating a public-market portfolio.",
        ),
    ],
)
def test_structural_noise_cannot_borrow_core_company_or_infrastructure_terms(
    title, summary
):
    assert axios.admission_reason(_item(title, summary=summary)) == ""


def test_parser_fails_closed_on_challenge_or_changed_dom_but_allows_zero_relevant():
    with pytest.raises(RuntimeError, match="验证页|拦截"):
        axios.parse_search_results(
            "<html><title>Just a moment...</title></html>",
            axios.TOPIC_LABEL,
            axios.LATEST_AI_URL,
        )
    with pytest.raises(RuntimeError, match="DOM|结果链接"):
        axios.parse_search_results(
            "<html><main><h1>Search</h1></main></html>",
            axios.TOPIC_LABEL,
            axios.LATEST_AI_URL,
        )
    noise = _card(
        "City council approves a new downtown park",
        "downtown-park",
        summary="Artificial intelligence was mentioned during public comment.",
        section="Local",
    )
    assert axios.parse_search_results(
        _listing(noise), axios.TOPIC_LABEL, axios.LATEST_AI_URL
    ) == []


def test_parser_refuses_any_listing_other_than_fixed_latest_query():
    html = _listing(_card("OpenAI releases a new model", "openai-model"))
    for wrong in (
        "https://www.axios.com/results?q=artificial%20intelligence&sort=1",
        "https://www.axios.com/results?q=GPU&sort=2",
        "https://example.com/results?q=artificial%20intelligence&sort=2",
    ):
        with pytest.raises(RuntimeError, match="固定 Latest"):
            axios.parse_search_results(html, axios.TOPIC_LABEL, wrong)


def test_persisted_rows_reuse_the_same_admission_gate():
    rows = {
        "good": {
            "article_id": "good",
            "title_en": "OpenAI releases a new reasoning model",
            "url": "https://www.axios.com/2026/09/04/openai-model",
        },
        "bad": {
            "article_id": "bad",
            "title_en": "AI startup shares surge after earnings",
            "url": "https://www.axios.com/2026/09/04/ai-stock",
        },
    }
    assert [row["article_id"] for row in axios.admitted_rows(rows)] == ["good"]


def test_smart_brevity_uses_exact_relative_container_and_dual_threshold():
    assert axios.BODY_SELECTORS == (
        '.gtmView[data-vars-page-type="story"] > div:last-child '
        '> div[data-chromatic="ignore"]',
    )
    assert axios.BODY_PARAGRAPH_SELECTORS == ("p",)
    assert 350 <= axios.MIN_BODY_CHARS < 900
    assert 60 <= axios.MIN_BODY_WORDS <= 100
    assert axios.ALLOW_TRAFILATURA is False

    body = "OpenAI released an AI model for secure data center workloads. " * 12
    before = "Google preferred source illustration caption " * 40
    result = fetch._body_from_html(
        _body_html(body, before=before),
        "https://www.axios.com/2026/09/04/openai-model",
        "OpenAI model",
        axios,
    )
    assert result["extractor"] == "站点容器"
    assert "Google preferred source" not in result["body"]
    assert "Unrelated first child" not in result["body"]
    assert len(result["body"]) >= axios.MIN_BODY_CHARS

    long_but_too_few_words = "infrastructure-development " * 55
    rejected = fetch._body_from_html(
        _body_html(long_but_too_few_words),
        "https://www.axios.com/2026/09/04/short-video",
        "AI video",
        axios,
    )
    assert rejected["body"] == ""
    assert rejected["longest"] >= axios.MIN_BODY_CHARS
    assert rejected["most_words"] < axios.MIN_BODY_WORDS


def test_barrier_before_body_only_flags_an_early_challenge():
    assert axios.barrier_before_body("Just a moment. Verify you are human", "")
    body = "OpenAI model " * 500 + " Access denied was an error message in testing."
    assert not axios.barrier_before_body(body, "OpenAI model")
