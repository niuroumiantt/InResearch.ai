#!/usr/bin/env python3
"""指标回填器：从六张表自动计算可推导的指标值，写回 framework/indicators.json。

    python3 pipeline/refresh_indicators.py

规则：只回填"库内数据可直接计算"的指标；渠道/外部指标仍靠人工录入。
每次运行覆盖计算值（value + as_of），人工录入的指标不受影响。
collect.py 每日调用。零依赖。
"""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODAY = date.today().isoformat()


def load(name):
    return json.loads((ROOT / "data" / f"{name}.json").read_text(encoding="utf-8"))["records"]


def cap_buckets(p):
    op = bu = pl = 0
    def put(lvl, v):
        nonlocal op, bu, pl
        n = int(lvl[1])
        if n >= 8: op += v
        elif n >= 6: bu += v
        else: pl += v
    if p.get("capacity_it_mw"):
        put(p["status"], p["capacity_it_mw"])
    for k, v in (p.get("capacity_it_mw_by_status") or {}).items():
        put(k, v)
    return op, bu, pl


def latest_price(prices, series):
    pts = sorted((r for r in prices if r["series_id"] == series), key=lambda r: r["as_of"])
    return (pts[-1]["value"], pts[-1]["as_of"]) if pts else (None, None)


def main():
    projects = [p for p in load("projects") if "portfolio" not in p["site_id"]]
    prices = load("prices")
    contracts = load("contracts")

    op = sum(cap_buckets(p)[0] for p in projects)
    computed = {}

    # M01 全球投运容量（项目库 L8+ 聚合，GW）
    computed["global_operational_gw"] = (round(op / 1000, 2), TODAY, "projects 表 L8+ 聚合（库内口径，非全球普查）")
    # 价格序列直通指标
    for ind_id, series in [
        ("transformer_lead_time", "transformer-lead-time"),
        ("gpu_hourly_rate_spot", "gpu-hourly-h100-spot"),
        ("token_price_flagship", "token-price-openai-flagship-output"),
    ]:
        v, asof = latest_price(prices, series)
        if v is not None:
            computed[ind_id] = (v, asof, f"prices:{series} 最新点")
    # M03 循环交易占比（金额加权）
    vals = [c for c in contracts if c.get("value_usd_b")]
    if vals:
        circ = sum(c["value_usd_b"] for c in vals if c.get("circular_flag"))
        computed["circular_deal_exposure"] = (round(circ / sum(c["value_usd_b"] for c in vals) * 100, 1),
                                              TODAY, "contracts 表金额加权（样本小，仅示意）")
    # M03 大额合同余额
    if vals:
        computed["mega_contract_backlog"] = (round(sum(c["value_usd_b"] for c in vals), 1), TODAY,
                                             "contracts 表合计（种子样本）")

    p = ROOT / "framework" / "indicators.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    n = 0
    for ind in doc["indicators"]:
        if ind["id"] in computed:
            v, asof, note = computed[ind["id"]]
            ind["value"], ind["as_of"] = v, asof
            ind["auto_note"] = note
            n += 1
    doc["updated"] = TODAY
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"回填 {n} 个指标：" + "、".join(k for k in computed))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
