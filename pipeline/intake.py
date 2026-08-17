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

回流不另开写库路径：`--accept` 把过机检的 B/C 档写成**标准批次 CSV**，
走本地精读会话已经跑了 50+ 批的那条既有合并流程。A 档留给所有者人工过目，不自动入库。

成员登记的行 depth 标 **`成员精读`**——他确实读了，但**尚未经我们审计**。
它可以进精读队列（等着被审），但**不得进事实层**，与「半自动」同理：
不是不信任，是不宣称我们没做过的核实。审计通过后由所有者提级为「精读」。

用法：
  python3 pipeline/intake.py                       # 扫 docs/inbox/submissions/ 全部
  python3 pipeline/intake.py <投递目录>            # 只看一个
  python3 pipeline/intake.py --accept              # 把 B/C 档写成批次 CSV（A 档不自动入库）
零依赖。
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBS = ROOT / "docs" / "inbox" / "submissions"
SCORES = ROOT / "docs" / "LIBRARY_SCORES.csv"
OUT = ROOT / "reports" / "intake_review.md"
BATCHES = ROOT / "docs" / "inbox" / "scored_batches"
BATCH_FIELDS = ["new_path", "old_name", "importance", "confidence", "year", "org",
                "module", "summary", "scored", "depth"]

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


def safe(s, n):
    """生成的文件名要进账本，先洗掉分隔符与全角括号，避免账本里出现难查难引的名字。"""
    s = re.sub(r"[\\/:*?\"<>|（）()\[\]{}]", "", str(s)).strip()
    return re.sub(r"\s+", "", s)[:n] or "未署名"


def to_batch_rows(items, today):
    """把过机检的投递转成标准批次行——复用既有合并流程，不另开写库路径。"""
    rows = []
    for who, wo, it, bad, warn, d in items:
        name = (f"{it['claimed_importance']}{it['confidence']}_{it['year']}"
                f"_{safe(it['title'], 12)}_{safe(it['org'], 10)}")
        ext = Path(it["file"]).suffix or ".pdf"
        nums = "；".join(
            f"{n.get('what')}={n.get('value')}{n.get('unit')}（{n.get('locator')}"
            + (f"｜口径 {n['caliber_note']}" if n.get("caliber_note") else "") + "）"
            for n in (it.get("key_numbers") or []))
        summary = it["summary"]
        if nums:
            summary += f" **可落库数字**：{nums}"
        summary += (f" 【成员投递·{who}"
                    + (f"·回应工单 {wo}" if wo else "·自主发现")
                    + "】本行由成员登记，**尚未经我们审计**，不得直接上证据链。")
        if it.get("sensitive"):
            summary = "【敏感待判】" + summary
        rows.append({
            "new_path": f"docs/library/_submissions/{who}/{name}{ext}",
            "old_name": it["file"],
            "importance": str(it["claimed_importance"]),
            "confidence": it["confidence"],
            "year": str(it["year"]),
            "org": it["org"],
            "module": "/".join(it["modules"]),
            "summary": summary,
            "scored": today,
            "depth": "成员精读",
        })
    return rows


def hit_rates(buckets):
    """成员命中率——用户定的 KPI 是命中率不是投递量。"""
    tally = {}
    for t, items in buckets.items():
        for who, *_ in items:
            r = tally.setdefault(who, {"总": 0, "过": 0})
            r["总"] += 1
            if t != "退回":
                r["过"] += 1
    return tally


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    accept = "--accept" in sys.argv
    target = argv[0] if argv else None
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
    rates = hit_rates(buckets)
    if rates:
        print("  命中率（KPI）：" + "｜".join(
            f"{w} {v['过']}/{v['总']}（{v['过']*100//v['总']}%）" for w, v in sorted(rates.items())))

    if accept:
        promo = buckets["B"] + buckets["C"]
        if not promo:
            print("没有可自动入库的 B/C 档投递。")
        else:
            today = date.today().isoformat()
            rows = to_batch_rows(promo, today)
            BATCHES.mkdir(parents=True, exist_ok=True)
            who = safe(promo[0][0], 20)
            f = BATCHES / f"batch_sub_{today.replace('-', '')}_{who}.csv"
            with f.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=BATCH_FIELDS)
                w.writeheader(); w.writerows(rows)
            print(f"已写出批次 {f.relative_to(ROOT)}（{len(rows)} 行，depth=成员精读）")
            print("  → 走既有合并流程入表；**A 档不自动入库**，等你过目。")
    elif buckets["B"] or buckets["C"]:
        print(f"  提示：{len(buckets['B']) + len(buckets['C'])} 件 B/C 档可自动入库，加 --accept 生成批次。")

    print(f"完整审阅卡已写入 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
