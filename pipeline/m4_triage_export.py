#!/usr/bin/env python3
"""Hand the triage over to another machine without redoing any of it.

The corpus lives on Spark; M4 only did the work because Spark was offline.
Everything M4 decided - 51,457 duplicate moves, 35,895 filings, three rounds
of renaming and 16,020 judgements that cost 31.7 hours of model time - exists
only in M4's ledgers.  Without an export, reconciling the two machines means
deleting Spark's tree and running the whole thing again.

So this writes one line per physical file: where it started, where it ended,
and what was decided about it.  Applying that on Spark reproduces the same
library from Spark's own copy of the raw material.

  export                write mapping.jsonl from this machine's ledgers
  verify  --mapping F   compare a mapping against the local tree, change nothing
  apply   --mapping F   move local files to match, plan first unless --commit

Files are matched by SHA-256, not by path: the two trees are copies of one
corpus but nothing guarantees the paths agree, and content is the only join
key that survives a folder someone renamed by hand.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import m4_paths
import m4_triage_apply as APPLY
import m4_triage_l1 as L1

MAPPING_VERSION = '1.0'


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------

VERDICT_FIELDS = ('score', 'module', 'doc_type', 'year', 'org', 'title',
                  'keep_original_name', 'confidence', 'language', 'rationale')


def build_rows() -> tuple[list[dict], dict]:
    placed = APPLY.final_records()
    results = APPLY.load_results()

    out, stats = [], Counter()
    for origin in sorted(placed):
        moved = placed[origin]
        stage = moved.get('stage') or 'library'
        record = {'sha256': moved.get('sha256'), 'from': origin, 'to': moved['to'],
                  'size': moved.get('size', 0), 'stage': stage}
        # The judgement rides with the copy that was filed, not with the
        # duplicates that were set aside, so each file is scored once.
        res = results.get(moved.get('sha256')) if stage != 'duplicates' else None
        if res:
            record['status'] = res.get('status')
            record['level'] = res.get('level')
            record['category'] = res.get('category')
            for field in VERDICT_FIELDS:
                if res.get(field) is not None:
                    record[field] = res[field]
        out.append(record)
        stats[stage] += 1
        if record['sha256'] is None:
            stats['no_hash_in_ledger'] += 1

    inventoried = {row['rel'] for rows in APPLY.load_inventory().values() for row in rows}
    stats['never_moved'] = len(inventoried - set(placed))
    return out, stats


def cmd_export(a):
    rows, stats = build_rows()
    path = Path(a.out)
    header = {'mapping_version': MAPPING_VERSION, 'generated': now(),
              'source_root': str(APPLY.SOURCE), 'library_root': str(APPLY.LIBRARY),
              'dataset': m4_paths.dataset(), 'files': len(rows)}
    with path.open('w', encoding='utf-8') as fh:
        fh.write(json.dumps({'header': header}, ensure_ascii=False) + '\n')
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps({'wrote': str(path), **header, **stats}, ensure_ascii=False))


# --------------------------------------------------------------------------
# read a mapping back
# --------------------------------------------------------------------------

def load_mapping(path: Path) -> tuple[dict, list[dict]]:
    header, rows = {}, []
    with path.open(encoding='utf-8') as fh:
        for line in fh:
            try: record = json.loads(line)
            except ValueError: continue
            if 'header' in record and not rows:
                header = record['header']; continue
            if 'sha256' in record:
                rows.append(record)
    return header, rows


def local_index() -> dict:
    """sha256 -> every path holding that content on this machine."""
    index = defaultdict(list)
    for sha, rows in APPLY.load_inventory().items():
        for row in rows:
            index[sha].append(row['rel'])
    return index


def match(rows: list[dict], index: dict) -> tuple[list, list, list]:
    """Pair mapping rows with local files, by content then by path."""
    available = {sha: sorted(paths) for sha, paths in index.items()}
    taken = set()
    matched, missing = [], []
    for row in rows:
        options = available.get(row['sha256'], [])
        free = [p for p in options if p not in taken]
        if not free:
            missing.append(row); continue
        # Prefer the identical path, so a tree that does agree stays aligned.
        pick = row['from'] if row['from'] in free else free[0]
        taken.add(pick)
        matched.append({**row, 'local': pick})
    extra = sorted({p for paths in index.values() for p in paths} - taken)
    return matched, missing, extra


def report(header, rows, matched, missing, extra) -> dict:
    return {'mapping_files': len(rows), 'matched': len(matched),
            'missing_here': len(missing), 'extra_here': len(extra),
            'exported_from': header.get('source_root'),
            'applying_to': str(APPLY.SOURCE)}


def cmd_verify(a):
    header, rows = load_mapping(Path(a.mapping))
    matched, missing, extra = match(rows, local_index())
    summary = report(header, rows, matched, missing, extra)
    print(json.dumps(summary, ensure_ascii=False))
    for row in missing[:a.show]:
        print('  缺: ' + row['from'][-90:])
    for path in extra[:a.show]:
        print('  多: ' + path[-90:])


# --------------------------------------------------------------------------
# apply on the other machine
# --------------------------------------------------------------------------

def cmd_apply(a):
    header, rows = load_mapping(Path(a.mapping))
    matched, missing, extra = match(rows, local_index())
    summary = report(header, rows, matched, missing, extra)
    moves = [{'sha256': m['sha256'], 'from': m['local'], 'to': m['to'],
              'size': m.get('size', 0), 'stage': 'import',
              'score': m.get('score'), 'level': m.get('level')}
             for m in matched if m['local'] != m['to']]
    if a.limit:
        moves = moves[:a.limit]
    print(json.dumps(summary, ensure_ascii=False))
    if not a.commit:
        _, by_category = APPLY.do_apply(moves, dry=True)
        for name, count in by_category.most_common():
            print('  %-30s %d' % (name, count))
        return
    APPLY.do_apply(moves, dry=False)


def cmd_import_verdicts(a):
    """Write the exported judgements into this machine's l1_results.jsonl.

    Re-judging 16,020 files would cost another 31.7 hours and would not agree
    with the names already on disk, so the verdicts travel with the mapping.
    """
    _, rows = load_mapping(Path(a.mapping))
    have = L1.done_keys()
    written = skipped = 0
    L1.RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with L1.RESULTS.open('a', encoding='utf-8') as fh:
        for row in rows:
            if row.get('status') is None or row['sha256'] in have:
                skipped += 1; continue
            record = {'sha256': row['sha256'], 'rel': row['from'],
                      'suffix': Path(row['from']).suffix, 'size': row.get('size', 0),
                      'imported_from': 'mapping', 'at': now()}
            for key in ('status', 'level', 'category', *VERDICT_FIELDS):
                if row.get(key) is not None:
                    record[key] = row[key]
            fh.write(json.dumps(record, ensure_ascii=False) + '\n')
            have.add(row['sha256']); written += 1
    print(json.dumps({'imported': written, 'already_present': skipped}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('export'); e.add_argument('--out', default='mapping.jsonl')
    v = sub.add_parser('verify'); v.add_argument('--mapping', required=True)
    v.add_argument('--show', type=int, default=10)
    p = sub.add_parser('apply'); p.add_argument('--mapping', required=True)
    p.add_argument('--commit', action='store_true', help='actually move; otherwise plan only')
    p.add_argument('--limit', type=int, default=0)
    i = sub.add_parser('import-verdicts'); i.add_argument('--mapping', required=True)
    a = ap.parse_args()
    {'export': cmd_export, 'verify': cmd_verify, 'apply': cmd_apply,
     'import-verdicts': cmd_import_verdicts}[a.cmd](a)


if __name__ == '__main__':
    main()
