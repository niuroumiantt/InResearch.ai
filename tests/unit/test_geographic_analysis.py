import copy
import json
from pathlib import Path
import tempfile
import unittest

from inresearch.knowledge import industry


class GeographicAnalysisTests(unittest.TestCase):
    def test_native_ranges_clusters_and_lifecycle_have_distinct_totals(self):
        raw = [
            {'site_id': 'a', 'name': 'A', 'country': 'US', 'region': 'north-america',
             'province': 'Virginia', 'city': 'Ashburn', 'status': 'L8', 'capacity_it_mw': 100},
            {'site_id': 'cluster', 'name': 'Cluster', 'country': 'US', 'region': 'north-america',
             'identity_scope': 'cluster', 'status': 'L8', 'capacity_it_mw': 900},
            {'site_id': 'portfolio-x', 'name': 'Portfolio', 'country': 'US', 'status': 'L8', 'capacity_it_mw': 800},
            {'site_id': 'unknown', 'name': 'Unknown', 'country': 'US', 'status': 'L2'},
            {'site_id': 'range', 'name': 'Range', 'country': 'US', 'status': 'L6'},
            {'site_id': 'closed', 'name': 'Closed', 'country': 'US', 'status': 'L8',
             'lifecycle': 'closed', 'capacity_it_mw': 50},
        ]
        rows = [industry.project(row) for row in raw]
        rows[4]['capacity_ranges'] = [{'stage': 'construction', 'value_range': [1, 2], 'unit': 'GW'}]
        rows[4]['capacity_ranged'] = True
        before = copy.deepcopy(rows)
        analysis = industry.geographic_analysis(rows)
        country = next(g for g in analysis['groups'] if g['level'] == 'country')
        self.assertEqual(country['totals']['operating'], 100)
        self.assertEqual(country['totals']['construction'], 0)
        self.assertEqual((country['cluster_records'], country['portfolio_records']), (1, 1))
        self.assertEqual(country['totals']['inactive_sites'], 1)
        self.assertEqual(country['ranges'][0]['value_range'], [1, 2])
        self.assertEqual(country['ranges'][0]['unit'], 'GW')
        self.assertEqual(country['totals']['unknown'], 1)
        self.assertEqual(rows, before)

    def test_same_city_names_are_scoped_and_missing_geography_is_not_inferred(self):
        rows = [industry.project({'site_id': key, 'name': key, 'country': country,
                                 'province': province, 'city': city})
                for key, country, province, city in [('a', 'US', 'A', 'Same'),
                                                     ('b', 'US', 'B', 'Same'),
                                                     ('c', 'CA', None, None)]]
        groups = industry.geographic_analysis(rows)['groups']
        cities = [g for g in groups if g['level'] == 'city']
        self.assertEqual(len(cities), 2)
        self.assertEqual({g['filters']['province'] for g in cities}, {'A', 'B'})
        self.assertFalse(any(g['filters'].get('country') == 'CA' and g['level'] in ('city', 'province') for g in groups))

    def test_alias_search_and_city_filter_preserve_identity_and_records(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'data').mkdir()
            payload = {'records': [{'site_id': 'stable-a', 'name': 'Campus', 'aliases': ['Old campus'],
                                    'country': 'US', 'region': 'north-america', 'city': 'Ashburn'}]}
            for name, data in [('projects', payload), ('companies', {'records': []}), ('prices', {'records': []})]:
                (root / 'data' / (name + '.json')).write_text(json.dumps(data))
            before = (root / 'data/projects.json').read_bytes()
            result = industry.snapshot(root, {'q': 'old CAMPUS', 'city': 'Ashburn'})
            self.assertEqual([r['site_id'] for r in result['rows']], ['stable-a'])
            self.assertEqual(industry.snapshot(root, {'city': 'Other'})['rows'], [])
            self.assertEqual(industry.snapshot(root, {'site': 'stable-a'})['detail']['site_id'], 'stable-a')
            self.assertEqual((root / 'data/projects.json').read_bytes(), before)
            with self.assertRaises(ValueError):
                industry.snapshot(root, {'q': 'x' * 161})


if __name__ == '__main__':
    unittest.main()
