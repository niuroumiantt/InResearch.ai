#!/usr/bin/env python3
"""Office extraction, tested against containers this file builds byte by byte.

Fixtures are constructed rather than checked in: the tests then need no
libreoffice, no committed binaries, and can aim straight at the parts that
actually break real files - a shared string split across a CONTINUE record,
a stream small enough to live in the mini stream, CJK text that only survives
if the compression flag is read correctly.
"""
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m4_office_text as O

FREE = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
SECTOR = 512
MINI = 64
CUTOFF = 4096


def build_ole(streams: dict[str, bytes]) -> bytes:
    """A minimal but real compound file, exercising both storage paths."""
    big = {n: d for n, d in streams.items() if len(d) >= CUTOFF}
    small = {n: d for n, d in streams.items() if len(d) < CUTOFF}

    mini_blob = b''
    mini_at = {}
    for name, data in small.items():
        mini_at[name] = len(mini_blob) // MINI
        padded = data + b'\0' * (-len(data) % MINI)
        mini_blob += padded
    n_mini = len(mini_blob) // MINI

    def sectors_for(nbytes):
        return max(1, -(-nbytes // SECTOR)) if nbytes else 0

    alloc = []                       # list of (kind, key, n_sectors)
    for name, data in big.items():
        alloc.append(('big', name, sectors_for(len(data))))
    alloc.append(('mini', None, sectors_for(len(mini_blob))))
    minifat_bytes = n_mini * 4
    alloc.append(('minifat', None, sectors_for(minifat_bytes)))
    dir_bytes = (1 + len(streams)) * 128
    alloc.append(('dir', None, sectors_for(dir_bytes)))

    n_fat = 1
    while True:
        total = sum(n for _, _, n in alloc) + n_fat
        if -(-total * 4 // SECTOR) <= n_fat: break
        n_fat += 1
    alloc.append(('fat', None, n_fat))

    start, chains = 0, {}
    for kind, key, count in alloc:
        chains[(kind, key)] = list(range(start, start + count))
        start += count
    total_sectors = start

    fat = [FREE] * total_sectors
    for (kind, key), chain in chains.items():
        for i, s in enumerate(chain):
            fat[s] = ENDOFCHAIN if i == len(chain) - 1 else chain[i + 1]
    for s in chains[('fat', None)]:
        fat[s] = FATSECT

    mini_fat = [ENDOFCHAIN] * n_mini
    for name, data in small.items():
        first = mini_at[name]
        used = max(1, -(-len(data) // MINI))
        for i in range(used):
            mini_fat[first + i] = ENDOFCHAIN if i == used - 1 else first + i + 1

    entries = []

    def entry(name, etype, start_sector, size):
        raw = name.encode('utf-16-le') + b'\0\0'
        raw = raw.ljust(64, b'\0')[:64]
        e = bytearray(128)
        e[0:64] = raw
        struct.pack_into('<H', e, 0x40, min(len(name) * 2 + 2, 64))
        e[0x42] = etype
        e[0x43] = 1
        struct.pack_into('<III', e, 0x44, FREE, FREE, FREE)
        struct.pack_into('<I', e, 0x74, start_sector)
        struct.pack_into('<Q', e, 0x78, size)
        return bytes(e)

    minifat_chain = chains[('minifat', None)]
    mini_chain = chains[('mini', None)]
    mini_start = mini_chain[0] if mini_blob else ENDOFCHAIN
    entries.append(entry('Root Entry', 5, mini_start, len(mini_blob)))
    for name, data in streams.items():
        if name in big:
            entries.append(entry(name, 2, chains[('big', name)][0], len(data)))
        else:
            entries.append(entry(name, 2, mini_at[name], len(data)))

    out = bytearray(512 + total_sectors * SECTOR)

    def put(chain, blob):
        for i, s in enumerate(chain):
            piece = blob[i * SECTOR:(i + 1) * SECTOR].ljust(SECTOR, b'\0')
            out[512 + s * SECTOR:512 + (s + 1) * SECTOR] = piece

    for name, data in big.items():
        put(chains[('big', name)], data)
    put(chains[('mini', None)], mini_blob)
    put(chains[('minifat', None)], b''.join(struct.pack('<I', v) for v in mini_fat))
    put(chains[('dir', None)], b''.join(entries))
    put(chains[('fat', None)], b''.join(struct.pack('<I', v) for v in fat))

    out[0:8] = O.OLE_MAGIC
    struct.pack_into('<H', out, 0x18, 0x003E)
    struct.pack_into('<H', out, 0x1A, 0x0003)
    struct.pack_into('<H', out, 0x1C, 0xFFFE)
    struct.pack_into('<H', out, 0x1E, 9)          # 512-byte sectors
    struct.pack_into('<H', out, 0x20, 6)          # 64-byte mini sectors
    struct.pack_into('<I', out, 0x2C, n_fat)
    struct.pack_into('<I', out, 0x30, chains[('dir', None)][0])
    struct.pack_into('<I', out, 0x38, CUTOFF)
    struct.pack_into('<I', out, 0x3C, minifat_chain[0] if n_mini else ENDOFCHAIN)
    struct.pack_into('<I', out, 0x40, len(minifat_chain) if n_mini else 0)
    struct.pack_into('<I', out, 0x44, ENDOFCHAIN)
    struct.pack_into('<I', out, 0x48, 0)
    difat = chains[('fat', None)] + [FREE] * (109 - n_fat)
    for i, v in enumerate(difat[:109]):
        struct.pack_into('<I', out, 0x4C + i * 4, v)
    return bytes(out)


def biff(rec, payload):
    return struct.pack('<HH', rec, len(payload)) + payload


def boundsheet(name):
    body = name.encode('utf-16-le')
    return biff(O.BOUNDSHEET, struct.pack('<IBB', 0, 0, 0) + bytes([len(name), 0x01]) + body)


def sst(strings, split_in=None):
    """Build an SST.

    `split_in` splits the table in the middle of that string's character data
    and starts a CONTINUE record, which is what Excel actually writes: the
    continuation repeats the one-byte compression flag before resuming the
    characters.  Splitting raw bytes without that flag would test a file no
    spreadsheet ever produces.
    """
    head = struct.pack('<II', len(strings), len(strings))
    before, after = b'', None
    for i, s in enumerate(strings):
        entry = struct.pack('<HB', len(s), 0x01) + s.encode('utf-16-le')
        if i == split_in:
            half = 3 + (len(s) // 2) * 2          # header + half the characters
            before += entry[:half]
            after = bytes([0x01]) + entry[half:]  # flag repeats, then the rest
        elif after is None:
            before += entry
        else:
            after += entry
    if after is None:
        return biff(O.SST, head + before)
    return biff(O.SST, head + before) + biff(O.CONTINUE, after)


def ppt_atom(rec_type, payload, container=False):
    ver = 0x0F if container else 0x00
    return struct.pack('<HHI', ver, rec_type, len(payload)) + payload


class OleTests(unittest.TestCase):
    def test_reads_a_large_stream_from_the_regular_chain(self):
        blob = bytes(range(256)) * 40           # 10240 bytes, well over the cutoff
        ole = O.OleFile(build_ole({'Workbook': blob}))
        self.assertEqual(ole.stream('Workbook'), blob)

    def test_reads_a_small_stream_from_the_mini_stream(self):
        blob = b'tiny payload' * 10             # 120 bytes, under the cutoff
        ole = O.OleFile(build_ole({'Workbook': blob}))
        self.assertEqual(ole.stream('Workbook'), blob)

    def test_stream_lookup_is_case_insensitive_and_missing_is_empty(self):
        ole = O.OleFile(build_ole({'Workbook': b'x' * 100}))
        self.assertEqual(ole.stream('WORKBOOK'), b'x' * 100)
        self.assertEqual(ole.stream('NoSuchStream'), b'')

    def test_a_non_ole_file_is_refused(self):
        with self.assertRaises(ValueError):
            O.OleFile(b'not an ole file at all')


class XlsTests(unittest.TestCase):
    def book(self, records):
        return build_ole({'Workbook': b''.join(records)})

    def test_sheet_names_and_strings_come_back(self):
        raw = self.book([boundsheet('Demand Chart'), boundsheet('Source_Data'),
                         sst(['MFG Revenue ($M)', 'Top 4 US Cloud'])])
        text, meta = O.xls_text(raw)
        self.assertEqual(meta['sheets'], 2)
        self.assertIn('Demand Chart | Source_Data', text)
        self.assertIn('MFG Revenue ($M)', text)
        self.assertIn('Top 4 US Cloud', text)

    def test_cjk_survives(self):
        raw = self.book([boundsheet('数据中心机柜清单'),
                         sst(['中国移动IDC资质', 'Uptime Tier III 认证'])])
        text, _ = O.xls_text(raw)
        self.assertIn('数据中心机柜清单', text)
        self.assertIn('中国移动IDC资质', text)
        self.assertIn('Uptime Tier III 认证', text)

    def test_a_string_table_split_across_a_continue_record(self):
        strings = ['第%d季度机柜功率密度报告' % i for i in range(12)]
        raw = self.book([sst(strings, split_in=5)])    # splits inside string 5
        text, meta = O.xls_text(raw)
        self.assertEqual(meta['shared_strings'], 12,
                         'CONTINUE handling dropped part of the table')
        for s in strings:
            self.assertIn(s, text)

    def test_a_workbook_without_the_stream_reports_why(self):
        raw = build_ole({'Nonsense': b'z' * 100})
        text, meta = O.xls_text(raw)
        self.assertEqual(text, '')
        self.assertIn('no Workbook stream', meta['extract_error'])


class PptTests(unittest.TestCase):
    def deck(self, atoms):
        return build_ole({'PowerPoint Document': b''.join(atoms)})

    def test_byte_and_char_atoms_are_both_read(self):
        raw = self.deck([
            ppt_atom(O.TEXT_BYTES_ATOM, b'Modular Data Center'),
            ppt_atom(O.TEXT_CHARS_ATOM, '模块化数据中心解决方案'.encode('utf-16-le')),
        ])
        text, meta = O.ppt_text(raw)
        self.assertIn('Modular Data Center', text)
        self.assertIn('模块化数据中心解决方案', text)
        self.assertEqual(meta['text_atoms'], 2)

    def test_atoms_nested_in_containers_are_found(self):
        inner = ppt_atom(O.TEXT_CHARS_ATOM, '机房工程整体设计'.encode('utf-16-le'))
        raw = self.deck([ppt_atom(0x0FF0, ppt_atom(0x0FF0, inner, container=True), container=True)])
        text, _ = O.ppt_text(raw)
        self.assertIn('机房工程整体设计', text)

    def test_a_truncated_record_does_not_raise(self):
        raw = self.deck([struct.pack('<HHI', 0, O.TEXT_CHARS_ATOM, 9999) + b'ab'])
        text, _ = O.ppt_text(raw)
        self.assertEqual(text, '')


class XlsxTests(unittest.TestCase):
    def make(self, shared=None, inline_sheet=None, sheets=('Sheet1',)):
        tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        wb = '<workbook>' + ''.join('<sheet name="%s" sheetId="%d"/>' % (n, i + 1)
                                    for i, n in enumerate(sheets)) + '</workbook>'
        with zipfile.ZipFile(tmp.name, 'w') as z:
            z.writestr('xl/workbook.xml', wb)
            if shared is not None:
                z.writestr('xl/sharedStrings.xml',
                           '<sst>' + ''.join('<si><t>%s</t></si>' % s for s in shared) + '</sst>')
            z.writestr('xl/worksheets/sheet1.xml', inline_sheet or '<worksheet/>')
        return Path(tmp.name)

    def test_sheet_names_and_shared_strings(self):
        p = self.make(shared=['Revenue', 'Year-Over-Year Growth MFG Revenue (%)'],
                      sheets=('Demand Chart', 'Supply by Regions'))
        try:
            text, meta = O.extract(p)
            self.assertEqual(meta['sheets'], 2)
            self.assertIn('Demand Chart | Supply by Regions', text)
            self.assertIn('Year-Over-Year Growth MFG Revenue (%)', text)
        finally:
            p.unlink()

    def test_entities_are_unescaped(self):
        p = self.make(shared=['Dos &amp; Donts', 'a &lt; b'], sheets=('Servers &amp; Storage',))
        try:
            text, _ = O.extract(p)
            self.assertIn('Dos & Donts', text)
            self.assertIn('a < b', text)
            self.assertIn('Servers & Storage', text)
        finally:
            p.unlink()

    def test_inline_strings_are_used_when_there_is_no_shared_table(self):
        sheet = '<worksheet><c t="inlineStr"><is><t>机柜功率密度</t></is></c></worksheet>'
        p = self.make(shared=None, inline_sheet=sheet)
        try:
            text, meta = O.extract(p)
            self.assertIn('机柜功率密度', text)
            self.assertEqual(meta['shared_strings'], 1)
        finally:
            p.unlink()


class DispatchTests(unittest.TestCase):
    def test_container_is_chosen_by_magic_not_suffix(self):
        """A .et saved as OLE and a .et saved as OOXML must both work."""
        with tempfile.TemporaryDirectory() as tmp:
            ole_et = Path(tmp) / 'a.et'
            ole_et.write_bytes(build_ole({'Workbook': b''.join(
                [boundsheet('报价表'), sst(['单价'])])}))
            text, _ = O.extract(ole_et)
            self.assertIn('报价表', text)

            zip_et = Path(tmp) / 'b.et'
            with zipfile.ZipFile(zip_et, 'w') as z:
                z.writestr('xl/workbook.xml', '<workbook><sheet name="预算"/></workbook>')
                z.writestr('xl/sharedStrings.xml', '<sst><si><t>合计</t></si></sst>')
            text, _ = O.extract(zip_et)
            self.assertIn('预算', text)
            self.assertIn('合计', text)

    def test_unknown_container_reports_and_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            junk = Path(tmp) / 'x.xls'
            junk.write_bytes(b'\x00\x01\x02\x03 not a container')
            text, meta = O.extract(junk)
            self.assertEqual(text, '')
            self.assertIn('unrecognised container', meta['extract_error'])

    def test_a_missing_file_is_reported_not_raised(self):
        text, meta = O.extract(Path('/nonexistent/nope.xls'))
        self.assertEqual(text, '')
        self.assertIn('extract_error', meta)




class PptMasterTests(unittest.TestCase):
    """Template boilerplate crowds out the slides it is printed behind."""

    def deck(self, atoms):
        return build_ole({'PowerPoint Document': b''.join(atoms)})

    def slide_text(self, text):
        return ppt_atom(O.TEXT_CHARS_ATOM, text.encode('utf-16-le'))

    def test_master_placeholder_text_is_not_collected(self):
        raw = self.deck([
            ppt_atom(0x03F8, self.slide_text('单击此处编辑母版标题样式'), container=True),
            ppt_atom(0x03EE, self.slide_text('模块化数据中心交付方案'), container=True),
        ])
        text, _ = O.ppt_text(raw)
        self.assertIn('模块化数据中心交付方案', text)
        self.assertNotIn('母版标题样式', text, 'the template text crowded the preview')

    def test_handout_text_is_not_collected(self):
        raw = self.deck([
            ppt_atom(0x0FC9, self.slide_text('讲义页眉'), container=True),
            ppt_atom(0x03EE, self.slide_text('机柜功率密度'), container=True),
        ])
        text, _ = O.ppt_text(raw)
        self.assertIn('机柜功率密度', text)
        self.assertNotIn('讲义页眉', text)

    def test_a_deck_that_is_only_a_master_yields_nothing(self):
        raw = self.deck([ppt_atom(0x03F8, self.slide_text('单击此处编辑母版'), container=True)])
        text, _ = O.ppt_text(raw)
        self.assertEqual(text, '')

    def test_ordinary_slides_are_unaffected(self):
        raw = self.deck([self.slide_text('第一页'), self.slide_text('第二页')])
        text, _ = O.ppt_text(raw)
        self.assertIn('第一页', text)
        self.assertIn('第二页', text)


if __name__ == '__main__':
    unittest.main()
