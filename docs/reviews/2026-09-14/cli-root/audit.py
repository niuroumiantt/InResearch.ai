"""Dated CLI audit: preserve before evidence, enumerate calls and classify all files."""
import ast, collections, csv, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SCOPE = json.loads((OUT/'scope.json').read_text())
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def dump(name, value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def table(name, columns, rows):
    with (OUT/name).open('w',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(columns);writer.writerows(rows)
def snapshot():
    return {p:git('show',SCOPE['baseline']+':'+p) for p in git('ls-tree','-r','--name-only','-z',SCOPE['baseline']).decode().strip('\0').split('\0')}
def current():
    return {p:(ROOT/p).read_bytes() for p in sorted(set(git('ls-files','-co','--exclude-standard','-z').decode().strip('\0').split('\0'))) if (ROOT/p).is_file()}
def references(files):
    rows=[]
    for p,b in sorted(files.items()):
        if p.startswith(('docs/reviews/','docs/archive/','web/assets/vendor/')) or p=='framework/repository_manifest.json': continue
        try: lines=b.decode().splitlines()
        except UnicodeError: continue
        for n,line in enumerate(lines,1):
            if any(term in line for term in ('manage.py','interfaces.cli','interfaces import cli','-m inresearch')):
                kind='launch/command reference' if 'manage.py' in line or '-m inresearch' in line else 'direct import'
                rows.append([p,n,kind,line.strip()[:900],'retained invocation; local options belong after command'])
            elif p in ('tests/unit/test_commands.py','tests/unit/test_m4_triage.py') and 'cli.main(' in line:
                rows.append([p,n,'direct call',line.strip()[:900],'common root or child-local root preserved; explicit unsupported global root rejected'])
    return rows
def statistics(files):
    tree=ast.parse((ROOT/'docs/reviews/2026-09-13/deep-read/audit.py').read_text());ns=dict(Path=Path,collections=collections)
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('category','stats')],type_ignores=[]),'stats','exec'),ns)
    return ns['stats'](files)
def main():
    before=snapshot(); files=before if '--before' in sys.argv else current()
    mode='before' if '--before' in sys.argv else 'after'
    table('consumers-'+mode+'.csv',['path','line','kind','reference','migration_result'],references(files))
    if mode=='before':
        mapping=next(ast.literal_eval(n.value) for n in ast.parse(before['src/inresearch/interfaces/cli.py']).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='COMMANDS' for t in n.targets))
        rows=[]
        for command,module in sorted(mapping.items()):
            path='src/'+module.replace('.','/')+'.py'
            body=before[path].decode(); mainline=next(n.lineno for n in ast.parse(body).body if isinstance(n,ast.FunctionDef) and n.name=='main')
            options=' | '.join(line.strip() for line in body.splitlines() if 'add_argument' in line and any(word in line for word in ('root','dir','path')))
            rows.append([command,module,path,mainline,options,'retain child-local arguments; reject explicit global root before dispatch'])
        table('dispatch.csv',['command','module','path','main_line','directory_options','migration_result'],rows)
        paths=set(before)|{str(p.relative_to(ROOT)) for p in OUT.iterdir()}
        table('file-plan.csv',['path','action','destination','reason'],[[p,'modify' if p in SCOPE['changed'] else 'add audit' if p not in before else 'retain',p,'CLI interface/contract/test' if p in SCOPE['changed'] else 'dated evidence' if p.startswith(str(OUT.relative_to(ROOT))) else 'outside this bounded change; preserved'] for p in sorted(paths)])
        dump('statistics-before.json',{'baseline':SCOPE['baseline'],**statistics(before)})
        print(json.dumps({'baseline_files':len(before),'delegated_commands':len(mapping),'reference_sites':len(references(files))}))
    else:
        changed=[p for p in sorted(set(before)|set(files)) if before.get(p)!=files.get(p)]
        unplanned=[p for p in changed if p not in SCOPE['changed'] and not p.startswith(str(OUT.relative_to(ROOT)))]
        table('file-results.csv',['path','action','destination','result'],[[p,'removed' if p not in files else 'added' if p not in before else 'modified' if p in changed else 'retained',p,'changed within declared scope' if p in changed else 'unchanged bytes'] for p in sorted(set(before)|set(files))])
        dump('statistics-after.json',{'baseline':SCOPE['baseline'],'before':statistics(before),'after':statistics(current()),'note':'Physical lines; source/tests/docs/data/audit separate. Runtime originals and private files excluded; generated manifests measured before final self-refresh.'})
        print(json.dumps({'reference_sites':len(references(files)),'unplanned':unplanned}))
        if unplanned:raise SystemExit(1)
if __name__=='__main__':main()
