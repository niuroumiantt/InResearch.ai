#!/usr/bin/env python3
"""L1 scoring through the shared configured research model.

`calibrate` compares explicit terminal examples; `run` processes pending files.
The default is temporarily Claude CLI. Configure models via INRESEARCH_MODEL_CONFIG.
"""
from __future__ import annotations
from inresearch.materials.records import commit_result, result_revision, current_results
import argparse, json, random, threading, time
from concurrent.futures import ThreadPoolExecutor

from inresearch.adapters import models as models
from inresearch.materials import triage as L1
from inresearch.workflow import terminal_batch as PK

MAX_WORKERS = 16


def call(system: str, user: str, timeout=None) -> dict:
    return models.configured_client().generate(system, user, think=False)


def scored_rows():
    from inresearch.materials.records import current_results
    return [row for row in current_results(L1.RESULTS).values()
            if row.get('status') == 'ok' and L1.is_terminal_result(row)]


def system_prompt() -> str:
    return L1.task_card()


def judge(rec, system):
    text = PK.clean_preview(rec['preview'])[:PK.PREVIEW_CHARS]
    value = call(system, L1.user_message(rec, text, rec['meta'], rec['level']))
    return L1.validate_judgement(value)


def cmd_calibrate(a):
    system = system_prompt(); rows = scored_rows()
    random.Random(11).shuffle(rows); rows = rows[:a.limit]
    inv = {i['sha256']: i for i in L1.load_inventory()}
    agree = diff = 0; big = []; t0 = time.time()
    for r in rows:
        item = inv.get(r['sha256'])
        if not item: continue
        rec = L1.prepare(item)
        try: v = judge(rec, system)
        except Exception as exc:
            print(json.dumps({'rel': r['rel'][-50:], 'error': str(exc)[:80]}, ensure_ascii=False)); continue
        d = abs(v['score'] - r['score'])
        same_mod = v['module'] == r['category']
        if d <= 2 and same_mod: agree += 1
        else:
            diff += 1; big.append((r['rel'][-55:], r['score'], r['category'], v['score'], v['module']))
        print(json.dumps({'mine': [r['score'], r['category']], 'local': [v['score'], v['module']], 'f': r['rel'][-45:]}, ensure_ascii=False))
    n = agree + diff
    print(json.dumps({'compared': n, 'agree(±2分且同模块)': agree, 'disagree': diff,
                      'rate': round(agree / n, 2) if n else 0, 'sec_per_file': round((time.time() - t0) / max(n, 1), 1)}, ensure_ascii=False))


def cmd_run(a):
    """Score pending files, `a.workers` model requests in flight.

    Rows are appended under a lock, so an interrupted run keeps every row it
    already wrote and `pending()` skips them next time.  `--limit` still counts
    only files that reach the model: a file whose preview needs no model is
    written without spending the budget, and once the budget is gone the
    remaining files are left pending rather than written half-judged."""
    if not isinstance(a.workers, int) or not 1 <= a.workers <= MAX_WORKERS:
        raise SystemExit('workers must be 1..%d' % MAX_WORKERS)
    system = system_prompt()
    base = current_results(L1.RESULTS)
    items = PK.pending()
    counts = {'scored': 0, 'errors': 0, 'no_model': 0, 'dispatched': 0, 'conflicts': 0}
    guard = threading.Lock()
    t0 = time.time()

    def emit(row, key):
        with guard:
            try:
                commit_result(L1.RESULTS, row, result_revision(base.get(row['sha256'])))
            except ValueError as exc:
                if str(exc) != 'result_revision_conflict': raise
                counts['conflicts'] += 1
                return
            counts[key] += 1
            judged = counts['scored'] + counts['errors']
            if key != 'no_model' and judged % 25 == 0:
                print(json.dumps({'done': counts['scored'], 'errors': counts['errors'],
                                  'sec_per_file': round((time.time() - t0) / judged, 1)}), flush=True)

    def budget_gone():
        with guard:
            return bool(a.limit) and counts['dispatched'] >= a.limit

    def take_slot():
        """Reserve the budget before the call, not after it returns: several
        threads would otherwise all pass the check while none has finished."""
        with guard:
            if a.limit and counts['dispatched'] >= a.limit:
                return False
            counts['dispatched'] += 1
            return True

    def work(item):
        if budget_gone():
            return
        try:
            rec = L1.prepare(item)
        except (OSError, ValueError) as exc:
            with guard:
                counts['errors'] += 1
                print(json.dumps({'sha256': item['sha256'], 'error': str(exc)[:160]}))
            return
        if not rec['needs_model']:
            o = L1.finalize(rec, None, None, None)
            o['proposed_name'] = L1.proposed_name(o)
            emit(o, 'no_model')
            return
        if not take_slot():  # the preview may have taken a while
            return
        try:
            v = judge(rec, system)
        except Exception as exc:
            o = L1.finalize(rec, None, None, 'local_model:' + str(exc)[:80])
            o['proposed_name'] = L1.proposed_name(o)
            emit(o, 'errors')
            return
        o = L1.finalize(rec, v, {'judge': v.get('_model', {}).get('actual')}, None)
        o['proposed_name'] = L1.proposed_name(o); o['model'] = v.get('_model', {}).get('actual')
        emit(o, 'scored')

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(work, items))

    judged = counts['scored'] + counts['errors']
    print(json.dumps({'scored': counts['scored'], 'errors': counts['errors'],
                      'no_model': counts['no_model'], 'conflicts': counts['conflicts'], 'workers': a.workers,
                      'sec_per_file': round((time.time() - t0) / max(judged, 1), 1)}))


def main():
    ap = argparse.ArgumentParser(); s = ap.add_subparsers(dest='cmd', required=True)
    c = s.add_parser('calibrate'); c.add_argument('--limit', type=int, default=25)
    r = s.add_parser('run'); r.add_argument('--limit', type=int, default=0)
    r.add_argument('--workers', type=int, default=1,
                   help='model requests in flight (1..%d); needs OLLAMA_NUM_PARALLEL >= this on the server' % MAX_WORKERS)
    a = ap.parse_args()
    {'calibrate': cmd_calibrate, 'run': cmd_run}[a.cmd](a)


if __name__ == '__main__':
    main()
