"""Attach explicitly supplied source metadata to existing, SHA-verified research.

No fetching, extraction, Reader work, matching or adoption occurs here. A URL is
supplier metadata, not proof that the archived bytes were fetched from that URL.
"""
import hashlib
import json
import re
import sqlite3
from pathlib import Path, PurePosixPath

from inresearch.adapters.acquisition import encoded, hash_file, now
from inresearch.storage.files import atomic_write
from inresearch.materials.source_provenance import source_url, validate as validate_provenance


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('invalid_source_sha256')
    return value


def _file(base, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('invalid_source_path')
    parts = PurePosixPath(relative).parts
    if PurePosixPath(relative).is_absolute() or '..' in parts:
        raise ValueError('invalid_source_path')
    path = base
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('source_symlink')
    if not path.is_file():
        raise ValueError('source_file_missing')
    return path


def receive(sidecar, data, *, apply=False):
    """Preflight the whole batch; atomically fill metadata, never overwrite it."""
    sidecar = Path(sidecar)
    if sidecar.is_symlink() or not sidecar.is_file() or sidecar.stat().st_size > 1024 * 1024:
        raise ValueError('invalid_source_sidecar')
    body = sidecar.read_bytes()
    sidecar_sha = hashlib.sha256(body).hexdigest()
    payload = json.loads(body)
    if not isinstance(payload, dict) or not isinstance(payload.get('batch'), str) or not payload['batch']:
        raise ValueError('invalid_source_sidecar')
    items = payload.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 1000:
        raise ValueError('invalid_source_sidecar')
    planned = []
    seen = set()
    for row in items:
        if not isinstance(row, dict):
            raise ValueError('invalid_source_row')
        sha = _sha(row.get('sha256'))
        if sha in seen:
            raise ValueError('duplicate_source_sha256')
        seen.add(sha)
        path = _file(sidecar.parent, row.get('input_path'))
        if hash_file(path) != sha:
            raise ValueError('source_input_hash_mismatch')
        source_id = row.get('source_id')
        if not isinstance(source_id, str) or not source_id or len(source_id) > 160:
            raise ValueError('invalid_source_id')
        role = row.get('role')
        proof = {'method': 'supplied_sidecar_sha_binding_v1', 'sidecar_sha256': sidecar_sha,
                 'batch': payload['batch'], 'source_id': source_id, 'role': role,
                 'input_sha256': sha, 'url': source_url(row.get('url')),
                 'url_verification': 'supplier_metadata_only_no_fetch'}
        if role == 'downloaded_original':
            if _sha(row.get('original_sha256')) != sha:
                raise ValueError('source_original_hash_mismatch')
            proof['original_bytes_sha256'] = sha
        elif role == 'decoded_archived_tool_response':
            if 'original_bytes_sha256' not in row or row['original_bytes_sha256'] is not None:
                raise ValueError('tool_response_is_not_original')
            response_sha = _sha(row.get('response_sha256'))
            if hash_file(_file(sidecar.parent, row.get('response_path'))) != response_sha:
                raise ValueError('source_response_hash_mismatch')
            if not isinstance(row.get('derivation'), str) or not row['derivation']:
                raise ValueError('source_derivation_required')
            proof.update(original_bytes_sha256=None, response_sha256=response_sha,
                         derivation=row['derivation'])
        else:
            raise ValueError('invalid_source_role')
        planned.append((sha, validate_provenance(proof, sha, proof['url'])))
    if sidecar.read_bytes() != body:
        raise ValueError('source_sidecar_changed')
    catalog = Path(data) / 'acquisition/catalog.sqlite'
    if not catalog.is_file() or catalog.is_symlink():
        raise ValueError('source_catalog_missing')
    db = sqlite3.connect(catalog.resolve().as_uri() + ('?mode=rw' if apply else '?mode=ro'), uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    results = []
    try:
        db.execute('BEGIN IMMEDIATE' if apply else 'BEGIN')
        updates = []
        for sha, proof in planned:
            row = db.execute("SELECT id,url,metadata FROM items WHERE source='fetchreports' AND kind='supplied_research' AND source_key=?", (sha,)).fetchone()
            if row is None:
                raise ValueError('source_research_not_received')
            observations = db.execute('SELECT sha256,relative_path FROM observations WHERE item_id=? AND sha256=?', (row['id'], sha)).fetchall()
            if not observations or any(hash_file(_file(Path(data), o['relative_path'])) != sha for o in observations):
                raise ValueError('source_archive_hash_mismatch')
            meta = json.loads(row['metadata'])
            if meta.get('sha256') != sha:
                raise ValueError('source_metadata_hash_mismatch')
            if row['url'] and row['url'] != proof['url']:
                raise ValueError('source_url_conflict')
            if meta.get('source_url') and meta['source_url'] != proof['url']:
                raise ValueError('source_url_conflict')
            old = meta.get('source_provenance')
            if old is not None and old != proof:
                raise ValueError('source_provenance_conflict')
            changed = not row['url'] or old is None or not meta.get('source_url')
            before_sha = hashlib.sha256(row['metadata'].encode()).hexdigest()
            meta.update(source_url=proof['url'], source_provenance=proof)
            after = encoded(meta).decode()
            updates.append((proof['url'], after, now(), row['id']))
            results.append({'sha256': sha, 'source_id': proof['source_id'], 'role': proof['role'],
                            'url': proof['url'], 'change': 'filled' if changed else 'unchanged',
                            'metadata_before_sha256': before_sha,
                            'metadata_after_sha256': hashlib.sha256(after.encode()).hexdigest() if changed else before_sha})
        if apply:
            archive = Path(data) / 'material-reviews/source-sidecars' / (sidecar_sha + '.json')
            try:
                atomic_write(archive, body, exclusive=True)
            except FileExistsError:
                if archive.is_symlink() or archive.read_bytes() != body:
                    raise ValueError('source_sidecar_archive_conflict')
            for update, result in zip(updates, results):
                if result['change'] == 'filled':
                    db.execute('UPDATE items SET url=?,metadata=?,updated=? WHERE id=?', update)
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()
    return {'schema': 'research-source-receipt-v1', 'batch': payload['batch'],
            'sidecar_sha256': sidecar_sha, 'mode': 'applied' if apply else 'plan',
            'sidecar_archive': str(archive) if apply else None,
            'processed': len(results), 'filled': sum(r['change'] == 'filled' for r in results),
            'unchanged': sum(r['change'] == 'unchanged' for r in results),
            'downloaded_originals': sum(r['role'] == 'downloaded_original' for r in results),
            'archived_tool_response_carriers': sum(r['role'] == 'decoded_archived_tool_response' for r in results),
            'received_at': now(), 'results': results,
            'scope': 'Source metadata only; no fetch, extraction, queue, matching, C3 or formal data changes.'}
