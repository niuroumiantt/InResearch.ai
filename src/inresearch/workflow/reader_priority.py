"""Explicit reading order, independent of model importance and C3 authority."""
import json
from pathlib import Path
import re
import sqlite3

from inresearch.materials.artifacts import encoded, now_iso


def prioritize(data, *, doc_id, revision_id, expected_priority, priority, request_id,
               by, reason, dry_run=False):
    if not isinstance(doc_id, str) or not re.fullmatch(r'doc-[0-9a-f]{64}', doc_id):
        raise ValueError('priority_invalid_document')
    if (not isinstance(revision_id, str) or not 1 <= len(revision_id) <= 256
            or not isinstance(request_id, str)
            or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{7,79}', request_id)):
        raise ValueError('priority_invalid_identity')
    if (type(expected_priority) is not int or type(priority) is not int
            or not 0 <= expected_priority < priority <= 10):
        raise ValueError('priority_requires_explicit_increase')
    if any(not isinstance(v, str) or not v.strip() or len(v) > limit
           for v, limit in ((by, 300), (reason, 2000))):
        raise ValueError('priority_requires_actor_and_reason')
    intent = dict(doc_id=doc_id, revision_id=revision_id, expected_priority=expected_priority,
                  priority=priority, request_id=request_id, by=by, reason=reason)
    path = Path(data).expanduser().resolve() / 'catalog/catalog.sqlite'
    if not path.is_file() or path.is_symlink():
        raise ValueError('priority_catalog_missing_or_unsafe')
    db = sqlite3.connect(path.as_uri() + ('?mode=ro' if dry_run else '?mode=rw'),
                         uri=True, timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        if db.execute('PRAGMA user_version').fetchone()[0] != 2:
            raise ValueError('priority_requires_current_schema')
        db.execute('BEGIN' if dry_run else 'BEGIN IMMEDIATE')
        key = 'reader_priority:' + request_id
        previous = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        if previous:
            receipt = json.loads(previous[0])
            if receipt['intent'] != intent:
                raise ValueError('priority_request_id_conflict')
            return dict(receipt, status='already_applied')
        doc = db.execute('SELECT * FROM current_readings WHERE doc_id=?', (doc_id,)).fetchone()
        if not doc or doc['revision_id'] != revision_id:
            raise ValueError('priority_current_revision_changed')
        if doc['state'] in ('complete', 'rejected', 'superseded', 'failed', 'blocked'):
            raise ValueError('priority_reading_not_schedulable')
        if doc['priority'] != expected_priority:
            raise ValueError('priority_compare_failed')
        receipt = dict(schema_version=1, status='planned' if dry_run else 'applied',
                       intent=intent, recipe=doc['recipe'], at=now_iso(),
                       authority='reading_order_only_not_importance_or_adoption')
        if not dry_run:
            changed = db.execute('UPDATE reading_runs SET priority=? WHERE doc_id=? AND revision_id=? AND priority=?',
                                 (priority, doc_id, revision_id, expected_priority)).rowcount
            if changed != 1:
                raise ValueError('priority_compare_failed')
            db.execute('INSERT INTO meta(key,value) VALUES(?,?)', (key, encoded(receipt)))
            db.commit()
        return receipt
    finally:
        if db.in_transaction:
            db.rollback()
        db.close()
