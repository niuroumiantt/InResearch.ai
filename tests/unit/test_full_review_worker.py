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

    def generate_campus_adjudication(self, system, user, **kwargs):
        return self.generate(system, user, **kwargs)

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
        self.original = self.folder/'original'
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

    def test_extensionless_archive_original_remains_unchanged(self):
        before = self.original.read_bytes()
        client = FakeClient()
        self.assertIsNone(worker.proposal(self.item, self.original, self.folder, client))
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(self.original.name, 'original')
        self.assertEqual(self.original.read_bytes(), before)
        self.assertFalse((self.folder/'source.xlsx').exists())

    def test_source_failure_before_planning_reports_blocked_without_coverage(self):
        folder = self.folder/self.item['id']
        folder.mkdir()
        (folder/'original').write_bytes(self.original.read_bytes()+b'changed')
        reports = []
        def request(route, payload):
            reports.append((route, payload))
            return io.BytesIO(b'{"ok":true}')
        with patch.object(worker, 'client') as client:
            self.assertEqual(worker.run_item(self.item, self.folder, request), (0, False))
        client.assert_not_called()
        self.assertEqual(len(reports), 1)
        route, payload = reports[0]
        self.assertEqual(route, 'analysis-progress')
        self.assertEqual(payload['package_id'], 'a'*64)
        self.assertEqual((payload['window_completed'], payload['window_total']), (0, 0))
        self.assertEqual(payload['state'], 'blocked')
        self.assertEqual(payload['reason'], 'campus_source_sha_changed')
        self.assertEqual(self.item['full_analysis']['completed_package_ids'], [])

    def test_chinese_payload_uses_actual_wire_size_for_multipart(self):
        payload = {'id':self.item['id'], 'sha256':self.sha,
                   'analysis_id':'4'*36, 'summary':'园'*1600}
        self.assertLess(len(worker.encoded(payload)), 6000)
        self.assertGreater(len(json.dumps(payload).encode()), 8192)
        sent = []
        def request(route, body):
            sent.append((route, body))
            self.assertLessEqual(len(json.dumps(body).encode()), 6000)
            return io.BytesIO(b'{"ok":true}')
        self.assertEqual(worker.deliver(payload, request), {'ok':True})
        self.assertNotIn('analysis', [route for route, body in sent])
        self.assertEqual(sent[-1][0], 'analysis-commit')
        sent.clear()
        worker.deliver({**payload, 'summary':'small'}, request)
        self.assertEqual([route for route, body in sent], ['analysis'])

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
        self.assertTrue(all([{k:v for k,v in cell.items() if k != 'column_headers'}
                             for cell in call['identity_context']] == self.cells[:1]
                            for call in client.calls[:-1]))
        self.assertEqual(client.calls[-1]['stage'], 'whole_campus_adjudication')
        self.assertEqual(client.calls[0]['source_context']['sha256'], self.sha)
        self.assertEqual(client.calls[-1]['source_context'], client.calls[0]['source_context'])
        for call in client.calls:
            self.assertIn('本窗未提供某字段不等于整个园区缺失', call['instructions'])
            self.assertIn('不得要求用机架数量', call['instructions'])
            self.assertIn('不要求把市区或地址填入省份列', call['instructions'])
            self.assertIn('禁止借用其他表的同列名', call['instructions'])
            self.assertIn('不得要求把数值或其他数据填入表头单元格', call['instructions'])

    def test_only_final_uses_token_guard_and_reuses_unchanged_successful_windows(self):
        class LongSummaryClient(FakeClient):
            def __init__(self):
                super().__init__()
                self.final_calls = 0
            def generate(self, system, user, **kwargs):
                result = super().generate(system, user, **kwargs)
                if self.calls[-1].get('stage') != 'whole_campus_adjudication':
                    result['summary'] = '完整原文摘要' * 2500
                return result
            def generate_campus_adjudication(self, system, user, **kwargs):
                self.final_calls += 1
                self.final_input = user
                if kwargs.get('before_completion'):
                    kwargs['before_completion']()
                return self.generate(system, user, **kwargs)
        client = LongSummaryClient()
        for _ in range(3):
            self.assertIsNone(worker.proposal(self.item, self.original, self.folder, client))
        self.assertEqual(client.final_calls, 0)
        files = {path: path.read_bytes() for path in self.folder.rglob('chunk-*.json')}
        gates = []
        result = worker.proposal(self.item, self.original, self.folder, client,
                                 before_generate=lambda: gates.append('ready'))
        self.assertGreater(len((review_worker.SYSTEM+client.final_input).encode()), 27648)
        self.assertEqual(len(gates), 2)
        self.assertEqual(client.final_calls, 1)
        self.assertEqual(len(client.calls), 4)
        self.assertEqual(len(result['review_windows']), 3)
        self.assertEqual(files, {path: path.read_bytes() for path in files})
        self.assertEqual(json.loads(client.final_input)['window_summaries'],
                         ['完整原文摘要' * 2500] * 3)

    def test_busy_gpu_before_final_prevents_render_or_inference(self):
        client = FakeClient()
        for _ in range(3):
            worker.proposal(self.item, self.original, self.folder, client)
        files = {path: path.read_bytes() for path in self.folder.rglob('chunk-*.json')}
        def unavailable():
            raise worker.YieldWork('campus_waiting_for_gpu')
        with self.assertRaises(worker.YieldWork):
            worker.proposal(self.item, self.original, self.folder, client,
                            before_generate=unavailable)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(files, {path: path.read_bytes() for path in files})
        self.assertFalse(list(self.folder.rglob('adjudication.json')))

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

    def test_unadvanced_cache_tampering_is_not_a_retryable_model_rejection(self):
        client = FakeClient(); atomic = worker.atomic
        def crash_before_advance(path, value):
            if path.name == 'progress.json' and value.get('next') == 1:
                raise OSError('simulated cursor write failure')
            return atomic(path, value)
        with patch.object(worker, 'atomic', side_effect=crash_before_advance):
            with self.assertRaisesRegex(OSError, 'cursor write failure'):
                worker.proposal(self.item, self.original, self.folder, client)
        path = next(self.folder.rglob('chunk-00000.json'))
        saved = json.loads(path.read_text())
        saved['result']['summary'] = 'changed outside model'
        path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, 'campus_chunk_input_changed') as error:
            worker.proposal(self.item, self.original, self.folder, client)
        self.assertNotIsInstance(error.exception, worker.RejectedWindow)
        self.assertEqual(len(client.calls), 1)
        self.assertFalse(list(self.folder.rglob('response-*.json')))
        self.assertEqual(json.loads(next(self.folder.rglob('progress.json')).read_text())['next'], 0)

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

    def test_identity_context_uses_own_sheet_headers_in_every_window(self):
        def cell(sheet, number, address, value):
            return {**native(address, value), 'sheet': sheet,
                    'locator': f'xlsx:sheet:{number}:cell:{address}:context:{address}:{address}'}
        identity = cell('1-地点与身份', 1, 'J7', '未见公开披露')
        identity_header = cell(identity['sheet'], 1, 'J1', '坐标精度')
        power_header = cell('3-电源输配与接入', 2, 'J1', '未获项与原因')
        self.packet['identity_cells'] = [identity]
        self.packet['header_cells'] = [identity_header, power_header]
        self.packet['cells'] = [identity]+[
            cell(power_header['sheet'], 2, f'J{n}', '电力原文') for n in range(2, 69)]
        parts = worker.chunks(self.packet, self.task, [], FakeClient().profile)
        self.assertGreater(len(parts), 1)
        expected = {key: identity_header[key] for key in ('sheet', 'cell', 'locator', 'value')}
        for part in parts:
            self.assertEqual(part['identity_context'][0]['column_headers'], [expected])
            for fragment in part['native_fragments']:
                if fragment['sheet'] == power_header['sheet']:
                    self.assertEqual(fragment['column_headers'], [power_header])
        observed = [fragment['locator'] for part in parts for fragment in part['native_fragments']]
        self.assertEqual(observed, [row['locator'] for row in self.packet['cells']])
        self.assertEqual(len(observed), len(set(observed)))
        self.assertNotIn('column_headers', identity)
        self.assertNotIn(identity_header['locator'], observed)

    def test_identity_headers_are_visible_but_cannot_supply_candidate_values(self):
        name, location, detail = native('B7', '园区甲'), native('D7', '内蒙古自治区'), native('J7', '未见公开披露')
        header = native('J1', '坐标精度')
        self.packet['identity_cells'] = [name, location, detail]
        self.packet['header_cells'] = [header]
        self.packet['cells'] = [native('G8', '实际备注')]
        part = worker.chunks(self.packet, self.task, [], FakeClient().profile)[0]
        self.assertEqual([f['locator'] for f in part['native_fragments']], [native('G8', '')['locator']])
        schema = worker.reading_schema(part)
        props = schema['properties']['candidates']['items']['properties']
        self.assertNotIn(header['locator'], props['locator']['enum'])
        self.assertNotIn(header['locator'], props['name_locator']['enum'])
        branches = schema['properties']['findings']['items']['oneOf']
        self.assertTrue(any(branch['properties']['sheet']['const'] == header['sheet']
                            and header['cell'] in branch['properties']['cell']['enum'] for branch in branches))
        result = FakeClient().generate('规则', '{}')
        result['findings'] = [{'sheet': header['sheet'], 'cell': header['cell'], 'priority': 'P1',
                              'issue': '定位含义待核', 'action': '核对坐标精度来源', 'acceptance': '保留原表头'}]
        worker.validate_result(result, part, 'campus')
        result['candidates'] = [{'name_locator': name['locator'], 'location_locator': location['locator'],
                                 'locator': header['locator'], 'unit_locator': ''}]
        with self.assertRaisesRegex(ValueError, 'candidate_outside_complete_cells'):
            worker.validate_result(result, part, 'campus')

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
            self.assertEqual(worker.run_item(self.item, self.folder, lambda *a: io.BytesIO(b'{"ok":true}')), (0, False))
        status = json.loads(next(folder.rglob('status.json')).read_text())
        self.assertTrue(status['operator_required'])
        self.assertEqual(status['reason'], 'campus_delivery_http_400')

    def test_decoder_restricts_priorities_and_single_native_location(self):
        self.packet['identity_cells'] = [native('B7', '园区甲'), native('D7', '内蒙古自治区'),
                                         native('E7', '乌兰察布市')]
        part = worker.chunks(self.packet, self.task, [], FakeClient().profile)[0]
        schema = worker.reading_schema(part)
        props = schema['properties']['candidates']['items']['properties']
        self.assertEqual(props['location']['enum'], ['内蒙古自治区'])
        self.assertEqual(props['location_locator']['enum'], [native('D7', '')['locator']])
        self.assertTrue(all(branch['properties']['priority']['enum'] == ['P0','P1','P2']
                            for branch in schema['properties']['findings']['items']['oneOf']))
        self.assertNotIn('内蒙古自治区乌兰察布市', props['location']['enum'])

    def test_finding_decoder_binds_sheet_to_its_actual_cells(self):
        identity = {**native('C7', '内蒙古自治区'), 'sheet': '1-地点与身份'}
        capacity = {**native('A7', '园区甲'), 'sheet': '4-容量口径与分期'}
        headers = [{**native(f'{letter}1', '表头'), 'sheet': capacity['sheet']}
                   for letter in 'ABCDEFGHIJKLM']
        part = {'native_fragments': [{**worker.fragments([capacity])[0], 'column_headers': headers}],
                'identity_context': [identity]}
        schema = worker.finding_schema([identity, capacity]+headers)
        self.assertEqual(set(schema['items']), {'oneOf'})
        branches = schema['items']['oneOf']
        def accepted(sheet, cell):
            return any(branch['properties']['sheet']['const'] == sheet
                       and cell in branch['properties']['cell']['enum'] for branch in branches)
        self.assertTrue(accepted(identity['sheet'], 'C7'))
        self.assertTrue(accepted(capacity['sheet'], 'A7'))
        self.assertTrue(accepted(capacity['sheet'], 'C1'))
        self.assertFalse(accepted(capacity['sheet'], 'C7'))
        result = FakeClient().generate('规则', '{}')
        result['findings'] = [{'sheet': capacity['sheet'], 'cell': 'C7', 'priority': 'P0',
                               'issue': '本窗缺少容量', 'action': '查原始披露', 'acceptance': '核对原值'}]
        with self.assertRaisesRegex(ValueError, 'finding_outside_read_cells'):
            worker.validate_result(result, part, 'campus')
        result['findings'][0]['cell'] = 'A7'
        worker.validate_result(result, part, 'campus')
        # The same linked schema is used for each reading call, including
        # repeated headers, and for final adjudication.
        self.assertEqual(worker.reading_schema({**part, 'packet_kind': 'unassigned',
                            'campus_name': '', 'known_sites': []})['properties']['findings'], schema)

    def test_rejected_window_retries_without_reusing_failure_or_rereading_success(self):
        client = FakeClient()
        generate = client.generate
        def once_invalid(*args, **kwargs):
            result = generate(*args, **kwargs)
            if len(client.calls) == 2:
                result['findings'] = [{'sheet': '园区', 'cell': 'Z99', 'priority': 'P0',
                                      'issue': '未见定位', 'action': '核对', 'acceptance': '原文'}]
            return result
        client.generate = once_invalid
        worker.proposal(self.item, self.original, self.folder, client)
        first = next(self.folder.rglob('chunk-00000.json'))
        before = first.read_bytes()
        with self.assertRaises(worker.RejectedWindow) as error:
            worker.proposal(self.item, self.original, self.folder, client)
        self.assertTrue(error.exception.retryable)
        rejected = next(self.folder.rglob('response-01.json'))
        rejected_before = rejected.read_bytes()
        saved = json.loads(rejected_before)
        self.assertEqual(saved['result']['findings'][0]['cell'], 'Z99')
        self.assertEqual(saved['result_sha256'], worker.digest(saved['result']))
        self.assertFalse(list(self.folder.rglob('chunk-00001.json')))
        self.assertEqual(json.loads(next(self.folder.rglob('progress.json')).read_text())['next'], 1)
        payload = None
        for _ in range(3):
            payload = worker.proposal(self.item, self.original, self.folder, client)
        self.assertIsNotNone(payload)
        self.assertEqual(client.calls[1], client.calls[2])
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual(len(client.calls), 5)
        self.assertEqual(len(payload['review_windows']), 3)
        self.assertEqual(payload['findings'], [])
        self.assertEqual(rejected.read_bytes(), rejected_before)

    def test_rejected_window_budget_survives_status_reset_and_preserves_all_responses(self):
        archive = self.folder/'archive'; folder = archive/self.item['id']
        folder.mkdir(parents=True); (folder/'original').write_bytes(self.original.read_bytes())
        client = FakeClient(); generate = client.generate
        def always_invalid(*args, **kwargs):
            result = generate(*args, **kwargs)
            result['findings'] = [{'sheet': '园区', 'cell': 'Z99', 'priority': 'P0',
                                  'issue': '未见定位', 'action': '核对', 'acceptance': '原文'}]
            return result
        client.generate = always_invalid
        status = folder/'full-review'/self.item['full_analysis']['attempt_id']/'status.json'
        reports = []
        def request(route, body):
            reports.append(body)
            return io.BytesIO(b'{"ok":true}')
        with patch.object(worker, 'client', return_value=client), \
                patch.object(worker, 'resource_ready', return_value=(True, '')):
            for index in range(3):
                with patch.object(worker.time, 'time', return_value=1000+301*index):
                    self.assertEqual(worker.run_item(self.item, archive, request), (0, True))
                saved = json.loads(status.read_text())
                self.assertEqual(saved['operator_required'], index == 2)
                self.assertEqual(reports[-1]['window_completed'], 0)
                self.assertEqual(len(client.calls), index+1)
                if index == 0:
                    with patch.object(worker.time, 'time', return_value=1301), \
                            patch.object(worker, 'resource_ready', return_value=(False, 'campus_waiting_for_gpu')):
                        self.assertEqual(worker.run_item(self.item, archive, request), (0, False))
                    self.assertEqual(len(client.calls), 1)
                    self.assertEqual(json.loads(status.read_text())['state'], 'waiting')
            retained = {path: path.read_bytes() for path in folder.rglob('response-*.json')}
            self.assertEqual(len(retained), 3)
            self.assertEqual(len(list(folder.rglob('rejection-*.json'))), 3)
            self.assertEqual(len(client.calls), 3)
            # Simulate loss of advisory status: durable rejected responses still
            # prevent an unbounded fourth call for this frozen window.
            status.unlink()
            self.assertEqual(worker.run_item(self.item, archive, request), (0, False))
        self.assertEqual(len(client.calls), 3)
        self.assertTrue(json.loads(status.read_text())['operator_required'])
        self.assertEqual(json.loads(status.read_text())['reason'], 'campus_window_rejections_exhausted')
        self.assertFalse(list(folder.rglob('proposal.json')))
        self.assertFalse(list(folder.rglob('chunk-00000.json')))
        self.assertTrue(all(path.read_bytes() == raw for path, raw in retained.items()))

    def test_prompt_or_decoder_change_cannot_mix_successful_windows(self):
        client = FakeClient(); worker.proposal(self.item, self.original, self.folder, client)
        with patch.object(review_worker, 'SYSTEM', review_worker.SYSTEM+'新规则'):
            with self.assertRaisesRegex(ValueError, 'recipe_changed'):
                worker.proposal(self.item, self.original, self.folder, client)
        original = worker.reading_schema
        with patch.object(worker, 'reading_schema', side_effect=lambda part: {**original(part), 'description':'new'}):
            with self.assertRaisesRegex(ValueError, 'recipe_changed'):
                worker.proposal(self.item, self.original, self.folder, client)
        self.assertEqual(len(client.calls), 1)

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
                self.assertEqual(worker.run_item(self.item, archive, lambda *a: io.BytesIO(b'{"ok":true}')), (0, False))
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
