"""Dated, read-only source inventory; evidence files are the only writes."""
import ast, collections, csv, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = '083e3b10c4208cca40d8ce3394928e6691dc5cae'
CHANGED = '''src/inresearch/storage/catalog.py
src/inresearch/workflow/reading_stages.py
src/inresearch/workflow/deep_read.py
src/inresearch/interfaces/deep_read.py
src/inresearch/interfaces/reader.py
src/inresearch/delivery/reading_packet.py
src/inresearch/materials/text_similarity.py
tests/unit/deep_read_fixtures.py
tests/unit/test_deep_read.py
tests/unit/test_deep_read_transactions.py
tests/unit/test_text_similarity.py
tests/unit/test_fact_contract.py
framework/CURRENT.md
framework/current_state.json
framework/verification_contract.json
framework/repository_manifest.json
framework/04_reading_scoring_standard.md
framework/08_model_execution.md
framework/09_software_contracts.md
docs/M4_TRIAGE_TASK.md
docs/local_reader/SPARK_OPERATIONS.md
docs/DECISIONS.md
docs/REPOSITORY_REGISTER.md
src/inresearch/README.md'''.splitlines()
NEW = ['src/inresearch/materials/reading_artifacts.py', 'src/inresearch/workflow/reading_results.py', 'tests/unit/test_reading_results.py']
TERMS = ('ReadingStages', 'ReadingArtifacts', 'ReadingResults', 'verify_seal', 'validate_report',
         'artifact_path', 'read_documents', 'remember_read', 'documents_read', 'already_read',
         'eligible_unread', 'l2_read.jsonl', 'current_readings', 'processed_documents',
         'remember_processing', 'reading_results', 'reading_artifacts')

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def table(name, header, rows):
    with (OUT/name).open('w') as stream:
        writer = csv.writer(stream, lineterminator='\n'); writer.writerow(header); writer.writerows(rows)

def stats(files):
    # Same frozen classification used by the preceding L2 phase; no script side effects.
    path = OUT.parent/'deep-read/audit.py'
    tree = ast.parse(path.read_text()); scope = dict(Path=Path, collections=collections)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('category', 'stats')]
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), scope)
    return scope['stats'](files)

def dump(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def inventory(after=False):
    old = {p:git('show', BASE+':'+p) for p in git('ls-tree','-r','--name-only','-z',BASE).decode().strip('\0').split('\0')}
    files = {p:(ROOT/p).read_bytes() for p in git('ls-files','--cached','--others','--exclude-standard','-z').decode().strip('\0').split('\0') if (ROOT/p).is_file()} if after else old
    paths = sorted(set(old)|set(files)|set(NEW)|{str(p.relative_to(ROOT)) for p in OUT.iterdir()})
    rows = []
    for p in paths:
        action = ('removed' if p not in files else 'added' if p not in old else 'modified' if files[p]!=old[p] else 'retained') if after else ('modify' if p in CHANGED else 'add' if p not in old else 'retain')
        rows.append([p,action,p,'contract / consumer migration' if p in CHANGED+NEW else 'dated evidence' if p.startswith(str(OUT.relative_to(ROOT))) else 'source/data/history retained'])
    table('file-results.csv' if after else 'file-plan.csv',['path','action','target','reason'],rows)
    refs=[]
    for p,b in sorted(files.items()):
        if p.startswith(('docs/archive/','docs/reviews/')): continue
        try: lines=b.decode().splitlines()
        except UnicodeError: continue
        refs += [[p,i,line.strip()] for i,line in enumerate(lines,1) if any(term in line for term in TERMS)]
    table('consumers-after.csv' if after else 'consumers-before.csv',['path','line','reference'],refs)
    dump('statistics-after.json' if after else 'statistics-before.json',dict(baseline=BASE,**stats(files)))
    if after:
        public=[]; calls=[]
        for path,body in files.items():
            if not path.endswith('.py') or path.startswith('docs/'): continue
            tree=ast.parse(body)
            for node in ast.walk(tree):
                if isinstance(node,ast.Call):
                    target=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else None
                    if target: calls.append((target,path,node.lineno,ast.unparse(node.func)))
                elif isinstance(node,ast.Attribute):
                    calls.append((node.attr,path,node.lineno,ast.unparse(node)))
            if path not in CHANGED+NEW or not path.startswith('src/'):continue
            for node in tree.body:
                if isinstance(node,ast.FunctionDef) and not node.name.startswith('_'):
                    public.append((path,node.name,node.name,node.lineno))
                if isinstance(node,ast.ClassDef):
                    public.append((path,node.name,node.name,node.lineno))
                    public += [(path,node.name+'.'+n.name,n.name,n.lineno) for n in node.body
                               if isinstance(n,ast.FunctionDef) and not n.name.startswith('_')]
        rows=[]
        for path,symbol,name,line in sorted(public):
            matches=sorted(set((consumer,location,call) for target,consumer,location,call in calls if target==name))
            rows += [[path,symbol,line,consumer,location,call,'statically observable name/attribute; receiver review in DELIVERY'] for consumer,location,call in matches]
            if not matches:rows.append([path,symbol,line,'none observed','','','no static calls; see operational references'])
        table('public-consumers.csv',['implementation','symbol','definition_line','consumer','line','call','resolution'],rows)
        def tests(items):
            result=set()
            for path,b in items.items():
                if not path.startswith('tests/unit/') or not path.endswith('.py'):continue
                classes={c.name:c for c in ast.parse(b).body if isinstance(c,ast.ClassDef)}
                def methods(cls):
                    own={n.name for n in cls.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
                    for base in cls.bases:
                        if isinstance(base,ast.Name) and base.id in classes:own.update(methods(classes[base.id]))
                    return own
                for c in classes.values():result.update(path+'::'+c.name+'.'+name for name in methods(c))
            return result
        previous,current=tests(old),tests(files);renames=json.loads((OUT/'test-renames.json').read_text())
        rows=[]
        for identity in sorted(previous):
            name=identity.rsplit('.',1)[1];target=identity.rsplit('.',1)[0]+'.'+renames.get(name,name)
            rows.append([identity,target,'preserved' if identity==target and target in current else 'renamed with processing semantics' if target in current else 'MISSING'])
        table('test-migration.csv',['before','after','result'],rows)
        dump('test-migration.json',dict(before=len(previous),preserved_or_renamed=sum(r[2]!='MISSING' for r in rows),
             renamed=sum(r[2]=='renamed with processing semantics' for r in rows),added=sorted(current-{r[1] for r in rows}),missing=[r for r in rows if r[2]=='MISSING']))

if __name__ == '__main__':
    inventory('--after' in sys.argv)
