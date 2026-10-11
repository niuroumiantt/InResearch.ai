"""Bounded native XLSX evidence; no Excel, formula evaluation or network access."""
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
CELL = r'[A-Z]{1,3}[1-9][0-9]{0,6}'
LOCATOR = re.compile(r'xlsx:sheet:([1-9][0-9]*):cell:('+CELL+r'):context:('+CELL+r'):('+CELL+r')')


def coordinates(address):
    match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})', address)
    if not match:
        raise ValueError('xlsx_cell_required')
    column = 0
    for letter in match[1]:
        column = column * 26 + ord(letter) - 64
    row = int(match[2])
    if column > 16384 or row > 1048576:
        raise ValueError('xlsx_cell_outside_limits')
    return column, row


class Workbook:
    """Parse once per source and freeze explicit rectangular review contexts.

    Values are original XML strings. Date serials, error cells and cached
    formulas are never guessed or evaluated; named review remains independent.
    """
    def __init__(self, path):
        path = Path(path)
        if path.suffix.lower() != '.xlsx':
            raise ValueError('native_xlsx_source_required')
        if path.stat().st_size > 20_000_000:
            raise ValueError('xlsx_source_too_large')
        try:
            with ZipFile(path) as archive:
                entries = archive.infolist()
                names = [x.filename for x in entries]
                if (len(entries) > 10000 or len(set(names)) != len(names)
                        or sum(x.file_size for x in entries) > 50_000_000
                        or any(x.flag_bits & 1 or x.file_size > 20_000_000 for x in entries)):
                    raise ValueError('xlsx_archive_limits')
                def xml(name):
                    raw = archive.read(name)
                    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
                        raise ValueError('xlsx_xml_entities_forbidden')
                    return ET.fromstring(raw)
                shared = []
                if 'xl/sharedStrings.xml' in names:
                    shared = [''.join(n.itertext()) for n in xml('xl/sharedStrings.xml').findall('m:si', NS)]
                book = xml('xl/workbook.xml')
                properties = book.find('m:workbookPr', NS)
                self.date1904 = properties is not None and properties.get('date1904') in ('1', 'true')
                relationships = {n.get('Id'): n for n in xml('xl/_rels/workbook.xml.rels')}
                self.sheets = []
                for sheet in book.findall('m:sheets/m:sheet', NS):
                    relationship = relationships[sheet.get('{'+REL+'}id')]
                    target = relationship.get('Target', '')
                    if relationship.get('TargetMode') == 'External' or '\\' in target or ':' in target:
                        raise ValueError('xlsx_external_sheet_forbidden')
                    member = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl', target))
                    if not member.startswith('xl/') or '..' in PurePosixPath(member).parts:
                        raise ValueError('xlsx_sheet_path_forbidden')
                    tree = xml(member)
                    cells = {}
                    for c in tree.findall('m:sheetData/m:row/m:c', NS):
                        address = c.get('r', '')
                        coordinates(address)
                        if address in cells or len(cells) >= 250000:
                            raise ValueError('xlsx_duplicate_or_excess_cells')
                        value = c.find('m:v', NS)
                        value = value.text if value is not None else None
                        kind = c.get('t', 'n')
                        if kind == 's':
                            index = int(value)
                            if not 0 <= index < len(shared):
                                raise ValueError('xlsx_shared_string_required')
                            value = shared[index]
                        elif kind == 'inlineStr':
                            inline = c.find('m:is', NS)
                            value = ''.join(inline.itertext()) if inline is not None else ''
                        formula = c.find('m:f', NS)
                        cells[address] = {'cell': address, 'type': kind, 'value': value,
                                          'formula': ET.tostring(formula, encoding='unicode') if formula is not None else None,
                                          'style': c.get('s')}
                    merges = [n.get('ref', '') for n in tree.findall('m:mergeCells/m:mergeCell', NS)]
                    self.sheets.append({'name': sheet.get('name'), 'cells': cells, 'merged_ranges': merges})
        except (BadZipFile, KeyError, ET.ParseError, TypeError, IndexError) as exc:
            raise ValueError('invalid_native_xlsx') from exc

    def select(self, locator):
        match = LOCATOR.fullmatch(str(locator))
        if not match or int(match[1]) > len(self.sheets):
            raise ValueError('native_xlsx_locator_required')
        index = int(match[1]); address = match[2]
        left, top = coordinates(match[3]); right, bottom = coordinates(match[4])
        x, y = coordinates(address)
        if (left > right or top > bottom or (right-left+1)*(bottom-top+1) > 4096
                or not (left <= x <= right and top <= y <= bottom)):
            raise ValueError('bounded_xlsx_context_required')
        sheet = self.sheets[index-1]
        cell = sheet['cells'].get(address)
        if not cell or cell['value'] in (None, '') or cell['formula'] is not None or cell['type'] in ('e', 'b'):
            raise ValueError('xlsx_native_nonformula_value_required')
        selected = []
        for item in sheet['cells'].values():
            cx, cy = coordinates(item['cell'])
            if left <= cx <= right and top <= cy <= bottom:
                selected.append(item)
        merges = []
        for merged in sheet['merged_ranges']:
            a, b = merged.split(':') if ':' in merged else (merged, merged)
            mx, my = coordinates(a); nx, ny = coordinates(b)
            if not (nx < left or mx > right or ny < top or my > bottom):
                if not (left <= mx <= nx <= right and top <= my <= ny <= bottom):
                    raise ValueError('xlsx_context_cuts_merged_header')
                merges.append(merged)
        selected.sort(key=lambda n: (coordinates(n['cell'])[1], coordinates(n['cell'])[0]))
        context = json.dumps({'sheet_index': index, 'sheet_name': sheet['name'],
                              'range': match[3]+':'+match[4], 'date1904': self.date1904,
                              'merged_ranges': merges, 'cells': selected},
                             ensure_ascii=False, sort_keys=True, allow_nan=False)
        if len(context) > 2_000_000:
            raise ValueError('xlsx_context_too_large')
        return cell, context


def matches_value(cell, value):
    if isinstance(value, str):
        return value == cell['value']
    if cell['type'] == 'n' and type(value) in (int, float):
        try:
            native, proposed = Decimal(cell['value']), Decimal(str(value))
            return native.is_finite() and proposed.is_finite() and native == proposed
        except (InvalidOperation, TypeError):
            pass
    return False
