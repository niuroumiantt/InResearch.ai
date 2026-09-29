#!/usr/bin/env python3
"""Catalog projection tests: source metadata never becomes adopted evidence or SKU facts."""

from inresearch.paths import project_root
import csv
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from inresearch.knowledge import registry as research


class CatalogBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inresearch-catalog-test-')
        self.root = Path(self.temp.name)
        # 图谱 3.0 的骨架片段：部件 → 链路 → 系统 → 根；主体只经 supplies 相连，不进导航闭包
        self.graph = {
            'version': '3.0.0',
            'objects': [{'id': 'root', 'kind': 'root', 'parent': None}, {'id': 'system:it', 'kind': 'system', 'parent': 'root'},
                        {'id': 'system:compute', 'kind': 'system', 'parent': 'system:it'}, {'id': 'chain:compute/1', 'kind': 'chain', 'parent': 'system:compute'},
                        {'id': 'part:gpu', 'kind': 'part', 'parent': 'chain:compute/1'}, {'id': 'part:cpu', 'kind': 'part', 'parent': 'chain:compute/1'},
                        {'id': 'part:server', 'kind': 'part', 'parent': 'chain:compute/1'}, {'id': 'part:dram', 'kind': 'part', 'parent': 'system:memory'},
                        {'id': 'part:hbm', 'kind': 'part', 'parent': 'system:memory'}, {'id': 'part:rack-frame', 'kind': 'part', 'parent': 'system:facility'},
                        {'id': 'actor:vendor', 'kind': 'actor', 'parent': None}],
            'relations': [
                {'type': 'part_of', 'source': 'part:gpu', 'target': 'chain:compute/1'},
                {'type': 'part_of', 'source': 'chain:compute/1', 'target': 'system:compute'},
                {'type': 'part_of', 'source': 'system:compute', 'target': 'system:it'},
                {'type': 'part_of', 'source': 'system:it', 'target': 'root'},
                {'type': 'supplies', 'source': 'actor:vendor', 'target': 'part:gpu'},
            ]}
        self.write('data/companies.json', {'records': [{'company_id': 'vendor', 'name': 'Vendor', 'name_cn': '厂商', 'is_group': True}]})

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def product(self, line='图形处理器', **changes):
        return dict(company_id='vendor', company_en='Vendor', company_cn='厂商', product_line=line,
                    bom_parts=['gpu'], module='M06', status='mature', is_group=True,
                    representative_models='GPU family / future models', website='vendor.example', **changes)

    def doc(self, line='图形处理器', model='G100', **changes):
        row = dict(company_id='vendor', product_line=line, model=model, bom_part='gpu',
                   doc_type='DS', status='todo', source_url='', doc_id='')
        row.update(changes)
        return row

    def plans(self, rows):
        path = self.root / 'data/product_docs_plan.csv'
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def build(self, products=None):
        if products is not None:
            self.write('data/products.json', {'records': products})
        return research.build_catalog(self.root, self.graph)

    def test_product_line_identity_preserves_chinese_and_survives_reorder(self):
        rows = [self.product('中文甲'), self.product('中文乙')]
        first = self.build(rows)
        ids = {p['product_line']: p['id'] for p in first['products']}
        self.assertEqual(len(set(ids.values())), 2)
        rows.reverse()
        rows[0]['status'] = 'tight'
        rows[0]['representative_models'] = 'new family description'
        second = self.build(rows)
        self.assertEqual({p['product_line']: p['id'] for p in second['products']}, ids)
        self.assertTrue(all(p['identity_kind'] == 'product_line' for p in second['products']))
        self.assertTrue(all(p['is_group'] for p in second['products']))
        self.assertTrue(second['companies'][0]['is_group'])
        self.assertEqual(second['products'][0]['source_record'], rows[0])
        self.assertEqual(second['products'][0]['models'], [])  # prose was not split into invented SKUs

    def test_explicit_multiple_bom_parts_and_no_module_inference(self):
        rows = [self.product('内存'), self.product('仅模块')]
        rows[0]['bom_parts'] = ['dram', 'hbm', 'unknown']
        rows[0]['bom_part'] = 'cpu'
        rows[1].pop('bom_parts')
        result = self.build(rows)
        memory, module_only = result['products']
        self.assertEqual(memory['object_ids'], ['part:cpu', 'part:dram', 'part:hbm'])
        self.assertEqual(memory['unmapped_bom_parts'], ['unknown'])
        self.assertEqual(memory['mapping_status'], 'needs_review')
        self.assertEqual(module_only['object_ids'], [])
        self.assertEqual(module_only['related_object_ids'], [])
        self.assertEqual(module_only['mapping_status'], 'needs_review')

    def test_skeleton_closure_is_the_only_navigation(self):
        result = self.build([self.product()])['products'][0]
        self.assertEqual(result['object_ids'], ['part:gpu'])
        self.assertEqual(result['related_object_ids'], ['chain:compute/1', 'part:gpu', 'root', 'system:compute', 'system:it'])
        self.assertEqual(result['catalog_node_ids'], ['chain:compute/1'])
        self.assertEqual(result['catalog_node_basis'], 'skeleton_parent')
        self.assertFalse(any(oid.startswith('actor:') for oid in result['related_object_ids']), 'suppliers are relations, not navigation context')
        self.assertNotIn('representation', result)  # no actual physical installation asserted

    def test_planned_even_if_label_downloaded_is_not_indexed_or_read(self):
        plan = self.doc(status='downloaded', source_url='https://vendor.example/datasheet.pdf', doc_id='D123')
        self.plans([plan])
        result = self.build([self.product()])
        row = result['documents'][0]
        self.assertEqual(row['kind'], 'document_plan')
        self.assertEqual(row['status'], 'downloaded')
        self.assertEqual(row['verification_status'], 'planned_only')
        self.assertEqual(row['current_availability'], 'not_checked')
        self.assertEqual(row['source_record'], plan)
        self.assertEqual(row['acceptance'], 'catalog_metadata')
        self.assertNotIn('coverage', row)
        self.assertNotIn('review', row)
        self.assertEqual(result['products'][0]['document_ids'], [])
        self.assertEqual(result['products'][0]['plan_ids'], [row['id']])

    def test_primary_index_wins_and_does_not_merge_fallback(self):
        self.write('data/product_library_index.json', {'records': [self.doc(doc_id='D1', status='verified')]})
        self.write('docs/inbox/inresearch-alignment/library_index.json', {'records': [self.doc(doc_id='D2', status='downloaded')]})
        result = self.build([self.product()])
        self.assertEqual(result['counts']['indexed_documents'], 1)
        row = result['documents'][0]
        self.assertEqual(row['doc_id'], 'D1')
        self.assertEqual(row['verification_status'], 'historical_index_metadata')
        self.assertEqual(row['current_availability'], 'not_checked')
        self.assertEqual(row['status'], 'verified')
        self.assertEqual(result['sources']['index_selection'], 'primary')
        self.write('data/product_library_index.json', {'records': []})
        fallback = self.build()
        self.assertEqual(fallback['documents'][0]['doc_id'], 'D2')
        self.assertEqual(fallback['sources']['index_selection'], 'alignment_fallback')

    def test_legacy_path_punctuation_match_preserves_raw_source_line(self):
        original = self.doc('训练-推理GPU', doc_id='D1', status='needs_manual')
        self.write('docs/inbox/inresearch-alignment/library_index.json', {'records': [original]})
        result = self.build([self.product('训练/推理GPU')])
        row = result['documents'][0]
        self.assertEqual(row['product_ids'], [result['products'][0]['id']])
        self.assertEqual(row['product_match_basis'], 'unique_normalized_product_line')
        self.assertEqual(row['source_record']['product_line'], '训练-推理GPU')
        self.assertEqual(row['status'], 'needs_manual')

    def test_ambiguous_normalized_line_never_links_to_both_products(self):
        self.plans([self.doc('A-B')])
        result = self.build([self.product('A/B'), self.product('AB')])
        self.assertEqual(result['documents'][0]['product_ids'], [])
        self.assertEqual(result['documents'][0]['product_match_basis'], 'unmatched_or_ambiguous')
        self.assertTrue(all(p['plan_ids'] == [] for p in result['products']))

    def test_models_and_document_links_are_local_to_exact_product_line(self):
        self.plans([self.doc('中文甲', model='G100'), self.doc('中文乙', model='G100'), self.doc('中文甲', model='line', doc_type='BR')])
        self.write('data/product_library_index.json', {'records': [self.doc('中文甲', model='G100', doc_id='D1', status='verified')]})
        result = self.build([self.product('中文甲'), self.product('中文乙')])
        first, second = result['products']
        self.assertEqual(len(first['models']), 1)
        self.assertEqual(first['models'][0]['label'], 'G100')
        self.assertEqual(first['models'][0]['identity_kind'], 'registered_model_label')
        self.assertEqual(len(first['models'][0]['document_ids']), 1)
        self.assertEqual(second['models'][0]['document_ids'], [])
        self.assertNotEqual(first['models'][0]['id'], second['models'][0]['id'])
        second_plan = next(d for d in result['documents'] if d['kind'] == 'document_plan' and d['product_line'] == '中文乙')
        self.assertEqual(second_plan['linked_document_ids'], [])

    def test_exact_admin_filters_and_non_invented_links(self):
        rows = [self.product('中文/产品线')]
        result = self.build(rows)
        p = result['products'][0]
        self.assertEqual(parse_qs(urlsplit(p['admin_url']).query), {'company': ['vendor'], 'line': ['中文/产品线']})
        self.assertEqual(p['source_url'], 'https://vendor.example')
        rows[0]['website'] = 'vendor.example or another company'
        self.assertIsNone(self.build(rows)['products'][0]['source_url'])
        rows[0]['website'] = 'javascript:alert(1)'
        self.assertIsNone(self.build(rows)['products'][0]['source_url'])

    def test_explicit_document_id_does_not_fall_back_to_other_versions(self):
        self.plans([self.doc(doc_id='D2')])
        self.write('data/product_library_index.json', {'records': [self.doc(doc_id='D1', status='verified'),
                                                                  self.doc(doc_id='D2', status='downloaded')]})
        result = self.build([self.product()])
        plan = next(d for d in result['documents'] if d['kind'] == 'document_plan')
        wanted = next(d for d in result['documents'] if d['kind'] == 'indexed_document' and d['doc_id'] == 'D2')
        self.assertEqual(plan['linked_document_ids'], [wanted['id']])
        self.assertEqual(plan['document_link_basis'], 'explicit_doc_id')

    def test_descriptive_website_and_ir_text_never_become_links(self):
        invalid = ['各家官网', '各公司官网', '见供配电表', 'https://各家官网',
                   'localhost', 'http://127.0.0.1', 'https://bad_domain.example']
        for value in invalid:
            with self.subTest(value=value):
                product = self.product()
                product['website'] = value
                self.write('data/companies.json', {'records': [{'company_id': 'vendor', 'name': 'Vendor',
                                                               'website': value, 'ir_url': value}]})
                result = self.build([product])
                self.assertIsNone(result['products'][0]['source_url'])
                self.assertIsNone(result['companies'][0]['source_url'])
                self.assertEqual(result['products'][0]['source_record']['website'], value)
                self.assertEqual(result['companies'][0]['source_record']['ir_url'], value)

    def test_dotted_internationalized_domains_remain_linkable(self):
        for value, expected in [('例子.中国', 'https://例子.中国'),
                                ('https://例子.中国/产品', 'https://例子.中国/产品'),
                                ('https://vendor.example:443/products', 'https://vendor.example:443/products')]:
            with self.subTest(value=value):
                product = self.product()
                product['website'] = value
                self.assertEqual(self.build([product])['products'][0]['source_url'], expected)

    def test_all_existing_corpus_website_descriptions_stay_unlinked(self):
        root = project_root()
        catalog = research.build_catalog(root, research.read_json(root / 'framework/research_graph.json'))
        descriptions = [p for p in catalog['products'] if p['website'] in ('各家官网', '见供配电表')]
        self.assertEqual(len(descriptions), 21)
        self.assertEqual(sum(p['website'] == '各家官网' for p in descriptions), 20)
        for product in descriptions:
            self.assertIsNone(product['source_url'])
            self.assertEqual(product['source_record']['website'], product['website'])

    def test_existing_repository_counts_references_and_no_adoption(self):
        root = project_root()
        graph = research.read_json(root / 'framework/research_graph.json')
        result = research.build_catalog(root, graph)
        self.assertEqual(result['counts'], {'product_lines': 175, 'companies': 166, 'plans': 801, 'indexed_documents': 6})
        product_ids = {p['id'] for p in result['products']}
        document_ids = {d['id'] for d in result['documents']}
        self.assertEqual(len(product_ids), 175)
        self.assertEqual(len(document_ids), 807)
        for row in result['documents']:
            self.assertTrue(set(row['product_ids']) <= product_ids)
            self.assertEqual(row['current_availability'], 'not_checked')
            self.assertEqual(row['acceptance'], 'catalog_metadata')
        self.assertTrue(all(p['object_ids'] for p in result['products']))
        self.assertTrue(all(set(p['document_ids'] + p['plan_ids']) <= document_ids for p in result['products']))
        nvidia = next(p for p in result['products'] if p['company_id'] == 'nvidia' and p['product_line'] == '训练/推理GPU')
        self.assertEqual(len(nvidia['document_ids']), 6)
        self.assertEqual(len(nvidia['plan_ids']), 10)
        self.assertTrue(all(d['status'] == 'todo' for d in result['documents'] if d['kind'] == 'document_plan'))


if __name__ == '__main__':
    unittest.main()
