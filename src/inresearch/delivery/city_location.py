"""Append city representative points with independent campus and gazetteer evidence.

This operator-only path never creates a campus or rewrites its initial identity.
Original files stay private; only a labelled approximate map point is projected.
"""
import copy
from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path
import re
import shutil
import tempfile
from zipfile import ZipFile

from inresearch.adapters.xlsx_document import Workbook, coordinates
from inresearch.materials import inbox, native_review_contract
from inresearch.storage.files import locked, write_json_streaming
from inresearch.storage.layout import workspace_path

SOURCE_URL = 'https://download.geonames.org/export/dump/CN.zip'
# Explicit identity columns from the reviewed native layouts, never guessed.
COLUMNS = {'mainland-register-v6': ('B', 'D', 'E'),
           'mainland-register-v5': ('B', 'D', 'E'),
           'dahai-campus-v1': ('B', 'G', 'H'),
           'national-campus-v1': ('F', 'C', 'D')}
ITEM_KEYS = {'site_id', 'submission_id', 'source_sha256', 'sheet', 'name_cell',
             'province_cell', 'city_cell', 'geoname_id', 'geonames_line'}


def _sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def _name(value):
    # Only administrative suffix variants; no substring/fuzzy/name translation.
    return re.sub(r'(壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|省|市)$', '', value.strip())


def _matches(value, fields):
    return _name(value) in {_name(text) for text in [fields[1], fields[2], *fields[3].split(',')] if text}


def _geography(path, sha, items):
    if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha) or _sha(path) != sha:
        raise ValueError('city_geography_bytes_changed')
    wanted = {item['geonames_line'] for item in items}
    selected, provinces = {}, {}
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if (len(entries) > 100 or len({row.filename for row in entries}) != len(entries)
                or 'CN.txt' not in archive.namelist()):
            raise ValueError('city_geography_archive_invalid')
        info = archive.getinfo('CN.txt')
        if info.flag_bits & 1 or info.file_size > 300_000_000:
            raise ValueError('city_geography_archive_limits')
        with archive.open('CN.txt') as raw:
            stream = io.TextIOWrapper(raw, encoding='utf-8', errors='strict')
            number = 0
            while True:
                line = stream.readline(65537)
                if not line: break
                number += 1
                if len(line) > 65536: raise ValueError('city_geography_line_too_large')
                text = line.rstrip('\r\n'); fields = text.split('\t')
                if number in wanted:
                    if len(fields) != 19: raise ValueError('city_geography_record_invalid')
                    selected[number] = (fields, text)
                if len(fields) == 19 and fields[6:9] == ['A', 'ADM1', 'CN']:
                    provinces.setdefault(fields[10], []).append((number, fields, text))
    if set(selected) != wanted or _sha(path) != sha:
        raise ValueError('city_geography_bytes_or_locator_changed')
    return selected, provinces


def _membership_source(item):
    """Load one approved original; callers keep it within one validation phase."""
    record = inbox.worker_record(item['submission_id'])
    if record['sha256'] != item['source_sha256']:
        raise ValueError('city_membership_source_changed')
    original = inbox.record_path(item['submission_id']) / 'content'
    # The intake stores extensionless originals. Parse an exact private copy.
    with tempfile.TemporaryDirectory(prefix='inresearch-city-source-') as directory:
        target = Path(directory) / 'source.xlsx'
        shutil.copyfile(original, target)
        if _sha(target) != item['source_sha256']:
            raise ValueError('city_membership_source_changed')
        book = Workbook(target)
    layout_id = native_review_contract.detect_layout(book)
    return book, layout_id


def _membership_from_source(item, book, layout_id):
    layout = native_review_contract.LAYOUTS[layout_id]
    if item['sheet'] != layout['main']:
        raise ValueError('city_membership_main_sheet_required')
    cells = next(sheet['cells'] for sheet in book.sheets if sheet['name'] == item['sheet'])
    addresses = [item[key] for key in ('name_cell', 'province_cell', 'city_cell')]
    parsed = [coordinates(address) for address in addresses]
    if (len({row for _, row in parsed}) != 1 or parsed[0][1] <= 1
            or [re.match('[A-Z]+', address)[0] for address in addresses] != list(COLUMNS[layout_id])):
        raise ValueError('city_membership_identity_columns_required')
    values = []
    for address in addresses:
        cell = cells.get(address, {})
        value = cell.get('value')
        if cell.get('formula') is not None or not isinstance(value, str) or not value.strip():
            raise ValueError('city_membership_literal_required')
        values.append(value)
    return {'submission_id': item['submission_id'], 'source_sha256': item['source_sha256'],
            'layout_id': layout_id, 'sheet': item['sheet'],
            'cells': {key: {'cell': address, 'value': value} for key, address, value in
                      zip(('name', 'province', 'city'), addresses, values)}}


def _memberships(items):
    """Share parsing per exact submission/SHA, never across validation phases.

    Process one original at a time. Only small, independent membership proofs
    survive the group; complete workbooks are not retained for the batch.
    """
    groups = {}
    for index, item in enumerate(items):
        groups.setdefault((item['submission_id'], item['source_sha256']), []).append(index)
    result = [None] * len(items)
    for indexes in groups.values():
        book, layout_id = _membership_source(items[indexes[0]])
        for index in indexes:
            result[index] = _membership_from_source(items[index], book, layout_id)
        del book
    return result


def _membership(item):
    return _memberships([item])[0]


def _point(item, membership, selected, provinces, sha):
    fields, text = selected[item['geonames_line']]
    city = membership['cells']['city']['value']; province = membership['cells']['province']['value']
    administrative = fields[6:8] == ['A', 'ADM2']
    accepted_type = administrative or fields[6] == 'P' and fields[7] in ('PPLC', 'PPLA', 'PPLA2')
    if (fields[0] != item['geoname_id'] or not accepted_type
            or fields[8] != 'CN' or not fields[10] or not fields[11] or not _matches(city, fields)):
        raise ValueError('city_geography_identity_mismatch')
    if administrative and city.strip() not in [fields[1], fields[2], *fields[3].split(',')]:
        raise ValueError('city_administrative_exact_name_required')
    admins = [entry for entry in provinces.get(fields[10], []) if _matches(province, entry[1])]
    if len(admins) != 1: raise ValueError('city_geography_province_mismatch')
    from inresearch.knowledge import site_register
    point = fields[4] + ',' + fields[5]
    site_register.check_wgs84_point(point)
    source = {'precision': 'city', 'coordinate_system': 'WGS84', 'method': 'city_reference', 'feature_code': fields[7],
              'source_sha256': sha, 'url': 'https://www.geonames.org/' + fields[0] + '/',
              'locator': 'CN.txt:' + str(item['geonames_line']),
              'basis': '城市级定位（园区精确位置待补）；GeoNames 城市代表点，非园区实址或行政几何质心；CC BY 4.0。'}
    if administrative:
        source['basis'] = '城市级定位（园区精确位置待补）；GeoNames 地级行政区参考点，非园区地址或行政几何质心；CC BY 4.0。'
    return {'version': 1, 'site_id': item['site_id'], 'coordinates': point, 'coordinate_source': source,
            'province': province, 'city': city, 'membership': membership,
            'geography': {'source_sha256': sha, 'source_url': SOURCE_URL, 'member': 'CN.txt',
                          'line': item['geonames_line'], 'geoname_id': fields[0], 'feature_class': fields[6],
                          'feature_code': fields[7], 'native_line': text,
                          'province_line': admins[0][0], 'province_native_line': admins[0][2],
                          'license': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/'}}


def install(root, payload, geography_path):
    """Validate both originals before an immutable, CAS-protected publication."""
    from inresearch.delivery import source_publication as publication
    if (not isinstance(payload, dict) or set(payload) != {'version', 'expected_state_sha', 'geography_sha256', 'sites'}
            or type(payload['version']) is not int or payload['version'] != 1
            or not re.fullmatch('[0-9a-f]{64}', str(payload['expected_state_sha']))
            or not isinstance(payload['sites'], list) or not 1 <= len(payload['sites']) <= 500):
        raise ValueError('bounded_city_location_batch_required')
    items = payload['sites']; seen = set()
    for item in items:
        if (not isinstance(item, dict) or set(item) != ITEM_KEYS
                or any(not isinstance(item[k], str) or not item[k].strip() or len(item[k]) > 200 for k in ITEM_KEYS - {'geonames_line'})
                or item['site_id'] in seen
                or not re.fullmatch('[0-9a-f]{64}', item['source_sha256'])
                or not re.fullmatch('[1-9][0-9]{0,12}', item['geoname_id'])
                or type(item['geonames_line']) is not int or not 1 <= item['geonames_line'] <= 2_000_000):
            raise ValueError('unique_city_location_identity_required')
        seen.add(item['site_id'])
    selected, provinces = _geography(geography_path, payload['geography_sha256'], items)
    memberships = _memberships(items)
    prepared = [_point(item, membership, selected, provinces, payload['geography_sha256'])
                for item, membership in zip(items, memberships)]
    # Context CAS is execution bookkeeping, not the identity of the append.
    key = publication.digest({'kind': 'city_location', 'version': 1, 'sites': prepared})
    path = workspace_path(publication.PATH, root)
    with locked(path):
        previous = publication.state(root)
        if key in previous['receipts']:
            return {**previous['receipts'][key], 'state': 'already_published', 'new_locations': 0}
        if publication.digest(previous) != payload['expected_state_sha']:
            raise ValueError('source_publication_context_changed')
        projects = {row['site_id']: row for row in publication.projects(root, previous)['records']}
        for point in prepared:
            row = projects.get(point['site_id'])
            if (not row or row.get('country') != 'CN' or row.get('duplicate_of')
                    or row.get('identity_scope') in ('cluster', 'portfolio') or 'portfolio' in point['site_id']):
                raise ValueError('existing_unique_city_site_required')
            if row.get('coordinates') or row.get('coordinate_source') or previous['sites'].get(point['site_id'], {}).get('city_location'):
                raise ValueError('existing_location_cannot_be_changed')
            name = point['membership']['cells']['name']['value']
            if name not in {row.get('name'), (row.get('identity_registration') or {}).get('native_name')}:
                raise ValueError('city_site_name_binding_mismatch')
            if any(row.get(field) and _name(row[field]) != _name(point[field]) for field in ('province', 'city')):
                raise ValueError('city_site_geography_conflict')
            refs = [ref for observation in row.get('observations', [])
                    if observation.get('fields', {}).get('name') == name
                    for ref in observation.get('adoption', {}).get('document_refs', [])]
            if not any(ref.get('source_sha256') == point['membership']['source_sha256'] for ref in refs):
                raise ValueError('city_membership_not_registered_for_site')
        updated = {name: value if name == 'records' else copy.deepcopy(value) for name, value in previous.items()}
        stamp = datetime.now(timezone.utc).isoformat()
        for point in prepared:
            target = updated['sites'].setdefault(point['site_id'], {'baseline': None, 'observations': []})
            target['city_location'] = {**point, 'registered_at': stamp}
        receipt = {'batch_id': key, 'state': 'published', 'kind': 'city_location', 'site_ids': sorted(seen),
                   'new_locations': len(prepared), 'new_sites': 0, 'new_records': 0,
                   'published_at': stamp, 'truth_checked': False, 'precision': 'city'}
        updated['receipts'][key] = receipt
        # Recheck originals immediately before publishing the durable pointer.
        if _sha(geography_path) != payload['geography_sha256']: raise ValueError('city_geography_bytes_changed')
        # Build fresh proofs from approved originals inside the publication lock.
        # The initial phase's parsed sources must never satisfy this recheck.
        verified = _memberships(items)
        if verified != memberships: raise ValueError('city_membership_source_changed')
        write_json_streaming(path, updated)
    return receipt


def project(row, location):
    """A code baseline with a later precise point always wins; audit is retained."""
    if not row.get('coordinates') and not row.get('coordinate_source'):
        if any(row.get(field) and _name(row[field]) != _name(location[field]) for field in ('province', 'city')):
            raise ValueError('city_location_conflicts_with_site')
        row['coordinates'] = location['coordinates']
        row['coordinate_source'] = copy.deepcopy(location['coordinate_source'])
        for field in ('province', 'city'):
            if not row.get(field): row[field] = location[field]
