"""Reuters：官方 Artificial Intelligence 专题的文字正稿采集线。

Reuters 的专题页是 B 路线：编辑页负责召回，本站适配器再把视频、Reuters
Breakingviews、AI Weekly、活动与市场噪声挡在正文请求之前。专题的 Load more
由既有浏览器探针点击；不直接调用站方 robots.txt 明确禁止的 ``/pf/api/``。

普通 HTTP 当前会收到 DataDome 401，因此这里没有自建网络客户端。该模块只有在
浏览器档位、注册表与定时策略分别审阅后才应启用；单独导入适配器不会启动抓取。
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from inews.sites import _shared
from inews.textutil import canonical_url, clean_text, parse_datetime

KEY = "reuters"
NAME = "Reuters"
HOME = "https://www.reuters.com"
LABEL = "REUTERS.COM"
TAGLINE = "AI 专题文字稿"
OUT_DIR = "REUTERS.COM"

SEARCHABLE = False
# 不直连 Reuters 的内部分页 API；由既有浏览器在官方页面滚动并点 Load more。
LISTING_FETCHER = None
TOPIC_LABEL = "Reuters AI 专题"
HUBS = ("technology/artificial-intelligence",)
HUB_LABELS = {"technology/artificial-intelligence": TOPIC_LABEL}
# 专题仍混有市场、活动及泛 AI 使用案例，所以不能标成无条件 trusted。
HUB_TIERS = {"technology/artificial-intelligence": "ai"}
LISTING_SCROLLS = True
# 实页按钮完整文案是 “Load more articles”。共享探针按可见文字精确匹配，
# 这里不能简写成 “load more”，否则会把首屏稳定误判为整条河已经展开完。
LOAD_MORE_TEXT = "load more articles"

RULES = (
    "只爬 Reuters 官方 Artificial Intelligence 专题；不做全站关键词搜索",
    "在官方页面滚动并展开 Load more；不调用 robots.txt 禁止的 /pf/api/ 内部接口",
    "只收带发布日期的 Reuters 文字正稿；视频、图集、播客、直播与赞助内容先剔除",
    "AI Weekly、活动、Opinion/Breakingviews、股票、债券、宏观口水不进入正文队列",
    "保留模型、开闭源、芯片、内存、服务器、数据中心、网络、散热及供应链实质事件",
    "正文至少 900 字符、150 词；DataDome/挑战页必须明确失败，不能冒充短正文",
)

# Reuters 正稿以 ``slug-YYYY-MM-DD`` 结尾，且可分布在 technology、business、
# legal、world 等栏目。日期和同域校验一起提供稳定身份；视频等路径另行封死。
LINK_PATTERN = (
    r"/(?:[a-z0-9._~-]+/)+[a-z0-9._~-]+-\d{4}-\d{2}-\d{2}/?$"
)
_ARTICLE_RX = re.compile(
    r"/(?:[a-z0-9._~-]+/)+"
    r"(?P<slug>[a-z0-9](?:[a-z0-9._~-]*[a-z0-9])?)-"
    r"(?P<date>\d{4}-\d{2}-\d{2})/?$",
    re.I,
)
_EXCLUDED_PATH_RX = re.compile(
    r"/(?:video|videos|watch|pictures?|graphics|podcasts?|live|livecoverage|"
    r"breakingviews|commentary|opinion|sponsored|plus|press-releases?)"
    r"(?:/|$)|/markets/quote/",
    re.I,
)

BODY_SELECTORS = (
    "[data-testid='ArticleBody']",
    "article [data-testid='ArticleBody']",
    "article div[data-testid*='ArticleBody']",
    "main article",
)
BODY_PARAGRAPH_SELECTORS = ("[data-testid^='paragraph-']",)
# DataDome 的 HTML 主要是脚本，正常情况下提不出正文；仍把其结构指纹交给共享
# 严格门，防止页面改版后挑战文案或隐藏节点意外长到字符门槛。
RAW_HTML_REJECT_PATTERNS = (
    r"\bx-datadome\b|captcha-delivery\.com",
    r"Please enable JS and disable any ad blocker",
)
ALLOW_TRAFILATURA = False
MIN_BODY_CHARS = 900
MIN_BODY_WORDS = 150
MIN_BODY_COVERAGE = 0.70
# Reuters 正文不是订阅墙；Cookie 不应被镜像。反自动化挑战由浏览器档位处理。
REQUIRES_AUTH = False
EARLIEST = "2025-01-01"

BARRIER_RX = re.compile(
    r"(?:please enable js and disable any ad blocker|captcha-delivery\.com|"
    r"\bx-datadome\b|access denied|are you a robot|unusual activity|"
    r"verify (?:that )?you are human)",
    re.I,
)

_AI_TOPIC_RX = re.compile(
    r"\b(?:artificial intelligence|generative ai|genai|machine learning|"
    r"deep learning|ai|llms?|large language models?|foundation models?|"
    r"frontier models?|reasoning models?|multimodal models?|agentic|ai agents?|"
    r"model training|model inference|open[ -]?weight|open[ -]?source models?|"
    r"openai|chatgpt|anthropic|claude|deepmind|gemini|deepseek|hugging ?face|"
    r"mistral|llama|qwen|grok|xai|perplexity|scale ai|cohere)\b",
    re.I,
)
_INFRA_RX = re.compile(
    r"\b(?:data[ -]?cent(?:er|re)s?|datacent(?:er|re)s?|compute capacity|"
    r"gpu(?:s| cloud)?|hbm\d*|high.bandwidth memory|dram|nand|memory chips?|"
    r"ai chips?|accelerators?|hyperscalers?|neoclouds?|servers?|racks?|"
    r"semiconductors?|chipmakers?|foundr(?:y|ies)|fabs?|cowos|advanced packaging|"
    r"optical|photonics?|interconnects?|infiniband|nvlink|ethernet|networking chips?|"
    r"liquid cooling|immersion cooling|switchgear|power grids?|power supply|"
    r"electricity demand|cloud infrastructure|supply chain|chip supply)\b",
    re.I,
)
_CORE_ENTITY_RX = re.compile(
    r"\b(?:nvidia|amd|tsmc|sk hynix|micron|broadcom|marvell|arm|asml|"
    r"supermicro|equinix|coreweave|groq|cerebras)\b",
    re.I,
)
_MATERIAL_EVENT_RX = re.compile(
    r"\b(?:acquir(?:e|es|ed|ing)|acquisition|agrees? to buy|buys?|bought|"
    r"merger|deals?|contracts?|partner(?:s|ed|ing)?|launch(?:es|ed|ing)?|"
    r"releas(?:e|es|ed|ing)|roll(?:s|ed|ing)? out|unveil(?:s|ed|ing)?|"
    r"open[ -]?sources?|build(?:s|ing)?|construction|expand(?:s|ed|ing)?|"
    r"production|supply|shortage|capacity|orders?|ship(?:s|ped|ping|ments?)?|"
    r"comes? online|goes? online|standards?|rules?|regulat(?:e|ion)|laws?|"
    r"ban(?:s|ned|ning)?|restrict(?:s|ed|ion)|export controls?|"
    r"files? (?:a )?lawsuit|sues?|court|judge|copyright|security flaw|"
    r"cyber risk|outages?|hack(?:s|ed|ing)?)\b",
    re.I,
)
_INFRA_COMMITMENT_RX = re.compile(
    r"\b(?:contracts?|deals?|acquir(?:e|es|ed|ing)|invest(?:s|ed|ing)?|"
    r"build(?:s|ing)?|construction|capex|spend(?:s|ing)?|orders?|capacity|"
    r"supply|ship(?:s|ped|ping|ments?)?|production|launch(?:es|ed|ing)?|"
    r"unveil(?:s|ed|ing)?)\b",
    re.I,
)
_MARKET_RX = re.compile(
    r"\b(?:stocks?|shares?|bonds?|bond yields?|treasur(?:y|ies)|market value|"
    r"market cap|price targets?|wall street|investors?|portfolio|trading|"
    r"bull (?:or|and) bear market|bear market|earnings|quarterly results?|"
    r"record results?|profits?|annual forecasts?|revenue forecasts?|"
    r"sales forecasts?|sales growth|revenue[ -](?:rise|growth|run rate|sharing)|"
    r"guidance|ipo|valuation|fundrais(?:e|es|ing)|venture capital|"
    r"budgets?|\$[\d.]+ billion budget|"
    r"rall(?:y|ies)|tumbles?|surges?|jumps?|slumps?|soars?|falls?|"
    r"nasdaq|dow jones|s&p 500)\b",
    re.I,
)
_MACRO_RX = re.compile(
    r"\b(?:federal reserve|the fed|interest rates?|rate cuts?|inflation|gdp|"
    r"central bankers?|factory activity|financial stability|jobs report|"
    r"payrolls?|unemployment|economic outlook|currency|forex)\b",
    re.I,
)
_CHATTER_RX = re.compile(
    r"\b(?:op-?ed|interview|q&a|analysis|takeaways?|what to know|"
    r"warn(?:s|ed|ing)?|says?|tells?|argues?|believes?|predicts?|expects?|"
    r"urges?|calls? for|weighs? in|speaks? about|on what.s next)\b",
    re.I,
)
_PERSONNEL_RX = re.compile(
    r"\b(?:names?|appoints?|promotes?|hires?)\b.{0,70}"
    r"\b(?:ceo|chief executive|president|head)\b|"
    r"\b(?:steps down|resigns?|retires?|succession|successor|executive exits?|"
    r"leadership shake-up|job cuts?|layoffs?|founders? who walked away|"
    r"executives? who walked away)\b|"
    # “A hands Company to B” 是 Reuters 常见的接班标题；即使摘要顺手提到
    # AI，也仍然是人事稿，不该进入模型/基础设施材料库。
    r"\b(?:hands?|handing)\b.{0,45}\bto\b",
    re.I,
)
_PERIPHERAL_RX = re.compile(
    r"\b(?:smartphones?|iphone|consumer gadgets?|dating|homework|classrooms?|"
    r"schoolchildren|teachers?|mental health|hollywood|movies?|music|fashion|"
    r"recipes?|sports?|travel|shopping|retail(?:ers?)?|insurance|insurers?|"
    r"human resources?|hr software|free access to ai tools?|elections?|"
    r"political campaign|advertising|ad business|"
    r"healthcare diagnosis|medical diagnosis|farmers?|agriculture)\b",
    re.I,
)
_CRYPTO_RX = re.compile(
    r"\b(?:crypto|bitcoin|ether(?:eum)?|stablecoins?|nfts?|memecoins?)\b",
    re.I,
)
_EDITORIAL_NOISE_RX = re.compile(
    r"\b(?:ai weekly|reuters next|reuters events?|breakingviews|commentary|"
    r"opinion|sponsored|brand features?|partner content|podcasts?|videos?|"
    r"photo essay|pictures?|graphics)\b",
    re.I,
)
_SECTION_NOISE_RX = re.compile(
    r"\b(?:most read|most popular|recommended|related stories|more from reuters|"
    r"editor.s picks|sponsored|breakingviews|opinion|videos?|pictures?)\b",
    re.I,
)


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _first_text(asset: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = asset.get(key)
        if isinstance(value, str) and value.strip():
            return clean_text(value)
    return ""


def _label_text(value: Any) -> str:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, dict):
        return " ".join(
            text
            for key in ("name", "title", "label", "type", "slug")
            if (text := _label_text(value.get(key)))
        )
    if isinstance(value, list):
        return " ".join(text for item in value if (text := _label_text(item)))
    return ""


def _asset_url(asset: dict[str, Any], base: str = HOME) -> str:
    raw = _first_text(asset, "canonical_url", "canonicalUrl", "url", "href", "web_url")
    return canonical_url(raw, base)


def article_id(url: str) -> str:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in {"reuters.com", "www.reuters.com"}:
        return ""
    if _EXCLUDED_PATH_RX.search(parts.path):
        return ""
    match = _ARTICLE_RX.fullmatch(parts.path)
    if not match:
        return ""
    return f"{match.group('date')}-{match.group('slug').lower()}"


def search_url(keyword: str, page: int = 1) -> str:
    raise RuntimeError("Reuters 未配搜索线:只走官方 AI 专题")


def hub_url(slug: str, page: int = 1) -> str:
    # Reuters 没有公开的 ?page=N 专题页。浏览器一次打开后持续滚动并点 Load more；
    # collect 若被要求多页，会靠“没有新的”停下，不能伪造一个站方不支持的分页。
    return f"{HOME}/{str(slug).strip('/')}/"


def admission_reason(asset: dict[str, Any]) -> str:
    """返回结构与主题准入理由；空串表示不值得打开一次正文。"""
    url = _asset_url(asset)
    if not article_id(url):
        return ""

    kind = _first_text(asset, "type", "content_type", "contentType").lower()
    media = _first_text(
        asset, "primary_media_type", "primaryMediaType", "media_type", "mediaType"
    ).lower()
    if any(
        word in kind or word in media
        for word in ("video", "podcast", "gallery", "graphic", "live")
    ):
        return ""
    if any(
        _truthy(asset.get(key))
        for key in (
            "isVideo", "is_video", "isVerticalVideoContent",
            "is_vertical_video_content", "isLiveContent", "is_live_content",
            "isSponsored", "is_sponsored", "sponsored",
        )
    ):
        return ""

    title = _first_text(asset, "title", "headline", "heading")
    summary = _first_text(asset, "description", "summary", "dek", "subheadline")
    section = " ".join(
        text
        for key in ("section", "kicker", "labels", "badges")
        if (text := _label_text(asset.get(key)))
    )
    evidence = f"{title} {summary} {section}"
    if len(title) < 12 or _EDITORIAL_NOISE_RX.search(f"{title} {section}"):
        return ""

    direct_ai = bool(_AI_TOPIC_RX.search(evidence))
    infra = bool(_INFRA_RX.search(evidence))
    entity_in_context = bool(_CORE_ENTITY_RX.search(evidence) and (direct_ai or infra))
    if not (direct_ai or infra or entity_in_context):
        return ""

    title_topic = bool(
        _AI_TOPIC_RX.search(title)
        or _INFRA_RX.search(title)
        or (_CORE_ENTITY_RX.search(title) and (direct_ai or infra))
    )
    material = bool(_MATERIAL_EVENT_RX.search(title))
    # 摘要里偶然出现 AI 不能让普通商业、政治或消费稿入库。唯一例外是摘要明确
    # 交代了数据中心/芯片等实质动作，而标题也写出了那个动作。
    if not title_topic and not (infra and material):
        return ""
    if _CRYPTO_RX.search(title):
        return ""
    if _PERSONNEL_RX.search(title):
        return ""
    if _PERIPHERAL_RX.search(title) and not (infra and material):
        return ""
    if _MACRO_RX.search(title) and not (infra and material):
        return ""

    if _MARKET_RX.search(title):
        # 融资/股价标题只有同时陈述了可核验的基础设施建设或供给动作才留下。
        if not (infra and _INFRA_COMMITMENT_RX.search(title)):
            return ""
    if _CHATTER_RX.search(title) and not material:
        return ""
    return "core_infrastructure" if infra else "ai_article"


def _nearest_card(link, root):
    fallback = link.parent
    for depth, parent in enumerate(link.parents):
        if parent is root or getattr(parent, "name", "") in {"main", "body", "html"}:
            break
        marker = " ".join(
            (
                clean_text(parent.get("data-testid")),
                " ".join(parent.get("class") or []),
            )
        ).lower()
        if parent.name in {"article", "li"} or "storycard" in marker or "story-card" in marker:
            return parent
        if depth >= 5:
            break
        fallback = parent
    return fallback


def _inside_noisy_section(link, root) -> bool:
    for parent in link.parents:
        if parent is root or getattr(parent, "name", "") in {"body", "html"}:
            break
        if parent.name == "aside" or clean_text(parent.get("role")).lower() == "complementary":
            return True
        marker = " ".join(
            (
                clean_text(parent.get("aria-label")),
                clean_text(parent.get("data-testid")),
                " ".join(parent.get("class") or []),
            )
        )
        if _SECTION_NOISE_RX.search(marker):
            return True
        if parent.name == "section":
            headings = parent.find_all(["h1", "h2"], recursive=False)
            if any(
                _SECTION_NOISE_RX.search(clean_text(node.get_text(" ", strip=True)))
                for node in headings
            ):
                return True
    return False


def _assets_from_html(html: str, base: str) -> list[dict[str, Any]]:
    if BARRIER_RX.search(str(html or "")):
        raise RuntimeError("Reuters AI 专题返回了 DataDome/人机验证页")
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("main")
    if root is None:
        raise RuntimeError("Reuters AI 专题缺少 main 主河，页面结构可能已改版")

    assets: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()
    for link in root.find_all("a", href=re.compile(LINK_PATTERN, re.I)):
        url = canonical_url(clean_text(link.get("href")), base)
        identifier = article_id(url)
        if not identifier or identifier in seen_candidates:
            continue
        link_marker = clean_text(link.get("data-testid")).lower()
        # 实页主河不用 h1-h4：标题是 TitleLink → TitleHeading；同一 URL 还会先
        # 出现一次 MediaImageLink。图片、Related 与 Read more 都不能抢走标题身份。
        if link_marker == "mediaimagelink":
            continue
        heading = link.select_one("[data-testid='TitleHeading']")
        if heading is None:
            heading = link.find(["h1", "h2", "h3", "h4"])
        if heading is None:
            heading = link.find_parent(["h1", "h2", "h3", "h4"])
        is_title_link = link_marker == "titlelink"
        if heading is None and not is_title_link and "heading" not in link_marker:
            continue
        if _inside_noisy_section(link, root):
            continue
        title = clean_text(
            heading.get_text(" ", strip=True) if heading is not None
            else link.get_text(" ", strip=True)
        )
        if len(title) < 12:
            continue
        seen_candidates.add(identifier)
        card = _nearest_card(link, root)
        summary = ""
        for paragraph in card.find_all("p") if card is not None else ():
            candidate = clean_text(paragraph.get_text(" ", strip=True))
            if candidate and candidate != title and len(candidate) > len(summary):
                summary = candidate
        time_node = (
            card.select_one("time[data-testid='DateLineText'][datetime]")
            if card is not None
            else None
        )
        if time_node is None and card is not None:
            time_node = card.find("time")
        published = clean_text(
            (time_node.get("datetime") if time_node is not None else "")
            or (time_node.get_text(" ", strip=True) if time_node is not None else "")
        )
        marker = " ".join(
            (
                clean_text(card.get("data-testid")) if card is not None else "",
                " ".join(card.get("class") or []) if card is not None else "",
                clean_text(link.get("aria-label")),
            )
        )
        assets.append(
            {
                "type": (
                    "video"
                    if re.search(r"\bvideo(?:story)?card\b", marker, re.I)
                    else "article"
                ),
                "url": url,
                "title": title,
                "description": summary,
                "published_time": published,
                "section": "",
                "isSponsored": bool(re.search(r"\b(?:sponsored|partner content)\b", marker, re.I)),
            }
        )
    if not seen_candidates:
        raise RuntimeError("Reuters AI 专题主河没有可识别的日期型标题链接")
    return assets


def _assets_from_structured(payload: Any) -> list[dict[str, Any]]:
    """解析人工保存的 Reuters mobile JSON；本模块不会主动请求其内部 API。"""
    assets: list[dict[str, Any]] = []
    recognized = False
    if isinstance(payload, list):
        blocks = payload
    elif isinstance(payload, dict):
        result = payload.get("result")
        if isinstance(result, dict) and isinstance(result.get("articles"), list):
            return [item for item in result["articles"] if isinstance(item, dict)]
        blocks = payload.get("components") or payload.get("blocks") or []
    else:
        blocks = []
    for block in blocks if isinstance(blocks, list) else ():
        if not isinstance(block, dict):
            continue
        block_type = clean_text(block.get("type") or block.get("name")).lower()
        if _SECTION_NOISE_RX.search(block_type):
            continue
        if not any(token in block_type for token in ("story", "latest", "article")):
            continue
        data = block.get("data") if isinstance(block.get("data"), dict) else block
        for key in ("stories", "articles", "items"):
            batch = data.get(key)
            if isinstance(batch, list):
                recognized = True
                assets.extend(item for item in batch if isinstance(item, dict))
                break
    if not recognized:
        raise RuntimeError("Reuters AI 专题结构化列表缺少 stories/articles 主河")
    return assets


def _rows_from_assets(
    assets: list[dict[str, Any]], keyword: str, base: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for asset in assets:
        reason = admission_reason(asset)
        if not reason:
            continue
        url = _asset_url(asset, base)
        identifier = article_id(url)
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        published = _first_text(
            asset, "published_time", "publishedAt", "published_at",
            "display_time", "datePublished", "timestamp",
        )
        if not parse_datetime(published):
            published = identifier[:10]
        section = _label_text(
            asset.get("section") or asset.get("kicker") or asset.get("labels")
            or asset.get("badges")
        )
        rows.append(
            {
                "article_id": identifier,
                "title_en": _first_text(asset, "title", "headline", "heading"),
                # 摘要是准入证据的一部分；必须跟着行进入台账，否则首次解析通过后，
                # library_rows 的存量复核会在证据缺失的情况下把它立即隐藏。
                "description": _first_text(
                    asset, "description", "summary", "dek", "subheadline"
                ),
                "url": url,
                "published_at": published,
                "section": section,
                "keywords": [keyword],
                "admission_reason": reason,
            }
        )
    return rows


def parse_search_results(
    html: str,
    keyword: str,
    page_url: str = "",
) -> list[dict[str, Any]]:
    base = page_url or hub_url(HUBS[0])
    try:
        payload = json.loads(html)
    except (TypeError, json.JSONDecodeError):
        assets = _assets_from_html(html, base)
    else:
        assets = _assets_from_structured(payload)
    return _rows_from_assets(assets, keyword, base)


def barrier_before_body(text: str, title: str) -> bool:
    return _shared.barrier_before_body(text, title, BARRIER_RX)


def drop_padding(
    rows: dict[str, dict[str, Any]], searched: list[str]
) -> list[str]:
    return []


merge = _shared.merge


def admitted_rows(
    rows: dict[str, dict[str, Any]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    values = list(rows.values()) if isinstance(rows, dict) else list(rows)
    admitted: list[dict[str, Any]] = []
    for row in values:
        candidate = {
            "type": "article",
            "url": row.get("url", ""),
            "title": row.get("title_en") or row.get("title") or "",
            "description": row.get("description", ""),
            "section": row.get("section", ""),
        }
        if admission_reason(candidate):
            admitted.append(row)
    return admitted


newest_first = _shared.newest_first
oldest_first = _shared.oldest_first


def floor_for(since: str) -> str:
    return _shared.floor_for(since, EARLIEST)


def within_window(row: dict[str, Any], since: str) -> bool:
    return _shared.within_window(row, since, EARLIEST)
