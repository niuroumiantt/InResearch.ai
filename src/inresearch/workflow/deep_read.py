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

from inresearch.materials.artifacts import verified_content
from inresearch.paths import project_root
from inresearch.storage.jsonl import append_record, read_rows
from inresearch.materials.records import commit_result, result_revision, current_results
from inresearch.storage.files import locked, write_json
from functools import wraps
from inresearch.knowledge.fact_contract import CORROBORATION as CORROBORATION, PLACEHOLDER_VALUES as PLACEHOLDER_VALUES, claim_key as claim_key, forecast_key as forecast_key, index_claims, check_fact as check_fact
from inresearch.delivery.reading_packet import FULL_TEXT_CHARS as FULL_TEXT_CHARS, full_text as full_text, chunks as chunks, metric_menu as metric_menu, other_modules_index as other_modules_index, question_menu, ATTRIBUTION_ASK, PACKET_HEAD

import argparse, hashlib, json, os, re, sys, time
from collections import Counter
from pathlib import Path

from inresearch.materials import paths as m4_paths
from inresearch.materials import triage as L1

REPO = project_root()
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
# 完整 sha 与前缀要分开对待：完整的自证，前缀得有判定可解。
FULL_SHA = re.compile(r'[0-9a-f]{64}')
# L1's budget is a preview's; L2's is the document's.  A workbook cut at
# twenty thousand characters is read as though its last surviving row were its
# last row, and the facts drawn from it would be silently partial.

# 自由文本维填这些等于没填：它们不区分任何两条数，而区分正是这类维存在的理由。
# A year is always the anchor; everything after it says what kind of year.
#   2022-01        an actual, to the month
#   2026-Q1        a quarter
#   2026E          a forecast, not an outturn
#   2025-2027E     a forecast over a span
#   2025目标        a target somebody set, which is neither
#   2025E@2024-04  a 2025 forecast made in April 2024 - the vintage matters,
#                  because the same year forecast twelve months apart is two
#                  different claims and must not be averaged together
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
    return {row['sha256'] for row in read_rows(READ_LOG)
            if row.get('sha256') and 'twin_of' not in row}


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


# --------------------------------------------------------------------------
# the reading packet
# --------------------------------------------------------------------------


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
    return {row['sha256']: row['text_md5'] for row in read_rows(TEXT_MD5)
            if row.get('sha256') and row.get('text_md5')}


def remember_fingerprint(sha: str, text_md5: str,
                         sketch: list[str] | None = None) -> None:
    TEXT_MD5.parent.mkdir(parents=True, exist_ok=True)
    append_record(TEXT_MD5, {'sha256': sha, 'text_md5': text_md5, 'at': now(),
                             **({'sketch': sketch} if sketch else {})})


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
    return {row['sha256']: row['sketch'] for row in read_rows(TEXT_MD5)
            if row.get('sha256') and row.get('sketch')}


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
    with verified_content(path, row['sha256']):
        text, meta = full_text(path, row['suffix'])
    if not text.strip():
        print(json.dumps({'packed': 0, 'sha256': row['sha256'], 'rel': row.get('rel'),
                          'meta': meta, 'reason': '抽不出正文'}, ensure_ascii=False))
        return
    text_md5 = text_fingerprint(text, meta)
    if text_md5:
        twins = already_read_with_same_text(row['sha256'], text_md5)
        # Equal extracted text does not prove equal diagrams, footnotes or
        # document identity. Keep the observation; never block another SHA.
        # 在记账之前问：正文一样、还没读、已经开过包的是哪几份。
        # 记账之后再问就问不出来了——自己会出现在账本里。
        open_twins = packed_not_read_with_same_text(row['sha256'], text_md5)
        sketch = text_sketch(text)
        remember_fingerprint(row['sha256'], text_md5, sketch)
    else:
        twins, open_twins, sketch = [], [], []
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
                      'same_text_already_read': twins or None,
                      'near_twin_note': ('提取文本与其他材料高度重合；核对原件图表、脚注和版本差异。'
                                         '相似度不能证明缺的只是版权页，不能据此自动跳读或沿用旧证据。'
                                         if approximate else None),
                      'same_text_note': ('提取文本相同；原件 SHA 不同，图表或其他未抽取内容可能不同。'
                                         '保留独立内容身份，确认原件等价前不自动跳读。'
                                         if twins or open_twins else None),
                      'unattributed': missing or None,
                      'again': True if a.again and row['sha256'] in read_documents() else None,
                      'brief': str(out / 'brief.md'), 'text': str(out / 'text.md'),
                      **{k: v for k, v in meta.items() if k != 'extract_error'}},
                     ensure_ascii=False))


# --------------------------------------------------------------------------
# validation - the contract is worthless unless something enforces it
# --------------------------------------------------------------------------


def fact_write(fn):
    @wraps(fn)
    def commit(args):
        with locked(FACTS):
            return fn(args)
    return commit


def resolve_document(prefix: str, what: str = 'sha') -> dict:
    """A sha prefix -> the one L1 result it names, or exit saying why not.

    Every command that takes a document takes a prefix, because nobody types
    sixty-four hex characters by hand.  record used to be the exception and it
    did not say so: --doc wrote whatever it was given straight into the read
    ledger, and the queue matches on the full hash, so a prefix marked nothing
    as read - the document stayed at the top of the queue and got packed
    again.  Refusing a prefix outright fixes the silence but leaves record the
    odd one out; resolving it here, once, fixes both.
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


@fact_write
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
    existing = {f['fact_id']: f for f in store['records']}
    replayed = 0

    accepted, rejected = [], []
    for fact in incoming:
        # 比的是解析后的完整 sha，不是命令行上那一串：--doc 收前缀，而事实
        # 自证的 evidence.sha256 永远是完整哈希，拿前缀去比会全部判成不一致。
        if doc_sha and (fact.get('evidence') or {}).get('sha256') != doc_sha:
            rejected.append({'fact_id': fact.get('fact_id'), 'problems': ['evidence.sha256 与 --doc 材料身份不一致']})
            continue
        if doc_sha and existing.get(fact.get('fact_id')) == fact:
            replayed += 1
            continue
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
        return 1

    if accepted:
        store['records'].extend(accepted)
        store['updated'] = now()[:10]
        write_json(FACTS, store)
    if doc_sha and not rejected:
        READ_LOG.parent.mkdir(parents=True, exist_ok=True)
        append_record(READ_LOG, {'sha256': doc_sha, 'at': now(),
                             'facts': len(accepted)})
    # Zero facts is a legal outcome and always was.  But zero facts and an
    # unwritten facts.json print the same line, and --doc has by then marked a
    # document read for good - so say which one this was.
    print(json.dumps({'incoming': len(incoming), 'accepted': len(accepted),
                      'rejected': len(rejected), 'replayed': replayed, 'facts_total': len(store['records']),
                      **({'note': 'facts.json 解析出 0 条。读不出数是合法结果；'
                                  '但若不该是 0，先确认文件真的写出来了——'
                                  '这一份已按 --doc 记入已读，重开要用 pack --again --sha'}
                         if not incoming else {})},
                     ensure_ascii=False))
    for r in rejected[:a.show]:
        print('  %s' % r['fact_id'])
        for p in r['problems']:
            print('     - ' + p)
    return 1 if rejected else 0


def cmd_attribute(a):
    """Append a corrected L1 verdict.  Nothing is renamed here; restage does that.

    Appending rather than rewriting keeps the superseded verdict readable: the
    whole triage ledger works this way, the effective success is selected centrally, and what
    the preview thought stays next to what the full text turned out to say.
    """
    matches = [r for sha, r in all_results().items() if sha.startswith(a.sha)]
    if len(matches) != 1:
        sys.exit('sha 前缀 %r 匹配到 %d 条判定，要正好一条' % (a.sha, len(matches)))
    row = dict(matches[0])
    base_revision = result_revision(row)
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

    commit_result(L1.RESULTS, row, base_revision)
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
    base_revision = result_revision(row)
    was = restricted(row)
    for name in names:
        if a.clear:
            row.pop(name, None)
        else:
            row[name] = True
    row.setdefault('flagged', []).append(
        {'at': now(), 'fields': names, 'clear': bool(a.clear), 'evidence': a.evidence})

    commit_result(L1.RESULTS, row, base_revision)
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
    rows = [row for row in read_rows(GAPS) if row.get('gap_id')]
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
    for entry in written:
        append_record(GAPS, entry)

    READ_LOG.parent.mkdir(parents=True, exist_ok=True)
    append_record(READ_LOG, {'sha256': sha, 'at': at, 'facts': 0,
                         'skipped': a.reason or '菜单没有位置',
                         'gaps': [e['gap_id'] for e in written]})
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
        for row in open_gaps():
            if row['gap_id'] in set(a.filled):
                append_record(GAPS, {**row, 'filled': at})
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
    for row in read_rows(MOVES):
        line = json.dumps(row, ensure_ascii=False)
        for name in want:
            if name in line and row.get('sha256'):
                hits.setdefault(name, set()).add(row['sha256'])
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


@fact_write
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
    write_json(FACTS, store)
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
    sub.add_parser('status')
    a = ap.parse_args()
    return {'queue': cmd_queue, 'pack': cmd_pack, 'record': cmd_record,
     'attribute': cmd_attribute, 'flag': cmd_flag, 'skip': cmd_skip,
     'gaps': cmd_gaps, 'backfill-provenance': cmd_backfill_provenance,
     'status': cmd_status}[a.cmd](a)


if __name__ == '__main__':
    raise SystemExit(main())
