"""Useful legacy estimates remain available with their uncertainty disclosed."""
import json
from pathlib import Path
import unittest

from inresearch.delivery.project_capacity_map import cap_by_bucket, cap_total
from inresearch.knowledge.industry import project, totals
from inresearch.knowledge import site_timeline

ROOT = Path(__file__).resolve().parents[2]


class AbileneCapacityTests(unittest.TestCase):
    def test_provisional_estimate_preserves_values_history_and_uncertainty(self):
        rows = json.loads((ROOT / 'data/projects.json').read_text())['records']
        row = next(r for r in rows if r['site_id'] == 'us-tx-abilene')
        baseline = {k: v for k, v in row.items() if k != 'observations'}
        audit = json.loads((ROOT / 'docs/reviews/2026-10-11/research-remediation/abilene-capacity-correction.json').read_text())
        self.assertEqual(audit['current_record'], baseline, 'new dated observations preserve the complete historical baseline')
        self.assertEqual(audit['previous_record']['capacity_it_mw_by_status'], {'L8': 421, 'L6': 422})
        self.assertEqual(row['status'], audit['previous_record']['status'])
        self.assertEqual(row['verified_date'], audit['previous_record']['verified_date'])
        self.assertIsNone(row['capacity_it_mw'])
        self.assertEqual(row['capacity_it_mw_by_status'], {'L8': 421, 'L6': 422})
        self.assertEqual(row['capacity_facility_mw'], 1200)
        self.assertEqual(cap_total(baseline), 843)
        self.assertEqual(cap_by_bucket(baseline), (421, 422, 0))
        self.assertTrue(project(baseline)['capacity_known'])
        self.assertTrue(project(baseline)['capacity_estimated'])
        self.assertEqual(project(baseline)['capacity_assessment']['status'], 'provisional')
        self.assertIsNone(project(baseline)['capacity_assessment']['as_of'])
        self.assertTrue(project(baseline)['capacity_assessment']['missing_conditions'])
        self.assertEqual(row['sources'][0]['date'], '2026-04-17')
        self.assertEqual(len(audit['source_review']['original_sha256']), 64)
        self.assertTrue(audit['remaining_evidence'])
        combined = totals([project(baseline)])
        self.assertEqual(combined['estimated'], {'operating': 421, 'construction': 422, 'planning': 0})
        self.assertEqual(combined['estimated_sites'], 1)

    def test_real_dated_estimate_and_forecast_do_not_rewrite_or_add_to_legacy_capacity(self):
        rows = json.loads((ROOT / 'data/projects.json').read_text())['records']
        row = next(r for r in rows if r['site_id'] == 'us-tx-abilene')
        current = site_timeline.current(row, '2026-10-11')
        self.assertEqual(current['capacity_it_mw'], 421)
        self.assertEqual(current['capacity_it_mw_by_status'], {})
        self.assertEqual(current['capacity_assessment']['as_of'], '2026-07-28')
        self.assertEqual(current['tracking']['forecasts'], 1)
        self.assertEqual(cap_total(row), 421)
        self.assertEqual(cap_by_bucket(row), (421, 0, 0))
        self.assertEqual(totals([project(row)])['estimated'], {'operating': 421, 'construction': 0, 'planning': 0})
        estimate, forecast = row['observations']
        self.assertEqual((estimate['effective_at'], estimate['kind']), ('2026-07-28', 'estimated'))
        self.assertEqual((forecast['effective_at'], forecast['kind'], forecast['fields']['capacity_it_mw']), ('2026-11-01', 'forecast', 843))
        source = next(s for s in estimate['source_versions'] if s['published_at'] is not None)
        self.assertEqual(source['published_at'], '2026-10-05')
        self.assertTrue(source['first_received_at'].startswith('2026-10-11T'))
        self.assertNotEqual(estimate['recorded_at'], estimate['reviewed_at'])
        self.assertEqual(row['capacity_it_mw_by_status'], {'L8': 421, 'L6': 422})

    def test_small_estimate_revision_is_preserved_without_rounding_or_becoming_measured(self):
        row = {'site_id': 'sample', 'status': 'L8', 'capacity_it_mw': 421.25,
               'capacity_assessment': {'kind': 'estimate', 'status': 'provisional',
                                       'as_of': '2026-10-11'}}
        current = project(row)
        self.assertEqual(current['capacity']['operating'], 421.25)
        self.assertTrue(current['capacity_estimated'])
        self.assertEqual(totals([current])['estimated']['operating'], 421.25)
