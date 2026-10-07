"""Batched inference preserves per-page evidence, leases and frozen recipes."""
import contextlib
import io
import threading
import unittest
from unittest import mock
import test_continuous_reader as fixtures
from inresearch.materials.artifacts import read_json
from inresearch.materials.reader_contracts import Deferred, TransientModelError
from inresearch.adapters.reader_model import _schema
from inresearch.adapters.codex_inference import strict_schema, validate_shape
from inresearch.adapters.models import InferenceError


class ReadBatchTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ReaderTests(); self.f.setUp(); self.addCleanup(self.f.tearDown)
        self.r = self.f.reader
        self.r.stages.pdf_mode = 'native_text_only'
        self.r.stages.read_batch_chunks = 4
        self.texts = ['Page %d: capacity %dMW IT, power %dMW.\n' % (i, i*10, i*12) for i in range(1, 9)]
        self.batch_calls = []
        self.base_generate = self.f.model.generate
        self.f.model.generate = self.generate
        self.f.put('paper.pdf', '%PDF original stays unchanged')
        self.f.reader.scan()

    def generate(self, stage, payload, retry_instruction=None):
        if stage != 'read_batch':
            return self.base_generate(stage, payload, retry_instruction)
        self.batch_calls.append(payload)
        return {'chunks': [dict(self.base_generate('read', p), chunk_index=p['chunk_index']) for p in payload['chunks']],
                '_model': {'backend': 'injected_test', 'actual': self.f.model.identity['model']}}

    def command(self, args, **kw):
        if args[0] == 'pdfinfo': return 'Pages: %d\n' % len(self.texts)
        if args[0] == 'pdfimages': return ''
        if args[0] == 'pdftotext': return '\f'.join(self.texts) + '\f'
        raise AssertionError(args)

    def prepare(self):
        with mock.patch('inresearch.workflow.reading_stages.shutil.which', return_value='/tool'), \
                mock.patch.object(self.r.stages, '_command', side_effect=self.command):
            for stage in ('extract', 'triage'):
                job = self.r.claim(); self.assertEqual(job['stage'], stage)
                self.assertEqual(self.r.process(job), 'succeeded')
        return self.r.doc(self.f.first_doc()['doc_id'])

    def finish(self):
        with contextlib.redirect_stdout(io.StringIO()): self.f.run_reader()
        doc = self.r.doc(self.f.first_doc()['doc_id'])
        self.assertEqual(doc['state'], 'complete')
        return self.r.stages.verify_seal(doc)

    def test_batch_reduces_calls_but_every_page_and_quote_remain_sealed(self):
        doc = self.prepare(); raw = (self.r.data / doc['original_rel']).read_bytes()
        report = self.finish()
        self.assertEqual(len(self.batch_calls), 2)
        self.assertEqual(report['coverage']['chunks_read'], 8)
        self.assertEqual([e['page_index'] for e in report['evidence']], list(range(1, 9)))
        for e in report['evidence']:
            self.assertIn(e['quote'], self.texts[e['page_index'] - 1])
        self.assertEqual((self.r.data / doc['original_rel']).read_bytes(), raw)
        self.assertFalse(report['coverage']['visual_review_performed'])

    def test_adjacent_jobs_are_leased_once_and_never_cross_documents(self):
        self.prepare()
        first = self.r.claim(); second = self.r.claim()
        a = {j['chunk'] for j in [first, *first['batch_jobs']]}
        b = {j['chunk'] for j in [second, *second['batch_jobs']]}
        self.assertFalse(a & b); self.assertEqual(a | b, set(range(8)))
        self.assertEqual(self.r.conn.execute("select count(*) from jobs where state='running'").fetchone()[0], 8)
        self.assertIsNone(self.r.claim())
        with contextlib.redirect_stdout(io.StringIO()):
            self.r.process(first); self.r.process(second)
        self.finish()

    def test_parallel_claims_are_disjoint_and_crash_reuses_checked_artifacts(self):
        doc = self.prepare(); jobs = []
        def claim():
            jobs.append(self.r.claim()); self.r.catalog._close_thread()
        threads = [threading.Thread(target=claim) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        groups = [[j, *j['batch_jobs']] for j in jobs]
        self.assertEqual(len({m['job_id'] for g in groups for m in g}), 8)
        # Simulate process death after model output persisted, before DB completion.
        for group in groups:
            with contextlib.redirect_stdout(io.StringIO()):
                self.r.stages._read_batch(doc, [j['chunk'] for j in group])
        calls = len(self.batch_calls)
        self.finish()
        self.assertEqual(len(self.batch_calls), calls)

    def test_partial_member_failure_keeps_other_pages_and_only_failed_page_retries(self):
        self.prepare(); job = self.r.claim()
        def fail(stage, payload, retry_instruction=None):
            out = self.generate(stage, payload, retry_instruction)
            if stage == 'read_batch': out['chunks'][0]['summary'] = None
            elif stage == 'read' and payload['chunk_index'] == 0:
                raise TransientModelError('model_cli_timeout')
            return out
        with mock.patch.object(self.f.model, 'generate', side_effect=fail), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.r.process(job), 'batch_partial')
        self.assertEqual(self.r.doc(job['doc_id'])['chunks_read'], 3)
        self.f.clock.advance(100)
        self.finish()

    def test_character_limit_and_unavailable_neighbor_are_respected(self):
        self.prepare()
        self.r.conn.execute("update jobs set available=99999 where stage='read' and chunk=1")
        job = self.r.claim(); self.assertEqual(job['chunk'], 0); self.assertNotIn('batch_jobs', job)
        self.r.process(job)
        job = self.r.claim(); self.assertEqual([j['chunk'] for j in [job, *job['batch_jobs']]], [2,3,4,5])

    def test_oversized_short_page_group_does_not_exceed_frozen_budget(self):
        # The policy was frozen at registration, so use a fresh explicit revision.
        old = self.r.doc(self.f.first_doc()['doc_id'])
        self.r.stages.read_batch_chars = len(self.texts[0]) + len(self.texts[1])
        self.r.revisions.restart_unfinished(old['doc_id'], old['revision_id'], 'small-budget', 'bounded test')
        self.prepare()
        job = self.r.claim(); self.assertEqual(len(job['batch_jobs']), 1)

    def test_malformed_members_and_timeout_fall_back_without_false_completion(self):
        self.prepare()
        for error in ('missing', 'timeout'):
            job = self.r.claim()
            def fail(stage, payload, retry_instruction=None):
                if stage == 'read_batch':
                    if error == 'timeout': raise TransientModelError('model_cli_timeout')
                    return {'chunks': []}
                return self.base_generate(stage, payload, retry_instruction)
            with mock.patch.object(self.f.model, 'generate', side_effect=fail), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.r.process(job), 'succeeded')
        self.finish()

    def test_cross_chunk_quote_is_rejected_and_other_checked_members_survive(self):
        self.prepare(); job = self.r.claim()
        def cross(stage, payload, retry_instruction=None):
            result = self.generate(stage, payload, retry_instruction)
            if stage == 'read_batch':
                result['chunks'][0]['claims'][0]['evidence'][0]['quote'] = payload['chunks'][1]['text'].strip()
            elif stage == 'read' and payload['chunk_index'] == 0:
                result['claims'][0]['evidence'][0]['quote'] = self.texts[1].strip()
            return result
        with mock.patch.object(self.f.model, 'generate', side_effect=cross), contextlib.redirect_stdout(io.StringIO()):
            self.r.process(job)
        report = self.finish()
        self.assertEqual(report['coverage']['dropped_claims'], 1)
        self.assertEqual(len(report['claims']), 7)
        self.assertEqual(len(self.f.model.retry_instructions), 1)

    def test_quota_wait_returns_all_leases_without_consuming_attempts(self):
        self.prepare(); job = self.r.claim()
        with mock.patch.object(self.f.model, 'generate', side_effect=Deferred('model_quota_wait')):
            self.assertEqual(self.r.process(job), 'batch_partial')
        self.assertEqual(self.r.conn.execute("select sum(attempts) from jobs where stage='read'").fetchone()[0], 0)
        self.assertEqual(self.r.conn.execute("select count(*) from jobs where state='running'").fetchone()[0], 0)
        self.assertIsNone(self.r.claim())

    def test_legacy_recipe_stays_single_and_explicit_new_policy_preserves_history(self):
        # Create an old single-page recipe, not an in-place rewrite.
        self.r.stages.read_batch_chunks = 1
        self.f.put('legacy.pdf', '%PDF legacy original')
        self.r.scan()
        old = dict(self.r.conn.execute("select * from current_readings where original_name='legacy.pdf'").fetchone())
        path = self.r.stages.artifact_path(old, 'recipe.json'); before = path.read_bytes()
        self.r.stages.read_batch_chunks = 4
        self.assertNotIn('read_batch', read_json(path))
        new = self.r.revisions.restart_unfinished(old['doc_id'], old['revision_id'], 'batch-upgrade', 'explicit batching')
        self.assertEqual(path.read_bytes(), before)
        self.assertIn('read_batch', read_json(self.r.stages.artifact_path(self.r.doc(old['doc_id']), 'recipe.json')))
        self.assertNotEqual(self.r.doc(old['doc_id'])['recipe'], old['recipe'])
        self.assertEqual(self.r.doc(old['doc_id'])['revision_id'], new['revision_id'])

    def test_schema_keeps_required_hash_and_individual_quotes(self):
        schema = strict_schema(_schema('read_batch', True))
        members = []
        for i in range(2):
            members.append({'chunk_index': i, 'chunk_sha256': str(i), 'summary': '正文摘要',
                            'claims': [], 'object_ids': [], 'question_ids': []})
        validate_shape(schema, {'chunks': members})
        with self.assertRaises(InferenceError): validate_shape(schema, {'chunks': members[:1]})


if __name__ == '__main__': unittest.main()
