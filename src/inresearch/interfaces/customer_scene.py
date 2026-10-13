"""Exact, adopted visual-asset delivery; internal reviews never define customer grants."""
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from inresearch.materials import model_assets as authority


def model_assets(root, page):
    """Only a selected scene and separately granted, reviewed model bytes may leave."""
    if page not in authority.PAGES:
        raise ValueError('One delivery scene is required')
    root = Path(root)
    grants = json.loads((root / 'framework/site_navigation.json').read_text())['access']['customer']['assets']
    manifest = authority.read_manifest(root)
    result = []
    keys = ('file', 'page', 'status', 'sha256', 'source', 'license', 'scale', 'fitHeight', 'rotationY', 'hideRack')
    for row in manifest['models']:
        url = '/assets/models/' + row['file']
        if row['status'] != 'adopted' or row['page'] != page or url not in grants:
            continue
        source = urlsplit(row['source'])
        credential_keys = {'token', 'access_token', 'api_key', 'password', 'secret', 'authorization'}
        if (source.username or source.password or
                credential_keys.intersection(key.casefold() for key in parse_qs(source.query))):
            raise ValueError('Model source attribution contains credentials')
        data = (authority.model_directory(root) / row['file']).read_bytes()
        if authority.validate_glb(data) != row['sha256']:
            raise ValueError('Reviewed model content identity changed')
        item = {key: row[key] for key in keys if key in row and
                (row[key] is None or isinstance(row[key], (str, int, float, bool)))}
        item['url'] = url
        if 'position' in row:
            item['position'] = list(row['position'])  # authority validates three finite numbers.
        result.append(item)
    published = {'schema_version': 1, 'models': result}
    revision = hashlib.sha256(json.dumps(published, ensure_ascii=False, sort_keys=True,
                                        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return {**published, 'revision': revision}
