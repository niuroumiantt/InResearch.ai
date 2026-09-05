"""Financial Times:地址构造、结果解析、正文规则。

一个站的全部知识集中在一个文件里 —— 加第二个站就照这个形状再写一个,
不必去动编排、台账、渲染那几层。
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, urlsplit

from bs4 import BeautifulSoup

from inews import keywords as kw
from inews.sites import _shared
from inews.textutil import canonical_url, clean_text, parse_datetime

KEY = "ft"
NAME = "Financial Times"
HOME = "https://www.ft.com"
# 页面上给读者看的站名与口号 —— 编排与渲染层只认这套词汇表,不认「ft」二字。
LABEL = "FT.COM"
TAGLINE = "AI 关键词清单"
OUT_DIR = "FT.COM"
# FT 走混合召回:搜索线 + 专题页。Bloomberg 那边是纯专题页 —— 两种立场,
# 由站点声明,编排层不表态。
SEARCHABLE = True
# 搜索页依赖浏览器渲染；没有站点专用的公开列表接口。
LISTING_FETCHER = None
TOPIC_LABEL = kw.TOPIC_LABEL
# 搜索页与专题页都有真分页,列表不靠滚动加长 —— 不滚。
LISTING_SCROLLS = False
# 没有「展开更多」按钮:FT 的列表靠真分页翻,不点。
LOAD_MORE_TEXT = ""
# 抓取规则,印在清单页顶上给人看。只写被测试钉住的事实,不写愿望;
# 不写具体数字(关键词几个、地板哪天)—— 那些另有唯一来源,抄一份就会过时。
RULES = (
    "关键词全文搜索只负责召回;默认清单要求标题命中 AI 主体与具体事件,否则由正文复核",
    "AI 专题页与半导体专题页分别记来源;正文失败且标题证据不足的进入待验证",
    "只收 /content/ 文章详情页;早于时间地板的一律不收",
    "每小时一轮、新增不设上限;正文用站长自己的订阅在可见浏览器里取",
    "每篇按主题中心度、事件、影响、证据、原创、时效打分;次要内容只折叠,不删稿",
)
SEARCH_URL = HOME + "/search?q={q}&sort=date&contentType=article&page={page}"

# 只放行文章详情页;搜索页上还有作者页、专题页、订阅入口。
LINK_PATTERN = r"/content/[0-9a-zA-Z][0-9a-zA-Z-]{7,}"

# 第二条召回线:FT 自己的专题页。这里是**编辑判定**的「这是 AI 稿」,和关键词
# 匹配是两套逻辑 —— 关键词漏掉的(标题正文都不含我们的词、但确实是 AI 报道)
# 只能从这里进来。同域名,不扩大 browser/contract.py 里「能读谁」的边界。
#
# 路径 2026-08-21 站长在浏览器里逐个核对过(面包屑都是 TECH > …)。
# 不是 /topics/ 那种形态。没核实过的分类页不往这里加 —— 猜错了只会每轮
# 白开五页,而且「0 条」看起来和「今天没新闻」一模一样。
#
# technology / cyber-security 2026-08-24 下架(站长裁决):这两条线的编辑判定是
# 「这是科技稿 / 安全稿」,不是「这是 AI 稿」—— 「皮克工厂被黑」这类稿子全从
# 它们进来。留下的两条,编辑判定本身就是 AI(或它的供给侧)。
HUBS = (
    "artificial-intelligence",
    "semiconductors",
)
HUB_LABELS = {
    "artificial-intelligence": kw.AI_HUB_LABEL,
    "semiconductors": kw.SEMICONDUCTOR_HUB_LABEL,
    # v5 前两个栏目共用一个标签，历史台账无法再无损拆开。明确写“不区分”，
    # 比把它猜成 AI 栏目或继续显示含糊的「FT 专题」更诚实。
    "__legacy__": "FT 专题（历史未区分）",
}
# ``ai`` 是强 AI 来源但仍需标题/正文证明；``context`` 是供给链来源，不能
# 因为栏目身份绕过主题判断。``trusted`` 留给真正可以直接准入的栏目。
HUB_TIERS = {
    "artificial-intelligence": "ai",
    "semiconductors": "context",
    "__legacy__": "context",
}

# 正文容器,按信任度从高到低。
BODY_SELECTORS = (
    "article#article-body",
    "div.article__content-body",
    "div[data-component='article-body']",
    "div.n-content-body",
    "div.n-layout__row--content",
    "article",
    "main",
)
BODY_PARAGRAPH_SELECTORS: tuple[str, ...] = ()
RAW_HTML_REJECT_PATTERNS: tuple[str, ...] = ()
ALLOW_TRAFILATURA = True
MIN_BODY_CHARS = 600
MIN_BODY_WORDS = 0
MIN_BODY_COVERAGE = 0.0
REQUIRES_AUTH = True

# 时间硬地板:比这更早的一律不抓。**写在代码里,不靠命令行记得传。**
# 2026-08-21 站长少传了一次 `--since`,积压从 276 涨到 1370 —— 一个「永远不做
# 的事」只写在使用习惯里,它就总有一天不生效。`--since` 只能把窗口收得更窄。
EARLIEST = "2025-01-01"

# 付费墙拦截页的指纹。命中不等于失败 —— 还要看它出现在正文之前还是之后。
BARRIER_RX = re.compile(
    r"(subscribe to unlock|then \$?\d+ per (?:week|month)|"
    r'data-trackable="barrier|barrier-page|/products\?segmentId=|'
    r"choose your subscription|complete your subscription)",
    re.I,
)


def article_id(url: str) -> str:
    """``/content/<uuid>`` 是 FT 自己发的稳定标识 —— 台账认它,不认标题。"""
    match = re.search(
        r"/content/([0-9a-zA-Z][0-9a-zA-Z-]{7,})/?$", urlsplit(url).path
    )
    return match.group(1) if match else ""


def search_url(keyword: str, page: int = 1) -> str:
    """``sort=date`` 让结果按时间而不是相关度排。"""
    return SEARCH_URL.format(
        q=quote_plus(str(keyword or "").strip()), page=max(1, int(page))
    )


def barrier_before_body(text: str, title: str) -> bool:
    return _shared.barrier_before_body(text, title, BARRIER_RX)


def _teaser_container(link: Any) -> Any:
    """从标题链接上溯到含时间与栏目标签的整张卡片。"""
    for parent in link.parents:
        classes = parent.get("class") or []
        if "o-teaser" in classes or parent.name == "article":
            return parent
        if parent.name in {"body", "html"}:
            break
    return link.parent


def _teaser_metadata(teaser: Any) -> tuple[str, str]:
    time_node = teaser.find("time") if teaser else None
    published = (
        clean_text(
            time_node.get("datetime") or time_node.get("data-o-date-datetime")
        )
        if time_node
        else ""
    )
    tag_node = (
        teaser.find(class_=re.compile(r"o-teaser__tag")) if teaser else None
    )
    section = clean_text(tag_node.get_text(" ", strip=True)) if tag_node else ""
    return published, section


def hub_url(slug: str, page: int = 1) -> str:
    """分类页地址。路径段里的斜杠是路径本身,不能编码掉。"""
    path = "/".join(quote_plus(part) for part in str(slug).strip("/").split("/"))
    return f"{HOME}/{path}?page={max(1, int(page))}"


def parse_search_results(
    html: str,
    keyword: str,
    page_url: str = "",
) -> list[dict[str, Any]]:
    """解析一页搜索结果。

    **不再用标题正则复筛一遍。** 搜索走的是站方全文索引,标题里没出现关键词的
    稿子同样是真命中;再筛一次等于拿弱证据推翻强证据。
    """
    base = page_url or search_url(keyword)
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=re.compile(LINK_PATTERN)):
        url = canonical_url(link["href"], base)
        identifier = article_id(url)
        title = clean_text(link.get_text(" ", strip=True))
        if not identifier or identifier in seen or len(title) < 12:
            continue
        seen.add(identifier)
        published, section = _teaser_metadata(_teaser_container(link))
        rows.append(
            {
                "article_id": identifier,
                "title_en": title,
                "url": url,
                "published_at": published,
                "section": section,
                "keywords": [keyword],
            }
        )
    return rows


# ---------------- 合并、排序、凑数剔除 ----------------
# 合并与排序没有一行是 FT 特有的,实现住在 _shared(9-02 加第二个站时搬的);
# 这里保留同名出口,调用方和用例的词汇表不变。

merge = _shared.merge
admitted_rows = _shared.admitted_rows
newest_first = _shared.newest_first
oldest_first = _shared.oldest_first


PADDING_MIN_GROUPS = 3


def drop_padding(
    rows: dict[str, dict[str, Any]],
    searched: list[str],
) -> list[str]:
    """剔掉「搜什么都返回它」的条目,返回被剔除的 article_id。

    站方真实命中不足时会拿最近的普通新闻填满结果页。这类凑数有一个逃不掉的
    指纹:**同一篇出现在几乎每个关键词底下** —— 它不是被搜出来的,而是站点的
    「最新新闻」。真命中不会这样。

    **票按语义组算,不按词算。** 按词算会把最正中靶心的那篇当成凑数删掉
    (一篇好的 AI 报道天然同时命中 AI agent / agentic AI / AI coding),
    判据整个反过来。这个教训来自 yidian 项目 2026-08-07 的实测。

    判据保守:搜过的组少于 3 个不判(样本不足),要出现在**过半**组下才算。
    """
    searched_groups = {kw.group_of(word) for word in searched}
    if len(searched_groups) < PADDING_MIN_GROUPS:
        return []
    threshold = max(PADDING_MIN_GROUPS, (len(searched_groups) + 1) // 2)
    padding = [
        identifier
        for identifier, row in rows.items()
        if len({kw.group_of(w) for w in row.get("keywords", [])}) >= threshold
    ]
    for identifier in padding:
        rows.pop(identifier, None)
    return padding


def floor_for(since: str) -> str:
    return _shared.floor_for(since, EARLIEST)


def within_window(row: dict[str, Any], since: str) -> bool:
    return _shared.within_window(row, since, EARLIEST)
