"""Rebuild source-only architecture evidence from the frozen baseline and checkout.
Run from any directory. Does not touch business data, user stores or remote hosts.
"""
import ast
from collections import Counter, defaultdict
import csv
import hashlib
import json
import posixpath
from pathlib import Path
import re
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BASE = '8150149e2c77e4f820ba6e6434ec26cc2efda4d3'
PLAN = '6331161'
AUDIT = OUT.relative_to(ROOT).as_posix() + '/'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def write_csv(name, rows):
    with (OUT/name).open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def plan_csv(name):
    return list(csv.DictReader(git('show', PLAN+':'+AUDIT+name).decode().splitlines()))


def category(path, raw):
    try:
        if b'\x00' in raw: return 'binary'
        raw.decode()
    except UnicodeDecodeError: return 'binary'
    if path.startswith('docs/inbox/framework_proposals/'): return 'external_material'
    if '/vendor/' in path or Path(path).name.startswith('Inter'): return 'third_party'
    if path.startswith('tests/'): return 'tests'
    if Path(path).suffix in {'.py', '.js', '.cjs', '.mjs', '.css', '.html', '.sh'}: return 'owned_source'
    if Path(path).suffix in {'.json', '.jsonl', '.csv', '.tsv'}: return 'data_config_registry'
    return 'docs_other_text'


SPLITS = {
 'pipeline/continuous_reader.py': ['workflow/reading_stages.py','materials/artifacts.py','materials/reader_contracts.py','adapters/reader_model.py','storage/catalog.py','delivery/reader_export.py','interfaces/reader.py'],
 'pipeline/m4_l2.py': ['knowledge/fact_contract.py','delivery/reading_packet.py'],
 'pipeline/m4_triage_l1.py': ['materials/triage.py','materials/naming.py'],
 'pipeline/m4_office_text.py': ['adapters/office_container.py','adapters/office_grid.py','adapters/office_biff.py','adapters/office_ppt.py','adapters/office_ooxml.py'],
 'pipeline/serve.py': ['workflow/commands.py','interfaces/static.py'],
 'pipeline/auth.py': ['interfaces/pages.py'],
}
rows = plan_csv('file-migration.csv')
actual = {r['old_path']: r['target_path'] for r in rows}
actual['pipeline/fetch_news_signals.py'] = 'src/inresearch/knowledge/news_policy.py'
for row in rows:
    old = row['old_path']; target = actual[old]
    row['planned_target'] = row['target_path']; row['target_path'] = target
    extras = ['src/inresearch/'+p for p in SPLITS.get(old, [])]
    if old == 'assets/site-skin.js': extras = ['web/themes/preference.js']
    if old in ('bom3d.html', 'rack3d.html'): extras = ['web/components/part-inspector.js','web/components/part-dossier.js','web/components/series-summary.js']
    row['split_targets'] = ';'.join(extras)
    if not target:
        assert not (ROOT/old).exists(), old
        row.update(result='deleted entry; historical/runtime records preserved', lines_after=0, sha256_after='')
        continue
    raw = (ROOT/target).read_bytes()
    for extra in extras: assert (ROOT/extra).is_file(), extra
    row['sha256_after'] = ('' if target in {'framework/repository_manifest.json','docs/REPOSITORY_REGISTER.md'}
                            else hashlib.sha256(raw).hexdigest())
    row['lines_after'] = 0 if row['category']=='binary' else len(raw.decode().splitlines())
    row['result'] = ('retained byte-identical' if row['sha256_after']==row['sha256_before']
                     else 'implementation/reference updated; details in DELIVERY.md')
    if target in {'framework/repository_manifest.json','docs/REPOSITORY_REGISTER.md'}:
        row['result'] = 'governance-generated; after hash omitted to avoid audit/manifest reference cycle'
    if old != target:
        assert not (ROOT/old).exists(), old
        row['result'] = 'old source retired; single destination'+('; responsibilities split' if extras else '')
    if old == 'pipeline/fetch_news_signals.py': row['result'] = 'rules moved; legacy CLI wrapper deleted; acquisition news is the only command'
write_csv('file-migration.csv', rows)

paths = sorted({p for p in git('ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0') if p and (ROOT/p).is_file()})
texts = {}
for p in paths:
    try: texts[p] = (ROOT/p).read_text()
    except UnicodeDecodeError: pass
mods = {'inresearch.'+'.'.join(Path(p).relative_to('src/inresearch').with_suffix('').parts):p
        for p in paths if p.startswith('src/inresearch/') and p.endswith('.py')}
refs = []; edges = defaultdict(set)

def ref(implementation, consumer, line, kind, symbols):
    refs.append(dict(implementation=implementation, consumer=consumer, line=line, kind=kind,
                     symbols=symbols, result='current source consumer; local verification in DELIVERY.md'))

for p, text in texts.items():
    if not p.endswith('.py') or p.startswith(AUDIT): continue
    tree = ast.parse(text)
    module = next((m for m,f in mods.items() if f==p), None)
    bindings={}
    for node in ast.walk(tree):
        targets=[]
        if isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                full=node.module+'.'+a.name
                if full in mods:
                    targets.append((full, a.asname or a.name))
                    bindings[a.asname or a.name]=full
                elif node.module in mods: targets.append((node.module, a.name))
        if isinstance(node, ast.Import):
            targets.extend((a.name, a.asname or a.name) for a in node.names if a.name in mods)
        if p.endswith('/interfaces/cli.py') and isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in mods:
            targets.append((node.value, 'CLI command registry'))
        for target, symbol in targets:
            ref(mods[target], p, node.lineno, 'python import / command registry', symbol)
            if module: edges[module].add(target)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in bindings:
            ref(mods[bindings[node.value.id]],p,node.lineno,'python module member',node.attr)

routes = json.loads((ROOT/'web/routes.json').read_text())
reverse={v:k for k,v in routes.items()}
for p,text in texts.items():
    if not p.startswith('web/') or Path(p).suffix not in {'.html','.js','.css'}: continue
    pattern=r'''(?:from\s+|(?:src|href)\s*=\s*)["']([^"']+)["']|url\(["']?([^\)"']+)["']?\)'''
    for match in re.finditer(pattern,text):
        url=match.group(1) or match.group(2)
        if url=='three': url='/assets/vendor/three.module.js'
        public=posixpath.normpath(posixpath.join(posixpath.dirname(reverse.get(p,'/assets/'+Path(p).name)), url))
        target=routes.get(public)
        if target: ref(target,p,text[:match.start()].count('\n')+1,'web import / declared resource',url)
for provider, text in texts.items():
    if not provider.startswith('web/') or '/vendor/' in provider: continue
    for name in re.findall(r'window\.([A-Za-z_]+)\s*=',text):
        for consumer,body in texts.items():
            if consumer==provider or not consumer.startswith('web/'): continue
            for match in re.finditer(r'window\.'+re.escape(name)+r'\b',body):
                ref(provider,consumer,body[:match.start()].count('\n')+1,'public browser state contract',name)
for public,target in routes.items(): ref(target,'web/routes.json',1,'stable public URL',public)
for p,text in texts.items():
    if p.startswith(AUDIT) or p.startswith(('docs/archive/','docs/reviews/')) or p=='deploy/docker-compose.yml': continue
    for line_no,line in enumerate(text.splitlines(),1):
        for match in re.finditer(r'manage\.py["\']?[, ]+["\']?([a-z][a-z-]+)',line):
            ref('src/inresearch/interfaces/cli.py',p,line_no,'CLI invocation/reference',match.group(1))
refs = sorted({tuple(r.values()):r for r in refs}.values(),key=lambda r:(r['implementation'],r['consumer'],r['line'],r['symbols']))
write_csv('public-consumers.csv',refs)
by_impl=defaultdict(list)
for r in refs: by_impl[r['implementation']].append(r)
shared=[]
for p in sorted(set(mods.values()) | {r['implementation'] for r in refs}):
    if p.endswith('/__init__.py'): continue
    consumers=sorted({r['consumer'] for r in by_impl[p]})
    shared.append(dict(implementation=p,consumers=';'.join(consumers),consumer_count=len(consumers),
                       status='all statically observed repo consumers listed' if consumers else 'module entry/internal only; no observed external repo import'))
write_csv('shared-implementations.csv',shared)

old_refs=plan_csv('consumers.csv')
for row in old_refs:
    consumer=actual.get(row['consumer_before'],row['consumer_before'])
    implementation=actual.get(row['implementation_before'],row['implementation_after'])
    row.update(consumer_after=consumer,implementation_after=implementation)
    old=row['implementation_before']; text=texts.get(consumer,'')
    if not consumer: result='consumer retired with old entry'
    elif consumer.startswith(('docs/archive/','docs/reviews/')) or consumer=='deploy/docker-compose.yml' or '/_selftest/' in consumer: result='historical text retained; not a runtime instruction'
    elif row['kind']=='asset_reference': result='public URL retained; web/routes.json resolves to unique migrated source'
    elif old in text: result='REVIEW: old path remains'
    else:
        direct=[r for r in by_impl[implementation] if r['consumer']==consumer]
        result=('direct consumer migrated; see public-consumers.csv' if direct else
                'old direct reference retired or moved into extracted module; current full consumer set in public-consumers.csv')
    if consumer.startswith('deploy/spark-reader/') or consumer.endswith('/ocr_worker.py'):
        result += '; remote execution not verified'
    row['migration_result']=result
write_csv('consumers.csv',old_refs)

# Strongly connected components report actual import cycles, including lazy imports.
index={};low={};stack=[];on=set();cycles=[]
def visit(n):
    index[n]=low[n]=len(index);stack.append(n);on.add(n)
    for target in edges[n]:
        if target not in index:visit(target);low[n]=min(low[n],low[target])
        elif target in on:low[n]=min(low[n],index[target])
    if low[n]==index[n]:
        group=[]
        while True:
            item=stack.pop();on.remove(item);group.append(item)
            if item==n:break
        if len(group)>1:cycles.append(sorted(group))
for m in mods:
    if m not in index:visit(m)
violations=[{'from':a,'to':b} for a,bs in edges.items() for b in bs
            if a.split('.')[1] in ('materials','knowledge','adapters','storage') and b.split('.')[1] in ('interfaces','workflow','delivery')]
write_json('dependency-audit.json',dict(modules=len(mods),edges=sum(map(len,edges.values())),cycles=cycles,
    forbidden_direction_edges=violations,scope='Python explicit imports and CLI registry; not a whole-program dynamic call proof'))

baseline_targets={r['target_path'] for r in rows if r['target_path']}
new=[dict(path=p,category=category(p,(ROOT/p).read_bytes()),owner=p.split('/')[2] if p.startswith('src/') else p.split('/')[0],
          reason='audit evidence' if p.startswith(AUDIT) else 'new responsibility or verification; see DELIVERY.md',
          consumers=';'.join(sorted({r['consumer'] for r in by_impl[p]}))) for p in paths if p not in baseline_targets]
write_csv('new-files.csv',new)
# Audit files are separately reported. Product categories use the original classifier.
totals=defaultdict(lambda:dict(files=0,lines=0)); dirs=set(); product_dirs=set(); audit_count=Counter()
for p in paths:
    raw=(ROOT/p).read_bytes(); cat=category(p,raw)
    lines=0 if cat=='binary' else len(raw.decode().splitlines())
    dirs.update(str(d) for d in Path(p).parents if str(d)!='.')
    if p.startswith(AUDIT):audit_count.update(files=1,lines=lines);continue
    totals[cat]['files']+=1;totals[cat]['lines']+=lines
    product_dirs.update(str(d) for d in Path(p).parents if str(d)!='.')
write_json('after.json',dict(baseline=BASE,plan_commit=PLAN,files=len(paths),directories=len(dirs),
    directories_excluding_this_audit=len(product_dirs),categories=totals,audit_evidence=dict(audit_count),
    top_level_directories=sorted({p.split('/')[0] for p in paths if '/' in p}),
    source_scope='Tracked/proposed files only; physical UTF-8 lines including comments/blanks. This audit directory separately counted; no runtime databases, originals or dependency installs.',
    baseline_file_rows=len(rows),baseline_consumer_rows=len(old_refs),current_consumer_rows=len(refs),
    unresolved_old_references=[r for r in old_refs if 'REVIEW' in r['migration_result']]))
baseline=json.loads((OUT/'baseline.json').read_text())
labels={'owned_source':'自有源码','tests':'测试','docs_other_text':'文档及其他文本','data_config_registry':'数据、配置与注册表','third_party':'第三方文本及许可','external_material':'外部提案原件','binary':'二进制资产'}
table=['| 分类 | 原文件数 → 现文件数 | 原物理行 → 现物理行 | 净行数 |','|---|---:|---:|---:|']
for key,label in labels.items():
    before=baseline['categories'][key]; after=totals[key]
    table.append(f"| {label} | {before['files']} → {after['files']} | {before['lines']:,} → {after['lines']:,} | {after['lines']-before['lines']:+,} |")
table += ['',f"在册文件 **491 → {len(paths)}**，目录 **47 → {len(dirs)}**（排除本批审计目录为 {len(product_dirs)}）；顶层目录 **13 → 12**。本批审计证据另外 {audit_count['files']} 个文件，不计入上表产品类别；详见 after.json。"]
p=OUT/'DELIVERY.md'
if p.exists():
    text=p.read_text(); text=re.sub(r'<!-- METRICS_START -->.*?<!-- METRICS_END -->','<!-- METRICS_START -->\n'+'\n'.join(table)+'\n<!-- METRICS_END -->',text,flags=re.S);p.write_text(text)
print(json.dumps(dict(categories=totals,files=len(paths),directories=len(dirs),audit=dict(audit_count),
                     cycles=cycles,forbidden=violations,old_references_to_review=sum('REVIEW' in r['migration_result'] for r in old_refs)),ensure_ascii=False))
