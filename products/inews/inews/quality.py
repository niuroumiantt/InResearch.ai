"""可解释的编辑准入：召回可以宽，默认清单必须窄。

搜索、栏目页和正文各回答不同的问题：

* 搜索负责发现候选，不替编辑判断相关性；
* 标题负责证明文章的主语确实是 AI，并判断有没有具体事件；
* 正文只在标题证据不足时补证，抓取失败不能再默认放行。

所有条目都保留在台账与 HTML 中；本模块只给出默认视图的分层，不删除文章。
规则只使用标题、正文和发现来源这些可复核事实，不依赖旧的主观总分。
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Iterable

VERSION = 1

CORE = "core"
SECONDARY = "secondary"
UNVERIFIED = "unverified"
OFF_TOPIC = "off_topic"
STATUSES = (CORE, SECONDARY, UNVERIFIED, OFF_TOPIC)

LABELS = {
    CORE: "核心",
    SECONDARY: "次要",
    UNVERIFIED: "待验证",
    OFF_TOPIC: "主题不符",
}

# 这些词单独出现在标题里就足以证明 AI 是标题主题。较宽的供给链实体（Nvidia、
# TSMC、semiconductor 等）仍由当轮搜索关键词提供，但只算较弱的标题证据。
DIRECT_TOPICS = (
    "artificial intelligence", "generative ai", "genai", "machine learning",
    "deep learning", "large language model", "foundation model", "frontier model",
    "llm", "agentic", "ai agent", "ai model", "ai chip", "ai data centre",
    "ai data center", "ai datacenter", "ai safety", "ai regulation", "ai copyright",
    "openai", "chatgpt", "anthropic", "deepmind", "gemini ai", "claude ai",
    "deepseek", "hugging face", "perplexity ai", "mistral ai", "meta ai",
    "人工智能", "大模型", "大语言模型", "生成式ai", "生成式 ai", "智能体",
)

BARE_AI = re.compile(r"(?<![a-z0-9])ai(?![a-z0-9])", re.I)

# Bloomberg 高价值样本最明显的结构是“主体 + 具体动作 + 对象/后果”。这里不做
# 文学理解，只认标题上可复核的动作词。词干覆盖常见英语时态。
EVENT_RX = re.compile(
    r"\b(?:launch(?:es|ed|ing)?|release[sd]?|unveil(?:s|ed)?|ship(?:s|ped)?|"
    r"raise[sd]?|fund(?:s|ed|ing)?|invest(?:s|ed|ing)?|acquir(?:e|es|ed|ing)|"
    r"buy(?:s|ing)?|sell(?:s|ing)?|build(?:s|ing)?|open(?:s|ed|ing)?|"
    r"expand(?:s|ed|ing)?|sign(?:s|ed|ing)?|partner(?:s|ed|ing)?|"
    r"deploy(?:s|ed|ing)?|adopt(?:s|ed|ing)?|develop(?:s|ed|ing)?|"
    r"announce[sd]?|plan(?:s|ned|ning)?|seek(?:s|ing)?|pause[sd]?|halt(?:s|ed)?|"
    r"ban(?:s|ned|ning)?|regulat(?:e|es|ed|ing)|rule[sd]?|approv(?:e|es|ed)|"
    r"reject(?:s|ed)?|order(?:s|ed)?|sue[sd]?|warn(?:s|ed)?|cut(?:s|ting)?|"
    r"boost(?:s|ed)?|surge[sd]?|fall(?:s|ing)?|rise[sd]?|report(?:s|ed)?|"
    r"beat(?:s|en)?|miss(?:es|ed)?|forecast(?:s|ed)?|introduc(?:e|es|ed)|"
    r"say(?:s|ing)?|pledge[sd]?|take[sn]?|bec(?:ome|omes|ame)|double[sd]?|"
    r"top(?:s|ped)?|mount(?:s|ed)?|read(?:y|ies)|pursue[sd]?|struggle[sd]?|"
    r"expose[sd]?|narrow[sd]?|cash(?:es|ed)?\s+in|rein(?:s|ed)?\s+in|"
    r"race[sd]?|limit(?:s|ed)?|face[sd]?|urge[sd]?|push(?:es|ed)?|"
    r"publis(?:h|hes|hed)|test(?:s|ed|ing)?|train(?:s|ed|ing)?)\b|"
    r"发布|推出|上线|开源|融资|投资|收购|并购|上市|建设|签署|合作|"
    r"部署|采用|研发|宣布|计划|暂停|叫停|禁止|监管|立法|起诉|批准|"
    r"扩建|量产|投产|裁员|警告|报告|增长|下降|突破|测试|训练",
    re.I,
)

# 这类标题可以高度相关，却不是用户要的 Bloomberg 式事件新闻。保留在次要层，
# 不混入默认清单。股价/荐股词比普通问句更强：AI 常只是行情解释或卖点。
MARKET_NOISE_RX = re.compile(
    r"\b(?:stock|shares?)\b.{0,35}\b(?:rise|rose|rises|fall|fell|falls|"
    r"drop|drops|dropped|slip|slips|slide|slides|tumble|tumbles|sink|sinks|"
    r"plunge|plunges|rally|rallies|climb|climbs|hit|hits|jump|jumps|surge|surges|"
    r"buyback|buybacks|price target)\b|"
    r"\b(?:rise|rose|fall|fell|drop|slip|slide|tumble|sink|plunge|rally|climb|hit|jump|surge)\w*\b.{0,35}\b(?:stock|shares?)\b|"
    r"stocks? to buy|etfs? to buy|no-brainer|should you buy|buy and hold|"
    r"股价|概念股|龙头股|涨停|跌停|买入评级|目标价",
    re.I,
)
SOFT_GENRE_RX = re.compile(
    r"^(?:letter:|review:|firstft\b)|\bfurther reading\b|\bweek in review\b|"
    r"\bmarket wrap\b|\bmorning brief\b|\bare you ready\b|"
    r"^(?:could|should|would|can|how|why|what)\b|\?$",
    re.I,
)


def _normal(text: object) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def _contains(haystack: str, needle: str) -> bool:
    """短语边界匹配；避免 ``AI`` 命中 ``said``、``GPU`` 命中更长产品名。"""
    word = _normal(needle).strip()
    if not word:
        return False
    plural = r"(?:s|es)?" if word[-1:].isalpha() else ""
    return bool(re.search(
        rf"(?<![a-z0-9]){re.escape(word)}{plural}(?![a-z0-9])", haystack
    ))


def origins_of(row: dict[str, Any]) -> list[dict[str, str]]:
    """兼容旧 ``found_via``，统一返回去重后的全部发现来源。"""
    origins: list[dict[str, str]] = []
    for item in row.get("origins") or []:
        if not isinstance(item, dict):
            continue
        kind, name = str(item.get("kind") or ""), str(item.get("name") or "")
        if kind and name and {"kind": kind, "name": name} not in origins:
            origins.append({"kind": kind, "name": name})
    first = str(row.get("found_via") or "")
    if first and not any(item["name"] == first for item in origins):
        origins.append({"kind": "legacy", "name": first})
    return origins


def title_strength(row: dict[str, Any], topic_labels: Iterable[str] = ()) -> int:
    """0=标题无主题证据，1=命中搜索词/供给链实体，2=明确 AI 主题。"""
    title = _normal(row.get("title_en"))
    if not title:
        return 0
    if BARE_AI.search(title) or any(_contains(title, word) for word in DIRECT_TOPICS):
        return 2
    labels = set(topic_labels)
    terms = (word for word in row.get("keywords") or [] if word not in labels)
    return 1 if any(_contains(title, word) for word in terms) else 0


def body_evidence(
    row: dict[str, Any], topic_labels: Iterable[str] = ()
) -> tuple[bool, int, bool]:
    """返回（正文是否以 AI 为主、命中段落百分比、导语是否命中）。"""
    body = str(row.get("body") or "").strip()
    if not body:
        return False, 0, False
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\n", body) if part.strip()]
    labels = set(topic_labels)
    terms = list(DIRECT_TOPICS) + [
        str(word) for word in row.get("keywords") or [] if word not in labels
    ]

    def hit(paragraph: str) -> bool:
        hay = _normal(paragraph)
        return bool(BARE_AI.search(hay) or any(_contains(hay, word) for word in terms))

    flags = [hit(part) for part in paragraphs]
    count = sum(flags)
    share = round(count * 100 / len(paragraphs)) if paragraphs else 0
    lead = any(flags[:3])
    central = (lead and count >= 2 and share >= 20) or (count >= 3 and share >= 35)
    return central, share, lead


def _hub_tier(row: dict[str, Any], hub_tiers: dict[str, str]) -> str:
    tiers = [
        hub_tiers.get(origin["name"], "")
        for origin in origins_of(row)
        if origin["kind"] == "hub"
    ]
    if "trusted" in tiers:
        return "trusted"
    if "ai" in tiers:
        return "ai"
    if "context" in tiers:
        return "context"
    return ""


def assess(
    row: dict[str, Any], *, topic_labels: Iterable[str] = (),
    hub_tiers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """给一篇文章作可解释分层；返回的字段可直接并入行与台账。"""
    hub_tiers = hub_tiers or {}
    title = str(row.get("title_en") or "")
    strength = title_strength(row, topic_labels)
    event = bool(EVENT_RX.search(title))
    central, share, lead = body_evidence(row, topic_labels)
    tier = _hub_tier(row, hub_tiers)
    # 旧 Bloomberg 台账没有 origins，但只有一个 trusted 栏目；这种单义历史数据
    # 可以无损推回来源层级。FT 有两个不同层级，不能猜，留给标题/正文判断。
    labels = set(topic_labels)
    unique_tiers = set(hub_tiers.values())
    if (
        not tier and len(unique_tiers) == 1
        and any(word in labels for word in row.get("keywords") or [])
    ):
        tier = next(iter(unique_tiers))
    body = bool(row.get("body"))

    if tier == "trusted":
        status, reason = CORE, "官方 AI 栏目直接准入"
    elif MARKET_NOISE_RX.search(title):
        status, reason = SECONDARY, "AI 只是股价、荐股或市场行情背景"
    elif SOFT_GENRE_RX.search(title) and strength:
        status, reason = SECONDARY, "观点、问句或汇编体，不是具体事件"
    elif strength >= 2 and event:
        status, reason = CORE, "标题同时包含明确 AI 主体和具体事件"
    elif strength == 1 and event and (central or not body):
        status, reason = CORE, "标题命中供给链主体并包含具体事件"
    elif strength:
        status, reason = SECONDARY, "标题主题明确，但缺少具体事件"
    elif not body:
        status, reason = UNVERIFIED, "标题证据不足且正文尚未取到"
    elif central and event:
        status, reason = CORE, "正文中心度与标题事件性同时通过"
    elif strength or central:
        status, reason = SECONDARY, "主题相关，但缺少具体事件或仅作分析背景"
    else:
        status, reason = OFF_TOPIC, "标题未命中，正文中心度也未通过"

    return {
        "quality_version": VERSION,
        "quality_status": status,
        "quality_reason": reason,
        "title_strength": strength,
        "event_signal": event,
        "topic_share": share,
        "lead_signal": lead,
        "source_tier": tier,
    }


def hidden_by_default(row: dict[str, Any]) -> bool:
    """旧数据没有判定时不擅自隐藏；回填后只有核心层默认展示。"""
    status = row.get("quality_status")
    return bool(status) and status != CORE


def summary(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("quality_status") or "legacy") for row in rows)
    return {name: counts.get(name, 0) for name in (*STATUSES, "legacy")}
