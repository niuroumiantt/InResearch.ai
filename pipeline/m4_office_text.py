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


def xls_text(raw: bytes) -> tuple[str, dict]:
    ole = OleFile(raw)
    book = ole.stream('Workbook', 'Book')
    if not book:
        return no_text_layer('no Workbook stream')
    sheets, strings = [], []
    records = list(biff_records(book))
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
    meta = {'sheets': len(sheets), 'shared_strings': len(strings)}
    parts = []
    if sheets: parts.append('工作表: ' + ' | '.join(sheets))
    parts.extend(strings)
    return '\n'.join(parts)[:MAX_CHARS], meta


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
# OOXML spreadsheets
# --------------------------------------------------------------------------

def _xml_text(blob: bytes) -> str:
    text = re.sub(rb'<[^>]+>', b' ', blob).decode('utf-8', 'ignore')
    return re.sub(r'[ \t]+', ' ', text)


def xlsx_text(path: Path) -> tuple[str, dict]:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        sheets = []
        if 'xl/workbook.xml' in names:
            wb = z.read('xl/workbook.xml').decode('utf-8', 'ignore')
            sheets = re.findall(r'<sheet[^>]*\bname="([^"]*)"', wb)
        strings = []
        if 'xl/sharedStrings.xml' in names:
            ss = z.read('xl/sharedStrings.xml').decode('utf-8', 'ignore')
            strings = [s for s in re.findall(r'<t[^>]*>(.*?)</t>', ss, re.S)]
        if not strings:                       # inline strings, no shared table
            for n in sorted(x for x in names if x.startswith('xl/worksheets/sheet')):
                strings.extend(re.findall(r'<t[^>]*>(.*?)</t>',
                                          z.read(n).decode('utf-8', 'ignore'), re.S))
                if len(strings) > 2000: break
    unescape = lambda s: (s.replace('&amp;', '&').replace('&lt;', '<')
                          .replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'"))
    sheets = [unescape(s) for s in sheets]
    strings = [unescape(s).strip() for s in strings]
    strings = [s for s in strings if s]
    meta = {'sheets': len(sheets), 'shared_strings': len(strings)}
    parts = []
    if sheets: parts.append('工作表: ' + ' | '.join(sheets))
    parts.extend(strings)
    return '\n'.join(parts)[:MAX_CHARS], meta


def ooxml_text(path: Path) -> tuple[str, dict]:
    """Route a zip container by what is inside it, not by its suffix."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    if 'xl/workbook.xml' in names:
        return xlsx_text(path)
    with zipfile.ZipFile(path) as z:
        wanted = [n for n in sorted(names)
                  if n == 'word/document.xml' or n.startswith('ppt/slides/slide')
                  or n.startswith('visio/pages/page')]
        parts, total = [], 0
        for n in wanted:
            t = _xml_text(z.read(n)); parts.append(t); total += len(t)
            if total > MAX_CHARS: break
    return '\n'.join(parts)[:MAX_CHARS], {'parts': len(wanted)}


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

SUPPORTED = {'.xlsx', '.xlsm', '.xltx', '.xls', '.ppt', '.et', '.wps', '.dps', '.vsdx', '.vsd'}


def extract(path: Path) -> tuple[str, dict]:
    """(text, meta) for one Office file.  Never raises."""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(8)
        if head.startswith(ZIP_MAGIC):
            return ooxml_text(path)
        if head.startswith(OLE_MAGIC):
            raw = Path(path).read_bytes()
            ole = OleFile(raw)
            names = {e['name'].lower() for e in ole.dir_entries if e['type'] == 2}
            if 'workbook' in names or 'book' in names:
                return xls_text(raw)
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
