import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
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
