"""Reader-facing physical campus identity, roles and field-level provenance.

Geography is recorded explicitly. A city, campus name or approximate coordinate
is never a deduplication key; only the reviewed canonical site_id links records.
"""
import copy
import math
import re
from urllib.parse import urlsplit

ACTOR_ROLES = {
    'land_owner': '土地权利人', 'owner': '资产所有者', 'developer': '开发方',
    'designer': '设计方', 'builder': 'EPC／总包', 'operator': '运营方',
    'tenant': '直接使用／承租方', 'end_user': '最终使用者',
    'investor': '股权出资方', 'lender': '贷款方', 'borrower': '借款主体',
    'guarantor': '担保方', 'lessor': '租约出租方',
    'power_supplier': '供电服务方', 'water_supplier': '供水服务方',
    'network_provider': '网络服务方',
}
GEOGRAPHY_FIELDS = ('province', 'city', 'district', 'street_address', 'parcel_ids')


def _sources(rows):
    result = []
    for source in rows:
        try:
            url = urlsplit(source.get('url', ''))
            if url.scheme in ('http', 'https') and url.hostname and not url.username and not url.password:
                result.append({key: source.get(key) for key in ('url', 'date', 'grade', 'note')})
        except (ValueError, AttributeError):
            continue
    return result


def geography(row):
    address = ' · '.join(row[key] for key in ('city', 'district', 'street_address') if row.get(key))
    result = {'country': row.get('country'), **{
        key: copy.deepcopy(row.get(key)) for key in GEOGRAPHY_FIELDS},
        'regional_address': address or row.get('location') or '',
        'location_description': row.get('location'),
        'identity': row.get('site_id'),
        'identity_scope': 'portfolio' if 'portfolio' in row.get('site_id', '') else
            'cluster' if row.get('identity_scope') == 'cluster' else
            row.get('identity_scope', 'registered_site')}
    if row.get('coordinate_source'):
        # Byte/receiver audit and local locators stay in the private source record.
        result['coordinate_source'] = {k: row['coordinate_source'].get(k) for k in
            ('precision', 'coordinate_system', 'method', 'url', 'basis')}
    return result


def provenance(row, field):
    selected = row.get('tracking', {}).get('fields', {}).get(field)
    observations = row.get('observations', [])
    if selected:
        observation = next((r for r in observations if r.get('id') == selected['observation_id']), {})
        return {'effective_at': selected['effective_at'], 'reviewed_at': selected['reviewed_at'],
                'observation_id': selected['observation_id'], 'kind': selected['kind'],
                **{k: selected.get(k) for k in ('registration_status','selection_at','selection_time_basis')},
                'source_versions': [{key: version.get(key) for key in
                    ('source_sha256', 'published_at', 'first_received_at')}
                    for version in observation.get('source_versions', [])],
                'sources': _sources(observation.get('sources', []))}
    # A source publication date or legacy verification date is not observation time.
    assessment = row.get('capacity_assessment') or {}
    return {'effective_at': assessment.get('as_of') if field.startswith('capacity_it_') else None,
            'reviewed_at': row.get('verified_date'), 'observation_id': None,
            'kind': 'legacy_registration', 'source_versions': [],
            'sources': _sources(row.get('sources', []))}


def participants(row):
    return [{'role': key, 'label': label, 'company_ids': copy.deepcopy(row[key]),
             **provenance(row, key)} for key, label in ACTOR_ROLES.items() if row.get(key)]


def capacities(row):
    """Planned total is independent of legacy stage buckets, never their sum."""
    native = row.get('quantity_fields') or {}
    planned = copy.deepcopy(native.get('capacity_planned_it_mw', row.get('capacity_planned_it_mw')))
    return {'planned': {'quantity': planned, 'boundary': 'whole_site',
                         **provenance(row, 'capacity_planned_it_mw')},
            'operating': {'boundary': 'registered_operating_phases',
                          **provenance(row, 'capacity_it_mw_by_status' if
                              row.get('capacity_it_mw_by_status') else 'capacity_it_mw')}}


INITIAL_IDENTITY_KEYS = frozenset(('version', 'site_id', 'name', 'country', 'region', 'location',
                                  'native_name', 'basis', 'province', 'city', 'district', 'street_address',
                                  'coordinates', 'coordinate_source'))
COORDINATE_SOURCE_KEYS = frozenset(('precision', 'coordinate_system', 'method', 'source_sha256',
                                   'url', 'locator', 'basis'))


def check_initial_coordinates(identity):
    """Optional source-located WGS84 point, never an inferred city centroid."""
    if not isinstance(identity, dict):
        raise ValueError('initial_identity_object_required')
    present = {'coordinates', 'coordinate_source'} & identity.keys()
    if not present:
        return
    if len(present) != 2:
        raise ValueError('coordinates_and_source_required_together')
    value, source = identity['coordinates'], identity['coordinate_source']
    if (not isinstance(value, str) or len(value) > 100 or not re.fullmatch(
            r'\s*[+-]?\d+(?:\.\d+)?\s*,\s*[+-]?\d+(?:\.\d+)?\s*', value)):
        raise ValueError('initial_coordinates_lat_lon_required')
    lat, lon = (float(v) for v in value.split(','))
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('initial_coordinates_out_of_range')
    if (not isinstance(source, dict) or set(source) != COORDINATE_SOURCE_KEYS
            or source.get('precision') not in ('address', 'site', 'building')
            or source.get('coordinate_system') != 'WGS84'
            or source.get('method') not in ('address_geocode', 'source_map', 'reported_coordinates')
            or source.get('method') == 'address_geocode' and source.get('precision') != 'address'
            or not re.fullmatch('[0-9a-f]{64}', str(source.get('source_sha256', '')))
            or any(not isinstance(source.get(k), str) or not source[k].strip()
                   or len(source[k]) > limit for k, limit in (('locator', 1000), ('basis', 4000)))):
        raise ValueError('initial_coordinate_source_required')
    url = source.get('url')
    try:
        parsed = urlsplit(url)
        parsed.port
        if (not isinstance(url, str) or len(url) > 4096 or re.search(r'\s|[\x00-\x1f\x7f]', url)
                or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('initial_coordinate_source_https_required') from None


def check_initial_identity(identity, project=None):
    """Explicit reviewed campus anchor; an address or coordinates may be unknown."""
    required = {'version', 'site_id', 'name', 'country', 'region', 'location', 'native_name', 'basis'}
    if (not isinstance(identity, dict) or not required <= identity.keys()
            or set(identity) - INITIAL_IDENTITY_KEYS or type(identity['version']) is not int
            or identity['version'] != 1
            or any(not isinstance(identity[k], str) or not identity[k].strip()
                   for k in identity if k not in ('version', 'coordinate_source'))
            or len(identity['country']) != 2 or not identity['country'].isascii()
            or not identity['country'].isupper() or not identity['country'].isalpha()
            or 'portfolio' in identity['site_id'] or len(identity['native_name'].strip()) < 4):
        raise ValueError('reviewed_initial_physical_identity_required')
    check_initial_coordinates(identity)
    if project is not None and (project.get('duplicate_of') or project.get('identity_scope') in ('cluster', 'portfolio')
            or any(project.get(k) != v for k, v in identity.items() if k not in ('version', 'basis', 'native_name'))):
        raise ValueError('initial_physical_identity_mismatch')
    return identity
