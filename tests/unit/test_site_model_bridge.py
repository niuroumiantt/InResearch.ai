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
        with self.assertRaisesRegex(ValueError,'derivation_output'):bridge.validate(changed,self.projects,self.spec)
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
        self.assertEqual(len(out['review']['derivations']),13)
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
        changed_doc=copy.deepcopy(self.doc);changed_doc['sites'][0]['parameter_basis']['pue']['private_note']='private'
        changed_doc['sites'][0]['parameter_basis']['pue']['source_ref']['machine']='private'
        with patch.object(bridge,'load',return_value=changed_doc):out=bridge.project(ROOT,self.projects,'us-tx-abilene')
        self.assertNotIn('private_note',out['parameter_basis']['pue'])
        self.assertNotIn('machine',out['parameter_basis']['pue']['source_ref'])

    def test_invalid_mapping_keeps_site_readable_without_filling(self):
        with patch.object(bridge,'project',side_effect=ValueError('private path must not escape')):
            out=snapshot(ROOT,{'site':'us-tx-abilene'})
        self.assertEqual(out['detail']['site_id'],'us-tx-abilene')
        self.assertIsNone(out['detail']['model_bridge'])
        self.assertIn('重新复核',out['detail']['model_bridge_error'])
        self.assertNotIn('private path',json.dumps(out))
        self.assertFalse(bridge._url('https://example.com/file?token=secret'))

    def test_shared_dependencies_cannot_be_declared_independent(self):
        site=self.doc['sites'][0]
        self.assertEqual(site['dependency_notice']['status'],'shared_upstream_assumptions')
        self.assertNotIn('independent_of',site['rules'][0])
        changed=copy.deepcopy(self.doc);changed['sites'][0]['rules'][0]['independent_of']=['gpu-integer-configuration']
        with self.assertRaisesRegex(ValueError,'false_independence'):bridge.validate(changed,self.projects,self.spec)
        changed=copy.deepcopy(self.doc);item=changed['sites'][0]
        next(d for d in item['review']['derivations'] if d['id']=='current-it-from-configuration')['input_item_ids']=['permit-turbines']
        item['review_sha256']=bridge.digest(item['review'])
        with self.assertRaisesRegex(ValueError,'shared_dependencies'):bridge.validate(changed,self.projects,self.spec)

    def test_source_content_checks_never_adopt_site_or_model(self):
        item=self.doc['sites'][0]
        self.assertEqual(len(item['document_checks']),10)
        self.assertTrue(all(d['status']=='source_content_checked' and not d['actual_site_verified'] and not d['model_eligible'] for d in item['document_checks']))
        changed=copy.deepcopy(self.doc);item=changed['sites'][0];item['document_checks'][0]['model_eligible']=True
        item['document_review_sha256']=bridge.digest(item['document_checks'])
        with self.assertRaisesRegex(ValueError,'content_not_site_adoption'):bridge.validate(changed,self.projects,self.spec)
        self.assertIn('四个翼区不是四栋',next(d for d in self.doc['sites'][0]['document_checks'] if d['id']=='drawing-building2')['boundary'])

    def test_parameter_labels_cover_inputs_without_false_facts(self):
        item=self.doc['sites'][0];basis=item['parameter_basis']
        self.assertEqual(set(basis),set(self.spec['inputs']))
        self.assertEqual(basis['energy_quota_mw']['kind'],'unknown_unset')
        self.assertEqual(basis['gate_wait_years']['kind'],'assumption')
        self.assertEqual(basis['permit_months']['kind'],'assumption')
        self.assertEqual(basis['construction_years']['kind'],'generic_reference')
        self.assertEqual(basis['it_class']['kind'],'scenario_choice')
        changed=copy.deepcopy(self.doc);changed['sites'][0]['parameter_basis']['energy_quota_mw']['kind']='regional_reference'
        with self.assertRaisesRegex(ValueError,'parameter_semantics'):bridge.validate(changed,self.projects,self.spec)
        changed=copy.deepcopy(self.doc);changed['sites'][0]['parameter_basis']['pue']['actual_state']='existing_estimate'
        with self.assertRaisesRegex(ValueError,'false_site_fact'):bridge.validate(changed,self.projects,self.spec)

    def test_official_mirror_is_one_source_and_version_gap_stays_visible(self):
        item=self.doc['sites'][0];sources={s['id']:s for s in item['review']['sources']}
        self.assertEqual(sources['permit-official']['sha256'],sources['permit']['sha256'])
        self.assertIn('旧版工作簿',item['dependency_notice']['version_limit'])
        self.assertEqual(sources['permit-transfer']['remaining_pages'],'not_individually_reviewed')
        changed=copy.deepcopy(self.doc);item=changed['sites'][0]
        next(s for s in item['review']['sources'] if s['id']=='permit-official')['sha256']='0'*64
        item['review_sha256']=bridge.digest(item['review'])
        with self.assertRaisesRegex(ValueError,'source_mirror'):bridge.validate(changed,self.projects,self.spec)

    def test_arithmetic_replays_are_not_source_formula_execution(self):
        from decimal import Decimal as D
        replay={row['label']:row for row in self.doc['sites'][0]['dependency_notice']['replays']}
        self.assertEqual(D(str(replay['所选四栋IT估算']['value'])),D(4)*D(50400)/D(72)*D('.132')*D('1.14'))
        self.assertEqual(replay['GPU合计']['value'],100800+100800)
        self.assertEqual(replay['所选四栋算力估算']['status'],'precision_unresolved')
        self.assertIn('未贯通',self.doc['sites'][0]['dependency_notice']['cost_limit'])

    def test_energy_review_preserves_unknowns_and_snapshot_period(self):
        out=bridge.project(ROOT,self.projects,'us-tx-abilene');energy=out['energy_review']
        self.assertEqual(energy['period']['snapshot_date'],out['scope']['effective_at'])
        self.assertIsNone(energy['period']['actual_start'])
        self.assertEqual(energy['period']['capacity_profile_state'],'unknown')
        self.assertEqual({c['id']:c['actual_state'] for c in energy['checks']},
                         {'capacity_range':'existing_estimate','average_it_load':'unknown','period_pue':'unknown','applicable_price':'unknown'})
        self.assertTrue(all(not c['automatic_fill'] for c in energy['checks']))
        self.assertEqual(out['review']['item_counts']['anomaly'],3)
        self.assertIn('energy-rep-candidate',next(c for c in energy['checks'] if c['id']=='applicable_price')['evidence_ids'])
        self.assertEqual(next(s for s in out['review']['sources'] if s['id']=='sec-dc1-extract')['capture_kind'],'web_tool_extract')
        self.assertEqual(out['energy_review_sha256'],bridge.digest(energy))
        sources={s['id']:s for s in out['review']['sources']}
        self.assertEqual(sources['mortenson-grid']['mirror_of'],'mortenson')
        self.assertEqual(sources['mortenson-grid']['sha256'],sources['mortenson']['sha256'])
        for field,value,error in [('status','measured','review_changed')]:
            changed=copy.deepcopy(self.doc);item=changed['sites'][0];item['energy_review'][field]=value
            item['energy_review_sha256']=bridge.digest(item['energy_review'])
            with self.assertRaisesRegex(ValueError,error):bridge.validate(changed,self.projects,self.spec)
        for change,error in [('period','energy_period'),('candidate','energy_not_measured'),('source','energy_evidence')]:
            changed=copy.deepcopy(self.doc);item=changed['sites'][0];e=item['energy_review']
            if change=='period':e['period']['actual_start']='2026-01-01'
            elif change=='candidate':e['checks'][1]['actual_state']='measured'
            else:e['checks'][0]['source_ids']=['missing']
            item['energy_review_sha256']=bridge.digest(e)
            with self.assertRaisesRegex(ValueError,error):bridge.validate(changed,self.projects,self.spec)

    def test_energy_proxy_rejects_double_count_and_false_bounds(self):
        for change,error in [('demand','energy_double_count'),('probability','sensitivity_identity'),('bounds','sensitivity_bounds')]:
            changed=copy.deepcopy(self.doc);item=changed['sites'][0];e=item['energy_review']
            if change=='demand':e['billing']['demand_rate_override']=3.8
            elif change=='probability':e['sensitivity']['status']='confidence_interval'
            else:e['sensitivity']['load_factors']=[.5,.7,1.2]
            item['energy_review_sha256']=bridge.digest(e)
            with self.assertRaisesRegex(ValueError,error):bridge.validate(changed,self.projects,self.spec)
        b=self.doc['sites'][0]['parameter_basis']['demand_rate']
        self.assertEqual(b['kind'],'analysis_choice');self.assertEqual(b['actual_state'],'unknown')

    def test_energy_public_projection_drops_unregistered_nested_metadata(self):
        changed=copy.deepcopy(self.doc['sites'][0]);e=changed['energy_review']
        e['private']='/Users/private/source';e['checks'][0]['private']='/Users/private/contract';e['billing']['secret']='contract';e['period']['local_path']='private'
        out=bridge._public(changed,bridge.BRIDGE)
        self.assertNotIn('/Users/',json.dumps(out));self.assertNotIn('secret',out['energy_review']['billing']);self.assertNotIn('local_path',out['energy_review']['period'])
