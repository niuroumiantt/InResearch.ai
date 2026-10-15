import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from inresearch.materials.collector_receive import receive, lookup_receipt
from tests.unit.test_collector_handoff import example


class CollectorReceiptLookupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.package=example.build(self.root/'input','fetchquotes')
        self.sandbox=self.root/'sandbox'
    def snapshot(self):
        return {str(p.relative_to(self.sandbox)):(p.read_bytes(),p.stat().st_mtime_ns)
                for p in self.sandbox.rglob('*') if p.is_file()}
    def test_missing_lookup_does_not_create_state(self):
        self.assertIsNone(lookup_receipt(self.sandbox,'fetchquotes','unknown'))
        self.assertFalse(self.sandbox.exists())
    def test_lookup_preserves_all_bytes_mtimes_and_first_clock(self):
        first=receive(self.package,self.sandbox);before=self.snapshot()
        found=lookup_receipt(self.sandbox,'fetchquotes',first['delivery_id'])
        self.assertEqual(found['first_received_at'],first['first_received_at']);self.assertTrue(found['lookup_only'])
        self.assertTrue(all(v==0 for v in found['current_receive_counts'].values()))
        self.assertEqual(before,self.snapshot());self.assertTrue(found['local_only'])
        self.assertIsNone(lookup_receipt(self.sandbox,'fetchquotes','not-found'))
        self.assertEqual(before,self.snapshot())
    def test_unmarked_and_production_directory_rejected(self):
        self.sandbox.mkdir();(self.sandbox/'unique.txt').write_text('keep')
        with self.assertRaises(ValueError):lookup_receipt(self.sandbox,'fetchquotes','unknown')
        self.assertEqual((self.sandbox/'unique.txt').read_text(),'keep')
    def test_changed_archive_or_candidate_ledger_never_yields_ack(self):
        first=receive(self.package,self.sandbox)
        with sqlite3.connect(self.sandbox/'receipts.sqlite3') as db:
            db.execute("UPDATE observations SET payload='{}'")
        with self.assertRaisesRegex(ValueError,'candidate ledger'):lookup_receipt(self.sandbox,'fetchquotes',first['delivery_id'])
    def test_changed_archive_is_not_repaired(self):
        first=receive(self.package,self.sandbox);p=next((self.sandbox/'packages').rglob('observations.jsonl'))
        p.write_text('corrupt-copy')
        with self.assertRaises(ValueError):lookup_receipt(self.sandbox,'fetchquotes',first['delivery_id'])
        self.assertEqual(p.read_text(),'corrupt-copy')
    def test_symlink_and_forged_receipt_authority_are_rejected(self):
        first=receive(self.package,self.sandbox)
        with sqlite3.connect(self.sandbox/'receipts.sqlite3') as db:
            receipt=json.loads(db.execute('SELECT receipt FROM deliveries').fetchone()[0]);receipt['local_only']=False
            db.execute('UPDATE deliveries SET receipt=?',(json.dumps(receipt),))
        with self.assertRaises(ValueError):lookup_receipt(self.sandbox,'fetchquotes',first['delivery_id'])
        alias=self.root/'alias';alias.symlink_to(self.sandbox,target_is_directory=True)
        with self.assertRaises(ValueError):lookup_receipt(alias,'fetchquotes',first['delivery_id'])
