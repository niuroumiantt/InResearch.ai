#!/usr/bin/env python3
"""`batch record` must hold a judgement to the same schema the API path does.

On 2026-09-19 a terminal executor judged 12,764 files through pack/record.
Fifteen lines came back with the doc_type value in the module field --
`whitepaper`, `report`, `presentation`, `financial` -- plus one `unreated`.
`parse_verdicts` only splits on `|`; `cmd_record` never called
`validate_judgement`; `finalize` copies module straight into category.  The
ledger accepted all sixteen, and `organize library plan` then proposed five
top-level directories named after document types.  The API path has always
validated (workflow/triage.py); this is the same gate on the other door.
"""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import types
import unittest

from inresearch.materials import triage as L1
from inresearch.materials.records import current_results
from inresearch.workflow import terminal_batch as PK

SHA = '%064x' % 0x8cbdfd644919
ID = SHA[:12]


def write(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                    encoding='utf-8')


class RecordValidatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='record-validates-')
        base = Path(self.temp.name)
        self.results = base / 'l1_results.jsonl'
        self.results.write_text('', encoding='utf-8')
        inventory = base / 'inventory.jsonl'
        write(inventory, [{
            'schema_version': 2, 'sha256': SHA, 'size_bytes': 4096, 'suffix': '.pdf',
            'original_rel': 'x/华为WLAN物联网融合技术白皮书.pdf',
            'original_name': '华为WLAN物联网融合技术白皮书.pdf',
            'l0_bucket': 'text_candidate', 'route': 'l1_preview'}])
        batches = base / 'batches'
        batches.mkdir()
        (batches / 'batch.json').write_text(json.dumps([{
            'id': ID, 'path': 'x/华为WLAN物联网融合技术白皮书.pdf', 'level': 'p',
            'preview': '企业无线局域网与物联网融合' * 20, 'meta': {}}]), encoding='utf-8')
        self.verdicts = base / 'verdicts.txt'
        self._saved = (L1.RESULTS, L1.INVENTORY, PK.BATCH_DIR)
        L1.RESULTS, L1.INVENTORY, PK.BATCH_DIR = self.results, inventory, batches

    def tearDown(self):
        (L1.RESULTS, L1.INVENTORY, PK.BATCH_DIR) = self._saved
        self.temp.cleanup()

    def record(self, line):
        self.verdicts.write_text(line + '\n', encoding='utf-8')
        out = io.StringIO()
        with redirect_stdout(out):
            PK.cmd_record(types.SimpleNamespace(verdicts=str(self.verdicts), batch=None,
                                                digests=False, executor='test', model=None))
        return json.loads(out.getvalue().strip().splitlines()[-1])

    def test_a_doc_type_in_the_module_field_is_rejected_not_filed(self):
        # The exact shape of the real failure: module duplicated from doc_type.
        report = self.record(
            ID + '|2|whitepaper|whitepaper|未知|华为|华为 WLAN 物联网融合技术白皮书|1|m|泛IT白皮书')
        self.assertEqual(report['recorded'], 0)
        self.assertEqual(report['rejected'], 1)
        self.assertEqual(current_results(self.results), {},
                         'a judgement that fails the schema must not reach the ledger')

    def test_the_rejection_names_the_id_and_the_field(self):
        # Sixteen silent rows cost a morning of forensics; the operator needs
        # exactly what to feed `pack --sha` next.
        report = self.record(
            ID + '|2|whitepaper|whitepaper|未知|华为|华为 WLAN 物联网融合技术白皮书|1|m|泛IT白皮书')
        self.assertEqual(report['invalid_total'], 1)
        self.assertEqual(report['invalid'][0]['id'], ID)
        self.assertEqual(report['invalid'][0]['reason'], 'invalid_judgement:module')

    def test_a_score_out_of_range_is_rejected_the_same_way(self):
        report = self.record(
            ID + '|11|unrelated|whitepaper|未知|华为|华为 WLAN 物联网融合技术白皮书|1|m|越界')
        self.assertEqual(report['rejected'], 1)
        self.assertEqual(report['invalid'][0]['reason'], 'invalid_judgement:score')
        self.assertEqual(current_results(self.results), {})

    def test_a_valid_line_is_still_filed(self):
        # Control: the gate must not reject what the schema accepts.
        report = self.record(
            ID + '|2|unrelated|whitepaper|未知|华为|华为 WLAN 物联网融合技术白皮书|1|m|泛IT白皮书')
        self.assertEqual(report['recorded'], 1)
        self.assertEqual(report['rejected'], 0)
        self.assertNotIn('invalid', report)
        filed = current_results(self.results)[SHA]
        self.assertEqual(filed['module'], 'unrelated')
        self.assertEqual(filed['category'], '_review')
        self.assertEqual(filed['executor'], 'test')


if __name__ == '__main__':
    unittest.main()
