"""站点间共用的清单机制:合并、排序、时间窗、付费墙位置判定。

第二个站(Bloomberg,9-02)进来时,这些函数在 ft.py 里但没有一行是 FT 特有的
—— 复制会让「一件事只有一处实现」失守,于是搬到这里。**站名一个都不写**:
硬地板、拦截页指纹这类站点事实由各站声明,这里只收参数。
"""
from __future__ import annotations

import re
from typing import Any

from inews.textutil import parse_datetime


def merge(
    into: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    source: str | dict[str, str] = "",
) -> int:
    """按 article_id 合并；同一篇被多条线命中时记下全部关键词与来源。

    ``found_via`` 为旧页面保留，仍只表示第一次发现；``origins`` 保存所有线，
    才能在准入时区分搜索、AI 专题和半导体专题。
    """
    origin = (
        {"kind": str(source.get("kind") or ""), "name": str(source.get("name") or "")}
        if isinstance(source, dict)
        else {"kind": "legacy", "name": str(source or "")}
    )
    origin = origin if origin["kind"] and origin["name"] else {}
    fresh = 0
    for row in rows:
        existing = into.get(row["article_id"])
        if existing is None:
            if origin:
                row.setdefault("found_via", origin["name"])
                row.setdefault("origins", [origin])
            into[row["article_id"]] = row
            fresh += 1
            continue
        existing["keywords"] = sorted(
            set(existing["keywords"]) | set(row["keywords"])
        )
        if not existing["published_at"] and row["published_at"]:
            existing["published_at"] = row["published_at"]
        if origin:
            origins = list(existing.get("origins") or [])
            if origin not in origins:
                origins.append(origin)
            existing["origins"] = origins
    return fresh


def admitted_rows(
    rows: dict[str, dict[str, Any]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """存量视图的默认准入是 identity；需清理历史漏项的站必须显式覆盖。"""
    return list(rows.values()) if isinstance(rows, dict) else list(rows)


def newest_first(
    rows: dict[str, dict[str, Any]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按发布时间倒序;时间解析不出来的排最后,而不是被悄悄丢掉。"""
    values = list(rows.values()) if isinstance(rows, dict) else list(rows)

    def key(row: dict[str, Any]) -> tuple[int, float]:
        parsed = parse_datetime(row.get("published_at", ""))
        return (1, parsed.timestamp()) if parsed else (0, 0.0)

    return sorted(values, key=key, reverse=True)


def oldest_first(
    rows: dict[str, dict[str, Any]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ordered = newest_first(rows)
    dated = [r for r in ordered if parse_datetime(r.get("published_at", ""))]
    undated = [r for r in ordered if not parse_datetime(r.get("published_at", ""))]
    return list(reversed(dated)) + undated


def floor_for(since: str, earliest: str) -> str:
    """实际生效的时间下限:`--since` 只能比站点硬地板更晚,不能更早。"""
    asked = parse_datetime(since)
    hard = parse_datetime(earliest)
    if asked is None or hard is None:
        return earliest
    return since if asked > hard else earliest


def within_window(row: dict[str, Any], since: str, earliest: str) -> bool:
    """**时间解析不出来的一律保留** —— 缺时间不是「太旧」,是「不知道」。"""
    published = parse_datetime(row.get("published_at", ""))
    floor = parse_datetime(floor_for(since, earliest))
    if published is None or floor is None:
        return True
    return published >= floor


def barrier_before_body(text: str, title: str, barrier_rx: re.Pattern[str]) -> bool:
    """付费墙提示出现在正文主体**之前**才算被拦。

    出现在文末的订阅推广每篇都有,拿它判失败会把好稿子全部误杀。
    """
    barrier = barrier_rx.search(text)
    if not barrier:
        return False
    title_position = text.find(title) if title else -1
    if title_position >= 0:
        return barrier.start() - title_position < 5000
    return barrier.start() < 5000
