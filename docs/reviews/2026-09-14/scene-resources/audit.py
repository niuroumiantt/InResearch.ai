"""Dated scene resource audit; inventories exact baseline and public consumers."""
import ast, collections, csv, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SCOPE = json.loads((OUT / 'scope.json').read_text())

def git(*args): return subprocess.check_output(['git', *args], cwd=ROOT)
def snapshot(ref):
    paths = git('ls-tree', '-r', '--name-only', '-z', ref).decode().strip('\0').split('\0')
    return {path: git('show', ref + ':' + path) for path in paths}
def current():
    paths = git('ls-files', '-co', '--exclude-standard', '-z').decode().strip('\0').split('\0')
    return {path: (ROOT / path).read_bytes() for path in paths if path and (ROOT / path).is_file()}
def table(name, columns, rows):
    with (OUT / name).open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n'); writer.writerow(columns); writer.writerows(rows)
def stats(files):
    tree = ast.parse((ROOT / 'docs/reviews/2026-09-13/deep-read/audit.py').read_text())
    namespace = {'Path': Path, 'collections': collections}
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ('category', 'stats')]
    exec(compile(ast.Module(body=body, type_ignores=[]), 'stats', 'exec'), namespace)
    return namespace['stats'](files)
def references(files):
    terms = ('EXRLoader', 'PMREMGenerator', 'CanvasTexture', 'TextureLoader', 'scene.environment',
             'proceduralEnv', 'ctex(', 'pagehide', 'scene-resources')
    rows = []
    for path, raw in sorted(files.items()):
        if path.startswith(('docs/reviews/', 'docs/archive/', 'web/assets/vendor/')): continue
        try: lines = raw.decode().splitlines()
        except UnicodeError: continue
        for number, line in enumerate(lines, 1):
            for term in terms:
                if term in line:
                    result = 'planned shared owner consumer' if path in ('web/pages/bom3d.html', 'web/pages/rack3d.html') else 'direct contract regression' if path.startswith('tests/') else 'retained separate lifetime' if path in ('web/pages/bake.html', 'web/pages/compare.html') else 'route, source record or operational reference'
                    rows.append([term, path, number, line.strip()[:900], result])
    return rows

before = snapshot(SCOPE['baseline'])
if '--before' in sys.argv:
    planned = set(SCOPE['changed'])
    additions = {str(path.relative_to(ROOT)) for path in OUT.iterdir()}
    paths = sorted(set(before) | planned | additions)
    table('file-plan.csv', ['path', 'action', 'destination', 'reason'], [
        [path, 'add' if path not in before else 'modify' if path in planned else 'retain', path,
         'shared resource boundary or verification' if path in planned else 'dated audit evidence' if path.startswith(str(OUT.relative_to(ROOT))) else 'outside bounded change; bytes and authority preserved']
        for path in paths])
    refs = references(before)
    table('consumers-before.csv', ['implementation', 'consumer', 'line', 'reference', 'migration_result'], refs)
    (OUT / 'statistics-before.json').write_text(json.dumps({'baseline': SCOPE['baseline'], **stats(before)}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'baseline_files': len(before), 'reference_sites': len(refs), 'planned_paths': len(planned)}))
else:
    after = current(); refs = references(after)
    table('consumers-after.csv', ['implementation', 'consumer', 'line', 'reference', 'migration_result'], refs)
    planned = set(SCOPE['changed']); inherited = set(SCOPE.get('inherited', [])); audit_prefix = str(OUT.relative_to(ROOT))
    changed = [path for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]
    unplanned = [path for path in changed if path not in planned and path not in inherited and not path.startswith(audit_prefix)]
    table('file-results.csv', ['path', 'action', 'destination', 'result'], [
        [path, 'removed' if path not in after else 'added' if path not in before else 'modified' if path in changed else 'retained', path,
         'changed within declared scope' if path in changed and path in planned else 'inherited from integrated main; preserved' if path in changed and path in inherited else 'changed dated audit evidence' if path in changed else 'unchanged bytes'] for path in sorted(set(before) | set(after))])
    (OUT / 'statistics-after.json').write_text(json.dumps({'baseline': SCOPE['baseline'], 'before': stats(before), 'after': stats(after), 'note': 'Physical lines; source/tests/docs/data/audit separated. Private/runtime/original files excluded.'}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'reference_sites': len(refs), 'unplanned': unplanned}))
    if unplanned: raise SystemExit(1)
