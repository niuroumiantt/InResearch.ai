"""骨架校验（图谱 3.0）：对象集合 = 骨架节点集合，新增或删除对象不能悄悄发生，包含关系单亲无环，顺序固定，旧 ID 折算。"""
import copy
import json
import unittest
from pathlib import Path

from inresearch.knowledge import graph as graph_mod
from inresearch.knowledge import registry as research
from inresearch.knowledge.navigation import validate_navigation

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class SkeletonNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = load('framework/research_graph.json')
        cls.questions = load('framework/research_questions.json')
        cls.bom = load('framework/bom.json')

    def test_repository_graph_is_the_skeleton(self):
        self.assertEqual(validate_navigation(self.graph), [])
        self.assertEqual({o['kind'] for o in self.graph['objects']}, set(graph_mod.KINDS))
        self.assertEqual({o['id'] for o in self.graph['objects'] if o['kind'] == 'part'}, {'part:' + p['id'] for p in self.bom['parts']})

    def test_new_or_deleted_object_cannot_silently_disappear(self):
        g = copy.deepcopy(self.graph)
        g['objects'].append({'id': 'part:new', 'name': 'x', 'kind': 'part', 'parent': 'system:power', 'system': 'power', 'representation': 'conceptual'})
        self.assertTrue(any('part objects must equal' in e for e in validate_navigation(g)))
        g = copy.deepcopy(self.graph)
        g['objects'] = [o for o in g['objects'] if o['id'] != 'part:dram']
        self.assertTrue(any('part objects must equal' in e for e in validate_navigation(g)))
        g = copy.deepcopy(self.graph)
        g['objects'] = [o for o in g['objects'] if o['id'] != 'system:memory']
        self.assertTrue(any('system objects must equal' in e for e in validate_navigation(g)))

    def test_parent_must_be_a_skeleton_node_and_containment_is_single_and_acyclic(self):
        g = copy.deepcopy(self.graph)
        next(o for o in g['objects'] if o['id'] == 'part:gpu')['parent'] = 'part:nowhere'
        self.assertTrue(any('parent must be a skeleton node' in e for e in validate_navigation(g)))
        g = copy.deepcopy(self.graph)
        g['relations'].append({'id': 'x', 'type': 'part_of', 'source': 'part:gpu', 'target': 'part:cpu', 'representation': 'conceptual'})
        self.assertTrue(any('multiple parents' in e for e in validate_navigation(g)))
        g = copy.deepcopy(self.graph)
        g['relations'].append({'id': 'y', 'type': 'part_of', 'source': 'system:power', 'target': 'part:transformer', 'representation': 'conceptual'})
        self.assertTrue(any('cycle' in e for e in validate_navigation(g)))

    def test_order_follows_system_chain_and_chain_order(self):
        g = copy.deepcopy(self.graph)
        parts = [i for i, o in enumerate(g['objects']) if o['kind'] == 'part']
        g['objects'][parts[0]], g['objects'][parts[-1]] = g['objects'][parts[-1]], g['objects'][parts[0]]
        self.assertTrue(any('ordered by system order' in e for e in validate_navigation(g)))

    def test_unknown_relation_type_and_dangling_ends_are_rejected(self):
        g = copy.deepcopy(self.graph)
        g['relations'].append({'id': 'z', 'type': 'research_scope', 'source': 'part:gpu', 'target': 'scope:M06', 'representation': 'conceptual'})
        errors = validate_navigation(g)
        self.assertTrue(any('unknown relation type' in e for e in errors))
        self.assertTrue(any('dangling relation' in e for e in errors))

    def test_old_graphs_without_kinds_are_history_not_navigation(self):
        self.assertEqual(validate_navigation({'version': '2.2.1', 'objects': [], 'relations': []}), [])

    def test_questions_hang_on_skeleton_nodes(self):
        objects = {o['id'] for o in self.graph['objects']}
        for q in self.questions['records']:
            self.assertIn(q['node'], objects, q['id'])
            self.assertTrue(set(q['object_ids']) <= objects, q['id'])
            self.assertIn(q['variable_class'], (1, 2, 3, 4, 5), q['id'])
        self.assertEqual([], research.validate(self.graph, self.questions, load('data/research_knowledge.json')))


if __name__ == '__main__':
    unittest.main()
