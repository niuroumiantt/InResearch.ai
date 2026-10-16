"""Deterministic complete native-cell packets for explicitly supported campus tables.

The layout is server code, never an instruction supplied by a workbook. Packets
preserve every original value and formula; ambiguous rows stay unassigned.
"""
import hashlib
import json
import re
import uuid
from collections import defaultdict

from inresearch.adapters.xlsx_document import coordinates
from inresearch.materials.native_review_layouts import LAYOUTS

VERSION = 'native-campus-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _address(column, row):
    letters = ''
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters + str(row)


def _context(sheet, address):
    left, top = coordinates(address); right, bottom = left, top
    changed = True
    while changed:
        changed = False
        for merged in sheet['merged_ranges']:
            start, end = merged.split(':') if ':' in merged else (merged, merged)
            ax, ay = coordinates(start); bx, by = coordinates(end)
            if not (bx < left or ax > right or by < top or ay > bottom):
                bounds = min(left, ax), min(top, ay), max(right, bx), max(bottom, by)
                if bounds != (left, top, right, bottom):
                    left, top, right, bottom = bounds; changed = True
        if (right-left+1)*(bottom-top+1) > 4096:
            raise ValueError('native_packet_merged_context_too_large')
    return _address(left, top), _address(right, bottom)


def _native_cells(book):
    cells, rows = {}, defaultdict(dict)
    for index, sheet in enumerate(book.sheets, 1):
        for address, native in sheet['cells'].items():
            if native['value'] in (None, '') and native['formula'] is None:
                continue
            start, end = _context(sheet, address)
            locator = f'xlsx:sheet:{index}:cell:{address}:context:{start}:{end}'
            value = {'sheet': sheet['name'], 'sheet_index': index, 'cell': address,
                     'locator': locator, **{key: native[key] for key in ('value', 'formula', 'type', 'style')}}
            cells[(index, address)] = value
            rows[index].setdefault(coordinates(address)[1], []).append(value)
    for table in rows.values():
        for line in table.values():
            line.sort(key=lambda cell: coordinates(cell['cell'])[0])
    return cells, rows


def _value(line, column):
    return next((str(cell['value']) for cell in line if re.match(r'[A-Z]+', cell['cell'])[0] == column
                 and cell['value'] is not None and cell['formula'] is None), '').strip()


def detect_layout(book):
    matches = []
    for name in LAYOUTS:
        try:
            _check_layout(book, name)
            matches.append(name)
        except ValueError:
            pass
    if len(matches) != 1:
        raise ValueError('native_review_layout_unknown_or_ambiguous')
    return matches[0]


def _check_layout(book, layout_id):
    layout = LAYOUTS.get(layout_id)
    if layout is None:
        raise ValueError('native_review_layout_unknown')
    sheets = {sheet['name']: sheet for sheet in book.sheets}
    if len(sheets) != len(book.sheets) or set(sheets) != set(layout['sheets']):
        raise ValueError('native_review_layout_sheet_mismatch')
    for name, descriptor in layout['sheets'].items():
        if descriptor.get('headers'):
            actual = {address: cell['value'] for address, cell in sheets[name]['cells'].items()
                      if coordinates(address)[1] == descriptor['header_row'] and cell['value'] not in (None, '')}
            if actual != descriptor['headers']:
                raise ValueError('native_review_layout_header_mismatch')
        for address, expected in descriptor.get('headers', {}).items():
            cell = sheets[name]['cells'].get(address)
            if not cell or cell['value'] != expected or cell['formula'] is not None:
                raise ValueError('native_review_layout_header_mismatch')
    return layout


def _references(text, known):
    tokens = set(re.findall(r'[A-Za-z0-9][A-Za-z0-9_.-]*', text))
    return sorted(tokens.intersection(known))


def _identity_eligibility(book, rows, names, layout_id, key, campus):
    """Ordinary source registration only; no table label grants C3 verification."""
    if layout_id == 'mainland-register-v6':
        index = names['12-对象关系与计数资格']
        matching = [line for row, line in rows[index].items() if row > 1 and _value(line, 'A') == key]
        if len(matching) != 1:
            return False, '对象关系表缺少唯一同ID身份记录，待核物理范围'
        line = matching[0]
        kind, parent, qualification = _value(line, 'C'), _value(line, 'D'), _value(line, 'F')
        if parent:
            return False, '原件列有父对象关系，不能把子项自动新建为独立园区'
        allowed = {'园区（总园区）', '园区（单体）（自动归类，待人工复核）', '园区（单体）'}
        if kind not in allowed or not qualification.startswith('计入1次') or re.search(r'待核|疑似|重复', qualification):
            return False, '原件对象类型或计数资格未明确为独立园区：'+kind+'；'+qualification
        for sheet_index, row in campus['rows']:
            if sheet_index != names['1-地点与身份']: continue
            address = ' '.join(_value(rows[sheet_index][row], col) for col in ('G', 'K'))
            if re.search(r'(租用|租赁).*(楼|栋)|(楼|栋).*(租用|租赁)', address, re.S):
                return False, '原件地点为租用楼栋，物理母园区关系尚未解决'
        return True, '原件按同ID列明独立或总园区；仅作基础来源登记，自动归类仍待复核'
    if layout_id == 'dahai-campus-v1':
        line = next(rows[index][row] for index, row in campus['rows'] if index == names['园区主表'])
        if _value(line, 'X') != '已核验':
            return False, '该表园区身份仍为基础登记待查，需补可复验的独立园区依据'
        if re.search(r'集群|多址|楼栋|分期|疑似|租用|租赁', _value(line, 'B')+' '+_value(line, 'K')):
            return False, '原件名称或边界仍含子项、多址或租赁范围，需先核对独立园区'
        return True, '原件主表声明园区身份并有设施从属记录；只登记未核实来源，不提升C3'
    return False, '该布局没有已登记的独立园区身份裁定列，保留研究与身份补证任务'


def build_manifest(book, source_sha, layout_id=None):
    """Rebuild all campus, shared-evidence and unassigned packets from native bytes."""
    if not isinstance(source_sha, str) or not re.fullmatch(r'[a-f0-9]{64}', source_sha):
        raise ValueError('native_review_source_sha_required')
    layout_id = layout_id or detect_layout(book)
    layout = _check_layout(book, layout_id)
    cells, rows = _native_cells(book)
    names = {sheet['name']: index for index, sheet in enumerate(book.sheets, 1)}
    main_index = names[layout['main']]
    main = layout['sheets'][layout['main']]
    keyed = defaultdict(list)
    for row, line in rows[main_index].items():
        if row > main.get('header_row', 1):
            key, name = _value(line, main['id_col']), _value(line, main['name_col'])
            if key and name:
                keyed[key].append((row, name))
    campuses = {key: {'name': entries[0][1], 'rows': {(main_index, entries[0][0])}}
                for key, entries in keyed.items() if len(entries) == 1}
    lookup = {}
    for name, descriptor in layout['sheets'].items():
        if descriptor.get('role') != 'lookup':
            continue
        index = names[name]; records = defaultdict(list)
        for row, line in rows[index].items():
            if row > descriptor.get('header_row', 1):
                key = _value(line, descriptor['id_col'])
                if key: records[key].append((index, row))
        lookup[name] = {key: entries[0] for key, entries in records.items() if len(entries) == 1}
    for name, descriptor in layout['sheets'].items():
        if descriptor.get('role') != 'campus' or name == layout['main']:
            continue
        index = names[name]
        for row, line in rows[index].items():
            if row <= descriptor.get('header_row', 1): continue
            key = _value(line, descriptor['id_col'])
            if key in campuses:
                campuses[key]['rows'].add((index, row))
    packets, assigned = [], set()
    for key, campus in sorted(campuses.items()):
        selected = set(campus['rows'])
        pending = list(selected)
        while pending:
            index, row = pending.pop()
            descriptor = layout['sheets'][book.sheets[index-1]['name']]
            for column, target in descriptor.get('references', {}).items():
                mapping = lookup[target]
                for ref in _references(_value(rows[index][row], column), mapping):
                    linked = mapping[ref]
                    if linked not in selected:
                        selected.add(linked); pending.append(linked)
        packet = _packet(book, rows, selected, layout, source_sha, layout_id,
                         'campus', key, campus['name'], owned=selected-assigned)
        packet['identity_cells'] = [cell for index, row in sorted(campus['rows'])
                                    if index == main_index for cell in rows[index][row]]
        packet['identity_eligible'], packet['identity_reason'] = _identity_eligibility(
            book, rows, names, layout_id, key, campus)
        packets.append(packet)
        assigned.update(selected)
    for index, table in sorted(rows.items()):
        remaining = sorted(row for row in table if (index, row) not in assigned)
        groups, group, count = [], set(), 0
        for row in remaining:
            if group and count + len(table[row]) > 200:
                groups.append(group); group, count = set(), 0
            group.add((index, row)); count += len(table[row])
        if group: groups.append(group)
        for ordinal, group in enumerate(groups, 1):
            packets.append(_packet(book, rows, group, layout, source_sha, layout_id,
                                   'unassigned', f'sheet:{index}:part:{ordinal}', book.sheets[index-1]['name']))
    covered = {(cell['sheet_index'], cell['cell']) for packet in packets for cell in packet['cells']}
    if covered != set(cells):
        raise ValueError('native_review_manifest_incomplete')
    manifest = {'version': VERSION, 'layout_id': layout_id, 'source_sha256': source_sha,
                'date1904': book.date1904, 'total_nonblank_cells': len(cells),
                'packets': packets}
    manifest['manifest_sha256'] = digest(manifest)
    return manifest


def _packet(book, rows, selected, layout, source_sha, layout_id, kind, key, name, owned=None):
    evidence = set(selected); context = set()
    owned = evidence if owned is None else owned
    for index, _ in selected:
        descriptor = layout['sheets'][book.sheets[index-1]['name']]
        if descriptor.get('header_row') in rows[index]:
            context.add((index, descriptor['header_row']))
    selected = selected | context
    content = [cell for index, row in sorted(selected) for cell in rows[index][row]]
    evidence_locators = [cell['locator'] for index, row in sorted(evidence-context)
                        for cell in rows[index][row]]
    packet = {'kind': kind, 'campus_key': key, 'campus_name': name,
              'cells': content, 'cells_sha256': digest(content),
              'header_cells': [cell for index, row in sorted(context) for cell in rows[index][row]],
              'owned_locators': [cell['locator'] for index, row in sorted(owned) for cell in rows[index][row]],
              'evidence_locators': evidence_locators,
              'row_refs': [[index, row] for index, row in sorted(evidence)]}
    packet['package_id'] = digest({'version': VERSION, 'layout_id': layout_id,
                                   'source_sha256': source_sha, 'packet': packet})
    return packet


def make_scope(manifest, packet, attempt_id, task_sha):
    uuid.UUID(attempt_id)
    if not isinstance(task_sha, str) or not re.fullmatch(r'[a-f0-9]{64}', task_sha):
        raise ValueError('native_review_task_sha_required')
    return {'mode': 'full_native_campus', 'version': VERSION, 'attempt_id': attempt_id,
            'layout_id': manifest['layout_id'], 'manifest_sha256': manifest['manifest_sha256'],
            'package_id': packet['package_id'], 'source_sha256': manifest['source_sha256'],
            'task_sha256': task_sha, 'cells_sha256': packet['cells_sha256'],
            'cell_count': len(packet['cells']), 'total_packages': len(manifest['packets']),
            'owned_cell_count': len(packet['owned_locators']),
            'total_nonblank_cells': manifest['total_nonblank_cells'],
            'kind': packet['kind'], 'campus_key': packet['campus_key'],
            'identity_eligible': packet.get('identity_eligible', False),
            'identity_reason': packet.get('identity_reason', '未归属内容不得创建园区')}


def analysis_id(attempt_id, package_id, task_sha):
    return str(uuid.uuid5(uuid.UUID(attempt_id), package_id + ':' + task_sha))


def validate_windows(packet, windows):
    """Prove lossless source-fragment coverage for the successful model requests."""
    if not isinstance(windows, list) or not 1 <= len(windows) <= 2000:
        raise ValueError('native_review_windows_required')
    texts = {cell['locator']: '' if cell['value'] is None else str(cell['value'])
             for cell in packet['cells']}
    coverage = defaultdict(list)
    for window in windows:
        if not isinstance(window, dict) or set(window) != {'fragments', 'input_sha256', 'model'}:
            raise ValueError('native_review_window_invalid')
        model = window['model']
        if (not isinstance(model, dict) or model.get('backend') != 'ollama'
                or model.get('requested') != 'qwen3.8:27b' or model.get('actual') != 'qwen3.8:27b'
                or model.get('input_sha256') != window['input_sha256']
                or any(not isinstance(model.get(key), str) or not re.fullmatch(r'[a-f0-9]{64}', model[key])
                       for key in ('input_sha256', 'prompt_sha256'))):
            raise ValueError('native_review_window_model_mismatch')
        if not isinstance(window['fragments'], list) or not 1 <= len(window['fragments']) <= 10000:
            raise ValueError('native_review_window_fragments_required')
        for fragment in window['fragments']:
            if not isinstance(fragment, dict) or set(fragment) != {'locator', 'start', 'end', 'value_sha256'}:
                raise ValueError('native_review_fragment_invalid')
            text = texts.get(fragment['locator'])
            start, end = fragment['start'], fragment['end']
            if (text is None or type(start) is not int or type(end) is not int
                    or not 0 <= start <= end <= len(text) or start == end and text):
                raise ValueError('native_review_fragment_bounds_invalid')
            if hashlib.sha256(text[start:end].encode()).hexdigest() != fragment['value_sha256']:
                raise ValueError('native_review_fragment_hash_mismatch')
            coverage[fragment['locator']].append((start, end))
    if set(coverage) != set(texts):
        raise ValueError('native_review_window_coverage_incomplete')
    for locator, text in texts.items():
        end = 0
        for start, stop in sorted(coverage[locator]):
            if start > end:
                raise ValueError('native_review_window_coverage_incomplete')
            end = max(end, stop)
        if end != len(text):
            raise ValueError('native_review_window_coverage_incomplete')


def validate_scope(book, record, payload):
    scope = payload.get('review_scope'); attempt = record.get('full_analysis') or {}
    if (not isinstance(scope, dict) or scope.get('attempt_id') != attempt.get('attempt_id')
            or attempt.get('state') not in ('running', 'continuing')
            or scope.get('layout_id') != attempt.get('layout_id')):
        raise ValueError('explicit_full_review_attempt_required')
    manifest = build_manifest(book, record['sha256'], attempt['layout_id'])
    if (manifest['manifest_sha256'] != attempt.get('manifest_sha256')
            or [row['package_id'] for row in manifest['packets']] != attempt.get('package_ids')):
        raise ValueError('native_review_manifest_changed')
    packet = next((row for row in manifest['packets'] if row['package_id'] == scope.get('package_id')), None)
    if packet is None:
        raise ValueError('native_review_package_unknown')
    expected = make_scope(manifest, packet, attempt['attempt_id'], payload['task_provenance']['sha256'])
    if scope != expected:
        raise ValueError('native_review_scope_mismatch')
    if payload['analysis_id'] != analysis_id(attempt['attempt_id'], packet['package_id'], scope['task_sha256']):
        raise ValueError('native_review_analysis_id_mismatch')
    if packet['package_id'] not in attempt.get('available_package_ids', []):
        raise ValueError('native_review_package_not_released')
    if packet['package_id'] in attempt.get('completed_package_ids', []):
        raise ValueError('native_review_package_already_completed')
    if packet['kind'] != 'campus' and payload['candidates']:
        raise ValueError('unassigned_native_content_cannot_publish')
    allowed = {cell['locator'] for cell in packet['cells']}
    evidence = set(packet['evidence_locators'])
    locations = {(cell['sheet'], cell['cell']) for cell in packet['cells']}
    identity = {cell['locator'] for cell in packet.get('identity_cells', [])}
    for candidate in payload['candidates']:
        if not isinstance(candidate, dict): raise ValueError('native_review_candidate_required')
        for key in ('name_locator', 'location_locator', 'locator', 'unit_locator'):
            locator = candidate.get(key)
            if key == 'unit_locator' and not locator: continue
            if locator not in allowed:
                raise ValueError('native_review_candidate_outside_packet')
        if candidate['locator'] not in evidence:
            raise ValueError('native_review_candidate_uses_context_only')
        if (candidate.get('site_name') != packet['campus_name']
                or candidate.get('name_locator') not in identity
                or candidate.get('location_locator') not in identity):
            raise ValueError('native_review_candidate_identity_outside_master')
    if any(not isinstance(row, dict) or (row.get('sheet'), row.get('cell')) not in locations
           for row in payload['findings']):
        raise ValueError('native_review_finding_outside_packet')
    validate_windows(packet, payload.get('review_windows'))
    adjudication = payload.get('campus_adjudication')
    if (not isinstance(adjudication, dict)
            or set(adjudication) != {'input_sha256','model','candidate_sha256'}):
        raise ValueError('native_review_campus_adjudication_required')
    model = adjudication['model']
    if (not isinstance(model, dict) or model.get('backend') != 'ollama'
            or model.get('requested') != 'qwen3.8:27b' or model.get('actual') != 'qwen3.8:27b'
            or model.get('input_sha256') != adjudication['input_sha256']
            or any(not isinstance(model.get(key), str) or not re.fullmatch(r'[a-f0-9]{64}', model[key])
                   for key in ('input_sha256','prompt_sha256'))
            or payload['model'] != model
            or adjudication['candidate_sha256'] != digest(payload['candidates'])):
        raise ValueError('native_review_campus_adjudication_mismatch')
    return scope
