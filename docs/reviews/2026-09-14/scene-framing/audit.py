"""Inventory tracked source boundaries, preserving pre-change classifications."""
import ast
import collections
import csv
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
SCOPE=json.loads((OUT/'scope.json').read_text())
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def table(name,columns,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(columns);w.writerows(rows)
def main():
    before={p:git('show',SCOPE['baseline']+':'+p) for p in git('ls-tree','-r','--name-only','-z',SCOPE['baseline']).decode().strip('\0').split('\0')}
    paths=set(git('ls-files','-co','--exclude-standard','-z').decode().strip('\0').split('\0'))
    after={p:(ROOT/p).read_bytes() for p in paths if (ROOT/p).is_file()}
    inherited=set(SCOPE.get('inherited',[])); planned=set(SCOPE['changed'])
    refs=[]
    terms=['scene-view','visibleBounds','fitPerspective','createViewport','mountSceneView','sceneView','sceneModels','createPartInspector','inspector.','objects:()','barren_cohorts','.cohort(','.is_cohort(']
    for p,body in sorted(after.items()):
        if p.startswith(('docs/reviews/','docs/archive/','web/assets/vendor/')) or p=='framework/repository_manifest.json':continue
        try:lines=body.decode().splitlines()
        except UnicodeError:continue
        for n,line in enumerate(lines,1):
            for term in terms:
                if term in line:
                    result='migrated shared view/ownership consumer' if p.startswith('web/') else 'actual regression consumer; execution separately recorded' if p.startswith('tests/') else 'current rule/operational reference'
                    if term in ['barren_cohorts','.cohort(','.is_cohort(']:result='inherited PR 180 numeric-processing queue consumer; original behavior retained, not framing verification'
                    refs.append([term,p,n,line.strip()[:800],result])
    table('public-consumers.csv',['implementation','consumer','line','reference','migration_result'],refs)
    table('file-results.csv',['path','action','target','reason'],[[p,'removed' if p not in after else 'added' if p not in before else 'modified' if before[p]!=after[p] else 'retained',p,'framing responsibility or verification migrated' if p in planned else 'inherited upstream change; preserved' if p in inherited else 'dated audit evidence' if p.startswith(str(OUT.relative_to(ROOT))) else 'outside bounded change; preserved'] for p in sorted(set(before)|set(after))])
    for p in OUT.iterdir():
        if p.is_file():after[str(p.relative_to(ROOT))]=p.read_bytes()
    tree=ast.parse((ROOT/'docs/reviews/2026-09-13/deep-read/audit.py').read_text());ns=dict(Path=Path,collections=collections)
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('category','stats')],type_ignores=[]),'stats','exec'),ns)
    (OUT/'statistics-after.json').write_text(json.dumps({'baseline':SCOPE['baseline'],'before':ns['stats'](before),'after':ns['stats'](after),'note':'Git source only; physical lines; tests/docs/data/audit separate. Before final inventory self-refresh, not runtime/originals.'},indent=2)+'\n')
    unplanned=[p for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p) and p not in planned and p not in inherited and not p.startswith(str(OUT.relative_to(ROOT)))]
    print(json.dumps({'files':len(after),'references':len(refs),'unplanned':unplanned}))
    if unplanned:raise SystemExit(1)
if __name__=='__main__':main()
