import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load("collector_handoff_validator", "scripts/validate_collector_handoff.py")
example = load("collector_handoff_example", "docs/guides/fetchdata/examples/make_sample.py")


class CollectorHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.package = example.build(self.temp.name, "fetchstat")

    def row(self):
        return json.loads((self.package / "observations.jsonl").read_text())

    def write_rows(self, *rows):
        (self.package / "observations.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_all_four_templates_validate_without_research_targets_or_known_identity(self):
        for team in ("fetchstat", "fetchfilings", "fetchreports", "fetchquotes"):
            package = self.package if team == "fetchstat" else example.build(self.temp.name, team)
            before = {p.name: p.read_bytes() for p in package.iterdir() if p.is_file()}
            result = validator.validate(package)
            self.assertTrue(result["offline_valid"], result)
            self.assertFalse(result["formal_adoption"])
            self.assertEqual(result["candidate_rows"], 1)
            self.assertEqual(before, {p.name: p.read_bytes() for p in package.iterdir() if p.is_file()})

    def test_sha_tamper_and_symlink_fail(self):
        original = next((self.package / "originals").iterdir())
        original.write_bytes(b"tampered")
        self.assertFalse(validator.validate(self.package)["offline_valid"])
        original.unlink()
        outside = Path(self.temp.name) / "outside"
        outside.write_bytes(b"outside")
        original.symlink_to(outside)
        self.assertFalse(validator.validate(self.package)["offline_valid"])

    def test_path_escape_and_absolute_path_are_rejected(self):
        for path in ("../outside", "/tmp/outside", "originals/../outside", "originals\\outside"):
            with self.assertRaises(ValueError):
                validator._file(self.package, path)

    def test_native_range_and_unknown_times_retained_invalid_range_is_isolated(self):
        good = self.row()
        good["value"] = {"type": "range", "lower": 2, "upper": 13, "raw": "2–13"}
        bad = json.loads(json.dumps(good))
        bad["observation_id"] = "bad"
        bad["value"]["lower"] = 14
        self.write_rows(good, bad)
        result = validator.validate(self.package)
        self.assertEqual(result["valid_candidate_rows"], 1)
        self.assertEqual(result["invalid_candidates"][0]["line"], 2)
        self.assertEqual(good["value"]["upper"], 13)

    def test_source_dangling_duplicate_and_forged_adoption_rejected(self):
        good = self.row()
        for key, value in (("source_item_id", "absent"), ("adopted", True), ("first_received_at", "2026-10-11T00:00:00Z")):
            bad = {**good, key: value}
            self.write_rows(bad)
            self.assertFalse(validator.validate(self.package)["offline_valid"])
        self.write_rows(good, good)
        self.assertFalse(validator.validate(self.package)["offline_valid"])

    def test_time_precision_and_evidence_required_but_unknown_allowed(self):
        for value in ({"value": "2026-02-30", "precision": "day", "basis": "bad date"},
                      {"value": "2026-01", "precision": "day", "basis": "invented precision"},
                      {"value": "2026-10-11T00:00:00", "precision": "datetime", "basis": "no zone"}):
            bad = self.row()
            bad["effective_time"] = value
            self.write_rows(bad)
            self.assertFalse(validator.validate(self.package)["offline_valid"])
        bad = self.row()
        bad["effective_time"] = {"value": None, "precision": "unknown", "basis": None}
        bad["evidence"]["quote"] = ""
        self.write_rows(bad)
        self.assertFalse(validator.validate(self.package)["offline_valid"])

    def test_original_without_candidate_is_valid_receipt_not_adoption(self):
        (self.package / "observations.jsonl").write_text("")
        result = validator.validate(self.package)
        self.assertTrue(result["offline_valid"])
        self.assertEqual(result["candidate_rows"], 0)
        self.assertFalse(result["formal_adoption"])

    def test_reused_original_does_not_invent_old_retrieval_time(self):
        path = self.package / "manifest.json"
        manifest = json.loads(path.read_text())
        item = manifest["items"][0]
        item["reused_at"] = item["retrieved_at"]
        item["retrieved_at"] = None
        path.write_text(json.dumps(manifest))
        self.assertFalse(validator.validate(self.package)["offline_valid"])
        item["provenance_id"] = "existing-private-receipt"
        path.write_text(json.dumps(manifest))
        self.assertTrue(validator.validate(self.package)["offline_valid"])

    def test_invalid_json_is_reported_per_row(self):
        good = (self.package / "observations.jsonl").read_text()
        (self.package / "observations.jsonl").write_text(good + "{bad json}\n")
        result = validator.validate(self.package)
        self.assertEqual(result["valid_candidate_rows"], 1)
        self.assertEqual(len(result["invalid_candidates"]), 1)


if __name__ == "__main__":
    unittest.main()
