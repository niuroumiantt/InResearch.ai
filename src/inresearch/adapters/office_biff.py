"""BIFF worksheet records to an addressable text grid."""
from __future__ import annotations
import struct
from inresearch.adapters.office_container import OleFile
from inresearch.adapters.office_grid import MAX_CHARS, no_text_layer, is_date_format, number_text, grid_text


SST = 0x00FC

CONTINUE = 0x003C

BOUNDSHEET = 0x0085

BOF = 0x0809

SHEET_SUBSTREAM = 0x0010     # a BOF of this kind opens a worksheet

FORMAT_REC = 0x041E

XF_REC = 0x00E0

LABELSST = 0x00FD

LABEL_REC = 0x0204

RSTRING = 0x00D6             # LABEL plus run formatting; the text sits the same

NUMBER_REC = 0x0203

RK_REC = 0x027E

MULRK_REC = 0x00BD

FORMULA_REC = 0x0006

STRING_REC = 0x0207          # carries a formula's string result

BOOLERR_REC = 0x0205

CELL_RECORDS = {LABELSST, LABEL_REC, RSTRING, NUMBER_REC, RK_REC, MULRK_REC,
                FORMULA_REC, BOOLERR_REC}

def biff_records(data: bytes):
    pos = 0
    while pos + 4 <= len(data):
        rec, length = struct.unpack_from('<HH', data, pos)
        pos += 4
        if pos + length > len(data): break
        yield rec, data[pos:pos + length]
        pos += length

def _sst_strings(payload: bytes, continues: list[bytes]) -> list[str]:
    """Walk the shared string table, following CONTINUE record boundaries.

    A string may be split across records, and the compression flag is repeated
    at the start of each continuation, which is the part that makes a naive
    reader produce mojibake.
    """
    blocks = [payload[8:]] + continues        # skip cstTotal/cstUnique
    bi, pos = 0, 0

    def need(n):
        """Advance to a block that still has n bytes, hopping continuations."""
        nonlocal bi, pos
        while bi < len(blocks) and pos + n > len(blocks[bi]):
            if pos >= len(blocks[bi]):
                bi += 1; pos = 0
            else:
                return False                  # split mid-field: give up cleanly
        return bi < len(blocks)

    out = []
    while bi < len(blocks):
        if not need(3): break
        block = blocks[bi]
        cch = struct.unpack_from('<H', block, pos)[0]; pos += 2
        grbit = block[pos]; pos += 1
        rich = bool(grbit & 0x08); ext = bool(grbit & 0x04)
        runs = 0; ext_len = 0
        if rich:
            if not need(2): break
            runs = struct.unpack_from('<H', blocks[bi], pos)[0]; pos += 2
        if ext:
            if not need(4): break
            ext_len = struct.unpack_from('<I', blocks[bi], pos)[0]; pos += 4
        chars, remaining, wide = [], cch, bool(grbit & 0x01)
        while remaining > 0:
            if bi >= len(blocks): break
            block = blocks[bi]
            if pos >= len(block):
                bi += 1; pos = 0
                if bi >= len(blocks): break
                block = blocks[bi]
                wide = bool(block[pos] & 0x01); pos += 1   # flag repeats
                continue
            width = 2 if wide else 1
            take = min(remaining, (len(block) - pos) // width)
            if take <= 0:
                bi += 1; pos = 0
                if bi >= len(blocks): break
                block = blocks[bi]
                wide = bool(block[pos] & 0x01); pos += 1
                continue
            raw = block[pos:pos + take * width]; pos += take * width
            chars.append(raw.decode('utf-16-le' if wide else 'latin-1', 'ignore'))
            remaining -= take
        skip = runs * 4 + ext_len
        while skip > 0 and bi < len(blocks):
            step = min(skip, len(blocks[bi]) - pos)
            if step <= 0:
                bi += 1; pos = 0; continue
            pos += step; skip -= step
        out.append(''.join(chars))
        if bi < len(blocks) and pos >= len(blocks[bi]):
            bi += 1; pos = 0
    return out

def rk_number(bits: int) -> float:
    """Decode an RK: a double squeezed into four bytes, two ways at once.

    Bit 1 says whether the remaining 30 bits are a signed integer or the top
    of a double's mantissa; bit 0 says the result was divided by a hundred.
    """
    if bits & 0x02:
        value = bits >> 2
        if value & 0x20000000:
            value -= 0x40000000
        value = float(value)
    else:
        value = struct.unpack('<d', b'\x00\x00\x00\x00'
                              + struct.pack('<I', bits & 0xFFFFFFFC))[0]
    return value / 100 if bits & 0x01 else value

def biff_string(payload: bytes, at: int) -> str:
    """XLUnicodeString: a length, a flag byte, then wide or compressed chars."""
    if len(payload) < at + 3:
        return ''
    cch = struct.unpack('<H', payload[at:at + 2])[0]
    body = payload[at + 3:]
    if payload[at + 2] & 0x01:
        return body[:cch * 2].decode('utf-16-le', 'ignore')
    return body[:cch].decode('latin-1', 'ignore')

def xls_cell(rec: int, payload: bytes, strings: list[str], dated: list[bool],
             following: str) -> list[tuple[int, int, str]]:
    """One BIFF cell record -> [(row, column, text)].  MULRK yields a span."""
    if len(payload) < 6:
        return []
    row, col, xf = struct.unpack('<HHH', payload[:6])
    def render(value, style):
        return number_text(value, 0 <= style < len(dated) and dated[style])

    if rec == LABELSST and len(payload) >= 10:
        index = struct.unpack('<I', payload[6:10])[0]
        return [(row, col, strings[index])] if index < len(strings) else []
    if rec in (LABEL_REC, RSTRING):
        return [(row, col, biff_string(payload, 6))]
    if rec == NUMBER_REC and len(payload) >= 14:
        return [(row, col, render(struct.unpack('<d', payload[6:14])[0], xf))]
    if rec == RK_REC and len(payload) >= 10:
        return [(row, col, render(rk_number(struct.unpack('<I', payload[6:10])[0]), xf))]
    if rec == MULRK_REC and len(payload) >= 10:
        out, at, column = [], 4, col
        while at + 6 <= len(payload) - 2:
            style, bits = struct.unpack('<HI', payload[at:at + 6])
            out.append((row, column, render(rk_number(bits), style)))
            at += 6
            column += 1
        return out
    if rec == BOOLERR_REC and len(payload) >= 8:
        if payload[7]:
            return [(row, col, '#ERR')]
        return [(row, col, 'TRUE' if payload[6] else 'FALSE')]
    if rec == FORMULA_REC and len(payload) >= 14:
        # A cached result is a double unless the last two bytes are 0xFFFF, in
        # which case the first byte says what kind of non-number it was.
        if payload[12:14] == b'\xff\xff':
            kind = payload[6]
            if kind == 0:
                return [(row, col, following)] if following else []
            if kind == 1:
                return [(row, col, 'TRUE' if payload[8] else 'FALSE')]
            return [(row, col, '#ERR')] if kind == 2 else []
        return [(row, col, render(struct.unpack('<d', payload[6:14])[0], xf))]
    return []

def xls_text(raw: bytes, limit: int = MAX_CHARS) -> tuple[str, dict]:
    ole = OleFile(raw)
    book = ole.stream('Workbook', 'Book')
    if not book:
        return no_text_layer('no Workbook stream')
    records = list(biff_records(book))

    sheets, strings, formats, xfs = [], [], {}, []
    for i, (rec, payload) in enumerate(records):
        if rec == BOUNDSHEET and len(payload) >= 8:
            cch = payload[6]; grbit = payload[7]
            body = payload[8:]
            name = body[:cch * 2].decode('utf-16-le', 'ignore') if grbit & 0x01 \
                else body[:cch].decode('latin-1', 'ignore')
            if name: sheets.append(name)
        elif rec == SST:
            cont = []
            for nrec, npayload in records[i + 1:]:
                if nrec != CONTINUE: break
                cont.append(npayload)
            strings = _sst_strings(payload, cont)
        elif rec == FORMAT_REC and len(payload) >= 2:
            formats[struct.unpack('<H', payload[:2])[0]] = biff_string(payload, 2)
        elif rec == XF_REC and len(payload) >= 4:
            xfs.append(struct.unpack('<H', payload[2:4])[0])
    dated = [is_date_format(formats.get(fid), fid) for fid in xfs]

    # Cells live in the per-sheet substreams that follow the globals, in the
    # same order BOUNDSHEET named them.
    grids, current = [], None
    for i, (rec, payload) in enumerate(records):
        if rec == BOF and len(payload) >= 4 \
                and struct.unpack('<H', payload[2:4])[0] == SHEET_SUBSTREAM:
            current = {}
            grids.append(current)
        elif current is not None and rec in CELL_RECORDS:
            following = ''
            if rec == FORMULA_REC and i + 1 < len(records) \
                    and records[i + 1][0] == STRING_REC:
                following = biff_string(records[i + 1][1], 0)
            for row, col, value in xls_cell(rec, payload, strings, dated, following):
                if value != '':
                    current[(row + 1, col)] = value      # BIFF rows count from 0

    named = [(sheets[i] if i < len(sheets) else 'Sheet%d' % (i + 1), g)
             for i, g in enumerate(grids)]
    body, counts = grid_text(named, limit)
    meta = {'sheets': len(sheets), 'shared_strings': len(strings), **counts}
    parts = []
    if sheets: parts.append('工作表: ' + ' | '.join(sheets))
    if body:
        parts.append(body)
    else:
        parts.extend(strings)
    return '\n'.join(parts)[:limit], meta
