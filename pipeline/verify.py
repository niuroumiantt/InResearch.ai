#!/usr/bin/env python3
"""核验队列生成器：扫描六张表，按优先级列出"今天该核验什么"。

这是核验工作的固定入口（与 validate.py 分工：validate 管"数据合不合规"，
verify 管"数据该不该重新查证"）。零依赖。collect.py 复用本模块的 build_queue()。

用法：
    python3 pipeline/verify.py              # 生成队列 → reports/verify_queue.md + stdout 摘要
    python3 pipeline/verify.py --all        # 包含 P3（未到期但临近的记录）

优先级规则：
  P1  争议记录（disputed）；核验超期的记录（项目 L6-L9 超90天 / L1-L5 超180天 / 价格超30天）
  P2  仅有 media/estimate 级来源的记录；单一来源且级别低于 research 的记录
  P3  距离超期不足 20% 余量的记录（--all 时显示）

核验动作（对每条队列项）：
  1. 打开记录列出的 source_url，核对关键数字/状态是否仍然成立
  2. 有变化 → 更新字段 + status_history + 换/增来源；无变化 → 仅更新 verified_date
  3. 保存后运行 python3 pipeline/validate.py 把关
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "reports" / "verify_queue.md"

FRESH = {"project_late": 90, "project_early": 180, "default": 365}
LOW_GRADES = {"media", "estimate"}

# 价格序列保鲜阈值（天）：按更新频率区分。记录可用 frequency 字段显式声明，
# 否则按 series_id 推断。年度序列给足财报披露滞后（一年 + 约 3 个月）。
PRICE_FRESH = {"annual": 455, "quarterly": 150, "monthly": 45, "spot": 30, "default": 365}


def price_series_freq(r):
    """推断价格序列的更新频率：显式 frequency 字段优先，否则按 series_id 命名推断。"""
    f = r.get("frequency")
    if f in PRICE_FRESH:
        return f
    sid = r.get("series_id", "")
    if "annual" in sid or sid.startswith("delloro-capex"):
        return "annual"
    if sid.startswith(("dc-rent", "vacancy-rate")):
        return "quarterly"
    if sid.startswith(("gpu-hourly", "token-price")):
        return "quarterly"  # 牌价/现货：季度扫一遍已足够灵敏，日常变化走信号管线
    if "lead-time" in sid or sid.startswith("construction-cost"):
        return "quarterly"
    return "default"


def price_series_limit(r):
    return PRICE_FRESH[price_series_freq(r)]


def days_since(datestr):
    try:
        return (date.today() - datetime.strptime(str(datestr)[:10], "%Y-%m-%d").date()).days
    except (ValueError, TypeError):
        return None


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))["records"]


def build_queue(show_all=False):
    """返回按优先级排序的核验队列：[{p, table, id, reason, urls, action}]"""
    queue = []

    def add(prio, table, rid, reason, urls, action):
        queue.append({"p": prio, "table": table, "id": rid, "reason": reason,
                      "urls": [u for u in urls if u], "action": action})

    # 项目库
    for r in load("projects"):
        rid = r["site_id"]
        urls = [s.get("url") for s in r.get("sources", [])]
        limit = FRESH["project_late"] if r.get("status") in {"L6", "L7", "L8", "L9"} else FRESH["project_early"]
        d = days_since(r.get("verified_date"))
        if r.get("disputed"):
            add(1, "projects", rid, "标记为争议（disputed）", urls, "查证冲突来源，裁决后去掉 disputed 或保留并注明")
        if d is None or d > limit:
            add(1, "projects", rid, f"核验超期 {d} 天（阈值 {limit}）", urls, "核对状态与容量，更新 verified_date")
        elif show_all and d > limit * 0.8:
            add(3, "projects", rid, f"临近超期（{d}/{limit} 天）", urls, "顺手核验")
        grades = {s.get("grade") for s in r.get("sources", [])}
        if grades and grades <= LOW_GRADES:
            add(2, "projects", rid, f"仅有低级别来源（{'/'.join(sorted(grades))}）", urls, "补一手来源（公司披露/监管文件）")
        elif len(r.get("sources", [])) == 1 and "regulatory" not in grades and "company" not in grades:
            add(2, "projects", rid, "单一来源且非一手", urls, "交叉验证，补第二来源")

    # 价格库：保鲜度按"序列"判断——历史点是冻结存档，只看每条序列的最新点是否该续
    latest = {}
    for r in load("prices"):
        s = r["series_id"]
        if s not in latest or str(r.get("as_of")) > str(latest[s].get("as_of")):
            latest[s] = r
    for s, r in sorted(latest.items()):
        if r.get("category") == "benchmark":
            continue  # 机构基准是一次性锚点，随机构新版报告更新，不按日历催
        rid = f"{s}@{r['as_of']}"
        limit = price_series_limit(r)
        d = days_since(r.get("as_of"))
        if d is not None and d > limit:
            add(1, "prices", rid, f"序列最新点已 {d} 天（阈值 {limit}，按{price_series_freq(r)}频率）", [r.get("source_url")], "抓取/查询最新值，新增一条 as_of 记录")
        if r.get("grade") == "estimate":
            add(2, "prices", rid, "序列最新点为 estimate 级（带假设推算）", [r.get("source_url")], "寻找可替代的一手/研究级来源")

    # 知识层：研究文档的 Finding 状态
    import re
    for rp in sorted((ROOT / "research").glob("M*.md")) if (ROOT / "research").exists() else []:
        text = rp.read_text(encoding="utf-8")
        for m in re.finditer(r"^##\s+(M\d+-F\d+)\s+(.*?)\s*(\{[^}]*\})?\s*\n-\s+\*\*状态\*\*：(\S+?)\s*｜\s*\*\*修订\*\*：(\S+)", text, re.M):
            fid, ftitle, status, revised = m.group(1), m.group(2)[:30], m.group(4), m.group(5)
            d = days_since(revised)
            if status == "needs-review":
                add(1, "research", fid, f"标记 needs-review（{ftitle}…）", [], f"复核证据后改回 current 或修订结论（{rp.name}）")
            elif status == "stale" or (d is not None and d > 365):
                add(1, "research", fid, f"研究结论 {d} 天未复核（{ftitle}…）", [], f"复核并更新修订日期（{rp.name}）")
            elif show_all and d is not None and d > 300:
                add(3, "research", fid, f"临近复核期（{d}/365 天）", [], f"顺手复核（{rp.name}）")

    # 合同库 / 政策库
    for r in load("contracts"):
        d = days_since(r.get("verified_date"))
        if r.get("grade") in LOW_GRADES:
            add(2, "contracts", r["contract_id"], f"{r['grade']} 级来源", [r.get("source_url")], "用财报 RPO/监管文件交叉验证金额与期限")
        if d is not None and d > FRESH["default"]:
            add(1, "contracts", r["contract_id"], f"核验超期 {d} 天", [r.get("source_url")], "确认合同执行状态")
    for r in load("policies"):
        d = days_since(r.get("verified_date"))
        if d is not None and d > FRESH["default"]:
            add(1, "policies", r["policy_id"], f"核验超期 {d} 天", [r.get("source_url")], "确认政策现行版本")

    queue.sort(key=lambda q: (q["p"], q["table"], q["id"]))
    return queue


def write_markdown(queue, show_all=False):
    counts = {p: sum(1 for q in queue if q["p"] == p) for p in (1, 2, 3)}
    lines = [
        "# 核验队列",
        "",
        f"生成时间：{date.today().isoformat()} ｜ P1（必须处理）{counts[1]} 条 ｜ P2（补强来源）{counts[2]} 条"
        + (f" ｜ P3（临近超期）{counts[3]} 条" if show_all else ""),
        "",
        "流程：打开来源链接核对 → 有变化改数据+来源，无变化只改 verified_date → `python3 pipeline/validate.py`",
        "",
    ]
    for p in (1, 2, 3):
        items = [q for q in queue if q["p"] == p]
        if not items or (p == 3 and not show_all):
            continue
        lines.append(f"## P{p}")
        lines.append("")
        for q in items:
            lines.append(f"- [ ] **{q['table']} / {q['id']}** — {q['reason']}")
            lines.append(f"      动作：{q['action']}")
            for u in q["urls"][:3]:
                lines.append(f"      来源：{u}")
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def main():
    show_all = "--all" in sys.argv
    queue = build_queue(show_all)
    counts = write_markdown(queue, show_all)
    print(f"P1 必须处理 {counts[1]} 条 ｜ P2 补强来源 {counts[2]} 条" + (f" ｜ P3 {counts[3]} 条" if show_all else ""))
    for q in [q for q in queue if q["p"] == 1][:10]:
        print(f"  P1  {q['table']:10s} {q['id']:28s} {q['reason']}")
    print(f"完整队列已写入 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
