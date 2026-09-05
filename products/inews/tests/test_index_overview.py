"""清单页顶上那几行「一眼看懂」的用例。

站长要的是**图形**:库有多大、覆盖到哪、正文取到多少、这一轮干了什么、前几轮
什么时候跑的。数字之外还要有条形/时间轴,因为「47 成功 13 失败」这种一对数字,
比例要人心算 —— 凌晨三点没人会心算。
"""
from __future__ import annotations

from typing import Any

from inews import render


def _rows(n: int = 3) -> list[dict[str, Any]]:
    return [
        {
            "article_id": f"id{i}", "title_en": f"T{i}",
            "url": f"https://www.ft.com/content/{i}",
            "published_at": f"2026-08-1{i}T09:30:00Z",
            "keywords": ["AI chip", "AI jobs"][: 1 + i % 2],
            "body_status": "ok" if i else "failed",
        }
        for i in range(n)
    ]


def _runs() -> list[dict[str, Any]]:
    return [
        {"finished_at": f"2026-08-23T0{h}:00:00+08:00", "ok": True, "new": h,
         "hits": 100 + h, "processed": 20, "body_failed": 1, "backlog": 2482}
        for h in range(3, 9)
    ]


def _html(**kw: Any) -> str:
    base: dict[str, Any] = dict(
        keywords=["AI chip", "AI jobs"], generated_at="2026-08-24T00:13:39+08:00",
        runs=_runs(), new_count=20, body_chars=1_234_567,
    )
    base.update(kw)
    return render.render_index(_rows(), **base)


def test_the_library_band_answers_how_big_and_how_far_back():
    """库有多大、覆盖到哪、多少话题、正文多少字 —— 四件事都要在第一屏。"""
    html = _html()
    assert "库内篇数" in html
    assert "2026-08-10" in html and "2026-08-12" in html, "最早和最新都要写出来"
    assert "话题" in html
    # 123 万字:字数用「万字」而不是 1234567 —— 七位数要人一位一位数。
    assert "123 万字" in html


def test_body_coverage_is_a_bar_not_two_bare_numbers():
    """「取到 2 / 失败 1」的比例要看得见,不是让人心算。"""
    html = _html()
    assert 'class="cover"' in html, "正文覆盖要画成一条堆叠条"
    assert "取正文失败" in html


def test_the_round_band_reports_what_this_round_actually_did():
    """这一轮:命中多少、新增多少、还剩多少要下轮处理。"""
    html = _html()
    assert "最近一轮发现" in html
    assert "当轮正文失败" in html, "历史失败不得写成当前仍失败"
    assert "2482" in html, "积压要写出来 —— 它决定库要多久才追平"


def test_the_last_five_rounds_come_with_bars():
    """五个时间戳排一列还是要人对比。每轮的新增画成条,长短一眼就看出来。"""
    html = _html()
    band = html[html.index("最近"):]
    assert band.count('class="runbar"') == 5


def test_nothing_is_invented_when_there_is_no_run_log():
    """一轮都没跑过时,不许拿 0 冒充「跑过、结果是 0」。"""
    html = _html(runs=[], new_count=None, body_chars=0)
    assert "还没有跑过" in html
    assert "万字" not in html, "没有正文就不要报一个 0 万字"


def test_the_button_asks_the_local_listener_to_actually_run():
    """按钮要真的能让本机跑起来 —— 敲的就是 serve.py 那个口子。"""
    html = _html()
    assert "抓一轮" in html
    assert "127.0.0.1" in html and "/run" in html
    # 监听没开的时候不能装作按成功了:退回到「把命令给你」。
    assert "tools/hourly.sh" in html


def test_coverage_span_is_the_real_earliest_article_not_the_floor():
    """覆盖区间以**真实最早的那篇**为准。

    8-24 站长:「覆盖时间以真实的最早的文章时间为准」。原来那条时间轴左端写的是
    硬地板 2025-01-01 —— 那是「最早允许抓到哪」,不是「实际抓到了哪」。把政策上限
    画成事实,看的人会以为库里真有 2025 年 1 月的稿子。硬地板仍然在后台的
    「进度」卡上,那里明写着「硬地板」。
    """
    html = _html()
    band = html[html.index("原文库"):html.index("最近一轮发现")]
    assert "2025-01-01" not in band, "清单页的覆盖区间不许拿硬地板冒充最早文章"
    assert "2026-08-10" in band, "真实最早那篇的日期要在"
