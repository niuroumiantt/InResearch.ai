#!/usr/bin/env python3
"""Historical cache briefing only. Network acquisition runs on Spark via acquisition.py.
Current policy: framework/06_acquisition.md. Cached data is not live collection status.
"""
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import verify  # noqa: E402


def atomic_write(path: Path, text: str):
    """先写同目录临时文件再 os.replace 原子换名——写到一半被 kill 也不会截断原文。
    这对 research/Mxx.md 尤其重要：那是唯一被代码自动改写的知识层原文。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)

SEC_RECENT_DAYS = 7
SEC_WATCH_FORMS = {"10-Q", "10-K", "8-K", "S-1", "424B5", "20-F", "6-K"}


def run_step(name, args, timeout=180):
    print(f"── {name}")
    try:
        r = subprocess.run([sys.executable] + args, cwd=ROOT, timeout=timeout,
                           capture_output=True, text=True)
        tail = (r.stdout or r.stderr).strip().splitlines()
        for line in tail[-3:]:
            print(f"   {line}")
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        print("   超时，跳过（用已有数据继续）")
        return False


def latest_news_signals():
    d = ROOT / "data" / "raw" / "news_signals"
    files = sorted(d.glob("*_signals.json"), reverse=True) if d.exists() else []
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8")), files[0].name[:10]


def recent_sec_filings():
    """从 data/raw/sec/ 存档解析近 N 天的关注文件。"""
    cutoff = (date.today() - timedelta(days=SEC_RECENT_DAYS)).isoformat()
    out = []
    d = ROOT / "data" / "raw" / "sec"
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        cik = data.get("cik")
        recent = data.get("filings", {}).get("recent", {})
        forms, dates = recent.get("form", []), recent.get("filingDate", [])
        accs, docs = recent.get("accessionNumber", []), recent.get("primaryDocument", [])
        for i in range(len(forms)):
            if forms[i] in SEC_WATCH_FORMS and dates[i] >= cutoff:
                out.append({
                    "company": f.stem, "date": dates[i], "form": forms[i],
                    "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accs[i].replace('-', '')}/{docs[i]}",
                })
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def mark_findings_needs_review(sec_filings):
    """事件驱动核验联动：近 7 天有 10-Q/10-K/8-K 的实体，其触发器命中的 current Finding
    自动标为 needs-review（进入 verify.py 的 P1 队列）。人工复核后改回 current。"""
    import re
    # 各实体最近一次硬信号（10-Q/10-K/8-K）的文件日期
    hard = {}
    for f in sec_filings:
        if f["form"] in {"10-Q", "10-K", "8-K"}:
            hard[f["company"]] = max(hard.get(f["company"], ""), f["date"])
    marked = []
    if not hard:
        return marked
    for rp in sorted((ROOT / "research").glob("M*.md")):
        text = rp.read_text(encoding="utf-8")
        out, changed = [], False
        pending = None  # (fid, title) 等待其状态行
        for line in text.split("\n"):
            h = re.match(r"^##\s+(M\d+-F\d+)\s+(.*?)\s*(\{[^}]*\})?\s*$", line)
            if h:
                pending = (h.group(1), h.group(2))
            elif pending and re.match(r"^-\s+\*\*状态\*\*：current\s*｜", line):
                rev = re.search(r"\*\*修订\*\*：(\S+)", line)
                revised = rev.group(1) if rev else ""
                # 只对"信号晚于最后修订"的 Finding 标记——复核过的不重复打扰
                hits = [c for c, d in hard.items() if f"entity:{c}" in line and d > revised]
                if hits:
                    line = line.replace("**状态**：current", "**状态**：needs-review", 1)
                    marked.append({"finding": pending[0], "title": pending[1][:40],
                                   "entities": hits, "file": rp.name})
                    changed = True
                pending = None
            out.append(line)
        if changed:
            atomic_write(rp, "\n".join(out))
    return marked


def research_stats():
    """知识层统计：各模块 Finding 数与状态分布。"""
    import re
    stats = {}
    d = ROOT / "research"
    for f in sorted(d.glob("M*.md")) if d.exists() else []:
        text = f.read_text(encoding="utf-8")
        statuses = re.findall(r"^-\s+\*\*状态\*\*：(\S+?)\s*｜", text, re.M)
        ids = re.findall(r"^##\s+(M\d+)-F\d+", text, re.M)
        if ids:
            mid = ids[0]
            stats[mid] = {"findings": len(ids), "needs_review": statuses.count("needs-review"),
                          "stale": statuses.count("stale")}
        else:
            stats[f.stem] = {"findings": 0, "needs_review": 0, "stale": 0}
    return stats


def main():
    offline = "--offline" in sys.argv
    today = date.today().isoformat()
    print(f"每日信号流水线 {today}")

    print("兼容简报：使用历史缓存；联网采集改用 Spark acquisition.py，见 framework/06_acquisition.md")

    run_step("②b 指标回填", ["pipeline/refresh_indicators.py"], timeout=30)

    news, news_date = latest_news_signals() or ({}, None)
    sec = recent_sec_filings()
    marked = mark_findings_needs_review(sec)
    queue = verify.build_queue()
    counts = verify.write_markdown(queue)

    # 公司名映射（简报里显示中文名）
    companies = {c["company_id"]: c for c in verify.load("companies")}
    projects = {p["site_id"]: p for p in verify.load("projects")}

    def display(eid):
        if eid in companies:
            return companies[eid].get("name_cn") or companies[eid]["name"]
        if eid in projects:
            return projects[eid]["name"]
        return eid

    entities = sorted(news.get("signals", {}).items(), key=lambda kv: -len(kv[1]["hits"]))
    brief = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "date": today,
        "news": {
            "signal_date": news_date,
            "scanned_items": news.get("scanned_items", 0),
            "scanned_dates": news.get("scanned_dates", []),
            "entities": [
                {"id": eid, "name": display(eid), "type": s["type"], "count": len(s["hits"]),
                 "top": [{"title": h["title"], "source": h["source"], "url": h["url"]} for h in s["hits"][:3]]}
                for eid, s in entities[:15]
            ],
        },
        "sec": [{**f, "name": display(f["company"])} for f in sec[:20]],
        "verify": {
            "p1": counts[1], "p2": counts[2],
            "items": [{"table": q["table"], "id": q["id"], "reason": q["reason"]}
                      for q in queue if q["p"] == 1][:10],
        },
        "research": research_stats(),
        "review_marked": marked,
    }
    atomic_write(ROOT / "data" / "brief.json",
                 json.dumps(brief, ensure_ascii=False, indent=2) + "\n")

    # 人读简报
    lines = [f"# 每日简报 {today}", ""]
    lines.append(f"## 新闻信号（{news_date or '无数据'}，扫描 {brief['news']['scanned_items']} 条）")
    lines.append("")
    for e in brief["news"]["entities"][:10]:
        lines.append(f"- **{e['name']}**（{e['count']} 条）")
        for t in e["top"][:2]:
            lines.append(f"  - [{t['source']}] [{t['title'][:70]}]({t['url']})")
    lines.append("")
    lines.append(f"## SEC 文件（近 {SEC_RECENT_DAYS} 天 {len(sec)} 份）")
    lines.append("")
    for f in brief["sec"]:
        lines.append(f"- {f['date']} **{f['name']}** {f['form']} — [文件]({f['url']})")
    lines.append("")
    lines.append(f"## 核验队列：P1 {counts[1]} 条 ｜ P2 {counts[2]} 条（详见 verify_queue.md）")
    lines.append("")
    for q in brief["verify"]["items"]:
        lines.append(f"- [ ] {q['table']} / {q['id']} — {q['reason']}")
    atomic_write(ROOT / "reports" / "daily_brief.md", "\n".join(lines) + "\n")

    if marked:
        print(f"◆ 事件驱动核验：{len(marked)} 条 Finding 因 SEC 信号标为 needs-review")
        for m in marked:
            print(f"    {m['finding']}  ←  {', '.join(m['entities'])}（{m['file']}）")
    print(f"③ 核验队列  P1 {counts[1]} ｜ P2 {counts[2]}")
    print(f"④ 简报已写出  data/brief.json ｜ reports/daily_brief.md")
    print(f"   新闻信号 {len(brief['news']['entities'])} 实体 ｜ SEC 文件 {len(sec)} 份")
    return 0


if __name__ == "__main__":
    sys.exit(main())
