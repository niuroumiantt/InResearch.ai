#!/usr/bin/env python3
"""plan must predict apply exactly, and never touch anything while predicting.

The ledger invariant tested here - two lines per move, intent before the
rename and outcome after - is what makes moves.jsonl replayable in reverse,
and what lets a doubled line count be read as healthy rather than as a
double-move.
"""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m4_triage_apply as A
import m4_triage_l1 as L1


def write(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m4-apply-test-")
        base = Path(self.temp.name)
        self.source = base / "source"
        self.library = base / "library"
        self.state = base / "state"
        self.data = base / "data"
        self.source.mkdir(); self.data.mkdir()
        self._saved = (A.SOURCE, A.LIBRARY, A.STATE, A.MOVES, A.INVENTORY, A.RESULTS)
        A.SOURCE, A.LIBRARY, A.STATE = self.source, self.library, self.state
        A.MOVES = self.state / "moves.jsonl"
        A.INVENTORY = self.data / "inventory.jsonl"
        A.RESULTS = self.data / "l1_results.jsonl"

    def tearDown(self):
        (A.SOURCE, A.LIBRARY, A.STATE, A.MOVES, A.INVENTORY, A.RESULTS) = self._saved
        self.temp.cleanup()

    def build(self, specs):
        """specs: (rel, sha, category, name) -> inventory + results + real files."""
        inventory, results = [], []
        for rel, sha, category, name in specs:
            path = self.source / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(sha, encoding="utf-8")
            inventory.append({"sha256": sha, "rel": rel, "size": path.stat().st_size})
            results.append({"sha256": sha, "category": category, "proposed_name": name,
                            "score": 5, "level": "p"})
        write(A.INVENTORY, inventory)
        write(A.RESULTS, results)

    def sample(self, n=3):
        return [("dir%d/f%d.pdf" % (i, i), "%064d" % i, "M%02d" % (i % 3 + 1),
                 "05p_2025_org_t%d__%s.pdf" % (i, "%016d" % i)) for i in range(n)]

    def run_cli(self, *argv):
        out = io.StringIO()
        saved = sys.argv
        sys.argv = ["m4_triage_apply.py", *argv]
        try:
            with redirect_stdout(out):
                A.main()
        finally:
            sys.argv = saved
        return out.getvalue()

    # --- plan is read-only -------------------------------------------------

    def test_plan_creates_no_state_and_moves_nothing(self):
        self.build(self.sample(3))
        self.run_cli("library", "plan")
        self.assertFalse(self.state.exists(), "plan created the state directory")
        self.assertFalse(A.MOVES.exists(), "plan wrote to the move ledger")
        self.assertFalse(self.library.exists(), "plan created the library tree")
        for rel, *_ in self.sample(3):
            self.assertTrue((self.source / rel).is_file(), "plan moved %s" % rel)

    def test_plan_reports_the_four_counters(self):
        self.build(self.sample(3))
        lines = self.run_cli("library", "plan").splitlines()
        counts = json.loads(lines[1])
        self.assertEqual(counts, {"would_move": 3, "already_done": 0,
                                  "source_missing": 0, "destination_exists": 0})

    def test_plan_would_move_matches_what_apply_moves(self):
        self.build(self.sample(5))
        predicted = json.loads(self.run_cli("library", "plan").splitlines()[1])["would_move"]
        actual = json.loads(self.run_cli("library", "apply").splitlines()[0])["moved"]
        self.assertEqual(predicted, actual)

    def test_plan_category_breakdown_sums_to_would_move(self):
        self.build(self.sample(7))
        _, by_category = A.do_apply(A.plan_library(), dry=True)
        self.assertEqual(sum(by_category.values()), 7)
        self.assertEqual(set(by_category), {"M01", "M02", "M03"})

    # --- plan sees what apply would refuse ---------------------------------

    def test_plan_counts_already_moved_instead_of_planning_them(self):
        self.build(self.sample(4))
        self.run_cli("library", "apply", "--limit", "2")
        counts = json.loads(self.run_cli("library", "plan").splitlines()[1])
        self.assertEqual(counts["already_done"], 2)
        self.assertEqual(counts["would_move"], 2)

    def test_plan_counts_a_destination_collision(self):
        specs = self.sample(2)
        self.build(specs)
        occupied = self.library / specs[0][2] / specs[0][3]
        occupied.parent.mkdir(parents=True, exist_ok=True)
        occupied.write_text("someone got here first", encoding="utf-8")
        counts = json.loads(self.run_cli("library", "plan").splitlines()[1])
        self.assertEqual(counts["destination_exists"], 1)
        self.assertEqual(counts["would_move"], 1)

    def test_plan_counts_a_vanished_source(self):
        specs = self.sample(3)
        self.build(specs)
        (self.source / specs[0][0]).unlink()
        counts = json.loads(self.run_cli("library", "plan").splitlines()[1])
        self.assertEqual(counts["source_missing"], 1)
        self.assertEqual(counts["would_move"], 2)

    def test_a_collision_never_overwrites(self):
        specs = self.sample(1)
        self.build(specs)
        occupied = self.library / specs[0][2] / specs[0][3]
        occupied.parent.mkdir(parents=True, exist_ok=True)
        occupied.write_text("original", encoding="utf-8")
        self.run_cli("library", "apply")
        self.assertEqual(occupied.read_text(encoding="utf-8"), "original")
        self.assertTrue((self.source / specs[0][0]).is_file(), "source was consumed")

    # --- the ledger invariant ----------------------------------------------

    def test_every_move_writes_intent_then_outcome(self):
        self.build(self.sample(6))
        self.run_cli("library", "apply")
        with A.MOVES.open(encoding="utf-8") as fh:
            rows = [json.loads(l) for l in fh]
        self.assertEqual(len(rows), 12, "expected exactly two ledger lines per move")
        intent = [r for r in rows if r["event"] == "move" and not r["ok"]]
        done = [r for r in rows if r["event"] == "move" and r["ok"]]
        self.assertEqual(len(intent), 6)
        self.assertEqual(len(done), 6)
        self.assertEqual({r["from"] for r in intent}, {r["from"] for r in done})
        # Intent is on disk before the rename, so every outcome has a predecessor.
        for position, row in enumerate(rows):
            if row["ok"]:
                self.assertFalse(rows[position - 1]["ok"])
                self.assertEqual(rows[position - 1]["from"], row["from"])

    def test_apply_is_idempotent(self):
        self.build(self.sample(4))
        first = json.loads(self.run_cli("library", "apply").splitlines()[0])
        second = json.loads(self.run_cli("library", "apply").splitlines()[0])
        self.assertEqual(first["moved"], 4)
        self.assertEqual(second, {"moved": 0, "already_done": 4,
                                  "source_missing": 0, "destination_exists": 0})
        with A.MOVES.open(encoding="utf-8") as fh:
            lines = sum(1 for _ in fh)
        self.assertEqual(lines, 8, "the second run appended to the ledger")

    def test_revert_puts_every_file_back(self):
        specs = self.sample(4)
        self.build(specs)
        self.run_cli("library", "apply")
        for rel, *_ in specs:
            self.assertFalse((self.source / rel).exists())
        self.run_cli("library", "revert")
        for rel, *_ in specs:
            self.assertTrue((self.source / rel).is_file(), "%s never came back" % rel)


if __name__ == "__main__":
    unittest.main()


class SourceDirTests(unittest.TestCase):
    """An unread file's own name does not say which project it belongs to."""

    def unread(self, rel, sha):
        return {'rel': rel, 'sha256': sha + '0' * (64 - len(sha)),
                'suffix': Path(rel).suffix, 'status': 'l0'}

    def test_two_projects_same_drawing_name_stay_apart(self):
        a = L1.proposed_name(self.unread('报告/2019中国移动广州IDC/图纸/一层平面图.dwg', 'aaaa'))
        b = L1.proposed_name(self.unread('报告/2019中国移动深圳IDC/图纸/一层平面图.dwg', 'bbbb'))
        self.assertNotEqual(a, b)
        self.assertIn('广州', a)
        self.assertIn('深圳', b)

    def test_the_source_tree_is_preserved(self):
        name = L1.proposed_name(self.unread('数据中心报告购买/01 解决方案/4 投标/图纸/剖面.dwg', 'cc'))
        self.assertEqual(Path(name).parent.parts,
                         ('数据中心报告购买', '01 解决方案', '4 投标', '图纸'))

    def test_a_file_at_the_root_gets_no_directory(self):
        name = L1.proposed_name(self.unread('孤儿文件.dwg', 'dd'))
        self.assertEqual(Path(name).parent, Path('.'))
        self.assertTrue(name.startswith('__n_'))

    def test_a_scored_file_stays_flat_by_design(self):
        scored = {'rel': '报告/深圳/年报.pdf', 'sha256': 'ee' + '0' * 62, 'suffix': '.pdf',
                  'status': 'ok', 'score': 8, 'score_status': 'provisional', 'level': 'p',
                  'year': '2026', 'org': 'DellOro', 'title': '资本开支预测',
                  'keep_original_name': False}
        name = L1.proposed_name(scored)
        self.assertEqual(Path(name).parent, Path('.'))
        self.assertTrue(name.startswith('08p_2026_DellOro_'))

    def test_a_very_deep_path_elides_the_middle_visibly(self):
        deep = '/'.join('第%d层这是一个相当长的目录名称用来越过长度上限' % i for i in range(12))
        out = L1.source_dir(deep + '/x.dwg')
        self.assertIn('__', out.split('/'), 'elision was silent')
        self.assertTrue(out.startswith('第0层'), 'lost the outermost folder')
        self.assertIn('第11层这是一个相当长的目录名称', out, 'lost the innermost folder')

    def test_separators_inside_a_segment_cannot_create_directories(self):
        name = L1.proposed_name(self.unread('a/b/中国移动IDC资质\\Uptime T3级.png', 'ff'))
        self.assertEqual(len(Path(name).parts), 3, 'a backslash became a directory level')


class RestageTests(unittest.TestCase):
    """Re-filing what the first pass put in the wrong place."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-restage-test-')
        base = Path(self.temp.name)
        self.source = base / 'source'; self.library = base / 'library'
        self.state = base / 'state'; self.data = base / 'data'
        self.source.mkdir(); self.data.mkdir()
        self._saved = (A.SOURCE, A.LIBRARY, A.STATE, A.MOVES, A.INVENTORY, A.RESULTS)
        A.SOURCE, A.LIBRARY, A.STATE = self.source, self.library, self.state
        A.MOVES = self.state / 'moves.jsonl'
        A.INVENTORY = self.data / 'inventory.jsonl'
        A.RESULTS = self.data / 'l1_results.jsonl'

    def tearDown(self):
        (A.SOURCE, A.LIBRARY, A.STATE, A.MOVES, A.INVENTORY, A.RESULTS) = self._saved
        self.temp.cleanup()

    def sha(self, i):
        # varying digits first: the destination carries only sha[:16], and a
        # zero-padded counter makes every fixture collide there
        return format(i, 'x').ljust(64, '0')

    def flat_file_first(self, rels):
        """File everything the old way: bucket plus basename, no directories."""
        inventory, results = [], []
        A.STATE.mkdir(parents=True, exist_ok=True)
        with A.MOVES.open('a', encoding='utf-8') as log:
            for i, rel in enumerate(rels):
                path = self.source / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('content %d' % i, encoding='utf-8')
                sha = self.sha(i)
                inventory.append({'sha256': sha, 'rel': rel, 'size': path.stat().st_size})
                results.append({'sha256': sha, 'rel': rel, 'suffix': Path(rel).suffix,
                                'status': 'l0', 'category': '_drawings_unread', 'level': 'n'})
                flat = '_drawings_unread/__n_%s__%s%s' % (Path(rel).stem, sha[:16], Path(rel).suffix)
                dst = self.library / flat
                dst.parent.mkdir(parents=True, exist_ok=True)
                path.rename(dst)
                log.write(json.dumps({'event': 'move', 'at': 'x', 'sha256': sha, 'from': rel,
                                      'to': flat, 'ok': True, 'stage': 'library'},
                                     ensure_ascii=False) + '\n')
        write(A.INVENTORY, inventory)
        write(A.RESULTS, results)

    def run_cli(self, *argv):
        out = io.StringIO(); saved = sys.argv
        sys.argv = ['m4_triage_apply.py', *argv]
        try:
            with redirect_stdout(out):
                A.main()
        finally:
            sys.argv = saved
        return out.getvalue()

    def test_restage_moves_a_flattened_drawing_back_under_its_project(self):
        self.flat_file_first(['报告/2019广州IDC/图纸/一层平面图.dwg',
                              '报告/2019深圳IDC/图纸/一层平面图.dwg'])
        counts = json.loads(self.run_cli('restage', 'apply').splitlines()[0])
        self.assertEqual(counts['moved'], 2)
        for i, city in enumerate(('2019广州IDC', '2019深圳IDC')):
            want = (self.library / '_drawings_unread/报告' / city / '图纸'
                    / ('__n_一层平面图__%s.dwg' % self.sha(i)[:16]))
            self.assertTrue(want.is_file(), '%s not re-filed under its project' % city)
        loose = [p.name for p in (self.library / '_drawings_unread').iterdir() if p.is_file()]
        self.assertEqual(loose, [], 'a file was left flattened in the bucket')

    def test_restage_is_idempotent(self):
        self.flat_file_first(['报告/广州/图纸/平面.dwg'])
        first = json.loads(self.run_cli('restage', 'apply').splitlines()[0])
        second = json.loads(self.run_cli('restage', 'apply').splitlines()[0])
        self.assertEqual(first['moved'], 1)
        self.assertEqual(second['moved'], 0)

    def test_restage_skips_files_that_were_never_filed(self):
        write(A.INVENTORY, [{'sha256': self.sha(0), 'rel': 'a/b.dwg', 'size': 3}])
        write(A.RESULTS, [{'sha256': self.sha(0), 'rel': 'a/b.dwg', 'suffix': '.dwg',
                           'status': 'l0', 'category': '_drawings_unread', 'level': 'n'}])
        counts = json.loads(self.run_cli('restage', 'plan').splitlines()[1])
        self.assertEqual(counts['would_move'], 0)

    def test_restage_plan_touches_nothing(self):
        self.flat_file_first(['报告/广州/图纸/平面.dwg'])
        with A.MOVES.open(encoding='utf-8') as fh:
            before = sum(1 for _ in fh)
        self.run_cli('restage', 'plan')
        with A.MOVES.open(encoding='utf-8') as fh:
            self.assertEqual(sum(1 for _ in fh), before)

    def test_restage_writes_the_same_two_line_ledger(self):
        self.flat_file_first(['报告/广州/图纸/平面.dwg'])
        with A.MOVES.open(encoding='utf-8') as fh:
            before = sum(1 for _ in fh)
        self.run_cli('restage', 'apply')
        with A.MOVES.open(encoding='utf-8') as fh:
            rows = [json.loads(l) for l in fh][before:]
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[0]['ok'])
        self.assertTrue(rows[1]['ok'])
        self.assertEqual(rows[0]['from_root'], 'library')

    def test_restage_revert_returns_it_to_the_library_not_the_source(self):
        rels = ['报告/广州/图纸/平面.dwg']
        self.flat_file_first(rels)
        self.run_cli('restage', 'apply')
        self.run_cli('restage', 'revert')
        flat = self.library / ('_drawings_unread/__n_平面__%s.dwg' % self.sha(0)[:16])
        self.assertTrue(flat.is_file(), 'revert did not put it back in the library')
        self.assertFalse((self.source / rels[0]).exists(),
                         'revert wrongly pushed it back into the source tree')

    def test_a_pathological_path_still_terminates(self):
        """The marker used to be re-inserted where it had just been removed."""
        deep = '/'.join(('x' * 55) + str(i) for i in range(40))
        out = L1.source_dir(deep + '/x.dwg')
        parts = out.split('/')
        self.assertIn('__', parts)
        self.assertGreaterEqual(len(parts), 3)
        self.assertTrue(parts[-1].endswith('39'), 'lost the innermost folder')
