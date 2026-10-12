"""Read-only worked examples from private runtime packages.

The producer installs immutable source bytes and real receipts. This projection
does not collect, receive, register, publish or certify research. Every download
is selected by an artifact ID and checked against the installed allowlist;
anonymous access additionally requires an explicit public artifact grant.
"""
import hashlib
import json
import math
import os
from pathlib import PurePosixPath
import re
import stat
from urllib.parse import quote, urlsplit

from inresearch.storage.layout import workspace_path

EXAMPLE_IDS = ('equinix-sg3-20261012',)
PREFIX = 'data/raw/research-task-examples'
API = '/api/research-task-examples'
MAX_METADATA = 4 * 1024 * 1024
MAX_ARTIFACT = 128 * 1024 * 1024
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z')
STATES = ('complete', 'pending', 'blocked', 'not_applicable')


class NotInstalled(FileNotFoundError):
    pass


class ArtifactUnavailable(ValueError):
    pass


class PrivateArtifact(PermissionError):
    pass


def _text(value, *, optional=False, limit=4000):
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('invalid_example_text')
    return value


def _id(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('invalid_example_id')
    return value


def _parts(relative):
    if (not isinstance(relative, str) or '\\' in relative
            or PurePosixPath(relative).is_absolute()
            or any(not p or p.startswith('.') for p in relative.split('/'))):
        raise ValueError('invalid_example_artifact_path')
    return relative.split('/')


def _read_file(root, sample_id, relative, limit):
    """Walk all components with O_NOFOLLOW and freeze verified response bytes."""
    if sample_id not in EXAMPLE_IDS:
        raise NotInstalled('example_not_installed')
    base = workspace_path(PREFIX, root)
    parts = list(base.parts[1:]) + [sample_id] + _parts(relative)
    fd = os.open(base.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = next_fd
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(leaf)
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise ArtifactUnavailable('example_artifact_invalid')
            with os.fdopen(leaf, 'rb', closefd=False) as stream:
                body = stream.read(limit + 1)
            after = os.fstat(leaf)
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if len(body) > limit or identity(before) != identity(after):
                raise ArtifactUnavailable('example_artifact_changed')
            return body
        finally:
            os.close(leaf)
    finally:
        os.close(fd)


def _unique(rows, name):
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError('invalid_example_' + name)
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid_example_' + name)
        ident = _id(row.get('id'))
        if ident in result:
            raise ValueError('duplicate_example_' + name)
        result[ident] = row
    return result


def _link(value, *, external=False):
    if value is None:
        return None
    _text(value, limit=2000)
    parsed = urlsplit(value)
    if external:
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('invalid_example_source_url')
    elif (parsed.scheme or parsed.netloc or parsed.path not in ('/project.html', '/industry.html')
          or '\\' in value or any(ord(c) < 32 for c in value)):
        raise ValueError('invalid_example_site_link')
    return value


def _load(root, sample_id):
    try:
        body = _read_file(root, sample_id, 'example.json', MAX_METADATA)
    except FileNotFoundError:
        raise NotInstalled('example_not_installed') from None
    def pairs(values):
        row = {}
        for key, value in values:
            if key in row:
                raise ValueError('duplicate_example_key')
            row[key] = value
        return row
    value = json.loads(body, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid_example_number')))
    if not isinstance(value, dict) or value.get('version') != 1 or value.get('id') != sample_id:
        raise ValueError('invalid_example_manifest')
    for field in ('name', 'site_id', 'status'):
        _text(value.get(field), limit=300)
    _text(value.get('processed_at'), optional=True, limit=100)
    execution = value.get('execution', {})
    if not isinstance(execution, dict):
        raise ValueError('invalid_example_execution')
    for field in ('machine', 'model', 'actor', 'reading_scope'):
        _text(execution.get(field), optional=True, limit=500)
    artifacts = _unique(value.get('artifacts'), 'artifacts')
    for row in artifacts.values():
        _parts(row.get('path'))
        if (not isinstance(row.get('sha256'), str) or not re.fullmatch('[a-f0-9]{64}', row['sha256'])
                or type(row.get('size')) is not int or not 0 <= row['size'] <= MAX_ARTIFACT):
            raise ValueError('invalid_example_artifact_identity')
        filename = _text(row.get('filename'), limit=180)
        if any(c in filename for c in '/\\\r\n') or any(ord(c) < 32 for c in filename):
            raise ValueError('invalid_example_filename')
        if row.get('access_scope', 'private') not in ('public', 'private'):
            raise ValueError('invalid_example_artifact_access')
    sources = _unique(value.get('sources'), 'sources')
    for row in sources.values():
        _text(row.get('title'), limit=500); _link(row.get('url'), external=True)
        _text(row.get('locator'), optional=True)
        if row.get('artifact_id') is not None and row['artifact_id'] not in artifacts:
            raise ValueError('unknown_example_source_artifact')
    for row in _unique(value.get('facts'), 'facts').values():
        _text(row.get('label'), limit=300)
        actual = row.get('value')
        if (actual is not None and not isinstance(actual, str)
                and (type(actual) not in (int, float) or not math.isfinite(actual))):
            raise ValueError('invalid_example_fact')
        if isinstance(actual, str):
            _text(actual)
        _text(row.get('unit'), optional=True, limit=100)
        _text(row.get('locator'), optional=True)
        if not isinstance(row.get('source_ids'), list) or any(s not in sources for s in row['source_ids']):
            raise ValueError('unknown_example_fact_source')
    for row in _unique(value.get('unknowns'), 'unknowns').values():
        for field in ('label', 'reason', 'next_action'):
            _text(row.get(field))
    for row in _unique(value.get('stages'), 'stages').values():
        _text(row.get('title'), limit=300); _text(row.get('result'))
        if row.get('state') not in STATES or not isinstance(row.get('artifact_ids'), list):
            raise ValueError('invalid_example_stage')
        if any(a not in artifacts for a in row['artifact_ids']):
            raise ValueError('unknown_example_stage_artifact')
    if not isinstance(value.get('links'), dict):
        raise ValueError('invalid_example_links')
    for key in ('project', 'map'):
        _link(value['links'].get(key))
    return value


def _artifact_body(root, sample_id, artifact):
    try:
        body = _read_file(root, sample_id, artifact['path'], MAX_ARTIFACT)
    except (ValueError, OSError):
        raise ArtifactUnavailable('example_artifact_unavailable') from None
    if len(body) != artifact['size'] or hashlib.sha256(body).hexdigest() != artifact['sha256']:
        raise ArtifactUnavailable('example_artifact_changed')
    return body


def snapshot(root, *, authenticated=False):
    examples = []
    for sample_id in EXAMPLE_IDS:
        try:
            value = _load(root, sample_id)
        except NotInstalled:
            continue
        # Publish an explicit projection: local paths and extra producer metadata
        # never become browser metadata just because they occur in a manifest.
        result = {k: value[k] for k in ('version', 'id', 'name', 'site_id', 'status')}
        result['processed_at'] = value.get('processed_at')
        result['execution'] = {k: value.get('execution', {}).get(k) if authenticated or k == 'reading_scope' else None
                               for k in ('machine', 'model', 'actor', 'reading_scope')}
        for name, keys in (('sources', ('id', 'title', 'url', 'artifact_id', 'locator')),
                           ('facts', ('id', 'label', 'value', 'unit', 'source_ids', 'locator')),
                           ('unknowns', ('id', 'label', 'reason', 'next_action')),
                           ('stages', ('id', 'title', 'state', 'result', 'artifact_ids'))):
            result[name] = [{k: row.get(k) for k in keys} for row in value[name]]
        result['links'] = {k: value['links'].get(k) for k in ('project', 'map')}
        result['artifacts'] = []
        for artifact in value['artifacts']:
            access_scope = artifact.get('access_scope', 'private')
            if not authenticated and access_scope != 'public':
                continue
            item = {k: artifact[k] for k in ('id', 'sha256', 'size', 'filename')}
            item['access_scope'] = access_scope
            try:
                _artifact_body(root, sample_id, artifact)
                item.update(available=True, download_url=API + '/' + quote(sample_id) + '/files/' + quote(artifact['id']))
            except ArtifactUnavailable:
                item.update(available=False, download_url=None)
            result['artifacts'].append(item)
        allowed_artifacts = {a['id'] for a in result['artifacts']}
        for source in result['sources']:
            if source['artifact_id'] not in allowed_artifacts:
                source['artifact_id'] = None
        for stage in result['stages']:
            stage['artifact_ids'] = [a for a in stage['artifact_ids'] if a in allowed_artifacts]
        examples.append(result)
    return {'version': 1, 'status': 'available' if examples else 'not_installed',
            'authenticated': authenticated, 'examples': examples}


def download(root, sample_id, artifact_id, *, authenticated=False):
    _id(sample_id); _id(artifact_id)
    value = _load(root, sample_id)
    artifact = next((a for a in value['artifacts'] if a['id'] == artifact_id), None)
    if artifact is None:
        raise NotInstalled('example_artifact_not_registered')
    if not authenticated and artifact.get('access_scope', 'private') != 'public':
        raise PrivateArtifact('example_artifact_requires_login')
    return {'body': _artifact_body(root, sample_id, artifact),
            'filename': artifact['filename'], 'sha256': artifact['sha256']}
