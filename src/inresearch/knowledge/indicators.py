#!/usr/bin/env python3
"""指标回填器：按发布定义与当前业务数据生成指标投影。

    python3 manage.py indicators

规则：只回填"库内数据可直接计算"的指标；渠道/外部指标仍靠人工录入。
每次运行覆盖计算值（value + as_of），人工录入的指标不受影响。
作者工作区写 framework/indicators.json；部署写独立运行投影，保留发布定义。零依赖。
"""

from inresearch.paths import project_root
from inresearch.storage.layout import workspace_path
from inresearch.storage.files import locked, write_json
from inresearch.knowledge import industry
import json
from datetime import date
from pathlib import Path

ROOT = project_root()


def load(name, root):
    return json.loads((workspace_path(f"data/{name}.json", root)).read_text(encoding="utf-8"))["records"]


def cap_buckets(p):
    """Current active unique single-value phase subtotal, not complete site capacity.

    Ranges have no representative scalar. Use capacity_summary for coverage.
    """
    total = industry.totals([industry.project(p)])
    return tuple(total[stage] for stage in industry.STAGES)


def capacity_summary(projects):
    """Use the same current-time, phase, lifecycle and identity policy as industry."""
    views = [industry.project(p) for p in projects]
    total = industry.totals(views)
    active = industry.totals([p for p in views if not p['portfolio'] and not p.get('duplicate_of')
                              and p['lifecycle'] == 'active'])
    coverage = {'value_scope': '当前活跃去重站点的单值分期小计（含已标记估算）；区间与未知不按零计完整容量',
                'active_sites': active['sites'], 'ranged_sites': active['ranged_sites'],
                'unknown_sites': active['unknown'],
                'has_unquantified_sites': bool(active['ranged_sites'] or active['unknown']),
                'inactive_sites_excluded': total['inactive_sites'],
                'duplicates_excluded': sum(bool(p.get('duplicate_of')) and not p['portfolio'] for p in views),
                'portfolios_excluded': total['portfolios_excluded'],
                'estimated_operating_mw': total['estimated']['operating']}
    return {'totals': total, 'coverage': coverage}


def latest_price(prices, series):
    pts = sorted((r for r in prices if r["series_id"] == series), key=lambda r: r["as_of"])
    return (pts[-1]["value"], pts[-1]["as_of"]) if pts else (None, None)


def refresh(root=ROOT):
    with locked(workspace_path("framework/indicators.json", root)):
        return _refresh(Path(root))


def _refresh(root):
    today = date.today().isoformat()
    projects = load("projects", root)
    prices = load("prices", root)
    contracts = load("contracts", root)

    capacity = capacity_summary(projects)
    op = capacity['totals']['operating']
    coverage = capacity['coverage']
    computed = {}

    # M01 全球投运容量（项目库 L8+ 聚合，GW）
    computed["global_operational_gw"] = (round(op / 1000, 2), today,
        'projects 当前活跃去重 L8+ 单值小计（含已标记估算，非全球普查）；'
        f"活跃站点中含区间 {coverage['ranged_sites']}、未知 {coverage['unknown_sites']}，均不按零计完整容量；"
        f"排除非活跃 {coverage['inactive_sites_excluded']}、重复 {coverage['duplicates_excluded']}、组合 {coverage['portfolios_excluded']}")
    # 价格序列直通指标
    for ind_id, series in [
        ("transformer_lead_time", "transformer-lead-time"),
        ("gpu_hourly_rate_spot", "gpu-hourly-h100-spot"),
        ("token_price_flagship", "token-price-openai-flagship-output"),
        ("vacancy_rate_na", "vacancy-rate-na"),
        ("dc_rent_index_na", "dc-rent-index-na"),
    ]:
        v, asof = latest_price(prices, series)
        if v is not None:
            computed[ind_id] = (v, asof, f"prices:{series} 最新点")
    # M11 运营资产每 MW 成交价（asset-deal 记录滚动中位数）
    deals = [r["value"] for r in prices if r.get("category") == "asset-deal"]
    if deals:
        import statistics
        computed["price_per_mw_operational"] = (round(statistics.median(deals), 1), today,
                                                f"prices 表 asset-deal 类 {len(deals)} 笔中位数")
    # M03 循环交易占比（金额加权）
    vals = [c for c in contracts if c.get("value_usd_b")]
    if vals:
        circ = sum(c["value_usd_b"] for c in vals if c.get("circular_flag"))
        computed["circular_deal_exposure"] = (round(circ / sum(c["value_usd_b"] for c in vals) * 100, 1),
                                              today, "contracts 表金额加权（样本小，仅示意）")
    # M03 大额合同余额
    if vals:
        computed["mega_contract_backlog"] = (round(sum(c["value_usd_b"] for c in vals), 1), today,
                                             "contracts 表合计（种子样本）")

    p = workspace_path("framework/indicators.json", root)
    doc = json.loads((root / "framework/indicators.json").read_text(encoding="utf-8"))
    n = 0
    for ind in doc["indicators"]:
        if ind["id"] in computed:
            v, asof, note = computed[ind["id"]]
            ind["value"], ind["as_of"] = v, asof
            ind["auto_note"] = note
            if ind['id'] == 'global_operational_gw':
                ind['auto_coverage'] = coverage
            n += 1
    doc["updated"] = today
    write_json(p, doc)
    return {"count": n, "indicators": list(computed)}


def main():
    result = refresh()
    print(f"回填 {result['count']} 个指标：" + "、".join(result['indicators']))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
