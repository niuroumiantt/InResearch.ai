"""清单页每一行长什么样,以及一页放多少条。

8-24 站长两条:
1. 「一页显示所有文章太长了」—— 160 篇一条长卷,滚到底要十几屏。
2. 「把 AI search / FT 专题 / FT.COM ↗ 放在第一行的右边,省一些空间;
   标题请用不同的颜色。」
"""
from __future__ import annotations

from typing import Any

from inews import render, sites


def _rows(n: int) -> list[dict[str, Any]]:
    return [
        {"article_id": f"id{i}", "title_en": f"Headline {i}", "title_zh": f"中文标题 {i}",
         "url": f"https://www.ft.com/content/{i}",
         "published_at": f"2026-08-{10 + i % 12:02d}T09:30:00Z",
         "keywords": ["AI chip"], "body_status": "ok"}
        for i in range(n)
    ]


def _html(n: int = 160) -> str:
    return render.render_index(_rows(n), keywords=["AI chip"], generated_at="now")


def test_the_page_offers_25_50_100_and_everything():
    """每页多少条要能选。**「全部」也留着** —— 想 Ctrl-F 搜整库时分页是碍事的。"""
    html = _html()
    for size in ("25", "50", "100", "全部"):
        assert size in html
    assert 'id="pagesize"' in html


def test_fifty_is_the_default():
    """默认 50:两三次滚动能扫完一天多的量,又不像 25 那样频繁翻页。"""
    html = _html()
    picker = html[html.index('id="pagesize"'):]
    chunk = picker[: picker.index("</select>")]
    assert 'value="50" selected' in chunk


def test_every_row_is_still_in_the_html():
    """**分页在浏览器本地做,全部行都在 HTML 里。**

    静态站没有服务端翻页;更重要的是,搜索框和筛选要能搜到全库 —— 如果只把
    当前页写进 HTML,筛选就会变成「只在这 50 条里筛」,那是另一件事,而且它
    看起来和「库里就这么多」一模一样。
    """
    html = _html(160)
    assert html.count('class="row"') == 160


def test_the_pager_says_which_page_you_are_on():
    """页码要写出来:只有「上一页/下一页」的话,人不知道自己在哪、还有多少。"""
    html = _html()
    assert 'class="pager"' in html
    assert 'id="pageinfo"' in html


def test_tags_and_source_sit_on_the_headline_row():
    """关键词和来源挪到标题那一行的右边 —— 它们原来自己占一行,白吃一行高度。"""
    html = _html(1)
    row = html[html.index('class="row"'):]
    row = row[: row.index("</div></div>")]
    head = row[row.index('class="story"'):]
    # 标题和 meta 在同一层里,meta 紧跟标题(靠 CSS 推到右边)
    assert head.index('class="headline"') < head.index('class="meta"')
    assert 'class="titlerow"' in head, "标题那一行要有自己的容器,才推得动右边那组"


def test_each_library_links_its_siblings_in_the_tab_bar():
    """所有来源的清单要能互相跳,不必回时间线绕路。

    9-03 页眉改成两层之后,姊妹库住在**上层**那一行:上层选库、下层选页。
    姊妹库走绝对地址 —— 产出挂在 /rawarticle/<站>/ 下,相对路径爬不回站点根。
    """
    def sites_row(html: str) -> str:
        row = html[html.index('tabs--sites'):]
        return row[: row.index("</nav>")]

    for current in sites.REGISTRY.values():
        row = sites_row(render.render_index(
            _rows(1), keywords=[], generated_at="now", site_key=current.KEY,
            site_label=current.LABEL, tagline=current.TAGLINE,
        ))
        for sibling in sites.REGISTRY.values():
            assert (
                f"https://inews.today/rawarticle/{sibling.KEY}/index.html" in row
            )
            assert sibling.LABEL in row
        # 当前这个库也在这一行里,但要被标出来(不是靠「不出现」来区分)
        assert 'aria-current="true"' in row


def test_the_headline_has_its_own_colour():
    """标题用不同颜色:一眼分得清「标题」和「原题 / 标签」这两层。"""
    css = render.STYLESHEET
    rule = css[css.index(".headline {"):]
    rule = rule[: rule.index("}")]
    assert "color:" in rule, "标题要有自己的颜色,不跟正文同色"


def test_the_nav_treats_both_sites_as_one_project():
    """几个 repo,一个项目。**导航就得长在一起**,不是一个角落里的小链接。

    2026-08-24 站长:「我需要这两个集合成一个页面,可以有按钮点击跳转的」。
    9-03 又提:「目录不清晰无逻辑,要能体现到每个单独的页面,也要有跨页面」——
    于是分两层:上层是主站与各库(跨页面),下层是这个库自己的页面。
    """
    html = _html(1)
    header = html[html.index('class="console"'):html.index("</header>")]
    assert "https://inews.today/" in header, "主站要在导航里"
    assert "时间线" in header
    # 本库两页在下层,当前页标出来
    pages = header[header.index("tabs--pages"):]
    assert "清单" in pages and "后台" in pages
    assert 'aria-current="page"' in pages
