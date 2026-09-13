"""Material versions survive failures and reject competing stale replacements."""
import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest

from inresearch.materials.records import commit_result, current_results, result_revision


def replace_result(path, base, score, queue):
    try:
        commit_result(path, {'sha256': 'a'*64, 'status': 'ok', 'score': score}, base)
        queue.put('committed')
    except ValueError as exc:
        queue.put(str(exc))


class VersionFlows(unittest.TestCase):
    def test_unversioned_legacy_batch_cannot_replace_an_existing_success(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'results.jsonl'
            first = commit_result(path, {'sha256':'a'*64, 'status':'ok', 'score':8})
            first['score'] = 0  # Returned values cannot mutate the cached authority.
            with self.assertRaisesRegex(ValueError, 'result_revision_conflict'):
                commit_result(path, {'sha256':'a'*64, 'status':'ok', 'score':3})
            self.assertEqual(current_results(path)['a'*64]['score'], 8)

    def test_competing_processes_and_failed_retry_keep_one_effective_result(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'results.jsonl'
            first = commit_result(path, {'sha256':'a'*64, 'status':'ok', 'score':8}, None)
            base = result_revision(first)
            context = multiprocessing.get_context('spawn')
            queue = context.Queue()
            processes = [context.Process(target=replace_result, args=(path,base,score,queue)) for score in (7,9)]
            for p in processes: p.start()
            for p in processes:
                p.join(15)
                self.assertEqual(p.exitcode, 0)
            self.assertEqual(sorted(queue.get(timeout=2) for _ in processes), ['committed','result_revision_conflict'])
            winner = current_results(path)['a'*64]
            self.assertEqual(winner['supersedes'], base)
            failed = commit_result(path, {'sha256':'a'*64, 'status':'error', 'error':'model_timeout'})
            self.assertIsNone(failed['supersedes'])
            self.assertEqual(current_results(path)['a'*64], winner)
            self.assertEqual(len(path.read_text().splitlines()), 3)
            queue.close()

    def test_external_edit_invalidates_cache_and_corruption_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'results.jsonl'
            first = commit_result(path, {'sha256':'a'*64, 'status':'ok', 'score':8}, None)
            replacement = {'sha256':'a'*64, 'status':'ok', 'score':9}
            path.write_text(json.dumps(replacement)+'\n')
            with self.assertRaisesRegex(ValueError, 'revision_conflict'):
                commit_result(path, first, result_revision(first))
            with path.open('a') as f: f.write('broken\n')
            with self.assertRaisesRegex(ValueError, 'invalid JSON record'):
                commit_result(path, first)


if __name__ == '__main__':
    unittest.main()
