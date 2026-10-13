"""Explicit customer product views, independent of acquisition/research payloads.

Only received official product identities, original specification cells and their
public source links are copied. Unknown fields at every declared record level
are dropped; internal snapshots remain intact. CSV uses this same full view.
"""
from collections import Counter
import math
from urllib.parse import urlsplit

_DROP = object()


def _atom(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return _DROP


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else _DROP


def _text(value):
    return value if isinstance(value, str) else _DROP


def _url(value):
    if not isinstance(value, str):
        return _DROP
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return _DROP


def _copy(value, schema):
    if callable(schema):
        return schema(value)
    if isinstance(schema, list):
        if not isinstance(value, list):
            return _DROP
        return [result for item in value if (result := _copy(item, schema[0])) is not _DROP]
    if not isinstance(value, dict):
        return _DROP
    return {key: result for key, item in value.items() if key in schema
            and (result := _copy(item, schema[key])) is not _DROP}


def _fields(names):
    return {key: _atom for key in names.split()}


def _nullable(schema):
    return lambda value: None if value is None else _copy(value, schema)


def _counts(names):
    allowed = set(names.split())
    return lambda value: {key: count for key, count in value.items()
                          if key in allowed and type(count) is int and count >= 0} if isinstance(value, dict) else _DROP


SOURCE = {**_fields('label kind sha256'), 'url': _url}
RESOURCE = {**_fields('label kind format content_type access_status sha256 source_sha256 language filename'),
            'url': _url, 'source_url': _url}
TAXONOMY = {**_fields('slug name'), 'url': _url}
CELL = _fields('text colspan rowspan header')
TABLE = {**_fields('index section notes'), 'rows': [[CELL]], 'source_refs': [SOURCE], 'part_ids': [_text]}
NAVIGATION = {**_fields('version group family family_label role basis status'), 'official_source': _url}
BROWSE_NODE = _fields('id label entities named_products with_tables')
PARAMETER = _fields('label value')
COMPANY = {**_fields('id label navigation country parent_company_id entity_type'), 'products_url': _url}
COMPUTE = {**_fields('category form architecture version basis evidence_quote architecture_quote'),
           'source_refs': [SOURCE],
           'chip_links': [{**_fields('product_id evidence_quote'), 'source_refs': [SOURCE]}]}
PRODUCT = {**_fields('id name company_id parent_id category kind availability extraction_status observed_at '
                     'map_change_status seen_in_latest_run table_count company_line official_status listing part_number'),
           'source_url': _url, 'product_url': _url, 'source_sha256': _text,
           'categories': [_text], 'taxonomy': [TAXONOMY], 'navigation': NAVIGATION,
           'compute': COMPUTE, 'tables': [TABLE], 'attachments': [RESOURCE],
           'official_resources': [RESOURCE], 'official_pages': [SOURCE],
           'website_sitemap': {**_fields('matched'), 'roles': [_text], 'lastmod_claims': [_text]},
           'browse_path': [BROWSE_NODE], 'parameters': [PARAMETER],
           'brief_decoded': _fields('capacity form_factor')}
GROUP_COUNT = {**_fields('id label entities with_tables'),
               'families': [_fields('id label entities with_tables')]}
COVERAGE_COUNT = {'with_tables': _number, 'total': _number}
SUMMARY = {'basis': _text, 'entities': _number,
           'by_kind': _counts('named_product family_or_directory software_service'),
           'by_listing': _counts('active obsolete directory unspecified'), 'by_group': [GROUP_COUNT],
           'specification_coverage': {'named_products': COVERAGE_COUNT, 'current_named_products': COVERAGE_COUNT,
                                      'all_entities': COVERAGE_COUNT, 'obsolete_listed': _number}}
CATALOG = {**_fields('available company_id generated_at acceptance view'), 'company': COMPANY,
           'registered_companies': [COMPANY], 'products': [PRODUCT], 'summary': SUMMARY,
           'company_lines': [_fields('id name entities')], 'coverage': _fields('complete'),
           'navigation': {**_fields('version official_source basis status'), 'groups': [_fields('id label')]}}
BROWSE = {**_fields('available company_id version basis generated_at category total_entities total_named_products '
                    'matched offset limit'), 'roots': [BROWSE_NODE], 'children': [BROWSE_NODE],
          'breadcrumb': [BROWSE_NODE], 'items': [PRODUCT]}
MATERIAL = {**_fields('id format name basis link_count'), 'urls': [_url],
            'links': [{**_fields('product_id product_name label source_sha256 current_product'),
                       'url': _url, 'source_url': _url}]}
MATERIALS = {**_fields('available company_id total matched unassigned offset limit basis'), 'items': [MATERIAL]}



# The company window is a separate bounded projection. Its source disclosure
# records and display-association lines can grow independently of this contract.
WINDOW_EXAMPLE = _fields('id name table_count')
WINDOW_COUNTS = _fields('entities named_products named_with_tables with_tables')
WINDOW_LINE = {**_fields('id name label description basis query'), **WINDOW_COUNTS,
               'source_url': _url, 'examples': [WINDOW_EXAMPLE], 'families': [_text],
               'filter': _fields('line scope group family category q kind with_specs')}
WINDOW_PROFILE = {**_fields('company_id name name_cn legal_name ticker cik hq_country hq_address '
                            'founded_year employees employees_as_of ceo website profile profile_as_of'),
                  'roles': [_text], 'ir_url': _url, 'profile_source': _url}
WINDOW_SUMMARY = _fields('entities named_products named_with_tables with_tables specification_tables '
                         'without_vendor_taxonomy auxiliary_entities unmapped_entities')
WINDOW_CATALOG = {**_fields('available registered status generated_at mapping_basis material_count'),
                  'summary': WINDOW_SUMMARY, 'business_lines': [WINDOW_LINE],
                  'groups': [{**_fields('id label'), **WINDOW_COUNTS,
                              'examples': [WINDOW_EXAMPLE], 'families': [_text]}]}
WINDOW_FINANCIAL = {**_fields('period kind period_end form source summary_status'), 'url': _url}
COMPANY_WINDOW = {'company': WINDOW_PROFILE, 'companies': [_fields('id name')],
                  'product_lines': [WINDOW_LINE], 'catalog': WINDOW_CATALOG,
                  'financials': [WINDOW_FINANCIAL], 'checked_at': _atom}


def project_company_window(value):
    """Copy only company facts, report citations and delivered catalog counts.

    Acquisition run IDs, unknown disclosure metadata and unknown business-line
    filters are omitted at every nesting level, without changing internal data.
    """
    if not isinstance(value, dict):
        raise ValueError('company window response must be an object')
    return _copy(value, COMPANY_WINDOW)



COMPANY_QUOTE = {key: _nullable(_text) for key in
                 'symbol currency as_of market_status provider retrieved_at delay_note ticker status'.split()}
COMPANY_QUOTE.update({key: _nullable(_number) for key in
                      'price market_cap change change_percent retrieved_epoch'.split()})
COMPANY_QUOTE.update(source_url=_nullable(_url),
                     refreshing=lambda value: value if type(value) is bool else _DROP)


def project_company_quote(value):
    """Keep verified quote scalars, never nested cache/provider bookkeeping."""
    if not isinstance(value, dict):
        raise ValueError('company quote response must be an object')
    return _copy(value, COMPANY_QUOTE)


def _series(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        return _DROP
    result = _copy(value, {**_fields('id name category source_sha256 observed_at'), 'source_url': _url,
                          'taxonomy': [TAXONOMY], 'navigation': NAVIGATION, 'columns': [_text],
                          'common': [PARAMETER], 'shared_tables': [TABLE]})
    labels = set(result.get('columns', [])) | {item.get('label') for item in result.get('common', [])}
    result['parts'] = []
    for part in value.get('parts', []) if isinstance(value.get('parts'), list) else []:
        row = _copy(part, {**_fields('id name part_number official_status listing extraction_status'), 'source_url': _url})
        if row is _DROP:
            continue
        row['values'] = {key: text for key, text in part.get('values', {}).items()
                         if key in labels and isinstance(text, str)} if isinstance(part.get('values'), dict) else {}
        result['parts'].append(row)
    counts = _copy(value.get('counts', {}), {'parts': _number, 'with_specifications': _number})
    result['counts'] = counts if counts is not _DROP else {}
    # Vendor status labels are open-ended; derive their counts from the delivered
    # parts instead of accepting arbitrary future bookkeeping map keys.
    for field in ('official_status', 'listing'):
        result['counts']['by_' + field] = dict(sorted(Counter(row.get(field) or 'unspecified' for row in result['parts']).items()))
    return result


def project(value, view='full'):
    """Return a new, closed customer JSON view; never mutate the internal value."""
    if not isinstance(value, dict):
        raise ValueError('catalog response must be an object')
    base = _fields('available company_id generated_at acceptance')
    schemas = {'full': CATALOG, 'index': CATALOG,
               'summary': {key: child for key, child in CATALOG.items() if key != 'products'},
               'product': {**base, 'product': _nullable(PRODUCT)},
               'series': {**base, 'series': _series}, 'browse': BROWSE, 'materials': MATERIALS}
    if view not in schemas:
        raise ValueError('unknown customer catalog view')
    return _copy(value, schemas[view])


def csv_export(value, mode='products', *args, **filters):
    """Keep existing export/filter/escaping semantics over only customer fields."""
    from inresearch.workflow.product_catalog import csv_export as export
    return export(project(value, 'full'), mode, *args, **filters)
