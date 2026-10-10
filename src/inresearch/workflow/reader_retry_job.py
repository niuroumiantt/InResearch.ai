"""Explicit, source-bound single-job retry in an existing Reader catalog.

This use case shares SQLite's writer transaction with claim(), not the worker
lifecycle lock. It never constructs a Reader or runs inference/reconciliation.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time

from inresearch.materials.artifacts import digest_file, encoded, now_iso, private_dir, safe_path
from inresearch.materials.reading_artifacts import ReadingArtifacts
from inresearch.materials.reader_contracts import Blocked, RECIPE_VERSION
from inresearch.storage.files import atomic_write, locked, sync_directory

ERRORS = frozenset({'model_cli_failed'})


def _require(condition, code):
    if not condition:
        raise Blocked(code)


def _connect(path, mode):
    _require(path.is_file() and not path.is_symlink(), 'reader_catalog_missing_or_unsafe')
    conn = sqlite3.connect(path.as_uri() + '?mode=' + mode, uri=True, timeout=5,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        _require(conn.execute('PRAGMA user_version').fetchone()[0] == 2,
                 'reader_catalog_requires_current_schema')
        view = conn.execute("SELECT sql FROM sqlite_master WHERE type='view' AND name='current_readings'").fetchone()
        _require(view and 'execution_root:' in view[0] and 'COALESCE(d.current_revision_id' in view[0],
                 'reader_catalog_requires_current_schema')
        if mode == 'ro':
            conn.execute('PRAGMA query_only=ON')
        return conn
    except BaseException:
        conn.close()
        raise


def _snapshot(conn, intent):
    doc = conn.execute('SELECT * FROM current_readings WHERE doc_id=?', (intent['doc_id'],)).fetchone()
    _require(doc and doc['revision_id'] == intent['revision_id'], 'retry_current_revision_changed')
    doc = dict(doc)
    _require(doc['state'] == 'failed' and doc['phase'] == 'read'
             and doc['error_code'] == intent['error_code'] and doc['recipe'] == intent['recipe'],
             'retry_reading_state_changed')
    jobs = [dict(r) for r in conn.execute('SELECT * FROM jobs WHERE doc_id=? AND revision_id=? ORDER BY stage,chunk',
                                         (intent['doc_id'], intent['revision_id']))]
    failed = [j for j in jobs if j['state'] in ('failed', 'blocked')]
    _require(len(failed) == 1 and not any(j['state'] == 'running' for j in jobs),
             'retry_requires_one_failed_idle_job')
    job = failed[0]
    _require(job['state'] == 'failed' and job['stage'] == intent['stage']
             and job['chunk'] == intent['chunk_index'] and job['error_code'] == intent['error_code']
             and job['attempts'] == intent['attempts']
             and type(job['max_attempts']) is int and job['max_attempts'] >= 1
             and job['attempts'] >= job['max_attempts']
             and job['result_rel'] is None, 'retry_job_compare_failed')
    return {'document': doc, 'jobs': jobs, 'job': job}


def _files(data, snapshot, expected_recipe_sha256):
    doc = snapshot['document']; artifacts = ReadingArtifacts(data)
    source = safe_path(data, doc['original_rel'])
    _require(digest_file(source) == doc['sha256'] and doc['doc_id'] == 'doc-' + doc['sha256'],
             'retry_original_source_changed')
    recipe = artifacts.artifact_path(doc, 'recipe.json')
    _require(digest_file(recipe) == expected_recipe_sha256, 'retry_frozen_recipe_changed')
    value = json.loads(recipe.read_text())
    _require(isinstance(value, dict) and value.get('recipe') == doc['recipe'] and value.get('version') == RECIPE_VERSION,
             'retry_frozen_recipe_changed')
    context_path = artifacts.artifact_path(doc, 'context.json')
    context = json.loads(context_path.read_text())
    _require(isinstance(context, dict), 'retry_frozen_context_changed')
    context_sha = hashlib.sha256(encoded({k: v for k, v in context.items() if k != 'snapshot_hash'}).encode()).hexdigest()
    _require(context.get('snapshot_hash') == context_sha, 'retry_frozen_context_changed')
    identity = {k: v for k, v in value.items() if k != 'recipe'}
    identity['snapshot'] = context_sha
    _require(hashlib.sha256(encoded(identity).encode()).hexdigest()[:24] == doc['recipe'],
             'retry_frozen_recipe_changed')
    extraction = artifacts._cached(doc, 'extraction.json', 'extract')
    _require(extraction and len(extraction['chunks']) == doc['chunks_total'],
             'retry_extraction_changed')
    paths = [source, recipe, context_path,
             artifacts.artifact_path(doc, 'extraction.json')]
    failed_cache = artifacts.artifact_path(doc, 'chunks/%06d.json' % snapshot['job']['chunk'])
    _require(not failed_cache.exists(), 'retry_failed_chunk_cache_exists')
    for index, chunk in enumerate(extraction['chunks']):
        _require(chunk.get('index') == index, 'retry_extraction_changed')
        artifacts._chunk_text(chunk)  # Existing frozen native bytes, never re-extract.
        paths.append(safe_path(data, chunk['text_rel']))
    if any(j['stage'] == 'triage' and j['state'] == 'succeeded' for j in snapshot['jobs']):
        _require(artifacts._cached(doc, 'triage.json', 'triage') is not None, 'retry_triage_changed')
        paths.append(artifacts.artifact_path(doc, 'triage.json'))
    successes = [j for j in snapshot['jobs'] if j['stage'] == 'read' and j['state'] == 'succeeded']
    _require(len(successes) == doc['chunks_read'], 'retry_success_coverage_changed')
    for job in successes:
        index = job['chunk']
        _require(type(index) is int and 0 <= index < len(extraction['chunks']), 'retry_success_coverage_changed')
        value = artifacts._cached(doc, 'chunks/%06d.json' % index, 'read:%d' % index)
        text = artifacts._chunk_text(extraction['chunks'][index])
        _require(value and value.get('chunk_sha256') == extraction['chunks'][index]['sha256']
                 and value.get('chunk_index') == index
                 and value.get('page_index') == extraction['chunks'][index]['page_index']
                 and value.get('characters') == len(text),
                 'retry_success_cache_changed')
        paths.append(artifacts.artifact_path(doc, 'chunks/%06d.json' % index))
    _require(0 <= snapshot['job']['chunk'] < doc['chunks_total'], 'retry_chunk_out_of_range')
    return {p.relative_to(data).as_posix(): digest_file(p) for p in paths}


def _backup(db, target):
    fd = os.open(target, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    source = _connect(db, 'ro'); dest = sqlite3.connect(target); started = time.monotonic()
    try:
        def bounded(status, remaining, total):
            _require(time.monotonic() - started < 20, 'retry_backup_timeout')
        source.backup(dest, pages=1024, progress=bounded, sleep=.01)
        _require(dest.execute('PRAGMA journal_mode=DELETE').fetchone()[0] == 'delete', 'retry_backup_invalid')
        _require(dest.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'retry_backup_invalid')
    finally:
        dest.close(); source.close()
    with target.open('rb') as stream:
        os.fsync(stream.fileno())
    sync_directory(target.parent)


def _marker(conn, key):
    row = conn.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
    return json.loads(row[0]) if row else None


def _check_audit(directory, intent, marker=None):
    before = directory / 'before.json'; backup = directory / 'catalog-before.sqlite'
    _require(directory.is_dir() and not directory.is_symlink() and not (directory.stat().st_mode & 0o077),
             'retry_audit_not_private')
    _require(before.is_file() and not before.is_symlink() and backup.is_file() and not backup.is_symlink(),
             'retry_request_incomplete')
    record = json.loads(before.read_text())
    _require(not (before.stat().st_mode & 0o077) and not (backup.stat().st_mode & 0o077),
             'retry_audit_not_private')
    _require(isinstance(record, dict) and record.get('intent') == intent, 'retry_request_id_conflict')
    _require(record.get('backup_sha256') == digest_file(backup), 'retry_backup_changed')
    connection = _connect(backup, 'ro')
    try:
        _require(_snapshot(connection, intent) == record.get('snapshot'), 'retry_backup_snapshot_changed')
    finally:
        connection.close()
    if marker:
        _require(isinstance(marker, dict) and marker.get('request_id') == intent['request_id']
                 and marker.get('doc_id') == intent['doc_id'] and marker.get('revision_id') == intent['revision_id'],
                 'retry_audit_changed')
        _require(marker.get('before_sha256') == digest_file(before)
                 and marker.get('backup_sha256') == record['backup_sha256'], 'retry_audit_changed')
    return record


def _commit(conn):
    conn.commit()


def retry_job(data_root, *, doc_id, revision_id, stage, chunk_index, error_code,
              expected_attempts, expected_recipe, expected_recipe_sha256, request_id, by, reason, dry_run=False):
    """Requeue one failed read job without replacing its exhausted budget."""
    _require(data_root is not None, 'retry_explicit_data_root_required')
    _require(re.fullmatch(r'doc-[a-f0-9]{64}', doc_id or '')
             and re.fullmatch(r'rev-[a-f0-9]{32}', revision_id or ''), 'retry_invalid_identity')
    _require(stage == 'read' and type(chunk_index) is int and chunk_index >= 0,
             'retry_invalid_stage_or_chunk')
    _require(error_code in ERRORS and type(expected_attempts) is int and expected_attempts >= 1,
             'retry_invalid_error_or_attempts')
    _require(re.fullmatch(r'[a-f0-9]{24}', expected_recipe or '')
             and re.fullmatch(r'[a-f0-9]{64}', expected_recipe_sha256 or ''), 'retry_invalid_recipe')
    _require(re.fullmatch(r'[a-z0-9][a-z0-9._-]{7,79}', request_id or ''), 'retry_invalid_request_id')
    _require(all(isinstance(x, str) and x.strip() == x and 1 <= len(x) <= limit
                 for x, limit in ((by, 300), (reason, 2000))), 'retry_requires_actor_and_reason')
    candidate = Path(data_root).expanduser()
    _require(candidate.is_dir(), 'reader_catalog_missing_or_unsafe')
    data = candidate.resolve(strict=True)
    db = safe_path(data, 'catalog/catalog.sqlite'); conn = _connect(db, 'ro')
    conn.close()  # Refuse missing/old catalogs before creating audit paths.
    intent = {'doc_id': doc_id, 'revision_id': revision_id, 'stage': stage,
              'chunk_index': chunk_index, 'error_code': error_code, 'attempts': expected_attempts,
              'recipe': expected_recipe, 'recipe_sha256': expected_recipe_sha256, 'request_id': request_id, 'by': by, 'reason': reason}
    if dry_run:
        conn = _connect(db, 'ro')
        try:
            conn.execute('BEGIN')
            snapshot = _snapshot(conn, intent)
            hashes = _files(data, snapshot, expected_recipe_sha256)
            return {'status': 'eligible', 'dry_run': True, 'job_id': snapshot['job']['job_id'],
                    'attempts_preserved': expected_attempts,
                    'available_preserved': snapshot['job']['available'],
                    'successful_read_chunks_preserved': snapshot['document']['chunks_read'],
                    'source_and_cache_file_count': len(hashes),
                    'snapshot_sha256': hashlib.sha256(encoded(snapshot).encode()).hexdigest()}
        finally:
            conn.close()
    base = safe_path(data, 'catalog/reader-job-retries'); private_dir(base)
    directory = safe_path(data, 'catalog/reader-job-retries/' + request_id)
    key = 'reader_retry_job:' + request_id
    with locked(directory):
        _require(not (base.stat().st_mode & 0o077), 'retry_audit_not_private')
        conn = _connect(db, 'ro')
        try: previous = _marker(conn, key)
        finally: conn.close()
        if previous:
            _check_audit(directory, intent, previous)
            return {**previous, 'status': 'already_applied', 'request_id': request_id}
        if not directory.exists():
            private_dir(directory)
            _backup(db, directory / 'catalog-before.sqlite')
            backup = _connect(directory / 'catalog-before.sqlite', 'ro')
            try: snapshot = _snapshot(backup, intent)
            finally: backup.close()
            record = {'schema_version': 1, 'operation': 'reader_retry_job', 'prepared_at': now_iso(),
                      'intent': intent, 'snapshot': snapshot, 'file_sha256': _files(data, snapshot, expected_recipe_sha256),
                      'backup_sha256': digest_file(directory / 'catalog-before.sqlite')}
            atomic_write(directory / 'before.json', (encoded(record) + '\n').encode(), exclusive=True)
        _require(not (directory.stat().st_mode & 0o077), 'retry_audit_not_private')
        record = _check_audit(directory, intent)
        marker = {'schema_version': 1, 'request_id': request_id, 'job_id': record['snapshot']['job']['job_id'],
                  'doc_id': doc_id, 'revision_id': revision_id,
                  'before_rel': (directory / 'before.json').relative_to(data).as_posix(),
                  'before_sha256': digest_file(directory / 'before.json'),
                  'backup_sha256': record['backup_sha256'], 'attempts_preserved': expected_attempts,
                  'available_preserved': record['snapshot']['job']['available'], 'recorded_at': now_iso()}
        conn = _connect(db, 'rw'); committed = False
        try:
            conn.execute('BEGIN IMMEDIATE')
            _require(_marker(conn, key) is None, 'retry_request_changed')
            snapshot = _snapshot(conn, intent)
            _require(snapshot == record['snapshot'] and _files(data, snapshot, expected_recipe_sha256) == record['file_sha256'],
                     'retry_snapshot_changed')
            job = snapshot['job']
            changed = conn.execute("UPDATE jobs SET state='pending',error_code=NULL WHERE job_id=? AND doc_id=? AND revision_id=? AND stage=? AND chunk=? AND state='failed' AND attempts=? AND error_code=?",
                                   (job['job_id'], doc_id, revision_id, stage, chunk_index, expected_attempts, error_code))
            _require(changed.rowcount == 1, 'retry_job_compare_failed')
            changed = conn.execute("UPDATE reading_runs SET state='queued',error_code=NULL WHERE doc_id=? AND revision_id=? AND state='failed' AND phase='read' AND recipe=? AND error_code=?",
                                   (doc_id, revision_id, expected_recipe, error_code))
            _require(changed.rowcount == 1, 'retry_reading_state_changed')
            conn.execute('INSERT INTO meta(key,value) VALUES(?,?)', (key, encoded(marker)))
            _commit(conn); committed = True
        except BaseException:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            # A commit can become visible before an I/O error reaches the caller.
            # The transaction marker is authoritative; never repeat or roll back
            # a retry already visible to the running worker.
            check = _connect(db, 'ro')
            try: visible = _marker(check, key)
            finally: check.close()
            if visible != marker:
                raise
            committed = True
        finally:
            conn.close()
        result = {**marker, 'status': 'applied', 'receipt_written': False}
        if committed:
            try:
                atomic_write(directory / 'receipt.json', (encoded(result) + '\n').encode(), exclusive=True)
                result['receipt_written'] = True
            except OSError:
                result['receipt_error'] = 'post_commit_receipt_unavailable; transaction marker retained'
        return result
