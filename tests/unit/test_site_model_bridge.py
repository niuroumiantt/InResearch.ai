import copy
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from inresearch.knowledge import site_model_bridge as bridge
from inresearch.knowledge.industry import snapshot

ROOT = Path(__file__).resolve().parents[2]


class SiteModelBridgeTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT/'data/site_model_bridges.json').read_text())
        self.projects = json.loads((ROOT/'data/projects.json').read_text())['records']
        self.spec = json.loads((ROOT/'data/datacenter_model.json').read_text())

    def test_pinned_estimate_not_future_or_baseline(self):
        result = bridge.project(ROOT, self.projects, 'us-tx-abilene')
        self.assertEqual(result['expected_it_mw'], 421)
        self.assertEqual(result['capacity_source']['kind'], 'estimated')
        self.assertEqual(result['scope']['effective_at'], '2026-07-28')
        self.assertEqual(result['readiness']['project_feasibility'], 'not_verified')
        self.assertEqual({r['target'] for r in result['rules']}, {'it_mw', 'site'})
        self.assertEqual(result['capacity_source']['source_versions'], [s['source_sha256'] for s in next(p for p in self.projects if p['site_id']=='us-tx-abilene')['observations'][0]['source_versions']])
        self.assertEqual(len(result['observation_sha256']), 64)
        self.assertEqual(next(e for e in result['review']['items'] if e['id']=='body-it')['observation_id'],result['observation_id'])

    def test_stale_scope_and_future_fail_closed(self):
        for change in [dict(expected_it_mw=843), dict(observation_id='missing'), dict(scope={**self.doc['sites'][0]['scope'],'effective_at':'2026-11-01'})]:
            doc = copy.deepcopy(self.doc);doc['sites'][0].update(change)
            with self.assertRaises(ValueError):bridge.validate(doc,self.projects,self.spec)

    def test_candidate_cannot_promote_or_fill_parameters(self):
        doc=copy.deepcopy(self.doc);doc['sites'][0]['configurations'][0]['status']='adopted'
        with self.assertRaisesRegex(ValueError,'candidate_not_adopted'):bridge.validate(doc,self.projects,self.spec)
        doc=copy.deepcopy(self.doc);doc['sites'][0]['rules'].append({'target':'it_capex_per_kw'})
        with self.assertRaisesRegex(ValueError,'rule_targets'):bridge.validate(doc,self.projects,self.spec)
        out=bridge.project(ROOT,self.projects,'us-tx-abilene')
        self.assertTrue(all(c['status']=='candidate' for c in out['configurations']+out['economic_candidates']))
        changed=copy.deepcopy(self.doc);item=changed['sites'][0]
        next(e for e in item['review']['items'] if e['id']=='body-it')['observation_id']='wrong-observation'
        item['review_sha256']=bridge.digest(item['review'])
        with self.assertRaisesRegex(ValueError,'rule_targets'):bridge.validate(changed,self.projects,self.spec)
        self.assertEqual(out['economic_candidates'][0]['value'],15900000000)
        self.assertTrue(all(c['state'] in {'adopted','candidate','excluded','unknown','not_checked'} for c in out['coverage']))

    def test_unknown_identity_and_mutation_isolation(self):
        original=copy.deepcopy(self.projects)
        self.assertIsNone(bridge.project(ROOT,self.projects,'unknown'))
        out=bridge.project(ROOT,self.projects,'us-tx-abilene');out['scope']['actor']='Oracle'
        self.assertIsNone(bridge.project(ROOT,self.projects,'us-tx-abilene')['scope']['actor'])
        self.assertEqual(self.projects,original)

    def test_detail_only_and_legacy_link(self):
        detail=snapshot(ROOT,{'site':'us-tx-abilene'})['detail']
        self.assertEqual(detail['site_id'],'us-tx-abilene')
        self.assertEqual(detail['model_bridge']['expected_it_mw'],421)
        self.assertTrue(all('model_bridge' not in row for row in snapshot(ROOT,{'overview':'1'})['rows']))
        self.assertTrue(all('model_bridge' not in row for row in snapshot(ROOT,{'site':'us-tx-abilene'})['rows']))

    def test_review_versions_and_private_paths(self):
        out=bridge.project(ROOT,self.projects,'us-tx-abilene')
        self.assertEqual(len(out['review']['derivations']),5)
        self.assertEqual(len(out['blockers']),3)
        self.assertEqual(out['review']['item_counts']['anomaly'],3)
        self.assertEqual(out['review']['report_exhaustive'],'not_certified')
        encoded=json.dumps(out)
        for text in ['/Users/','text_path','source_receipt','path_sha']:
            self.assertNotIn(text,encoded)
        changed=copy.deepcopy(self.doc)
        changed['sites'][0]['review']['sources'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'review_changed'):bridge.validate(changed,self.projects,self.spec)
        changed=copy.deepcopy(self.projects)
        next(p for p in changed if p['site_id']=='us-tx-abilene')['observations'][0]['basis']+=' changed'
        with self.assertRaisesRegex(ValueError,'observation_changed'):bridge.validate(self.doc,changed,self.spec)

    def test_anomaly_removal_and_rule_bypass_are_rejected(self):
        changed=copy.deepcopy(self.doc)
        changed['sites'][0]['blockers'].pop()
        with self.assertRaisesRegex(ValueError,'missing_blocker'):bridge.validate(changed,self.projects,self.spec)
        changed=copy.deepcopy(self.doc)
        changed['sites'][0]['blockers'][0]['automatic_fill']=True
        with self.assertRaisesRegex(ValueError,'bridge_blocker'):bridge.validate(changed,self.projects,self.spec)
        changed=copy.deepcopy(self.doc)
        changed['sites'][0]['rules'][0]['evidence_ids']=['native-it-overheads']
        with self.assertRaisesRegex(ValueError,'rule_targets'):bridge.validate(changed,self.projects,self.spec)

    def test_source_derivation_cycles_and_unknown_inputs_fail_closed(self):
        for bad in ['cycle','missing']:
            changed=copy.deepcopy(self.doc);item=changed['sites'][0]
            d=item['review']['derivations'][0]
            d['input_item_ids']=[d['output_item_id'] if bad=='cycle' else 'unregistered']
            item['review_sha256']=bridge.digest(item['review'])
            with self.assertRaisesRegex(ValueError,'derivation'):bridge.validate(changed,self.projects,self.spec)

    def test_nested_public_projection_drops_future_metadata(self):
        changed=copy.deepcopy(self.doc['sites'][0])
        changed['private']={'secret':'internal'}
        changed['review']['sources'][0]['path']='/private/source.pdf'
        changed['configurations'][0]['relations']['internal_note']='private'
        changed['review']['items'][0]['machine']='private'
        projected=bridge._public(changed,bridge.BRIDGE)
        self.assertNotIn('/private/',json.dumps(projected))
        self.assertNotIn('private',projected)
        self.assertNotIn('internal_note',projected['configurations'][0]['relations'])
        self.assertNotIn('machine',projected['review']['items'][0])

    def test_invalid_mapping_keeps_site_readable_without_filling(self):
        with patch.object(bridge,'project',side_effect=ValueError('private path must not escape')):
            out=snapshot(ROOT,{'site':'us-tx-abilene'})
        self.assertEqual(out['detail']['site_id'],'us-tx-abilene')
        self.assertIsNone(out['detail']['model_bridge'])
        self.assertIn('重新复核',out['detail']['model_bridge_error'])
        self.assertNotIn('private path',json.dumps(out))
        self.assertFalse(bridge._url('https://example.com/file?token=secret'))
