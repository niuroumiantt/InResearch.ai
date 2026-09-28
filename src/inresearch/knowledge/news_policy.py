"""Headline eligibility and entity matching; no collection or database writes."""
import json
import re

INEWS_DATACENTER_URL = 'https://inews.today/api/feeds/datacenter'
# Additive feed v2 fields (schema_version stays 1). inews tags events; inresearch never
# treats a tag as adopted evidence, only as a lead that names the team owning the original.
EVENT_TYPES = ('financing', 'lease_contract', 'project_milestone', 'tariff_power_policy', 'lead_time_supply',
               'onsite_power_grid', 'tax_regulation', 'operations_incident', 'transaction_valuation', 'product_price_change')
RESEARCH_ANGLES = ('technology', 'supply', 'market', 'capital', 'deployment', 'policy', 'safety', 'society', 'other')
FEED_V2_FIELDS = ('event_type', 'research_angle', 'layer_tags', 'origin_pointer', 'editorial_pick')

def trusted_news_selection(metadata):
    selection = metadata.get('upstream_selection')
    return (isinstance(selection, dict)
            and selection.get('url') == INEWS_DATACENTER_URL
            and selection.get('schema_version') == 1
            and selection.get('verification') == 'direct_https_feed_v1')

POLICY = 'datacenter-headline-v2'
DIRECT = re.compile(r"data[ -]?cent(?:er|re)s?|colocation|hyperscal(?:e|er)|数据中心|资料中心|數據中心|智算中心|算力中心|机房|機房", re.I)
INFRA = re.compile(r"enterprise ssd|server (?:cpu|gpu|rack|memory)|gpu cluster|ai server|infiniband|nvlink|cpo|co-packaged optics|800g|1\.6t|coolant distribution unit|direct.to.chip|液冷|冷板|企业级.?ssd|伺服器|服务器|光模块|算力租赁|算力基建|供配电", re.I)
CONTEXT = re.compile(r"server|gpu|compute|rack|hyperscal|data[ -]?cent|ai infrastructure|服务器|机柜|算力|数据中心|智算", re.I)
SUPPLY = re.compile(r"nand|dram|ssd|controller|power|grid|substation|cooling|ppa|transformer|电网|变电|供电|储能|冷却|控制器|存储", re.I)
MEMORY = re.compile(r'memory|wafer|semiconductor|dram|gpu|chip|stack|内存|記憶體|存储|芯片|晶圆|運算|运算|堆叠|堆疊', re.I)
HBM_MODEL = re.compile(r'(?<![a-z0-9])hbm[2-9][a-z0-9]*(?![a-z0-9])', re.I)
HBM = re.compile(r'(?<![a-z0-9])hbm(?![a-z0-9])', re.I)
NOISE = re.compile(r"gaming|geforce|playstation|xbox|smartphone|游戏|手机|笔记本|stocks to buy|price target|股价|目标价", re.I)

def classify(row):
    text = str(row.get('title') or '') + ' ' + str(row.get('title_zh') or '')
    if DIRECT.search(text): return '数据中心建设与运营'
    if NOISE.search(text): return None
    if HBM_MODEL.search(text) or (HBM.search(text) and MEMORY.search(text)): return '数据中心内存供应链'
    if INFRA.search(text): return '数据中心硬件与基础设施'
    if SUPPLY.search(text) and CONTEXT.search(text): return '数据中心供应链'
    return None

# 歧义词条：常见词/多义词，必须与语境词同现
AMBIGUOUS = {"meta", "switch", "lambda", "scala", "oracle", "frontier", "colossus",
             "prometheus", "hyperion", "eaton", "trane", "crusoe", "stack", "台达", "华为"}
ENTITY_CONTEXT = re.compile(
    r"data\s?cent|datacenter|\bai\b|\bgpu\b|cloud|compute|chip|cooling|server|hyperscal|"
    r"数据中心|算力|智算|液冷|散热|芯片|服务器|云|机房|英伟达|超算", re.IGNORECASE)


def build_terms(root):
    """返回 [(entity_id, entity_type, term, is_latin)]，词条已清洗。"""
    terms = []

    def clean(name):
        name = re.sub(r"[（(].*?[)）]", "", name)          # 去括号注释
        return [p.strip() for p in name.split(" / ") if len(p.strip()) >= 3]

    companies = json.loads((root / "data" / "companies.json").read_text(encoding="utf-8"))["records"]
    for c in companies:
        for term in clean(c["name"]) + ([c["name_cn"]] if c.get("name_cn") and c["name_cn"] != c["name"] else []):
            terms.append((c["company_id"], "company", term))
    projects = json.loads((root / "data" / "projects.json").read_text(encoding="utf-8"))["records"]
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
