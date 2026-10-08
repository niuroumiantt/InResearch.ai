import copy
import json
import unittest
from unittest.mock import patch

from inresearch.knowledge import material_baseline as baseline, registry
from inresearch.interfaces import http as serve
from test_research import complete_document, adopted_knowledge
import test_research


def material():
    doc = complete_document()
    doc.update(read_status='complete', report_sha256='b' * 64, reading_revision_id='rev-2015',
               published_date='2015-04-01', stored_path='/private/original.pdf',
               source_url='https://example.org/report')
    ev = {'id': 'e1', 'document_id': doc['id'], 'page_index': 0,
          'quote': 'Original bounded source text.', 'status': 'candidate'}
    claim = {'id': 'c1', 'document_id': doc['id'], 'text': 'Historical source description',
             'kind': 'author_claim', 'object_ids': ['part:coldplate'],
             'evidence_ids': ['e1'], 'status': 'candidate'}
    return {'documents': [doc], 'evidence': [ev], 'statements': [claim], 'answers': []}


class MaterialBaselineTests(unittest.TestCase):
    def setUp(self):
        baseline.available_materials.cache_clear()
        self.addCleanup(baseline.available_materials.cache_clear)

    def test_old_material_usable_without_c3_and_never_closes_questions(self):
        knowledge = material(); before = copy.deepcopy(knowledge)
        rows, skipped = baseline.rows(knowledge, {})
        self.assertEqual(len(rows), 1); self.assertEqual(skipped, {})
        self.assertEqual(rows[0]['source_date'], '2015-04-01')
        self.assertEqual(rows[0]['status'], 'source_material')
        self.assertNotIn('stored_path', json.dumps(rows))
        self.assertFalse(registry.supported_adoption(rows[0], knowledge))
        self.assertEqual(registry.completed_questions(knowledge), set())
        self.assertEqual(knowledge, before)

    def test_missing_date_remains_unknown_and_unsafe_url_is_removed(self):
        knowledge = material(); doc = knowledge['documents'][0]
        doc.pop('published_date'); doc.update(created='2026-10-08', source_url='https://u:p@example.org/')
        row = baseline.rows(knowledge, {})[0][0]
        self.assertIsNone(row['source_date']); self.assertIsNone(row['source']['url'])

    def test_missing_or_mismatched_original_and_gap_pages_do_not_enter_baseline(self):
        for alter in (lambda k: k['evidence'][0].update(quote=''),
                      lambda k: k['evidence'][0].update(document_id='wrong'),
                      lambda k: k['evidence'][0].update(page_index=10),
                      lambda k: k['documents'][0]['coverage'].update(gap_pages=[1]),
                      lambda k: k['documents'][0].update(report_sha256=''),
                      lambda k: k['documents'][0].update(read_status='running'),
                      lambda k: k['statements'][0].update(object_ids=[])):
            knowledge = material(); alter(knowledge)
            self.assertEqual(baseline.rows(knowledge, {})[0], [])

    def test_current_snapshot_keeps_unadopted_claims_from_partly_adopted_document(self):
        knowledge = material(); curated = adopted_knowledge()
        curated['statements'][0]['source_candidate_ids'] = ['different-candidate']
        graph = registry.read_json(registry.ROOT / 'framework/research_graph.json')
        questions = registry.read_json(registry.ROOT / 'framework/research_questions.json')
        runtime = {'knowledge': knowledge, 'received_at': '2026-10-08T00:00:00Z'}
        with patch.object(registry, '_snapshot_inputs', return_value=(graph, questions, curated, curated, runtime)):
            result = baseline.for_node(registry.ROOT, 'part:coldplate')
            self.assertEqual(result['total'], 1)
            self.assertTrue(baseline.for_node(registry.ROOT, 'missing')['unknown'])
            self.assertEqual(baseline.for_node(registry.ROOT, 'part:gpu')['total'], 0)

    def test_adopted_source_candidate_not_double_counted(self):
        curated = adopted_knowledge(); curated['statements'][0]['source_candidate_ids'] = ['c1']
        self.assertEqual(baseline.rows(material(), curated)[0], [])

    def test_pagination_search_and_unknown_year_keep_all_records(self):
        knowledge = material()
        knowledge['statements'] += [{**knowledge['statements'][0], 'id': 'c2', 'text': 'Other source'}]
        graph = registry.read_json(registry.ROOT / 'framework/research_graph.json')
        questions = registry.read_json(registry.ROOT / 'framework/research_questions.json')
        with patch.object(registry, '_snapshot_inputs', return_value=(graph, questions, {}, {}, {'knowledge': knowledge})):
            result = baseline.for_node(registry.ROOT, limit=1)
            self.assertEqual(result['total'], 2); self.assertEqual(result['next_offset'], 1)
            self.assertEqual(baseline.for_node(registry.ROOT, offset=1, limit=1)['records'][0]['id'], 'c2')
            self.assertEqual(baseline.for_node(registry.ROOT, query='HISTORICAL')['total'], 1)

    def test_new_snapshot_version_invalidates_material_cache(self):
        knowledge = material()
        graph = registry.read_json(registry.ROOT / 'framework/research_graph.json')
        questions = registry.read_json(registry.ROOT / 'framework/research_questions.json')
        with patch.object(registry, '_snapshot_inputs', return_value=(graph, questions, {}, {}, {'knowledge': knowledge})) as load, \
             patch.object(baseline, 'input_version', return_value=('old',)) as version:
            self.assertEqual(baseline.for_node(registry.ROOT)['total'], 1)
            baseline.for_node(registry.ROOT, offset=1)
            self.assertEqual(load.call_count, 1)
            knowledge['statements'].append({**knowledge['statements'][0], 'id': 'c2'})
            version.return_value = ('new',)
            self.assertEqual(baseline.for_node(registry.ROOT)['total'], 2)
            self.assertEqual(load.call_count, 2)

    def test_http_filters_and_existing_login_gate(self):
        case = test_research.ReaderSnapshotHTTPTests(); case.setUp(); self.addCleanup(case.doCleanups)
        result = {'total': 0, 'records': []}
        with patch.object(baseline, 'for_node', return_value=result) as query:
            code, body = case.request('GET', '/api/research-materials?node=root&offset=1&limit=2')
            self.assertEqual(code, 200); self.assertEqual(body, result)
            query.assert_called_once_with(case.root, 'root', offset=1, limit=2, query='')
            for suffix in ('?offset=-1', '?limit=51', '?node=a&node=b', '?offset=oops'):
                self.assertEqual(case.request('GET', '/api/research-materials' + suffix)[0], 400)
            with patch.object(serve, 'AUTH_ON', True), patch.object(serve.auth, 'session_user', return_value=None):
                self.assertEqual(case.request('GET', '/api/research-materials')[0], 401)
