"""Bounded public company window; specifications and private research stay elsewhere."""
import json
import sqlite3
from inresearch.workflow import product_catalog

PROFILE_FIELDS = ('company_id', 'name', 'name_cn', 'legal_name', 'ticker', 'cik', 'roles',
                  'hq_country', 'hq_address', 'founded_year', 'employees', 'employees_as_of',
                  'ceo', 'website', 'ir_url', 'profile', 'profile_source', 'profile_as_of')


def company(root, cid):
    record = next((c for c in json.loads((root/'data/companies.json').read_text())['records']
                   if c['company_id'] == cid), None)
    if record is None:
        raise KeyError('unknown company')
    return {k: record[k] for k in PROFILE_FIELDS if k in record}


def catalog_groups(root, cid):
    """Select only navigation fields from SQLite; never load specification arrays."""
    if cid not in product_catalog.COMPANIES:
        return {'available': False, 'registered': False, 'groups': []}
    path = product_catalog.database(root, cid)
    if not path.is_file():
        return {'available': False, 'registered': True, 'groups': []}
    con = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    try:
        run = con.execute('SELECT id,generated FROM runs ORDER BY generated DESC LIMIT 1').fetchone()
        if run is None:
            return {'available': False, 'registered': True, 'groups': []}
        rows = con.execute("""SELECT json_extract(payload,'$.name') AS name,
            json_extract(payload,'$.source_url') AS source_url,
            json_extract(payload,'$.product_url') AS product_url,
            json_extract(payload,'$.taxonomy') AS taxonomy,
            json_extract(payload,'$.listing') AS listing
            FROM products WHERE run_id=?""", (run['id'],))
        groups = {}
        for row in rows:
            item = dict(row)
            item['taxonomy'] = json.loads(item['taxonomy']) if item['taxonomy'] else []
            nav = product_catalog.classify(item, cid)
            if not nav['group'] or nav['role'] != 'catalog':
                continue
            taxonomy = item['taxonomy']
            label = next((g['label'] for g in product_catalog.navigation_block([], cid)['groups']
                          if g['id'] == nav['group']), None)
            label = label or (taxonomy[0].get('name') if taxonomy else None) or nav['group']
            group = groups.setdefault(nav['group'], {'id': nav['group'], 'label': label, 'entities': 0, 'families': []})
            group['entities'] += 1
            if nav['family_label'] not in group['families'] and len(group['families']) < 4:
                group['families'].append(nav['family_label'])
        return {'available': True, 'registered': True, 'generated_at': run['generated'],
                'groups': sorted(groups.values(), key=lambda g: -g['entities'])[:12]}
    finally:
        con.close()


def snapshot(root, cid):
    profile = company(root, cid)
    disclosures = json.loads((root/'data/company_disclosures.json').read_text())
    record = next((r for r in disclosures['records'] if r['company_id'] == cid), {})
    lines = record.get('product_lines') or []
    if not lines:
        for r in json.loads((root/'data/products.json').read_text())['records']:
            if r['company_id'] == cid and r.get('product_line') not in [v['name'] for v in lines]:
                lines.append({'name': r['product_line'], 'description': r.get('category') or r.get('segment') or '',
                              'query': r['product_line'], 'basis': 'registered_product_line'})
    try:
        catalog = catalog_groups(root, cid)
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        catalog = {'available': False, 'status': 'error', 'groups': []}
    return {'company': profile, 'companies': [{'id': c['company_id'], 'name': c.get('name_cn') or c['name']}
                for c in json.loads((root/'data/companies.json').read_text())['records']],
            'product_lines': lines[:12], 'catalog': catalog,
            'financials': record.get('financials', [])[:24], 'checked_at': record.get('checked_at')}
