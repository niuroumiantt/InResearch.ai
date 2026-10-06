"""Match supplied originals to the current task book. All results are candidates."""
import argparse
import json
import re
import sqlite3
import subprocess
from pathlib import Path
from inresearch.adapters.acquisition import Collector, hash_file, now, data_root
from inresearch.adapters.html_document import extract as html_text
from inresearch.storage.files import write_json
from inresearch.knowledge import news_observations

# Vocabulary is an extraction aid, never an object or task registry.
TERMS = {
    'gpu': r'\bGPU\b|图形处理器', 'ai-asic': r'\bTPU\b|Trainium|AI ASIC',
    'rack-system': r'NVL72|GB200|GB300|Vera Rubin', 'server': r'\bserver\b|服务器|NVL72',
    'cdu': r'\bCDU\b|coolant distribution|冷却液分配', 'coldplate': r'cold.?plate|冷板',
    'manifold': r'manifold|歧管', 'hbm': r'\bHBM\b|高带宽内存', 'dram': r'\bDRAM\b|动态随机',
    'nic': r'\bNIC\b|network interface|网卡', 'switch': r'\bswitch(?:es)?\b|交换机',
    'transformer': r'\btransformer\b|变压器', 'gas-turbine': r'gas turbine|燃气轮机',
    'gas-engine': r'gas engine|燃气发动机', 'bess': r'\bBESS\b|battery storage|储能',
}
ASPECTS = {
    1: r'architecture|specification|component|\bBOM\b|composition|架构|规格|构成|组成',
    2: r'utilization|goodput|efficiency|load|downtime|reliability|performance|利用率|负载|效率|性能|停机',
    3: r'\$|USD|price|pricing|cost|capex|\bTCO\b|价格|成本|美元|报价',
    4: r'lead time|permit|approval|construction|delivery|queue|timeline|交期|审批|排队|工期|建设',
    5: r'supplier|vendor|customer|operator|tenant|manufacturer|供应商|主体|客户|运营商',
}
FACTORS = {
    'revenue.utilization': r'utilization|goodput|downtime|利用率|停机',
    'revenue.gpus.density': r'NVL72|rack power|GPU.*(?:MW|rack)|密度|整柜功率',
    'cost.depreciation.capex.accelerators': r'GPU.*cost|GPU.*price|\bBOM\b|NVL72|加速器',
    'cost.depreciation.capex.btm': r'behind.the.meter|onsite gas|on.site power|表后|现场燃气',
    'cost.energy': r'electricity|grid|power price|电价|电网',
    'time.build': r'permit|approval|construction|interconnection|审批|工期|建设|并网',
    'capital': r'financing|cost of capital|interest rate|融资|资本成本',
}
ANGLES = [
    ('goodput', r'goodput|training downtime|有效吞吐|训练停机', 'root', 2,
     '模型已有利用率，但已售小时、可用时间与有效训练/推理产出不同。',
     '建议比较有效吞吐、停机与收入的关系；先挂运行变量，若增加模型输入再讨论经济规则，暂无新增部件的依据。'),
    ('dynamic-grid-load', r'load fluctuations|power fluctuations|grid blackout|负载波动|电网.*停电', 'site:grid', 2,
     '站点并网权与电力系统已有归属；静态 MW 不能表达动态爬坡、电能质量和稳定性。',
     '先作为并网条件与运行约束证据；新增动态规则或部件需另案论证，不能把排队容量计入投运。'),
    ('scale-up-network', r'UALink|Ultra Ethernet|scale.up ethernet|纵向扩展', 'root', 1,
     '网络系统已有交换、网卡与互连；协议/拓扑是属性，未证明需要新部件。',
     '建议补互连拓扑、协议及 TCO 比较，先匹配现有规格/运行/价格目标。'),
    ('onsite-power', r'behind.the.meter|onsite gas|on.site power|表后|现场燃气', 'site:grid', 4,
     '站点权利、电力设备与表后发电因子已经登记；供气、排放许可与供电时序需要联查。',
     '先补建设时间和许可条件；如需独立供气权节点，须证明现有六条权利无法表达后再讨论骨架变更。'),
]


def pages(path):
    if path.suffix.lower() == '.pdf':
        result = subprocess.run(['pdftotext', '-enc', 'UTF-8', str(path), '-'], capture_output=True, timeout=120)
        if result.returncode: raise ValueError('pdf_extraction_failed')
        if len(result.stdout) > 20_000_000: raise ValueError('text_too_large')
        return result.stdout.decode('utf-8').split('\f')[:-1] or [result.stdout.decode('utf-8')]
    if path.suffix.lower() in ('.html', '.htm'):
        text, meta = html_text(path)
        if meta['truncated']: raise ValueError('html_extraction_truncated')
        return [text]
    if path.suffix.lower() in ('.txt', '.md'):
        return [path.read_text(encoding='utf-8')]
    raise ValueError('extractor_required')


def match_pages(texts, root):
    root = Path(root)
    targets = json.loads((root/'framework/tco_targets.json').read_text())['targets']
    parts = {p['id']: p for p in json.loads((root/'framework/bom.json').read_text())['parts']}
    matches = []
    for target in targets:
        part = target.get('part_id')
        pattern = TERMS.get(part)
        if not pattern and part in parts:
            pattern = '|'.join(re.escape(x) for x in (parts[part]['name'], part.replace('-', ' ')) if len(x) > 3)
        if not pattern and target.get('factor_id'):
            pattern = next((v for k,v in FACTORS.items() if target['factor_id'].startswith(k)), None)
        if not pattern and target.get('site_right_id'):
            pattern = {'grid': r'interconnection|electricity grid|并网|电网', 'permits': r'permit|approval|审批|许可',
                       'land': r'land acquisition|zoning|土地|选址', 'water': r'water|drought|水资源|缺水'}.get(target['site_right_id'])
        if not pattern: continue
        found = None
        for index, text in enumerate(texts):
            for hit in re.finditer(pattern, text, re.I):
                start, end = max(0, hit.start()-250), min(len(text), hit.end()+350)
                quote = text[start:end].strip()
                if re.search(ASPECTS[target['variable_class']], quote, re.I):
                    found = {'target_id': target['id'], 'node': 'part:'+part if part else 'site:'+target['site_right_id'] if target.get('site_right_id') else 'root',
                             'variable_class': target['variable_class'], 'team': target['team'], 'target_status': target['status'],
                             'model_inputs': target.get('model_inputs', []), 'feeds_primary': target.get('feeds_primary', []),
                             'page': index+1, 'quote': quote, 'status': 'topical_candidate',
                             'next_action': '逐篇深读；核对原文数值、时点、范围、可比口径与反证，再走 C3 采用。'}
                    break
            if found: break
        if found: matches.append(found)
    matches.sort(key=lambda m: (m['target_status']=='sourced', not bool(m['feeds_primary']), m['target_id']))
    proposals = []
    for ident, pattern, node, col, gap, proposal in ANGLES:
        for index, text in enumerate(texts):
            hit = re.search(pattern, text, re.I)
            if hit:
                proposals.append({'id': ident, 'node': node, 'variable_class': col, 'page': index+1,
                    'quote': text[max(0,hit.start()-120):hit.end()+220].strip(), 'gap': gap, 'proposal': proposal,
                    'status': 'discussion_required', 'skeleton_changed': False})
                break
    return matches, proposals


def ingest(path, data, root, title=None, daily_sources=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256*1024*1024: raise ValueError('invalid_material')
    sha = hash_file(path)
    texts = pages(path)
    if hash_file(path) != sha: raise ValueError('material_changed_during_extract')
    matches, proposals = match_pages(texts, root)
    daily = []
    if path.suffix.lower() in ('.html','.htm'):
        from inresearch.materials.daily_events import parse as parse_daily, receive as receive_daily
        daily = parse_daily(path, root, title, daily_sources)
    sites = json.loads((Path(root)/'data/projects.json').read_text())['records']
    companies = json.loads((Path(root)/'data/companies.json').read_text())['records']
    project_observations = []
    for page, text in enumerate(texts, 1):
        for paragraph in re.split(r'\n\s*\n|(?<=[。！？])\s*', text):
            if not re.search(r'data[ -]?cent(?:er|re)|数据中心|园区|campus', paragraph, re.I): continue
            capacity = news_observations.power(paragraph, 'page:'+str(page))
            constraints = news_observations.constraints(paragraph)
            if not capacity and not constraints: continue
            identity = news_observations.identity({'title':paragraph}, sites, companies)
            project_observations.append({'page':page, 'quote':paragraph[:1200], 'capacity_observations':capacity,
                                         'constraints':constraints, **identity, 'acceptance':'candidate'})
    document = {'sha256': sha, 'title': title or path.name, 'pages': len(texts), 'indexed_at': now(),
                'targets_sha256': hash_file(Path(root)/'framework/tco_targets.json'),
                'method': 'page_text_topic_match_v1', 'acceptance': 'candidate', 'full_read': False,
                'matches': matches, 'proposals': proposals,
                'project_observations': project_observations[:200], 'project_observations_truncated':len(project_observations)>200,
                'daily_event_ids':[event['id'] for event in daily],
                'scope': '页内主题检索，不证明整篇已读、引文支持数值或已采用。'}
    c = Collector(data)
    try:
        ident = c.item('fetchreports', sha, 'supplied_research', '', title or path.name, document, state='matched_candidate')
        # Original bytes and source receipt are permanent, separate from the index.
        archived_sha = c.archive_file(ident, path, path.suffix.lower(), {'method': 'user_supplied', 'sha256': sha})
        if archived_sha != sha: raise ValueError('material_changed_during_archive')
        if daily: receive_daily(path, data, root, title, daily_sources)
        import os
        for match in matches:
            node = re.sub(r'[^A-Za-z0-9_.-]', '-', match['node'])
            folder = Path(data)/'library/candidates-by-node'/node/('variable-'+str(match['variable_class']))
            folder.mkdir(parents=True,exist_ok=True,mode=0o700)
            link=folder/(sha[:20]+'-'+Path(title or path.name).name)
            blob=Path(data)/'acquisition/blobs'/sha[:2]/(sha+path.suffix.lower())
            if link.is_symlink():
                if link.resolve()!=blob.resolve():raise ValueError('candidate_view_collision')
            elif link.exists():raise ValueError('candidate_view_collision')
            else:os.symlink(os.path.relpath(blob,folder),link)
        if matches or proposals or daily:
            # Only matched user submissions enter the existing Reader intake.
            # SHA identity prevents duplicate model work. Reader freezes demand
            # ownership and priority when creating a new reading revision.
            raw = Path(data)/'raw-materials'/('research-match-'+sha)
            raw.mkdir(parents=True, exist_ok=True, mode=0o700)
            dest = raw/Path(title or path.name).name
            blob = Path(data)/'acquisition/blobs'/sha[:2]/(sha+path.suffix.lower())
            if not dest.exists(): os.link(blob, dest)
    finally: c.close()
    return document


def projection(data):
    path = Path(data)/'acquisition/catalog.sqlite'
    if not path.exists(): return {'records': [], 'total': 0, 'status': 'not_initialized'}
    con = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    try:
        docs = [json.loads(r[0]) for r in con.execute("SELECT metadata FROM items WHERE kind='supplied_research' ORDER BY updated DESC")]
    finally: con.close()
    counts = {}
    for doc in docs:
        for match in doc['matches']: counts[match['target_id']] = counts.get(match['target_id'],0)+1
    # Join only to the existing Reader catalog; an index never claims full reading.
    readings = {}
    catalog = Path(data)/'catalog/catalog.sqlite'
    if catalog.is_file():
        db = sqlite3.connect(catalog.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            for row in db.execute('SELECT d.sha256,r.state,r.phase,r.chunks_total,r.chunks_read FROM documents d LEFT JOIN reading_runs r ON r.doc_id=d.doc_id AND r.base_revision_id IS NULL'):
                readings[row[0]]={'state':row[1] or 'registered','phase':row[2],'chunks_total':row[3],'chunks_read':row[4]}
        except sqlite3.OperationalError: pass
        finally: db.close()
    exported = []
    for doc in docs[:500]:
        exported.append({**doc, 'reading':readings.get(doc['sha256'],{'state':'awaiting_reader_registration'}),
                         'matches':doc['matches'][:32], 'matches_total':len(doc['matches']),
                         'project_observations':doc.get('project_observations',[])[:8],
                         'project_observations_total':len(doc.get('project_observations',[]))})
    return {'records': exported, 'total': len(docs), 'truncated': len(docs)>500, 'by_target': counts,
            'matched_documents': sum(bool(d['matches']) for d in docs), 'full_read': None, 'adopted': None,
            'status': 'candidate_index', 'scope': '全文提取后的页内主题候选；阅读与采用查 Reader/C3 登记，不由此推断。'}


def reading_objective(data, root, sha):
    """Freeze current demand ownership for a new reading, not an adoption score."""
    target_path = Path(root)/'framework/tco_targets.json'
    if not target_path.is_file(): return {}
    targets = json.loads(target_path.read_text())['targets']
    catalog = Path(data)/'acquisition/catalog.sqlite'
    matched = set()
    if catalog.is_file():
        db = sqlite3.connect(catalog.resolve().as_uri()+'?mode=ro', uri=True)
        try:
            for (metadata,) in db.execute("SELECT metadata FROM items WHERE source='fetchreports' AND kind='supplied_research' AND source_key=?", (sha,)):
                matched.update(m['target_id'] for m in json.loads(metadata).get('matches', []))
        finally: db.close()
    selected = []
    for row in targets:
        if row['id'] not in matched: continue
        node = 'part:'+row['part_id'] if row.get('part_id') else 'site:'+row['site_right_id'] if row.get('site_right_id') else 'root'
        selected.append({'id':row['id'], 'node':node, 'variable_class':row['variable_class'],
                         'team':row['team'], 'status':row['status'], 'model_inputs':row.get('model_inputs', []),
                         'feeds_primary':row.get('feeds_primary', [])})
    selected.sort(key=lambda r:(r['status']=='sourced', not bool(r['feeds_primary']), r['id']))
    gaps = [r for r in selected if r['status'] in ('needed','assumed','delivered')]
    return {'reading_contract':'skeleton-demand-v1', 'targets_sha256':hash_file(target_path),
            'research_demands':selected, 'demand_priority':8 if any(r['feeds_primary'] for r in gaps) else 7 if gaps else 5,
            'purpose':'服务三级账、四问、五类变量与六队现行目标；匹配仅安排阅读，不证明证据支持或 C3 采用。'}


def main():
    from inresearch.paths import project_root
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, default=data_root())
    args = parser.parse_args()
    files = sorted(p for p in args.input.rglob('*') if p.suffix.lower() in ('.pdf','.html','.htm','.txt','.md') and p.is_file()) if args.input.is_dir() else [args.input]
    results = []
    for path in files:
        try:
            row = ingest(path, args.data_root, project_root())
            results.append({'file': path.name, 'sha256': row['sha256'], 'matches': len(row['matches']), 'proposals': len(row['proposals'])})
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            results.append({'file': path.name, 'error': str(exc)})
    receipt = args.data_root/'material-reviews'/'matching-receipts'/('scan-'+now().replace(':','-')+'.json')
    write_json(receipt, {'results': results})
    print(json.dumps({'processed':len(results), 'matched':sum(r.get('matches',0)>0 for r in results),
                      'errors':sum('error' in r for r in results), 'receipt':str(receipt)}, ensure_ascii=False))
    return 1 if any('error' in r for r in results) else 0
