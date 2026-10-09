"""Check a reviewed policy/test map. Never approve changed hashes on refresh.

This is traceability, not proof of semantic completeness or test execution.
Human/agent review must update the map and disclose remaining coverage gaps.
"""
import ast
import hashlib
import json
import re
from pathlib import Path

CONTRACT = 'framework/verification_contract.json'


def verification_errors(state, root):
    root = Path(root)
    try:
        contract = json.loads((root / CONTRACT).read_text())
    except (OSError, ValueError):
        return ['verification: reviewed policy/test map missing or invalid']
    errors = []
    if contract.get('version') != state['version']:
        errors.append('verification: baseline version changed; review required')
    active = {r['id']: r for r in state['policies'] if r['status'] == 'current'}
    rows = contract.get('policies', [])
    if len(rows) != len(active) or {r['policy'] for r in rows} != set(active):
        errors.append('verification: every current policy/scope needs exactly one review')
    reviewed = contract.get('reviewed_files', {})
    for name, digest in reviewed.items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or not (root / path).is_file():
            errors.append('verification: invalid reviewed path ' + name)
        elif hashlib.sha256((root / path).read_bytes()).hexdigest() != digest:
            errors.append('verification: changed reviewed file; review required: ' + name)
    for name in state.get('operational_guides', []):
        if name not in reviewed:
            errors.append('verification: unreviewed operational guide ' + name)
    runner = (root / 'tests/run_browser.cjs').read_text()
    if "require('./browser_suites.cjs')" in runner:
        catalog = 'tests/browser_suites.cjs'
        if catalog not in reviewed:
            errors.append('verification: unreviewed browser suite catalog ' + catalog)
        runner = (root / catalog).read_text() if (root / catalog).is_file() else ''
    match = re.search(r'const defaults = \[([^]]+)\]', runner)
    browser_suites = re.findall(r"'([^']+)'", match[1]) if match else []
    for row in rows:
        policy = active.get(row['policy'], {})
        if row.get('source') != policy.get('source') or row.get('scope') != policy.get('scope'):
            errors.append('verification: policy source/scope mismatch ' + row['policy'])
        if row.get('source') not in reviewed:
            errors.append('verification: unreviewed policy source ' + row['policy'])
        # Partial coverage is explicit and is not converted to complete by green tests.
        if not row.get('checked_requirement') or not row.get('tests') or not row.get('not_verified'):
            errors.append('verification: requirement, tests and coverage limits required ' + row['policy'])
        for reference in row.get('tests', []):
            name, _, symbol = reference.partition('::')
            if name not in reviewed or not (root / name).is_file():
                errors.append('verification: missing reviewed test ' + reference)
                continue
            if name.startswith('tests/unit/test_') and name.endswith('.py'):
                tree = ast.parse((root / name).read_text())
                names = {c.name + '.' + f.name for c in tree.body if isinstance(c, ast.ClassDef)
                         for f in c.body if isinstance(f, ast.FunctionDef) and f.name.startswith('test_')}
                if symbol not in names:
                    errors.append('verification: test case missing ' + reference)
            elif name == 'tests/' + Path(name).stem + '.cjs' and not symbol:
                if Path(name).stem not in browser_suites:
                    errors.append('verification: browser suite not in default runner ' + name)
            else:
                errors.append('verification: test outside configured runners ' + reference)
    return errors
