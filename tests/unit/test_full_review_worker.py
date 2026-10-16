"""Complete model input coverage, durable resume, and isolation from other jobs."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from inresearch.adapters import models
from inresearch.materials import full_review_worker as worker
from inresearch.materials import review_worker
from tests.unit.test_xlsx_document import workbook_bytes


def native(address, value):
    return {'sheet': '园区', 'cell': address,
            'locator': f'xlsx:sheet:1:cell:{address}:context:{address}:{address}',
            'value': value, 'formula': None}


class FakeClient:
    def __init__(self, truncate=False):
        self.profile = models.ModelProfile(backend='ollama', url='http://127.0.0.1:11434',
            model='qwen3.8:27b', context=32768, max_output_tokens=4096, max_parallel=1)
        self.calls = []
        self.truncate = truncate

    def generate(self, system, user, **kwargs):
        self.calls.append(json.loads(user))
        if self.truncate:
            self.truncate = False
            raise models.InferenceError('model_output_truncated')
        output = ({'accept_candidates': list(range(len(self.calls[-1]['candidates'])))}
                  if self.calls[-1].get('stage') == 'whole_campus_adjudication' else {'candidates': []})
        return {'summary': '已读本次全部原生片段。', 'findings': [], **output,
                '_model': {**self.profile.identity, 'requested': 'qwen3.8:27b',
                           'actual': 'qwen3.8:27b',
                           'prompt_sha256': hashlib.sha256(system.encode()).hexdigest(),
                           'input_sha256': hashlib.sha256(user.encode()).hexdigest()}}


class FullReviewWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.original = self.folder/'source.xlsx'
        self.original.write_bytes(workbook_bytes())
        self.sha = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.task = {'task_revision': 1, 'mission_goal': '完整核对园区身份及来源',
                     'package': {'id': 'dc-census-cn'}}
        self.cells = [native(f'A{n}', '材料'+str(n)) for n in range(1, 68)]
        self.packet = {'package_id': 'a'*64, 'kind': 'campus', 'campus_key': 'one',
                       'campus_name': '园区甲', 'cells': self.cells,
                       'identity_cells': self.cells[:1]}
        self.manifest = {'manifest_sha256': 'b'*64, 'packets': [self.packet]}
        self.item = {'id': '1'*32, 'sha256': self.sha, 'name': 'source.xlsx',
                     'assigned_task': self.task, 'known_sites': [],
                     'full_analysis': {'attempt_id': '3'*36, 'layout_id': 'fixture',
                        'manifest_sha256': 'b'*64, 'package_ids': ['a'*64],
                        'available_package_ids': ['a'*64], 'completed_package_ids': []}}
        approved = patch.object(worker, 'require_approved')
        approved.start(); self.addCleanup(approved.stop)
        manifest = patch.object(worker.contract, 'build_manifest', return_value=self.manifest)
        manifest.start(); self.addCleanup(manifest.stop)
        scope = patch.object(worker.contract, 'make_scope', return_value={'package_id': 'a'*64})
        scope.start(); self.addCleanup(scope.stop)
        identity = patch.object(worker.contract, 'analysis_id', return_value='4'*36)
        identity.start(); self.addCleanup(identity.stop)

    def test_long_unicode_cell_reassembles_without_truncation(self):
        text = ('原文甲𠮷🙂乙\n'*1300)+'最后一字'
        parts = worker.fragments([native('A1', text)])
        self.assertGreater(len(parts), 1)
        self.assertEqual(''.join(p['value'] for p in parts), text)
        self.assertEqual(parts[0]['start'], 0)
        self.assertEqual(parts[-1]['end'], len(text))
        for part in parts:
            self.assertEqual(part['value'], text[part['start']:part['end']])
            self.assertEqual(part['value_sha256'], hashlib.sha256(part['value'].encode()).hexdigest())

    def test_every_cell_reaches_model_and_no_payload_before_completion(self):
        client = FakeClient()
        self.assertIsNone(worker.proposal(self.item, self.original, self.folder, client))
        self.assertIsNone(worker.proposal(self.item, self.original, self.folder, client))
        self.assertIsNone(worker.proposal(self.item, self.original, self.folder, client))
        payload = worker.proposal(self.item, self.original, self.folder, client)
        self.assertIsNotNone(payload)
        observed = [f['locator'] for call in client.calls for f in call.get('native_fragments', [])]
        self.assertEqual(observed, [c['locator'] for c in self.cells])
        self.assertEqual(len(payload['review_windows']), 3)
        self.assertTrue(all(call['identity_context'] == self.cells[:1] for call in client.calls[:-1]))
        self.assertEqual(client.calls[-1]['stage'], 'whole_campus_adjudication')

    def test_successful_calls_and_final_payload_replay_without_inference(self):
        client = FakeClient()
        for _ in range(4):
            payload = worker.proposal(self.item, self.original, self.folder, client)
        replay = worker.proposal(self.item, self.original, self.folder, client)
        self.assertEqual(replay, payload)
        self.assertEqual(len(client.calls), 4)

    def test_output_limit_splits_only_unfinished_window_without_losing_cells(self):
        client = FakeClient(truncate=True)
        self.assertIsNone(worker.proposal(self.item, self.original, self.folder, client))
        payload = None
        for _ in range(5):
            payload = worker.proposal(self.item, self.original, self.folder, client)
        self.assertIsNotNone(payload)
        observed = [f['locator'] for call in client.calls[1:] for f in call.get('native_fragments', [])]
        self.assertEqual(observed, [c['locator'] for c in self.cells])
        self.assertEqual(len(payload['review_windows']), 4)

    def test_changed_approved_original_rejected_before_inference(self):
        client = FakeClient()
        self.original.write_bytes(self.original.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError, 'source_sha_changed'):
            worker.proposal(self.item, self.original, self.folder, client)
        self.assertEqual(client.calls, [])

    def test_frozen_model_change_cannot_mix_existing_chunks(self):
        client = FakeClient()
        worker.proposal(self.item, self.original, self.folder, client)
        changed = FakeClient()
        changed.profile = models.ModelProfile(backend='ollama', url='http://127.0.0.1:11434',
            model='qwen3.8:27b', context=32768, max_output_tokens=2048, max_parallel=1)
        with self.assertRaisesRegex(ValueError, 'recipe_changed'):
            worker.proposal(self.item, self.original, self.folder, changed)
        self.assertEqual(changed.calls, [])

    def test_completed_chunk_tampering_is_not_reused(self):
        client = FakeClient()
        worker.proposal(self.item, self.original, self.folder, client)
        path = next(self.folder.rglob('chunk-00000.json'))
        raw = json.loads(path.read_text()); raw['input_sha256'] = '0'*64
        path.write_text(json.dumps(raw))
        worker.proposal(self.item, self.original, self.folder, client)
        worker.proposal(self.item, self.original, self.folder, client)
        with self.assertRaisesRegex(ValueError, 'completed_chunk_changed'):
            worker.proposal(self.item, self.original, self.folder, client)

    def test_invented_findings_and_partial_value_candidates_rejected(self):
        cell = native('A1', '原文')
        part = {'native_fragments': worker.fragments([cell]), 'identity_context': []}
        result = FakeClient().generate('规则', '{}')
        result['findings'] = [{'sheet': '园区', 'cell': 'Z99', 'priority': 'P0',
                               'issue': '缺', 'action': '找', 'acceptance': '原文'}]
        with self.assertRaisesRegex(ValueError, 'finding_outside'):
            worker.validate_result(result, part, 'campus')
        result['findings'] = []
        result['candidates'] = [{'name_locator': cell['locator'], 'location_locator': cell['locator'],
                                 'locator': cell['locator'], 'unit_locator': ''}]
        part['native_fragments'][0]['start'] = 1
        with self.assertRaisesRegex(ValueError, 'candidate_outside'):
            worker.validate_result(result, part, 'campus')

    def test_pilot_release_does_not_read_other_packets(self):
        client = FakeClient()
        self.item['full_analysis']['available_package_ids'] = []
        self.assertIsNone(worker.proposal(self.item, self.original, self.folder, client))
        self.assertEqual(client.calls, [])

    def test_gpu_busy_hot_and_unknown_yield_only_this_worker(self):
        class Result:
            stdout = '64, 75\n'
        with patch.object(worker.subprocess, 'run', return_value=Result()):
            self.assertEqual(worker.resource_ready(), (False, 'campus_waiting_for_gpu'))
            Result.stdout = '81, 0\n'
            self.assertEqual(worker.resource_ready(), (False, 'campus_waiting_for_temperature'))
        with patch.object(worker.subprocess, 'run', side_effect=OSError):
            self.assertEqual(worker.resource_ready(), (False, 'campus_gpu_status_unavailable'))

    def test_empty_value_with_long_formula_is_preserved(self):
        cell = native('A1', None)
        cell['formula'] = '<f>SUM('+','.join(['B1']*1400)+')</f>'
        parts = worker.fragments([cell])
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]['formula'], cell['formula'])
        self.assertEqual(parts[0]['value'], '')

    def test_later_window_retains_native_column_headers(self):
        self.packet['header_cells'] = [native('A100', '年实际用电量（kWh）')]
        parts = worker.chunks(self.packet, self.task, [], FakeClient().profile)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(f['column_headers'] == self.packet['header_cells']
                            for f in parts[1]['native_fragments']))

    def test_repeated_header_can_supply_unit_but_not_candidate_value(self):
        cell, header = native('A2', '10'), native('A1', 'MW')
        part = {'native_fragments': [{**worker.fragments([cell])[0], 'column_headers': [header]}],
                'identity_context': []}
        result = FakeClient().generate('规则', '{}')
        result['candidates'] = [{'name_locator': cell['locator'], 'location_locator': cell['locator'],
                                 'locator': cell['locator'], 'unit_locator': header['locator']}]
        worker.validate_result(result, part, 'campus')
        result['candidates'][0]['locator'] = header['locator']
        with self.assertRaisesRegex(ValueError, 'candidate_outside'):
            worker.validate_result(result, part, 'campus')

    def test_whole_campus_adjudication_can_reject_earlier_candidates(self):
        client = FakeClient()
        def decide(system, user, **kwargs):
            self.assertEqual(json.loads(user)['window_summaries'], ['前窗候选', '后窗发现冲突'])
            return {'summary': '冲突未解，保留补证任务', 'findings': [], 'accept_candidates': [],
                    '_model': {**client.profile.identity, 'actual': 'qwen3.8:27b',
                               'input_sha256': hashlib.sha256(user.encode()).hexdigest()}}
        client.generate = decide
        result = worker.adjudicate(self.packet, self.task, [],
            [{'summary': '前窗候选'}, {'summary': '后窗发现冲突'}], [],
            [{'locator': self.cells[0]['locator']}], client, self.folder, None)
        self.assertEqual(result['accept_candidates'], [])
        client.generate = lambda *a, **k: self.fail('durable final adjudication was rerun')
        self.assertEqual(worker.adjudicate(self.packet, self.task, [],
            [{'summary': '前窗候选'}, {'summary': '后窗发现冲突'}], [],
            [{'locator': self.cells[0]['locator']}], client, self.folder, None), result)

    def test_rejected_delivery_blocks_only_this_attempt_and_keeps_cache(self):
        folder = self.folder/self.item['id']; folder.mkdir()
        (folder/'original').write_bytes(self.original.read_bytes())
        payload = {'review_scope': {'package_id': 'a'*64}, 'analysis_id': '4'*36}
        error = HTTPError('https://example.invalid', 400, 'invalid', {},
                          io.BytesIO(b'{"error":"native_review_scope_mismatch"}'))
        with patch.object(worker, 'proposal', return_value=payload), \
                patch.object(worker, 'deliver', side_effect=error):
            self.assertEqual(worker.run_item(self.item, self.folder, lambda *a: None), (0, False))
        status = json.loads(next(folder.rglob('status.json')).read_text())
        self.assertTrue(status['operator_required'])
        self.assertEqual(status['reason'], 'campus_delivery_http_400')

    def test_continuing_job_never_falls_back_to_old_sampled_path(self):
        item = {**self.item, 'full_analysis': {**self.item['full_analysis'], 'state': 'continuing'}}
        def request(path, payload=None):
            self.assertEqual(path, 'analysis-pending')
            return io.StringIO(json.dumps({'items': [item]}))
        with patch.object(review_worker, 'require_approved'), \
                patch.object(worker, 'run_item', return_value=(1, True)) as full, \
                patch.object(review_worker, 'proposal', side_effect=AssertionError('sampled path')):
            self.assertEqual(review_worker.run(self.folder, request), 1)
        full.assert_called_once()

    def test_blocked_full_job_does_not_starve_next_attempt(self):
        a = {**self.item, 'full_analysis': {**self.item['full_analysis'], 'state': 'running'}}
        b = {**a, 'id': '2'*32}
        def request(path, payload=None):
            return io.StringIO(json.dumps({'items': [a, b]}))
        with patch.object(review_worker, 'require_approved'), \
                patch.object(worker, 'run_item', side_effect=[(0, False), (1, True)]) as full:
            self.assertEqual(review_worker.run(self.folder, request), 1)
        self.assertEqual(full.call_count, 2)

    def test_ollama_transport_failure_retries_with_finite_budget(self):
        archive = self.folder/'archive'; folder = archive/self.item['id']
        folder.mkdir(parents=True); (folder/'original').write_bytes(self.original.read_bytes())
        status = folder/'full-review'/self.item['full_analysis']['attempt_id']/'status.json'
        with patch.object(worker, 'proposal', side_effect=models.InferenceError('model_failure')):
            for index in range(3):
                self.assertEqual(worker.run_item(self.item, archive, None), (0, False))
                saved = json.loads(status.read_text())
                self.assertEqual(saved['operator_required'], index == 2)
                saved['retry_after'] = 0; status.write_text(json.dumps(saved))

    def test_prepared_delivery_does_not_require_idle_gpu(self):
        archive = self.folder/'archive'; folder = archive/self.item['id']
        folder.mkdir(parents=True); (folder/'original').write_bytes(self.original.read_bytes())
        payload = {'analysis_id': '5'*36, 'review_scope': {'package_id': 'a'*64}}
        with patch.object(worker, 'proposal', return_value=payload), \
                patch.object(worker, 'deliver', return_value={'ok': True}), \
                patch.object(worker, 'resource_ready', side_effect=AssertionError('GPU not needed')):
            self.assertEqual(worker.run_item(self.item, archive, None), (1, False))


if __name__ == '__main__':
    unittest.main()
