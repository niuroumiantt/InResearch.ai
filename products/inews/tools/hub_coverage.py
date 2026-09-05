#!/usr/bin/env python3
"""验证站长的猜想:「想要的文章都在 /technology 下,不搜也能拿到」。

只读不写:开分类页若干页拿一份快照,和台账里**搜索线召回**的文章对比,
打印覆盖率和漏掉的名单。不动词表、不动 HUBS、不写台账、不写产出 ——
验证归验证,裁决(要不要裁词表)留给站长看着名单做。

    .venv/bin/python tools/hub_coverage.py                    # 默认 technology,10 页
    .venv/bin/python tools/hub_coverage.py --slug technology --pages 15
    .venv/bin/python tools/hub_coverage.py --out out/FT.COM

**会打开可见的 Chrome 窗口**(FT 是 manual 档),页与页之间和平时一轮同样限速。
出网走的还是 run.py 那道门(fetch_rendered_listing),不开新口。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from inews import keywords as kw  # noqa: E402
from inews import ledger as ledger_store  # noqa: E402
from inews import run as run_mod  # noqa: E402
from inews import stats  # noqa: E402
from inews.sites import ft  # noqa: E402
from inews.textutil import parse_datetime  # noqa: E402


def snapshot(slug: str, pages: int) -> dict[str, dict]:
    """开分类页若干页,合并成 {article_id: row}。停下的条件抄 run.py 的
    分类页循环:0 条(翻到底/解析失效)或没有新的(?page=N 不生效)。"""
    from inews.browser import fetch_rendered_listing

    pace = run_mod._pace(run_mod.PACE_SECONDS)
    rows: dict[str, dict] = {}
    for page in range(1, max(1, pages) + 1):
        url = ft.hub_url(slug, page)
        print(f"分类页「{slug}」第 {page} 页", flush=True)
        if page > 1:
            time.sleep(pace)
        html, _final = fetch_rendered_listing(
            url, site=ft.KEY, link_pattern=ft.LINK_PATTERN
        )
        parsed = ft.parse_search_results(html, kw.TOPIC_LABEL, url)
        if not parsed:
            print(f"第 {page} 页 0 条,停止翻页", flush=True)
            break
        new_here = ft.merge(rows, parsed, source=slug)
        print(f"第 {page} 页 {len(parsed)} 条 / {new_here} 新", flush=True)
        if not new_here:
            print(f"第 {page} 页没有新的,停止翻页", flush=True)
            break
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slug", default="technology")
    parser.add_argument("--pages", type=int, default=10)
    parser.add_argument("--out", type=Path, default=ROOT / "out" / "FT.COM")
    args = parser.parse_args()

    entries = ledger_store.load(ledger_store.path_for(args.out))
    if not entries:
        print(f"台账是空的:{ledger_store.path_for(args.out)} —— 没有对照就没有验证")
        return 2

    hub_rows = snapshot(args.slug, args.pages)
    if not hub_rows:
        print("快照一条都没有 —— 页面结构变了或这条路径不存在,验证做不了")
        return 2
    dated = sorted(
        published
        for published in (
            parse_datetime(row.get("published_at", "")) for row in hub_rows.values()
        )
        if published
    )
    if not dated:
        print("快照里一条带时间的都没有,横不出比较窗口,验证做不了")
        return 2
    oldest, newest = dated[0], dated[-1]

    report = stats.hub_coverage(
        ledger_store.rows(entries),
        hub_ids=set(hub_rows),
        hub_oldest=oldest.isoformat(),
    )
    covered, missed = report["covered"], report["missed"]
    denominator = len(covered) + len(missed)

    print()
    print(f"快照:/{args.slug} 共 {len(hub_rows)} 篇,"
          f"时间范围 {oldest:%Y-%m-%d} ~ {newest:%Y-%m-%d}")
    print(f"台账里搜索线召回、且落在这个窗口内的:{denominator} 篇")
    if denominator:
        print(f"其中也出现在 /{args.slug} 上的:{len(covered)} 篇"
              f"({len(covered) * 100 // denominator}%)")
    print(f"窗口之前的(快照够不着,不计入):{len(report['out_of_reach'])} 篇;"
          f"时间未知的(不猜,不计入):{len(report['undated'])} 篇")

    if missed:
        print(f"\n搜索找到了、/{args.slug} 上没有的 {len(missed)} 篇 ——"
              f"只爬分类页就会漏掉这些:")
        for row in ft.newest_first(missed):
            words = "、".join(sorted(set(row.get("keywords", [])) - {kw.TOPIC_LABEL}))
            section = row.get("section") or "未标注"
            print(f"  {str(row.get('published_at') or '')[:10]:10}"
                  f" [{section}] {row.get('title_en', '')}({words})")
    else:
        print(f"\n这个窗口内搜索线没有召回 /{args.slug} 之外的任何一篇。")

    # 反向粗估:快照上有、台账没有的,就是「只爬这个分类页」会额外背上的量。
    # 说「粗估」是因为台账≠想要的全集(有失败、有窗口),但量级是准的。
    extra = [i for i in hub_rows if i not in entries]
    print(f"\n反向看:/{args.slug} 快照上有、台账里没有的:{len(extra)} 篇 ——"
          f"改爬它就要逐篇处理这些(8-24 下架它,就是因为这批多数不是 AI 稿)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
