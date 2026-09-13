#!/usr/bin/env python3
"""投递入口：机检 + 三档分流。团队化之后，所有者是唯一合并者，也就是唯一瓶颈。

**本脚本的唯一目的：在所有者看到之前，把不合格的投递挡掉，把该他判的顶到最前面。**

15 个成员每周各交 2 次就是 30 次审阅；每次哪怕只花 20 分钟判断也是每周 10 小时。
所以不能"全部等他批"——那只是把瓶颈从「读」挪到「批」。

三档分流（2026-08-16 立，2026-08-17 用户批复）：
  A 必须人批   自评 ≥8 ／ 与现有事实冲突 ／ 标了 sensitive ／ 会改写既有结论
  B 模型批     5-7 分、命中工单缺口、无冲突 → 模型入库，抽 10% 复核
  C 自动入库   ≤4 分存档件

「与现有事实冲突」怎么判（2026-08-17 补，此前只写在注释里、代码没实现）：
拿投递的 key_number 去 data/facts.json 里找**同单位且指标名相近**的既有事实，
数值相差 ≥2 倍就升 A 档。这是烟雾报警器不是判决书——名字相近不等于同口径，
同口径的两个数差 2 倍也可能都对（不同地区、不同年份）。它的作用只是**别让
一个和我们既有结论打架的数静默入库**。误报的代价是所有者多看一件，漏报的
代价是错误数据进了库还没人知道；**误报便宜、漏报贵**，所以宁可报宽。

10% 抽查怎么抽（同上，此前也没实现）：按投递件的稳定标识哈希取模，
**确定性抽样**——同一件每次跑都是同一个结论，不会重跑一次换一批。
抽中的件在批次 CSV 的 summary 里带「【抽查复核】」前缀，合进
LIBRARY_SCORES.csv 后仍可 grep 到；否则「抽了 10%」只是屏幕上一闪的数字，
事后没人找得到该复核哪几件。

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
  python3 manage.py submissions                       # 扫 docs/inbox/submissions/ 全部
  python3 manage.py submissions <投递目录>            # 只看一个
  python3 manage.py submissions --accept              # 把 B/C 档写成批次 CSV（A 档不自动入库）
  python3 manage.py submissions --selftest            # 自检：冲突升档与模板排除是否还生效
零依赖。
"""

from inresearch.paths import project_root
import csv
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = project_root()
SUBS = ROOT / "docs" / "inbox" / "submissions"
SCORES = ROOT / "docs" / "LIBRARY_SCORES.csv"
FACTS = ROOT / "data" / "facts.json"
METRICS = ROOT / "framework" / "metrics.json"
OUT = ROOT / "reports" / "intake_review.md"
BATCHES = ROOT / "docs" / "inbox" / "scored_batches"
BATCH_FIELDS = ["new_path", "old_name", "importance", "confidence", "year", "org",
                "module", "summary", "scored", "depth"]

VALID_MODULES = {f"M{i:02d}" for i in range(1, 16)}
MIN_SUMMARY = 200

CONFLICT_RATIO = 2.0   # 与既有事实相差达此倍数即报冲突
NAME_OVERLAP = 0.30    # 指标名相近的判据：2-gram 重合率下限
AUDIT_RATE = 10        # B 档抽查比例的分母：10 → 抽 10%

REJECT = {
    "DUP": "重复——库内已有",
    "NO_LOCATOR": "证据无出处——缺 locator，无法回原文核对",
    "NO_EVIDENCE": "缺可定位的数字或非数字证据",
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


def load_facts():
    """既有事实按单位归桶，供冲突检测比对。缺文件不算错——事实层还在长。"""
    if not (FACTS.exists() and METRICS.exists()):
        return {}
    names = {m["metric_id"]: m["name"]
             for m in json.loads(METRICS.read_text(encoding="utf-8"))["metrics"]}
    by_unit = {}
    for r in json.loads(FACTS.read_text(encoding="utf-8"))["records"]:
        if r.get("value") is None:      # 留白记录没有数值，比不了
            continue
        by_unit.setdefault(norm_unit(r["unit"]), []).append(
            (names.get(r["metric_id"], r["metric_id"]), r))
    return by_unit


def norm_unit(u):
    """单位比较前抹掉空格与大小写差异；「元/㎡」和「元 / ㎡」是同一个单位。"""
    return re.sub(r"\s+", "", str(u or "")).lower()


def grams(s):
    s = re.sub(r"[\s（）()、，,]", "", str(s or ""))
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def close_name(a, b):
    """指标名是否相近——2-gram 重合率。中文没有词边界，按字对比比分词稳。"""
    ga, gb = grams(a), grams(b)
    return len(ga & gb) / max(1, min(len(ga), len(gb))) >= NAME_OVERLAP


def conflicts(it, by_unit):
    """返回与既有事实疑似冲突的说明列表。**烟雾报警器，不是判决书**——
    报出来只是让所有者看一眼，不改分、不退回。"""
    out = []
    for n in it.get("key_numbers") or []:
        try:
            v = float(n.get("value"))
        except (TypeError, ValueError):
            continue
        if v == 0:
            continue
        for label, r in by_unit.get(norm_unit(n.get("unit")), []):
            if not close_name(n.get("what"), label):
                continue
            old = float(r["value"])
            if old == 0:
                continue
            ratio = max(v, old) / min(v, old)
            if ratio >= CONFLICT_RATIO:
                cal = "/".join(str(x) for x in (r.get("caliber") or {}).values()) or "口径未标"
                out.append(f"「{n.get('what')}」= {v}{n.get('unit')}，"
                           f"而库内「{label}」已有 {old}{r['unit']}"
                           f"（{cal}，{r['as_of']}）——**差 {ratio:.1f} 倍**")
                break   # 同一个数报一次就够，不刷屏
    return out


def audit_sampled(it):
    """确定性抽样：同一件每次跑结论相同，不会重跑一次换一批人复核。"""
    key = f"{it.get('file','')}|{it.get('title','')}"
    return int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16) % AUDIT_RATE == 0


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
    if type(it.get("claimed_importance")) is not int or not 1 <= it["claimed_importance"] <= 9:
        bad.append("BAD_FIELD"); warn.append("claimed_importance 须为 1-9 整数")

    if len(it.get("summary") or "") < MIN_SUMMARY:
        bad.append("SHORT_SUMMARY")
        warn.append(f"summary 仅 {len(it.get('summary') or '')} 字")

    kn = it.get("key_numbers") or []
    statements = it.get('key_statements') or []
    if not kn and not statements and type(it.get('claimed_importance')) is int and it['claimed_importance'] >= 5:
        bad.append('NO_EVIDENCE')
        warn.append('自评 ≥5 分须提供可定位的 key_numbers 或 key_statements')
    for n in kn:
        if not (n.get("locator") or "").strip():
            bad.append("NO_LOCATOR")
            warn.append(f"数字「{n.get('what','?')}」没有 locator")
    for statement in statements:
        if not isinstance(statement, dict):
            bad.append('BAD_FIELD')
            continue
        if statement.get('kind') not in ('definition', 'mechanism', 'interface', 'standard', 'failure_case'):
            bad.append('BAD_FIELD')
            warn.append('key_statement.kind 须为 definition/mechanism/interface/standard/failure_case')
        if not all(isinstance(statement.get(k), str) and statement[k].strip() for k in ('text', 'quote')):
            bad.append('NO_EVIDENCE')
            warn.append('非数字陈述须有 text 与原文 quote')
        if not isinstance(statement.get('locator'), str) or not statement['locator'].strip():
            bad.append('NO_LOCATOR')

    stem = Path(it.get("file", "")).name.lower()
    title = (it.get("title") or "").strip().lower()
    if stem in lib_names or stem in lib_olds or (title and title in lib_olds):
        bad.append("DUP")
        warn.append(f"库内已有同名件：{it.get('file')}")

    if decl_module and decl_module not in mods:
        bad.append("OFF_TARGET")
        warn.append(f"投递声明服务 {decl_module}，但本件 modules={mods} 不含它")

    return sorted(set(bad)), warn


def tier(it, bad, conf):
    if bad:
        return "退回"
    if it.get("sensitive"):
        return "A"
    if it.get("claimed_importance", 0) >= 8:
        return "A"
    if conf:                     # 与既有事实打架的，不管几分都得人看
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
    for who, wo, it, bad, warn, conf, d in items:
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
        for statement in it.get('key_statements') or []:
            summary += f" **候选陈述**：{statement['text']}；原文：{statement['quote']}（{statement['locator']}）"
        summary += (f" 【成员投递·{who}"
                    + (f"·回应工单 {wo}" if wo else "·自主发现")
                    + "】本行由成员登记，**尚未经我们审计**，不得直接上证据链。")
        if it.get("sensitive"):
            summary = "【敏感待判】" + summary
        if audit_sampled(it):
            # 前缀留在库里，事后 grep「抽查复核」就能找回该复核哪几件；
            # 只在屏幕上打印一次的抽样等于没抽。
            summary = "【抽查复核】" + summary
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


def selftest():
    """两条规则各一个断言。**靠肉眼看输出是靠不住的**——本项目已经在
    「改了但没生效」上栽过三次（brief 补丁匹配串写错、循环变量覆盖导致
    整类工单静默消失、补标批次键约定不匹配）。规则写进代码不算数，
    能证明它触发才算数。"""
    d = SUBS / "_selftest"
    if not (d / "submission.json").exists():
        print("✗ 自检夹具缺失：", d.relative_to(ROOT)); return 1
    sub = json.loads((d / "submission.json").read_text(encoding="utf-8"))
    by_unit, (ln, lo) = load_facts(), load_library()
    got = {}
    for it in sub["items"]:
        bad, _ = check_item(it, ln, lo, sub.get("module"))
        conf = [] if bad else conflicts(it, by_unit)
        got[it["title"]] = (tier(it, bad, conf), conf)

    ok = True
    t, conf = got["某数据中心造价"]
    if t != "A" or not conf:
        ok = False; print(f"✗ 冲突未升 A 档：档位={t} 冲突={conf}")
    else:
        print(f"✓ 冲突升 A 档：{conf[0]}")
    t, _ = got["普通材料"]
    if t != "B":
        ok = False; print(f"✗ 干净的 6 分件应落 B 档，实为 {t}")
    else:
        print("✓ 干净的 6 分件落 B 档")

    scanned = [p.parent.name for p in SUBS.rglob("submission.json")
               if not any(x.startswith("_") for x in p.relative_to(SUBS).parts)]
    if any(n.startswith("_") for n in scanned):
        ok = False; print(f"✗ 默认扫描没排除下划线目录：{scanned}")
    else:
        print(f"✓ 默认扫描排除模板与夹具（本次扫到 {len(scanned)} 个真投递）")
    print("自检通过" if ok else "自检失败")
    return 0 if ok else 1


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--selftest" in sys.argv:
        return selftest()
    accept = "--accept" in sys.argv
    target = argv[0] if argv else None
    if not SUBS.exists():
        print(f"投递目录不存在：{SUBS.relative_to(ROOT)}（还没有成员投递）")
        return 0

    lib_names, lib_olds = load_library()
    by_unit = load_facts()
    # 下划线开头的目录是模板与自测夹具，不是成员投递。不排除的话 `--accept`
    # 会把 _template 里那条示例数字（1234 万只）当真数据写进批次——**编造的数进库**。
    dirs = ([Path(target)] if target else
            sorted(p.parent for p in SUBS.rglob("submission.json")
                   if not any(part.startswith("_") for part in p.relative_to(SUBS).parts)))
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
            conf = [] if bad else conflicts(it, by_unit)
            t = tier(it, bad, conf)
            buckets[t].append((who, sub.get("workorder"), it, bad, warn, conf, d))

    total = sum(len(v) for v in buckets.values())
    accepted = total - len(buckets["退回"])
    lines.append(f"共 {total} 件｜通过机检 {accepted}｜退回 {len(buckets['退回'])}"
                 f"｜**需你批 {len(buckets['A'])}**｜模型批 {len(buckets['B'])}｜自动 {len(buckets['C'])}")
    lines.append("")

    for t, label in (("A", "🔴 必须你批"), ("退回", "↩️ 退回成员"), ("B", "模型批（抽查）"), ("C", "自动入库")):
        if not buckets[t]:
            continue
        lines += [f"## {label}（{len(buckets[t])} 件）", ""]
        for who, wo, it, bad, warn, conf, d in buckets[t]:
            head = (f"- **{it.get('claimed_importance','?')}{it.get('confidence','?')}** "
                    f"{it.get('title','?')[:52]} ｜ {it.get('org','?')} {it.get('year','?')} "
                    f"｜ → {'/'.join(it.get('modules') or [])} ｜ {who}"
                    + (f" ｜ 工单 {wo}" if wo else " ｜ *自主发现*")
                    + (" ｜ 🔍 **抽中复核**" if t == "B" and audit_sampled(it) else ""))
            lines.append(head)
            if it.get("sensitive"):
                lines.append("      🔒 **标了敏感** —— 对外产出前须脱敏或聚合")
            for c in conf:
                lines.append(f"      ⚠️ **疑似与库内冲突**：{c}")
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
            if t in ('A', 'B'):
                for statement in (it.get('key_statements') or [])[:3]:
                    lines.append(f"      陈述：{statement['text']}；原文：{statement['quote']}（{statement['locator']}）")
        lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sampled = [it for _, _, it, _, _, _, _ in buckets["B"] if audit_sampled(it)]
    print(f"共 {total} 件｜通过 {accepted}｜退回 {len(buckets['退回'])}")
    print(f"  🔴 需你批 {len(buckets['A'])}｜模型批 {len(buckets['B'])}"
          f"（抽中复核 {len(sampled)}）｜自动入库 {len(buckets['C'])}")
    for who, wo, it, bad, warn, conf, d in buckets["退回"]:
        print(f"  ↩️ {it.get('title','?')[:40]}：{'；'.join(REJECT.get(b, b) for b in bad)}")
    for who, wo, it, bad, warn, conf, d in buckets["A"]:
        for c in conf:
            print(f"  ⚠️ 冲突升 A：{it.get('title','?')[:32]} — {c}")
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
