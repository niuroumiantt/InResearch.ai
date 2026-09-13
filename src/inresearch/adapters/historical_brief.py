#!/usr/bin/env python3
"""Historical cache briefing only. Network acquisition runs on Spark via acquisition.py.
Current policy: framework/06_acquisition.md. Cached data is not live collection status.
"""

from inresearch.paths import project_root
from inresearch.storage.layout import workspace_path
import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = project_root()

from inresearch.knowledge import verify as verify  # noqa: E402


def atomic_write(path: Path, text: str):
    from inresearch.storage.files import atomic_write as commit
    commit(path, text.encode('utf-8'))

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
    d = workspace_path("data/raw/news_signals", ROOT)
    files = sorted(d.glob("*_signals.json"), reverse=True) if d.exists() else []
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8")), files[0].name[:10]


def recent_sec_filings():
    """从 data/raw/sec/ 存档解析近 N 天的关注文件。"""
    cutoff = (date.today() - timedelta(days=SEC_RECENT_DAYS)).isoformat()
    out = []
    d = workspace_path("data/raw/sec", ROOT)
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


def review_suggestions(sec_filings):
    """Suggest event-triggered review; signals never rewrite adopted research."""
    import re
    hard = {}
    for filing in sec_filings:
        if filing["form"] in {"10-Q", "10-K", "8-K"}:
            hard[filing["company"]] = max(hard.get(filing["company"], ""), filing["date"])
    suggestions = []
    for path in sorted((ROOT / "research").glob("M*.md")) if hard else ():
        pending = None
        for line in path.read_text(encoding="utf-8").splitlines():
            heading = re.match(r"^##\s+(M\d+-F\d+)\s+(.*?)\s*(\{[^}]*\})?\s*$", line)
            if heading:
                pending = heading.group(1), heading.group(2)
            elif pending and re.match(r"^-\s+\*\*状态\*\*：current\s*｜", line):
                revision = re.search(r"\*\*修订\*\*：(\S+)", line)
                revised = revision.group(1) if revision else ""
                hits = [c for c, stamp in hard.items() if f"entity:{c}" in line and stamp > revised]
                if hits:
                    suggestions.append({'finding': pending[0], 'title': pending[1][:40],
                                        'entities': hits, 'file': path.name, 'status': 'review_suggested',
                                        'signals': [f for f in sec_filings if f['company'] in hits
                                                    and f['date'] > revised
                                                    and f['form'] in {'10-Q', '10-K', '8-K'}]})
                pending = None
    return suggestions


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
    today = date.today().isoformat()
    print(f"每日信号流水线 {today}")

    print("兼容简报：使用历史缓存；联网采集改用 Spark acquisition.py，见 framework/06_acquisition.md")

    run_step("②b 指标回填", ["manage.py", "indicators"], timeout=30)

    news, news_date = latest_news_signals() or ({}, None)
    sec = recent_sec_filings()
    suggestions = review_suggestions(sec)
    queue = verify.build_queue()
    queue.extend({'p': 1, 'table': 'research', 'id': item['finding'],
                  'reason': '事件触发的待复核建议（尚未修改正式状态）',
                  'urls': [signal['url'] for signal in item['signals'] if signal.get('url')],
                  'action': '核对信号与原文后走研究审核：' + item['file']} for item in suggestions)
    queue.sort(key=lambda row: (row['p'], row['table'], row['id']))
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
        "review_suggestions": suggestions,
    }
    atomic_write(workspace_path("data/brief.json", ROOT),
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
    atomic_write(workspace_path("reports/daily_brief.md", ROOT), "\n".join(lines) + "\n")

    if suggestions:
        print(f"◆ 事件驱动核验：{len(suggestions)} 条 Finding 因 SEC 信号建议复核（正式状态未修改）")
        for m in suggestions:
            print(f"    {m['finding']}  ←  {', '.join(m['entities'])}（{m['file']}）")
    print(f"③ 核验队列  P1 {counts[1]} ｜ P2 {counts[2]}")
    print(f"④ 简报已写出  data/brief.json ｜ reports/daily_brief.md")
    print(f"   新闻信号 {len(brief['news']['entities'])} 实体 ｜ SEC 文件 {len(sec)} 份")
    return 0


if __name__ == "__main__":
    sys.exit(main())
