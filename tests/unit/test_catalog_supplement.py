import copy
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from inresearch.workflow import product_catalog as catalog, catalog_materials, company_window
from inresearch.workflow.catalog_bundle import import_bundle
from tests.unit.test_company_window import company_catalog_fixture


def historical_fixture():
    base=company_catalog_fixture()
    data=copy.deepcopy(base)
    data.update(catalog_mode='historical_supplement',generated_at='2026-10-07T01:00:00+00:00')
    old=data['products'][0]
    old.update(source_sha256='c'*64,observed_at='2026-09-23T17:55:00+00:00')
    old['tables'][0]['rows'][0][1]['text']='OLD_TEST_VALUE'
    new=copy.deepcopy(old)
    new.update(id='supermicro-'+'f'*20,name='SYS-6039P-TXRT',source_url='https://www.supermicro.com/en/products/system/3u/6039/sys-6039p-txrt.php',source_sha256='d'*64)
    data['products']=[old,new]
    data['sources']=[{'sha256':p['source_sha256'],'source_url':p['source_url']} for p in data['products']]
    link={'product_id':new['id'],'label':'Test Report','url':'https://www.supermicro.com/products/powersupply/80PLUS/test.pdf',
          'source_url':new['source_url'],'source_sha256':new['source_sha256']}
    data['material_index']=[{'id':'a'*64,'format':'pdf','urls':[link['url']],'links':[link]},
                            {'id':'b'*64,'format':'pdf','urls':['https://www.supermicro.com/manuals/other/unassigned.pdf'],'links':[]}]
    return base,data


class CatalogSupplementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        env=patch.dict('os.environ',{},clear=True);env.start();self.addCleanup(env.stop)
        (self.root/'framework').mkdir()
        (self.root/'framework/tco_targets.json').write_text(json.dumps({'targets':[]}))

    def test_historical_supplement_preserves_current_products_and_indexes_unassigned_documents(self):
        base,data=historical_fixture()
        catalog.receive(self.root,base,'supermicro')
        receipt=catalog.receive(self.root,data,'supermicro')
        self.assertEqual((receipt['added_products'],receipt['preserved_products'],receipt['current_products']),(1,5,6))
        value=catalog.snapshot(self.root,'supermicro')
        current=next(p for p in value['products'] if p['id']==base['products'][0]['id'])
        self.assertEqual(current['tables'],base['products'][0]['tables'])
        with sqlite3.connect(catalog.database(self.root,'supermicro')) as db:
            self.assertEqual(json.loads(db.execute('SELECT payload FROM products WHERE id=?',(current['id'],)).fetchone()[0]),base['products'][0])
            self.assertEqual(db.execute('SELECT count(*) FROM versions').fetchone()[0],7)
        self.assertEqual(catalog_materials.query(self.root,'supermicro','Test Report')['matched'],1)
        self.assertEqual(catalog_materials.query(self.root,'supermicro','unassigned')['matched'],1)
        self.assertEqual(catalog_materials.query(self.root,'supermicro')['unassigned'],1)
        self.assertTrue(catalog.receive(self.root,data,'supermicro')['replayed'])

    def test_material_only_batch_and_completed_bundle_replay_keep_product_union(self):
        base,data=historical_fixture();catalog.receive(self.root,base,'supermicro')
        catalog.receive(self.root,data,'supermicro')
        next_batch=copy.deepcopy(data)
        next_batch.update(products=[],generated_at='2026-10-07T02:00:00+00:00')
        receipt=catalog.receive(self.root,next_batch,'supermicro')
        self.assertEqual(receipt['current_products'],6)
        self.assertTrue(catalog.receive(self.root,data,'supermicro')['replayed'])
        self.assertEqual(catalog_materials.query(self.root,'supermicro')['total'],2)

    def test_invalid_or_unknown_material_links_fail_without_adopting_products(self):
        base,data=historical_fixture();catalog.receive(self.root,base,'supermicro')
        for kind in ['mode','url','parent','identity']:
            broken=copy.deepcopy(data)
            if kind=='mode': broken['catalog_mode']='merge_typo'
            if kind=='url': broken['material_index'][0]['urls']=['https://fake.example/report.pdf']
            if kind=='parent': broken['material_index'][0]['links'][0]['product_id']='supermicro-'+'e'*20
            if kind=='identity': broken['material_index'][0]['id']='bad'
            with self.assertRaises(ValueError):catalog.receive(self.root,broken,'supermicro')
            self.assertEqual(len(catalog.snapshot(self.root,'supermicro')['products']),5)
            self.assertEqual(catalog_materials.query(self.root,'supermicro')['total'],0)

    def test_tar_links_and_unverified_batch_fail_before_database_creation(self):
        for name in ['../outside','originals/'+'a'*64+'.html']:
            stream=io.BytesIO()
            with tarfile.open(fileobj=stream,mode='w:gz') as tar:
                member=tarfile.TarInfo(name);member.type=tarfile.SYMTYPE;member.linkname='/etc/passwd';tar.addfile(member)
            stream.seek(0)
            with self.assertRaisesRegex(ValueError,'bundle member'):import_bundle(self.root,stream,'supermicro')
        self.assertFalse(catalog.database(self.root,'supermicro').exists())
