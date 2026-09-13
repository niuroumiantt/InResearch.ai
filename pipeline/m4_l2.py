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
  attribute --sha S     put back a publisher L1 could not see in a preview
  flag --sha S          keep a document out of the fact layer, with the reason
  status                progress

The packet carries three things, because a reader needs all three to produce a
usable fact: the document's full text with page markers, the metrics that
belong to its module (with their caliber dimensions spelled out), and the open
research questions that module still owes an answer to.

Nothing here rewrites a document.  Facts reference their source by SHA-256:
paths move between machines and archive layouts, content does not.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys, time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import m4_office_text
import m4_paths
from m4_records import current_results
import m4_triage_l1 as L1

REPO = Path(__file__).resolve().parent.parent
METRICS = REPO / 'framework/metrics.json'
QUESTIONS = REPO / 'framework/research_questions.json'
FACTS = REPO / 'data/facts.json'
CONTRACT = REPO / 'framework/data_contract.json'
# In the repo, not in machine-local state: a gap found while reading on M4
# is only useful if it reaches whoever edits the menu, and that is a
# different machine.  The read ledger stays local because it is about one
# machine's progress; the gaps are about the contract.
GAPS = REPO / 'data/metric_gaps.jsonl'

STATE = m4_paths.state()
READ_LOG = STATE / 'l2_read.jsonl'
# sha256 -> 正文指纹。sha256 认的是字节，这本账认的是内容：
# 同一份报告的两个副本字节不同、sha256 不同，正文一字不差。
TEXT_MD5 = STATE / 'l2_text_md5.jsonl'
PACKET_DIR = m4_paths.data() / 'l2'

MIN_SCORE = 8
CHUNK_CHARS = 15000
# L1's budget is a preview's; L2's is the document's.  A workbook cut at
# twenty thousand characters is read as though its last surviving row were its
# last row, and the facts drawn from it would be silently partial.
FULL_TEXT_CHARS = 600000
GRADES = ('S1', 'S2', 'S3', 'S4', 'S5')
# 完整 sha 与前缀要分开对待：完整的自证，前缀得有判定可解。
FULL_SHA = re.compile(r'[0-9a-f]{64}')
DEPTHS = ('精读', '据实生成')          # 半自动 and 目录级 never reach the fact layer
BOUNDS = ('point', 'upper', 'lower')
CORROBORATION = ('待交叉验证', '已交叉验证', '孤证已知', '同源转述')

# 自由文本维填这些等于没填：它们不区分任何两条数，而区分正是这类维存在的理由。
PLACEHOLDER_VALUES = frozenset(
    ('见 notes', '见notes', '见备注', '同上', '未填', '待补', '略', '-', '—', 'N/A', 'n/a'))
# A year is always the anchor; everything after it says what kind of year.
#   2022-01        an actual, to the month
#   2026-Q1        a quarter
#   2026E          a forecast, not an outturn
#   2025-2027E     a forecast over a span
#   2025目标        a target somebody set, which is neither
#   2025E@2024-04  a 2025 forecast made in April 2024 - the vintage matters,
#                  because the same year forecast twelve months apart is two
#                  different claims and must not be averaged together
# 半年与季度并列，因为渠道纪要按半年给数：寒武纪 2025 上半年已交付 4 万片、
# 下半年预计约 7 万片。拆成两个季度是我们替原文做的拆分，原文没这个拆分。
AS_OF = re.compile(r'^\d{4}(-\d{4}|-\d{2}(-\d{2})?|-Q[1-4]E?|-H[12]E?)?(E|目标)?(@\d{4}-\d{2})?$')
FACT_ID = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
UNKNOWN = '未知'            # what L1 writes when the preview never named a publisher
YEAR = re.compile(r'^\d{4}$')


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

def all_results() -> dict:
    """Use the same effective reading as classification, moves and exports."""
    return current_results(L1.RESULTS)


def read_documents() -> set:
    """Documents already given a full read, so pack advances instead of looping."""
    done = set()
    if READ_LOG.exists():
        with READ_LOG.open(encoding='utf-8') as fh:
            for line in fh:
                try: done.add(json.loads(line)['sha256'])
                except (ValueError, KeyError): continue
    return done


# Our own output is not a source.  A summary this project wrote was derived
# from facts; reading it back as evidence records those facts a second time,
# now wearing a grade and a locator so they look like independent support.
# That is the hardest kind of error to spot later and the most damaging: it
# turns one observation into two and makes a lone claim look corroborated.
SELF_AUTHORED_ORGS = {'本项目', 'inresearch', 'inresearch.ai', '内部研究'}
SELF_AUTHORED_PREFIXES = ('要删/reader/', 'docs/', 'data/', 'framework/', 'reports/')


def self_authored(row: dict) -> bool:
    if str(row.get('org') or '').strip() in SELF_AUTHORED_ORGS:
        return True
    return str(row.get('rel') or '').startswith(SELF_AUTHORED_PREFIXES)


# Two reasons a document stays out of the fact layer whatever it scored.
# Neither is a judgement about quality: both documents below scored 8 or
# better precisely because they carry real first-hand numbers.
RESTRICTIONS = {
    # NOT for the word "Confidential" on its own.  In this corpus a machine
    # footer reading 机密 / Confidential is boilerplate - most vendor decks
    # carry one - and gating on it would exclude most of the library for no
    # gain.  This flag is for an explicit restriction naming a recipient:
    # "Confidential for X Corp. / Not to be distributed".  Nothing sets it
    # automatically; a person decides, per file, and says where they saw it.
    'confidential': '文件写明限定收件方且不得分发——不是泛用的机密页脚',
    'pii': '含个人信息（姓名、电话、邮箱、职级）或内网地址，'
           '这些不该出现在任何被引用的产物里',
}


def restricted(row: dict) -> list[str]:
    """Why this document must not reach the fact layer, if it must not.

    The gate exists because score and admissibility are different questions.
    A quarterly that says "Confidential / Not to be distributed" on its cover
    is exactly the kind of first-hand source L1 scores 8, and scoring it 8 is
    correct - it is a real document and the library should know it is there.
    What it must not do is flow through L2 into facts that get quoted.
    """
    return [name for name in RESTRICTIONS if row.get(name)]


def unattributed(row: dict) -> list[str]:
    """Which identifying fields L1 left as 未知, once, in one place.

    A preview is 6000 characters off the front of a file, and a spreadsheet的
    front is column headers.  So the workbooks that scored 9 and 10 on the
    strength of their numbers are exactly the ones whose publisher never made
    it into the preview - and a number whose publisher is unknown cannot be
    graded as first-hand.  L2 reads the whole document, so L2 is where this
    gets fixed.
    """
    missing = [field for field in ('org', 'year')
               if str(row.get(field) or UNKNOWN).strip() in ('', UNKNOWN)]
    # Saying the publisher cannot be found silences the publisher ask, not the
    # year one: they are looked for in different places and found separately.
    searched = set(row.get('unrecoverable') or ())
    if row.get('org_unrecoverable'):
        searched.add('org')
    return [field for field in missing if field not in searched]


def gap_label(row: dict) -> str:
    """Name the field that is actually missing.

    The first version printed 出处未知 whenever either field was blank, so
    「09p_未知_中国移动_忠县…」 - publisher known, year not - was labelled as
    having no provenance at all.  A marker that misreports which half is
    missing is worse than no marker: it sends you looking for something the
    row already has.
    """
    missing = unattributed(row)
    if 'org' in missing:
        return '出处未知'
    return '年份未知' if 'year' in missing else '    '


YEAR4 = re.compile(r'(19|20)\d{2}')


def document_year(row: dict) -> int:
    """The document's year, or 0 when it never said.

    Unknown sorts with the oldest rather than the newest: a document that will
    not say when it was written cannot claim to be current, and the way to move
    it up the queue is to find the year, which `attribute` exists for.
    """
    for field in ('year', 'proposed_name', 'rel'):
        found = YEAR4.search(str(row.get(field) or ''))
        if found:
            return int(found.group(0))
    return 0


def eligible(min_score=MIN_SCORE, include_read=False, since=0) -> list[dict]:
    """Judged documents worth a full read, best first, least-read module first.

    Ordering by module coverage rather than by score alone keeps one prolific
    module from consuming the whole first pass: fifteen modules each owe
    answers, and a fact layer that is deep in M10 and empty everywhere else
    cannot close questions anywhere else.
    """
    rows = all_results()
    done = read_documents()
    picked = [r for r in rows.values()
              if (r.get('score') or 0) >= min_score
              and r.get('status') == 'ok'
              and (include_read or r['sha256'] not in done)
              and not self_authored(r)
              and not restricted(r)
              and (not since or document_year(r) >= since)]
    # Least-covered module first, then highest score.  Fifteen modules each owe
    # answers; a fact layer deep in M10 and empty elsewhere closes nothing
    # elsewhere, so breadth comes before one more document from a rich module.
    metrics = load_metrics()
    covered = Counter(metrics.get(f['metric_id'], {}).get('module')
                      for f in load_facts()['records'])
    # Coverage first, then score, then recency.  Age is in the key because a
    # 2016 工程量清单 and a 2026 预测 at the same score are not equally worth
    # reading now: the first batch of re-judged tables was one 2016 project
    # forty files deep, and nothing in the ordering knew that.
    return sorted(picked, key=lambda r: (covered.get(r.get('category'), 0),
                                         -(r.get('score') or 0),
                                         -document_year(r), r.get('rel', '')))


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
你看到的是全文——顺手把出处找回来。通常写在这些地方之一：封面、页眉页脚、
版权页、免责声明、图表下方的「数据来源 / Source」、末页联系方式。

找到了：

```
python3 pipeline/m4_l2.py attribute --sha {sha16} --org "IDC" --year 2024 \\
    --evidence "封面右下：IDC China, March 2024"
```

全文翻完确实没有：

```
python3 pipeline/m4_l2.py attribute --sha {sha16} --unrecoverable \\
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
  "as_of": "2022-01 实绩 / 2026-Q1 季度 / 2026-H1 半年 / 2026E 预测 / 2025目标 目标值 / 2025E@2024-04 预测及其做出的时点",
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


# A document's text can be identical while its bytes are not: the same report
# re-exported, re-downloaded, or carried through a system that rewrites PDF
# metadata.  sha256 sees two files; a reader sees one.  Two 信通院 reports made
# it into the reading queue twice this way - same 41 pages, same 23,935
# characters, same body md5, two different sha256.
MIN_FINGERPRINT_CHARS = 500


def text_fingerprint(text: str, meta: dict) -> str | None:
    """A hash of what a reader would see, not of the bytes on disk.

    Whitespace is dropped entirely, not collapsed to single spaces: a reflow
    breaks a Chinese line mid-sentence where the original had no space at all,
    so collapsing would still leave the two texts different.  Dropping it makes
    a re-wrap invisible, which is what we want - a reflow is not a different
    document.  Page count joins the hash because two documents can share
    a long identical front matter (a quarterly series off one template) while
    being different documents - a shared prefix plus a different page count is
    not a duplicate.

    Returns None below MIN_FINGERPRINT_CHARS: a dozen characters of extracted
    text would collide across every scanned cover page in the corpus, and a
    fingerprint that fires on unrelated files is worse than none.
    """
    body = re.sub(r'\s+', '', text)
    if len(body) < MIN_FINGERPRINT_CHARS:
        return None
    pages = (meta or {}).get('pages') or 0
    return hashlib.md5(('%s\x00%s' % (pages, body)).encode('utf-8')).hexdigest()


def fingerprints() -> dict:
    """sha256 -> text_md5, last write wins."""
    seen = {}
    if TEXT_MD5.exists():
        with TEXT_MD5.open(encoding='utf-8') as fh:
            for line in fh:
                try: row = json.loads(line)
                except ValueError: continue
                if row.get('sha256') and row.get('text_md5'):
                    seen[row['sha256']] = row['text_md5']
    return seen


def remember_fingerprint(sha: str, text_md5: str,
                         sketch: list[str] | None = None) -> None:
    TEXT_MD5.parent.mkdir(parents=True, exist_ok=True)
    with TEXT_MD5.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps({'sha256': sha, 'text_md5': text_md5, 'at': now(),
                             **({'sketch': sketch} if sketch else {})},
                            ensure_ascii=False) + '\n')


def already_read_with_same_text(sha: str, text_md5: str) -> list[str]:
    """Documents already read whose text is this same text - other files only."""
    if not text_md5:
        return []
    known, read = fingerprints(), read_documents()
    return sorted(other for other, other_md5 in known.items()
                  if other_md5 == text_md5 and other != sha and other in read)


def packed_not_read_with_same_text(sha: str, text_md5: str) -> list[str]:
    """Copies whose text is this text and which are packed but not yet read.

    The read twin check below only fires once the other copy is in the read
    ledger.  That is deliberate - with both copies still in the queue, either
    one may be read first.  But it leaves the case M4 actually hit on the third
    pair (the 赛莱默 water report): both copies were packed in the same round,
    neither was read yet, so nothing fired and the duplicate was caught by the
    reader's own memory.  A fingerprint recorded by pack and never compared at
    pack time is a ledger nobody reads.

    So this does not block - it says so.  The packet is still written; the
    output names the copy already open, and the reader decides whether to read
    this one or skip it.
    """
    if not text_md5:
        return []
    known, read = fingerprints(), read_documents()
    return sorted(other for other, other_md5 in known.items()
                  if other_md5 == text_md5 and other != sha and other not in read)


# --------------------------------------------------------------------------
# near-duplicates - the copy that is not byte-for-byte and not word-for-word
# --------------------------------------------------------------------------
# text_md5 catches a re-export: same text, different bytes.  It does not catch
# the copy that lost a page.  Three PDFs of one 信通院 liquid-cooling report
# reached the queue at 28,615 / 28,932 / 29,032 characters - one missing a
# copyright page, one a different header - so three different text_md5 and
# nothing fired.  A prefix fingerprint would not have helped either: what
# differs sits at the front.
#
# So compare content, not offsets.  Cut the body into chunks at boundaries the
# content itself decides (a gear hash over the last few dozen bytes), and an
# inserted page changes only the chunks it touches; every other chunk hashes
# the same as before.  Keep the 64 numerically smallest chunk hashes as the
# document's sketch and the overlap of two sketches estimates how much text
# the two share - that is the bottom-k estimator, and 64 values is enough to
# tell "a page apart" from "a different report".
SKETCH_SIZE = 64
CHUNK_BITS = 0xFF               # 边界平均每 256 字节一次
NEAR_TWIN_RATIO = 0.8           # 共有八成以上正文就值得说一声
GEAR = [(i * 0x9E3779B1) & 0xFFFFFFFF for i in range(256)]


def text_sketch(text: str) -> list[str]:
    """The 64 smallest content-defined chunk hashes of this text.

    Whitespace goes first, for the same reason text_fingerprint drops it: a
    reflow is not a different document.  Returns [] below the same floor -
    a sketch of a cover page would match every cover page in the corpus.
    """
    body = re.sub(r'\s+', '', text)
    if len(body) < MIN_FINGERPRINT_CHARS:
        return []
    data = body.encode('utf-8')
    hashes, start, h = set(), 0, 0
    for i, byte in enumerate(data):
        h = ((h << 1) + GEAR[byte]) & 0xFFFFFFFF
        if not h & CHUNK_BITS and i - start >= 64:
            hashes.add(hashlib.md5(data[start:i + 1]).hexdigest()[:12])
            start, h = i + 1, 0
    if start < len(data):
        hashes.add(hashlib.md5(data[start:]).hexdigest()[:12])
    return sorted(hashes)[:SKETCH_SIZE]


def sketch_overlap(a: list[str], b: list[str]) -> float:
    """Bottom-k estimate of how much text two sketches share, 0.0 - 1.0.

    The k smallest hashes of the union are a uniform sample of the union, so
    the share of them present in both sketches estimates the Jaccard index.
    Taking them from the union rather than from either side is what keeps the
    estimate honest when one document is longer than the other.
    """
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    k = min(len(a), len(b), SKETCH_SIZE)
    sample = sorted(sa | sb)[:k]
    if not sample:
        return 0.0
    return sum(1 for h in sample if h in sa and h in sb) / len(sample)


def sketches() -> dict:
    """sha256 -> sketch, last write wins.  Same ledger as the fingerprints."""
    seen = {}
    if TEXT_MD5.exists():
        with TEXT_MD5.open(encoding='utf-8') as fh:
            for line in fh:
                try: row = json.loads(line)
                except ValueError: continue
                if row.get('sha256') and row.get('sketch'):
                    seen[row['sha256']] = row['sketch']
    return seen


def near_twins(sha: str, sketch: list[str]) -> list[dict]:
    """Documents whose text mostly is this text - copies that lost a page.

    Exact twins are left to text_md5; they come back with ratio 1.0 there and
    would only say the same thing twice.  Everything at or above the ratio is
    reported with how much it shares and whether it was already read, because
    those two facts decide what the reader does next.
    """
    if not sketch:
        return []
    read = read_documents()
    out = []
    for other, other_sketch in sketches().items():
        if other == sha:
            continue
        ratio = sketch_overlap(sketch, other_sketch)
        if ratio >= NEAR_TWIN_RATIO:
            out.append({'sha256': other, 'shared': round(ratio, 3),
                        'read': other in read})
    return sorted(out, key=lambda r: -r['shared'])


def cmd_pack(a):
    metrics, questions = load_metrics(), load_questions()
    # --again exists because the read ledger is append-only and pack skips what
    # it holds: a document marked read by accident - an empty facts.json, a
    # batch recorded against the wrong sha - could otherwise never be packed
    # again.  It takes a --sha so it can only ever reopen the one you name.
    if a.again and not a.sha:
        sys.exit('--again 要跟 --sha：它重开的是你指名的那一份，不是队列里的下一份')
    pool = eligible(a.min_score, include_read=a.again, since=a.since)
    if a.sha:
        pool = [r for r in pool if r['sha256'].startswith(a.sha)]
    if not pool:
        print(json.dumps({'packed': 0, 'reason': '没有符合条件且未读的文件'
                          if not a.again else '没有匹配这个 sha 的判定'},
                         ensure_ascii=False))
        return
    row = pool[0]
    path, from_library = L1.readable_path(row)
    text, meta = full_text(path, row['suffix'])
    if not text.strip():
        print(json.dumps({'packed': 0, 'sha256': row['sha256'], 'rel': row.get('rel'),
                          'meta': meta, 'reason': '抽不出正文'}, ensure_ascii=False))
        return
    text_md5 = text_fingerprint(text, meta)
    if text_md5:
        twins = already_read_with_same_text(row['sha256'], text_md5)
        if twins and not a.again:
            # Not a refusal to ever read it - a refusal to read it twice
            # without saying so.  --again reopens it by name.
            print(json.dumps(
                {'packed': 0, 'sha256': row['sha256'], 'rel': row.get('rel'),
                 'text_md5': text_md5, 'same_text_already_read': twins,
                 'reason': '正文与已读过的文件一字不差——sha256 不同是因为字节不同，'
                           '不是因为内容不同。确要再读一遍用 pack --again --sha %s；'
                           '若确认是同一份，直接 skip 掉这一份'
                           % row['sha256'][:12]}, ensure_ascii=False))
            return
        # 在记账之前问：正文一样、还没读、已经开过包的是哪几份。
        # 记账之后再问就问不出来了——自己会出现在账本里。
        open_twins = packed_not_read_with_same_text(row['sha256'], text_md5)
        sketch = text_sketch(text)
        remember_fingerprint(row['sha256'], text_md5, sketch)
    else:
        open_twins, sketch = [], []
    # 近似副本：正文不是一字不差，但差的只是一页版权声明。同样只报不挡。
    approximate = near_twins(row['sha256'], sketch) if sketch else []

    pieces = chunks(text)
    out = PACKET_DIR / row['sha256'][:16]
    out.mkdir(parents=True, exist_ok=True)
    (out / 'text.md').write_text(text, encoding='utf-8')
    module = row.get('category') or row.get('module') or 'unknown'
    missing = unattributed(row)
    (out / 'brief.md').write_text(PACKET_HEAD.format(
        attribution=ATTRIBUTION_ASK.format(
            org=row.get('org') or UNKNOWN, year=row.get('year') or UNKNOWN,
            preview=L1.MAX_PREVIEW_CHARS, sha16=row['sha256'][:16]) if missing else '',
        name=Path(row.get('rel', '')).name, sha=row['sha256'], module=module,
        score=row.get('score'), kb=round(row.get('size', 0) / 1024),
        pages='    页数：%s' % meta['pages'] if meta.get('pages') else '',
        n_chunks=len(pieces), chars=len(text),
        truncated='\n\n**注意：正文被字数上限截断了，这不是全文。**'
                  '不要把最后一行当作表格的最后一行，也不要据此说「全表只有这些」。'
                  if meta.get('truncated') else '',
        metrics=metric_menu(module, metrics),
        others=other_modules_index(module, metrics),
        questions=question_menu(module, questions)), encoding='utf-8')
    print(json.dumps({'packed': 1, 'sha256': row['sha256'], 'module': module,
                      'score': row.get('score'), 'chars': len(text), 'chunks': len(pieces),
                      'read_from': 'library' if from_library else 'source',
                      'text_md5': text_md5,
                      'same_text_packed_not_read': open_twins or None,
                      'near_twins': approximate or None,
                      'near_twin_note': ('正文与 %d 份高度重合（%s），像是丢了一页'
                                         '版权声明或页眉的副本——sha256 与 text_md5 '
                                         '都挡不住这种。确认是同一份就 skip 掉这一份'
                                         % (len(approximate),
                                            '、'.join('%s %.0f%%%s' %
                                                      (t['sha256'][:12],
                                                       t['shared'] * 100,
                                                       ' 已读' if t['read'] else ' 未读')
                                                      for t in approximate)))
                                        if approximate else None,
                      'same_text_note': ('正文与已开包但尚未读的 %d 份一字不差：%s。'
                                         '两份都读就是把同一篇读两遍——确认是同一份的话'
                                         '读完这一份后 skip 掉另一份' %
                                         (len(open_twins),
                                          ' '.join(t[:12] for t in open_twins)))
                                        if open_twins else None,
                      'unattributed': missing or None,
                      'again': True if a.again and row['sha256'] in read_documents() else None,
                      'brief': str(out / 'brief.md'), 'text': str(out / 'text.md'),
                      **{k: v for k, v in meta.items() if k != 'extract_error'}},
                     ensure_ascii=False))


# --------------------------------------------------------------------------
# validation - the contract is worthless unless something enforces it
# --------------------------------------------------------------------------

def claim_key(fact: dict) -> tuple:
    """What makes two records the same claim: metric, entity, date, caliber.

    Caliber belongs in the key because it is the thing that makes two numbers
    different rather than contradictory.  The store already holds 4406 元/㎡
    and 3736.6 元/㎡ for one project in one month - 施工总包 against 土建本体 -
    and 5.00 against 6.54 backlog years in one quarter, one over capacity and
    one over deliveries.  Keyed without caliber those read as duplicates; keyed
    with it they are what they are, two calibers of one thing.

    bound belongs in the key for the same reason.  「1800-2100 万只」 is two
    records about one metric at one date in one caliber - an upper and a lower.
    Keyed without bound the second one is refused as a duplicate, the range
    collapses to whichever end was recorded first, and the other end survives
    only as prose in notes.  Ranges are the normal shape of an expert call, not
    an edge case.
    """
    caliber = fact.get('caliber')
    dims = (tuple(sorted((k, str(v)) for k, v in caliber.items()))
            if isinstance(caliber, dict) else ())
    return ('claim', fact.get('metric_id'), (fact.get('entity') or {}).get('id'),
            str(fact.get('as_of') or ''), dims, fact.get('bound') or 'point')


def forecast_key(fact: dict) -> tuple | None:
    """The same claim with the vintage stripped off - forecasts only.

    Two forecasts of one year made a year apart are two claims about the same
    future, not one claim recorded twice.  Stored as a bare 2025E they collide,
    and whoever reads them later sees one metric carrying two values and
    averages them.  The vintage is the only thing that separates them, which is
    why a forecast that collides without one is refused.
    """
    as_of = str(fact.get('as_of') or '')
    if 'E' not in as_of:
        return None
    _, metric, entity, _, dims, bound = claim_key(fact)
    return ('forecast', metric, entity, as_of.split('@')[0], dims, bound)


def index_claims(records: list[dict]) -> dict:
    """claim/forecast key -> the fact_id already holding it."""
    claims = {}
    for f in records:
        claims[claim_key(f)] = f.get('fact_id')
        key = forecast_key(f)
        if key is not None:
            claims.setdefault(key, f.get('fact_id'))
    return claims


def check_fact(fact: dict, metrics: dict, seen: set, claims: dict | None = None) -> list[str]:
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
                elif dim.get('free_text'):
                    # 有些口径维本来就是开放的：设备规格、调查选项、清单分项名。
                    # 拿一个占位值糊过去比不填更糟——两台不同规格的 UPS 会撞成
                    # 同一个 claim_key，后录的那台被当成重复直接拒掉。
                    text = str(got).strip()
                    if not text:
                        bad.append('caliber.%s 是自由文本维，不能留空' % dim['id'])
                    elif text in PLACEHOLDER_VALUES:
                        bad.append('caliber.%s = %r 是占位词不是取值——'
                                   '自由文本维要填原文的那一串（规格、选项、分项名），'
                                   '它是把两条数区分开的东西' % (dim['id'], got))
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
        bad.append('as_of 必须是 YYYY / YYYY-MM / YYYY-MM-DD / YYYY-Q1 / YYYY-H1'
                   '（可带 E 或 目标，可带 @快照）：%r' % fact.get('as_of'))

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

    if claims is not None:
        key = forecast_key(fact)
        if key is not None and '@' not in str(fact.get('as_of') or ''):
            prior = claims.get(key)
            if prior:
                bad.append('同一年份的预测已有一条 %s——若是同一个数，属重复录入；'
                           '若是不同时点做出的两次预测，两条都要写成 2025E@2024-04 '
                           '的形式带上做出时点，否则它们会被平均到一起。'
                           '同一家自己的再预测不构成交叉验证。' % prior)
        else:
            prior = claims.get(claim_key(fact))
            if prior:
                bad.append('同口径同时点同 bound 已有一条 %s——要么是重复录入，'
                           '要么少了一个把两者区分开的口径维度；'
                           '若这两个数是一个区间的两端，把它们写成 '
                           'bound: upper 与 bound: lower 两条' % prior)
    return bad


def resolve_document(prefix: str, what: str = 'sha') -> dict:
    """A sha prefix -> the one L1 result it names, or exit saying why not.

    Every command that takes a document takes a prefix, because nobody types
    sixty-four hex characters by hand.  record was the exception and it did not
    say so: --doc wrote whatever it was given straight into the read ledger,
    and the queue matches on the full hash, so a prefix marked nothing as read.
    The document stayed at the top of the queue and got packed again - the only
    way it surfaced was a reader noticing the same file twice.

    Silent is the problem, not strict.  Resolve it here, once, for everyone.
    """
    matched = [r for sha, r in all_results().items() if sha.startswith(prefix)]
    if len(matched) != 1 and FULL_SHA.fullmatch(prefix or ''):
        # A full hash is unambiguous whether or not L1 has a row for it: the
        # read ledger keys on the hash, not on the judgement.  Only a prefix
        # needs a row to resolve against.
        return {'sha256': prefix}
    if len(matched) != 1:
        sys.exit('%s 前缀「%s」匹配到 %d 份判定，要正好一份%s'
                 % (what, prefix, len(matched),
                    '。给长一点的前缀' if len(matched) > 1 else
                    '。这个前缀不在 L1 判定里——抄错了，或者这份还没进判定'))
    return matched[0]


def cmd_record(a):
    # 先把 --doc 解析成完整 sha，再动 facts.json：解析失败要在写之前失败，
    # 否则事实进了库、文件没记成已读，得手工回。
    doc_sha = resolve_document(a.doc, '--doc')['sha256'] if a.doc else None
    metrics = load_metrics()
    incoming = json.loads(Path(a.facts).read_text(encoding='utf-8'))
    if isinstance(incoming, dict):
        incoming = incoming.get('records') or incoming.get('facts') or [incoming]
    store = load_facts()
    seen = {f['fact_id'] for f in store['records']}
    claims = index_claims(store['records'])

    accepted, rejected = [], []
    for fact in incoming:
        problems = check_fact(fact, metrics, seen, claims)
        if problems:
            rejected.append({'fact_id': fact.get('fact_id'), 'problems': problems})
            continue
        seen.add(fact['fact_id'])
        claims[claim_key(fact)] = fact['fact_id']
        key = forecast_key(fact)
        if key is not None:
            claims.setdefault(key, fact['fact_id'])
        accepted.append(fact)

    if rejected and not a.partial:
        print(json.dumps({'incoming': len(incoming), 'accepted': 0,
                          'rejected': len(rejected),
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
            fh.write(json.dumps({'sha256': doc_sha, 'at': now(),
                                 'facts': len(accepted)}, ensure_ascii=False) + '\n')
    # Zero facts is a legal outcome and always was.  But zero facts and an
    # unwritten facts.json print the same line, and --doc has by then marked a
    # document read for good - so say which one this was.
    print(json.dumps({'incoming': len(incoming), 'accepted': len(accepted),
                      'rejected': len(rejected), 'facts_total': len(store['records']),
                      **({'note': 'facts.json 解析出 0 条。读不出数是合法结果；'
                                  '但若不该是 0，先确认文件真的写出来了——'
                                  '这一份已按 --doc 记入已读，重开要用 pack --again --sha'}
                         if not incoming else {})},
                     ensure_ascii=False))
    for r in rejected[:a.show]:
        print('  %s' % r['fact_id'])
        for p in r['problems']:
            print('     - ' + p)


def cmd_attribute(a):
    """Append a corrected L1 verdict.  Nothing is renamed here; restage does that.

    Appending rather than rewriting keeps the superseded verdict readable: the
    whole triage ledger works this way, last row wins, and the record of what
    the preview thought stays next to what the full text turned out to say.
    """
    matches = [r for sha, r in all_results().items() if sha.startswith(a.sha)]
    if len(matches) != 1:
        sys.exit('sha 前缀 %r 匹配到 %d 条判定，要正好一条' % (a.sha, len(matches)))
    row = dict(matches[0])
    if bool(a.org) == bool(a.unrecoverable):
        sys.exit('要么给出 --org，要么用 --unrecoverable 说明全文翻完确实没有——不能都给，也不能都不给')
    if a.year and not YEAR.match(a.year):
        sys.exit('--year 要是四位数字：%r' % a.year)

    was = {'org': row.get('org'), 'year': row.get('year'), 'proposed_name': row.get('proposed_name')}
    if a.org:
        row['org'] = a.org
    if a.year:
        row['year'] = a.year
    if a.unrecoverable:
        # Everything still unknown after reading the whole document was looked
        # for and is not there.  Declaring it per field rather than as one flag
        # matters: 忠县's workbook names 中国移动 on its cover and no year
        # anywhere, so its publisher is known and its year is genuinely absent.
        row['unrecoverable'] = sorted(set(row.get('unrecoverable') or ())
                                      | set(unattributed(row)))
    if a.title:
        row['title'] = a.title
        row['keep_original_name'] = False
    row['attributed'] = {'at': now(), 'by': 'l2-full-text', 'evidence': a.evidence, 'was': was}
    row['proposed_name'] = L1.proposed_name(row)

    with L1.RESULTS.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps({'sha256': row['sha256'], 'org': row.get('org'), 'year': row.get('year'),
                      'unrecoverable': row.get('unrecoverable') or [],
                      'was': was['proposed_name'], 'now': row['proposed_name'],
                      'renamed_by': '改名不在这一步；跑 m4_triage_apply.py restage plan 复核后再 apply'
                      if row['proposed_name'] != was['proposed_name'] else '文件名不变'},
                     ensure_ascii=False))


def matches(row: dict, needle: str | None) -> bool:
    if not needle:
        return True
    hay = '%s %s %s' % (row.get('proposed_name') or '', row.get('rel') or '',
                        row.get('title') or '')
    return needle.lower() in hay.lower()


def cmd_flag(a):
    """Mark a document as one the fact layer must not draw from.

    Appended as a superseding verdict, like every other correction here: the
    score stays, the file stays, the name stays.  Only L2 admission changes.
    """
    matches = [r for sha, r in all_results().items() if sha.startswith(a.sha)]
    if len(matches) != 1:
        sys.exit('sha 前缀 %r 匹配到 %d 条判定，要正好一条' % (a.sha, len(matches)))
    names = [n for n in RESTRICTIONS if getattr(a, n)]
    if not names:
        sys.exit('要给出至少一个：%s' % ' / '.join('--' + n for n in RESTRICTIONS))
    row = dict(matches[0])
    was = restricted(row)
    for name in names:
        if a.clear:
            row.pop(name, None)
        else:
            row[name] = True
    row.setdefault('flagged', []).append(
        {'at': now(), 'fields': names, 'clear': bool(a.clear), 'evidence': a.evidence})

    with L1.RESULTS.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    now_set = restricted(row)
    print(json.dumps({'sha256': row['sha256'], 'score': row.get('score'),
                      'was': was, 'now': now_set,
                      'reasons': [RESTRICTIONS[n] for n in now_set],
                      'effect': '已排除在 L2 精读队列之外；文件与分数都不变'
                      if now_set else '限制已解除，重新进入 L2 队列'},
                     ensure_ascii=False))


def cmd_queue(a):
    pool = eligible(a.min_score, since=a.since)
    by_module = Counter(r.get('category') for r in pool)
    metrics = load_metrics()
    covered = Counter(metrics.get(f['metric_id'], {}).get('module')
                      for f in load_facts()['records'])
    excluded = sum(1 for r in all_results().values()
                   if (r.get('score') or 0) >= a.min_score
                   and r.get('status') == 'ok' and self_authored(r))
    print(json.dumps({'eligible_unread': len(pool), 'min_score': a.min_score,
                      'already_read': len(read_documents()),
                      'self_authored_excluded': excluded,
                      'unattributed': sum(1 for r in pool if unattributed(r)),
                      **({'since': a.since} if a.since else {}),
                      'restricted_excluded': sum(1 for r in all_results().values()
                                                 if (r.get('score') or 0) >= a.min_score
                                                 and r.get('status') == 'ok'
                                                 and restricted(r)),
                      'mb': round(sum(r.get('size', 0) for r in pool) / 1e6)},
                     ensure_ascii=False))
    for module, n in by_module.most_common():
        print('  %-8s 待读 %-4d 已有事实 %d' % (module, n, covered.get(module, 0)))
    # The reading order turns on how many facts a module already has, so print
    # that alongside each row.  With only the score shown, a queue ordered by
    # coverage is indistinguishable from one ordered by score, and nobody can
    # tell whether the ordering did anything.
    # The sha leads, because it is the argument the next command takes: pack
    # addresses a document by hash, and a queue that prints only names makes
    # you go hunting for the one thing you need to act on the row you just read.
    #
    # And --grep, because the reading order is by module coverage: the document
    # you mean to read next can sit two hundred rows down a list that is not
    # sorted by anything you can guess.  Reading one named document should not
    # require paging through the whole queue to find its hash.
    shown = [r for r in pool if matches(r, a.grep)]
    if a.grep:
        print('  匹配「%s」%d 条（共 %d 条待读）' % (a.grep, len(shown), len(pool)))
    for row in shown[:a.show]:
        module = row.get('category') or '?'
        year = document_year(row)
        print('  %s  %-5s 已有事实 %-3d %2s 分 %s %s %s' % (
            row['sha256'][:16], module, covered.get(module, 0), row.get('score'),
            '%4d' % year if year else '  ??', gap_label(row),
            (row.get('proposed_name') or row.get('rel', ''))[:58]))


def open_gaps() -> list[dict]:
    """Menu gaps recorded by skip and not yet marked filled."""
    rows = []
    if GAPS.exists():
        with GAPS.open(encoding='utf-8') as fh:
            for line in fh:
                try: row = json.loads(line)
                except ValueError: continue
                if row.get('gap_id'):
                    rows.append(row)
    latest = {}
    for row in rows:            # append-and-supersede, same as every other ledger
        latest[row['gap_id']] = row
    return [r for r in latest.values() if not r.get('filled')]


def cmd_skip(a):
    """Read it, found nothing the menu can hold, move on - and say what was missing.

    Without this the loop deadlocks.  pack without --sha always returns the
    same top-of-queue document, so a reader who cannot record anything has no
    way forward except record --doc with an empty array, which marks the file
    read and throws the finding away.  The gap is the whole point: it is the
    only signal that the menu is behind the corpus, and it has to survive to
    the machine where the menu is edited.
    """
    row = resolve_document(a.doc, '--doc')
    sha = row['sha256']

    at = now()
    written = []
    for text in a.gap:
        gap_id = hashlib.sha256(('%s|%s' % (sha, text)).encode('utf-8')).hexdigest()[:12]
        written.append({'gap_id': gap_id, 'at': at, 'sha256': sha,
                        'rel': row.get('rel'), 'module': row.get('category'),
                        'gap': text})
    GAPS.parent.mkdir(parents=True, exist_ok=True)
    with GAPS.open('a', encoding='utf-8') as fh:
        for entry in written:
            fh.write(json.dumps(entry, ensure_ascii=False) + '\n')

    READ_LOG.parent.mkdir(parents=True, exist_ok=True)
    with READ_LOG.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps({'sha256': sha, 'at': at, 'facts': 0,
                             'skipped': a.reason or '菜单没有位置',
                             'gaps': [e['gap_id'] for e in written]},
                            ensure_ascii=False) + '\n')
    print(json.dumps({'skipped': sha[:16], 'rel': row.get('rel'),
                      'gaps_recorded': len(written),
                      'gap_ids': [e['gap_id'] for e in written],
                      'note': '已记入已读，队列会前进；菜单补齐后用 '
                              'gaps --filled 销账，再 pack --again --sha %s 重读'
                              % sha[:12]}, ensure_ascii=False))


def cmd_gaps(a):
    if a.filled:
        known = {r['gap_id'] for r in open_gaps()}
        unknown = [g for g in a.filled if g not in known]
        if unknown:
            sys.exit('这些 gap_id 不在未销账的缺口里：%s' % ' '.join(unknown))
        at = now()
        with GAPS.open('a', encoding='utf-8') as fh:
            for row in open_gaps():
                if row['gap_id'] in set(a.filled):
                    fh.write(json.dumps({**row, 'filled': at}, ensure_ascii=False) + '\n')
        print(json.dumps({'filled': a.filled, 'remaining': len(open_gaps())},
                         ensure_ascii=False))
        return

    rows = open_gaps()
    print(json.dumps({'open_gaps': len(rows),
                      'documents_waiting': len({r['sha256'] for r in rows})},
                     ensure_ascii=False))
    for row in sorted(rows, key=lambda r: (r.get('module') or '', r['at'])):
        print('  %s  %-8s %s' % (row['gap_id'], row.get('module') or '?', row['gap']))
        print('           %s' % (row.get('rel') or row['sha256'][:16]))


HEX12 = re.compile(r'^[0-9a-f]{12}$')

# The twelve-hex ids in evidence.source_id are reader cache keys, not sha256
# prefixes.  Expanding one takes two hops: this remap gives the path the cache
# key stood for, and the move ledger gives the sha256 that path carried before
# the library was renamed around it.
CACHE_REMAP = REPO / 'docs/inbox/path_migrations/cache_key_remap_20260818.json'
MOVES = m4_paths.state() / 'moves.jsonl'


def cache_key_to_sha(keys: set) -> dict:
    """reader cache key -> sha256, for the keys asked about.

    Two hops because neither half is enough on its own.  cache_key_remap holds
    cache key -> the path that key was cached from, but those paths are from
    the pre-rename library layout and no longer exist.  moves.jsonl holds every
    rename ever performed, each line carrying the sha256 of the file being
    moved - so the old path is still findable there, attached to a content
    hash that does not move.

    A basename that resolves to more than one sha256 is dropped rather than
    guessed: duplicate copies of one report are common in this corpus, and two
    of them are not necessarily the same bytes.
    """
    if not keys or not CACHE_REMAP.exists() or not MOVES.exists():
        return {}
    try:
        remap = json.loads(CACHE_REMAP.read_text(encoding='utf-8'))
    except ValueError:
        return {}
    want = {}
    for key in keys:
        entry = remap.get(key) or {}
        for field in ('new_path', 'pre_path'):
            path = entry.get(field)
            if path:
                want.setdefault(os.path.basename(path), set()).add(key)
    if not want:
        return {}
    hits = {}
    with MOVES.open(encoding='utf-8') as fh:
        for line in fh:
            for name in want:
                if name in line:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    sha = row.get('sha256')
                    if sha:
                        hits.setdefault(name, set()).add(sha)
    out = {}
    for name, shas in hits.items():
        if len(shas) != 1:
            continue
        sha = next(iter(shas))
        for key in want[name]:
            out[key] = sha
    return out


def owing_provenance(records: list[dict]) -> list[dict]:
    return [f for f in records if not (f.get('evidence') or {}).get('sha256')]


def sources_index() -> dict:
    """source_id -> the sources.json row, for the ones that carry a real name."""
    path = REPO / 'data/sources.json'
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding='utf-8')).get('records') or []
    except ValueError:
        return {}
    return {r['source_id']: r for r in rows if r.get('source_id')}


def cmd_backfill_provenance(a):
    """Turn the sha256 prefixes already sitting in evidence.source_id into
    real evidence.sha256 values.

    119 facts carry no content hash, and the reflex reading of that number is
    「出处丢了」.  It is not: 81 of them name their document as a twelve-hex
    string in evidence.source_id, which is sha256[:12] - the identity is there,
    just abbreviated past the point where a join works.  Expanding it needs the
    L1 ledger, which lives on the machine that did the reading, not in the
    repo; hence a command rather than an edit.

    A prefix that matches two documents is left alone and reported.  Twelve hex
    characters over a corpus this size make that vanishingly unlikely, but
    「不太可能」 is not a reason to write the wrong hash into the fact layer.
    """
    store = load_facts()
    owing = owing_provenance(store['records'])
    ledger = all_results()
    sources = sources_index()
    by_prefix = {}
    for sha in ledger:
        by_prefix.setdefault(sha[:12], []).append(sha)
    inventory_rel = {}
    try:
        for item in L1.load_inventory():
            for rel in item.get('paths') or [item.get('rel')]:
                if rel:
                    inventory_rel.setdefault(rel, item['sha256'])
    except Exception as exc:                  # noqa: BLE001 - inventory is optional here
        print(json.dumps({'note': '读不到清单，只用 L1 账本前缀这一条路：%s'
                          % (type(exc).__name__)}, ensure_ascii=False))

    fixed, ambiguous, unknown, by_path = [], [], [], []
    by_cache_key = []
    cache_keys = cache_key_to_sha({
        str((f.get('evidence') or {}).get('source_id') or '')
        for f in owing
        if HEX12.match(str((f.get('evidence') or {}).get('source_id') or ''))
        and str((f.get('evidence') or {}).get('source_id')) not in by_prefix})
    for fact in owing:
        evidence = fact.get('evidence') or {}
        sid = str(evidence.get('source_id') or '')
        if HEX12.match(sid):
            hits = by_prefix.get(sid) or []
            if len(hits) == 1:
                fixed.append((fact, hits[0], 'prefix'))
            elif len(hits) > 1:
                ambiguous.append({'fact_id': fact['fact_id'], 'prefix': sid,
                                  'matches': hits})
            elif sid in cache_keys:
                by_cache_key.append((fact, cache_keys[sid], sid))
            else:
                unknown.append({'fact_id': fact['fact_id'], 'prefix': sid,
                                'why': '既不是 sha256 前缀，也不是能还原的 reader 缓存键'})
            continue
        rel = (evidence.get('local_file')
               or (sources.get(sid) or {}).get('local_file'))
        sha = inventory_rel.get(rel) if rel else None
        if sha:
            by_path.append((fact, sha, rel))
        else:
            unknown.append({'fact_id': fact['fact_id'],
                            'source_id': sid or None, 'local_file': rel,
                            'why': '既不是 sha256 前缀，也没有能在清单里查到的路径'})

    report = {'owing_before': len(owing),
              '按前缀补全': len(fixed), '按路径补全': len(by_path),
              '按缓存键补全': len(by_cache_key),
              '前缀撞车（未动）': len(ambiguous),
              '查不到（未动）': len(unknown),
              'owing_after': len(owing) - len(fixed) - len(by_path)
                             - len(by_cache_key)}
    if not a.commit:
        report['note'] = '这是干跑，什么都没写。确认无误后加 --commit'
    print(json.dumps(report, ensure_ascii=False))
    for row in ambiguous:
        print('  撞车 %s  前缀 %s 命中 %d 份' %
              (row['fact_id'], row['prefix'], len(row['matches'])))
    for row in unknown[:a.show]:
        print('  查不到 %s  %s' % (row['fact_id'], row['why']))
    if len(unknown) > a.show:
        print('  ……另有 %d 条查不到' % (len(unknown) - a.show))

    if not a.commit or not (fixed or by_path or by_cache_key):
        return
    for fact, sha, how in fixed:
        fact['evidence']['sha256'] = sha
    for fact, sha, rel in by_path:
        fact['evidence']['sha256'] = sha
        fact['evidence'].setdefault('local_file', rel)
    for fact, sha, key in by_cache_key:
        fact['evidence']['sha256'] = sha
    store['updated'] = now()[:10]
    tmp = FACTS.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2) + '\n',
                   encoding='utf-8')
    os.replace(tmp, FACTS)
    written = len(fixed) + len(by_path) + len(by_cache_key)
    print(json.dumps({'written': written,
                      'note': '记得把 test_m4_l2.py 的 PROVENANCE_DEBT 改成 %d'
                              % (len(owing) - written)},
                     ensure_ascii=False))


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
                                              if f.get('corroboration') == '待交叉验证'),
                      '正文指纹_已记': len(fingerprints()),
                      '欠内容哈希的事实': len(owing_provenance(records)),
                      '菜单缺口_未补': len(open_gaps()),
                      '等菜单补齐后重读': len({r['sha256'] for r in open_gaps()})},
                     ensure_ascii=False))
    for module, n in by_module.most_common():
        print('  %-8s %d' % (module, n))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('queue'); q.add_argument('--min-score', type=int, default=MIN_SCORE)
    q.add_argument('--since', type=int, default=0, help='只看这一年及以后的文件')
    q.add_argument('--show', type=int, default=15)
    q.add_argument('--grep', help='只列名字或路径里含这个词的')
    p = sub.add_parser('pack'); p.add_argument('--sha'); p.add_argument('--min-score', type=int, default=MIN_SCORE)
    p.add_argument('--again', action='store_true', help='重开一份已记入已读的文件，须同时给 --sha')
    p.add_argument('--since', type=int, default=0, help='只取这一年及以后的文件')
    r = sub.add_parser('record'); r.add_argument('--facts', required=True)
    r.add_argument('--doc', help='读完的文件 sha256，前缀即可，写进已读账本')
    r.add_argument('--partial', action='store_true', help='收下通过校验的，跳过不通过的')
    r.add_argument('--show', type=int, default=10)
    t = sub.add_parser('attribute', help='把 L1 从预览里没看出来的出处补回判定')
    t.add_argument('--sha', required=True, help='文件 sha256，前缀即可')
    t.add_argument('--org', help='读全文找到的机构名')
    t.add_argument('--unrecoverable', action='store_true', help='全文翻完确实没有署名')
    t.add_argument('--year', help='四位数字')
    t.add_argument('--title', help='顺带修正标题')
    t.add_argument('--evidence', required=True, help='在哪一页哪一处看到的——出处得有出处')
    fl = sub.add_parser('flag', help='把一份文件挡在事实层之外，并记下理由')
    fl.add_argument('--sha', required=True, help='文件 sha256，前缀即可')
    fl.add_argument('--confidential', action='store_true', help='文件自称机密或限制分发')
    fl.add_argument('--pii', action='store_true', help='含个人信息或内网地址')
    fl.add_argument('--clear', action='store_true', help='解除该标记')
    fl.add_argument('--evidence', required=True, help='在哪一页哪一处看到的')
    sk = sub.add_parser('skip', help='读了，菜单里没有位置，记下缺口再往前走')
    sk.add_argument('--doc', required=True, help='文件 sha256，前缀即可')
    sk.add_argument('--gap', required=True, action='append',
                    help='缺的是什么——指标、维度还是枚举值，可重复给')
    sk.add_argument('--reason', help='除了菜单缺口以外的原因')
    g = sub.add_parser('gaps', help='列出未补的菜单缺口')
    # extend 而不是 append：一批补完常常是几十条，一条一个 --filled 抄错的概率
    # 比打字的成本高。--filled a b c 与 --filled a --filled b 都收。
    g.add_argument('--filled', action='extend', nargs='+', default=[],
                   metavar='GAP_ID',
                   help='菜单已补上，销掉这些 gap_id，可给多个、可重复给')
    bp = sub.add_parser('backfill-provenance',
                        help='把 evidence.source_id 里的 sha256 前缀补成完整哈希')
    bp.add_argument('--commit', action='store_true', help='真写；不给就是干跑')
    bp.add_argument('--show', type=int, default=10)
    s = sub.add_parser('status')
    a = ap.parse_args()
    {'queue': cmd_queue, 'pack': cmd_pack, 'record': cmd_record,
     'attribute': cmd_attribute, 'flag': cmd_flag, 'skip': cmd_skip,
     'gaps': cmd_gaps, 'backfill-provenance': cmd_backfill_provenance,
     'status': cmd_status}[a.cmd](a)


if __name__ == '__main__':
    main()
