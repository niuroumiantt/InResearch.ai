"""The Wall Street Journal：官方 AI 专题的文字正稿采集线。

WSJ 与 Bloomberg 一样走 B 路线：只读编辑维护的 AI 专题，不做全站关键词
搜索。不同之处是 WSJ 专题会混入视频、Opinion、市场简报和消费侧软稿，所以
专题只负责召回，本站适配器还要在打开正文前做一次严格准入。
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from inews.sites import _shared
from inews.textutil import canonical_url, clean_text, parse_datetime

KEY = "wsj"
NAME = "The Wall Street Journal"
HOME = "https://www.wsj.com"
LABEL = "WSJ.COM"
TAGLINE = "AI 专题文字稿"
OUT_DIR = "WSJ.COM"

SEARCHABLE = False
# 普通 HTTP 请求会被 WSJ 拒绝；列表与正文都走现有的人工有头/BPC 通道。
LISTING_FETCHER = None
TOPIC_LABEL = "WSJ AI 专题"
HUBS = ("tech/ai",)
HUB_LABELS = {"tech/ai": TOPIC_LABEL}
# 官方专题仍有股票、人事与生活方式噪声，不能像 Bloomberg 那样无条件 trusted。
HUB_TIERS = {"tech/ai": "ai"}
LISTING_SCROLLS = False
LOAD_MORE_TEXT = ""

RULES = (
    "只爬 WSJ 官方 Artificial Intelligence 专题；不做全站关键词搜索",
    "历史河使用 /tech/ai?page=N；只解析页面主河 moreInArticles，不收侧栏与泛科技 View All",
    "只收 type=article 的文字正稿；视频、Opinion、广告在打开正文前结构性剔除",
    "再次复核 AI、模型、数据中心、芯片、存储、网络、散热与供给链；股票、人事、口水和生活方式稿不入库",
    "正文至少 900 字符、150 词；通常达到声明词数的 70%，保留墙容器时须达到 90%",
)

# 现代 WSJ 正稿以 8 位站内 ID 结尾。专题主河可能把稿件挂在 CIO、Business 等
# 子路径下，因此不把路径写死成 /tech/ai；结构化主河和下面的域名校验共同定界。
LINK_PATTERN = r"/(?:[a-z0-9._~-]+/)+[a-z0-9%._~-]+-[a-f0-9]{8}/?$"
_ARTICLE_RX = re.compile(
    r"/(?:[a-z0-9._~-]+/)+[a-z0-9%._~-]+-(?P<id>[a-f0-9]{8})/?$",
    re.I,
)
_EXCLUDED_PATH_RX = re.compile(
    r"/(?:video|videos|opinion|podcasts?|livecoverage)(?:/|$)", re.I
)

BODY_SELECTORS = ("article div.crawler",)
BODY_PARAGRAPH_SELECTORS = (
    "section > p[data-type='paragraph']",
    "section > div.paywall > p[data-type='paragraph']",
)
# WSJ 的墙是 HTML class，不会进入正文 ``innerText``；但现场确认 BPC 恢复到
# 作者简介/Up Next 后仍保留这个 class。它因此只触发共享的 90% 严格恢复率门，
# 不能一票否决。``div.paywall`` 还是恢复后的正文容器，也不能被宽泛词误杀。
RAW_HTML_REJECT_PATTERNS = (r"\bPaywalledContentContainer\b",)
ALLOW_TRAFILATURA = False
# 现场样本：预览约 912 字符/142 词；BPC 完整稿 3960 字符/607 词，页面声明
# 625 词且仍保留墙 class。通常使用 70%，命中该 class 时共享契约提升到 90%。
MIN_BODY_CHARS = 900
MIN_BODY_WORDS = 150
MIN_BODY_COVERAGE = 0.70
REQUIRES_AUTH = True
EARLIEST = "2025-01-01"

BARRIER_RX = re.compile(
    r"(?:subscribe to read|sign in to keep reading|continue reading.{0,80}"
    r"WSJ subscription|PaywalledContentContainer|please enable JS and disable any "
    r"ad blocker|captcha-delivery|are you a robot|unusual activity)",
    re.I,
)

_AI_TOPIC_RX = re.compile(
    r"\b(?:artificial intelligence|generative ai|genai|machine learning|deep learning|"
    r"ai|llms?|large language models?|foundation models?|frontier models?|"
    r"reasoning models?|agentic|ai agents?|model training|model inference|"
    r"openai|chatgpt|anthropic|claude|deepmind|gemini|deepseek|hugging ?face|"
    r"mistral|llama|qwen|grok|xai|perplexity|scale ai|moonshot ai)\b",
    re.I,
)
_INFRA_RX = re.compile(
    r"\b(?:data[ -]?cent(?:er|re)s?|datacent(?:er|re)s?|gpu(?:s| cloud)?|hbm\d*|"
    r"high.bandwidth memory|dram|nand|memory chips?|ai chips?|accelerators?|"
    r"hyperscalers?|neoclouds?|servers?|racks?|semiconductors?|chipmakers?|"
    r"foundr(?:y|ies)|fabs?|cowos|advanced packaging|optical|photonics?|"
    r"interconnects?|infiniband|nvlink|ethernet|networking chips?|"
    r"liquid cooling|immersion cooling|switchgear|power grids?|power supply|"
    r"electricity demand|cloud infrastructure|compute capacity|supply chain)\b",
    re.I,
)
_CORE_ENTITY_RX = re.compile(
    r"\b(?:nvidia|amd|tsmc|sk hynix|micron|broadcom|marvell|arm|asml|"
    r"supermicro|equinix|coreweave|groq|cerebras)\b",
    re.I,
)
_MARKET_RX = re.compile(
    r"\b(?:market talk|morning download|morning risk|what.s news|newsletter|"
    r"stocks?|shares?|ipo|valuation|market value|market cap|price target|"
    r"wall street|private equity|investors?|investment|portfolio|earnings|"
    r"quarterly results?|revenue|sales|guidance|total addressable market|"
    r"venture fund|analyst ratings?|buybacks?|fundraising|raises? \$?\d|"
    r"venture capital|banker|financial engineering)\b",
    re.I,
)
_PERSONNEL_RX = re.compile(
    r"\b(?:co-?founder|researcher|executive|chief|head of [a-z -]+).{0,60}"
    r"\b(?:joins?|leaves?|has left)\b|"
    r"\b(?:names?|appoints?|promotes?|hires?)\b.{0,80}"
    r"\b(?:as|to be)\b.{0,24}\b(?:ceo|chief executive|president|head)\b|"
    r"\b(?:salary|compensation|successor|succession|steps down|resigns?|retires?|"
    r"has left|leaves? (?:the )?company|departures?|shake-up|"
    r"leadership|chief executive is out|ceo is out|named (?:the )?ceo|"
    r"appointed (?:as )?ceo|new ceo|executive exits?|hires?|layoffs?|job cuts?)\b",
    re.I,
)
_PERIPHERAL_RX = re.compile(
    r"\b(?:apple maps|smart glasses|robotaxis?|classrooms?|schoolchildren|teachers?|"
    r"homework|mental health|dating|personal assistant|personal intelligence|"
    r"access my life|screen time|slack messages?|your boss|workplace happiness|"
    r"startup founders|working harder|humans happier|robots? fall|hollywood|"
    r"careers?|job hunting|consumer gadgets?|mac mini|mac studio|swiss watch|"
    r"status symbol|wilderness camp|fishing outings|fashion|flight attendants?|"
    r"viral ai assistant|buzzy startup|handle emails|precocious teen|nostradamus|"
    r"reporting structure|human skills|job candidates?|rise and fall)\b",
    re.I,
)
_CHATTER_RX = re.compile(
    r"\b(?:asks?|urges?|warn(?:s|ed|ing)?|says?|tells?|argues?|predicts?|believes?|"
    r"insists?|expects?|calls? for|what .{0,40} can learn|may resemble|"
    r"takeaways? from|on what.s next|hits? back)\b",
    re.I,
)
_MATERIAL_EVENT_RX = re.compile(
    r"\b(?:acquir(?:e|es|ed|ing)|acquisition|agrees? to buy|buys?|bought|deal|"
    r"contracts?|partner(?:s|ed|ing)?|launch(?:es|ed|ing)?|releas(?:e|es|ed|ing)|"
    r"roll(?:s|ed|ing)? out|unveil(?:s|ed|ing)?|open.sources?|build(?:s|ing)?|"
    r"construction|expand(?:s|ed|ing)?|production|supply|shortage|capacity|"
    r"orders?|ship(?:s|ped|ping|ments?)|comes? online|goes? online|"
    r"standard|rules?|regulat(?:e|ion)|law|ban(?:s|ned|ning)?|restrict(?:s|ed|ion)|"
    r"export controls?|files? (?:a )?lawsuit|sues?|court|judge|copyright|"
    r"security flaw|cyber risk|"
    r"outages?|hack(?:s|ed|ing)?)\b",
    re.I,
)
_INFRA_COMMITMENT_RX = re.compile(
    r"\b(?:contracts?|deal|acquir(?:e|es|ed|ing)|invest(?:s|ed|ing)?|raises?|"
    r"build(?:s|ing)?|construction|"
    r"capex|spend(?:s|ing)?|orders?|capacity|supply|ship(?:s|ped|ping|ments?)|"
    r"production|launch(?:es|ed|ing)?|unveil(?:s|ed|ing)?)\b",
    re.I,
)
_CRYPTO_RX = re.compile(r"\b(?:crypto|bitcoin|ether|stablecoins?|nfts?)\b", re.I)
_INCIDENTAL_RX = re.compile(
    r"\b(?:with the help of ai|delivered with ai|using ai|"
    r"has nothing to do with technology|ai was mentioned)\b",
    re.I,
)
_SOFT_FLASHLINE_RX = re.compile(r"^(?:CEO Brief|WSJ Weekend Reads|Essay)$", re.I)
_BACKLASH_RX = re.compile(r"\b(?:backlash|grassroots ai revolt)\b", re.I)


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def article_id(url: str) -> str:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in {"wsj.com", "www.wsj.com"}:
        return ""
    if _EXCLUDED_PATH_RX.search(parts.path):
        return ""
    match = _ARTICLE_RX.fullmatch(parts.path)
    return match.group("id").lower() if match else ""


def search_url(keyword: str, page: int = 1) -> str:
    raise RuntimeError("WSJ 未配搜索线:只走官方 AI 专题")


def hub_url(slug: str, page: int = 1) -> str:
    return f"{HOME}/{str(slug).strip('/')}?page={max(1, int(page))}"


def _requested_page(page_url: str) -> int:
    try:
        value = parse_qs(urlsplit(page_url).query).get("page", ["1"])[0]
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _main_river(html: str, requested_page: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.select_one("script#__NEXT_DATA__")
    if script is None:
        raise RuntimeError("WSJ AI 专题缺少 __NEXT_DATA__，页面结构可能已改版")
    try:
        payload = json.loads(script.get_text(strip=True))
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("WSJ AI 专题的 __NEXT_DATA__ 不是有效 JSON") from exc
    page_props = payload.get("props", {}).get("pageProps", {})
    try:
        actual_page = int(page_props.get("pageNumber"))
        last_page = int(page_props.get("lastPage"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("WSJ AI 专题缺少有效 pageNumber/lastPage") from exc
    if actual_page != requested_page:
        raise RuntimeError(
            f"WSJ AI 专题请求第 {requested_page} 页却返回第 {actual_page} 页"
        )
    if last_page < actual_page:
        raise RuntimeError(
            f"WSJ AI 专题分页自相矛盾:第 {actual_page} 页 / 共 {last_page} 页"
        )
    assets = page_props.get("moreInArticles")
    if not isinstance(assets, list):
        raise RuntimeError("WSJ AI 专题缺少主河 moreInArticles")
    return [asset for asset in assets if isinstance(asset, dict)]


def admission_reason(asset: dict[str, Any]) -> str:
    """返回结构与主题准入理由；空串表示不值得为它打开一次正文。"""
    if clean_text(asset.get("type")).lower() != "article":
        return ""
    if _truthy(asset.get("isVideo")) or _truthy(asset.get("isOpinion")):
        return ""
    if _truthy(asset.get("isSponsored")):
        return ""
    url = canonical_url(clean_text(asset.get("articleUrl")), HOME)
    if not article_id(url):
        return ""

    title = clean_text(asset.get("headline"))
    summary = clean_text(asset.get("summary"))
    flashline = clean_text(asset.get("flashline"))
    evidence = f"{title} {summary} {flashline}"
    material = bool(_MATERIAL_EVENT_RX.search(title))
    direct_ai = bool(_AI_TOPIC_RX.search(evidence))
    infra = bool(_INFRA_RX.search(evidence))
    entity_in_context = bool(_CORE_ENTITY_RX.search(evidence) and (direct_ai or infra))
    if not (direct_ai or infra or entity_in_context):
        return ""
    title_has_topic = bool(
        _AI_TOPIC_RX.search(title)
        or _INFRA_RX.search(title)
        or (_CORE_ENTITY_RX.search(title) and (direct_ai or infra))
    )
    # 官方专题也会把“工作招聘中出现 AI”之类的稿子收进来。标题自己没有主题
    # 证据时，只放行摘要明确交代的真实基础设施动作（如 Nscale 算力合同）。
    if not title_has_topic and not (infra and material):
        return ""
    # 一篇 AI 基建交易的背景句可能提到创始人早年做 NFT；只有标题以币圈为
    # 主题才剔除，不能让一处旁带信息推翻标题里的实质模型/算力事件。
    if _CRYPTO_RX.search(title):
        return ""
    if _INCIDENTAL_RX.search(evidence) and not infra:
        return ""
    if _SOFT_FLASHLINE_RX.fullmatch(flashline) and not infra:
        return ""
    if re.match(r"^(?:plus|also),", summary, re.I):
        title_is_specific_chip_story = bool(
            _INFRA_RX.search(title) and _CORE_ENTITY_RX.search(title)
        )
        if not title_is_specific_chip_story:
            return ""
    if _PERSONNEL_RX.search(title) or _PERIPHERAL_RX.search(evidence):
        return ""

    if _BACKLASH_RX.search(title) and not infra:
        return ""
    if _MARKET_RX.search(f"{title} {flashline}"):
        # 股票、估值和财报只有在标题同时交代了真实的算力/供给动作时才留下。
        if not (infra and _INFRA_COMMITMENT_RX.search(title)):
            return ""
    if _CHATTER_RX.search(title) and not material:
        return ""
    return "core_infrastructure" if infra else "ai_article"


def parse_search_results(
    html: str,
    keyword: str,
    page_url: str = "",
) -> list[dict[str, Any]]:
    base = page_url or hub_url(HUBS[0])
    assets = _main_river(html, _requested_page(base))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for asset in assets:
        reason = admission_reason(asset)
        if not reason:
            continue
        url = canonical_url(clean_text(asset.get("articleUrl")), base)
        identifier = article_id(url)
        title = clean_text(asset.get("headline"))
        if not identifier or identifier in seen or len(title) < 12:
            continue
        seen.add(identifier)
        published = clean_text(asset.get("timestamp"))
        if not parse_datetime(published):
            published = ""
        rows.append(
            {
                "article_id": identifier,
                "title_en": title,
                "url": url,
                "published_at": published,
                "section": clean_text(asset.get("flashline")),
                "keywords": [keyword],
                "admission_reason": reason,
            }
        )
    return rows


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
