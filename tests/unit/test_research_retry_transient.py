"""Exact exhausted transport retries preserve source eligibility and history."""
import concurrent.futures
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_continuous_reader as fixtures
from inresearch.materials.artifacts import atomic_json, digest_file, read_json
from inresearch.materials.reading_artifacts import ReadingArtifacts
from inresearch.materials.reader_contracts import IntegrityError
from inresearch.workflow import research_review as review


class TransientRetryTests(unittest.TestCase):
    def setUp(self):
        self.reader_fixture = fixtures.ReaderTests()
        self.reader_fixture.setUp()
        self.addCleanup(self.reader_fixture.tearDown)
        self.reader_fixture.install_registry()
        self.reader_fixture.put()
        self.reader_fixture.run_reader()
        self.doc = self.reader_fixture.first_doc()
        self.store = review.ReviewStore(self.reader_fixture.reader.data)
        self.addCleanup(self.store.db.close)
        self.bid = 'a' * 64
        self.cid = self.doc['revision_id'] + ':chunk:0:claim:0'
        self.add_batch(self.bid, [self.cid])

    def add_batch(self, bid, ids, *, error='model_relay_unavailable', attempts=4, available=123.5):
        self.store.db.execute('INSERT INTO batches VALUES(?,?,?,?,?,?,?,?,?,?)',
                              (bid, self.doc['doc_id'], self.doc['revision_id'], self.doc['report_sha256'],
                               'deferred', review.encoded(ids), 'before', error, attempts, available))
        for cid in ids:
            self.store.db.execute('INSERT INTO dispositions VALUES(?,?,?,?,?,?,?)',
                                  (cid, self.doc['doc_id'], self.doc['revision_id'], 'deferred', bid, error, 'before'))
        self.store.db.commit()
        directory = self.store.directory_for(bid)/('attempt-%04d' % attempts)
        directory.mkdir()
        atomic_json(directory/('failure-%d.json' % attempts), {'at': 'before', 'code': error})
        (directory/'matching-request.json').write_text('immutable old request')
        return directory

    def retry(self, **overrides):
        values = {'expected_attempts': 4, 'expected_error': 'model_relay_unavailable', **overrides}
        return self.store.retry_transient(self.bid, **values)

    def snapshot(self):
        return {name: [tuple(row) for row in self.store.db.execute('SELECT rowid,* FROM '+name+' ORDER BY rowid')]
                for name in ('batches', 'dispositions', 'routing_history')}

    def audit_hashes(self):
        return {str(p.relative_to(self.store.directory)): digest_file(p)
                for p in self.store.directory.rglob('*') if p.is_file() and p.suffix == '.json'}

    def unchanged_on_error(self, expected, operation=None):
        before, audit = self.snapshot(), self.audit_hashes()
        with self.assertRaises((ValueError, OSError, RuntimeError, IntegrityError)) as caught:
            (operation or self.retry)()
        self.assertRegex(getattr(caught.exception, 'code', str(caught.exception)), expected)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.audit_hashes(), audit)

    def test_one_exact_batch_preserves_budget_available_candidates_and_all_audit(self):
        self.add_batch('b'*64, ['unrelated'])
        before, audit = self.snapshot(), self.audit_hashes()
        result = self.retry()
        after = self.snapshot()
        self.assertEqual(after['batches'][1], before['batches'][1])
        self.assertEqual(after['dispositions'][1], before['dispositions'][1])
        old = dict(zip(['rowid', 'id', 'doc_id', 'revision_id', 'report_sha', 'state', 'candidate_ids',
                        'updated', 'error', 'attempts', 'available'], before['batches'][0]))
        current = dict(self.store.db.execute('SELECT rowid,* FROM batches WHERE id=?', (self.bid,)).fetchone())
        for key in old.keys()-{'state', 'error', 'updated'}:
            self.assertEqual(current[key], old[key], key)
        self.assertEqual((current['state'], result['attempts'], result['available']), ('queued', 4, 123.5))
        history = json.loads(after['routing_history'][0][3])
        self.assertEqual(history['previous_disposition'], dict(zip(
            ['id', 'doc_id', 'revision_id', 'state', 'batch_id', 'reason', 'updated'], before['dispositions'][0][1:])))
        self.assertEqual(history['failure_sha256'], result['failure_sha256'])
        self.assertEqual(history['expected_error'], 'model_relay_unavailable')
        self.assertEqual(history['manifest_sha256'], self.doc['manifest_sha256'])
        self.assertEqual(self.audit_hashes(), audit)
        self.assertIsNone(self.store.db.execute("SELECT name FROM sqlite_master WHERE name='review_scheduling'").fetchone())
        self.unchanged_on_error('compare_failed')

    def test_allowlist_accepts_only_explicit_transport_timeout_and_quota_codes(self):
        for i, code in enumerate(sorted(review.TRANSIENT_RETRY_ERRORS)):
            bid = str(i+1)*64
            self.add_batch(bid, [bid+':candidate'], error=code)
            self.assertEqual(self.store.retry_transient(bid, expected_attempts=4, expected_error=code)['state'], 'queued')
        for code in ('model_cli_authentication_failed', 'model_identity_mismatch', 'model_output_invalid',
                     'independent_sample_not_confirmed', 'review_context_over_budget', 'model_cli_failed', '', None, []):
            with self.subTest(code=code):
                self.unchanged_on_error('only_explicit_transient', lambda: self.retry(expected_error=code))

    def test_malformed_id_counter_and_stale_compare_are_rejected_without_writes(self):
        for bid in ('a'*63, 'a'*65, 'A'*64, '%', ' '+self.bid, '../'+self.bid, ''):
            with self.subTest(bid=bid):
                self.unchanged_on_error('invalid_review_batch_id', lambda: self.store.retry_transient(
                    bid, expected_attempts=4, expected_error='model_relay_unavailable'))
        for count in (0, 3, True, '4', None):
            self.unchanged_on_error('exhausted_transient_attempt', lambda: self.retry(expected_attempts=count))
        self.unchanged_on_error('compare_failed', lambda: self.retry(expected_attempts=5))
        self.unchanged_on_error('compare_failed', lambda: self.retry(expected_error='model_cli_timeout'))
        self.unchanged_on_error('compare_failed', lambda: self.store.retry_transient(
            'f'*64, expected_attempts=4, expected_error='model_relay_unavailable'))
        for state in ('queued', 'reviewing', 'review_ready', 'published', 'split_context'):
            self.store.db.execute('UPDATE batches SET state=? WHERE id=?', (state, self.bid));self.store.db.commit()
            self.unchanged_on_error('compare_failed')

    def test_current_source_tuple_and_complete_state_are_required(self):
        conn = self.reader_fixture.reader.conn
        for field, wrong, right in (('state', 'queued', 'complete'),
                                    ('report_sha256', 'f'*64, self.doc['report_sha256'])):
            conn.execute('UPDATE reading_runs SET '+field+'=? WHERE revision_id=?', (wrong, self.doc['revision_id']));conn.commit()
            self.unchanged_on_error('reading_revision_changed')
            conn.execute('UPDATE reading_runs SET '+field+'=? WHERE revision_id=?', (right, self.doc['revision_id']));conn.commit()
        self.store.db.execute('UPDATE batches SET revision_id=? WHERE id=?', ('old-revision', self.bid));self.store.db.commit()
        self.store.db.execute('UPDATE dispositions SET revision_id=? WHERE id=?', ('old-revision', self.cid));self.store.db.commit()
        self.unchanged_on_error('reading_revision_changed')

    def test_invalid_candidate_sets_are_rejected_without_rerouting(self):
        for value in ('[]', '{}', '[null]', '["same","same"]', 'not-json'):
            self.store.db.execute('UPDATE batches SET candidate_ids=? WHERE id=?', (value, self.bid));self.store.db.commit()
            self.unchanged_on_error('candidates_invalid|Expecting value')

    def test_real_manifest_extraction_and_original_corruption_fail_closed(self):
        data = self.reader_fixture.reader.data
        extraction = read_json(data/self.doc['artifact_rel']/'extraction.json')
        for path in (data/self.doc['artifact_rel']/'manifest.json', data/self.doc['report_rel'],
                     data/extraction['chunks'][0]['text_rel'], data/self.doc['original_rel']):
            original = path.read_bytes()
            mode = path.stat().st_mode
            path.chmod(mode | 0o200)
            try:
                path.write_bytes(original+b'changed')
                self.unchanged_on_error('integrity|original_changed')
            finally:
                path.write_bytes(original)
                path.chmod(mode)

    def test_activation_during_seal_check_is_detected_without_queue_changes(self):
        verify = ReadingArtifacts.verify_seal
        def change(artifacts, doc):
            report = verify(artifacts, doc)
            conn = self.reader_fixture.reader.conn
            conn.execute('UPDATE reading_runs SET state=? WHERE revision_id=?', ('queued', doc['revision_id']));conn.commit()
            return report
        with patch.object(ReadingArtifacts, 'verify_seal', change):
            self.unchanged_on_error('reading_revision_changed')

    def test_missing_or_mismatched_failure_audit_and_rerouted_candidate_are_rejected(self):
        failure = self.store.directory/self.bid/'attempt-0004/failure-4.json'
        original = failure.read_bytes()
        failure.unlink()
        self.unchanged_on_error('No such file')
        atomic_json(failure, {'code': 'model_cli_authentication_failed'})
        self.unchanged_on_error('failure_audit_mismatch')
        failure.write_bytes(original)
        self.store.db.execute('UPDATE dispositions SET batch_id=? WHERE id=?', ('different-batch', self.cid));self.store.db.commit()
        self.unchanged_on_error('disposition_changed')

    def test_history_and_queue_rollback_together_if_history_write_fails(self):
        self.store.db.execute('UPDATE batches SET candidate_ids=? WHERE id=?', (review.encoded([self.cid, 'second']), self.bid))
        self.store.db.execute('INSERT INTO dispositions VALUES(?,?,?,?,?,?,?)',
                              ('second', self.doc['doc_id'], self.doc['revision_id'], 'deferred', self.bid, 'old error', 'before'))
        self.store.db.commit()
        # The first history/disposition pair has already changed when the
        # second insertion fails. Neither partial write may survive rollback.
        self.store.db.execute("CREATE TRIGGER reject_history BEFORE INSERT ON routing_history WHEN NEW.id='second' BEGIN SELECT RAISE(ABORT,'injected_history_failure'); END")
        before, audit = self.snapshot(), self.audit_hashes()
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'injected_history_failure'):self.retry()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.audit_hashes(), audit)

    def test_concurrent_exact_requests_commit_only_one_retry_and_history(self):
        data = self.store.data
        def retry():
            store = review.ReviewStore(data)
            try:
                try:return store.retry_transient(self.bid, expected_attempts=4, expected_error='model_relay_unavailable')['state']
                except ValueError as error:return str(error)
            finally:store.db.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _:retry(), range(2)))
        self.assertCountEqual(outcomes, ['queued', 'transient_retry_compare_failed'])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM routing_history').fetchone()[0], 1)
        self.assertEqual(self.store.db.execute('SELECT attempts FROM batches WHERE id=?', (self.bid,)).fetchone()[0], 4)

    def test_next_failed_attempt_defers_without_a_fresh_automatic_budget(self):
        self.store.db.execute('UPDATE batches SET available=0 WHERE id=?', (self.bid,));self.store.db.commit()
        audit = self.audit_hashes()
        self.retry()
        client = SimpleNamespace(profile=SimpleNamespace(context=100000, max_output_tokens=1000),
                                 generate=lambda *args: (_ for _ in ()).throw(review.InferenceError('model_relay_unavailable')))
        packet = {'items': [{'candidate': {'id': self.cid}}]}
        with patch.object(self.store, 'packet', return_value=packet), patch.object(review, 'match_packet', return_value=packet):
            self.store.run_one(Path('/unused'), client, self.bid)
        row = self.store.db.execute('SELECT state,attempts,available,error FROM batches WHERE id=?', (self.bid,)).fetchone()
        self.assertEqual(tuple(row), ('deferred', 5, 0, 'model_relay_unavailable'))
        self.assertEqual(read_json(self.store.directory/self.bid/'attempt-0005/failure-5.json')['code'], 'model_relay_unavailable')
        self.assertTrue(all(self.audit_hashes()[name] == digest for name, digest in audit.items()))
        self.unchanged_on_error('compare_failed')

    def test_retry_respects_available_and_has_no_semantic_retry_priority(self):
        self.store.db.execute('UPDATE batches SET available=? WHERE id=?', (time.time()+3600, self.bid));self.store.db.commit()
        self.retry()
        self.assertIsNone(self.store.claim(self.bid))
        self.add_batch('b'*64, ['older-queued'])
        self.store.db.execute("UPDATE batches SET state='queued',error='' WHERE id=?", ('b'*64,));self.store.db.commit()
        self.add_batch('c'*64, ['later-retry'])
        self.store.retry_transient('c'*64, expected_attempts=4, expected_error='model_relay_unavailable')
        self.assertEqual(self.store.claim()['id'], 'b'*64)

    def test_cli_rejects_bad_arguments_before_queue_initialization(self):
        for arguments in (['--batch-id', '%', '--expected-attempts', '4', '--expected-error', 'model_relay_unavailable'],
                          ['--batch-id', self.bid, '--expected-attempts', '3', '--expected-error', 'model_relay_unavailable'],
                          ['--batch-id', self.bid, '--expected-attempts', '4', '--expected-error', 'model_cli_failed']):
            with patch('sys.argv', ['research-review', 'retry-transient', *arguments]), patch.object(review, 'ReviewStore') as store:
                with self.assertRaises(ValueError):review.main()
                store.assert_not_called()

    def test_cli_only_queues_exact_existing_batch_and_prints_receipt(self):
        arguments = ['research-review', '--data', str(self.store.data), 'retry-transient', '--batch-id', self.bid,
                     '--expected-attempts', '4', '--expected-error', 'model_relay_unavailable']
        output = io.StringIO()
        with patch('sys.argv', arguments), contextlib.redirect_stdout(output), patch.object(review, 'configured_client') as model:
            review.main()
            model.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['batch_id'], self.bid)
        self.assertEqual(json.loads(output.getvalue())['state'], 'queued')


if __name__ == '__main__':unittest.main()
