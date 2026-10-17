"""Packed-window compatibility, lossless budget splits, and no unknown replay."""
import copy
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from inresearch.adapters import models, ollama_token_budget as budget
from inresearch.materials import full_review_worker as worker, packed_reading as packed, review_worker
from tests.unit import test_full_review_worker as legacy_tests
from tests.unit.test_full_review_worker import FakeClient, native


def receipt(system, part, schema, tokens=1000):
    body = {'model': 'qwen3.8:27b', 'messages': [{'role': 'system', 'content': system},
        {'role': 'user', 'content': packed.encoded(part).decode()}],
        'format': copy.deepcopy(schema), 'options': {'num_ctx': 32768, 'num_predict': 4096},
        'truncate': False, 'shift': False, 'think': False, 'stream': False}
    proof = {'version': 'ollama-campus-token-v2', 'stage': packed.STAGE, 'reading_recipe': packed.VERSION,
        'truncate': False, 'shift': False, 'think': False, 'request_sha256': packed.digest(body), 'schema_sha256': packed.digest(schema),
        'system_sha256': hashlib.sha256(system.encode()).hexdigest(), 'input_sha256': packed.digest(part),
        'context': 32768, 'max_output_tokens': 4096, 'reserve_tokens': 1024, 'input_tokens': tokens,
        'model_binding': {'manifest': 'fixture'}, 'tokenizer_binding': {'pid': 123}}
    return body, proof


class PackedClient(FakeClient):
    def __init__(self, *, limit=64, outcome='success'):
        super().__init__()
        self.limit = limit
        self.outcome = outcome
        self.measurements = []
        self.dispatches = []

    def generate_campus_reading(self, system, user, *, json_schema, before_completion, before_dispatch):
        if before_completion:
            before_completion()
        part = json.loads(user)
        self.measurements.append(part)
        body, proof = receipt(system, part, json_schema,
                              27649 if len(part['native_fragments']) > self.limit else 1000)
        if len(part['native_fragments']) > self.limit:
            raise budget.ReadingBudgetExceeded(body, proof)
        if before_completion:
            before_completion()
        before_dispatch(copy.deepcopy(body), copy.deepcopy(proof))
        self.dispatches.append(copy.deepcopy(body))
        if self.outcome == 'transport':
            raise models.InferenceError('campus_token_runtime_unverified')
        result = super().generate(system, user, json_schema=json_schema)
        if self.outcome == 'invalid':
            result['findings'] = [{'sheet': 'invented', 'cell': 'Z999', 'priority': 'P0',
                                  'issue': 'i', 'action': 'a', 'acceptance': 'a'}]
        response = {'model': 'qwen3.8:27b', 'done': True, 'done_reason': 'stop',
                    'message': {'content': packed.encoded({k:v for k,v in result.items()
                                                          if k != '_model'}).decode()}}
        if self.outcome == 'truncated':
            response['done_reason'] = 'length'
            response['message']['content'] = '{"summary":"incomplete'
            raise budget.CompletionUnverified(models.InferenceError('model_output_truncated'),
                                              body, proof, response)
        evidence = {'request': body, 'request_sha256': packed.digest(body), 'token_budget': proof,
                    'response': response, 'response_sha256': packed.digest(response)}
        result['_model']['token_budget'] = {**proof, 'generation_binding': {
            'model_binding_sha256': packed.digest(proof['model_binding']),
            'request_sha256': packed.digest(body), 'actual_model': response['model'],
            'model_verified_before_and_after': True, 'response_sha256': packed.digest(response)}}
        return result, evidence


class PackedReadingTests(unittest.TestCase):
    def setUp(self):
        legacy_tests.FullReviewWorkerTests.setUp(self)
        self.legacy_recipe.stop()

    def run_folder(self):
        return next((self.folder/'full-review').rglob('plan.json')).parent

    def call(self, client, **kwargs):
        return worker.proposal(self.item, self.original, self.folder, client, **kwargs)

    def test_only_untouched_packages_get_64_fragment_recipe(self):
        client = PackedClient()
        self.call(client)
        part = client.measurements[0]
        self.assertEqual(len(part['native_fragments']), 64)
        self.assertEqual(part['reading_recipe'], packed.VERSION)
        plan = json.loads((self.run_folder()/'plan.json').read_text())
        self.assertEqual([len(p['native_fragments']) for p in plan['parts']], [64, 3])
        marker = self.run_folder().parent/'reading-recipe.json'
        before = marker.read_bytes()
        self.call(client)
        self.assertEqual(marker.read_bytes(), before)
        self.assertEqual(len(client.dispatches), 2)
        self.assertEqual(len(client.calls), 2)

    def test_any_prior_task_checkpoint_keeps_legacy_across_task_revision(self):
        for filename in ('plan.json', 'progress.json', 'chunk-00000.json', 'proposal.json'):
            with self.subTest(filename=filename):
                folder = self.folder/filename.replace('.', '-')
                old = folder/'full-review'/self.item['full_analysis']['attempt_id']/self.packet['package_id']/('f'*64)
                old.mkdir(parents=True)
                (old/filename).write_bytes(b'original old task artifact')
                client = FakeClient()
                worker.proposal(self.item, self.original, folder, client)
                self.assertEqual(len(client.calls[0]['native_fragments']), 32)
                self.assertNotIn('stage', client.calls[0])
                self.assertEqual((old/filename).read_bytes(), b'original old task artifact')
                self.assertFalse((old.parent/'reading-recipe.json').exists())

    def test_prepared_proposal_replays_without_new_recipe_or_inference(self):
        client = PackedClient()
        self.call(client); self.call(client)
        result = self.call(client)
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run_folder().rglob('*') if p.is_file()}
        with patch.object(client, 'generate_campus_reading', side_effect=AssertionError('new inference')):
            self.assertEqual(self.call(client), result)
        self.assertEqual(hashes, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in hashes})

    def test_complete_fragments_order_and_shared_context_are_preserved(self):
        self.cells[30]['value'] = '长原格🙂'*2000
        headers = [native('A1000', 'native column header')]
        self.packet['header_cells'] = headers
        old = worker.chunks(self.packet, self.task, [], FakeClient().profile)
        new = worker.chunks(self.packet, self.task, [], FakeClient().profile, packed=True)
        self.assertEqual([f for p in old for f in p['native_fragments']],
                         [f for p in new for f in p['native_fragments']])
        old_base = {k:v for k,v in old[0].items() if k != 'native_fragments'}
        for part in new:
            self.assertEqual({k:v for k,v in part.items()
                              if k not in ('native_fragments','stage','reading_recipe')}, old_base)
        value = ''.join(f['value'] for p in new for f in p['native_fragments'] if f['cell'] == 'A31')
        self.assertEqual(value, self.cells[30]['value'])

    def test_existing_successful_legacy_window_is_reused_after_upgrade(self):
        client = FakeClient()
        with patch.object(packed, 'select_recipe', return_value=packed.LEGACY):
            self.call(client)
        folder = self.run_folder()
        old = (folder/'chunk-00000.json').read_bytes()
        self.call(client)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual([len(p['native_fragments']) for p in client.calls], [32,32])
        self.assertEqual((folder/'chunk-00000.json').read_bytes(), old)
        self.assertFalse((folder.parent/'reading-recipe.json').exists())

    def test_new_windows_delegate_long_full_inputs_to_exact_token_guard(self):
        for cell in self.cells:
            cell['value'] = '原生中文'*100
        client = PackedClient()
        self.call(client)
        self.assertGreater(len(worker.encoded(client.measurements[0])), 27648)
        self.assertEqual(len(client.measurements[0]['native_fragments']), 64)
        self.assertEqual(len(client.dispatches), 1)
        self.assertEqual(client.dispatches[0]['messages'][1]['content'],
                         worker.encoded(client.measurements[0]).decode())

    def test_exact_input_overflow_bisects_before_generation_then_resumes_losslessly(self):
        client = PackedClient(limit=20)
        self.call(client)
        folder = self.run_folder()
        self.assertEqual(client.dispatches, [])
        plan = json.loads((folder/'plan.json').read_text())
        self.assertEqual([len(p['native_fragments']) for p in plan['parts']], [32,32,3])
        self.assertEqual(json.loads((folder/'progress.json').read_text())['next'], 0)
        for _ in range(30):
            value = self.call(client)
            if value is not None: break
        self.assertIsNotNone(value)
        delivered = [f for p in client.calls if p.get('stage') == packed.STAGE for f in p['native_fragments']]
        self.assertEqual(delivered, [f for p in worker.chunks(self.packet, self.task, [], client.profile, packed=True)
                          for f in p['native_fragments']])
        self.assertEqual(len(client.dispatches), 5)
        self.assertEqual(len(list((folder/'input-budget-checks').glob('*.json'))), 3)

    def test_single_fragment_and_task_context_overflow_stays_blocked(self):
        self.packet['cells'] = self.cells[:1]
        client = PackedClient(limit=0)
        with self.assertRaisesRegex(models.InferenceError, 'campus_reading_token_budget_exceeded'):
            self.call(client)
        self.assertEqual(client.dispatches, [])
        self.assertEqual(json.loads((self.run_folder()/'progress.json').read_text())['next'], 0)
        self.assertEqual(len(list((self.run_folder()/'input-budget-checks').glob('*.json'))), 1)

    def test_split_proof_and_repartition_tampering_are_rejected(self):
        client = PackedClient(limit=20)
        self.call(client)
        folder = self.run_folder(); path = folder/'plan.json'
        original = path.read_text(); plan = json.loads(original)
        plan['parts'] = [plan['parts'][1], plan['parts'][0], plan['parts'][2]]
        path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, 'campus_plan_coverage_changed'):
            self.call(client)
        path.write_text(original)
        proof_path = next((folder/'input-budget-checks').glob('*.json'))
        proof = json.loads(proof_path.read_text()); proof['token_budget']['input_tokens'] = 10
        proof_path.write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError, 'campus_reading_split_changed'):
            self.call(client)
        self.assertEqual(client.dispatches, [])

    def test_returned_response_recovers_cursor_failure_without_new_generation(self):
        client = PackedClient()
        real_atomic = worker.atomic
        def fail_chunk(path, value):
            if path.name == 'chunk-00000.json': raise OSError('simulated process failure')
            return real_atomic(path, value)
        with patch.object(worker, 'atomic', side_effect=fail_chunk):
            with self.assertRaises(OSError): self.call(client)
        self.assertEqual(len(client.dispatches), 1)
        self.call(client)
        self.assertEqual(len(client.dispatches), 1)
        self.assertEqual(json.loads((self.run_folder()/'progress.json').read_text())['next'], 1)

    def test_unknown_transport_and_truncated_response_never_replay_after_status_loss(self):
        for outcome in ('transport', 'truncated'):
            with self.subTest(outcome=outcome):
                folder = self.folder/outcome
                client = PackedClient(outcome=outcome)
                with self.assertRaises(models.InferenceError):
                    worker.proposal(self.item, self.original, folder, client)
                audit = next((folder/'full-review').rglob('dispatch.json'))
                before = audit.read_bytes()
                for _ in range(2):
                    with self.assertRaisesRegex(models.InferenceError, 'campus_reading_completion_outcome_unverified'):
                        worker.proposal(self.item, self.original, folder, client)
                self.assertEqual(len(client.dispatches), 1)
                self.assertEqual(audit.read_bytes(), before)
                self.assertFalse((audit.parent/'returned.json').exists())
                self.assertFalse((audit.parent/'response.json').exists())
                if outcome == 'truncated':
                    unverified = audit.parent/'unverified.json'
                    saved = json.loads(unverified.read_text())
                    self.assertEqual(saved['completion']['response']['message']['content'], '{"summary":"incomplete')
                plan = json.loads(next((folder/'full-review').rglob('plan.json')).read_text())
                self.assertEqual(plan['splits'], [])

    def test_invalid_semantic_response_has_three_durable_attempts_and_no_reread(self):
        client = PackedClient(outcome='invalid')
        for n in range(3):
            with self.assertRaises(worker.RejectedWindow): self.call(client)
        with self.assertRaises(worker.RejectedWindow): self.call(client)
        self.assertEqual(len(client.dispatches), 3)
        folder = self.run_folder()
        self.assertEqual(len(list((folder/'reading-audits').rglob('response.json'))), 3)
        self.assertEqual(len(list((folder/'rejected-responses').rglob('response-*.json'))), 3)

    def test_gpu_gate_blocks_before_render_and_again_before_dispatch(self):
        client = PackedClient()
        def busy(): raise worker.YieldWork('busy')
        with self.assertRaises(worker.YieldWork): self.call(client, before_generate=busy)
        self.assertEqual(client.measurements, [])
        calls = []
        def becomes_busy():
            calls.append(1)
            if len(calls) == 2: raise worker.YieldWork('busy after tokenize')
        with self.assertRaises(worker.YieldWork): self.call(client, before_generate=becomes_busy)
        self.assertEqual(len(client.measurements), 1)
        self.assertEqual(client.dispatches, [])
        self.assertEqual(list(self.run_folder().rglob('dispatch.json')), [])

    def test_completed_audit_mutation_is_rejected_before_more_inference(self):
        client = PackedClient()
        self.call(client); self.call(client)
        before = len(client.calls)
        response_path = next(self.run_folder().rglob('response.json'))
        saved = json.loads(response_path.read_text()); saved['completion']['response']['message']['content'] = '{}'
        response_path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, 'campus_reading_audit_changed'):
            self.call(client)
        self.assertEqual(len(client.calls), before)

    def test_one_receive_cycle_generates_one_window_and_never_completes_early(self):
        archive = self.folder/'archive'
        folder = archive/self.item['id']; folder.mkdir(parents=True)
        (folder/'original').write_bytes(self.original.read_bytes())
        (folder/'receipt.json').write_text(json.dumps(self.item))
        client = PackedClient()
        with patch.object(worker, 'client', return_value=client), \
                patch.object(worker, 'resource_ready', return_value=(True, '')):
            self.assertEqual(worker.run_item(self.item, archive, lambda *a, **k: io.BytesIO(b'{"ok":true}')), (0, True))
        self.assertEqual(len(client.dispatches), 1)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(list(folder.rglob('proposal.json')), [])

    def test_new_truncation_marks_operator_and_status_loss_does_not_replay(self):
        archive = self.folder/'archive'
        folder = archive/self.item['id']; folder.mkdir(parents=True)
        (folder/'original').write_bytes(self.original.read_bytes())
        (folder/'receipt.json').write_text(json.dumps(self.item))
        client = PackedClient(outcome='truncated')
        with patch.object(worker, 'client', return_value=client), \
                patch.object(worker, 'resource_ready', return_value=(True, '')):
            self.assertEqual(worker.run_item(self.item, archive, lambda *a, **k: io.BytesIO(b'{"ok":true}')), (0, True))
            status = folder/'full-review'/self.item['full_analysis']['attempt_id']/'status.json'
            self.assertTrue(json.loads(status.read_text())['operator_required'])
            self.assertEqual(json.loads(status.read_text())['reason'], 'model_output_truncated')
            status.unlink()
            self.assertEqual(worker.run_item(self.item, archive, lambda *a, **k: io.BytesIO(b'{"ok":true}')), (0, False))
            self.assertTrue(json.loads(status.read_text())['operator_required'])
        self.assertEqual(len(client.dispatches), 1)

    def test_recipe_marker_cannot_change_source_or_package(self):
        client = PackedClient(); self.call(client)
        marker = self.run_folder().parent/'reading-recipe.json'
        value = json.loads(marker.read_text()); value['source_sha256'] = 'f'*64
        marker.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'campus_reading_recipe_changed'):
            self.call(client)
        self.assertEqual(len(client.dispatches), 1)

    def test_returned_journal_precedes_consumer_checks_and_recovers_without_new_call(self):
        client = PackedClient()
        def interrupted(result, evidence):
            returned_path = next(self.run_folder().rglob('returned.json'))
            saved = json.loads(returned_path.read_text())
            self.assertEqual(saved['result'], result)
            self.assertEqual(saved['completion'], evidence)
            self.assertEqual(saved['result_sha256'], packed.digest(result))
            self.assertEqual(saved['completion_sha256'], packed.digest(evidence))
            self.assertEqual(list(self.run_folder().rglob('response.json')), [])
            raise OSError('interrupted consumer validation')
        with patch.object(packed, '_bound_result', side_effect=interrupted), self.assertRaises(OSError):
            self.call(client)
        returned_path = next(self.run_folder().rglob('returned.json'))
        before = returned_path.read_bytes()
        with patch.object(client, 'generate_campus_reading', side_effect=AssertionError('new generation')):
            self.call(client)
        self.assertEqual(returned_path.read_bytes(), before)
        self.assertEqual(len(client.dispatches), 1)
        self.assertEqual(len(client.measurements), 1)
        self.assertEqual(json.loads((self.run_folder()/'progress.json').read_text())['next'], 1)

    def test_bad_adapter_return_is_saved_before_binding_rejection_and_never_replayed(self):
        client = PackedClient()
        adapter = client.generate_campus_reading
        def invalid(*args, **kwargs):
            result, evidence = adapter(*args, **kwargs)
            result['_model']['token_budget']['tokenizer_binding'] = {'changed_after_generation': True}
            return result, evidence
        with patch.object(client, 'generate_campus_reading', side_effect=invalid), \
                self.assertRaisesRegex(ValueError, 'campus_reading_audit_changed'):
            self.call(client)
        returned_path = next(self.run_folder().rglob('returned.json'))
        saved = json.loads(returned_path.read_text())
        self.assertEqual(saved['result']['_model']['token_budget']['tokenizer_binding'],
                         {'changed_after_generation': True})
        self.assertEqual(saved['completion']['response']['done_reason'], 'stop')
        self.assertEqual(saved['completion_sha256'], packed.digest(saved['completion']))
        before = returned_path.read_bytes()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'campus_reading_audit_changed'):
                self.call(client)
        self.assertEqual(returned_path.read_bytes(), before)
        self.assertEqual(len(client.dispatches), 1)
        self.assertEqual(list(self.run_folder().rglob('response.json')), [])
        self.assertEqual(list(self.run_folder().glob('chunk-*.json')), [])

    def test_returned_journal_tampering_cannot_promote_or_replay_even_with_new_hashes(self):
        for mutation in ('result_hash', 'bound_result', 'bound_request', 'dispatch'):
            with self.subTest(mutation=mutation):
                folder = self.folder/mutation
                client = PackedClient()
                with patch.object(packed, '_bound_result', side_effect=OSError('interrupted')), \
                        self.assertRaises(OSError):
                    worker.proposal(self.item, self.original, folder, client)
                returned_path = next(folder.rglob('returned.json'))
                saved = json.loads(returned_path.read_text())
                if mutation == 'result_hash':
                    saved['result_sha256'] = '0'*64
                elif mutation == 'bound_result':
                    saved['result']['_model']['input_sha256'] = '0'*64
                    saved['result_sha256'] = packed.digest(saved['result'])
                elif mutation == 'bound_request':
                    saved['completion']['request']['messages'][1]['content'] = 'replaced input'
                    saved['completion_sha256'] = packed.digest(saved['completion'])
                else:
                    dispatch = returned_path.parent/'dispatch.json'
                    value = json.loads(dispatch.read_text())
                    value['token_budget']['tokenizer_binding']['pid'] = 987
                    dispatch.write_text(json.dumps(value))
                returned_path.write_text(json.dumps(saved))
                before = {p: p.read_bytes() for p in returned_path.parent.iterdir()}
                with patch.object(client, 'generate_campus_reading', side_effect=AssertionError('new generation')), \
                        self.assertRaisesRegex(ValueError, 'campus_reading_audit_changed'):
                    worker.proposal(self.item, self.original, folder, client)
                self.assertEqual(before, {p: p.read_bytes() for p in before})
                self.assertFalse((returned_path.parent/'response.json').exists())
                self.assertEqual(len(client.dispatches), 1)

    def test_existing_response_without_returned_journal_stays_byte_identical(self):
        client = PackedClient()
        self.call(client)
        folder = self.run_folder()
        returned_path = next(folder.rglob('returned.json'))
        returned_path.unlink()  # Receipt written by the previously deployed helper.
        response_path = returned_path.parent/'response.json'
        before = response_path.read_bytes()
        plan = json.loads((folder/'plan.json').read_text())
        part = plan['parts'][0]
        result = json.loads(response_path.read_text())['result']
        packed.verify_cached(result, review_worker.SYSTEM, part, worker.reading_schema(part), folder, 0, 0)
        self.assertEqual(response_path.read_bytes(), before)
        self.assertFalse(returned_path.exists())
        self.assertEqual(len(client.dispatches), 1)

    def test_returned_journal_must_agree_with_existing_response_and_unverified_state(self):
        client = PackedClient()
        self.call(client)
        folder = self.run_folder()
        returned_path = next(folder.rglob('returned.json'))
        response_path = returned_path.parent/'response.json'
        response = response_path.read_bytes()
        original = returned_path.read_bytes()
        saved = json.loads(original)
        saved['result']['summary'] = 'different return'
        saved['result_sha256'] = packed.digest(saved['result'])
        returned_path.write_text(json.dumps(saved))
        part = json.loads((folder/'plan.json').read_text())['parts'][0]
        with self.assertRaisesRegex(ValueError, 'campus_reading_audit_changed'):
            packed.generate(None, review_worker.SYSTEM, part, worker.reading_schema(part), folder, 0, 0, None)
        self.assertEqual(response_path.read_bytes(), response)
        returned_path.write_bytes(original)
        response_path.unlink()
        (returned_path.parent/'unverified.json').write_text('{}')
        with self.assertRaisesRegex(models.InferenceError, 'campus_reading_completion_outcome_unverified'):
            packed.generate(None, review_worker.SYSTEM, part, worker.reading_schema(part), folder, 0, 0, None)
        self.assertFalse(response_path.exists())
        self.assertEqual(returned_path.read_bytes(), original)
        self.assertEqual(len(client.dispatches), 1)
