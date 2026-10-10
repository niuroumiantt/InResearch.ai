"""Read-only source inventory. Possible orphans are review hints, never deletions."""
import ast
from collections import defaultdict,Counter
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[4]
paths=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
modules={}
for p in paths:
 if p.startswith('src/inresearch/') and p.endswith('.py'):
  name='.'.join(Path(p).relative_to('src').with_suffix('').parts)
  if name.endswith('.__init__'):name=name[:-9]
  modules[name]=p
edges=defaultdict(set);missing=[];sizes=[];hashes=defaultdict(list)
for name,p in modules.items():
 text=(ROOT/p).read_text();tree=ast.parse(text,filename=p);sizes.append((len(text.splitlines()),p))
 if Path(p).name!='__init__.py':hashes[hashlib.sha256(text.encode()).hexdigest()].append(p)
 for n in ast.walk(tree):
  refs=[]
  if isinstance(n,ast.Import):refs=[a.name for a in n.names]
  if isinstance(n,ast.ImportFrom) and n.module:
   refs=[n.module]
   refs.extend(n.module+'.'+a.name for a in n.names if n.module+'.'+a.name in modules)
  for ref in refs:
   if ref.startswith('inresearch.'):
    if ref not in modules:missing.append({'file':p,'line':n.lineno,'module':ref})
    else:edges[name].add(ref)
visited=set();active=set();stack=[];cycles=set()
def walk(n):
 if n in active:
  cycle=stack[stack.index(n):];i=cycle.index(min(cycle));cycles.add(tuple(cycle[i:]+cycle[:i]));return
 if n in visited:return
 active.add(n);stack.append(n)
 for x in sorted(edges[n]):walk(x)
 stack.pop();active.remove(n);visited.add(n)
for n in sorted(modules):walk(n)
refs=Counter(x for v in edges.values() for x in v)
value={'baseline':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'python_modules':len(modules),'owned_web_files':sum(p.startswith(('web/components/','web/themes/','web/pages/')) for p in paths),
 'largest_modules':[{'lines':n,'path':p} for n,p in sorted(sizes,reverse=True)[:10]],
 'missing_internal_imports':missing,'duplicate_nonempty_modules':[v for v in hashes.values() if len(v)>1],
 'import_cycles_including_lazy_imports':[list(c) for c in sorted(cycles)],
 'unreferenced_from_core':[modules[n] for n in sorted(modules) if refs[n]==0 and not modules[n].endswith('__init__.py')],
 'limits':['AST includes function-local imports; cycles are not evidence of load failure.',
 'CLI, tests, deployments and dynamic imports are separate consumers; unreferenced_from_core does not prove dead code.',
 'No runtime database, original, secret or file was deleted.']}
print(json.dumps(value,ensure_ascii=False,indent=2))
