"""正文抓取:先用登录态直抓,不行再走本地浏览器。

这一层替代了原项目里那条拖着编译管线、模型调用和数据库的 ``FtSource`` 继承链。
它只做一件事:**给一个 URL,还回一段正文或一句实话**。

提取顺序就是信任等级:页面自报的 JSON-LD → 站点声明的精确容器 → trafilatura 猜。
猜排在最后是因为它会把「下一篇推荐」当成正文续上去。
"""
from __future__ import annotations

import urllib.request
from typing import Any

from inews import cookies, extract
from inews.browser import BrowserBypassError, fetch_article
from inews.browser.contract import (
    body_coverage_is_enough,
    count_body_words,
    declared_body_words_from_html,
    raw_html_marker_matches,
)
from inews.sites import ft
from inews.textutil import clean_text

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DROP_SELECTORS = (
    "script, style, noscript, nav, aside, form, figure, .advertisement, .ad, "
    ".related-article, .article-list, .share, .social, .tags, "
    ".ArticleBody-extraData, .xyz-data"
)


def _direct(url: str, cookie: str, timeout: int = 40) -> tuple[str, str]:
    """带登录态直抓。**只走 HTTPS**,并复刻本地浏览器的 Referer 规则。"""
    if not url.startswith("https://"):
        raise RuntimeError(f"拒绝非 HTTPS 地址:{url}")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Cookie": cookie,
            "Referer": "https://www.google.com/",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 已限定 https
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace"), response.geturl()


def _extractors(html: str, final_url: str, site) -> list[tuple[str, Any]]:
    extractors = [
        ("JSON-LD", lambda: extract.extract_jsonld_article_body(html, clean_text)),
        (
            "站点容器",
            lambda: extract.extract_bs4(
                html,
                container_selectors=site.BODY_SELECTORS,
                drop_selectors=DROP_SELECTORS,
                clean_text=clean_text,
                paragraph_selectors=site.BODY_PARAGRAPH_SELECTORS,
            ),
        ),
    ]
    if site.ALLOW_TRAFILATURA:
        extractors.append(
            ("trafilatura", lambda: extract.extract_trafilatura(html, final_url))
        )
    return extractors


def _body_from_html(html: str, final_url: str, title: str, site) -> dict[str, Any]:
    metadata = extract.metadata_from_html(html, title, clean_text)
    longest = 0
    most_words = 0
    declared_words = declared_body_words_from_html(html)
    raw_marker = raw_html_marker_matches(html, site.RAW_HTML_REJECT_PATTERNS)
    for name, run in _extractors(html, final_url, site):
        body = run()
        longest = max(longest, len(body))
        words = count_body_words(body)
        most_words = max(most_words, words)
        enough_coverage = body_coverage_is_enough(
            words,
            declared_words,
            site.MIN_BODY_COVERAGE,
            raw_marker=raw_marker,
        )
        if (
            len(body) >= site.MIN_BODY_CHARS
            and words >= site.MIN_BODY_WORDS
            and enough_coverage
            and not site.barrier_before_body(
                body, metadata["page_title"]
            )
        ):
            return {
                "body": body,
                "extractor": name,
                "final_url": final_url,
                "longest": longest,
                "most_words": most_words,
                "declared_words": declared_words,
                "raw_html_marker": raw_marker,
                **metadata,
            }
    return {
        "body": "", "longest": longest, "most_words": most_words,
        "declared_words": declared_words, "raw_html_marker": raw_marker,
        "final_url": final_url, **metadata,
    }


def _short_body_reason(
    html: str,
    size: int,
    words: int,
    declared_words: int,
    raw_marker: bool,
    url: str,
    site,
) -> str:
    """失败要说人话,并且要能区分三种完全不同的原因。"""
    diagnostic = (
        f"仅 {size} 字、{words} 词、declared={declared_words}、"
        f"rawMarker={str(raw_marker).lower()}"
    )
    if site.REQUIRES_AUTH:
        auth = cookies.store_for(site.KEY).status()
        if not auth["ok"]:
            return f"正文读不到({diagnostic}):{auth['note']}"
    if site.REQUIRES_AUTH and site.BARRIER_RX.search(html):
        return (
            f"拿到的是付费墙拦截页({diagnostic}):登录态可能已失效,"
            f"请在已登录的浏览器里重新导出 {cookies.store_for(site.KEY).domain} cookie"
        )
    return (
        f"正文提取过短({diagnostic}),"
        f"可能是直播/图集/付费导语/摘要页:{url}"
    )


def fetch_body(article: dict[str, Any], site=ft) -> dict[str, Any]:
    """订阅 Cookie 直抓优先,失败再走本地浏览器。

    两条路吃同一套验收(字符数、词数、声明全文覆盖率与付费墙位置判定):
    换路从来不等于放松验收。
    """
    url = article["url"]
    title = article.get("title_en", "")
    store = cookies.store_for(site.KEY) if site.REQUIRES_AUTH else None
    cookie = store.header() if store else ""
    direct_error = ""
    # 公开站不需要伪造一个「空 cookie 仓库」再绕去浏览器。CNBC 先做普通 HTTPS
    # 直抓；只有正文确实不完整时才进无头浏览器兜底。
    if cookie or not site.REQUIRES_AUTH:
        try:
            html, final_url = _direct(url, cookie)
            result = _body_from_html(html, final_url, title, site)
            if result["body"]:
                return {**result, "extractor": f"直抓 · {result['extractor']}"}
            direct_error = _short_body_reason(
                html, result["longest"], result["most_words"],
                result["declared_words"], result["raw_html_marker"], url, site,
            )
        except Exception as error:  # noqa: BLE001 直抓失败不该盖过浏览器那条路
            direct_error = f"{type(error).__name__}: {error}"
    else:
        direct_error = str(store.status()["note"])

    try:
        html, final_url = fetch_article(
            url,
            site=site.KEY,
            cookie=cookie,
            min_chars=site.MIN_BODY_CHARS,
            min_words=site.MIN_BODY_WORDS,
            min_coverage=site.MIN_BODY_COVERAGE,
            selectors=site.BODY_SELECTORS,
            paragraph_selectors=site.BODY_PARAGRAPH_SELECTORS,
            reject_patterns=site.RAW_HTML_REJECT_PATTERNS,
        )
    except Exception as error:  # noqa: BLE001 两条路的原话都要留下
        raise RuntimeError(
            f"{direct_error};浏览器兜底也失败:{type(error).__name__}: {error}"
        ) from error
    result = _body_from_html(html, final_url, title, site)
    if result["body"]:
        return {**result, "extractor": f"浏览器 · {result['extractor']}"}
    raise BrowserBypassError(
        f"{direct_error};浏览器打开后正文仍不完整"
        f"(最长 {result['longest']} 字、{result['most_words']} 词、"
        f"declared={result['declared_words']}、"
        f"rawMarker={str(result['raw_html_marker']).lower()})"
    )
