"""编排:搜索 → 逐篇取正文 → 落地静态站点。

出网只经两道门:搜索页走 ``browser.fetch_rendered_listing``,正文走
``fetch.fetch_body``。本模块**不自己发一个请求**,所以域名边界、获取档位、
限速这三件事仍然只有一处实现。
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

from inews import archive
from inews import ledger as ledger_store
from inews import ledger as rows_module  # 同一份台账,两个名字只为读得顺
from inews import render
from inews import quality
from inews import stats
from inews.storage import interprocess_lock, write_json_atomic, write_text_atomic
from inews.sites import ft
from inews.textutil import canonical_url

Progress = Callable[[str], None]
ListingFetcher = Callable[[str], tuple[str, str]]
BodyFetcher = Callable[[dict[str, Any]], dict[str, Any]]

# 每次页面打开之间的间隔。可以用 INEWS_PACE_SECONDS 覆盖 —— 用例把它设成 0,
# 否则一轮用例要等上一分多钟(而等待本身什么也没验证)。
PACE_SECONDS = 4.0


def _pace(override: float) -> float:
    try:
        return float(os.getenv("INEWS_PACE_SECONDS", override))
    except ValueError:
        return override


def _listing_fetcher_for(site) -> ListingFetcher:
    # CNBC 这类公开栏目把「Load More」背后的结构化接口声明在站点模块里；
    # 能在发现阶段拿到顶层内容类型，就可以在点正文前结构性排除视频。FT / Bloomberg
    # 没有这条公开、稳定的路，仍走下面同一套渲染浏览器。
    if site.LISTING_FETCHER is not None:
        return site.LISTING_FETCHER

    def fetch(url: str) -> tuple[str, str]:
        from inews.browser import fetch_rendered_listing

        return fetch_rendered_listing(
            url, site=site.KEY, link_pattern=site.LINK_PATTERN,
            scroll_listing=site.LISTING_SCROLLS,
            load_more_text=site.LOAD_MORE_TEXT,
        )

    return fetch


def _body_fetcher_for(site) -> BodyFetcher:
    def fetch(row: dict[str, Any]) -> dict[str, Any]:
        from inews.fetch import fetch_body

        return fetch_body(row, site=site)

    return fetch


def collect(
    keywords: list[str],
    *,
    site=ft,
    pages: int = 1,
    limit: int = 20,
    since: str = "",
    order: str = "newest",
    fetch_listing: ListingFetcher | None = None,
    progress: Progress = lambda _message: None,
    pace_seconds: float = PACE_SECONDS,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """逐个关键词逐页打开搜索页,合并去重、剔凑数、按时间排序后返回。

    第三个返回值是**每条召回线的账**:开了几页(成本)、命中几篇、首次带来
    几篇(价值)。站长的猜想是「站内搜索比分类页高效」—— 这里不替他下结论,
    只保证判断所需要的数字每轮都被记下来,几周后回头看真账。

    ``limit<=0`` 表示不截断 —— 深挖时「取回多少」应该由关键词和页数决定,
    而不是被一个默认值悄悄砍掉。
    """
    fetch = fetch_listing or _listing_fetcher_for(site)
    pace_seconds = _pace(pace_seconds)
    sources: list[dict[str, Any]] = []
    rows: dict[str, dict[str, Any]] = {}
    notes: list[str] = []
    searched: list[str] = []
    first = True
    for keyword in keywords:
        hits = 0
        fresh = 0
        pages_ok = 0
        for page in range(1, max(1, pages) + 1):
            url = site.search_url(keyword, page)
            progress(f"搜索「{keyword}」第 {page} 页")
            if not first:
                time.sleep(pace_seconds)
            first = False
            try:
                html, _final = fetch(url)
            except Exception as error:  # noqa: BLE001 单个词失败不该中断整轮
                notes.append(f"「{keyword}」第 {page} 页失败:{error}")
                progress(notes[-1])
                continue
            parsed = site.parse_search_results(html, keyword, url)
            if not parsed:
                # 结果页解析出 0 条:要么翻到底了,要么页面结构变了。两种都该说出来,
                # 静默的 0 会让「今天没新闻」和「解析失效」长得一模一样。
                notes.append(f"「{keyword}」第 {page} 页 0 条,停止翻页")
                break
            pages_ok += 1
            hits += len(parsed)
            fresh += site.merge(
                rows, parsed, source={"kind": "search", "name": keyword}
            )
        if pages_ok:
            searched.append(keyword)
        notes.append(f"「{keyword}」{hits} 命中 / {fresh} 新 / {pages_ok} 页")
        sources.append({
            "name": keyword, "kind": "search",
            "pages": pages_ok, "hits": hits, "first": fresh,
        })
    # 第二条召回线:分类页。**不进 `searched`** —— 凑数判据按「搜过几个语义组」
    # 计票,分类页不是搜索,把它算进去会悄悄改变那条判据的阈值。
    for slug in site.HUBS:
        hits = 0
        fresh = 0
        pages_ok = 0
        for page in range(1, max(1, pages) + 1):
            url = site.hub_url(slug, page)
            progress(f"分类页「{slug}」第 {page} 页")
            time.sleep(pace_seconds)
            try:
                html, _final = fetch(url)
            except Exception as error:  # noqa: BLE001 一条线失败不该中断整轮
                notes.append(f"分类「{slug}」第 {page} 页失败:{error}")
                progress(notes[-1])
                continue
            label = site.HUB_LABELS.get(slug, site.TOPIC_LABEL)
            parsed = site.parse_search_results(html, label, url)
            if not parsed:
                notes.append(f"分类「{slug}」第 {page} 页 0 条,停止翻页")
                break
            pages_ok += 1
            hits += len(parsed)
            new_here = site.merge(
                rows, parsed, source={"kind": "hub", "name": slug}
            )
            fresh += new_here
            notes.append(f"分类「{slug}」第 {page} 页 {len(parsed)} 条 / {new_here} 新")
            if not new_here:
                # 分类页的 ?page=N 不一定存在,站方可能每页都返回第一页 ——
                # 那种情况下「0 条」永远不会发生,只有「没有新的」才是停下的信号。
                notes.append(f"分类「{slug}」第 {page} 页没有新的,停止翻页")
                break
        sources.append({
            "name": slug, "kind": "hub",
            "pages": pages_ok, "hits": hits, "first": fresh,
        })

    padding = site.drop_padding(rows, searched)
    if padding:
        notes.append(f"凑数剔除 {len(padding)}(同一篇在过半主题组下重复出现)")
    # 时间窗**总是**生效:没传 --since 时下限就是站点声明的硬地板。
    floor = site.floor_for(since)
    before = len(rows)
    rows = {
        article_id: row
        for article_id, row in rows.items()
        if site.within_window(row, since)
    }
    if before != len(rows):
        notes.append(f"{floor} 之前剔除 {before - len(rows)}")
    ordered = (
        site.oldest_first(rows)
        if order == "oldest"
        else site.newest_first(rows)
    )
    assess_quality(ordered, site=site)
    return (ordered if limit <= 0 else ordered[:limit]), notes, sources


def fetch_bodies(
    rows: list[dict[str, Any]],
    *,
    site=ft,
    fetch_body: BodyFetcher | None = None,
    progress: Progress = lambda _message: None,
) -> list[dict[str, Any]]:
    """逐篇点进去读正文;失败的把原话留在 ``body_error`` 上,不丢这一条。"""
    fetch = fetch_body or _body_fetcher_for(site)
    for index, row in enumerate(rows, start=1):
        progress(f"读取正文 {index}/{len(rows)}:{row.get('title_en', '')}")
        try:
            result = fetch(row)
        except Exception as error:  # noqa: BLE001 失败要留原话,不能吞
            # 重试行是从台账摊回来的,手里可能还带着上一次的
            # ``body_status``。本轮的结果必须在行上就自洽,不能只等
            # ledger.record 最后替我们纠正。
            row.pop("body", None)
            row["body_status"] = "failed"
            row["body_error"] = f"{type(error).__name__}: {error}"
            # **原因也要进日志。** 每小时一轮跑在后台没人盯着终端 ——
            # 只打「读取正文 3/20:标题」的话,失败和成功在日志里长得一模一样。
            progress(f"取正文失败:{row['body_error']}")
            continue
        row["body"] = str(result.get("body") or "")
        row["extractor"] = result.get("extractor", "")
        if not row["body"]:
            row["body_status"] = "failed"
            row["body_error"] = "抓取返回了空正文"
            continue
        # 取到正文就是本轮的最终事实。清掉重试行携带的旧失败
        # 原话,否则终端、存档和页面会在同一次成功后继续报失败。
        row.pop("body_error", None)
        row["body_status"] = "ok"
        # 拿到正文的这一刻是数词的唯一机会:台账不存正文,过后想数也没得数。
        row["mention_only"] = stats.is_mention_only(row)
        row.update(quality.assess(
            row, topic_labels=_topic_labels(site), hub_tiers=site.HUB_TIERS,
        ))
    return rows


def _topic_labels(site) -> set[str]:
    return {site.TOPIC_LABEL, *site.HUB_LABELS.values()}


def assess_quality(rows: list[dict[str, Any]], *, site=ft) -> int:
    """按当前规则分层并写回行；返回实际处理数。"""
    for row in rows:
        row.update(quality.assess(
            row, topic_labels=_topic_labels(site), hub_tiers=site.HUB_TIERS,
        ))
    return len(rows)


# 取正文失败之后的重试退避:第 1 次失败等 6 小时,第 2 次 24,第 3 次 72;
# 试满之后**每小时那一轮不再碰它**,只有手动的「修复未抓取」还会捡起来。
#
# 9-03 站长的判断:「可能真的抓取不到,总是尝试也无意义,但是可能是能抓取到的
# 也说不定」。两端都要防:每轮全试 = 把一轮拖成几十次注定失败的浏览器打开;
# 一次失败就永别 = 一次登录态过期,那几篇永久停在「正文未取到」。
#
# 写成一张明表而不是公式:读的人一眼看得出「试几次、隔多久」,改也只改这一行。
RETRY_BACKOFF_HOURS = (6, 24, 72)
# 自动轮次优先完成新稿；旧失败每轮最多捡五篇，不能再用 145 个旧重试阻塞
# 新文章的正文、评分与最终清单。手动 --retry-failed 仍可显式处理更多。
AUTOMATIC_RETRY_LIMIT = 5


def due_for_retry(
    entries: dict[str, dict[str, Any]],
    *,
    now: str,
) -> list[dict[str, Any]]:
    """台账里**这会儿该再试一次**的失败条目。

    判据只有两条:它失败着,而且距上次尝试已经超过它这一档的退避。时间读不出来
    就当「早该试了」—— 不猜时间,但也不拿读不懂当「刚试过」把它永久卡住。
    """
    from inews.textutil import parse_datetime

    moment = parse_datetime(now)
    due: list[dict[str, Any]] = []
    for row in rows_module.rows(entries):
        if row.get("body_status") != "failed":
            continue
        attempts = int(entries[row["article_id"]].get("body_attempts") or 1)
        if attempts > len(RETRY_BACKOFF_HOURS):
            continue  # 试满了:交给手动那条路
        gap_hours = RETRY_BACKOFF_HOURS[attempts - 1]
        last = parse_datetime(str(row.get("crawled_at") or ""))
        if last is None or moment is None:
            due.append(row)
            continue
        if (moment - last).total_seconds() >= gap_hours * 3600:
            due.append(row)
    return due


def failed_rows(entries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """台账里记着**取正文失败**的那些。

    只挑 ``failed``:``skipped`` 是压根没取过(``--no-body`` 的正常状态),
    ``ok`` 是已经有了 —— 两种都不该被重试拖进来。
    """
    return [
        row for row in ledger_store.rows(entries)
        if row.get("body_status") == "failed"
    ]


def library_rows(
    entries: dict[str, dict[str, Any]],
    listed: list[dict[str, Any]],
    *,
    order: str = "newest",
    site=ft,
) -> list[dict[str, Any]]:
    """台账里爬过的 + 本轮这批,合成清单要列的全部,按发布时间排好。

    **本轮的行覆盖台账的行**:同一篇这轮刚取到正文,清单上就不该还挂着上一轮
    那个「失败」的状态。

    分数是例外的方向:它只住在台账里(存档存正文的正本,不存分)。存档行
    覆盖台账行时,把台账里的分**借回来** —— 否则一次重画,整页的分就没了。
    本轮刚打的分在行上自带,照旧赢过台账。
    """
    merged = {row["article_id"]: row for row in ledger_store.rows(entries)}
    for row in listed:
        prior = merged.get(row["article_id"])
        if prior:
            borrowed = {
                key: prior[key]
                for key in (
                    "score", "score_detail", "score_notes", "score_error",
                    *ledger_store.QUALITY_FIELDS,
                )
                if key in prior and key not in row
            }
            same_url = bool(
                row.get("url")
                and prior.get("url")
                and canonical_url(str(row["url"])) == canonical_url(str(prior["url"]))
            )
            discovery = {}
            if same_url:
                for key in (
                    "url", "description", "published_at", "keywords", "section",
                    "found_via", "origins",
                ):
                    if prior.get(key):
                        discovery[key] = prior[key]
                # Archive 保存的是抓正文当时的标题，ledger 保存站方最近一次发现的
                # 标题。同 URL 改标题时必须以 ledger 为准，并让已清空的旧译文也
                # 覆盖 archive，否则一次 --render-only 就会把旧标题重新带回来。
                if (
                    prior.get("title_en")
                    and prior.get("title_en") != row.get("title_en")
                ):
                    discovery["title_en"] = prior["title_en"]
                    discovery["title_zh"] = prior.get("title_zh", "")
                # render-only 随后会用同一批 archive 行重写正文页与正本；原地同步
                # 才能让修订后的标题不只出现在清单，也真正取代 archive 旧元数据。
                row.update(discovery)
            row = {**row, **borrowed, **discovery}
        merged[row["article_id"]] = row
    values = _admitted_library_rows(site, list(merged.values()))
    return site.oldest_first(values) if order == "oldest" else site.newest_first(values)


def _admitted_library_rows(site, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """应用站点可选的存量准入；没有声明的站保持既有行为。

    发现阶段的结构化过滤仍由各 adapter 的 ``parse_search_results`` 完成。这个
    hook 只让旧 ledger 在独立清单、跨库摘要和统一后台使用同一名单，且不删除
    ledger/archive 正本。Bloomberg 是首个需要它的站：早期全页解析曾收进侧栏。
    """
    return list(site.admitted_rows(rows))


def backfill_mentions(
    entries: dict[str, dict[str, Any]],
    stored: list[dict[str, Any]],
) -> int:
    """给还没有提及型判定的存量补一次,返回补了几条。

    判定发生在取正文那一刻(台账不存正文,过后没得数),所以 2026-08-24 之前
    入库的都没有判定。正文的正本在存档里 —— 从那儿数。**已有判定的不重判**:
    那可能是站长手工改过的。
    """
    changed = 0
    for row in stored:
        entry = entries.get(row.get("article_id", ""))
        if entry is None or "mention_only" in entry or not row.get("body"):
            continue
        entry["mention_only"] = stats.is_mention_only(row)
        changed += 1
    return changed


def backfill_provenance(
    entries: dict[str, dict[str, Any]], *, site=ft,
) -> int:
    """从旧台账仍保留的关键词无损恢复发现路径；不能确定的栏目明确标旧。

    v5 之前 ``keywords`` 同时装搜索词和栏目标签，但没有 ``origins``。搜索词
    可以精确恢复；单栏目站也能精确恢复；FT 的两个旧栏目共用同一标签，只能
    标记为历史未区分，绝不猜成其中一个。
    """
    label_to_hub = {label: slug for slug, label in site.HUB_LABELS.items()}
    topic_labels = set(label_to_hub) | {site.TOPIC_LABEL}
    legacy_slug = site.HUBS[0] if len(site.HUBS) == 1 else "__legacy__"
    legacy_label = site.HUB_LABELS.get(legacy_slug, site.TOPIC_LABEL)
    changed = 0
    for entry in entries.values():
        before = (list(entry.get("keywords") or []), list(entry.get("origins") or []))
        words = list(entry.get("keywords") or [])
        origins = [
            dict(origin) for origin in entry.get("origins") or []
            if isinstance(origin, dict) and origin.get("kind") and origin.get("name")
        ]
        for word in words:
            if word == site.TOPIC_LABEL:
                origin = {"kind": "hub", "name": legacy_slug}
            elif word in label_to_hub:
                origin = {"kind": "hub", "name": label_to_hub[word]}
            elif word not in topic_labels:
                origin = {"kind": "search", "name": word}
            else:
                continue
            if origin not in origins:
                origins.append(origin)
        if site.TOPIC_LABEL != legacy_label and site.TOPIC_LABEL in words:
            words = [legacy_label if word == site.TOPIC_LABEL else word for word in words]
        entry["keywords"] = sorted(set(words))
        if origins:
            entry["origins"] = origins
        after = (entry["keywords"], list(entry.get("origins") or []))
        changed += before != after
    return changed


def backfill_quality(
    entries: dict[str, dict[str, Any]],
    stored: list[dict[str, Any]],
    *,
    site=ft,
) -> int:
    """用正文正本重算整库准入；规则版本未变的条目不重复处理。"""
    bodies = {row.get("article_id", ""): row for row in stored}
    changed = 0
    for article_id, entry in entries.items():
        if entry.get("quality_version") == quality.VERSION:
            continue
        row = {
            **ledger_store.rows({article_id: entry})[0],
            **bodies.get(article_id, {}),
        }
        verdict = quality.assess(
            row, topic_labels=_topic_labels(site), hub_tiers=site.HUB_TIERS,
        )
        entry.update(verdict)
        changed += 1
    return changed


def missing_titles(entries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """台账里还没有中文标题的那些行。

    存量补译只看台账:标题、时间、关键词它都记着,**不需要碰存档也不需要出网**
    ——除了翻译本身那一次调用。
    """
    return [
        row for row in ledger_store.rows(entries)
        if row.get("title_en") and not str(row.get("title_zh") or "").strip()
    ]


def missing_from_archive(
    entries: dict[str, dict[str, Any]],
    out_dir: Path,
) -> list[dict[str, Any]]:
    """台账说取到过正文、存档里却没有的那些行。

    2026-08-22:存档机制上线之前爬的那批,正文只存在于渲染好的 HTML 里;
    整理目录时那些 HTML 被当成产物删掉了,正文就跟着没了。**产物可以重画,
    但只有正本重画得出来** —— 这个函数找的就是「有账无正本」的那些。

    只找台账记着 ``ok`` 的:``failed`` 是取过没取到,``skipped`` 是压根没取,
    两种都不是「缺了一份正本」。
    """
    stored = archive.stored_ids(out_dir)
    return [
        row
        for row in ledger_store.rows(entries)
        if row.get("body_status") == "ok" and row["article_id"] not in stored
    ]


def library_summaries(out_dir: Path) -> list[dict[str, Any]]:
    """各库一行摘要:从**本机各库的产出目录**读台账与跑批记录。

    为什么读盘的活在这里而不在 render:render 是纯函数(不写盘、不出网),
    跨库对比却需要姊妹库的台账 —— 那就由编排层读好再交进去。

    姊妹库的目录是 ``out/<OUT_DIR>``,和当前这库同级。读不到就标 missing:
    **一个假的 0 会被当成「那边没抓到东西」**,而真相是「这台机器上没有它」。
    """
    from inews import runlog
    from inews import sites as sites_registry

    root = out_dir.parent
    summaries: list[dict[str, Any]] = []
    for other in sites_registry.REGISTRY.values():
        base = root / other.OUT_DIR
        entries = ledger_store.load(ledger_store.path_for(base))
        runs = runlog.load(runlog.path_for(base))
        # 新来源最需要被看见的恰恰是「第一次发现就失败」：这时还没有 ledger，
        # 但 runs.json 已经是一次真实运行。只有两份状态都不存在才叫“未安装/未跑过”。
        if not entries and not runs:
            summaries.append({"label": other.LABEL, "key": other.KEY, "missing": True})
            continue
        visible = _admitted_library_rows(other, ledger_store.rows(entries))
        last = runs[-1] if runs else {}
        summaries.append({
            "label": other.LABEL,
            "key": other.KEY,
            "articles": len(visible),
            "with_body": sum(
                1 for row in visible if row.get("body_status") == "ok"
            ),
            "failed": sum(
                1 for row in visible if row.get("body_status") == "failed"
            ),
            "last_at": str(last.get("finished_at") or ""),
            "last_new": last.get("new", "—"),
            "last_ok": last.get("ok") if last else None,
            "backlog": last.get("backlog", "—"),
        })
    return summaries


def library_snapshots(out_root: Path) -> list[dict[str, Any]]:
    """读取统一后台所需的各库快照。

    与逐库页面共用台账和跑批记录，不建立第三份状态；Dashboard 永远是可重画的
    视图。关键词也从真实台账归纳，避免为每个站再维护一份展示配置。
    """
    from inews import runlog
    from inews import sites as sites_registry

    summaries = {
        item["key"]: item
        for item in library_summaries(out_root / "_current")
    }
    snapshots: list[dict[str, Any]] = []
    for site in sites_registry.REGISTRY.values():
        base = out_root / site.OUT_DIR
        entries = ledger_store.load(ledger_store.path_for(base))
        runs = runlog.load(runlog.path_for(base))
        summary = summaries.get(site.KEY, {
            "label": site.LABEL, "key": site.KEY, "missing": True,
        })
        if not entries and not runs:
            snapshots.append({"site": site, "summary": summary, "missing": True})
            continue
        rows = _admitted_library_rows(site, ledger_store.rows(entries))
        snapshots.append({
            "site": site,
            "summary": summary,
            "rows": rows,
            "runs": runs,
            "keywords": sorted({
                word
                for row in rows
                for word in row.get("keywords", [])
                if word not in sites_registry.TOPIC_LABELS
            }),
        })
    return snapshots


def write_unified_dashboard(out_root: Path, generated_at: str) -> Path:
    """写唯一的跨来源后台；各来源的清单和正文仍留在各自目录。"""
    # daily_chrome 与 headless 两个资源组允许并行；两边都会在一轮末尾重画这份
    # 共享快照。读各库 + 渲染 + 原子切换必须作为一个串行区间，否则较早的快照
    # 可能后写，反而覆盖已经包含另一站新台账的版本。
    with interprocess_lock(out_root / ".dashboard-generation.lock"):
        target = out_root / "DASHBOARD"
        target.mkdir(parents=True, exist_ok=True)
        write_text_atomic(target / render.STYLESHEET_NAME, render.STYLESHEET)
        index = target / "index.html"
        write_text_atomic(
            index,
            render.render_unified_dashboard(
                library_snapshots(out_root), generated_at=generated_at
            ),
        )
    return index


def _library_body_chars(out_dir: Path, rows: list[dict[str, Any]]) -> int:
    """只统计当前清单可见条目的正文；隐藏旧稿仍原样保留在 archive。"""
    visible_ids = {str(row.get("article_id") or "") for row in rows}
    return sum(
        len(str(row.get("body") or ""))
        for row in archive.load(out_dir)
        if str(row.get("article_id") or "") in visible_ids
    )


def write_site(
    rows: list[dict[str, Any]],
    out_dir: Path,
    *,
    keywords: list[str],
    generated_at: str,
    site=ft,
    order: str = "newest",
    notes: list[str] | None = None,
    library: list[dict[str, Any]] | None = None,
    new_count: int | None = None,
    runs: list[dict[str, Any]] | None = None,
) -> Path:
    """写出 ``index.html``、``dashboard.html`` 与逐篇正文页,返回清单页路径。

    ``rows`` 是**本轮**的稿子:只给它们写正文页。``library`` 是清单要列的全部
    (默认就是本轮)—— 每小时跑一轮时它是累积库,里面绝大多数行来自台账,
    手里没有正文;那些页面早就在盘上了,重写只会拿空正文把它们盖掉。
    """
    listing = rows if library is None else library
    out_dir.mkdir(parents=True, exist_ok=True)
    # `data/` 永不发布，但主站需要 Bloomberg 的每日标尺。只投影比较所需的
    # 非敏感字段到发布根目录：绝不带正文、错误原话、cookie、日志或内部路径。
    write_json_atomic(out_dir / "editorial-reference.json", {
        "schema_version": 1,
        "site": site.KEY,
        "generated_at": generated_at,
        "articles": [
            {
                "title": row.get("title_en", ""),
                "published_at": row.get("published_at", ""),
                "score": row.get("score"),
                "body_status": "ok" if row.get("body") else row.get("body_status", ""),
            }
            for row in listing
        ],
    }, backup=False)
    # 样式一份、页面多张:清单页、分析页和每篇正文页都 `<link>` 同一个相对路径,
    # 所以本地双击和挂到 inews.today/rawarticle/ft 下都能用同一份产出。
    (out_dir / render.STYLESHEET_NAME).write_text(render.STYLESHEET, encoding="utf-8")
    # 正文存档先落盘,再渲染页面:HTML 是产物,存档是正本。
    archive.save(out_dir, rows)
    for row in rows:
        page = out_dir / render.article_filename(row)
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            render.render_article(row, site_label=site.LABEL, site_key=site.KEY),
            encoding="utf-8",
        )
    # 后台页:给站长看链路和明细,不是给读者看的。和清单页一起发布 ——
    # 它已经在 forward_auth 后面,登录才看得到。
    (out_dir / "dashboard.html").write_text(
        render.render_dashboard(
            listing,
            generated_at=generated_at,
            keywords=keywords,
            runs=runs or [],
            notes=notes,
            # 站名与它的时间地板都只从 sites/ 来:render 里不写任何一个站的知识。
            floor=site.EARLIEST,
            site_label=site.LABEL,
            tagline=site.TAGLINE,
            site=site,
            libraries=library_summaries(out_dir),
        ),
        encoding="utf-8",
    )
    index = out_dir / "index.html"
    # **盘上真有哪几页**:存档里有的(重画得出来)加本轮刚写的。清单据此决定
    # 标题给不给链接 —— 台账记着这一篇不等于本地有它的正文页。
    on_disk = archive.stored_ids(out_dir) | {row["article_id"] for row in rows}
    index.write_text(
        render.render_index(
            listing,
            keywords=keywords,
            generated_at=generated_at,
            order=order,
            notes=notes,
            new_count=new_count,
            linkable=on_disk,
            # 清单页也要看得见抓取节奏:定时静默停摆时,页面本身是不变的。
            runs=runs or [],
            # 字数从存档正本数。重画一次就重数一次 —— 这份数字不该有第二个来源。
            body_chars=_library_body_chars(out_dir, listing),
            site_label=site.LABEL,
            tagline=site.TAGLINE,
            rules=site.RULES,
            site_key=site.KEY,
        ),
        encoding="utf-8",
    )
    write_unified_dashboard(out_dir.parent, generated_at)
    return index
