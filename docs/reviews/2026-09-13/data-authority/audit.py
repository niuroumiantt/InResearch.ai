"""Dated evidence generation; writes only this review's inventory artifacts."""
import ast
import collections
import csv
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = '9b073ac3cee08a7e9509d9ccf84d0a683e9fc95b'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def table(name, fields, rows):
    with (OUT / name).open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(fields); writer.writerows(rows)


def statistics(files):
    # Preserve the preceding phases' frozen categories; execute no historical script.
    path = OUT.parent / 'deep-read/audit.py'
    tree = ast.parse(path.read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('category', 'stats')]
    scope = dict(Path=Path, collections=collections)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), scope)
    return scope['stats'](files)


def main():
    old = {p: git('show', BASE + ':' + p) for p in git('ls-tree', '-r', '--name-only', '-z', BASE).decode().strip('\0').split('\0')}
    paths = sorted(set(git('ls-files', '-co', '--exclude-standard', '-z').decode().strip('\0').split('\0')))
    files = {p: (ROOT / p).read_bytes() for p in paths if (ROOT / p).is_file()}
    scope = json.loads((OUT / 'scope.json').read_text())
    changed = set(scope['changed'] + scope['new'])
    changed.add('src/inresearch/storage/files.py')  # reused public transaction primitives
    definitions, trees = {}, {}
    for p, body in files.items():
        if not p.endswith('.py') or p.startswith('docs/'): continue
        tree = ast.parse(body); trees[p] = tree
        if not p.startswith('src/') or p not in changed: continue
        module = p[4:-3].replace('/', '.')
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith('_'):
                definitions[module + '.' + node.name] = (p, node.lineno)
    references, layouts = [], []
    for p, tree in trees.items():
        module = p[4:-3].replace('/', '.') if p.startswith('src/') else ''
        aliases = {n.name: module + '.' + n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                aliases.update({a.asname or a.name: node.module + '.' + a.name for a in node.names})
            if isinstance(node, ast.Import):
                aliases.update({a.asname or a.name.split('.')[0]: a.name if a.asname else a.name.split('.')[0] for a in node.names})
        def resolve(node):
            if isinstance(node, ast.Name): return aliases.get(node.id, node.id)
            if isinstance(node, ast.Attribute): return resolve(node.value) + '.' + node.attr
            return ''
        seen = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Name, ast.Attribute, ast.Call)): continue
            target = resolve(node.func if isinstance(node, ast.Call) else node)
            if isinstance(node, ast.Call) and target == 'inresearch.storage.layout.workspace_path':
                owners = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= node.lineno <= n.end_lineno]
                owner = min(owners, key=lambda n: n.end_lineno - n.lineno).name if owners else '<module defaults>'
                layouts.append([p, node.lineno, owner, ast.unparse(node), 'same resolver for all transports; authoring has no runtime override'])
            if target not in definitions or (target, node.lineno) in seen: continue
            seen.add((target, node.lineno))
            references.append([target, *definitions[target], p, node.lineno, 'resolved Python reference', 'migrated; existing API identity retained except explicitly retired names'])
    # Registered CLI entry points use importlib rather than direct Python calls.
    cli = ROOT / 'src/inresearch/interfaces/cli.py'
    for line, text in enumerate(cli.read_text().splitlines(), 1):
        for target, (p, number) in definitions.items():
            if target.endswith('.main') and repr(target[:-5]) in text:
                references.append([target, p, number, str(cli.relative_to(ROOT)), line, 'registered CLI main', 'same command; storage is a new command'])
    observed = {row[0] for row in references}
    for target, (p, number) in definitions.items():
        if target not in observed:
            references.append([target, p, number, '', '', 'no statically resolved consumer', 'review entry/HTTP inheritance and external usage separately; not proof of unused code'])
    table('public-consumers.csv', ['implementation', 'definition', 'definition_line', 'consumer', 'line', 'evidence', 'result'], sorted(references))
    table('storage-consumers.csv', ['consumer', 'line', 'owner', 'call', 'result'], sorted(layouts))
    refs = []
    terms = ('workspace_path', 'storage_contract', 'INRESEARCH_RUNTIME_ROOT', 'review_suggestions', 'review_marked', 'mark_findings_needs_review')
    for p, body in sorted(files.items()):
        if p.startswith(('docs/reviews/', 'docs/archive/')): continue
        try: lines = body.decode().splitlines()
        except UnicodeError: continue
        refs.extend([p, i, line.strip()[:600]] for i, line in enumerate(lines, 1) if any(t in line for t in terms))
    table('consumers-after.csv', ['path', 'line', 'reference'], refs)
    # List evidence artifacts too, so the results table covers its own generated set.
    for p in OUT.iterdir():
        if p.is_file(): files[str(p.relative_to(ROOT))] = p.read_bytes()
    results = []
    for p in sorted(set(old) | set(files)):
        action = 'removed' if p not in files else 'added' if p not in old else 'modified' if files[p] != old[p] else 'retained'
        reason = 'unchanged source/data/history' if action == 'retained' else 'dated evidence' if p.startswith('docs/reviews/') else 'contract and consumer migration; see DELIVERY'
        if p in ('src/inresearch/adapters/acquisition.py', 'src/inresearch/adapters/news_sync.py'):
            reason = 'reviewed; these use the independent Reader root, not website runtime; no migration required'
        results.append([p, action, p, reason])
    table('file-results.csv', ['path', 'action', 'target', 'reason'], results)
    for name in ('file-results.csv', 'statistics-after.json'):
        files[str((OUT / name).relative_to(ROOT))] = (OUT / name).read_bytes() if (OUT / name).exists() else b''
    (OUT / 'statistics-after.json').write_text(json.dumps(dict(baseline=BASE, before=statistics(old), after=statistics(files),
        scope='Git source only; runtime originals and databases excluded; audit artifact physical line totals are a pre-final snapshot'), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(public_implementations=len(definitions), resolved_reference_rows=len(references), path_consumers=len(layouts), files=len(files))))


if __name__ == '__main__':
    main()
