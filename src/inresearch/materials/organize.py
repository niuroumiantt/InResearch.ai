#!/usr/bin/env python3
"""M4 triage, physical stage: rename and move originals per the mapping table.

Two independent stages, each with plan / apply / revert:

  duplicates   Pure SHA-256 work, needs no model.  Keeps exactly one copy of
               every content-identical file and moves the rest to
               _to_delete/duplicates/.  Safe to run before L1.
  library      Needs L1 results.  Moves the surviving copy into its category
               directory under the scored filename.

Every move checks SHA-256 and durably journals its intent before reserving the
destination. Interrupted moves recover under the same exclusive writer lock.  Nothing is ever deleted or overwritten: a move whose destination
already exists is skipped and reported.
"""
from __future__ import annotations
import argparse, json, sys, time
from contextlib import nullcontext
from collections import Counter, defaultdict
from pathlib import Path

from inresearch.materials import paths as m4_paths
from inresearch.storage.moves import MoveJournal, digest, endpoints, replay
from inresearch.storage.jsonl import read_rows
from inresearch.materials import triage as m4_triage_l1
from inresearch.materials import records as m4_records

SOURCE = m4_paths.source()
LIBRARY = m4_paths.library()
DATA = m4_paths.data()
STATE = m4_paths.state()
INVENTORY = DATA / 'inventory.jsonl'
RESULTS = DATA / 'l1_results.jsonl'
MOVES = STATE / 'moves.jsonl'

DUP_DIR = '_to_delete/duplicates'
EMPTY_DIR = '_to_delete/empty'


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def keep_rank(rel: str):
    """Lower sorts first = the copy we keep.

    Prefer a path outside the user's own 要删 tree, then outside the previous
    pipeline's derived output, then the shallowest path, then alphabetical.
    Deterministic, so plan and apply always agree.
    """
    parts = rel.split('/')
    return (parts[0] == '要删', rel.startswith('要删/reader/'), len(parts), rel)


def load_inventory():
    by_sha = defaultdict(list)
    for row in m4_records.load_inventory(INVENTORY):
        if not row.get('error'):
            by_sha[row['sha256']].append({**row, 'rel': row['original_rel'], 'size': row['size_bytes']})
    return by_sha


def load_results():
    return m4_records.current_results(RESULTS)


def category_of(mv):
    """Top-level destination directory: the module code, or a _bucket."""
    return mv['to'].split('/')[0]


def plan_duplicates():
    """Content-identical copies beyond the first.

    Zero-byte files all share one SHA-256, but an empty .dwg and an empty .txt
    are not copies of each other - they are separate broken/placeholder files.
    They get their own bucket and keep their names.
    """
    by_sha = load_inventory(); moves = []
    for sha, rows in by_sha.items():
        if rows[0]['size'] == 0:
            for r in rows:
                moves.append({'sha256': sha, 'from': r['rel'], 'to': str(Path(EMPTY_DIR) / r['rel']), 'size': 0, 'stage': 'duplicates', 'empty': True})
            continue
        if len(rows) < 2: continue
        rows = sorted(rows, key=lambda r: keep_rank(r['rel']))
        keep = rows[0]
        for n, r in enumerate(rows[1:], 1):
            # Several copies can share a basename, so number them: without this
            # the second and third copy would target the same destination and
            # silently stay behind.
            stem = Path(r['rel']); dest = Path(DUP_DIR) / sha[:2] / ('%s__%02d__%s' % (sha[:16], n, stem.name))
            moves.append({'sha256': sha, 'from': r['rel'], 'to': str(dest), 'keep': keep['rel'], 'size': r['size'], 'stage': 'duplicates'})
    return moves


def desired_destination(res: dict) -> str | None:
    """Where the current rules say this file belongs.

    Recomputed from m4_triage_l1 rather than read from the stored
    proposed_name, so a naming rule that changes takes effect everywhere at
    once instead of leaving the library half on the old scheme.
    """
    cat = res.get('category') or '_review'
    try:
        name = m4_triage_l1.proposed_name(res)
    except Exception:
        name = res.get('proposed_name')
    return str(Path(cat) / name) if name else None


def ledger_rows():
    return read_rows(MOVES)


def final_records() -> dict:
    """Original source paths and current placements from the shared journal replay."""
    return {record['origin']: {key: value for key, value in record.items() if key != 'chain'}
            for record in replay(ledger_rows()).values()}


def final_locations() -> dict:
    """Source path -> where that file is now."""
    return {origin: record['to'] for origin, record in final_records().items()}


def plan_library():
    results = load_results()
    if not results:
        sys.exit('no L1 results yet: run `manage.py triage run` first')
    by_sha = load_inventory(); moves = []
    for sha, res in results.items():
        rows = by_sha.get(sha)
        if not rows: continue
        keep = sorted(rows, key=lambda r: keep_rank(r['rel']))[0]
        dest = desired_destination(res)
        if not dest: continue
        moves.append({'sha256': sha, 'from': keep['rel'], 'to': dest, 'size': keep['size'], 'stage': 'library',
                      'score': res.get('score'), 'level': res.get('level')})
    return moves


def plan_restage():
    """Re-file what is already in the library, when the rules have moved on.

    Needed because the first library pass flattened unread files to their
    basename: two projects' 一层平面图.dwg landed side by side in one bucket
    with nothing but a hash to tell them apart.  Restage puts each back under
    the folders it came from.  Files never filed are left to `library apply`.
    """
    results = load_results()
    if not results:
        sys.exit('no L1 results yet: run `manage.py triage run` first')
    placed = final_locations(); by_sha = load_inventory(); moves = []
    for sha, res in results.items():
        rows = by_sha.get(sha)
        if not rows: continue
        # The same copy plan_library filed, so restage follows that one file.
        keep = sorted(rows, key=lambda r: keep_rank(r['rel']))[0]
        now_at = placed.get(keep['rel'])
        if not now_at: continue
        dest = desired_destination(res)
        if not dest or dest == now_at: continue
        moves.append({'sha256': sha, 'from': now_at, 'to': dest, 'from_root': 'library',
                      'size': keep['size'], 'stage': 'restage',
                      'score': res.get('score'), 'level': res.get('level')})
    return moves


def journal():
    return MoveJournal(MOVES, {'source': SOURCE, 'library': LIBRARY})


def do_apply(moves, dry):
    """Plan and apply check the same paths and hashes; only apply writes/recoveries."""
    book = journal()
    counts = {'would_move' if dry else 'moved': 0, 'already_done': 0,
              'source_missing': 0, 'destination_exists': 0}
    by_category = Counter()
    errors = []
    with nullcontext() if dry else book.locked():
        placed = replay(book.rows())
        done = {(endpoints(step)[0], record['sha256']): record
                for record in placed.values() for step in record['chain']}
        for mv in moves:
            row = {'event': 'move', 'at': now(), **mv}
            try:
                src, dst = book.paths(row)
                key = (endpoints(row)[0], row['sha256'])
                if not src.exists() and key in done:
                    current = done[key]
                    _, located = book.paths({**row, 'to_root': current['to_root'], 'to': current['to']})
                    if located.is_file() and digest(located) == row['sha256']:
                        counts['already_done'] += 1
                        continue
                if not src.is_file():
                    counts['source_missing'] += 1
                    continue
                if dst.exists():
                    counts['destination_exists'] += 1
                    continue
                if dry:
                    if digest(src) != row['sha256']:
                        raise ValueError('move_source_hash_mismatch')
                    m4_paths.require_same_volume(src, dst.parent)
                else:
                    book.move(row)
                counts['would_move' if dry else 'moved'] += 1
                by_category[category_of(mv)] += 1
            except FileExistsError:
                counts['destination_exists'] += 1
            except ValueError as exc:
                if str(exc) not in {'move_source_hash_mismatch', 'move_path_outside_root',
                                    'move_symlink_not_allowed', 'move_regular_file_required'}:
                    raise  # A journal or mid-move failure requires recovery before proceeding.
                errors.append({'from': row['from'], 'error': str(exc)})
    if errors:
        counts['rejected'] = len(errors)
        counts['errors'] = errors[:20]
    print(json.dumps(counts, ensure_ascii=False))
    return counts, by_category


def do_revert(stage):
    if not MOVES.exists():
        sys.exit('no move log')
    counts = {'reverted': 0}
    book = journal()
    with book.locked():
        for record in replay(book.rows()).values():
            chain = record['chain']
            if stage and chain[-1].get('stage') != stage:
                if any(step.get('stage') == stage for step in chain):
                    counts['blocked_by_later_stage'] = counts.get('blocked_by_later_stage', 0) + 1
                continue
            for row in reversed(chain):
                if stage and row.get('stage') != stage:
                    break
                source, target = endpoints(row)
                reverse = {**row, 'event': 'revert', 'at': now(),
                           'from_root': target[0], 'from': target[1],
                           'to_root': source[0], 'to': source[1]}
                src, dst = book.paths(reverse)
                if not src.is_file():
                    counts['source_missing'] = counts.get('source_missing', 0) + 1
                    break
                if dst.exists():
                    counts['destination_exists'] = counts.get('destination_exists', 0) + 1
                    break
                book.move(reverse)
                counts['reverted'] += 1
    print(json.dumps(counts))
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['duplicates', 'library', 'restage'])
    ap.add_argument('action', choices=['plan', 'apply', 'revert'])
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--show', type=int, default=15)
    a = ap.parse_args()
    if a.action == 'revert':
        return do_revert(a.stage)
    moves = {'duplicates': plan_duplicates, 'library': plan_library,
             'restage': plan_restage}[a.stage]()
    if a.limit: moves = moves[:a.limit]
    if a.action == 'plan':
        gb = sum(m['size'] for m in moves) / 1e9
        print(json.dumps({'stage': a.stage, 'moves': len(moves), 'gb': round(gb, 1)}, ensure_ascii=False))
        # The same code path apply takes, so the plan cannot disagree with it.
        _, by_category = do_apply(moves, dry=True)
        for name, count in by_category.most_common():
            print('  %-30s %d' % (name, count))
        for m in moves[:a.show]:
            print('  ' + m['from'][-80:] + '\n    -> ' + m['to'][:100] + ('\n    保留: ' + m['keep'][-80:] if 'keep' in m else ''))
        return
    do_apply(moves, dry=False)


if __name__ == '__main__':
    main()
