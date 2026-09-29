"""登记表两列（node、variable_class）由骨架派生，不手写：存储值等于派生值，每个节点都在骨架里，录价自动带列。"""
import json
import unittest
from pathlib import Path

from inresearch.knowledge import nodes

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class NodeColumnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = nodes.build_index(ROOT)
        cls.derived = nodes.derive(ROOT)

    def test_stored_values_equal_their_derivation(self):
        self.assertEqual(nodes.problems(ROOT), [])
        self.assertEqual(set(self.derived), set(nodes.REGISTRIES), 'every registry exists and is covered')

    def test_every_record_names_a_skeleton_node_and_a_variable_class(self):
        for rel, (doc, key, _changed, _rows, _indent) in self.derived.items():
            for rec in doc[key]:
                self.assertTrue(nodes.valid_node(rec.get('node'), self.idx), (rel, rec.get('node')))
                self.assertIn(rec.get('variable_class'), (1, 2, 3, 4, 5), rel)

    def test_indicators_are_registered_one_by_one(self):
        ids = {i['id'] for i in load('framework/indicators.json')['indicators']}
        self.assertEqual(ids, set(nodes.INDICATOR_CLASS), 'a new indicator must be classed in knowledge.nodes; a removed one must leave the table')
        lead = {i['id'] for i in load('framework/indicators.json')['indicators'] if i['node'].startswith('part:') and 'lead_time' in i['id']}
        self.assertTrue(lead)
        for i in load('framework/indicators.json')['indicators']:
            if i['id'] in lead:
                self.assertEqual(i['variable_class'], 4, i['id'])

    def test_prices_hang_on_parts_rights_or_root(self):
        by_node = {}
        for r in load('data/prices.json')['records']:
            by_node.setdefault(r['node'], set()).add(r['series_id'])
        self.assertIn('transformer-lead-time', by_node.get('part:transformer', set()))
        self.assertTrue(by_node.get('root'), 'benchmarks and capex series hang on the root')
        for r in load('data/prices.json')['records']:
            if r['category'] == 'lead-time':
                self.assertEqual(r['variable_class'], 4, r['series_id'])
            if r['category'] == 'efficiency':
                self.assertEqual(r['variable_class'], 2, r['series_id'])

    def test_products_derive_system_and_chain_from_their_first_part(self):
        parts = {p['id']: p for p in load('framework/bom.json')['parts']}
        for rec in load('data/products.json')['records']:
            self.assertEqual(rec['variable_class'], 1)
            self.assertEqual(rec['node'], 'part:' + rec['bom_parts'][0], rec['product_line'])
            self.assertEqual(rec['nodes'], ['part:' + p for p in rec['bom_parts']])
            self.assertEqual((rec['system'], rec['chain']), (parts[rec['bom_parts'][0]]['system'], parts[rec['bom_parts'][0]].get('chain')))
        memory = [r for r in load('data/products.json')['records'] if r['system'] == 'memory']
        self.assertTrue(memory, '内存单列：DRAM/HBM 产品线挂内存系统，不再归存储')

    def test_companies_are_actors(self):
        for rec in load('data/companies.json')['records']:
            self.assertEqual((rec['node'], rec['variable_class']), ('actor:' + rec['company_id'], 5))

    def test_facts_follow_their_metric(self):
        metrics = {m['metric_id']: m for m in load('framework/metrics.json')['metrics']}
        for rec in load('data/facts.json')['records'][:500]:
            m = metrics[rec['metric_id']]
            self.assertEqual((rec['node'], rec['variable_class']), (m['node'], m['variable_class']), rec['fact_id'])

    def test_a_new_price_record_gets_its_columns(self):
        self.assertEqual(nodes.series_fields({'series_id': 'transformer-lead-time', 'category': 'lead-time', 'unit': '月'}, self.idx),
                         {'node': 'part:transformer', 'variable_class': 4})
        self.assertEqual(nodes.series_fields({'series_id': 'brand-new-benchmark', 'category': 'benchmark', 'unit': 'GW'}, self.idx),
                         {'node': 'root', 'variable_class': 1})
        self.assertEqual(nodes.series_fields({'series_id': 'x', 'category': 'rent', 'unit': '$/kW/月'}, nodes.build_index(ROOT / 'nowhere')),
                         {'node': 'root', 'variable_class': 3}, 'a root without registries still classes by unit')

    def test_unit_rules(self):
        self.assertEqual([nodes.unit_class(u) for u in ('月', 'PUE', '$/hr', '人/MW', 'MW', 'kW/机柜', '%', '¢/kWh', '万张')],
                         [4, 2, 3, 2, 1, 1, None, 3, 1])


if __name__ == '__main__':
    unittest.main()
