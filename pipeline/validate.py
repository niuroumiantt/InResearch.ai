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
import csv
import json
import re
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

    # 产品目录与爆炸图 BOM 的引用完整性
    # 由来（2026-08-18）：产品研究目录项目对齐落库（docs/inbox/inresearch-alignment/），
    # 两项目仅靠 company_id + bom_part_id 两个 ID 锚定；锚点断了对齐就断了，所以必须校验。
    # 顺带发现 bom.json 的 companies 此前从没人检查——coldplate 挂着的 motivair
    # 在 companies.json 里根本不存在，爆炸图上点开就是死链。
    bom_path = ROOT / "framework" / "bom.json"
    bom_part_ids = set()
    if bom_path.exists():
        bom = json.loads(bom_path.read_text(encoding="utf-8"))
        layer_ids = {ly["id"] for ly in bom.get("layers", [])}
        bom_part_ids = {p["id"] for p in bom.get("parts", [])}
        if len(bom_part_ids) != len(bom.get("parts", [])):
            err("bom.json: 部件 id 重复")
        for p in bom.get("parts", []):
            if p.get("layer") not in layer_ids:
                err(f"bom[{p['id']}]: layer 非法: {p.get('layer')}")
            for c in p.get("companies", []):
                if c not in comp_by_id:
                    err(f"bom[{p['id']}]: 引用了不存在的 company_id: {c}")

    prod_status = {"mature", "tight", "transition", "emerging"}
    products = load("products") if (DATA / "products.json").exists() else []
    prod_keys = set()
    for r in products:
        rid = f"{r.get('company_id')}/{r.get('product_line')}"
        k = (r.get("company_id"), r.get("product_line"))
        if k in prod_keys:
            err(f"products: 公司+产品线重复 {rid}")
        prod_keys.add(k)
        if r.get("company_id") not in comp_by_id:
            err(f"products[{rid}]: 引用了不存在的 company_id")
        for part in r.get("bom_parts", []) or [None]:
            if bom_part_ids and part not in bom_part_ids:
                err(f"products[{rid}]: 引用了不存在的 bom_part: {part}")
        if r.get("status") not in prod_status:
            err(f"products[{rid}]: status 非法（须 mature/tight/transition/emerging）: {r.get('status')}")
        if r.get("priority") not in {"P0", "P1", "P2"}:
            err(f"products[{rid}]: priority 非法: {r.get('priority')}")
        if not r.get("library_path"):
            err(f"products[{rid}]: 缺 library_path（对方资料库锚点）")

    # 模块声明与模块定义文件不得分叉
    # 由来（2026-08-17）：framework/modules/Mxx_*.md 的「核心问题」有 80 条，
    # 而工单生成器读的 modules.json 只声明了 36 条——**44 条搭骨架时就想清楚的问题
    # 从来没生成过工单，而且没有任何地方会报错**。与 indicators/metrics 那次分叉同类：
    # 同一件事有两处声明，谁也不检查谁，久了必然只有一处是真的。
    # 逐字比对（不做模糊匹配）：改了 .md 不同步 modules.json 就校验失败。
    mods_json = ROOT / "framework" / "modules.json"
    mods_dir = ROOT / "framework" / "modules"
    if mods_json.exists() and mods_dir.is_dir():
        decl = {m["id"]: m.get("questions") or []
                for m in json.loads(mods_json.read_text(encoding="utf-8"))["modules"]}
        for p in sorted(mods_dir.glob("M*.md")):
            mid = p.name[:3]
            sec = re.search(r"## 核心问题\n(.*?)(?=\n## |\Z)", p.read_text(encoding="utf-8"), re.S)
            for q in (re.findall(r"^\d+\.\s*(.+?)\s*$", sec.group(1), re.M) if sec else []):
                if q not in decl.get(mid, []):
                    err(f"modules.json[{mid}]: 定义文件的核心问题未声明，工单生成器看不见它 —— 「{q[:40]}」")

    # 打分表的 depth 不得与 summary 自述矛盾
    # 由来（2026-08-17）：加 depth 列时，批次 CSV 还不带该列，云端只能按 summary 文案猜。
    # 规则之一是「含 auto_batch → 半自动」，结果把**改判件**判反了——那几条 summary 里出现
    # auto_batch，是在解释「原记录是 auto_batch 生成的、未精读，所以要改判」，
    # 判定器把改判理由当成了自我描述。
    # 代价不是标签难看：facts.py 只认「精读」与「据实生成」，**半自动不得进事实层**，
    # 而误判的三份里就有 M11 REITs 事实的来源（信通院《算力中心创新融资研究报告》）。
    # 现在批次显式带 depth 了，猜的通道理应不再使用；这道检查是防它悄悄复活。
    scores = ROOT / "docs" / "LIBRARY_SCORES.csv"
    if scores.exists():
        csv.field_size_limit(10 ** 9)          # summary 很长，默认上限会抛异常
        SELF_READ = ("逐份精读后的手工打分", "本条为逐份精读")
        with scores.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                s = row.get("summary") or ""
                if row.get("depth") == "半自动" and any(k in s for k in SELF_READ):
                    warn(f"LIBRARY_SCORES[{row['new_path'].split('/')[-1][:48]}]: "
                         f"summary 自述「逐份精读」但 depth 标为半自动——"
                         f"半自动不得进事实层，这条会被证据链拒收")

    # 汇总
    print(f"记录数: projects={len(projects)} companies={len(companies)} prices={len(prices)} "
          f"policies={len(policies)} contracts={len(contracts)} sources={len(sources)} "
          f"products={len(products)} bom_parts={len(bom_part_ids)}")
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
