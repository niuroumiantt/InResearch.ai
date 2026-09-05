"""付费私站浏览器通道共享的安全契约。

这里只定义允许访问的站点、Cookie 域限制与公共异常，不启动浏览器、不读取
Chrome 资料，也不依赖任何站点适配器。
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit


class BrowserBypassError(RuntimeError):
    """本地 BPC 浏览器链路不可用或没有恢复出完整正文。"""


# 正文「有多少个词」的唯一判据。两条浏览器通道都要用它:日常 Chrome 把这段
# 模式插进页内 JS 数,隔离 Playwright 在 Python 里数 —— **同一个字符类**。
#
# 各数各的就会悄悄分叉:同一篇稿子,一条通道说够 150 词、另一条说不够,而
# min_words 存在的全部理由是挡住「字数够、词数不够」的导语(WSJ 直抓拿回
# 920 字被当正文入库,门槛正好 900 字)。判据分叉 = 那道门在某条路上不存在。
#
# 字符类在 JS 正则与 Python 正则里含义一致,所以一份字符串两边都能用。
BODY_WORD_PATTERN = r"[A-Za-z0-9][A-Za-z0-9'’.-]*"
BODY_WORD_RX = re.compile(BODY_WORD_PATTERN)

# WSJ 等站会在 meta 中声明全文词数。选择器集中在这里，保证直抓、隔离浏览器与
# 日常 Chrome 用的是同一份口径；没有声明的站自然跳过比例门槛。
BODY_WORD_COUNT_META_SELECTORS = (
    "meta[property='article:word_count']",
    "meta[name='cXenseParse:wsj-word-count']",
)

# WSJ 经 BPC 恢复出完整正文后仍会保留 ``PaywalledContentContainer``。因此这个
# DOM 标记不是一票否决，而是一道更严格的完整度门：必须有站方声明词数，且正文
# 至少恢复到 90%。常量和下面两个纯函数由直抓与 Playwright 共用；日常 Chrome
# 将同一个常量注入页内 JS，三条通道不能各猜一个阈值。
RAW_HTML_RECOVERY_COVERAGE = 0.90


def count_body_words(text: str) -> int:
    """正文词数;与日常 Chrome 页内 JS 的口径逐字一致。"""
    return len(BODY_WORD_RX.findall(str(text or "")))


def declared_body_words_from_html(html: str) -> int:
    """读取页面自报的全文词数；缺失或非法时返回 0，不凭正文长度反推。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(str(html or ""), "html.parser")
    for selector in BODY_WORD_COUNT_META_SELECTORS:
        node = soup.select_one(selector)
        if node is None:
            continue
        try:
            value = int(float(str(node.get("content") or "").strip()))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 0


def raw_html_marker_matches(html: str, patterns: tuple[str, ...]) -> bool:
    """结构标记只在整页 HTML 上匹配；坏表达式忽略，与浏览器通道一致。"""
    for pattern in patterns:
        try:
            if re.search(pattern, str(html or ""), flags=re.IGNORECASE | re.DOTALL):
                return True
        except re.error:
            continue
    return False


def body_coverage_is_enough(
    words: int,
    declared_words: int,
    min_coverage: float,
    *,
    raw_marker: bool,
) -> bool:
    """统一正文覆盖率门槛；结构标记存在时要求可证明的 90% 恢复率。"""
    if raw_marker:
        return (
            declared_words > 0
            and words >= declared_words * RAW_HTML_RECOVERY_COVERAGE
        )
    return (
        declared_words <= 0
        or min_coverage <= 0
        or words >= declared_words * min_coverage
    )


# 列表页「渲染完成了没有」的唯一判据。两条通道共用:日常 Chrome 把它注进页面,
# 隔离 Playwright 用 page.evaluate 跑同一段 —— 与 BODY_WORD_PATTERN 同一条纪律。
#
# **「有链接」不等于「结果已渲染」**:搜索页在结果回来之前就带着导航与「最多阅读」
# 推荐位,只等 links.length>0 会把当天热门新闻当成搜索结果收走(实跑中 BBC 搜
# 「HBM」返回的是谋杀案庭审)。所以要三道条件一起成立:限定在结果容器内、
# 链接集合连续多轮不变、且没被重定向走。
#
# 判据分叉的代价与正文那条一样:同一个页面,一条通道说渲染好了、另一条说没有,
# 而这道门存在的全部理由就是挡住「看起来有链接」的半渲染页。
def expected_path(url: str) -> str:
    """这个地址在浏览器里的 `location.pathname`。

    裸域名(`https://www.bbc.com`)的 urlsplit path 是空串,而浏览器给的是 `/` ——
    直接比较则**任何首页都会被判成「被重定向走了」**。2026-08-07 实测:BBC /
    Reuters / 日経 / CTech 四个首页全部误报,而页面其实好好地开着。
    """
    return urlsplit(url).path or "/"


# 整页没加载完时,要多等几轮才认。
#
# 2026-08-23 站长的日志:`links=112,roots=1,stable=35,onPage=true` —— 报出来的四项
# 全部满足,页面却一路等到 45 秒超时。FT 是默认 `settle_polls=1`,所以真正没过的
# 只可能是**没被报出来**的那两条,而 `wall` 若成立会在这个关键词的每一页都成立
# (实际是第 2、3 页照常成功),剩下的就是 `document.readyState`。
#
# `readyState==='complete'` 说的是**整页子资源**(广告、埋点、长连接)都完了 ——
# FT 搜索页上它可能永远不到,而那与「搜索结果渲染好了没有」无关。所以把它从硬
# 条件降级成**等多久**:整页完成时沿用站点声明的稳定轮数;没完成时要求链接集合
# 多稳定几轮,拿更长的静默期换掉那条信号。
#
# 3 这个数:AppleScript 那边 `delay 1`,一轮就是一秒。多等 3 秒对一次 45 秒的
# 打开可以忽略,而半渲染页的链接集合在 3 秒里几乎不可能一动不动。
_SETTLE_WITHOUT_COMPLETE = 3


def settle_target(settle_polls: int, *, page_complete: bool) -> int:
    """链接集合要连续多少轮不变,才算「这一页渲染好了」。

    下限是 1:一轮都不等就会把半渲染页的第一帧收走 —— 那正是这道门存在的理由。
    """
    base = max(1, int(settle_polls))
    return base if page_complete else base + _SETTLE_WITHOUT_COMPLETE


# 滚动收割的两个预算,只对声明了「列表页越滚越长」的站生效(9-02 实测:
# Bloomberg /ai 的「More AI news」是懒加载的河,初始 HTML 只有一屏 22-25 条,
# 两天五六十篇里的大多数从未进入视野)。
#
# 上限 25:默认 45 秒超时、一轮约一秒 —— 滚动最多占 25 轮,余量留给首屏渲染
# 与最后的静默确认。不设上限的话,一条真正无底的河会把每一轮都拖到超时失败,
# 比少收更糟。
LISTING_SCROLL_CAP = 25
# 滚动触发的加载是异步的:滚到底之后下一批可能一秒后才落地,settle_polls=1
# 会把「下一批还没来得及长」误判成「河到底了」。滚动时稳定期至少这么多轮。
SCROLL_SETTLE_POLLS = 3

# 「Load more」按钮最多点几次。9-03 站长截图:Bloomberg /ai 的河末尾是一个
# **按钮**,不是无限滚动 —— 滚多少次都不会有新条目(9-02 那版滚动修法因此无效)。
# 上限 8:一批约十条,八次点完够覆盖一天的量;而一轮只有 45 秒预算,每点一次
# 要等这批落地(至少两轮),不设上限的话一条长河会把每轮拖到超时失败,比少收更糟。
LOAD_MORE_CLICK_CAP = 8
# React/Next 页面偶尔会先画出按钮、稍后才绑定 click handler。首次点击后若链接
# 签名连续这么多轮完全没变，且按钮仍可用，允许把这一击判为“未生效”再试一次；
# 正常慢请求仍由 clickedSignature 保护，不会每轮连点。
LOAD_MORE_STALL_POLLS = 6


def listing_probe_script(
    *,
    link_pattern: str,
    container_selector: str,
    link_selector: str,
    settle_polls: int,
    url: str,
    scroll: bool = False,
    load_more_text: str = "",
) -> str:
    """返回那段自证「列表页好了没有」的 JS;READY 时带回整页 HTML。

    **WAIT 文案要报出每一个参与判定的量。** 少报一条,读日志的人就分不出「还在
    渲染」和「判据把它误杀了」—— 8-23 那次就是这么误诊的:报出来的全满足,没过的
    那条不在文案里。

    ``scroll=True`` 时每轮先滚到页底再量:懒加载的河还在吐新链接时集合不稳定、
    自然继续等,吐完了集合稳定即 READY —— 正是既有 stable 机制的自然延伸,
    完成判据本身一条都不用改。

    ``load_more_text`` 声明「展开更多」按钮上的可见文字(小写):有它就点,
    点到按钮消失或到上限为止。**按文字认而不是按类名** —— 这类站点的类名是
    构建时哈希出来的(``styles_itemLink__VgyXJ``),类选择器随一次发布就失效,
    而按钮上的字是给人看的,改动要慢得多。
    """
    import json as _json

    if scroll or load_more_text:
        settle_polls = max(int(settle_polls), SCROLL_SETTLE_POLLS)
    scroll_js = (
        (
            "const scrolls=(old.scrolls||0)+1;"
            f"if(scrolls<={LISTING_SCROLL_CAP}&&document.body)"
            "window.scrollTo(0,document.body.scrollHeight);"
        )
        if scroll
        else "const scrolls=0;"
    )
    scroll_wait = f"+',scrolls='+scrolls+'/{LISTING_SCROLL_CAP}'" if scroll else ""
    # 展开更多:**先等这一批落地到统一稳定门槛再点下一次**,否则就是对着按钮猛敲。
    # 点击与异步 DOM 更新之间可能隔着多轮，因此还要记住点击当刻的链接签名；
    # 新签名没出现前，即使 stable 继续增长也不能再点。
    # 按钮还在但已到上限,或按钮消失(河到底了),都算展开完毕。达到上限的
    # **最后一次点击**也必须等新签名落地：否则同一轮 JS 刚 click() 就会因为
    # clicks==cap 返回 READY，拿到的仍是点击前 DOM。
    load_more_js = (
        (
            f"const wantMore={_json.dumps(load_more_text)};"
            "const moreBtn=[...document.querySelectorAll('button,a,[role=\"button\"]')]"
            ".find(el=>(el.textContent||'').trim().toLowerCase()===wantMore);"
            "let clicks=old.clicks||0;"
            # 点击并不保证下一批链接已经落地。记住点击当刻的链接签名；只要签名
            # 仍相同，就说明还在等这一批，不能让持续增长的 ``stable`` 再点一次。
            # 新签名出现后先重新通过稳定门槛，再允许下一次点击。
            "let clickedSignature=old.clickedSignature||'';"
            "let clickWaits=old.clickWaits||0;"
            "if(clickedSignature&&clickedSignature!==signature){"
            "clickedSignature='';clickWaits=0;"
            "}else if(clickedSignature){clickWaits++;}"
            f"if(clickedSignature&&clickWaits>={LOAD_MORE_STALL_POLLS}"
            "&&moreBtn&&!moreBtn.disabled){clickedSignature='';clickWaits=0;}"
            "let waitingForChange=!!clickedSignature;"
            f"if(moreBtn&&clicks<{LOAD_MORE_CLICK_CAP}"
            f"&&stable>={SCROLL_SETTLE_POLLS}&&!waitingForChange){{"
            "moreBtn.scrollIntoView({block:'center'});moreBtn.click();clicks++;"
            "clickedSignature=signature;clickWaits=0;waitingForChange=true;}"
            f"const expanded=!moreBtn||(clicks>={LOAD_MORE_CLICK_CAP}&&!waitingForChange);"
        )
        if load_more_text
        else (
            "const clicks=0;const expanded=true;const moreBtn=null;"
            "const clickedSignature='';const clickWaits=0;"
            "const waitingForChange=false;"
        )
    )
    load_more_wait = (
        f"+',clicks='+clicks+'/{LOAD_MORE_CLICK_CAP}'+',btn='+!!moreBtn"
        "+',awaiting='+waitingForChange+',clickWaits='+clickWaits"
        if load_more_text
        else ""
    )
    return (
        "(() => {"
        "const old=window.__paywallListingProbe||"
        "{signature:'',stable:0,scrolls:0,clicks:0,clickedSignature:'',clickWaits:0};"
        + scroll_js
        + f"const articlePath=new RegExp({_json.dumps(link_pattern)});"
        f"const sel={_json.dumps(container_selector)};"
        "const roots=sel?[...document.querySelectorAll(sel)]:[document];"
        f"const linkSel={_json.dumps(link_selector)};"
        "const links=roots.flatMap(r=>[...r.querySelectorAll(linkSel)])"
        ".filter(a=>a.href)"
        ".map(a=>{try{return new URL(a.href,location.href).pathname}"
        "catch(_){return ''}}).filter(p=>p&&articlePath.test(p));"
        "const signature=[...new Set(links)].sort().join('|');"
        "const stable=old.signature===signature?old.stable+1:1;"
        + load_more_js
        + "window.__paywallListingProbe={signature,stable,scrolls,clicks,clickedSignature,clickWaits};"
        "const wall=/are you a robot|unusual activity|just a moment|"
        "verify (?:that )?you are human|checking your browser|"
        "enable javascript and cookies to continue/i.test("
        "(document.body?.innerText||'')+' '+document.title);"
        f"const onPage=location.pathname==={_json.dumps(expected_path(url))};"
        # 阈值在 Python 那边算,这里只挑一个 —— 规则只有一处实现。
        f"const need=document.readyState==='complete'"
        f"?{settle_target(settle_polls, page_complete=True)}"
        f":{settle_target(settle_polls, page_complete=False)};"
        "const ready=links.length>0&&!wall&&onPage&&roots.length>0"
        "&&stable>=need&&expanded;"
        "return ready?'READY\\n'+document.documentElement.outerHTML:"
        "'WAIT\\n'+document.title+'\\nlinks='+links.length"
        "+',roots='+roots.length+',stable='+stable+'/'+need"
        "+',onPage='+onPage+',wall='+wall"
        "+',readyState='+document.readyState"
        + scroll_wait
        + load_more_wait
        + ";})()"
    )


# 允许本地浏览器通道打开的站点。**这份表就是安全边界**：不在表里的域名，
# 日常 Chrome 通道一律拒绝打开，Cookie 也永远不会被送出去。新增一家付费媒体时，
# 这里加一行域名、``paid_registry`` 加一条站点声明后，通用浏览器读取本身不需要
# 新适配器；正式启用仍要审阅 Mac 启动器与服务器导入协议是否已经覆盖该 site。
SITE_DOMAINS: dict[str, str] = {
    "ft": "ft.com",
    "bloomberg": "bloomberg.com",
    "cnbc": "cnbc.com",
    "wsj": "wsj.com",
    "bbc": "bbc.com",
    "nytimes": "nytimes.com",
    "economist": "economist.com",
    "cnn": "cnn.com",
    "reuters": "reuters.com",
    "axios": "axios.com",
    "theinformation": "theinformation.com",
    "nikkei": "nikkei.com",
    "lemonde": "lemonde.fr",
    "handelsblatt": "handelsblatt.com",
    "washingtonpost": "washingtonpost.com",
    # thetimes 2026-08-04 下架(站长裁决):登录态 + BPC 只拿到 fetch blocked,
    # 改走 archive 快照后 43/50 仍失败。域名一并撤出 —— 站点下架却留着放行域名,
    # 等于留一扇没人再看的门。
    # archive 档的伪站点:acquire_via=archive 的媒体正文经 archive.ph 最新快照
    # 读取,浏览器打开的是快照站而不是源站。快照地址只能由 archive_newest_url
    # 构造,里面包的原文链接仍必须属于本表里的媒体。
    "archive": "archive.ph",
}

ARCHIVE_SITE = "archive"


def archive_newest_url(url: str) -> str:
    """构造 archive.ph 最新快照地址;只接受已登记媒体的文章链接。

    archive 档改变的是「怎么读」(换一扇门进),不放宽「能读谁」:包在快照
    地址里的原文必须属于 SITE_DOMAINS 已登记的媒体,快照站自己不能再套快照。
    """
    inner = site_for_url(url)
    if not inner or inner == ARCHIVE_SITE:
        raise BrowserBypassError("archive 档只接受已登记媒体的文章链接")
    return f"https://{SITE_DOMAINS[ARCHIVE_SITE]}/newest/{url}"

# 同一媒体的部分子域走完全不同的内容体系(cn.ft.com 是独立的中文站)，不纳入通道。
EXCLUDED_HOSTS = frozenset({"cn.ft.com"})


def site_for_url(url: str) -> str:
    """把受支持的 HTTPS URL 映射到站点键；其它输入一律拒绝."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host in EXCLUDED_HOSTS:
        return ""
    for key, domain in SITE_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return key
    return ""


def cookies_from_header(header: str, site: str = "ft") -> list[dict[str, object]]:
    """把可选 Cookie 限定到当前媒体域名，绝不发送给另一私站."""
    if site not in SITE_DOMAINS:
        raise BrowserBypassError("Cookie 目标站点不受支持")
    domain = "." + SITE_DOMAINS[site]
    cookies: list[dict[str, object]] = []
    for part in header.split(";"):
        if "=" not in part:
            continue
        name, value = (item.strip() for item in part.split("=", 1))
        if (
            not name
            or not value
            or not re.fullmatch(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+", name)
        ):
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "secure": True,
                "sameSite": "Lax",
            }
        )
    return cookies
