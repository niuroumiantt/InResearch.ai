"""文章价值评分 v2 的用例。

9-01 站长:「对每一篇收进来的文章进行打分……深度,长度,数据,分析,影响,
独家等等不同的角度」。打分**只标注、不过滤**:分数摆在页面上给人看,
要不要按分数裁,是之后看着数据另做的裁决 —— 这守住了「过滤名单的判据必须是
结构性事实」那条边界:分数不是过滤判据,是站长要求展示的一列信息。

钉住的性质:
- 模型负责六个价值维度，篇幅本身不再加分;
- 模型的回答常带壳(围栏、解释),解析只认第一段 JSON,缺维度如实报错;
- 总分公式写死在代码里，主题中心度与事件性拥有硬门槛;
- 一篇失败不带走整批,原话留在 ``score_error``;
- 清单标题后显示分数,正文页在正文**之前**显示评分依据。
"""
from __future__ import annotations

import pytest

from inews import ledger as ledger_store
from inews import render
from inews import score


# ---------------- 解析与公式 ----------------


def test_parse_accepts_a_wrapped_json_reply():
    reply = (
        "好的,以下是评分:\n```json\n"
        '{"centrality": 9, "event": 7, "impact": 8, "evidence": 6,'
        ' "originality": 5, "timeliness": 9, "notes": "核心在写 AI 资本开支"}\n```'
    )
    detail, notes = score._parse_reply(reply)
    assert detail["centrality"] == 9
    assert notes == "核心在写 AI 资本开支"


def test_parse_clamps_out_of_range_values_instead_of_trusting_them():
    reply = '{"centrality": 15, "event": -3, "impact": 7, "evidence": 6, "originality": 5, "timeliness": 9, "notes": "x"}'
    detail, _notes = score._parse_reply(reply)
    assert detail["centrality"] == 10
    assert detail["event"] == 0


def test_parse_refuses_a_reply_missing_a_dimension():
    """缺一维就如实失败,不拿 0 分冒充「模型判了 0 分」。"""
    with pytest.raises(RuntimeError):
        score._parse_reply('{"relevance": 9, "notes": "只有一维"}')


def test_length_is_not_a_score_dimension_any_more():
    assert all(name != "length" for name, _label, _weight in score.DIMENSIONS)
    assert "篇幅本身不加分" in score.SYSTEM_PROMPT


def test_composite_weights_centrality_and_event_and_caps_weak_articles():
    top = {name: 10 for name, _label, _weight in score.DIMENSIONS}
    assert score.composite(top) == 100
    zero = {name: 0 for name, _label, _weight in score.DIMENSIONS}
    assert score.composite(zero) == 0
    assert score.composite(dict(zero, centrality=10)) == 30
    otherwise_high = dict(top, centrality=5)
    assert score.composite(otherwise_high) == 49
    assert score.composite(dict(top, event=3)) == 64


def test_the_prompt_pins_dimensions_and_json_only():
    """提示词要点名每个维度、并要求只输出 JSON —— 少了后者,解释就会混进来。"""
    for name, _label, _weight in score.DIMENSIONS:
        assert name in score.SYSTEM_PROMPT
    assert "JSON" in score.SYSTEM_PROMPT
    assert "notes" in score.SYSTEM_PROMPT


# ---------------- 整批打分 ----------------


def _row(article_id: str = "aaaa", **extra) -> dict:
    return {
        "article_id": article_id,
        "title_en": "Nvidia becomes the bank of AI",
        "url": "https://www.ft.com/content/" + article_id,
        "published_at": "2026-08-30T00:00:00Z",
        "keywords": ["Nvidia"],
        "body": "正文" * 400,
        **extra,
    }


def _fake_score_one(row, creds=None):
    return {
        "score": 82,
        "score_version": score.VERSION,
        "score_detail": {"centrality": 9, "event": 8, "impact": 7,
                         "evidence": 8, "originality": 5, "timeliness": 9},
        "score_notes": "核心在写 AI 资本开支",
    }


def test_fill_scores_only_touches_rows_with_body_and_without_score():
    rows = [
        _row("aaaa"),
        _row("bbbb", body="", body_error="拦截页"),
        _row("cccc", score=90, score_version=score.VERSION),
    ]
    done = score.fill_scores(rows, score_one=_fake_score_one)
    assert done == 1
    assert rows[0]["score"] == 82
    assert "score" not in rows[1]
    assert rows[2]["score"] == 90


def test_a_failed_score_keeps_its_words_and_spares_the_batch():
    def explode(row, creds=None):
        if row["article_id"] == "aaaa":
            raise RuntimeError("Cloudflare 返回 429:额度用完")
        return _fake_score_one(row)

    rows = [_row("aaaa"), _row("bbbb")]
    done = score.fill_scores(rows, score_one=explode)
    assert done == 1
    assert "429" in rows[0]["score_error"]
    assert rows[1]["score"] == 82


# ---------------- 台账 ----------------


def test_the_ledger_keeps_the_score_and_its_reasons():
    entries: dict = {}
    ledger_store.record(entries, [_row("aaaa", **_fake_score_one(None))],
                        crawled_at="2026-09-01T00:00:00Z")
    entry = entries["aaaa"]
    assert entry["score"] == 82
    assert entry["score_version"] == score.VERSION
    assert entry["score_detail"]["centrality"] == 9
    assert entry["score_notes"] == "核心在写 AI 资本开支"
    (row,) = ledger_store.rows(entries)
    assert row["score"] == 82 and row["score_notes"]


# ---------------- 页面 ----------------


def test_the_index_shows_the_score_right_after_the_title():
    scored = _row("aaaa", title_zh="Nvidia 成了 AI 的银行", **_fake_score_one(None))
    plain = _row("bbbb", title_zh="没有分的那篇")
    html = render.render_index([scored, plain], keywords=[], generated_at="now")
    assert 'class="score"' in html
    assert ">82<" in html
    # 没分的那行不挂空分数
    assert html.count('class="score"') == 1


def test_the_article_page_puts_the_reasons_before_the_body():
    row = _row("aaaa", title_zh="Nvidia 成了 AI 的银行", **_fake_score_one(None))
    html = render.render_article(row)
    assert "评分依据" in html
    assert "核心在写 AI 资本开支" in html
    assert html.index("评分依据") < html.index("正文正文")
    # 各维度的中文名要在页面上 —— 一个裸数字解释不了自己
    for _name, label, _weight in score.DIMENSIONS:
        assert label in html


def test_the_article_headline_is_chinese_with_the_original_below():
    row = _row("aaaa", title_zh="Nvidia 成了 AI 的银行")
    html = render.render_article(row)
    assert "<h1>Nvidia 成了 AI 的银行</h1>" in html
    assert "Nvidia becomes the bank of AI" in html
    # 没有译文就用原题,不留空 <h1>
    bare = render.render_article(_row("bbbb"))
    assert "<h1>Nvidia becomes the bank of AI</h1>" in bare


def test_parse_ignores_a_thinking_block_even_one_with_braces():
    """Qwen3 的 <think> 段里常有花括号草稿 —— 解析必须跳过思考段,
    只认思考之后的那段 JSON。"""
    reply = (
        '<think>先草拟 {"centrality": 1} 再想想……</think>\n'
        '{"centrality": 9, "event": 7, "impact": 8, "evidence": 6,'
        ' "originality": 5, "timeliness": 9, "notes": "核心在写 AI"}'
    )
    detail, notes = score._parse_reply(reply)
    assert detail["centrality"] == 9
    assert notes == "核心在写 AI"


def test_an_exhausted_quota_stops_the_whole_batch():
    """429「额度用完」再问一百遍还是 429 —— 当轮剩下的不再尝试,
    没试过的行保持干净(不给它们抄一句它们没收到过的失败原话)。"""
    calls = []

    def quota(row, creds=None):
        calls.append(row["article_id"])
        raise RuntimeError(
            'Cloudflare 返回 429:{"errors":[{"message":"AiError: you have used up '
            "your daily free allocation of 10,000 neurons\",\"code\":4006}]}"
        )

    rows = [_row("aaaa"), _row("bbbb")]
    done = score.fill_scores(rows, score_one=quota)
    assert done == 0
    assert calls == ["aaaa"]
    assert "free allocation" in rows[0]["score_error"]
    assert "score_error" not in rows[1]


def test_parse_accepts_an_already_structured_reply():
    """9-01 实测:Workers AI 对 qwen3 会把模型的 JSON 输出**解析好再给我们**
    (result.response 直接是个对象,不是字符串)。把它 str() 成 Python 字典
    的样子再当 JSON 读,一定失败 —— 结构化的回答直接收下,照样验维度、收界。"""
    reply = {"centrality": 15, "event": 7, "impact": 8, "evidence": 6,
             "originality": 5, "timeliness": 9, "notes": "核心在写 AI"}
    detail, notes = score._parse_reply(reply)
    assert detail["centrality"] == 10
    assert notes == "核心在写 AI"


# ---------------- 低分折叠 ----------------


def test_low_scores_fold_by_default_with_a_way_back():
    """9-01 站长:「让我们低分折叠吧」。照「仅提及」那套:默认藏、勾一下回来,
    **藏不是删**。阈值 60 来自当天页面上的实际分布:清晰的垃圾都 ≤51,
    正稿都 ≥74,60 落在沟里。"""
    assert render.LOW_SCORE_THRESHOLD == 60
    low = _row("aaaa", **{**_fake_score_one(None), "score": 41})
    high = _row("bbbb", **_fake_score_one(None))
    html = render.render_index([low, high], keywords=[], generated_at="now")
    assert 'data-low="1"' in html
    assert html.count('data-low="1"') == 1
    assert 'id="lowscores"' in html
    assert "显示低分" in html
    assert "lowscores" in render._FILTER_JS


def test_an_unscored_row_is_not_treated_as_low():
    """没打过分和低分是两回事 —— 没有分的行不折叠。"""
    plain = _row("cccc")
    html = render.render_index([plain], keywords=[], generated_at="now")
    assert 'data-low="1"' not in html
