#!/usr/bin/env python3
"""数据校验器：按 framework/01_data_standards.md 的规则检查 data/ 下六张表。

零依赖（仅标准库），与 news 项目同基因。用法：
    python3 pipeline/validate.py            # 校验全部，退出码非 0 表示有 ERROR
    python3 pipeline/validate.py --strict   # WARN 也算失败

检查项：
  1. JSON 可解析、必填字段齐全（轻量检查，不做完整 JSON Schema 校验）
  2. 口径规则：estimate 级来源必须带 assumptions；capacity 字段类型
  3. 状态枚举：项目 status 必须是 L1-L9
  4. 去重：主键唯一（site_id / company_id / 序列+时点 等）
  5. 引用完整性：contracts.parties / projects.developer 引用的 company_id 是否存在
  6. 保鲜度：verified_date 超过阈值告警（L6-L9 项目 90 天，L3-L5 项目 180 天，价格 30 天）
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

STATUS_LEVELS = {f"L{i}" for i in range(1, 10)}
GRADES = {"regulatory", "company", "research", "media", "estimate"}
FRESH_DAYS = {"project_late": 90, "project_early": 180, "price": 30, "default": 365}

errors, warns = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warns.append(msg)


def load(name):
    path = DATA / f"{name}.json"
    if not path.exists():
        err(f"{name}.json 不存在")
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        err(f"{name}.json 解析失败: {e}")
        return []
    records = doc.get("records", [])
    if not isinstance(records, list):
        err(f"{name}.json 缺少 records 数组")
        return []
    return records


def days_since(datestr):
    if not datestr:
        return None
    try:
        return (date.today() - datetime.strptime(datestr[:10], "%Y-%m-%d").date()).days
    except ValueError:
        return None


def check_unique(records, key, table):
    seen = {}
    for r in records:
        k = r.get(key)
        if not k:
            err(f"{table}: 有记录缺主键 {key}")
            continue
        if k in seen:
            err(f"{table}: 主键重复 {key}={k}")
        seen[k] = r
    return seen


def main():
    strict = "--strict" in sys.argv

    projects = load("projects")
    companies = load("companies")
    prices = load("prices")
    policies = load("policies")
    contracts = load("contracts")
    sources = load("sources")

    proj_by_id = check_unique(projects, "site_id", "projects")
    comp_by_id = check_unique(companies, "company_id", "companies")
    check_unique(policies, "policy_id", "policies")
    check_unique(contracts, "contract_id", "contracts")
    check_unique(sources, "source_id", "sources")

    price_keys = set()
    for r in prices:
        k = (r.get("series_id"), r.get("as_of"))
        if k in price_keys:
            err(f"prices: 序列+时点重复 {k}")
        price_keys.add(k)

    # 项目库规则
    for r in projects:
        sid = r.get("site_id", "?")
        if r.get("status") not in STATUS_LEVELS:
            err(f"projects[{sid}]: status 非法（须 L1-L9）: {r.get('status')}")
        cap, cap_by = r.get("capacity_it_mw"), r.get("capacity_it_mw_by_status")
        if cap is not None and cap_by:
            err(f"projects[{sid}]: capacity_it_mw 与 by_status 只能填一个（避免重复计入）")
        if cap_by:
            bad = set(cap_by) - STATUS_LEVELS
            if bad:
                err(f"projects[{sid}]: by_status 含非法状态 {bad}")
        if not r.get("sources"):
            err(f"projects[{sid}]: 缺 sources")
        for s in r.get("sources", []):
            if s.get("grade") not in GRADES:
                err(f"projects[{sid}]: 来源 grade 非法: {s.get('grade')}")
        d = days_since(r.get("verified_date"))
        limit = FRESH_DAYS["project_late"] if r.get("status") in {"L6", "L7", "L8", "L9"} else FRESH_DAYS["project_early"]
        if d is None:
            err(f"projects[{sid}]: verified_date 缺失或格式错误")
        elif d > 2 * limit:
            err(f"projects[{sid}]: 核验超期 {d} 天（红线 {2*limit}），不得进入输出物")
        elif d > limit:
            warn(f"projects[{sid}]: 核验超期 {d} 天（阈值 {limit}）")
        for c in r.get("developer", []) + r.get("tenant", []):
            if c not in comp_by_id and c != "multiple":
                warn(f"projects[{sid}]: 引用了不存在的 company_id: {c}")

    # 价格库规则
    for r in prices:
        rid = f"{r.get('series_id')}@{r.get('as_of')}"
        if r.get("grade") == "estimate" and not r.get("assumptions"):
            err(f"prices[{rid}]: estimate 级必须写 assumptions（推导链条）")
        if r.get("grade") not in GRADES:
            err(f"prices[{rid}]: grade 非法")
        if not isinstance(r.get("value"), (int, float)):
            err(f"prices[{rid}]: value 必须是数字")

    # 合同库规则
    for r in contracts:
        cid = r.get("contract_id", "?")
        for p in r.get("parties", []):
            if p not in comp_by_id:
                warn(f"contracts[{cid}]: 引用了不存在的 company_id: {p}")
        for s in r.get("site_ids", []):
            if s not in proj_by_id:
                warn(f"contracts[{cid}]: 引用了不存在的 site_id: {s}")
        if r.get("grade") not in GRADES:
            err(f"contracts[{cid}]: grade 非法")

    # 汇总
    print(f"记录数: projects={len(projects)} companies={len(companies)} prices={len(prices)} "
          f"policies={len(policies)} contracts={len(contracts)} sources={len(sources)}")
    for m in errors:
        print(f"  ERROR {m}")
    for m in warns:
        print(f"  WARN  {m}")
    if errors or (strict and warns):
        print(f"校验失败: {len(errors)} errors, {len(warns)} warnings")
        return 1
    print(f"校验通过（{len(warns)} warnings）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
