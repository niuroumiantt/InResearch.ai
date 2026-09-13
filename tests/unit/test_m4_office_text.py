#!/usr/bin/env python3
"""Office extraction, tested against containers this file builds byte by byte.

Fixtures are constructed rather than checked in: the tests then need no
libreoffice, no committed binaries, and can aim straight at the parts that
actually break real files - a shared string split across a CONTINUE record,
a stream small enough to live in the mini stream, CJK text that only survives
if the compression flag is read correctly.
"""
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from inresearch.adapters import office as O
import inresearch.adapters.office_biff as office_biff
import inresearch.adapters.office_container as office_container
import inresearch.adapters.office_grid as office_grid
import inresearch.adapters.office_ppt as office_ppt
import inresearch.adapters.office_ooxml as office_ooxml

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
        used = -(-len(data) // MINI)      # an empty stream occupies no sector
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

    out[0:8] = office_container.OLE_MAGIC
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
    return biff(office_biff.BOUNDSHEET, struct.pack('<IBB', 0, 0, 0) + bytes([len(name), 0x01]) + body)


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
        return biff(office_biff.SST, head + before)
    return biff(office_biff.SST, head + before) + biff(office_biff.CONTINUE, after)


def ppt_atom(rec_type, payload, container=False):
    ver = 0x0F if container else 0x00
    return struct.pack('<HHI', ver, rec_type, len(payload)) + payload


class OleTests(unittest.TestCase):
    def test_reads_a_large_stream_from_the_regular_chain(self):
        blob = bytes(range(256)) * 40           # 10240 bytes, well over the cutoff
        ole = office_container.OleFile(build_ole({'Workbook': blob}))
        self.assertEqual(ole.stream('Workbook'), blob)

    def test_reads_a_small_stream_from_the_mini_stream(self):
        blob = b'tiny payload' * 10             # 120 bytes, under the cutoff
        ole = office_container.OleFile(build_ole({'Workbook': blob}))
        self.assertEqual(ole.stream('Workbook'), blob)

    def test_stream_lookup_is_case_insensitive_and_missing_is_empty(self):
        ole = office_container.OleFile(build_ole({'Workbook': b'x' * 100}))
        self.assertEqual(ole.stream('WORKBOOK'), b'x' * 100)
        self.assertEqual(ole.stream('NoSuchStream'), b'')

    def test_a_non_ole_file_is_refused(self):
        with self.assertRaises(ValueError):
            office_container.OleFile(b'not an ole file at all')


class XlsTests(unittest.TestCase):
    def book(self, records):
        return build_ole({'Workbook': b''.join(records)})

    def test_sheet_names_and_strings_come_back(self):
        raw = self.book([boundsheet('Demand Chart'), boundsheet('Source_Data'),
                         sst(['MFG Revenue ($M)', 'Top 4 US Cloud'])])
        text, meta = office_biff.xls_text(raw)
        self.assertEqual(meta['sheets'], 2)
        self.assertIn('Demand Chart | Source_Data', text)
        self.assertIn('MFG Revenue ($M)', text)
        self.assertIn('Top 4 US Cloud', text)

    def test_cjk_survives(self):
        raw = self.book([boundsheet('数据中心机柜清单'),
                         sst(['中国移动IDC资质', 'Uptime Tier III 认证'])])
        text, _ = office_biff.xls_text(raw)
        self.assertIn('数据中心机柜清单', text)
        self.assertIn('中国移动IDC资质', text)
        self.assertIn('Uptime Tier III 认证', text)

    def test_a_string_table_split_across_a_continue_record(self):
        strings = ['第%d季度机柜功率密度报告' % i for i in range(12)]
        raw = self.book([sst(strings, split_in=5)])    # splits inside string 5
        text, meta = office_biff.xls_text(raw)
        self.assertEqual(meta['shared_strings'], 12,
                         'CONTINUE handling dropped part of the table')
        for s in strings:
            self.assertIn(s, text)

    def test_a_workbook_without_the_stream_reports_why(self):
        raw = build_ole({'Nonsense': b'z' * 100})
        text, meta = office_biff.xls_text(raw)
        self.assertEqual(text, '')
        self.assertIn('no Workbook stream', meta['extract_error'])


class PptTests(unittest.TestCase):
    def deck(self, atoms):
        return build_ole({'PowerPoint Document': b''.join(atoms)})

    def test_byte_and_char_atoms_are_both_read(self):
        raw = self.deck([
            ppt_atom(office_ppt.TEXT_BYTES_ATOM, b'Modular Data Center'),
            ppt_atom(office_ppt.TEXT_CHARS_ATOM, '模块化数据中心解决方案'.encode('utf-16-le')),
        ])
        text, meta = office_ppt.ppt_text(raw)
        self.assertIn('Modular Data Center', text)
        self.assertIn('模块化数据中心解决方案', text)
        self.assertEqual(meta['text_atoms'], 2)

    def test_atoms_nested_in_containers_are_found(self):
        inner = ppt_atom(office_ppt.TEXT_CHARS_ATOM, '机房工程整体设计'.encode('utf-16-le'))
        raw = self.deck([ppt_atom(0x0FF0, ppt_atom(0x0FF0, inner, container=True), container=True)])
        text, _ = office_ppt.ppt_text(raw)
        self.assertIn('机房工程整体设计', text)

    def test_a_truncated_record_does_not_raise(self):
        raw = self.deck([struct.pack('<HHI', 0, office_ppt.TEXT_CHARS_ATOM, 9999) + b'ab'])
        text, _ = office_ppt.ppt_text(raw)
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
        return ppt_atom(office_ppt.TEXT_CHARS_ATOM, text.encode('utf-16-le'))

    def test_master_placeholder_text_is_not_collected(self):
        raw = self.deck([
            ppt_atom(0x03F8, self.slide_text('单击此处编辑母版标题样式'), container=True),
            ppt_atom(0x03EE, self.slide_text('模块化数据中心交付方案'), container=True),
        ])
        text, _ = office_ppt.ppt_text(raw)
        self.assertIn('模块化数据中心交付方案', text)
        self.assertNotIn('母版标题样式', text, 'the template text crowded the preview')

    def test_handout_text_is_not_collected(self):
        raw = self.deck([
            ppt_atom(0x0FC9, self.slide_text('讲义页眉'), container=True),
            ppt_atom(0x03EE, self.slide_text('机柜功率密度'), container=True),
        ])
        text, _ = office_ppt.ppt_text(raw)
        self.assertIn('机柜功率密度', text)
        self.assertNotIn('讲义页眉', text)

    def test_a_deck_that_is_only_a_master_yields_nothing(self):
        raw = self.deck([ppt_atom(0x03F8, self.slide_text('单击此处编辑母版'), container=True)])
        text, _ = office_ppt.ppt_text(raw)
        self.assertEqual(text, '')

    def test_ordinary_slides_are_unaffected(self):
        raw = self.deck([self.slide_text('第一页'), self.slide_text('第二页')])
        text, _ = office_ppt.ppt_text(raw)
        self.assertIn('第一页', text)
        self.assertIn('第二页', text)


class PermanentFailureTests(unittest.TestCase):
    """Every "the container is fine but has no text" exit must say so.

    Three of these exist and only one was flagged, so the other two read as
    transient: the file returned to the re-read queue, came out identical, and
    went back again.  A 37 MB .ppt looped that way until the queue visibly
    refused to drain, and the .xls twin was still unflagged after the .ppt was
    fixed.  Enumerating them here is the point - a fourth exit that forgets
    the flag fails this test rather than a production run.
    """

    def containers(self):
        """Each case: an OLE file whose named stream exists but is empty."""
        return {
            'xls': build_ole({'Workbook': b''}),
            'ppt': build_ole({'PowerPoint Document': b''}),
            'unknown': build_ole({'VisioDocument': b'x' * 100}),
        }

    def test_every_permanent_failure_sets_the_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, raw in self.containers().items():
                path = Path(tmp) / (name + '.bin')
                path.write_bytes(raw)
                _, meta = O.extract(path)
                self.assertTrue(meta.get('no_text_layer'),
                                '%s reports a permanent failure as transient: %r' % (name, meta))
                self.assertTrue(meta.get('extract_error'),
                                '%s gives no reason' % name)

    def test_a_transient_failure_is_not_flagged(self):
        """A file that is not there may be there next time; do not give up."""
        _, meta = O.extract(Path('/nonexistent/never-written.xlsx'))
        self.assertFalse(meta.get('no_text_layer'), meta)
        self.assertIn('extract_error', meta)

    def test_a_readable_workbook_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'real.xlsx'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('xl/workbook.xml', '<workbook><sheet name="数据"/></workbook>')
                z.writestr('xl/sharedStrings.xml', '<sst><si><t>合计</t></si></sst>')
            text, meta = O.extract(path)
            self.assertIn('合计', text)
            self.assertFalse(meta.get('no_text_layer'), meta)

    def test_the_helper_is_what_produces_the_flag(self):
        text, meta = office_grid.no_text_layer('某种原因')
        self.assertEqual(text, '')
        self.assertTrue(meta['no_text_layer'])
        self.assertEqual(meta['extract_error'], '某种原因')



# --------------------------------------------------------------------------
# cells
# --------------------------------------------------------------------------

def bof(sheet=True):
    return biff(office_biff.BOF, struct.pack('<HH', 0x0600, 0x0010 if sheet else 0x0005))


def number(row, col, value, xf=0):
    return biff(office_biff.NUMBER_REC, struct.pack('<HHH', row, col, xf) + struct.pack('<d', value))


def rk(row, col, bits, xf=0):
    return biff(office_biff.RK_REC, struct.pack('<HHHI', row, col, xf, bits))


def labelsst(row, col, index, xf=0):
    return biff(office_biff.LABELSST, struct.pack('<HHHI', row, col, xf, index))


def xf_record(fmt_id):
    return biff(office_biff.XF_REC, struct.pack('<HH', 0, fmt_id) + b'\x00' * 16)


def fmt_record(fmt_id, code):
    return biff(office_biff.FORMAT_REC, struct.pack('<H', fmt_id)
                + struct.pack('<HB', len(code), 0x01) + code.encode('utf-16-le'))


class NumberRenderingTests(unittest.TestCase):
    def test_a_whole_number_loses_its_decimal_point(self):
        self.assertEqual(office_grid.number_text(4406.0, False), '4406')

    def test_binary_noise_is_trimmed_but_the_value_is_not_rounded_away(self):
        self.assertEqual(office_grid.number_text(0.5800000000000001, False), '0.58')
        self.assertEqual(office_grid.number_text(3736.6, False), '3736.6')

    def test_a_serial_under_the_phantom_leap_day_stays_a_number(self):
        """Serial 60 is Excel's 1900-02-29, which never existed."""
        self.assertIsNone(office_grid.serial_to_iso(60))
        self.assertEqual(office_grid.number_text(60.0, True), '60')

    def test_a_dated_serial_becomes_a_date(self):
        self.assertEqual(office_grid.number_text(45292.0, True), '2024-01-01')

    def test_a_number_is_only_a_date_when_its_format_says_so(self):
        self.assertEqual(office_grid.number_text(45292.0, False), '45292')

    def test_a_currency_format_with_a_quoted_suffix_is_not_a_date(self):
        """0.00"元" contains no date code; the quoted text is not one either."""
        self.assertFalse(office_grid.is_date_format('0.00"元"', 176))
        self.assertTrue(office_grid.is_date_format('yyyy"年"m"月"', 177))

    def test_builtin_date_ids_need_no_format_string(self):
        self.assertTrue(office_grid.is_date_format(None, 14))
        self.assertFalse(office_grid.is_date_format(None, 0))

    def test_columns_past_z(self):
        self.assertEqual([office_grid.col_index('A1'), office_grid.col_index('Z9'), office_grid.col_index('AB3')],
                         [0, 25, 27])


class XlsxCellTests(unittest.TestCase):
    """The regression that mattered: numbers, and where they sat."""

    def make(self, sheet, shared=None, styles=None, sheets=('Sheet1',)):
        tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        wb = '<workbook>' + ''.join('<sheet name="%s"/>' % n for n in sheets) + '</workbook>'
        with zipfile.ZipFile(tmp.name, 'w') as z:
            z.writestr('xl/workbook.xml', wb)
            if shared is not None:
                z.writestr('xl/sharedStrings.xml', '<sst>%s</sst>' % ''.join(shared))
            if styles is not None:
                z.writestr('xl/styles.xml', styles)
            for i, body in enumerate(sheet if isinstance(sheet, list) else [sheet]):
                z.writestr('xl/worksheets/sheet%d.xml' % (i + 1), body)
        return Path(tmp.name)

    def read(self, **kw):
        p = self.make(**kw)
        try:
            return O.extract(p)
        finally:
            p.unlink()

    def test_a_number_reaches_the_text_at_all(self):
        """Before this, every numeric cell in the corpus was silently dropped."""
        text, meta = self.read(sheet='<worksheet><sheetData><row r="7">'
                                     '<c r="A7" t="s"><v>0</v></c>'
                                     '<c r="B7"><v>4406</v></c>'
                                     '</row></sheetData></worksheet>',
                               shared=['<si><t>楼面荷载</t></si>'])
        self.assertIn('楼面荷载\t4406', text)
        self.assertEqual(meta['cells'], 2)

    # -- 合并单元格 -------------------------------------------------------
    # 冷源工程表-09：小计行的值写在合并区的左上角，其余格在 XML 里不存在，
    # 渲染成空白后读者把右边一列的数读成了那一列的数（4067+165+2593+67 ≠
    # 2825.41），逐项人工费因此加出 94.8 万、与表-04 的 62.9 万对不上。
    MERGED = ('<worksheet><sheetData>'
              '<row r="5"><c r="A5"><v>1</v></c><c r="E5"><v>2825.41</v></c></row>'
              '</sheetData>'
              '<mergeCells count="1"><mergeCell ref="A5:D5"/></mergeCells>'
              '</worksheet>')

    def test_a_merged_range_is_marked_so_the_span_is_visible(self):
        text, _ = self.read(sheet=self.MERGED)
        self.assertIn('5\t1\t〃\t〃\t〃\t2825.41', text)

    def test_the_mark_is_explained_once(self):
        text, _ = self.read(sheet=self.MERGED)
        self.assertEqual(text.count('同属一个合并单元格'), 1)

    def test_the_mark_is_not_counted_as_a_cell(self):
        """cells 是 35,895 份文件的判定依据，不能被记号灌水。"""
        _, meta = self.read(sheet=self.MERGED)
        self.assertEqual(meta['cells'], 2)

    def test_an_empty_merged_range_says_nothing(self):
        text, _ = self.read(sheet='<worksheet><sheetData>'
                                  '<row r="5"><c r="E5"><v>1</v></c></row></sheetData>'
                                  '<mergeCells><mergeCell ref="A5:D5"/></mergeCells>'
                                  '</worksheet>')
        self.assertNotIn('〃', text)

    def test_a_merged_range_never_writes_over_a_value(self):
        text, _ = self.read(sheet='<worksheet><sheetData><row r="5">'
                                  '<c r="A5"><v>1</v></c><c r="C5"><v>7</v></c>'
                                  '</row></sheetData>'
                                  '<mergeCells><mergeCell ref="A5:D5"/></mergeCells>'
                                  '</worksheet>')
        self.assertIn('5\t1\t〃\t7\t〃', text)

    def test_a_malformed_merge_ref_is_ignored(self):
        text, _ = self.read(sheet='<worksheet><sheetData>'
                                  '<row r="5"><c r="A5"><v>1</v></c></row></sheetData>'
                                  '<mergeCells><mergeCell ref="A5:D"/></mergeCells>'
                                  '</worksheet>')
        self.assertIn('5\t1', text)

    def test_huge_merged_range_is_rejected_before_expanding(self):
        cells = {(1, 0): 'heading'}
        with self.assertRaisesRegex(ValueError, 'exceeds_extraction_budget'):
            office_ooxml.mark_merges(cells, '<mergeCell ref="A1:XFD1048576"/>')
        self.assertEqual({(1, 0): 'heading'}, cells)

    def test_merge_budget_is_cumulative_and_invalid_ranges_fail(self):
        with self.assertRaisesRegex(ValueError, 'exceeds_extraction_budget'):
            office_ooxml.mark_merges({(1, 0): 'a', (2, 0): 'b'},
                                    '<mergeCell ref="A1:C1"/><mergeCell ref="A2:C2"/>', max_cells=5)
        with self.assertRaisesRegex(ValueError, 'invalid_merged_cell_range'):
            office_ooxml.mark_merges({(2, 0): 'a'}, '<mergeCell ref="A2:C1"/>')

    def test_a_gap_is_kept_so_a_value_stays_under_its_header(self):
        text, _ = self.read(sheet='<worksheet><sheetData><row r="3">'
                                  '<c r="A3"><v>1</v></c><c r="D3"><v>2</v></c>'
                                  '</row></sheetData></worksheet>')
        self.assertIn('3\t1\t\t\t2', text)

    def test_rich_text_does_not_shift_the_shared_string_index(self):
        """Two <t> runs in one <si> are one string, not two."""
        text, _ = self.read(
            sheet='<worksheet><sheetData><row r="1">'
                  '<c r="A1" t="s"><v>1</v></c></row></sheetData></worksheet>',
            shared=['<si><r><t>机柜</t></r><r><t>功率</t></r></si>', '<si><t>第二条</t></si>'])
        self.assertIn('第二条', text)
        self.assertNotIn('机柜', text)

    def test_a_dated_cell_is_rendered_as_a_date(self):
        styles = ('<styleSheet><numFmts><numFmt numFmtId="176" formatCode="yyyy-mm-dd"/>'
                  '</numFmts><cellXfs><xf numFmtId="0"/><xf numFmtId="176"/></cellXfs>'
                  '</styleSheet>')
        text, _ = self.read(sheet='<worksheet><sheetData><row r="1">'
                                  '<c r="A1" s="1"><v>45292</v></c>'
                                  '<c r="B1" s="0"><v>45292</v></c>'
                                  '</row></sheetData></worksheet>', styles=styles)
        self.assertIn('2024-01-01\t45292', text)

    def test_formula_results_and_booleans_come_through(self):
        text, _ = self.read(sheet='<worksheet><sheetData><row r="2">'
                                  '<c r="A2"><f>SUM(B:B)</f><v>1234.5</v></c>'
                                  '<c r="B2" t="str"><v>合计</v></c>'
                                  '<c r="C2" t="b"><v>1</v></c>'
                                  '</row></sheetData></worksheet>')
        self.assertIn('1234.5\t合计\tTRUE', text)

    def test_each_sheet_is_labelled(self):
        text, _ = self.read(
            sheet=['<worksheet><sheetData><row r="1"><c r="A1"><v>1</v></c></row></sheetData></worksheet>',
                   '<worksheet><sheetData><row r="1"><c r="A1"><v>2</v></c></row></sheetData></worksheet>'],
            sheets=('造价汇总', '分项明细'))
        self.assertIn('== 工作表: 造价汇总 ==', text)
        self.assertIn('== 工作表: 分项明细 ==', text)

    def test_a_sheet_with_no_addressable_cells_still_yields_its_labels(self):
        text, _ = self.read(sheet='<worksheet/>', shared=['<si><t>只有图表</t></si>'])
        self.assertIn('只有图表', text)


class DrawingTests(unittest.TestCase):
    """688d46ed 的署名是一张水印，重复在五个 drawing 里，单元格里一个字都没有。

    表格的出处常常不在表格里。取数的读者只看单元格，于是 L1 判它出处未知，
    而机构名一直就在文件中。
    """

    SHEET = ('<worksheet><sheetData><row r="1">'
             '<c r="A1"><v>4406</v></c></row></sheetData></worksheet>')

    def make(self, drawings, sheet=None):
        tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        with zipfile.ZipFile(tmp.name, 'w') as z:
            z.writestr('xl/workbook.xml', '<workbook><sheet name="Sheet1"/></workbook>')
            z.writestr('xl/worksheets/sheet1.xml', self.SHEET if sheet is None else sheet)
            for i, body in enumerate(drawings):
                z.writestr('xl/drawings/drawing%d.xml' % (i + 1), body)
        return Path(tmp.name)

    def read(self, drawings, sheet=None):
        path = self.make(drawings, sheet)
        try:
            return O.extract(path)
        finally:
            path.unlink()

    @staticmethod
    def shape(*paragraphs):
        return ('<xdr:wsDr>' + ''.join(
            '<xdr:sp><xdr:txBody>' + p + '</xdr:txBody></xdr:sp>'
            for p in paragraphs) + '</xdr:wsDr>')

    @staticmethod
    def para(*runs):
        return '<a:p>' + ''.join('<a:r><a:t>%s</a:t></a:r>' % r for r in runs) + '</a:p>'

    def test_a_watermark_reaches_the_text(self):
        text, meta = self.read([self.shape(self.para('知识星球：Global Semi Research'))])
        self.assertIn('知识星球：Global Semi Research', text)
        self.assertEqual(meta['drawing_lines'], 1)

    def test_it_lands_before_the_grid(self):
        """L1 判的是预览，而表格的预览就是表头——落在单元格后面的署名它看不到。"""
        text, _ = self.read([self.shape(self.para('Global Semi Research'))])
        self.assertLess(text.index('Global Semi Research'), text.index('4406'))

    def test_the_same_line_in_five_drawings_is_one_line_counted_five_times(self):
        one = self.shape(self.para('知识星球：Global Semi Research'))
        text, meta = self.read([one] * 5)
        self.assertEqual(text.count('知识星球'), 1)
        self.assertIn('×5', text)
        self.assertEqual(meta['drawing_lines'], 1)

    def test_a_one_off_label_carries_no_count(self):
        text, _ = self.read([self.shape(self.para('单位：亿美元'))])
        self.assertIn('单位：亿美元', text)
        self.assertNotIn('×', text)

    def test_runs_inside_one_paragraph_are_one_line(self):
        """一行被拆成几个 run 是排版的事，不该拆成几行。"""
        text, meta = self.read([self.shape(self.para('知识星球：', 'Global ', 'Semi Research'))])
        self.assertIn('知识星球：Global Semi Research', text)
        self.assertEqual(meta['drawing_lines'], 1)

    def test_two_paragraphs_are_two_lines(self):
        text, meta = self.read([self.shape(self.para('数据来源：IDC'), self.para('2025 年 3 月'))])
        self.assertEqual(meta['drawing_lines'], 2)
        self.assertIn('数据来源：IDC', text)
        self.assertIn('2025 年 3 月', text)

    def test_the_cells_still_come_through(self):
        text, meta = self.read([self.shape(self.para('水印'))])
        self.assertIn('4406', text)
        self.assertEqual(meta['cells'], 1)

    def test_entities_are_decoded(self):
        text, _ = self.read([self.shape(self.para('A &amp; B 研究院'))])
        self.assertIn('A & B 研究院', text)

    def test_an_empty_paragraph_is_not_a_line(self):
        text, meta = self.read([self.shape('<a:p/>', self.para('IDC'))])
        self.assertEqual(meta['drawing_lines'], 1)
        self.assertIn('IDC', text)

    def test_a_workbook_with_no_drawings_is_unchanged(self):
        text, meta = self.read([])
        self.assertEqual(meta['drawing_lines'], 0)
        self.assertNotIn('文本框/水印', text)

    def test_a_chart_only_workbook_still_yields_its_shape_text(self):
        """一张只有图表的表：单元格是空的，说明全在文本框里。"""
        text, meta = self.read([self.shape(self.para('图 3：全球服务器出货量'))],
                               sheet='<worksheet><sheetData/></worksheet>')
        self.assertEqual(meta['cells'], 0)
        self.assertIn('图 3：全球服务器出货量', text)


class XlsCellTests(unittest.TestCase):
    def book(self, records):
        return build_ole({'Workbook': b''.join(records)})

    def test_a_number_record_reaches_the_text(self):
        """Before this, every numeric cell in every .xls was silently dropped."""
        text, meta = office_biff.xls_text(self.book([
            boundsheet('工艺要求'), bof(sheet=False), bof(), number(6, 1, 8.0)]))
        self.assertIn('8', text)
        self.assertEqual(meta['cells'], 1)

    def test_a_label_and_its_number_land_side_by_side(self):
        text, _ = office_biff.xls_text(self.book([
            boundsheet('工艺要求'), sst(['楼面荷载 kN/㎡']), bof(sheet=False), bof(),
            labelsst(6, 0, 0), number(6, 1, 8.0)]))
        self.assertIn('楼面荷载 kN/㎡\t8', text)

    def test_rk_encodings_all_decode(self):
        cases = {(100 << 2) | 0x02: '100',            # integer
                 (12345 << 2) | 0x03: '123.45',       # integer, divided by 100
                 struct.unpack('<I', struct.pack('<d', 2.5)[4:])[0] & 0xFFFFFFFC: '2.5'}
        for bits, want in cases.items():
            text, _ = office_biff.xls_text(self.book([boundsheet('S'), bof(sheet=False),
                                            bof(), rk(0, 0, bits)]))
            self.assertIn(want, text, hex(bits))

    def test_a_negative_rk_integer_keeps_its_sign(self):
        bits = ((-37 & 0x3FFFFFFF) << 2) | 0x02
        text, _ = office_biff.xls_text(self.book([boundsheet('S'), bof(sheet=False),
                                        bof(), rk(0, 0, bits)]))
        self.assertIn('-37', text)

    def test_a_mulrk_span_fills_consecutive_columns(self):
        body = struct.pack('<HH', 4, 2)                       # row 4, first col 2
        for value in (10, 20, 30):
            body += struct.pack('<HI', 0, (value << 2) | 0x02)
        body += struct.pack('<H', 4)                          # last col
        text, meta = office_biff.xls_text(self.book([boundsheet('S'), bof(sheet=False), bof(),
                                           biff(office_biff.MULRK_REC, body)]))
        self.assertIn('10\t20\t30', text)
        self.assertEqual(meta['cells'], 3)

    def test_a_formula_keeps_its_cached_number(self):
        payload = struct.pack('<HHH', 1, 1, 0) + struct.pack('<d', 79483818.9)
        text, _ = office_biff.xls_text(self.book([boundsheet('S'), bof(sheet=False), bof(),
                                        biff(office_biff.FORMULA_REC, payload)]))
        self.assertIn('79483818.9', text)

    def test_a_formula_with_a_string_result_takes_the_following_record(self):
        payload = (struct.pack('<HHH', 1, 1, 0) + b'\x00' * 6 + b'\xff\xff')
        follow = struct.pack('<HB', 3, 0x01) + '招标价'.encode('utf-16-le')
        text, _ = office_biff.xls_text(self.book([boundsheet('S'), bof(sheet=False), bof(),
                                        biff(office_biff.FORMULA_REC, payload),
                                        biff(office_biff.STRING_REC, follow)]))
        self.assertIn('招标价', text)

    def test_a_dated_cell_uses_its_format_record(self):
        raw = self.book([boundsheet('S'), fmt_record(176, 'yyyy-mm-dd'),
                         xf_record(0), xf_record(176),
                         bof(sheet=False), bof(),
                         number(0, 0, 45292.0, xf=1), number(0, 1, 45292.0, xf=0)])
        text, _ = office_biff.xls_text(raw)
        self.assertIn('2024-01-01\t45292', text)

    def test_cells_land_under_the_sheet_they_belong_to(self):
        raw = self.book([boundsheet('第一张'), boundsheet('第二张'), bof(sheet=False),
                         bof(), number(0, 0, 11.0),
                         bof(), number(0, 0, 22.0)])
        text, _ = office_biff.xls_text(raw)
        second = text.index('== 工作表: 第二张 ==')
        self.assertLess(text.index('11'), second)
        self.assertGreater(text.index('22'), second)

    def test_a_workbook_with_only_a_string_table_still_yields_it(self):
        text, _ = office_biff.xls_text(self.book([boundsheet('S'), sst(['只有标签'])]))
        self.assertIn('只有标签', text)

if __name__ == '__main__':
    unittest.main()
