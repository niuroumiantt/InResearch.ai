#!/usr/bin/env python3
"""逐篇阅读队列。分数只影响优先级；目录索引不是独立文章。

深读完成仅由稳定 doc_id 和完整覆盖率证明，旧来源登记/摘要/路径不能代替。
Spark 永久队列还负责公平调度、重试与阻塞状态，本脚本是旧打分表的迁移视图。
"""

from inresearch.paths import project_root
from inresearch.storage.layout import workspace_path
from inresearch.storage.files import atomic_write
import csv
import sys
from inresearch.knowledge import registry as research
from collections import Counter
from datetime import date

ROOT = project_root()
SCORES = ROOT / "docs" / "LIBRARY_SCORES.csv"
SOURCES = ROOT / "data" / "sources.json"
OUT = workspace_path("reports/reading_queue.md", ROOT)


def eligible(row):
    """按阅读深度决定该行是否有资格进精读队列。"""
    return row.get("depth") != "目录级"


def proven_complete(row, documents):
    doc_id = row.get('doc_id')
    return bool(doc_id and any(d.get('doc_id', d.get('id')) == doc_id
        and research.coverage_complete(d)
        for d in documents))


def audit_pending(row):
    """成员投递尚未审计——排在队列最前，且在行末标出来。"""
    return (row.get("depth") or "") == "成员精读"


def main():
    show_all = "--all" in sys.argv
    documents = research.build_snapshot(ROOT)["knowledge"]["documents"]
    rows = list(csv.DictReader(SCORES.open(encoding="utf-8")))
    pool = rows if show_all else [r for r in rows if eligible(r)]
    queue = [r for r in pool if not proven_complete(r, documents)]
    queue.sort(key=lambda r: (not audit_pending(r), -int(r["importance"]), r["confidence"]))

    by_depth = Counter(r.get("depth") or "精读" for r in rows)
    lines = [
        "# 精读队列 — 该读什么",
        "",
        f"生成时间：{date.today().isoformat()} ｜ 打分表 {len(rows)} 份 ｜ 入队候选 {len(pool)} 份 "
        f"｜ 已消化 {len(pool) - len(queue)} 份 ｜ 待消化 {len(queue)} 份",
        "",
        "阅读深度分布：" + "、".join(f"{k} {v}" for k, v in by_depth.most_common()),
        "入队规则：每篇独立文章都精读；分数只影响优先级；目录索引单列。旧表未建立内容身份和覆盖记录的材料保持待核。",
        "",
        "出阅读队列须稳定 doc_id 与完整页/分块覆盖；审核采用另行记录。登记来源或路径匹配不代表已精读。",
        "节奏：每周至少 2 份 importance ≥ 8。",
        "",
    ]
    for r in queue:
        fname = r["new_path"].split("/")[-1]
        lines.append(f"- [ ] **{r['importance']}{r['confidence']}** {fname} ｜ {r['org']} {r['year']} ｜ → {r['module']} ｜ {r.get('depth') or '精读'}"
                     + ("　**⚠ 待审计**" if audit_pending(r) else ""))
        lines.append(f"      {r['new_path']}")
    atomic_write(OUT, ("\n".join(lines) + "\n").encode('utf-8'))

    print(f"打分表 {len(rows)} ｜ 入队候选 {len(pool)} ｜ 已消化 {len(pool) - len(queue)} ｜ 待消化 {len(queue)}")
    for r in queue[:8]:
        print(f"  {r['importance']}{r['confidence']}  {r['new_path'].split('/')[-1][:52]:52s} → {r['module']}")
    print(f"完整队列已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
