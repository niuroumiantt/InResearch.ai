"""One versioned report projection for the web and document exporters."""

from inresearch.paths import project_root
import hashlib
import json
import re
from pathlib import Path

ROOT = project_root()
INTERNAL_FIELDS = {"\u5f85\u529e"}


def parse_findings(md_text):
    """把研究文档拆成 finding 块：[{id, title, qtags, status, revised, body_lines}]"""
    findings = []
    cur = None
    for line in md_text.split("\n"):
        m = re.match(r"^##\s+(M\d+-F\d+)\s+(.*?)\s*(\{[^}]*\})?\s*$", line)
        if m:
            if cur:
                findings.append(cur)
            cur = {"id": m.group(1), "title": m.group(2),
                   "qtags": (m.group(3) or "").strip("{}"), "status": "current",
                   "revised": "", "body": []}
            continue
        if cur is None:
            continue
        s = re.match(r"^-\s+\*\*状态\*\*：(\S+?)\s*｜\s*\*\*修订\*\*：(\S+)", line)
        if s:
            cur["status"], cur["revised"] = s.group(1), s.group(2)
            continue
        cur["body"].append(line)
    if cur:
        findings.append(cur)
    return findings


def clean_body(body_lines):
    """剔除内部字段（待办），保留结论/论证/证据/口径提醒。"""
    out, skipping = [], False
    for line in body_lines:
        m = re.match(r"^-\s+\*\*([^*]+)\*\*：?", line)
        if m:
            skipping = m.group(1).strip() in INTERNAL_FIELDS
        elif skipping and not line.startswith("  "):
            skipping = False
        if not skipping:
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return out


def collect_sources(findings):
    urls = []
    for f in findings:
        for line in f["body"]:
            for u in re.findall(r"https?://[^\s)）]+", line):
                if u not in urls:
                    urls.append(u)
    return urls


def build_report(root=ROOT, selected=()):
    root = Path(root)
    inputs = {}

    def read(relative):
        path = (root / relative).resolve()
        path.relative_to(root.resolve())
        value = path.read_text(encoding='utf-8')
        inputs[relative] = hashlib.sha256(value.encode('utf-8')).hexdigest()
        return value

    registry = json.loads(read('framework/modules.json'))
    chapters, history = [], []
    for module in registry['modules']:
        if selected and module['id'] not in selected:
            continue
        source = module.get('research') or f"research/{module['id']}.md"
        if not (root / source).exists():
            continue
        findings = parse_findings(read(source))
        current = []
        for finding in findings:
            if finding['status'] not in ('current', 'needs-review', 'stale'):
                history.append({k: finding[k] for k in ('id', 'title', 'status', 'revised')} | {'source': source})
                continue
            current.append({**finding, 'body': clean_body(finding['body'])})
        if not current:
            continue
        definitions = sorted((root / 'framework/modules').glob(module['id'] + '_*.md'))
        definition = module.get('doc') or (str(definitions[0].relative_to(root / 'framework')) if definitions else '')
        position = ''
        if definition:
            text = read('framework/' + definition)
            match = re.search(r'##\s*定位与边界\s*\n(.+?)(?:\n##|\Z)', text, re.S)
            position = match.group(1).strip() if match else ''
        chapters.append({'module': module, 'source': source, 'definition': definition,
                         'position': position, 'findings': current})
    summary = read('research/SUMMARY.md') if not selected and (root / 'research/SUMMARY.md').exists() else ''
    findings = [f for chapter in chapters for f in chapter['findings']]
    revision = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return {'schema_version': 1, 'title': '全球数据中心研究报告' if not selected else
            '专题报告：' + '、'.join(ch['module']['name'] for ch in chapters),
            'framework_version': registry['version'], 'data_revision': revision,
            'acceptance': 'legacy_unverified', 'summary': summary, 'chapters': chapters,
            'history': history, 'sources': collect_sources(findings),
            'finding_count': len(findings), 'review_count': sum(f['status'] != 'current' for f in findings)}


def markdown_report(report, title, generated):
    lines = [f'# {title}', '',
             f"> inresearch.ai ｜ 生成日期 {generated} ｜ 内容版本 {report['data_revision'][:12]} ｜ 框架 v{report['framework_version']}",
             '> 兼容研究结论；未自动取得对象证据的 C3 采用资格。生成日期不代表来源核验日期。', '']
    if report['summary']:
        summary = re.sub(r'^#\s+.*\n', '', report['summary'], count=1).strip()
        lines += ['## 执行摘要', '', summary, '']
    for chapter in report['chapters']:
        module = chapter['module']
        lines += [f"## {module['id']} {module['name']}", '']
        if chapter['position']:
            lines += ['> ' + chapter['position'].replace('\n', ' '), '']
        for finding in chapter['findings']:
            lines += [f"### {finding['id']} {finding['title']}", '']
            if finding['status'] != 'current':
                lines += [f"> ⚠️ {finding['status']}（最后修订 {finding['revised']}），引用前请核验。", '']
            lines += finding['body'] + ['']
    if report['history']:
        lines += ['## 历史记录入口', '']
        lines += [f"- {f['id']}：{f['status']}，见 {f['source']}" for f in report['history']]
        lines.append('')
    lines += ['## 附录：来源清单', '']
    lines += [f'{i + 1}. {url}' for i, url in enumerate(report['sources'])]
    return lines + ['']



# ---------------------------------------------------------------------------------------------
# 成果 = 树的可发布快照（05「目录」，2026-09-28）：四章即四问，封面是可信边界，末章是专题目录。
# 全部由权威文件生成（dashboard.json、tco_targets.json、tco_factors.json、datacenter_model.json、
# bom.json、site_rights.json、图谱与问题表的版本），不另写第二份事实；旧的 15 个兼容模块结论只作专题目录。
# ---------------------------------------------------------------------------------------------
QUESTIONS = [('q1', '它值多少'), ('q2', '它由什么组成'), ('q3', '它怎么影响账'), ('q4', '数据从哪来、缺什么')]
COLUMNS = {'1': '构成', '2': '运行', '3': '价格', '4': '时间', '5': '主体'}


def build_snapshot_report(root=ROOT):
    root = Path(root)
    inputs = {}

    def load(relative):
        path = (root / relative).resolve()
        path.relative_to(root.resolve())
        raw = path.read_bytes()
        inputs[relative] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw.decode('utf-8'))

    dash = load('data/dashboard.json')
    targets = load('framework/tco_targets.json')
    factors = load('framework/tco_factors.json')
    model = load('data/datacenter_model.json')
    bom = load('framework/bom.json')
    rights = load('framework/site_rights.json')['rights']
    graph_version = load('framework/research_graph.json').get('version')
    questions_version = load('framework/research_questions.json').get('version')
    evidence = model.get('evidence', {})
    ev_counts = {'sourced': 0, 'assumed': 0, 'input': 0}
    for v in evidence.values():
        if v.get('status') in ev_counts:
            ev_counts[v['status']] += 1
    ev_counts['total'] = len(evidence)
    rows = targets['targets']
    by_status = dict(targets['counts'].get('by_status', {}))
    teams = {}
    for t in rows:
        team = teams.setdefault(t['team'], {'team': t['team'], 'name': targets['teams'].get(t['team'], {}).get('name', t['team']),
                                           'rows': 0, 'needed': 0, 'delivered': 0, 'sourced': 0, 'connected': t['team_state'] == 'connected', 'next_due': None})
        team['rows'] += 1
        if t['status'] in ('needed', 'delivered', 'sourced'):
            team[t['status']] += 1
        if t.get('next_due') and t['status'] != 'sourced' and (team['next_due'] is None or t['next_due'] < team['next_due']):
            team['next_due'] = t['next_due']
    stages = bom.get('stages', [])
    stage_rows = [{'id': st['id'], 'name': st['name'], 'order': st['order'],
                   'parts': [p['id'] for p in bom['parts'] if p.get('stage') == st['id']],
                   'rights': [r['id'] for r in rights if r.get('stage') == st['id']]} for st in stages]
    systems = [{'id': e['id'], 'name': e['name'], 'parent': e.get('parent'), 'chains': e.get('chains', []), 'parts': len(e['parts']),
                'cells': {col: c['status'] for col, c in e['cells'].items()}} for e in dash['system_nodes']]
    parents = [{'id': e['id'], 'name': e['name'], 'children': e['children'], 'cells': {col: c['status'] for col, c in e['cells'].items()}} for e in dash.get('parent_systems', [])]
    site = {'rights': [{'id': r['id'], 'name': r['name'], 'stage': r.get('stage'), 'variable_classes': r['variable_classes'],
                        'cells': {col: dash['rights'][r['id']]['cells'][col]['status'] for col in ('3', '4', '5')}} for r in rights],
            'cells': {col: c['status'] for col, c in dash['site']['cells'].items()}}
    root_cells = {col: {'name': COLUMNS[col], 'status': c['status'],
                        'items': [{'label': i['label'], 'value': i['value'], 'unit': i.get('unit'), 'as_of': i.get('as_of')} for i in c['items'][:4]]}
                  for col, c in dash['root']['cells'].items()}
    factor_rows = [{'id': f['id'], 'label': f['label'], 'side': f['side'], 'parent': f['parent'], 'unit': f.get('unit'), 'formula': f.get('formula'),
                    'model_inputs': len(f.get('model_inputs', [])), 'bom_parts': len(f.get('bom_parts', [])), 'site_rights': len(f.get('site_rights', [])),
                    'fetch': len(f.get('fetch', []))} for f in factors['factors']]
    due = dash['changes']
    legacy = build_report(root)
    topics = {'finding_count': legacy['finding_count'], 'review_count': legacy['review_count'], 'acceptance': legacy['acceptance'],
              'chapters': [{'module': ch['module']['id'], 'name': ch['module']['name'], 'findings': len(ch['findings']),
                            'review': sum(f['status'] != 'current' for f in ch['findings'])} for ch in legacy['chapters']],
              'link': 'report.html?legacy=1', 'note': '兼容模块的研究结论只作专题目录；未自动取得骨架节点证据的 C3 采用资格。'}
    inputs['legacy_report'] = legacy['data_revision']
    revision = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return {
        'schema_version': 2, 'kind': 'datacenter_snapshot', 'title': '一座 AI 数据中心 · 可发布快照', 'as_of': dash['updated'],
        'data_revision': revision, 'acceptance': 'generated_from_registries',
        'boundary': {'model_inputs': ev_counts, 'targets': {**by_status, 'total': len(rows), 'not_connected': sum(1 for t in rows if t['team_state'] == 'not_connected')},
                     'registries': {'graph': graph_version, 'questions': questions_version, 'targets': targets['version'], 'dashboard': dash['version'],
                                    'bom': bom.get('version'), 'factors': factors.get('version'), 'model': model.get('as_of')},
                     'honesty': dash.get('generated_from') and load('framework/dashboard_rules.json').get('honesty', []),
                     'scenario': dash['root']['account']['scenario']},
        'chapters': [
            {'id': 'q1', 'title': '它值多少', 'account': dash['root']['account']['rows'], 'columns': root_cells,
             'calibration': [{'id': cid, 'preset': cal['preset'], 'label': model['presets'].get(cal['preset'], {}).get('label'), 'source': cal.get('source'),
                              'anchors': {k: v for k, v in cal.items() if k not in ('preset', 'source')}} for cid, cal in model.get('calibration', {}).items()],
             'readings': dash['root']['account'].get('readings', [])},
            {'id': 'q2', 'title': '它由什么组成', 'systems': systems, 'parent_systems': parents, 'site': site, 'stages': stage_rows,
             'counts': {'parts': sum(1 for p in bom['parts'] if p['kind'] == 'part'), 'software': sum(1 for p in bom['parts'] if p['kind'] == 'software'),
                        'archetype': sum(1 for p in bom['parts'] if p['kind'] == 'archetype'), 'rights': len(rights), 'chains': sum(len(s['chains']) for s in systems)}},
            {'id': 'q3', 'title': '它怎么影响账', 'formulas': factors.get('formulas', {}), 'factors': factor_rows},
            {'id': 'q4', 'title': '数据从哪来、缺什么', 'by_status': by_status, 'statuses': targets.get('statuses', {}), 'carriers': targets.get('carriers', {}),
             'teams': sorted(teams.values(), key=lambda t: -t['rows']), 'due_30d': due.get('due_total', 0), 'due_targets': due.get('due_targets', [])[:20],
             'not_connected': sum(1 for t in rows if t['team_state'] == 'not_connected')},
        ],
        'topics': topics,
        'exports': [{'id': 'markdown', 'label': 'Markdown', 'how': 'python3 manage.py export'}, {'id': 'json', 'label': 'JSON', 'how': '/api/report 或 python3 manage.py export'},
                    {'id': 'print', 'label': '打印 / PDF', 'how': 'report.html 打印'}],
    }


def markdown_snapshot(report, generated):
    b = report['boundary']
    lines = [f"# {report['title']}", '',
             f"> inresearch.ai ｜ 数据时点 {report['as_of']} ｜ 生成日期 {generated} ｜ 内容版本 {report['data_revision'][:12]} ｜ 图谱 {b['registries']['graph']} · 问题表 {b['registries']['questions']} · 目标表 {b['registries']['targets']}",
             f"> 可信边界：模型输入 {b['model_inputs']['total']} 个（已有 {b['model_inputs']['sourced']} · 假设 {b['model_inputs']['assumed']} · 用户给定 {b['model_inputs']['input']}）；目标行 {b['targets']['total']} 行（已有 {b['targets'].get('sourced', 0)} · 假设 {b['targets'].get('assumed', 0)} · 已交付 {b['targets'].get('delivered', 0)} · 缺 {b['targets'].get('needed', 0)}，待建队名下 {b['targets']['not_connected']} 行）。视图层不填估值；生成日期不代表来源核验日期。", '']
    q1, q2, q3, q4 = report['chapters']
    lines += ['## 一、它值多少', '', f"基准情景：{b['scenario']}", '']
    for r in q1['account']:
        ev = r.get('evidence', {})
        lines.append(f"- **{r['label']}** {r['value']} {r['unit']}（{r['note']}；输入 {ev.get('inputs', '?')}：已有 {ev.get('sourced', 0)} · 假设 {ev.get('assumed', 0)} · 用户给定 {ev.get('input', 0)}）")
    lines += ['', '五列的根节点现值：', '']
    for col, c in q1['columns'].items():
        vals = '；'.join(f"{i['label']} {i['value']}{' ' + i['unit'] if i.get('unit') else ''}" for i in c['items'] if i['value'] is not None) or '缺'
        lines.append(f"- {col} {c['name']}（{c['status']}）：{vals}")
    if q1['calibration']:
        lines += ['', '校准锚：', ''] + [f"- {c['label']}：{'，'.join(f'{k} {v}' for k, v in c['anchors'].items())}（{c['source']}）" for c in q1['calibration']]
    lines += ['', '## 二、它由什么组成', '', f"五个系统（IT 展开三类，存储再分两类）× 链路 {q2['counts']['chains']} 条，部件 {q2['counts']['parts']} 个、软件 {q2['counts']['software']}、基型 {q2['counts']['archetype']}；站点权利 {q2['counts']['rights']} 条并列。", '']
    for e in q2['systems']:
        lines.append(f"- {e['name']}：{e['parts']} 个部件，链路 {' → '.join(e['chains'])}；五列状态 " + ' / '.join(f"{COLUMNS[c]} {s}" for c, s in e['cells'].items()))
    lines += ['', '建设阶段（它怎么建）：', ''] + [f"- {st['order']} {st['name']}：部件 {len(st['parts'])} 个，权利 {len(st['rights'])} 条" for st in q2['stages']]
    lines += ['', '## 三、它怎么影响账', ''] + [f"- **{k}**：{v}" for k, v in q3['formulas'].items()] + ['']
    for f in q3['factors']:
        if f['parent'] is None:
            lines.append(f"- {f['label']}（{f['side']}）：{f['formula'] or ''}")
        else:
            lines.append(f"  - {f['label']}：模型输入 {f['model_inputs']} 个，部件 {f['bom_parts']}，权利 {f['site_rights']}，抓取登记 {f['fetch']}")
    lines += ['', '## 四、数据从哪来、缺什么', '', '目标表是唯一任务书：' + '，'.join(f"{k} {v}" for k, v in q4['by_status'].items()) + f"；30 天内到期且仍缺 {q4['due_30d']} 行；待建队名下 {q4['not_connected']} 行不排到期。", '']
    for t in q4['teams']:
        lines.append(f"- {t['name']}：{'已接入' if t['connected'] else '待建队'} · {t['rows']} 行 · 缺 {t['needed']} · 已交付 {t['delivered']} · 下一到期 {t['next_due'] or '—'}")
    lines += ['', '## 附录：专题目录（兼容研究结论）', '', report['topics']['note'], '']
    lines += [f"- {ch['module']} {ch['name']}：{ch['findings']} 条（待复核 {ch['review']}）" for ch in report['topics']['chapters']]
    return lines + ['']
