"""Operational pages stay independent of full candidate-library allocation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
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
