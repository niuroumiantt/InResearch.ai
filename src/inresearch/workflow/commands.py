"""Business mutations shared by authenticated HTTP and trusted local CLI.

The transport supplies an actor; it cannot override a domain decision. Runtime
data paths are explicit so tests, deployment volumes and local tools agree.
"""
import math
import os
from datetime import date
from pathlib import Path

from inresearch.knowledge import registry as research
from inresearch.knowledge.policy import price_errors
from inresearch.storage.layout import workspace_path
from inresearch.storage.files import json_transaction, locked, write_json

ASSIGN_STATUSES = {'已派', '进行中', '已交付', '已合并', '已放弃'}

# Reader snapshots travel gzip-compressed (JSON shrinks roughly tenfold). The wire
# limit stays 64 MiB; the inflated document may be larger, up to SNAPSHOT_MAX_BYTES,
# which also bounds a decompression bomb. Uncompressed bodies are still accepted.
SNAPSHOT_WIRE_MAX_BYTES = 64 * 1024 * 1024
SNAPSHOT_MAX_BYTES = 192 * 1024 * 1024


class SnapshotTooLarge(ValueError):
    pass


def inflate_snapshot(raw, encoding):
    """Request body -> JSON bytes, refusing anything past SNAPSHOT_MAX_BYTES."""
    import zlib
    encoding = (encoding or 'identity').strip().lower()
    if encoding == 'identity':
        return raw
    if encoding != 'gzip':
        raise ValueError('unsupported Content-Encoding: ' + encoding[:40])
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = inflater.decompress(raw, SNAPSHOT_MAX_BYTES + 1)
    except zlib.error:
        raise ValueError('snapshot body is not valid gzip') from None
    if len(out) > SNAPSHOT_MAX_BYTES or inflater.unconsumed_tail:
        raise SnapshotTooLarge('inflated snapshot exceeds %d MiB' % (SNAPSHOT_MAX_BYTES // 1024 // 1024))
    if not inflater.eof:
        raise ValueError('snapshot body is not valid gzip')
    return out


class Rejected(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def add_price(root, record):
    rec = dict(record)
    required = ('series_id', 'as_of', 'value', 'unit', 'grade', 'source_url', 'category', 'module')
    missing = [key for key in required if rec.get(key) in (None, '')]
    if missing:
        raise Rejected('缺少字段: ' + ', '.join(missing))
    try:
        if isinstance(rec['value'], bool):
            raise ValueError()
        rec['value'] = float(rec['value'])
        if not math.isfinite(rec['value']):
            raise ValueError()
    except (ValueError, TypeError):
        raise Rejected('value 必须是数字') from None
    problems = price_errors(rec)
    if problems:
        raise Rejected('；'.join(problems))
    rec.setdefault('region', None)
    rec.setdefault('assumptions', None)
    rec.setdefault('note', '人工录入')
    # 登记表两列（2026-09-28）：node 与 variable_class 从骨架派生，录入者不填、填了也以派生为准
    from inresearch.knowledge import nodes as node_columns
    rec.update(node_columns.series_fields(rec, node_columns.build_index(root)))
    with json_transaction(workspace_path('data/prices.json', root)) as doc:
        if any((row['series_id'], row['as_of']) == (rec['series_id'], rec['as_of'])
               for row in doc['records']):
            raise Rejected('该序列在此时点已有记录（series_id + as_of 唯一）', 409)
        doc['records'].append(rec)
    reply = {'ok': True, 'msg': "已入库 %s@%s = %s %s" %
             (rec['series_id'], rec['as_of'], rec['value'], rec['unit'])}
    # The price file is the commit point. A projection failure must not invite
    # resubmission of an already committed record; rebuilding is independently retryable.
    try:
        from inresearch.knowledge.indicators import refresh
        reply['indicators'] = refresh(root)
    except (OSError, ValueError, KeyError, TypeError):
        reply['projection_pending'] = True
        reply['msg'] += '；指标待回填，可重试 indicators'
    return reply


def assign(root, rec, by='', role='admin'):
    """派工：2026-09-28 起按目标行 ID（target_id，目标表是唯一任务书）；workorder_id 只作兼容工单。"""
    tid = str(rec.get('target_id') or '').strip()
    wid = str(rec.get('workorder_id') or '').strip()
    status = str(rec.get('status') or '').strip()
    if not wid and not tid:
        raise Rejected('缺 target_id（目标行）或 workorder_id（兼容工单）')
    if status and status not in ASSIGN_STATUSES:
        raise Rejected('状态非法（合法：%s）' % '、'.join(sorted(ASSIGN_STATUSES)))
    with json_transaction(workspace_path('data/assignments.json', root)) as doc:
        doc.setdefault('records', [])
        if tid:
            from inresearch.workflow import dispatch
            if tid not in dispatch.target_ids(root):
                raise Rejected(tid + ' 不在当前目标表里，请刷新', 404)
            row = next((r for r in doc['records'] if r.get('target_id') == tid), None)
        else:
            if wid not in {o['wid'] for o in research.current_tasks(root)}:
                raise Rejected(wid + ' 已不在当前任务集合中，请刷新任务列表')
            row = next((r for r in doc['records'] if r.get('workorder_id') == wid), None)
        if role == 'intern':
            if not by or not row or row.get('assignee') != by or rec.get('assignee', by) != by:
                raise Rejected('只能更新分配给自己的工单', 403)
            if status not in ('进行中', '已交付'):
                raise Rejected('实习生可提交交付，采用与合并由内部审核', 403)
        if row is None:
            row = {'target_id': tid} if tid else {'workorder_id': wid}
            doc['records'].append(row)
        for key in ('assignee', 'status', 'due', 'note'):
            if rec.get(key) is not None:
                row[key] = rec[key]
        row.setdefault('status', '已派')
        row['updated'] = date.today().isoformat()
        if by:
            row['by'] = by
        row.setdefault('assigned', row['updated'])
        if row['status'] == '已放弃' and not row.get('note'):
            raise Rejected('标为已放弃必须写 note 说明原因')
        doc['updated'] = row['updated']
    return {'ok': True, 'msg': "%s → %s（%s）" % (tid or wid, row.get('assignee') or '未指定', row['status'])}


def receive_snapshot(root, payload, destination=None):
    root = Path(root)
    destination = Path(destination or os.environ.get('INRESEARCH_READER_SNAPSHOT', workspace_path('data/research_runtime.json', root)))
    with locked(destination):
        snapshot = research.candidate_snapshot(payload,
            research.read_json(root / 'framework/research_graph.json'),
            research.read_json(root / 'framework/research_questions.json'))
        research.merge_knowledge(research.read_json(root / 'data/research_knowledge.json'), snapshot['knowledge'])
        previous = research.read_json(destination, {})
        if previous.get('generated') and research.parse_time(snapshot['generated']) <= research.parse_time(previous['generated']):
            raise Rejected('stale or repeated snapshot', 409)
        write_json(destination, snapshot)
    return {'ok': True, 'received_at': snapshot['received_at'], 'documents': len(snapshot['knowledge']['documents'])}
