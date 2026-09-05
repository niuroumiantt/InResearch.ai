#!/usr/bin/env python3
"""精读队列生成器：已打分但未消化的文献，按重要性排序——"这周该读什么"。

机制（与 verify.py 的核验队列平行）：
  已打分 = 在 docs/LIBRARY_SCORES.csv 里（importance 1-9 × confidence A-C）
  已消化 = 其 new_path 出现在 data/sources.json 某条记录的 local_file 字段
           （消化 = 读进知识层出 Finding + 登记来源，见 docs/DECISIONS.md）
  精读队列 = 已打分 − 已消化，importance 降序

depth 口径过滤（2026-08-16 全库通读后新增）：打分表混装四种阅读深度，
不能一股脑排进精读队列——
  精读/据实生成 → 可直接进队列（原文已读或每个数字可逐行回查）
  成员精读      → 全进且排最前——**等的是审计不是消化**，压着不审等于把未核实的内容
                  留在库里冒充已读
  半自动        → 只有 importance ≥ 6 才进队列（auto_batch 上限封 6，
                  分数是保守初值，需回原文复核才能上引证据链）
  目录级        → 一律不进队列（一行覆盖一个目录，是检索索引不是材料）
`--all` 可绕过过滤看全表。

节奏约定：每周至少消化 2 份 importance ≥ 8 的文献；打分本身由"扫描收件箱→
粗读打分"流程持续供给（LIBRARY_SCORES.csv 追加行）。

用法：python3 pipeline/reading_queue.py    # 队列 → reports/reading_queue.md + stdout
零依赖。
"""
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORES = ROOT / "docs" / "LIBRARY_SCORES.csv"
SOURCES = ROOT / "data" / "sources.json"
OUT = ROOT / "reports" / "reading_queue.md"


def eligible(row):
    """按阅读深度决定该行是否有资格进精读队列。"""
    depth = row.get("depth") or "精读"
    if depth == "目录级":
        return False
    if depth == "半自动":
        return int(row["importance"]) >= 6
    return True


def audit_pending(row):
    """成员投递尚未审计——排在队列最前，且在行末标出来。"""
    return (row.get("depth") or "") == "成员精读"


def main():
    show_all = "--all" in sys.argv
    digested = {r.get("local_file") for r in json.loads(SOURCES.read_text(encoding="utf-8"))["records"] if r.get("local_file")}
    rows = list(csv.DictReader(SCORES.open(encoding="utf-8")))
    pool = rows if show_all else [r for r in rows if eligible(r)]
    queue = [r for r in pool if r["new_path"] not in digested]
    queue.sort(key=lambda r: (not audit_pending(r), -int(r["importance"]), r["confidence"]))

    by_depth = Counter(r.get("depth") or "精读" for r in rows)
    lines = [
        "# 精读队列 — 该读什么",
        "",
        f"生成时间：{date.today().isoformat()} ｜ 打分表 {len(rows)} 份 ｜ 入队候选 {len(pool)} 份 "
        f"｜ 已消化 {len(pool) - len(queue)} 份 ｜ 待消化 {len(queue)} 份",
        "",
        "阅读深度分布：" + "、".join(f"{k} {v}" for k, v in by_depth.most_common()),
        "入队规则：**成员精读全进且排最前（等的是审计）**；精读/据实生成全进；半自动仅 importance ≥ 6；目录级不进（`--all` 看全表）。",
        "",
        "消化 = 读进知识层出 Finding + 登记 data/sources.json（local_file 对上即出队）。",
        "节奏：每周至少 2 份 importance ≥ 8。",
        "",
    ]
    for r in queue:
        fname = r["new_path"].split("/")[-1]
        lines.append(f"- [ ] **{r['importance']}{r['confidence']}** {fname} ｜ {r['org']} {r['year']} ｜ → {r['module']} ｜ {r.get('depth') or '精读'}"
                     + ("　**⚠ 待审计**" if audit_pending(r) else ""))
        lines.append(f"      {r['new_path']}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"打分表 {len(rows)} ｜ 入队候选 {len(pool)} ｜ 已消化 {len(pool) - len(queue)} ｜ 待消化 {len(queue)}")
    for r in queue[:8]:
        print(f"  {r['importance']}{r['confidence']}  {r['new_path'].split('/')[-1][:52]:52s} → {r['module']}")
    print(f"完整队列已写入 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
