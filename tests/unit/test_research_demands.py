"""Demand responsibility is enforceable without granting evidence or closure."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from inresearch.knowledge import economics, research_gaps, target_request_contract
from inresearch.workflow import supply

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    return json.loads((ROOT / name).read_text())


class ResearchDemandTests(unittest.TestCase):
    def setUp(self):
        self.targets = load('framework/tco_targets.json')['targets']
        self.model = load('data/datacenter_model.json')
        self.review = load('framework/research_demand_review.json')
        self.requests = {r['model_input']: (t, r) for t in self.targets for r in t['request']['requirements']}

    def test_all_reviewed_inputs_have_one_primary_request_and_explicit_owner(self):
        definitions = self.review['requirements']
        self.assertEqual(set(self.requests), {r['model_input'] for r in definitions})
        self.assertEqual(set(self.requests), set(self.model['input_governance']))
        self.assertEqual(self.requests['tokens_per_gpu_sec'][1]['mechanism'], 'api')
        self.assertEqual(self.requests['water_price'][1]['mechanism'], 'table')
        self.assertEqual(len(self.requests), 17)
        self.assertEqual(len({t['id'] for t, r in self.requests.values()}), 9)
        for key, (t, r) in self.requests.items():
            self.assertIn(key, t['feeds_primary'])
            self.assertEqual(r['id'], t['id'] + '::' + key)
            self.assertEqual(r['decision_owner'], 'research')
            self.assertTrue(r['scope_fields'] and r['question_ids'] and r['acceptance'])
        expected = {'energy_quota_mw': 'fetchstat', 'gate_wait_years': 'fetchstat',
                    'tokens_per_gpu_sec': 'fetchreports', 'refresh_cost_factor': 'fetchquotes',
                    'bot_service_rate': 'fetchfilings', 'renewal_probability': 'fetchfilings'}
        for key, team in expected.items():
            self.assertEqual(self.requests[key][1]['source_team'], team)

    def test_cross_variable_support_and_news_lead_are_explicit_not_answers(self):
        questions = {q['id']: q for q in load('framework/research_questions.json')['records']}
        operation = next(t for t in self.targets if t['id'] == 'P.gpu.operation')
        self.assertEqual(operation['variable_class'], 2)
        self.assertFalse(operation['request']['candidate_question_ids'])
        link = next(r for r in operation['request']['question_links'] if r['question_id'] == 'OBJ-gpu-performance')
        self.assertEqual(questions[link['question_id']]['variable_class'], 1)
        self.assertEqual(link['relation'], 'supports')
        news = [l for t in self.targets if t['id'].startswith('P.') and t['id'].endswith('.news') for l in t['request']['question_links']]
        self.assertTrue(news)
        self.assertTrue(all(l['relation'] == 'lead_for' for l in news))

    def test_mixed_request_requires_selection_scope_and_connected_channel(self):
        target, r = self.requests['energy_quota_mw']
        base = dict(action='create', target_id=target['id'], title='项目批准容量', scope='项目审批原文',
                    acceptance=r['acceptance'], expected_revision=0, question_id=r['question_ids'][0])
        def mutate(**changes):
            return supply.mutate(ROOT, dict(base, operation_id=str(uuid.uuid4()), **changes), 'reviewer')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT': tmp}):
            with self.assertRaisesRegex(ValueError, 'requirement_id'):
                mutate()
            with self.assertRaisesRegex(ValueError, '字段缺失'):
                mutate(requirement_id=r['id'])
            scope = {f: '未知，待取得项目原文' for f in r['scope_fields']}
            with self.assertRaisesRegex(ValueError, '供应方与主执行机'):
                mutate(requirement_id=r['id'], scope_values=scope, provider_id='fetchspec', execution_mode='continuous', execution_host='macmini')
            with self.assertRaisesRegex(ValueError, '尚未接通'):
                mutate(requirement_id=r['id'], scope_values=scope, provider_id=r['source_team'], execution_mode='continuous', execution_host=r['host'])
            mutate(requirement_id=r['id'], scope_values=scope)
            state = supply.read(ROOT)
            self.assertEqual(state['revision'], 1)
            self.assertFalse(state['tasks'])
            self.assertEqual(state['demands'][0]['requirement_id'], r['id'])

    def test_legacy_mixed_demand_cannot_gain_task_and_reviewed_cross_link_can(self):
        target, r = self.requests['tokens_per_gpu_sec']
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT': tmp}):
            path = supply.ledger_path(ROOT)
            path.parent.mkdir(parents=True)
            state = {'version': 1, 'revision': 0, 'demands': [{'id': 'legacy', 'target_id': target['id']}], 'tasks': [], 'operations': []}
            path.write_text(json.dumps(state))
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'requirement_id'):
                supply.mutate(ROOT, dict(action='assign', operation_id=str(uuid.uuid4()), expected_revision=0,
                    demand_id='legacy', provider_id='fetchquotes', execution_mode='assisted', execution_host='macmini'), 'admin')
            self.assertEqual(path.read_bytes(), before)
            supply.mutate(ROOT, dict(action='create', operation_id=str(uuid.uuid4()), expected_revision=0,
                target_id='P.gpu.operation', question_id='OBJ-gpu-performance', title='GPU测试条件',
                scope='型号与测试负载', acceptance='原厂原件及脚注', provider_id='fetchspec',
                execution_mode='continuous', execution_host='macmini'), 'admin')
            self.assertEqual(supply.read(ROOT)['demands'][-1]['question_id'], 'OBJ-gpu-performance')

    def test_gap_ledger_retains_identity_gaps_and_has_no_raw_paths(self):
        gaps = research_gaps.build(ROOT)
        counts = gaps['counts']
        self.assertEqual(counts['unconnected_parent_targets'], sum(t['team_state'] == 'not_connected' for t in self.targets))
        self.assertEqual(counts['same_cell_retrieval_empty'], sum(not t['request']['candidate_question_ids'] for t in self.targets))
        self.assertEqual(counts['by_kind']['model_input'], sum(self.model['evidence'][k]['status'] not in ('sourced', 'input') for k in self.requests))
        missing = {f['fact_id'] for f in load('data/facts.json')['records'] if not f.get('evidence', {}).get('sha256')}
        self.assertEqual({r['fact_id'] for r in gaps['records'] if r['kind'] == 'original_identity'}, missing)
        self.assertEqual(len({r['id'] for r in gaps['records']}), len(gaps['records']))
        self.assertTrue(all(r['state'] == 'open' for r in gaps['records']))
        for r in gaps['records']:
            self.assertFalse(set(r) & {'original_file', 'source_url', 'quote', 'raw_path', 'sha256'})
        self.assertEqual(counts['reviewed_purpose_empty'], sum(not t['request']['question_ids'] for t in self.targets))

    def test_unknown_and_positive_capacity_presets_never_claim_project_approval(self):
        for preset in [None, *self.model['presets']]:
            a = economics.with_preset(self.model, preset)
            for capacity in (0, 500):
                a['energy_quota_mw'] = capacity
                result = economics.readiness(a, self.model)
                self.assertEqual(result['project_feasibility'], 'not_verified')
                self.assertEqual(result['status'], 'scenario_only')
                self.assertEqual(result['capacity_basis'], 'scenario_limit_not_approval' if capacity else 'unknown_or_unset')
                self.assertEqual(set(result['unverified_inputs']), {k for k in self.requests if self.model['evidence'][k]['status'] not in ('sourced', 'input')})
