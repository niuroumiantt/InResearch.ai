import copy
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from http.client import HTTPConnection
import unittest
from unittest.mock import patch

from inresearch.workflow import product_catalog as catalog
from inresearch.workflow import product_navigation as navigation


def bundle():
    url = 'https://www.nvidia.com/en-us/data-center/h200/'
    sha = 'a' * 64
    cell = lambda s: {'text': s, 'colspan': 1, 'rowspan': 1, 'header': False}
    return {'schema_version': 1, 'company_id': 'nvidia', 'generated_at': '2026-09-27T12:00:00+00:00',
        'coverage': {'complete': False}, 'sources': [{'sha256': sha, 'source_url': url}],
        'products': [{'id': 'nvidia-'+'a'*20, 'name': '=H200', 'category': 'Data Center',
          'kind': 'named_product', 'availability': 'not_verified', 'source_url': url,
          'source_sha256': sha, 'observed_at': '2026-09-27', 'extraction_status': 'native_tables_extracted',
          'attachments': [], 'tables': [{'index': 1, 'section': 'Specifications', 'notes': 'per GPU',
            'rows': [[cell(''), cell('SXM'), cell('NVL')], [cell('Memory'), cell('141 GB'), cell('141 GB')]]}]}]}


class ProductCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict('os.environ', {}, clear=True)
        env.start(); self.addCleanup(env.stop)

    def test_import_replay_versions_and_stale_write(self):
        data = bundle()
        catalog.receive(self.root, data)
        self.assertTrue(catalog.receive(self.root, data)['replayed'])
        old = copy.deepcopy(data)
        data['generated_at'] = '2026-09-28T12:00:00+00:00'
        data['products'][0]['source_sha256'] = data['sources'][0]['sha256'] = 'b'*64
        catalog.receive(self.root, data)
        with self.assertRaisesRegex(ValueError, 'older'):
            catalog.receive(self.root, old)
        with sqlite3.connect(catalog.database(self.root)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM versions').fetchone()[0], 2)
        self.assertEqual(catalog.snapshot(self.root)['products'][0]['source_sha256'], 'b'*64)

    def test_missing_evidence_and_unsafe_attachment_rejected_without_writes(self):
        for mutation in ('source', 'attachment', 'span'):
            data = bundle()
            if mutation == 'source': data['sources'] = []
            if mutation == 'attachment': data['products'][0]['attachments'] = [{'url': 'javascript:alert(1)'}]
            if mutation == 'span': data['products'][0]['tables'][0]['rows'][0][0]['colspan'] = 0
            with self.assertRaises(ValueError): catalog.receive(self.root, data)
        self.assertFalse(catalog.database(self.root).exists())

    def test_child_product_keeps_parent_resource_links_and_csv_alignment(self):
        data = bundle()
        parent = data['products'][0]
        child = copy.deepcopy(parent)
        child.update(id='nvidia-'+'b'*20, name='NVIDIA BlueField-4 DPU', parent_id=parent['id'], product_url=parent['source_url'],
                     official_resources=[{'url':'https://resources.nvidia.com/en-us/bluefield-4-datasheet','label':'BlueField-4 Datasheet','access_status':'not_checked'}],
                     map_change_status='new')
        data['products'].append(child)
        data['product_map'] = {'entries': 2, 'changes': {'new': 1}}
        catalog.receive(self.root, data)
        snapshot = catalog.snapshot(self.root)
        received = next(p for p in snapshot['products'] if p['id'] == child['id'])
        self.assertEqual(received['parent_id'], parent['id'])
        self.assertEqual(received['official_resources'][0]['url'], child['official_resources'][0]['url'])
        self.assertEqual(snapshot['coverage']['product_map']['entries'], 2)
        rows = list(csv.DictReader(io.StringIO(catalog.csv_export(snapshot, scope='all').lstrip('\ufeff'))))
        self.assertEqual(next(r for r in rows if r['product_id'] == child['id'])['parent_id'], parent['id'])

    def test_csv_preserves_variants_notes_and_prevents_formula_execution(self):
        catalog.receive(self.root, bundle())
        data = catalog.snapshot(self.root)
        products = list(csv.reader(io.StringIO(catalog.csv_export(data))))
        self.assertEqual(products[1][1], "'=H200")
        specs = list(csv.DictReader(io.StringIO(catalog.csv_export(data, 'specs').lstrip('\ufeff'))))
        self.assertEqual(json.loads(specs[0]['official_cells_json'])[1]['text'], 'SXM')
        self.assertEqual(specs[1]['official_notes'], 'per GPU')
        self.assertEqual(len(list(csv.reader(io.StringIO(catalog.csv_export(data, query='not found'))))), 1)

    def test_navigation_uses_product_identity_not_polluted_parent_categories(self):
        product = bundle()['products'][0]
        product['category'] = 'Gaming and Creating / Data Center / Software / Networking'
        original = copy.deepcopy(product)
        self.assertEqual(navigation.classify(product)['group'], 'datacenter')
        self.assertEqual(product, original)
        for name, path, group in [
            ('GeForce RTX 5090', '/geforce/graphics-cards/50-series/rtx-5090/', 'consumer'),
            ('NVIDIA DGX Spark', '/products/workstations/dgx-spark/', 'professional'),
            ('NVIDIA IGX Thor', '/edge-computing/products/igx/', 'embedded'),
            ('NVIDIA DOCA', '/networking/products/software/doca/', 'software'),
            ('NVIDIA RTX PRO Server', '/data-center/products/rtx-pro-server/', 'datacenter'),
        ]:
            product.update(name=name, source_url='https://www.nvidia.com/en-us'+path)
            self.assertEqual(navigation.classify(product)['group'], group)
        self.assertEqual(len(navigation.GROUPS), 5)

    def test_auxiliary_unknown_and_components_keep_explicit_navigation_roles(self):
        p = bundle()['products'][0]
        p.update(name='NVIDIA Training', source_url='https://www.nvidia.com/en-us/learn/organizations/')
        self.assertEqual(navigation.classify(p)['role'], 'auxiliary')
        p.update(name='Unknown', source_url='https://www.nvidia.com/en-us/new-path/')
        self.assertEqual(navigation.classify(p)['role'], 'unclassified')
        p.update(name='NVIDIA GeForce RTX 5070', product_url='https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/')
        self.assertEqual(navigation.classify(p)['family'], 'geforce-50')

    def test_navigation_snapshot_and_csv_filters_share_the_same_projection(self):
        catalog.receive(self.root, bundle())
        data = catalog.snapshot(self.root)
        self.assertEqual(len(data['navigation']['groups']), 5)
        self.assertEqual(data['products'][0]['category'], 'Data Center')
        self.assertEqual(len(list(csv.reader(io.StringIO(catalog.csv_export(data, group='consumer'))))), 1)
        text = catalog.csv_export(data, group='datacenter', family='accelerators', scope='catalog')
        rows = list(csv.DictReader(io.StringIO(text.lstrip('\ufeff'))))
        self.assertEqual(rows[0]['display_family'], 'accelerators')
        self.assertEqual(len(list(csv.reader(io.StringIO(catalog.csv_export(data, scope='auxiliary'))))), 1)

    def test_http_authentication_and_receiver_validation(self):
        from inresearch.interfaces import http
        token_file = self.root / 'token'
        token_file.write_text('x' * 48)
        with patch.object(http, 'ROOT', self.root), patch.object(http, 'AUTH_ON', True), patch.object(http.auth, 'session_user', return_value=None), patch.object(http.pilot_progress, 'token_path', return_value=token_file):
            server = http.ThreadingHTTPServer(('127.0.0.1', 0), http.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def request(method, body=None, token=''):
                    client = HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    client.request(method, '/api/product-catalog/nvidia', json.dumps(body) if body else None,
                                   {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
                    response = client.getresponse(); status = response.status
                    data = json.loads(response.read()); client.close()
                    return status, data
                self.assertEqual(request('GET')[0], 401)
                self.assertEqual(request('POST', bundle(), 'bad')[0], 401)
                self.assertFalse(catalog.database(self.root).exists())
                self.assertEqual(request('POST', bundle(), 'x'*48)[0], 200)
                self.assertEqual(len(catalog.snapshot(self.root)['products']), 1)
            finally:
                server.shutdown(); thread.join(); server.server_close()


if __name__ == '__main__':
    unittest.main()
