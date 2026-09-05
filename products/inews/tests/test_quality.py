"""Bloomberg 式编辑准入：标题主题 + 具体事件，正文只作补证。"""
from __future__ import annotations

import pytest

from inews import quality, render, run
from inews.sites import bloomberg, ft


def verdict(title: str, *, keywords=(), body="", origins=()):
    row = {
        "article_id": "x", "url": "u", "title_en": title,
        "keywords": list(keywords), "body": body, "origins": list(origins),
    }
    return quality.assess(
        row,
        topic_labels={ft.TOPIC_LABEL, *ft.HUB_LABELS.values()},
        hub_tiers=ft.HUB_TIERS,
    )


@pytest.mark.parametrize(("title", "keywords"), [
    ("Vulnerable Republicans urge Trump to unleash Maga Inc’s $400mn cash pile",
     ("AI copyright", "AI data centre", "OpenAI")),
    ("FTAV’s further reading", ("deepfake",)),
    ("Fantasy M&A: the recipe for a European champion", ("China AI",)),
    ("What the Indiana state fair reveals about Trump’s America",
     ("AI data centre", "AI jobs")),
    ("How finance redeemed itself", ("Nvidia",)),
    ("Harry and Meghan — are you ready for the sequel?", ("OpenAI",)),
])
def test_full_text_hits_without_title_or_body_evidence_are_quarantined(title, keywords):
    assert verdict(title, keywords=keywords)["quality_status"] == quality.UNVERIFIED


def test_ai_as_a_stock_explanation_is_secondary_even_when_the_title_says_ai():
    result = verdict(
        "Activist pushes EPAM Systems for buybacks as AI hits its shares",
        keywords=("enterprise AI",),
    )
    assert result["quality_status"] == quality.SECONDARY
    assert "股价" in result["quality_reason"]


def test_an_ai_question_is_analysis_not_core_event_news():
    result = verdict("Could AI revive the socialist dream?", keywords=("AI agent",))
    assert result["quality_status"] == quality.SECONDARY


def test_a_long_roundup_cannot_pass_on_five_semiconductor_mentions():
    paragraphs = ["Japan and Taiwan discuss bonds."] * 24 + [
        "The semiconductor sector was also discussed."
    ] * 5
    result = verdict(
        "Japan-Taiwan bonds and a tariff refund boost",
        keywords=("AI chip", "China AI", "Nvidia", "TSMC", "semiconductor"),
        body="\n\n".join(paragraphs),
    )
    assert result["topic_share"] < 20
    assert result["quality_status"] == quality.OFF_TOPIC


def test_actor_plus_ai_topic_plus_action_is_core_before_body_arrives():
    result = verdict("Anthropic launches a new enterprise AI agent", keywords=("Anthropic",))
    assert result["quality_status"] == quality.CORE
    assert result["title_strength"] == 2 and result["event_signal"] is True


def test_a_strong_body_can_rescue_an_editorial_ai_hub_headline():
    body = "AI labs announced the project.\n\nAI models are central.\n\nThe company will deploy AI."
    result = verdict(
        "Company launches a new research project",
        keywords=(ft.HUB_LABELS["artificial-intelligence"],),
        body=body,
        origins=({"kind": "hub", "name": "artificial-intelligence"},),
    )
    assert result["quality_status"] == quality.CORE


def test_bloomberg_ai_hub_remains_the_trusted_reference_set():
    row = {
        "title_en": "Why the next decade will look different", "keywords": [bloomberg.TOPIC_LABEL],
        "origins": [{"kind": "hub", "name": "ai"}],
    }
    result = quality.assess(
        row, topic_labels={bloomberg.TOPIC_LABEL}, hub_tiers=bloomberg.HUB_TIERS,
    )
    assert result["quality_status"] == quality.CORE


def test_non_core_rows_are_in_html_but_hidden_by_default():
    row = {
        "article_id": "x", "url": "u", "title_en": "FTAV’s further reading",
        "published_at": "2026-09-03T00:00:00Z", "keywords": ["deepfake"],
        **verdict("FTAV’s further reading", keywords=("deepfake",)),
    }
    html = render.render_index([row], keywords=["deepfake"], generated_at="now")
    assert 'data-quality="unverified"' in html
    assert 'id="secondary"' in html
    assert html.count('class="row"') == 1
    assert "待验证" in html


def test_legacy_ft_provenance_is_recovered_without_guessing_the_hub():
    entries = {
        "x": {"keywords": ["OpenAI", ft.TOPIC_LABEL]},
        "y": {"keywords": [ft.HUB_LABELS["semiconductors"]]},
    }
    assert run.backfill_provenance(entries, site=ft) == 2
    assert {"kind": "search", "name": "OpenAI"} in entries["x"]["origins"]
    assert {"kind": "hub", "name": "__legacy__"} in entries["x"]["origins"]
    assert "FT 专题（历史未区分）" in entries["x"]["keywords"]
    assert {"kind": "hub", "name": "semiconductors"} in entries["y"]["origins"]


def test_single_hub_legacy_label_can_be_recovered_exactly():
    entries = {"x": {"keywords": [bloomberg.TOPIC_LABEL]}}
    run.backfill_provenance(entries, site=bloomberg)
    assert entries["x"]["origins"] == [{"kind": "hub", "name": "ai"}]
