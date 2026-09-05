"""CNBC：官方 AI 专题的文字稿采集线。

这条线和 Bloomberg 一样只认官方专题，不做全站关键词搜索；不同点是 CNBC 的
专题混有大量视频、股市节目与偶发的非 AI 卡片。页面自己的 ``assetList`` 数据会
明确给出顶层内容类型，因此视频在打开正文前就被剔除，不能靠「正文太短」事后猜。
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from inews.sites import _shared
from inews.textutil import canonical_url, clean_text, parse_datetime

KEY = "cnbc"
NAME = "CNBC"
HOME = "https://www.cnbc.com"
LABEL = "CNBC.COM"
TAGLINE = "AI 专题文字稿"
OUT_DIR = "CNBC.COM"

# B 路线：只走 CNBC 官方 AI 专题。Load More 背后的 assetList 是公开的结构化
# 数据源，能在发现阶段给出 cnbcnewsstory / cnbcvideo，优先使用它而不是渲染
# 200 张卡片后再猜类型。
SEARCHABLE = False
TOPIC_LABEL = "CNBC AI 专题"
HUBS = ("ai-artificial-intelligence",)
HUB_LABELS = {"ai-artificial-intelligence": TOPIC_LABEL}
# 专题本身有 Meta 青少年、Uber 裁员、Cramer 荐股等漏项；即使前置过滤已经很窄，
# 这里仍不赋 Bloomberg 的 unconditional trusted，保留标题/正文复核这道保险。
HUB_TIERS = {"ai-artificial-intelligence": "ai"}
LISTING_SCROLLS = False
LOAD_MORE_TEXT = "load more"

RULES = (
    "只爬 CNBC 官方 AI 专题；沿用页面 Load More 的 assetList 分页，必须读到 totalCount 才算完整",
    "只收顶层类型 cnbcnewsstory；cnbcvideo、/video/、原生广告在点正文之前直接剔除",
    "专题卡片再次做 AI/算力/芯片/数据中心复核；纯股票、Cramer、消费设备与无关卡片不入库",
    "会员专属与仅注册可读卡片不进入重试队列，避免把确定的访问限制伪装成正文抓取失败",
    "正文先公开 HTTPS 直抓，最长正文不足门槛才无头兜底；每篇继续使用统一评分与折叠规则",
)

# 正常文字稿：/YYYY/MM/DD/slug.html。视频多一层 /video/，从路径结构上就不匹配。
LINK_PATTERN = r"/\d{4}/\d{2}/\d{2}/[a-z0-9%._-]+\.html"
_ARTICLE_RX = re.compile(
    r"/(\d{4})/(\d{2})/(\d{2})/([a-z0-9%._-]+)\.html/?$", re.I
)

BODY_SELECTORS = (
    "div.ArticleBody-articleBody",
    "div[class*='ArticleBody-articleBody']",
    "div[data-module='ArticleBody']",
)
# 根容器还含行情组件与“In this article”；正文自己的稳定范围是 ``div.group p``。
BODY_PARAGRAPH_SELECTORS = ("div.group p",)
RAW_HTML_REJECT_PATTERNS: tuple[str, ...] = ()
# CNBC 会把会员正文放进 ``display:none`` 的节点；正常免费稿都有上面的精确容器。
# 因而绝不能在容器失败后让通用提取器猜，否则会把不可见会员全文误当抓取成功。
ALLOW_TRAFILATURA = False
# 实测文字稿正文为数千字，视频页约四百字；视频已结构性排除，600 只负责挡住
# teaser / 注册墙，不误伤一篇正常的短新闻。
MIN_BODY_CHARS = 600
MIN_BODY_WORDS = 0
MIN_BODY_COVERAGE = 0.0
REQUIRES_AUTH = False
EARLIEST = "2025-01-01"

BARRIER_RX = re.compile(
    r"(?:sign in to (?:continue|access)|create (?:a )?free account to continue|"
    r"subscribe to cnbc pro|join (?:the )?investing club)",
    re.I,
)

_GRAPHQL_URL = "https://webql-redesign.cnbcfm.com/graphql"
_SECTION_ID = 107230561
_PAGE_SIZE = 30  # 站方接口会把更大的请求截成 30。
_MAX_PAGES = 20
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_ASSET_QUERY = """
query getAssetList(
  $id: Int!, $offset: Int!, $pageSize: Int!, $nonFilter: Boolean,
  $includeNative: Boolean, $include: [String]!
) {
  assetList(
    id: $id, offset: $offset, pageSize: $pageSize,
    nonFilter: $nonFilter, includeNative: $includeNative, include: $include
  ) {
    assets {
      id brand type url native datePublished description title headline premium
      contentClassification
      section { id title eyebrow type url subType sectionLabel }
      author { id name url }
    }
    pagination { page totalCount pageSize }
  }
}
""".strip()


def _payload(offset: int) -> bytes:
    return json.dumps(
        {
            "operationName": "getAssetList",
            "variables": {
                "id": _SECTION_ID,
                "offset": offset,
                "pageSize": _PAGE_SIZE,
                "nonFilter": True,
                "includeNative": False,
                "include": [],
            },
            "query": _ASSET_QUERY,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _asset_page(offset: int) -> dict[str, Any]:
    request = urllib.request.Request(
        _GRAPHQL_URL,
        data=_payload(offset),
        headers={
            "User-Agent": _USER_AGENT,
            "Referer": hub_url(HUBS[0]),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=40) as response:  # noqa: S310 固定 HTTPS
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if payload.get("errors"):
        message = clean_text(payload["errors"])
        raise RuntimeError(f"CNBC assetList 返回错误:{message[:300]}")
    result = payload.get("data", {}).get("assetList")
    if not isinstance(result, dict) or not isinstance(result.get("assets"), list):
        raise RuntimeError("CNBC assetList 缺少 assets，页面接口可能已经改版")
    return result


def fetch_listing(url: str) -> tuple[str, str]:
    """完整读取 Load More 的结构化分页；不完整时失败，不拿半份清单冒充成功。"""
    if canonical_url(url) != canonical_url(hub_url(HUBS[0])):
        raise RuntimeError(f"CNBC 列表抓取器只接受官方 AI 专题:{url}")

    assets: list[dict[str, Any]] = []
    seen: set[str] = set()
    offset = 0
    total: int | None = None
    raw_loaded = 0
    for _page in range(_MAX_PAGES):
        result = _asset_page(offset)
        batch = result["assets"]
        pagination = result.get("pagination") or {}
        if total is None:
            try:
                total = int(pagination.get("totalCount"))
            except (TypeError, ValueError):
                total = None
            if total is None or total < 0:
                raise RuntimeError(
                    "CNBC assetList 缺少有效 totalCount，不能证明 Load More 已完整展开"
                )
        if not batch:
            break
        raw_loaded += len(batch)
        for asset in batch:
            identity = str(asset.get("id") or asset.get("url") or "")
            if identity and identity not in seen:
                seen.add(identity)
                assets.append(asset)
        offset += len(batch)
        if total is not None and offset >= total:
            break
        if total is None and len(batch) < _PAGE_SIZE:
            break

    if total is None or raw_loaded < total or len(assets) != total:
        raise RuntimeError(
            "CNBC Load More 未展开完整:"
            f"接口读取 {raw_loaded}/{total} 条，去重后 {len(assets)} 条"
        )
    return (
        json.dumps(
            {
                "kind": "cnbc-asset-list",
                "total_count": total,
                "raw_loaded": raw_loaded,
                "assets": assets,
            },
            ensure_ascii=False,
        ),
        hub_url(HUBS[0]),
    )


# 主题证据：直接 AI/模型信号，以及用户明确点名的供给侧信号。宽实体必须和
# 芯片/供给/模型上下文一起出现；不能看到 Apple/Meta 就当 AI。
_AI_TOPIC_RX = re.compile(
    r"\b(?:artificial intelligence|generative ai|genai|ai|llms?|large language models?|"
    r"foundation models?|frontier models?|reasoning models?|agentic|ai agents?|"
    r"openai|chatgpt|anthropic|claude|deepmind|gemini|deepseek|hugging ?face|"
    r"mistral|llama|qwen|grok|xai|perplexity|scale ai)\b",
    re.I,
)
_INFRA_RX = re.compile(
    r"\b(?:data[ -]?cent(?:er|re)s?|datacent(?:er|re)s?|gpu(?:s| cloud)?|hbm\d*|"
    r"high.bandwidth memory|dram|nand|ai chips?|accelerators?|hyperscalers?|"
    r"neoclouds?|servers?|racks?|semiconductors?|foundr(?:y|ies)|fabs?|cowos|"
    r"advanced packaging|optical|interconnects?|infiniband|nvlink|ethernet|"
    r"liquid cooling|immersion cooling|transformers?|switchgear|power grids?)\b",
    re.I,
)
_CORE_ENTITY_RX = re.compile(
    r"\b(?:nvidia|amd|tsmc|sk hynix|micron|broadcom|marvell|arm|asml|"
    r"supermicro|equinix|coreweave|groq)\b",
    re.I,
)
_CORE_EVENT_RX = re.compile(
    r"\b(?:acquir(?:e|es|ed|ing)|acquisition|buy|buys|bought|deal|"
    r"partner(?:s|ed|ing)?\s+with|partnership|"
    r"launch(?:es|ed|ing)?|releas(?:e|es|ed|ing)|roll(?:s|ed|ing)? out|"
    r"unveil(?:s|ed|ing)?|build(?:s|ing)?|construction|expand(?:s|ed|ing)?|"
    r"production|supply|shortage|capacity|orders?|ship(?:s|ped|ping|ments?)|"
    r"online|standard|ban(?:s|ned|ning)?|block(?:s|ed|ing)?|regulat(?:e|ion)|"
    r"lawsuit|court|policy|outage|hack|security|price hikes?|"
    r"cross(?:es|ed).{0,30}capabilit(?:y|ies)|open.source|open models?)\b",
    re.I,
)
_MARKET_NOISE_RX = re.compile(
    r"\b(?:stocks?|shares?|wall street|market value|market cap|price target|buybacks?|"
    r"portfolio|investors?|earnings|quarterly estimates?|sales forecast|ipo|"
    r"rall(?:y|ies)|tumbles?|surges?|jumps?|pops?|skyrockets?|upside|hold for now|"
    r"best.value|unloved stocks?|ai trade)\b|\bjim cramer\b|\bcramer\b",
    re.I,
)
_EARNINGS_NOISE_RX = re.compile(
    r"\b(?:earnings|quarter(?:ly)?|estimates?|sales forecast|revenue forecast)\b",
    re.I,
)
_MARKET_WITH_MATERIAL_EVENT_RX = re.compile(
    r"\b(?:acquir(?:e|es|ed|ing)|agrees? to buy|deal|launch(?:es|ed|ing)?|"
    r"releas(?:e|es|ed|ing)|build(?:s|ing)?|construction|production|supply|"
    r"shortage|capacity|orders?|ship(?:s|ped|ping|ments?)|online|price hikes?)\b",
    re.I,
)
_VERIFIABLE_TITLE_EVENT_RX = re.compile(
    r"\b(?:acquir(?:e|es|ed|ing)|acquisition|agrees? to buy|buys?|bought|deal|"
    r"partner(?:s|ed|ing)?\s+with|partnership|launch(?:es|ed|ing)?|"
    r"releas(?:e|es|ed|ing)|roll(?:s|ed|ing)? out|unveil(?:s|ed|ing)?|"
    r"build(?:s|ing)?|construction|expand(?:s|ed|ing)?|production|supply|"
    r"shortage|capacity|orders?|ship(?:s|ped|ping|ments?)|"
    r"(?:comes?|goes?|went|brought|will be) online|"
    r"price hikes?|standard|ban(?:s|ned|ning)?|block(?:s|ed|ing)?|"
    r"regulat(?:e|ion)|lawsuit|court|outages?|hack|"
    r"cross(?:es|ed).{0,30}capabilit(?:y|ies))\b",
    re.I,
)
_INFRA_COMMITMENT_RX = re.compile(
    r"\b(?:build(?:s|ing)?|construction|capex|spend(?:s|ing)?|orders?|capacity|"
    r"supply|ship(?:s|ped|ping|ments?)|production)\b",
    re.I,
)
_MEMBERS_ONLY_RX = re.compile(
    r"(?:subscriber|investing.?club|registered.?only|premium|pro)", re.I
)
_PERIPHERAL_RX = re.compile(
    r"\b(?:iphone|ipad|mac mini|mac studio|smartphones?|social media|teen apps?|"
    r"dating|vacation|recipes?|gaming|cybercab|election|senate primary|campaign)\b",
    re.I,
)
_CRYPTO_RX = re.compile(r"\b(?:crypto|bitcoin|stablecoins?|ai tokens?)\b", re.I)
_CHATTER_RX = re.compile(
    r"\b(?:op-ed|interview|jim cramer|cramer|bill gates|goldman sachs partner)\b|"
    r"\b(?:ceo|chief|governor|gov\.?|president|trump|committee|analyst|partner)"
    r"(?=\W|$)\s*:|"
    r"\b(?:ceo|chief|governor|gov\.?|president|trump|committee|analyst|partner)"
    r"(?=\W|$).{0,45}\b(?:says?|tells?|warns?|argues?|believes?|predicts?|"
    r"defends?|claims?|urges?|expects?|sees?|calls?)\b|"
    r"\b(?:says?|tells?|warns?|argues?|believes?|predicts?|defends?|claims?|"
    r"urges?|expects?|sees?|calls?)\b.{0,45}\b(?:ceo|chief|governor|gov\.?|"
    r"president|trump|committee|analyst|partner)(?=\W|$)",
    re.I,
)
_PERSONNEL_RX = re.compile(
    r"\b(?:executive exits?|successor|succession|chief .{0,30} is out|ceo era|"
    r"takes the helm|steps down|resigns?|getting (?:his|her) mojo)\b|"
    r"\b(?:appointed|named)\b.{0,35}\bceo\b",
    re.I,
)
_NAMED_ERA_RX = re.compile(
    r"\benters\s+(?:[A-Z][\w.’'-]*\s+){1,3}era\b"
)
_NAMED_CHATTER_RX = re.compile(
    r"\b(?:[A-Z][A-Za-z.’'-]*\s+){1,2}"
    r"(?:says?|tells?|warns?|argues?|believes?|predicts?|defends?|claims?|"
    r"urges?|expects?|sees?|calls?)\b"
)
_SOFT_SOCIAL_RX = re.compile(
    r"\b(?:worker trust|job disruption|inequality|backlash)\b", re.I
)


def admission_reason(asset: dict[str, Any]) -> str:
    """返回准入理由；空串表示不值得为它打开一次正文。"""
    url = canonical_url(str(asset.get("url") or ""), HOME)
    kind = str(asset.get("type") or "").lower()
    if kind != "cnbcnewsstory":
        return ""
    if "/video/" in urlsplit(url).path.lower() or not article_id(url):
        return ""
    if asset.get("native"):
        return ""
    raw_classifications = asset.get("contentClassification") or []
    classifications = (
        raw_classifications
        if isinstance(raw_classifications, str)
        else " ".join(str(item) for item in raw_classifications)
    )
    if asset.get("premium") or _MEMBERS_ONLY_RX.search(classifications):
        return ""

    title = clean_text(asset.get("headline") or asset.get("title"))
    description = clean_text(asset.get("description"))
    evidence = f"{title} {description}"
    direct_ai = bool(_AI_TOPIC_RX.search(evidence))
    infra = bool(_INFRA_RX.search(evidence))
    entity_with_context = bool(_CORE_ENTITY_RX.search(evidence) and (direct_ai or infra))
    if not (direct_ai or infra or entity_with_context):
        return ""
    # CNBC 的 AI 页偶尔混进纯币价与竞选卡片；它们有 AI 两个字也不属于本产品。
    if _CRYPTO_RX.search(evidence):
        return ""
    if _PERSONNEL_RX.search(title) or _NAMED_ERA_RX.search(title):
        return ""
    title_infra = bool(_INFRA_RX.search(title))
    if _PERIPHERAL_RX.search(evidence) and not (
        title_infra and _VERIFIABLE_TITLE_EVENT_RX.search(title)
    ):
        return ""

    title_material = bool(_VERIFIABLE_TITLE_EVENT_RX.search(title))
    # 股票词本身不构成新闻。复合标题只有同时给出模型、芯片、数据中心等具体
    # 供给事实时才留下，和 Techmeme 的现行规则保持一致。
    if _MARKET_NOISE_RX.search(title):
        if _EARNINGS_NOISE_RX.search(title) and not (
            title_infra and _INFRA_COMMITMENT_RX.search(title)
        ):
            return ""
        if not (
            _MARKET_WITH_MATERIAL_EVENT_RX.search(title)
            and (direct_ai or infra)
        ):
            return ""
    # 个人观点、节目口水和泛社会讨论不值得打开正文；若同一句同时陈述了收购、
    # 供货、上线等可核验事件，则保留那个事件。
    if (
        _CHATTER_RX.search(title) or _NAMED_CHATTER_RX.search(title)
    ) and not title_material:
        return ""
    if _SOFT_SOCIAL_RX.search(title) and not infra:
        return ""
    return "core_infrastructure" if infra else "ai_article"


def article_id(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host not in {"cnbc.com", "www.cnbc.com"}:
        return ""
    match = _ARTICLE_RX.fullmatch(parts.path)
    return "-".join(match.groups()) if match else ""


def search_url(keyword: str, page: int = 1) -> str:
    raise RuntimeError("CNBC 未配搜索线:只走官方 AI 专题")


def hub_url(slug: str, page: int = 1) -> str:
    return f"{HOME}/{str(slug).strip('/')}/"


def _rows_from_assets(
    assets: list[dict[str, Any]], keyword: str, base: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for asset in assets:
        reason = admission_reason(asset)
        if not reason:
            continue
        url = canonical_url(str(asset.get("url") or ""), base)
        identifier = article_id(url)
        title = clean_text(asset.get("headline") or asset.get("title"))
        if not identifier or identifier in seen or len(title) < 12:
            continue
        seen.add(identifier)
        section_data = asset.get("section") or {}
        published = clean_text(asset.get("datePublished"))
        if not parse_datetime(published):
            published = identifier[:10]
        rows.append(
            {
                "article_id": identifier,
                "title_en": title,
                "url": url,
                "published_at": published,
                "section": clean_text(
                    section_data.get("eyebrow") or section_data.get("title")
                ),
                "keywords": [keyword],
                "admission_reason": reason,
            }
        )
    return rows


def _assets_from_html(html: str) -> list[dict[str, Any]]:
    """兼容测试/人工传入的渲染 HTML；主线 GraphQL 不完整时仍然失败关闭。"""
    soup = BeautifulSoup(html, "html.parser")
    assets: list[dict[str, Any]] = []
    for card in soup.select("[data-test='Card']"):
        title_link = card.select_one("a.Card-title[href]")
        if title_link is None:
            continue
        classes = " ".join(card.get("class") or [])
        url = canonical_url(title_link.get("href", ""), HOME)
        is_video = "Card-cnbcvideo" in classes or "/video/" in urlsplit(url).path
        classifications: list[str] = []
        if card.select_one("a[href*='/investingclub/'], [class*='ProPill'], [class*='proPill']"):
            classifications.append("investingClub")
        description_node = card.select_one(".Card-description")
        time_node = card.select_one(".Card-time, time")
        section_node = card.select_one(".Card-eyebrow")
        assets.append(
            {
                "type": "cnbcvideo" if is_video else "cnbcnewsstory",
                "url": url,
                "headline": clean_text(title_link.get_text(" ", strip=True)),
                "description": clean_text(
                    description_node.get_text(" ", strip=True)
                    if description_node else ""
                ),
                "datePublished": clean_text(
                    (time_node.get("datetime") if time_node else "")
                    or (time_node.get_text(" ", strip=True) if time_node else "")
                ),
                "contentClassification": classifications,
                "section": {
                    "eyebrow": clean_text(
                        section_node.get_text(" ", strip=True)
                        if section_node else ""
                    )
                },
            }
        )
    return assets


def parse_search_results(
    html: str,
    keyword: str,
    page_url: str = "",
) -> list[dict[str, Any]]:
    base = page_url or hub_url(HUBS[0])
    assets: list[dict[str, Any]]
    try:
        payload = json.loads(html)
    except (TypeError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict) and payload.get("kind") == "cnbc-asset-list":
        assets = payload.get("assets") or []
    else:
        assets = _assets_from_html(html)
    return _rows_from_assets(assets, keyword, base)


def barrier_before_body(text: str, title: str) -> bool:
    return _shared.barrier_before_body(text, title, BARRIER_RX)


def drop_padding(
    rows: dict[str, dict[str, Any]], searched: list[str]
) -> list[str]:
    return []


merge = _shared.merge
admitted_rows = _shared.admitted_rows
newest_first = _shared.newest_first
oldest_first = _shared.oldest_first


def floor_for(since: str) -> str:
    return _shared.floor_for(since, EARLIEST)


def within_window(row: dict[str, Any], since: str) -> bool:
    return _shared.within_window(row, since, EARLIEST)


LISTING_FETCHER = fetch_listing
