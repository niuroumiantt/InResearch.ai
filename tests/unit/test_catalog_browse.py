"""Hierarchical browsing is a read-only projection of archived official paths."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from inresearch.workflow import catalog_browse as browse, product_catalog as catalog
from tests.unit.test_company_window import company_catalog_fixture


def browse_fixture():
    """Production URL/model shapes; TEST_VALUE cells are illustrative, not research."""
    data=company_catalog_fixture()
    template=data['products'][0]
    entries=[('SYS-1028U-TNR4T+', 'system/1u/1028/sys-1028u-tnr4t_.php'),
             ('SYS-6029UZ-TR4+', 'system/2u/6029/sys-6029uz-tr4_.php'),
             ('SYS-6039P-TXRT', 'system/3u/6039/sys-6039p-txrt.php'),
             ('SC745', 'chassis/4u/745/sc745bac-r1k23b'),
             ('X11DPH', 'motherboard/xeon/c620/x11dph-t.php'),
             ('H11DSI', 'motherboard/amd/socket_sp3/h11dsi.php'),
             ('AOC-2020SA', 'accessories/addon/aoc-2020sa.php'),
             ('POWER-TEST', 'accessories/powersupply/pws-test.php'),
             ('DIRECTORY_TEST', 'unexplained/archive/test.php'),
             ('SRS-GB200-NVL72', 'rack/srs-gb200-nvl72')]
    for i,(name,path) in enumerate(entries):
        p=copy.deepcopy(template);url='https://www.supermicro.com/en/products/'+path
        sha=hashlib.sha256(url.encode()).hexdigest()
        p.update(id='supermicro-'+sha[:20],name=name,category='官方档案产品页',
                 source_url=url,source_sha256=sha,observed_at='2026-09-23',taxonomy=[],
                 kind='family_or_directory' if name=='DIRECTORY_TEST' else 'named_product')
        if name=='SRS-GB200-NVL72':
            cell=lambda text:{'text':text,'colspan':1,'rowspan':1,'header':False}
            groups=[('Rack-Level Specifications',[('GPUs','TEST_VALUE 72 NVIDIA B200 GPUs'),
                ('CPUs','TEST_VALUE 36 NVIDIA Grace CPUs'),('GPU Memory','TEST_VALUE 13.4 TB HBM3e'),
                ('System Memory','TEST_VALUE 17 TB LPDDR5X'),('Storage','TEST_VALUE 144 E1.S PCIe 5.0 drive bays')]),
                ('Rack Configuration',[('Nodes','TEST_VALUE 18 x 1U'),('Power','TEST_VALUE 132kW')]),
                ('Enclosure',[('Dimensions','TEST_VALUE W600 x D1068 x H2236')]),
                ('Networking',[('Compute Fabric','TEST_VALUE 400Gb/s Ethernet')]),
                ('Liquid Cooling',[('Liquid Cooling Options','TEST_VALUE 250kW CDU')]),
                ('Product SKUs',[('Part Number',name)])]
            p['tables']=[{'index':i+1,'section':section,'notes':'TEST_VALUE: UI fixture, not official parameter evidence',
                          'rows':[[cell(k),cell(v)] for k,v in rows]} for i,(section,rows) in enumerate(groups)]
        data['products'].append(p);data['sources'].append({'sha256':sha,'source_url':url})
    return data


class CatalogBrowseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        env=patch.dict(os.environ,{},clear=True);env.start();self.addCleanup(env.stop)
        self.root=Path(self.tmp.name)
        (self.root/'framework').mkdir();(self.root/'framework/tco_targets.json').write_text('{"targets":[]}')
        self.data=browse_fixture();catalog.receive(self.root,self.data,'supermicro')

    def test_hierarchy_counts_paths_and_unknown_bucket_without_changing_vendor_payloads(self):
        path=catalog.database(self.root,'supermicro');before=path.read_bytes()
        value=browse.query(self.root)
        roots={n['id']:n for n in value['roots']}
        self.assertEqual(sum(n['entities'] for n in value['roots']),len(self.data['products']))
        self.assertEqual((roots['boards']['entities'],roots['components']['entities'],roots['unmapped']['entities']),(2,2,1))
        servers=browse.query(self.root,line='servers')
        self.assertTrue({'servers/rack-systems','servers/chassis','servers/rack-scale'} <= {n['id'] for n in servers['children']})
        rack=browse.query(self.root,category='servers/rack-systems')
        self.assertEqual({n['label'] for n in rack['children']},{'1U 形态','2U 形态','3U 形态'})
        self.assertTrue(all(not any(k in item for k in ('tables','attachments','private_payload')) for item in value['items']))
        self.assertEqual(path.read_bytes(),before)
        with sqlite3.connect(path) as db:
            stored=json.loads(db.execute('SELECT payload FROM products WHERE id=?',(self.data['products'][-1]['id'],)).fetchone()[0])
        self.assertEqual(stored,self.data['products'][-1])

    def test_searches_specification_text_and_csv_uses_same_category_and_query(self):
        # Name matches neither the search nor the GPU value's spelling case.
        self.data['products'][-1]['name']='SRS-RACK-TEST'
        self.data['generated_at']='2026-10-07T01:00:00+00:00';catalog.receive(self.root,self.data,'supermicro')
        value=browse.query(self.root,q='b200',category='servers/rack-scale')
        self.assertEqual((value['matched'],len(value['items'])),(1,1))
        self.assertEqual(value['items'][0]['name'],'SRS-RACK-TEST')
        self.assertTrue(any('72 NVIDIA B200' in p['value'] for p in value['items'][0]['parameters']))
        csv=catalog.csv_export(catalog.snapshot(self.root,'supermicro'),query='b200',company='supermicro',category='servers/rack-scale')
        self.assertIn('SRS-RACK-TEST',csv);self.assertNotIn('SYS-6039P-TXRT',csv)
        self.assertEqual(browse.query(self.root,q='%')['matched'],0,'SQL wildcards are literal search text')

    def test_current_run_pagination_invalid_filters_and_safe_official_paths(self):
        value=browse.query(self.root,limit=3,offset=3)
        self.assertEqual(len(value['items']),3)
        self.assertNotEqual(value['items'][0]['id'],browse.query(self.root,limit=3)['items'][0]['id'])
        for args in ({'offset':-1},{'limit':51},{'category':'servers/nonexistent'},{'category':'boards/amd','line':'servers'}):
            with self.assertRaises(ValueError):browse.query(self.root,**args)
        p={'name':'GPU B200 server','source_url':'https://supermicro.com.evil.test/products/system/gpu/test'}
        self.assertEqual(browse.category_path(p)[0]['id'],'unmapped')
        p['source_url']='https://www.supermicro.com/en/products/unexplained/a.php'
        self.assertEqual(browse.category_path(p)[0]['id'],'unmapped','names never invent a product type')

    def test_configuration_spans_duplicate_parameters_and_detail_preserve_raw_cells(self):
        p=copy.deepcopy(self.data['products'][-1]);cell=lambda text,span=1:{'text':text,'colspan':span,'rowspan':1,'header':False}
        p['tables'].append({'index':7,'section':'Configuration','rows':[[cell('GPU Memory'),cell('AMBIGUOUS')],
                          [cell('Memory'),cell('MERGED_VALUE',2)]]})
        values=browse.parameters(p)
        self.assertNotIn('GPU Memory',[v['label'] for v in values])
        self.assertNotIn('Memory',[v['label'] for v in values])
        self.data['products'][-1]=p;self.data['generated_at']='2026-10-07T02:00:00+00:00'
        catalog.receive(self.root,self.data,'supermicro')
        detail=catalog.product_snapshot(self.root,p['id'],'supermicro')['product']
        self.assertEqual(detail['tables'],p['tables'])
        self.assertEqual(detail['browse_path'][-1]['id'],'servers/rack-scale')

    def test_explicit_board_and_adapter_fields_match_list_detail_and_export(self):
        cell=lambda text:{'text':text,'colspan':1,'rowspan':1,'header':False}
        board=self.data['products'][10]
        board['source_url']='https://www.supermicro.com/en/products/motherboard/h11dsi'
        board['source_sha256']=hashlib.sha256(board['source_url'].encode()).hexdigest()
        board['id']='supermicro-'+board['source_sha256'][:20]
        self.data['sources'].append({'source_url':board['source_url'],'sha256':board['source_sha256']})
        board['tables']=[{'index':1,'section':'Specifications','rows':[
            [cell('CPU'),cell('Dual Socket AMD EPYC 64-Core processors')],
            [cell('Form Factor'),cell('E-ATX')]]}]
        adapter=self.data['products'][11]
        adapter['tables']=[{'index':1,'section':'Specifications','rows':[
            [cell('Device Support'),cell('1 SATA Hard Disk Drive per Port')]]}]
        self.data['generated_at']='2026-10-07T03:00:00+00:00'
        catalog.receive(self.root,self.data,'supermicro')
        category='boards/amd-epyc/dual-socket/e-atx'
        listing=browse.query(self.root,category=category)
        self.assertEqual(listing['matched'],1)
        self.assertEqual(listing['items'][0]['id'],board['id'])
        detail=catalog.product_snapshot(self.root,board['id'],'supermicro')['product']
        self.assertEqual(detail['browse_path'],listing['items'][0]['browse_path'])
        export=catalog.csv_export(catalog.snapshot(self.root,'supermicro'),company='supermicro',category=category)
        self.assertIn(board['name'],export);self.assertNotIn('X11DPH',export)
        self.assertEqual(browse.query(self.root,category='components/addon/storage-adapters')['matched'],1)
        # A duplicated CPU field and contradictory socket text cannot justify a platform or route.
        ambiguous=copy.deepcopy(board)
        ambiguous['tables'][0]['rows'].append([cell('CPU'),cell('Single Socket Intel Xeon processors')])
        self.assertEqual(browse.category_path(ambiguous)[1]['id'],'boards/platform-pending')
        ambiguous['tables'][0]['rows']=[ [cell('CPU'),cell('Single Socket / Dual Socket AMD EPYC processors')] ]
        self.assertEqual(len(browse.category_path(ambiguous)),2)
        ambiguous['tables'][0]['rows']=[[cell('CPU'),cell('AMD EPYC')]]*40
        self.assertEqual(browse.hint_rows(ambiguous),[])
        rows=browse.hint_rows(board)
        self.assertEqual(browse.category_path({**board,'browse_hints':rows}),browse.category_path(board))

    def test_captured_blade_chassis_and_directory_paths_remain_distinct(self):
        expected={'superblade/module/sbi-test':'servers/superblade/module',
                  'microblade/module/mbi-test':'servers/microblade/module',
                  'superblade/powersupply/test':'components/superblade/powersupply',
                  'microblade/networking/test':'network/microblade/networking',
                  'accessories/networking/test':'network/network-accessories',
                  'chassis/mid-tower/test':'servers/chassis/tower',
                  'chassis/compact%20mini-tower/test':'servers/chassis/tower',
                  'chassis/mini-1u/test':'servers/chassis/mini-1u',
                  'gpu/liquid-cooled':'gpu-systems/gpu-platforms/liquid-cooled',
                  'motherboards/server-boards':'boards/directories/server-boards',
                  'compare':'unmapped/compare'}
        for path,category in expected.items():
            with self.subTest(path=path):
                p={'source_url':'https://www.supermicro.com/en/products/'+path}
                self.assertEqual(browse.category_path(p)[-1]['id'],category)
