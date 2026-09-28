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


def official_attachment(url, attachment, source_keys):
    if official(url):
        return True
    p = urlsplit(url)
    if (p.scheme != 'https' or p.username or p.password or p.port not in (None, 443)
            or p.hostname != 'dam-cdn.nvd.orangelogic.com'):
        return False
    # NVIDIA's public product pages and resource viewers embed PDFs from this
    # exact DAM host. Require a per-file link back to the captured first-party
    # page that exposed it; do not broaden hosts.
    source_url, source_sha = attachment.get('source_url'), attachment.get('source_sha256')
    return (official(source_url or '') and (source_sha, source_url) in source_keys)


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
        source_url = source.get('source_url', '')
        parsed_source = urlsplit(source_url)
        dam_receipt = (parsed_source.scheme == 'https' and not parsed_source.username and not parsed_source.password
            and parsed_source.port in (None, 443) and parsed_source.hostname == 'dam-cdn.nvd.orangelogic.com'
            and source.get('kind') == 'official_pdf_attachment')
        if not re.fullmatch('[0-9a-f]{64}', source.get('sha256', '')) or not (official(source_url) or dam_receipt):
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
            if not official_attachment(attachment['url'], attachment, source_keys):
                raise ValueError('attachment must be an official HTTPS source')
            if attachment.get('sha256'):
                if (attachment['sha256'], attachment['url']) not in source_keys:
                    raise ValueError('attachment snapshot receipt is missing')
                if attachment.get('source_url') and (attachment.get('source_sha256'), attachment['source_url']) not in source_keys:
                    raise ValueError('attachment source page receipt is missing')
        for resource in product.get('official_resources', []):
            if not official(resource['url']):
                raise ValueError('product resource must be an official HTTPS source')
        for source in product.get('official_pages', []):
            if not official(source['url']) or not re.fullmatch('[0-9a-f]{64}', source['sha256']):
                raise ValueError('localized product source must have an official URL and SHA-256')
            if (source['sha256'], source['url']) not in source_keys:
                raise ValueError('localized product source is missing its snapshot receipt')
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
            for ref in table.get('source_refs', []):
                if (ref.get('sha256'), ref.get('url')) not in source_keys:
                    raise ValueError('table source reference is missing its receipt')
    for product in products:
        if product.get('parent_id') and product['parent_id'] not in ids:
            raise ValueError('product parent is missing from this catalog')
    return payload


def verify_snapshots(payload, archive_root):
    archive_root = Path(archive_root).expanduser().resolve()
    for source in payload['sources']:
        path = (archive_root / source['snapshot_path']).resolve()
        if not path.is_relative_to(archive_root) or not path.is_file():
            raise ValueError('source snapshot outside archive or missing')
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('source snapshot hash mismatch')


def source_refs_for_table(table):
    """Return only evidence already admitted by the catalog receipt validator."""
    return table.get('source_refs', [])


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
            coverage = {**payload['coverage'], 'product_map': payload.get('product_map', {})}
            db.execute('INSERT INTO runs VALUES(?,?,?,?)', (run_id, payload['generated_at'], datetime.now(timezone.utc).isoformat(), json.dumps(coverage, ensure_ascii=False)))
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


def index_snapshot(root):
    """Return the lightweight product map used for initial catalog rendering.

    Specification tables, attachments and source receipts stay behind the
    per-product endpoint.  Keeping the index projection here (rather than in
    the browser) makes the transfer size independent of table density.
    """
    value = snapshot(root)
    value['view'] = 'index'
    value['products'] = [{
        'id': p['id'],
        'name': p['name'],
        'parent_id': p.get('parent_id'),
        'category': p['category'],
        'kind': p['kind'],
        'availability': p['availability'],
        'extraction_status': p['extraction_status'],
        'observed_at': p['observed_at'],
        'map_change_status': p.get('map_change_status', ''),
        'table_count': len(p['tables']),
        'navigation': p['navigation'],
    } for p in value['products']]
    target_document = json.loads((root / 'framework/tco_targets.json').read_text())
    related = [row for row in target_document['targets'] if row.get('team') == 'fetchspec'
               and any('nvidia' in str(instance).casefold() for instance in row.get('instances', []))]
    value['research_alignment'] = {
        'target_ids': [row['id'] for row in related],
        'part_ids': sorted({row['part_id'] for row in related if row.get('part_id')}),
        'acceptance': 'target_demand_only_not_research_adoption',
    }
    return value


def product_snapshot(root, product_id):
    """Return one evidence-backed product detail from the current run."""
    if not re.fullmatch(r'nvidia-[0-9a-f]{20}', product_id):
        raise ValueError('invalid product ID')
    if not database(root).is_file():
        return {'available': False, 'company_id': 'nvidia', 'product': None}
    db = sqlite3.connect(f'file:{database(root)}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        run = db.execute('SELECT * FROM runs ORDER BY generated DESC LIMIT 1').fetchone()
        if run is None:
            return {'available': False, 'company_id': 'nvidia', 'product': None}
        row = db.execute('SELECT payload FROM products WHERE run_id=? AND id=?',
                         (run['id'], product_id)).fetchone()
        product = json.loads(row['payload']) if row else None
        if product:
            product['seen_in_latest_run'] = True
            product['navigation'] = product_navigation.classify(product)
            for table in product['tables']:
                table.pop('text', None)
        return {
            'available': True,
            'company_id': 'nvidia',
            'generated_at': run['generated'],
            'acceptance': 'source_extracted_not_research_adopted',
            'product': product,
        }
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
    if mode in {'products', 'map'}:
        row(['product_id', 'name', 'parent_id', 'official_category', 'entity_kind', 'availability', 'extraction_status', 'specification_tables', 'map_change_status', 'official_sitemap_match', 'official_sitemap_roles', 'official_sitemap_lastmod_claims', 'official_resource_urls', 'source_url', 'source_sha256', 'observed_at', 'display_group', 'display_family', 'navigation_role'])
        for p in products:
            nav = product_navigation.classify(p)
            sitemap = p.get('website_sitemap', {})
            row([p['id'], p['name'], p.get('parent_id', ''), p['category'], p['kind'], p['availability'], p['extraction_status'], len(p['tables']), p.get('map_change_status', ''), sitemap.get('matched', False), ' | '.join(sitemap.get('roles', [])), ' | '.join(sitemap.get('lastmod_claims', [])), ' | '.join(a['url'] for a in p.get('official_resources', [])), p['source_url'], p['source_sha256'], p['observed_at'], nav['group'], nav['family'], nav['role']])
    elif mode == 'specs':
        row(['product_id', 'name', 'official_section', 'table', 'row', 'official_parameter', 'official_values', 'official_column_headers', 'official_cells_json', 'official_notes', 'source_url', 'source_sha256', 'table_evidence_urls', 'table_evidence_sha256'])
        for p in products:
            for table in p['tables']:
                for n, cells in enumerate(table['rows'], 1):
                    first = table['rows'][0]
                    headers = ' | '.join(c['text'] for c in first[1:]) if not first[0]['text'] or all(c['header'] for c in first) else ''
                    refs = source_refs_for_table(table)
                    row([p['id'], p['name'], table['section'], table['index'], n, cells[0]['text'], ' | '.join(c['text'] for c in cells[1:]), headers, json.dumps(cells, ensure_ascii=False), table.get('notes', ''), p['source_url'], p['source_sha256'], ' | '.join(ref['url'] for ref in refs), ' | '.join(ref['sha256'] for ref in refs)])
    else:
        raise ValueError('unknown export')
    return '\ufeff' + stream.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['import', 'publish', 'status', 'export'])
    ap.add_argument('--input', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--mode', choices=['products', 'map', 'specs'], default='products')
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
