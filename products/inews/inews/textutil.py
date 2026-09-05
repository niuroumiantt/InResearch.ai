"""字符串与时间的公共工具(纯函数)。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_url(url: str, base_url: str = "") -> str:
    """绝对化并去掉查询、片段和末尾斜杠 —— 同一篇稿子只有一个地址。"""
    absolute = urljoin(base_url, url)
    parts = urlsplit(absolute)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def parse_datetime(value: str) -> datetime | None:
    """解析 ISO 8601 或 RSS 常见的 RFC 2822 时间;解析不了返回 None。

    **返回 None 不等于「很旧」** —— 调用方要把「没有时间」当成一种状态,
    而不是当成 1970 年。
    """
    if not value:
        return None
    parsers = (
        lambda text: datetime.fromisoformat(text.replace("Z", "+00:00")),
        parsedate_to_datetime,
    )
    for parser in parsers:
        try:
            parsed = parser(str(value).strip())
        except (TypeError, ValueError):
            continue
        if parsed is not None:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def localname(element: Any) -> str:
    """去掉 XML 命名空间前缀的标签名。"""
    tag = getattr(element, "tag", "")
    return str(tag).rsplit("}", 1)[-1]
