import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inresearch.adapters.acquisition import hash_file
from inresearch.paths import project_root
from inresearch.workflow import research_match, research_sources
from inresearch.delivery import reader_export
from inresearch.knowledge import registry, material_baseline


class ResearchSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.data = self.base / 'data'
        self.original = self.base / 'source.html'
        self.original.write_text('<p>GPU server TCO cost $100 and electricity grid approval.</p>')
        self.carrier = self.base / 'response.md'
        self.carrier.write_text('Archived tool response, not downloaded original. GPU cost $80.')
        self.response = self.base / 'response.json'
        self.response.write_text(json.dumps('GPU cost $80.'))
        self.first = research_match.ingest(self.original, self.data, project_root())
        self.second = research_match.ingest(self.carrier, self.data, project_root())
        self.sidecar = self.base / 'sources.json'
        self.payload = {'batch': 'fixture', 'items': [
            {'source_id': 'original', 'role': 'downloaded_original', 'input_path': 'source.html',
             'sha256': self.first['sha256'], 'original_sha256': self.first['sha256'],
             'url': 'https://example.test/original'},
            {'source_id': 'carrier', 'role': 'decoded_archived_tool_response', 'input_path': 'response.md',
             'sha256': self.second['sha256'], 'response_path': 'response.json',
             'response_sha256': hash_file(self.response), 'original_bytes_sha256': None,
             'url': 'https://example.test/tool-response', 'derivation': 'JSON string decode with provenance header'}]}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        self.sidecar.write_text(json.dumps(self.payload))

    def ledger(self):
        db = sqlite3.connect(self.data / 'acquisition/catalog.sqlite')
        try:
            return {table: db.execute('SELECT * FROM ' + table + ' ORDER BY 1').fetchall()
                    for table in ('items', 'observations', 'links', 'runs', 'product_documents')}
        finally:
            db.close()

    def queue(self):
        return {str(p.relative_to(self.data)): hash_file(p)
                for p in (self.data / 'raw-materials').rglob('*') if p.is_file()}

    def test_plan_apply_and_replay_preserve_matches_bytes_and_queue(self):
        before, queue = self.ledger(), self.queue()
        planned = research_sources.receive(self.sidecar, self.data)
        self.assertEqual((planned['mode'], planned['filled']), ('plan', 2))
        self.assertEqual(self.ledger(), before)
        self.assertFalse((self.data / 'material-reviews').exists())
        received = research_sources.receive(self.sidecar, self.data, apply=True)
        self.assertEqual((received['downloaded_originals'], received['archived_tool_response_carriers']), (1, 1))
        self.assertEqual(Path(received['sidecar_archive']).read_bytes(), self.sidecar.read_bytes())
        after = self.ledger()
        self.assertEqual({k:v for k,v in after.items() if k != 'items'},
                         {k:v for k,v in before.items() if k != 'items'})
        for old, new in zip(before['items'], after['items']):
            self.assertEqual(old[:5], new[:5])  # Identity, kind and state retained.
            self.assertEqual(old[6], new[6])  # Title retained.
            old_meta, new_meta = json.loads(old[7]), json.loads(new[7])
            for key in ('source_url', 'source_provenance'): new_meta.pop(key)
            self.assertEqual(old_meta, new_meta)
        replay = research_sources.receive(self.sidecar, self.data, apply=True)
        self.assertEqual((replay['filled'], replay['unchanged']), (0, 2))
        self.assertEqual(self.ledger(), after)
        self.assertEqual(self.queue(), queue)
        view = research_match.projection(self.data)['records']
        tool = next(row for row in view if row['sha256'] == self.second['sha256'])
        self.assertIsNone(tool['source_provenance']['original_bytes_sha256'])
        self.assertEqual(tool['source_provenance']['response_sha256'], hash_file(self.response))
        self.assertFalse(tool['full_read'])
        self.assertEqual(tool['acceptance'], 'candidate')

    def test_reindex_preserves_received_source_provenance(self):
        research_sources.receive(self.sidecar, self.data, apply=True)
        old = {row['sha256']: row for row in research_match.projection(self.data)['records']}
        research_match.ingest(self.original, self.data, project_root())
        new = {row['sha256']: row for row in research_match.projection(self.data)['records']}
        sha = self.first['sha256']
        self.assertEqual(new[sha]['source_url'], old[sha]['source_url'])
        self.assertEqual(new[sha]['source_provenance'], old[sha]['source_provenance'])
        self.assertEqual(new[sha]['matches'], old[sha]['matches'])
        self.assertEqual(research_sources.receive(self.sidecar, self.data, apply=True)['filled'], 0)

    def test_unchanged_receipt_hashes_actual_noncanonical_metadata_bytes(self):
        research_sources.receive(self.sidecar, self.data, apply=True)
        db = sqlite3.connect(self.data / 'acquisition/catalog.sqlite')
        with db:
            for ident, metadata in db.execute('SELECT id,metadata FROM items').fetchall():
                db.execute('UPDATE items SET metadata=? WHERE id=?',
                           (json.dumps(json.loads(metadata), indent=3), ident))
        db.close()
        before = self.ledger()
        replay = research_sources.receive(self.sidecar, self.data, apply=True)
        self.assertEqual(self.ledger(), before)
        self.assertEqual(replay['filled'], 0)
        for row in replay['results']:
            self.assertEqual(row['metadata_before_sha256'], row['metadata_after_sha256'])

    def test_received_urls_invalidate_only_bound_document_cache_and_reach_baseline(self):
        from inresearch.workflow.reader import Reader
        from test_continuous_reader import Model
        unrelated = self.data / 'raw-materials/unrelated.txt'
        unrelated.write_text('Independent server original without supplied URL metadata.')
        unchanged = 'doc-' + hash_file(unrelated)
        reader = Reader(self.data, self.base/'reader-state', project_root(),
                        model=Model(), stable_seconds=0).initialize()
        try:
            with patch('sys.stdout', io.StringIO()):
                reader.run(once=True)
            first = reader.export_snapshot()
            self.assertEqual(len(first['knowledge']['documents']), 3)
            self.assertTrue(all('source_url' not in d for d in first['knowledge']['documents']))
            readings = reader.conn.execute('SELECT * FROM current_readings ORDER BY doc_id').fetchall()
            reports = {r['report_rel']: hash_file(self.data/r['report_rel']) for r in readings}
            cache = sqlite3.connect(reader.state / reader_export.PROJECTION_CACHE)
            keys_before = dict(cache.execute('SELECT doc_id,fingerprint FROM projection'))
            cache.close()
            research_sources.receive(self.sidecar, self.data, apply=True)
            with patch.object(reader_export, 'read_report', wraps=reader_export.read_report) as reads:
                second = reader.export_snapshot()
            self.assertEqual({call.args[1]['sha256'] for call in reads.call_args_list},
                             {self.first['sha256'], self.second['sha256']})
            cache = sqlite3.connect(reader.state / reader_export.PROJECTION_CACHE)
            keys_after = dict(cache.execute('SELECT doc_id,fingerprint FROM projection'))
            cache.close()
            self.assertEqual(keys_before[unchanged], keys_after[unchanged])
            self.assertEqual(next(d for d in first['knowledge']['documents'] if d['id'] == unchanged),
                             next(d for d in second['knowledge']['documents'] if d['id'] == unchanged))
            graph = json.loads((project_root()/'framework/research_graph.json').read_text())
            questions = json.loads((project_root()/'framework/research_questions.json').read_text())
            normalized = registry.candidate_snapshot(second, graph, questions)['knowledge']
            tool = next(d for d in normalized['documents'] if d['content_sha256'] == self.second['sha256'])
            self.assertEqual(tool['source_url'], 'https://example.test/tool-response')
            self.assertIsNone(tool['source_provenance']['original_bytes_sha256'])
            self.assertEqual(tool['source_provenance']['role'], 'decoded_archived_tool_response')
            material_rows, _ = material_baseline.rows(normalized, {})
            tool_row = next(r for r in material_rows if r['source']['content_sha256'] == self.second['sha256'])
            self.assertEqual(tool_row['source']['url'], tool['source_url'])
            self.assertEqual(tool_row['source']['provenance'], tool['source_provenance'])
            self.assertEqual(reader.conn.execute('SELECT * FROM current_readings ORDER BY doc_id').fetchall(), readings)
            self.assertEqual({p:hash_file(self.data/p) for p in reports}, reports)
            with patch.object(reader_export, 'read_report', side_effect=AssertionError('cached report reread')):
                reader.export_snapshot()
        finally:
            reader.close()

    def test_export_rejects_unbound_or_corrupted_sidecar_provenance(self):
        research_sources.receive(self.sidecar, self.data, apply=True)
        self.assertEqual(len(reader_export.supplied_sources(self.data)), 2)
        proof = reader_export.supplied_sources(self.data)[self.first['sha256']]['source_provenance']
        archive = self.data/'material-reviews/source-sidecars'/(proof['sidecar_sha256']+'.json')
        archive.write_text('{}')
        self.assertEqual(reader_export.supplied_sources(self.data), {})

    def test_snapshot_receiver_rejects_carrier_original_claim_or_sha_mismatch(self):
        from test_research import complete_document
        research_sources.receive(self.sidecar, self.data, apply=True)
        source = reader_export.supplied_sources(self.data)[self.second['sha256']]
        graph = json.loads((project_root()/'framework/research_graph.json').read_text())
        questions = json.loads((project_root()/'framework/research_questions.json').read_text())
        doc = {**complete_document(self.second['sha256']), **source}
        payload = {'generated': research_sources.now(), 'graph_version': graph['version'],
                   'questions_version': questions['version'], 'knowledge': {'documents': [doc]}}
        for key, value in (('input_sha256', 'b'*64), ('original_bytes_sha256', self.second['sha256']),
                           ('url', 'https://example.test/different'), ('role', 'downloaded_original')):
            bad = json.loads(json.dumps(payload))
            bad['knowledge']['documents'][0]['source_provenance'][key] = value
            with self.assertRaises(ValueError):
                registry.candidate_snapshot(bad, graph, questions)

    def test_new_review_packet_preserves_carrier_role_and_legacy_source_checks(self):
        from inresearch.workflow.reader import Reader
        from inresearch.workflow import research_review
        from test_continuous_reader import Model
        reader = Reader(self.data, self.base/'reader-state', project_root(),
                        model=Model(), stable_seconds=0).initialize()
        store = research_review.ReviewStore(self.data)
        try:
            with patch('sys.stdout', io.StringIO()):
                reader.run(once=True)
            doc = dict(reader.conn.execute('SELECT * FROM current_readings WHERE sha256=?',
                                           (self.second['sha256'],)).fetchone())
            exported = reader.export_snapshot()['knowledge']
            ids = [s['id'] for s in exported['statements'] if s['document_id'] == doc['doc_id']]
            batch = {'id':'a'*64, 'doc_id':doc['doc_id'], 'revision_id':doc['revision_id'],
                     'report_sha':doc['report_sha256'], 'candidate_ids':json.dumps(ids)}
            with store.db:
                store.db.execute('INSERT INTO batches(id,doc_id,revision_id,report_sha,state,candidate_ids,updated,error) VALUES(?,?,?,?,?,?,?,?)',
                                 (batch['id'],batch['doc_id'],batch['revision_id'],batch['report_sha'],
                                  'queued',batch['candidate_ids'],research_sources.now(),''))
            old = store.packet(project_root(), batch, include_adopted=True)
            self.assertNotIn('source_provenance', old['document'])
            queue = store.db.execute('SELECT * FROM batches').fetchall()
            research_sources.receive(self.sidecar, self.data, apply=True)
            fresh = store.packet(project_root(), batch, include_adopted=True)
            proof = fresh['document']['source_provenance']
            self.assertEqual(proof['role'], 'decoded_archived_tool_response')
            self.assertIsNone(proof['original_bytes_sha256'])
            self.assertEqual(proof['response_sha256'], hash_file(self.response))
            restored = research_review.verify_source_packet(store, project_root(), batch['id'], {'packet':old})
            self.assertEqual(restored['document'], old['document'])
            checked = research_review.verify_source_packet(store, project_root(), batch['id'], {'packet':fresh})
            self.assertEqual(checked['document'], fresh['document'])
            self.assertEqual(store.db.execute('SELECT * FROM batches').fetchall(), queue)
            archive = self.data/'material-reviews/source-sidecars'/(proof['sidecar_sha256']+'.json')
            archive.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'source_report_changed: document'):
                research_review.verify_source_packet(store, project_root(), batch['id'], {'packet':fresh})
        finally:
            store.db.close()
            reader.close()

    def test_existing_url_conflict_rejects_entire_batch(self):
        db = sqlite3.connect(self.data / 'acquisition/catalog.sqlite')
        with db:
            db.execute('UPDATE items SET url=? WHERE source_key=?',
                       ('https://example.test/known-url', self.second['sha256']))
        db.close()
        before = self.ledger()
        with self.assertRaisesRegex(ValueError, 'source_url_conflict'):
            research_sources.receive(self.sidecar, self.data, apply=True)
        self.assertEqual(self.ledger(), before)
        self.assertFalse((self.data / 'material-reviews').exists())

    def test_input_response_and_archive_corruption_reject_before_writes(self):
        before = self.ledger()
        for path, error in ((self.original, 'source_input_hash_mismatch'),
                            (self.response, 'source_response_hash_mismatch')):
            original = path.read_bytes()
            path.write_bytes(b'corrupted')
            with self.assertRaisesRegex(ValueError, error):
                research_sources.receive(self.sidecar, self.data, apply=True)
            self.assertEqual(self.ledger(), before)
            path.write_bytes(original)
        sha = self.first['sha256']
        archive = self.data / 'acquisition/blobs' / sha[:2] / (sha + '.html')
        archive.chmod(0o600)
        archive.write_bytes(b'corrupted archive')
        with self.assertRaisesRegex(ValueError, 'source_archive_hash_mismatch'):
            research_sources.receive(self.sidecar, self.data, apply=True)
        self.assertEqual(self.ledger(), before)
        self.assertFalse((self.data / 'material-reviews').exists())

    def test_tool_carrier_cannot_claim_original_or_conflicting_provenance(self):
        before = self.ledger()
        self.payload['items'][1]['original_bytes_sha256'] = self.second['sha256']
        self.save()
        with self.assertRaisesRegex(ValueError, 'tool_response_is_not_original'):
            research_sources.receive(self.sidecar, self.data, apply=True)
        self.assertEqual(self.ledger(), before)
        self.payload['items'][1]['original_bytes_sha256'] = None
        self.save()
        research_sources.receive(self.sidecar, self.data, apply=True)
        before = self.ledger()
        self.payload['items'][1]['derivation'] = 'changed supplier account'
        self.save()
        with self.assertRaisesRegex(ValueError, 'source_provenance_conflict'):
            research_sources.receive(self.sidecar, self.data, apply=True)
        self.assertEqual(self.ledger(), before)

    def test_unreceived_source_unsafe_path_and_url_reject_without_queueing(self):
        before, queue = self.ledger(), self.queue()
        original_row = dict(self.payload['items'][0])
        for field, value, error in (
            ('input_path', '../source.html', 'invalid_source_path'),
            ('url', 'javascript:alert(1)', 'invalid_source_url'),
            ('url', 'https://user:secret@example.test/', 'invalid_source_url'),
            ('url', 'https://example.test:bad/', 'invalid_source_url')):
            self.payload['items'][0] = {**original_row, field: value}
            self.save()
            with self.assertRaisesRegex(ValueError, error):
                research_sources.receive(self.sidecar, self.data, apply=True)
            self.assertEqual(self.ledger(), before)
        (self.base / 'linked.html').symlink_to(self.original)
        self.payload['items'][0] = {**original_row, 'input_path': 'linked.html'}
        self.save()
        with self.assertRaisesRegex(ValueError, 'source_symlink'):
            research_sources.receive(self.sidecar, self.data, apply=True)
        unknown = self.base / 'unknown.txt'
        unknown.write_text('Not received')
        self.payload['items'][0] = {**original_row, 'input_path': 'unknown.txt',
                                    'sha256': hash_file(unknown), 'original_sha256': hash_file(unknown)}
        self.save()
        with self.assertRaisesRegex(ValueError, 'source_research_not_received'):
            research_sources.receive(self.sidecar, self.data, apply=True)
        self.assertEqual(self.ledger(), before)
        self.assertEqual(self.queue(), queue)

    def test_cli_metadata_mode_does_not_extract_match_or_open_reader(self):
        args = ['research-match', '--source-sidecar', str(self.sidecar),
                '--data-root', str(self.data), '--apply-sources']
        output = io.StringIO()
        with patch.object(sys, 'argv', args), patch('sys.stdout', output), \
             patch.object(research_match, 'pages', side_effect=AssertionError('no extraction')):
            self.assertEqual(research_match.main(), 0)
        receipt = json.loads(output.getvalue())
        self.assertEqual(json.loads(Path(receipt['receipt']).read_text())['processed'], 2)
        self.assertFalse((self.data / 'catalog').exists())
