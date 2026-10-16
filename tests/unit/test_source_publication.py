"""Independent data releases preserve identity, history and the public boundary."""
import copy
import hashlib
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
        with patch.object(publication, 'strict_json', side_effect=AssertionError('full registry parsed')):
            site_projection = publication.site_state(self.root)
        self.assertEqual(site_projection['version'], 1)
        self.assertEqual(list(site_projection['sites']), ['named-campus'])

    def test_site_projection_rejects_malformed_or_reordered_prefix(self):
        path = Path(self.runtime.name) / publication.PATH
        path.parent.mkdir(parents=True)
        for body in ('{"sites":{},"version":1}', '{"version":2,"sites":{}}',
                     '{"version":1,"sites":{"a":1,"a":2},"objects":{}}'):
            path.write_text(body)
            with self.subTest(body=body), self.assertRaises(ValueError):
                publication.site_state(self.root)

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

    def correction(self, action='reclassify', target=None):
        claim = self.claims()[0]
        if not target:
            target = intake.apply(self.root,self.data,claim)['statement_id']
        claim['registration_correction'] = {'of':target,'action':action,'reason':'Technical source classification correction'}
        if action == 'reclassify': claim['metric'] = 'reported_product_capability'
        return claim

    def test_ordinary_reclassification_is_append_only_replayable_and_not_C3(self):
        claim = self.correction()
        before = copy.deepcopy(ledger.load(self.root)['records'][0])
        receipt = intake.apply(self.root,self.data,claim)
        doc = ledger.check(ledger.load(self.root))
        self.assertEqual(doc['records'][0],before)
        self.assertIsNone(doc['records'][1]['reviewed_at'])
        self.assertEqual(ledger.current(doc,'2026-10-12')[0]['current'][0]['metric'],'reported_product_capability')
        self.assertEqual(len(ledger.public_page(self.root,{})['records']),2)
        updates = ledger.public_updates(self.root)['changes']
        self.assertEqual(len(updates),1)
        self.assertEqual(updates[0]['revision']['of'],before['id'])
        self.assertNotIn('registration_correction',updates[0])
        frozen = (self.root/ledger.PATH).read_bytes()
        self.assertEqual(intake.apply(self.root,self.data,claim)['state'],'already_registered')
        self.assertEqual((self.root/ledger.PATH).read_bytes(),frozen)
        payload = publication.bundle(self.root)
        (self.root/ledger.PATH).unlink()
        self.assertEqual(publication.install(self.root,payload)['new_records'],2)
        self.assertEqual(publication.install(self.root,payload)['new_records'],0)
        self.assertEqual(ledger.public_updates(self.root)['changes'][0]['id'],receipt['statement_id'])

    def test_ordinary_correction_cannot_change_value_source_identity_or_clocks(self):
        claim = self.correction()
        before = (self.root/ledger.PATH).read_bytes()
        for field,value in [('value',9),('unit','MW'),('kind','measured'),('effective_at','2024'),
                            ('valid_until','2030'),('period_start','2024'),('assumptions',['guess'])]:
            bad = copy.deepcopy(claim);bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):intake.apply(self.root,self.data,bad)
            self.assertEqual((self.root/ledger.PATH).read_bytes(),before)
        bad = copy.deepcopy(claim);bad['source']['quote'] = 'Changed native quote'
        with self.assertRaises(ValueError):intake.apply(self.root,self.data,bad)
        bad = copy.deepcopy(claim);bad['object'] = ledger.object_record('company',{'company_id':'other'},'Other')
        with self.assertRaises(ValueError):intake.apply(self.root,self.data,bad)
        self.assertEqual((self.root/ledger.PATH).read_bytes(),before)

    def test_identity_hold_release_preserve_audit_but_filter_runtime_directory_and_public_rows(self):
        claim = self.correction('quarantine_identity')
        old = copy.deepcopy(ledger.load(self.root)['records'][0])
        held = intake.apply(self.root,self.data,claim)
        self.assertEqual(ledger.load(self.root)['records'][0],old)
        self.assertEqual(ledger.public_page(self.root,{})['records'],[])
        self.assertEqual(publication.companies(self.root)['records'],[])
        self.assertEqual(ledger.current(ledger.load(self.root)),[])
        payload = publication.bundle(self.root)
        (self.root/ledger.PATH).unlink()
        publication.install(self.root,payload)
        self.assertEqual(ledger.public_page(self.root,{})['records'],[])
        self.assertEqual(publication.companies(self.root)['records'],[])
        (self.root/ledger.PATH).write_text(json.dumps({'version':1,'objects':payload['objects'],'records':payload['records']}))
        release = self.correction('release_identity',held['statement_id'])
        intake.apply(self.root,self.data,release)
        self.assertEqual(len(ledger.public_page(self.root,{})['records']),1)
        self.assertEqual(len(publication.companies(self.root)['records']),1)
        self.assertEqual(ledger.load(self.root)['records'][0],old)

    def test_hold_cannot_hide_reviewed_research_or_reclassify_and_missing_target_is_rejected(self):
        claim = self.correction('quarantine_identity')
        bad = copy.deepcopy(claim);bad['metric']='other'
        with self.assertRaises(ValueError):intake.apply(self.root,self.data,bad)
        bad = copy.deepcopy(claim);bad['registration_correction']['of']='missing'
        with self.assertRaises(ValueError):intake.apply(self.root,self.data,bad)
        doc = ledger.load(self.root);reviewed = copy.deepcopy(doc['records'][0])
        reviewed.pop('registration');reviewed['id']='reviewed';reviewed['review']={'public_fields_reviewed':True};reviewed['reviewed_at']=reviewed['recorded_at']
        intake.apply(self.root,self.data,claim);doc=ledger.load(self.root);doc['records'].append(reviewed)
        with patch('inresearch.knowledge.object_observations.review_valid',return_value=True), self.assertRaisesRegex(ValueError,'cannot_hide_reviewed'):
            ledger.check(doc)
        doc = ledger.load(self.root);doc['records'][0]=reviewed;doc['records'][1]['registration_correction']['of']='reviewed'
        with patch('inresearch.knowledge.object_observations.review_valid',return_value=True), self.assertRaisesRegex(ValueError,'preserve_source_value'):
            ledger.check(doc)

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


    def test_streamed_digest_matches_legacy_canonical_identity(self):
        values = [None, {}, [], {'z': '中文\\\"\n😀'*20000, 'a': [True, False, None, -0.0, 1.5]},
                  {3: 'three', 1: 'one'},
                  {'version': 1, 'sites': {}, 'objects': {'company:x': {'name': '原名'}},
                   'records': [{'id': str(index), 'quote': '原文\n'*100} for index in range(300)],
                   'receipts': {'batch': {'state': 'published'}}}]
        for value in values:
            with self.subTest(kind=type(value).__name__):
                old = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                self.assertEqual(publication.digest(value), old)
        for value in [float('nan'), float('inf'),
                      {'records': ['边界'*40000, {'invalid': float('-inf')}]}]:
            with self.subTest(nonfinite=True), self.assertRaises(ValueError):
                publication.digest(value)

    def test_streamed_digest_retains_full_state_cas_and_bounded_encoding_memory(self):
        import tracemalloc
        state = {'version': 1, 'sites': {}, 'objects': {},
                 'records': [{'id': str(index), 'quote': '原文'*2048} for index in range(500)],
                 'receipts': {}}
        before = publication.digest(state)
        for key, value in [('sites', {'a': {}}), ('objects', {'b': {}}),
                           ('records', []), ('receipts', {'other': {'state': 'published'}})]:
            self.assertNotEqual(publication.digest(dict(state, **{key: value})), before)
        def peak(call):
            tracemalloc.start()
            try:
                result = call()
                return result, tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
        expected, legacy_peak = peak(lambda: hashlib.sha256(json.dumps(state, ensure_ascii=False,
            sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest())
        actual, streamed_peak = peak(lambda: publication.digest(state))
        self.assertEqual(actual, expected)
        self.assertLess(streamed_peak, legacy_peak // 8)

    def test_object_merge_keeps_nested_inputs_detached_and_conflicts_atomic(self):
        doc = {'version': 1, 'objects': {'a': {'name': 'A', 'nested': ['old']}},
               'records': [{'id': 'old', 'source': {'quote': ['original']}}],
               'extra': {'nested': ['metadata']}}
        runtime = {'objects': {'b': {'name': 'B', 'nested': ['new']}},
                   'records': [{'id': 'new', 'source': {'quote': ['addition']}}]}
        before, additions = copy.deepcopy(doc), copy.deepcopy(runtime)
        merged = publication._objects(doc, runtime)
        self.assertEqual(list(merged), list(doc))
        self.assertEqual([row['id'] for row in merged['records']], ['old', 'new'])
        merged['objects']['a']['nested'].append('changed')
        merged['objects']['b']['nested'].append('changed')
        for row in merged['records']: row['source']['quote'].append('changed')
        merged['extra']['nested'].append('changed')
        self.assertEqual(doc, before)
        self.assertEqual(runtime, additions)
        for bad in [{'objects': {'a': {'name': 'changed'}}, 'records': []},
                    {'objects': {}, 'records': [{'id': 'old', 'source': {'quote': ['changed']}}]}]:
            with self.assertRaisesRegex(ValueError, 'collision'):
                publication._objects(doc, bad)
        self.assertEqual(doc, before)

    def test_streamed_install_preserves_legacy_receipt_cas_prefix_and_replay(self):
        from inresearch.storage import files
        intake.apply(self.root, self.data, self.item)
        payload = publication.bundle(self.root)
        (self.root/'data/projects.json').write_text(json.dumps({'records': []}))
        before = copy.deepcopy(payload)
        old_digest = lambda value: hashlib.sha256(json.dumps(value, ensure_ascii=False,
            sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        with patch.object(publication, 'write_json_streaming', wraps=files.write_json_streaming) as write:
            receipt = publication.install(self.root, payload, expected_state_sha=old_digest(publication.empty()))
        write.assert_called_once()
        self.assertEqual(receipt['batch_id'], old_digest(payload))
        path = Path(self.runtime.name)/publication.PATH
        raw = path.read_bytes()
        self.assertTrue(raw.startswith(b'{"version":1,"sites":'))
        self.assertEqual(publication.site_state(self.root)['sites'], publication.state(self.root)['sites'])
        self.assertEqual(publication.install(self.root, payload)['state'], 'already_published')
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(payload, before)
        with self.assertRaisesRegex(ValueError, 'source_publication_context_changed'):
            publication.install(self.root, {'version': 1, 'sites': [], 'objects': {}, 'records': []},
                                expected_state_sha=old_digest(publication.empty()))
        self.assertEqual(path.read_bytes(), raw)

    def test_streamed_install_encoding_failure_keeps_prior_registry_and_payload(self):
        from inresearch.storage import files
        intake.apply(self.root, self.data, self.item)
        payload = publication.bundle(self.root)
        (self.root/'data/projects.json').write_text(json.dumps({'records': []}))
        path = Path(self.runtime.name)/publication.PATH
        files.write_json(path, publication.empty())
        raw, before = path.read_bytes(), copy.deepcopy(payload)
        def interrupted(value):
            yield b'{"version":1,'
            raise OSError('simulated_stream_encoding_failure')
        with patch.object(files, 'iter_json_bytes', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'simulated_stream_encoding_failure'):
                publication.install(self.root, payload)
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(payload, before)
        self.assertFalse(list(path.parent.glob('.registry.json.tmp-*')))
        self.assertEqual(publication.install(self.root, payload)['new_records'], 1)


    def test_streamed_state_preserves_complete_strict_ledger_across_chunks(self):
        path = Path(self.runtime.name)/publication.PATH
        path.parent.mkdir(parents=True)
        body = {'version': 1, 'sites': {}, 'objects': {},
                'records': [{'id': str(index), 'quote': '中文原句\n😀'*100}
                            for index in range(500)], 'receipts': {'last': {'state': 'published'}}}
        raw = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
        path.write_text(raw, encoding='utf-8')
        self.assertGreater(len(raw), 65536)
        self.assertEqual(publication.state(self.root), body)
        self.assertEqual(publication.digest(publication.state(self.root)), publication.digest(body))
        # Invalid content after several input blocks must still be rejected;
        # full-state CAS cannot use a valid prefix or silently drop late keys.
        for invalid in [raw[:-1] + ',"sites":{}}',
                        raw.replace('"last":{"state":"published"}',
                                    '"last":{"state":"published","state":"other"}'),
                        raw.replace('"last":{"state":"published"}', '"last":NaN'),
                        raw[:-3], raw + '{}']:
            path.write_text(invalid, encoding='utf-8')
            with self.subTest(tail=invalid[-80:]), self.assertRaises(ValueError):
                publication.state(self.root)


    def test_install_keeps_previous_state_and_payload_immutable(self):
        from inresearch.storage import files
        payload = self.company_payload()
        publication.install(self.root, payload)
        previous = publication.state(self.root)
        incoming = self.relabel_company(payload, 'second-company', 'Second company')
        before, addition = copy.deepcopy(previous), copy.deepcopy(incoming)
        with patch.object(publication, 'state', return_value=previous), \
             patch.object(publication, 'write_json_streaming', wraps=files.write_json_streaming) as write:
            self.assertEqual(publication.install(self.root, incoming)['new_records'], 1)
        saved = write.call_args.args[1]
        self.assertEqual(len(saved['records']), 2)
        saved['records'][0]['source']['quote'] = 'changed saved old history'
        saved['records'][1]['source']['quote'] = 'changed saved addition'
        saved['objects'][next(iter(saved['objects']))]['name'] = 'changed saved identity'
        self.assertEqual(previous, before)
        self.assertEqual(incoming, addition)


    def isolate_site_context_cache(self):
        from collections import OrderedDict
        cache = patch.object(publication, '_site_context_cache', OrderedDict())
        cache.start()
        self.addCleanup(cache.stop)

    def test_site_context_keeps_full_digest_and_independent_small_projection(self):
        from inresearch.storage.files import write_json_streaming
        self.isolate_site_context_cache()
        projection, full_sha = publication.site_context(self.root)
        self.assertEqual(projection, {'version': 1, 'sites': {}})
        self.assertEqual(full_sha, publication.digest(publication.empty()))
        self.assertNotEqual(full_sha, publication.digest(projection))
        full = publication.empty()
        full['sites'] = {'a': {'observations': [{'nested': ['original']}]}}
        full['records'] = [{'private': 'unrelated complete history'}]
        full['receipts'] = {'receipt': {'state': 'published'}}
        write_json_streaming(Path(self.runtime.name)/publication.PATH, full)
        projection, full_sha = publication.site_context(self.root)
        self.assertEqual(full_sha, publication.digest(full))
        self.assertEqual(set(projection), {'version', 'sites'})
        projection['sites']['a']['observations'][0]['nested'].append('changed')
        with patch.object(publication, 'state', side_effect=AssertionError('warm context reparsed')):
            next_projection, next_sha = publication.site_context(self.root)
        self.assertEqual(next_projection['sites'], full['sites'])
        self.assertEqual(next_sha, full_sha)
        cached = next(iter(publication._site_context_cache.values()))
        self.assertEqual(set(cached[1]), {'version', 'sites'})
        self.assertNotIn('unrelated complete history', json.dumps(cached))

    def test_site_context_invalidates_atomic_inplace_removal_and_runtime_path(self):
        import os
        from inresearch.storage.files import write_json_streaming
        self.isolate_site_context_cache()
        path = Path(self.runtime.name)/publication.PATH
        full = publication.empty()
        full['records'] = [{'value': 11}]
        write_json_streaming(path, full)
        _, before = publication.site_context(self.root)
        stat = path.stat()
        full['records'][0]['value'] = 22
        write_json_streaming(path, full)
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(path.stat().st_size, stat.st_size)
        self.assertNotEqual(path.stat().st_ino, stat.st_ino)
        _, replaced = publication.site_context(self.root)
        self.assertNotEqual(replaced, before)
        stat = path.stat()
        full['records'][0]['value'] = 33
        path.write_text(json.dumps(full, ensure_ascii=False, separators=(',', ':')) + '\n')
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(path.stat().st_ino, stat.st_ino)
        self.assertEqual(path.stat().st_size, stat.st_size)
        self.assertEqual(path.stat().st_mtime_ns, stat.st_mtime_ns)
        self.assertNotEqual(publication.site_context(self.root)[1], replaced)
        path.unlink()
        self.assertEqual(publication.site_context(self.root)[1], publication.digest(publication.empty()))
        write_json_streaming(path, full)
        self.assertEqual(publication.site_context(self.root)[1], publication.digest(full))
        with tempfile.TemporaryDirectory() as other, patch.dict('os.environ', {'INRESEARCH_RUNTIME_ROOT': other}):
            self.assertEqual(publication.site_context(self.root)[1], publication.digest(publication.empty()))
        self.assertEqual(publication.site_context(self.root)[1], publication.digest(full))

    def test_site_context_has_four_root_lru_bound(self):
        self.isolate_site_context_cache()
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict('os.environ', {'INRESEARCH_RUNTIME_ROOT': ''}), \
             patch.object(publication, 'state', wraps=publication.state) as read:
            roots = [Path(directory)/str(n) for n in range(5)]
            for root in roots: publication.site_context(root)
            self.assertEqual(read.call_count, 5)
            self.assertEqual(len(publication._site_context_cache), 4)
            publication.site_context(roots[-1])
            self.assertEqual(read.call_count, 5)
            publication.site_context(roots[0])
            self.assertEqual(read.call_count, 6)
            self.assertEqual(len(publication._site_context_cache), 4)

    def test_site_context_concurrent_callers_share_one_builder(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        self.isolate_site_context_cache()
        entered, release = Event(), Event()
        original = publication.state
        def read(root):
            entered.set()
            if not release.wait(5): raise AssertionError('builder release timed out')
            return original(root)
        with patch.object(publication, 'state', side_effect=read) as count, ThreadPoolExecutor(max_workers=6) as pool:
            jobs = [pool.submit(publication.site_context, self.root) for _ in range(6)]
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(count.call_count, 1)
            finally:
                release.set()
            results = [job.result(timeout=5) for job in jobs]
            self.assertEqual(count.call_count, 1)
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len({id(result[0]) for result in results}), 6)

    def test_site_context_discards_unstable_reads_and_never_caches_failure(self):
        from inresearch.storage.files import write_json_streaming
        self.isolate_site_context_cache()
        path = Path(self.runtime.name)/publication.PATH
        full = publication.empty()
        write_json_streaming(path, full)
        original, reads = publication.state, []
        def change_once(root):
            value = original(root)
            reads.append(1)
            if len(reads) == 1:
                full['receipts']['new'] = {'state': 'published'}
                write_json_streaming(path, full)
            return value
        with patch.object(publication, 'state', side_effect=change_once):
            self.assertEqual(publication.site_context(self.root)[1], publication.digest(full))
        self.assertEqual(len(reads), 2)
        publication._site_context_cache.clear()
        def always_change(root):
            value = original(root)
            full['receipts'][str(len(full['receipts']))] = {'state': 'published'}
            write_json_streaming(path, full)
            return value
        with patch.object(publication, 'state', side_effect=always_change) as changed:
            with self.assertRaisesRegex(ValueError, 'context_changed_during_read'):
                publication.site_context(self.root)
            self.assertEqual(changed.call_count, 3)
        self.assertEqual(len(publication._site_context_cache), 0)
        path.write_text('{"version":1,"sites":{},"sites":{}}')
        with self.assertRaisesRegex(ValueError, 'duplicate_json_key'):
            publication.site_context(self.root)
        self.assertEqual(len(publication._site_context_cache), 0)
        write_json_streaming(path, full)
        self.assertEqual(publication.site_context(self.root)[1], publication.digest(full))

    def test_review_context_uses_cached_full_digest_but_respects_explicit_runtime(self):
        from inresearch.materials import review_context
        self.isolate_site_context_cache()
        runtime = publication.empty()
        runtime['records'] = [{'unrelated': 'full digest still includes this'}]
        from inresearch.storage.files import write_json_streaming
        write_json_streaming(Path(self.runtime.name)/publication.PATH, runtime)
        with patch.object(review_context.research_tasks, 'read', return_value={'revision': 1, 'packages': []}), \
             patch.object(review_context.research_tasks, 'plan', return_value={'mission': {'title': 'T', 'goal': 'G'}}):
            task, index = review_context.current(self.root, {}, task_records=[])
            self.assertEqual(task['source_state_sha256'], publication.digest(runtime))
            with patch.object(publication, 'site_context', side_effect=AssertionError('explicit runtime ignored')):
                direct_task, direct_index = review_context.current(self.root, {}, runtime=runtime, task_records=[])
            self.assertEqual((direct_task, direct_index), (task, index))
