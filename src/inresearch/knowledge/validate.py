#!/usr/bin/env python3
"""数据校验器：按 framework/01_data_standards.md 的规则检查 data/ 下六张表。

机器规则来自 framework/data_contract.json；语义规则见口径手册。用法：
    python3 manage.py validate            # 校验全部，退出码非 0 表示有 ERROR
    python3 manage.py validate --strict   # WARN 也算失败

检查项：
  1. JSON 可解析、必填字段齐全（轻量检查，不做完整 JSON Schema 校验）
  2. 口径规则：estimate 级来源必须带 assumptions；capacity 字段类型
  3. 状态枚举：项目 status 必须是 L1-L9
  4. 去重：主键唯一（site_id / company_id / 序列+时点 等）
  5. 引用完整性：contracts.parties / projects.developer 引用的 company_id 是否存在
  6. 保鲜度：verified_date 超过阈值告警（L6-L9 项目 90 天，L3-L5 项目 180 天，价格按序列频率）
"""

from inresearch.paths import project_root
from inresearch.storage.layout import workspace_path
import csv
import json
import re
import sys
from datetime import date, datetime

ROOT = project_root()
DATA = ROOT / "data"

from inresearch.knowledge.policy import STATUS_LEVELS, SOURCE_GRADES as GRADES, FRESH_DAYS, price_errors

errors, warns = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warns.append(msg)


def load(name):
    path = workspace_path(f"data/{name}.json", ROOT)
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
        for problem in price_errors(r):
            err(f"prices[{rid}]: {problem}")

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
    # 2026-09-28 BOM 2.0：kind 区分 part / software / archetype，只有 part 占尺度；
    # 权利与配额移到 framework/site_rights.json；被拆分的旧 ID 经 aliases 指向去处，
    # 网页与 3D 场景靠这张别名表解析旧 ID，所以别名目标断了就是死链。
    bom_path = ROOT / "framework" / "bom.json"
    rights_path = ROOT / "framework" / "site_rights.json"
    bom_part_ids = set()
    right_ids = set()
    layer_ids = set()
    if rights_path.exists():
        rights = json.loads(rights_path.read_text(encoding="utf-8")).get("rights", [])
        right_ids = {r["id"] for r in rights}
        if len(right_ids) != len(rights):
            err("site_rights.json: 权利 id 重复")
        for r in rights:
            if not set(r.get("variable_classes", [])) <= {1, 2, 3, 4, 5} or not r.get("variable_classes"):
                err(f"site_rights[{r['id']}]: variable_classes 须是 1–5 的非空子集")
            for c in r.get("companies", []):
                if c not in comp_by_id:
                    err(f"site_rights[{r['id']}]: 引用了不存在的 company_id: {c}")
    if bom_path.exists():
        bom = json.loads(bom_path.read_text(encoding="utf-8"))
        layer_ids = {ly["id"] for ly in bom.get("layers", [])}
        kinds = set(bom.get("kinds") or {"part": ""})
        stage_ids = {s["id"] for s in bom.get("stages", [])}
        chain_slots = {}
        bom_part_ids = {p["id"] for p in bom.get("parts", [])}
        if len(bom_part_ids) != len(bom.get("parts", [])):
            err("bom.json: 部件 id 重复")
        for p in bom.get("parts", []):
            kind = p.get("kind", "part")
            if kind not in kinds:
                err(f"bom[{p['id']}]: kind 非法: {kind}")
            if stage_ids and p.get("stage") not in stage_ids:
                err(f"bom[{p['id']}]: stage 非法: {p.get('stage')}")
            if kind == "part":
                if p.get("layer") not in layer_ids:
                    err(f"bom[{p['id']}]: layer 非法: {p.get('layer')}")
            elif p.get("layer") is not None:
                err(f"bom[{p['id']}]: {kind} 条目不占尺度，layer 须为 null")
            systems = bom.get("systems") or {}
            if systems and p.get("system") not in systems:
                err(f"bom[{p['id']}]: system 非法: {p.get('system')}")
            elif systems and isinstance(systems.get(p.get("system")), dict):
                sysd = systems[p["system"]]
                if any(isinstance(s, dict) and s.get("parent") == p["system"] for s in systems.values()):
                    err(f"bom[{p['id']}]: system 须是叶子系统，不能是父级: {p['system']}")
                if p.get("chain") not in sysd.get("chains", []):
                    err(f"bom[{p['id']}]: chain 不属于系统 {p['system']}: {p.get('chain')}")
                if not isinstance(p.get("chain_order"), int) or p["chain_order"] < 1:
                    err(f"bom[{p['id']}]: chain_order 须是正整数")
                key = (p["system"], p.get("chain"), p.get("chain_order"))
                if key in chain_slots:
                    err(f"bom[{p['id']}]: 链路序号与 {chain_slots[key]} 重复: {key}")
                chain_slots[key] = p["id"]
            for c in p.get("companies", []):
                if c not in comp_by_id:
                    err(f"bom[{p['id']}]: 引用了不存在的 company_id: {c}")
        for old, target in (bom.get("aliases") or {}).items():
            if old in bom_part_ids:
                err(f"bom.aliases[{old}]: 旧 ID 仍是现行部件")
            ok = target[5:] in right_ids if target.startswith("site:") else target in bom_part_ids
            if not ok:
                err(f"bom.aliases[{old}]: 去处不存在: {target}")
        if rights_path.exists():
            for r in json.loads(rights_path.read_text(encoding="utf-8")).get("rights", []):
                if r.get("scale") not in layer_ids:
                    err(f"site_rights[{r['id']}]: scale 非法: {r.get('scale')}")
                if stage_ids and r.get("stage") not in stage_ids:
                    err(f"site_rights[{r['id']}]: stage 非法: {r.get('stage')}")
                if r.get("from_bom_part") and (bom.get("aliases") or {}).get(r["from_bom_part"]) != "site:" + r["id"]:
                    err(f"site_rights[{r['id']}]: from_bom_part {r['from_bom_part']} 未在 bom.aliases 指回本条")

    # 部件级来源登记（2026-09-28）：只允许登记现行部件，队须在供应合同里
    fetch_path = ROOT / "framework" / "part_fetch.json"
    if fetch_path.exists() and bom_part_ids:
        contract_path = ROOT / "framework" / "supply_contract.json"
        providers = {p["id"] for p in json.loads(contract_path.read_text(encoding="utf-8")).get("providers", [])} if contract_path.exists() else set()
        for pid, kinds in json.loads(fetch_path.read_text(encoding="utf-8")).get("parts", {}).items():
            if pid not in bom_part_ids:
                err(f"part_fetch[{pid}]: 不是现行部件")
            for kind, reg in kinds.items():
                if kind not in ("spec", "operation", "price", "lead_time", "news"):
                    err(f"part_fetch[{pid}]: 未知数据类别 {kind}")
                if providers and reg.get("team") not in providers:
                    err(f"part_fetch[{pid}/{kind}]: 队不在供应合同里: {reg.get('team')}")
                if not reg.get("instances") or not reg.get("calendar") or not reg.get("publisher_category"):
                    err(f"part_fetch[{pid}/{kind}]: 须写出版方类别、实例与日历")
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

    # 产品资料库：作业计划与落盘索引（2026-08-19 新增）
    # 由来：资料本体在本机外置卷上、云端永远看不见，**索引与计划表就是唯一能被校验的部分**。
    # 不检查的话，company_id 写错、file_path 跑出 library/ 之外、同一份资料两个 doc_id，
    # 都要等到本机点开「本地 ⧉」404 才发现。
    plan_path = workspace_path("data/product_docs_plan.csv", ROOT)
    doc_types = {"DS", "PB", "BR", "WEB", "RA", "UM", "WP"}
    doc_status = {"todo", "downloaded", "needs_manual", "verified", "superseded"}
    plan_n = 0
    if plan_path.exists():
        seen_rows = set()
        with plan_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                plan_n += 1
                rid = f"{row.get('company_id')}/{row.get('product_line')}/{row.get('model')}/{row.get('doc_type')}"
                if row.get("company_id") not in comp_by_id:
                    err(f"product_docs_plan[{rid}]: 引用了不存在的 company_id")
                if row.get("doc_type") not in doc_types:
                    err(f"product_docs_plan[{rid}]: doc_type 非法: {row.get('doc_type')}")
                if row.get("status") not in doc_status:
                    err(f"product_docs_plan[{rid}]: status 非法: {row.get('status')}")
                if rid in seen_rows:
                    err(f"product_docs_plan: 作业行重复 {rid}")
                seen_rows.add(rid)

    plib_path = workspace_path("data/product_library_index.json", ROOT)
    plib = []
    if plib_path.exists():
        plib = json.loads(plib_path.read_text(encoding="utf-8")).get("records", [])
        seen_ids, seen_paths = set(), set()
        for r in plib:
            rid = r.get("doc_id") or "(无 doc_id)"
            if rid in seen_ids:
                err(f"product_library_index: doc_id 重复 {rid}")
            seen_ids.add(rid)
            if r.get("company_id") not in comp_by_id:
                err(f"product_library_index[{rid}]: 引用了不存在的 company_id: {r.get('company_id')}")
            fp = r.get("file_path") or ""
            if not fp.startswith("library/") or ".." in fp:
                err(f"product_library_index[{rid}]: file_path 必须在 library/ 之内: {fp}")
            if fp in seen_paths:
                err(f"product_library_index[{rid}]: file_path 与前面的记录撞了: {fp}")
            seen_paths.add(fp)
            if r.get("status") not in doc_status:
                err(f"product_library_index[{rid}]: status 非法: {r.get('status')}")
            if r.get("status") in {"downloaded", "verified"} \
                    and not re.fullmatch(r"[0-9a-f]{64}", r.get("sha256") or ""):
                err(f"product_library_index[{rid}]: 已落盘却没有合法 sha256——文件换了没人知道")

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

    # 登记表两列（2026-09-28）：node 与 variable_class 由 knowledge.nodes 从骨架派生，存储值须与派生一致
    try:
        from inresearch.knowledge import nodes as node_columns
        for problem in node_columns.problems(ROOT):
            err(problem)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        err(f"nodes: 无法派生登记表两列: {exc}")

    # 汇总
    print(f"记录数: projects={len(projects)} companies={len(companies)} prices={len(prices)} "
          f"policies={len(policies)} contracts={len(contracts)} sources={len(sources)} "
          f"products={len(products)} bom_parts={len(bom_part_ids)} "
          f"product_docs_plan={plan_n} product_library={len(plib)}")
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
