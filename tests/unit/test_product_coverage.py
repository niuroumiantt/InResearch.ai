import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from inresearch.workflow import product_catalog as catalog
from inresearch.workflow import product_coverage as coverage
from tests.unit.test_product_catalog import bundle


def nvidia_delivery():
    data = bundle()
    template = data['products'][0]
    products = []
    for index, (name, tables) in enumerate((('H200', True), ('H200 NVL', True), ('HGX H100', True), ('B300', False))):
        product = copy.deepcopy(template)
        product['id'] = 'nvidia-' + str(index) * 20
        product['name'] = name
        if not tables:
            product['tables'] = []
            product['extraction_status'] = 'no_native_tables'
        products.append(product)
    data['products'] = products
    return data


class ProductCoverageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = patch.dict('os.environ', {}, clear=True)
        env.start(); self.addCleanup(env.stop)
        (self.root / 'data').mkdir()
        (self.root / 'data/products.json').write_text(json.dumps({'records': [
            {'company_id': 'nvidia', 'company_cn': '英伟达', 'company_en': 'NVIDIA', 'sheet': '3-算力芯片与核心器件',
             'category': 'GPU/AI加速', 'product_line': '训练/推理GPU', 'priority': 'P0',
             'representative_models': 'H100/H200（Hopper）、B200/B300、GB200 NVL72'},
            {'company_id': 'dell', 'company_cn': '戴尔', 'sheet': '4-服务器与整机', 'category': '品牌整机（国内）',
             'product_line': 'AI服务器', 'priority': 'P0', 'representative_models': 'PowerEdge XE9680'},
            {'company_id': 'micron', 'company_cn': '美光', 'sheet': '6-存储', 'category': 'DRAM',
             'product_line': 'DRAM原厂', 'priority': 'P1', 'representative_models': 'HBM3E、DDR5 RDIMM'},
        ]}, ensure_ascii=False))

    def test_tags_match_catalog_names_and_link_to_best_entity(self):
        catalog.receive(self.root, nvidia_delivery())
        value = coverage.coverage(self.root)
        nvidia, dell, micron = value['lines']
        tags = {t['tag']: t for t in nvidia['tags']}
        self.assertEqual(list(tags), ['H100', 'H200', 'B200', 'B300', 'GB200 NVL72'])
        # exact name wins over a longer name that also contains the tag
        self.assertEqual(tags['H200']['product_name'], 'H200')
        self.assertEqual(tags['H200']['matches'], 2)
        # whole-word match inside a longer name
        self.assertEqual(tags['H100']['product_name'], 'HGX H100')
        # catalog entity without tables still counts as present, flagged
        self.assertEqual(tags['B300']['product_id'], 'nvidia-' + '3' * 20)
        self.assertFalse(tags['B300']['with_tables'])
        # B200 must not match B300; GB200 NVL72 is absent
        self.assertEqual(tags['B200']['matches'], 0)
        self.assertIsNone(tags['GB200 NVL72']['product_id'])
        self.assertEqual(nvidia['covered'], 3)
        self.assertEqual(nvidia['catalog'], {'company': 'nvidia', 'registered': True, 'available': True})
        # no catalog at all vs registered catalog not yet delivered
        self.assertEqual(dell['catalog'], {'company': None, 'registered': False, 'available': False})
        self.assertEqual(micron['catalog'], {'company': 'micron', 'registered': True, 'available': False})
        self.assertTrue(all(t['matches'] == 0 for t in dell['tags'] + micron['tags']))
        totals = value['totals']
        self.assertEqual((totals['lines_with_catalog'], totals['tags_in_catalog_lines'], totals['tags_covered']), (1, 5, 3))
        self.assertEqual(totals['catalog_companies'], ['nvidia'])

    def test_business_unit_lines_use_parent_catalog(self):
        records = json.loads((self.root / 'data/products.json').read_text())
        records['records'].append({'company_id': 'nvidia-networking', 'company_cn': '英伟达', 'sheet': '7-网络',
                                   'category': '交换机', 'product_line': 'IB', 'priority': 'P0',
                                   'representative_models': 'HGX H100'})
        (self.root / 'data/products.json').write_text(json.dumps(records, ensure_ascii=False))
        catalog.receive(self.root, nvidia_delivery())
        line = coverage.coverage(self.root)['lines'][-1]
        self.assertEqual(line['company_id'], 'nvidia-networking')
        self.assertEqual(line['catalog']['company'], 'nvidia')
        self.assertEqual(line['tags'][0]['product_name'], 'HGX H100')
        self.assertTrue(all(target in catalog.COMPANIES for target in coverage.CATALOG_OF.values()))

    def test_new_delivery_invalidates_cache(self):
        self.assertEqual(coverage.coverage(self.root)['totals']['tags_covered'], 0)
        catalog.receive(self.root, nvidia_delivery())
        self.assertEqual(coverage.coverage(self.root)['totals']['tags_covered'], 3)

    def test_model_tags_of_real_registry_are_nonempty(self):
        records = json.loads((Path(__file__).resolve().parents[2] / 'data/products.json').read_text())['records']
        tags = [coverage.model_tags(r['representative_models']) for r in records]
        self.assertGreater(sum(map(len, tags)), 300)
        self.assertEqual(coverage.model_tags('H100/H200（Hopper）、B200/B300'), ['H100', 'H200', 'B200', 'B300'])


if __name__ == '__main__':
    unittest.main()
