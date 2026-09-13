"""Published visual inputs: content identity, reviewed use and read-only projections.

The manifest is the commit point. Downloading creates a candidate; only a
reviewed source change can adopt it. These decisions are not research evidence.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from urllib.parse import urlsplit

from inresearch.paths import project_root

MAX_BYTES = 10 * 1024 * 1024
PAGES = {'bom3d', 'rack3d'}
FILENAME = re.compile(r'[a-z0-9][a-z0-9_.-]{0,79}\.glb\Z')


def permitted_license(label):
    """Check the project's declared license labels, not independent legal review."""
    return (isinstance(label, str)
            and re.search(r'CC0|Public Domain|CC Attribution|CC-BY', label, re.I)
            and not re.search(r'NonCommercial|NoDeriv|\bNC\b|\bND\b', label, re.I))


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def validate_entry(entry):
    if not isinstance(entry, dict) or not FILENAME.fullmatch(str(entry.get('file', ''))):
        raise ValueError('invalid_model_filename')
    if entry.get('page') not in PAGES or entry.get('status') not in {'candidate', 'adopted', 'rejected'}:
        raise ValueError('invalid_model_page_or_status')
    if not re.fullmatch(r'[a-f0-9]{64}', str(entry.get('sha256', ''))):
        raise ValueError('model_content_identity_required')
    source = urlsplit(str(entry.get('source', '')))
    if source.scheme not in {'https', 'http'} or not source.hostname or not permitted_license(entry.get('license')):
        raise ValueError('model_source_and_permitted_license_required')
    if entry['status'] != 'candidate' and (not isinstance(entry.get('decision'), str) or not entry['decision'].strip()):
        raise ValueError('model_decision_required')
    scale = entry.get('scale')
    if scale is not None and scale != 'auto' and not _positive(scale):
        raise ValueError('model_scale_must_be_positive_finite')
    if 'fitHeight' in entry and not _positive(entry['fitHeight']):
        raise ValueError('model_height_must_be_positive_finite')
    rotation = entry.get('rotationY', 0)
    if type(rotation) not in (int, float) or not math.isfinite(rotation):
        raise ValueError('invalid_model_rotation')
    position = entry.get('position', [0, 0, 0])
    if (not isinstance(position, list) or len(position) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in position)):
        raise ValueError('invalid_model_position')
    if type(entry.get('hideRack', False)) is not bool or (entry.get('hideRack') and entry['page'] != 'rack3d'):
        raise ValueError('invalid_model_rack_replacement')


def validate_glb(data):
    if not 20 <= len(data) <= MAX_BYTES or data[:4] != b'glTF':
        raise ValueError('model_requires_glb_up_to_10MiB')
    version, length = struct.unpack_from('<II', data, 4)
    if version != 2 or length != len(data):
        raise ValueError('invalid_glb_version_or_length')
    offset, chunks = 12, []
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError('truncated_glb_chunk')
        size, kind = struct.unpack_from('<I4s', data, offset)
        offset += 8
        if size % 4 or offset + size > len(data):
            raise ValueError('invalid_glb_chunk_length')
        chunks.append((kind, data[offset:offset + size]))
        offset += size
    if not chunks or chunks[0][0] != b'JSON':
        raise ValueError('glb_json_required')
    document = json.loads(chunks[0][1])
    if (not isinstance(document, dict) or not isinstance(document.get('asset'), dict)
            or document['asset'].get('version') != '2.0'):
        raise ValueError('glb_asset_version_required')
    # A self-contained GLB must not cause the browser to fetch undeclared files.
    collections = [document.get(key, []) for key in ('buffers', 'images')]
    if any(not isinstance(items, list) or any(not isinstance(item, dict) for item in items) for items in collections):
        raise ValueError('invalid_glb_resources')
    for item in collections[0] + collections[1]:
        uri = item.get('uri', '')
        if not isinstance(uri, str) or (uri and not uri.startswith('data:')):
            raise ValueError('external_glb_resource_forbidden')
    return hashlib.sha256(data).hexdigest()


def model_directory(root=None):
    directory = Path(root or project_root()).resolve() / 'web/assets/models'
    if directory.resolve() != directory:
        raise ValueError('unsafe_model_directory')
    return directory


def read_manifest(root=None, *, verify_files=False):
    directory = model_directory(root)
    document = json.loads((directory / 'manifest.json').read_text())
    if (not isinstance(document, dict) or type(document.get('schema_version')) is not int
            or document['schema_version'] != 1 or not isinstance(document.get('models'), list)):
        raise ValueError('unsupported_model_manifest')
    seen = set()
    for entry in document['models']:
        validate_entry(entry)
        if entry['file'] in seen:
            raise ValueError('duplicate_model_filename')
        seen.add(entry['file'])
        path = directory / entry['file']
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ValueError('missing_unsafe_or_oversized_model')
        if verify_files and validate_glb(path.read_bytes()) != entry['sha256']:
            raise ValueError('model_content_changed_without_review')
    return document


def snapshot(root=None, page=None):
    if page is not None and page not in PAGES:
        raise ValueError('invalid_scene_page')
    manifest = read_manifest(root)
    models = [dict(entry, url='/assets/models/' + entry['file']) for entry in manifest['models']
              if page is None or (entry['page'] == page and entry['status'] == 'adopted')]
    revision = hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'schema_version': 1, 'revision': revision, 'models': models}

