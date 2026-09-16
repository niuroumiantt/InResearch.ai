#!/usr/bin/env python3
"""Pack file previews into a batch for in-session scoring, and record verdicts.

No API key and no network: the preview extraction runs locally, the judgement is
made by the Claude Code session reading the packed batch, and `record` writes
those verdicts back into the same l1_results.jsonl the API path would produce.

  pack   --limit N [--workers N] [--cohort C]   write the next N files to judge
  record --verdicts FILE          append verdicts to l1_results.jsonl
  status                          progress by category and score
  versions [--min-score N]        report same-report-different-date groups
"""
from __future__ import annotations
from inresearch.materials.records import commit_result, result_revision
import argparse, json, re, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from inresearch.materials import triage as L1
from inresearch.workflow import l1_batch as L1B

BATCH_DIR = L1.DATA / 'batches'


def now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')


def overlap_with_previous(batch: list[dict]) -> int:
    """How many of these files were already in the batch sitting on disk."""
    previous = BATCH_DIR / 'batch.json'
    if not previous.exists() or not batch:
        return 0
    try:
        rows = json.loads(previous.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return 0
    seen = {r.get('id') for r in rows}
    return sum(1 for b in batch if b['id'] in seen)


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
    if not isinstance(workers, int) or not 1 <= workers <= L1B.MAX_WORKERS:
        raise SystemExit('workers must be 1..%d' % L1B.MAX_WORKERS)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    out = []; l0 = 0; failed = []; unchanged = 0
    cohort = getattr(a, 'cohort', None) or ('blind' if getattr(a, 'redo', False) else 'new')
    if cohort not in L1B.COHORTS:
        raise SystemExit('cohort must be one of %s' % ' / '.join(L1B.COHORTS))
    shas = [x.strip() for x in (getattr(a, 'sha', None) or '').split(',') if x.strip()]
    base = L1B.last_results()
    items = L1B.pending(cohort, shas)
    position = 0
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
                commit_result(L1.RESULTS, o, result_revision(base.get(o['sha256']))); l0 += 1; continue
            if cohort == 'cells' and L1B.nothing_new(rec['meta']):
                # Re-read and there is still nothing to see.  Spending a
                # judgement here buys nothing, but leaving the row alone
                # leaves it at the head of the cohort for every future
                # pack - the queue would never drain.  So carry the old
                # verdict forward with the fresh meta attached, which both
                # records that the re-read happened and takes the file out
                # of the cohort by its own definition.
                prior = base.get(rec['sha256'])
                if prior:
                    row = {**prior, 'meta': rec['meta'],
                           'rechecked': {'at': now(), 'cohort': cohort,
                                         'verdict': 'unchanged',
                                         'reason': '重新抽取后仍无单元格，预览不会变'}}
                    commit_result(L1.RESULTS, row, result_revision(prior))
                    unchanged += 1
                    continue
            text = L1B.clean_preview(rec['preview'])[:L1B.preview_budget(rec['suffix'])]
            out.append({'id': rec['sha256'][:12], 'path': rec['rel'], 'suffix': rec['suffix'],
                        'kb': round(rec['size'] / 1024), **({'pages': rec['meta']['pages']} if rec['meta'].get('pages') else {}),
                        'level': rec['level'], 'preview': text, 'meta': rec['meta'],
                        'base_revision': result_revision(base.get(rec['sha256']))})
    # A file leaves its cohort when `record` writes a verdict, not when pack
    # writes the batch.  So packing twice without recording in between builds
    # the same batch again, and every counter says the same thing it said the
    # first time - four identical lines and no way to tell nothing advanced.
    repeat = overlap_with_previous(out)
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
                      'cohort': cohort, 'unchanged_carried_forward': unchanged,
                      **({'与上一批重复': repeat,
                          'note': '上一批还没 record，这次打包的是同一批文件。'
                                  '先判 batch.txt 再 record --verdicts，队列才会往前走'}
                         if repeat and repeat == len(out) else
                         {'与上一批重复': repeat} if repeat else {}),
                      'preview_failed': len(failed), 'file': str(path),
                      # recomputed with the same selector: asking the plain
                      # queue how much redo work is left reports every scored
                      # file as done and lands on a negative remainder
                      'remaining_after': len(L1B.pending(cohort, shas)) - len(out)}, ensure_ascii=False))
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
                      'meta': b.get('meta') or {},
                      **({'base_revision': b['base_revision']} if 'base_revision' in b else {})}
    inv = {i['sha256'][:12]: i for i in L1.load_inventory()}
    n = bad = 0
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
        out = L1.finalize(rec, parsed, {'judge': getattr(a, 'executor', 'terminal')}, None)
        out['proposed_name'] = L1.proposed_name(out)
        out['executor'] = getattr(a, 'executor', 'terminal')
        out['model'] = getattr(a, 'model', None)
        out['model_identity'] = 'reported_by_executor' if out['model'] else 'unknown'
        try:
            if 'base_revision' in b:
                commit_result(L1.RESULTS, out, expected_revision=b['base_revision'])
            else:
                commit_result(L1.RESULTS, out)
            n += 1
        except ValueError as exc:
            if str(exc) != 'result_revision_conflict':
                raise
            bad += 1
    # A verdicts file still being written reads like a finished one: 28 rows
    # recorded, nothing rejected, and the line is indistinguishable from a
    # complete batch of 200.  The batch size is known here, so say when the
    # two disagree.  Recording part of a batch is legitimate - the rest stays
    # in the cohort and can be recorded later - it just must not be silent.
    short = len(batch) - n
    print(json.dumps({'recorded': n, 'rejected': bad, 'batch_size': len(batch),
                      **({'未判的': short,
                          'note': '批次里还有 %d 份没有判定。如果判定文件还在写，'
                                  '等它写完再对同一个文件跑一次 record——已录的会以'
                                  '相同内容重录，不影响结果' % short}
                         if short > 0 else {}),
                      'total_scored': len(L1.done_keys())}, ensure_ascii=False))

def cmd_versions(a):
    rows = L1B.scored_rows()
    groups = L1B.version_groups(rows, a.min_score, a.threshold)
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
    # One row per file, not per line.  record appends, so a re-judged file
    # keeps its superseded rows: counting lines reports the old score and the
    # old category alongside the current ones.  773 files were re-judged in the
    # Office pass, which put six extra documents in the 8-and-above bucket that
    # no longer belong there and inflated every category the re-read moved.
    rows = L1B.last_results()
    cat = collections.Counter(r.get('category') for r in rows.values())
    sc = collections.Counter(r['score'] for r in rows.values() if r.get('score') is not None)
    superseded = 0
    if L1.RESULTS.exists():
        with L1.RESULTS.open(encoding='utf-8') as fh:
            superseded = sum(1 for _ in fh) - len(rows)
    scored = L1.done_keys(); items = L1.load_inventory()
    need = sum(1 for i in items if i['sha256'] not in scored and not i['all_excluded']
               and L1.route(i['suffix']) in ('text', '_office_pending', '_archive_review', '_format_review'))
    auto = len(items) - len(scored) - need
    digests = [Path(L1.DATA / 'digests.jsonl')] + [Path(p) for p in sorted(glob.glob(str(L1.DATA / 'digests.part*.jsonl')))]
    def count_lines(path):
        with path.open(encoding='utf-8') as fh:
            return sum(1 for _ in fh)
    total = sum(count_lines(p) for p in digests if p.exists())
    rate = L1B.working_rate(L1B.digest_stamps(digests))
    basis = '运行中实测'
    if rate is None:  # older digests carry no timestamp
        first = min((p.stat().st_birthtime for p in digests if p.exists()), default=time.time())
        rate = total / max((time.time() - first) / 60, 1)
        basis = '挂钟含空闲，偏低'
    print(json.dumps({'唯一文件': len(items), '已打分': len(scored), '剩余': len(items) - len(scored),
                      '需抽取打分': need, '自动归类': auto, '已抽取': total,
                      '抽取速率_每分钟': round(rate, 1), '速率口径': basis,
                      '预计剩余小时': round(need / rate / 60, 1) if rate else None,
                      '被覆盖的旧判定行': superseded,
                      # Three cohorts that are not "unscored" but are not done
                      # either.  Without a number here the only way to learn
                      # how much re-judging is owed is to run a pack.
                      '待重判_只看过文件名': len(L1B.blind_scored()),
                      '待重判_读不到单元格时判的表格': len(L1B.judged_without_cells()),
                      '待重判_出处未知且没读过文本框': len(L1B.judged_without_drawings())},
                     ensure_ascii=False))
    for k, v in cat.most_common(10): print(f'  {v:7d}  {k}')
    if sc: print('分数分布: ' + json.dumps({str(k): sc[k] for k in sorted(sc, reverse=True)}))


def main():
    ap = argparse.ArgumentParser(); s = ap.add_subparsers(dest='cmd', required=True)
    p = s.add_parser('pack'); p.add_argument('--limit', type=int, default=40); p.add_argument('--out')
    p.add_argument('--redo', action='store_true',
                   help='等同 --cohort blind：重排只看文件名判过、现在能打开的文件')
    p.add_argument('--cohort', choices=sorted(L1B.COHORTS),
                   help='new=未判过 / blind=只看文件名判过的 / cells=在读不到单元格时判过的表格')
    p.add_argument('--sha', help='重判指定的这几份（sha 前缀，逗号分隔），不论属于哪个批次')
    p.add_argument('--workers', type=int, default=4,
                   help='preview extractions in parallel (1..%d); local CPU work, no model' % L1B.MAX_WORKERS)
    r = s.add_parser('record'); r.add_argument('--verdicts', required=True); r.add_argument('--batch'); r.add_argument('--digests', action='store_true')
    r.add_argument('--executor', default='terminal', help='client identity, e.g. claude-code or codex')
    r.add_argument('--model', help='actual model reported by the client; omit if unknown')
    s.add_parser('status')
    v = s.add_parser('versions'); v.add_argument('--min-score', type=int, default=0)
    v.add_argument('--show', type=int, default=15, help='groups to print in full')
    v.add_argument('--threshold', type=float, default=L1B.SIM_THRESHOLD,
                   help='filename similarity to call two files one report (0..1)')
    a = ap.parse_args()
    {'pack': cmd_pack, 'record': cmd_record, 'status': cmd_status, 'versions': cmd_versions}[a.cmd](a)


if __name__ == '__main__':
    main()
