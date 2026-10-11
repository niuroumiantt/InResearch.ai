"""A supplied original can request exact work without becoming its answer."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from inresearch.delivery import reader_export
from inresearch.knowledge import registry
from inresearch.materials import demand_bindings
from inresearch.paths import project_root
from inresearch.workflow import research_match, research_sources


class DemandBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.data = self.base / 'data'; self.root = project_root()
        self.original = self.base / 'native-log.txt'
        self.original.write_text('Completed tokens per second: 31106.28\nResult is : VALID\n')
        self.item = research_match.ingest(self.original, self.data, self.root, defer_reader=True)
        target_doc = json.loads((self.root / 'framework/tco_targets.json').read_text())
        target, request = next((t, r) for t in target_doc['targets'] for r in t['request']['requirements']
                               if r['model_input'] == 'tokens_per_gpu_sec')
        self.request = dict(target_version=target_doc['version'], target_id=target['id'], requirement_id=request['id'],
                            requirement_sha256=demand_bindings.requirement_digest(request),
                            question_id=request['question_ids'][0],
                            scope_values={f: 'Explicit test scope: ' + f for f in request['scope_fields']},
                            purpose='Read the native benchmark and its limits; do not change the model.')
        sha = self.item['sha256']
        self.payload = dict(batch='demand-binding-fixture', items=[dict(input_path=self.original.name,
            sha256=sha, original_sha256=sha, source_id='native-log', role='downloaded_original',
            url='https://example.test/native-log', research_requests=[self.request])])
        self.sidecar = self.base / 'sources.json'; self.save()

    def save(self):
        self.sidecar.write_text(json.dumps(self.payload, ensure_ascii=False))

    def metadata(self):
        with sqlite3.connect(self.data / 'acquisition/catalog.sqlite') as db:
            return db.execute('SELECT url,metadata FROM items ORDER BY id').fetchall()

    def receive(self, apply=True):
        return research_sources.receive(self.sidecar, self.data, root=self.root, apply=apply)

    def test_unmatched_original_is_bound_before_explicit_reader_enrollment(self):
        before = {p: (self.root / p).read_bytes() for p in ('data/datacenter_model.json', 'data/research_knowledge.json')}
        self.assertEqual(self.item['matches'], [])
        self.assertFalse((self.data / 'raw-materials').exists())
        metadata = self.metadata(); self.receive(apply=False)
        self.assertEqual(metadata, self.metadata())
        receipt = self.receive(); self.assertEqual(receipt['results'][0]['research_requests'], 1)
        self.assertFalse((self.data / 'raw-materials').exists())
        objective = research_match.reading_objective(self.data, self.root, self.item['sha256'])
        requested = objective['explicit_research_requests'][0]
        self.assertEqual((requested['source_team'], requested['team_state']), ('fetchreports', 'not_connected'))
        self.assertEqual(requested['requirement_id'], self.request['requirement_id'])
        self.assertEqual(requested['scope_values'], self.request['scope_values'])
        self.assertEqual(requested['relationship'], 'requested_reading_only')
        self.assertEqual(objective['demand_priority'], 8)
        research_match.ingest(self.original, self.data, self.root)
        intake = list((self.data / 'raw-materials').rglob('*.txt'))
        self.assertEqual(len(intake), 1); self.assertEqual(intake[0].read_bytes(), self.original.read_bytes())
        self.assertEqual(self.receive()['filled'], 0)
        self.assertEqual(before, {p: (self.root / p).read_bytes() for p in before})

    def test_bad_scope_version_question_definition_and_injected_owner_leave_ledger_unchanged(self):
        bad = [dict(target_version='old'), dict(requirement_sha256='0' * 64),
               dict(question_id='not-reviewed'), dict(scope_values={'project': 'wrong workload'}),
               dict(provider_id='fetchspec'), dict(scope_values={k: '' for k in self.request['scope_values']}),
               dict(purpose='a' * 12001)]
        before = self.metadata()
        for changes in bad:
            with self.subTest(changes=changes):
                self.payload['items'][0]['research_requests'] = [dict(self.request, **changes)]; self.save()
                with self.assertRaises(ValueError): self.receive()
                self.assertEqual(self.metadata(), before)
                self.assertFalse((self.data / 'material-reviews/source-sidecars').exists())
                self.assertFalse((self.data / 'raw-materials').exists())

    def test_sidecar_tampering_is_rejected_by_projection_objective_and_enrollment(self):
        self.receive()
        with sqlite3.connect(self.data / 'acquisition/catalog.sqlite') as db:
            metadata = json.loads(db.execute('SELECT metadata FROM items').fetchone()[0])
            metadata['research_requests'][0]['scope_values']['hardware'] = 'different hardware'
            db.execute('UPDATE items SET metadata=?', (json.dumps(metadata),))
        self.assertEqual(reader_export.supplied_sources(self.data), {})
        with self.assertRaisesRegex(ValueError, 'source_binding_unavailable'):
            research_match.reading_objective(self.data, self.root, self.item['sha256'])
        with self.assertRaisesRegex(ValueError, 'source_binding_unavailable'):
            research_match.ingest(self.original, self.data, self.root)
        self.assertFalse((self.data / 'raw-materials').exists())

    def test_binding_reaches_candidate_and_review_packet_without_adoption_authority(self):
        from inresearch.workflow.reader import Reader
        from test_continuous_reader import Model
        from inresearch.workflow.research_review import ReviewStore
        self.receive(); research_match.ingest(self.original, self.data, self.root)
        model = Model()
        reader = Reader(self.data, self.base / 'state', self.root, model=model, stable_seconds=0).initialize()
        self.addCleanup(reader.close)
        reader.run(once=True)
        doc = reader.doc('doc-' + self.item['sha256'])
        context_path = reader.artifact_path(doc['doc_id'], 'context.json')
        frozen = context_path.read_bytes()
        context = json.loads(frozen)
        self.assertEqual(context['explicit_research_requests'][0]['requirement_id'], self.request['requirement_id'])
        for stage, payload in model.calls:
            if stage in ('triage', 'read'):
                self.assertEqual(payload['research_requests'], context['explicit_research_requests'])
                self.assertEqual(payload['allowed_ids']['reading_contract'], 'skeleton-demand-v2')
                self.assertIn(self.request['question_id'], {q['id'] for q in payload['allowed_ids']['questions']})
        report = json.loads(reader.artifact_path(doc['doc_id'], 'report.json').read_text())
        self.assertEqual(report['explicit_research_requests'], context['explicit_research_requests'])
        research_match.ingest(self.original, self.data, self.root); reader.scan()
        self.assertEqual(context_path.read_bytes(), frozen)
        export = reader.export_snapshot()
        document = next(d for d in export['knowledge']['documents'] if d['id'] == doc['doc_id'])
        self.assertEqual(document['research_requests'], [self.request])
        normalized = registry.candidate_snapshot(export,
            json.loads((self.root / 'framework/research_graph.json').read_text()),
            json.loads((self.root / 'framework/research_questions.json').read_text()))
        self.assertEqual(normalized['knowledge']['documents'][0]['status'], 'candidate')
        store = ReviewStore(self.data); self.addCleanup(store.db.close)
        batch = dict(id='a' * 64, doc_id=doc['doc_id'], revision_id=doc['revision_id'],
                     report_sha=doc['report_sha256'], candidate_ids=json.dumps([s['id'] for s in export['knowledge']['statements']]))
        packet = store.packet(self.root, batch)
        self.assertEqual(packet['document']['research_requests'], [self.request])
        self.assertTrue(all(x['candidate']['status'] == 'candidate' for x in packet['items']))

    def test_binding_content_change_cannot_overwrite_received_source_or_scope(self):
        self.receive(); before = self.metadata()
        altered = copy.deepcopy(self.payload)
        altered['items'][0]['research_requests'][0]['scope_values']['hardware'] = 'Different source scope'
        self.sidecar.write_text(json.dumps(altered))
        with self.assertRaisesRegex(ValueError, 'source_provenance_conflict'): self.receive()
        self.assertEqual(self.metadata(), before)
