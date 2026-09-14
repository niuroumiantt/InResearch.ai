"""OOXML XML text, worksheets and drawings."""
from __future__ import annotations
import re, zipfile
from pathlib import Path
from inresearch.adapters.office_grid import MAX_CHARS, COL_REF, col_index, is_date_format, number_text, grid_text, MERGE_MARK


XML_ENTITIES = (('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'),
                ('&#39;', "'"), ('&apos;', "'"), ('&amp;', '&'))

SI = re.compile(r'<si\b[^>]*>(.*?)</si>', re.S)

T_RUN = re.compile(r'<t[^>]*>(.*?)</t>', re.S)

CELL = re.compile(r'<c\b([^>]*?)(?:/>|>(.*?)</c>)', re.S)

ATTR = re.compile(r'(\w+)="([^"]*)"')

V = re.compile(r'<v[^>]*>(.*?)</v>', re.S)

NUM_FMT = re.compile(r'<numFmt[^>]*\bnumFmtId="(\d+)"[^>]*\bformatCode="([^"]*)"')

CELL_XFS = re.compile(r'<cellXfs\b[^>]*>(.*?)</cellXfs>', re.S)

XF_FMT = re.compile(r'<xf\b[^>]*?\bnumFmtId="(\d+)"')

ROW = re.compile(r'<row\b([^>]*?)(?:/>|>(.*?)</row>)', re.S)

MERGE_REF = re.compile(r'<mergeCell[^>]*\bref="([A-Z]+)(\d+):([A-Z]+)(\d+)"')


def merge_ranges(xml: str) -> list[tuple[int, int, int, int]]:
    """<mergeCell ref="A5:D5"/> -> [(row1, col1, row2, col2)]，列从 0 起。"""
    out = []
    for c1, r1, c2, r2 in MERGE_REF.findall(xml):
        try:
            out.append((int(r1), col_index(c1 + r1), int(r2), col_index(c2 + r2)))
        except ValueError:
            continue
    return out


def mark_merges(cells: dict, xml: str, max_cells: int = MAX_CHARS) -> dict:
    """Fill the covered cells of every merged range with a continuation mark.

    Only where the top-left actually has a value and the covered cell is
    empty: a mark written over a value would invent a span that is not there,
    and an empty range is nothing to say anything about.
    """
    remaining = max_cells
    for r1, c1, r2, c2 in merge_ranges(xml):
        if not (0 < r1 <= r2 and 0 <= c1 <= c2):
            raise ValueError('invalid_merged_cell_range')
        if (r1, c1) not in cells:
            continue
        area = (r2 - r1 + 1) * (c2 - c1 + 1)
        if area > remaining:
            raise ValueError('merged_cell_expansion_exceeds_extraction_budget')
        remaining -= area
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                if (r, c) != (r1, c1):
                    cells.setdefault((r, c), MERGE_MARK)
    return cells


DRAWING = re.compile(r'xl/drawings/drawing\d+\.xml')

A_PARA = re.compile(r'<a:p(?:\s[^>]*)?>(.*?)</a:p>', re.S)

A_RUN = re.compile(r'<a:t[^>]*>(.*?)</a:t>', re.S)

def _xml_text(blob: bytes) -> str:
    text = re.sub(rb'<[^>]+>', b' ', blob).decode('utf-8', 'ignore')
    return re.sub(r'[ \t]+', ' ', text)

def unescape(text: str) -> str:
    for entity, char in XML_ENTITIES:      # &amp; last, or &amp;lt; double-decodes
        text = text.replace(entity, char)
    return text

def shared_strings(xml: str) -> list[str]:
    """One entry per <si>, runs joined.

    Collecting every <t> in the file instead would flatten rich text into
    separate entries and shift every index after the first formatted cell -
    so a workbook with one bold word in one header would mislabel the rest.
    """
    return [unescape(''.join(T_RUN.findall(item))) for item in SI.findall(xml)]

def date_styles(xml: str) -> list[bool]:
    """Per cell-format index: does it render its number as a date?"""
    custom = {int(i): code for i, code in NUM_FMT.findall(xml)}
    block = CELL_XFS.search(xml)
    if not block:
        return []
    return [is_date_format(custom.get(int(fid)), int(fid))
            for fid in XF_FMT.findall(block.group(1))]

def sheet_cells(xml: str, strings: list[str], dated: list[bool]) -> dict:
    """Cells keyed by (row, column), both zero-based on the column.

    Position comes from each element's r="B7" where it exists and from the
    element's place in its row where it does not.  Excel always writes r, but
    a generator that omits it still means "the next column", and dropping
    those cells silently would repeat the bug this function exists to fix.
    """
    blocks = ROW.findall(xml)
    if not blocks:
        blocks = [('', xml)]
    cells = {}
    for n, (row_attrs, row_body) in enumerate(blocks, start=1):
        stated = dict(ATTR.findall(row_attrs)).get('r')
        row = int(stated) if (stated or '').isdigit() else n
        cells.update(row_cells(row_body, row, strings, dated))
    return cells

def row_cells(xml: str, row: int, strings: list[str], dated: list[bool]) -> dict:
    cells, position = {}, 0
    for attrs, body in CELL.findall(xml):
        a = dict(ATTR.findall(attrs))
        ref = a.get('r', '')
        column = col_index(ref) if COL_REF.match(ref) else position
        position = column + 1
        kind = a.get('t', 'n')
        if kind == 'inlineStr':
            value = unescape(''.join(T_RUN.findall(body))).strip()
        else:
            raw = V.search(body)
            if not raw:
                continue
            raw = unescape(raw.group(1)).strip()
            if kind == 's':
                value = strings[int(raw)] if raw.isdigit() and int(raw) < len(strings) else ''
            elif kind in ('str', 'e'):
                value = raw
            elif kind == 'b':
                value = 'TRUE' if raw == '1' else 'FALSE'
            else:
                try:
                    style = int(a.get('s', -1))
                except ValueError:
                    style = -1
                is_date = 0 <= style < len(dated) and dated[style]
                try:
                    value = number_text(float(raw), is_date)
                except ValueError:
                    value = raw
        if value != '':
            cells[(row, column)] = value
    return cells

def drawing_text(z, names) -> list[tuple[str, int]]:
    """Text boxes, watermarks and shape labels - the text that is not in a cell.

    A workbook's publisher is often nowhere in its cells.  688d46ed carried
    「知识星球：Global Semi Research」 as a watermark repeated across five
    drawings and nothing else; the cell reader saw none of it, so L1 judged the
    file 出处未知 with the attribution sitting inside it the whole time.

    Returned as (line, times) rather than deduplicated away: a watermark on
    every sheet and a one-off label are different things, and the count is what
    tells them apart.
    """
    lines = {}
    for name in sorted(n for n in names if DRAWING.fullmatch(n)):
        try:
            xml = z.read(name).decode('utf-8', 'ignore')
        except (KeyError, zipfile.BadZipFile):
            continue
        for para in A_PARA.findall(xml):
            line = unescape(''.join(A_RUN.findall(para))).strip()
            if line:
                lines[line] = lines.get(line, 0) + 1
    return list(lines.items())

def xlsx_text(path: Path, limit: int = MAX_CHARS) -> tuple[str, dict]:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        sheets = []
        if 'xl/workbook.xml' in names:
            wb = z.read('xl/workbook.xml').decode('utf-8', 'ignore')
            sheets = [unescape(n) for n in
                      re.findall(r'<sheet[^>]*\bname="([^"]*)"', wb)]
        strings = []
        if 'xl/sharedStrings.xml' in names:
            strings = shared_strings(z.read('xl/sharedStrings.xml').decode('utf-8', 'ignore'))
        dated = []
        if 'xl/styles.xml' in names:
            dated = date_styles(z.read('xl/styles.xml').decode('utf-8', 'ignore'))
        files = sorted((n for n in names if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', n)),
                       key=lambda n: int(re.search(r'(\d+)', n.rsplit('/', 1)[1]).group(1)))
        grids, inline = [], 0
        for i, n in enumerate(files):
            label = sheets[i] if i < len(sheets) else n.rsplit('/', 1)[1]
            xml = z.read(n).decode('utf-8', 'ignore')
            if not strings:
                inline += len(T_RUN.findall(xml))
            grids.append((label, mark_merges(sheet_cells(xml, strings, dated), xml, limit)))
        shapes = drawing_text(z, names)

    body, counts = grid_text(grids, limit)
    # shared_strings stays in meta: it is what the redo pass was judged on, and
    # a workbook that suddenly reports far fewer of them has lost something.
    # shared_strings keeps its old meaning - text entries the sheet can draw
    # on, inline ones included - so the numbers recorded for 35,895 files still
    # mean what they meant.  `cells` is the new measure and the honest one.
    meta = {'sheets': len(sheets), 'shared_strings': len(strings) or inline,
            'drawing_lines': len(shapes), **counts}
    parts = []
    if sheets:
        parts.append('工作表: ' + ' | '.join(sheets))
    if shapes:
        # Ahead of the grid on purpose: L1 judges on a preview, and a preview
        # of a workbook is column headers.  Attribution that lands after the
        # cells is attribution L1 will never see.
        parts.append('文本框/水印:\n' + '\n'.join(
            '  ' + line + ('  ×%d' % times if times > 1 else '')
            for line, times in shapes))
    if MERGE_MARK in body:
        # 一次就够：读者需要知道这个符号是什么，不需要每行都被提醒一遍。
        parts.append('%s = 与左上角同属一个合并单元格，值只写在左上角那一格'
                     % MERGE_MARK)
    if body:
        parts.append(body)
    else:
        # No addressable cells - a chart-only sheet, or a shape holding the
        # text.  Fall back to the labels rather than returning nothing.
        parts.extend(s for s in (t.strip() for t in strings) if s)
    text = '\n'.join(parts)
    meta['truncated'] = meta.get('truncated', False) or len(text) > limit
    return text[:limit], meta

def ooxml_text(path: Path, limit: int = MAX_CHARS) -> tuple[str, dict]:
    """Route a zip container by what is inside it, not by its suffix."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    if 'xl/workbook.xml' in names:
        return xlsx_text(path, limit)
    with zipfile.ZipFile(path) as z:
        wanted = [n for n in sorted(names)
                  if n == 'word/document.xml' or n.startswith('ppt/slides/slide')
                  or n.startswith('visio/pages/page')]
        parts, total = [], 0
        for n in wanted:
            t = _xml_text(z.read(n)); parts.append(t); total += len(t)
            if total > limit: break
    return '\n'.join(parts)[:limit], {'parts': len(wanted),
                                      'truncated': total > limit}
