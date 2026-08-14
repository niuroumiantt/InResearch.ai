#!/usr/bin/env python3
"""GPU 租价采集器：拉取 vast.ai 市场 on-demand 报价，写入价格库时间序列。

    python3 pipeline/fetch_gpu_prices.py

口径：vast.ai 为市场化低价档（社区+机房混合供给），取最低 20 个报价的中位数，
反映现货底价走势；与 CoreWeave/超大规模长约价不是同一口径，不可混比。
每天最多写入一个数据点（幂等）。零依赖。
"""
import json
import statistics
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://console.vast.ai/api/v0/bundles/"
UA = "datacenter-hub research (niuroumiantt@gmail.com)"

TARGETS = [
    ("gpu-hourly-h100-spot", "H100 SXM", "H100 SXM 单卡现货时租"),
    ("gpu-hourly-b200-spot", "B200", "B200 单卡现货时租"),
]


def fetch_median(gpu_name):
    q = {"gpu_name": {"eq": gpu_name}, "num_gpus": {"eq": 1}, "rentable": {"eq": True},
         "type": "on-demand", "order": [["dph_total", "asc"]], "limit": 20}
    url = API + "?" + urllib.parse.urlencode({"q": json.dumps(q)})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        offers = json.loads(r.read().decode())["offers"]
    prices = [o["dph_total"] for o in offers if o.get("dph_total")]
    return (round(statistics.median(prices), 2), len(prices)) if prices else (None, 0)


def main():
    today = date.today().isoformat()
    p = ROOT / "data" / "prices.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    existing = {(r["series_id"], r["as_of"]) for r in doc["records"]}
    added = 0
    for series, gpu, note in TARGETS:
        if (series, today) in existing:
            print(f"[{series}] 今日已有数据点，跳过")
            continue
        try:
            v, n = fetch_median(gpu)
        except Exception as e:
            print(f"[{series}] 抓取失败: {e}")
            continue
        if v is None:
            print(f"[{series}] 无报价")
            continue
        doc["records"].append({
            "series_id": series, "category": "gpu-rental", "module": "M13",
            "as_of": today, "value": v, "unit": "$/hr", "region": "global",
            "assumptions": f"vast.ai 市场 on-demand 最低 {n} 个报价中位数（低价档口径，非长约/超大规模价）",
            "grade": "media", "source_url": "https://cloud.vast.ai/",
            "note": note + "；自动采集 fetch_gpu_prices.py"})
        added += 1
        print(f"[{series}] {gpu} = ${v}/hr（{n} 个报价中位数）")
    if added:
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已写入 {added} 个数据点")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
