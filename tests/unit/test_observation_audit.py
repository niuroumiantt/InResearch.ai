import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from inresearch.workflow import observation_audit as audit

ROOT=Path(__file__).resolve().parents[2]


class ObservationAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        p=Path(self.temp.name)/'source.txt';p.write_text('IT capacity estimate 421 MW. No measured bill.')
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        self.data=audit.template(ROOT,'us-tx-abilene')
        self.data['sources']=[dict(id='body',url='https://example.org/report',status='checked',reason='selected fragment read',path=str(p),sha256=sha,text_path=str(p),text_sha256=sha,checked_scope='selected text')]
        key=self.data['checks'][0]['check_id']
        self.data['items']=[dict(id='claim',label='capacity',check_ids=[key],state='candidate',reason='third-party estimate',destination='candidate register',source_id='body',locator='paragraph 1',evidence='421 MW',next_action='review scope')]
        self.data['inventory']=[dict(id='section',source_id='body',locator='section 1',item_ids=['claim'])]
        self.data['required_inventory_ids']=['section']
        self.data['checks'][0].update(state='candidate',item_ids=['claim'])

    def test_twelve_angles_dual_scope_reuse_existing_registry(self):
        c=audit.checklist(ROOT)
        self.assertTrue(c['angles'])
        self.assertTrue(all(a['checks'] for a in c['angles']))
        self.assertEqual(c['architecture']['legacy_variable_views']['role'],'compatibility_display_only')
        self.assertTrue(c['not_a_dispatch_axis'])
        self.assertTrue(all(x['applies_to']==['generic_dc','site'] for a in c['angles'] for x in a['checks']))
        self.assertEqual(next(a for a in c['angles'] if a['id']=='configuration')['provider_status']['fetchfilings'],'receiver_live_file_import')

    def test_partial_audit_never_adopts_or_certifies_exhaustive(self):
        result=audit.audit(ROOT,self.data)
        self.assertEqual(result['formal_adoptions'],0)
        self.assertFalse(result['published'])
        self.assertTrue(result['source_bytes_verified'])
        self.assertEqual(result['report_exhaustive'],'not_certified')
        self.assertEqual(len(result['unresolved_checks']),len(self.data['checks'])-1)

    def test_missing_angle_and_unaccounted_unit_rejected(self):
        for mutate in [lambda d:d['checks'].pop(),lambda d:d['inventory'].clear(),lambda d:d['required_inventory_ids'].append('unread-section')]:
            d=copy.deepcopy(self.data);mutate(d)
            with self.assertRaises(ValueError):audit.audit(ROOT,d)

    def test_unread_attachment_cannot_support_candidate(self):
        d=copy.deepcopy(self.data);d['sources'][0]['status']='unread_attachment'
        with self.assertRaisesRegex(ValueError,'checked_source_locator'):audit.audit(ROOT,d)
        d['items'][0].update(state='unread_attachment',reason='PDF not obtained')
        d['checks'][0]['state']='unread_attachment'
        self.assertEqual(audit.audit(ROOT,d)['item_counts']['unread_attachment'],1)

    def test_source_bytes_and_literal_fragment_required(self):
        for change in [dict(sha256='0'*64),dict(text_sha256='0'*64)]:
            d=copy.deepcopy(self.data);d['sources'][0].update(change)
            with self.assertRaises(ValueError):audit.audit(ROOT,d)
        d=copy.deepcopy(self.data);d['items'][0]['evidence']='Actual spend $15.9B'
        with self.assertRaisesRegex(ValueError,'fragment_missing'):audit.audit(ROOT,d)

    def test_existing_observation_requires_stable_id(self):
        d=copy.deepcopy(self.data);d['items'][0].update(state='existing_observation',observation_id='made-up')
        with self.assertRaisesRegex(ValueError,'existing_observation_missing'):audit.audit(ROOT,d)

    def test_coverage_mapping_and_unsafe_source_rejected(self):
        d=copy.deepcopy(self.data);d['checks'][1].update(state='candidate',item_ids=['claim'])
        with self.assertRaisesRegex(ValueError,'scope_mismatch'):audit.audit(ROOT,d)
        d=copy.deepcopy(self.data);d['sources'][0]['url']='javascript:alert(1)'
        with self.assertRaisesRegex(ValueError,'https_identity'):audit.audit(ROOT,d)

    def test_html_escapes_untrusted_content(self):
        self.data['items'][0]['label']='<script>alert(1)</script>'
        output=audit.render(audit.audit(ROOT,self.data))
        self.assertIn('&lt;script&gt;',output)
        self.assertNotIn('<script>',output)


    def test_new_view_does_not_require_fixed_count(self):
        temp=Path(self.temp.name)/'registry'
        files=['framework/observation_checklist.json','framework/research_questions.json','framework/supply_contract.json','framework/metrics.json','data/datacenter_model.json','data/schema/project.schema.json']
        for name in files:
            target=temp/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
        p=temp/'framework/observation_checklist.json';doc=json.loads(p.read_text())
        added=copy.deepcopy(doc['angles'][0]);added['id']='additional-view'
        for n,check in enumerate(added['checks']):check['id']='additional-view.'+str(n+1)
        doc['angles'].append(added)
        p.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'unmapped_observation_view'):audit.checklist(temp)
        doc['question_templates'].append({'id':'new-purpose','label':'new question','outputs':['explicit new use'],'coverage_ids':[added['id']]})
        p.write_text(json.dumps(doc));self.assertEqual(len(audit.checklist(temp)['angles']),len(doc['angles']))

    def test_provider_profiles_do_not_claim_connection(self):
        c=audit.checklist(ROOT);delivery=c['delivery_requirements']
        self.assertFalse(delivery['wire_protocol_changed'])
        self.assertEqual(delivery['scope'],'research_side_requirements_only')
        self.assertTrue(all(p['deliver'] and p['limit'] for p in delivery['profiles']))

    def test_derivation_unknown_input_and_cycles_rejected(self):
        d=copy.deepcopy(self.data)
        rel=dict(id='derived',output_item_id='claim',input_item_ids=['absent'],source_id='body',locator='p1',formula='a*b',review_state='candidate',assumptions=['scope not verified'],scope='example')
        d['derivations']=[rel]
        with self.assertRaisesRegex(ValueError,'dependencies'):audit.audit(ROOT,d)
        rel['input_item_ids']=['claim']
        with self.assertRaisesRegex(ValueError,'cycle'):audit.audit(ROOT,d)
