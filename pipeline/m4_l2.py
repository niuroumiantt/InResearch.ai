#!/usr/bin/env python3
"""L2: read a high-scoring document in full and turn it into facts.

L1 asked "is this worth reading" from a 400-character preview and answered with
a score.  L2 reads the whole thing and answers with numbers: one record per
fact, not per file.  The two layers are deliberately different databases -
LIBRARY_SCORES.csv indexes documents, data/facts.json holds the numbers - and
framework/metrics.json states the rule that separates them: the atom of the
fact layer is a fact.

  queue                 which documents are eligible and unread
  pack   [--sha S]      write a reading packet for one document
  record --facts F      validate against the contract and append
  status                progress

The packet carries three things, because a reader needs all three to produce a
usable fact: the document's full text with page markers, the metrics that
belong to its module (with their caliber dimensions spelled out), and the open
research questions that module still owes an answer to.

Nothing here rewrites a document.  Facts reference their source by SHA-256:
paths move between machines and archive layouts, content does not.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import m4_office_text
import m4_paths
import m4_triage_l1 as L1

REPO = Path(__file__).resolve().parent.parent
METRICS = REPO / 'framework/metrics.json'
QUESTIONS = REPO / 'framework/research_questions.json'
FACTS = REPO / 'data/facts.json'
CONTRACT = REPO / 'framework/data_contract.json'

STATE = m4_paths.state()
READ_LOG = STATE / 'l2_read.jsonl'
PACKET_DIR = m4_paths.data() / 'l2'

MIN_SCORE = 8
CHUNK_CHARS = 15000
GRADES = ('S1', 'S2', 'S3', 'S4', 'S5')
DEPTHS = ('精读', '据实生成')          # 半自动 and 目录级 never reach the fact layer
BOUNDS = ('point', 'upper', 'lower')
CORROBORATION = ('待交叉验证', '已交叉验证', '孤证已知')
# A year is always the anchor; everything after it says what kind of year.
#   2022-01        an actual, to the month
#   2026-Q1        a quarter
#   2026E          a forecast, not an outturn
#   2025-2027E     a forecast over a span
#   2025目标        a target somebody set, which is neither
#   2025E@2024-04  a 2025 forecast made in April 2024 - the vintage matters,
#                  because the same year forecast twelve months apart is two
#                  different claims and must not be averaged together
AS_OF = re.compile(r'^\d{4}(-\d{4}|-\d{2}(-\d{2})?|-Q[1-4]E?)?(E|目标)?(@\d{4}-\d{2})?$')
FACT_ID = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def load_metrics() -> dict:
    raw = json.loads(METRICS.read_text(encoding='utf-8'))['metrics']
    rows = raw if isinstance(raw, list) else list(raw.values())
    return {m['metric_id']: m for m in rows}


def load_questions() -> dict:
    out = {}
    for q in json.loads(QUESTIONS.read_text(encoding='utf-8'))['records']:
        out.setdefault(q.get('module_id'), []).append(q)
    return out


def load_facts() -> dict:
    return json.loads(FACTS.read_text(encoding='utf-8'))


# --------------------------------------------------------------------------
# what to read
# --------------------------------------------------------------------------

def read_documents() -> set:
    """Documents already given a full read, so pack advances instead of looping."""
    done = set()
    if READ_LOG.exists():
        with READ_LOG.open(encoding='utf-8') as fh:
            for line in fh:
                try: done.add(json.loads(line)['sha256'])
                except (ValueError, KeyError): continue
    return done


def eligible(min_score=MIN_SCORE) -> list[dict]:
    """Judged documents worth a full read, best first, least-read module first.

    Ordering by module coverage rather than by score alone keeps one prolific
    module from consuming the whole first pass: fifteen modules each owe
    answers, and a fact layer that is deep in M10 and empty everywhere else
    cannot close questions anywhere else.
    """
    rows = {}
    if L1.RESULTS.exists():
        with L1.RESULTS.open(encoding='utf-8') as fh:
            for line in fh:
                try: r = json.loads(line)
                except ValueError: continue
                if 'sha256' in r: rows[r['sha256']] = r
    done =read_documents()
    picked = [r for r in rows.values()
              if (r.get('score') or 0) >= min_score
              and r.get('status') == 'ok'
              and r['sha256'] not in done]
    # Least-covered module first, then highest score.  Fifteen modules each owe
    # answers; a fact layer deep in M10 and empty elsewhere closes nothing
    # elsewhere, so breadth comes before one more document from a rich module.
    metrics = load_metrics()
    covered = Counter(metrics.get(f['metric_id'], {}).get('module')
                      for f in load_facts()['records'])
    return sorted(picked, key=lambda r: (covered.get(r.get('category'), 0),
                                         -(r.get('score') or 0), r.get('rel', '')))


# --------------------------------------------------------------------------
# full text, with page markers so a locator can point at something
# --------------------------------------------------------------------------

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
            return m4_office_text.extract(path)
        if suffix in {'.docx', '.pptx'}:
            return m4_office_text.ooxml_text(path)
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


# --------------------------------------------------------------------------
# the reading packet
# --------------------------------------------------------------------------

def metric_menu(module: str, metrics: dict) -> str:
    rows = [m for m in metrics.values() if m.get('module') == module]
    if not rows:
        return '（本模块没有已声明的指标；如果读到值得记的数，先在 metrics.json 里补指标定义。）'
    lines = []
    for m in rows:
        lines.append('### %s — %s（单位 %s）' % (m['metric_id'], m.get('name', ''), m.get('unit', '')))
        for dim in m.get('caliber_dims', []):
            lines.append('  - caliber.%s（%s）取值：%s' % (
                dim['id'], dim.get('name', ''), ' / '.join(dim.get('values', []) or ['自由文本'])))
            if dim.get('note'):
                lines.append('    注意：' + dim['note'])
    return '\n'.join(lines)


def question_menu(module: str, questions: dict, limit=25) -> str:
    rows = [q for q in questions.get(module, []) if q.get('status') == 'open'][:limit]
    if not rows:
        return '（本模块暂无未决问题。）'
    return '\n'.join('  - %s %s' % (q['id'], q['text']) for q in rows)


PACKET_HEAD = """# L2 精读包

文件：{name}
sha256：{sha}
模块：{module}    L1 分数：{score}    大小：{kb} KB{pages}

正文见同目录 text.md（{n_chunks} 段，共 {chars} 字）。

## 你要产出什么

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
  "corroboration": "待交叉验证|已交叉验证|孤证已知",
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

## 本模块仍未回答的研究问题

读的时候留意这些；能被这份文件回答的，在 notes 里注明问题号。

{questions}
"""


def cmd_pack(a):
    metrics, questions = load_metrics(), load_questions()
    pool = eligible(a.min_score)
    if a.sha:
        pool = [r for r in pool if r['sha256'].startswith(a.sha)]
    if not pool:
        print(json.dumps({'packed': 0, 'reason': '没有符合条件且未读的文件'}, ensure_ascii=False))
        return
    row = pool[0]
    path, from_library = L1.readable_path(row)
    text, meta = full_text(path, row['suffix'])
    if not text.strip():
        print(json.dumps({'packed': 0, 'sha256': row['sha256'], 'rel': row.get('rel'),
                          'meta': meta, 'reason': '抽不出正文'}, ensure_ascii=False))
        return
    pieces = chunks(text)
    out = PACKET_DIR / row['sha256'][:16]
    out.mkdir(parents=True, exist_ok=True)
    (out / 'text.md').write_text(text, encoding='utf-8')
    module = row.get('category') or row.get('module') or 'unknown'
    (out / 'brief.md').write_text(PACKET_HEAD.format(
        name=Path(row.get('rel', '')).name, sha=row['sha256'], module=module,
        score=row.get('score'), kb=round(row.get('size', 0) / 1024),
        pages='    页数：%s' % meta['pages'] if meta.get('pages') else '',
        n_chunks=len(pieces), chars=len(text),
        metrics=metric_menu(module, metrics),
        questions=question_menu(module, questions)), encoding='utf-8')
    print(json.dumps({'packed': 1, 'sha256': row['sha256'], 'module': module,
                      'score': row.get('score'), 'chars': len(text), 'chunks': len(pieces),
                      'read_from': 'library' if from_library else 'source',
                      'brief': str(out / 'brief.md'), 'text': str(out / 'text.md'),
                      **{k: v for k, v in meta.items() if k != 'extract_error'}},
                     ensure_ascii=False))


# --------------------------------------------------------------------------
# validation - the contract is worthless unless something enforces it
# --------------------------------------------------------------------------

def check_fact(fact: dict, metrics: dict, seen: set) -> list[str]:
    bad = []
    fid = fact.get('fact_id')
    if not fid or not FACT_ID.match(str(fid)):
        bad.append('fact_id 缺失或不是小写连字符：%r' % fid)
    elif fid in seen:
        bad.append('fact_id 重复：%s' % fid)

    metric = metrics.get(fact.get('metric_id'))
    if metric is None:
        bad.append('metric_id 不在 metrics.json 里：%r' % fact.get('metric_id'))
    else:
        if fact.get('unit') != metric.get('unit'):
            bad.append('unit 与指标声明不符：%r ≠ %r' % (fact.get('unit'), metric.get('unit')))
        caliber = fact.get('caliber')
        if not isinstance(caliber, dict):
            bad.append('caliber 必须是对象')
        else:
            for dim in metric.get('caliber_dims', []):
                got = caliber.get(dim['id'])
                if got is None:
                    bad.append('caliber 缺 %s（%s）——缺一维即无法比较' % (dim['id'], dim.get('name', '')))
                elif dim.get('values') and got not in dim['values']:
                    bad.append('caliber.%s = %r 不在允许取值内：%s' % (
                        dim['id'], got, ' / '.join(dim['values'])))
            for extra in set(caliber) - {d['id'] for d in metric.get('caliber_dims', [])}:
                bad.append('caliber 多出未声明的维度：%s' % extra)

    value = fact.get('value', ...)
    if value is ...:
        bad.append('缺 value（未披露请显式写 null，不要省略）')
    elif value is not None and not isinstance(value, (int, float)):
        bad.append('value 必须是数字或 null：%r' % value)

    if not AS_OF.match(str(fact.get('as_of', ''))):
        bad.append('as_of 必须是 YYYY / YYYY-MM / YYYY-MM-DD：%r' % fact.get('as_of'))

    if fact.get('depth') not in DEPTHS:
        bad.append('depth 只收 %s，半自动与目录级不进事实层' % ' / '.join(DEPTHS))

    ev = fact.get('evidence')
    if not isinstance(ev, dict):
        bad.append('缺 evidence')
    else:
        if ev.get('grade') not in GRADES:
            bad.append('evidence.grade 必须是 %s' % ' / '.join(GRADES))
        if not str(ev.get('locator') or '').strip():
            bad.append('evidence.locator 不能为空——它是别人翻回去核对的唯一依据')
        sha = str(ev.get('sha256') or '')
        if not re.fullmatch(r'[0-9a-f]{64}', sha):
            bad.append('evidence.sha256 必须是 64 位十六进制——路径会变，内容不会')

    if fact.get('bound') is not None and fact['bound'] not in BOUNDS:
        bad.append('bound 必须是 %s' % ' / '.join(BOUNDS))
    if fact.get('corroboration') is not None and fact['corroboration'] not in CORROBORATION:
        bad.append('corroboration 必须是 %s' % ' / '.join(CORROBORATION))
    if fact.get('derived') and not str(fact.get('notes') or '').strip():
        bad.append('derived 为真时必须在 notes 里写清算法与被减项')
    return bad


def cmd_record(a):
    metrics = load_metrics()
    incoming = json.loads(Path(a.facts).read_text(encoding='utf-8'))
    if isinstance(incoming, dict):
        incoming = incoming.get('records') or incoming.get('facts') or [incoming]
    store = load_facts()
    seen = {f['fact_id'] for f in store['records']}

    accepted, rejected = [], []
    for fact in incoming:
        problems = check_fact(fact, metrics, seen)
        if problems:
            rejected.append({'fact_id': fact.get('fact_id'), 'problems': problems})
            continue
        seen.add(fact['fact_id'])
        accepted.append(fact)

    if rejected and not a.partial:
        print(json.dumps({'accepted': 0, 'rejected': len(rejected),
                          'note': '默认全有或全无；确认要收下通过的那些请加 --partial'},
                         ensure_ascii=False))
        for r in rejected[:a.show]:
            print('  %s' % r['fact_id'])
            for p in r['problems']:
                print('     - ' + p)
        return

    if accepted:
        store['records'].extend(accepted)
        store['updated'] = now()[:10]
        tmp = FACTS.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(tmp, FACTS)
    if a.doc:
        READ_LOG.parent.mkdir(parents=True, exist_ok=True)
        with READ_LOG.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps({'sha256': a.doc, 'at': now(),
                                 'facts': len(accepted)}, ensure_ascii=False) + '\n')
    print(json.dumps({'accepted': len(accepted), 'rejected': len(rejected),
                      'facts_total': len(store['records'])}, ensure_ascii=False))
    for r in rejected[:a.show]:
        print('  %s' % r['fact_id'])
        for p in r['problems']:
            print('     - ' + p)


def cmd_queue(a):
    pool = eligible(a.min_score)
    by_module = Counter(r.get('category') for r in pool)
    print(json.dumps({'eligible_unread': len(pool), 'min_score': a.min_score,
                      'already_read': len(read_documents()),
                      'mb': round(sum(r.get('size', 0) for r in pool) / 1e6)},
                     ensure_ascii=False))
    for module, n in by_module.most_common():
        print('  %-8s %d' % (module, n))
    for row in pool[:a.show]:
        print('  %s %s' % (row.get('score'), (row.get('proposed_name') or row.get('rel', ''))[:90]))


def cmd_status(a):
    store = load_facts()
    records = store['records']
    metrics = load_metrics()
    by_module = Counter(metrics.get(f['metric_id'], {}).get('module') for f in records)
    print(json.dumps({'facts': len(records),
                      'documents_read': len(read_documents()),
                      'metrics_covered': len({f['metric_id'] for f in records}),
                      'metrics_total': len(metrics),
                      'with_locator': sum(1 for f in records if (f.get('evidence') or {}).get('locator')),
                      'with_sha256': sum(1 for f in records if (f.get('evidence') or {}).get('sha256')),
                      'value_withheld': sum(1 for f in records if f.get('value') is None),
                      'not_corroborated': sum(1 for f in records
                                              if f.get('corroboration') == '待交叉验证')},
                     ensure_ascii=False))
    for module, n in by_module.most_common():
        print('  %-8s %d' % (module, n))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('queue'); q.add_argument('--min-score', type=int, default=MIN_SCORE)
    q.add_argument('--show', type=int, default=15)
    p = sub.add_parser('pack'); p.add_argument('--sha'); p.add_argument('--min-score', type=int, default=MIN_SCORE)
    r = sub.add_parser('record'); r.add_argument('--facts', required=True)
    r.add_argument('--doc', help='读完的文件 sha256，写进已读账本')
    r.add_argument('--partial', action='store_true', help='收下通过校验的，跳过不通过的')
    r.add_argument('--show', type=int, default=10)
    s = sub.add_parser('status')
    a = ap.parse_args()
    {'queue': cmd_queue, 'pack': cmd_pack, 'record': cmd_record, 'status': cmd_status}[a.cmd](a)


if __name__ == '__main__':
    main()
