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
