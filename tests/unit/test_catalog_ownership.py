import copy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from inresearch.workflow import catalog_browse, catalog_materials, company_window, product_catalog as catalog
from inresearch.workflow.catalog_ownership_audit import inspect
from tests.unit.test_company_window import company_catalog_fixture


class CatalogOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        env=patch.dict(os.environ,{},clear=True); env.start(); self.addCleanup(env.stop)
        (self.root/'framework').mkdir()
        (self.root/'framework/tco_targets.json').write_text(json.dumps({'targets':[]}))
        self.data=company_catalog_fixture()

    def test_new_support_page_delivery_fails_before_creating_catalog(self):
        for brand in ('kioxia','samsung','micron','intel','hgst'):
            data=copy.deepcopy(self.data)
            url='https://www.supermicro.com/en/products/storage/pci-e/'+brand
            data['products'][0].update(name=brand+' NVMe',source_url=url)
            data['sources'][0]['source_url']=url
            with self.subTest(brand=brand), self.assertRaisesRegex(ValueError,'ownership conflict'):
                catalog.receive(self.root,data,'supermicro')
        self.assertFalse(catalog.database(self.root,'supermicro').exists())

    def test_old_misattribution_is_removed_from_every_product_view_but_evidence_survives(self):
        catalog.receive(self.root,self.data,'supermicro')
        bad=copy.deepcopy(self.data['products'][0])
        bad.update(id='supermicro-'+'a'*20,name='Samsung NVMe',source_url='https://www.supermicro.com/en/products/storage/pci-e/samsung',
                   product_url='https://www.supermicro.com/en/products/storage/pci-e/samsung')
        path=catalog.database(self.root,'supermicro')
        with sqlite3.connect(path) as db:
            run=db.execute('SELECT id FROM runs').fetchone()[0]
            db.execute('INSERT INTO products VALUES(?,?,?)',(bad['id'],run,json.dumps(bad)))
            db.execute('INSERT INTO versions VALUES(?,?,?)',(bad['id'],bad['source_sha256'],json.dumps(bad)))
            material={'id':'b'*64,'format':'pdf','urls':['https://www.supermicro.com/manuals/test.pdf'],
                      'links':[{'product_id':bad['id'],'url':'https://www.supermicro.com/manuals/test.pdf','label':'TEST_VALUE','source_url':bad['source_url'],'source_sha256':bad['source_sha256']}]}
            db.execute('INSERT INTO materials VALUES(?,?)',(material['id'],json.dumps(material)))
        before=path.read_bytes()
        self.assertEqual(catalog.index_snapshot(self.root,'supermicro')['summary']['entities'],5)
        self.assertEqual(catalog.summary_snapshot(self.root,'supermicro')['summary']['entities'],5)
        self.assertEqual(company_window.catalog_groups(self.root,'supermicro')['summary']['entities'],5)
        self.assertEqual(catalog_browse.query(self.root)['matched'],5)
        self.assertEqual(catalog_browse.query(self.root,q='Samsung')['matched'],0)
        self.assertNotIn('Samsung',catalog.csv_export(catalog.snapshot(self.root,'supermicro')))
        self.assertIsNone(catalog.product_snapshot(self.root,bad['id'],'supermicro')['product'])
        self.assertIsNone(catalog.series_snapshot(self.root,bad['id'],'supermicro')['series'])
        materials=catalog_materials.query(self.root,'supermicro')
        self.assertEqual(materials['items'][0]['links'],[])
        self.assertEqual(materials['unassigned'],1)
        report=inspect(self.root)
        self.assertTrue(report['ok'])
        self.assertEqual((report['checked_entities'],report['conflicts']),(6,1))
        self.assertEqual(path.read_bytes(),before)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM products').fetchone()[0],6)
            self.assertEqual(db.execute('SELECT count(*) FROM versions').fetchone()[0],6)

    def test_other_company_audit_and_component_mentions_do_not_change_products(self):
        self.assertFalse(inspect(self.root)['ok'])
        data=copy.deepcopy(self.data)
        data['products'][0]['tables'][0]['rows'][0][1]['text']='Samsung DDR5 + Kioxia SSD + NVIDIA GPU'
        catalog.receive(self.root,data,'supermicro')
        self.assertEqual(catalog.index_snapshot(self.root,'supermicro')['summary']['entities'],5)
        self.assertEqual(inspect(self.root)['conflicts'],0)
        # Other company catalogs are audited even when no automatic exclusion
        # rule exists for their paths; an explicit foreign title needs review.
        from inresearch.workflow.catalog_ownership import audit
        for company in catalog.COMPANIES:
            if company not in ('samsung',):
                self.assertEqual(audit([{'name':'Samsung PM1743'}],company)['review_required'],1)


if __name__=='__main__':
    unittest.main()
