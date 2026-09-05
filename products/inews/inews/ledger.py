"""爬取台账:记下爬过谁,下一轮就别再爬。

每小时跑一次的前提是**增量**:首轮 500 多篇,之后每轮通常只有两三篇新的。
台账是这个应用唯一的持久状态,一份 JSON,跟输出目录放在一起。

**身份用 ``article_id``(``/content/<uuid>``),不用标题。** 标题会被编辑改、
会带上「Updated」前缀,时间也会随修订变;URL 里那个 uuid 是 FT 自己发的,
一篇稿子从头到尾只有一个。拿会变的东西当身份,就会同一篇反复爬。

**同 id 但链接变了当新的处理。** 那说明这不是我们记过的那一篇(转载、
改版、或者我们记错了),宁可多爬一次,不可把没爬过的当成爬过的静默跳过。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from inews import layout
from inews.storage import read_json, write_json_atomic
from inews.textutil import canonical_url

FILENAME = "ledger.json"
# v2:多记了 keywords / section。清单从「本轮」变成「累积库」之后,台账要能
# **独自重画一行** —— 少了关键词,上一轮的稿子就只剩个链接,分不了组也筛不了。
# v1 的老条目照读不误:缺的字段当空,只会让那几行少两个标签,不会让它消失。
# v3(9-01):多记了 score / score_detail / score_notes(与失败时的 score_error)。
# 老条目没有分数字段 = 「还没打过分」,由 --rescore 补;照读不误。
# v4(9-03):失败条目多记 ``body_attempts``(**连续**失败几次)。重试退避要按
# 次数拉长间隔,而次数只能由这份唯一的持久状态来记;取到正文的那一刻它被抹掉。
# 老条目没有这个字段 = 「刚失败第一次」,照读不误。
# v5(9-03):保存全部 ``origins`` 与可解释的 quality_* 准入结论。旧条目在
# --render-only 时用正文存档回填；缺字段期间按旧行为展示，不会凭空消失。
# v6(9-04):可选 ``description`` 也是站点准入证据。若只在发现页内存里保留，
# 首轮/重画的存量复核会丢掉摘要语境，把本已通过的基础设施稿静默隐藏。
VERSION = 6

QUALITY_FIELDS = (
    "quality_version", "quality_status", "quality_reason", "title_strength",
    "event_signal", "topic_share", "lead_signal", "source_tier",
)


def path_for(out_dir: Path) -> Path:
    """台账在 ``data/`` 下;老布局把它放在根上的,顺手搬过来(见 ``layout.adopt``)。"""
    return layout.adopt(out_dir, FILENAME)


def load(path: Path) -> dict[str, dict[str, Any]]:
    """读台账；不存在是空账，损坏则回退上一版或明确停止，绝不覆盖历史。"""
    payload = read_json(path, {})
    entries = payload.get("entries") if isinstance(payload, dict) else None
    return entries if isinstance(entries, dict) else {}


def save(path: Path, entries: dict[str, dict[str, Any]]) -> None:
    """原子写:先写临时文件再改名。半截的台账比没有台账更坏 —— 它会让
    已经爬过的那部分看起来没爬过,或者反过来。"""
    write_json_atomic(path, {"version": VERSION, "entries": entries})


def is_seen(entries: dict[str, dict[str, Any]], row: dict[str, Any]) -> bool:
    """爬过没有:id 记过、且链接对得上,才算同一篇。"""
    known = entries.get(row.get("article_id", ""))
    return bool(known) and known.get("url") == row.get("url")


def split_new(
    entries: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """把本轮清单分成「新的」和「爬过的」。"""
    fresh = [row for row in rows if not is_seen(entries, row)]
    seen = [row for row in rows if is_seen(entries, row)]
    return fresh, seen


def merge_discovery(
    entries: dict[str, dict[str, Any]], rows: list[dict[str, Any]]
) -> int:
    """把重新发现的站方元数据与来源补进旧台账，不重新抓正文。

    站方会在不改文章身份和 URL 的情况下修订标题。若只并关键词，下一轮会因
    ``split_new`` 判为已读而丢掉当前行，旧标题便永久留在清单里。只在 URL
    规范化后仍是同一地址时刷新标题/栏目并补上缺失时间；同 id 但真正换了链接
    仍按新稿处理。正文状态与分数保留；标题实质变化时旧译文清空，避免错配。
    """
    changed = 0
    for row in rows:
        entry = entries.get(row.get("article_id", ""))
        if not entry:
            continue
        before = {
            key: entry.get(key)
            for key in (
                "url", "title", "description", "published_at", "section",
                "keywords", "origins", "found_via",
            )
        }
        current_url = str(row.get("url") or "")
        known_url = str(entry.get("url") or "")
        same_url = bool(
            current_url
            and known_url
            and canonical_url(current_url) == canonical_url(known_url)
        )
        if same_url:
            entry["url"] = canonical_url(current_url)
            current_title = row.get("title_en")
            if str(current_title or "").strip():
                title_changed = str(current_title).strip() != str(
                    entry.get("title") or ""
                ).strip()
                entry["title"] = current_title
                if title_changed:
                    # 译文描述的是旧标题；继续展示会像 MediaTek 现场案例一样，
                    # 英文已经变成 AI 芯片交易，中文却仍写“股价上涨”。正文与
                    # 评分仍属于同一 article_id，可安全保留；标题等待 --retitle。
                    entry["title_zh"] = ""
                    entry.pop("title_zh_error", None)
            # 时间只补空缺，不用新一轮 URL 日期覆盖台账里更精确的时分秒。
            current_published = row.get("published_at")
            if (
                str(current_published or "").strip()
                and not str(entry.get("published_at") or "").strip()
            ):
                entry["published_at"] = current_published
            current_section = row.get("section")
            if str(current_section or "").strip():
                entry["section"] = current_section
            current_description = row.get("description")
            if str(current_description or "").strip():
                entry["description"] = current_description
        entry["keywords"] = sorted(set(entry.get("keywords") or []) | set(row.get("keywords") or []))
        origins = list(entry.get("origins") or [])
        for origin in row.get("origins") or []:
            if isinstance(origin, dict) and origin not in origins:
                origins.append(origin)
        if origins:
            entry["origins"] = origins
        if row.get("found_via") and not entry.get("found_via"):
            entry["found_via"] = row["found_via"]
        after = {
            key: entry.get(key)
            for key in (
                "url", "title", "description", "published_at", "section",
                "keywords", "origins", "found_via",
            )
        }
        changed += before != after
    return changed


def record(
    entries: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    crawled_at: str,
) -> None:
    """把本轮处理过的条目写进台账。

    ``body_status`` 如实记录:``ok`` / ``failed`` / ``skipped``(没尝试取正文)。
    只有 ``ok`` 和 ``failed`` 算爬过 —— **只取了标题的那些不该挡住以后取正文**,
    否则一次 ``--no-body`` 就把 500 篇永久封在「爬过但没正文」的状态里。
    """
    for row in rows:
        status = _body_status(row)
        if status == "skipped":
            continue
        previous = entries.get(row["article_id"]) or {}
        attempts = int(previous.get("body_attempts") or 0) + 1
        entries[row["article_id"]] = {
            "url": row["url"],
            "title": row.get("title_en", ""),
            "description": row.get("description") or previous.get("description", ""),
            "title_zh": row.get("title_zh", ""),
            "published_at": row.get("published_at", ""),
            "keywords": sorted(
                set(previous.get("keywords") or []) | set(row.get("keywords") or [])
            ),
            "section": row.get("section", ""),
            **({"found_via": row.get("found_via") or previous.get("found_via")}
               if row.get("found_via") or previous.get("found_via") else {}),
            **({"origins": list(row.get("origins") or previous.get("origins") or [])}
               if row.get("origins") or previous.get("origins") else {}),
            "crawled_at": crawled_at,
            "body_status": status,
            # **失败原话进台账。** 不进的话,重画一次页面就把原因抹掉了 ——
            # 2026-08-24 库里 31 篇取正文失败,想问「是不是同一个原因」时,
            # 发现原话只活在那一轮的内存里,一条都查不到了。
            # 截断到 400:诊断靠前半句,而台账是每轮都要重写的整份 JSON。
            **({"body_error": str(row.get("body_error") or "")[:400],
                # 连续失败次数:退避表按它决定「这次要等多久」。
                "body_attempts": attempts}
               if status == "failed" else {}),
            # 提及型的判定跟着正文走:重画页面不该抹掉它,也不该每轮重数全库。
            **({"mention_only": True} if row.get("mention_only") else {}),
            # 分数与依据一起进台账:正文不存台账,可依据必须活得比那一轮的内存长
            # —— 这正是 8-24 失败原话丢过一次的同一个教训。
            **({
                "score": int(row["score"]),
                "score_version": int(row.get("score_version") or 1),
                "score_detail": dict(row.get("score_detail") or {}),
                "score_notes": str(row.get("score_notes") or ""),
            } if isinstance(row.get("score"), int) else {}),
            **({"score_error": str(row.get("score_error") or "")[:400]}
               if row.get("score_error") and not isinstance(row.get("score"), int)
               else {}),
            **{
                key: row[key]
                for key in QUALITY_FIELDS
                if key in row
            },
        }


def _body_status(row: dict[str, Any]) -> str:
    if row.get("body"):
        return "ok"
    if row.get("body_error"):
        return "failed"
    return "skipped"


def rows(entries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """把台账摊回成清单能画的行(不排序 —— 排序是调用方的档次)。

    **不带 ``body``**:正文页早就在盘上了,台账只记状态。带上正文等于让这份
    JSON 变成一个没人维护的第二数据库。
    """
    return [
        {
            "article_id": article_id,
            "url": entry.get("url", ""),
            "title_en": entry.get("title", ""),
            "description": entry.get("description", ""),
            "title_zh": entry.get("title_zh", ""),
            "published_at": entry.get("published_at", ""),
            "keywords": list(entry.get("keywords", [])),
            "section": entry.get("section", ""),
            "found_via": entry.get("found_via", ""),
            "origins": list(entry.get("origins") or []),
            "body_status": entry.get("body_status", ""),
            "body_error": entry.get("body_error", ""),
            "mention_only": bool(entry.get("mention_only")),
            "crawled_at": entry.get("crawled_at", ""),
            # 分数只在有过判分时出现:没打过分和打了 0 分是两回事,不能混。
            **{
                key: entry[key]
                for key in (
                    "score", "score_version", "score_detail", "score_notes", "score_error",
                    *QUALITY_FIELDS,
                )
                if key in entry
            },
        }
        for article_id, entry in entries.items()
    ]
