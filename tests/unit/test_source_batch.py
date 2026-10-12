"""Batching reduces repeated I/O without changing identity or source boundaries."""
import copy
import json
import unittest
from unittest.mock import patch
from tests.unit import test_source_publication as fixtures
from inresearch.workflow import source_statements as intake
from inresearch.knowledge import object_observations as ledger


class SourceBatchTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.SourcePublicationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root, self.data = fixture.root, fixture.data
        self.site, self.claims = fixture.item, fixture.claims()

    def test_one_source_snapshot_and_one_write_for_many_fields_then_no_write_replay(self):
        rows = []
        for i in range(100):
            row = copy.deepcopy(self.claims[0]); row['metric'] = 'field_'+str(i)
            rows.append(row)
        with patch.object(intake,'source',wraps=intake.source) as source, patch.object(intake,'write_json',wraps=intake.write_json) as write:
            receipt = intake.apply_batch(self.root,self.data,rows)
            self.assertEqual((receipt['registered'],receipt['held']),(100,0))
            self.assertEqual(source.call_count,2)
            self.assertEqual(write.call_count,1)
        before = (self.root/ledger.PATH).read_bytes()
        with patch.object(intake,'write_json',wraps=intake.write_json) as write:
            replay = intake.apply_batch(self.root,self.data,rows)
            self.assertEqual(replay['replayed'],100)
            write.assert_not_called()
        self.assertEqual(before,(self.root/ledger.PATH).read_bytes())

    def test_bad_identity_missing_dependency_and_bad_source_do_not_contaminate_valid_rows(self):
        missing = copy.deepcopy(self.claims[1])
        invalid = copy.deepcopy(self.claims[0]); invalid['source']['sha256'] = '0'*64
        collision = copy.deepcopy(self.claims[0]); collision['object']['name'] = 'Different name'
        rows = [missing,invalid,self.claims[0],collision,self.claims[1],self.claims[2],self.claims[3]]
        result = intake.apply_batch(self.root,self.data,rows)
        self.assertEqual((result['registered'],result['held']),(4,3))
        self.assertEqual([r['index'] for r in result['receipts']],list(range(7)))
        doc = ledger.check(ledger.load(self.root),self.root)
        self.assertEqual(len(doc['records']),4)
        self.assertEqual(len(doc['objects']),4)
        self.assertEqual(doc['objects'][self.claims[0]['object']['id']]['name'],'Name company')

    def test_source_bytes_or_receiver_provenance_change_aborts_without_partial_write(self):
        for change in ('bytes','provenance'):
            with self.subTest(change=change):
                path = self.root/ledger.PATH
                before = path.read_bytes() if path.exists() else None
                resolve = intake.source; calls = []
                def changed(*args,**kwargs):
                    snapshot = resolve(*args,**kwargs); calls.append(snapshot)
                    if len(calls) == 2:
                        if change == 'bytes': raise ValueError('source_bytes_changed')
                        return (*snapshot[:2], '2025-01-01T00:00:00+00:00', snapshot[3])
                    return snapshot
                with patch.object(intake,'source',side_effect=changed):
                    result = intake.apply_batch(self.root,self.data,self.claims)
                self.assertEqual((result['registered'],result['held']),(0,4))
                self.assertEqual(path.read_bytes() if path.exists() else None,before)

    def test_duplicate_company_name_cannot_create_second_id_and_old_records_are_unchanged(self):
        intake.apply(self.root,self.data,self.claims[0]); before = copy.deepcopy(ledger.load(self.root))
        other = copy.deepcopy(self.claims[0]); other['object'] = ledger.object_record('company',{'company_id':'different-id'},'Name company')
        result = intake.apply_batch(self.root,self.data,[other,self.claims[1]])
        self.assertEqual((result['registered'],result['held']),(1,1))
        after = ledger.load(self.root)
        self.assertEqual(after['records'][:len(before['records'])],before['records'])
        self.assertNotIn(other['object']['id'],after['objects'])

    def test_bounded_chunks_and_mixed_site_order_preserve_dependencies(self):
        rows = []
        for i in range(501):
            row = copy.deepcopy(self.claims[0]);row['metric'] = 'field_'+str(i);rows.append(row)
        with patch.object(intake,'write_json',wraps=intake.write_json) as write:
            result = intake.apply_batch(self.root,self.data,rows)
            self.assertEqual(result['registered'],501)
            self.assertEqual(write.call_count,2)
        mixed = intake.apply_batch(self.root,self.data,[self.claims[0],self.site,self.claims[1]])
        self.assertEqual(mixed['registered'],3)
        self.assertEqual([r['index'] for r in mixed['receipts']],[0,1,2])
        self.assertEqual(mixed['receipts'][1]['site_id'],self.site['site_id'])
