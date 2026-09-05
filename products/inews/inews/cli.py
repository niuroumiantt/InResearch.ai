"""命令行入口:``inews``(等价于 ``python -m inews``)。

    inews --group "模型应用 · 通用组1" --limit 10
    inews --keyword "AI agent" --keyword "AI coding" --no-body

只在你自己的机器上跑:私有正文经**你自己的订阅登录态**取得，公开来源直接读取，
没有服务器参与。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from inews import keywords as kw
from inews import archive
from inews import ledger as ledger_store
from inews import runlog
from inews import stats
from inews import run
from inews import score as score_module
from inews import sites
from inews import translate



def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="inews", description="按站点规则采集文章并生成 HTML")
    parser.add_argument("--site", default="ft", choices=sorted(sites.REGISTRY),
                        help="抓哪个站(默认 ft；其余站点按各自 adapter 的固定召回线运行)")
    parser.add_argument("--keyword", action="append", default=[],
                        help="直接指定关键词,可重复;给了就忽略 --group")
    parser.add_argument("--group", default=kw.DEFAULT_GROUP,
                        help=f"关键词组名或 all(默认:{kw.DEFAULT_GROUP})")
    parser.add_argument("--pages", type=int, default=1, help="每个词翻几页搜索结果")
    parser.add_argument("--limit", type=int, default=20,
                        help="本轮最多处理几篇**新增**;给 0 表示不截断(深挖用)")
    parser.add_argument("--since", default="",
                        help="只要这个日期之后的,如 2026-08-01;缺时间的条目一律保留")
    parser.add_argument("--order", choices=("newest", "oldest"), default="newest",
                        help="清单按发布时间倒序(默认)还是正序")
    parser.add_argument("--no-translate", action="store_true",
                        help="不翻译标题(默认翻译新增的那几篇,缺凭据时自动跳过)")
    parser.add_argument("--no-score", action="store_true",
                        help="不打分(默认给新增的那几篇打分,缺凭据时自动跳过)")
    parser.add_argument("--rescore", action="store_true",
                        help="给库里还没有分的存量补打(从存档读正文,不出网抓取)")
    parser.add_argument("--no-body", action="store_true",
                        help="只取标题/时间/链接,不点进正文")
    parser.add_argument("--out", type=Path, default=None,
                        help="输出目录(默认 out/<站点>,如 out/FT.COM)")
    parser.add_argument("--ledger", type=Path, default=None,
                        help="爬取台账路径(默认 <out>/ledger.json)")
    parser.add_argument("--recrawl", action="store_true",
                        help="忽略台账,把爬过的也重爬一遍")
    parser.add_argument("--retitle", action="store_true",
                        help="给库里还没有中文标题的那些补译(一次性;之后跟着新增走)")
    parser.add_argument("--render-only", action="store_true",
                        help="不出网:从盘上的正文存档把整站重画一遍(换版式用)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="不搜索:把台账里记着「取正文失败」的那些重取一遍(并按原因归类报出来)")
    parser.add_argument("--refill", action="store_true",
                        help="不搜索:把台账说取到过、存档里却没有的那些正文重新取回来")
    parser.add_argument("--serve", action="store_true",
                        help="常驻本机监听,让清单页上的「抓一轮」按钮真的能按(只绑 127.0.0.1)")
    parser.add_argument("--include-seen", action="store_true",
                        help="清单里也列出爬过的(默认只列本轮新增)")
    return parser.parse_args(argv)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _translate(rows: list[dict[str, object]], progress) -> list[str]:
    """翻这一批的标题,返回要写进「本轮记录」的话。

    **没配凭据不是失败**:那是常态(比如刚 clone 下来的一台机器)。跳过就跳过,
    但要把缺什么说在页面上 —— 一个静默不翻译的程序,看起来和「翻译坏了」一样。
    """
    state = translate.status()
    if not state["ok"]:
        return [f"标题未翻译:{state['note']}"]
    done = translate.fill_titles(rows, progress=progress)
    failed = sum(1 for row in rows if row.get("title_zh_error"))
    notes = [f"标题翻译 {done} 条"]
    if failed:
        # 失败原话已经挂在每一行上,这里只报个数 —— 页面上那几行会自己说话。
        notes.append(f"其中 {failed} 条翻译失败(原话见对应条目)")
    return notes


def _score(rows: list[dict[str, object]], progress) -> list[str]:
    """给这一批打分,返回要写进「本轮记录」的话。凭据与翻译共用一份 ——
    没配就跳过并说清缺什么,和 ``_translate`` 同一个姿态。"""
    state = translate.status()
    if not state["ok"]:
        return [f"文章未打分:{state['note']}"]
    done = score_module.fill_scores(rows, progress=progress)
    failed = sum(1 for row in rows if row.get("score_error"))
    notes = [f"文章打分 {done} 篇"]
    if failed:
        notes.append(f"其中 {failed} 篇打分失败(原话见对应条目)")
    return notes


# 分数住在台账里,正文页却是从存档行画出来的 —— 重画前把分数并回行上,
# 否则一次 --render-only 就会把每一页的评分卡抹掉。
_SCORE_KEYS = (
    "score", "score_version", "score_detail", "score_notes", "score_error",
    *ledger_store.QUALITY_FIELDS,
)


def _overlay_scores(entries: dict, rows: list[dict[str, object]]) -> None:
    for row in rows:
        entry = entries.get(row.get("article_id", ""))
        if entry:
            row.update({key: entry[key] for key in _SCORE_KEYS if key in entry})


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.serve:
        # 这一支不抓任何东西:它只是把按钮和 tools/hourly.sh 接起来。
        from inews import serve

        return serve.main()
    site = sites.get(args.site)
    if args.out is None:
        args.out = Path.cwd() / "out" / site.OUT_DIR

    def progress(message: str) -> None:
        print(f"[inews] {message}", flush=True)

    if site.SEARCHABLE:
        words = list(args.keyword) or list(kw.keywords_for(args.group))
    else:
        # 这个站的立场是「确定性优先,只走栏目页」—— 词表在这里没有意义。
        # 静默吞掉用户显式传的词会让人以为搜了,所以要说一声。
        words = []
        if args.keyword:
            progress(f"{site.NAME} 未配搜索线,忽略 --keyword")

    ledger_path = args.ledger or ledger_store.path_for(args.out)
    if args.render_only:
        # 换版式不该是一次抓取。存档在盘上,重画一遍是纯本地的事。
        stored = archive.load(args.out)
        entries = ledger_store.load(ledger_path)
        provenance_judged = run.backfill_provenance(entries, site=site)
        # 顺路把存量的提及型判定补上:--render-only 本来就要读一遍全部存档,
        # 这是唯一一处不用再出网就能数到正文的地方。
        judged = run.backfill_mentions(entries, stored)
        quality_judged = run.backfill_quality(entries, stored, site=site)
        if provenance_judged or judged or quality_judged:
            ledger_store.save(ledger_path, entries)
        if provenance_judged:
            progress(f"补全发现来源 {provenance_judged} 条(已写回台账)")
        if judged:
            progress(f"补判「仅提及」{judged} 条(已写回台账)")
        if quality_judged:
            progress(f"补判编辑准入 {quality_judged} 条(已写回台账)")
        # 正文页从存档行画,分数在台账里 —— 不并回去,重画会抹掉每页的评分卡。
        _overlay_scores(entries, stored)
        library = run.library_rows(entries, stored, order=args.order, site=site)
        # 重画必须覆盖整个台账，不只覆盖有正文存档的行。失败页和只列清单页也
        # 是 HTML 产物；若只重写 stored，它们会永久保留旧模板和坏链接。
        index = run.write_site(
            library, args.out, keywords=words, site=site, order=args.order,
            generated_at=_now(), library=library,
            runs=runlog.load(runlog.path_for(args.out)),
        )
        progress(f"重画完成:{len(stored)} 篇正文 / 库内 {len(library)} 篇 → {index}")
        return 0

    if args.retitle:
        # 存量补译:**不搜索、不取正文**。要补哪些,台账一看就知道 ——
        # 混进一次抓取,就分不清「翻译花了多久」和「抓取花了多久」。
        entries = ledger_store.load(ledger_path)
        state = translate.status()
        if not state["ok"]:
            # 缺凭据不是崩溃,但**这条命令的全部意义就是翻译** —— 一句都翻不了
            # 还回 0,那是在说谎。
            progress(state["note"])
            return 1
        holes = run.missing_titles(entries)
        if not holes:
            progress("库里每条都有中文标题了")
            return 0
        if args.limit > 0 and len(holes) > args.limit:
            progress(f"缺 {len(holes)} 条,本轮先补前 {args.limit} 条")
            holes = holes[: args.limit]
        progress(f"要补 {len(holes)} 条标题")
        done = translate.fill_titles(holes, progress=progress)
        # **写回台账**:不写回,下一轮重画又是英文,而且会再翻一遍再花一次钱。
        for row in holes:
            entry = entries.get(row["article_id"])
            if entry is not None and row.get("title_zh"):
                entry["title_zh"] = row["title_zh"]
        ledger_store.save(ledger_path, entries)
        # 存档里有正本的那几篇也把译文补上,免得下次 --render-only 从存档读回旧的。
        stored = archive.load(args.out)
        translations = {row["article_id"]: row["title_zh"] for row in holes if row.get("title_zh")}
        touched = [
            {**row, "title_zh": translations[row["article_id"]]}
            for row in stored if row["article_id"] in translations
        ]
        archive.save(args.out, touched)
        library = run.library_rows(entries, archive.load(args.out), order=args.order, site=site)
        index = run.write_site(
            [], args.out, keywords=words, site=site, order=args.order, generated_at=_now(),
            library=library, runs=runlog.load(runlog.path_for(args.out)),
        )
        failed = sum(1 for row in holes if row.get("title_zh_error"))
        progress(f"补回 {done} 条 / 尝试 {len(holes)} 条" + (f",{failed} 条失败" if failed else "")
                 + f" → {index}")
        return 0

    if args.rescore:
        # 存量补分:**不搜索、不取正文**。正文的正本在存档里,分数进台账 ——
        # 和 --retitle 同一个形状:要补哪些,台账和存档一比就知道。
        entries = ledger_store.load(ledger_path)
        state = translate.status()
        if not state["ok"]:
            # 这条命令的全部意义就是打分,缺凭据时回 0 是在说谎。
            progress(state["note"])
            return 1
        stored = archive.load(args.out)
        pending = [
            row for row in stored
            if row.get("body")
            and row["article_id"] in entries
            and entries[row["article_id"]].get("score_version") != score_module.VERSION
        ]
        if not pending:
            progress("库里有正文的每篇都有分了")
            return 0
        if args.limit > 0 and len(pending) > args.limit:
            progress(f"缺 {len(pending)} 篇,本轮先打前 {args.limit} 篇")
            pending = pending[: args.limit]
        progress(f"要补 {len(pending)} 篇的分")
        done = score_module.fill_scores(pending, progress=progress)
        # 写回台账:不写回,分数只活在这一轮的内存里 —— 8-24 失败原话丢过
        # 一次的同一个坑。
        for row in pending:
            entry = entries.get(row["article_id"])
            if entry is None:
                continue
            if isinstance(row.get("score"), int):
                entry["score"] = row["score"]
                entry["score_version"] = row.get("score_version", score_module.VERSION)
                entry["score_detail"] = dict(row.get("score_detail") or {})
                entry["score_notes"] = str(row.get("score_notes") or "")
                entry.pop("score_error", None)
            elif row.get("score_error"):
                entry["score_error"] = str(row["score_error"])[:400]
        ledger_store.save(ledger_path, entries)
        # 刚打分的那几页重画,评分卡才会出现在正文页上;其余存量的分由
        # library_rows 从台账借给清单。
        _overlay_scores(entries, stored)
        index = run.write_site(
            pending, args.out, keywords=words, site=site, order=args.order, generated_at=_now(),
            library=run.library_rows(entries, stored, order=args.order, site=site),
            runs=runlog.load(runlog.path_for(args.out)),
        )
        failed = sum(1 for row in pending if row.get("score_error"))
        progress(f"补分 {done} 篇 / 尝试 {len(pending)} 篇"
                 + (f",{failed} 篇失败" if failed else "") + f" → {index}")
        return 0

    if args.retry_failed:
        # **不搜索。** 要重试哪几篇,台账自己说得清楚;再跑一遍搜索既慢,又会把
        # 「这批为什么失败」和「有没有新稿子」混成一件事。
        entries = ledger_store.load(ledger_path)
        stuck = run.failed_rows(entries)
        if not stuck:
            progress("台账里没有取正文失败的条目")
            return 0
        # 重试之前先把**旧原因**摆出来:这一条就是「是不是同一个原因」的答案。
        for reason, count in stats.by_failure_reason(stuck):
            progress(f"失败原因 · {reason}:{count} 篇")
        if args.limit > 0 and len(stuck) > args.limit:
            progress(f"失败 {len(stuck)} 篇,本轮先重试前 {args.limit} 篇")
            stuck = stuck[: args.limit]
        progress(f"重试 {len(stuck)} 篇")
        run.fetch_bodies(stuck, site=site, progress=progress)
        if not args.no_translate:
            for note in _translate(stuck, progress):
                progress(note)
        if not args.no_score:
            for note in _score(stuck, progress):
                progress(note)
        # 先把正文正本和新状态持久化,再从这两份真相重画页面。
        # 旧顺序先 write_site、最后才 record,会让 write_site 内部重画的
        # 统一 dashboard 仍读到失败台账。先存档再写台账,中途即使
        # 渲染失败,``--render-only`` 也能用盘上正本恢复。
        archive.save(args.out, stuck)
        ledger_store.record(entries, stuck, crawled_at=_now())
        ledger_store.save(ledger_path, entries)
        stored = archive.load(args.out)
        merged = {row["article_id"]: row for row in stored}
        merged.update({row["article_id"]: row for row in stuck if row.get("body")})
        index = run.write_site(
            stuck, args.out, keywords=words, site=site, order=args.order, generated_at=_now(),
            library=run.library_rows(entries, list(merged.values()), order=args.order, site=site),
            runs=runlog.load(runlog.path_for(args.out)),
        )
        got = sum(1 for row in stuck if row.get("body"))
        progress(f"补回 {got} 篇 / 重试 {len(stuck)} 篇 → {index}")
        for reason, count in stats.by_failure_reason(stuck):
            progress(f"仍然失败 · {reason}:{count} 篇")
        return 0

    if args.refill:
        # 补正本:**不搜索**。要补哪几篇,台账和存档一比就知道 —— 再跑一遍搜索
        # 既慢又会把这件事和「有没有新稿子」混在一起。
        entries = ledger_store.load(ledger_path)
        holes = run.missing_from_archive(entries, args.out)
        if not holes:
            progress("存档是全的,没有要补的")
            return 0
        if args.limit > 0 and len(holes) > args.limit:
            progress(f"缺 {len(holes)} 篇,本轮先补前 {args.limit} 篇")
            holes = holes[: args.limit]
        progress(f"要补 {len(holes)} 篇正文")
        run.fetch_bodies(holes, site=site, progress=progress)
        if not args.no_translate:
            for note in _translate(holes, progress):
                progress(note)
        if not args.no_score:
            for note in _score(holes, progress):
                progress(note)
        stored = archive.load(args.out)
        merged = {row["article_id"]: row for row in stored}
        merged.update({row["article_id"]: row for row in holes if row.get("body")})
        index = run.write_site(
            holes, args.out, keywords=words, site=site, order=args.order, generated_at=_now(),
            library=run.library_rows(entries, list(merged.values()), order=args.order, site=site),
            runs=runlog.load(runlog.path_for(args.out)),
        )
        filled = sum(1 for row in holes if row.get("body"))
        # 补不回来的**如实说**:那几篇的正文在本地已经没有了,页面上也照实标着。
        progress(f"补回 {filled} 篇 / 尝试 {len(holes)} 篇 → {index}")
        return 0

    # **不在这里截断。** --limit 必须落在剔完台账之后:先截断的话,每轮都是同样
    # 那 20 篇最旧的 → 全在台账里 → 新增永远 0,第 21 篇永远轮不到。
    # 2026-08-20 站长第一轮增量就撞上这个,「新增 0」看起来像没新闻,其实是卡住了。
    rows, notes, sources = run.collect(
        words,
        site=site,
        pages=args.pages,
        limit=0,
        since=args.since,
        order=args.order,
        progress=progress,
    )

    entries = {} if args.recrawl else ledger_store.load(ledger_path)
    provenance_judged = run.backfill_provenance(entries, site=site)
    discovered = ledger_store.merge_discovery(entries, rows)
    if provenance_judged or discovered:
        # 旧稿重新被另一条线发现时，来源本身就是新事实；正文无需重抓，但这个
        # 事实必须立刻持久化，下一次离线重画才能据此复判。
        ledger_store.save(ledger_path, entries)
    fresh, seen = ledger_store.split_new(entries, rows)
    if seen:
        notes.append(f"台账里已有 {len(seen)} 篇,跳过")
        progress(notes[-1])
    listed = rows if args.include_seen else fresh
    if args.limit > 0:
        if len(listed) > args.limit:
            notes.append(f"本轮只处理前 {args.limit} 篇,还剩 {len(listed) - args.limit} 篇待下轮")
            progress(notes[-1])
        listed = listed[: args.limit]
    fresh = [row for row in listed if not ledger_store.is_seen(entries, row)]

    # 本轮到点重试补回来的那些。**要进 write_site 的 rows** —— 不然正文取回来了,
    # 页面却不会被写出来,清单上照旧挂着「正文未取到」。它们不算「新增」:
    # new_count 仍然只数 fresh。
    repaired: list[dict[str, object]] = []

    def write() -> object:
        return run.write_site(
            listed + repaired,
            args.out,
            keywords=words,
            site=site,
            order=args.order,
            # 清单列的是**累积库**(台账 + 本轮),不是本轮那几篇。每小时跑一轮时
            # 本轮通常只有两三篇 —— 只列本轮的话,页面每小时清空一次,
            # 攒了几个月的库一次都不出现在读者眼前。
            library=run.library_rows(
                entries, listed + repaired, order=args.order, site=site
            ),
            new_count=len(fresh),
            runs=runs,
            generated_at=datetime.now(timezone.utc)
            .astimezone()
            .isoformat(timespec="seconds"),
            notes=notes,
        )

    # **清单先落盘,再去取正文。** 2026-08-19:站长跑了 90 页搜索,程序在写盘那步
    # 崩掉,一条都没留下 —— 最贵的那段(几十次浏览器打开)的成果不该押在后面每
    # 一步都不出错上。取正文失败也一样:清单已经在盘上了。
    runs = runlog.load(runlog.path_for(args.out))
    index = write()
    progress(f"清单已写入 {index}(新增 {len(fresh)} 篇 / 本轮命中 {len(rows)} 篇)")
    if not args.no_body:
        # **只给新增取正文。** 每小时一轮的成本必须随「新增了几篇」走,
        # 而不是随「搜索命中了几篇」走 —— 后者每轮都是 500。
        run.fetch_bodies(fresh, site=site, progress=progress)
        # 外加**到点该再试的**那几篇失败的:退避表(6/24/72 小时)决定谁到点了。
        # 每轮全试会把一轮拖成几十次注定失败的打开;一次失败就永别,又会让一次
        # 登录态过期永久留下几篇空白。试满之后这里不再碰它,只等「修复未抓取」。
        retries = run.due_for_retry(
            entries,
            now=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        )
        if len(retries) > run.AUTOMATIC_RETRY_LIMIT:
            notes.append(
                f"到点重试 {len(retries)} 篇,本轮只处理前 "
                f"{run.AUTOMATIC_RETRY_LIMIT} 篇"
            )
            retries = retries[:run.AUTOMATIC_RETRY_LIMIT]
        if retries:
            progress(f"到点重试 {len(retries)} 篇取正文失败的")
            run.fetch_bodies(retries, site=site, progress=progress)
            repaired.extend(row for row in retries if row.get("body"))
            progress(f"重试补回 {len(repaired)} 篇 / {len(retries)} 篇")
        # 翻译放在取正文**之后**、写台账**之前**:译文要跟着这一批一起进台账
        # 和存档,否则下一轮它们已经是「爬过的」,再也不会被翻到。
        if not args.no_translate:
            notes.extend(_translate(fresh + repaired, progress))
        # 打分同理:分要跟着这一批进台账,不然下一轮它们就轮不到 --rescore
        # 之外的任何机会了。放在翻译之后 —— 打分失败不该影响标题。
        if not args.no_score:
            notes.extend(_score(fresh + repaired, progress))
        index = write()
        ledger_store.record(
            entries,
            # 仍然失败的也要写回去:``body_attempts`` 和 ``crawled_at`` 是退避
            # 唯一的依据 —— 不写,下一轮它又「到点了」,退避形同虚设。
            fresh + retries,
            crawled_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        ledger_store.save(ledger_path, entries)
        progress(f"台账已更新:{ledger_path}(共 {len(entries)} 条)")
    # 每轮留一条记录。**「新增 0」是常态,「连着几轮失败」不是** —— 从页面上
    # 两者长得一模一样(都是没变化),只有记下来才分得开。
    failures = sum(1 for row in listed if row.get("body_error"))
    first_touch: dict[str, int] = {}
    for row in fresh:
        name = str(row.get("found_via") or "")
        first_touch[name] = first_touch.get(name, 0) + 1
    runs = runlog.record(
        runlog.path_for(args.out),
        {
            "finished_at": _now(),
            "ok": bool(rows),
            "error": "" if rows else "一篇都没命中(搜索链路可能断了)",
            "hits": len(rows),
            "new": len(fresh),
            "processed": len(listed),
            "body_failed": failures,
            "backlog": max(0, len(rows) - len(seen) - len(listed)),
            # 每条召回线的账。**入库新增按「谁先看见」归属**,有顺序偏向,
            # 所以它只回答「谁先带来」;要判断一条线值不值,看 dashboard 上
            # 按「每页新增」排的那张表,几周的累计比单轮可靠。
            "sources": [
                {**source, "ledger_new": first_touch.get(source["name"], 0)}
                for source in sources
            ],
        },
    )
    write()
    progress(f"共 {len(listed)} 篇,已写入 {index}")
    # 一篇都没命中时给非零退出码:静默的"全绿"会让链路断了也没人知道。
    # **新增为 0 不算失败** —— 每小时跑一轮时,那才是常态。
    if not rows:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
