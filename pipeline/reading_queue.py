#!/usr/bin/env python3
"""精读队列生成器：已打分但未消化的文献，按重要性排序——"这周该读什么"。

机制（与 verify.py 的核验队列平行）：
  已打分 = 在 docs/LIBRARY_SCORES.csv 里（importance 1-9 × confidence A-C）
  已消化 = 其 new_path 出现在 data/sources.json 某条记录的 local_file 字段
           （消化 = 读进知识层出 Finding + 登记来源，见 docs/DECISIONS.md）
  精读队列 = 已打分 − 已消化，importance 降序

节奏约定：每周至少消化 2 份 importance ≥ 8 的文献；打分本身由"扫描收件箱→
粗读打分"流程持续供给（LIBRARY_SCORES.csv 追加行）。

用法：python3 pipeline/reading_queue.py    # 队列 → reports/reading_queue.md + stdout
零依赖。
"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORES = ROOT / "docs" / "LIBRARY_SCORES.csv"
SOURCES = ROOT / "data" / "sources.json"
OUT = ROOT / "reports" / "reading_queue.md"


def main():
    digested = {r.get("local_file") for r in json.loads(SOURCES.read_text(encoding="utf-8"))["records"] if r.get("local_file")}
    rows = list(csv.DictReader(SCORES.open(encoding="utf-8")))
    queue = [r for r in rows if r["new_path"] not in digested]
    queue.sort(key=lambda r: (-int(r["importance"]), r["confidence"]))

    lines = [
        "# 精读队列 — 该读什么",
        "",
        f"生成时间：{date.today().isoformat()} ｜ 已打分 {len(rows)} 份 ｜ 已消化 {len(rows) - len(queue)} 份 ｜ 待消化 {len(queue)} 份",
        "",
        "消化 = 读进知识层出 Finding + 登记 data/sources.json（local_file 对上即出队）。",
        "节奏：每周至少 2 份 importance ≥ 8。",
        "",
    ]
    for r in queue:
        fname = r["new_path"].split("/")[-1]
        lines.append(f"- [ ] **{r['importance']}{r['confidence']}** {fname} ｜ {r['org']} {r['year']} ｜ → {r['module']}")
        lines.append(f"      {r['new_path']}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"已打分 {len(rows)} ｜ 已消化 {len(rows) - len(queue)} ｜ 待消化 {len(queue)}")
    for r in queue[:8]:
        print(f"  {r['importance']}{r['confidence']}  {r['new_path'].split('/')[-1][:52]:52s} → {r['module']}")
    print(f"完整队列已写入 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
