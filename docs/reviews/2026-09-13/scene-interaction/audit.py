"""Frozen-scope review inventory; no runtime or application writes."""
import ast
import collections
import csv
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SCOPE = json.loads((OUT / 'scope.json').read_text())


def table(name, fields, rows):
    with (OUT / name).open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n'); writer.writerow(fields); writer.writerows(rows)


def main():
    def git(*args): return subprocess.check_output(['git', *args], cwd=ROOT)
    before = {p: git('show', SCOPE['baseline'] + ':' + p) for p in git('ls-tree', '-r', '--name-only', '-z', SCOPE['baseline']).decode().strip('\0').split('\0')}
    paths = sorted(set(git('ls-files', '-co', '--exclude-standard', '-z').decode().strip('\0').split('\0')))
    after = {p: (ROOT / p).read_bytes() for p in paths if (ROOT / p).is_file()}
    terms = ('createScenePicking', 'createSceneMotion', 'createPartInspector', 'materialFor', 'userData.orig', 'sliderMotion', 'cameraMotion', 'setDim', 'installStageControl', 'scene-picking.js', 'scene-motion.js')
    refs = []
    for p, body in sorted(after.items()):
        if p.startswith(('docs/reviews/', 'docs/archive/')): continue
        try: lines = body.decode().splitlines()
        except UnicodeError: continue
        for i, line in enumerate(lines, 1):
            for term in terms:
                if term in line:
                    result = 'shared motion/picking consumer; full lifecycle owned by page; all observed callers migrated' if term not in ('setDim', 'installStageControl') else 'page-owned dimming or retained stage control; shared input handoff'
                    if p.startswith('tests/'): result = 'regression fixture/assertion; live HTTP and browser execution recorded separately'
                    refs.append([term, p, i, line.strip()[:1000], result])
    table('public-consumers.csv', ['implementation_or_endpoint', 'consumer', 'line', 'reference', 'result'], refs)
    for p in OUT.iterdir():
        if p.is_file(): after[str(p.relative_to(ROOT))] = p.read_bytes()
    table('file-results.csv', ['path', 'action', 'target', 'result'], [
        [p, 'removed' if p not in after else 'added' if p not in before else 'modified' if before[p] != after[p] else 'retained', p,
         'scene input/motion and material ownership implementation' if p in SCOPE['changed'] else 'dated review evidence' if p.startswith(str(OUT.relative_to(ROOT))) else 'source and records unchanged']
        for p in sorted(set(before) | set(after))])
    path = OUT.parent / 'deep-read/audit.py'; tree = ast.parse(path.read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('category', 'stats')]
    scope = dict(Path=Path, collections=collections)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), scope)
    for p in OUT.iterdir():
        if p.is_file(): after[str(p.relative_to(ROOT))] = p.read_bytes()
    (OUT / 'statistics-after.json').write_text(json.dumps(dict(baseline=SCOPE['baseline'], before=scope['stats'](before), after=scope['stats'](after),
        note='same physical-line categories; Git only, runtime excluded; audit totals before final self-inventory refresh'), indent=2) + '\n')
    print(json.dumps({'files': len(after), 'consumer_references': len(refs)}))


if __name__ == '__main__': main()
