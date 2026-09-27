"""Candidate-only progress projection for the M5 NVIDIA pilot."""
import json
import os
from pathlib import Path

from inresearch.storage.files import locked, write_json
from inresearch.storage.layout import workspace_path
from inresearch.knowledge import registry


def path(root):
    configured = os.environ.get('INRESEARCH_NVIDIA_PILOT_PROGRESS')
    return Path(configured).expanduser() if configured else workspace_path(
        'data/raw/pilot-progress/nvidia.json', root)


def token_path(root):
    configured = os.environ.get('INRESEARCH_PILOT_TOKEN_FILE')
    if configured:
        return Path(configured).expanduser()
    runtime = os.environ.get('INRESEARCH_RUNTIME_ROOT')
    if runtime:
        return Path(runtime).expanduser() / 'data/.nvidia_pilot_token'
    return workspace_path('data/.nvidia_pilot_token', root)


def receive(root, payload):
    """Validate a bounded status + candidate snapshot before storing separately."""
    if not isinstance(payload, dict) or payload.get('schema_version') != 1:
        raise ValueError('unsupported pilot progress schema')
    status = payload.get('status')
    snapshot = payload.get('snapshot')
    if not isinstance(status, dict) or not isinstance(snapshot, dict):
        raise ValueError('status and snapshot are required')
    if status.get('acceptance') != 'candidate_only' or status.get('backend', {}).get('backend') != 'claude_cli':
        raise ValueError('M5 Claude candidate status required')
    counts = status.get('counts')
    if not isinstance(counts, dict) or any(type(counts.get(k)) is not int or counts[k] < 0
        for k in ('complete', 'blocked', 'failed')):
        raise ValueError('invalid progress counts')
    knowledge = snapshot.get('knowledge')
    documents = knowledge.get('documents') if isinstance(knowledge, dict) else None
    if not isinstance(documents, list) or not documents:
        raise ValueError('candidate snapshot documents required')
    normalized = registry.candidate_snapshot(snapshot,
        registry.read_json(Path(root) / 'framework/research_graph.json'),
        registry.read_json(Path(root) / 'framework/research_questions.json'))
    if any(doc.get('coverage', {}).get('complete') is not True for doc in normalized['knowledge']['documents']):
        raise ValueError('pilot snapshot only accepts complete reading candidates')
    result = {'schema_version': 1, 'project': 'nvidia', 'source': 'm5_claude_cli',
        'acceptance': 'candidate_only', 'status': status,
        'snapshot': normalized, 'received_at': payload.get('received_at')}
    target = path(Path(root))
    with locked(target):
        previous = {}
        if target.exists():
            previous = json.loads(target.read_text(encoding='utf-8'))
        old_generated = previous.get('status', {}).get('generated', '')
        new_generated = status.get('generated', '')
        if not isinstance(new_generated, str) or not new_generated:
            raise ValueError('status generated timestamp required')
        if old_generated and new_generated <= old_generated:
            raise ValueError('stale or repeated pilot progress')
        write_json(target, result)
    return {'ok': True, 'received_at': result['received_at'],
        'documents': len(normalized['knowledge']['documents']), 'status_generated': new_generated}


def public_snapshot(root):
    target = path(Path(root))
    if not target.is_file() or target.is_symlink():
        return {'available': False, 'project': 'nvidia', 'acceptance': 'candidate_only'}
    value = json.loads(target.read_text(encoding='utf-8'))
    status = value['status']
    docs = value['snapshot']['knowledge']['documents']
    # Deliberately expose summaries only; candidate evidence remains in /api/research.
    return {'available': True, 'project': 'nvidia', 'source': value['source'],
        'acceptance': 'candidate_only', 'generated': status.get('generated'),
        'counts': status.get('counts', {}), 'documents_total': status.get('documents_total'),
        'documents': [{'id': d.get('id'), 'title': d.get('title'),
            'coverage': d.get('coverage')}
            for d in docs], 'received_at': value.get('received_at')}
