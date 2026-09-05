"""通过管理员日常 Chrome + BPC 读取登记为 manual 的媒体页面。

Apple Events 只创建并关闭脚本自己的临时标签页，执行仓库内固定只读脚本；
URL 始终通过 argv 传递，不拼接进 AppleScript 或 JavaScript。
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
from urllib.parse import urlsplit

from inews.browser.contract import (
    BODY_WORD_COUNT_META_SELECTORS,
    BODY_WORD_PATTERN,
    RAW_HTML_RECOVERY_COVERAGE,
    BrowserBypassError,
    expected_path,
    listing_probe_script,
    site_for_url,
)

# 页内检查脚本把「撞上墙了」压成 `wall=true` 回报。滑块这一类只有真人能过,
# 而原来的错误文案是原样倒出 `WAIT …wall=true` —— 读的人分不出这是「去滑一下
# 就好」还是「这站坏了」,而两者该做的处置完全不同(2026-08-07 路透社)。
_HUMAN_CHECK_HINT = "wall=true"

_CHROME_TAB_APPLESCRIPT = r"""
on run argv
    set targetURL to item 1 of argv
    set waitCount to (item 2 of argv) as integer
    set checkScript to item 3 of argv
    set targetTab to missing value
    try
        tell application "Google Chrome"
            activate
            if (count of windows) is 0 then make new window
            set targetWindow to front window
            set targetTab to make new tab at end of tabs of targetWindow with properties {URL:targetURL}
            set active tab index of targetWindow to (count of tabs of targetWindow)
        end tell
        set lastDiagnostic to ""
        repeat waitCount times
            delay 1
            tell application "Google Chrome"
                set payload to execute targetTab javascript checkScript
                if (count of payload) > 400 then
                    set lastDiagnostic to text 1 thru 400 of payload
                else
                    set lastDiagnostic to payload
                end if
                if payload starts with "READY" then
                    set finalURL to URL of targetTab
                    set htmlText to text 7 thru -1 of payload
                    close targetTab
                    return finalURL & linefeed & htmlText
                end if
            end tell
        end repeat
        tell application "Google Chrome" to close targetTab
        error "当前 Chrome 标签页仍未加载出可读取内容：" & lastDiagnostic
    on error errMessage number errNumber
        if targetTab is not missing value then
            try
                tell application "Google Chrome" to close targetTab
            end try
        end if
        error errMessage number errNumber
    end try
end run
"""


# 站长在同一台 Mac 前工作时,同步不该把 Chrome 抢到最前 —— 一轮几十篇每篇都
# activate 一次,人就没法干别的了(2026-08-04 反馈)。默认删掉 activate:标签仍设为
# 其窗口的活动标签(document 保持 visible,Chrome 不当后台标签节流,BPC 渲染与提取
# 不受影响),只是不再跳到你面前。回退阀:YIDIAN_LOCAL_SYNC_FOREGROUND=1 恢复前台。
def _foreground() -> bool:
    return os.getenv("YIDIAN_LOCAL_SYNC_FOREGROUND", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


# 2026-08-07 站长再报:「还在跳」。删掉 activate 只是不让 Chrome 抢到**别的 App**
# 前面 —— 脚本仍然往 `front window` 里插标签并把它设成活动标签,所以只要你人在
# Chrome 里,每一篇都会把眼前的页面顶掉一下。
#
# 这里改成开一个**专用窗口**:用一个 data: 哨兵标签认领它(建一次、之后一直复用),
# 抓取标签在那个窗口里保持活动,你正在用的窗口一根手指都不碰。
#
# 为什么不最小化、不藏到屏幕外:Chrome 对被遮挡/最小化的窗口会节流,而「标签必须
# 是其窗口的活动标签」正是 8-04 那次留下的判据 —— 节流了 BPC 就渲染不出正文。
# 这一版只把专用窗口**排到最后**(index),不动它的可见性;够不够安静、会不会被
# 节流,只有在真的 Mac 上跑一轮才知道,所以先给开关,不动默认值。
_SENTINEL_URL = "data:text/plain,inews-probe"
_FRONT_WINDOW_BLOCK = """            if (count of windows) is 0 then make new window
            set targetWindow to front window
"""
_DEDICATED_WINDOW_BLOCK = f"""            set targetWindow to missing value
            repeat with candidateWindow in windows
                try
                    if (URL of tab 1 of candidateWindow) is "{_SENTINEL_URL}" then
                        set targetWindow to candidateWindow
                        exit repeat
                    end if
                end try
            end repeat
            if targetWindow is missing value then
                set targetWindow to make new window
                set URL of tab 1 of targetWindow to "{_SENTINEL_URL}"
                set index of targetWindow to (count of windows)
            end if
"""


def _dedicated_window() -> bool:
    return os.getenv("YIDIAN_LOCAL_SYNC_DEDICATED_WINDOW", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _applescript(*, foreground: bool, dedicated: bool = False) -> str:
    script = _CHROME_TAB_APPLESCRIPT
    if not foreground:
        script = script.replace("            activate\n", "", 1)
    if dedicated:
        script = script.replace(_FRONT_WINDOW_BLOCK, _DEDICATED_WINDOW_BLOCK, 1)
        if foreground:
            # 只有人工 App 的显式点击会同时打开 dedicated + foreground。这时
            # 验证页必须真的在眼前；静默任务永远不会走到这组开关。
            script = script.replace(
                "            set targetTab to make new tab at end of tabs of targetWindow",
                "            set index of targetWindow to 1\n"
                "            set targetTab to make new tab at end of tabs of targetWindow",
                1,
            )
    return script


def run_with_daily_chrome(
    url: str,
    *,
    check_script: str,
    timeout_seconds: int,
    timeout_label: str,
    same_path: bool = False,
) -> tuple[str, str]:
    """在日常 Chrome 的临时标签页执行固定检查脚本并取回 DOM.

    ``same_path`` 要求最终 URL 仍停在请求的路径上。同站校验挡不住页面内跳转 ——
    实跑中要求打开 WSJ 搜索页,最后读到的却是某篇文章正文页(``ArticlePage_``、
    ``PaywalledContentContainer``),两者都是 wsj.com 所以一路放行,于是从正文
    段落的内联链接里刮出一堆东西当作「搜索结果」。列表通道必须开这道校验:
    宁可如实超时,也不要拿错页面的 DOM 冒充结果。
    """
    site = site_for_url(url)
    if platform.system() != "Darwin" or not site:
        raise BrowserBypassError(
            "日常 Chrome 通道只支持 Mac 上已登记的付费媒体 HTTPS 页面"
        )
    source_name = {"ft": "FT", "bloomberg": "Bloomberg"}.get(site, site.upper())
    command = [
        "/usr/bin/osascript",
        "-e",
        _applescript(
            foreground=_foreground(),
            dedicated=_dedicated_window(),
        ),
        url,
        str(max(15, min(int(timeout_seconds), 300))),
        check_script,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=max(30, int(timeout_seconds) + 25),
        )
    except subprocess.TimeoutExpired as exc:
        raise BrowserBypassError(
            f"日常 Chrome {timeout_label}没有响应；请关闭浏览器弹窗后重试"
        ) from exc
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        _raise_bridge_error(stderr, timeout_label, source_name)
    final_url, separator, html = stdout.partition("\n")
    final_url = final_url.strip()
    if not separator or site_for_url(final_url) != site or not html.strip():
        raise BrowserBypassError("日常 Chrome 返回格式不完整")
    if same_path and expected_path(final_url) != expected_path(url):
        raise BrowserBypassError(
            f"标签页已离开请求的页面({expected_path(url)} → "
            f"{expected_path(final_url)}),不采用这次的 DOM"
        )
    return html, final_url


def _raise_bridge_error(
    stderr: str,
    timeout_label: str,
    source_name: str,
) -> None:
    lowered = stderr.lower()
    if _HUMAN_CHECK_HINT in lowered:
        raise BrowserBypassError(
            f"{source_name} 这一页停在拦截/真人验证上(滑块或机器人验证)。"
            "请在抓取用的 Chrome 窗口里完成一次验证,过了之后重跑这个站;"
            f"原始诊断:{stderr[-200:]}"
        )
    if "javascript from apple events" in lowered or "apple events" in lowered:
        raise BrowserBypassError(
            "请在 Chrome 菜单「View/显示 → Developer/开发者」中勾选"
            f"「Allow JavaScript from Apple Events」，这是 {source_name} 一键同步的"
            f"一次性本机设置；脚本只读取自己新开的 {source_name} 标签页。"
        )
    raise BrowserBypassError(
        f"日常 Chrome {timeout_label}读取失败:{stderr[-400:] or '无诊断'}"
    )


def fetch_page(
    url: str,
    *,
    min_chars: int,
    timeout_seconds: int,
    min_words: int = 0,
    min_coverage: float = 0.0,
    settle_polls: int = 1,
    selectors: tuple[str, ...] = (),
    paragraph_selectors: tuple[str, ...] = (),
    reject_patterns: tuple[str, ...] = (),
) -> tuple[str, str]:
    """让日常 Chrome/BPC 打开私站正文页，并仅取回已恢复的 DOM."""
    containers = selectors or (
        '[data-component="body-content"]', ".body-content",
        '[class*="body-content"]', "article", "main",
    )
    selectors_json = json.dumps(containers, ensure_ascii=False)
    paragraphs_json = json.dumps(paragraph_selectors, ensure_ascii=False)
    reject_json = json.dumps(reject_patterns, ensure_ascii=False)
    word_count_selectors_json = json.dumps(
        BODY_WORD_COUNT_META_SELECTORS, ensure_ascii=False
    )
    normal_coverage = max(0.0, float(min_coverage))
    check_script = (
        "(() => {"
        f"const selectors={selectors_json};"
        f"const paragraphSelectors={paragraphs_json};"
        f"const rejectPatterns={reject_json};"
        f"const wordCountSelectors={word_count_selectors_json};"
        "let root=null;for(const selector of selectors){root=document.querySelector(selector);if(root)break;}"
        "let best='';"
        "if(root&&paragraphSelectors.length){"
        "const nodes=[...root.querySelectorAll(paragraphSelectors.join(','))];"
        "best=nodes.map(n=>(n.innerText||'').trim()).filter(Boolean).join('\\n\\n').trim();"
        "}else{best=((root&&root.innerText)||'').trim();}"
        # 站点墙标记常在 class/data attribute 中，只检查 ``best`` 文字会
        # 完全看不到。这里与 Python 直抓、Playwright 共用“整页 HTML”口径。
        "const pageHtml=document.documentElement?.outerHTML||'';"
        # 词的定义来自 browser_contract,与隔离通道共用一处(见那里的说明)
        f"const words=best.match(/{BODY_WORD_PATTERN}/g)||[];"
        "let declaredWords=0;for(const selector of wordCountSelectors){"
        "const raw=document.querySelector(selector)?.getAttribute('content')||'';"
        "const parsed=Number.parseInt(raw,10);if(Number.isFinite(parsed)&&parsed>0){"
        "declaredWords=parsed;break;}}"
        "const rawMarker=rejectPatterns.some(p=>{try{return new RegExp(p,'is').test(pageHtml)}catch(_){return false}});"
        f"const markerRecovered=rawMarker&&declaredWords>0&&words.length>=declaredWords*{RAW_HTML_RECOVERY_COVERAGE};"
        "const rawBlocked=rawMarker&&!markerRecovered;"
        f"const enoughCoverage=rawMarker?markerRecovered:(!declaredWords||{normal_coverage}<=0"
        f"||words.length>=declaredWords*{normal_coverage});"
        "const wall=/subscribe to read|sign in to keep reading|register to continue|"
        "before it.s here, it.s on the bloomberg terminal|are you a robot|"
        "unusual activity|just a moment|verify (?:that )?you are human|"
        "checking your browser|enable javascript and cookies to continue/i.test("
        "(document.body?.innerText||'')+' '+document.title)"
        "||!!document.querySelector('#bpc_fail')"
        "||rawBlocked;"
        "const old=window.__paywallArticleProbe||{text:'',stable:0};"
        "const stable=old.text===best?old.stable+1:1;"
        "window.__paywallArticleProbe={text:best,stable};"
        f"const enough=best.length>={max(100, int(min_chars))}"
        f"&&words.length>={max(0, int(min_words))}"
        "&&enoughCoverage;"
        f"const ready=enough&&!wall&&stable>={max(1, int(settle_polls))};"
        "return ready?'READY\\n'+document.documentElement.outerHTML:"
        "'WAIT\\n'+document.title+'\\nchars='+best.length+',words='+words.length"
        "+',declared='+declaredWords+',rawMarker='+rawMarker"
        "+',markerRecovered='+markerRecovered+',stable='+stable+',wall='+wall;"
        "})()"
    )
    return run_with_daily_chrome(
        url,
        check_script=check_script,
        timeout_seconds=timeout_seconds,
        timeout_label="正文",
    )


# Bloomberg 的文章路径。调用方不传 link_pattern 时沿用它,保持既有行为不变。
BLOOMBERG_LINK_PATTERN = (
    r"/(?:news/(?:articles|newsletters)|opinion/articles)/\d{4}-\d{2}-\d{2}/"
)


def fetch_listing(
    url: str,
    *,
    timeout_seconds: int | None = None,
    link_pattern: str = BLOOMBERG_LINK_PATTERN,
    container_selector: str = "",
    link_selector: str = "a[href]",
    settle_polls: int = 1,
    scroll_listing: bool = False,
    load_more_text: str = "",
) -> tuple[str, str]:
    """读取栏目/搜索页渲染后的文章链接。

    搜索页普遍由 JS 驱动且受 CDN 令牌保护(令牌只有几分钟有效期、且绑死具体
    query),所以不能自己拼地址直抓 —— 只能打开干净地址,让站点前端自己去换令牌、
    渲染结果,我们再从 DOM 收链接。``link_pattern`` 声明什么样的路径算文章。

    **「有链接」不等于「结果已渲染」**:搜索页在结果回来之前就带着导航与「最多
    阅读」推荐位,只等 ``links.length>0`` 会把当天热门新闻当成搜索结果收走(实跑中
    BBC 搜「HBM」返回的是谋杀案庭审)。因此两道额外条件:``container_selector``
    把范围限定在结果容器内(容器还没出现就继续等),``settle_polls`` 要求链接集合
    连续多轮不变 —— 这与正文通道判定「渲染完成」的方式一致。
    """
    timeout = timeout_seconds or int(
        os.getenv("BLOOMBERG_LISTING_TIMEOUT_SECONDS", "45")
    )
    # 判据与隔离通道共用一处(browser_contract):各写一份就会悄悄分叉,
    # 同一个页面一条通道说渲染好了、另一条说没有。
    check_script = listing_probe_script(
        link_pattern=link_pattern,
        container_selector=container_selector,
        link_selector=link_selector,
        settle_polls=settle_polls,
        url=url,
        scroll=scroll_listing,
        load_more_text=load_more_text,
    )
    return run_with_daily_chrome(
        url,
        check_script=check_script,
        timeout_seconds=max(15, min(int(timeout), 120)),
        timeout_label="文章列表",
        same_path=True,
    )
