"""清单页上的两个按钮,以及本机监听怎么认它们。

9-03 站长:「在 bloomberg 的页面上应该有个按钮,就是手动全盘抓取,和手动修复
未抓取连接。」

安全边界照旧、而且必须照旧:监听**只绑回环、只认放行来源、不接受任何参数**。
所以做法不是「给 /run 加个参数」,而是**一张固定的动作表** —— 页面只能从一份
写死的名单里挑一个动作,一个字都拼不出来。多一个站就多一行表,不是多一个参数。
"""
from __future__ import annotations

from typing import Any

from inews import render, serve


def _rows() -> list[dict[str, Any]]:
    return [{
        "article_id": "a", "title_en": "Boehringer Signs Deal for Owkin AI",
        "url": "https://www.bloomberg.com/news/articles/2026-09-02/x",
        "published_at": "2026-09-02T10:00:00Z", "keywords": ["Bloomberg 专题"],
        "body_status": "failed", "body_error": "超时",
    }]


def test_the_actions_table_is_a_closed_list_not_a_parameter():
    """一张写死的表:键是路径,值是那条路径唯一会执行的命令。"""
    for path in (
        "/run", "/run/bloomberg", "/run/cnbc", "/run/wsj",
        "/run/reuters", "/run/axios",
        "/repair", "/repair/bloomberg", "/repair/cnbc", "/repair/wsj",
        "/repair/reuters", "/repair/axios",
    ):
        assert path in serve.ACTIONS
    # 表里每条都得是**具体命令**,不是拼出来的
    for command in serve.ACTIONS.values():
        assert isinstance(command(), list) and command()[0] == "bash"


def test_an_unknown_action_is_refused():
    """表外的路径一律 404 —— 「不认识就拒绝」是这个口子的失败模式。"""
    assert "/run/nikkei" not in serve.ACTIONS
    assert "/repair/../run" not in serve.ACTIONS


def test_each_site_page_points_at_its_own_actions():
    """所有来源各按自己的路径 —— 按钮不许串站。"""
    ft_html = render.render_index(
        _rows(), keywords=["AI chip"], generated_at="now", site_key="ft",
    )
    bb_html = render.render_index(
        _rows(), keywords=[], generated_at="now", site_key="bloomberg",
        site_label="BLOOMBERG.COM", tagline="AI 栏目清单",
    )
    cnbc_html = render.render_index(
        _rows(), keywords=[], generated_at="now", site_key="cnbc",
        site_label="CNBC.COM", tagline="AI 专题文字稿",
    )
    wsj_html = render.render_index(
        _rows(), keywords=[], generated_at="now", site_key="wsj",
        site_label="WSJ.COM", tagline="AI 专题文字稿",
    )
    reuters_html = render.render_index(
        _rows(), keywords=[], generated_at="now", site_key="reuters",
        site_label="REUTERS.COM", tagline="AI 专题文字稿",
    )
    axios_html = render.render_index(
        _rows(), keywords=[], generated_at="now", site_key="axios",
        site_label="AXIOS.COM", tagline="Latest 核心 AI 文字稿",
    )
    assert "127.0.0.1:8787/run\"" in ft_html and "/run/bloomberg" not in ft_html
    assert "/run/bloomberg" in bb_html and "/repair/bloomberg" in bb_html
    assert "/run/cnbc" in cnbc_html and "/repair/cnbc" in cnbc_html
    assert "/run/bloomberg" not in cnbc_html
    assert "/run/wsj" in wsj_html and "/repair/wsj" in wsj_html
    assert "/run/cnbc" not in wsj_html
    assert "/run/reuters" in reuters_html and "/repair/reuters" in reuters_html
    assert "/run/axios" in axios_html and "/repair/axios" in axios_html
    assert "/run/axios" not in reuters_html and "/run/reuters" not in axios_html


def test_the_repair_button_is_there_and_says_what_it_does():
    """「修复未抓取」要能看出它修的是哪几篇 —— 页面上有几篇失败就写几篇。"""
    html = render.render_index(
        _rows(), keywords=[], generated_at="now", site_key="bloomberg",
    )
    assert 'id="repair"' in html
    assert "修复未抓取" in html
    assert "1 篇" in html, "有几篇取正文失败要写在按钮旁边"


def test_a_library_with_nothing_broken_hides_the_repair_button():
    """一篇都没失败时不摆这个按钮:一个按下去什么也不会发生的按钮,
    比没有更糟 —— 它让人以为自己漏做了什么。"""
    clean = [{**_rows()[0], "body_status": "ok", "body_error": ""}]
    html = render.render_index(
        clean, keywords=[], generated_at="now", site_key="bloomberg",
    )
    assert 'id="repair"' not in html
