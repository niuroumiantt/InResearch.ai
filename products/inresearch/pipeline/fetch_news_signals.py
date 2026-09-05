#!/usr/bin/env python3
"""news 信号桥接器：消费 news 项目的每日抓取结果，匹配出与公司库/项目库实体相关的新闻线索。

零依赖。自动信号只产生"待核验线索"，不直接写六张表（入库纪律见 pipeline/README.md）。

用法：
    python3 pipeline/fetch_news_signals.py            # 默认扫描最近 3 天
    python3 pipeline/fetch_news_signals.py 7          # 扫描最近 7 天
    NEWS_DIR=/path/to/news/data python3 pipeline/fetch_news_signals.py

匹配规则：
  - 实体词条 = 公司 name/name_cn + 项目 name/aliases（去掉括号注释，拆分 " / " 复合名）
  - 拉丁词条用词边界匹配，避免子串误报；过短或歧义词条（Meta、Switch、Lambda 等）
    须与行业语境词（数据中心/AI/GPU/cloud 等）同现才计为信号
输出：
  - data/raw/news_signals/YYYY-MM-DD_signals.json（按实体分组，含命中新闻列表）
  - stdout 打印实体命中排行（人工核验入口）
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEWS_DIR = Path(os.environ.get("NEWS_DIR", ROOT.parent / "news" / "data"))
OUT = ROOT / "data" / "raw" / "news_signals"

# 歧义词条：常见词/多义词，必须与语境词同现
AMBIGUOUS = {"meta", "switch", "lambda", "scala", "oracle", "frontier", "colossus",
             "prometheus", "hyperion", "eaton", "trane", "crusoe", "stack", "台达", "华为"}
CONTEXT = re.compile(
    r"data\s?cent|datacenter|ai|gpu|cloud|compute|chip|cooling|server|hyperscal|"
    r"数据中心|算力|智算|液冷|散热|芯片|服务器|云|机房|英伟达|超算", re.IGNORECASE)


def build_terms():
    """返回 [(entity_id, entity_type, term, is_latin)]，词条已清洗。"""
    terms = []

    def clean(name):
        name = re.sub(r"[（(].*?[)）]", "", name)          # 去括号注释
        return [p.strip() for p in name.split(" / ") if len(p.strip()) >= 3]

    companies = json.loads((ROOT / "data" / "companies.json").read_text(encoding="utf-8"))["records"]
    for c in companies:
        for term in clean(c["name"]) + ([c["name_cn"]] if c.get("name_cn") and c["name_cn"] != c["name"] else []):
            terms.append((c["company_id"], "company", term))
    projects = json.loads((ROOT / "data" / "projects.json").read_text(encoding="utf-8"))["records"]
    for p in projects:
        for term in clean(p["name"]) + [a for a in p.get("aliases", []) if len(a) >= 4]:
            terms.append((p["site_id"], "project", term))

    compiled = []
    for eid, etype, term in terms:
        is_latin = bool(re.match(r"^[\x00-\x7f]+$", term))
        if is_latin:
            pat = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        else:
            pat = re.compile(re.escape(term))
        compiled.append((eid, etype, term, pat))
    return compiled


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 3
    index = json.loads((NEWS_DIR / "index.json").read_text(encoding="utf-8"))
    dates = index.get("dates", [])[:days]
    if not dates:
        print(f"news 数据目录无日期索引: {NEWS_DIR}")
        return 1

    terms = build_terms()
    print(f"实体词条 {len(terms)} 条；扫描 {len(dates)} 天: {', '.join(dates)}")

    signals = {}   # entity_id -> {"type":..., "hits": [...]}
    seen_urls = set()
    total = 0
    for d in dates:
        path = NEWS_DIR / f"{d}.json"
        if not path.exists():
            continue
        items = json.loads(path.read_text(encoding="utf-8"))
        total += len(items)
        for item in items:
            title = item.get("title", "")
            for eid, etype, term, pat in terms:
                if not pat.search(title):
                    continue
                if term.lower() in AMBIGUOUS and not CONTEXT.search(title):
                    continue
                key = (eid, item.get("url"))
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                signals.setdefault(eid, {"type": etype, "hits": []})["hits"].append({
                    "term": term, "title": title, "url": item.get("url"),
                    "source": item.get("source"), "published": item.get("published"),
                    "lang": item.get("lang"),
                })

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"{date.today().isoformat()}_signals.json"
    out_path.write_text(json.dumps(
        {"scanned_dates": dates, "scanned_items": total, "signals": signals},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ranked = sorted(signals.items(), key=lambda kv: -len(kv[1]["hits"]))
    print(f"扫描 {total} 条新闻，命中 {len(ranked)} 个实体：")
    for eid, s in ranked[:20]:
        print(f"  {len(s['hits']):4d}  {s['type']:8s} {eid}")
        for h in s["hits"][:2]:
            print(f"        - [{h['source']}] {h['title'][:70]}")
    print(f"\n完整线索已写入 {out_path.relative_to(ROOT)}（人工核验后再入库）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
