#!/usr/bin/env python3
"""Pack file previews into a batch for in-session scoring, and record verdicts.

No API key and no network: the preview extraction runs locally, the judgement is
made by the Claude Code session reading the packed batch, and `record` writes
those verdicts back into the same l1_results.jsonl the API path would produce.

  pack   --limit N [--out FILE]   write the next N unscored files as a batch
  record --verdicts FILE          append verdicts to l1_results.jsonl
  status                          progress by category and score
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import m4_triage_l1 as L1

BATCH_DIR = L1.DATA / 'batches'
PREVIEW_CHARS = 400

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


def pending():
    done = L1.done_keys()
    items = [i for i in L1.load_inventory() if i['sha256'] not in done]
    return sorted(items, key=lambda i: priority(i['rel']))


def cmd_pack(a):
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    out = []; l0 = 0
    with L1.RESULTS.open('a', encoding='utf-8') as f:
        for item in pending():
            if len(out) >= a.limit: break
            rec = L1.prepare(item)
            if not rec['needs_model']:
                o = L1.finalize(rec, None, None, None); o['proposed_name'] = L1.proposed_name(o)
                f.write(json.dumps(o, ensure_ascii=False) + '\n'); l0 += 1; continue
            text = clean_preview(rec['preview'])[:PREVIEW_CHARS]
            out.append({'id': rec['sha256'][:12], 'path': rec['rel'], 'suffix': rec['suffix'],
                        'kb': round(rec['size'] / 1024), **({'pages': rec['meta']['pages']} if rec['meta'].get('pages') else {}),
                        'level': rec['level'], 'preview': text})
    path = Path(a.out) if a.out else BATCH_DIR / 'batch.txt'
    # One pipe-delimited line per file.  JSON key names cost more than the data
    # they label at this volume, and the batch is read once by one reader.
    lines = ['# id|suffix|kb|pages|level|path|preview']
    for o in out:
        lines.append('|'.join([o['id'], o['suffix'], str(o['kb']), str(o.get('pages', '')),
                               o['level'], o['path'], o['preview'].replace('|', '/')]))
    path.write_text('\n'.join(lines), encoding='utf-8')
    (BATCH_DIR / 'batch.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'packed': len(out), 'l0_auto_written': l0, 'file': str(path),
                      'remaining_after': len(pending()) - len(out)}, ensure_ascii=False))


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
                      'preview': b.get('preview', b.get('quote', ''))}
    inv = {i['sha256'][:12]: i for i in L1.load_inventory()}
    n = bad = 0
    with L1.RESULTS.open('a', encoding='utf-8') as f:
        for v in verdicts:
            b = batch.get(v.get('id')); item = inv.get(v.get('id'))
            if not b or not item: bad += 1; continue
            rec = {'sha256': item['sha256'], 'rel': b['path'], 'suffix': item['suffix'], 'size': item['size'],
                   'task_version': L1.TASK_VERSION, 'level': b['level'], 'category': None,
                   'preview': b['preview'], 'meta': {}, 'paths': item['paths'], 'copies': item['copies']}
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
    r = s.add_parser('record'); r.add_argument('--verdicts', required=True); r.add_argument('--batch'); r.add_argument('--digests', action='store_true')
    s.add_parser('status')
    a = ap.parse_args()
    {'pack': cmd_pack, 'record': cmd_record, 'status': cmd_status}[a.cmd](a)


if __name__ == '__main__':
    main()
