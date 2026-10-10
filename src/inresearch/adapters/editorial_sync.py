"""Receive authored research, separately from the originals it references."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, urlopen

from inresearch.adapters.acquisition import Collector, now
from inresearch.storage.files import locked, write_json
from inresearch.workflow.research_match import ingest

MAX_BYTES = 4 * 1024 * 1024


def digest(body):
    return hashlib.sha256(body).hexdigest()


def http_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('invalid_editorial_url')
    if re.search(r'\s|[\x00-\x1f\x7f]', value): raise ValueError('invalid_editorial_url')
    u = urlsplit(value)
    u.port
    if u.scheme not in ('https', 'http') or not u.hostname or u.username or u.password:
        raise ValueError('invalid_editorial_url')
    return value


def validate(item):
    if not isinstance(item, dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', item.get('id', '')):
        raise ValueError('invalid_editorial_identity')
    if item.get('source_role') != 'authored_analysis':
        raise ValueError('editorial_is_not_primary_evidence')
    if not isinstance(item.get('title'), str) or not 1 <= len(item['title']) <= 1000:
        raise ValueError('invalid_editorial_title')
    if not isinstance(item.get('text'), str) or not 1 <= len(item['text'].encode()) <= MAX_BYTES:
        raise ValueError('invalid_editorial_text')
    if item.get('url'): http_url(item['url'])
    refs = item.get('references', [])
    if not isinstance(refs, list) or len(refs) > 500:
        raise ValueError('invalid_editorial_references')
    for ref in refs:
        if not isinstance(ref, dict): raise ValueError('invalid_editorial_reference')
        http_url(ref.get('url'))
        if ref.get('sha256') is not None and not re.fullmatch(r'[0-9a-f]{64}', ref['sha256']):
            raise ValueError('invalid_reference_sha')
    if len(json.dumps(item).encode()) > 2 * MAX_BYTES:
        raise ValueError('editorial_metadata_too_large')
    return item


def enroll(scope, sha):
    """Append under the existing scope lock. Never replace its prior entries."""
    if not scope: return False
    path = Path(scope).expanduser()
    with locked(path):
        from inresearch.workflow.reader_scope import read_scope, MAX_SCOPE_DOCUMENTS, MAX_SCOPE_BYTES
        v = read_scope(path)
        ids = v['doc_ids']
        ident = 'doc-' + sha
        if not re.fullmatch(r'doc-[0-9a-f]{64}', ident):
            raise ValueError('invalid_editorial_document_sha')
        if ident not in ids:
            if len(ids) >= MAX_SCOPE_DOCUMENTS:
                raise ValueError('reader_scope_full')
            v['doc_ids'] = ids + [ident]
            if len(json.dumps(v, ensure_ascii=False, indent=2).encode('utf-8')) + 1 > MAX_SCOPE_BYTES:
                raise ValueError('scope_too_large')
            write_json(path, v)
    return True


def receive(item, data, root, scope=None):
    validate(item)
    data = Path(data)
    body = item['text'].encode('utf-8')
    sha = digest(body)
    revision = digest(json.dumps(item, ensure_ascii=False, sort_keys=True).encode())
    ledger = data / 'material-reviews/editorial-deliveries.json'
    with locked(ledger):
        state = json.loads(ledger.read_text()) if ledger.exists() else {'schema': 'editorial-receipts-v1', 'records': {}}
        key = item['id'] + ':' + revision
        old = state['records'].get(key)
        if old:
            enrolled = enroll(scope, sha) if old['matched'] else False
            return {**old, 'duplicate': True, 'scope_enrolled': enrolled}
        folder = data / 'incoming/editorial' / item['id'] / revision
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = folder / 'article.md'
        from inresearch.storage.files import atomic_write
        atomic_write(path, body)
        write_json(folder / 'delivery.json', item)
        doc = ingest(path, data, root, title=item['title'] + '.md')
        collector = Collector(data)
        try:
            collector.db.execute('BEGIN IMMEDIATE')
            row = collector.db.execute("SELECT id,url,metadata FROM items WHERE source='fetchreports' AND source_key=?", (sha,)).fetchone()
            meta = json.loads(row['metadata'])
            meta.update(source_role='authored_analysis', editorial_delivery={'id': item['id'], 'revision': revision,
                        'received_at': now(), 'primary_source_batch': item.get('primary_source_batch')},
                        editorial_references=item.get('references', []))
            url = row['url'] or item.get('url') or ''
            if url: meta['source_url'] = url
            collector.db.execute('UPDATE items SET url=?,metadata=?,updated=? WHERE id=?',
                                 (url, json.dumps(meta, ensure_ascii=False), now(), row['id']))
            collector.db.commit()
        finally: collector.close()
        matched = bool(doc['matches'] or doc['proposals'])
        enrolled = enroll(scope, sha) if matched else False
        receipt = {'id': item['id'], 'title': item['title'], 'revision': revision, 'article_sha256': sha,
                   'source_role': 'authored_analysis', 'references': len(item.get('references', [])),
                   'matched': matched, 'scope_enrolled': enrolled, 'received_at': now(),
                   'acceptance': 'candidate', 'full_read': False, 'adopted': False}
        state['records'][key] = receipt
        write_json(ledger, state)
        return {**receipt, 'duplicate': False}


def load_bundle(manifest):
    manifest = Path(manifest)
    if manifest.is_symlink() or manifest.stat().st_size > MAX_BYTES: raise ValueError('invalid_manifest')
    v = json.loads(manifest.read_text())
    if v.get('schema') != 'editorial-delivery-v1': raise ValueError('invalid_bundle_schema')
    verified = {}
    if not isinstance(v.get('files'), list) or not 1 <= len(v['files']) <= 10: raise ValueError('invalid_bundle_files')
    for f in v['files']:
        name = f.get('path', '')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in verified: raise ValueError('invalid_bundle_path')
        p = manifest.parent / name
        if p.is_symlink() or not p.is_file() or not 0 <= p.stat().st_size <= MAX_BYTES: raise ValueError('invalid_bundle_file')
        b = p.read_bytes()
        if len(b) != f['bytes'] or digest(b) != f['sha256']: raise ValueError('bundle_hash_mismatch')
        verified[name] = b
    article = verified[v['article']].decode('utf-8')
    sources = json.loads(verified.get('sources.json', b'{"records":[]}'))
    refs = [{'id': r.get('id'), 'title': r.get('title'), 'publisher': r.get('org'), 'url': r['url'],
             'sha256': r.get('sha256'), 'published': r.get('published'), 'retrieval_status': r.get('status'),
             'read_scope': r.get('read_scope'), 'verification': 'supplier_reference_not_independently_verified'}
            for r in sources.get('records', []) if r.get('url')]
    return validate({'id': v['id'], 'title': v['title'], 'text': article, 'source_role': v['source_role'],
                     'references': refs, 'primary_source_batch': v.get('primary_source_batch')})


def sync(data, root, endpoint, scope=None, fetch=None):
    http_url(endpoint)
    if urlsplit(endpoint).query or urlsplit(endpoint).fragment: raise ValueError('invalid_feed_endpoint')
    def request(address):
        with urlopen(Request(address, headers={'User-Agent': 'inresearch.ai-editorial-sync/1.0'}), timeout=30) as response:
            if response.status != 200 or response.url != address: raise ValueError('unexpected_feed_response')
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES: raise ValueError('feed_too_large')
            return json.loads(body)
    fetch = fetch or request
    after = 0
    results = []
    for _ in range(1000):
        page = fetch(endpoint + '?' + urlencode({'after': after, 'limit': 1}))
        if page.get('schema') != 'inews-editorial-feed-v1' or not isinstance(page.get('items'), list) or len(page['items']) > 1:
            raise ValueError('invalid_editorial_feed')
        previous = after
        for item in page['items']:
            validate(item)
            if not re.fullmatch(r'inews-column-[1-9][0-9]*', item['id']): raise ValueError('invalid_column_id')
            ident = int(item['id'].rsplit('-', 1)[1])
            if ident <= previous: raise ValueError('unordered_column_feed')
            previous = ident
            results.append(receive(item, data, root, scope))
        cursor = page.get('next_after')
        if cursor is None:
            return {'received': sum(not r['duplicate'] for r in results), 'unchanged': sum(r['duplicate'] for r in results), 'records': results}
        if str(cursor) != str(previous) or previous <= after: raise ValueError('invalid_column_cursor')
        after = previous
    raise ValueError('editorial_page_limit')


def main(argv=None):
    from inresearch.paths import project_root
    p = argparse.ArgumentParser(prog='editorial-sync')
    source = p.add_mutually_exclusive_group()
    source.add_argument('--bundle')
    source.add_argument('--feed', default=None)
    p.add_argument('--data-root', default=str(Path.home() / '.local/share/inresearch.ai'))
    p.add_argument('--scope', default=os.getenv('READER_DOCUMENT_SCOPE'))
    p.add_argument('--receipt')
    args = p.parse_args(argv)
    result = receive(load_bundle(args.bundle), args.data_root, project_root(), args.scope) if args.bundle else sync(
        args.data_root, project_root(), args.feed or 'https://inews.today/api/feeds/columns', args.scope)
    if args.receipt: write_json(Path(args.receipt), result)
    print(json.dumps(result, ensure_ascii=False))
    return 0
