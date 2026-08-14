#!/usr/bin/env python3
"""SEC EDGAR 采集器：拉取公司库中所有有 CIK 的公司的最新文件列表。

零依赖（仅标准库）。SEC 要求 User-Agent 带联系方式；限速 ≤10 req/s（这里逐个串行足够）。

用法：
    python3 pipeline/fetch_sec.py            # 全部有 CIK 的公司
    python3 pipeline/fetch_sec.py nvidia     # 只拉指定 company_id

输出：
  - data/raw/sec/<company_id>.json  原始 submissions 数据存档
  - stdout 打印近 90 天的 10-Q/10-K/8-K 清单（人工筛选后入库线索）
"""
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "sec"
UA = "datacenter-hub research (niuroumiantt@gmail.com)"
WATCH_FORMS = {"10-Q", "10-K", "8-K", "S-1", "424B5"}
RECENT_DAYS = 90


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    companies = json.loads((ROOT / "data" / "companies.json").read_text(encoding="utf-8"))["records"]
    targets = [c for c in companies if c.get("cik") and (not only or c["company_id"] == only)]
    if not targets:
        print("没有可拉取的公司（检查 companies.json 的 cik 字段）")
        return 1

    RAW.mkdir(parents=True, exist_ok=True)
    cutoff = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()

    for c in targets:
        cid, cik = c["company_id"], c["cik"]
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        try:
            data = fetch(url)
        except Exception as e:
            print(f"[{cid}] 拉取失败: {e}")
            continue
        (RAW / f"{cid}.json").write_text(json.dumps(data), encoding="utf-8")

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accs = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        hits = [
            (dates[i], forms[i],
             f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accs[i].replace('-', '')}/{docs[i]}")
            for i in range(len(forms))
            if forms[i] in WATCH_FORMS and dates[i] >= cutoff
        ]
        print(f"[{cid}] 近 {RECENT_DAYS} 天 {len(hits)} 份:")
        for d, f, link in hits[:10]:
            print(f"    {d}  {f:6s}  {link}")
        time.sleep(0.2)
    print(f"\n原始数据已存档到 {RAW}（拉取时间 {datetime.now().isoformat(timespec='seconds')}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
