import importlib.util
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
import unittest
from tests.unit import test_collector_production as fixtures
from inresearch.materials import collector_production as production

spec=importlib.util.spec_from_file_location('collector_gateway',Path(__file__).resolve().parents[2]/'scripts/collector_gateway.py')
gateway=importlib.util.module_from_spec(spec);spec.loader.exec_module(gateway)


class ProductionLookupTests(unittest.TestCase):
    provider="fetchstat"
    setUp=fixtures.CollectorProductionTests.setUp
    receive=fixtures.CollectorProductionTests.receive
    ledger=fixtures.CollectorProductionTests.ledger
    def lookup(self):
        manifest=json.loads((self.package/'manifest.json').read_text())
        return production.lookup_receipt(self.data,self.provider,manifest['delivery_id'])

    def test_lookup_does_not_initialize_missing_store(self):
        self.assertIsNone(self.lookup())
        self.assertFalse(self.ledger().exists())

    def test_completed_lookup_is_read_only_and_preserves_original_clocks(self):
        receipt=self.receive();before={str(p):p.read_bytes() for p in self.data.rglob('*') if p.is_file()}
        found=self.lookup()
        self.assertEqual(found['first_received_at'],receipt['first_received_at'])
        self.assertEqual(found['archive_completed_at'],receipt['archive_completed_at'])
        self.assertEqual(found['receiver_revision'],receipt['receiver_revision'])
        self.assertTrue(found['lookup_only'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.data.rglob('*') if p.is_file()})

    def test_pending_arrival_is_not_completed_ack(self):
        with patch.object(production,'materialize',side_effect=OSError('controlled')):
            with self.assertRaises(OSError):self.receive()
        self.assertIsNone(self.lookup())
        self.receive();self.assertIsNotNone(self.lookup())

    def test_missing_projection_stays_unknown_without_repair(self):
        self.receive();original=next(p for p in (self.data/'originals').rglob('*') if p.is_file());original.unlink()
        with self.assertRaisesRegex(ValueError,'incomplete'):self.lookup()
        self.assertFalse(original.exists())

    def test_corrupt_archive_never_confirms(self):
        self.receive();archive=next((self.ledger().parent/'packages').iterdir())
        native=next((archive/'originals').iterdir());native.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):self.lookup()

    def test_forged_ack_never_confirms(self):
        receipt=self.receive();receipt['adopted']=1
        with sqlite3.connect(self.ledger()) as db:db.execute('UPDATE production_acks SET receipt=?',(json.dumps(receipt),))
        with self.assertRaisesRegex(ValueError,'authority'):self.lookup()

    def test_changed_candidate_ledger_never_confirms(self):
        self.receive()
        with sqlite3.connect(self.ledger()) as db:db.execute("UPDATE observations SET payload='{}'")
        with self.assertRaisesRegex(ValueError,'ledger_changed'):self.lookup()

    def test_other_provider_refused(self):
        with self.assertRaisesRegex(ValueError,'scope_invalid'):production.lookup_receipt(self.data,'fetchquotes','anything')

    def test_gateway_actual_frozen_package_replay_and_lookup(self):
        import base64
        manifest=json.loads((self.package/'manifest.json').read_text())
        request=dict(protocol=gateway.PROVIDERS[self.provider],provider=self.provider,delivery=manifest['delivery_id'],action='deliver',receiver_revision='a'*40,
            files={k:base64.b64encode((self.package/k).read_bytes()).decode() for k in production.inventory(self.package)})
        first=gateway.execute(request,self.data,self.provider)['receipt'];again=gateway.execute(request,self.data,self.provider)['receipt']
        self.assertEqual(first['first_received_at'],again['first_received_at']);self.assertTrue(again['replayed'])
        del request['files'];request['action']='lookup'
        result=gateway.execute(request,self.data,self.provider);self.assertTrue(result['found'])
        self.assertEqual(result['receipt']['archive_completed_at'],first['archive_completed_at'])

    def test_gateway_rejects_path_escape_extra_files_and_other_teams(self):
        request=dict(protocol=gateway.PROVIDERS[self.provider],provider=self.provider,delivery='x',action='deliver',receiver_revision='a'*40,
                     files={str(x):'' for x in range(5)})
        request['files']['../escape']=''
        with self.assertRaises(ValueError):gateway.execute(request,self.data,self.provider)
        request['provider']='fetchquotes'
        with self.assertRaisesRegex(ValueError,'scope_invalid'):gateway.execute(request,self.data,self.provider)


class FilingsProductionLookupTests(ProductionLookupTests):
    provider='fetchfilings'

    # Explicit names keep the governance AST map linked to both provider runs.

    def test_lookup_does_not_initialize_missing_store(self):return super().test_lookup_does_not_initialize_missing_store()

    def test_completed_lookup_is_read_only_and_preserves_original_clocks(self):return super().test_completed_lookup_is_read_only_and_preserves_original_clocks()

    def test_pending_arrival_is_not_completed_ack(self):return super().test_pending_arrival_is_not_completed_ack()

    def test_missing_projection_stays_unknown_without_repair(self):return super().test_missing_projection_stays_unknown_without_repair()

    def test_corrupt_archive_never_confirms(self):return super().test_corrupt_archive_never_confirms()

    def test_forged_ack_never_confirms(self):return super().test_forged_ack_never_confirms()

    def test_changed_candidate_ledger_never_confirms(self):return super().test_changed_candidate_ledger_never_confirms()

    def test_other_provider_refused(self):return super().test_other_provider_refused()

    def test_gateway_actual_frozen_package_replay_and_lookup(self):return super().test_gateway_actual_frozen_package_replay_and_lookup()

    def test_gateway_rejects_path_escape_extra_files_and_other_teams(self):return super().test_gateway_rejects_path_escape_extra_files_and_other_teams()

    def test_fixed_gateway_does_not_accept_sibling_provider_or_protocol(self):
        request=dict(protocol=gateway.PROTOCOL,provider='fetchstat',delivery='x',action='lookup',receiver_revision='a'*40)
        with self.assertRaisesRegex(ValueError,'scope_invalid'):gateway.execute(request,self.data,'fetchfilings')
        request['provider']='fetchfilings'
        with self.assertRaisesRegex(ValueError,'scope_invalid'):gateway.execute(request,self.data,'fetchfilings')
        request['protocol']=gateway.PROVIDERS['fetchfilings']
        with self.assertRaisesRegex(ValueError,'scope_invalid'):gateway.execute(request,self.data,'fetchstat')


class ReportsProductionLookupTests(ProductionLookupTests):
    provider='fetchreports'

    # Explicit names keep the governance AST map linked to both provider runs.

    def test_lookup_does_not_initialize_missing_store(self):return super().test_lookup_does_not_initialize_missing_store()

    def test_completed_lookup_is_read_only_and_preserves_original_clocks(self):return super().test_completed_lookup_is_read_only_and_preserves_original_clocks()

    def test_pending_arrival_is_not_completed_ack(self):return super().test_pending_arrival_is_not_completed_ack()

    def test_missing_projection_stays_unknown_without_repair(self):return super().test_missing_projection_stays_unknown_without_repair()

    def test_corrupt_archive_never_confirms(self):return super().test_corrupt_archive_never_confirms()

    def test_forged_ack_never_confirms(self):return super().test_forged_ack_never_confirms()

    def test_changed_candidate_ledger_never_confirms(self):return super().test_changed_candidate_ledger_never_confirms()

    def test_other_provider_refused(self):return super().test_other_provider_refused()

    def test_gateway_actual_frozen_package_replay_and_lookup(self):return super().test_gateway_actual_frozen_package_replay_and_lookup()

    def test_gateway_rejects_path_escape_extra_files_and_other_teams(self):return super().test_gateway_rejects_path_escape_extra_files_and_other_teams()

    def test_fixed_gateway_does_not_accept_sibling_provider_or_protocol(self):
        for other,protocol in gateway.PROVIDERS.items():
            if other==self.provider:continue
            request=dict(protocol=protocol,provider=other,delivery='x',action='lookup',receiver_revision='a'*40)
            with self.assertRaisesRegex(ValueError,'scope_invalid'):gateway.execute(request,self.data,self.provider)
            request['provider']=self.provider
            with self.assertRaisesRegex(ValueError,'scope_invalid'):gateway.execute(request,self.data,self.provider)
            request['protocol']=gateway.PROVIDERS[self.provider]
            with self.assertRaisesRegex(ValueError,'scope_invalid'):gateway.execute(request,self.data,other)
