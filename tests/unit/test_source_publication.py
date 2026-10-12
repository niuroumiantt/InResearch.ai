"""Independent data releases preserve identity, history and the public boundary."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.unit import test_source_statements as fixtures
from inresearch.delivery import source_publication as publication
from inresearch.workflow import source_statements as intake
from inresearch.knowledge import object_observations as ledger
from inresearch.paths import project_root


class SourcePublicationTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.SourceStatementTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root, self.data = fixture.root, fixture.data
        self.item, self.sha = fixture.item, fixture.sha
        (self.root/'data/companies.json').write_text(json.dumps({'records':[]}))
        (self.root/'framework').mkdir()
        for name in ('storage_contract.json','research_publication.json'):
            (self.root/'framework'/name).write_bytes((project_root()/'framework'/name).read_bytes())
        self.runtime = tempfile.TemporaryDirectory(); self.addCleanup(self.runtime.cleanup)
        self.env = patch.dict('os.environ', {'INRESEARCH_RUNTIME_ROOT':self.runtime.name})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_data_release_without_git_or_code_writes_and_durable_replay(self):
        intake.apply(self.root, self.data, self.item)
        payload = publication.bundle(self.root)
        (self.root/'data/projects.json').write_text(json.dumps({'records':[]}))
        before = (self.root/'data/projects.json').read_bytes()
        receipt = publication.install(self.root, payload)
        self.assertEqual((receipt['new_sites'], receipt['new_records']), (1,1))
        self.assertEqual(before,(self.root/'data/projects.json').read_bytes())
        self.assertEqual(publication.projects(self.root)['records'][0]['site_id'],'named-campus')
        self.assertEqual(publication.install(self.root,payload)['new_records'],0)
        self.assertTrue((Path(self.runtime.name)/'data/raw/source-publication/registry.json').exists())
        self.assertFalse((self.root/'data/raw/source-publication/registry.json').exists())
        self.assertFalse((self.data/'original.txt').is_symlink())
        self.assertTrue((self.data/'original.txt').exists())

    def test_code_release_retains_runtime_additions_and_identical_git_import_is_not_duplicated(self):
        intake.apply(self.root,self.data,self.item)
        payload=publication.bundle(self.root)
        publication.install(self.root,payload)
        current=publication.projects(self.root)
        self.assertEqual(len(current['records'][0]['observations']),1)
        # A later code release may contain the same registration. Exactly one survives.
        (self.root/'data/projects.json').write_text(json.dumps(current))
        self.assertEqual(len(publication.projects(self.root)['records'][0]['observations']),1)
        (self.root/'code-release.txt').write_text('new code')
        self.assertEqual(publication.projects(self.root),current)

    def test_rewrite_reviewed_bypass_and_bad_batch_are_atomic_rejections(self):
        intake.apply(self.root,self.data,self.item)
        payload=publication.bundle(self.root);publication.install(self.root,payload)
        path=Path(self.runtime.name)/'data/raw/source-publication/registry.json';before=path.read_bytes()
        altered=copy.deepcopy(payload);altered['sites'][0]['observations'][0]['fields']['capacity_planned_it_mw']=999
        with self.assertRaisesRegex(ValueError,'collision'):publication.install(self.root,altered)
        self.assertEqual(before,path.read_bytes())
        altered=copy.deepcopy(payload);altered['sites'][0]['observations'][0]['schema_version']=2
        with self.assertRaisesRegex(ValueError,'ordinary_source_only'):publication.install(self.root,altered)
        self.assertEqual(before,path.read_bytes())
        with self.assertRaisesRegex(ValueError,'duplicate_json'):publication.strict_json('{"version":1,"version":2}')
        with self.assertRaisesRegex(ValueError,'nonfinite'):publication.strict_json('{"value":NaN}')

    def claims(self):
        native = [('company',{'company_id':'named-company'}),
                  ('product',{'company_id':'named-company','model':'P1','version':'v1'}),
                  ('statistic',{'publisher':'Named Institute','series':'series1','geography':'CN','definition':'native count'}),
                  ('quote',{'company_id':'named-company','configuration':'P1','market':'CN','currency':'CNY','billing_basis':'hour'})]
        return [dict(version=1,object=ledger.object_record(kind,identity,'Name '+kind),
                     metric='native_count',value={'value_range':[1,2]},unit='native',kind='reported',scope={'boundary':'source'},
                     effective_at=None,basis='Source registration, not verified',
                     source={'sha256':self.sha,'locator':'original:paragraph:1','quote':'Original source','published_at':None})
                for kind,identity in native]

    def test_four_types_register_publish_replay_and_share_allowlist(self):
        claims=self.claims()
        for claim in claims: self.assertFalse(intake.apply(self.root,self.data,claim)['truth_checked'])
        payload=publication.bundle(self.root)
        (self.root/ledger.PATH).unlink()
        result=publication.install(self.root,payload)
        self.assertEqual(result['new_records'],4)
        public=ledger.public_page(self.root,{})
        self.assertEqual(public['total'],4)
        for row in public['records']:
            self.assertEqual(row['registration_status'],'unverified')
            self.assertIsNone(row['reviewed_at']);self.assertIsNone(row['effective_at'])
            self.assertEqual(row['selection_time_basis'],'first_received_at')
            self.assertNotIn('quote',row['source']);self.assertNotIn('archive',row['source'])
        self.assertEqual(publication.companies(self.root)['records'][0]['company_id'],'named-company')
        self.assertEqual(publication.install(self.root,payload)['new_records'],0)

    def test_newer_unknown_effective_clock_and_conflict_keep_history(self):
        claim=self.claims()[0]
        intake.apply(self.root,self.data,claim)
        claim['source']['published_at']='2024-03';claim['value']=5
        intake.apply(self.root,self.data,claim)
        claim['value']=6;intake.apply(self.root,self.data,claim)
        doc=ledger.load(self.root);group=ledger.current(doc,'2024-03-10')[0]
        self.assertEqual(len(doc['records']),3)
        self.assertEqual(group['current'][0]['value'],6)
        self.assertEqual(len(group['conflicts']),2)
        self.assertEqual(len(ledger.public_page(self.root,{})['records']),3)

    def test_existing_reviewed_identity_export_does_not_resubmit_its_baseline(self):
        intake.apply(self.root,self.data,self.item)
        path=self.root/'data/projects.json';doc=json.loads(path.read_text())
        doc['records'][0]['verified_date']='2024-01-01'
        path.write_text(json.dumps(doc))
        payload=publication.bundle(self.root)
        self.assertIsNone(payload['sites'][0]['baseline'])
        receipt=publication.install(self.root,payload)
        self.assertEqual(receipt['new_records'],0)
        self.assertEqual(publication.projects(self.root)['records'][0]['verified_date'],'2024-01-01')
