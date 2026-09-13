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

if __name__ == '__main__':
    inventory('--after' in sys.argv)
