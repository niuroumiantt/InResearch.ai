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

    def test_initial_coordinate_identity_reaches_runtime_map_and_cannot_move(self):
        from inresearch.knowledge.industry import project
        self.item['identity'].update(coordinates='1.3254,103.6751', coordinate_source={
            'precision':'address', 'coordinate_system':'WGS84', 'method':'address_geocode',
            'source_sha256':self.sha, 'url':'https://example.org/map', 'locator':'/result/0',
            'basis':'Address point; not a surveyed building centre'})
        intake.apply(self.root,self.data,self.item)
        payload = publication.bundle(self.root)
        (self.root/'data/projects.json').write_text(json.dumps({'records':[]}))
        publication.install(self.root,payload)
        self.assertEqual(project(publication.projects(self.root)['records'][0])['coordinates'], [1.3254,103.6751])
        before = (Path(self.runtime.name)/publication.PATH).read_bytes()
        bad = copy.deepcopy(payload)
        bad['sites'][0]['baseline']['coordinates'] = '1.4,103.7'
        bad['sites'][0]['baseline']['identity_registration']['coordinates'] = '1.4,103.7'
        with self.assertRaisesRegex(ValueError, 'immutable_site_identity'):publication.install(self.root,bad)
        self.assertEqual(before,(Path(self.runtime.name)/publication.PATH).read_bytes())
        # A code baseline may not retain an old identity block while moving its point.
        code = publication.projects(self.root)
        code['records'][0]['coordinates'] = '1.4,103.7'
        (self.root/'data/projects.json').write_text(json.dumps(code))
        with self.assertRaisesRegex(ValueError, 'identity_mismatch'):publication.projects(self.root)

    def test_site_roles_accept_valid_same_batch_and_existing_runtime_companies(self):
        claim = self.claims()[0]
        intake.apply(self.root,self.data,claim)
        self.item['fields']['operator'] = ['named-company']
        intake.apply(self.root,self.data,self.item)
        payload = publication.bundle(self.root)
        (self.root/'data/projects.json').write_text(json.dumps({'records':[]}))
        (self.root/ledger.PATH).unlink()
        receipt = publication.install(self.root,payload)
        self.assertEqual((receipt['new_sites'],receipt['new_records']), (1,2))
        self.assertEqual(publication.companies(self.root)['records'][0]['company_id'], 'named-company')
        self.item['fields']['owner'] = ['named-company']
        intake.apply(self.root,self.data,self.item)
        later = publication.bundle(self.root);later.update(objects={},records=[])
        (self.root/'data/projects.json').write_text(json.dumps({'records':[]}))
        self.assertEqual(publication.install(self.root,later)['new_records'], 1)

    def test_bad_or_unknown_same_batch_company_is_rejected_atomically(self):
        claim = self.claims()[0];intake.apply(self.root,self.data,claim)
        self.item['fields']['operator'] = ['named-company']
        intake.apply(self.root,self.data,self.item)
        payload = publication.bundle(self.root)
        (self.root/'data/projects.json').write_text(json.dumps({'records':[]}))
        (self.root/ledger.PATH).unlink()
        bad = copy.deepcopy(payload);bad.update(objects={},records=[])
        with self.assertRaisesRegex(ValueError, 'unknown_participant'):publication.install(self.root,bad)
        bad = copy.deepcopy(payload)
        next(iter(bad['objects'].values()))['id'] = 'company:wrong'
        with self.assertRaisesRegex(ValueError, 'identity_digest'):publication.install(self.root,bad)
        bad = copy.deepcopy(payload);bad['records'] = []
        with self.assertRaisesRegex(ValueError, 'unreferenced_object'):publication.install(self.root,bad)
        self.assertFalse((Path(self.runtime.name)/publication.PATH).exists())
        publication.install(self.root,payload)
        before = (Path(self.runtime.name)/publication.PATH).read_bytes()
        bad = copy.deepcopy(payload);next(iter(bad['objects'].values()))['name'] = 'Different legal entity'
        with self.assertRaisesRegex(ValueError, 'identity_collision'):publication.install(self.root,bad)
        self.assertEqual(before,(Path(self.runtime.name)/publication.PATH).read_bytes())

    def company_payload(self):
        intake.apply(self.root,self.data,self.claims()[0])
        payload = publication.bundle(self.root)
        (self.root/ledger.PATH).unlink()
        return payload

    def relabel_company(self, payload, ident, name):
        result = copy.deepcopy(payload)
        obj = ledger.object_record('company', {'company_id':ident}, name)
        result['objects'] = {obj['id']:obj}
        result['records'][0]['object_id'] = obj['id']
        result['records'][0]['id'] += '-'+ident
        return result

    def test_company_name_conflicts_with_code_directory_reject_without_writes(self):
        payload = self.company_payload()
        (self.root/'data/companies.json').write_text(json.dumps({'records':[
            {'company_id':'existing-company','name':'NAME COMPANY'}]}))
        with self.assertRaisesRegex(ValueError, 'duplicate_company_identity'):
            publication.install(self.root,payload)
        same_id = self.relabel_company(payload,'existing-company','Different legal entity')
        with self.assertRaisesRegex(ValueError, 'immutable_company_identity'):
            publication.install(self.root,same_id)
        self.assertFalse((Path(self.runtime.name)/publication.PATH).exists())
        exact_identity = self.relabel_company(payload,'existing-company','NAME COMPANY')
        self.assertEqual(publication.install(self.root,exact_identity)['new_records'], 1)

    def test_company_name_conflicts_with_runtime_and_same_batch_are_atomic(self):
        payload = self.company_payload();publication.install(self.root,payload)
        path = Path(self.runtime.name)/publication.PATH;before = path.read_bytes()
        duplicate = self.relabel_company(payload,'other-company','nAmE cOmPaNy')
        with self.assertRaisesRegex(ValueError, 'duplicate_company_identity'):
            publication.install(self.root,duplicate)
        self.assertEqual(before,path.read_bytes())
        collision = self.relabel_company(payload,'named-company','Different legal entity')
        with self.assertRaisesRegex(ValueError, 'immutable_object_identity'):
            publication.install(self.root,collision)
        self.assertEqual(before,path.read_bytes())
        # A fresh install has no previous state to catch an intra-batch duplicate.
        path.unlink()
        together = copy.deepcopy(payload)
        together['objects'].update(duplicate['objects'])
        together['records'].extend(duplicate['records'])
        with self.assertRaisesRegex(ValueError, 'duplicate_company_identity'):
            publication.install(self.root,together)
        self.assertFalse(path.exists())

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
