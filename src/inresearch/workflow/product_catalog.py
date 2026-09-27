"""Evidence-backed vendor specifications, separate from adopted research facts."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import stat
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from inresearch.paths import project_root
from inresearch.storage.layout import workspace_path
from inresearch.delivery.publish_pilot_progress import NoRedirect
from inresearch.workflow import product_navigation


def database(root):
    return workspace_path('data/raw/product-catalog/nvidia.sqlite3', root)


def connect(root):
    path = database(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript('''
      CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, generated TEXT, received TEXT, coverage TEXT);
      CREATE TABLE IF NOT EXISTS sources(sha TEXT PRIMARY KEY, payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS source_observations(url TEXT, sha TEXT, payload TEXT NOT NULL, PRIMARY KEY(url,sha));
      CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS versions(product_id TEXT, sha TEXT, payload TEXT NOT NULL, PRIMARY KEY(product_id,sha));
      CREATE TABLE IF NOT EXISTS specs(product_id TEXT, sha TEXT, table_no INTEGER, row_no INTEGER, parameter TEXT, cells TEXT, PRIMARY KEY(product_id,sha,table_no,row_no));
    ''')
    return db


def official(url):
    p = urlsplit(url)
    return p.scheme == 'https' and not p.username and not p.password and p.port in (None, 443) and (
        p.hostname in {'nvidia.com', 'nvidia.cn'} or (p.hostname or '').endswith(('.nvidia.com', '.nvidia.cn')))


def validate(payload):
    if not isinstance(payload, dict) or payload.get('schema_version') != 1 or payload.get('company_id') != 'nvidia':
        raise ValueError('NVIDIA catalog schema 1 required')
    stamp = datetime.fromisoformat(payload['generated_at'])
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError('UTC timezone required')
    products, sources = payload['products'], payload['sources']
    if not isinstance(products, list) or len(products) > 10000 or not isinstance(sources, list) or len(sources) > 20000:
        raise ValueError('catalog size limit exceeded')
    if payload['coverage'].get('complete') is not False:
        raise ValueError('coverage remains incomplete until audited')
    source_keys = set()
    for source in sources:
        if not re.fullmatch('[0-9a-f]{64}', source['sha256']) or not official(source['source_url']):
            raise ValueError('invalid source identity')
        source_keys.add((source['sha256'], source['source_url']))
    ids = set()
    for product in products:
        key = product['id']
        if not re.fullmatch('nvidia-[0-9a-f]{20}', key) or key in ids or not product['name']:
            raise ValueError('invalid or repeated product ID')
        ids.add(key)
        if (product['source_sha256'], product['source_url']) not in source_keys:
            raise ValueError('product source missing')
        if product['kind'] not in {'named_product', 'software_service', 'family_or_directory'} or product['availability'] != 'not_verified':
            raise ValueError('invalid product classification')
        for attachment in product.get('attachments', []):
            if not official(attachment['url']):
                raise ValueError('attachment must be an official HTTPS source')
        for table in product['tables']:
            if type(table['index']) is not int or table['index'] < 1 or len(table['rows']) > 1000:
                raise ValueError('invalid table')
            for row in table['rows']:
                if not row or len(row) > 100:
                    raise ValueError('invalid row')
                for cell in row:
                    if not isinstance(cell['text'], str) or len(cell['text']) > 20000:
                        raise ValueError('invalid cell')
                    if any(type(cell[k]) is not int or not 1 <= cell[k] <= 100 for k in ('rowspan', 'colspan')):
                        raise ValueError('invalid cell span')
    return payload


def verify_snapshots(payload, archive_root):
    archive_root = Path(archive_root).expanduser().resolve()
    for source in payload['sources']:
        path = (archive_root / source['snapshot_path']).resolve()
        if not path.is_relative_to(archive_root) or not path.is_file():
            raise ValueError('source snapshot outside archive or missing')
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('source snapshot hash mismatch')


def publish(payload, token_file):
    token_file = Path(token_file).expanduser()
    if token_file.is_symlink() or not token_file.is_file() or stat.S_IMODE(token_file.stat().st_mode) & 0o077:
        raise ValueError('pilot credential must be a private regular file')
    token = token_file.read_text().strip()
    if len(token) < 32:
        raise ValueError('pilot credential unavailable')
    body = json.dumps(payload, ensure_ascii=False).encode()
    if len(body) > 16 * 1024 * 1024:
        raise ValueError('catalog delivery exceeds 16 MiB')
    request = Request('https://inresearch.ai/api/product-catalog/nvidia', data=body,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with build_opener(NoRedirect).open(request, timeout=60) as response:
        receipt = json.load(response)
    if receipt.get('ok') is not True or receipt.get('products') != len(payload['products']):
        raise ValueError('catalog receipt does not acknowledge this delivery')
    return receipt


def receive(root, payload):
    validate(payload)
    run_id = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    db = connect(root)
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            latest = db.execute('SELECT generated,id FROM runs ORDER BY generated DESC LIMIT 1').fetchone()
            if latest and latest['id'] == run_id:
                return {'ok': True, 'replayed': True, 'products': len(payload['products']), 'run_id': run_id}
            if latest and datetime.fromisoformat(payload['generated_at']) <= datetime.fromisoformat(latest['generated']):
                raise ValueError('older catalog cannot replace current observations')
            db.execute('INSERT INTO runs VALUES(?,?,?,?)', (run_id, payload['generated_at'], datetime.now(timezone.utc).isoformat(), json.dumps(payload['coverage'], ensure_ascii=False)))
            for source in payload['sources']:
                # Source evidence remains private; webpage API only projects tables.
                db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)', (source['sha256'], json.dumps(source, ensure_ascii=False)))
                db.execute('INSERT OR IGNORE INTO source_observations VALUES(?,?,?)', (source['source_url'], source['sha256'], json.dumps(source, ensure_ascii=False)))
            for product in payload['products']:
                raw = json.dumps(product, ensure_ascii=False)
                db.execute('INSERT OR REPLACE INTO products VALUES(?,?,?)', (product['id'], run_id, raw))
                db.execute('INSERT OR IGNORE INTO versions VALUES(?,?,?)', (product['id'], product['source_sha256'], raw))
                for table in product['tables']:
                    for n, row in enumerate(table['rows']):
                        if len(row) < 2 or not row[0]['text']:
                            continue
                        db.execute('INSERT OR IGNORE INTO specs VALUES(?,?,?,?,?,?)', (product['id'], product['source_sha256'], table['index'], n + 1, row[0]['text'], json.dumps(row[1:], ensure_ascii=False)))
        return {'ok': True, 'products': len(payload['products']), 'run_id': run_id}
    finally:
        db.close()


def snapshot(root):
    if not database(root).is_file():
        return {'available': False, 'products': [], 'coverage': {}}
    db = sqlite3.connect(f'file:{database(root)}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        run = db.execute('SELECT * FROM runs ORDER BY generated DESC LIMIT 1').fetchone()
        if run is None:
            return {'available': False, 'products': [], 'coverage': {}}
        products = []
        for row in db.execute('SELECT payload,run_id FROM products WHERE run_id=? ORDER BY id', (run['id'],)):
            p = json.loads(row['payload'])
            p['seen_in_latest_run'] = row['run_id'] == run['id']
            p['navigation'] = product_navigation.classify(p)
            # Tables are data, never injected source HTML. Source text stays private.
            for table in p['tables']:
                table.pop('text', None)
            products.append(p)
        return {'available': True, 'company_id': 'nvidia', 'generated_at': run['generated'],
                'received_at': run['received'], 'acceptance': 'source_extracted_not_research_adopted',
                'coverage': json.loads(run['coverage']), 'products': products,
                'navigation': {'version': product_navigation.VERSION, 'groups': product_navigation.GROUPS,
                               'official_source': product_navigation.SOURCE}}
    finally:
        db.close()


def csv_export(value, mode='products', query='', kind='', with_specs=False, group='', family='', scope='all'):
    products = [p for p in value['products'] if (not kind or p['kind'] == kind)
                and (not with_specs or p['tables'])
                and product_navigation.matches(p, group, family, scope)
                and query.casefold() in (p['name'] + ' ' + p['category']).casefold()]
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    def safe(text):
        text = str(text)
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
    def row(values):
        writer.writerow([safe(v) for v in values])
    if mode == 'products':
        row(['product_id', 'name', 'official_category', 'entity_kind', 'availability', 'extraction_status', 'specification_tables', 'source_url', 'source_sha256', 'observed_at', 'display_group', 'display_family', 'navigation_role'])
        for p in products:
            nav = product_navigation.classify(p)
            row([p['id'], p['name'], p['category'], p['kind'], p['availability'], p['extraction_status'], len(p['tables']), p['source_url'], p['source_sha256'], p['observed_at'], nav['group'], nav['family'], nav['role']])
    elif mode == 'specs':
        row(['product_id', 'name', 'official_section', 'table', 'row', 'official_parameter', 'official_values', 'official_column_headers', 'official_cells_json', 'official_notes', 'source_url', 'source_sha256'])
        for p in products:
            for table in p['tables']:
                for n, cells in enumerate(table['rows'], 1):
                    first = table['rows'][0]
                    headers = ' | '.join(c['text'] for c in first[1:]) if not first[0]['text'] or all(c['header'] for c in first) else ''
                    row([p['id'], p['name'], table['section'], table['index'], n, cells[0]['text'], ' | '.join(c['text'] for c in cells[1:]), headers, json.dumps(cells, ensure_ascii=False), table.get('notes', ''), p['source_url'], p['source_sha256']])
    else:
        raise ValueError('unknown export')
    return '\ufeff' + stream.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['import', 'publish', 'status', 'export'])
    ap.add_argument('--input', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--mode', choices=['products', 'specs'], default='products')
    ap.add_argument('--archive-root', type=Path)
    ap.add_argument('--token-file', default='~/.local/state/inresearch.ai/nvidia-pilot.token')
    args = ap.parse_args(argv)
    root = project_root()
    if args.action in {'import', 'publish'}:
        if not args.input or not args.archive_root:
            ap.error('--input and --archive-root required')
        payload = validate(json.loads(args.input.read_text()))
        verify_snapshots(payload, args.archive_root)
        receipt = receive(root, payload) if args.action == 'import' else publish(payload, args.token_file)
        print(json.dumps(receipt, ensure_ascii=False))
    elif args.action == 'export':
        if not args.out:
            ap.error('--out required')
        args.out.write_text(csv_export(snapshot(root), args.mode), encoding='utf-8')
    else:
        s = snapshot(root)
        print(json.dumps({k: v for k, v in s.items() if k != 'products'}, ensure_ascii=False, indent=2))
