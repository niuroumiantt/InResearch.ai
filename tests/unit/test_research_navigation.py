
from inresearch.paths import project_root
import copy
import json
import unittest

from inresearch.knowledge.navigation import validate_navigation


class ResearchNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads((project_root() /
                                'framework/research_graph.json').read_text())

    def test_repository_places_every_declared_object_and_keeps_demand_out_of_p(self):
        self.assertIn('navigation', self.graph)
        self.assertEqual(validate_navigation(self.graph), [])
        self.assertEqual(len(self.graph['navigation']['P']), 5)
        def ids(groups):
            return [oid for g in groups for oid in g['object_ids'] + ids(g['children'])]
        physical = ids(self.graph['navigation']['P'])
        self.assertEqual(set(physical), {o["id"] for o in self.graph["objects"] if "P" in o.get("views", []) and not o.get("navigation_hidden")})
        self.assertTrue(all(x.startswith(('part:', 'space:')) for x in physical))
        self.assertEqual(len(ids(self.graph['navigation']['R'])), len([o for o in self.graph['objects'] if not o.get('navigation_hidden')]))

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



class HardwareEcosystemTests(unittest.TestCase):
    def setUp(self):
        self.graph = json.loads((project_root() / 'framework/research_graph.json').read_text())

    def test_every_hardware_has_one_primary_ecosystem(self):
        self.assertEqual(validate_navigation(self.graph), [])
        self.graph['hardware_domains'][0]['object_ids'].append('part:cpu')
        self.assertTrue(any('duplicate primary' in e for e in validate_navigation(self.graph)))

    def test_deleted_drilldown_target_is_rejected(self):
        node = next(o for o in self.graph['objects'] if o['id'] == 'part:cpu')
        node['research_sections'][0]['object_ids'].append('arch:missing')
        self.assertTrue(any('unknown target' in e for e in validate_navigation(self.graph)))

    def test_memory_topics_are_not_universal_gpu_assembly_claims(self):
        edges = [r for r in self.graph['relations'] if r['source'] in ('part:lpddr', 'part:gddr')]
        self.assertFalse(any(r['type'] == 'part_of' and r['target'] == 'part:gpu-device' for r in edges))
        ids = {o['id'] for o in self.graph['objects']}
        self.assertTrue({'part:ssd','part:ssd-drive','part:nand','part:ssd-controller'} <= ids)


class RetiredObjectTests(unittest.TestCase):
    def test_legacy_ssd_is_hidden_and_redirects_to_live_identity(self):
        graph = json.loads((project_root() / 'framework/research_graph.json').read_text())
        old = next(o for o in graph['objects'] if o['id'] == 'part:ssd')
        self.assertTrue(old['navigation_hidden'])
        self.assertEqual(old['redirect_to'], 'part:ssd-drive')
        graph['navigation']['P'][0]['object_ids'].append('part:ssd')
        self.assertTrue(any('hidden object' in e for e in validate_navigation(graph)))
        old['redirect_to'] = 'part:ssd'
        self.assertTrue(any('direct redirect' in e for e in validate_navigation(graph)))


if __name__ == '__main__':
    unittest.main()
