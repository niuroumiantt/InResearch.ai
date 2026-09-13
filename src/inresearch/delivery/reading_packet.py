"""Full-text extraction and terminal packet presentation."""
from __future__ import annotations
import re, subprocess
from pathlib import Path
from inresearch.adapters import office as m4_office_text


CHUNK_CHARS = 15000

FULL_TEXT_CHARS = 600000

def run(cmd, timeout):
    return subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)

def pdf_text(path: Path) -> tuple[str, dict]:
    info = run(['pdfinfo', str(path)], 60).stdout.decode('utf-8', 'ignore')
    m = re.search(r'^Pages:\s+(\d+)', info, re.M)
    pages = int(m.group(1)) if m else None
    raw = run(['pdftotext', '-layout', str(path), '-'], 600).stdout.decode('utf-8', 'ignore')
    # pdftotext separates pages with a form feed; turning those into visible
    # markers is what lets a fact cite "p.42" and a reviewer find it again.
    parts = raw.split('\f')
    text = '\n'.join('\n[p.%d]\n%s' % (i + 1, part) for i, part in enumerate(parts) if part.strip())
    return text, {'pages': pages}

def full_text(path: Path, suffix: str) -> tuple[str, dict]:
    try:
        if suffix == '.pdf':
            return pdf_text(path)
        if suffix in m4_office_text.SUPPORTED:
            return m4_office_text.extract(path, FULL_TEXT_CHARS)
        if suffix in {'.docx', '.pptx'}:
            return m4_office_text.ooxml_text(path, FULL_TEXT_CHARS)
        if suffix in {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm'}:
            raw = path.read_bytes()
            for enc in ('utf-8', 'gb18030', 'utf-16'):
                try: return raw.decode(enc), {}
                except UnicodeDecodeError: continue
            return raw.decode('utf-8', 'ignore'), {}
        if suffix in {'.doc', '.rtf'}:
            return run(['textutil', '-convert', 'txt', '-stdout', str(path)],
                       300).stdout.decode('utf-8', 'ignore'), {}
    except Exception as exc:
        return '', {'extract_error': type(exc).__name__ + ': ' + str(exc)[:150]}
    return '', {'extract_error': 'no reader for ' + suffix}

def chunks(text: str, size=CHUNK_CHARS) -> list[str]:
    """Split on blank lines so a page marker never lands mid-sentence."""
    out, current = [], []
    length = 0
    for block in text.split('\n\n'):
        if length + len(block) > size and current:
            out.append('\n\n'.join(current)); current, length = [], 0
        current.append(block); length += len(block) + 2
    if current:
        out.append('\n\n'.join(current))
    return out

def metric_menu(module: str, metrics: dict) -> str:
    rows = [m for m in metrics.values() if m.get('module') == module]
    if not rows:
        return '（本模块没有已声明的指标；如果读到值得记的数，先在 metrics.json 里补指标定义。）'
    lines = []
    for m in rows:
        lines.append('### %s — %s（单位 %s）' % (m['metric_id'], m.get('name', ''), m.get('unit', '')))
        # The metric's own note carries the traps that span its dimensions - a
        # column header that lies about its unit, two metrics that must never
        # be plotted as one series.  It was defined and then never shown to the
        # one person who needs it.
        if m.get('note'):
            lines.append('  ' + m['note'].replace('\n', '\n  '))
        for dim in m.get('caliber_dims', []):
            lines.append('  - caliber.%s（%s）取值：%s' % (
                dim['id'], dim.get('name', ''), ' / '.join(dim.get('values', []) or ['自由文本'])))
            if dim.get('note'):
                lines.append('    注意：' + dim['note'])
    return '\n'.join(lines)

def other_modules_index(module: str, metrics: dict) -> str:
    """Every other module's metrics, by id only.

    A document belongs to one module; its numbers do not.  The Dell'Oro capex
    workbook is filed under M01 and carries server shipments and ASPs, which
    live in M06 - shown only its own module's menu, a reader would record the
    capex and drop the rest for want of a metric that exists.
    """
    rows = [m for m in metrics.values() if m.get('module') != module]
    if not rows:
        return ''
    lines = []
    for mod in sorted({m.get('module') for m in rows}):
        names = ['%-30s %s（%s）' % (m['metric_id'], m.get('name', ''), m.get('unit', ''))
                 for m in rows if m.get('module') == mod]
        lines.append('%s: %s' % (mod, '\n     '.join(names)))
    return '\n'.join(lines)

def question_menu(module: str, questions: dict, limit=25) -> str:
    rows = [q for q in questions.get(module, []) if q.get('status') == 'open'][:limit]
    if not rows:
        return '（本模块暂无未决问题。）'
    return '\n'.join('  - %s %s' % (q['id'], q['text']) for q in rows)

ATTRIBUTION_ASK = """## 这份文件的出处，L1 没认出来

当前记录：机构「{org}」，年份「{year}」。L1 判的时候只看到 {preview} 字预览，
请从本次正文找回出处；若标明截断，须补看完整原件。通常写在这些地方之一：封面、页眉页脚、
版权页、免责声明、图表下方的「数据来源 / Source」、末页联系方式。

找到了：

```
python3 manage.py deep-read attribute --sha {sha16} --expected-revision {revision} --org "IDC" --year 2024 \\
    --evidence "封面右下：IDC China, March 2024"
```

全文翻完确实没有：

```
python3 manage.py deep-read attribute --sha {sha16} --expected-revision {revision} --unrecoverable \\
    --evidence "封面/页眉页脚/版权页/图表来源/末页均无机构名"
```

`--evidence` 是必填的：出处得有出处，否则只是换了个人猜。

出处不明不妨碍你记事实，但它压着 `evidence.grade`——不知道是谁说的，就不能
按一手资料记。改名由 restage 统一执行，这条命令只改判定，不动文件。

"""

PACKET_HEAD = """# L2 精读包

文件：{name}
sha256：{sha}
模块：{module}    L1 分数：{score}    大小：{kb} KB{pages}

正文见同目录 text.md（{n_chunks} 段，共 {chars} 字）。{truncated}

{attribution}## 你要产出什么

**不是读后感，是记录。** 每读到一个可核验的数，写一条 fact。读不到数就写零条——
零条是合法结果，编一条不是。

写到 facts.json，一个 JSON 数组，每条形如：

```json
{{
  "fact_id": "小写连字符，全库唯一",
  "metric_id": "必须是下面菜单里的某一个",
  "entity": {{"type": "project|company|region|component|market", "id": "...", "label": "..."}},
  "value": 4406.0,
  "unit": "必须与指标声明的单位一致",
  "caliber": {{ "指标声明的每一维都要有取值，缺一不收" }},
  "as_of": "2022-01 实绩 / 2026-Q1 季度 / 2026E 预测 / 2025目标 目标值 / 2025E@2024-04 预测及其做出的时点",
  "evidence": {{
    "sha256": "{sha}",
    "locator": "页码/表号/段落——要能让人翻回去核对这一个数",
    "grade": "S1..S5"
  }},
  "depth": "精读",
  "bound": "point|upper|lower",
  "corroboration": "待交叉验证|已交叉验证|孤证已知|同源转述",
  "notes": "口径的例外、加总方式、被减项"
}}
```

## 五条纪律

1. **值未披露就填 `value: null`**，不要推算填充。留白即纪律。
   同理，**预测不要写成实绩**：`2026E` 与 `2026` 是两回事；同一个年份隔一年做出的
   两份预测更是两个说法，用 `2026E@2025-03` 把时点带上，否则它们会被平均到一起。
2. **「低于 30%」「不足 10%」「可达 40%」是边界不是点值** —— `bound` 填 upper/lower。
   存成点值会被当精确数拿去平均和比较。
3. **口径缺一维就不收。** 造价不写清是控制价还是结算价、是土建本体还是含机电，
   两个数就没法比。
4. **locator 要能让人翻回去。** 「第 42 页表 3-1」可以，「文中提到」不行。
5. **算出来的数标 `derived: true`**，并在 notes 里写清算法与被减项。

## 本模块的指标菜单

{metrics}

## 其他模块的指标（只给编号）

一份文件的数据不会只属于一个模块。下面这些不展开口径——**要用哪一个，就去
`framework/metrics.json` 查它完整的 caliber 维度再写**，凭名字猜口径必错。

{others}

## 本模块仍未回答的研究问题

读的时候留意这些；能被这份文件回答的，在 notes 里注明问题号。

{questions}
"""


def publish(root, row, text, meta, metrics, questions, missing, revision, preview=6000):
    """Publish one complete, independently named terminal packet; never overwrite."""
    import hashlib
    import json
    import os
    import uuid
    from inresearch.storage.files import atomic_write, make_directory, sync_directory

    module = row.get('category') or row.get('module') or 'unknown'
    attribution = ATTRIBUTION_ASK.format(org=row.get('org') or '未知', year=row.get('year') or '未知',
                    preview=preview, sha16=row['sha256'][:16], revision=revision) if missing else ''
    brief = PACKET_HEAD.format(attribution=attribution, name=Path(row.get('rel', '')).name,
        sha=row['sha256'], module=module, score=row.get('score'), kb=round(row.get('size', 0)/1024),
        pages='    页数：%s' % meta['pages'] if meta.get('pages') else '',
        n_chunks=len(chunks(text)), chars=len(text),
        truncated='\n\n**注意：正文被字数上限截断；这不是全文，不能据此宣称完整覆盖。不要把最后一行当作表格的最后一行。**' if meta.get('truncated') else '',
        metrics=metric_menu(module, metrics), others=other_modules_index(module, metrics),
        questions=question_menu(module, questions))
    brief += '\n\nL1 判定版本：`%s`。归属/限制修改须传 `--expected-revision %s`；冲突后重新查看当前判定。\n' % (revision, revision)
    parent = Path(root) / row['sha256']; make_directory(parent)
    packet_id = uuid.uuid4().hex
    staging, target = parent / ('.'+packet_id+'.pending'), parent / packet_id
    make_directory(staging)
    manifest = dict(sha256=row['sha256'], result_revision=revision, packet_id=packet_id,
                    text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    brief_sha256=hashlib.sha256(brief.encode()).hexdigest(), chars=len(text),
                    extraction=meta)
    atomic_write(staging/'text.md', text.encode())
    atomic_write(staging/'brief.md', brief.encode())
    atomic_write(staging/'manifest.json', (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
    os.rename(staging, target)
    sync_directory(parent)
    return dict(sha256=row['sha256'], module=module, score=row.get('score'), chars=len(text),
                chunks=len(chunks(text)), result_revision=revision, packet_id=packet_id,
                unattributed=missing or None, brief=str(target/'brief.md'), text=str(target/'text.md'),
                manifest=str(target/'manifest.json'), **{k:v for k,v in meta.items() if k!='extract_error'})
