"""浏览器门面:走无头还是可见窗口,由**该站的获取档位**决定,不由本模块决定。

依赖固定为 ``browser → {contract, profile, playwright, daily_chrome, tiers}``;
档位来自 ``tiers`` 的逐站声明 —— **这里一个站名都不写**。

这一层连同它的注释是从 yidian 项目原样带过来的,包括那些记着真实事故的段落。
删掉注释代码照跑,但下一个人就会重蹈同一个坑。
"""
from __future__ import annotations

import os
import platform
import sys as _sys

from inews.browser import contract as _contract
from inews.browser import daily_chrome as _daily
from inews.browser import playwright as _playwright
from inews.browser import profile as _profile
from inews.browser.channels import DAILY, HEADLESS, through as _via
from inews.browser.tiers import (
    HEADLESS_TIER as _HEADLESS_TIER,
    is_headless_site as _is_headless,
    requires_visible_browser as _requires_visible,
    tier_of as _tier_of,
)

BrowserBypassError = _contract.BrowserBypassError
extension_path = _profile.extension_path
chrome_profile_path = _profile.chrome_profile_path
_TRUE = {"1", "true", "yes", "on"}
_DEFAULT_LINK_RX = r"/[a-z0-9-]+/\d{4}-\d{2}-\d{2}/[a-z0-9-]+"


def _timeout(override: int | None, env_name: str, default: str) -> int:
    return override or int(
        os.getenv(env_name, os.getenv("INEWS_BYPASS_TIMEOUT_SECONDS", default))
    )


def _use_daily_chrome(env_name: str) -> bool:
    return (
        platform.system() == "Darwin"
        and os.getenv(env_name, "").strip().lower() not in _TRUE
    )


# 未登记站专用:失败只试一次。结构性原因(扩展没解压、profile 读不到)一篇失败就
# 篇篇失败,每篇白等一次隔离启动是纯浪费。有档位的站用不到它 —— 它们的档位已经
# 把路定死了,没有「回落」这一说。
_ISOLATED_GAVE_UP: set[str] = set()


def _isolated_available(site: str) -> bool:
    return (
        site not in _ISOLATED_GAVE_UP
        and bool(_profile.extension_path())
        and bool(_playwright.bypass_status().get("ok"))
    )


def _isolated_then_daily(site: str, isolated, daily):
    """走哪条路**只由该站的获取档位决定**,这里是唯一的裁决点。

    无头档:只走无头,失败就如实失败 —— **回落是被刻意取消的**。原项目站长的原话:
    「一打开 macbook 就自动跳出来更新,不是我点的,也关不掉。」病因正是那个回落:
    日常通道用 AppleScript 往当前窗口插标签、且刻意不最小化(被遮挡会被节流),
    配上定时轮询就是「一直在弹」。救回一篇正文的收益,远小于让人失去对自己
    电脑的控制。manual 档只在人工入口或站长明确登记的本机错峰任务中走可见窗口。

    先无头、失败再弹窗的那段回落,**只服务于没有档位声明的站**:没有档位就没人
    给过它「静默」的承诺,先试无头是为了尽量别弹。
    """
    if _is_headless(site):
        # 不试 _isolated_available:那是「回落前的探测」,这里没有回落。
        # 扩展没装、Playwright 缺失都该原样抛出去,而不是变成一次弹窗。
        return _via(HEADLESS, isolated)
    if _requires_visible(site):
        return _via(DAILY, daily)
    if not _isolated_available(site):
        return _via(DAILY, daily)
    try:
        return _via(HEADLESS, isolated)
    except BrowserBypassError as exc:
        _ISOLATED_GAVE_UP.add(site)
        print(
            f"[browser] {site} 无头通道不可用,本轮改用日常 Chrome:{exc}",
            file=_sys.stderr,
        )
        return _via(DAILY, daily)


def fetch_rendered_listing(
    url: str,
    *,
    site: str = "",
    timeout_seconds: int | None = None,
    link_pattern: str = "",
    container_selector: str = "",
    link_selector: str = "a[href]",
    settle_polls: int = 1,
    scroll_listing: bool = False,
    load_more_text: str = "",
) -> tuple[str, str]:
    """搜索页/栏目页读取 —— **发现阶段同样守分栏**。

    静默栏的承诺覆盖**整轮**,不是只覆盖取正文:发现才是开窗口最多的一段
    (每个关键词每一页都是一次打开),与最后抓到几篇正文无关。

    ``scroll_listing`` 由站点词汇表声明(LISTING_SCROLLS):懒加载的河要
    边滚边收,有真分页的搜索页不滚 —— 这里只转交,不替站点表态。
    """
    resolved = site or _contract.site_for_url(url)
    pattern = link_pattern or _DEFAULT_LINK_RX
    probe = _contract.listing_probe_script(
        link_pattern=pattern,
        container_selector=container_selector,
        link_selector=link_selector,
        settle_polls=settle_polls,
        url=url,
        scroll=scroll_listing,
        load_more_text=load_more_text,
    )
    timeout = _timeout(timeout_seconds, "INEWS_LISTING_TIMEOUT_SECONDS", "45")
    if _tier_of(resolved) == _HEADLESS_TIER:
        isolated = lambda: _playwright.fetch_public_listing_headless(  # noqa: E731
            url, site=resolved, probe=probe, timeout_seconds=timeout,
        )
    else:
        isolated = lambda: _playwright.fetch_listing_isolated(  # noqa: E731
            url, site=resolved, probe=probe, timeout_seconds=timeout,
        )
    daily = lambda: _daily.fetch_listing(  # noqa: E731 同上
        url, timeout_seconds=timeout, link_pattern=pattern,
        container_selector=container_selector, link_selector=link_selector,
        settle_polls=settle_polls, scroll_listing=scroll_listing,
        load_more_text=load_more_text,
    )
    return _isolated_then_daily(resolved, isolated, daily)


def fetch_article(
    url: str,
    *,
    site: str = "",
    cookie: str = "",
    min_chars: int = 600,
    min_words: int = 0,
    min_coverage: float = 0.0,
    settle_polls: int = 1,
    selectors: tuple[str, ...] = (),
    paragraph_selectors: tuple[str, ...] = (),
    reject_patterns: tuple[str, ...] = (),
    timeout_seconds: int | None = None,
) -> tuple[str, str]:
    """正文页读取。**域名边界只认 ``site``** —— 能读谁不可借用。

    两条路吃同一套验收(``min_chars``/``min_words``/全文覆盖率/该站声明的选择器):
    换路不等于放松验收,否则导语页会冒充全文混过门槛。
    """
    resolved = site or _contract.site_for_url(url)
    if not resolved or _contract.site_for_url(url) != resolved:
        raise BrowserBypassError(
            f"URL 不属于已登记的 {resolved or '任何'} 域名,拒绝用本地浏览器打开"
        )
    timeout = _timeout(
        timeout_seconds, f"{resolved.upper()}_BYPASS_TIMEOUT_SECONDS", "90"
    )
    if _tier_of(resolved) == _HEADLESS_TIER:
        isolated = lambda: _playwright.fetch_public_page_headless(  # noqa: E731
            url, site=resolved, min_chars=min_chars, min_words=min_words,
            min_coverage=min_coverage,
            selectors=selectors, paragraph_selectors=paragraph_selectors,
            reject_patterns=reject_patterns, settle_polls=settle_polls,
            timeout_seconds=timeout,
        )
    else:
        isolated = lambda: _playwright.fetch_paid_page_isolated(  # noqa: E731
            url, site=resolved, min_chars=min_chars, min_words=min_words,
            min_coverage=min_coverage,
            selectors=selectors, paragraph_selectors=paragraph_selectors,
            reject_patterns=reject_patterns, settle_polls=settle_polls,
            timeout_seconds=timeout,
        )
    daily = lambda: _daily.fetch_page(  # noqa: E731
        url, min_chars=min_chars, min_words=min_words, min_coverage=min_coverage,
        settle_polls=settle_polls, selectors=selectors,
        paragraph_selectors=paragraph_selectors,
        reject_patterns=reject_patterns, timeout_seconds=timeout,
    )
    return _isolated_then_daily(resolved, isolated, daily)


def bypass_status(site: str) -> dict[str, object]:
    """说明本轮实际会用哪条通道,避免把隔离扩展误报成日常通道。"""
    if _requires_visible(site):
        return {
            "ok": True,
            "note": "本机有头模式；人工或已授权错峰任务使用专用 Chrome",
        }
    if _tier_of(site) == _HEADLESS_TIER:
        return _playwright.public_status()
    env_name = f"{site.upper()}_USE_ISOLATED_BROWSER"
    if not _use_daily_chrome(env_name) or _isolated_available(site):
        return _playwright.bypass_status()
    return {"ok": True, "note": "使用当前 Chrome 前台窗口中已启用的 BPC"}
