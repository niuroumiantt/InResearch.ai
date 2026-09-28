"""Add readings finished on another trusted worker to Spark's published snapshot.

The site receiver replaces its whole candidate projection on every publish, and
Spark publishes every five minutes, so a snapshot sent from M4 alone is gone at
the next Spark run. Instead M4 exports a scoped candidate snapshot (``reader
export --dest x.json --doc-id ...``) and places it in Spark's external snapshot
directory; every Spark publish then overlays those documents. Spark's own
complete reading of a document always wins. Nothing here writes the catalog.
"""
from __future__ import annotations

import json
import stat
from pathlib import Path

KINDS = ("evidence", "statements")


def validate_external(payload, overlay=True):
    """The checks every externally produced snapshot must pass before publishing.

    A relayed snapshot (``publish --snapshot``) keeps its original checks; one that
    is overlaid on Spark's must also key every row to one of its documents."""
    if not isinstance(payload, dict) or not isinstance(payload.get('knowledge'), dict):
        raise ValueError('candidate snapshot is not a Reader snapshot')
    knowledge = payload['knowledge']
    documents = knowledge.get('documents')
    if (not isinstance(documents, list) or not documents
            or any(not isinstance(doc, dict) or not isinstance(doc.get('coverage'), dict)
                   or doc['coverage'].get('complete') is not True
                   for doc in documents)):
        raise ValueError('external snapshot requires complete reading coverage for every document')
    if any(row.get('acceptance') != 'candidate' for rows in knowledge.values()
           if isinstance(rows, list) for row in rows if isinstance(row, dict)):
        raise ValueError('external snapshot may contain candidates only')
    if not overlay:
        return payload
    ids = {doc.get('doc_id') for doc in documents}
    if None in ids or len(ids) != len(documents):
        raise ValueError('external snapshot documents need unique doc_id values')
    for kind in KINDS:
        rows = knowledge.get(kind, [])
        if not isinstance(rows, list) or any(not isinstance(r, dict) or r.get('document_id') not in ids for r in rows):
            raise ValueError('external snapshot %s must belong to its documents' % kind)
    return payload


def load_directory(directory):
    """Validated external snapshots, oldest first; a newer one wins for the same document."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    snapshots = []
    for path in sorted(directory.glob('*.json')):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 64 * 1024 * 1024:
            raise ValueError('external snapshot must be a regular file within the receiver limit: ' + path.name)
        payload = validate_external(json.loads(path.read_text(encoding='utf-8')))
        snapshots.append((str(payload.get('generated', '')), path.name, payload))
    return [(name, payload) for _, name, payload in sorted(snapshots)]


def overlay(payload, snapshots):
    """Merge external documents into ``payload`` in place and say what happened."""
    knowledge = payload['knowledge']
    own_complete = {doc['doc_id'] for doc in knowledge['documents']
                    if doc.get('coverage', {}).get('complete') is True}
    added, kept_own = {}, set()
    for name, snapshot in snapshots:
        external = snapshot['knowledge']
        for entry in external['documents']:
            doc_id = entry['doc_id']
            if doc_id in own_complete:
                kept_own.add(doc_id)
                continue
            knowledge['documents'] = [d for d in knowledge['documents'] if d.get('doc_id') != doc_id]
            for kind in KINDS:
                knowledge[kind] = [r for r in knowledge.get(kind, []) if r.get('document_id') != doc_id]
            knowledge['documents'].append({**entry, 'projection_source': 'external:' + name})
            for kind in KINDS:
                knowledge.setdefault(kind, []).extend(r for r in external.get(kind, []) if r['document_id'] == doc_id)
            added[doc_id] = name
    return {'added': len(added), 'kept_spark_reading': len(kept_own),
            'files': sorted({name for name, _ in snapshots})}
