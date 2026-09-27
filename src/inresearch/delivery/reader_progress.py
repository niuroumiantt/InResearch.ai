#!/usr/bin/env python3
"""One HTML progress page for the Spark reader, its priority documents and M4 OCR.

Read-only and safe while the reader runs: the catalog is opened with
``mode=ro`` and is never initialized, migrated or claimed; M4 activity is
read from the offload claims and uploaded page results; heat comes from the
reader's own journal lines. The page refreshes itself, so a loop that rewrites
the file (docs/local_setup/progress.sh) is all a viewer needs.

  manage.py reader-progress                 HTML to stdout
  manage.py reader-progress --html FILE     write FILE atomically
"""
from __future__ import annotations
import argparse
import html
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REFRESH_SECONDS = 60
PRIORITY_FLOOR = 7
TERMINAL = ('succeeded', 'failed', 'blocked')


def _journal(since_seconds):
    try:
        out = subprocess.run(['journalctl', '--user', '-u', 'inresearch-reader', '-o', 'cat',
                              '--since', '-%ds' % since_seconds], capture_output=True, text=True,
                             timeout=20, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return out.splitlines()


def _service():
    try:
        return subprocess.run(['systemctl', '--user', 'is-active', 'inresearch-reader'], capture_output=True,
                              text=True, timeout=10, check=False).stdout.strip() or 'unknown'
    except (OSError, subprocess.SubprocessError):
        return 'unknown'


def _celsius():
    from inresearch.adapters.thermal import read_celsius
    return read_celsius()


def heat(lines, window):
    """Pause share of the last window from the reader's own thermal lines."""
    if lines is None:
        return None
    pauses, seconds, peak = 0, 0.0, None
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('thermal') == 'pause':
            pauses += 1
            seconds += float(event.get('seconds') or 0)
            c = event.get('celsius')
            if isinstance(c, (int, float)):
                peak = c if peak is None else max(peak, c)
    return {'pauses': pauses, 'paused_seconds': seconds, 'share': min(1.0, seconds / window), 'peak_c': peak}


def _count_pages(directory):
    pages = directory / 'pages'
    if directory.is_symlink() or not pages.is_dir():
        return 0
    return sum(1 for _ in pages.glob('*.json'))


def collect(data, now=None, journal=_journal, service=_service, celsius=_celsius, floor=PRIORITY_FLOOR):
    now = time.time() if now is None else now
    data = Path(data)
    path = data / 'catalog' / 'catalog.sqlite'
    if not path.is_file():
        raise FileNotFoundError('catalog_missing: %s' % path)
    conn = sqlite3.connect('file:%s?mode=ro' % path, uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        q = lambda sql, *a: [dict(r) for r in conn.execute(sql, a)]
        stages = q("SELECT stage,state,count(*) n FROM jobs GROUP BY 1,2 ORDER BY 1,2")
        documents = {r['state']: r['n'] for r in q("SELECT state,count(*) n FROM reading_runs GROUP BY 1")}
        done = {}
        for label, span in (('1h', 3600), ('24h', 86400)):
            done[label] = q("SELECT stage,state,count(*) n FROM jobs WHERE finished>=? AND state IN (%s) "
                            "GROUP BY 1,2 ORDER BY 1,2" % ','.join('?' * len(TERMINAL)), now - span, *TERMINAL)
        errors = q("SELECT stage,error_code,count(*) n FROM jobs WHERE finished>=? AND state IN ('failed','blocked') "
                   "AND error_code IS NOT NULL GROUP BY 1,2 ORDER BY 3 DESC LIMIT 12", now - 86400)
        runs = q("SELECT d.doc_id,d.original_name,r.revision_id,r.state,r.phase,r.priority,r.error_code,"
                 "r.pages_total,r.chunks_total,r.chunks_read,r.updated FROM reading_runs r JOIN documents d USING(doc_id) "
                 "WHERE r.priority>=? AND r.revision_id=COALESCE(d.current_revision_id,r.revision_id) "
                 "ORDER BY r.priority DESC,r.updated DESC", floor)
        seen, priority = set(), []
        for run in runs:
            if run['doc_id'] in seen:
                continue
            seen.add(run['doc_id'])
            jobs = q("SELECT stage,state,count(*) n,max(error_code) error FROM jobs WHERE revision_id=? GROUP BY 1,2",
                     run['revision_id'])
            run['jobs'] = jobs
            priority.append(run)
        claims = []
        claim_root = data / 'offload' / 'm4' / 'claims'
        if claim_root.is_dir() and not claim_root.is_symlink():
            for entry in sorted(claim_root.iterdir()):
                row = conn.execute("SELECT d.original_name FROM reading_runs r JOIN documents d USING(doc_id) "
                                   "WHERE r.revision_id=?", (entry.name,)).fetchone()
                claims.append({'revision_id': entry.name, 'name': row[0] if row else None,
                               'since': entry.stat().st_mtime})
    finally:
        conn.close()
    results = data / 'offload' / 'm4' / 'results'
    for run in priority:
        run['m4_pages'] = _count_pages(results / run['doc_id']) if results.is_dir() else 0
    return {'generated': now, 'service': service(), 'release': os.environ.get('READER_RELEASE', 'unknown'),
            'celsius': celsius(), 'heat': heat(journal(3600), 3600), 'documents': documents, 'stages': stages,
            'done': done, 'errors': errors, 'priority': priority, 'claims': claims, 'floor': floor}


STATE_LABEL = {'complete': '完成', 'queued': '排队', 'running': '进行中', 'blocked': '阻塞', 'failed': '失败',
               'ready': '待采用', 'succeeded': '成功', 'pending': '待办'}


def _t(ts):
    return datetime.fromtimestamp(ts, timezone.utc).astimezone().strftime('%m-%d %H:%M') if ts else '—'


def _e(value):
    return html.escape('' if value is None else str(value))


def _jobs_line(jobs):
    parts = []
    for stage in ('extract', 'triage', 'read', 'synthesize', 'organize', 'receipt'):
        rows = [j for j in jobs if j['stage'] == stage]
        if not rows:
            continue
        total = sum(j['n'] for j in rows)
        ok = sum(j['n'] for j in rows if j['state'] == 'succeeded')
        bad = [j for j in rows if j['state'] in ('failed', 'blocked')]
        text = '%s %d/%d' % (stage, ok, total)
        if bad:
            text += ' <b class="bad">%s</b>' % _e(', '.join('%s×%d' % (j['error'] or j['state'], j['n']) for j in bad))
        parts.append(text)
    return ' · '.join(parts)


def _tone(state):
    return {'complete': 'ok', 'running': 'run', 'blocked': 'bad', 'failed': 'bad'}.get(state, 'wait')


def render(s):
    heat = s['heat']
    if heat is None:
        heat_text = '读不到 reader 日志'
    else:
        heat_text = '过去 1 小时暂停 %d 次，共 %d 分钟（%d%% 时间在降温）%s' % (
            heat['pauses'], heat['paused_seconds'] // 60, round(heat['share'] * 100),
            '，最高 %.1f ℃' % heat['peak_c'] if heat['peak_c'] is not None else '')
    celsius = '%.1f ℃' % s['celsius'] if s['celsius'] is not None else '读不到'
    hot = heat is not None and heat['share'] >= 0.25
    docs = s['documents']
    done1 = {(r['stage'], r['state']): r['n'] for r in s['done']['1h']}
    done24 = {(r['stage'], r['state']): r['n'] for r in s['done']['24h']}
    tiles = [
        ('reader 服务', s['service'], 'ok' if s['service'] == 'active' else 'bad'),
        ('GPU/机温', celsius, 'bad' if hot else 'ok'),
        ('完成文档', str(docs.get('complete', 0)), 'ok'),
        ('排队 / 进行中', '%d / %d' % (docs.get('queued', 0), docs.get('running', 0)), 'wait'),
        ('近 1 小时读完块', str(done1.get(('read', 'succeeded'), 0)), 'ok'),
        ('近 24 小时读失败块', str(done24.get(('read', 'failed'), 0)), 'bad' if done24.get(('read', 'failed')) else 'ok'),
    ]
    rows = []
    for r in s['priority']:
        name = r['original_name']
        rows.append('<tr><td class="num">%s</td><td><div class="name" title="%s">%s</div><div class="sub">%s</div></td>'
                    '<td><span class="pill %s">%s</span>%s</td><td class="sub">%s</td><td class="num">%s</td><td class="num">%s</td></tr>' % (
                        r['priority'], _e(name), _e(name), _jobs_line(r['jobs']), _tone(r['state']),
                        _e(STATE_LABEL.get(r['state'], r['state'])),
                        ' <span class="sub">%s</span>' % _e(r['error_code']) if r['error_code'] else '',
                        _e(r['phase']), '%s/%s' % (r['chunks_read'], r['chunks_total'] or '?'),
                        ('%d/%s' % (r['m4_pages'], r['pages_total'] or '?')) if r['m4_pages'] else '—'))
    stage_rows = ''.join('<tr><td>%s</td><td>%s</td><td class="num">%d</td></tr>' % (
        _e(r['stage']), _e(STATE_LABEL.get(r['state'], r['state'])), r['n']) for r in s['stages'])
    error_rows = ''.join('<tr><td>%s</td><td>%s</td><td class="num">%d</td></tr>' % (
        _e(r['stage']), _e(r['error_code']), r['n']) for r in s['errors']) or '<tr><td colspan="3" class="sub">无</td></tr>'
    claim_rows = ''.join('<li>%s <span class="sub">自 %s</span></li>' % (_e(c['name'] or c['revision_id']), _t(c['since']))
                         for c in s['claims']) or '<li class="sub">M4 当前没有认领 OCR 文档</li>'
    tile_html = ''.join('<div class="tile %s"><div class="label">%s</div><div class="value">%s</div></div>' % (
        tone, _e(label), _e(value)) for label, value, tone in tiles)
    return PAGE % {
        'refresh': REFRESH_SECONDS, 'generated': _t(s['generated']), 'release': _e(s['release'][:12]),
        'tiles': tile_html, 'heat': _e(heat_text), 'heat_tone': 'bad' if hot else 'ok', 'floor': s['floor'],
        'count': len(s['priority']), 'rows': ''.join(rows) or '<tr><td colspan="6" class="sub">无</td></tr>',
        'claims': claim_rows, 'stages': stage_rows, 'errors': error_rows}


PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="%(refresh)d">
<title>Spark 阅读进度</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--sub:#6b6b66;--line:#e4e4df;--ok:#1f7a4d;--bad:#b3261e;--run:#1b5fb4;--wait:#7a6a1f}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1d;--ink:#ecece8;--sub:#a3a39c;--line:#33332f;--ok:#5cc28f;--bad:#f2867e;--run:#7fb2f0;--wait:#d9c56b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 16px 48px}h1{font-size:20px;margin:0}h2{font-size:15px;margin:28px 0 10px}
.meta,.sub{color:var(--sub);font-size:12px}.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-top:16px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;border-left:4px solid var(--wait)}
.tile.ok{border-left-color:var(--ok)}.tile.bad{border-left-color:var(--bad)}.label{color:var(--sub);font-size:12px}.value{font-size:20px;font-weight:600}
.banner{margin-top:12px;padding:8px 12px;border-radius:8px;background:var(--card);border:1px solid var(--line)}.banner.bad{border-color:var(--bad);color:var(--bad)}
.scroll{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%%;min-width:640px}th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;color:var(--sub);font-weight:500}td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.name{max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pill{display:inline-block;padding:0 8px;border-radius:999px;font-size:12px;border:1px solid}
.pill.ok{color:var(--ok)}.pill.bad{color:var(--bad)}.pill.run{color:var(--run)}.pill.wait{color:var(--wait)}b.bad{color:var(--bad);font-weight:500}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}ul{margin:0;padding:10px 12px 10px 28px;background:var(--card);border:1px solid var(--line);border-radius:10px}
</style></head><body><main>
<h1>Spark 阅读进度</h1>
<div class="meta">生成于 %(generated)s · 版本 %(release)s · 每 %(refresh)d 秒自动刷新（需本机循环脚本在跑）</div>
<div class="tiles">%(tiles)s</div>
<div class="banner %(heat_tone)s">降温：%(heat)s</div>
<h2>重点文档（优先级 ≥ %(floor)d，共 %(count)d 份）</h2>
<div class="scroll"><table><thead><tr><th>分</th><th>文档 / 各环节 成功/总数</th><th>状态</th><th>环节</th><th>已读块</th><th>M4 OCR 页</th></tr></thead>
<tbody>%(rows)s</tbody></table></div>
<h2>M4 正在 OCR</h2><ul>%(claims)s</ul>
<div class="cols">
<div><h2>近 24 小时失败/阻塞原因</h2><div class="scroll"><table style="min-width:0"><thead><tr><th>环节</th><th>原因</th><th>数量</th></tr></thead><tbody>%(errors)s</tbody></table></div></div>
<div><h2>全队列任务</h2><div class="scroll"><table style="min-width:0"><thead><tr><th>环节</th><th>状态</th><th>数量</th></tr></thead><tbody>%(stages)s</tbody></table></div></div>
</div>
</main></body></html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data-root', default=os.environ.get('READER_DATA_ROOT') or str(Path.home() / '.local/share/inresearch.ai'))
    ap.add_argument('--html', help='write the page to this file (atomic); default stdout')
    ap.add_argument('--min-priority', type=int, default=PRIORITY_FLOOR)
    args = ap.parse_args(argv)
    try:
        page = render(collect(Path(args.data_root).expanduser(), floor=args.min_priority))
    except (OSError, sqlite3.Error) as exc:
        print('reader-progress: %s' % exc, file=sys.stderr)
        return 1
    if not args.html:
        sys.stdout.write(page)
        return 0
    target = Path(args.html).expanduser()
    partial = target.with_name('.' + target.name + '.partial')
    partial.write_text(page, encoding='utf-8')
    os.replace(partial, target)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
