"""Real catalog shapes retain official data while unknown nested fields stay internal."""
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from inresearch.interfaces import customer_catalog as customer
from inresearch.workflow import product_catalog as catalog, catalog_browse, catalog_materials, company_window
from tests.unit.test_product_catalog import bundle
from tests.unit.test_catalog_supplement import historical_fixture
from inresearch.paths import project_root

SECRET = 'PRIVATE-CATALOG-SENTINEL'


def poisoned(value):
    if isinstance(value, dict):
        return {**{key: poisoned(item) for key, item in value.items()},
                'future_private': {'path': SECRET, 'reviewer': SECRET}}
    if isinstance(value, list):
        return [poisoned(item) for item in value]
    return value


def series_bundle():
    data = bundle()
    template = data['products'][0]
    parent = copy.deepcopy(template)
    parent.update(id='nvidia-'+'1'*20, name='SYNTHETIC platform', kind='family_or_directory', tables=[])
    products = [parent]
    for i, capacity in enumerate(('141 GB', '282 GB'), 2):
        part = copy.deepcopy(template)
        part.update(id='nvidia-'+str(i)*20, name='FIXTURE-'+str(i), parent_id=parent['id'])
        cell = lambda text: {'text':text, 'rowspan':1, 'colspan':1, 'header':False}
        part['tables'] = [{'index':1, 'section':'Original parameter pairs', 'notes':'per GPU',
                           'rows':[[cell('Memory'),cell(capacity)], [cell('Technology'),cell('HBM3')]]},
                          copy.deepcopy(template['tables'][0])]
        products.append(part)
    data['products'] = products
    return data


class CustomerCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        environment = patch.dict('os.environ', {}, clear=True)
        environment.start(); self.addCleanup(environment.stop)
        (self.root/'framework').mkdir()
        (self.root/'framework/tco_targets.json').write_text(json.dumps({'targets':[
            {'id':'INTERNAL-TARGET-'+SECRET, 'team':'fetchspec', 'part_id':'gpu',
             'instances':['NVIDIA'], 'status':'needed'}]}))

    def safe(self, value, view):
        raw = poisoned(value)
        original = copy.deepcopy(raw)
        result = customer.project(raw, view)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn('future_private', json.dumps(result))
        self.assertEqual(raw, original, 'projection must not mutate stored/internal responses')
        return result

    def test_full_index_summary_and_product_use_real_received_shapes(self):
        data = bundle()
        p = data['products'][0]
        p['tables'][0]['rows'][1] = [{'text':'Memory', 'rowspan':2, 'colspan':1, 'header':True},
                                   {'text':'141 GB', 'rowspan':1, 'colspan':2, 'header':False}]
        p['tables'][0]['source_refs'] = [{'url':p['source_url'], 'sha256':p['source_sha256'],
                                         'label':'Official original', 'kind':'official_page'}]
        p['attachments'] = [{'url':p['source_url'], 'label':'Official attachment', 'sha256':p['source_sha256']}]
        p['official_resources'] = [{'url':p['source_url'], 'label':'Official resource', 'access_status':'not_checked'}]
        p['compute'] = {'category':'gpu','form':'module','architecture':'Hopper',
                        'evidence_quote':'Official module', 'architecture_quote':'Hopper architecture',
                        'source_refs':[{'url':p['source_url'],'sha256':p['source_sha256']}]}
        catalog.receive(self.root, data)
        full = catalog.snapshot(self.root)
        result = self.safe(full, 'full')
        product = result['products'][0]
        self.assertEqual(product['tables'], full['products'][0]['tables'])
        self.assertEqual(product['attachments'], full['products'][0]['attachments'])
        self.assertEqual(product['official_resources'], full['products'][0]['official_resources'])
        self.assertEqual(product['official_pages'], full['products'][0]['official_pages'])
        self.assertEqual(product['compute'], full['products'][0]['compute'])
        index = catalog.index_snapshot(self.root)
        self.assertIn(SECRET, json.dumps(index['research_alignment']))
        projected_index = self.safe(index, 'index')
        self.assertNotIn('research_alignment', projected_index)
        self.assertEqual(projected_index['products'][0]['table_count'], 1)
        self.assertEqual(projected_index['registered_companies'], index['registered_companies'])
        summary = self.safe(catalog.summary_snapshot(self.root), 'summary')
        self.assertNotIn('products', summary)
        self.assertEqual(summary['summary']['specification_coverage'], index['summary']['specification_coverage'])
        detail = self.safe(catalog.product_snapshot(self.root,p['id']), 'product')
        self.assertEqual(detail['product']['tables'], product['tables'])
        # Copies remain independent in both directions.
        result['products'][0]['tables'][0]['rows'][0][0]['text']='changed client copy'
        self.assertNotEqual(full['products'][0]['tables'][0]['rows'][0][0]['text'],'changed client copy')

    def test_series_keeps_common_values_shared_original_cells_and_status_counts(self):
        data = series_bundle(); catalog.receive(self.root,data)
        original = catalog.series_snapshot(self.root,data['products'][0]['id'])
        result = self.safe(original,'series')['series']
        self.assertEqual(result, original['series'])
        leaked = poisoned(original)
        leaked['series']['parts'][0]['values']['internal_target'] = SECRET
        leaked['series']['counts']['by_official_status']['internal_task'] = 999
        view = customer.project(leaked,'series')['series']
        self.assertNotIn(SECRET,json.dumps(view))
        self.assertNotIn('internal_task',view['counts']['by_official_status'])
        self.assertEqual(view['shared_tables'][0]['rows'], original['series']['shared_tables'][0]['rows'])
        self.assertEqual(view['parts'][0]['values']['Memory'],'141 GB')
        self.assertEqual(view['common'],[{'label':'Technology','value':'HBM3'}])

    def test_browse_and_materials_keep_actual_categories_and_product_links(self):
        base, data = historical_fixture()
        catalog.receive(self.root,base,'supermicro');catalog.receive(self.root,data,'supermicro')
        browse = catalog_browse.query(self.root,'supermicro')
        self.assertEqual(self.safe(browse,'browse'),browse)
        detail = catalog.product_snapshot(self.root,data['products'][1]['id'],'supermicro')
        projected = self.safe(detail,'product')
        self.assertEqual(projected['product']['browse_path'],detail['product']['browse_path'])
        self.assertEqual(projected['product']['parameters'],detail['product']['parameters'])
        materials = catalog_materials.query(self.root,'supermicro')
        self.assertEqual(self.safe(materials,'materials'),materials)
        linked = next(item for item in materials['items'] if item['links'])
        self.assertTrue(linked['links'][0]['product_name'])
        self.assertIn('source_sha256',linked['links'][0])

    def test_compute_chip_links_and_vendor_taxonomy_are_closed_at_each_level(self):
        product = {'id':'test','taxonomy':[{'slug':'gpu','name':'GPU','url':'https://vendor.test/gpu'}],
                   'compute':{'category':'gpu','form':'module','architecture':'A',
                              'evidence_quote':'Official module', 'architecture_quote':'Official A',
                              'source_refs':[{'url':'https://vendor.test/gpu','sha256':'a'*64}],
                              'chip_links':[{'product_id':'chip','evidence_quote':'Official chip identity',
                                             'source_refs':[{'url':'https://vendor.test/chip','sha256':'b'*64}]}]}}
        result = self.safe({'available':True,'product':product},'product')['product']
        self.assertEqual(result,product)
        raw = {'available':True,'product':{'id':'test','source_url':{'private':SECRET},
                 'tables':[{'rows':[[{'text':{'private':SECRET},'rowspan':1,'colspan':1,'header':False}]]}]}}
        self.assertNotIn(SECRET,json.dumps(customer.project(raw,'product')))

    def test_csv_all_modes_match_original_public_semantics_and_strip_nested_private_cells(self):
        data = bundle();catalog.receive(self.root,data)
        original = catalog.snapshot(self.root)
        dirty = poisoned(original)
        for mode in ('products','map','specs'):
            with self.subTest(mode=mode):
                text = customer.csv_export(dirty,mode,query='H200',company='nvidia')
                self.assertEqual(text,catalog.csv_export(original,mode,query='H200',company='nvidia'))
                self.assertNotIn(SECRET,text)
                self.assertNotIn('future_private',text)
                rows=list(csv.reader(io.StringIO(text.lstrip('\ufeff'))))
                self.assertGreater(len(rows),1)
                self.assertEqual(rows[1][1],"'=H200")
        base,data=historical_fixture();catalog.receive(self.root,base,'supermicro');catalog.receive(self.root,data,'supermicro')
        original=catalog.snapshot(self.root,'supermicro')
        for mode in ('products','map','specs'):
            self.assertEqual(customer.csv_export(poisoned(original),mode,company='supermicro',line='servers'),
                             catalog.csv_export(original,mode,company='supermicro',line='servers'))

    def test_company_window_preserves_real_facts_financial_citations_and_catalog_aggregation(self):
        base, data = historical_fixture()
        catalog.receive(self.root, base, 'supermicro'); catalog.receive(self.root, data, 'supermicro')
        path = catalog.database(self.root, 'supermicro')
        with patch.object(catalog, 'database', return_value=path):
            native = company_window.snapshot(project_root(), 'supermicro')
        original = poisoned(native)
        untouched = copy.deepcopy(original)
        result = customer.project_company_window(original)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn('future_private', json.dumps(result))
        self.assertEqual(original, untouched)
        expected = copy.deepcopy(native)
        expected['catalog'].pop('run_id')
        self.assertEqual(result, expected)
        self.assertEqual(result['company']['founded_year'], 1993)
        self.assertEqual(result['catalog']['summary']['named_products'], 6)
        self.assertEqual(result['catalog']['material_count'], 2)
        self.assertEqual(len(result['financials']), 9)
        self.assertTrue(all(row['url'].startswith('https://www.sec.gov/') for row in result['financials']))
        self.assertEqual(result['product_lines'][0]['source_url'], native['product_lines'][0]['source_url'])
        original['product_lines'][0]['filter']['internal_target'] = SECRET
        original['catalog']['business_lines'][0]['examples'][0]['private_path'] = SECRET
        original['company']['employees'] = {'internal': SECRET}
        original['financials'][0]['url'] = 'https://user:password@private.test/report'
        result = customer.project_company_window(original)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn('employees', result['company'])
        self.assertNotIn('url', result['financials'][0])
        self.assertNotIn('internal_target', result['product_lines'][0]['filter'])
        with self.assertRaises(ValueError): customer.project_company_window([SECRET])
        self.assertEqual(customer.project_company_window({'company': {}, 'catalog': {'available': False,
                         'registered': False, 'groups': []}, 'financials': [], 'checked_at': None}),
                         {'company': {}, 'catalog': {'available': False, 'registered': False, 'groups': []},
                          'financials': [], 'checked_at': None})

    def test_company_quote_keeps_real_normalized_values_and_rejects_nested_cache_fields(self):
        from inresearch.adapters import company_quotes
        value = company_quotes.normalize('SMCI', {'symbol': 'SMCI', 'marketStatus': 'Closed',
            'primaryData': {'lastSalePrice': '$123.45', 'lastTradeTimestamp': 'Oct 13, 2026',
                            'netChange': '-1.25', 'percentageChange': '-1.0%'}},
            {'symbol': 'SMCI', 'summaryData': {'MarketCap': {'value': '$20,000,000,000'}}})
        value.update(ticker='NASDAQ:SMCI', status='cached', refreshing=False)
        self.assertEqual(customer.project_company_quote(poisoned(value)), value)
        for key in value:
            with self.subTest(key=key):
                malformed = poisoned(value); malformed[key] = {'unknown': SECRET}
                result = customer.project_company_quote(malformed)
                self.assertNotIn(SECRET, json.dumps(result))
                self.assertNotIn(key, result)
        value.update(market_cap=None, change_percent=None)
        self.assertIsNone(customer.project_company_quote(value)['market_cap'])
        self.assertEqual(customer.project_company_quote({'status':'unavailable', 'price':float('nan'),
                         'source_url':'https://credentials:secret@host.test/', 'refreshing':False}),
                         {'status':'unavailable', 'refreshing':False})
        with self.assertRaises(ValueError): customer.project_company_quote([SECRET])

    def test_unavailable_nulls_and_unknown_views_do_not_fall_back_to_raw_payloads(self):
        for view, key in [('product','product'),('series','series')]:
            self.assertEqual(customer.project({'available':False,'company_id':'nvidia',key:None,'private':SECRET},view),
                             {'available':False,'company_id':'nvidia',key:None})
        with self.assertRaises(ValueError):customer.project({'private':SECRET},'future')
        with self.assertRaises(ValueError):customer.project([SECRET])
        projected=customer.project({'available':False,'products':[], 'coverage':{'complete':False,'private_path':SECRET}},'full')
        self.assertEqual(projected['coverage'],{'complete':False})


if __name__ == '__main__':
    unittest.main()
