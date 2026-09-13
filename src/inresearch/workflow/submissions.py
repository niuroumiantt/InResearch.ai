"""成员候选接收：验证证据登记、匹配当前工单、按 C3 分流。

规则唯一来源：framework/01_data_standards.md §4；结构见 submission.schema.json。
--accept 仅导出 B 待审核/C 存档候选 CSV，不执行模型审核或正式采用。
同名只提示；原件字节 SHA 身份由材料接收流程验证，本入口不推测内容相同。
数字相差倍数是疑似冲突提示，不能代替口径审阅或自动覆盖事实。

用法：python3 manage.py submissions [投递目录] [--accept | --selftest]
"""

import csv
import hashlib
import io
import json
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path

from inresearch.knowledge.registry import current_tasks
from inresearch.paths import project_root
from inresearch.storage.files import atomic_write, locked

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
    if not isinstance(it, dict):
        return ['BAD_FIELD'], ['材料登记须为对象']
    text_fields = ('file', 'title', 'org', 'confidence', 'summary')
    if (not all(isinstance(it.get(k), str) and it[k].strip() for k in text_fields)
            or type(it.get('year')) is not int or not 1990 <= it['year'] <= 2100
            or not isinstance(it.get('modules'), list) or not it['modules']
            or not all(isinstance(m, str) for m in it['modules'])
            or any(k in it and not isinstance(it[k], list)
                   for k in ('key_numbers', 'key_statements', 'replaces_record_ids'))
            or ('sensitive' in it and type(it['sensitive']) is not bool)
            or not all(isinstance(r, str) and r.strip() for r in it.get('replaces_record_ids', []))):
        return ['BAD_FIELD'], ['必填字段或证据集合类型非法，见 submission.schema.json']

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
        if not isinstance(n, dict):
            bad.append('BAD_FIELD')
            continue
        value = n.get('value')
        if (not all(isinstance(n.get(k), str) and n[k].strip() for k in ('what', 'unit'))
                or not (isinstance(value, str) and value.strip()
                        or type(value) in (int, float) and math.isfinite(value))):
            bad.append('BAD_FIELD')
        if not isinstance(n.get('locator'), str) or not n['locator'].strip():
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
        warn.append(f"库内有同名件，待原件 SHA 核对，不能按名称拒收：{it.get('file')}")

    if decl_module and decl_module not in mods:
        bad.append("OFF_TARGET")
        warn.append(f"投递声明服务 {decl_module}，但本件 modules={mods} 不含它")

    return sorted(set(bad)), warn


def matched_workorder(submission, item, tasks):
    """A declared ID alone cannot qualify a candidate for B review."""
    wid = submission.get('workorder')
    if not wid:
        return False
    task = tasks.get(wid, {})
    module = task.get('module_id') or task.get('mid')
    assignment = task.get('assignment') or {}
    return bool(module and module == submission.get('module') and module in item.get('modules', [])
                and assignment.get('status') not in ('已合并', '已放弃'))


def tier(it, bad, conf, matched=False):
    if bad:
        return "退回"
    if it.get("sensitive") or it.get('replaces_record_ids') or conf or it['claimed_importance'] >= 8:
        return "A"
    if it['claimed_importance'] >= 5:
        return "B" if matched else "待匹配"
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
            summary += f" **候选数字**：{nums}"
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
    """机检通过率，不冒充实际研究命中率。"""
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
    if t != "待匹配":
        ok = False; print(f"✗ 无工单的 6 分件应待匹配，实为 {t}")
    else:
        print("✓ 无工单的 6 分件保留候选，等待匹配")

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

    tasks = {task["wid"]: task for task in current_tasks(ROOT)}
    buckets = {"A": [], "B": [], "C": [], "待匹配": [], "退回": []}
    lines = ["# 投递审阅 — 机检结果与分流", "",
             ("> 三档：**A 必须你批**（≥8分／敏感／与现有结论冲突）｜"
             "**B 待模型审核**（5-7分命中工单，确定性抽样复核）｜**C 候选存档**（≤4 分）。未匹配工单的中分材料保持待匹配。"),
             "> 退回项已带理由码，直接回流给成员即可——**退回不给理由，下次照犯**。", ""]

    read_errors = 0
    for d in dirs:
        try:
            sub = json.loads((d / "submission.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            read_errors += 1
            print(f"✗ {d}：submission.json 读取失败 {e}")
            continue
        if (not isinstance(sub, dict) or not isinstance(sub.get('items'), list)
                or not sub['items'] or not isinstance(sub.get('contributor'), str)
                or not sub['contributor'].strip() or not isinstance(sub.get('module'), str)
                or sub['module'] not in VALID_MODULES
                or not isinstance(sub.get('submitted'), str)
                or ('workorder' in sub and not isinstance(sub['workorder'], str))):
            read_errors += 1
            print(f"✗ {d}：投递单必填字段或类型非法")
            continue
        try:
            date.fromisoformat(sub['submitted'])
        except ValueError:
            read_errors += 1
            print(f"✗ {d}：submitted 日期非法")
            continue
        who = sub.get("contributor", "?")
        decl = sub.get("module")
        for it in sub.get("items", []):
            bad, warn = check_item(it, lib_names, lib_olds, decl)
            matched = False if bad else matched_workorder(sub, it, tasks)
            if not bad and sub.get('workorder') and not matched:
                bad.append('OFF_TARGET')
                warn.append('工单已退出当前集合、已结束，或其模块与材料不匹配')
            conf = [] if bad else conflicts(it, by_unit)
            if not isinstance(it, dict):
                it = {}
            t = tier(it, bad, conf, matched)
            buckets[t].append((who, sub.get("workorder"), it, bad, warn, conf, d))

    total = sum(len(v) for v in buckets.values())
    accepted = total - len(buckets["退回"])
    lines.append(f"共 {total} 件｜通过机检 {accepted}｜退回 {len(buckets['退回'])}"
                 f"｜**需你批 {len(buckets['A'])}**｜待模型审核 {len(buckets['B'])}｜候选存档 {len(buckets['C'])}｜待匹配 {len(buckets['待匹配'])}")
    lines.append("")

    for t, label in (("A", "🔴 必须你批"), ("退回", "↩️ 退回成员"), ("B", "待模型审核（抽查）"), ("C", "候选存档"), ("待匹配", "候选待匹配工单")):
        if not buckets[t]:
            continue
        lines += [f"## {label}（{len(buckets[t])} 件）", ""]
        for who, wo, it, bad, warn, conf, d in buckets[t]:
            head = (f"- **{it.get('claimed_importance','?')}{it.get('confidence','?')}** "
                    f"{str(it.get('title','?'))[:52]} ｜ {it.get('org','?')} {it.get('year','?')} "
                    f"｜ → {it.get('modules') or []!s} ｜ {who}"
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
    print(f"  🔴 需你批 {len(buckets['A'])}｜待模型审核 {len(buckets['B'])}"
          f"（抽中复核 {len(sampled)}）｜候选存档 {len(buckets['C'])}｜待匹配 {len(buckets['待匹配'])}")
    for who, wo, it, bad, warn, conf, d in buckets["退回"]:
        print(f"  ↩️ {str(it.get('title','?'))[:40]}：{'；'.join(REJECT.get(b, b) for b in bad)}")
    for who, wo, it, bad, warn, conf, d in buckets["A"]:
        for c in conf:
            print(f"  ⚠️ 冲突升 A：{it.get('title','?')[:32]} — {c}")
    rates = hit_rates(buckets)
    if rates:
        print("  机检通过率（非研究命中率）：" + "｜".join(
            f"{w} {v['过']}/{v['总']}（{v['过']*100//v['总']}%）" for w, v in sorted(rates.items())))

    if accept:
        promo = buckets["B"] + buckets["C"]
        if not promo:
            print("没有可导出的 B/C 候选。")
        else:
            today = datetime.now().astimezone().date().isoformat()
            rows = to_batch_rows(promo, today)
            BATCHES.mkdir(parents=True, exist_ok=True)
            # Payload identity is only for idempotent candidate export, not material identity.
            stream = io.StringIO(newline='')
            writer = csv.DictWriter(stream, fieldnames=BATCH_FIELDS)
            writer.writeheader(); writer.writerows(rows)
            data = stream.getvalue().encode('utf-8')
            identity = [{k: v for k, v in row.items() if k != 'scored'} for row in rows]
            batch_id = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            f = BATCHES / f"batch_sub_{batch_id}.csv"
            with locked(f):
                if not f.exists():
                    atomic_write(f, data)
            print(f"已写出批次 {f.relative_to(ROOT)}（{len(rows)} 行，depth=成员精读）")
            print("  → 仅生成候选批次；B 尚需模型审核，C 仅存档，均不直接采用。")
    elif buckets["B"] or buckets["C"]:
        print(f"  提示：{len(buckets['B']) + len(buckets['C'])} 件 B/C 候选可导出，加 --accept 生成批次。")

    print(f"完整审阅卡已写入 {OUT.relative_to(ROOT)}")
    return 1 if read_errors or buckets["退回"] else 0


if __name__ == "__main__":
    sys.exit(main())
