"""私站 HTML 元数据与正文提取策略。"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from collections.abc import Callable, Iterator
from typing import Any

from bs4 import BeautifulSoup

try:
    import trafilatura
except ImportError:
    trafilatura = None


def iter_json_nodes(value: Any) -> Iterator[dict[str, Any]]:
    """递归遍历 JSON 对象中的所有字典节点。"""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_nodes(child)


def metadata_from_html(
    html: str,
    fallback_title: str,
    clean_text: Callable[[Any], str],
) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    def meta(*, prop: str = "", name: str = "") -> str:
        node = (
            soup.find("meta", attrs={"property": prop})
            if prop
            else soup.find("meta", attrs={"name": name})
        )
        return clean_text(node.get("content")) if node else ""

    page_title = (
        meta(prop="og:title")
        or (
            clean_text(soup.title.get_text(" ", strip=True))
            if soup.title
            else ""
        )
        or fallback_title
    )
    description = meta(prop="og:description") or meta(name="description")
    result = {"page_title": page_title, "description": description}
    # **现场验收拿文章页自己的时间**,不只信搜索列表 —— 列表可能给的是
    # 「最后更新」,而证据核验要的是当时那一篇。
    published = published_from_html(html)
    if published is not None and published <= datetime.now(timezone.utc) + timedelta(days=2):
        result["published_at"] = published.astimezone(timezone.utc).isoformat()
    return result


_META_DATE_KEYS = (
    ("property", "article:published_time"),
    ("property", "og:article:published_time"),
    ("name", "publish-date"),
    ("name", "date"),
    ("itemprop", "datePublished"),
)


def published_from_html(html: str) -> datetime | None:
    """文章页自报的发布时间:meta → JSON-LD → ``<time datetime>``。

    三处都读不到就返回 ``None``。**不猜、不拿抓取时间冒充** —— 一个假时间会
    一路流进排序、时间窗和台账,而且看不出来。
    """
    soup = BeautifulSoup(html, "html.parser")
    for attr, value in _META_DATE_KEYS:
        node = soup.find("meta", attrs={attr: value})
        parsed = _parse_iso(node.get("content")) if node else None
        if parsed:
            return parsed
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.get_text(strip=True))
        except (TypeError, json.JSONDecodeError):
            continue
        for node in iter_json_nodes(payload):
            parsed = _parse_iso(node.get("datePublished"))
            if parsed:
                return parsed
    time_node = soup.find("time")
    return _parse_iso(time_node.get("datetime")) if time_node else None


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def extract_trafilatura(html: str, url: str) -> str:
    if trafilatura is None:
        return ""
    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        include_links=False,
        favor_precision=True,
        output_format="txt",
    )
    return str(extracted or "").strip()


def extract_bs4(
    html: str,
    *,
    container_selectors: tuple[str, ...],
    drop_selectors: str,
    clean_text: Callable[[Any], str],
    paragraph_selectors: tuple[str, ...] = (),
) -> str:
    """在站点声明的正文容器中逐段提取文字。"""
    soup = BeautifulSoup(html, "html.parser")
    container = None
    for selector in container_selectors:
        container = soup.select_one(selector)
        if container is not None:
            break
    if container is None:
        return ""
    if drop_selectors.strip():
        for node in container.select(drop_selectors):
            node.decompose()
    paragraphs: list[str] = []
    nodes = (
        container.select(", ".join(paragraph_selectors))
        if paragraph_selectors
        else container.find_all(["p", "h2", "h3"])
    )
    for node in nodes:
        text = clean_text(node.get_text(" ", strip=True))
        if not text or text.lower() in {
            "related article",
            "read more",
            "see more articles",
        }:
            continue
        paragraphs.append(text)
    return "\n\n".join(paragraphs).strip()


def extract_jsonld_article_body(
    html: str,
    clean_text: Callable[[Any], str],
) -> str:
    """从 NewsArticle JSON-LD 选择最长 articleBody 并恢复段落。"""
    soup = BeautifulSoup(html, "html.parser")
    best = ""
    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    ):
        try:
            payload = json.loads(script.get_text(strip=True))
        except (TypeError, json.JSONDecodeError):
            continue
        for node in iter_json_nodes(payload):
            if "NewsArticle" not in str(node.get("@type") or ""):
                continue
            body = node.get("articleBody")
            if isinstance(body, str) and len(body) > len(best):
                best = body
    text = BeautifulSoup(best, "html.parser").get_text("\n", strip=True)
    return "\n\n".join(
        clean_text(part)
        for part in re.split(r"\n{1,}", text)
        if clean_text(part)
    )
