#!/usr/bin/env python3
"""M4 triage, physical stage: rename and move originals per the mapping table.

Two independent stages, each with plan / apply / revert:

  duplicates   Pure SHA-256 work, needs no model.  Keeps exactly one copy of
               every content-identical file and moves the rest to
               _to_delete/duplicates/.  Safe to run before L1.
  library      Needs L1 results.  Moves the surviving copy into its category
               directory under the scored filename.

Every move is written to moves.jsonl BEFORE it happens, so revert can replay it
backwards.  Nothing is ever deleted or overwritten: a move whose destination
already exists is skipped and reported.
"""
from __future__ import annotations
import argparse, json, os, shutil, sys, time
from collections import defaultdict
from pathlib import Path

SOURCE = Path('/Users/m4/Downloads/所有raw materials')
LIBRARY = Path('/Users/m4/Downloads/inresearch资料库')
DATA = Path.home() / '.local/share/inresearch.ai/m4-triage'
STATE = Path.home() / '.local/state/inresearch.ai/m4-triage'
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
    for line in INVENTORY.open(encoding='utf-8'):
        try: r = json.loads(line)
        except ValueError: continue
        if 'sha256' in r: by_sha[r['sha256']].append(r)
    return by_sha


def load_results():
    out = {}
    if RESULTS.exists():
        for line in RESULTS.open(encoding='utf-8'):
            try: r = json.loads(line); out[r['sha256']] = r
            except (ValueError, KeyError): pass
    return out


def applied_sources():
    """Destinations already reached, so apply is idempotent and resumable."""
    done = set()
    if MOVES.exists():
        for line in MOVES.open(encoding='utf-8'):
            try: r = json.loads(line)
            except ValueError: continue
            if r.get('event') == 'move' and r.get('ok'):
                done.add(r['from'])
    return done


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


def plan_library():
    results = load_results()
    if not results:
        sys.exit('no L1 results yet: run m4_triage_l1.py first')
    by_sha = load_inventory(); moves = []
    for sha, res in results.items():
        rows = by_sha.get(sha)
        if not rows: continue
        keep = sorted(rows, key=lambda r: keep_rank(r['rel']))[0]
        cat = res.get('category') or '_review'
        name = res.get('proposed_name')
        if not name: continue
        moves.append({'sha256': sha, 'from': keep['rel'], 'to': str(Path(cat) / name), 'size': keep['size'], 'stage': 'library',
                      'score': res.get('score'), 'level': res.get('level')})
    return moves


def do_apply(moves, dry):
    STATE.mkdir(parents=True, exist_ok=True)
    done = applied_sources()
    n = skipped = missing = collided = 0
    log = None if dry else MOVES.open('a', encoding='utf-8')
    for mv in moves:
        src = SOURCE / mv['from']
        if mv['from'] in done: skipped += 1; continue
        if not src.is_file(): missing += 1; continue
        dst = LIBRARY / mv['to']
        if dst.exists(): collided += 1; continue
        if dry: n += 1; continue
        rec = {'event': 'move', 'at': now(), **mv, 'ok': False}
        log.write(json.dumps(rec, ensure_ascii=False) + '\n'); log.flush()
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.rename(src, dst)            # same volume: atomic, no copy
            rec['ok'] = True
        except OSError as exc:
            rec['error'] = str(exc)[:200]
        log.write(json.dumps(rec, ensure_ascii=False) + '\n'); log.flush()
        if rec['ok']: n += 1
    if log: log.close()
    print(json.dumps({'moved' if not dry else 'would_move': n, 'already_done': skipped,
                      'source_missing': missing, 'destination_exists': collided}, ensure_ascii=False))


def do_revert(stage):
    if not MOVES.exists(): sys.exit('no move log')
    rows = [json.loads(l) for l in MOVES.open(encoding='utf-8')]
    back = [r for r in rows if r.get('event') == 'move' and r.get('ok') and (not stage or r.get('stage') == stage)]
    n = 0
    with MOVES.open('a', encoding='utf-8') as log:
        for r in reversed(back):
            src = LIBRARY / r['to']; dst = SOURCE / r['from']
            if not src.is_file() or dst.exists(): continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.rename(src, dst); n += 1
            log.write(json.dumps({'event': 'revert', 'at': now(), 'from': r['to'], 'to': r['from'], 'sha256': r['sha256'], 'ok': True}, ensure_ascii=False) + '\n')
    print(json.dumps({'reverted': n}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['duplicates', 'library'])
    ap.add_argument('action', choices=['plan', 'apply', 'revert'])
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--show', type=int, default=15)
    a = ap.parse_args()
    if a.action == 'revert':
        return do_revert(a.stage)
    moves = plan_duplicates() if a.stage == 'duplicates' else plan_library()
    if a.limit: moves = moves[:a.limit]
    if a.action == 'plan':
        gb = sum(m['size'] for m in moves) / 1e9
        print(json.dumps({'stage': a.stage, 'moves': len(moves), 'gb': round(gb, 1)}, ensure_ascii=False))
        for m in moves[:a.show]:
            print('  ' + m['from'][-80:] + '\n    -> ' + m['to'][:100] + ('\n    保留: ' + m['keep'][-80:] if 'keep' in m else ''))
        return
    do_apply(moves, dry=False)


if __name__ == '__main__':
    main()
