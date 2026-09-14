"""Reproduce the bounded source/consumer inventory; never scan private runtime roots."""
import ast
import collections
import csv
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
SCOPE=json.loads((OUT/'scope.json').read_text())
INTEGRATED=set(SCOPE.get('integration',{}).get('paths',[]))

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def table(name,fields,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(fields);w.writerows(rows)

def main():
    before={p:git('show',SCOPE['baseline']+':'+p) for p in git('ls-tree','-r','--name-only','-z',SCOPE['baseline']).decode().strip('\0').split('\0')}
    paths=set(git('ls-files','-co','--exclude-standard','-z').decode().strip('\0').split('\0'))
    after={p:(ROOT/p).read_bytes() for p in paths if (ROOT/p).is_file()}
    terms=('model_assets','model-assets','/api/model-assets','import_candidate','read_manifest','permitted_license','loadModel','createModelLoad','mountSceneModels','atomic_write','loadSceneData')
    refs=[]
    for p,body in sorted(after.items()):
        if p.startswith(('docs/reviews/','docs/archive/','web/assets/vendor/')) or p=='framework/repository_manifest.json':continue
        try:lines=body.decode().splitlines()
        except UnicodeError:continue
        for number,line in enumerate(lines,1):
            for term in terms:
                if term not in line:continue
                if term=='atomic_write' and p!='src/inresearch/materials/model_assets.py':
                    result='existing consumer keeps two-argument replacement semantics; full unit suite required'
                elif p.startswith('tests/'):
                    result='regression consumer; real execution recorded in DELIVERY/local run evidence'
                elif p.startswith(('docs/','framework/')):
                    result='current operational/specification consumer; old automatic adoption text retired where in scope'
                else:result='shared visual-input authority or lifecycle consumer; source location retained'
                refs.append([term,p,number,line.strip()[:750],result])
    table('public-consumers.csv',['implementation_or_endpoint','consumer','line','reference','migration_result'],refs)
    for p in OUT.iterdir():
        if p.is_file():after[str(p.relative_to(ROOT))]=p.read_bytes()
    table('file-results.csv',['path','action','target','planned','result'],[
      [p,'removed' if p not in after else 'added' if p not in before else 'modified' if before[p]!=after[p] else 'retained',p,
       p in SCOPE['changed'] or p in INTEGRATED or p.startswith(str(OUT.relative_to(ROOT))),
       'authority/lifecycle consumer migrated; see public contracts' if p in SCOPE['changed'] else 'dated evidence' if p.startswith(str(OUT.relative_to(ROOT))) else 'integrated unchanged from upstream '+SCOPE['integration']['commit'] if p in INTEGRATED else 'outside scope; preserved']
      for p in sorted(set(before)|set(after))])
    tree=ast.parse((ROOT/'docs/reviews/2026-09-13/deep-read/audit.py').read_text());ns=dict(Path=Path,collections=collections)
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('category','stats')],type_ignores=[]),'stats','exec'),ns)
    for p in OUT.iterdir():
        if p.is_file():after[str(p.relative_to(ROOT))]=p.read_bytes()
    (OUT/'statistics-after.json').write_text(json.dumps({'baseline':SCOPE['baseline'],'before':ns['stats'](before),'after':ns['stats'](after),'note':'Same physical-line categories; tests/docs/data/audit separate. Git source only. Generated inventories measured before final self-refresh.'},indent=2)+'\n')
    print(json.dumps({'files':len(after),'public_references':len(refs),'unplanned_application_changes':[p for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p) and p not in SCOPE['changed'] and p not in INTEGRATED and not p.startswith(str(OUT.relative_to(ROOT)))]}))

if __name__=='__main__':main()
