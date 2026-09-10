#!/usr/bin/env python3
"""Pack file previews into a batch for in-session scoring, and record verdicts.

No API key and no network: the preview extraction runs locally, the judgement is
made by the Claude Code session reading the packed batch, and `record` writes
those verdicts back into the same l1_results.jsonl the API path would produce.

  pack   --limit N [--workers N] [--out FILE]   write the next N unscored files
  record --verdicts FILE          append verdicts to l1_results.jsonl
  status                          progress by category and score
  versions [--min-score N]        report same-report-different-date groups
"""
from __future__ import annotations
import argparse, json, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import m4_triage_l1 as L1
import m4_office_text

BATCH_DIR = L1.DATA / 'batches'
PREVIEW_CHARS = 400
# A workbook opens with its sheet names - eleven of them on a forecast model -
# so a 400-character window can close before the first row of data.  Office
# formats get a wider one; PDFs and plain text still lead with their title.
OFFICE_PREVIEW_CHARS = 1200
MAX_WORKERS = 16

# Word/PowerPoint field codes and table-of-contents scaffolding carry no meaning
# but eat most of a short preview, so they are stripped before truncation.
NOISE = re.compile(r'(HYPERLINK|PAGEREF|TOC)\s+\\?[A-Za-z]?[^ ]*|_Toc\d+|style\.visibility|ppt_[xy]|\\[hzou]\b|EMBED [A-Za-z.0-9]+')


def clean_preview(text: str) -> str:
    text = NOISE.sub(' ', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'(?:\s\d+\s){4,}', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def priority(rel: str):
    """Most useful material first, so partial progress is still worth having."""
    top = rel.split('/')[0]
    rank = {'数据中心报告购买': 0, '数据中心资料': 1, '报告': 2, 'Global半导体研究资料': 3,
            '42套数据中心IDC机房楼机房2024 —2025': 5, '要删': 6}.get(top, 4)
    return (rank, rel)


def last_results() -> dict:
    """The newest row per file: record appends, so the last one wins."""
    last = {}
    if L1.RESULTS.exists():
        with L1.RESULTS.open(encoding='utf-8') as fh:
            for line in fh:
                try: r = json.loads(line)
                except ValueError: continue
                if 'sha256' in r: last[r['sha256']] = r
    return last


def blind_scored() -> set:
    """Files judged on their filename alone that can now actually be opened.

    The first pass routed .xlsx / .xls / .ppt to _office_pending and never
    opened them, so a workbook of forecast data was scored from its name while
    its prose summary was scored from its text.  These are the ones worth
    asking again about.
    """
    return {sha for sha, r in last_results().items()
            if r.get('level') == 'n' and r.get('suffix') in m4_office_text.SUPPORTED
            and not opened_and_empty(r)}


def opened_and_empty(r: dict) -> bool:
    """True when the extractor really ran on this file and found no text.

    Empty meta means the file was never opened - the first pass routed it to
    _office_pending, or it was read back through a stale path - so it still
    owes us a look.  A transient failure (the file was not where the inventory
    said) is also worth retrying.  Sheet counts, text atom counts, or a
    permanent no-text-layer verdict all mean the answer will not change.
    """
    meta = r.get('meta') or {}
    if not meta:
        return False
    if meta.get('no_text_layer'):
        return True
    # Any other error is transient - a stale path, a truncated download - and
    # the file still owes us a look.
    return not meta.get('extract_error')


def pending(redo=False):
    if redo:
        wanted = blind_scored()
        items = [i for i in L1.load_inventory() if i['sha256'] in wanted]
    else:
        done = L1.done_keys()
        items = [i for i in L1.load_inventory() if i['sha256'] not in done]
    return sorted(items, key=lambda i: priority(i['rel']))


def prepared(item):
    """L1.prepare, but a file that cannot be previewed does not kill the batch."""
    try:
        return L1.prepare(item), None
    except Exception as exc:  # noqa: BLE001 - reported per file, batch continues
        return None, {'rel': item.get('rel'), 'error': str(exc)[:100]}


def cmd_pack(a):
    """Pack the next unscored files, extracting previews `a.workers` at a time.

    Preview extraction is local CPU work (pdftotext and friends), not a model
    call, but one file at a time still makes a 200-file batch a wait.  Files are
    prepared in priority order a chunk at a time, so which files land in the
    batch does not depend on how many threads ran."""
    workers = getattr(a, 'workers', None)
    workers = 4 if workers is None else workers
    if not isinstance(workers, int) or not 1 <= workers <= MAX_WORKERS:
        raise SystemExit('workers must be 1..%d' % MAX_WORKERS)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    out = []; l0 = 0; failed = []
    redo = getattr(a, 'redo', False)
    items = pending(redo)
    position = 0
    with L1.RESULTS.open('a', encoding='utf-8') as f:
        while len(out) < a.limit and position < len(items):
            chunk = items[position:position + max(a.limit, 1)]
            position += len(chunk)
            with ThreadPoolExecutor(workers) as pool:
                results = list(pool.map(prepared, chunk))  # map keeps chunk order
            for rec, problem in results:
                if len(out) >= a.limit: break
                if problem is not None:
                    failed.append(problem); continue
                if not rec['needs_model']:
                    o = L1.finalize(rec, None, None, None); o['proposed_name'] = L1.proposed_name(o)
                    f.write(json.dumps(o, ensure_ascii=False) + '\n'); l0 += 1; continue
                budget = OFFICE_PREVIEW_CHARS if rec['suffix'] in m4_office_text.SUPPORTED else PREVIEW_CHARS
                text = clean_preview(rec['preview'])[:budget]
                out.append({'id': rec['sha256'][:12], 'path': rec['rel'], 'suffix': rec['suffix'],
                            'kb': round(rec['size'] / 1024), **({'pages': rec['meta']['pages']} if rec['meta'].get('pages') else {}),
                            'level': rec['level'], 'preview': text, 'meta': rec['meta']})
    path = Path(a.out) if a.out else BATCH_DIR / 'batch.txt'
    # One pipe-delimited line per file.  JSON key names cost more than the data
    # they label at this volume, and the batch is read once by one reader.
    lines = ['# id|suffix|kb|pages|level|path|preview']
    for o in out:
        lines.append('|'.join([o['id'], o['suffix'], str(o['kb']), str(o.get('pages', '')),
                               o['level'], o['path'], o['preview'].replace('|', '/')]))
    path.write_text('\n'.join(lines), encoding='utf-8')
    (BATCH_DIR / 'batch.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'packed': len(out), 'l0_auto_written': l0, 'workers': workers,
                      'preview_failed': len(failed), 'file': str(path),
                      # recomputed with the same selector: asking the plain
                      # queue how much redo work is left reports every scored
                      # file as done and lands on a negative remainder
                      'remaining_after': len(pending(redo)) - len(out)}, ensure_ascii=False))
    for problem in failed[:5]:
        print(json.dumps(problem, ensure_ascii=False))


FIELDS = ('id', 'score', 'module', 'doc_type', 'year', 'org', 'title', 'keep_original_name', 'confidence', 'rationale')


def parse_verdicts(path: Path):
    """Accept either a JSON array or the compact pipe-delimited line format.

    Compact line: id|score|module|doc_type|year|org|title|keep(1/0)|conf(h/m/l)|rationale
    It exists purely to keep the judging pass cheap; the recorded row is identical.
    """
    raw = path.read_text(encoding='utf-8').strip()
    if raw.startswith('['):
        return json.loads(raw)
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('#'): continue
        f = line.split('|')
        if len(f) < 9: continue
        out.append({'id': f[0].strip(), 'score': int(f[1]), 'module': f[2].strip(), 'doc_type': f[3].strip(),
                    'year': f[4].strip() or '未知', 'org': f[5].strip() or '未知', 'title': f[6].strip(),
                    'keep_original_name': f[7].strip() not in ('0', 'n', 'false'),
                    'confidence': {'h': 'high', 'm': 'medium', 'l': 'low'}.get(f[8].strip()[:1], 'medium'),
                    'rationale': f[9].strip() if len(f) > 9 else '', 'evidence': '', 'language': ''})
    return out


def cmd_record(a):
    verdicts = parse_verdicts(Path(a.verdicts))
    src = Path(a.batch) if a.batch else (BATCH_DIR / 'digest_batch.json' if a.digests else BATCH_DIR / 'batch.json')
    raw = json.loads(src.read_text(encoding='utf-8'))
    # Digest rows are keyed by full sha and carry `rel`/`quote` instead of
    # `path`/`preview`; normalise so one record path serves both batch shapes.
    batch = {}
    for b in raw:
        key = b.get('id') or b['sha256'][:12]
        batch[key] = {'path': b.get('path') or b['rel'], 'level': b['level'],
                      'preview': b.get('preview', b.get('quote', '')),
                      'meta': b.get('meta') or {}}
    inv = {i['sha256'][:12]: i for i in L1.load_inventory()}
    n = bad = 0
    with L1.RESULTS.open('a', encoding='utf-8') as f:
        for v in verdicts:
            b = batch.get(v.get('id')); item = inv.get(v.get('id'))
            if not b or not item: bad += 1; continue
            rec = {'sha256': item['sha256'], 'rel': b['path'], 'suffix': item['suffix'], 'size': item['size'],
                   'task_version': L1.TASK_VERSION, 'level': b['level'], 'category': None,
                   'preview': b['preview'], 'meta': b['meta'], 'paths': item['paths'], 'copies': item['copies']}
            parsed = {k: v[k] for k in ('score', 'module', 'title', 'org', 'year', 'keep_original_name',
                                        'doc_type', 'language', 'rationale', 'evidence', 'confidence') if k in v}
            for k, d in (('language', '未知'), ('evidence', ''), ('doc_type', 'other'), ('confidence', 'medium'),
                         ('org', '未知'), ('year', '未知'), ('rationale', ''), ('keep_original_name', True)):
                parsed.setdefault(k, d)
            if 'score' not in parsed or 'module' not in parsed or 'title' not in parsed: bad += 1; continue
            out = L1.finalize(rec, parsed, {'judge': 'claude-code-session'}, None)
            out['proposed_name'] = L1.proposed_name(out); out['model'] = 'claude-code-session'
            f.write(json.dumps(out, ensure_ascii=False) + '\n'); n += 1
    print(json.dumps({'recorded': n, 'rejected': bad, 'total_scored': len(L1.done_keys())}, ensure_ascii=False))


IDLE_GAP_SECONDS = 300.0


def working_rate(stamps, idle_gap=IDLE_GAP_SECONDS):
    """Files per minute while extraction was actually running.

    Dividing by the age of the digest file counts every hour the machine sat
    idle between sessions, which made the ETA wrong by an order of magnitude
    (0.7/min and 343 hours remaining, measured over a night nothing ran).  Sum
    only the gaps between consecutive digests that look like work, and divide
    the files that produced them.  Returns None when there is nothing to
    measure, so the caller can say so instead of inventing a number.
    """
    stamps = sorted(s for s in stamps if s is not None)
    if len(stamps) < 2:
        return None
    active = 0.0
    counted = 0
    for before, after in zip(stamps, stamps[1:]):
        gap = after - before
        if 0 <= gap <= idle_gap:
            active += gap
            counted += 1
    if not counted or active <= 0:
        return None
    return counted / (active / 60)


def digest_stamps(paths):
    """Epoch seconds of each digest row that carries an `at` field."""
    import calendar, time as _time
    out = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.open(encoding='utf-8'):
            try:
                at = json.loads(line).get('at')
            except ValueError:
                continue
            if not at:
                continue
            try:
                out.append(calendar.timegm(_time.strptime(at, '%Y-%m-%dT%H:%M:%SZ')))
            except ValueError:
                continue
    return out


# A report issued repeatedly (weekly, a re-upload days later) lands as several
# files with different bytes, so SHA-256 dedup never sees them.  Matching the
# judged title exactly does not find them either: four copies of one report were
# titled four different ways.  The filename is the stabler signal, but only
# fuzzily -- the same report arrives as
#   20250925-国信证券-化工行业·数据中心及AI服务器液冷冷却液行业分析框架(40页).pdf
#   20251003-国信证券：行业分析框架：国信化工：数据中心及AI服务器液冷冷却液(40页).pdf
# so names are compared by character-trigram overlap.  Measured on real files:
# copies of one report score 0.48 to 0.95, unrelated files at most 0.35, so 0.45
# sits in the gap with margin on both sides.
SIM_THRESHOLD = 0.45
GRAM = 3
# A trigram in more than this share of names ("数据中心" and friends) says nothing
# about which report a file is, and indexing it would compare everything to
# everything.  The floor matters: on a small set the share alone drops to two or
# three rows and discards the very features that identify a report.
COMMON_GRAM_SHARE = 0.10
COMMON_GRAM_FLOOR = 200
DATE_PREFIX = re.compile(r'^\s*(?:20\d{6}|20\d{2}[-_.]?\d{2}[-_.]?\d{2})[-_\s]*')
PAGE_TAIL = re.compile(r'[\(（]\s*\d+\s*页\s*[\)）]|[\(（]\s*(?:重复版|副本|copy|\d+)\s*[\)）]', re.I)
PUNCT = re.compile(r'[\s·・:：,，。.、\-_()（）\[\]【】/\\|"“”\'‘’&]+')


def name_key(rel: str) -> str:
    """Normalise a filename to what stays the same across issues of one report."""
    stem = Path(str(rel or '')).stem
    stem = DATE_PREFIX.sub('', stem)
    stem = PAGE_TAIL.sub('', stem)
    return PUNCT.sub('', stem).lower()


def trigrams(text: str) -> set:
    if len(text) <= GRAM:
        return {text} if text else set()
    return {text[i:i + GRAM] for i in range(len(text) - GRAM + 1)}


def similarity(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def scored_rows():
    rows = []
    if not L1.RESULTS.exists():
        return rows
    for line in L1.RESULTS.open(encoding='utf-8'):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('status') == 'ok' and row.get('rel'):
            rows.append(row)
    return rows


def version_groups(rows, min_score=0, threshold=SIM_THRESHOLD):
    """Cluster rows whose filenames say they are the same report issued twice.

    Candidates come from an inverted trigram index rather than comparing every
    pair, so this stays usable on tens of thousands of rows.  Nothing is moved
    or deleted; this only reports.
    """
    import collections
    items = [r for r in rows if (r.get('score') or 0) >= min_score]
    names = [name_key(r.get('rel')) for r in items]
    grams = [trigrams(n) for n in names]

    index = collections.defaultdict(list)
    for position, gset in enumerate(grams):
        for gram in gset:
            index[gram].append(position)
    cap = max(COMMON_GRAM_FLOOR, int(len(items) * COMMON_GRAM_SHARE))
    index = {gram: rows_ for gram, rows_ in index.items() if len(rows_) <= cap}

    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[b] = a

    for position, gset in enumerate(grams):
        shared = collections.Counter()
        for gram in gset:
            for other in index.get(gram, ()):
                if other > position:
                    shared[other] += 1
        need = max(1, int(len(gset) * threshold * 0.5))
        for other, count in shared.items():
            if count >= need and similarity(gset, grams[other]) >= threshold:
                union(position, other)

    def rank(position):
        row = items[position]
        pages = (row.get('meta') or {}).get('pages') or 0
        excluded = 1 if str(row.get('rel', '')).startswith('要删/') else 0
        return (excluded, -pages, -(row.get('size') or 0), row.get('rel') or '')

    clusters = collections.defaultdict(list)
    for position in range(len(items)):
        clusters[find(position)].append(position)

    out = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        members = sorted(members, key=rank)
        out.append({'keep': items[members[0]], 'extra': [items[m] for m in members[1:]]})
    return sorted(out, key=lambda g: -len(g['extra']))


def cmd_versions(a):
    rows = scored_rows()
    groups = version_groups(rows, a.min_score, a.threshold)
    extra = sum(len(g['extra']) for g in groups)
    wasted = sum(sum(m.get('size') or 0 for m in g['extra']) for g in groups)
    print(json.dumps({'judged_rows': len(rows), 'threshold': a.threshold,
                      'version_groups': len(groups), 'extra_copies': extra,
                      'share_of_judged': round(extra / len(rows), 3) if rows else 0,
                      'extra_bytes': wasted}, ensure_ascii=False))
    for group in groups[:a.show]:
        keep = group['keep']
        print('%d 份 · %s' % (len(group['extra']) + 1, Path(keep.get('rel') or '').name))
        print('   保留 %s' % (keep.get('rel') or ''))
        for member in group['extra']:
            print('   重复 %s' % (member.get('rel') or ''))


def cmd_status(a):
    """Progress plus an ETA measured from how fast extraction actually runs."""
    import collections, glob, time
    from pathlib import Path
    cat = collections.Counter(); sc = collections.Counter(); n = 0
    if L1.RESULTS.exists():
        for line in L1.RESULTS.open(encoding='utf-8'):
            try: r = json.loads(line)
            except ValueError: continue
            n += 1; cat[r.get('category')] += 1
            if r.get('score') is not None: sc[r['score']] += 1
    scored = L1.done_keys(); items = L1.load_inventory()
    need = sum(1 for i in items if i['sha256'] not in scored and not i['all_excluded']
               and L1.route(i['suffix']) in ('text', '_office_pending', '_archive_review', '_format_review'))
    auto = len(items) - len(scored) - need
    digests = [Path(L1.DATA / 'digests.jsonl')] + [Path(p) for p in sorted(glob.glob(str(L1.DATA / 'digests.part*.jsonl')))]
    total = sum(sum(1 for _ in p.open(encoding='utf-8')) for p in digests if p.exists())
    rate = working_rate(digest_stamps(digests))
    basis = '运行中实测'
    if rate is None:  # older digests carry no timestamp
        first = min((p.stat().st_birthtime for p in digests if p.exists()), default=time.time())
        rate = total / max((time.time() - first) / 60, 1)
        basis = '挂钟含空闲，偏低'
    print(json.dumps({'唯一文件': len(items), '已打分': len(scored), '剩余': len(items) - len(scored),
                      '需抽取打分': need, '自动归类': auto, '已抽取': total,
                      '抽取速率_每分钟': round(rate, 1), '速率口径': basis,
                      '预计剩余小时': round(need / rate / 60, 1) if rate else None}, ensure_ascii=False))
    for k, v in cat.most_common(10): print(f'  {v:7d}  {k}')
    if sc: print('分数分布: ' + json.dumps({str(k): sc[k] for k in sorted(sc, reverse=True)}))


def main():
    ap = argparse.ArgumentParser(); s = ap.add_subparsers(dest='cmd', required=True)
    p = s.add_parser('pack'); p.add_argument('--limit', type=int, default=40); p.add_argument('--out')
    p.add_argument('--redo', action='store_true',
                   help='re-queue files scored from their filename alone that can now be opened')
    p.add_argument('--workers', type=int, default=4,
                   help='preview extractions in parallel (1..%d); local CPU work, no model' % MAX_WORKERS)
    r = s.add_parser('record'); r.add_argument('--verdicts', required=True); r.add_argument('--batch'); r.add_argument('--digests', action='store_true')
    s.add_parser('status')
    v = s.add_parser('versions'); v.add_argument('--min-score', type=int, default=0)
    v.add_argument('--show', type=int, default=15, help='groups to print in full')
    v.add_argument('--threshold', type=float, default=SIM_THRESHOLD,
                   help='filename similarity to call two files one report (0..1)')
    a = ap.parse_args()
    {'pack': cmd_pack, 'record': cmd_record, 'status': cmd_status, 'versions': cmd_versions}[a.cmd](a)


if __name__ == '__main__':
    main()
