"""后台是**这个库**的后台,页眉是**整个项目**的导航。

9-03 站长打开 `/rawarticle/bloomberg/dashboard.html`,看到的却是「FT.COM · 后台」,
连「45 个词 · 8 个语义组」「sites/ft.py」「每轮限 20 篇」都照抄了 FT ——
Bloomberg 一个关键词都没有。多了第二个库之后,这一页整页都在说谎。

站长两条:
1. 「还是只针对 ft.com 的,我们现在有了更多的页面,应该是跨页面的分析」;
2. 「页眉,目录不清晰无逻辑,要能体现到每个单独的页面,也要有跨页面,
   而且各种跳转的选择也要有」。

于是:
- 后台每一句话都从**站点词汇表**来,没有一个站名是写死的;
- 后台多一张跨库对比(数据由编排层从盘上读好再交进来 —— render 仍然不碰盘);
- 页眉分两层:上层选库(时间线 / 各库),下层选这个库里的页面(清单 / 后台)。
"""
from __future__ import annotations

from typing import Any

from inews import render
from inews.sites import bloomberg, ft


def _rows() -> list[dict[str, Any]]:
    return [{
        "article_id": "a", "title_en": "Boehringer Signs Deal for Owkin AI",
        "url": "https://www.bloomberg.com/news/articles/2026-09-02/x",
        "published_at": "2026-09-02T10:00:00Z", "keywords": ["Bloomberg 专题"],
        "body": "正文" * 400, "body_status": "ok",
    }]


def _dash(site) -> str:
    return render.render_dashboard(
        _rows(), generated_at="2026-09-03T09:14:09+08:00",
        keywords=[] if site is bloomberg else ["AI chip"],
        runs=[{"finished_at": "2026-09-03T09:00:00+08:00", "ok": True,
               "hits": 94, "new": 0}],
        site=site,
    )


# ---------------- 后台不许再说别的站的事 ----------------


def test_the_dashboard_names_the_library_it_belongs_to():
    assert "BLOOMBERG.COM · 后台" in _dash(bloomberg)
    assert "FT.COM · 后台" in _dash(ft)


def test_a_keywordless_library_never_claims_to_have_keywords():
    """Bloomberg 没有关键词。流程图第一格是「栏目页」,不是「45 个词 · 8 个语义组」。"""
    html = _dash(bloomberg)
    assert "语义组" not in html
    assert "sites/bloomberg.py" in html and "sites/ft.py" not in html
    assert "栏目页" in html


def test_the_architecture_facts_come_from_the_site_vocabulary():
    """能读谁 / 怎么读 / 读到多早 —— 三条都得是这个站自己的事实。"""
    html = _dash(bloomberg)
    assert "bloomberg.com" in html and "ft.com" not in html
    assert bloomberg.EARLIEST in html


def test_the_crawl_logic_panel_quotes_this_sites_own_rules():
    """「抓取逻辑」= 这个站声明的规则 + 全项目通用的那几条纪律。
    通用的(失败留原话、不猜时间)两个站都该有;站点那几条不许串。"""
    bb, ft_html = _dash(bloomberg), _dash(ft)
    assert bloomberg.RULES[0] in bb and bloomberg.RULES[0] not in ft_html
    assert ft.RULES[0] in ft_html and ft.RULES[0] not in bb
    for shared in ("失败留原话", "不猜时间"):
        assert shared in bb and shared in ft_html


# ---------------- 跨库对比 ----------------


def test_the_dashboard_compares_every_library_when_given_the_numbers():
    """跨库那张牌的数据由编排层从盘上读好交进来 —— render 不碰盘(模块开头的约定)。"""
    html = render.render_dashboard(
        _rows(), generated_at="now", keywords=[], runs=[], site=bloomberg,
        libraries=[
            {"label": "FT.COM", "key": "ft", "articles": 448, "with_body": 430,
             "failed": 3, "last_at": "2026-09-03T09:17:46+08:00", "last_new": 1},
            {"label": "BLOOMBERG.COM", "key": "bloomberg", "articles": 97,
             "with_body": 97, "failed": 0,
             "last_at": "2026-09-03T09:14:09+08:00", "last_new": 0},
        ],
    )
    assert "跨库" in html
    for token in ("FT.COM", "BLOOMBERG.COM", "448", "97"):
        assert token in html
    # 当前这一库要标出来:同一张表上「我在哪」不该靠数
    assert 'class="me"' in html


def test_a_library_with_no_local_data_says_so_instead_of_showing_zero():
    """读不到姊妹库的盘就如实说读不到 —— 一个假的 0 会让人以为那边停了。"""
    html = render.render_dashboard(
        _rows(), generated_at="now", keywords=[], runs=[], site=bloomberg,
        libraries=[{"label": "FT.COM", "key": "ft", "missing": True}],
    )
    assert "本机没有这一库的数据" in html


def test_cross_library_table_exposes_coverage_backlog_and_health():
    html = render.render_dashboard(
        _rows(), generated_at="now", keywords=[], runs=[], site=bloomberg,
        libraries=[{
            "label": "FT.COM", "key": "ft", "articles": 100,
            "with_body": 92, "failed": 3, "backlog": 5,
            "last_at": "2026-09-03T09:17:46+08:00", "last_new": 2,
            "last_ok": False,
        }],
    )
    for token in ("正文覆盖", "92%", "积压", "失败"):
        assert token in html
    assert 'class="table-scroll"' in html


# ---------------- 页眉:两层导航 ----------------


def _nav(html: str) -> str:
    return html[html.index('class="console"'):html.index("</header>")]


def test_the_header_has_a_library_row_and_a_page_row():
    """上层选库、下层选页 —— 「清单」和「FT.COM」平铺在一行里是 9-03 之前那版
    最让人迷惑的地方:一个是页面,一个是另一个库,却长得一模一样。"""
    nav = _nav(render.render_index(
        _rows(), keywords=[], generated_at="now", site_key="bloomberg",
        site_label="BLOOMBERG.COM",
    ))
    assert 'class="tabs tabs--sites"' in nav and 'class="tabs tabs--pages"' in nav
    # 上层:主站 + 每一个库,当前库标出来
    assert "https://inews.today/" in nav
    assert "FT.COM" in nav and "BLOOMBERG.COM" in nav
    sites_row = nav[nav.index("tabs--sites"):nav.index("tabs--pages")]
    assert 'aria-current="true"' in sites_row, "当前在哪个库要标出来"
    # 下层:这个库自己的页面,当前页标出来
    pages_row = nav[nav.index("tabs--pages"):]
    assert "清单" in pages_row and "后台" in pages_row
    assert 'aria-current="page"' in pages_row


def test_article_pages_keep_both_rows_reachable():
    """正文页回本库清单，后台则统一进入跨来源单页。"""
    html = render.render_article(
        {**_rows()[0], "published_at": "2026-09-02T10:00:00Z"},
        site_label="BLOOMBERG.COM", site_key="bloomberg",
    )
    nav = _nav(html)
    assert 'href="../../index.html"' in nav
    assert 'href="https://inews.today/rawarticle/dashboard/"' in nav
    # 姊妹库是绝对地址,不受层数影响
    assert "https://inews.today/rawarticle/ft/index.html" in nav
