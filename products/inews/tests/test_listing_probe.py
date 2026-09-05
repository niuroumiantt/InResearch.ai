"""列表页「渲染好了没有」那道门的用例。

2026-08-23 站长的日志里,同一轮里反复出现:

    「AI chatbot」第 1 页失败:… links=112,roots=1,stable=35,onPage=true

`settle_polls` 对 FT 是默认的 1,所以 WAIT 文案里报出来的四项**全部满足**,
页面却一直等到超时 —— 也就是说,真正没过的那一条**根本没有被报出来**。
只剩两条没报:`document.readyState==='complete'` 和拦截页 `wall`。

这里钉两件事:
1. WAIT 文案要报出**每一个**参与判定的量。少报一条,读日志的人就只能靠猜。
2. 整页 `readyState` 不再是硬条件。它说的是子资源(广告、埋点、长连接)加载完,
   FT 搜索页上可能永远不到;而「文章链接集合连续 N 轮不变」才是列表渲染好了的
   结构性证据。
"""
from __future__ import annotations

from inews.browser import contract


def _script(settle: int = 1) -> str:
    return contract.listing_probe_script(
        link_pattern=r"/content/", container_selector=".search-results",
        link_selector="a[href]", settle_polls=settle,
        url="https://www.ft.com/search?q=AI",
    )


def test_wait_text_reports_every_condition_that_can_hold_it_back():
    """报了 links/roots/stable/onPage 却不报 readyState 和 wall,就是这次误诊的成因。"""
    script = _script()
    wait = script[script.index("'WAIT"):]
    for name in ("links=", "roots=", "stable=", "onPage=", "wall=", "readyState="):
        assert name in wait, f"WAIT 文案里必须报出 {name}"


def test_cloudflare_interstitial_is_reported_as_a_human_check():
    """Axios 的 Just a moment 不能只表现成 links=0 的神秘超时。"""
    script = _script()
    assert "just a moment" in script
    assert "verify (?:that )?you are human" in script


def test_wait_text_says_how_many_stable_polls_are_still_needed():
    """`stable=35` 单独看不出是多还是少 —— 要和它此刻需要达到的值一起报。"""
    wait = _script(2)[_script(2).index("'WAIT"):]
    assert "+'/'+" in wait or "/'+need" in wait, "stable 要报成「已达/需要」"


def test_full_page_load_is_not_a_hard_condition():
    """`readyState==='complete'` 不许再出现在 ready 的合取里。

    它是整页子资源加载完的信号,不是「搜索结果渲染好了」的信号。
    """
    script = _script()
    ready = script[script.index("const ready="):script.index("return ready")]
    assert "readyState" not in ready, "readyState 不该再决定 ready,只该决定要等多久"


def test_scrolling_is_off_unless_a_site_asks_for_it():
    """FT 搜索页有真分页,列表不靠滚动加长 —— 默认不滚,老站不许被波及。"""
    assert "scrollTo" not in _script()


def test_a_scrolling_probe_scrolls_until_the_river_stops_growing():
    """9-02 实测:/ai 页的「More AI news」是懒加载的河 —— 初始 HTML 只有一屏
    22-25 条,两天里五六十篇里的大多数从未进入视野(命中数每轮钉死在一屏,
    9-01 已沉到河下面的稿子再也收不到)。滚到底、等链接集合不再增长,
    是把河收完的唯一结构性判据 —— 恰好就是既有 stable 机制的自然延伸。"""
    script = contract.listing_probe_script(
        link_pattern=r"/news/", container_selector="",
        link_selector="a[href]", settle_polls=1,
        url="https://www.bloomberg.com/ai", scroll=True,
    )
    assert "scrollTo" in script
    # 滚动有上限:默认 45 秒超时、一轮约一秒,不设上限的话一条真正无底的河
    # 会把每一轮都拖到超时失败 —— 比少收更糟。上限要真的进到脚本里。
    assert str(contract.LISTING_SCROLL_CAP) in script
    # 滚动触发的加载是异步的:settle_polls=1 会把「下一批还没落地」误判成
    # 「到底了」。滚动时稳定期要被抬高到 SCROLL_SETTLE_POLLS。
    assert contract.SCROLL_SETTLE_POLLS > 1
    assert (
        str(contract.settle_target(contract.SCROLL_SETTLE_POLLS, page_complete=True))
        in script
    )
    # 滚了几轮也是参与判定的量,WAIT 文案要报 —— 少报一条,读日志的人就只能靠猜。
    wait = script[script.index("'WAIT"):]
    assert "scrolls=" in wait


def test_a_page_that_never_finishes_loading_must_settle_for_longer():
    """放宽不等于取消:整页没加载完时,要用更长的稳定期换掉那条硬条件。"""
    assert contract.settle_target(1, page_complete=True) == 1
    assert contract.settle_target(1, page_complete=False) > 1
    assert contract.settle_target(1, page_complete=False) >= 4
    # 传 0 或负数也不能变成「不用等」:一轮都不等就会收走半渲染的第一帧。
    assert contract.settle_target(0, page_complete=True) == 1
    # 两个阈值都要真的进到脚本里,否则 Python 这边算得再对也没人用。
    script = _script(2)
    assert str(contract.settle_target(2, page_complete=True)) in script
    assert str(contract.settle_target(2, page_complete=False)) in script


def test_clicking_load_more_is_off_unless_a_site_declares_the_button():
    """FT 没有「Load more」——不声明就一次也不点,老站不许被波及。"""
    assert "click()" not in _script()


def test_a_declared_load_more_button_gets_clicked_until_the_list_is_exhausted():
    """9-03 站长截图:/ai 页「More AI news」末尾是一个 **Load more 按钮**,
    不是无限滚动 —— 滚多少次都不会有新条目(9-02 那版滚动修法因此无效)。

    按钮的类名是构建时哈希出来的(styles_itemLink__VgyXJ 这种),类选择器
    随一次发布就失效;按**可见文字**认才是稳的。
    """
    script = contract.listing_probe_script(
        link_pattern=r"/news/", container_selector="",
        link_selector="a[href]", settle_polls=1,
        url="https://www.bloomberg.com/ai", load_more_text="load more",
    )
    assert "load more" in script and "click()" in script
    # 点击有上限:一轮 45 秒的预算里,不设上限的话一条长河会把每轮拖到超时失败。
    assert str(contract.LOAD_MORE_CLICK_CAP) in script
    # 点完要等这一批真的落地再点下一次,否则就是对着按钮猛敲。
    assert f"stable>={contract.SCROLL_SETTLE_POLLS}" in script
    assert "clickedSignature=signature" in script
    assert "clickedSignature!==signature" in script
    assert "!waitingForChange" in script
    # 点了几次是参与判定的量,WAIT 文案要报 —— 少报一条,读日志的人只能靠猜。
    wait = script[script.index("'WAIT"):]
    assert "clicks=" in wait
    assert "awaiting=" in wait


def test_load_more_waits_for_a_new_link_signature_before_clicking_again():
    """同一批链接没落地前,增长中的 stable 不能触发第二次点击。

    按钮消失或达到点击上限时仍沿用原有完成语义。
    """
    script = contract.listing_probe_script(
        link_pattern=r"/news/", container_selector="",
        link_selector="a[href]", settle_polls=1,
        url="https://www.bloomberg.com/ai", load_more_text="load more",
    )
    guard = script[
        script.index("let clickedSignature="):script.index("const expanded=")
    ]
    assert "old.clickedSignature" in guard
    assert "clickedSignature!==signature" in guard
    assert f"stable>={contract.SCROLL_SETTLE_POLLS}&&!waitingForChange" in guard
    assert guard.index("clickedSignature!==signature") < guard.index("moreBtn.click()")
    assert "clickedSignature=signature;clickWaits=0;waitingForChange=true" in guard
    assert (
        "const expanded=!moreBtn||(clicks>="
        f"{contract.LOAD_MORE_CLICK_CAP}&&!waitingForChange)"
        in script
    )


def test_an_ignored_pre_hydration_click_can_retry_without_rapid_double_clicking():
    script = contract.listing_probe_script(
        link_pattern=r"/news/", container_selector="", link_selector="a[href]",
        settle_polls=1, url="https://www.axios.com/results",
        load_more_text="show 10 more results",
    )
    assert f"clickWaits>={contract.LOAD_MORE_STALL_POLLS}" in script
    assert "moreBtn&&!moreBtn.disabled" in script
    assert "moreBtn.scrollIntoView({block:'center'})" in script
    assert "clickWaits=" in script[script.index("'WAIT"):]
