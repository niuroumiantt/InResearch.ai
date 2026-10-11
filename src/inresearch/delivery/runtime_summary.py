"""Rebuildable operational view of an intact, validated Reader snapshot.

This view carries candidate previews and measured counters, never adoption.
Management requests must not parse the entire candidate evidence library.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

from inresearch.storage.files import (CommitUncertain, iter_json_bytes, locked, make_directory,
                                     sync_directory, write_json_streaming)
from inresearch.storage.layout import workspace_path

SMALL_SNAPSHOT = 8 * 1024 * 1024
MAX_CONTROL = 64 * 1024 * 1024


def source_path(root):
    return Path(os.environ.get('INRESEARCH_READER_SNAPSHOT', workspace_path('data/research_runtime.json', root)))


def control_path(source):
    return source.parent / 'raw/research-runtime' / (source.stem.replace('_', '-') + '-control.json')


def prepared_control_path(source):
    path = control_path(source)
    return path.with_name(path.stem + '-prepared.json')


def signature(path):
    stat = path.stat()
    return dict(device=stat.st_dev, inode=stat.st_ino, size=stat.st_size, mtime_ns=stat.st_mtime_ns)


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def semantic_digest(value):
    digest = hashlib.sha256()
    comparable = {k: v for k, v in value.items() if k != 'received_at'}
    for chunk in iter_json_bytes(comparable, sort_keys=True):
        digest.update(chunk)
    return digest.hexdigest()


def physical_digest(value):
    digest = hashlib.sha256()
    for chunk in iter_json_bytes(value):
        digest.update(chunk)
    digest.update(b'\n')
    return digest.hexdigest()


def reading_deliveries(reader, matched):
    """Linear join; retain the existing per-document preview and coverage rules."""
    wanted = {r.get('sha256') for r in matched.get('records', [])}
    truncated = matched.get('truncated') is True
    documents = [d for d in reader.get('documents', []) if d.get('read_status') == 'complete'
                 and (truncated or d.get('content_sha256') in wanted)]
    ids = {d.get('doc_id') or d.get('id') for d in documents}
    claims, quotes = defaultdict(list), defaultdict(list)
    for row in reader.get('statements', []):
        key = row.get('document_id')
        if key in ids and len(claims[key]) < 6:
            claims[key].append(row.get('text', ''))
    for row in reader.get('evidence', []):
        key = row.get('document_id')
        if key in ids and len(quotes[key]) < 3:
            quotes[key].append({k: row.get(k) for k in ('quote', 'page_index')})
    return [{'title': d.get('title'), 'sha256': d['content_sha256'],
             'claims': claims[d.get('doc_id') or d.get('id')],
             'quotes': quotes[d.get('doc_id') or d.get('id')],
             'coverage': d.get('coverage') or {}, 'acceptance': 'candidate_only'} for d in documents]


def _control_value(source, snapshot, source_sha256=None, *, root):
    before = signature(source)
    acquisition = snapshot.get('reader', {}).get('acquisition')
    matched = (acquisition.get('material_matches') or {}) if isinstance(acquisition, dict) else {}
    value = dict(schema_version=1, authority='derived_candidate_operational_view',
                 source_signature=before, source_sha256=source_sha256 or digest_file(source),
                 semantic_sha256=semantic_digest(snapshot),
                 curated_sha256=digest_file(Path(root) / 'data/research_knowledge.json'),
                 graph_version=snapshot['graph_version'], questions_version=snapshot['questions_version'],
                 generated=snapshot['generated'], received_at=snapshot.get('received_at'),
                 reader=snapshot.get('reader', {}),
                 reading_deliveries=reading_deliveries(snapshot.get('knowledge', {}), matched))
    if signature(source) != before:
        raise ValueError('runtime_source_changed')
    return value


def write_control(source, snapshot, source_sha256=None, *, root):
    value = _control_value(source, snapshot, source_sha256, root=root)
    write_json_streaming(control_path(source), value)
    return value


def _read_control_at(source, path, *, verify_bytes=False):
    try:
        if source.is_symlink() or not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_CONTROL:
            return None
        before = signature(source)
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            return None
        if (value.get('schema_version') != 1 or value.get('authority') != 'derived_candidate_operational_view'
                or value.get('source_signature') != before
                or any(not re.fullmatch('[0-9a-f]{64}', value.get(k, '')) for k in ('source_sha256', 'semantic_sha256'))
                or not isinstance(value.get('reader'), dict) or not isinstance(value.get('reading_deliveries'), list)):
            return None
        if verify_bytes and digest_file(source) != value['source_sha256']:
            return None
        if signature(source) != before:
            return None
        return value
    except (OSError, ValueError, TypeError):
        return None


def read_control(source, *, verify_bytes=False):
    """Only a slot matching the current source inode may provide a projection.

    The prepared slot makes the source replacement itself the commit point:
    before it, the previous control matches; afterwards, the prepared control
    matches, including after a crash before its promotion. No timestamp or slot
    filename grants authority, and byte verification applies to either slot.
    """
    for _ in range(2):  # A promotion/replacement racing a read needs only a retry.
        for path in (control_path(source), prepared_control_path(source)):
            value = _read_control_at(source, path, verify_bytes=verify_bytes)
            if value is not None:
                return value
    return None


def recover_control(source):
    """Finish a committed installation, under the existing source writer lock."""
    if source.is_symlink() or control_path(source).is_symlink():
        raise ValueError('refuse_symlink_destination')
    if _read_control_at(source, control_path(source)) is not None:
        return
    prepared = prepared_control_path(source)
    if _read_control_at(source, prepared, verify_bytes=True) is not None:
        os.replace(prepared, control_path(source))
        try:
            sync_directory(prepared.parent)
        except OSError as exc:
            raise CommitUncertain() from exc


class SnapshotInstallFailed(OSError):
    """A complete staged candidate remains available for a safe retry."""


def install_snapshot(source, snapshot, *, root):
    """Build privately, then install a physically identified source/control pair.

    The caller holds locked(source). Long encoding, hashing and joins leave the
    old pair untouched. Complete staged files survive failures; they are never
    mistaken for active data. The prepared control is durable before switching
    the source, so a failed promotion remains readable and exactly replayable.
    """
    source = Path(source)
    recover_control(source)
    stage = Path(tempfile.mkdtemp(prefix='.' + source.name + '.stage-', dir=source.parent))
    sync_directory(source.parent)
    staged_source, staged_control = stage / 'source.json', stage / 'control.json'
    prepared = prepared_control_path(source)
    temporary = prepared.with_name('.' + prepared.name + '.tmp-' + uuid.uuid4().hex)
    installed = False
    complete = False
    try:
        source_sha = write_json_streaming(staged_source, snapshot)
        value = _control_value(staged_source, snapshot, source_sha, root=root)
        write_json_streaming(staged_control, value)
        if staged_control.stat().st_size > MAX_CONTROL:
            raise SnapshotInstallFailed(
                'snapshot control exceeds operational projection limit; snapshot not installed; '
                'previous projection retained; staged candidate retained')
        make_directory(prepared.parent)
        if prepared.is_symlink() or source.is_symlink() or control_path(source).is_symlink():
            raise ValueError('refuse_symlink_destination')
        if signature(staged_source) != value['source_signature']:
            raise ValueError('runtime_stage_changed')
        # A hard link keeps the complete staged control recoverable without a
        # second large encoding. Both files are on the source filesystem.
        os.link(staged_control, temporary)
        os.replace(temporary, prepared)
        try:
            sync_directory(prepared.parent)
        except OSError as exc:
            raise CommitUncertain() from exc
        os.replace(staged_source, source)
        installed = True
        try:
            sync_directory(source.parent)
        except OSError as exc:
            raise CommitUncertain() from exc
        os.replace(prepared, control_path(source))
        try:
            sync_directory(prepared.parent)
        except OSError as exc:
            raise CommitUncertain() from exc
        complete = True
        return value
    except (CommitUncertain, SnapshotInstallFailed):
        raise
    except OSError as exc:
        state = ('snapshot source installed; control promotion pending; retry exact snapshot'
                 if installed else 'snapshot not installed; previous projection retained; staged candidate retained')
        raise SnapshotInstallFailed(state) from exc
    finally:
        temporary.unlink(missing_ok=True)  # Only an extra link to staged_control.
        if complete:
            staged_control.unlink()  # Active control holds the same inode.
            stage.rmdir()


def load(root):
    """A missing large-file projection is explicit; never allocate a giant fallback."""
    from inresearch.knowledge import registry
    source = source_path(root)
    if source.exists():
        value = read_control(source)
        if value is not None and value.get('curated_sha256') == digest_file(Path(root) / 'data/research_knowledge.json'):
            return value
        if source.stat().st_size <= SMALL_SNAPSHOT:
            try:
                raw = registry.read_json(source)
                snapshot = registry.candidate_snapshot(raw,
                    registry.read_json(Path(root) / 'framework/research_graph.json'),
                    registry.read_json(Path(root) / 'framework/research_questions.json'))
                registry.merge_knowledge(registry.read_json(Path(root) / 'data/research_knowledge.json'), snapshot['knowledge'])
            except (ValueError, TypeError, KeyError, AttributeError, OSError):
                return dict(reader={'status': 'degraded'}, reading_deliveries=[], received_at=None)
            snapshot['received_at'] = raw.get('received_at')
            acquisition = snapshot['reader'].get('acquisition')
            matched = (acquisition.get('material_matches') or {}) if isinstance(acquisition, dict) else {}
            return dict(snapshot, knowledge={}, reading_deliveries=reading_deliveries(snapshot['knowledge'], matched))
        status = 'awaiting_operational_projection'
    else:
        status = 'not_connected'
    return dict(reader={'status': status, 'message': '候选原库保留；运行视图尚未生成或版本不一致。'},
                reading_deliveries=[], received_at=None)


def load_acquisition(root):
    """Read only physically current receiver metadata, independent of curated adoption.

    A later research commit does not invalidate received news. Missing or changed
    source/control files remain unknown; this endpoint never parses a giant library.
    """
    source=source_path(root)
    value=read_control(source) if source.is_file() else None
    if value is None:
        return dict(reader={'status':'awaiting_operational_projection' if source.exists() else 'not_connected'},received_at=None)
    reader=value['reader'];acquisition=reader.get('acquisition')
    if not isinstance(acquisition,dict):
        return dict(reader={'status':'degraded'},received_at=value.get('received_at'))
    clean={key:acquisition[key] for key in ('news_feed','project_pipeline','daily_delivery') if key in acquisition}
    return dict(received_at=value.get('received_at'),reader={'status':reader.get('status'),'acquisition':clean})


def read_header(source):
    """Read the writer's small metadata prefix, stopping before knowledge/reader."""
    if not source.exists():
        return {}
    with source.open(encoding='utf-8') as stream:
        prefix = stream.read(65536)
    decoder = json.JSONDecoder()
    pos = 0
    def spaces():
        nonlocal pos
        while pos < len(prefix) and prefix[pos].isspace():
            pos += 1
    spaces()
    if prefix[pos:pos+1] != '{':
        raise ValueError('runtime_header_invalid')
    pos += 1
    fields = {}
    while True:
        spaces()
        key, pos = decoder.raw_decode(prefix, pos)
        spaces()
        if prefix[pos:pos+1] != ':':
            raise ValueError('runtime_header_invalid')
        pos += 1
        spaces()
        if key in ('knowledge', 'reader'):
            break
        value, pos = decoder.raw_decode(prefix, pos)
        fields[key] = value
        spaces()
        if prefix[pos:pos+1] == '}':
            break
        if prefix[pos:pos+1] != ',':
            raise ValueError('runtime_header_invalid')
        pos += 1
    if not fields.get('generated'):
        raise ValueError('runtime_header_missing_generation')
    return fields


def main(argv=None):
    from inresearch.paths import project_root
    from inresearch.knowledge import registry
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', required=True)
    parser.parse_args(argv)
    root = project_root()
    source = source_path(root)
    with locked(source):
        raw = registry.read_json(source)
        snapshot = registry.candidate_snapshot(raw,
            registry.read_json(root / 'framework/research_graph.json'),
            registry.read_json(root / 'framework/research_questions.json'))
        registry.merge_knowledge(registry.read_json(root / 'data/research_knowledge.json'), snapshot['knowledge'])
        snapshot['received_at'] = raw.get('received_at')
        result = write_control(source, snapshot, root=root)
    print(json.dumps({'source_sha256': result['source_sha256'], 'reading_deliveries': len(result['reading_deliveries']),
                      'control_bytes': control_path(source).stat().st_size, 'adoption': 'unchanged'}))
    return 0
