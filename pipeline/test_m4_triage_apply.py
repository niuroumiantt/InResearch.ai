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
        rows = [json.loads(l) for l in A.MOVES.open(encoding="utf-8")]
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
        lines = sum(1 for _ in A.MOVES.open(encoding="utf-8"))
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
