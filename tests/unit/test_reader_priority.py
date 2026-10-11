"""Named scheduling changes never become source scores or reading results."""
import concurrent.futures
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from inresearch.interfaces import reader as cli
from inresearch.workflow.reader import Reader
from inresearch.workflow.reader_priority import prioritize
from test_continuous_reader import Model


class ReaderPriorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.reader = Reader(self.base/'data', self.base/'state', self.base/'repo', Model(), 0).initialize()
        self.addCleanup(self.reader.close)
        for name in ('named.txt', 'other.txt'):
            (self.reader.data/'raw-materials'/name).write_text(name + ' original source text.\n')
        self.reader.scan()
        self.doc = dict(self.reader.conn.execute("SELECT * FROM current_readings WHERE original_name='named.txt'").fetchone())
        self.args = dict(doc_id=self.doc['doc_id'], revision_id=self.doc['revision_id'],
                         expected_priority=self.doc['priority'], priority=9, request_id='named-pilot-001',
                         by='test operator', reason='User explicitly requested this named pilot next.')

    def tables(self):
        return {name: [dict(r) for r in self.reader.conn.execute('SELECT * FROM '+name+' ORDER BY 1')]
                for name in ('documents', 'reading_runs', 'jobs', 'sources', 'meta')}

    def call(self, **changes):
        return prioritize(self.reader.data, **dict(self.args, **changes))

    def test_plan_is_read_only_commit_changes_only_named_order_and_replay_is_idempotent(self):
        before = self.tables()
        paths = list((self.reader.data/self.doc['artifact_rel']).rglob('*'))
        frozen = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
        self.assertEqual(self.call(dry_run=True)['status'], 'planned')
        self.assertEqual(before, self.tables())
        receipt = self.call(); after = self.tables()
        self.assertEqual(receipt['authority'], 'reading_order_only_not_importance_or_adoption')
        for table in ('documents', 'jobs', 'sources'):
            self.assertEqual(before[table], after[table])
        expected = [dict(r, priority=9) if r['revision_id']==self.doc['revision_id'] else r
                    for r in before['reading_runs']]
        self.assertEqual(expected, after['reading_runs'])
        self.assertEqual(len(before['meta'])+1, len(after['meta']))
        self.assertEqual(frozen, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen})
        self.assertEqual(self.call()['status'], 'already_applied')
        self.assertEqual(after, self.tables())

    def test_model_importance_and_full_reading_remain_independent_of_priority(self):
        self.call()
        with contextlib.redirect_stdout(io.StringIO()): self.reader.run(once=True)
        doc = self.reader.doc(self.doc['doc_id'])
        report = json.loads(self.reader.artifact_path(doc['doc_id'], 'report.json').read_text())
        self.assertEqual((doc['state'], doc['priority'], report['importance']), ('complete', 9, 6))
        self.assertTrue(report['coverage']['complete'])
        self.assertEqual(self.call()['status'], 'already_applied')

    def test_stale_revision_priority_collision_and_terminal_state_refuse_without_mutation(self):
        before = self.tables()
        for changes in (dict(revision_id='stale'), dict(expected_priority=4), dict(priority=4),
                        dict(expected_priority=True), dict(by=''), dict(request_id='../escape')):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError): self.call(**changes)
                self.assertEqual(before, self.tables())
        self.call(); before = self.tables()
        with self.assertRaisesRegex(ValueError, 'request_id_conflict'): self.call(reason='changed intent')
        self.assertEqual(before, self.tables())
        self.reader.conn.execute("UPDATE reading_runs SET state='failed' WHERE revision_id=?", (self.doc['revision_id'],))
        before = self.tables()
        with self.assertRaisesRegex(ValueError, 'not_schedulable'):
            self.call(expected_priority=9, priority=10, request_id='named-pilot-002')
        self.assertEqual(before, self.tables())

    def test_concurrent_cas_has_one_winner_and_cli_never_constructs_reader(self):
        def attempt(n):
            try: return self.call(request_id='concurrent-pilot-'+str(n))['status']
            except ValueError as exc: return str(exc)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(attempt, (1, 2))), ['applied', 'priority_compare_failed'])
        args=['--data-root',str(self.reader.data),'prioritize','--doc-id',self.doc['doc_id'],
              '--revision-id',self.doc['revision_id'],'--expected-priority','9','--priority','10',
              '--request-id','cli-pilot-001','--by','test operator','--reason','Explicit next reading']
        with patch('inresearch.workflow.reader.Reader', side_effect=AssertionError('must not create a worker')):
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(cli.main(args), 0)
