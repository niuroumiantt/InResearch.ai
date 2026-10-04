"""Product-line coverage measured against the delivered specification catalog (规格库).

``data/products.json`` is the industry-chain denominator: 175 product lines, each with
free-text representative models.  This module splits those models into tags and looks
each tag up in the company's catalog (the same SQLite delivery ``product-catalog.html``
reads).  A tag is covered when a catalog entity carries that model name; the link then
points to that entity in the catalog.  Companies without a registered catalog are
reported as such, never as zero coverage of an existing catalog.

Nothing here adopts research facts: a match only says the catalog holds an entity of
that name, with or without official specification tables.
"""
import json
import re

from inresearch.paths import project_root
from inresearch.workflow import product_catalog

# Product lines registered under a vendor's business unit share the parent's catalog
# (the 规格库 is one database per vendor).  Only units whose products the parent's
# official site actually lists belong here.
CATALOG_OF = {'nvidia-networking': 'nvidia', 'amd-instinct': 'amd', 'amd-pensando': 'amd',
              'huawei-atlas': 'huawei-ascend'}

_CJK = re.compile(r'[一-鿿]')
_PAREN = re.compile(r'[（(][^）)]*[）)]')
_SKIP = re.compile(r'^(第|全|各|其他|新一?代|主流|重点)')


def model_tags(text):
    """Split a representative-models string into model tags (port of the former page helper)."""
    tags = []
    for part in re.split(r'[、;；]', _PAREN.sub('', text or '')):
        part = part.strip()
        if not part:
            continue
        pieces = [x.strip() for x in part.split('/')]
        if '/' in part and len(part) < 40 and all(re.match(r'[A-Za-z0-9]', x) for x in pieces):
            tail = (re.search(r'\s+(.+)$', pieces[-1]) or [None, ''])[1]
            for piece in pieces:
                head = re.sub(r'\s+.*$', '', piece)
                tags.append(head + (' ' + tail if tail and tail not in piece and not _CJK.search(tail) else ''))
        else:
            tags.append(part)
    result = []
    for tag in tags:
        if re.match(r'[A-Za-z0-9]', tag):
            cut = _CJK.search(tag)
            if cut and cut.start() > 1:
                tag = tag[:cut.start()].strip()
        if 1 < len(tag) < 40 and not _SKIP.match(tag) and re.search(r'[A-Za-z0-9]{2}', tag) and tag not in result:
            result.append(tag)
    return result


def norm(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value or '').casefold()).strip('-')


def match(tag, entities):
    """Catalog entities whose name contains the tag as whole hyphen-separated words.

    Exact names first, then products with specification tables, then shorter names,
    so the link lands on the most specific entity with evidence.
    """
    key = norm(tag)
    if not key:
        return []
    hits = [e for e in entities if ('-' + e['key'] + '-').find('-' + key + '-') >= 0]
    return sorted(hits, key=lambda e: (e['key'] != key, not e['tables'], len(e['key']), e['name']))


_CACHE = {}


def _catalog_entities(root, company):
    """Names of the latest delivery; cached per database file version (snapshots are large)."""
    path = product_catalog.database(root, company)
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return None
    cached = _CACHE.get((str(path), company))
    if cached and cached[0] == stamp:
        return cached[1]
    value = product_catalog.snapshot(root, company)
    entities = ([{'id': p['id'], 'name': p['name'], 'key': norm(p['name']), 'tables': bool(p.get('tables'))}
                 for p in value['products']] if value.get('available') else None)
    _CACHE[(str(path), company)] = (stamp, entities)
    return entities


def coverage(root=None):
    root = root or project_root()
    records = json.loads((root / 'data/products.json').read_text())['records']
    catalogs = {}
    lines = []
    for index, record in enumerate(records):
        company = CATALOG_OF.get(record['company_id'], record['company_id'])
        registered = company in product_catalog.COMPANIES
        if registered and company not in catalogs:
            catalogs[company] = _catalog_entities(root, company)
        entities = catalogs.get(company)
        tags = []
        for tag in model_tags(record.get('representative_models')):
            hits = match(tag, entities) if entities else []
            best = hits[0] if hits else None
            tags.append({'tag': tag, 'matches': len(hits),
                         'product_id': best and best['id'], 'product_name': best and best['name'],
                         'with_tables': bool(best and best['tables'])})
        lines.append({
            'key': str(index), 'company_id': record['company_id'],
            'company_cn': record.get('company_cn', ''), 'company_en': record.get('company_en', ''),
            'sheet': record.get('sheet', ''), 'category': record.get('category', ''),
            'product_line': record.get('product_line', ''), 'priority': record.get('priority', ''),
            'representative_models': record.get('representative_models', ''),
            # registered: a 规格库 receiving point exists; available: Fetchspec has delivered into it.
            'catalog': {'company': company if registered else None,
                        'registered': registered, 'available': entities is not None},
            'tags': tags,
            'covered': sum(t['matches'] > 0 for t in tags),
        })
    with_catalog = [line for line in lines if line['catalog']['available']]
    return {
        'basis': 'model_tags_matched_against_delivered_catalog_names',
        'acceptance': 'catalog_entity_present_not_research_adopted',
        'lines': lines,
        'totals': {
            'lines': len(lines),
            'lines_with_catalog': len(with_catalog),
            'catalog_companies': sorted(c for c, e in catalogs.items() if e is not None),
            'tags_in_catalog_lines': sum(len(line['tags']) for line in with_catalog),
            'tags_covered': sum(line['covered'] for line in with_catalog),
        },
    }
