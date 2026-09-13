#!/usr/bin/env python3
"""The hand-off has to survive the two trees not being identical.

Spark and M4 hold copies of one corpus, but nothing guarantees the paths
agree, so the mapping joins on content.  What must not happen is a silent
mismatch: a file the mapping expects and Spark does not have, or a file Spark
has that no one judged, has to be reported rather than skipped.
"""
import io
import json
import hashlib
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest

from inresearch.materials import organize as APPLY
from inresearch.materials import mapping as EX
from inresearch.materials import triage as L1


def write(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                    encoding='utf-8')


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-export-test-')
        base = Path(self.temp.name)
        self.source = base / 'source'; self.library = base / 'library'
        self.state = base / 'state'; self.data = base / 'data'
        for d in (self.source, self.state, self.data):
            d.mkdir(parents=True)
        self._saved = (APPLY.SOURCE, APPLY.LIBRARY, APPLY.STATE, APPLY.MOVES,
                       APPLY.INVENTORY, APPLY.RESULTS, L1.RESULTS)
        APPLY.SOURCE, APPLY.LIBRARY, APPLY.STATE = self.source, self.library, self.state
        APPLY.MOVES = self.state / 'moves.jsonl'
        APPLY.INVENTORY = self.data / 'inventory.jsonl'
        APPLY.RESULTS = L1.RESULTS = self.data / 'l1_results.jsonl'
        self.mapping = base / 'mapping.jsonl'

    def tearDown(self):
        (APPLY.SOURCE, APPLY.LIBRARY, APPLY.STATE, APPLY.MOVES,
         APPLY.INVENTORY, APPLY.RESULTS, L1.RESULTS) = self._saved
        self.temp.cleanup()

    def sha(self, i):
        return format(i, 'x').ljust(64, '0')

    def seed(self, inventory, results=(), ledger=()):
        write(APPLY.INVENTORY, inventory)
        write(APPLY.RESULTS, results)
        if ledger:
            write(APPLY.MOVES, ledger)

    def moved(self, sha, src, dst, stage='library'):
        return [{'event': 'move', 'sha256': sha, 'from': src, 'to': dst,
                 'stage': stage, 'ok': False, 'at': 'x'},
                {'event': 'move', 'sha256': sha, 'from': src, 'to': dst,
                 'stage': stage, 'ok': True, 'at': 'x'}]

    def run_cli(self, *argv):
        out = io.StringIO(); saved = sys.argv
        sys.argv = ['m4_triage_export.py', *argv]
        try:
            with redirect_stdout(out):
                EX.main()
        finally:
            sys.argv = saved
        return out.getvalue()

    # --- the ledger replay -------------------------------------------------

    def test_duplicates_of_one_hash_each_keep_their_own_destination(self):
        """A sha-keyed replay reported only whichever copy moved last."""
        sha = self.sha(1)
        self.seed(
            inventory=[{'sha256': sha, 'rel': 'a/keep.pdf', 'size': 10},
                       {'sha256': sha, 'rel': 'b/copy.pdf', 'size': 10}],
            ledger=self.moved(sha, 'b/copy.pdf', '_to_delete/duplicates/x/copy.pdf', 'duplicates')
                   + self.moved(sha, 'a/keep.pdf', 'M10/09p_keep.pdf'))
        placed = APPLY.final_locations()
        self.assertEqual(placed['a/keep.pdf'], 'M10/09p_keep.pdf')
        self.assertEqual(placed['b/copy.pdf'], '_to_delete/duplicates/x/copy.pdf')

    def test_a_chain_of_renames_reports_the_last_one(self):
        sha = self.sha(2)
        self.seed(inventory=[{'sha256': sha, 'rel': 'a/x.dwg', 'size': 5}],
                  ledger=self.moved(sha, 'a/x.dwg', '_drawings_unread/__n_x.dwg')
                         + self.moved(sha, '_drawings_unread/__n_x.dwg',
                                      '_drawings_unread/proj/__n_proj_x.dwg', 'restage'))
        self.assertEqual(APPLY.final_locations(),
                         {'a/x.dwg': '_drawings_unread/proj/__n_proj_x.dwg'})

    def test_a_full_revert_drops_out(self):
        sha = self.sha(3)
        self.seed(inventory=[{'sha256': sha, 'rel': 'a/x.pdf', 'size': 5}],
                  ledger=self.moved(sha, 'a/x.pdf', 'M10/x.pdf')
                         + [{'event': 'revert', 'sha256': sha, 'from': 'M10/x.pdf',
                             'to': 'a/x.pdf', 'ok': True, 'at': 'x'}])
        self.assertEqual(APPLY.final_locations(), {})

    # --- export ------------------------------------------------------------

    def test_export_carries_the_verdict_only_on_the_filed_copy(self):
        sha = self.sha(4)
        self.seed(
            inventory=[{'sha256': sha, 'rel': 'a/keep.pdf', 'size': 10},
                       {'sha256': sha, 'rel': 'b/copy.pdf', 'size': 10}],
            results=[{'sha256': sha, 'status': 'ok', 'level': 'p', 'category': 'M10',
                      'score': 9, 'org': 'DellOro', 'title': '资本开支'}],
            ledger=self.moved(sha, 'b/copy.pdf', '_to_delete/duplicates/x/c.pdf', 'duplicates')
                   + self.moved(sha, 'a/keep.pdf', 'M10/09p_keep.pdf'))
        self.run_cli('export', '--out', str(self.mapping))
        header, rows = EX.load_mapping(self.mapping)
        self.assertEqual(header['files'], 2)
        filed = [r for r in rows if r['stage'] == 'library'][0]
        aside = [r for r in rows if r['stage'] == 'duplicates'][0]
        self.assertEqual(filed['score'], 9)
        self.assertEqual(filed['org'], 'DellOro')
        self.assertNotIn('score', aside, 'a set-aside duplicate must not be scored twice')

    # --- verify and apply on a tree whose paths differ ---------------------

    def spark_side(self, files):
        """Point the module at a second tree holding the same content."""
        other = Path(self.temp.name) / 'spark'
        other.mkdir(exist_ok=True)
        APPLY.SOURCE = other
        APPLY.LIBRARY = Path(self.temp.name) / 'spark-library'
        inventory = []
        for rel, sha, size in files:
            path = other / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('x' * size, encoding='utf-8')
            inventory.append({'sha256': sha, 'rel': rel, 'size': size})
        write(APPLY.INVENTORY, inventory)
        return other

    def test_content_matches_even_when_the_paths_differ(self):
        sha = self.sha(5)
        self.seed(inventory=[{'sha256': sha, 'rel': 'm4/path/x.pdf', 'size': 4}],
                  results=[{'sha256': sha, 'status': 'ok', 'level': 'p',
                            'category': 'M10', 'score': 8}],
                  ledger=self.moved(sha, 'm4/path/x.pdf', 'M10/08p_x.pdf'))
        self.run_cli('export', '--out', str(self.mapping))
        self.spark_side([('spark/other/place/x.pdf', sha, 4)])
        out = json.loads(self.run_cli('verify', '--mapping', str(self.mapping)).splitlines()[0])
        self.assertEqual(out['matched'], 1)
        self.assertEqual(out['missing_here'], 0)
        self.assertEqual(out['extra_here'], 0)

    def test_a_file_the_other_machine_lacks_is_reported(self):
        here, gone = self.sha(6), self.sha(7)
        self.seed(inventory=[{'sha256': here, 'rel': 'a/x.pdf', 'size': 4},
                             {'sha256': gone, 'rel': 'a/y.pdf', 'size': 4}],
                  ledger=self.moved(here, 'a/x.pdf', 'M10/x.pdf')
                         + self.moved(gone, 'a/y.pdf', 'M10/y.pdf'))
        self.run_cli('export', '--out', str(self.mapping))
        self.spark_side([('a/x.pdf', here, 4)])
        out = json.loads(self.run_cli('verify', '--mapping', str(self.mapping)).splitlines()[0])
        self.assertEqual(out['matched'], 1)
        self.assertEqual(out['missing_here'], 1)

    def test_a_file_only_the_other_machine_has_is_reported(self):
        sha, only = self.sha(8), self.sha(9)
        self.seed(inventory=[{'sha256': sha, 'rel': 'a/x.pdf', 'size': 4}],
                  ledger=self.moved(sha, 'a/x.pdf', 'M10/x.pdf'))
        self.run_cli('export', '--out', str(self.mapping))
        self.spark_side([('a/x.pdf', sha, 4), ('a/unjudged.pdf', only, 4)])
        out = json.loads(self.run_cli('verify', '--mapping', str(self.mapping)).splitlines()[0])
        self.assertEqual(out['extra_here'], 1, 'an unjudged local file must surface')

    def test_two_copies_are_paired_with_two_mapping_rows(self):
        sha = self.sha(10)
        self.seed(inventory=[{'sha256': sha, 'rel': 'a/keep.pdf', 'size': 4},
                             {'sha256': sha, 'rel': 'b/copy.pdf', 'size': 4}],
                  ledger=self.moved(sha, 'b/copy.pdf', '_to_delete/duplicates/c.pdf', 'duplicates')
                         + self.moved(sha, 'a/keep.pdf', 'M10/keep.pdf'))
        self.run_cli('export', '--out', str(self.mapping))
        self.spark_side([('a/keep.pdf', sha, 4), ('elsewhere/copy.pdf', sha, 4)])
        out = json.loads(self.run_cli('verify', '--mapping', str(self.mapping)).splitlines()[0])
        self.assertEqual(out['matched'], 2)
        self.assertEqual(out['extra_here'], 0, 'one local file was left unpaired')

    def test_apply_plans_before_it_moves(self):
        sha = hashlib.sha256(b'xxxx').hexdigest()
        self.seed(inventory=[{'sha256': sha, 'rel': 'a/x.pdf', 'size': 4}],
                  results=[{'sha256': sha, 'status': 'ok', 'level': 'p',
                            'category': 'M10', 'score': 8}],
                  ledger=self.moved(sha, 'a/x.pdf', 'M10/08p_x.pdf'))
        self.run_cli('export', '--out', str(self.mapping))
        other = self.spark_side([('raw/x.pdf', sha, 4)])
        self.run_cli('apply', '--mapping', str(self.mapping))
        self.assertTrue((other / 'raw/x.pdf').is_file(), 'plan moved a file')
        self.run_cli('apply', '--mapping', str(self.mapping), '--commit')
        self.assertTrue((APPLY.LIBRARY / 'M10/08p_x.pdf').is_file())
        self.assertFalse((other / 'raw/x.pdf').exists())

    def test_mapping_rejects_truncation_and_duplicate_targets(self):
        sha = self.sha(15)
        self.seed(inventory=[{'sha256': sha, 'rel': 'a', 'size': 4}],
                  ledger=self.moved(sha, 'a', 'M01/a'))
        self.run_cli('export', '--out', str(self.mapping))
        original = self.mapping.read_text()
        self.mapping.write_text(original.splitlines()[0] + '\n{"sha256":')
        with self.assertRaisesRegex(ValueError, 'header_or_count'):
            EX.load_mapping(self.mapping)
        self.mapping.write_text(original)
        header, rows = EX.load_mapping(self.mapping)
        header['files'] = 2
        write(self.mapping, [{'header': header}, rows[0], {**rows[0], 'from': 'b'}])
        with self.assertRaisesRegex(ValueError, 'duplicate_path'):
            EX.load_mapping(self.mapping)

    def test_import_same_relative_path_still_moves_between_roots(self):
        sha = hashlib.sha256(b'xxxx').hexdigest()
        self.seed(inventory=[{'sha256': sha, 'rel': 'a', 'size': 4}],
                  ledger=self.moved(sha, 'a', 'a'))
        self.run_cli('export', '--out', str(self.mapping))
        other = self.spark_side([('a', sha, 4)])
        self.run_cli('apply', '--mapping', str(self.mapping), '--commit')
        self.assertFalse((other / 'a').exists())
        self.assertEqual((APPLY.LIBRARY / 'a').read_bytes(), b'xxxx')

    def test_mismatched_corpus_cannot_partially_commit(self):
        sha = hashlib.sha256(b'xxxx').hexdigest()
        self.seed(inventory=[{'sha256': sha, 'rel': 'a', 'size': 4}],
                  ledger=self.moved(sha, 'a', 'M01/a'))
        self.run_cli('export', '--out', str(self.mapping))
        other = self.spark_side([('a', sha, 4), ('extra', self.sha(14), 4)])
        with self.assertRaisesRegex(ValueError, 'corpus_mismatch'):
            self.run_cli('apply', '--mapping', str(self.mapping), '--commit')
        self.assertTrue((other / 'a').exists())
        self.assertFalse((APPLY.LIBRARY / 'M01/a').exists())

    def test_model_and_executor_provenance_survives_export(self):
        sha = self.sha(15)
        self.seed(inventory=[{'sha256': sha, 'rel': 'a', 'size': 4}],
                  results=[{'sha256': sha, 'status': 'ok', 'model': 'configured-model',
                            'executor': 'terminal', '_model': {'actual': 'configured-model'}}],
                  ledger=self.moved(sha, 'a', 'M01/a'))
        self.run_cli('export', '--out', str(self.mapping))
        _, rows = EX.load_mapping(self.mapping)
        self.assertEqual(rows[0]['model'], 'configured-model')
        self.assertEqual(rows[0]['executor'], 'terminal')
        self.assertEqual(rows[0]['_model']['actual'], 'configured-model')

    def test_importing_verdicts_does_not_duplicate_existing_rows(self):
        sha = self.sha(12)
        self.seed(inventory=[{'sha256': sha, 'rel': 'a/x.pdf', 'size': 4}],
                  results=[{'sha256': sha, 'status': 'ok', 'level': 'p',
                            'category': 'M10', 'score': 8, 'title': '某报告'}],
                  ledger=self.moved(sha, 'a/x.pdf', 'M10/08p_x.pdf'))
        self.run_cli('export', '--out', str(self.mapping))
        self.spark_side([('raw/x.pdf', sha, 4)])
        L1.RESULTS = APPLY.RESULTS = Path(self.temp.name) / 'spark-results.jsonl'
        first = json.loads(self.run_cli('import-verdicts', '--mapping', str(self.mapping)))
        second = json.loads(self.run_cli('import-verdicts', '--mapping', str(self.mapping)))
        self.assertEqual(first['imported'], 1)
        self.assertEqual(second['imported'], 0, 'a second import duplicated the verdict')
        rows = [json.loads(l) for l in L1.RESULTS.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows[0]['score'], 8)
        self.assertEqual(rows[0]['title'], '某报告')



    def test_duplicates_survive_an_inventory_that_no_longer_lists_them(self):
        """The real failure: 51,457 copies vanished from the mapping.

        The duplicates stage moves extra copies out of the source tree, so a
        rescanned inventory lists only what stayed.  Looking each origin up in
        that inventory drops every duplicate on the floor.
        """
        sha = self.sha(20)
        self.seed(
            # Only the surviving copy is inventoried, exactly as after a rescan.
            inventory=[{'sha256': sha, 'rel': 'a/keep.pdf', 'size': 10}],
            results=[{'sha256': sha, 'status': 'ok', 'level': 'p',
                      'category': 'M10', 'score': 9}],
            ledger=self.moved(sha, 'b/copy.pdf', '_to_delete/duplicates/x/c.pdf', 'duplicates')
                   + self.moved(sha, 'a/keep.pdf', 'M10/09p_keep.pdf'))
        report = json.loads(self.run_cli('export', '--out', str(self.mapping)))
        self.assertEqual(report['files'], 2, 'the duplicate was dropped')
        self.assertEqual(report.get('no_hash_in_ledger', 0), 0)
        _, rows = EX.load_mapping(self.mapping)
        by_stage = {r['stage']: r for r in rows}
        self.assertEqual(set(by_stage), {'library', 'duplicates'})
        self.assertEqual(by_stage['duplicates']['sha256'], sha,
                         'the hash must come from the ledger, not the inventory')
        self.assertNotIn('score', by_stage['duplicates'])
        self.assertEqual(by_stage['library']['score'], 9)

    def test_a_zero_scored_file_is_not_labelled_a_duplicate(self):
        """_to_delete/unrelated is a verdict, not a content duplicate."""
        sha = self.sha(21)
        self.seed(inventory=[{'sha256': sha, 'rel': 'a/junk.pdf', 'size': 4}],
                  results=[{'sha256': sha, 'status': 'ok', 'level': 'p',
                            'category': '_to_delete/unrelated', 'score': 0}],
                  ledger=self.moved(sha, 'a/junk.pdf', '_to_delete/unrelated/junk.pdf'))
        report = json.loads(self.run_cli('export', '--out', str(self.mapping)))
        self.assertEqual(report.get('duplicates', 0), 0)
        self.assertEqual(report['library'], 1)
        _, rows = EX.load_mapping(self.mapping)
        self.assertEqual(rows[0]['score'], 0, 'a zero verdict still travels')

    def test_the_stage_kept_is_the_original_decision_not_the_last_rename(self):
        sha = self.sha(22)
        self.seed(inventory=[{'sha256': sha, 'rel': 'a/x.dwg', 'size': 4}],
                  ledger=self.moved(sha, 'a/x.dwg', '_drawings_unread/__n_x.dwg')
                         + self.moved(sha, '_drawings_unread/__n_x.dwg',
                                      '_drawings_unread/p/__n_p_x.dwg', 'restage'))
        report = json.loads(self.run_cli('export', '--out', str(self.mapping)))
        self.assertEqual(report['library'], 1)
        self.assertEqual(report.get('restage', 0), 0)


if __name__ == '__main__':
    unittest.main()
