import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from inresearch.adapters.xlsx_document import Workbook, matches_value


def workbook_bytes(sheet=None, relationship=None, shared=None):
    stream = io.BytesIO()
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with ZipFile(stream, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="'+ns+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><workbookPr date1904="1"/><sheets><sheet name="Forecast 2025e" sheetId="1" r:id="r1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', relationship or '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/sharedStrings.xml', shared or '<sst xmlns="'+ns+'"><si><r><t>Forecast </t></r><r><t>2025e</t></r></si></sst>')
        z.writestr('xl/worksheets/sheet1.xml', sheet or '<worksheet xmlns="'+ns+'"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="inlineStr"><is><t>MW</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>TEST-64</t></is></c><c r="C2" s="7"><v>64.00</v></c><c r="D2"><f>1+2</f><v>999</v></c><c r="E2" t="e"><v>#N/A</v></c></row><row r="3"><c r="A3" t="inlineStr"><is><t>Source footnote; estimate, not actual</t></is></c></row></sheetData><mergeCells><mergeCell ref="A1:B1"/></mergeCells></worksheet>')
    return stream.getvalue()


class NativeXlsxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'source.xlsx'; self.path.write_bytes(workbook_bytes())
        self.loc = 'xlsx:sheet:1:cell:C2:context:A1:E3'

    def test_native_context_keeps_headers_footnotes_units_merges_and_date_mode(self):
        cell, context = Workbook(self.path).select(self.loc)
        doc = json.loads(context)
        self.assertTrue(doc['date1904']); self.assertEqual(doc['sheet_name'], 'Forecast 2025e')
        self.assertEqual(doc['merged_ranges'], ['A1:B1'])
        self.assertIn('Source footnote',context); self.assertIn('Forecast 2025e',context)
        self.assertIn('MW',context); self.assertEqual(cell['style'],'7')
        self.assertEqual(cell['value'],'64.00')
        self.assertIn('999',context); self.assertIn('1+2',context)
        self.assertEqual(Workbook(self.path).select(self.loc)[1],context)

    def test_exact_values_reject_boolean_rounding_and_unit_rewrites(self):
        cell, _ = Workbook(self.path).select(self.loc)
        for v in [64,64.0,'64.00']: self.assertTrue(matches_value(cell,v))
        for v in [True,63.999,'64','64 MW',{'value_range':[63,65]},float('nan')]:
            self.assertFalse(matches_value(cell,v))
        self.assertFalse(matches_value({'type':'s','value':'64'},64))

    def test_formula_cached_values_and_errors_cannot_be_adopted(self):
        book=Workbook(self.path)
        for cell in ['D2','E2','B2']:
            with self.assertRaisesRegex(ValueError,'nonformula'):
                book.select(self.loc.replace('cell:C2','cell:'+cell))

    def test_context_is_bounded_contains_selected_cell_and_full_merged_header(self):
        for loc in ['xlsx:sheet:2:cell:C2:context:A1:E3',
                    'xlsx:sheet:1:cell:C2:context:A1:B3',
                    'xlsx:sheet:1:cell:C2:context:B1:E3',
                    'xlsx:sheet:1:cell:C2:context:A1:XFD1048576',
                    'xlsx:sheet:1:cell:C2:context:E3:A1']:
            with self.assertRaises(ValueError):Workbook(self.path).select(loc)

    def test_external_relationship_and_traversal_are_rejected_without_fetch(self):
        for target in ['https://outside.test/sheet.xml','../../../outside.xml']:
            self.path.write_bytes(workbook_bytes(relationship='<Relationships><Relationship Id="r1" Target="'+target+'" TargetMode="External"/></Relationships>'))
            with self.assertRaisesRegex(ValueError,'external_sheet'):Workbook(self.path)

    def test_entities_and_duplicate_members_are_rejected(self):
        self.path.write_bytes(workbook_bytes(shared='<!DOCTYPE a [<!ENTITY a "boom">]><sst/>'))
        with self.assertRaisesRegex(ValueError,'entities'):Workbook(self.path)
        self.path.write_bytes(workbook_bytes())
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with ZipFile(self.path,'a') as z:z.writestr('xl/workbook.xml','duplicate')
        with self.assertRaisesRegex(ValueError,'archive_limits'):Workbook(self.path)

    def test_invalid_archive_and_oversize_are_rejected(self):
        self.path.write_bytes(b'not a workbook')
        with self.assertRaisesRegex(ValueError,'invalid_native'):Workbook(self.path)
        with self.path.open('wb') as f:f.truncate(20_000_001)
        with self.assertRaisesRegex(ValueError,'source_too_large'):Workbook(self.path)


if __name__ == '__main__':
    unittest.main()
