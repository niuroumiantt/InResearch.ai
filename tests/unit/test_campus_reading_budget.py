"""No-inference checks for packed reading's measured input and dispatch evidence."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from inresearch.adapters import models, ollama_token_budget as budget
from inresearch.materials import packed_reading as packed


class ReadingBudgetTests(unittest.TestCase):
    def setUp(self):
        self.profile = models.ModelProfile(backend='ollama', url='http://127.0.0.1:11434',
            model='qwen3.8:27b', context=32768, max_output_tokens=4096, max_parallel=1)
        self.client = models.JsonModelClient(self.profile)
        self.system = 'Complete native-source rules'
        self.part = {'stage': 'native_campus_reading', 'reading_recipe': 'campus-packed-reading-v1',
                     'native_fragments': [{'value': 'full native cell value ' * 1800}]}
        self.user = budget.encoded(self.part).decode()
        self.schema = {'type': 'object', 'properties': {'answer': {'type': 'integer'}}}
        self.model = {'manifest_sha256': 'bound', 'model_file': {'path': '/bound.gguf'}}
        self.runner = {'pid': 10, 'starttime': '20', 'port': 12345, 'props_sha256': 'props',
                       'context': 16384}
        self.tokens = [1] * 1000
        self.reply = {'model': budget.MODEL, 'done': True, 'done_reason': 'stop',
                      'message': {'content': '{"answer":42,"_model":{"forged":true}}'}}
        self.calls, self.events = [], []
        def model_identity(_):
            self.events.append('model')
            return copy.deepcopy(self.model)
        for name, options in (
                ('_model_identity', {'side_effect': model_identity}),
                ('_runner_identity', {'return_value': self.runner}),
                ('_call', {'side_effect': self.call})):
            item = patch.object(budget, name, **options)
            item.start(); self.addCleanup(item.stop)

    def call(self, url, body=None, timeout=20):
        self.assertEqual(self.client._slots._value, 0)
        self.calls.append((url, copy.deepcopy(body)))
        if url.endswith('/tokenize'):
            self.events.append('tokenize')
            self.assertEqual(body, {'content': self.system + self.user,
                'add_special': False, 'parse_special': True, 'with_pieces': False})
            return {'tokens': self.tokens}
        if body.get('_debug_render_only'):
            self.events.append('render')
            return {'model': budget.MODEL, 'done': False, 'message': {'content': ''},
                    '_debug_info': {'rendered_template': self.system + self.user}}
        self.events.append('completion')
        return copy.deepcopy(self.reply)

    def generate(self, **kwargs):
        return self.client.generate_campus_reading(self.system, self.user,
                                                   json_schema=self.schema, **kwargs)

    def actual_calls(self):
        return [body for url, body in self.calls
                if url.endswith('/api/chat') and not body.get('_debug_render_only')]

    def test_long_reading_returns_full_bound_request_response_and_single_completion(self):
        with self.assertRaisesRegex(models.InferenceError, 'input_exceeds_context_budget'):
            self.client.generate(self.system, self.user, json_schema=self.schema)
        self.assertEqual(self.calls, [])
        result, evidence = self.generate()
        self.assertEqual(set(evidence), {'request', 'request_sha256', 'token_budget',
                                         'response', 'response_sha256'})
        self.assertEqual(result['answer'], 42)
        self.assertNotIn('forged', result['_model'])
        self.assertEqual(evidence['request_sha256'], budget.digest(evidence['request']))
        self.assertEqual(evidence['response_sha256'], budget.digest(self.reply))
        self.assertEqual(evidence['response'], self.reply)
        proof = evidence['token_budget']
        self.assertEqual(proof['stage'], self.part['stage'])
        self.assertEqual(proof['reading_recipe'], self.part['reading_recipe'])
        self.assertEqual(proof['input_sha256'], hashlib.sha256(self.user.encode()).hexdigest())
        self.assertNotIn('generation_binding', proof)
        self.assertEqual(proof['tokenizer_binding']['context'], 16384)
        actual = self.actual_calls()[0]
        self.assertEqual({k: v for k, v in self.calls[0][1].items()
                          if k != '_debug_render_only'}, actual)
        self.assertEqual(actual, evidence['request'])
        self.assertEqual(actual['messages'], [{'role': 'system', 'content': self.system},
                                              {'role': 'user', 'content': self.user}])
        self.assertEqual(actual['options'], {'num_ctx': 32768, 'num_predict': 4096, 'temperature': 0})
        self.assertFalse(actual['think']); self.assertFalse(actual['shift']); self.assertFalse(actual['truncate'])
        self.assertEqual(len(self.actual_calls()), 1)
        self.assertTrue(result['_model']['token_budget']['generation_binding']['model_verified_before_and_after'])
        evidence['token_budget']['model_binding']['manifest_sha256'] = 'caller mutation'
        self.assertEqual(result['_model']['token_budget']['model_binding']['manifest_sha256'], 'bound')
        self.assertEqual(self.client._slots._value, 1)

    def test_only_measured_overflow_carries_split_evidence_after_stable_tokenizer_check(self):
        self.tokens = [7] * 27649
        gates, dispatches = [], []
        with self.assertRaises(budget.ReadingBudgetExceeded) as error:
            self.generate(before_completion=lambda: gates.append('gate'),
                          before_dispatch=lambda *args: dispatches.append(args))
        self.assertEqual(error.exception.code, 'campus_reading_token_budget_exceeded')
        evidence = error.exception.budget_evidence
        self.assertEqual(set(evidence), {'request', 'request_sha256', 'token_budget'})
        self.assertEqual(evidence['request_sha256'], budget.digest(evidence['request']))
        proof = evidence['token_budget']
        self.assertEqual(proof['input_tokens'], 27649)
        self.assertEqual(proof['token_ids_sha256'], budget.digest(self.tokens))
        self.assertEqual(proof['request_sha256'], evidence['request_sha256'])
        self.assertEqual(proof['model_binding'], self.model)
        self.assertEqual(proof['tokenizer_binding'], self.runner)
        self.assertEqual(proof['context'], 32768)
        self.assertEqual(proof['max_output_tokens'], 4096)
        self.assertEqual(proof['reserve_tokens'], 1024)
        self.assertNotIn('generation_binding', proof)
        self.assertEqual(gates, ['gate']); self.assertEqual(dispatches, [])
        self.assertEqual(self.actual_calls(), [])
        self.assertLess(self.events.index('tokenize'), len(self.events)-1)
        self.assertEqual(self.events[-1], 'model')
        self.assertEqual(self.client._slots._value, 1)

    def test_exact_input_boundary_includes_output_and_reserve(self):
        self.tokens = [2] * 27648
        result, proof = self.generate()
        self.assertEqual(proof['token_budget']['input_tokens'] + 4096 + 1024, 32768)
        self.assertEqual(len(self.actual_calls()), 1)
        self.calls.clear(); self.tokens.append(2)
        with self.assertRaises(budget.ReadingBudgetExceeded):
            self.generate()
        self.assertEqual(self.actual_calls(), [])
        with self.assertRaises(TypeError):
            self.client.generate_campus_reading(self.system, self.user,
                json_schema=self.schema, token_count=1)

    def test_reading_stage_recipe_profile_and_final_entrypoints_remain_separate(self):
        for part in ({'stage': 'whole_campus_adjudication'},
                     {'stage': 'native_campus_reading'},
                     {**self.part, 'reading_recipe': 'unfrozen'}, {'stage': 'reading'}):
            with self.subTest(part=part), self.assertRaisesRegex(models.InferenceError, 'scope_required'):
                self.client.generate_campus_reading(self.system, budget.encoded(part).decode(),
                                                    json_schema=self.schema)
        with self.assertRaisesRegex(models.InferenceError, 'scope_required'):
            self.client.generate_campus_adjudication(self.system, self.user, json_schema=self.schema)
        for changes in ({'url': 'http://remote.example:11434'}, {'model': 'other'},
                        {'context': 65536}, {'max_output_tokens': 8192}, {'max_parallel': 2},
                        {'api_key_env': 'SOME_KEY'}, {'request_model': 'other'}, {'capabilities': ('vision_json',)}):
            with self.subTest(changes=changes), self.assertRaisesRegex(models.InferenceError, 'profile_unverified'):
                models.JsonModelClient(replace(self.profile, **changes)).generate_campus_reading(
                    self.system, self.user, json_schema=self.schema)
        self.assertEqual(self.calls, [])

    def test_gpu_wait_before_render_or_after_measure_never_dispatches_completion(self):
        class ResourceWait(RuntimeError):
            pass
        for stop_at in (1, 2):
            self.calls.clear(); gates, dispatches = [], []
            def gate():
                gates.append(len(gates)+1)
                if len(gates) == stop_at:
                    raise ResourceWait('campus_waiting_for_gpu')
            with self.subTest(stop_at=stop_at), self.assertRaises(ResourceWait):
                self.generate(before_completion=gate, before_dispatch=lambda *a: dispatches.append(a))
            self.assertEqual(len(gates), stop_at)
            self.assertEqual(dispatches, []); self.assertEqual(self.actual_calls(), [])
            self.assertEqual(len(self.calls), 0 if stop_at == 1 else 2)
            self.assertEqual(self.client._slots._value, 1)

    def test_durable_dispatch_follows_final_gpu_model_checks_and_precedes_http(self):
        saved = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'dispatch.json'
            def gate():
                self.events.append('gpu')
            def dispatch(body, proof):
                self.assertEqual(self.events[-1], 'model')
                self.assertEqual(self.events.count('gpu'), 2)
                self.assertEqual(self.actual_calls(), [])
                self.assertEqual(self.client._slots._value, 0)
                saved.append({'request': body, 'request_sha256': budget.digest(body), 'token_budget': proof})
                path.write_bytes(budget.encoded(saved[-1]))
                self.events.append('dispatch')
            original = self.call
            def transport(url, body=None, timeout=20):
                if url.endswith('/api/chat') and not body.get('_debug_render_only'):
                    self.assertTrue(path.exists())
                    self.assertEqual(json.loads(path.read_text())['request'], body)
                    self.assertEqual(self.events[-1], 'dispatch')
                return original(url, body, timeout)
            with patch.object(budget, '_call', side_effect=transport):
                result, evidence = self.generate(before_completion=gate, before_dispatch=dispatch)
        self.assertEqual(saved, [{k: evidence[k] for k in ('request', 'request_sha256', 'token_budget')}])
        self.assertLess(self.events.index('gpu'), self.events.index('render'))
        self.assertLess(self.events.index('dispatch'), self.events.index('completion'))

    def test_dispatch_receives_detached_copies_and_cannot_change_measured_body(self):
        def dispatch(body, proof):
            body['messages'][1]['content'] = 'altered'
            body['format']['properties']['answer']['type'] = 'string'
            proof['input_tokens'] = 1
            proof['model_binding']['manifest_sha256'] = 'forged'
        result, evidence = self.generate(before_dispatch=dispatch)
        self.assertEqual(evidence['request']['messages'][1]['content'], self.user)
        self.assertEqual(evidence['request']['format'], self.schema)
        self.assertEqual(evidence['token_budget']['input_tokens'], 1000)
        self.assertEqual(result['_model']['token_budget']['model_binding'], self.model)

    def test_internal_request_mutation_after_dispatch_callback_is_rejected(self):
        body = budget._body(self.profile, self.system, self.user, self.schema, reading=True)
        proof = {'request_sha256': budget.digest(body), 'model_binding': self.model}
        def dispatch(*_):
            body['messages'][1]['content'] = 'changed original reference'
        with patch.object(budget, '_prepare', return_value=(body, proof)), \
                self.assertRaisesRegex(models.InferenceError, 'request_changed'):
            self.generate(before_dispatch=dispatch)
        self.assertEqual(self.actual_calls(), [])

    def test_failed_dispatch_journal_prevents_completion(self):
        def dispatch(*_):
            raise OSError('disk full')
        with self.assertRaisesRegex(models.InferenceError, 'campus_token_runtime_unverified'):
            self.generate(before_dispatch=dispatch)
        self.assertEqual(self.actual_calls(), [])
        self.assertEqual(self.client._slots._value, 1)

    def test_invalid_count_or_binding_failure_cannot_be_misclassified_as_input_overflow(self):
        for tokens in ([True], ['1'], [], None):
            self.tokens = tokens
            with self.subTest(tokens=tokens), self.assertRaises(models.InferenceError) as error:
                self.generate()
            self.assertNotIsInstance(error.exception, budget.ReadingBudgetExceeded)
            self.assertFalse(hasattr(error.exception, 'budget_evidence'))
        self.tokens = [1] * 27649
        with patch.object(budget, '_runner_identity', side_effect=[self.runner, {**self.runner, 'pid': 99}]), \
                self.assertRaisesRegex(models.InferenceError, 'runner_contention') as error:
            self.generate()
        self.assertNotIsInstance(error.exception, budget.ReadingBudgetExceeded)
        self.assertFalse(hasattr(error.exception, 'budget_evidence'))
        self.assertEqual(self.actual_calls(), [])

    def test_model_change_after_measure_blocks_before_dispatch(self):
        dispatches = []
        with patch.object(budget, '_model_identity', side_effect=[self.model]*3+[{'changed': True}]), \
                self.assertRaisesRegex(models.InferenceError, 'model_binding_changed') as error:
            self.generate(before_dispatch=lambda *a: dispatches.append(a))
        self.assertFalse(hasattr(error.exception, 'budget_evidence'))
        self.assertEqual(dispatches, []); self.assertEqual(self.actual_calls(), [])

    def test_postcompletion_binding_failure_keeps_complete_unaccepted_response(self):
        dispatches = []
        with patch.object(budget, '_model_identity', side_effect=[self.model]*4+[{'changed': True}]), \
                self.assertRaises(budget.CompletionUnverified) as error:
            self.generate(before_dispatch=lambda *a: dispatches.append(a))
        self.assertEqual(error.exception.code, 'campus_token_model_binding_changed')
        evidence = error.exception.completion_evidence
        self.assertEqual(evidence['response'], self.reply)
        self.assertEqual(evidence['response_sha256'], budget.digest(self.reply))
        self.assertEqual(evidence['request'], self.actual_calls()[0])
        self.assertNotIn('generation_binding', evidence['token_budget'])
        self.assertFalse(hasattr(error.exception, 'budget_evidence'))
        self.assertEqual(len(dispatches), 1)
        self.assertEqual(len(self.actual_calls()), 1)

    def test_truncation_and_incomplete_output_are_unverified_not_input_split(self):
        original = copy.deepcopy(self.reply)
        for change, code in (({'done_reason': 'length'}, 'model_output_truncated'),
                             ({'done': False}, 'model_output_incomplete'),
                             ({'remote_host': 'remote'}, 'model_output_incomplete'),
                             ({'model': 'other'}, 'model_identity_unverified'),
                             ({'message': {'content': '{"answer":'}}, 'model_output_invalid')):
            self.reply = {**original, **change}; self.calls.clear()
            with self.subTest(change=change), self.assertRaises(budget.CompletionUnverified) as error:
                self.generate()
            self.assertEqual(error.exception.code, code)
            self.assertEqual(error.exception.completion_evidence['response'], self.reply)
            self.assertFalse(hasattr(error.exception, 'budget_evidence'))
            self.assertEqual(len(self.actual_calls()), 1)

    def test_unknown_completion_transport_preserves_dispatch_without_split_proof(self):
        dispatches = []
        original = self.call
        def transport(url, body=None, timeout=20):
            response = original(url, body, timeout)
            if url.endswith('/api/chat') and not body.get('_debug_render_only'):
                raise TimeoutError('response lost')
            return response
        with patch.object(budget, '_call', side_effect=transport), \
                self.assertRaisesRegex(models.InferenceError, 'campus_token_runtime_unverified') as error:
            self.generate(before_dispatch=lambda *a: dispatches.append(a))
        self.assertFalse(hasattr(error.exception, 'budget_evidence'))
        self.assertEqual(len(dispatches), 1); self.assertEqual(len(self.actual_calls()), 1)

    def test_real_adapter_to_packed_normalizes_nested_uid_tuples_before_consumer_checks(self):
        self.runner['uid_binding'] = {'method': 'system_service_parent_in_user_namespace',
            'uids': (65534, 65534, 65534, 65534),
            'self_uid_map': [(1001, 1001, 1)],
            'runner_process': {'uids': (65534, 65534, 65534, 65534),
                               'uid_map': [(0, 0, 4294967295)]},
            'service_process': {'uids': (65534, 65534, 65534, 65534),
                                'uid_map': [(0, 0, 4294967295)]}}
        self.model['model_file']['stat'] = (1, 2, 3, 4)
        adapter = self.client.generate_campus_reading
        captured = []
        def actual_adapter(*args, **kwargs):
            result, evidence = adapter(*args, **kwargs)
            token_budget = result['_model']['token_budget']
            self.assertEqual(token_budget, json.loads(budget.encoded(token_budget)))
            self.assertEqual(token_budget['tokenizer_binding'], evidence['token_budget']['tokenizer_binding'])
            self.assertEqual(token_budget['model_binding'], evidence['token_budget']['model_binding'])
            captured.append((copy.deepcopy(result), copy.deepcopy(evidence)))
            return result, evidence
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(self.client, 'generate_campus_reading', side_effect=actual_adapter):
            folder = Path(directory)
            result = packed.generate(self.client, self.system, self.part, self.schema, folder, 0, 0, None)
            audit = packed._audit_path(folder, 0, 0, self.part)
            returned = json.loads((audit/'returned.json').read_text())
            self.assertEqual(returned['result'], captured[0][0])
            self.assertEqual(returned['completion'], captured[0][1])
            self.assertEqual(returned['result_sha256'], packed.digest(result))
            self.assertEqual((audit/'response.json').read_bytes(), (audit/'returned.json').read_bytes())
            snapshots = {p: p.read_bytes() for p in audit.iterdir()}
            self.assertEqual(packed.generate(None, self.system, self.part, self.schema, folder, 0, 0, None), result)
            self.assertEqual(snapshots, {p: p.read_bytes() for p in snapshots})
        self.assertEqual(len(self.actual_calls()), 1)
        self.assertIsInstance(self.runner['uid_binding']['uids'], tuple)

    def test_real_adapter_returned_journal_recovers_without_render_tokenize_or_completion(self):
        self.runner['uid_binding'] = {'uids': (996, 996, 996, 996),
                                      'nested': {'uid_map': [(0, 0, 4294967295)]}}
        atomic = packed.atomic
        def fail_response(path, value):
            if path.name == 'response.json':
                raise OSError('interrupted before response promotion')
            return atomic(path, value)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with patch.object(packed, 'atomic', side_effect=fail_response), self.assertRaises(OSError):
                packed.generate(self.client, self.system, self.part, self.schema, folder, 0, 0, None)
            audit = packed._audit_path(folder, 0, 0, self.part)
            before = (audit/'returned.json').read_bytes()
            calls = copy.deepcopy(self.calls)
            with patch.object(budget, '_call', side_effect=AssertionError('repeated model operation')):
                result = packed.generate(None, self.system, self.part, self.schema, folder, 0, 0, None)
            self.assertEqual(result['answer'], 42)
            self.assertEqual(before, (audit/'returned.json').read_bytes())
            self.assertEqual(json.loads((audit/'response.json').read_text())['result'], result)
            self.assertEqual(self.calls, calls)
        self.assertEqual(len(self.actual_calls()), 1)
