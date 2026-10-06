"""Bind private editorial source sidecars to exact daily-document bytes."""
import hashlib
import json
import re
from pathlib import Path
from inresearch.adapters.news_sync import public_url


def load(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 5*1024*1024:
        raise ValueError('invalid_daily_sources_file')
    raw = path.read_bytes()
    value = json.loads(raw)
    if isinstance(value, dict) and 'sources' in value:
        value = value['sources']
    rows = list(value.items()) if isinstance(value, dict) else list(enumerate(value)) if isinstance(value, list) else []
    if not rows or len(rows) > 500:
        raise ValueError('unsupported_daily_sources')
    result = {}
    for key, row in rows:
        if not isinstance(row, dict):
            continue
        ident = row.get('id', row.get('n'))
        if ident is None and isinstance(key, str) and re.fullmatch(r'\[?\d+\]?', key):
            ident = key
        match = re.fullmatch(r'\[?(\d+)\]?', str(ident))
        if not match:
            continue  # Never infer a citation number from list position.
        ident = str(int(match[1]))
        urls = row.get('urls', [])
        if not isinstance(urls, list):
            raise ValueError('invalid_daily_source_urls')
        urls = urls + [row[k] for k in ('url', 'primary') if isinstance(row.get(k), str)]
        if len(urls) > 30 or any(not public_url(u) for u in urls):
            raise ValueError('invalid_daily_source_url')
        label = next((row[k] for k in ('name', 'publisher', 'outlet', 'source', 'institution', 'title', 'event')
                      if isinstance(row.get(k), str)), '来源 '+ident)
        source = result.setdefault(ident, {'reference_id': ident, 'label': label[:1200], 'urls': [],
                                           'source_sha256': hashlib.sha256(raw).hexdigest(),
                                           'source_locator': 'sources.json#'+ident,
                                           'evidence_scope': str(row.get('evidence_scope', row.get('scope', row.get('read', ''))))[:2000]})
        source['urls'] = list(dict.fromkeys(source['urls'] + urls))
    if not result:
        raise ValueError('unsupported_daily_sources')
    return result


def attach(events, sources):
    for event in events:
        # Citation identifiers, not publisher/name similarity, authorize a link.
        ids = {a or b for a, b in re.findall(r'\[(\d+)\]|【(\d+)】', event['title']+'\n'+event['body'])}
        for ident in sorted(ids, key=int):
            if ident in sources and sources[ident] not in event['sources']:
                event['sources'].append({**sources[ident], 'document_sha256':event['document_refs'][0]['sha256']})
    return events
