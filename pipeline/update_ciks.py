#!/usr/bin/env python3
"""CIK 回填器：用 SEC 官方 ticker→CIK 映射表补全公司库中美股公司的 cik 字段。

零依赖。数据源 https://www.sec.gov/files/company_tickers.json（覆盖全部 EDGAR 申报主体，
含 GDS/VNET/NBIS 等外国发行人）。只补 ticker 前缀为 NASDAQ:/NYSE: 且 cik 为空的记录；
已有 cik 的记录做一致性核对，不一致时告警但不覆盖（人工裁决）。

用法：python3 pipeline/update_ciks.py [--dry-run]
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "data" / "companies.json"
UA = "datacenter-hub research (niuroumiantt@gmail.com)"
US_PREFIXES = ("NASDAQ:", "NYSE:")


def main():
    dry = "--dry-run" in sys.argv
    req = urllib.request.Request("https://www.sec.gov/files/company_tickers.json",
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        mapping = json.loads(resp.read().decode("utf-8"))
    by_ticker = {v["ticker"].upper(): (str(v["cik_str"]).zfill(10), v["title"]) for v in mapping.values()}
    print(f"SEC 映射表共 {len(by_ticker)} 个 ticker")

    doc = json.loads(COMPANIES.read_text(encoding="utf-8"))
    filled, missing, checked = 0, [], 0
    for c in doc["records"]:
        ticker = c.get("ticker") or ""
        if not ticker.upper().startswith(US_PREFIXES):
            continue
        symbol = ticker.split(":", 1)[1].upper()
        hit = by_ticker.get(symbol)
        if not hit:
            missing.append(f"{c['company_id']} ({ticker})")
            continue
        cik, title = hit
        if c.get("cik"):
            checked += 1
            if c["cik"] != cik:
                print(f"  WARN {c['company_id']}: 现有 cik {c['cik']} 与 SEC {cik} 不一致（{title}），未覆盖")
        else:
            c["cik"] = cik
            filled += 1
            print(f"  + {c['company_id']:22s} {symbol:6s} → CIK {cik}  ({title})")

    if missing:
        print("未匹配（核对 ticker 拼写）: " + ", ".join(missing))
    if not dry and filled:
        COMPANIES.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已写回 {COMPANIES.name}")
    print(f"回填 {filled} 个，核对 {checked} 个已有记录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
