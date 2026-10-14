import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from inresearch.adapters.acquisition import Collector
from inresearch.materials import collector_production as production
from tests.unit.test_collector_handoff import example


class CollectorProductionTests(unittest.TestCase):
    provider = "fetchstat"
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.data=self.root/'data'
        c=Collector(self.data);c.close()
        self.package=example.build(self.root/'input',self.provider)
        self.policy=self.root/'policy';(self.policy/'framework').mkdir(parents=True)
        manifest=json.loads((self.package/'manifest.json').read_text());item=manifest['items'][0]
        policy={'collector_reception':{'enabled_providers':[self.provider],'sources':{self.provider:[{
            'source_id':item['source_id'],'native_id':item['source_item_id'],'url':item['url']}]}}}
        (self.policy/'framework/supply_contract.json').write_text(json.dumps(policy))
        self.patcher=patch.object(production,'ROOT',self.policy);self.patcher.start();self.addCleanup(self.patcher.stop)

    def receive(self):return production.receive(self.package,self.data)
    def ledger(self):return self.data/'acquisition/collectors'/self.provider/'receipts.sqlite3'
    def counts(self):
        with sqlite3.connect(self.data/'acquisition/catalog.sqlite') as db:
            return {t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('items','observations','runs')}

    def test_real_storage_ack_candidate_only_and_replay_has_no_writes(self):
        result=self.receive();counts=self.counts()
        self.assertEqual(result['status'],'received_candidate_unreviewed')
        self.assertFalse(result['local_only']);self.assertEqual(result['reader_enqueued'],0)
        self.assertFalse(result['formal_adoption']);self.assertEqual(result['model_parameters_written'],0)
        self.assertEqual(counts['items'],1);self.assertEqual(counts['observations'],1)
        again=self.receive();self.assertTrue(again['replayed']);self.assertEqual(counts,self.counts())
        self.assertEqual(result['first_received_at'],again['first_received_at'])
        self.assertEqual(result['archive_completed_at'],again['archive_completed_at'])
        self.assertTrue(all(v==0 for v in again['current_receive_counts'].values()))
        self.assertFalse((self.data/'raw-materials').exists())

    def test_projection_failure_has_no_ack_and_retry_preserves_arrival_time(self):
        with patch.object(production,'materialize',side_effect=OSError('controlled projection failure')):
            with self.assertRaises(OSError):self.receive()
        with sqlite3.connect(self.ledger()) as db:
            arrival=json.loads(db.execute('SELECT receipt FROM deliveries').fetchone()[0])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM production_acks').fetchone()[0],0)
        result=self.receive()
        self.assertEqual(result['first_received_at'],arrival['first_received_at'])
        self.assertTrue(result['recovered_after_pending'])
        self.assertEqual(self.counts()['observations'],1)

    def test_partial_catalog_write_resumes_without_duplicate_source_item(self):
        with patch.object(Collector,'archive_file',side_effect=OSError('interrupted after source registration')):
            with self.assertRaises(OSError):self.receive()
        self.assertEqual(self.counts()['items'],1);self.assertEqual(self.counts()['observations'],0)
        result=self.receive();self.assertTrue(result['recovered_after_pending'])
        self.assertEqual(self.counts()['items'],1);self.assertEqual(self.counts()['observations'],1)
        with sqlite3.connect(self.data/'acquisition/catalog.sqlite') as db:
            self.assertEqual([r[0] for r in db.execute('SELECT status FROM runs ORDER BY id')],['failed','success'])

    def test_missing_original_projection_recovers_without_new_receipt(self):
        first=self.receive();original=next(p for p in (self.data/'originals').rglob('*') if p.is_file());original.unlink()
        again=self.receive();self.assertTrue(original.exists());self.assertTrue(again['projection_repaired'])
        self.assertEqual(first['archive_completed_at'],again['archive_completed_at'])
        self.assertEqual(self.counts()['observations'],1)

    def test_tampered_transport_rejected_before_arrival_and_intact_retry_succeeds(self):
        native=next((self.package/'originals').iterdir());original=native.read_bytes();native.write_bytes(b'incomplete')
        with self.assertRaises(ValueError):self.receive()
        self.assertEqual(self.counts()['observations'],0);self.assertFalse(self.ledger().exists())
        native.write_bytes(original);self.assertEqual(self.receive()['candidate_rows'],1)

    def test_other_teams_and_unregistered_source_do_not_enter_catalog(self):
        other=example.build(self.root/'other','fetchquotes')
        with self.assertRaisesRegex(ValueError,'not_enabled'):production.receive(other,self.data)
        p=self.package/'manifest.json';manifest=json.loads(p.read_text());manifest['items'][0]['url']='https://unregistered.example/data';p.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'not_registered'):self.receive()
        self.assertEqual(self.counts()['observations'],0)

    def test_archive_sync_failure_never_acknowledges_and_intact_retry_succeeds(self):
        from inresearch.materials import collector_receive
        with patch.object(collector_receive,'sync_directory',side_effect=OSError('controlled fsync failure')):
            with self.assertRaises(OSError):self.receive()
        self.assertEqual(self.counts()['observations'],0)
        with sqlite3.connect(self.ledger()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0],0)
        self.assertEqual(self.receive()['status'],'received_candidate_unreviewed')

    def test_cli_rejects_changed_or_dirty_receiver_before_reception(self):
        import contextlib
        import io
        for outputs in (['b'*40,''],['a'*40,' M tracked.py']):
            with patch('sys.argv',['collector-receive','package','--data-root',str(self.data),'--expected-receiver-revision','a'*40]), patch.object(production.subprocess,'check_output',side_effect=outputs), patch.object(production,'receive') as receiver, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(production.main(),1)
                receiver.assert_not_called()

    def test_supplier_payload_and_unknowns_are_preserved_in_shared_catalog(self):
        manifest=json.loads((self.package/'manifest.json').read_text());rows=[json.loads((self.package/'observations.jsonl').read_text())]
        self.receive()
        with sqlite3.connect(self.data/'acquisition/catalog.sqlite') as db:
            stored=json.loads(db.execute('SELECT request_json FROM observations').fetchone()[0])
        self.assertEqual(stored['item'],manifest['items'][0]);self.assertEqual(stored['observations'],rows)
        self.assertEqual(stored['collector_revision'],manifest['collector_revision'])

class FilingsProductionTests(CollectorProductionTests):
    provider = "fetchfilings"

    def test_enabled_providers_keep_separate_roots_and_catalog_identity(self):
        other=example.build(self.root/'stat','fetchstat')
        policy=json.loads((self.policy/'framework/supply_contract.json').read_text())
        item=json.loads((other/'manifest.json').read_text())['items'][0]
        policy['collector_reception']['enabled_providers'].append('fetchstat')
        policy['collector_reception']['sources']['fetchstat']=[{
            'source_id':item['source_id'],'native_id':item['source_item_id'],'url':item['url']}]
        (self.policy/'framework/supply_contract.json').write_text(json.dumps(policy))
        first=self.receive();stat=production.receive(other,self.data)
        self.assertEqual(self.counts()['observations'],2)
        self.assertEqual(self.receive()['first_received_at'],first['first_received_at'])
        self.assertEqual(production.receive(other,self.data)['first_received_at'],stat['first_received_at'])
        with sqlite3.connect(self.data/'acquisition/catalog.sqlite') as db:
            self.assertEqual({r[0] for r in db.execute('SELECT source FROM items')},{'fetchstat','fetchfilings'})
        # Even an enabled team cannot receive another team's registered source.
        manifest=json.loads((self.package/'manifest.json').read_text())
        manifest['provider_id']='fetchstat'
        policy['collector_reception']['sources']['fetchstat'][0]['source_id']='fetchstat-only-source'
        (self.policy/'framework/supply_contract.json').write_text(json.dumps(policy))
        with self.assertRaisesRegex(ValueError,'not_registered'):production.authorize(manifest)

    def test_provider_change_after_initial_selection_is_rejected_before_storage(self):
        manifest=json.loads((self.package/'manifest.json').read_text())
        changed={**manifest,'provider_id':'fetchstat'}
        def raced(package, root, **kwargs):
            kwargs['guard'](changed)
        with patch.object(production,'_receive',side_effect=raced):
            with self.assertRaisesRegex(ValueError,'changed_during_snapshot'):self.receive()
        self.assertFalse(self.ledger().exists())
        self.assertEqual(self.counts()['observations'],0)

class ReportsProductionTests(CollectorProductionTests):
    provider = "fetchreports"

if __name__=='__main__':unittest.main()
