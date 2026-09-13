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

