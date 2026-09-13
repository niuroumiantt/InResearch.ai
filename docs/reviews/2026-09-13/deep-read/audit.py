"""Reproduce this dated audit without changing earlier evidence: --before or --after."""
import ast, collections, csv, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
BASE='465f8defe21e9fe7a7a75ad87bfeaa07e10e2fab'
SOURCE='src/inresearch/workflow/deep_read.py'
NEW=['tests/unit/deep_read_fixtures.py','src/inresearch/interfaces/deep_read.py','src/inresearch/materials/reading_policy.py','src/inresearch/materials/text_similarity.py','src/inresearch/knowledge/provenance.py','src/inresearch/workflow/reading_gaps.py','tests/unit/test_deep_read.py','tests/unit/test_fact_contract.py','tests/unit/test_text_similarity.py','tests/unit/test_deep_read_transactions.py']
INTEGRATED='077471c'
CHANGED={SOURCE,'src/inresearch/knowledge/fact_contract.py','src/inresearch/interfaces/cli.py','src/inresearch/README.md','src/inresearch/delivery/reading_packet.py','framework/09_software_contracts.md','framework/CURRENT.md','framework/current_state.json','framework/verification_contract.json','framework/repository_manifest.json','docs/REPOSITORY_REGISTER.md','docs/M4_TRIAGE_TASK.md','docs/DECISIONS.md'}
REMOVED={'tests/unit/test_m4_l2.py'}
PURE={'self_authored','restricted','unattributed','gap_label','document_year','matches'}
SIMILAR={'text_fingerprint','text_sketch','sketch_overlap','fingerprints','sketches','remember_fingerprint','already_read_with_same_text','packed_not_read_with_same_text','near_twins'}
PROVENANCE={'cache_key_to_sha','owing_provenance','sources_index'}
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def before():return {p:git('show',BASE+':'+p) for p in git('ls-tree','-r','--name-only','-z',BASE).decode().strip('\0').split('\0')}
def current():return {p:(ROOT/p).read_bytes() for p in sorted(set(git('ls-files','--cached','--others','--exclude-standard','-z').decode().strip('\0').split('\0'))) if (ROOT/p).is_file()}
def table(name,rows):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def dump(name,data):(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def category(p,b):
 try:
  if b'\0' in b:return 'binary'
  b.decode()
 except UnicodeError:return 'binary'
 if p.startswith('docs/reviews/'):return 'audit_artifacts'
 if p.startswith('docs/inbox/framework_proposals/'):return 'external_material'
 if '/vendor/' in p or Path(p).name.startswith('Inter'):return 'third_party'
 if p.startswith('tests/'):return 'tests'
 if Path(p).suffix in {'.py','.js','.cjs','.mjs','.css','.html','.sh'}:return 'owned_source'
 if Path(p).suffix in {'.json','.jsonl','.csv','.tsv'}:return 'data_config_registry'
 return 'docs_other_text'
def stats(files):
 counts=collections.defaultdict(lambda:dict(files=0,lines=0));dirs=set()
 for p,b in files.items():
  c=category(p,b);counts[c]['files']+=1
  if c!='binary':counts[c]['lines']+=len(b.decode().splitlines())
  dirs.update(str(x) for x in Path(p).parents if str(x)!='.')
 return dict(categories=counts,files=len(files),directories=len(dirs))
def references(files):
 rows=[]
 for p,b in sorted(files.items()):
  if p.startswith(('docs/reviews/','docs/archive/')):continue
  if p.endswith('.py'):
   t=ast.parse(b)
   for n in ast.walk(t):
    if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='L2':
     rows.append(dict(consumer=p,line=n.lineno,symbol=n.attr,kind='direct L2 member'))
  try:lines=b.decode().splitlines()
  except UnicodeError:continue
  for i,line in enumerate(lines,1):
   if any(x in line for x in ('deep_read','deep-read','m4_l2','l2_read.jsonl','l2_text_md5.jsonl','metric_gaps.jsonl')):
    rows.append(dict(consumer=p,line=i,symbol=line.strip()[:250],kind='import, registered entry, path or operational reference'))
 return rows
old=before()
if '--before' in sys.argv:
 files=sorted(set(old)|set(NEW)|{str(p.relative_to(ROOT)) for p in OUT.iterdir()})
 rows=[]
 for p in files:
  action='remove/split tests' if p in REMOVED else 'add' if p not in old else 'modify' if p in CHANGED else 'retain'
  reason='responsibility migration or contract consumer' if action!='retain' else 'outside this change; source/data/history retained'
  if p.startswith(str(OUT.relative_to(ROOT))):reason='dated evidence; not a current policy'
  rows.append(dict(path=p,action=action,destination='test_deep_read.py;test_fact_contract.py;test_text_similarity.py' if p in REMOVED else p,reason=reason))
 table('file-plan.csv',rows)
 table('consumers-before.csv',references(old))
 funcs=[]
 for n in ast.parse(old[SOURCE]).body:
  if not isinstance(n,ast.FunctionDef):continue
  target='materials.reading_policy' if n.name in PURE else 'materials.text_similarity' if n.name in SIMILAR else 'knowledge.provenance' if n.name in PROVENANCE else 'interfaces.deep_read + explicit use case' if n.name.startswith('cmd_') or n.name=='main' else 'workflow.deep_read.DeepRead'
  if n.name=='fact_write':target='removed; explicit transaction inside use case'
  funcs.append(dict(symbol=n.name,line=n.lineno,lines=n.end_lineno-n.lineno+1,target=target))
 table('functions-before.csv',funcs)
 dump('statistics-before.json',dict(baseline=BASE,method='Physical lines; generated audit artifacts and runtime originals are separate',**stats(old)))
elif '--after' in sys.argv:
 new=current(); table('consumers-after.csv',references(new))
 table('file-results.csv',[dict(path=p,action='removed' if p not in new else 'added' if p not in old else 'modified' if old[p]!=new[p] else 'retained',planned=p in CHANGED or p in NEW or p in REMOVED or p.startswith(str(OUT.relative_to(ROOT))),result='see public-contracts and delivery; history/originals not deleted' if old.get(p)!=new.get(p) else 'unchanged') for p in sorted(set(old)|set(new))])
 upstream={p:git('show',INTEGRATED+':'+p) for p in git('ls-tree','-r','--name-only','-z',INTEGRATED).decode().strip('\0').split('\0')}
 table('integration-files.csv',[dict(path=p,upstream_change=p not in old or old.get(p)!=upstream.get(p),our_change=upstream.get(p)!=new.get(p),disposition='unchanged from integrated main' if upstream.get(p)==new.get(p) else 'see contract migration') for p in sorted(set(upstream)|set(new))])
 dump('statistics-after.json',dict(baseline=BASE,integration_baseline=INTEGRATED,before=stats(old),integrated=stats(upstream),after=stats(current())))
else:raise SystemExit('Use --before once before implementation, or --after after review')
