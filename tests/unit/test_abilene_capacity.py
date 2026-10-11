"""Useful legacy estimates remain available with their uncertainty disclosed."""
import json
from pathlib import Path
import unittest

from inresearch.delivery.project_capacity_map import cap_by_bucket, cap_total
from inresearch.knowledge.industry import project, totals

ROOT = Path(__file__).resolve().parents[2]


class AbileneCapacityTests(unittest.TestCase):
    def test_provisional_estimate_preserves_values_history_and_uncertainty(self):
        rows = json.loads((ROOT / 'data/projects.json').read_text())['records']
        row = next(r for r in rows if r['site_id'] == 'us-tx-abilene')
        audit = json.loads((ROOT / 'docs/reviews/2026-10-11/research-remediation/abilene-capacity-correction.json').read_text())
        self.assertEqual(audit['current_record'], row)
        self.assertEqual(audit['previous_record']['capacity_it_mw_by_status'], {'L8': 421, 'L6': 422})
        self.assertEqual(row['status'], audit['previous_record']['status'])
        self.assertEqual(row['verified_date'], audit['previous_record']['verified_date'])
        self.assertIsNone(row['capacity_it_mw'])
        self.assertEqual(row['capacity_it_mw_by_status'], {'L8': 421, 'L6': 422})
        self.assertEqual(row['capacity_facility_mw'], 1200)
        self.assertEqual(cap_total(row), 843)
        self.assertEqual(cap_by_bucket(row), (421, 422, 0))
        self.assertTrue(project(row)['capacity_known'])
        self.assertTrue(project(row)['capacity_estimated'])
        self.assertEqual(project(row)['capacity_assessment']['status'], 'provisional')
        self.assertIsNone(project(row)['capacity_assessment']['as_of'])
        self.assertTrue(project(row)['capacity_assessment']['missing_conditions'])
        self.assertEqual(row['sources'][0]['date'], '2026-04-17')
        self.assertEqual(len(audit['source_review']['original_sha256']), 64)
        self.assertTrue(audit['remaining_evidence'])
        combined = totals([project(row)])
        self.assertEqual(combined['estimated'], {'operating': 421, 'construction': 422, 'planning': 0})
        self.assertEqual(combined['estimated_sites'], 1)

    def test_small_estimate_revision_is_preserved_without_rounding_or_becoming_measured(self):
        row = {'site_id': 'sample', 'status': 'L8', 'capacity_it_mw': 421.25,
               'capacity_assessment': {'kind': 'estimate', 'status': 'provisional',
                                       'as_of': '2026-10-11'}}
        current = project(row)
        self.assertEqual(current['capacity']['operating'], 421.25)
        self.assertTrue(current['capacity_estimated'])
        self.assertEqual(totals([current])['estimated']['operating'], 421.25)
