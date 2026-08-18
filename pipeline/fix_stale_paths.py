#!/usr/bin/env python3
"""修复打分表死路径：new_path 指向已迁移/不存在文件的行，按文件名在库内重新定位。

    python3 pipeline/fix_stale_paths.py            # 干跑：只出报告，不改表
    python3 pipeline/fix_stale_paths.py --apply    # 唯一匹配的行改写 new_path（原子写）

⚠️ **只能在本机跑**——库本体 docs/library/ 不进 git，云端会话没有它，无从验证存在性。
（全景审读 2026-08-18 查出数百行路径指向重组前的旧目录；云端不猜路径，
定位与改写都以磁盘实测为准，这就是本工具存在的原因。）

规则（与「数据只留不删」及留白纪律一致）：
- 行永不删除；改的只有 new_path 一个字段。
- 只有当文件名（basename）在库内**恰好命中一个**现存文件时才改写；
  零命中（文件真没了）与多命中（同名多份）一律不动，进报告人工处置。
- 报告落 reports/stale_paths.md；--apply 后必须跑 python3 pipeline/validate.py。

零依赖。
"""
import csv
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORES = ROOT / "docs" / "LIBRARY_SCORES.csv"
LIB = ROOT / "docs" / "library"
REPORT = ROOT / "reports" / "stale_paths.md"


def main():
    apply_mode = "--apply" in sys.argv
    if not LIB.exists():
        sys.exit("docs/library/ 不存在——本工具只能在持有库本体的本机上跑（见文件头注释）。")

    with SCORES.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    # 库内现存文件按 basename 建索引（一次遍历，13k 行查询走字典）
    disk = defaultdict(list)
    for p in LIB.rglob("*"):
        if p.is_file() and not p.name.startswith("."):
            disk[p.name].append(p.relative_to(ROOT).as_posix())

    stale, fixed, gone, ambiguous = [], [], [], []
    for r in rows:
        path = r.get("new_path") or ""
        if not path or (ROOT / path).exists():
            continue
        stale.append(r)
        hits = disk.get(path.rsplit("/", 1)[-1], [])
        if len(hits) == 1:
            fixed.append((path, hits[0]))
            if apply_mode:
                r["new_path"] = hits[0]
        elif not hits:
            gone.append(path)
        else:
            ambiguous.append((path, hits))

    lines = [f"# 打分表死路径报告 — {date.today().isoformat()}",
             "", f"全表 {len(rows)} 行 ｜ 路径失效 {len(stale)} 行：",
             f"唯一定位 {len(fixed)}（{'已改写' if apply_mode else '干跑未改，--apply 生效'}）｜"
             f" 文件已不存在 {len(gone)} ｜ 同名多份需人裁 {len(ambiguous)}", ""]
    if fixed:
        lines += ["## 唯一定位" + ("（已改写）" if apply_mode else "（待 --apply）"), ""]
        lines += [f"- {a}\n  → {b}" for a, b in fixed] + [""]
    if gone:
        lines += ["## 零命中（库内已无此文件名——行保留，路径不动，待人工核对）", ""]
        lines += [f"- {p}" for p in gone] + [""]
    if ambiguous:
        lines += ["## 多命中（同名多份，不敢自动挑——待人工指定）", ""]
        for a, hits in ambiguous:
            lines += [f"- {a}"] + [f"  - 候选：{h}" for h in hits]
        lines.append("")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if apply_mode and fixed:
        tmp = SCORES.with_name(SCORES.name + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, SCORES)
        print(f"已改写 {len(fixed)} 行 → 记得跑 python3 pipeline/validate.py")
    print(f"失效 {len(stale)} ｜ 唯一定位 {len(fixed)} ｜ 零命中 {len(gone)} ｜ "
          f"多命中 {len(ambiguous)} ｜ 报告：reports/stale_paths.md")


if __name__ == "__main__":
    main()
