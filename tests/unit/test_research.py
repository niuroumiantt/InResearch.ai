import copy
import http.client
import os
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from inresearch.knowledge import registry as research
from inresearch.workflow import reading_queue as reading_queue
from inresearch.interfaces import http as serve


def complete_document(sha='a' * 64):
    return {'id': 'doc-' + sha, 'content_sha256': sha,
            'title': 'Original fixture', 'coverage': {
                'complete': True, 'pages_total': 2, 'pages_read': 2,
                'chunks_total': 3, 'chunks_read': 3,
                'characters_total': 100, 'characters_read': 100}}


def adopted_knowledge():
    """A valid control; mutating one link must reopen the question."""
    review = {'by': 'test-owner', 'tier': 'A', 'at': '2026-09-06T00:00:00+00:00',
              'authority': 'owner', 'decision': 'adopted'}
    doc = complete_document()
    evidence = {'id': 'ev:reviewed', 'document_id': doc['id'], 'page_index': 0,
                'locator': 'p1/table1', 'quote': 'Original fixture quotation',
                'status': 'adopted', 'review': copy.deepcopy(review)}
    statement = {'id': 'statement:reviewed', 'text': 'Original bounded assertion',
                 'evidence_ids': [evidence['id']], 'status': 'adopted',
                 'review': copy.deepcopy(review)}
    answer = {'id': 'answer:reviewed', 'question_id': 'M01-Q01',
              'text': 'A reviewed answer with original evidence',
              'evidence_ids': [evidence['id']], 'statement_ids': [statement['id']],
              'status': 'adopted', 'review': copy.deepcopy(review)}
    return {'documents': [doc], 'evidence': [evidence],
            'statements': [statement], 'answers': [answer]}


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.graph = research.read_json(research.ROOT / 'framework/research_graph.json')
        self.questions = research.read_json(research.ROOT / 'framework/research_questions.json')
        self.knowledge = {key: [] for key in research.COLLECTIONS}

    def candidate(self):
        self.knowledge['documents'] = [{'id': 'doc:test', 'coverage': {'complete': False}}]
        self.knowledge['evidence'] = [{'id': 'ev:test', 'document_id': 'doc:test', 'page_index': 0}]
        self.knowledge['answers'] = [{'id': 'answer:test', 'question_id': 'M01-Q01',
                                      'text': 'Candidate only', 'evidence_ids': ['ev:test'],
                                      'status': 'adopted', 'review': {'by': 'model', 'tier': 'A', 'at': 'today'}}]
        return {'generated': '2026-09-06T00:00:00+00:00', 'graph_version': self.graph['version'], 'questions_version': self.questions['version'],
                'knowledge': self.knowledge, 'reader': {'status': 'idle'}}

    def test_registry_and_stable_legacy_identity(self):
        self.assertEqual([], research.validate(self.graph, self.questions, self.knowledge))
        self.assertEqual(116, sum(q.get('origin') == 'legacy-module' for q in self.questions['records']))
        coldplate = [q for q in self.questions['records'] if q['object_ids'] == ['part:coldplate']]
        self.assertEqual(5, len(coldplate))
        self.assertTrue(all(q['id'].startswith('OBJ-coldplate-') for q in coldplate))

    def test_containment_cycle_and_multiple_parent_rejected(self):
        self.graph['relations'].append({'id': 'bad', 'type': 'part_of', 'source': 'part:rack-frame',
            'target': 'part:server', 'configuration_id': 'template:dc-v2'})
        self.assertTrue(any('cycle' in e for e in research.validate(self.graph, self.questions, self.knowledge)))

    def test_model_cannot_adopt_or_close_question(self):
        snapshot = research.candidate_snapshot(self.candidate(), self.graph, self.questions)
        self.assertEqual('candidate', snapshot['knowledge']['answers'][0]['status'])
        self.assertNotIn('review', snapshot['knowledge']['answers'][0])
        self.assertEqual(set(), research.completed_questions(snapshot['knowledge']))

    def test_reading_revision_survives_receipt_without_replacing_adopted_evidence(self):
        curated=adopted_knowledge()
        candidate=copy.deepcopy(curated)
        candidate['documents'][0].update(reading_revision_id='rev-new',report_sha256='b'*64)
        candidate['evidence'][0].update(id='rev-new:ev:1',reading_revision_id='rev-new')
        candidate['statements']=[];candidate['answers']=[]
        payload=dict(generated=datetime.now(timezone.utc).isoformat(),graph_version=self.graph['version'],
                     questions_version=self.questions['version'],knowledge=candidate)
        normalized=research.candidate_snapshot(payload,self.graph,self.questions)['knowledge']
        self.assertEqual(normalized['documents'][0]['reading_revision_id'],'rev-new')
        self.assertEqual(normalized['evidence'][0]['reading_revision_id'],'rev-new')
        self.assertEqual(normalized['evidence'][0]['status'],'candidate')
        merged=research.merge_knowledge(curated,normalized)
        self.assertEqual(merged['evidence'][0],curated['evidence'][0])
        self.assertEqual(merged['answers'],curated['answers'])
        self.assertEqual(len(merged['documents']),1)
        self.assertEqual(len(merged['evidence']),2)

    def test_dangling_source_and_unknown_mapping_rejected(self):
        payload = self.candidate()
        payload['knowledge']['evidence'][0]['document_id'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'original document'):
            research.candidate_snapshot(payload, self.graph, self.questions)
        payload = self.candidate()
        payload['knowledge']['documents'][0]['object_ids'] = ['invented:part']
        with self.assertRaisesRegex(ValueError, 'object_ids'):
            research.candidate_snapshot(payload, self.graph, self.questions)

    def test_original_locator_required(self):
        payload = self.candidate()
        del payload['knowledge']['evidence'][0]['page_index']
        with self.assertRaisesRegex(ValueError, 'locator'):
            research.candidate_snapshot(payload, self.graph, self.questions)

    def test_low_scores_are_read_and_paths_are_not_completion(self):
        row = {'depth': '半自动', 'importance': '1', 'new_path': 'a.pdf'}
        self.assertTrue(reading_queue.eligible(row))
        self.assertFalse(reading_queue.proven_complete(row, [{'stored_path': 'a.pdf', 'coverage': {'complete': False}}]))
        row['doc_id'] = 'doc:test'
        self.assertFalse(reading_queue.proven_complete(row, [{'id': 'doc:test', 'coverage': {'complete': True, 'chunks_total': 2, 'chunks_read': 1}}]))

    def test_foreign_framework_snapshot_rejected(self):
        payload = self.candidate()
        payload['graph_version'] = 'old'
        with self.assertRaisesRegex(ValueError, 'graph_version'):
            research.candidate_snapshot(payload, self.graph, self.questions)


    def test_complete_reading_requires_pages_characters_chunks_and_content_hash(self):
        document = complete_document()
        row = {'doc_id': document['id'], 'depth': '半自动', 'importance': '1'}
        self.assertTrue(reading_queue.proven_complete(row, [document]))
        payload = self.candidate()
        payload['knowledge'] = {key: [] for key in research.COLLECTIONS}
        payload['knowledge']['documents'] = [document]
        self.assertTrue(research.candidate_snapshot(payload, self.graph, self.questions)
                        ['knowledge']['documents'][0]['coverage']['complete'])

        mutations = [
            ('unread_page', ('coverage', 'pages_read'), 1),
            ('unread_characters', ('coverage', 'characters_read'), 99),
            ('unread_chunk', ('coverage', 'chunks_read'), 2),
            ('missing_page_count', ('coverage', 'pages_total'), None),
            ('bool_is_not_page_count', ('coverage', 'pages_read'), True),
            ('zero_chunks', ('coverage', 'chunks_total'), 0),
            ('missing_hash', ('content_sha256',), None),
            ('invalid_hash', ('content_sha256',), 'not-a-content-hash'),
            ('different_content_identity', ('content_sha256',), 'b' * 64),
        ]
        for name, path, value in mutations:
            with self.subTest(case=name):
                broken = copy.deepcopy(document)
                target = broken[path[0]] if len(path) == 2 else broken
                key = path[-1]
                if value is None:
                    target.pop(key, None)
                else:
                    target[key] = value
                self.assertFalse(reading_queue.proven_complete(row, [broken]))
                bad_payload = copy.deepcopy(payload)
                bad_payload['knowledge']['documents'] = [broken]
                with self.assertRaises(ValueError):
                    research.candidate_snapshot(bad_payload, self.graph, self.questions)

    def test_valid_adoption_closes_only_its_reviewed_question(self):
        knowledge = adopted_knowledge()
        self.assertEqual([], research.validate(self.graph, self.questions, knowledge))
        self.assertEqual({'M01-Q01'}, research.completed_questions(knowledge))
        task_ids = {task['question_ids'][0] for task in research.question_tasks(self.questions, knowledge)}
        self.assertNotIn('M01-Q01', task_ids)
        self.assertIn('M01-Q02', task_ids)

    def test_withdrawn_or_invalid_original_evidence_reopens_question(self):
        cases = [
            ('evidence', 'status', 'withdrawn'),
            ('evidence', 'status', 'needs_review'),
            ('evidence', 'status', 'candidate'),
            ('evidence', 'page_index', -500),
            ('evidence', 'page_index', True),
            ('evidence', 'page_index', 2),
            ('evidence', 'page_index', 999),
            ('evidence', 'quote', ''),
            ('evidence', 'quote', None),
            ('evidence', 'content_sha256', 'b' * 64),
            ('statements', 'status', 'superseded'),
            ('statements', 'status', 'withdrawn'),
            ('statements', 'review', {}),
            ('statements', 'statement_ids', ['statement:reviewed']),
            ('evidence', 'review', {}),
            ('documents', 'status', 'withdrawn'),
            ('documents', 'status', 'rejected'),
            ('documents', 'content_sha256', ''),
        ]
        for table, field, value in cases:
            with self.subTest(table=table, field=field, value=value):
                knowledge = adopted_knowledge()
                knowledge[table][0][field] = value
                self.assertNotIn('M01-Q01', research.completed_questions(knowledge))
                self.assertTrue(research.validate(self.graph, self.questions, knowledge))
                self.assertIn('M01-Q01', {task['question_ids'][0]
                              for task in research.question_tasks(self.questions, knowledge)})
        for missing in ('evidence', 'documents', 'statements'):
            with self.subTest(missing=missing):
                knowledge = adopted_knowledge()
                knowledge[missing] = []
                self.assertEqual(set(), research.completed_questions(knowledge))
                self.assertTrue(research.validate(self.graph, self.questions, knowledge))

    def test_invalid_C3_review_never_closes_question(self):
        cases = [
            {'by': 'model', 'tier': 'A', 'at': 'today'},
            {'at': 'not-a-date'}, {'at': '2026-09-06T00:00:00'},
            {'tier': 'invented'}, {'authority': 'worker'},
            {'tier': 'A', 'authority': 'reviewer'},
            {'decision': 'candidate'}, {'by': ''}, {'by': '   '}, {'tier': 'C'},
        ]
        for override in cases:
            for table in ('answers', 'statements', 'evidence'):
                with self.subTest(table=table, override=override):
                    knowledge = adopted_knowledge()
                    knowledge[table][0]['review'].update(override)
                    self.assertEqual(set(), research.completed_questions(knowledge))
                    self.assertTrue(research.validate(self.graph, self.questions, knowledge))

    def test_C_archive_cannot_close_and_valid_B_reopens_then_closes(self):
        knowledge = adopted_knowledge()
        for table in ('evidence', 'statements', 'answers'):
            knowledge[table][0]['review'].update(tier='B', authority='reviewer')
        self.assertEqual({'M01-Q01'}, research.completed_questions(knowledge))
        for malformed in (None, [], 'review', {'tier': 'C'}):
            broken = copy.deepcopy(knowledge)
            broken['statements'][0]['review'] = malformed
            self.assertEqual(set(), research.completed_questions(broken))
            tasks = research.question_tasks(self.questions, broken)
            self.assertIn('Q-M01-Q01', {t['wid'] for t in tasks})
        self.assertEqual({'M01-Q01'}, research.completed_questions(knowledge))


class MutationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        (self.root / 'reports').mkdir()
        research.atomic_json(self.root / 'data/prices.json', {'records': []})
        research.atomic_json(self.root / 'data/assignments.json', {'records': [
            {'workorder_id': 'test', 'assignee': 'alice', 'status': '已派'}]})
        research.atomic_json(self.root / 'reports/workorders.json', {'orders': [{'wid': 'test'}]})
        research.atomic_json(self.root / 'framework/research_questions.json', {'records': []})
        research.atomic_json(self.root / 'data/research_knowledge.json', {key: [] for key in research.COLLECTIONS})
        self.root_patch = patch.object(serve, 'ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def handler(self):
        handler = object.__new__(serve.Handler)
        handler._json = lambda code, data: (code, data)
        return handler

    def test_intern_cannot_merge_or_reassign(self):
        with patch.object(serve.auth, 'user_role', return_value='intern'):
            h = self.handler()
            self.assertEqual(403, h.api_assign({'workorder_id': 'test', 'status': '已合并'}, by='alice')[0])
            self.assertEqual(403, h.api_assign({'workorder_id': 'test', 'status': '已交付'}, by='bob')[0])
            self.assertEqual(200, h.api_assign({'workorder_id': 'test', 'status': '已交付'}, by='alice')[0])

    def test_price_concurrency_and_nonfinite(self):
        def record(i):
            return dict(series_id=f's{i}', as_of='2026-09-06', value=i, unit='USD',
                        grade='company', source_url='https://example.test', category='gpu', module='M06')
        with patch.object(serve.subprocess, 'run') as runner:
            runner.return_value.returncode = 0
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda i: self.handler().api_add_price(record(i)), range(20)))
            self.assertTrue(all(code == 200 for code, _ in results))
            self.assertEqual(20, len(research.read_json(self.root / 'data/prices.json')['records']))
            self.assertEqual(409, self.handler().api_add_price(record(0))[0])
            rec = record(21)
            rec['value'] = float('nan')
            self.assertEqual(400, self.handler().api_add_price(rec)[0])

    def test_new_question_is_assignable_without_regenerating_legacy_projection(self):
        questions = research.read_json(research.ROOT / 'framework/research_questions.json')
        research.atomic_json(self.root / 'framework/research_questions.json', questions)
        question = questions['records'][-1]
        wid = 'Q-' + question['id']
        self.assertIn(wid, {task['wid'] for task in research.current_tasks(self.root)})
        code, reply = self.handler().api_assign({'workorder_id': wid, 'assignee': 'alice', 'status': '已派'})
        self.assertEqual(200, code, reply)
        task = next(task for task in research.current_tasks(self.root) if task['wid'] == wid)
        self.assertEqual('alice', task['assignment']['assignee'])

    def test_export_uses_real_module_files(self):
        from inresearch.delivery import export as export
        with patch.object(export, 'OUT_DIR', self.root / 'export'), patch('sys.argv', ['export.py']):
            self.assertEqual(0, export.main())
        result = next((self.root / 'export').glob('*.md')).read_text()
        self.assertIn('## M01 ', result)
        self.assertIn('## M15 ', result)


class ReaderSnapshotHTTPTests(unittest.TestCase):
    """Exercise the real HTTP receiver and disk commit against an isolated root."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inresearch-snapshot-http-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.graph = research.read_json(research.ROOT / 'framework/research_graph.json')
        self.questions = research.read_json(research.ROOT / 'framework/research_questions.json')
        self.curated_path = self.root / 'data/research_knowledge.json'
        self.snapshot_path = self.root / 'data/research_runtime.json'
        self.token_path = self.root / 'reader-test-token'
        self.token = 'local-http-regression-only-' + '0' * 48
        self.token_path.write_text(self.token)
        for file, data in [
            ('framework/research_graph.json', self.graph),
            ('framework/research_questions.json', self.questions),
            ('data/research_knowledge.json', {key: [] for key in research.COLLECTIONS}),
            ('data/sources.json', {'records': []}),
            ('data/assignments.json', {'records': []}),
            ('reports/workorders.json', {'orders': []}),
        ]:
            research.atomic_json(self.root / file, data)
        self.base_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(serve, 'ROOT', self.root))
        stack.enter_context(patch.object(serve, 'AUTH_ON', False))
        stack.enter_context(patch.dict(os.environ, {
            'INRESEARCH_READER_TOKEN_FILE': str(self.token_path),
            'INRESEARCH_READER_SNAPSHOT': str(self.snapshot_path),
        }))
        self.server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': 0.02}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def payload(self, knowledge=None, seconds=0):
        return {'generated': (self.base_time + timedelta(seconds=seconds)).isoformat(),
                'graph_version': self.graph['version'],
                'questions_version': self.questions['version'],
                'knowledge': knowledge if knowledge is not None else adopted_knowledge(),
                'reader': {'status': 'idle'}}

    def request(self, method, path, payload=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=4)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def post(self, payload, token=None):
        return self.request('POST', '/api/reader-snapshot', payload,
                            self.token if token is None else token)

    def test_successful_http_receipt_is_candidate_only_and_bad_token_is_401(self):
        curated_before = self.curated_path.read_bytes()
        code, reply = self.post(self.payload())
        self.assertEqual(200, code, reply)
        self.assertEqual(1, reply['documents'])
        saved = research.read_json(self.snapshot_path)
        for table in research.COLLECTIONS:
            for record in saved['knowledge'][table]:
                self.assertEqual('candidate', record['status'])
                self.assertNotIn('review', record)
        self.assertEqual(curated_before, self.curated_path.read_bytes())
        self.assertEqual(set(), research.completed_questions(saved['knowledge']))
        before = self.snapshot_path.read_bytes()
        for name, token in [('wrong', 'wrong-token'), ('empty', ''), ('missing', None)]:
            with self.subTest(token=name):
                code, reply = self.request('POST', '/api/reader-snapshot',
                                           self.payload(seconds=1), token=token)
                self.assertEqual(401, code, reply)
                self.assertEqual(before, self.snapshot_path.read_bytes())
        code, view = self.request('GET', '/api/research')
        self.assertEqual(200, code, view)
        self.assertEqual('open', next(q['status'] for q in view['questions']['records']
                                     if q['id'] == 'M01-Q01'))

    def test_old_or_replayed_http_snapshot_is_409_and_cannot_erase_new_data(self):
        payload = self.payload(seconds=10)
        self.assertEqual(200, self.post(payload)[0])
        before = self.snapshot_path.read_bytes()
        for seconds in (9, 10):
            with self.subTest(seconds=seconds):
                old_empty = self.payload({key: [] for key in research.COLLECTIONS}, seconds=seconds)
                code, reply = self.post(old_empty)
                self.assertEqual(409, code, reply)
                self.assertEqual(before, self.snapshot_path.read_bytes())
        newer = self.payload(seconds=11)
        newer['knowledge']['documents'].append(complete_document('b' * 64))
        self.assertEqual(200, self.post(newer)[0])
        self.assertEqual(2, len(research.read_json(self.snapshot_path)['knowledge']['documents']))

    def test_identity_collision_is_rejected_before_snapshot_commit(self):
        curated = adopted_knowledge()
        research.atomic_json(self.curated_path, curated)
        self.assertEqual(200, self.post(self.payload(curated))[0])
        before = self.snapshot_path.read_bytes()
        curated_before = self.curated_path.read_bytes()
        for table, field, replacement in [
            ('documents', 'content_sha256', 'b' * 64),
            ('evidence', 'quote', 'Quotation from a different original'),
            ('statements', 'text', 'Different statement under the reviewed identity'),
            ('answers', 'question_id', 'M01-Q02'),
        ]:
            with self.subTest(table=table, field=field):
                # Reset only this isolated fixture so one failing case cannot mask the next.
                self.snapshot_path.write_bytes(before)
                collision = copy.deepcopy(curated)
                collision[table][0][field] = replacement
                if table == 'documents':
                    collision[table][0]['coverage'] = {'complete': False}
                code, reply = self.post(self.payload(collision, seconds=1))
                self.assertIn(code, (400, 409), reply)
                self.assertEqual(before, self.snapshot_path.read_bytes())
                self.assertEqual(curated_before, self.curated_path.read_bytes())
                code, view = self.request('GET', '/api/research')
                self.assertEqual(200, code, view)
                original = next(d for d in view['knowledge']['documents']
                                if d['id'] == curated['documents'][0]['id'])
                self.assertEqual('a' * 64, original['content_sha256'])

    def test_invalid_runtime_preserves_curated_http_view(self):
        curated = adopted_knowledge()
        research.atomic_json(self.curated_path, curated)
        valid = self.payload()
        foreign = copy.deepcopy(valid)
        foreign['graph_version'] = 'retired-version'
        collision = copy.deepcopy(valid)
        collision['knowledge']['evidence'][0]['quote'] = 'Unreviewed replacement quote'
        for name, content in [('malformed', '{'), ('foreign-framework', json.dumps(foreign)),
                              ('identity-collision', json.dumps(collision))]:
            with self.subTest(runtime=name):
                self.snapshot_path.write_text(content)
                code, view = self.request('GET', '/api/research')
                self.assertEqual(200, code, view)
                self.assertEqual(curated, {key: view['knowledge'][key] for key in research.COLLECTIONS})
                self.assertTrue(view['reader'].get('stale') or view['reader'].get('error')
                                or view['reader'].get('status') not in ('idle', 'running'))
                code, news = self.request('GET', '/api/news')
                self.assertEqual(code, 200)
                self.assertIsNone(news['feed'])
                self.assertEqual(news['reader']['status'], view['reader']['status'])
                code, summary = self.request('GET', '/api/research-summary')
                self.assertEqual(code, 200)
                self.assertEqual(summary['reader']['status'], view['reader']['status'])
                self.assertEqual([e['id'] for e in summary['knowledge']['evidence']], [e['id'] for e in curated['evidence']])

    def test_news_projection_uses_validated_input_without_catalog_tasks_or_private_metadata(self):
        payload = self.payload()
        payload['reader'].update(roots={'private': '/private/originals'}, acquisition={'news_feed': {
            'status': 'success', 'exported_at': datetime.now(timezone.utc).isoformat(),
            'internal_path': '/private/cache', 'items': [
                {'title_zh': str(i), 'title': 'unneeded original', 'url': 'https://example.test/' + str(i),
                 'domain': 'example.test', 'published_at': 1700000000000 + i, 'private': 'do not project'}
                for i in range(100)]}})
        self.assertEqual(self.post(payload)[0], 200)
        before = self.snapshot_path.read_bytes()
        with patch.object(research, 'build_catalog', side_effect=AssertionError('unneeded catalog')), \
                patch.object(research, 'current_tasks', side_effect=AssertionError('unneeded tasks')):
            code, news = self.request('GET', '/api/news')
        self.assertEqual(code, 200)
        self.assertEqual(set(news), {'schema_version', 'feed', 'reader'})
        self.assertEqual(len(news['feed']['items']), 80)
        self.assertEqual([item['title_zh'] for item in news['feed']['items']], [str(i) for i in range(99, 19, -1)])
        self.assertEqual(set(news['feed']), {'status', 'exported_at', 'items'})
        self.assertEqual(set(news['feed']['items'][0]), {'title_zh', 'url', 'domain', 'published_at'})
        code, full = self.request('GET', '/api/research')
        self.assertEqual(news['reader'], {key: full['reader'][key] for key in news['reader']})
        self.assertEqual(self.snapshot_path.read_bytes(), before)

    def test_news_missing_stale_fresh_replacement_and_replay_follow_one_snapshot(self):
        code, news = self.request('GET', '/api/news')
        self.assertEqual(code, 200)
        self.assertEqual(news['reader']['status'], 'not_connected')
        self.assertIsNone(news['feed'])
        payload = self.payload(seconds=1)
        payload['reader']['acquisition'] = {'news_feed': {'status': 'success',
            'exported_at': datetime.now(timezone.utc).isoformat(), 'items': [
                {'title_zh': 'old', 'url': 'https://example.test/old'}]}}
        self.assertEqual(self.post(payload)[0], 200)
        stored = research.read_json(self.snapshot_path)
        stored['received_at'] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        self.snapshot_path.write_text(json.dumps(stored))
        self.assertTrue(self.request('GET', '/api/news')[1]['reader']['stale'])
        new = copy.deepcopy(payload); new['generated'] = self.payload(seconds=2)['generated']
        new['reader']['acquisition']['news_feed']['items'][0]['title_zh'] = 'new'
        self.assertEqual(self.post(new)[0], 200)
        for old in (payload, new): self.assertEqual(self.post(old)[0], 409)
        news = self.request('GET', '/api/news')[1]
        self.assertFalse(news['reader']['stale'])
        self.assertEqual(news['feed']['items'][0]['title_zh'], 'new')

    def test_invalid_news_metadata_fails_the_view_without_rewriting_the_snapshot(self):
        for acquisition in (['unexpected'], {'news_feed': []}, {'news_feed': {'items': 'not-array'}},
                            {'news_feed': {'items': [None]}}):
            payload = self.payload(); payload['reader']['acquisition'] = acquisition
            self.snapshot_path.write_text(json.dumps(payload))
            before = self.snapshot_path.read_bytes()
            code, news = self.request('GET', '/api/news')
            self.assertEqual(code, 503)
            self.assertFalse(news['ok'])
            self.assertEqual(self.snapshot_path.read_bytes(), before)


    def test_summary_obeys_research_auth_boundary_before_building_state(self):
        with patch.object(serve, 'AUTH_ON', True), \
                patch.object(research, 'build_research_summary', side_effect=AssertionError('unauthorized read')):
            self.assertEqual(self.request('GET', '/api/research-summary')[0], 401)
            with patch.object(serve.auth, 'session_user', return_value='intern'), \
                    patch.object(serve.auth, 'user_role', return_value='intern'):
                connection = http.client.HTTPConnection(*self.server.server_address, timeout=4)
                try:
                    connection.request('GET', '/api/research-summary')
                    response = connection.getresponse()
                    self.assertEqual(response.status, 403)
                    response.read()  # The existing role gate returns its forbidden HTML page.
                finally:
                    connection.close()

    def test_research_summary_shares_state_but_omits_content_catalog_and_reader_payload(self):
        payload = self.payload()
        payload['reader']['private_large_state'] = 'PRIVATE_MARKER' * 10000
        payload['knowledge']['documents'][0]['stored_path'] = '/private/originals/PRIVATE_MARKER.pdf'
        self.assertEqual(self.post(payload)[0], 200)
        before = self.snapshot_path.read_bytes()
        code, full = self.request('GET', '/api/research')
        self.assertEqual(code, 200)
        with patch.object(research, 'build_catalog', side_effect=AssertionError('unneeded catalog')):
            code, summary = self.request('GET', '/api/research-summary')
        self.assertEqual(code, 200)
        self.assertNotIn('catalog', summary)
        self.assertNotIn('documents', summary['knowledge'])
        self.assertNotIn('PRIVATE_MARKER', json.dumps(summary))
        self.assertNotIn('quote', summary['knowledge']['evidence'][0])
        self.assertEqual([q['id'] for q in full['questions']['records']], [q['id'] for q in summary['questions']])
        for key in ('evidence', 'statements', 'answers'):
            self.assertEqual([row['id'] for row in full['knowledge'][key]], [row['id'] for row in summary['knowledge'][key]])
        self.assertEqual([row['wid'] for row in full['tasks']], [row['wid'] for row in summary['tasks']])
        self.assertEqual([row['id'] for row in full['graph']['objects']], [row['id'] for row in summary['graph']['objects']])
        self.assertEqual(self.snapshot_path.read_bytes(), before)

    def test_summary_new_snapshot_replaces_associations_and_failed_retry_keeps_authority(self):
        first = self.payload(seconds=1)
        self.assertEqual(self.post(first)[0], 200)
        code, old = self.request('GET', '/api/research-summary')
        self.assertEqual(code, 200)
        replacement = self.payload(seconds=2)
        replacement['knowledge']['answers'][0]['question_id'] = 'M02-Q01'
        self.assertEqual(self.post(replacement)[0], 200)
        current = self.snapshot_path.read_bytes()
        for payload in (first, replacement):
            self.assertEqual(self.post(payload)[0], 409)
        with patch.object(research, 'current_tasks', side_effect=OSError('temporary read failure')):
            self.assertEqual(self.request('GET', '/api/research-summary')[0], 503)
        code, new = self.request('GET', '/api/research-summary')
        self.assertEqual(code, 200)
        self.assertEqual(old['knowledge']['answers'][0]['question_id'], 'M01-Q01')
        self.assertEqual(new['knowledge']['answers'][0]['question_id'], 'M02-Q01')
        self.assertEqual(self.snapshot_path.read_bytes(), current)


if __name__ == '__main__':
    unittest.main()
