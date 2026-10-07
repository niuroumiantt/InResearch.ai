"""Bounded public company window; specifications and private research stay elsewhere."""
import json
import sqlite3
from inresearch.workflow import product_catalog, product_navigation

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
    """Read a bounded index from the current received run, including unclassified items.

    SQLite returns identities, navigation and table counts only. Specification
    cells, private payload fields and original bytes never leave this projection.
    """
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
        rows = con.execute("""SELECT json_extract(payload,'$.id') AS id,
            json_extract(payload,'$.name') AS name,
            json_extract(payload,'$.kind') AS kind,
            json_extract(payload,'$.source_url') AS source_url,
            json_extract(payload,'$.product_url') AS product_url,
            json_extract(payload,'$.taxonomy') AS taxonomy,
            json_extract(payload,'$.listing') AS listing,
            COALESCE(json_array_length(payload,'$.tables'),0) AS table_count
            FROM products WHERE run_id=? ORDER BY id""", (run['id'],))
        groups, lines = {}, {v['id']: {**v, 'entities': 0, 'named_products': 0,
            'named_with_tables': 0, 'with_tables': 0, 'examples': []}
            for v in product_navigation.COMPANY_LINES.get(cid, [])}
        summary = {'entities': 0, 'named_products': 0, 'named_with_tables': 0,
                   'with_tables': 0, 'specification_tables': 0, 'without_vendor_taxonomy': 0,
                   'auxiliary_entities': 0, 'unmapped_entities': 0}
        known_labels = {g['id']: g['label'] for g in product_catalog.navigation_block([], cid)['groups']}
        def add(bucket, item):
            bucket['entities'] += 1
            bucket['with_tables'] += bool(item['table_count'])
            named = item['kind'] == 'named_product'
            bucket['named_products'] += named
            bucket['named_with_tables'] += named and bool(item['table_count'])
            if named and item['id'] and len(bucket['examples']) < 2:
                bucket['examples'].append({'id': item['id'], 'name': item['name'],
                                          'table_count': item['table_count']})
        for row in rows:
            item = dict(row)
            item['taxonomy'] = json.loads(item['taxonomy']) if item['taxonomy'] else []
            summary['entities'] += 1
            summary['named_products'] += item['kind'] == 'named_product'
            summary['with_tables'] += bool(item['table_count'])
            summary['named_with_tables'] += item['kind'] == 'named_product' and bool(item['table_count'])
            summary['specification_tables'] += item['table_count']
            summary['without_vendor_taxonomy'] += not bool(item['taxonomy'])
            nav = product_catalog.classify(item, cid)
            if nav['group'] and nav['role'] == 'catalog':
                taxonomy = item['taxonomy']
                label = known_labels.get(nav['group']) or (taxonomy[0].get('name') if taxonomy else None) or nav['group']
                group = groups.setdefault(nav['group'], {'id': nav['group'], 'label': label,
                    'entities': 0, 'named_products': 0, 'named_with_tables': 0,
                    'with_tables': 0, 'examples': [], 'families': []})
                add(group, item)
                if nav['family_label'] not in group['families'] and len(group['families']) < 4:
                    group['families'].append(nav['family_label'])
            else:
                summary['auxiliary_entities'] += 1
            line = product_navigation.company_line(item, cid)
            if line in lines:
                add(lines[line], item)
            else:
                summary['unmapped_entities'] += 1
        return {'available': True, 'registered': True, 'generated_at': run['generated'],
                'run_id': run['id'], 'summary': summary,
                'mapping_basis': 'official_product_path_display_association' if lines else 'delivered_vendor_taxonomy',
                'business_lines': list(lines.values()),
                'material_count': con.execute('SELECT count(*) FROM materials').fetchone()[0] if con.execute("SELECT 1 FROM sqlite_master WHERE name='materials'").fetchone() else 0,
                'groups': sorted(groups.values(), key=lambda g: (-g['entities'], g['id']))[:12]}
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
    if catalog.get('available'):
        mapped = {v['id']: v for v in catalog.get('business_lines', [])}
        if mapped:
            lines = [{**line, **mapped.get(line.get('id'), {}), 'filter': {'line': line.get('id'), 'scope': 'all'}}
                     for line in lines]
        else:
            lines = [{**group, 'name': group['label'], 'description': ' / '.join(group['families']),
                      'basis': 'received_vendor_taxonomy', 'filter': {'group': group['id']}}
                     for group in catalog['groups']]
            if catalog['summary']['auxiliary_entities']:
                lines.append({'name': '目录与待归类资料', 'description': '已收录，原厂分类待补齐',
                              'entities': catalog['summary']['auxiliary_entities'],
                              'filter': {'scope': 'auxiliary'}, 'basis': 'received_catalog_index'})
    return {'company': profile, 'companies': [{'id': c['company_id'], 'name': c.get('name_cn') or c['name']}
                for c in json.loads((root/'data/companies.json').read_text())['records']],
            'product_lines': lines[:13], 'catalog': catalog,
            'financials': record.get('financials', [])[:24], 'checked_at': record.get('checked_at')}
