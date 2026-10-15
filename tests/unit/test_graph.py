"""研究图谱 3.0 由骨架生成：对象集合 = 骨架节点集合，问题 ID 不变并挂节点与变量类，旧 ID 都有去处。"""
import json
import unittest
from pathlib import Path

from inresearch.knowledge import graph as graph_mod

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class Graph3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bom = load('framework/bom.json')
        cls.rights = load('framework/site_rights.json')['rights']
        cls.companies = load('data/companies.json')['records']
        cls.graph, cls.questions = graph_mod.build(ROOT)
        cls.objects = {o['id']: o for o in cls.graph['objects']}

    def test_files_are_generated_from_the_skeleton(self):
        self.assertEqual(load(graph_mod.GRAPH), self.graph, 'framework/research_graph.json is stale; run python3 manage.py graph --refresh')
        self.assertEqual(load(graph_mod.QUESTIONS), self.questions, 'framework/research_questions.json is stale; run python3 manage.py graph --refresh')
        self.assertEqual(graph_mod.validate(self.graph, self.bom), [])

    def test_retagging_preserves_reviewed_question_content_version_and_date(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            for rel in ('framework/bom.json', 'framework/site_rights.json', 'data/companies.json'):
                destination = fixture / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((ROOT / rel).read_bytes())
            source = load(graph_mod.QUESTIONS)
            source['version'] = '3.1.0'
            source['updated'] = '2030-01-01'
            source['records'][0]['text'] = '已审问题内容，不由骨架重生成覆盖。'
            source['records'][0]['node'] = 'part:not-current'
            (fixture / graph_mod.QUESTIONS).write_text(json.dumps(source))
            _, questions = graph_mod.build(fixture)
            self.assertEqual(questions['version'], source['version'])
            self.assertEqual(questions['updated'], source['updated'])
            self.assertEqual([q['id'] for q in questions['records']], [q['id'] for q in source['records']])
            self.assertEqual(questions['records'][0]['text'], source['records'][0]['text'])
            self.assertEqual(questions['records'][0]['status'], source['records'][0]['status'])
            self.assertNotEqual(questions['records'][0]['node'], 'part:not-current')

    def test_financial_scope_words_do_not_move_reviewed_legacy_query_cells(self):
        expected = {'M03-Q01': 4, 'M03-Q03': 1, 'M03-Q04': 5, 'M11-Q05': 5,
                    'M13-Q01': 2, 'M13-Q03': 3, 'M13-Q07': 2, 'M13-Q08': 1, 'M13-Q09': 2}
        questions = {q['id']: q for q in self.questions['records']}
        for qid, cell in expected.items():
            self.assertEqual(questions[qid]['variable_class'], cell, qid)

    def test_objects_are_exactly_the_skeleton(self):
        kinds = {}
        for o in self.graph['objects']:
            kinds[o['kind']] = kinds.get(o['kind'], 0) + 1
        systems = {k for k, v in self.bom['systems'].items() if isinstance(v, dict)}
        self.assertEqual(kinds, {'root': 1, 'system': len(systems), 'chain': sum(len(v.get('chains', [])) for v in self.bom['systems'].values() if isinstance(v, dict)),
                                 'part': len(self.bom['parts']), 'site_right': len(self.rights), 'actor': len(self.companies)})
        for prefix in ('scope:', 'ecosystem:', 'arch:', 'tech:', 'workload:', 'demand:', 'activity:', 'space:'):
            self.assertFalse(any(o.startswith(prefix) for o in self.objects), prefix + ' objects are retired')
        self.assertNotIn('system:safety', self.objects)
        for key in ('views', 'navigation', 'hardware_domains', 'catalog_topic_mappings', 'research_topics'):
            self.assertNotIn(key, self.graph, key + ' is retired')
        part = self.objects['part:transformer']
        self.assertEqual((part['system'], part['chain'], part['stage'], part['parent']), ('power', '变电', 'grid', 'chain:power/2'))
        self.assertIn('part:substation', part['aliases'], 'old ids point at their skeleton node')
        self.assertEqual(self.objects['site:grid']['parent'], 'root')
        self.assertEqual(self.objects['system:compute']['parent'], 'system:it')

    def test_relations_follow_the_registries(self):
        supplies = {(r['source'], r['target']) for r in self.graph['relations'] if r['type'] == 'supplies'}
        for p in self.bom['parts']:
            for c in p['companies']:
                self.assertIn(('actor:' + c, 'part:' + p['id']), supplies)
        self.assertEqual(len(supplies), sum(len(p['companies']) for p in self.bom['parts']))
        parents = {r['source']: r['target'] for r in self.graph['relations'] if r['type'] == 'part_of'}
        for o in self.graph['objects']:
            if o['kind'] in ('system', 'chain', 'part', 'site_right'):
                self.assertEqual(parents[o['id']], o['parent'], o['id'])

    def test_questions_keep_their_ids_and_gain_node_and_class(self):
        old = load('framework/research_questions.json')['records']
        self.assertEqual([q['id'] for q in self.questions['records']], [q['id'] for q in old], '458 question IDs are the M4 / Spark contract')
        for q in self.questions['records']:
            self.assertIn(q['variable_class'], (1, 2, 3, 4, 5), q['id'])
            self.assertIn(q['node'], self.objects, q['id'])
            self.assertTrue(set(q['object_ids']) <= set(self.objects), q['id'])
            self.assertTrue(q['legacy_module'], q['id'])
            for key in ('views', 'topic_id', 'module_id'):
                self.assertNotIn(key, q, q['id'])
        nodes = {q['id']: q['node'] for q in self.questions['records']}
        self.assertEqual(nodes['M01-Q01'], 'root')
        self.assertTrue(any(n.startswith('part:') for n in nodes.values()))
        self.assertTrue(any(n.startswith('site:') for n in nodes.values()))

    def test_every_legacy_id_resolves(self):
        for old, target in graph_mod.LEGACY_NODES.items():
            self.assertIn(target, self.objects, old)
            self.assertEqual(graph_mod.node_for(old, self.bom), target, old)
        for old, target in self.bom['aliases'].items():
            self.assertEqual(graph_mod.node_for('part:' + old, self.bom), target if target.startswith('site:') else 'part:' + target, old)
        self.assertEqual(graph_mod.node_for('scope:M06', self.bom), 'root')
        self.assertIsNone(graph_mod.node_for('part:never-existed', self.bom))


if __name__ == '__main__':
    unittest.main()
