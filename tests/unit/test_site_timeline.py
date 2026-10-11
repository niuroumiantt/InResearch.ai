import copy
import unittest
from inresearch.knowledge import site_timeline


class SiteTimelineTests(unittest.TestCase):
    def observation(self, ident='new', when='2026-10-01', **fields):
        return dict(id=ident, effective_at=when, recorded_at='2026-10-11T00:00:00Z',
                    scope='whole_site', kind='disclosed', basis='source review',
                    fields=fields or {'tenant': ['new-user']}, adoption={'review_id': ident})

    def native(self, ident='native', when='2026-10-01', **fields):
        row=self.observation(ident,when,**fields)
        row.update(schema_version=2,reviewed_at='2026-10-11T00:00:00Z',source_versions=[{
            'source_sha256':'a'*64,'published_at':None,'first_received_at':None,
            'published_at_precision':'unknown','first_received_at_precision':'unknown',
            'published_at_provenance':'unknown native publication date',
            'first_received_at_provenance':'unknown legacy receipt'}])
        row['adoption']['review']={'by':'fixture reviewer','at':row['reviewed_at'],'tier':'A','score':8,
                                  'authority':'delegated_reviewer','decision':'adopted','rationale':'fixture reviewed source',
                                  'delegation':{'delegate':'fixture reviewer','granted_by':'fixture owner',
                                                'granted_at':'2026-10-11','reference':'test-only delegation',
                                                'scope':'new_or_supplemental_research'}}
        row['adoption'].update(source_kind='daily_event',source_id='fixture-event',source_version='b'*64,
                               document_refs=[{'sha256':'c'*64}],target_ids=['fixture-demand'],
                               assertions=[{'source_sha256':'a'*64,'quote':'fixture native quote','locator':'fixture:1'}])
        return row

    def revision(self, old, ident='revision', action='replace', **fields):
        row=self.native(ident,old['effective_at'],**(fields or old['fields']))
        row['scope']=old['scope']
        row['adoption']['review'].update(by='fixture owner',authority='owner')
        row['revision']={'action':action,'observation_ids':[old['id']],'owner_decision':{
            'by':'fixture owner','at':'2026-10-11','decision':'approved','action':action,
            'observation_ids':[old['id']],'after_sha256':site_timeline.revision_digest(row),
            'rationale':'fixture approves this exact historical correction',
            'evidence_reference':'test-only concrete owner decision'}}
        return row

    def test_precision_intervals_overlap_without_inventing_a_later_day(self):
        old=self.native('old','2026-08-31',tenant=['older'])
        month=self.native('month','2026-09',tenant=['monthly'])
        row={'observations':[old,month]}
        result=site_timeline.current(row,'2026-10-11')
        self.assertEqual(result['tenant'],['monthly'])
        self.assertEqual(result['tracking']['fields']['tenant']['effective_at'],'2026-09')
        row['observations'].append(self.native('day','2026-09-20',tenant=['day claim']))
        result=site_timeline.current(row,'2026-10-11')
        self.assertEqual(result['tenant'],['older'])
        self.assertEqual(set(result['tracking']['conflicts'][0]['observation_ids']),{'day','month'})
        row['observations'].append(self.native('future-month','2026-10',tenant=['not dated yet']))
        self.assertEqual(site_timeline.current(row,'2026-10-11')['tracking']['forecasts'],1)

    def test_validity_order_and_expiry_never_resurrect_an_old_tenant(self):
        row=self.native();row['valid_until']='2026-09'
        with self.assertRaisesRegex(ValueError,'reversed'):site_timeline.check(row)
        row['valid_until']='2026-10-05'
        result=site_timeline.current({'tenant':['legacy'],'observations':[row]},'2026-10-11')
        self.assertIsNone(result['tenant'])
        self.assertTrue(result['tracking']['fields']['tenant']['expired'])
        row['effective_at']='2026-10';row['valid_until']='2026-10-05'
        site_timeline.check(row)  # Precision intervals overlap; no false exact ordering.
        row['recorded_at']='2026-10-11T12:00:00'
        with self.assertRaises(ValueError):site_timeline.check(row)

    def test_native_ranges_preserve_units_and_do_not_supply_a_scalar_or_partial_total(self):
        quantity={'value_range':[.4,.5],'unit':'GW','assumptions':['cooling-based interval']}
        row=self.native(capacity_it_mw=quantity,capacity_it_mw_by_status={},capacity_assessment=None)
        result=site_timeline.current({'observations':[row]},'2026-10-11')
        self.assertIsNone(result['capacity_it_mw'])
        self.assertEqual(result['quantity_fields']['capacity_it_mw'],quantity)
        row['fields'].update(capacity_it_mw=None,capacity_it_mw_by_status={'L8':quantity,'L7':20})
        result=site_timeline.current({'observations':[row]},'2026-10-11')
        self.assertEqual(result['capacity_it_mw_by_status'],{})
        self.assertEqual(result['quantity_fields']['capacity_it_mw_by_status'],{'L8':quantity,'L7':20})
        for bad in ({'value_range':[5,4],'unit':'MW','basis':'native range'},
                    {'value_range':[4,5],'unit':'MWh','basis':'native range'},
                    {'value_range':[False,5],'unit':'MW','basis':'native range'},
                    {'value_range':[4,5],'unit':'MW'}):
            row['fields'].update(capacity_it_mw=bad,capacity_it_mw_by_status={})
            with self.subTest(bad=bad),self.assertRaises(ValueError):site_timeline.check(row)

    def test_scope_values_and_revision_chains_are_isolated_and_exact(self):
        whole=self.native(tenant=['whole user'])
        phase=self.native('phase',tenant=['phase user']);phase['scope']='phase:hall-a'
        result=site_timeline.current({'observations':[whole,phase]},'2026-10-11')
        self.assertEqual(result['tenant'],['whole user'])
        self.assertEqual(result['scope_views']['phase:hall-a']['tenant'],['phase user'])
        corrected=self.revision(whole,tenant=['corrected'])
        project,_=site_timeline.append({'observations':[whole,phase]},corrected)
        self.assertEqual(site_timeline.current(project,'2026-10-11')['tenant'],['corrected'])
        withdrawal=self.revision(corrected,'withdrawal','withdraw')
        project,_=site_timeline.append(project,withdrawal)
        self.assertNotIn('tenant',site_timeline.current(project,'2026-10-11'))
        self.assertEqual(project['observations'][0]['fields']['tenant'],['whole user'])
        for key in ('delegation','after','scope','fields','absent'):
            bad=copy.deepcopy(corrected)
            if key=='delegation':bad['adoption']['review']['authority']='delegated_reviewer'
            if key=='after':bad['revision']['owner_decision']['after_sha256']='0'*64
            if key=='scope':bad['scope']='phase:hall-a'
            if key=='fields':bad['fields']['notes']='extra field'
            if key=='absent':bad['revision']['observation_ids']=['missing'];bad['revision']['owner_decision']['observation_ids']=['missing']
            if key in ('scope','fields'):bad['revision']['owner_decision']['after_sha256']=site_timeline.revision_digest(bad)
            with self.subTest(key=key),self.assertRaises(ValueError):site_timeline.append({'observations':[whole]},bad)

    def test_equivalent_units_do_not_create_a_same_time_conflict(self):
        first=self.native('mw',capacity_facility_mw=1000)
        second=self.native('gw',capacity_facility_mw={'value':1,'unit':'GW'})
        result=site_timeline.current({'observations':[first,second]},'2026-10-11')
        self.assertEqual(result['capacity_facility_mw'],1000)
        self.assertEqual(result['tracking']['conflicts'],[])

    def test_v2_history_validation_rejects_incomplete_support_and_bad_review(self):
        row=self.native()
        for key in ('support','source','delegation','review_time','precision','review_shape'):
            bad=copy.deepcopy(row)
            if key=='support':bad['adoption']['assertions']=[]
            if key=='source':bad['adoption']['assertions'][0]['source_sha256']='f'*64
            if key=='delegation':bad['adoption']['review']['delegation']['granted_by']='fixture reviewer'
            if key=='review_time':bad['reviewed_at']='2026-10-10T00:00:00Z'
            if key=='precision':bad['effective_at']='2026-13'
            if key=='review_shape':bad['adoption']['review']='not a review object'
            with self.subTest(key=key),self.assertRaises(ValueError):site_timeline.check_history({'observations':[bad]})

    def test_expiry_disagreement_is_a_conflict_and_conversion_cannot_overflow(self):
        a=self.native('open');b=self.native('end');b['valid_until']='2026-10-05'
        result=site_timeline.current({'tenant':['baseline'],'observations':[a,b]},'2026-10-11')
        self.assertEqual(result['tenant'],['baseline'])
        self.assertTrue(result['tracking']['conflicts'])
        bad=self.native(capacity_facility_mw={'value_range':[1e308,1e308],'unit':'GW','basis':'overflow fixture'})
        with self.assertRaises(ValueError):site_timeline.current({'observations':[bad]},'2026-10-11')

    def test_same_value_different_nature_does_not_promote_or_erase_estimation_by_id(self):
        for estimate_id,disclosed_id in (('a','b'),('b','a')):
            estimate=self.native(estimate_id,capacity_it_mw=421,capacity_it_mw_by_status={},capacity_assessment=None)
            estimate.update(kind='estimated',assumptions=['satellite estimate'])
            disclosed=self.native(disclosed_id,capacity_it_mw=421,capacity_it_mw_by_status={},capacity_assessment=None)
            result=site_timeline.current({'observations':[estimate,disclosed]},'2026-10-11')
            self.assertTrue(result['tracking']['conflicts'])
            self.assertNotIn('capacity_it_mw',result['tracking']['fields'])
        different=copy.deepcopy(estimate);different['id']='other';different['assumptions']=['different method']
        self.assertTrue(site_timeline.current({'observations':[estimate,different]},'2026-10-11')['tracking']['conflicts'])

    def test_new_metadata_cannot_bypass_v2_review_by_claiming_the_legacy_protocol(self):
        row=self.observation(capacity_facility_mw={'value_range':[1,2],'unit':'MW','basis':'native range'})
        with self.assertRaisesRegex(ValueError,'v2_required'):site_timeline.check(row)

    def test_native_range_freshness_uses_the_quantity_and_actual_review_time(self):
        quantity={'value_range':[400,500],'unit':'MW','basis':'explicit native interval'}
        for field in ('capacity_it_mw','capacity_it_mw_by_status','capacity_facility_mw'):
            fields={'capacity_it_mw':None,'capacity_it_mw_by_status':{},'capacity_assessment':None}
            fields[field]={'L8':quantity} if field=='capacity_it_mw_by_status' else quantity
            row=self.native('range','2026-01-01',**fields)
            old_time='2026-01-01T00:00:00Z'
            row['reviewed_at']=old_time;row['adoption']['review']['at']=old_time
            row['adoption']['review']['delegation']['granted_at']='2026-01-01'
            stale=site_timeline.current({'status':'L8','observations':[row]},'2026-10-11')
            with self.subTest(field=field):
                self.assertIn(field,stale['tracking']['review_due_fields'])
                self.assertEqual(stale['quantity_fields'][field],fields[field])
                row['reviewed_at']='2026-10-11T00:00:00Z'
                row['adoption']['review']['at']=row['reviewed_at']
                fresh=site_timeline.current({'status':'L8','observations':[row]},'2026-10-11')
                self.assertNotIn(field,fresh['tracking']['review_due_fields'])
                self.assertEqual(fresh['tracking']['fields'][field]['effective_at'],'2026-01-01')

    def test_newer_effective_time_wins_even_when_older_event_arrives_last(self):
        baseline={'site_id':'fixed-land', 'location':'same block', 'tenant':['old-user']}
        newer=self.observation();older=self.observation('old', '2026-09-01',tenant=['intermediate'])
        row,_=site_timeline.append(baseline,newer);row,_=site_timeline.append(row,older)
        projected=site_timeline.current(row, '2026-10-11')
        self.assertEqual(projected['tenant'], ['new-user'])
        self.assertEqual(row['tenant'],['old-user']);self.assertEqual(row['location'],baseline['location'])
        self.assertEqual(site_timeline.append(row,newer),(row,True))
        changed=copy.deepcopy(newer);changed['fields']['tenant']=[]
        with self.assertRaisesRegex(ValueError,'id_conflict'):site_timeline.append(row,changed)

    def test_future_forecast_and_equal_time_conflict_do_not_silently_replace_current(self):
        row={'tenant':['baseline']}
        rows=[self.observation(),self.observation('disagreement',tenant=['another']),
              self.observation('future','2026-12-01',tenant=['future'])]
        rows[-1]['kind']='forecast';row['observations']=rows
        result=site_timeline.current(row,'2026-10-11')
        self.assertEqual(result['tenant'],['baseline'])
        self.assertEqual(result['tracking']['forecasts'],1)
        self.assertEqual(result['tracking']['conflicts'][0]['field'],'tenant')

    def test_estimated_small_change_accepted_and_it_bundle_does_not_mix_dates(self):
        row={'capacity_it_mw':None,'capacity_it_mw_by_status':{'L8':421}}
        observation=self.observation(capacity_it_mw=421.25,capacity_it_mw_by_status={},capacity_assessment=None)
        observation.update(kind='estimated',assumptions=['satellite cooling estimate'])
        row,_=site_timeline.append(row,observation)
        result=site_timeline.current(row,'2026-10-11')
        self.assertEqual(result['capacity_it_mw'],421.25)
        self.assertEqual(result['capacity_it_mw_by_status'],{})
        self.assertEqual(result['capacity_assessment']['as_of'],'2026-10-01')
        bad=self.observation(capacity_it_mw=422)
        with self.assertRaisesRegex(ValueError,'bundle'):site_timeline.append(row,bad)
        bad=self.observation(location='different block')
        with self.assertRaisesRegex(ValueError,'fields'):site_timeline.append(row,bad)

    def test_assessment_only_update_is_rejected_and_preserves_operating_baseline(self):
        from inresearch.knowledge.industry import project
        baseline={'site_id':'fixed-land', 'status':'L8', 'capacity_it_mw':200,
                  'capacity_it_mw_by_status':{}, 'capacity_assessment':None}
        before=copy.deepcopy(baseline)
        observation=self.observation(capacity_assessment={'kind':'estimate'})
        with self.assertRaisesRegex(ValueError,'capacity_bundle_required'):
            site_timeline.append(baseline,observation)
        self.assertEqual(baseline,before)
        self.assertEqual(site_timeline.current(baseline,'2026-10-11')['capacity_it_mw'],200)
        self.assertEqual(project(baseline)['capacity']['operating'],200)

    def test_source_paths_and_review_private_data_are_not_public(self):
        observation=self.observation();observation['adoption']['private_path']='/secret'
        observation['sources']=[{'url':'https://example.org/original','private_path':'/secret'}]
        result=site_timeline.public_timeline({'observations':[observation]})
        self.assertNotIn('/secret',str(result));self.assertNotIn('adoption',result[0])

    def test_pause_keeps_capacity_history_but_excludes_active_supply(self):
        from inresearch.knowledge.industry import project, totals
        row={'site_id':'same-land','status':'L8','capacity_it_mw':200}
        row,_=site_timeline.append(row,self.observation(lifecycle='paused'))
        view=project(row)
        self.assertEqual(view['capacity']['operating'],200)
        self.assertIn('暂停',view['stage_label'])
        self.assertEqual(totals([view])['operating'],0)
        self.assertEqual(totals([view])['inactive_sites'],1)

    def test_unknown_and_month_only_times_can_be_saved_without_inventing_day(self):
        row={'tenant':['baseline']}
        for ident,when in [('unknown',None),('month','2026-10')]:
            row,_=site_timeline.append(row,self.observation(ident,when))
        result=site_timeline.current(row,'2026-10-11')
        self.assertEqual(result['tenant'],['baseline'])
        self.assertEqual(result['tracking']['imprecise_times'],2)
        self.assertEqual(row['observations'][1]['effective_at'],'2026-10')

    def test_recheck_refreshes_only_reviewed_field_without_rewriting_event_date(self):
        row={'tenant':['old-user'],'status':'L8','verified_date':'2025-01-01'}
        observation=self.observation(when='2026-01-01')
        row,_=site_timeline.append(row,observation)
        result=site_timeline.current(row,'2026-10-11')
        self.assertNotIn('tenant',result['tracking']['review_due_fields'])
        self.assertIn('status',result['tracking']['review_due_fields'])
        self.assertEqual(result['tracking']['fields']['tenant']['effective_at'],'2026-01-01')
        self.assertEqual(row['verified_date'],'2025-01-01')

    def test_news_identity_follows_current_tenant_after_transfer(self):
        from inresearch.knowledge.news_observations import identity
        row={'site_id':'us-tx-unique','name':'Unique Abilene Campus','developer':[],
             'tenant':['old-user'],'location':'Abilene'}
        row,_=site_timeline.append(row,self.observation())
        result=identity({'title':'Unique Abilene Campus expands', 'object_ids':['actor:new-user']},[row])
        self.assertEqual(result['matched_site_id'],'us-tx-unique')

    def test_daily_adoption_metric_counts_time_observations_without_creating_raw_capacity(self):
        import json,tempfile
        from pathlib import Path
        from datetime import datetime,timezone
        from inresearch.knowledge.raw_atlas import build
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'data').mkdir()
            row={'site_id':'us-tx-unique','name':'Unique Abilene Campus','tenant':['old-user']}
            observation=self.observation();observation['adoption']['review']={'at':'2026-10-11T00:00:00Z'}
            row,_=site_timeline.append(row,observation)
            (root/'data/projects.json').write_text(json.dumps({'records':[row]}))
            result=build(root,None,[],now=datetime(2026,10,11,tzinfo=timezone.utc))
            self.assertEqual(result['daily']['adopted_fields_projects'],1)
            self.assertEqual(result['daily']['adopted_project_updates'],1)
            self.assertEqual(result['records'],[])
