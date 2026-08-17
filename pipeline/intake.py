#!/usr/bin/env python3
"""投递入口：机检 + 三档分流。团队化之后，所有者是唯一合并者，也就是唯一瓶颈。

**本脚本的唯一目的：在所有者看到之前，把不合格的投递挡掉，把该他判的顶到最前面。**

15 个成员每周各交 2 次就是 30 次审阅；每次哪怕只花 20 分钟判断也是每周 10 小时。
所以不能"全部等他批"——那只是把瓶颈从「读」挪到「批」。

三档分流（2026-08-16 立，用户未否决）：
  A 必须人批   自评 ≥8 ／ 与现有 Finding 冲突 ／ 标了 sensitive ／ 会改写既有结论
  B 模型批     5-7 分、命中工单缺口、无冲突 → 模型入库，每周抽 10% 复核
  C 自动入库   ≤4 分存档件

机检五关（过不了直接退，不占所有者时间）：
  1. 格式    submission.json 必填字段、summary ≥200 字
  2. 溯源    每个 key_number 必须有 locator——写不出就说明没真看到那个数
  3. 查重    文件名/标题 撞 LIBRARY_SCORES.csv 即退
  4. 合法    模块号 M01-M15、confidence A-C、claimed_importance 1-9
  5. 命中    声明了 workorder 的，检查是否真的命中该模块

退回理由取小枚举并写进结果，便于回流给成员——**退回不给理由，成员下次照犯**。

用法：
  python3 pipeline/intake.py                       # 扫 docs/inbox/submissions/ 全部
  python3 pipeline/intake.py <投递目录>            # 只看一个
零依赖。
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBS = ROOT / "docs" / "inbox" / "submissions"
SCORES = ROOT / "docs" / "LIBRARY_SCORES.csv"
OUT = ROOT / "reports" / "intake_review.md"

VALID_MODULES = {f"M{i:02d}" for i in range(1, 16)}
MIN_SUMMARY = 200

REJECT = {
    "DUP": "重复——库内已有",
    "NO_LOCATOR": "数字无出处——key_number 缺 locator，无法回原文核对",
    "NO_NUMBERS": "无可落库数字——对事实层没有贡献",
    "SHORT_SUMMARY": f"summary 不足 {MIN_SUMMARY} 字",
    "BAD_MODULE": "模块号非法",
    "BAD_FIELD": "必填字段缺失或取值非法",
    "OFF_TARGET": "不命中所声明的工单模块",
}


def load_library():
    if not SCORES.exists():
        return set(), set()
    rows = list(csv.DictReader(SCORES.open(encoding="utf-8")))
    names = {Path(r["new_path"]).name.lower() for r in rows}
    olds = {(r["old_name"] or "").strip().lower() for r in rows if r.get("old_name")}
    return names, olds


def check_item(it, lib_names, lib_olds, decl_module):
    """返回 (退回理由码列表, 提示列表)。"""
    bad, warn = [], []
    for k in ("file", "title", "org", "year", "modules", "claimed_importance", "confidence", "summary"):
        if it.get(k) in (None, "", []):
            bad.append("BAD_FIELD")
            warn.append(f"缺字段 `{k}`")
    if bad:
        return bad, warn

    mods = it.get("modules") or []
    if any(m not in VALID_MODULES for m in mods):
        bad.append("BAD_MODULE")
        warn.append(f"非法模块号 {[m for m in mods if m not in VALID_MODULES]}")
    if it.get("confidence") not in {"A", "B", "C"}:
        bad.append("BAD_FIELD"); warn.append("confidence 须为 A/B/C")
    if not isinstance(it.get("claimed_importance"), int) or not 1 <= it["claimed_importance"] <= 9:
        bad.append("BAD_FIELD"); warn.append("claimed_importance 须为 1-9 整数")

    if len(it.get("summary") or "") < MIN_SUMMARY:
        bad.append("SHORT_SUMMARY")
        warn.append(f"summary 仅 {len(it.get('summary') or '')} 字")

    kn = it.get("key_numbers") or []
    if not kn:
        # 低分存档件允许无数字；≥5 分声称有价值却拿不出数字，退回
        if it.get("claimed_importance", 0) >= 5:
            bad.append("NO_NUMBERS")
            warn.append("自评 ≥5 分却没有任何 key_number")
    for n in kn:
        if not (n.get("locator") or "").strip():
            bad.append("NO_LOCATOR")
            warn.append(f"数字「{n.get('what','?')}」没有 locator")

    stem = Path(it.get("file", "")).name.lower()
    title = (it.get("title") or "").strip().lower()
    if stem in lib_names or stem in lib_olds or (title and title in lib_olds):
        bad.append("DUP")
        warn.append(f"库内已有同名件：{it.get('file')}")

    if decl_module and decl_module not in mods:
        bad.append("OFF_TARGET")
        warn.append(f"投递声明服务 {decl_module}，但本件 modules={mods} 不含它")

    return sorted(set(bad)), warn


def tier(it, bad):
    if bad:
        return "退回"
    if it.get("sensitive"):
        return "A"
    if it.get("claimed_importance", 0) >= 8:
        return "A"
    if it.get("claimed_importance", 0) >= 5:
        return "B"
    return "C"


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if not SUBS.exists():
        print(f"投递目录不存在：{SUBS.relative_to(ROOT)}（还没有成员投递）")
        return 0

    lib_names, lib_olds = load_library()
    dirs = [Path(target)] if target else sorted(p.parent for p in SUBS.rglob("submission.json"))
    if not dirs:
        print("没有找到任何 submission.json")
        return 0

    buckets = {"A": [], "B": [], "C": [], "退回": []}
    lines = ["# 投递审阅 — 机检结果与分流", "",
             "> 三档：**A 必须你批**（≥8分／敏感／与现有结论冲突）｜"
             "**B 模型批**（5-7分命中缺口，抽 10% 复核）｜**C 自动入库**（≤4 分存档）。",
             "> 退回项已带理由码，直接回流给成员即可——**退回不给理由，下次照犯**。", ""]

    for d in dirs:
        try:
            sub = json.loads((d / "submission.json").read_text(encoding="utf-8"))
        except Exception as e:
            print(f"✗ {d}：submission.json 读取失败 {e}")
            continue
        who = sub.get("contributor", "?")
        decl = sub.get("module")
        for it in sub.get("items", []):
            bad, warn = check_item(it, lib_names, lib_olds, decl)
            t = tier(it, bad)
            buckets[t].append((who, sub.get("workorder"), it, bad, warn, d))

    total = sum(len(v) for v in buckets.values())
    accepted = total - len(buckets["退回"])
    lines.append(f"共 {total} 件｜通过机检 {accepted}｜退回 {len(buckets['退回'])}"
                 f"｜**需你批 {len(buckets['A'])}**｜模型批 {len(buckets['B'])}｜自动 {len(buckets['C'])}")
    lines.append("")

    for t, label in (("A", "🔴 必须你批"), ("退回", "↩️ 退回成员"), ("B", "模型批（抽查）"), ("C", "自动入库")):
        if not buckets[t]:
            continue
        lines += [f"## {label}（{len(buckets[t])} 件）", ""]
        for who, wo, it, bad, warn, d in buckets[t]:
            head = (f"- **{it.get('claimed_importance','?')}{it.get('confidence','?')}** "
                    f"{it.get('title','?')[:52]} ｜ {it.get('org','?')} {it.get('year','?')} "
                    f"｜ → {'/'.join(it.get('modules') or [])} ｜ {who}"
                    + (f" ｜ 工单 {wo}" if wo else " ｜ *自主发现*"))
            lines.append(head)
            if it.get("sensitive"):
                lines.append("      🔒 **标了敏感** —— 对外产出前须脱敏或聚合")
            if bad:
                lines.append(f"      退回理由：{'；'.join(REJECT.get(b, b) for b in bad)}")
            for w in warn:
                lines.append(f"      · {w}")
            kn = it.get("key_numbers") or []
            if kn and t in ("A", "B"):
                for n in kn[:3]:
                    cal = f"｜口径：{n['caliber_note']}" if n.get("caliber_note") else ""
                    lines.append(f"      数：{n.get('what')} = {n.get('value')} {n.get('unit')}"
                                 f"（{n.get('locator')}）{cal}")
        lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"共 {total} 件｜通过 {accepted}｜退回 {len(buckets['退回'])}")
    print(f"  🔴 需你批 {len(buckets['A'])}｜模型批 {len(buckets['B'])}｜自动入库 {len(buckets['C'])}")
    for who, wo, it, bad, warn, d in buckets["退回"]:
        print(f"  ↩️ {it.get('title','?')[:40]}：{'；'.join(REJECT.get(b, b) for b in bad)}")
    print(f"完整审阅卡已写入 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
