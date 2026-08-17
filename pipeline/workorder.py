#!/usr/bin/env python3
"""工单生成器：工单 = 模块声明 − 仓库现状。

设计前提（2026-08-16 用户拍板的声明式架构）：
  模块是**声明**不是代码。core 里不允许出现 if M07 这类分支；模块声明放在
  framework/modules.json（要回答什么问题、由哪些信源跑口供养），现状散在
  indicators.json / LIBRARY_SCORES.csv / research/Mxx.md / sources.json 里。
  **工单不由任何人手写，它是两者的差。**

六类缺口（按优先级）：
  P1 声明缺失   模块没声明指标或没声明信源跑口——先补声明，否则无从算差
  P1 弹药饥饿   ≥7 分材料为 0 或弹药过薄——只能靠新采集救
  P2 指标留白   indicators.json 里 value 为空——"留白即纪律"，但留白要有人去填
  P2 信源未开口 声明了跑口但库内一份都没有——渠道还没打通
  P2 口径未定义 监测指标在 metrics.json 里没有对应定义——没有口径维度的数无法判定可比性
  P2 事实层空白 指标定义了口径但一条事实都没有——声明了却没去取数
  P2 待审计     成员投递的行堆积——未审计的成员登记不能当已读用
  P3 消化积压   半自动行堆积——缺的不是材料是精读，派消化不派采集
  P3 鲜度逾期   Finding 处于 needs-review/stale——派核验

用法：python3 pipeline/workorder.py            # → reports/workorders.md + stdout 摘要
      python3 pipeline/workorder.py M11        # 只看某模块
零依赖。
"""
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "workorders.md"
OUT_JSON = ROOT / "reports" / "workorders.json"   # 给 team.html 等机器消费方

AMMO_THIN = 60          # 弹药（非目录级）低于此值视为偏瘦
DIGEST_BACKLOG = 40     # 半自动 ≥6 分未消化超过此值视为消化积压

# 指标留白的三种取数路径——决定派给谁、怎么派。
# 判据取自 indicators.json 的 source 字段（声明里已经写了从哪取，只是没人按它路由）。
SOURCE_CLASS = [
    (re.compile(r"projects\s*表|状态历史|表聚合|prices\.|benchmarks"), "内部聚合",
     "**不用读任何文件**——这个数从我们自己的实体表算得出来。缺的是聚合代码，不是材料。"),
    (re.compile(r"财报|10-K|电话会|公司披露|白皮书|规范|机构报告|公告"), "库内抽取",
     "库内很可能已经有原文——先在打分表里检索候选件，读原文抽数，不要先去外面找。"),
    (re.compile(r"渠道|调研|市场报价|租赁平台|二手|REIT|债券|M&A|排队数据|推算"), "外部采集",
     "库内多半没有——这是要新开渠道的，属于成员的采集工单。"),
]

# 内部聚合类指标依赖的实体表字段——工单要报出分母，否则算出来的数看着权威实则悬空。
FIELD_DEPS = {
    "benchmark_spread": ("projects", "capacity_it_mw"),
    "pipeline_conversion_rate": ("projects", "status_history"),
    "top10_pipeline_share": ("projects", "capacity_it_mw"),
    "region_pipeline_share": ("projects", "capacity_it_mw"),
    "construction_duration_months": ("projects", "status_history"),
}


def classify_source(src):
    for rx, cls, how in SOURCE_CLASS:
        if rx.search(src or ""):
            return cls, how
    return "未分类", "声明里的 source 写得太含糊，无法路由——先把 source 写清楚。"


def field_coverage(table, field):
    """返回 (有该字段的条数, 总条数)。"""
    recs = json.loads((ROOT / "data" / f"{table}.json").read_text(encoding="utf-8"))["records"]
    ok = sum(1 for r in recs if r.get(field) not in (None, "", [], {}))
    return ok, len(recs)


ACCEPT = ("每份填一行登记（{importance}{confidence}_{年份}_{主题}_{机构}），"
          "summary ≥200 字且**每个数字必须能在原文逐字查到**，查不到标 `[未核]`；"
          "库内已有的不计分（见附表查重）。")


def load_state():
    rows = list(csv.DictReader((ROOT / "docs" / "LIBRARY_SCORES.csv").open(encoding="utf-8")))
    sources = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))["records"]
    inds = json.loads((ROOT / "framework" / "indicators.json").read_text(encoding="utf-8"))["indicators"]
    mods = json.loads((ROOT / "framework" / "modules.json").read_text(encoding="utf-8"))["modules"]
    mets = json.loads((ROOT / "framework" / "metrics.json").read_text(encoding="utf-8"))["metrics"]
    facts = json.loads((ROOT / "data" / "facts.json").read_text(encoding="utf-8"))["records"]
    return rows, sources, inds, mods, mets, facts


def module_keys(cell):
    return [m.strip() for m in re.split(r"[/、,，]", cell or "") if re.fullmatch(r"M\d\d", m.strip())]


def findings_state(mid):
    """返回 (总数, needs-review 数, stale 数)。"""
    p = ROOT / "research" / f"{mid}.md"
    if not p.exists():
        return 0, 0, 0
    t = p.read_text(encoding="utf-8")
    total = len(re.findall(r"^## " + mid + r"-F", t, re.M))
    return total, len(re.findall(r"状态\*\*：needs-review", t)), len(re.findall(r"状态\*\*：stale", t))


def org_seen(beat_org, known):
    """跑口机构是否已在库内出现过（跑口串可能形如 'JLL / CBRE / Cushman'）。"""
    for tok in re.split(r"[/／]", beat_org):
        tok = tok.strip()
        if len(tok) >= 2 and any(tok.lower() in k for k in known):
            return True
    return False


def build(only=None):
    rows, sources, inds, mods, mets, facts = load_state()
    met_by_mod = defaultdict(list)
    for m in mets:
        met_by_mod[m.get("module")].append(m)
    fact_cnt = Counter(f["metric_id"] for f in facts)
    # 指标是否已有口径定义：先按 id 直连，再退回按名称匹配（两套声明尚未打通）
    met_ids = {m["metric_id"] for m in mets}
    met_names = {m["name"] for m in mets}
    digested = {r.get("local_file") for r in sources if r.get("local_file")}
    known_orgs = {(r.get("org") or "").lower() for r in rows} | {(s.get("publisher") or "").lower() for s in sources}
    known_orgs = {o for o in known_orgs if o}

    ammo, high, backlog, unaudited = Counter(), Counter(), Counter(), Counter()
    for r in rows:
        if r.get("depth") == "目录级":
            continue
        for m in module_keys(r["module"]):
            ammo[m] += 1
            if int(r["importance"]) >= 7:
                high[m] += 1
            if r.get("depth") == "半自动" and int(r["importance"]) >= 6 and r["new_path"] not in digested:
                backlog[m] += 1
            if r.get("depth") == "成员精读":
                unaudited[m] += 1

    ind_by_mod = defaultdict(list)
    for i in inds:
        ind_by_mod[i.get("module")].append(i)

    orders = []
    for m in mods:
        mid, name = m["id"], m["name"]
        if only and mid != only:
            continue
        beats = m.get("beats", [])
        fc, nr, stale = findings_state(mid)
        blank = [i for i in ind_by_mod.get(mid, []) if i.get("value") is None]

        def add(pri, kind, gap, action, key):
            """key 是**内容键**，决定工单号——必须与计数无关，否则弹药数一变工单号就变，
            已 assign 出去的活会错位到别的任务上。"""
            h = hashlib.sha1(f"{mid}|{key}".encode("utf-8")).hexdigest()[:4]
            orders.append(dict(pri=pri, mid=mid, name=name, kind=kind, gap=gap,
                               action=action, wid=f"{mid}-{h}", key=key))

        # P1 声明缺失
        if not beats:
            add("P1", "声明缺失",
                f"{mid} 没有任何信源跑口声明——这就是它长不出弹药的原因（现有弹药 {ammo[mid]} 份）",
                "**这条是给所有者的，不是给成员的**：先在 framework/modules.json 给本模块补 beats，"
                "否则任何采集工单都无从下手（不知道该去哪找）。", key="声明缺失:beats")
        if not ind_by_mod.get(mid):
            add("P1", "声明缺失", f"{mid} 在 indicators.json 里没有任何指标",
                "**给所有者**：本模块无可监测量，看板上会是一片空白。先声明 2-3 个指标。", key="声明缺失:indicators")

        # P1 弹药饥饿
        if beats and high[mid] == 0:
            src = "、".join(b["org"] for b in beats[:3])
            add("P1", "弹药饥饿",
                f"{mid} 弹药 {ammo[mid]} 份但 **≥7 分为 0**——有量无质，缺一手口径",
                f"去 {src} 找**一手**材料（实测/官方规范/机构原始数据表），"
                f"不要再收转述汇编。{ACCEPT}", key="弹药")
        elif beats and ammo[mid] < AMMO_THIN:
            src = "、".join(b["org"] for b in beats[:3])
            add("P2", "弹药偏瘦", f"{mid} 弹药仅 {ammo[mid]} 份（阈值 {AMMO_THIN}），但 ≥7 分有 {high[mid]} 份——有质缺量",
                f"缺口猎人任务：{src}。{ACCEPT}", key="弹药")

        # P2 指标留白——按声明的取数路径路由，三类派法完全不同
        for i in blank:
            cls, how = classify_source(i.get("source"))
            extra = ""
            if i["id"] in FIELD_DEPS:
                tbl, fld = FIELD_DEPS[i["id"]]
                ok, tot = field_coverage(tbl, fld)
                pct = ok * 100 // tot if tot else 0
                extra = (f" **但先看分母**：算它要 `{tbl}.{fld}`，当前只有 **{ok}/{tot}（{pct}%）** 条记录有这个字段。"
                         + ("覆盖太薄，先补字段再算——现在算出来的数看着权威，实则悬空。"
                            if pct < 50 else "覆盖够，可以算。"))
            add("P2", f"指标留白·{cls}",
                f"`{i['id']}` {i['name']}（单位 {i.get('unit') or '—'}，频率 {i.get('freq') or '—'}）",
                f"{how}{extra} 声明的来源是「{i.get('source') or '未声明'}」。"
                "拿不到就如实回报拿不到——**留白是纪律，编一个数是事故**。", key=f"指标:{i['id']}")

        # P2 口径未定义——监测指标没有 metrics.json 里的口径维度声明
        undef = [i for i in ind_by_mod.get(mid, [])
                 if i["id"] not in met_ids and i["name"] not in met_names]
        if undef:
            add("P2", "口径未定义",
                f"{mid} 有 **{len(undef)}/{len(ind_by_mod.get(mid, []))} 个监测指标**在 metrics.json 里没有口径定义",
                "**给所有者**：没有口径维度的指标，它的数无法判定可比性——两个不可比的值并列时"
                "没有任何机制会拦。逐个补 `caliber_dims` 到 framework/metrics.json，"
                f"涉及：{'、'.join(i['id'] for i in undef[:6])}"
                + ("…" if len(undef) > 6 else ""),
                key="口径未定义")

        # P2 事实层空白——口径定义了却没去取数
        # 变量名不能用 m——外层 `for m in mods` 还要用它取 questions；
        # 这里曾因覆盖循环变量，导致 34 条「声明问题开放」工单静默消失
        empty = [x for x in met_by_mod.get(mid, []) if fact_cnt[x["metric_id"]] == 0]
        for met in empty:
            add("P2", "事实层空白",
                f"指标 `{met['metric_id']}`（{met['name']}）已声明口径维度，但事实层一条数都没有",
                "去取数入 `data/facts.json`。口径维度已经定好，照着填即可；"
                "拿不到就如实回报——**留白是纪律**。",
                key=f"事实空白:{met['metric_id']}")

        # P2 信源未开口
        for b in beats:
            if not org_seen(b["org"], known_orgs):
                add("P2", "信源未开口",
                    f"声明了跑口「{b['org']}」（{b['channel']}）但库内一份都没有"
                    + (f"——{b['note']}" if b.get("note") else ""),
                    f"打通该渠道：先取一份最新的公开件验证格式与价值，再决定是否长期跟。{ACCEPT}", key=f"信源:{b['org']}")

        # P2 成员投递待审计
        if unaudited[mid]:
            add("P2", "待审计",
                f"{mid} 有 **{unaudited[mid]} 行成员投递**尚未审计",
                "成员读过并按契约登记了，但我们没核过。**未审计的登记不能当已读用**——"
                "抽查其 key_number 能否回原文对上，通过则提级为「精读」，不通过退回并记入该成员命中率。",
                key="待审计")

        # P3 消化积压
        if backlog[mid] >= DIGEST_BACKLOG:
            add("P3", "消化积压",
                f"{mid} 有 **{backlog[mid]} 份半自动 ≥6 分**未消化——缺的不是材料是精读",
                "**派消化不派采集**：回原文复核这些行，把够格的提级为精读并出 Finding。"
                "半自动行不复核不得上证据链。", key="消化积压")

        # P3 鲜度逾期
        if nr or stale:
            add("P3", "鲜度逾期", f"{mid} 有 {nr} 条 needs-review、{stale} 条 stale",
                "跑 `python3 pipeline/verify.py` 取核验队列，按触发器找新证据复核。", key="鲜度")

        # 模块自身声明的开放问题（answered_by 为空 = 声明上仍开放）
        for q in m.get("questions", []):
            if isinstance(q, dict):
                if q.get("answered_by"):
                    continue          # 已链到 Finding，声明上已闭合
                q = q["q"]
            add("P2", "声明问题开放", q,
                f"这是 {mid} 在 modules.json 里声明为**开放**的问题（answered_by 为空）。"
                f"答掉之后把 Finding 号回填进声明，工单自动消失。{ACCEPT}", key=f"问题:{q}")

    return orders, ammo, high, backlog


def render(orders, ammo, high, backlog):
    by_mod = defaultdict(list)
    for o in orders:
        by_mod[o["mid"]].append(o)
    pri_rank = {"P1": 0, "P2": 1, "P3": 2}

    lines = [
        "# 工单队列 — 每个模块下一步该做什么",
        "",
        f"生成时间：{date.today().isoformat()} ｜ 共 {len(orders)} 张工单",
        "",
        "> **本文件是生成物，不要手写。** 工单 = `framework/modules.json` 的模块声明 −"
        " 仓库现状（indicators / LIBRARY_SCORES / research / sources）。",
        "> 工单号按**内容**哈希而非位置编号——队列重算后同一件事的号不变，"
        "所以派出去的活不会错位到别的任务上。",
        "> 改工单的正确做法是改声明或改现状，然后重跑 `python3 pipeline/workorder.py`。",
        "",
        "优先级：**P1** 声明缺失与弹药饥饿（不补就长不出东西）｜"
        "**P2** 指标留白、信源未开口、声明问题未答（正常采集量）｜"
        "**P3** 消化积压与鲜度逾期（不是采集，是加工）",
        "",
        "## 全局概览",
        "",
        "| 模块 | Finding | 弹药 | ≥7分 | 消化积压 | 工单 | 最高优先级 |",
        "|---|---:|---:|---:|---:|---:|:--|",
    ]
    for mid in sorted(by_mod):
        os_ = by_mod[mid]
        fc, _, _ = findings_state(mid)
        top = min(o["pri"] for o in os_) if os_ else "—"
        lines.append(f"| {mid} {os_[0]['name']} | {fc} | {ammo[mid]} | {high[mid]} | "
                     f"{backlog[mid]} | {len(os_)} | {top} |")
    lines.append("")

    for mid in sorted(by_mod):
        os_ = sorted(by_mod[mid], key=lambda o: pri_rank[o["pri"]])
        lines += [f"## {mid} {os_[0]['name']}", ""]
        for o in os_:
            lines += [f"### {o['pri']} · {o['kind']} · `{o['wid']}`", "",
                      f"**缺口**：{o['gap']}", "",
                      f"**动作**：{o['action']}", ""]
    return "\n".join(lines) + "\n"


def main():
    only = sys.argv[1] if len(sys.argv) > 1 and re.fullmatch(r"M\d\d", sys.argv[1]) else None
    orders, ammo, high, backlog = build(only)
    OUT.write_text(render(orders, ammo, high, backlog), encoding="utf-8")

    stats = {m: {"ammo": ammo[m], "high": high[m], "backlog": backlog[m],
                 "findings": findings_state(m)[0]}
             for m in {o["mid"] for o in orders}}
    OUT_JSON.write_text(json.dumps(
        {"generated": date.today().isoformat(), "orders": orders, "module_stats": stats},
        ensure_ascii=False, indent=1), encoding="utf-8")

    c = Counter(o["pri"] for o in orders)
    print(f"工单 {len(orders)} 张｜P1 {c['P1']} P2 {c['P2']} P3 {c['P3']}")
    # 按类型打印分布：整类工单静默消失过一次（循环变量被覆盖，34 条开放问题全丢），
    # 只看总数看不出来——分布摆出来，某类掉到 0 就一眼可见
    print("  类型分布：" + "｜".join(f"{k} {v}" for k, v in
                                  Counter(o["kind"] for o in orders).most_common()))
    for o in [x for x in orders if x["pri"] == "P1"]:
        print(f"  P1 {o['mid']} {o['kind']}：{o['gap'][:60]}")
    print(f"完整队列已写入 {OUT.relative_to(ROOT)} 与 {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
