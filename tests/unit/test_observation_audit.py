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
        self.assertEqual(len(c['angles']),12)
        self.assertEqual(sum(len(a['checks']) for a in c['angles']),58)
        self.assertTrue(c['not_a_dispatch_axis'])
        self.assertTrue(all(x['applies_to']==['generic_dc','site'] for a in c['angles'] for x in a['checks']))
        self.assertEqual(next(a for a in c['angles'] if a['id']=='configuration')['provider_status']['fetchfilings'],'not_connected')

    def test_partial_audit_never_adopts_or_certifies_exhaustive(self):
        result=audit.audit(ROOT,self.data)
        self.assertEqual(result['formal_adoptions'],0)
        self.assertFalse(result['published'])
        self.assertTrue(result['source_bytes_verified'])
        self.assertEqual(result['report_exhaustive'],'not_certified')
        self.assertEqual(len(result['unresolved_checks']),57)

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
