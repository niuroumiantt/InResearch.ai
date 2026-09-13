"""Dated static consumer/dependency audit; known dynamic CLI entries are explicit."""
import ast
import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
MODULES = {
    'inresearch.workflow.deep_read', 'inresearch.interfaces.deep_read',
    'inresearch.materials.reading_policy', 'inresearch.materials.text_similarity',
    'inresearch.knowledge.provenance', 'inresearch.knowledge.fact_contract',
    'inresearch.workflow.reading_gaps', 'inresearch.delivery.reading_packet',
}
DEEP = 'inresearch.workflow.deep_read.DeepRead'
GAPS = 'inresearch.workflow.reading_gaps.ReadingGaps'
SIM = 'inresearch.materials.text_similarity.SimilarityIndex'


def table(name, rows):
    with (OUT / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others',
                                '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
trees = {p: ast.parse((ROOT/p).read_bytes()) for p in sorted(set(paths))
         if p.endswith('.py') and (ROOT/p).is_file() and not p.startswith('docs/reviews/')}
modules = {p: p[4:-3].replace('/', '.').removesuffix('.__init__')
           for p in trees if p.startswith('src/')}
definitions = {}
for path, module in modules.items():
    if module not in MODULES:
        continue
    for node in trees[path].body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith('_'):
            definitions[module+'.'+node.name] = (path, node.lineno)
        if isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, ast.FunctionDef) and not method.name.startswith('_'):
                    definitions[module+'.'+node.name+'.'+method.name] = (path, method.lineno)
consumers = {symbol: set() for symbol in definitions}
edges = set()
for path, tree in trees.items():
    module = modules.get(path, path)
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for item in node.names:
                aliases[item.asname or item.name] = node.module+'.'+item.name
        elif isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split('.')[0]] = item.name if item.asname else item.name.split('.')[0]
    for value in aliases.values():
        candidate = value
        while candidate not in modules.values() and '.' in candidate:
            candidate = candidate.rsplit('.', 1)[0]
        if module in modules.values() and candidate in modules.values() and candidate != module:
            edges.add((module, candidate))
    for symbol in definitions:
        if symbol.rsplit('.', 1)[0] == module:
            aliases[symbol.rsplit('.', 1)[1]] = symbol
    # Explicitly reviewed service receiver names in the migrated callers/tests.
    # No claim is made that this is whole-program Python type inference.
    if path in {'src/inresearch/interfaces/deep_read.py', 'tests/unit/test_deep_read.py',
                'tests/unit/test_fact_contract.py', 'tests/unit/test_deep_read_transactions.py',
                'tests/unit/deep_read_fixtures.py'}:
        aliases.update(app=DEEP, L2=DEEP)

    def resolve(node, owner=None):
        if isinstance(node, ast.Name):
            return module+'.'+owner if node.id == 'self' and owner else aliases.get(node.id, '')
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'self' and node.attr == 'app' and path.startswith('tests/'):
                return DEEP
            parent = resolve(node.value, owner)
            if parent == DEEP and node.attr in {'gaps', 'similarity'}:
                return GAPS if node.attr == 'gaps' else SIM
            return parent+'.'+node.attr if parent else ''
        return ''

    def visit(node, owner=None, context='<module>'):
        if isinstance(node, ast.ClassDef):
            owner = node.name
        if isinstance(node, ast.FunctionDef):
            context = (owner+'.' if owner else '')+node.name
        if isinstance(node, (ast.Name, ast.Attribute)):
            symbol = resolve(node, owner)
            if symbol in consumers:
                consumers[symbol].add((path, node.lineno, context))
        for child in ast.iter_child_nodes(node):
            visit(child, owner, context)
    visit(tree)

# These registered calls use command dispatch strings rather than Python refs.
consumers['inresearch.interfaces.deep_read.main'].add(('src/inresearch/interfaces/cli.py',
    next(i for i, line in enumerate((ROOT/'src/inresearch/interfaces/cli.py').read_text().splitlines(), 1)
         if 'interfaces.deep_read' in line), 'manage.py -> registered deep-read command'))
table('public-contracts.csv', [dict(symbol=s, implementation=p, line=line,
      consumer_count=len(consumers[s]), consumers='; '.join('%s:%s [%s]' % c for c in sorted(consumers[s])),
      result='migrated; see DELIVERY for external/runtime boundaries')
      for s, (p, line) in sorted(definitions.items())])
graph = {m: set() for m in modules.values()}
for a, b in edges: graph[a].add(b)
cycles = set()


def walk(start, current, seen):
    for target in graph[current]:
        if target == start:
            cycles.add(tuple(seen+[target]))
        elif target not in seen:
            walk(start, target, seen+[target])


for node in graph: walk(node, node, [node])
(OUT/'dependency-audit.json').write_text(json.dumps(dict(
    method='AST imports, explicit reviewed DeepRead receivers; dynamic external imports cannot be enumerated',
    modules=len(graph), edges=len(edges), cycles=sorted(cycles),
    import_edges=sorted(edges)), ensure_ascii=False, indent=2)+'\n')

# Preserve test identity independently of file names and test suite totals.
def cases(tree):
    return {n.name+'.'+m.name for n in tree.body if isinstance(n, ast.ClassDef)
            for m in n.body if isinstance(m, ast.FunctionDef) and m.name.startswith('test_')}

prior = ast.parse(subprocess.check_output(['git', 'show', '20814b8:tests/unit/test_m4_l2.py'], cwd=ROOT))
after = set().union(*(cases(tree) for p, tree in trees.items()
                     if p in {'tests/unit/test_deep_read.py', 'tests/unit/test_fact_contract.py', 'tests/unit/test_text_similarity.py'}))
renamed = {'SkipTests.test_filling_the_same_gap_twice_is_refused': 'SkipTests.test_filling_the_same_gap_twice_replays'}
table('test-results.csv', [dict(test=case, current=renamed.get(case, case),
      present=renamed.get(case, case) in after,
      result='replaced by explicitly replayable fill contract' if case in renamed else 'preserved; dependency migrated')
      for case in sorted(cases(prior))])
assert all(renamed.get(case, case) in after for case in cases(prior))
assert not cycles
