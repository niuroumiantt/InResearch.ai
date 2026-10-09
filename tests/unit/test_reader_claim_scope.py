"""Large explicit scopes must not multiply every pending-job lookup."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from inresearch.paths import project_root
from inresearch.workflow.reader import Reader
from inresearch.workflow.reader_scope import DocumentScope
from test_continuous_reader import Model, Clock


class ClaimScopeTests(unittest.TestCase):
    def test_large_scope_claim_uses_bounded_work_and_preserves_dispatch_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw = base / 'data/raw-materials'
            raw.mkdir(parents=True)
            for i in range(100):
                (raw / f'{i:03d}.txt').write_text(f'Unique research source {i}')
            reader = Reader(base/'data', base/'state', project_root(), Model(), 0, 200, Clock()).initialize()
            try:
                with reader.worker_session():
                    reader.scan()
                ids = [r[0] for r in reader.conn.execute('SELECT doc_id FROM documents ORDER BY doc_id')]
                selected = ids[:80]
                path = base/'scope.json'
                path.write_text(json.dumps({'schema_version':1, 'doc_ids':selected + ['doc-'+format(i, '064x') for i in range(5900)]}))
                reader.document_scope = DocumentScope(path, base/'data')
                reader.conn.execute('UPDATE reading_runs SET priority=9 WHERE doc_id=?', (selected[-1],))
                for turn in (0, 1, 2):
                    with self.subTest(turn=turn):
                        reader.conn.execute("UPDATE jobs SET state='pending'")
                        reader.conn.execute("UPDATE meta SET value=? WHERE key='dispatch_count'", (str(turn),))
                        expected = reader.conn.execute("SELECT j.job_id FROM jobs j JOIN reading_runs d ON d.doc_id=j.doc_id AND d.revision_id=j.revision_id WHERE j.doc_id IN (SELECT value FROM json_each(?)) ORDER BY " + ('j.created,j.doc_id,j.chunk,j.job_id' if turn == 0 else 'd.priority DESC,j.created,j.doc_id,j.chunk,j.job_id') + ' LIMIT 1', (json.dumps(selected),)).fetchone()[0]
                        steps = []
                        # Deterministic VM instruction budget, no machine-speed deadline.
                        reader.conn.set_progress_handler(lambda: steps.append(1) or len(steps)>500, 1000)
                        try:
                            with patch('inresearch.workflow.daily_dispatch.fast_reading_shas', return_value=[]):
                                job = reader.claim()
                        finally:
                            reader.conn.set_progress_handler(None, 0)
                        self.assertEqual(job['job_id'], expected)
                        self.assertIn(job['doc_id'], selected)
            finally:
                reader.close()

if __name__ == '__main__':
    unittest.main()
