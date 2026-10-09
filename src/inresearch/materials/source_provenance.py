"""Validate supplier-only SHA source bindings without granting evidence authority."""
import re
from urllib.parse import urlsplit


def source_url(value):
    if not isinstance(value, str) or len(value) > 4096 or re.search(r'\s|[\x00-\x1f\x7f]', value):
        raise ValueError('invalid_source_url')
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError as exc:
        raise ValueError('invalid_source_url') from exc
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('invalid_source_url')
    return value


def validate(value, content_sha256, url):
    fields = {'method', 'sidecar_sha256', 'batch', 'source_id', 'role', 'input_sha256',
              'url', 'url_verification', 'original_bytes_sha256'}
    if not isinstance(value, dict):
        raise ValueError('invalid_source_provenance')
    role = value.get('role')
    if role == 'decoded_archived_tool_response':
        fields.update(('response_sha256', 'derivation'))
    elif role != 'downloaded_original':
        raise ValueError('invalid_source_provenance')
    if set(value) != fields or value.get('method') != 'supplied_sidecar_sha_binding_v1' or value.get('url_verification') != 'supplier_metadata_only_no_fetch':
        raise ValueError('invalid_source_provenance')
    for key in ('input_sha256', 'sidecar_sha256'):
        if not isinstance(value[key], str) or not re.fullmatch(r'[0-9a-f]{64}', value[key]):
            raise ValueError('invalid_source_provenance')
    if value['input_sha256'] != content_sha256 or source_url(value['url']) != url:
        raise ValueError('invalid_source_provenance')
    for key in ('batch', 'source_id'):
        if not isinstance(value[key], str) or not 1 <= len(value[key]) <= 160:
            raise ValueError('invalid_source_provenance')
    if role == 'downloaded_original':
        if value['original_bytes_sha256'] != content_sha256:
            raise ValueError('invalid_source_provenance')
    elif (value['original_bytes_sha256'] is not None
          or not isinstance(value['response_sha256'], str)
          or not re.fullmatch(r'[0-9a-f]{64}', value['response_sha256'])
          or not isinstance(value['derivation'], str) or not 1 <= len(value['derivation']) <= 4096):
        raise ValueError('invalid_source_provenance')
    return dict(value)
