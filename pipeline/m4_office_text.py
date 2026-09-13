#!/usr/bin/env python3
"""Text out of Office formats the preview stage could not open, stdlib only.

The L1 pass scored 4,789 files having seen nothing but their filename, because
.xlsx / .xls / .ppt were routed to _office_pending and never opened.  That is
how a Dell'Oro capex workbook - eleven sheets of forecast data - scored 8 while
its prose summary PDF scored 9.

No third-party parser is used: the machine doing the triage has no libreoffice
and no python-xlrd, and asking a user to install a toolchain to read their own
files is not an acceptable step in this pipeline.

Two container families are handled, chosen by magic bytes rather than suffix,
because .et / .wps / .dps are written as either one depending on the version
that saved them:

  PK\\x03\\x04           OOXML zip     .xlsx .xlsm .vsdx and their WPS twins
  \\xd0\\xcf\\x11\\xe0   OLE2 / CFBF   .xls .ppt and their WPS twins

Everything here is defensive: a malformed file returns whatever text was
recovered before the parse went wrong, never an exception.
"""
from __future__ import annotations
import datetime
import re
import struct
import zipfile
from pathlib import Path

OLE_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
ZIP_MAGIC = b'PK\x03\x04'

MAX_CHARS = 20000          # far above the 6000 the model is shown; trimmed later
FREE_SECTOR = 0xFFFFFFFF
END_OF_CHAIN = 0xFFFFFFFE


# --------------------------------------------------------------------------
# OLE2 compound file
# --------------------------------------------------------------------------

class OleFile:
    """Minimal reader for the streams inside a compound file.

    Implements only what is needed to pull one named stream out: the FAT, the
    mini FAT and the directory.  No writing, no storages beyond name lookup.
    """

    def __init__(self, raw: bytes):
        if not raw.startswith(OLE_MAGIC):
            raise ValueError('not an OLE2 compound file')
        self.raw = raw
        self.sector_size = 1 << struct.unpack_from('<H', raw, 0x1E)[0]
        self.mini_size = 1 << struct.unpack_from('<H', raw, 0x20)[0]
        self.cutoff = struct.unpack_from('<I', raw, 0x38)[0]
        first_dir = struct.unpack_from('<I', raw, 0x30)[0]
        first_mini_fat = struct.unpack_from('<I', raw, 0x3C)[0]
        self.fat = self._read_fat()
        self.dir_entries = self._read_directory(first_dir)
        self.mini_fat = self._read_chain_as_uints(first_mini_fat)
        self.mini_stream = self._read_mini_stream()

    def _sector(self, n: int) -> bytes:
        start = 512 + n * self.sector_size
        return self.raw[start:start + self.sector_size]

    def _difat(self) -> list[int]:
        """Sector numbers holding the FAT: 109 inline, the rest chained."""
        entries = list(struct.unpack_from('<109I', self.raw, 0x4C))
        nxt = struct.unpack_from('<I', self.raw, 0x44)[0]
        guard = 0
        while nxt not in (END_OF_CHAIN, FREE_SECTOR) and guard < 4096:
            block = self._sector(nxt)
            if len(block) < self.sector_size: break
            count = self.sector_size // 4 - 1
            entries.extend(struct.unpack_from('<%dI' % count, block, 0))
            nxt = struct.unpack_from('<I', block, self.sector_size - 4)[0]
            guard += 1
        return [e for e in entries if e not in (FREE_SECTOR, END_OF_CHAIN)]

    def _read_fat(self) -> list[int]:
        fat: list[int] = []
        per = self.sector_size // 4
        for sector in self._difat():
            block = self._sector(sector)
            if len(block) < self.sector_size: break
            fat.extend(struct.unpack_from('<%dI' % per, block, 0))
        return fat

    def _chain(self, start: int) -> list[int]:
        out, seen, cur = [], set(), start
        while cur not in (END_OF_CHAIN, FREE_SECTOR) and 0 <= cur < len(self.fat):
            if cur in seen: break            # a corrupt file can loop
            seen.add(cur); out.append(cur)
            cur = self.fat[cur]
        return out

    def _read_chain_bytes(self, start: int, size: int | None = None) -> bytes:
        data = b''.join(self._sector(s) for s in self._chain(start))
        return data if size is None else data[:size]

    def _read_chain_as_uints(self, start: int) -> list[int]:
        data = self._read_chain_bytes(start)
        return list(struct.unpack_from('<%dI' % (len(data) // 4), data, 0)) if data else []

    def _read_directory(self, first: int) -> list[dict]:
        data = self._read_chain_bytes(first)
        out = []
        for off in range(0, len(data) - 127, 128):
            name_len = struct.unpack_from('<H', data, off + 0x40)[0]
            if not 2 <= name_len <= 64: continue
            name = data[off:off + name_len - 2].decode('utf-16-le', 'ignore')
            out.append({
                'name': name,
                'type': data[off + 0x42],
                'start': struct.unpack_from('<I', data, off + 0x74)[0],
                'size': struct.unpack_from('<Q', data, off + 0x78)[0],
            })
        return out

    def _read_mini_stream(self) -> bytes:
        for e in self.dir_entries:
            if e['type'] == 5:               # root storage holds the mini stream
                return self._read_chain_bytes(e['start'], e['size'])
        return b''

    def _read_mini_chain(self, start: int, size: int) -> bytes:
        out, seen, cur = [], set(), start
        while cur not in (END_OF_CHAIN, FREE_SECTOR) and 0 <= cur < len(self.mini_fat):
            if cur in seen: break
            seen.add(cur)
            off = cur * self.mini_size
            out.append(self.mini_stream[off:off + self.mini_size])
            cur = self.mini_fat[cur]
        return b''.join(out)[:size]

    def stream(self, *names: str) -> bytes:
        """First stream matching any of `names`, empty if none is present."""
        wanted = {n.lower() for n in names}
        for e in self.dir_entries:
            if e['type'] == 2 and e['name'].lower() in wanted:
                if e['size'] < self.cutoff:
                    return self._read_mini_chain(e['start'], e['size'])
                return self._read_chain_bytes(e['start'], e['size'])
        return b''


def no_text_layer(reason: str) -> tuple[str, dict]:
    """The container opened fine but holds no text stream, and never will.

    Callers use the flag to drop a file out of the re-read queue.  It exists
    as one helper rather than a literal at each exit because forgetting it
    reads as a transient failure: the file goes back in the queue, comes out
    identical, and goes back again.  A 37 MB .ppt did exactly that until
    somebody noticed the queue would not drain.
    """
    return '', {'no_text_layer': True, 'extract_error': reason}


# --------------------------------------------------------------------------
# BIFF (.xls)
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# PowerPoint 97-2003 (.ppt)
# --------------------------------------------------------------------------

TEXT_CHARS_ATOM = 0x0FA0      # UTF-16LE
TEXT_BYTES_ATOM = 0x0FA8      # one byte per char, high byte implied zero
CSTRING_ATOM = 0x0FBA         # UTF-16LE, used for titles and notes

# A deck's master and handout carry the template's placeholder text - "单击此处
# 编辑母版标题样式" and friends - which says nothing about this deck and is
# repeated once per layout.  Collected indiscriminately it can fill a preview
# window before the first real slide, which is what made a 1200-character
# budget come back full of boilerplate.
SKIP_CONTAINERS = {
    0x03F8,   # MainMaster
    0x0FC9,   # Handout
}


def ppt_atoms(data: bytes, depth: int = 0):
    """Yield (type, payload), descending into container records."""
    pos = 0
    while pos + 8 <= len(data):
        ver_inst, rec_type, rec_len = struct.unpack_from('<HHI', data, pos)
        pos += 8
        if rec_len > len(data) - pos: break
        payload = data[pos:pos + rec_len]
        if rec_type in SKIP_CONTAINERS:
            pos += rec_len
            continue
        if (ver_inst & 0x0F) == 0x0F and depth < 12:
            yield from ppt_atoms(payload, depth + 1)
        else:
            yield rec_type, payload
        pos += rec_len


def ppt_text(raw: bytes) -> tuple[str, dict]:
    ole = OleFile(raw)
    doc = ole.stream('PowerPoint Document', 'PP97_DUALSTORAGE')
    if not doc:
        # Same permanent verdict as a Visio binary: the stream the text lives in
        # is simply not in this file, so a later re-read finds the same nothing.
        return no_text_layer('no PowerPoint Document stream')
    parts = []
    for rec_type, payload in ppt_atoms(doc):
        if rec_type == TEXT_BYTES_ATOM:
            parts.append(payload.decode('latin-1', 'ignore'))
        elif rec_type in (TEXT_CHARS_ATOM, CSTRING_ATOM):
            parts.append(payload.decode('utf-16-le', 'ignore'))
    text = '\n'.join(p.replace('\r', '\n') for p in parts if p.strip())
    return text[:MAX_CHARS], {'text_atoms': len(parts)}


# --------------------------------------------------------------------------
# cells, not just labels
#
# The first version of both spreadsheet readers collected strings: sheet names,
# the shared-string table, inline <t> runs.  Every number was dropped, and the
# strings that survived arrived as a flat list with no row or column.  For a
# corpus of 造价表, 产能表 and 财务数据 that is not a lossy preview, it is an
# empty one: 「楼面荷载」 and 8.0 sit in adjacent cells and only the label came
# through.  A reader handed that text can honestly report zero facts from a
# document full of them, which is exactly what happened on the first L2 read.
#
# So both readers now walk cells and lay them out as a grid.  A grid is also
# what makes a locator possible: 「Sheet1 第 12 行第 3 列」 can be checked, and
# a bare list of labels cannot be.
# --------------------------------------------------------------------------

COL_REF = re.compile(r'^([A-Z]+)')

# Excel's built-in date and time formats, plus any custom format whose code
# actually spells a date out.  A date is stored as a number; handed over as one
# it reads as a quantity - 45292 filed as a value instead of 2024-01-01.
DATE_FMT_IDS = set(range(14, 23)) | set(range(45, 48)) | {27, 28, 29, 30, 31,
                                                          32, 33, 34, 35, 36,
                                                          50, 51, 52, 53, 54,
                                                          55, 56, 57, 58}
DATE_CODE = re.compile(r'(?<!\\)[ymdhs]', re.I)
EPOCH = datetime.date(1899, 12, 30)      # 1900-system, Excel's phantom leap day


def col_index(ref: str) -> int:
    """'A' -> 0, 'AB' -> 27.  Anything unparseable lands in column 0."""
    m = COL_REF.match(ref or '')
    n = 0
    for ch in (m.group(1) if m else ''):
        n = n * 26 + (ord(ch) - 64)
    return max(n - 1, 0)


def is_date_format(code: str | None, fmt_id: int) -> bool:
    if code:
        # Strip the literal text sections a format may carry: "元" in
        # 0.00"元" must not be read as a date code.
        bare = re.sub(r'"[^"]*"|\[[^\]]*\]', '', code)
        return bool(DATE_CODE.search(bare))
    return fmt_id in DATE_FMT_IDS


def serial_to_iso(value: float) -> str | None:
    """Excel serial -> ISO date, or None when the number is not plausibly one.

    Serials at or below 60 straddle Excel's phantom 1900-02-29; converting them
    would be wrong by a day, so they stay numbers.
    """
    if not (61 <= value < 80000):
        return None
    try:
        day = EPOCH + datetime.timedelta(days=int(value))
    except (OverflowError, ValueError):
        return None
    frac = value - int(value)
    if frac > 1e-6:
        secs = int(round(frac * 86400))
        return '%s %02d:%02d' % (day.isoformat(), secs // 3600, (secs // 60) % 60)
    return day.isoformat()


def number_text(value: float, dated: bool) -> str:
    if dated:
        iso = serial_to_iso(value)
        if iso:
            return iso
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    # Repr of a float read back from 8 bytes carries the binary noise Excel
    # never showed anyone (0.5800000000000001).  Twelve digits is past any
    # precision these documents claim and short of inventing any.
    return repr(round(value, 12))


def grid_text(sheets: list[tuple[str, dict]], limit: int = MAX_CHARS) -> tuple[str, dict]:
    """Render [(sheet name, {(row, col): text})] as tab-separated rows.

    Empty cells are kept as empty fields so the columns still line up: a value
    that has drifted one column left of its header is a different claim.

    The only cap is the character budget, and when it bites the caller is told
    so - a reader who believes they saw the whole sheet will report the last
    row they were given as the last row there is.
    """
    out, rows_out, cells_out, truncated = [], 0, 0, False
    total = 0
    for name, cells in sheets:
        if not cells:
            continue
        out.append('== 工作表: %s ==' % name)
        total += len(out[-1]) + 1
        numbers = sorted({r for r, _ in cells})
        for r in numbers:
            if total > limit:
                truncated = True
                break
            width = max(c for rr, c in cells if rr == r) + 1
            line = '%d\t%s' % (r, '\t'.join(cells.get((r, c), '') for c in range(width)))
            out.append(line.rstrip('\t'))
            rows_out += 1
            cells_out += sum(1 for c in range(width)
                             if cells.get((r, c), '') not in ('', MERGE_MARK))
            total += len(line) + 1
    return '\n'.join(out), {'rows': rows_out, 'cells': cells_out,
                            'truncated': truncated or total > limit}


# --------------------------------------------------------------------------
# OOXML spreadsheets
# --------------------------------------------------------------------------

def _xml_text(blob: bytes) -> str:
    text = re.sub(rb'<[^>]+>', b' ', blob).decode('utf-8', 'ignore')
    return re.sub(r'[ \t]+', ' ', text)


XML_ENTITIES = (('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'),
                ('&#39;', "'"), ('&apos;', "'"), ('&amp;', '&'))


def unescape(text: str) -> str:
    for entity, char in XML_ENTITIES:      # &amp; last, or &amp;lt; double-decodes
        text = text.replace(entity, char)
    return text


SI = re.compile(r'<si\b[^>]*>(.*?)</si>', re.S)
T_RUN = re.compile(r'<t[^>]*>(.*?)</t>', re.S)
CELL = re.compile(r'<c\b([^>]*?)(?:/>|>(.*?)</c>)', re.S)
ATTR = re.compile(r'(\w+)="([^"]*)"')
V = re.compile(r'<v[^>]*>(.*?)</v>', re.S)
ROW_NUM = re.compile(r'(\d+)')
NUM_FMT = re.compile(r'<numFmt[^>]*\bnumFmtId="(\d+)"[^>]*\bformatCode="([^"]*)"')
CELL_XFS = re.compile(r'<cellXfs\b[^>]*>(.*?)</cellXfs>', re.S)
XF_FMT = re.compile(r'<xf\b[^>]*?\bnumFmtId="(\d+)"')


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


ROW = re.compile(r'<row\b([^>]*?)(?:/>|>(.*?)</row>)', re.S)


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


MERGE_REF = re.compile(r'<mergeCell[^>]*\bref="([A-Z]+)(\d+):([A-Z]+)(\d+)"')
# 合并单元格的值只存在左上角那一格，其余格在 XML 里根本不存在。渲染成空白
# 的后果不是「少了一格」，而是读者把右边某一列的数读成那一列的数——冷源工程
# 表-09 的 小计 行就是这么错列的（4067+165+2593+67 ≠ 2825.41）。
# 标一个「〃」出来，跨了哪几列就一目了然。
MERGE_MARK = '〃'


def merge_ranges(xml: str) -> list[tuple[int, int, int, int]]:
    """<mergeCell ref="A5:D5"/> -> [(row1, col1, row2, col2)]，列从 0 起。"""
    out = []
    for c1, r1, c2, r2 in MERGE_REF.findall(xml):
        try:
            out.append((int(r1), col_index(c1 + r1), int(r2), col_index(c2 + r2)))
        except ValueError:
            continue
    return out


def mark_merges(cells: dict, xml: str) -> dict:
    """Fill the covered cells of every merged range with a continuation mark.

    Only where the top-left actually has a value and the covered cell is
    empty: a mark written over a value would invent a span that is not there,
    and an empty range is nothing to say anything about.
    """
    for r1, c1, r2, c2 in merge_ranges(xml):
        if (r1, c1) not in cells:
            continue
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                if (r, c) != (r1, c1):
                    cells.setdefault((r, c), MERGE_MARK)
    return cells


DRAWING = re.compile(r'xl/drawings/drawing\d+\.xml')
A_PARA = re.compile(r'<a:p(?:\s[^>]*)?>(.*?)</a:p>', re.S)
A_RUN = re.compile(r'<a:t[^>]*>(.*?)</a:t>', re.S)


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
            grids.append((label, mark_merges(sheet_cells(xml, strings, dated), xml)))
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
    return '\n'.join(parts)[:limit], meta


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


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

SUPPORTED = {'.xlsx', '.xlsm', '.xltx', '.xls', '.ppt', '.et', '.wps', '.dps', '.vsdx', '.vsd'}


def extract(path: Path, limit: int = MAX_CHARS) -> tuple[str, dict]:
    """(text, meta) for one Office file.  Never raises.

    `limit` is the character budget.  L1 judges from a preview and the default
    is plenty; L2 reads the document to record numbers out of it and asks for
    far more, because a workbook silently cut at twenty thousand characters is
    read as though its last surviving row were its last row.
    """
    try:
        with open(path, 'rb') as fh:
            head = fh.read(8)
        if head.startswith(ZIP_MAGIC):
            return ooxml_text(path, limit)
        if head.startswith(OLE_MAGIC):
            raw = Path(path).read_bytes()
            ole = OleFile(raw)
            names = {e['name'].lower() for e in ole.dir_entries if e['type'] == 2}
            if 'workbook' in names or 'book' in names:
                return xls_text(raw, limit)
            if 'powerpoint document' in names:
                return ppt_text(raw)
            # A Visio binary carries no text stream at all.  Callers decide
            # whether to re-read a file later, and that decision must not rest
            # on matching the prose below - hence the flag.
            return no_text_layer(
                'OLE2 with no known stream: ' + ','.join(sorted(names))[:80])
        return '', {'extract_error': 'unrecognised container'}
    except Exception as exc:
        return '', {'extract_error': type(exc).__name__ + ': ' + str(exc)[:120]}
