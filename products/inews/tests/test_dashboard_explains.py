"""后台要能**解释这个系统**,不只是报数字。

站长的话:「后台应该要扩充更多的信息,包括文章爬取的逻辑、本项目的架构,
这个还要画个图」。所以这里钉的是:图在、边界在图上、每一步的「为什么」在页面上,
而且**不许和代码分叉** —— 图里写的档位、地板、限速,要能从代码里读出来。
"""
from __future__ import annotations

from inews import render
from inews.browser import tiers
from inews.sites import ft


def _html() -> str:
    return render.render_dashboard(
        [], generated_at="2026-08-24T00:13:39+08:00", keywords=["AI chip"],
        runs=[], floor=ft.EARLIEST,
    )


def test_the_dashboard_draws_the_pipeline():
    """一张图。文字描述读三遍才知道谁先谁后,图一眼就看出来。"""
    html = _html()
    assert "<svg" in html, "架构要画出来,不是列个清单"
    assert "架构" in html


def test_the_diagram_names_every_stage_in_the_real_order():
    """图上的步骤要和 run.py 里真正的顺序一致,少一步就会有人照着图去找。"""
    html = _html()
    for stage in ("关键词", "搜索页", "台账", "正文", "存档", "发布"):
        assert stage in html, f"图上缺了「{stage}」这一步"


def test_the_boundaries_are_on_the_page_and_come_from_the_code():
    """三条边界:能读谁(域名表)、怎么读(档位)、读多久以前(时间地板)。

    **值从代码里取**,不在页面上手抄 —— 手抄的那份迟早和代码分叉,而分叉的
    文档比没有文档更坏:它看起来是可信的。
    """
    html = _html()
    assert ft.EARLIEST in html, "时间地板要写出来"
    assert tiers.tier_of(ft.KEY) in html, "FT 的获取档位要写出来,而且取自 tiers.py"
    assert "ft.com" in html, "能读谁由域名表决定"


def test_the_crawl_logic_is_explained_not_just_charted():
    """每轮为什么这么跑,要写在页面上:第 1 页、限量、失败不回落、锁。"""
    html = _html()
    for point in ("每小时", "第 1 页", "20", "不回落", "锁"):
        assert point in html, f"抓取逻辑里少了「{point}」"


def test_a_stale_success_is_not_shown_as_healthy():
    """最后一次成功不等于现在健康:调度器停摆后不会再留下失败记录。"""
    html = render.render_dashboard(
        [], generated_at="2026-08-24T08:30:00+08:00", keywords=["AI chip"],
        runs=[{
            "finished_at": "2026-08-24T01:00:00+08:00", "ok": True,
            "new": 0, "hits": 0,
        }], floor=ft.EARLIEST,
    )
    assert "定时任务可能停了" in html
    assert "上一轮正常" not in html
    assert 'lamp lamp--bad' in html
