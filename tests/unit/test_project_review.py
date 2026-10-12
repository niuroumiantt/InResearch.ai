import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from inresearch.paths import project_root
from inresearch.materials import daily_bundle
from inresearch.workflow import project_review
import test_daily_bundle as bundle_tests


class ProjectReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name);self.root=base/'root';self.data=base/'data'
        (self.root/'data').mkdir(parents=True);(self.root/'framework').mkdir()
        (self.root/'data/projects.json').write_text(json.dumps({'records':[]}))
        (self.root/'framework/tco_targets.json').write_bytes((project_root()/'framework/tco_targets.json').read_bytes())
        folder=base/'bundle';folder.mkdir();bundle_tests.DailyBundleTests().bundle(folder,True)
        daily_bundle.receive(folder,self.data,project_root())
        self.event=project_review.read_events(self.data)[0]
        sha=self.event['editorial_event']['evidence_checks'][0]['source_sha256']
        target=self.event['demand_matches'][0]['target_id']
        self.proposal={'event_id':self.event['id'],'source_version':project_review.event_identity(self.event),
          'target_ids':[target],'fields':['capacity_it_mw_by_status'],'scope':'Planned, not operating.',
          'review':{'by':'test reviewer','at':'2026-10-06T12:00:00Z','score':8,'tier':'A',
                    'authority':'delegated_reviewer','delegation':'explicit new-project review','decision':'adopted','rationale':'original reviewed'},
          'project':{'site_id':'fi-salo-test','name':'FIN05','country':'FI','region':'europe','location':'Salo',
                     'status':'L2','verified_date':'2026-10-06','capacity_it_mw':None,
                     'capacity_it_mw_by_status':{'L2':60},'capacity_facility_mw':None,'notes':'一期规划',
                     'sources':[{'url':'https://example.org/campus','grade':'company'}]},
          'assertions':[{'source_sha256':sha,'locator':'research/evidence.txt','quote':'60 MW of IT load',
                         'value':60,'unit':'MW','basis':'it','phase':'一期','scope':'aggregate'}]}

    def initial_proposal(self):
        event,sha=self.replace_native_text('FIN05 campus in Salo, Finland is planned. Street address not stated.')
        p=copy.deepcopy(self.proposal);p.update(source_version=project_review.event_identity(event),target_ids=[],fields=['name','status'])
        p['project'].update(capacity_it_mw=None,capacity_it_mw_by_status={},capacity_facility_mw=None)
        p['observation']={'effective_at':None,'kind':'reported','basis':'source reports planned campus; date unknown','scope':'whole_site'}
        p['initial_identity']={'version':1,'site_id':'fi-salo-test','name':'FIN05','native_name':'FIN05',
                               'country':'FI','region':'europe','location':'Salo','basis':'named physical campus, address unknown'}
        p['object_binding']={'version':1,'site_id':'fi-salo-test','fields':p['fields'],'scope':'whole_site'}
        p['assertions']=[{'source_sha256':sha,'locator':'research/evidence.txt','quote':'FIN05 campus in Salo, Finland is planned.'}]
        p['review']['delegation']={'delegate':p['review']['by'],'granted_by':'fixture owner','granted_at':'2026-10-06',
                                 'reference':'test-only delegation','scope':'new_or_supplemental_research'}
        return p

    def test_initial_site_registers_without_targets_and_preserves_replay_times(self):
        p=self.initial_proposal();(self.root/'framework/tco_targets.json').unlink()
        result=project_review.apply(self.root,self.data,p);self.assertEqual(result['state'],'applied_in_checkout')
        before=(self.root/'data/projects.json').read_bytes();site=json.loads(before)['records'][0]
        self.assertEqual(site['identity_registration'],p['initial_identity']);self.assertEqual(len(site['observations']),1)
        self.assertIsNone(site['observations'][0]['effective_at']);self.assertEqual(site['observations'][0]['adoption']['target_ids'],[])
        self.assertEqual(project_review.apply(self.root,self.data,p)['state'],'already_applied')
        self.assertEqual(before,(self.root/'data/projects.json').read_bytes())

    def test_initial_site_rejects_identity_mismatch_duplicate_and_unquoted_native_name(self):
        p=self.initial_proposal();before=(self.root/'data/projects.json').read_bytes()
        bad=copy.deepcopy(p);bad['initial_identity']['country']='US'
        with self.assertRaisesRegex(ValueError,'identity_mismatch'):project_review.apply(self.root,self.data,bad)
        bad=copy.deepcopy(p);bad['initial_identity']['native_name']='another campus'
        with self.assertRaisesRegex(ValueError,'not_in_reviewed_quote'):project_review.apply(self.root,self.data,bad)
        self.assertEqual(before,(self.root/'data/projects.json').read_bytes())
        project_review.apply(self.root,self.data,p)
        bad=copy.deepcopy(p);bad['project']['site_id']='fi-salo-another';bad['initial_identity']['site_id']='fi-salo-another';bad['object_binding']['site_id']='fi-salo-another'
        with self.assertRaisesRegex(ValueError,'duplicate_project_identity'):project_review.apply(self.root,self.data,bad)
        bad['project']['name']='Renamed campus';bad['initial_identity']['name']='Renamed campus';bad['project']['aliases']=['fin05']
        with self.assertRaisesRegex(ValueError,'duplicate_project_identity'):project_review.apply(self.root,self.data,bad)

    def test_initial_site_cannot_inject_unreviewed_baseline_or_history(self):
        p=self.initial_proposal();before=(self.root/'data/projects.json').read_bytes()
        for field,value,error in [('observations',[], 'inject_history'),
                                  ('adoption_history',[], 'inject_history'),
                                  ('capacity_planned_it_mw',100, 'empty_capacity_baseline'),
                                  ('developer',['unreviewed'], 'actor_requires_reviewed_field')]:
            bad=copy.deepcopy(p);bad['project'][field]=value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError,error):project_review.apply(self.root,self.data,bad)
                self.assertEqual(before,(self.root/'data/projects.json').read_bytes())

    def observation_proposal(self, **fields):
        project_review.apply(self.root,self.data,self.proposal)
        old=json.loads((self.root/'data/projects.json').read_text())['records'][0]
        p=copy.deepcopy(self.proposal);p['baseline_sha256']=project_review.digest(old)
        p['fields']=list(fields or {'tenant':['new-user']})
        p['project'].update(fields or {'tenant':['new-user']})
        p['observation']={'effective_at':'2026-10-05','kind':'reported','basis':'reviewed original','scope':'whole_site'}
        p['review']['delegation']={'delegate':p['review']['by'],'granted_by':'fixture owner',
                                 'granted_at':'2026-10-06','reference':'test-only delegation',
                                 'scope':'new_or_supplemental_research'}
        return p

    def replace_native_text(self, text):
        folder=Path(self.temp.name)/'native-bundle';folder.mkdir()
        manifest=bundle_tests.DailyBundleTests().bundle(folder,True)
        path=folder/'research/evidence.txt';path.write_text(text)
        row=next(r for r in manifest['files'] if r['path']=='research/evidence.txt')
        row.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
        (folder/'research-delivery.json').write_text(json.dumps(manifest))
        daily_bundle.receive(folder,self.data,project_root())
        event=project_review.read_events(self.data)[0]
        return event,row['sha256']

    def test_review_recording_and_first_receipt_are_distinct_and_replay_preserves_clocks(self):
        p=self.observation_proposal()
        with patch.object(project_review,'now',return_value='2026-10-11T09:00:00Z'):
            project_review.apply(self.root,self.data,p)
        before=(self.root/'data/projects.json').read_bytes()
        row=json.loads(before)['records'][0]['observations'][0]
        self.assertEqual(row['reviewed_at'],p['review']['at'])
        self.assertEqual(row['recorded_at'],'2026-10-11T09:00:00Z')
        version=row['source_versions'][0]
        self.assertIsNone(version['published_at'])
        self.assertEqual(version['published_at_precision'],'unknown')
        self.assertTrue(version['first_received_at'])
        self.assertIn(version['first_received_at_provenance'],('local_archive_first_observed_at','indexed_bundle_first_verified_arrival'))
        with patch.object(project_review,'now',return_value='2026-11-01T09:00:00Z'):
            self.assertEqual(project_review.apply(self.root,self.data,p)['state'],'already_applied')
        self.assertEqual((self.root/'data/projects.json').read_bytes(),before)

    def test_received_daily_event_updates_registered_site_without_research_demand(self):
        p = self.observation_proposal()
        p['target_ids'] = []
        p['object_binding'] = {'version': 1, 'site_id': p['project']['site_id'],
                               'fields': p['fields'], 'scope': p['observation']['scope']}
        (self.root/'framework/tco_targets.json').unlink()
        project_review.apply(self.root, self.data, p)
        record = json.loads((self.root/'data/projects.json').read_text())['records'][0]
        observation = record['observations'][0]
        self.assertEqual(observation['adoption']['source_kind'], 'daily_event')
        self.assertEqual(observation['adoption']['target_ids'], [])
        self.assertEqual(observation['fields']['tenant'], ['new-user'])

    def test_daily_queue_accepts_verified_existing_identity_without_model_targets(self):
        p = self.observation_proposal()
        event = dict(self.event, id=self.event['id']+'-new-observation', demand_matches=[], identity_review='resolved',
                     matched_site_id=p['project']['site_id'], structured_evidence_status='quotes_verified')
        with patch.object(project_review, 'read_events', return_value=[event]):
            row = project_review.queue(self.data, self.root)['records'][0]
            self.assertEqual(row['state'], 'ready_for_review')
            self.assertEqual(row['target_ids'], [])
            self.assertEqual(row['site_id'], p['project']['site_id'])
        event['matched_site_id'] = 'another-campus'
        event['editorial_event'] = {}
        with patch.object(project_review, 'read_events', return_value=[event]):
            self.assertNotEqual(project_review.queue(self.data, self.root)['records'][0]['state'], 'ready_for_review')

    def test_native_publication_format_is_parsed_but_false_dates_and_self_receipts_are_rejected(self):
        p=self.observation_proposal()
        event,sha=self.replace_native_text('Updated Oct. 5, 2026. Phase 1 delivers 60 MW of IT load.')
        p.update(source_version=project_review.event_identity(event));p['assertions'][0]['source_sha256']=sha
        native={'source_sha256':sha,'published_at':'2026-10-05','publication_evidence':{
            'kind':'original_quote','locator':'research/evidence.txt','quote':'Updated Oct. 5, 2026.',
            'basis':'native source version update date, not physical event date'}}
        p['observation']['source_versions']=[native]
        for key in ('date','source','receipt','quote'):
            bad=copy.deepcopy(p);source=bad['observation']['source_versions'][0]
            if key=='date':source['published_at']='2026-10-06'
            if key=='source':source['source_sha256']='f'*64
            if key=='receipt':source['first_received_at']='2020-01-01T00:00:00Z'
            if key=='quote':source['publication_evidence']['quote']='Published Oct. 5, 2026.'
            with self.subTest(key=key),self.assertRaises(ValueError):project_review.apply(self.root,self.data,bad)
        project_review.apply(self.root,self.data,p)
        record=json.loads((self.root/'data/projects.json').read_text())['records'][0]['observations'][0]
        self.assertEqual(record['source_versions'][0]['published_at'],'2026-10-05')
        self.assertEqual(record['source_versions'][0]['publication_evidence'],native['publication_evidence'])
        self.assertEqual(record['effective_at'],'2026-10-05')

    def test_native_interval_is_quote_backed_and_does_not_become_an_average(self):
        quantity={'value_range':[50,60],'unit':'MW','basis':'explicit reported range'}
        p=self.observation_proposal(capacity_it_mw=quantity,capacity_it_mw_by_status={},capacity_assessment=None)
        event,sha=self.replace_native_text('Phase 1 delivers 50–60 MW of IT load.')
        p.update(source_version=project_review.event_identity(event))
        p['assertions']=[{'source_sha256':sha,'locator':'research/evidence.txt','quote':'50–60 MW of IT load',
                          'value_range':[50,60],'unit':'MW','range_basis':'explicit native interval','basis':'it','scope':'aggregate'}]
        for pair in ([40,60],[50,600],[60,50]):
            bad=copy.deepcopy(p);bad['project']['capacity_it_mw']['value_range']=pair
            bad['assertions'][0]['value_range']=pair
            with self.subTest(pair=pair),self.assertRaises(ValueError):project_review.apply(self.root,self.data,bad)
        project_review.apply(self.root,self.data,p)
        row=json.loads((self.root/'data/projects.json').read_text())['records'][0]
        from inresearch.knowledge.site_timeline import current
        view=current(row,'2026-10-11')
        self.assertIsNone(view['capacity_it_mw'])
        self.assertEqual(view['quantity_fields']['capacity_it_mw'],quantity)
        unsupported={'value_range':[50,60],'unit':'MW','range_basis':'invented interval','quote':'50 MW and 60 MW'}
        self.assertFalse(project_review.quantity_supported(unsupported,[50,60]))

    def test_historical_revision_requires_exact_owner_decision_and_preserves_old_values(self):
        from inresearch.knowledge import site_timeline
        p=self.observation_proposal();project_review.apply(self.root,self.data,p)
        old=json.loads((self.root/'data/projects.json').read_text())['records'][0]
        prior=old['observations'][0]
        corrected=copy.deepcopy(p);corrected['baseline_sha256']=project_review.digest(old)
        corrected['project']['tenant']=['corrected user']
        corrected['review'].update(by='fixture owner',authority='owner')
        metadata=corrected['observation']
        metadata['revision']={'action':'replace','observation_ids':[prior['id']]}
        # Authority alone, or a generic approved string, is never sufficient.
        for decision in (None,{'decision':'approved'}):
            metadata['revision']['owner_decision']=decision
            with self.assertRaisesRegex(ValueError,'specific_owner'):project_review.apply(self.root,self.data,corrected)
        metadata['revision']['owner_decision']={
            'by':'fixture owner','at':'2026-10-11','decision':'approved','action':'replace',
            'observation_ids':[prior['id']],'after_sha256':site_timeline.revision_digest(dict(metadata,fields={'tenant':['corrected user']})),
            'rationale':'fixture approves this exact correction','evidence_reference':'test fixture owner message'}
        wrong=copy.deepcopy(corrected);wrong['project']['tenant']=['unapproved new after value']
        with self.assertRaisesRegex(ValueError,'specific_owner'):project_review.apply(self.root,self.data,wrong)
        project_review.apply(self.root,self.data,corrected)
        self.assertEqual(project_review.apply(self.root,self.data,corrected)['state'],'already_applied')
        row=json.loads((self.root/'data/projects.json').read_text())['records'][0]
        self.assertEqual(row['observations'][0],prior)
        self.assertEqual(site_timeline.current(row,'2026-10-11')['tenant'],['corrected user'])

    def test_legacy_observation_exact_replay_is_not_rewritten_by_new_protocol(self):
        p=self.observation_proposal();project_review.apply(self.root,self.data,p)
        path=self.root/'data/projects.json';value=json.loads(path.read_text());row=value['records'][0]['observations'][0]
        for key in ('schema_version','source_versions','reviewed_at'):row.pop(key)
        row['recorded_at']=p['review']['at']
        row['adoption'].pop('source_kind');row['adoption'].pop('source_id')
        path.write_text(json.dumps(value));before=path.read_bytes()
        self.assertEqual(project_review.apply(self.root,self.data,p)['state'],'already_applied')
        self.assertEqual(path.read_bytes(),before)

    def test_new_observation_rejects_malformed_or_self_granted_C3_and_bad_CAS(self):
        p=self.observation_proposal();before=(self.root/'data/projects.json').read_bytes()
        for key in ('legacy','missing','delegate','self','future','clock','cas'):
            bad=copy.deepcopy(p);delegation=bad['review']['delegation']
            if key=='legacy':bad['review']['delegation']='someone said approved'
            if key=='missing':delegation.pop('reference')
            if key=='delegate':delegation['delegate']='someone else'
            if key=='self':delegation['granted_by']=bad['review']['by']
            if key=='future':delegation['granted_at']='2027-01-01'
            if key=='clock':bad['review']['at']='2026-10-06T12:00:00'
            if key=='cas':bad['baseline_sha256']='0'*64
            with self.subTest(key=key),self.assertRaises(ValueError):project_review.apply(self.root,self.data,bad)
            self.assertEqual((self.root/'data/projects.json').read_bytes(),before)

    def test_reader_publication_date_requires_the_actual_sealed_page(self):
        sha='a'*64
        quote='Updated Oct. 5, 2026.'
        context={'source_kind':'reader_report','source_texts':{sha:quote+'\nPhysical event on another page'},
                 'source_pages':{sha:{1:quote,2:'Physical event on another page'}},'first_received':{},'publication_metadata':{}}
        meta={'source_versions':[{'source_sha256':sha,'published_at':'2026-10-05','publication_evidence':{
            'kind':'original_quote','quote':quote,'locator':'reader:page:1','basis':'native version update date'}}]}
        result=project_review._source_versions(meta,context)
        self.assertEqual(result[0]['published_at'],'2026-10-05');self.assertIsNone(result[0]['first_received_at'])
        for locator in ('reader:page:2','reader:page:0','some arbitrary location'):
            bad=copy.deepcopy(meta);bad['source_versions'][0]['publication_evidence']['locator']=locator
            with self.subTest(locator=locator),self.assertRaisesRegex(ValueError,'sealed_reader_page'):
                project_review._source_versions(bad,context)

    def test_computed_interval_requires_recomputable_inputs_and_explicit_assumptions(self):
        assertion={'value_range':[400,500],'unit':'MW','range_basis':'explicit estimated interval',
                   'quote':'Facility supply is 1000 MW.',
                   'derivation':{'operation':'scale_range','inputs':[1000],'factor_range':[.4,.5],
                                 'basis':'bounded facility-to-IT factor'}}
        self.assertTrue(project_review.quantity_supported(assertion,[1000]))
        self.assertFalse(project_review.quantity_supported(assertion,[900]))
        assertion['derivation']['factor_range']=[.5,.4]
        self.assertFalse(project_review.quantity_supported(assertion,[1000]))

    def test_reader_bridge_cannot_bypass_new_review_by_using_the_legacy_write(self):
        p=copy.deepcopy(self.proposal);p['source_kind']='reader_report'
        p['review']['delegation']='generic unverified string'
        before=(self.root/'data/projects.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'requires_site_observation'):
            project_review.apply(self.root,self.data,p)
        self.assertEqual((self.root/'data/projects.json').read_bytes(),before)

    def test_daily_first_arrival_requires_exact_completed_bundle_member_identity(self):
        sha=self.proposal['assertions'][0]['source_sha256'];unknown='f'*64
        directory=self.data/'material-reviews/daily-deliveries'
        for name,receipt in {
            'complete':{'producer':'inews_geluoke','status':'indexed_candidate','first_received_at':'2026-10-05T23:00:00-01:00',
                        'members':[{'sha256':sha}]},
            'failed':{'producer':'inews_geluoke','status':'arrived','first_received_at':'2020-01-01T00:00:00Z',
                      'members':[{'sha256':sha},{'sha256':unknown}]},
            'unrelated':{'producer':'inews_geluoke','status':'indexed_candidate','first_received_at':'2021-01-01T00:00:00Z',
                         'members':[{'sha256':'e'*64}]},
            'legacy':{'producer':'inews_geluoke','status':'indexed_candidate','first_received_at':None,
                      'received_at':'2019-01-01T00:00:00Z','members':[{'sha256':sha}]}}.items():
            (directory/(name+'.json')).write_text(json.dumps(receipt))
        result=project_review._daily_first_received(self.data,{sha,unknown})
        self.assertEqual(result[sha]['at'],'2026-10-05T23:00:00-01:00')
        self.assertEqual(result[sha]['provenance'],'indexed_bundle_first_verified_arrival')
        self.assertNotIn(unknown,result)

    def test_explicit_review_adopts_one_project_and_replay_does_not_duplicate(self):
        first=project_review.apply(self.root,self.data,self.proposal)
        second=project_review.apply(self.root,self.data,self.proposal)
        self.assertEqual(first['review_id'],second['review_id'])
        self.assertEqual(second['state'],'already_applied')
        rows=json.loads((self.root/'data/projects.json').read_text())['records']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['capacity_it_mw_by_status'],{'L2':60})
        self.assertEqual(project_review.queue(self.data,self.root)['counts']['adopted'],1)

    def test_changed_source_fake_quote_and_grid_as_it_rejected_before_write(self):
        for key in ('stale','quote','basis','delegation','replacement','overlap'):
            p=copy.deepcopy(self.proposal)
            if key=='stale':p['source_version']='bad'
            if key=='quote':p['assertions'][0]['quote']='unseen 60 MW'
            if key=='basis':p['assertions'][0]['basis']='grid'
            if key=='delegation':p['review'].pop('delegation')
            if key=='replacement':p['replaces_record_ids']=['old']
            if key=='overlap':p['project']['capacity_it_mw']=60
            with self.subTest(key=key),self.assertRaises(ValueError):project_review.apply(self.root,self.data,p)
            self.assertEqual(json.loads((self.root/'data/projects.json').read_text())['records'],[])

    def test_existing_conclusion_cannot_be_overwritten_and_source_bytes_required(self):
        project_review.apply(self.root,self.data,self.proposal)
        p=copy.deepcopy(self.proposal);p['project']['notes']='new conclusion'
        with self.assertRaisesRegex(ValueError,'existing_project'):project_review.apply(self.root,self.data,p)
        source=next((self.data/'acquisition/blobs').rglob('*.txt'));source.chmod(0o600);source.write_text('changed')
        with self.assertRaisesRegex(ValueError,'source_archive'):project_review.apply(self.root,self.data,self.proposal)

    def test_ready_queue_does_not_adopt_or_block_other_materials(self):
        before=(self.root/'data/projects.json').read_bytes()
        self.assertEqual(project_review.prepare(self.data,self.root)['counts']['needs_identity'],1)
        self.assertEqual((self.root/'data/projects.json').read_bytes(),before)

    def test_missing_field_supplement_preserves_prior_adoption_and_conflicting_value_waits(self):
        project_review.apply(self.root,self.data,self.proposal)
        old=json.loads((self.root/'data/projects.json').read_text())['records'][0]
        p=copy.deepcopy(self.proposal);p['baseline_sha256']=project_review.digest(old)
        p['project']['power_status']='一期供电仍待核验'
        project_review.apply(self.root,self.data,p)
        self.assertEqual(project_review.apply(self.root,self.data,p)['state'],'already_applied')
        updated=json.loads((self.root/'data/projects.json').read_text())['records'][0]
        self.assertEqual(updated['adoption_history'][0],old['adoption'])
        p['baseline_sha256']=project_review.digest(updated);p['project']['notes']='different conclusion'
        with self.assertRaisesRegex(ValueError,'owner_decision'):project_review.apply(self.root,self.data,p)

    def test_b_tier_selected_sample_requires_actual_named_confirmation(self):
        ledger_path=self.data/'acquisition/daily-events.json'
        ledger=json.loads(ledger_path.read_text());e=ledger['records'][self.event['id']]
        for n in range(100):
            e['body']=self.event['body']+' sample '+str(n)
            if int(project_review.event_identity(e)[:8],16)%10==0:break
        else:self.fail('sample fixture not found')
        ledger_path.write_text(json.dumps(ledger))
        p=copy.deepcopy(self.proposal);p['source_version']=project_review.event_identity(e)
        p['review'].update(score=7,tier='B',authority='reviewer')
        with self.assertRaisesRegex(ValueError,'sample_review'):project_review.apply(self.root,self.data,p)
        p['review']['sample_review']={'by':'second actual reviewer','decision':'confirmed'}
        self.assertEqual(project_review.apply(self.root,self.data,p)['state'],'applied_in_checkout')

    def test_new_time_observation_updates_view_preserves_baseline_and_replays(self):
        from inresearch.knowledge.site_timeline import current
        project_review.apply(self.root,self.data,self.proposal)
        old=json.loads((self.root/'data/projects.json').read_text())['records'][0]
        p=copy.deepcopy(self.proposal);p['baseline_sha256']=project_review.digest(old)
        p['fields']=['tenant'];p['project']['tenant']=['new-user']
        p['observation']={'effective_at':'2026-10-05','kind':'reported','basis':'reviewed original','scope':'whole_site'}
        p['review']['delegation']={'delegate':p['review']['by'],'granted_by':'fixture owner',
                                 'granted_at':'2026-10-06','reference':'test-only delegation',
                                 'scope':'new_or_supplemental_research'}
        first=project_review.apply(self.root,self.data,p)
        self.assertEqual(project_review.apply(self.root,self.data,p)['state'],'already_applied')
        updated=json.loads((self.root/'data/projects.json').read_text())['records'][0]
        self.assertEqual(updated.get('tenant'),old.get('tenant'))
        self.assertEqual(current(updated,'2026-10-11')['tenant'],['new-user'])
        self.assertEqual(updated['observations'][0]['adoption']['review_id'],first['review_id'])
        p['project']['location']='Different land';p['fields']=['location']
        with self.assertRaisesRegex(ValueError,'relocate'):project_review.apply(self.root,self.data,p)

    def test_explicit_rounding_and_derived_increment_keep_precision_and_scope(self):
        self.assertTrue(project_review.quantity_supported(
            {'value':421,'unit':'MW','decimal_places':0,'approximation_basis':'rounded satellite estimate'},[421.25]))
        self.assertFalse(project_review.quantity_supported({'value':421,'unit':'MW'},[421.25]))
        assertion={'value':422,'unit':'MW','derivation':{'operation':'difference','inputs':[843,421],
                                                       'basis':'forecast total less estimated current IT'}}
        self.assertTrue(project_review.quantity_supported(assertion,[421,843]))
        self.assertFalse(project_review.quantity_supported(assertion,[421]))
        assertion['derivation'].update(operation='sum',inputs=[211,211]);assertion['value']=422
        self.assertFalse(project_review.quantity_supported(assertion,[211]))

    def test_known_reviewed_site_update_does_not_require_recreating_phase_identity(self):
        project_review.apply(self.root,self.data,self.proposal)
        ledger_path=self.data/'acquisition/daily-events.json';ledger=json.loads(ledger_path.read_text())
        event=ledger['records'][self.event['id']]
        event.update(identity_review='resolved',matched_site_id='fi-salo-test',structured_evidence_status='quotes_verified')
        event['editorial_event']['project']={}
        ledger_path.write_text(json.dumps(ledger))
        # No current adoption for this changed source, so readiness is recomputed.
        self.assertEqual(project_review.queue(self.data,self.root)['records'][0]['state'],'ready_for_review')
        p=copy.deepcopy(self.proposal);p['source_version']=project_review.event_identity(event)
        p['project']['site_id']='different-land'
        with self.assertRaisesRegex(ValueError,'site_mismatch'):project_review.apply(self.root,self.data,p)
