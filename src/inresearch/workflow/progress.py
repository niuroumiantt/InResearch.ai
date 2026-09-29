#!/usr/bin/env python3
"""One progress report for the M4 triage: judged, moved, remaining, how long left.

Read-only.  Every number comes from a file the pipeline already writes, so the
report cannot disagree with the ledger:

  inventory.jsonl   every file, one line per path
  l1_results.jsonl  one line per judged or auto-filed document
  moves.jsonl       one line per rename/move, written before the move happens

  report            print once
  report --every N  print every N seconds until stopped

The rate counts only the minutes work actually ran.  Dividing by wall clock
since the first row counts every hour the machine sat idle and made an earlier
estimate wrong by an order of magnitude.
"""
from __future__ import annotations
import argparse, collections, json, sys, time
from pathlib import Path

from inresearch.materials import triage as L1
from inresearch.workflow import batch_reporting
from inresearch.materials import paths as m4_paths
from inresearch.materials import records as m4_records
from inresearch.storage.moves import replay
from inresearch.storage.jsonl import read_rows

MOVES = m4_paths.state() / 'moves.jsonl'


def moved_counts(path: Path | None = None):
    """Moves actually performed, minus anything a revert put back.

    The path is resolved on each call, not frozen as a default argument: a
    default binds the module constant once, so a caller that points MOVES
    somewhere else silently reads the original file.
    """
    path = MOVES if path is None else path
    rows = list(read_rows(path))
    records = replay(rows).values()
    stages = collections.Counter(row.get('stage') or 'unknown' for row in records)
    reverted = sum(row.get('event') == 'revert' and bool(row.get('ok')) for row in rows)
    return {'moved': sum(stages.values()), 'reverted': reverted, 'by_stage': dict(stages)}


def fmt_duration(hours):
    if hours is None:
        return '未知'
    if hours < 1:
        return '约 %d 分钟' % max(1, round(hours * 60))
    if hours < 48:
        return '约 %.1f 小时' % hours
    return '约 %.1f 天' % (hours / 24)


def collect():
    inventory = m4_records.load_inventory(L1.INVENTORY)
    results = list(m4_records.current_results(L1.RESULTS).values())
    judged = [r for r in results if r.get('status') == 'ok']
    auto = [r for r in results if r.get('status') == 'l0']
    failed = [r for r in results if r.get('status') == 'error']
    settled = {r['sha256'] for r in results if r.get('status') in {'ok', 'l0'}}

    unique = {r['sha256'] for r in inventory if r.get('sha256')}
    remaining = len(unique - settled)

    stamps = []
    for row in judged:
        at = row.get('at')
        if at:
            try:
                stamps.append(time.mktime(time.strptime(at, '%Y-%m-%dT%H:%M:%SZ')))
            except ValueError:
                pass
    rate = batch_reporting.working_rate(stamps)
    hours = (remaining / rate / 60) if rate else None

    scores = collections.Counter(r['score'] for r in judged if r.get('score') is not None)
    modules = collections.Counter(r.get('category') for r in judged)
    return {'inventory_paths': len(inventory), 'unique_files': len(unique),
            'judged': len(judged), 'auto_filed': len(auto), 'failed': len(failed),
            'remaining': remaining,
            'percent_done': round(100 * (len(unique) - remaining) / len(unique), 1) if unique else 0,
            'rate_per_minute': round(rate, 1) if rate else None,
            'eta_hours': round(hours, 1) if hours else None,
            **moved_counts(),
            'scores': dict(sorted(scores.items(), reverse=True)),
            'modules': dict(modules.most_common(8))}


def render(snapshot):
    lines = [
        '=== %s' % time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        '文件总数 %d（清单路径 %d，去重后唯一）'
        % (snapshot['unique_files'], snapshot['inventory_paths']),
        '已处理 %.1f%%：模型判定 %d，按类型自动归类 %d，判定失败 %d'
        % (snapshot['percent_done'], snapshot['judged'], snapshot['auto_filed'], snapshot['failed']),
        '待处理 %d' % snapshot['remaining'],
        '已改名移动 %d（其中回退 %d）' % (snapshot['moved'], snapshot['reverted']),
    ]
    if snapshot['rate_per_minute']:
        lines.append('判定速率 %.1f 份/分钟（只计运行中的时间），预计剩余 %s'
                     % (snapshot['rate_per_minute'], fmt_duration(snapshot['eta_hours'])))
    else:
        lines.append('判定速率：样本不足，下次再算')
    if snapshot['scores']:
        lines.append('分数分布 ' + json.dumps(snapshot['scores'], ensure_ascii=False))
    if snapshot['modules']:
        lines.append('模块前八 ' + json.dumps(snapshot['modules'], ensure_ascii=False))
    return '\n'.join(lines) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--every', type=int, help='seconds between reports; omit to print once')
    ap.add_argument('--json', action='store_true', help='machine-readable instead of text')
    a = ap.parse_args(argv)
    if a.every is not None and a.every < 30:
        ap.error('--every must be at least 30 seconds')
    while True:
        snapshot = collect()
        sys.stdout.write(json.dumps(snapshot, ensure_ascii=False) + '\n' if a.json else render(snapshot))
        sys.stdout.flush()
        if a.every is None:
            return 0
        time.sleep(a.every)


if __name__ == '__main__':
    sys.exit(main())
