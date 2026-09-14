#!/usr/bin/env python3
"""Register all versioned source/record files and enforce one current policy per scope.

--refresh rewrites only the generated registry/report, never research source records.
--check is deterministic and read-only. Git inventory excludes ignored runtime data.
"""

from inresearch.paths import project_root
from inresearch.interfaces.verification import verification_errors
import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = project_root()
STATE = 'framework/current_state.json'
MANIFEST = 'framework/repository_manifest.json'
REPORT = 'docs/REPOSITORY_REGISTER.md'
GENERATED = {MANIFEST, REPORT}
LABELS = {'normative': '现行规范', 'entrypoint': '现行入口', 'retired_entrypoint': '已退役入口',
          'historical': '历史快照', 'design_reference': '已采用设计依据', 'research_record': '兼容研究记录',
          'source_record': '在册数据/索引', 'candidate': '候选与外部输入', 'generated': '生成物',
          'implementation': '运行代码', 'test': '测试', 'supporting_document': '配套说明',
          'asset': '静态资源', 'project_config': '项目配置'}


def policy_errors(state, root=ROOT):
    errors, by_id, active = [], {}, {}
    for row in state.get('policies', []):
        rid = row.get('id')
        if not rid or rid in by_id:
            errors.append(f'duplicate/missing policy ID: {rid}')
            continue
        by_id[rid] = row
        source = row.get('source', '')
        if not source or Path(source).is_absolute() or '..' in Path(source).parts or not (root / source).is_file():
            errors.append(f'{rid}: source missing or outside repository')
        if row.get('status') == 'current':
            key = (row.get('topic'), row.get('scope'))
            if key in active:
                errors.append(f'multiple current policies for {key}')
            active[key] = rid
            try:
                date.fromisoformat(row.get('effective_at', ''))
            except (ValueError, TypeError):
                errors.append(f'{rid}: effective date required')
            if not row.get('reason'):
                errors.append(f'{rid}: change reason required')
            if source.startswith('docs/archive/'):
                errors.append(f'{rid}: archive cannot be current')
            for target in row.get('implementations', []):
                if not (root / target).is_file():
                    errors.append(f'{rid}: missing implementation {target}')
        elif row.get('status') == 'superseded':
            if not source.startswith('docs/archive/'):
                errors.append(f'{rid}: retired policy source must be archived')
        else:
            errors.append(f'{rid}: policy status must be current or superseded')
    for rid, row in by_id.items():
        for old in row.get('supersedes', []):
            before = by_id.get(old)
            if not before:
                errors.append(f'{rid}: unknown supersedes {old}')
            elif (before.get('superseded_by') != rid or before.get('status') != 'superseded'
                  or before.get('topic') != row.get('topic') or before.get('scope') != row.get('scope')):
                errors.append(f'{rid}: inconsistent replacement {old}')
        if row.get('status') == 'superseded':
            target = by_id.get(row.get('superseded_by'), {})
            if rid not in target.get('supersedes', []):
                errors.append(f'{rid}: missing replacement backlink')
    visiting, done = set(), set()
    def visit(rid):
        if rid in visiting:
            errors.append('policy replacement cycle: ' + rid)
            return
        if rid in done or rid not in by_id:
            return
        visiting.add(rid)
        for old in by_id[rid].get('supersedes', []):
            visit(old)
        visiting.remove(rid)
        done.add(rid)
    for rid in by_id:
        visit(rid)
    return errors


def paths(root=ROOT):
    return sorted(set(p.decode('utf-8') for p in subprocess.check_output(
        ['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard']).split(b'\0') if p))


def classify(path, state):
    if path in GENERATED:
        return 'generated'
    if path in {r['source'] for r in state['policies'] if r['status'] == 'current'}:
        return 'normative'
    if path in state['entrypoints']:
        return 'entrypoint'
    if path in state['retired_entrypoints']:
        return 'retired_entrypoint'
    if path in state.get('operational_guides', []):
        return 'supporting_document'
    if path.endswith('/RESEARCH_ARCHITECTURE_V2.md'):
        return 'design_reference'
    if path.startswith(('docs/archive/', 'docs/reviews/', 'docs/intern/')):
        return 'historical'
    if path.startswith('research/') and path.endswith('.md'):
        return 'research_record'
    if path.startswith('docs/inbox/'):
        return 'candidate'
    if path.startswith('reports/'):
        return 'generated'
    if path.startswith('data/') or path.endswith('.csv') or path == 'docs/LIBRARY_REPORT.md':
        return 'source_record'
    if path.startswith('tests/') or Path(path).name.startswith('test_'):
        return 'test'
    if path.endswith(('.py', '.sh', '.js', '.html', '.css')) and not path.startswith('web/assets/vendor/'):
        return 'implementation'
    if path.endswith('.md'):
        return 'supporting_document'
    if path.startswith('web/assets/'):
        return 'asset'
    return 'project_config'


def collections(path, raw):
    result = []
    if path.endswith('.csv'):
        rows = list(csv.DictReader(raw.decode('utf-8-sig').splitlines(keepends=True)))
        result.append({'name': 'rows', 'count': len(rows), 'fields': list(rows[0]) if rows else []})
    elif path.endswith('.json'):
        value = json.loads(raw)
        if isinstance(value, list):
            result.append({'name': 'items', 'count': len(value)})
        elif isinstance(value, dict):
            for name, rows in value.items():
                if isinstance(rows, list):
                    result.append({'name': name, 'count': len(rows)})
    elif path.startswith('research/') and path.endswith('.md'):
        text = raw.decode('utf-8')
        ids = re.findall(r'^##\s+(M\d+-F\d+)\b', text, re.M)
        if ids:
            result.append({'name': 'Finding', 'count': len(ids), 'identity': 'Mxx-Fn'})
    return result


def build_manifest(state, root=ROOT):
    entries = []
    for path in paths(root):
        role = classify(path, state)
        row = {'path': path, 'role': role}
        if path not in GENERATED:
            raw = (root / path).read_bytes()
            row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), collections=collections(path, raw))
        entries.append(row)
    return {'version': state['version'], 'scope': 'Git source/records only; runtime stores and cloud originals excluded',
            'files': entries, 'counts_by_role': dict(sorted(Counter(r['role'] for r in entries).items()))}


def retired_errors(manifest, state, root=ROOT):
    errors = []
    checked = {'normative', 'entrypoint', 'implementation', 'supporting_document'}
    for row in manifest['files']:
        if row['role'] not in checked or row['path'] == 'src/inresearch/interfaces/governance.py':
            continue
        path = row['path']
        if Path(path).suffix not in {'.md', '.py', '.sh', '.html', '.js'}:
            continue
        text = (root / path).read_text(encoding='utf-8')
        for pattern in state['known_retired_patterns']:
            if re.search(pattern, text):
                errors.append(f'{path}: retired assertion {pattern}')
    return errors


def render_report(manifest):
    lines = ['# 在册源码与记录清单', '', '> GENERATED · 由 `python3 manage.py governance --refresh` 从 Git 在册与本次新增路径生成。当前基准：'+manifest['version']+'。',
             '', '现行依据见 [CURRENT](../framework/CURRENT.md)。本清单覆盖每个在册文件；对应内容 SHA-256、大小和记录集合结构见 `framework/repository_manifest.json`。修改内容或新增文件须重新生成并通过 CI。',
             '', '范围仅限 Git 源码和记录，不扫描百度网盘、Spark 原件/SQLite、密钥、忽略文件或外置盘。记录集合分别计数，不能相加当作唯一文档数、已读数或研究完成度。内容摘要用于发现改动，不表示逐条事实已核验。', '', f'在册文件：{len(manifest["files"])}。', '', '| 身份 | 文件数 |', '|---|---|']
    for role, count in manifest['counts_by_role'].items():
        lines.append(f'| {LABELS[role]} | {count} |')
    lines += ['', '## 在册记录集合', '', '| 文件 | 集合 | 条数 |', '|---|---|---|']
    for row in manifest['files']:
        for collection in row.get('collections', []):
            lines.append(f'| `{row["path"]}` | {collection["name"]} | {collection["count"]} |')
    lines += ['', '## 全部文件', '', '| 路径 | 身份 |', '|---|---|']
    for row in manifest['files']:
        path = row['path']
        target = ('../' + path) if not path.startswith('docs/') else path[5:]
        label = f'[{path}]({target})' if path.endswith(('.md', '.csv')) else '`'+path+'`'
        lines.append(f'| {label} | {LABELS[row["role"]]} |')
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.refresh:
        for name in GENERATED:
            if not (ROOT / name).exists():
                (ROOT / name).write_text('')
    state = json.loads((ROOT / STATE).read_text())
    errors = policy_errors(state)
    errors += verification_errors(state, ROOT)
    manifest = build_manifest(state)
    errors += retired_errors(manifest, state)
    text = json.dumps(manifest, ensure_ascii=False, indent=2)+'\n'
    report = render_report(manifest)
    if args.refresh and not errors:
        (ROOT / MANIFEST).write_text(text)
        (ROOT / REPORT).write_text(report)
    elif not args.refresh:
        for name, expected in ((MANIFEST, text), (REPORT, report)):
            if not (ROOT / name).exists() or (ROOT / name).read_text() != expected:
                errors.append(f'{name}: stale or missing; run governance.py --refresh')
    for error in errors:
        print('ERROR:', error)
    if not errors:
        print(f'Governance {state["version"]}: {len(manifest["files"])} files; scopes, inventory and reviewed test map verified; semantic coverage remains partial')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
