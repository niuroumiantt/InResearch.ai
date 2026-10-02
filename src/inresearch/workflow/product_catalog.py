"""Evidence-backed vendor specifications, separate from adopted research facts.

One pipeline for every registered company (``COMPANIES``): the same schema 1
delivery, one SQLite database per company, a per-company official host rule and
a per-company browsing projection.  NVIDIA keeps its reviewed display mapping;
other companies are browsed by the vendor's own product path.
"""
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

# Registered companies.  ``domains`` are the official first-party hosts (the
# domain itself and its subdomains, HTTPS on 443 only).  ``attachment_hosts``
# are exact third-party hosts the vendor embeds official files from; such a
# file is admitted only with a receipt for the first-party page that exposed it.
COMPANIES = {
    'nvidia': {'label': 'NVIDIA', 'match': 'nvidia', 'domains': ('nvidia.com', 'nvidia.cn'),
               'attachment_hosts': ('dam-cdn.nvd.orangelogic.com',),
               'navigation': 'display_mapping', 'products_url': product_navigation.SOURCE},
    'micron': {'label': 'Micron', 'match': 'micron', 'domains': ('micron.com',),
               'attachment_hosts': (),
               'navigation': 'vendor_taxonomy', 'products_url': 'https://www.micron.com/products'},
    'intel': {'label': 'Intel', 'match': 'intel', 'domains': ('intel.com',),
              'attachment_hosts': (), 'navigation': 'vendor_taxonomy',
              'products_url': 'https://www.intel.com/content/www/us/en/products.html'},
    'amd': {'label': 'AMD', 'match': 'amd', 'domains': ('amd.com',),
            'attachment_hosts': (), 'navigation': 'vendor_taxonomy',
            'products_url': 'https://www.amd.com/en/products.html'},
    'supermicro': {'label': 'Supermicro', 'match': 'supermicro', 'domains': ('supermicro.com',),
                   'attachment_hosts': (), 'navigation': 'vendor_taxonomy',
                   'products_url': 'https://www.supermicro.com/en/products'},
    'sk-hynix': {'label': 'SK hynix', 'match': 'sk hynix', 'domains': ('skhynix.com',),
                 'attachment_hosts': (), 'navigation': 'vendor_taxonomy',
                 'products_url': 'https://product.skhynix.com/'},
}
LISTINGS = {'active', 'obsolete', 'directory'}


def company_config(company):
    if company not in COMPANIES:
        raise ValueError('unknown catalog company')
    return COMPANIES[company]


def product_id_pattern(company):
    company_config(company)
    return re.escape(company) + '-[0-9a-f]{20}'


def classify(product, company='nvidia'):
    config = company_config(company)
    if config['navigation'] == 'display_mapping':
        return product_navigation.classify(product)
    return product_navigation.classify_taxonomy(product, config['products_url'])


def navigation_block(products, company='nvidia'):
    config = company_config(company)
    if config['navigation'] == 'display_mapping':
        return {'version': product_navigation.VERSION, 'groups': product_navigation.GROUPS,
                'official_source': product_navigation.SOURCE}
    return {'version': product_navigation.TAXONOMY_VERSION, 'groups': product_navigation.taxonomy_groups(products),
            'official_source': config['products_url'], 'basis': 'vendor_product_path', 'status': 'vendor_taxonomy'}


def database(root, company='nvidia'):
    company_config(company)
    return workspace_path(f'data/raw/product-catalog/{company}.sqlite3', root)


def connect(root, company='nvidia'):
    path = database(root, company)
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


def _https(p):
    return p.scheme == 'https' and not p.username and not p.password and p.port in (None, 443)


def official(url, company='nvidia'):
    domains = company_config(company)['domains']
    p = urlsplit(url)
    return _https(p) and (p.hostname in domains or (p.hostname or '').endswith(tuple('.' + d for d in domains)))


def attachment_host(url, company='nvidia'):
    p = urlsplit(url)
    return _https(p) and p.hostname in company_config(company)['attachment_hosts']


def official_attachment(url, attachment, source_keys, company='nvidia'):
    if official(url, company):
        return True
    if not attachment_host(url, company):
        return False
    # NVIDIA's public product pages and resource viewers embed PDFs from this
    # exact DAM host. Require a per-file link back to the captured first-party
    # page that exposed it; do not broaden hosts.
    source_url, source_sha = attachment.get('source_url'), attachment.get('source_sha256')
    return (official(source_url or '', company) and (source_sha, source_url) in source_keys)


def _text(value, limit=500):
    return isinstance(value, str) and len(value) <= limit


def validate_vendor_fields(product):
    """Optional vendor-path fields; passed through untouched once well-formed."""
    if 'taxonomy' in product:
        path = product['taxonomy']
        if not isinstance(path, list) or len(path) > 20 or not all(
                isinstance(step, dict) and _text(step.get('slug'), 200) and step['slug']
                and _text(step.get('name', ''), 500) for step in path):
            raise ValueError('taxonomy must be a list of {slug, name}')
    if 'listing' in product and product['listing'] not in LISTINGS:
        raise ValueError('listing must be active, obsolete or directory')
    for key in ('official_status', 'part_number'):
        if key in product and not _text(product[key]):
            raise ValueError(key + ' must be text')


def validate(payload, company=None):
    """Validate a schema 1 delivery for a registered company.

    ``company`` names the receiver; a delivery for another company is refused.
    """
    if not isinstance(payload, dict) or payload.get('schema_version') != 1 or payload.get('company_id') not in COMPANIES:
        raise ValueError('catalog schema 1 for a registered company required')
    if company is not None and payload['company_id'] != company:
        raise ValueError(company_config(company)['label'] + ' catalog schema 1 required')
    company = payload['company_id']
    id_pattern = product_id_pattern(company)
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
        dam_receipt = attachment_host(source_url, company) and source.get('kind') == 'official_pdf_attachment'
        if not re.fullmatch('[0-9a-f]{64}', source.get('sha256', '')) or not (official(source_url, company) or dam_receipt):
            raise ValueError('invalid source identity')
        source_keys.add((source['sha256'], source['source_url']))
    ids = set()
    for product in products:
        key = product['id']
        if not re.fullmatch(id_pattern, key) or key in ids or not product['name']:
            raise ValueError('invalid or repeated product ID')
        ids.add(key)
        if (product['source_sha256'], product['source_url']) not in source_keys:
            raise ValueError('product source missing')
        if product['kind'] not in {'named_product', 'software_service', 'family_or_directory'} or product['availability'] != 'not_verified':
            raise ValueError('invalid product classification')
        validate_vendor_fields(product)
        for attachment in product.get('attachments', []):
            if not official_attachment(attachment['url'], attachment, source_keys, company):
                raise ValueError('attachment must be an official HTTPS source')
            if attachment.get('sha256'):
                if (attachment['sha256'], attachment['url']) not in source_keys:
                    raise ValueError('attachment snapshot receipt is missing')
                if attachment.get('source_url') and (attachment.get('source_sha256'), attachment['source_url']) not in source_keys:
                    raise ValueError('attachment source page receipt is missing')
        for resource in product.get('official_resources', []):
            if not official(resource['url'], company):
                raise ValueError('product resource must be an official HTTPS source')
        for source in product.get('official_pages', []):
            if not official(source['url'], company) or not re.fullmatch('[0-9a-f]{64}', source['sha256']):
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


def publish(payload, token_file, company='nvidia'):
    token_file = Path(token_file).expanduser()
    if token_file.is_symlink() or not token_file.is_file() or stat.S_IMODE(token_file.stat().st_mode) & 0o077:
        raise ValueError('pilot credential must be a private regular file')
    token = token_file.read_text().strip()
    if payload.get('company_id') != company:
        raise ValueError('catalog delivery is for another company')
    if len(token) < 32:
        raise ValueError('pilot credential unavailable')
    body = json.dumps(payload, ensure_ascii=False).encode()
    if len(body) > 16 * 1024 * 1024:
        raise ValueError('catalog delivery exceeds 16 MiB')
    request = Request('https://inresearch.ai/api/product-catalog/' + company, data=body,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with build_opener(NoRedirect).open(request, timeout=60) as response:
        receipt = json.load(response)
    if receipt.get('ok') is not True or receipt.get('products') != len(payload['products']):
        raise ValueError('catalog receipt does not acknowledge this delivery')
    return receipt


def receive(root, payload, company='nvidia'):
    validate(payload, company)
    run_id = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    db = connect(root, company)
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


def company_block(company):
    config = company_config(company)
    return {'id': company, 'label': config['label'], 'products_url': config['products_url'],
            'navigation': config['navigation']}


def with_list_fields(product):
    """Deliveries may leave empty optional lists out to stay small; readers always get the lists."""
    for key in ('attachments', 'official_resources', 'official_pages'):
        product.setdefault(key, [])
    product.setdefault('categories', [product['category']] if product.get('category') else [])
    return product


def snapshot(root, company='nvidia'):
    path = database(root, company)
    if not path.is_file():
        return {'available': False, 'company_id': company, 'company': company_block(company), 'products': [], 'coverage': {}}
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        run = db.execute('SELECT * FROM runs ORDER BY generated DESC LIMIT 1').fetchone()
        if run is None:
            return {'available': False, 'company_id': company, 'company': company_block(company), 'products': [], 'coverage': {}}
        products = []
        for row in db.execute('SELECT payload,run_id FROM products WHERE run_id=? ORDER BY id', (run['id'],)):
            p = with_list_fields(json.loads(row['payload']))
            p['seen_in_latest_run'] = row['run_id'] == run['id']
            p['navigation'] = classify(p, company)
            # Tables are data, never injected source HTML. Source text stays private.
            for table in p['tables']:
                table.pop('text', None)
            products.append(p)
        return {'available': True, 'company_id': company, 'company': company_block(company),
                'generated_at': run['generated'],
                'received_at': run['received'], 'acceptance': 'source_extracted_not_research_adopted',
                'coverage': json.loads(run['coverage']), 'products': products,
                'navigation': navigation_block(products, company)}
    finally:
        db.close()


VENDOR_FIELDS = ('taxonomy', 'official_status', 'listing', 'part_number')


def summary(products, groups=()):
    """Counts computed from the delivered data; never a vendor-wide product total.

    The standard keeps two denominators apart: named products with official
    specification tables / named products, and all catalog entities with tables /
    all entities.
    """
    def count(values):
        result = {}
        for value in values:
            result[value] = result.get(value, 0) + 1
        return dict(sorted(result.items()))
    def tables(p):
        return bool(p.get('tables')) if 'tables' in p else bool(p.get('table_count'))
    labels = {g['id']: g['label'] for g in groups}
    by_group = {}
    for p in products:
        nav = p['navigation']
        group = by_group.setdefault(nav['group'], {'id': nav['group'], 'label': labels.get(nav['group']) or nav['group'] or '待归类',
                                                   'entities': 0, 'with_tables': 0, 'families': {}})
        family = group['families'].setdefault(nav['family'], {'id': nav['family'], 'label': nav['family_label'],
                                                             'entities': 0, 'with_tables': 0})
        for bucket in (group, family):
            bucket['entities'] += 1
            bucket['with_tables'] += tables(p)
    named = [p for p in products if p['kind'] == 'named_product']
    current = [p for p in named if p.get('listing', 'active') == 'active']
    return {
        'basis': 'delivered_catalog_entities_not_vendor_total',
        'entities': len(products),
        'by_kind': count(p['kind'] for p in products),
        'by_listing': count(p.get('listing') or 'unspecified' for p in products),
        'by_official_status': count(p.get('official_status') or 'unspecified' for p in products),
        # how each entity's specification was obtained (part component, family product brief, gap, …)
        'by_extraction_status': count(p.get('extraction_status') or 'unspecified' for p in products),
        'by_group': [{**g, 'families': sorted(g['families'].values(), key=lambda f: f['id'])}
                     for g in sorted(by_group.values(), key=lambda g: (not g['id'], g['label'].casefold()))],
        'specification_coverage': {
            'named_products': {'with_tables': sum(map(tables, named)), 'total': len(named)},
            # Parts the vendor lists as obsolete are catalogued but not collected; the standard's first
            # denominator is the current named products (when the catalog marks listings at all).
            **({'current_named_products': {'with_tables': sum(map(tables, current)), 'total': len(current)},
                'obsolete_listed': len(named) - len(current)} if any('listing' in p for p in named) else {}),
            'all_entities': {'with_tables': sum(map(tables, products)), 'total': len(products)},
        },
    }


def research_alignment(root, company='nvidia'):
    term = company_config(company)['match'].casefold()
    # Match word boundaries after separators, so AMD does not match RAMDisk.
    pattern = re.compile(r'(?<![a-z0-9])' + re.escape(term).replace(r'\ ', r'[\s_-]+') + r'(?![a-z0-9])')
    target_document = json.loads((root / 'framework/tco_targets.json').read_text())
    related = [row for row in target_document['targets'] if row.get('team') == 'fetchspec'
               and any(pattern.search(str(instance).casefold()) for instance in row.get('instances', []))]
    return {
        'target_ids': [row['id'] for row in related],
        'part_ids': sorted({row['part_id'] for row in related if row.get('part_id')}),
        'targets': [{'id': row['id'], 'part_id': row.get('part_id'), 'status': row.get('status')} for row in related],
        'acceptance': 'target_demand_only_not_research_adoption',
    }


def index_snapshot(root, company='nvidia'):
    """Return the lightweight product map used for initial catalog rendering.

    Specification tables, attachments and source receipts stay behind the
    per-product endpoint.  Keeping the index projection here (rather than in
    the browser) makes the transfer size independent of table density.
    """
    value = snapshot(root, company)
    value['view'] = 'index'
    value['registered_companies'] = [company_block(c) for c in COMPANIES]
    value['summary'] = summary(value['products'], value.get('navigation', {}).get('groups', ()))
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
        **{key: p[key] for key in VENDOR_FIELDS if key in p},
    } for p in value['products']]
    value['research_alignment'] = research_alignment(root, company)
    return value


def summary_snapshot(root, company='nvidia'):
    """The index without its product list: what a company page shows about the catalog."""
    value = index_snapshot(root, company)
    value.pop('products', None)
    value['view'] = 'summary'
    return value


def product_snapshot(root, product_id, company='nvidia'):
    """Return one evidence-backed product detail from the current run."""
    if not re.fullmatch(product_id_pattern(company), product_id):
        raise ValueError('invalid product ID')
    path = database(root, company)
    if not path.is_file():
        return {'available': False, 'company_id': company, 'product': None}
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        run = db.execute('SELECT * FROM runs ORDER BY generated DESC LIMIT 1').fetchone()
        if run is None:
            return {'available': False, 'company_id': company, 'product': None}
        row = db.execute('SELECT payload FROM products WHERE run_id=? AND id=?',
                         (run['id'], product_id)).fetchone()
        product = with_list_fields(json.loads(row['payload'])) if row else None
        if product:
            product['seen_in_latest_run'] = True
            product['navigation'] = classify(product, company)
            for table in product['tables']:
                table.pop('text', None)
        return {
            'available': True,
            'company_id': company,
            'generated_at': run['generated'],
            'acceptance': 'source_extracted_not_research_adopted',
            'product': product,
        }
    finally:
        db.close()


# Series comparison column order: the parameters a reader compares first, then the rest in the
# vendor's own order, packaging and status bookkeeping last.  Ordering only; labels stay verbatim.
SERIES_FIRST = ('capacity', 'density', 'speed', 'mt/s', 'data rate', 'interface', 'form factor',
                'module version', 'technology', 'component config', 'bus width', 'width', 'voltage',
                'operating temp', 'package', 'pin count')
SERIES_LAST = ('qty', 'package type', 'part status code')
DECODED_LABELS = {'capacity': 'Capacity (decoded from part number)',
                  'form_factor': 'Form factor (decoded from part number)'}


def _column_rank(label, position):
    text = label.casefold()
    if any(key in text for key in SERIES_LAST):
        return (2, 0, position)
    first = next((i for i, key in enumerate(SERIES_FIRST) if key in text), None)
    return (0, first, position) if first is not None else (1, 0, position)


def _natural(name):
    return [(0, int(s), '') if s.isdigit() else (1, 0, s) for s in re.split(r'(\d+)', name)]


def series_snapshot(root, series_id, company='nvidia'):
    """One vendor series (the directory page its parts hang from) as a comparison.

    Two-column ``label | value`` part tables are pivoted into one row per part; a
    parameter with the same value on every part is listed once as common.  Any other
    table (e.g. a family product brief that every part shares) is kept whole and shown
    once with the parts it applies to.  Labels and values stay verbatim.
    """
    if not re.fullmatch(product_id_pattern(company), series_id):
        raise ValueError('invalid series ID')
    path = database(root, company)
    if not path.is_file():
        return {'available': False, 'company_id': company, 'series': None}
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        run = db.execute('SELECT * FROM runs ORDER BY generated DESC LIMIT 1').fetchone()
        if run is None:
            return {'available': False, 'company_id': company, 'series': None}
        products = [json.loads(row['payload']) for row in
                    db.execute('SELECT payload FROM products WHERE run_id=?', (run['id'],))]
    finally:
        db.close()
    value = {'available': True, 'company_id': company, 'generated_at': run['generated'],
             'acceptance': 'source_extracted_not_research_adopted', 'series': None}
    series = next((p for p in products if p['id'] == series_id), None)
    if series is None:
        return value
    parts = sorted((p for p in products if p.get('parent_id') == series_id and p['kind'] == 'named_product'),
                   key=lambda p: _natural(p['name']))
    order, rows, shared = {}, [], {}
    for part in parts:
        values = {}
        for key, label in DECODED_LABELS.items():
            if (part.get('brief_decoded') or {}).get(key):
                values[label] = str(part['brief_decoded'][key])
        for table in part.get('tables', []):
            # a family product brief is one series-level table every part shares, never a per-part row
            if (table.get('rows') and part['extraction_status'] != 'family_brief_table_extracted'
                    and all(len(r) == 2 for r in table['rows'])):
                for label_cell, value_cell in table['rows']:
                    label, text = label_cell['text'].strip(), value_cell['text'].strip()
                    if label and label in values and text not in values[label].split('; '):
                        values[label] += '; ' + text
                    elif label:
                        values.setdefault(label, text)
            elif table.get('rows'):
                table = {k: v for k, v in table.items() if k != 'text'}
                key = hashlib.sha256(json.dumps(table['rows'], sort_keys=True).encode()).hexdigest()
                shared.setdefault(key, {'table': table, 'part_ids': []})['part_ids'].append(part['id'])
        for label in values:
            order.setdefault(label, len(order))
        rows.append({'id': part['id'], 'name': part['name'], 'part_number': part.get('part_number', ''),
                     'official_status': part.get('official_status', ''), 'listing': part.get('listing', ''),
                     'extraction_status': part['extraction_status'], 'source_url': part['source_url'],
                     'values': values})
    labels = sorted(order, key=lambda label: _column_rank(label, order[label]))
    with_values = [r for r in rows if r['values']]
    common = [{'label': label, 'value': with_values[0]['values'][label]} for label in labels
              if len(with_values) > 1 and all(r['values'].get(label) == with_values[0]['values'].get(label)
                                              for r in with_values)]
    common_labels = {c['label'] for c in common}
    shared_ids = {i for s in shared.values() for i in s['part_ids']}
    def count(values):
        result = {}
        for item in values:
            result[item] = result.get(item, 0) + 1
        return dict(sorted(result.items()))
    value['series'] = {
        'id': series['id'], 'name': series['name'], 'category': series['category'],
        'taxonomy': series.get('taxonomy', []), 'source_url': series['source_url'],
        'source_sha256': series['source_sha256'], 'observed_at': series['observed_at'],
        'navigation': classify(series, company),
        'parts': rows, 'columns': [label for label in labels if label not in common_labels], 'common': common,
        'shared_tables': [{**s['table'], 'part_ids': s['part_ids']} for s in shared.values()],
        'counts': {'parts': len(rows),
                   'with_specifications': sum(bool(r['values']) or r['id'] in shared_ids for r in rows),
                   'by_official_status': count(r['official_status'] or 'unspecified' for r in rows),
                   'by_listing': count(r['listing'] or 'unspecified' for r in rows)},
    }
    return value


def csv_export(value, mode='products', query='', kind='', with_specs=False, group='', family='', scope='all', company=None):
    company = company or value.get('company_id') or 'nvidia'
    classifier = lambda p: classify(p, company)
    # Vendor-path companies carry the vendor's own path and part status; NVIDIA
    # columns stay exactly as reviewed.
    vendor = company_config(company)['navigation'] == 'vendor_taxonomy'
    def searchable(p):
        return p['name'] + ' ' + p['category'] + (' ' + p['part_number'] if vendor and p.get('part_number') else '')
    products = [p for p in value['products'] if (not kind or p['kind'] == kind)
                and (not with_specs or p['tables'])
                and product_navigation.matches(p, group, family, scope, classifier)
                and query.casefold() in searchable(p).casefold()]
    def vendor_columns(p):
        path = product_navigation.taxonomy_path(p)
        return [' > '.join(str(step.get('name') or step['slug']) for step in path),
                ' > '.join(str(step['slug']) for step in path),
                p.get('official_status', ''), p.get('listing', ''), p.get('part_number', '')] if vendor else []
    vendor_headers = ['official_taxonomy', 'official_taxonomy_slugs', 'official_status', 'listing', 'part_number'] if vendor else []
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    def safe(text):
        text = str(text)
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
    def row(values):
        writer.writerow([safe(v) for v in values])
    if mode in {'products', 'map'}:
        row(['product_id', 'name', 'parent_id', 'official_category', 'entity_kind', 'availability', 'extraction_status', 'specification_tables', 'map_change_status', 'official_sitemap_match', 'official_sitemap_roles', 'official_sitemap_lastmod_claims', 'official_resource_urls', 'source_url', 'source_sha256', 'observed_at', 'display_group', 'display_family', 'navigation_role', *vendor_headers])
        for p in products:
            nav = classifier(p)
            sitemap = p.get('website_sitemap', {})
            row([p['id'], p['name'], p.get('parent_id', ''), p['category'], p['kind'], p['availability'], p['extraction_status'], len(p['tables']), p.get('map_change_status', ''), sitemap.get('matched', False), ' | '.join(sitemap.get('roles', [])), ' | '.join(sitemap.get('lastmod_claims', [])), ' | '.join(a['url'] for a in p.get('official_resources', [])), p['source_url'], p['source_sha256'], p['observed_at'], nav['group'], nav['family'], nav['role'], *vendor_columns(p)])
    elif mode == 'specs':
        row(['product_id', 'name', 'official_section', 'table', 'row', 'official_parameter', 'official_values', 'official_column_headers', 'official_cells_json', 'official_notes', 'source_url', 'source_sha256', 'table_evidence_urls', 'table_evidence_sha256', *(['part_number'] if vendor else [])])
        for p in products:
            for table in p['tables']:
                for n, cells in enumerate(table['rows'], 1):
                    first = table['rows'][0]
                    headers = ' | '.join(c['text'] for c in first[1:]) if not first[0]['text'] or all(c['header'] for c in first) else ''
                    refs = source_refs_for_table(table)
                    row([p['id'], p['name'], table['section'], table['index'], n, cells[0]['text'], ' | '.join(c['text'] for c in cells[1:]), headers, json.dumps(cells, ensure_ascii=False), table.get('notes', ''), p['source_url'], p['source_sha256'], ' | '.join(ref['url'] for ref in refs), ' | '.join(ref['sha256'] for ref in refs), *([p.get('part_number', '')] if vendor else [])])
    else:
        raise ValueError('unknown export')
    return '\ufeff' + stream.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['import', 'publish', 'status', 'export'])
    ap.add_argument('--company', choices=sorted(COMPANIES), default='nvidia')
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
        payload = validate(json.loads(args.input.read_text()), args.company)
        verify_snapshots(payload, args.archive_root)
        receipt = (receive(root, payload, args.company) if args.action == 'import'
                   else publish(payload, args.token_file, args.company))
        print(json.dumps(receipt, ensure_ascii=False))
    elif args.action == 'export':
        if not args.out:
            ap.error('--out required')
        args.out.write_text(csv_export(snapshot(root, args.company), args.mode, company=args.company), encoding='utf-8')
    else:
        s = snapshot(root, args.company)
        print(json.dumps({k: v for k, v in s.items() if k != 'products'}, ensure_ascii=False, indent=2))
