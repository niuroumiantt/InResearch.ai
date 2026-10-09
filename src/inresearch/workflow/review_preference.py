"""Validated, explicit source preference; it never makes an unfinished report eligible."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

MAX_SOURCES = 1000
MAX_BYTES = 1024 * 1024


@dataclass(frozen=True)
class PreferredSources:
    sha256: str
    doc_ids: tuple
    eligible_keys: tuple


def load_preferred_sources(path, data):
    """Read exact bytes, reject unknown identities, retain the current complete version only."""
    path = Path(path).expanduser()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError('invalid_preferred_source_file')
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('preferred_source_file_too_large')
    value = json.loads(raw)
    ids = value.get('doc_ids') if isinstance(value, dict) else None
    if (not isinstance(value, dict) or set(value) != {'schema_version', 'doc_ids'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or not isinstance(ids, list) or not 1 <= len(ids) <= MAX_SOURCES
            or any(not isinstance(i, str) or not re.fullmatch(r'doc-[0-9a-f]{64}', i) for i in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError('invalid_preferred_source_scope')
    database = (Path(data).resolve() / 'catalog/catalog.sqlite').as_uri() + '?mode=ro'
    conn = sqlite3.connect(database, uri=True, timeout=5)
    try:
        registered = {row[0] for row in conn.execute(
            'SELECT doc_id FROM documents WHERE doc_id IN (SELECT value FROM json_each(?))',
            (json.dumps(ids),))}
        if set(ids) != registered:
            raise ValueError('preferred_source_not_registered')
        keys = tuple('/'.join(row) for row in conn.execute(
            "SELECT doc_id,revision_id,report_sha256 FROM current_readings WHERE state='complete' "
            "AND report_sha256 IS NOT NULL AND manifest_sha256 IS NOT NULL "
            "AND doc_id IN (SELECT value FROM json_each(?))", (json.dumps(ids),)))
    finally:
        conn.close()
    return PreferredSources(hashlib.sha256(raw).hexdigest(), tuple(ids), keys)
