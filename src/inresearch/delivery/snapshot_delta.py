"""Bounded candidate deltas over the existing authenticated snapshot endpoint.

Absent documents are retained. Each atomic batch uses the previous generated
version as CAS; retries rediscover hashes, so partial progress is recoverable.
This transport never promotes candidates or changes ordinary source intake.
"""
import copy
import hashlib
import json
import re
from datetime import datetime, timezone

COLLECTIONS = ('documents', 'evidence', 'statements', 'answers')
MAX_DOCUMENTS = 250
MAX_DELTA_BYTES = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 32 * 1024 * 1024


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pieces(knowledge):
    result = {d['id']: {k: [] for k in COLLECTIONS} for d in knowledge['documents']}
    for d in knowledge['documents']:
        result[d['id']]['documents'].append(d)
    for kind in ('evidence', 'statements'):
        for row in knowledge[kind]:
            if row.get('document_id') not in result:
                raise ValueError('candidate delta has orphan rows')
            result[row['document_id']][kind].append(row)
    # Formal/candidate answers have cross-document support and must use the
    # unchanged full-snapshot path, not a document-local replacement.
    if knowledge.get('answers'):
        raise ValueError('candidate answer deltas require an explicit support-closure protocol')
    return result


def hashes(knowledge):
    return {ident: hashlib.sha256(encoded(part)).hexdigest()
            for ident, part in pieces(knowledge).items()}


def manifest(snapshot):
    result = {'ok': True, 'protocol': 'candidate-delta-v1',
              'base_generated': snapshot.get('generated'),
              'document_hashes': hashes(snapshot.get('knowledge', {k: [] for k in COLLECTIONS}))}
    if len(encoded(result)) > MAX_MANIFEST_BYTES:
        raise ValueError('candidate manifest exceeds bounded response limit')
    return result


def batches(snapshot, remote):
    if (not isinstance(remote, dict) or remote.get('protocol') != 'candidate-delta-v1'
            or not isinstance(remote.get('document_hashes'), dict)
            or any(not isinstance(k, str) or not isinstance(v, str)
                   or not re.fullmatch('[0-9a-f]{64}', v)
                   for k, v in remote['document_hashes'].items())):
        raise ValueError('receiver does not support candidate-delta-v1')
    grouped = pieces(snapshot['knowledge'])
    changed = [i for i, h in hashes(snapshot['knowledge']).items()
               if remote['document_hashes'].get(i) != h]
    current = []
    size = 0
    for ident in changed:
        part_size = len(encoded(grouped[ident]))
        # Leave room for all Reader status metadata and envelope fields.
        overhead = len(encoded({k: v for k, v in snapshot.items() if k != 'knowledge'})) + 4096
        if part_size + overhead > MAX_DELTA_BYTES:
            raise ValueError('single candidate document exceeds delta limit; original retained')
        if current and (len(current) >= MAX_DOCUMENTS or size + part_size + overhead > MAX_DELTA_BYTES):
            yield current, grouped
            current, size = [], 0
        current.append(ident); size += part_size
    if current or not changed:
        yield current, grouped


def envelope(snapshot, ids, grouped, base_generated):
    partial = {k: copy.deepcopy(v) for k, v in snapshot.items() if k not in ('knowledge', 'received_at')}
    partial['generated'] = datetime.now(timezone.utc).isoformat()
    partial['knowledge'] = {k: [row for ident in ids for row in grouped[ident][k]] for k in COLLECTIONS}
    result = {'operation': 'candidate-delta-v1', 'base_generated': base_generated,
              'document_ids': ids, 'snapshot': partial}
    if len(encoded(result)) > MAX_DELTA_BYTES:
        raise ValueError('candidate delta exceeds bounded request limit')
    return result


def merge(previous, delta):
    if (set(delta) != {'operation', 'base_generated', 'document_ids', 'snapshot'}
            or delta['operation'] != 'candidate-delta-v1'
            or len(encoded(delta)) > MAX_DELTA_BYTES):
        raise ValueError('invalid candidate delta envelope')
    if delta['base_generated'] != previous.get('generated'):
        raise ValueError('candidate delta base changed; refresh manifest before retry')
    ids = delta['document_ids']
    if (not isinstance(ids, list) or len(ids) > MAX_DOCUMENTS
            or any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids)):
        raise ValueError('invalid candidate delta document set')
    incoming = delta['snapshot']
    if not isinstance(incoming, dict) or not isinstance(incoming.get('knowledge'), dict):
        raise ValueError('candidate delta snapshot required')
    grouped = pieces(incoming['knowledge'])
    if set(grouped) != set(ids):
        raise ValueError('candidate delta document set mismatch')
    old = previous.get('knowledge', {k: [] for k in COLLECTIONS})
    if old.get('answers'):
        raise ValueError('candidate answer deltas require an explicit support-closure protocol')
    result = copy.deepcopy(incoming)
    selected = set(ids)
    result['knowledge'] = {}
    for kind in COLLECTIONS:
        key = 'id' if kind == 'documents' else 'document_id'
        result['knowledge'][kind] = ([r for r in old.get(kind, []) if r.get(key) not in selected]
                                     + incoming['knowledge'].get(kind, []))
    return result
