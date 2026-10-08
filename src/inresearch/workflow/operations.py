"""Read-only management projections and durable web-task execution records.

Observability describes execution; it never adopts research, retries work or
changes a catalog. All durations use timezone-aware UTC at the API boundary.
"""
from __future__ import annotations

import copy
import json
import os
import re
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from inresearch.storage.files import atomic_write, write_json
from inresearch.storage.layout import workspace_path

STAGES = {'extract': '正文提取', 'triage': '评分分流', 'read': '分块精读',
          'synthesize': '综合报告', 'organize': '资料归档', 'receipt': '交付回执'}
CODE_PATHS = {
    'extract': 'src/inresearch/workflow/reading_stages.py',
    'triage': 'src/inresearch/workflow/reading_stages.py',
    'read': 'src/inresearch/workflow/reading_stages.py',
    'synthesize': 'src/inresearch/workflow/reading_stages.py',
    'organize': 'src/inresearch/storage/moves.py',
    'receipt': 'src/inresearch/workflow/reader.py',
}
_CACHE = {}
_CACHE_LOCK = threading.Lock()


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


def age(value, now):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            return None
        seconds = now - dt.timestamp()
        return max(0, seconds) if seconds >= -300 else None
    except (ValueError, TypeError, OverflowError):
        return None


def error_info(code, stage=None):
    code = code or 'unknown'
    if code == 'worker_service_inactive':
        title, action, kind = '阅读服务未运行', '核对 Spark 的 inresearch-reader.service 与服务日志。', 'service'
    elif code.startswith('parked_'):
        title, action, kind = '按分流规则暂存', '检查分流结论；只有需要恢复的资料才按错误码选择性重排。', 'policy'
    elif code in ('ocr_deferred_behind_text_documents', 'ocr_checkpoint_yield'):
        title, action, kind = 'OCR 按调度策略排后', '核对优先级和正文优先策略；排后不代表程序崩溃。', 'policy'
    elif code.startswith('unsupported_format_'):
        title, action, kind = '原件格式尚无处理器', '按格式转换或采用专用工作流；这是处理能力缺口，不直接认定程序异常。', 'material'
    elif code == 'large_format_page_requires_drawing_workflow':
        title, action, kind = '大幅面图纸需专用处理', '走图纸工作流；不要将这些资料随全文阅读失败全队重试。', 'material'
    elif code == 'text_encoding_requires_conversion':
        title, action, kind = '文本编码需转换', '保留原件，核对编码并生成可读派生版本。', 'material'
    elif code == 'scanned_page_requires_ocr':
        title, action, kind = '扫描页缺少 OCR 文字', '核对当前正文提取策略；纯图片资料需人工处理，不要自动全队重跑。', 'material'
    elif code.startswith(('ocr_', 'm4_offload_')):
        title, action, kind = 'OCR 页面质量或覆盖受阻', '按文档和页号检查已有 OCR / 缺页记录，保留旧证据后补齐或人工裁决。', 'material'
    elif code.startswith(('model_', 'ollama_')):
        title, action, kind = '模型调用或输出校验失败', '核对模型服务与该任务的结构化输出日志；修复后仅重试对应任务。', 'execution'
    else:
        title, action, kind = '执行异常待定位', '按错误码、文档与 revision 查 Spark 服务日志，定位后再选择性重试。', 'execution'
    return {'code': code, 'title': title, 'action': action, 'kind': kind,
            'code_path': CODE_PATHS.get(stage, 'src/inresearch/workflow/reader.py')}


# Observe the in-flight replacement, if any, alongside published current results.
# A superseded failed initial revision must not inflate today's bottlenecks.
EXECUTION = """FROM reading_runs r JOIN documents d USING(doc_id)
 WHERE r.revision_id=COALESCE(
 (SELECT x.revision_id FROM reading_runs x WHERE x.doc_id=d.doc_id
  AND x.base_revision_id IS NOT NULL AND x.state IN ('queued','running','blocked','failed','ready')
  ORDER BY x.created DESC,x.revision_id DESC LIMIT 1),
 d.current_revision_id,
 (SELECT value FROM meta WHERE key='execution_root:'||d.doc_id),
 (SELECT x.revision_id FROM reading_runs x WHERE x.doc_id=d.doc_id AND x.base_revision_id IS NULL
  ORDER BY x.created,x.revision_id LIMIT 1))"""


def reader_observability(conn, now):
    """Small, bounded telemetry published with the candidate snapshot; SQL only."""
    q = lambda sql, args=(): [dict(r) for r in conn.execute(sql, args)]
    scope = 'WITH observed AS (SELECT r.*,' + 'd.original_name ' + EXECUTION + ') '
    jobs = ' FROM jobs j JOIN observed r ON r.revision_id=j.revision_id '
    stages = q(scope + 'SELECT j.stage,j.state,COUNT(*) count,COUNT(DISTINCT j.doc_id) documents' + jobs + 'GROUP BY j.stage,j.state')
    errors = q(scope + 'SELECT j.stage,j.error_code,COUNT(*) jobs,COUNT(DISTINCT j.doc_id) documents,MIN(j.finished) since,MAX(j.finished) last_seen' + jobs + "WHERE j.state IN ('blocked','failed') GROUP BY j.stage,j.error_code ORDER BY documents DESC,jobs DESC")
    examples = q(scope + 'SELECT * FROM (SELECT j.job_id,j.doc_id,j.revision_id,r.original_name,j.stage,j.state,j.chunk,j.attempts,j.created,j.available,j.started,j.finished,j.error_code,r.priority,r.pages_total,r.chunks_read,r.chunks_total,ROW_NUMBER() OVER(PARTITION BY j.stage,j.error_code ORDER BY j.finished,j.job_id) sample_rank' + jobs + "WHERE j.state IN ('blocked','failed')) WHERE sample_rank<=3")
    samples = {}
    for row in examples:
        for key in ('created', 'available', 'started', 'finished'):
            row[key] = iso(row[key])
        row['code_path'] = CODE_PATHS.get(row['stage'])
        samples.setdefault((row['stage'], row['error_code']), []).append(row)
    for row in errors:
        row['examples'] = samples.get((row['stage'], row['error_code']), [])
        row.update(error_info(row['error_code'], row['stage']))
        row['since'], row['last_seen'] = iso(row['since']), iso(row['last_seen'])
    categories = {}
    rank = {'policy': 0, 'material': 1, 'execution': 2, 'service': 3}
    for row in q(scope + 'SELECT DISTINCT j.doc_id,j.stage,j.error_code' + jobs + "WHERE j.state IN ('blocked','failed')"):
        kind = error_info(row['error_code'], row['stage'])['kind']
        previous = categories.get(row['doc_id'])
        if previous is None or rank[kind] > rank[previous]:
            categories[row['doc_id']] = kind
    windows = {}
    for label, seconds in (('1h', 3600), ('24h', 86400)):
        windows[label] = q('SELECT stage,state,COUNT(*) count FROM jobs WHERE finished>=? AND finished<=? AND state IN (\'succeeded\',\'failed\',\'blocked\') GROUP BY stage,state', (now - seconds, now))
    lists = {}
    for state, condition, order in (
        ('pending', "j.state='pending'", 'j.created,j.job_id'),
        ('running', "j.state='running'", 'j.started,j.job_id'),
        ('blocked', "j.state IN ('blocked','failed')", 'j.finished,j.job_id')):
        total = q(scope + 'SELECT COUNT(*) count' + jobs + 'WHERE ' + condition)[0]['count']
        rows = q(scope + 'SELECT j.job_id,j.doc_id,j.revision_id,r.original_name,j.stage,j.state,j.chunk,j.attempts,j.created,j.available,j.started,j.finished,j.error_code,r.priority,r.pages_total,r.chunks_read,r.chunks_total' + jobs + 'WHERE ' + condition + ' ORDER BY ' + order + ' LIMIT 100')
        for row in rows:
            for key in ('created', 'available', 'started', 'finished'):
                row[key] = iso(row[key])
            row['code_path'] = CODE_PATHS.get(row['stage'])
        lists[state] = {'total': total, 'items': rows, 'limit': 100, 'order': 'oldest_first'}
    current = {r['state']: r['count'] for r in q('SELECT state,COUNT(*) count FROM current_readings GROUP BY state')}
    return {'schema_version': 1, 'generated': iso(now), 'current_documents': current,
            'execution_documents': {r['state']: r['count'] for r in q(scope + 'SELECT state,COUNT(*) count FROM observed GROUP BY state')},
            'bottleneck_documents': dict(Counter(categories.values())), 'stages': stages, 'errors': errors, 'windows': windows, 'queues': lists,
            'scope': 'one_execution_revision_per_document',
            'window_scope': 'all_completed_jobs_in_time_window'}


def record_task(root, task, name, output, *, started, returncode=None, outcome=None, duration=None):
    """Keep full output and an immutable run record, plus the latest task record."""
    run_id = uuid.uuid4().hex
    directory = workspace_path('logs/ops', root)
    directory.mkdir(parents=True, exist_ok=True)
    now = time.time()
    outcome = outcome or ('succeeded' if returncode == 0 else 'failed')
    row = {'id': run_id, 'task': task, 'name': name, 'started': iso(started),
           'finished': iso(now), 'duration_seconds': duration if duration is not None else max(0, now - started),
           'outcome': outcome, 'returncode': returncode, 'output_chars': len(output)}
    atomic_write(directory / (run_id + '.log'), output.encode('utf-8'))
    write_json(directory / (run_id + '.json'), row)
    write_json(workspace_path('logs/task_' + task + '.json', root), row)
    atomic_write(workspace_path('logs/task_' + task + '.log', root), ('[' + iso(now) + ']\n' + output + '\n').encode('utf-8'))
    return row


def log_content(root, run_id):
    if not isinstance(run_id, str) or not re.fullmatch('[0-9a-f]{32}', run_id):
        raise ValueError('invalid run identity')
    path = workspace_path('logs/ops/' + run_id + '.log', root)
    if path.is_symlink():
        raise ValueError('invalid log')
    return path.read_text(encoding='utf-8')


def task_state(root, tasks, running):
    rows = {}
    for task, (name, _, _) in tasks.items():
        path = workspace_path('logs/task_' + task + '.json', root)
        legacy = workspace_path('logs/task_' + task + '.log', root)
        try:
            row = json.loads(path.read_text())
            if not isinstance(row, dict):
                raise ValueError('invalid task record')
        except (OSError, ValueError):
            row = {'outcome': 'unknown', 'finished': iso(legacy.stat().st_mtime) if legacy.exists() else None,
                   'legacy': legacy.exists()}
        rows[task] = dict(row, name=name, running=task in running, last=row.get('finished'))
    return rows


def task_history(root):
    directory = workspace_path('logs/ops', root)
    items = []
    files = sorted(directory.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True) if directory.exists() else []
    for path in files[:50]:
        try:
            row = json.loads(path.read_text())
            if isinstance(row, dict):
                items.append(row)
        except (OSError, ValueError):
            continue
    return {'total': len(files), 'limit': 50, 'items': items}


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _cached(key, stamp, build):
    with _CACHE_LOCK:
        if key not in _CACHE or _CACHE[key][0] != stamp:
            _CACHE[key] = stamp, build()
        return copy.deepcopy(_CACHE[key][1])


def _stamp(path):
    try:
        st = Path(path).stat()
        return st.st_mtime_ns, st.st_size
    except OSError:
        return None


def _reader(root):
    from inresearch.knowledge import registry
    path = Path(os.environ.get('INRESEARCH_READER_SNAPSHOT', workspace_path('data/research_runtime.json', root)))
    stamp = (_stamp(path), _stamp(root / 'framework/research_graph.json'), _stamp(root / 'framework/research_questions.json'), _stamp(root / 'data/research_knowledge.json'))
    def load():
        # Use the existing validation/identity rules, never trust a copied raw snapshot.
        *_, runtime = registry._snapshot_inputs(root)
        reader = registry._reader_state(runtime)
        # The management screen needs counters and bounded diagnostic samples,
        # not the multi-megabyte daily events / matching / delivery feed.
        summary = {key: reader[key] for key in (
            'status', 'generated', 'received_at', 'counts', 'release', 'registry_lag',
            'operations', 'thermal', 'claim_floor', 'execution_scope', 'last_scan'
        ) if key in reader}
        acquisition = reader.get('acquisition')
        if isinstance(acquisition, dict):
            summary['acquisition'] = {key: acquisition[key] for key in ('status', 'sources') if key in acquisition}
        return summary
    return _cached(('reader', str(root), str(path)), stamp, load)


def _quality(root):
    from inresearch.knowledge.fact_contract import check_fact
    from inresearch.knowledge import verify
    facts = _read(root / 'data/facts.json')['records']
    metrics = {m['metric_id']: m for m in _read(root / 'framework/metrics.json')['metrics']}
    problems, seen = [], set()
    for fact in facts:
        problems.extend({'id': fact.get('fact_id'), 'reason': reason} for reason in check_fact(fact, metrics, seen))
        seen.add(fact.get('fact_id'))
    queue = verify.build_queue(root=root)
    return {'facts': {'records': len(facts), 'errors': len(problems), 'items': problems[:100], 'limit': 100},
            'verification': {'counts': dict(Counter(str(r['p']) for r in queue)), 'items': queue[:100], 'total': len(queue)}}


def snapshot(root, tasks, running, now=None):
    root = Path(root)
    now = time.time() if now is None else now
    result = {'generated': iso(now), 'timezone': 'Asia/Shanghai', 'tasks': task_state(root, tasks, running),
              'history': task_history(root), 'unavailable': []}
    try:
        reader = _reader(root)
        reader['snapshot_age_seconds'] = age(reader.get('received_at'), now)
        reader['generated_age_seconds'] = age(reader.get('generated'), now)
        reader['stale'] = reader['snapshot_age_seconds'] is None or reader['snapshot_age_seconds'] > 900 or reader['generated_age_seconds'] is None or reader['generated_age_seconds'] > 900
        result['reader'] = reader
    except (ValueError, TypeError, KeyError, OSError):
        result['reader'] = {'status': 'unknown', 'stale': True}
        result['unavailable'].append('阅读快照无法读取或校验')
    files = ['data/facts.json', 'framework/metrics.json', 'data/projects.json', 'data/prices.json',
             'data/contracts.json', 'data/policies.json', 'data/research.json']
    stamp = (int(now // 60), *(_stamp(workspace_path(f, root)) for f in files))
    try:
        result['quality'] = _cached(('quality', str(root)), stamp, lambda: _quality(root))
    except (ValueError, TypeError, KeyError, OSError):
        result['unavailable'].append('事实与核验台账无法读取')
    try:
        targets = _read(root / 'framework/tco_targets.json')
        rows = targets['targets']
        result['targets'] = {'total': len(rows), 'states': dict(Counter(r.get('status', 'unknown') for r in rows)),
                             'teams': [dict(team=k, **dict(v)) for k, v in _teams(rows).items()], 'updated': targets.get('updated')}
    except (ValueError, TypeError, KeyError, OSError):
        result['unavailable'].append('目标行台账无法读取')
    return result


def _teams(rows):
    teams = {}
    for row in rows:
        teams.setdefault(row.get('team', 'unknown'), Counter())[row.get('status', 'unknown')] += 1
    return teams
