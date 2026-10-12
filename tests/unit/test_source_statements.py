import copy,hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from inresearch.workflow import source_statements as intake
from inresearch.knowledge import site_timeline

class SourceStatementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.data=self.root/'runtime';(self.root/'data').mkdir();(self.data/'catalog').mkdir(parents=True)
        (self.root/'data/projects.json').write_text(json.dumps({'records':[]}))
        raw=self.data/'original.txt';raw.write_text('Original source: Named Campus, Test City; stated capacity 10 MW.');self.sha=hashlib.sha256(raw.read_bytes()).hexdigest()
        with sqlite3.connect(self.data/'catalog/catalog.sqlite') as db:
            db.execute('create table documents(doc_id text,sha256 text,original_rel text)')
            db.execute('create table sources(id integer,doc_id text,source_key text,received real)')
            db.execute('insert into documents values(?,?,?)',('doc-'+self.sha,self.sha,'original.txt'))
            db.execute('insert into sources values(?,?,?,?)',(1,'doc-'+self.sha,'/private/unique-original.txt',1704067200))
        self.identity={'version':1,'site_id':'named-campus','name':'Named Campus','native_name':'Named Campus','country':'US','region':'north-america','location':'Test City','basis':'A separately identified physical campus from source metadata; street unknown'}
        self.item={'version':1,'site_id':'named-campus','identity':self.identity,'source':{'sha256':self.sha,'published_at':'2024-02-01','locator':'original:paragraph:1'},'fields':{'name':'Named Campus','status':'L2','capacity_planned_it_mw':10},'basis':'Source states this number; registered without fact-checking'}
    def register(self,item=None):return intake.apply(self.root,self.data,item or self.item)
    def row(self):return json.loads((self.root/'data/projects.json').read_text())['records'][0]
    def test_no_url_sidecar_model_target_or_c3_is_required(self):
        receipt=self.register();r=self.row();self.assertFalse(receipt['truth_checked']);self.assertEqual(r['observations'][0]['schema_version'],3)
        self.assertNotIn('review',r['observations'][0]['adoption']);self.assertIsNone(r['sources'][0]['url']);site_timeline.check_history(r)
        p=site_timeline.current(r,'2026-10-12');self.assertEqual(p['capacity_planned_it_mw'],10);f=p['tracking']['fields']['capacity_planned_it_mw'];self.assertIsNone(f['effective_at']);self.assertEqual(f['selection_time_basis'],'published_at');self.assertEqual(f['registration_status'],'unverified')
    def test_newer_statement_changes_display_and_keeps_old_version(self):
        self.register();p=copy.deepcopy(self.item);p['source']['published_at']='2024-03-01';p['fields']['capacity_planned_it_mw']=200;self.register(p)
        r=self.row();self.assertEqual(len(r['observations']),2);self.assertEqual(r['observations'][0]['fields']['capacity_planned_it_mw'],10);self.assertEqual(site_timeline.current(r,'2026-10-12')['capacity_planned_it_mw'],200)
    def test_late_arriving_older_source_cannot_replace_newer_observation(self):
        p=copy.deepcopy(self.item);p['effective_at']='2024-06-01';p['fields']['capacity_planned_it_mw']=50;self.register(p)
        self.register();self.assertEqual(site_timeline.current(self.row(),'2026-10-12')['capacity_planned_it_mw'],50)
    def test_unknown_clocks_use_actual_receipt_without_fabricating_event_date(self):
        self.item['source']['published_at']=None;self.register();r=site_timeline.current(self.row(),'2026-10-12');self.assertEqual(r['capacity_planned_it_mw'],10);f=r['tracking']['fields']['capacity_planned_it_mw'];self.assertIsNone(f['effective_at']);self.assertEqual(f['selection_time_basis'],'first_received_at')
    def test_replay_is_byte_identical_and_original_is_not_deleted(self):
        self.register();before=(self.root/'data/projects.json').read_bytes();self.assertEqual(self.register()['state'],'already_registered');self.assertEqual(before,(self.root/'data/projects.json').read_bytes());self.assertTrue((self.data/'original.txt').exists())
    def test_same_name_cannot_create_another_id_and_identity_cannot_move(self):
        self.register();p=copy.deepcopy(self.item);p['site_id']=p['identity']['site_id']='another-id'
        with self.assertRaisesRegex(ValueError,'duplicate'):self.register(p)
        p=copy.deepcopy(self.item);p['identity']['location']='Another City'
        with self.assertRaisesRegex(ValueError,'identity_changed'):self.register(p)
    def test_actual_source_identity_required_but_source_number_is_not_truth_checked(self):
        p=copy.deepcopy(self.item);p['fields']['capacity_planned_it_mw']=9999;self.register(p);self.assertEqual(site_timeline.current(self.row(),'2026-10-12')['capacity_planned_it_mw'],9999)
        (self.data/'original.txt').write_text('different file')
        with self.assertRaisesRegex(ValueError,'bytes_changed'):self.register(p)
    def test_v3_does_not_impersonate_reviewed_research_or_authorize_history_rewrite(self):
        self.register();r=self.row();bad=copy.deepcopy(r['observations'][0]);bad['adoption']['review']={'decision':'adopted'}
        with self.assertRaisesRegex(ValueError,'registration_required'):site_timeline.check(bad)
        bad=copy.deepcopy(r['observations'][0]);bad['revision']={'action':'replace'}
        with self.assertRaisesRegex(ValueError,'registration_required'):site_timeline.check(bad)

    def test_batch_holds_one_bad_identity_and_continues(self):
        bad=copy.deepcopy(self.item);bad['site_id']=''
        result=intake.apply_batch(self.root,self.data,[bad,self.item,self.item])
        self.assertEqual((result['registered'],result['held'],result['replayed']),(1,1,1))
        self.assertFalse(result['published'])
    def test_same_time_new_registration_displays_latest_and_marks_disagreement(self):
        self.register();p=copy.deepcopy(self.item);p['fields']['capacity_planned_it_mw']=22;self.register(p)
        view=site_timeline.current(self.row(),'2026-10-12')
        self.assertEqual(view['capacity_planned_it_mw'],22);self.assertTrue(view['tracking']['conflicts'])
        self.assertEqual(len(self.row()['observations']),2)
    def test_archive_receipt_and_review_clock_cannot_be_fabricated(self):
        self.register();r=self.row()['observations'][0];self.assertIsNone(site_timeline.public_timeline(self.row())[0]['reviewed_at'])
        r['adoption']['document_refs'][0]['archive']['receipts']=[]
        with self.assertRaisesRegex(ValueError,'archive_receipt'):site_timeline.check(r)

    def test_phase_registration_does_not_invent_whole_site_capacity_or_event_date(self):
        self.item['scope']='phase:a';self.register()
        view=site_timeline.current(self.row(),'2026-10-12')
        self.assertIsNone(view['capacity_planned_it_mw'])
        part=view['scope_views']['phase:a'];self.assertEqual(part['capacity_planned_it_mw'],10)
        self.assertIsNone(part['tracking']['fields']['capacity_planned_it_mw']['effective_at'])
    def test_water_interval_can_register_without_fact_review(self):
        self.item['fields']['water_consumption_m3']={'value_range':[10,20],'unit':'m3','basis':'Source estimate','measurement_kind':'reported','boundary':'site','period_start':None,'period_end':None}
        self.register();view=site_timeline.current(self.row(),'2026-10-12')
        self.assertEqual(view['quantity_fields']['water_consumption_m3']['value_range'],[10,20])
        self.assertIsNone(self.row()['verified_date'])

    def test_missing_stage_is_unknown_instead_of_invented_rumor_or_plan(self):
        self.item['fields'].pop('status');self.register()
        self.assertIsNone(self.row()['status'])
        from inresearch.knowledge.industry import project
        view=project(self.row());self.assertEqual(view['stage_label'],'阶段待核实')
        self.assertEqual(view['registration_status'],'unverified')

    def located_item(self):
        raw = self.data/'geocode.json'
        raw.write_text('{"LATITUDE":"1.3254","LONGITUDE":"103.6751","ADDRESS":"Named Campus"}')
        sha = hashlib.sha256(raw.read_bytes()).hexdigest()
        with sqlite3.connect(self.data/'catalog/catalog.sqlite') as db:
            db.execute('insert into documents values(?,?,?)', ('doc-'+sha, sha, 'geocode.json'))
            db.execute('insert into sources values(?,?,?,?)', (2, 'doc-'+sha, '/private/geocode.json', 1704067201))
        item = copy.deepcopy(self.item)
        item['identity'].update(coordinates='1.3254,103.6751', coordinate_source={
            'precision':'address', 'coordinate_system':'WGS84', 'method':'address_geocode',
            'source_sha256':sha, 'url':'https://example.org/geocode?address=NamedCampus',
            'locator':'/results/0/LATITUDE and /results/0/LONGITUDE',
            'basis':'Official address match; address location, not a surveyed building centre'})
        item['fields']['status'] = 'L8'
        return item

    def test_initial_coordinates_register_map_point_with_private_source_audit(self):
        from inresearch.knowledge.industry import project
        item = self.located_item()
        self.register(item)
        view = project(self.row())
        self.assertEqual(view['coordinates'], [1.3254,103.6751])
        self.assertEqual(view['geography']['coordinate_source']['precision'], 'address')
        self.assertNotIn('source_sha256', view['geography']['coordinate_source'])
        self.assertNotIn('locator', view['geography']['coordinate_source'])
        self.assertEqual(view['registration_status'], 'unverified')
        before = (self.root/'data/projects.json').read_bytes()
        self.assertEqual(self.register(item)['state'], 'already_registered')
        self.assertEqual(before, (self.root/'data/projects.json').read_bytes())

    def test_initial_coordinates_require_source_precision_and_finite_wgs84_bounds(self):
        from inresearch.knowledge.site_register import check_initial_identity
        item = self.located_item()
        for value in ('91,103', '1,181', 'NaN,103', '1,Infinity', '1e309,103', '1,2,3'):
            identity = copy.deepcopy(item['identity']);identity['coordinates'] = value
            with self.subTest(coordinates=value), self.assertRaisesRegex(ValueError, 'coordinates'):
                check_initial_identity(identity)
        for key in ('coordinates', 'coordinate_source'):
            identity = copy.deepcopy(item['identity']);identity.pop(key)
            with self.assertRaisesRegex(ValueError, 'required_together'):check_initial_identity(identity)
        for key, value in (('precision','city'), ('precision','building'), ('coordinate_system','SVY21'),
                           ('source_sha256','bad'), ('url','http://example.org/map'),
                           ('url','https://user:password@example.org/map'), ('locator','')):
            identity = copy.deepcopy(item['identity']);identity['coordinate_source'][key] = value
            with self.subTest(field=key,value=value), self.assertRaises(ValueError):check_initial_identity(identity)

    def test_reported_coordinate_table_is_distinct_from_map_or_address_geocoding(self):
        from inresearch.knowledge.site_register import check_initial_identity
        from inresearch.knowledge.industry import project
        item = self.located_item()
        item['identity']['coordinate_source'].update(method='reported_coordinates', precision='site',
            basis='Operator-reported point displayed in WGS84; not a surveyed boundary or entrance')
        check_initial_identity(item['identity'])
        self.register(item)
        view = project(self.row())
        self.assertEqual(view['geography']['coordinate_source']['method'], 'reported_coordinates')
        self.assertEqual(view['geography']['coordinate_source']['coordinate_system'], 'WGS84')
        self.assertEqual(view['registration_status'], 'unverified')

    def test_coordinate_source_bytes_are_real_and_reverified_on_replay(self):
        item = self.located_item();bad = copy.deepcopy(item)
        bad['identity']['coordinate_source']['source_sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'received_source_required'):self.register(bad)
        self.assertEqual(json.loads((self.root/'data/projects.json').read_text())['records'], [])
        self.register(item);before = (self.root/'data/projects.json').read_bytes()
        (self.data/'geocode.json').write_text('changed geocoding response')
        with self.assertRaisesRegex(ValueError, 'bytes_changed'):self.register(item)
        self.assertEqual(before, (self.root/'data/projects.json').read_bytes())

    def test_existing_coordinates_and_source_cannot_be_changed_or_added(self):
        item = self.located_item();self.register(item)
        before = (self.root/'data/projects.json').read_bytes()
        for key, value in (('coordinates','1.4,103.7'), ('coordinate_source',
                           {**item['identity']['coordinate_source'], 'basis':'different address'})):
            bad = copy.deepcopy(item);bad['identity'][key] = value
            with self.assertRaisesRegex(ValueError, 'identity_changed:'+key):self.register(bad)
        self.assertEqual(before, (self.root/'data/projects.json').read_bytes())
        self.item['site_id'] = self.item['identity']['site_id'] = 'another-campus'
        self.item['identity']['name'] = self.item['fields']['name'] = 'Another Campus'
        self.register()
        bad = copy.deepcopy(self.item)
        bad['identity'].update({k:item['identity'][k] for k in ('coordinates','coordinate_source')})
        with self.assertRaisesRegex(ValueError, 'identity_changed:coordinates'):self.register(bad)
