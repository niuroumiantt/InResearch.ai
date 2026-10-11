"""Operational pages stay independent of full candidate-library allocation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from inresearch.delivery import runtime_summary as views
from inresearch.knowledge import registry
from inresearch.paths import project_root
from inresearch.storage import files
from inresearch.workflow import commands, supply


class RuntimeSummaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = project_root()
        self.source = self.base / 'research_runtime.json'
        env = patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT': str(self.base),
                                    'INRESEARCH_READER_SNAPSHOT': str(self.source)})
        env.start(); self.addCleanup(env.stop)
        registry.clear_runtime_cache(); self.addCleanup(registry.clear_runtime_cache)
        sha = 'a' * 64; ident = 'doc-' + sha
        self.payload = dict(graph_version=registry.read_json(self.root/'framework/research_graph.json')['version'],
            questions_version=registry.read_json(self.root/'framework/research_questions.json')['version'],
            generated=datetime.now(timezone.utc).isoformat(), reader={'status': 'running',
                'acquisition': {'material_matches': {'records': [{'sha256': sha}], 'total': 1}}},
            knowledge={'documents': [{'id': ident, 'content_sha256': sha, 'read_status': 'complete', 'title': 'Source',
                'coverage': {'complete': True, 'pages_total': 1, 'pages_read': 1,
                    'chunks_total': 1, 'chunks_read': 1, 'characters_total': 40, 'characters_read': 40}}],
                'evidence': [{'id': 'e:test', 'document_id': ident, 'quote': 'Original quotation',
                    'page_index': 0, 'object_ids': ['part:gpu']}],
                'statements': [{'id': 's:test', 'document_id': ident, 'text': 'Bounded candidate',
                    'evidence_ids': ['e:test'], 'object_ids': ['part:gpu']}], 'answers': []})

    def receive(self):
        return commands.receive_snapshot(self.root, self.payload, self.source)

    def test_control_roundtrip_replay_and_original_bytes_remain_intact(self):
        formal = (self.root/'data/research_knowledge.json').read_bytes()
        self.receive(); before = self.source.read_bytes()
        view = views.read_control(self.source, verify_bytes=True)
        self.assertEqual(view['source_sha256'], hashlib.sha256(before).hexdigest())
        self.assertNotIn('knowledge', view)
        self.assertEqual(view['reading_deliveries'][0]['quotes'], [{'quote': 'Original quotation', 'page_index': 0}])
        self.assertEqual(view['reading_deliveries'][0]['acceptance'], 'candidate_only')
        self.assertTrue(self.receive()['replayed'])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual((self.root/'data/research_knowledge.json').read_bytes(), formal)
        changed = dict(self.payload, knowledge=dict(self.payload['knowledge'], answers=[]))
        changed['knowledge']['statements'] = [dict(self.payload['knowledge']['statements'][0], text='Changed claim')]
        with self.assertRaises(commands.Rejected):
            commands.receive_snapshot(self.root, changed, self.source)
        self.assertEqual(self.source.read_bytes(), before)

    def newer_payload(self, title='New news'):
        payload = copy.deepcopy(self.payload)
        payload['generated'] = (registry.parse_time(payload['generated']) + timedelta(seconds=1)).isoformat()
        payload['reader']['acquisition']['news_feed'] = {'items': [{'title': title}]}
        return payload

    def news_title(self):
        value = views.load_acquisition(self.root)
        return value.get('reader', {}).get('acquisition', {}).get('news_feed', {}).get('items', [{}])[0].get('title')

    def test_long_source_encoding_and_control_hashing_keep_old_pair_readable(self):
        self.payload['reader']['acquisition']['news_feed'] = {'items': [{'title': 'Old news'}]}
        self.receive()
        before = self.source.read_bytes()
        control_before = views.control_path(self.source).read_bytes()
        for phase in ('source_encoding', 'control_hashing'):
            with self.subTest(phase=phase):
                started, release = threading.Event(), threading.Event()
                newer = self.newer_payload(phase)
                target = 'write_json_streaming' if phase == 'source_encoding' else '_control_value'
                original = getattr(views, target)
                def pause(path, *args, **kwargs):
                    if Path(path).name == 'source.json':
                        started.set()
                        if not release.wait(5):
                            raise AssertionError('staged build did not resume')
                    return original(path, *args, **kwargs)
                with patch.object(views, target, side_effect=pause), ThreadPoolExecutor(max_workers=4) as pool:
                    future = pool.submit(commands.receive_snapshot, self.root, newer, self.source)
                    try:
                        self.assertTrue(started.wait(5))
                        reads = list(pool.map(lambda _: self.news_title(), range(8)))
                        self.assertEqual(reads, ['Old news'] * 8)
                        self.assertEqual(self.source.read_bytes(), before)
                        self.assertEqual(views.control_path(self.source).read_bytes(), control_before)
                    finally:
                        release.set()
                    self.assertTrue(future.result()['ok'])
                self.assertEqual(self.news_title(), phase)
                self.assertEqual(views.read_control(self.source, verify_bytes=True)['source_sha256'],
                                 views.physical_digest(registry.read_json(self.source)))
                self.assertFalse(list(self.base.glob('.research_runtime.json.stage-*')))
                # Use the newly committed pair as the old generation for the next phase.
                self.payload = newer
                self.payload['reader']['acquisition']['news_feed']['items'][0]['title'] = 'Old news'
                self.payload['generated'] = (registry.parse_time(newer['generated']) + timedelta(seconds=1)).isoformat()
                self.receive()
                before = self.source.read_bytes()
                control_before = views.control_path(self.source).read_bytes()

    def test_source_replacement_selects_prepared_control_and_promotion_failure_replays(self):
        self.receive()
        newer = self.newer_payload()
        prepared, active = views.prepared_control_path(self.source), views.control_path(self.source)
        original = views.os.replace
        def fail_promotion(source, destination):
            if Path(source) == prepared and Path(destination) == active:
                raise OSError('injected control promotion failure')
            return original(source, destination)
        with patch.object(views.os, 'replace', side_effect=fail_promotion), \
             self.assertRaisesRegex(commands.Rejected, 'source installed; control promotion pending') as caught:
            commands.receive_snapshot(self.root, newer, self.source)
        self.assertEqual(caught.exception.status, 503)
        committed = self.source.read_bytes()
        self.assertEqual(self.news_title(), 'New news')
        self.assertEqual(views.read_control(self.source, verify_bytes=True)['source_sha256'],
                         hashlib.sha256(committed).hexdigest())
        self.assertTrue(prepared.exists())
        stages = list(self.base.glob('.research_runtime.json.stage-*'))
        self.assertEqual(len(stages), 1)
        self.assertTrue((stages[0] / 'control.json').is_file())
        self.assertTrue(commands.receive_snapshot(self.root, newer, self.source)['replayed'])
        self.assertEqual(self.source.read_bytes(), committed)
        self.assertFalse(prepared.exists())
        self.assertIsNotNone(views.read_control(self.source, verify_bytes=True))

    def test_build_or_source_install_failure_retains_old_pair_and_staged_candidate(self):
        self.receive()
        before = self.source.read_bytes()
        control_before = views.control_path(self.source).read_bytes()
        newer = self.newer_payload()
        with patch.object(views, 'semantic_digest', side_effect=ValueError('injected hashing failure')), \
             self.assertRaisesRegex(ValueError, 'injected hashing failure'):
            commands.receive_snapshot(self.root, newer, self.source)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(views.control_path(self.source).read_bytes(), control_before)
        self.assertFalse(views.prepared_control_path(self.source).exists())
        original = views.os.replace
        def fail_source(source, destination):
            if Path(destination) == self.source:
                raise OSError('injected source installation failure')
            return original(source, destination)
        with patch.object(views.os, 'replace', side_effect=fail_source), \
             self.assertRaisesRegex(commands.Rejected, 'previous projection retained') as caught:
            commands.receive_snapshot(self.root, newer, self.source)
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(views.control_path(self.source).read_bytes(), control_before)
        self.assertEqual(views.read_control(self.source, verify_bytes=True)['source_sha256'],
                         hashlib.sha256(before).hexdigest())
        stages = list(self.base.glob('.research_runtime.json.stage-*'))
        self.assertEqual(len(stages), 2)
        for stage in stages:
            self.assertEqual(stage.stat().st_mode & 0o777, 0o700)
            self.assertEqual((stage / 'source.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(registry.read_json(stage / 'source.json')['generated'], newer['generated'])
        self.assertEqual(views.prepared_control_path(self.source).stat().st_mode & 0o777, 0o600)
        self.assertTrue(commands.receive_snapshot(self.root, newer, self.source)['ok'])
        self.assertTrue(all(stage.exists() for stage in stages))  # Failed complete originals survive retry.

    def test_growing_control_over_read_limit_never_installs_or_acknowledges_source(self):
        self.payload['reader']['acquisition']['news_feed'] = {'items': [{'title': 'Old news'}]}
        self.receive()
        before = self.source.read_bytes()
        active = views.control_path(self.source)
        control_before = active.read_bytes()
        cap = len(control_before) + 1
        newer = self.newer_payload('New news ' + 'x' * (cap * 2))
        with patch.object(views, 'MAX_CONTROL', cap):
            with self.assertRaisesRegex(commands.Rejected, 'control exceeds operational projection limit') as caught:
                commands.receive_snapshot(self.root, newer, self.source)
            self.assertEqual(caught.exception.status, 503)
            self.assertEqual(self.source.read_bytes(), before)
            self.assertEqual(active.read_bytes(), control_before)
            self.assertEqual(self.news_title(), 'Old news')
            self.assertIsNotNone(views.read_control(self.source, verify_bytes=True))
        stages = list(self.base.glob('.research_runtime.json.stage-*'))
        self.assertEqual(len(stages), 1)
        self.assertTrue((stages[0] / 'source.json').is_file())
        self.assertGreater((stages[0] / 'control.json').stat().st_size, cap)
        self.assertFalse(views.prepared_control_path(self.source).exists())
        self.assertTrue(commands.receive_snapshot(self.root, newer, self.source)['ok'])
        self.assertTrue(stages[0].exists())  # Failed complete candidate is retained after a later successful retry.

    def test_source_directory_sync_failure_keeps_prepared_projection_recoverable(self):
        self.receive()
        newer = self.newer_payload()
        original = views.sync_directory
        def fail_after_source(path):
            if Path(path) == self.source.parent and views.read_header(self.source)['generated'] == newer['generated']:
                raise OSError('injected source directory sync failure')
            return original(path)
        with patch.object(views, 'sync_directory', side_effect=fail_after_source), \
             self.assertRaises(files.CommitUncertain):
            commands.receive_snapshot(self.root, newer, self.source)
        self.assertEqual(self.news_title(), 'New news')
        self.assertIsNotNone(views.read_control(self.source, verify_bytes=True))
        self.assertTrue(views.prepared_control_path(self.source).exists())
        self.assertTrue(commands.receive_snapshot(self.root, newer, self.source)['replayed'])

    def test_prepared_install_and_directory_sync_failures_leave_the_matching_slot(self):
        self.payload['reader']['acquisition']['news_feed'] = {'items': [{'title': 'Old news'}]}
        self.receive()
        newer = self.newer_payload()
        before = self.source.read_bytes()
        control_before = views.control_path(self.source).read_bytes()
        prepared = views.prepared_control_path(self.source)
        original_replace, original_sync = views.os.replace, views.sync_directory
        def fail_prepared(source, destination):
            if Path(destination) == prepared:
                raise OSError('injected prepared installation failure')
            return original_replace(source, destination)
        with patch.object(views.os, 'replace', side_effect=fail_prepared), \
             self.assertRaisesRegex(commands.Rejected, 'previous projection retained'):
            commands.receive_snapshot(self.root, newer, self.source)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(views.control_path(self.source).read_bytes(), control_before)
        self.assertEqual(self.news_title(), 'Old news')
        def fail_prepared_sync(path):
            if Path(path) == prepared.parent and prepared.exists():
                raise OSError('injected prepared directory sync failure')
            return original_sync(path)
        with patch.object(views, 'sync_directory', side_effect=fail_prepared_sync), \
             self.assertRaises(files.CommitUncertain):
            commands.receive_snapshot(self.root, newer, self.source)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(views.control_path(self.source).read_bytes(), control_before)
        self.assertEqual(self.news_title(), 'Old news')
        def fail_promoted_sync(path):
            if Path(path) == prepared.parent and not prepared.exists():
                raise OSError('injected promoted directory sync failure')
            return original_sync(path)
        with patch.object(views, 'sync_directory', side_effect=fail_promoted_sync), \
             self.assertRaises(files.CommitUncertain):
            commands.receive_snapshot(self.root, newer, self.source)
        self.assertEqual(self.news_title(), 'New news')
        self.assertIsNotNone(views.read_control(self.source, verify_bytes=True))
        self.assertTrue(commands.receive_snapshot(self.root, newer, self.source)['replayed'])

    def test_switch_boundary_reads_old_then_new_without_mixing_generations(self):
        self.payload['reader']['acquisition']['news_feed'] = {'items': [{'title': 'Old news'}]}
        self.receive()
        original = views.os.replace
        seen = []
        def observe_switch(source, destination):
            if Path(destination) == self.source:
                seen.append(self.news_title())
                self.assertIsNotNone(views.read_control(self.source, verify_bytes=True))
                original(source, destination)
                seen.append(self.news_title())
                self.assertIsNotNone(views.read_control(self.source, verify_bytes=True))
                return
            return original(source, destination)
        with patch.object(views.os, 'replace', side_effect=observe_switch):
            commands.receive_snapshot(self.root, self.newer_payload(), self.source)
        self.assertEqual(seen, ['Old news', 'New news'])

    def test_prepared_control_requires_physical_identity_authority_and_byte_verification(self):
        self.receive()
        active, prepared = views.control_path(self.source), views.prepared_control_path(self.source)
        value = registry.read_json(active)
        active.unlink()
        for changed in ([], dict(value, authority='untrusted'),
                        dict(value, source_signature=dict(value['source_signature'], size=1)),
                        dict(value, source_sha256='not-a-sha')):
            files.write_json(prepared, changed)
            self.assertIsNone(views.read_control(self.source))
        files.write_json(prepared, value)
        self.assertEqual(views.read_control(self.source, verify_bytes=True)['source_sha256'], value['source_sha256'])
        before = self.source.stat()
        raw = self.source.read_bytes()
        self.source.write_bytes(b' ' + raw[1:])  # Preserve physical metadata to exercise the SHA check itself.
        os.utime(self.source, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(views.signature(self.source), value['source_signature'])
        self.assertIsNone(views.read_control(self.source, verify_bytes=True))
        self.source.write_bytes(raw)
        self.assertIsNone(views.read_control(self.source))  # Ordinary external mutation changes the signature.

    def test_symlink_control_slots_and_source_are_refused(self):
        self.receive()
        active, prepared = views.control_path(self.source), views.prepared_control_path(self.source)
        valid = self.base / 'valid-control.json'
        valid.write_bytes(active.read_bytes())
        active.unlink()
        prepared.symlink_to(valid)
        self.assertIsNone(views.read_control(self.source))
        with self.assertRaisesRegex(ValueError, 'refuse_symlink_destination'):
            commands.receive_snapshot(self.root, self.newer_payload(), self.source)
        prepared.unlink()
        files.write_json(prepared, registry.read_json(valid))
        active.symlink_to(valid)
        with self.assertRaisesRegex(ValueError, 'refuse_symlink_destination'):
            self.receive()
        self.assertTrue(active.is_symlink())
        active.unlink()
        original = self.base / 'original-source.json'
        self.source.rename(original)
        self.source.symlink_to(original)
        self.assertIsNone(views.read_control(self.source))

    def test_management_uses_control_without_full_library_read(self):
        self.receive()
        with patch.object(views, 'SMALL_SNAPSHOT', 1), \
             patch.object(registry, '_snapshot_inputs', side_effect=AssertionError('full candidate read')):
            out = supply.snapshot(self.root)
        self.assertEqual(out['reading_deliveries'][0]['claims'], ['Bounded candidate'])
        self.assertEqual(out['matching_reader']['status'], 'running')

    def test_missing_stale_or_modified_control_never_loads_large_source(self):
        self.receive(); path = views.control_path(self.source)
        path.unlink()
        with patch.object(views, 'SMALL_SNAPSHOT', 1), patch.object(registry, 'read_json', side_effect=AssertionError('giant fallback')):
            result = views.load(self.root)
        self.assertEqual(result['reader']['status'], 'awaiting_operational_projection')
        self.assertEqual(result['reading_deliveries'], [])
        with patch.object(views, 'SMALL_SNAPSHOT', 1):
            self.assertTrue(self.receive()['replayed'])  # Byte-identical replay repairs its missing view.
        self.assertTrue(self.source.exists())
        self.source.write_bytes(self.source.read_bytes() + b' ')
        self.assertIsNone(views.read_control(self.source))
        with patch.object(views, 'SMALL_SNAPSHOT', 1), self.assertRaisesRegex(commands.Rejected, 'requires runtime-summary'):
            self.receive()
        self.assertTrue(self.source.read_bytes().endswith(b' '))

    def test_candidate_cache_singleflight_and_atomic_source_replacement(self):
        self.receive()
        with patch.object(registry, 'candidate_snapshot', wraps=registry.candidate_snapshot) as normalize:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: registry._snapshot_inputs(self.root)[-1], range(4)))
            self.assertEqual(normalize.call_count, 1)
            self.assertTrue(all(v is results[0] for v in results))
            files.write_json(self.source, registry.read_json(self.source))
            registry._snapshot_inputs(self.root)
            self.assertEqual(normalize.call_count, 2)

    def test_streaming_json_matches_format_hash_and_failure_is_atomic(self):
        normal, streamed = self.base/'normal.json', self.base/'streamed.json'
        value = {'中文': [1, {'data': 'value'}]}
        files.write_json(normal, value)
        digest = files.write_json_streaming(streamed, value)
        self.assertEqual(json.loads(normal.read_bytes()), json.loads(streamed.read_bytes()))
        expected = (json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
        self.assertEqual(streamed.read_bytes(), expected)
        self.assertEqual(digest, hashlib.sha256(streamed.read_bytes()).hexdigest())
        with self.assertRaises(ValueError):
            files.write_json_streaming(streamed, {'partial': [1, float('nan')]})
        self.assertEqual(streamed.read_bytes(), expected)
        self.assertFalse(list(self.base.glob('.*.tmp-*')))

    def test_stream_encoder_large_values_canonical_order_and_cycles(self):
        value = {'records': [{'id': i, 'text': '中文\n\t"\\' * 500} for i in range(300)],
                 'large': '🙂"\n' * 50000, 'nested': {str(i): [i, None, True] for i in range(5000)}}
        for canonical in (False, True):
            blocks = list(files.iter_json_bytes(value, sort_keys=canonical))
            expected = json.dumps(value, ensure_ascii=False, allow_nan=False,
                                  sort_keys=canonical, separators=(',', ':')).encode()
            self.assertEqual(b''.join(blocks), expected)
            self.assertLess(max(map(len, blocks)), 256 * 1024)
        keys = {i: 'value' * 200 for i in range(500)}
        self.assertEqual(json.loads(b''.join(files.iter_json_bytes(keys))),
                         json.loads(json.dumps(keys)))
        cyclic = []; cyclic.append(cyclic)
        with self.assertRaises(ValueError):
            b''.join(files.iter_json_bytes(cyclic))

    def test_prefix_stops_before_evidence_and_preserves_generation(self):
        self.receive()
        with self.source.open('r') as stream:
            raw = json.load(stream)
        header = views.read_header(self.source)
        self.assertEqual(header['generated'], raw['generated'])
        self.assertEqual(header['received_at'], raw['received_at'])
        self.assertNotIn('knowledge', header)
        self.assertNotIn('reader', header)
