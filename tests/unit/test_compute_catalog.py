import copy
import json
from pathlib import Path
import unittest

from inresearch.workflow import compute_catalog as compute, product_catalog as catalog


class ComputeCatalogTests(unittest.TestCase):
    def test_classifies_products_not_vendors_or_hosted_components(self):
        cases=[('intel','Intel Gaudi 3','accelerator','unknown'),('intel','Xeon 6980P','cpu','chip'),
               ('amd','AMD Instinct MI300X','gpu','unknown'),('nvidia','NVIDIA H200','gpu','unknown'),
               ('nvidia','NVIDIA Grace CPU Superchip','cpu','board'),('nvidia','NVIDIA DGX H200','unknown','system'),
               ('nvidia','NVIDIA BlueField-3 DPU','excluded','unknown'),('arm','Neoverse V3','excluded','ip'),
               ('hygon-dcu','Z100','unknown','unknown'),('hygon-dcu','K100','unknown','unknown')]
        for company,name,category,form in cases:
            with self.subTest(name=name):
                p={'name':name,'kind':'named_product','category':'GPU / CPU','navigation':{'group':'original'}}
                before=copy.deepcopy(p);result=compute.project(p,company)
                self.assertEqual((result['category'],result['form']),(category,form))
                self.assertEqual(result['architecture'],'');self.assertEqual(p,before)
        result=compute.project({'name':'NVIDIA H200 series','kind':'family_or_directory'},'nvidia')
        self.assertEqual(result['form'],'series')

    def test_reviewed_architecture_requires_receipt_and_quote(self):
        ref={'url':'https://www.hygon.cn/product/dcu','sha256':'a'*64}
        value={'category':'gpu','form':'board','architecture':'GPGPU','architecture_quote':'model-specific GPGPU', 'source_refs':[ref]}
        compute.validate(value,{('a'*64,ref['url'])})
        with self.assertRaisesRegex(ValueError,'snapshot'):compute.validate(value,set())
        with self.assertRaisesRegex(ValueError,'quote'):compute.validate({**value,'architecture_quote':''},{('a'*64,ref['url'])})
        with self.assertRaises(ValueError):compute.validate({**value,'category':'dcu'},{('a'*64,ref['url'])})

    def test_registry_reuses_company_ids_and_preserves_parent_lines(self):
        root=Path(__file__).resolve().parents[2]
        records=json.loads((root/'data/companies.json').read_text())['records']
        ids=[r['company_id'] for r in records]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(set(catalog.COMPANIES)<=set(ids))
        for child,parent in [('huawei-kunpeng','huawei'),('huawei-ascend','huawei'),('hygon-dcu','hygon')]:
            block=catalog.company_block(child)
            self.assertEqual(block['parent_company_id'],parent);self.assertEqual(block['country'],'CN')
        self.assertFalse(catalog.official('https://hygon.cn.evil.test/x','hygon'))
        self.assertFalse(catalog.official('https://www.mthreads.com/product','metax'))
        self.assertTrue(catalog.official('https://docs.mthreads.com/s4000/','moore-threads'))

    def test_compute_roundtrip_preserves_navigation_and_rejects_missing_proof(self):
        import tempfile
        from test_product_catalog import bundle
        payload=bundle();p=payload['products'][0]
        p['compute']={'category':'gpu','form':'board','architecture':'','evidence_quote':p['name'],
                      'source_refs':[{'url':p['source_url'],'sha256':p['source_sha256']}]}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'framework').mkdir()
            (root/'framework/tco_targets.json').write_text('{"targets": []}')
            bad=copy.deepcopy(payload);bad['products'][0]['compute']['source_refs'][0]['sha256']='f'*64
            with self.assertRaisesRegex(ValueError,'snapshot'):catalog.receive(root,bad)
            self.assertFalse(catalog.database(root).exists())
            catalog.receive(root,payload)
            view=catalog.index_snapshot(root)['products'][0]
            self.assertEqual(view['compute']['category'],'gpu')
            self.assertEqual(view['compute']['form'],'board')
            self.assertEqual(view['navigation'],catalog.classify(p))
            self.assertEqual(catalog.product_snapshot(root,p['id'])['product']['compute']['architecture'],'')
