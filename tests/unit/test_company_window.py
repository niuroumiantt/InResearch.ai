"""Company indexes, bounded quote cache and actor-scoped inews projection."""
import http.client
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from inresearch.paths import project_root
from inresearch.workflow import company_window, product_catalog, product_navigation
from tests.unit.test_product_catalog import bundle
from inresearch.adapters import company_quotes as quotes
from inresearch.interfaces import http as serve, auth
from inresearch.knowledge import registry

ROOT = project_root()


def company_catalog_fixture():
    """Published model/path identities with illustrative specification cells only."""
    import copy
    data = bundle()
    data.update(company_id='supermicro', generated_at='2026-10-07T00:00:00+00:00')
    template = data['products'][0]
    data['products'], data['sources'] = [], []
    paths = [('SYS-821GE-TNHR', 'gpu/8u/sys-821ge-tnhr'),
             ('SYS-442B-NR', 'mp/4u/sys-442b-nr'),
             ('SYS-222H-TN', 'hyper/2u/sys-222h-tn'),
             ('SYS-621C-TN12R', 'CloudDC/2U/SYS-621C-TN12R'),
             ('SYS-212GB-FNR', 'iot/2u/sys-212gb-fnr')]
    for n, (name, path) in enumerate(paths):
        p = copy.deepcopy(template)
        url = 'https://www.supermicro.com/en/products/system/' + path
        sha = str(n+1)*64
        p.update(id='supermicro-'+str(n+1)*20, name=name, category='服务器 / Server',
                 source_url=url, source_sha256=sha, taxonomy=[], official_pages=[],
                 tables=[{'index': 1, 'section': '界面验证原表', 'rows': [[
                     {'text': 'Fixture parameter', 'rowspan': 1, 'colspan': 1, 'header': False},
                     {'text': 'TEST_VALUE', 'rowspan': 1, 'colspan': 1, 'header': False}]]}])
        data['products'].append(p)
        data['sources'].append({'sha256': sha, 'source_url': url})
    return data

class CompanyWindowTests(unittest.TestCase):
    def test_existing_taxonomy_free_delivery_maps_to_database_backed_business_lines(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            data = company_catalog_fixture()
            product_catalog.receive(root, data, company='supermicro')
            path = product_catalog.database(root, 'supermicro')
            with patch.object(product_catalog, 'database', return_value=path):
                home = company_window.snapshot(ROOT, 'supermicro')
                index = product_catalog.index_snapshot(ROOT, 'supermicro')
                full = product_catalog.snapshot(ROOT, 'supermicro')
            self.assertEqual(home['catalog']['summary']['named_products'], 5)
            self.assertEqual(home['catalog']['summary']['named_with_tables'], 5)
            self.assertEqual(home['catalog']['summary']['without_vendor_taxonomy'], 5)
            self.assertEqual(home['catalog']['summary']['unmapped_entities'], 0)
            counts = {r['id']: r['entities'] for r in home['product_lines']}
            self.assertEqual(counts, {'gpu-systems': 1, 'servers': 3, 'edge': 1,
                                      'storage': 0, 'network': 0, 'software': 0})
            self.assertNotIn('TEST_VALUE', json.dumps(home))
            self.assertNotIn('"tables":', json.dumps(home['product_lines']))
            for line in home['product_lines']:
                ids = {p['id'] for p in index['products'] if p['company_line'] == line['id']}
                self.assertEqual(len(ids), line['entities'])
                self.assertTrue(all(p['id'] in ids for p in line['examples']))
                export = product_catalog.csv_export(full, company='supermicro', line=line['id'])
                self.assertEqual(sum(p['id'] in export for p in index['products']), line['entities'])
            with self.assertRaisesRegex(ValueError, 'unknown'):
                product_catalog.csv_export(full, company='supermicro', line='invented')

    def test_unmapped_series_and_old_runs_are_not_lost_or_counted_as_models(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            data = company_catalog_fixture()
            unknown = dict(data['products'][0], id='supermicro-'+'f'*20,
                           source_url='https://www.supermicro.com/en/products/unknown/gpu',
                           name='GPU software edge', kind='family_or_directory', tables=[])
            unknown['source_sha256'] = 'f'*64
            data['products'].append(unknown)
            data['sources'].append({'sha256': 'f'*64, 'source_url': unknown['source_url']})
            product_catalog.receive(root, data, company='supermicro')
            db = product_catalog.connect(root, 'supermicro')
            db.execute('INSERT INTO runs VALUES (?,?,?,?)', ('old', '2000-01-01', '', '{}'))
            db.execute('INSERT INTO products VALUES (?,?,?)', ('old-only', 'old', json.dumps(data['products'][0])))
            db.commit(); db.close()
            result = company_window.catalog_groups(root, 'supermicro')
            self.assertEqual(result['summary']['entities'], 6)
            self.assertEqual(result['summary']['named_products'], 5)
            self.assertEqual(result['summary']['unmapped_entities'], 1)
            self.assertEqual(product_navigation.company_line(unknown, 'supermicro'), '')
            unsafe = dict(unknown, product_url='https://supermicro.com.evil.test/en/products/system/gpu/foo')
            self.assertEqual(product_navigation.company_line(unsafe, 'supermicro'), '')

    def test_generic_company_uses_received_categories_instead_of_registered_search_labels(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            data = bundle()
            product_catalog.receive(Path(tmp), data)
            path = product_catalog.database(Path(tmp))
            with patch.object(product_catalog, 'database', return_value=path):
                home = company_window.snapshot(ROOT, 'nvidia')
            self.assertEqual(home['product_lines'][0]['filter']['group'], 'datacenter')
            self.assertEqual(home['product_lines'][0]['entities'], 1)
            self.assertEqual(home['catalog']['summary']['named_products'], 1)

    def test_public_index_has_sources_and_excludes_internal_annexes(self):
        result = company_window.snapshot(ROOT, 'supermicro')
        self.assertEqual(result['company']['ticker'], 'NASDAQ:SMCI')
        self.assertEqual(result['company']['founded_year'], 1993)
        self.assertEqual(len(result['product_lines']), 6)
        self.assertEqual({r['kind'] for r in result['financials']}, {'annual', 'quarterly'})
        self.assertTrue(all(r['url'].startswith('https://www.sec.gov/') for r in result['financials']))
        self.assertNotIn('research_notes', result['company'])
        self.assertNotIn('contracts', result)
        with self.assertRaises(KeyError): company_window.snapshot(ROOT, '../private')

    def test_navigation_reads_projected_sql_not_specification_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'catalog.sqlite3'
            db=sqlite3.connect(path)
            db.execute('CREATE TABLE runs(id TEXT, generated TEXT)')
            db.execute('CREATE TABLE products(run_id TEXT, payload TEXT)')
            db.execute('INSERT INTO runs VALUES (?,?)', ('run','2026-10-07'))
            record={'name':'GPU system','source_url':'https://www.supermicro.com/en/products/system/gpu/test',
                    'taxonomy':[{'slug':'servers','name':'Servers'}], 'listing':'active',
                    'tables':[{'private_test_marker':'not in homepage'}]}
            db.execute('INSERT INTO products VALUES (?,?)',('run',json.dumps(record)));db.commit();db.close()
            with patch.object(product_catalog,'database',return_value=path), patch.object(product_catalog,'snapshot',side_effect=AssertionError('heavy snapshot')):
                result=company_window.catalog_groups(ROOT,'supermicro')
            self.assertTrue(result['available'])
            self.assertEqual(result['groups'][0]['entities'],1)
            self.assertNotIn('private_test_marker',json.dumps(result))

    def test_quote_rejects_wrong_identity_missing_price_time_and_nonfinite(self):
        info={'symbol':'SMCI','primaryData':{'lastSalePrice':'$123.45','lastTradeTimestamp':'Oct 7, 2026 10:01 AM ET','percentageChange':'-1.25%'}}
        q=quotes.normalize('SMCI',info,{'summaryData':{'MarketCap':{'value':'$12,000,000,000'}}})
        self.assertEqual(q['price'],123.45);self.assertEqual(q['market_cap'],12e9)
        self.assertEqual(q['as_of'],info['primaryData']['lastTradeTimestamp'])
        for changed in ({**info,'symbol':'NVDA'}, {**info,'primaryData':{'lastSalePrice':'$12'}},
                        {**info,'primaryData':{'lastSalePrice':'NaN','lastTradeTimestamp':'now'}}):
            with self.assertRaises(ValueError):quotes.normalize('SMCI',changed,None)
        with self.assertRaises(ValueError): quotes.normalize('SMCI',info,{'symbol':'NVDA'})
        self.assertIsNone(quotes.number('∞'));self.assertIsNone(quotes.number('1e999'))

    def test_stale_cache_survives_provider_failure_and_pool_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cache.json';cached={'symbol':'SMCI','price':12,'as_of':'Oct 1, 2026', 'retrieved_epoch':time.time()-1000,'private':'must not project'}
            path.write_text(json.dumps(cached));company={'company_id':'supermicro','ticker':'NASDAQ:SMCI'}
            with patch.object(quotes,'workspace_path',return_value=path), patch.dict(os.environ,{'INRESEARCH_MARKET_ENABLED':'0'}):
                q=quotes.snapshot(ROOT,company)
                self.assertEqual(q['status'],'stale');self.assertNotIn('private',q)
            with patch.object(quotes,'read_provider',side_effect=OSError('provider down')):
                quotes.refresh(path,str(path),'SMCI')
            self.assertEqual(json.loads(path.read_text()),cached)
            with patch.object(quotes,'workspace_path',return_value=path),patch.object(quotes,'PENDING',set(map(str,range(8)))),patch.object(quotes.POOL,'submit') as submit,patch.dict(os.environ,{'INRESEARCH_MARKET_ENABLED':'1'}):
                quotes.snapshot(ROOT,company);submit.assert_not_called()
            path.write_text('[]')
            with patch.object(quotes,'workspace_path',return_value=path),patch.dict(os.environ,{'INRESEARCH_MARKET_ENABLED':'0'}):
                self.assertEqual(quotes.snapshot(ROOT,company)['status'],'unavailable')
        self.assertEqual(quotes.snapshot(ROOT,{'company_id':'x','ticker':None})['status'],'unregistered')

    def test_company_news_filters_before_limit_without_pipeline_or_marks(self):
        items=[{'title':'Other company','object_ids':['actor:nvidia'],'published_at':1000-i} for i in range(85)]
        items.extend([{'title':'SMCI original title','object_ids':['actor:supermicro'],'published_at':1,'url':'https://example.test/smci'},
                      {'title':'Supermicro in title only','object_ids':['actor:nvidia'],'published_at':2000}])
        runtime={'reader':{'status':'success','stale':True,'acquisition':{'news_feed':{'status':'success','items':items}}}}
        with patch.object(registry,'_snapshot_inputs',return_value=(None,None,{},runtime)):
            result=registry.build_news(ROOT,company_id='supermicro',limit=6)
        self.assertEqual(len(result['feed']['items']),1)
        self.assertEqual(result['feed']['items'][0]['title'],'SMCI original title')
        self.assertNotIn('pipeline',result)

    def test_anonymous_endpoints_validate_filters_and_keep_deep_links(self):
        with patch.object(serve,'AUTH_ON',True),patch.object(auth,'session_user',return_value=None),patch.dict(os.environ,{'INRESEARCH_MARKET_ENABLED':'0'}):
            server=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler)
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
            try:
                for url,code in [('/api/company-window?c=supermicro',200),('/api/company-quote?c=supermicro',200),
                                  ('/api/company-window?c=missing',404),('/api/company-quote?c=supermicro&url=https://evil.test',400),
                                  ('/api/news?company=missing',404),('/api/news?company=supermicro&limit=21',400),
                                  ('/api/news?company=supermicro&company=nvidia',400)]:
                    connection=http.client.HTTPConnection('127.0.0.1',server.server_port);connection.request('GET',url);response=connection.getresponse();response.read();self.assertEqual(response.status,code,url);connection.close()
                for query,marker in [('?c=supermicro',b'id="company-products"'),('?c=supermicro&view=products',b'id="products"'),('?c=supermicro&product_id=abc',b'id="products"')]:
                    connection=http.client.HTTPConnection('127.0.0.1',server.server_port);connection.request('GET','/product-catalog.html'+query);response=connection.getresponse();body=response.read();self.assertIn(marker,body);connection.close()
            finally:server.shutdown();server.server_close();thread.join()
