"""The TCO factor tree must only reference objects that exist: BOM parts, price series, questions, model inputs."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class TcoFactorTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = load('framework/tco_factors.json')
        cls.factors = {f['id']: f for f in cls.tree['factors']}
        cls.bom = {p['id'] for p in load('framework/bom.json')['parts']}
        cls.series = {r['series_id'] for r in load('data/prices.json')['records']}
        cls.questions = {q['id'] for q in load('framework/research_questions.json')['records']}
        cls.model_inputs = set(load('data/datacenter_economics_model.json')['inputs'])

    def test_ids_unique_and_parents_resolve(self):
        ids = [f['id'] for f in self.tree['factors']]
        self.assertEqual(len(ids), len(set(ids)))
        for f in self.tree['factors']:
            if f['parent'] is not None:
                self.assertIn(f['parent'], self.factors, f['id'])
                self.assertTrue(f['id'].startswith(f['parent'] + '.'), f['id'])
            self.assertIn(f['side'], ('revenue', 'cost', 'capital'))

    def test_references_exist(self):
        for f in self.tree['factors']:
            for part in f.get('bom_parts', []):
                self.assertIn(part, self.bom, f"{f['id']} → bom {part}")
            for sid in f.get('price_series', []):
                self.assertIn(sid, self.series, f"{f['id']} → series {sid}")
            for qid in f.get('questions', []):
                self.assertIn(qid, self.questions, f"{f['id']} → question {qid}")
            for key in f.get('model_inputs', []):
                self.assertIn(key, self.model_inputs, f"{f['id']} → input {key}")
            for fetch in f.get('fetch', []):
                self.assertIn(fetch['kind'], ('product', 'news', 'data', 'report'), f['id'])
                self.assertTrue(fetch.get('what') and fetch.get('sources') and fetch.get('cadence'), f['id'])

    def test_every_model_input_belongs_to_a_factor(self):
        covered = {k for f in self.tree['factors'] for k in f.get('model_inputs', [])}
        missing = self.model_inputs - covered
        self.assertEqual(missing, set(), f"model inputs without a factor: {sorted(missing)}")

    def test_leaf_factors_have_a_fetch_or_series(self):
        parents = {f['parent'] for f in self.tree['factors'] if f['parent']}
        for f in self.tree['factors']:
            if f['id'] not in parents and f['id'] not in ('cost.facility',):
                self.assertTrue(f.get('fetch') or f.get('price_series'), f"{f['id']} has no fetch target or series")


if __name__ == '__main__':
    unittest.main()
