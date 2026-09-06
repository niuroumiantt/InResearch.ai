import copy
import json
import unittest
from pathlib import Path

from research_navigation import validate_navigation


class ResearchNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads((Path(__file__).resolve().parents[1] /
                                'framework/research_graph.json').read_text())

    def test_repository_places_every_declared_object_and_keeps_demand_out_of_p(self):
        self.assertIn('navigation', self.graph)
        self.assertEqual(validate_navigation(self.graph), [])
        self.assertEqual(len(self.graph['navigation']['P']), 5)
        def ids(groups):
            return [oid for g in groups for oid in g['object_ids'] + ids(g['children'])]
        physical = ids(self.graph['navigation']['P'])
        self.assertEqual(len(physical), 50)
        self.assertTrue(all(x.startswith(('part:', 'space:')) for x in physical))
        self.assertEqual(len(ids(self.graph['navigation']['R'])), len(self.graph['objects']))

    def test_new_or_deleted_object_cannot_silently_disappear(self):
        g = copy.deepcopy(self.graph)
        g['objects'].append({'id': 'part:new', 'views': ['P']})
        self.assertTrue(any('unplaced' in x for x in validate_navigation(g)))
        g = copy.deepcopy(self.graph)
        g['objects'] = [o for o in g['objects'] if o['id'] != 'part:dram']
        self.assertTrue(any('unknown object part:dram' in x for x in validate_navigation(g)))

    def test_duplicate_location_or_cross_view_entry_rejected(self):
        g = copy.deepcopy(self.graph)
        g['navigation']['P'][0]['object_ids'].append('part:dram')
        self.assertTrue(any('duplicate browse' in x for x in validate_navigation(g)))
        g['navigation']['P'][0]['object_ids'].append('workload:storage')
        self.assertTrue(any('outside declared view workload:storage' in x for x in validate_navigation(g)))

    def test_malformed_structure_and_duplicate_group_ids_fail(self):
        g = copy.deepcopy(self.graph)
        g['navigation']['P'][0]['children'] = 'not a group list'
        self.assertTrue(any('groups must be a list' in x for x in validate_navigation(g)))
        g = copy.deepcopy(self.graph)
        g['navigation']['P'][1]['id'] = g['navigation']['P'][0]['id']
        self.assertTrue(any('duplicate group ID' in x for x in validate_navigation(g)))

    def test_system_navigation_cannot_invent_a_membership(self):
        g = copy.deepcopy(self.graph)
        power = next(row for row in g['navigation']['F'] if row.get('system_id') == 'system:power')
        power['children'][0]['object_ids'].append('part:cpu')
        self.assertTrue(any('system members must match' in x for x in validate_navigation(g)))


if __name__ == '__main__':
    unittest.main()
