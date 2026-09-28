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
        'coverage': {'complete': False, 'website_sitemap': {'candidate_urls': 7062, 'product_source_pages_matched': 1}},
        'sources': [{'sha256': sha, 'source_url': url}, {'sha256': 'b'*64, 'source_url': 'https://www.nvidia.cn/data-center/h200/'}],
        'products': [{'id': 'nvidia-'+'a'*20, 'name': '=H200', 'category': 'Data Center',
          'kind': 'named_product', 'availability': 'not_verified', 'source_url': url,
          'source_sha256': sha, 'observed_at': '2026-09-27', 'extraction_status': 'native_tables_extracted',
          'website_sitemap': {'matched': True, 'roles': ['en_us'], 'lastmod_claims': ['2026-09-26']},
          'official_pages': [{'url': url, 'sha256': sha}, {'url': 'https://www.nvidia.cn/data-center/h200/', 'sha256': 'b'*64}],
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
        data['products'][0]['official_pages'][0]['sha256'] = 'b'*64
        catalog.receive(self.root, data)
        with self.assertRaisesRegex(ValueError, 'older'):
            catalog.receive(self.root, old)
        with sqlite3.connect(catalog.database(self.root)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM versions').fetchone()[0], 2)
        self.assertEqual(catalog.snapshot(self.root)['products'][0]['source_sha256'], 'b'*64)

    def test_missing_evidence_and_unsafe_attachment_rejected_without_writes(self):
        for mutation in ('source', 'attachment', 'unlinked_cdn', 'span', 'localized_source'):
            data = bundle()
            if mutation == 'source': data['sources'] = []
            if mutation == 'attachment': data['products'][0]['attachments'] = [{'url': 'javascript:alert(1)'}]
            if mutation == 'unlinked_cdn': data['products'][0]['attachments'] = [{'url': 'https://dam-cdn.nvd.orangelogic.com/AssetLink/a.pdf'}]
            if mutation == 'span': data['products'][0]['tables'][0]['rows'][0][0]['colspan'] = 0
            if mutation == 'localized_source': data['products'][0]['official_pages'] = [{'url': 'javascript:alert(1)', 'sha256': 'b'*64}]
            with self.assertRaises(ValueError): catalog.receive(self.root, data)
        self.assertFalse(catalog.database(self.root).exists())

    def test_nvidia_resource_viewer_proves_exact_dam_attachment_host(self):
        data = bundle()
        product = data['products'][0]
        resource_url = 'https://resources.nvidia.com/en-us-accelerated-networking-resource-library/bluefield-4-dpu-datasheet'
        product['attachments'] = [{'url': 'https://dam-cdn.nvd.orangelogic.com/AssetLink/bluefield.pdf',
                                   'source_url': resource_url, 'source_sha256': 'c'*64}]
        product['official_pages'].append({'url': resource_url, 'sha256': 'c'*64})
        data['sources'].append({'sha256': 'c'*64, 'source_url': resource_url})
        catalog.receive(self.root, data)
        self.assertEqual(catalog.snapshot(self.root)['products'][0]['attachments'], product['attachments'])

    def test_pdf_table_evidence_requires_and_preserves_exact_attachment_receipt(self):
        data = bundle()
        product = data['products'][0]
        pdf_url = 'https://dam-cdn.nvd.orangelogic.com/AssetLink/h200.pdf'
        resource_url = 'https://resources.nvidia.com/en-us-accelerated-networking-resource-library/h200-datasheet'
        pdf_sha, page_sha = 'c'*64, 'd'*64
        data['sources'].extend([
            {'sha256': page_sha, 'source_url': resource_url},
            {'sha256': pdf_sha, 'source_url': pdf_url, 'snapshot_path': f'blobs/{pdf_sha}.pdf', 'kind': 'official_pdf_attachment'}])
        product['attachments'] = [{'url': pdf_url, 'label': 'H200 Datasheet', 'source_url': resource_url,
                                   'source_sha256': page_sha, 'sha256': pdf_sha,
                                   'snapshot_path': f'blobs/{pdf_sha}.pdf'}]
        product['official_pages'].append({'url': resource_url, 'sha256': page_sha})
        product['tables'][0]['source_refs'] = [{'url': pdf_url, 'sha256': pdf_sha, 'label': 'H200 Datasheet', 'kind': 'official_pdf'}]
        catalog.validate(data)
        with self.assertRaisesRegex(ValueError, 'table source reference'):
            broken = copy.deepcopy(data)
            broken['products'][0]['tables'][0]['source_refs'][0]['sha256'] = 'e'*64
            catalog.validate(broken)
        catalog.receive(self.root, data)
        specs = list(csv.DictReader(io.StringIO(catalog.csv_export(catalog.snapshot(self.root), 'specs').lstrip('\ufeff'))))
        self.assertEqual(specs[0]['table_evidence_urls'], pdf_url)
        self.assertEqual(specs[0]['table_evidence_sha256'], pdf_sha)

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
        self.assertEqual(snapshot['coverage']['website_sitemap']['candidate_urls'], 7062)
        product_rows = list(csv.DictReader(io.StringIO(catalog.csv_export(snapshot, mode='map').lstrip('\ufeff'))))
        self.assertEqual(product_rows[0]['official_sitemap_match'], 'True')
        self.assertEqual(product_rows[0]['official_sitemap_roles'], 'en_us')
        rows = list(csv.DictReader(io.StringIO(catalog.csv_export(snapshot, scope='all').lstrip('\ufeff'))))
        self.assertEqual(next(r for r in rows if r['product_id'] == child['id'])['parent_id'], parent['id'])

    def test_product_sitemap_metadata_and_map_csv_are_preserved(self):
        data = bundle()
        catalog.receive(self.root, data)
        snapshot = catalog.snapshot(self.root)
        self.assertEqual(snapshot['coverage']['website_sitemap']['product_source_pages_matched'], 1)
        self.assertEqual(len(snapshot['products'][0]['official_pages']), 2)
        mapped = list(csv.DictReader(io.StringIO(catalog.csv_export(snapshot, mode='map').lstrip('\ufeff'))))
        self.assertEqual(mapped[0]['official_sitemap_roles'], 'en_us')
        self.assertEqual(mapped[0]['official_sitemap_match'], 'True')

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
            ('NVIDIA ConnectX-5 MCX545A-ECAN', 'https://networking-docs.nvidia.com/connectx5en/specifications', 'datacenter'),
            ('NVIDIA BlueField-3 DPU', 'https://networking-docs.nvidia.com/bluefield3/specifications', 'datacenter'),
            ('NVIDIA Spectrum-4 SN5600', 'https://networking-docs.nvidia.com/spectrum4/specifications', 'datacenter'),
            ('NVIDIA RTX PRO Server', '/data-center/products/rtx-pro-server/', 'datacenter'),
        ]:
            product.update(name=name, source_url='https://www.nvidia.com/en-us'+path)
            self.assertEqual(navigation.classify(product)['group'], group)
        product.update(name='Specifications', source_url='https://www.nvidia.com/en-us/geforce/graphics-cards/gtx-780/specifications/')
        self.assertEqual(navigation.classify(product)['role'], 'auxiliary')
        product.update(name='NVIDIA ConnectX-5 MCX545A-ECAN', source_url='https://networking-docs.nvidia.com/connectx5en/specifications')
        self.assertEqual(navigation.classify(product)['family'], 'networking')
        self.assertEqual(navigation.classify(product)['role'], 'catalog')
        product.update(name='NVIDIA DOCA', source_url='https://networking-docs.nvidia.com/doca/latest/')
        self.assertEqual(navigation.classify(product)['group'], 'software')
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

    def test_index_is_lightweight_and_detail_is_loaded_by_stable_product_id(self):
        (self.root / 'framework').mkdir()
        (self.root / 'framework/tco_targets.json').write_text(json.dumps({'targets': [{
            'id': 'P.compute_accelerator.spec', 'team': 'fetchspec', 'part_id': 'compute_accelerator',
            'instances': ['NVIDIA H200']
        }]}))
        catalog.receive(self.root, bundle())
        index = catalog.index_snapshot(self.root)
        summary = index['products'][0]
        self.assertEqual(index['view'], 'index')
        self.assertEqual(summary['table_count'], 1)
        self.assertNotIn('tables', summary)
        self.assertNotIn('official_pages', summary)
        self.assertEqual(index['research_alignment']['acceptance'], 'target_demand_only_not_research_adoption')
        self.assertTrue(index['research_alignment']['target_ids'])
        detail = catalog.product_snapshot(self.root, summary['id'])
        self.assertEqual(detail['product']['tables'][0]['section'], 'Specifications')
        self.assertEqual(detail['acceptance'], 'source_extracted_not_research_adopted')
        self.assertIsNone(catalog.product_snapshot(self.root, 'nvidia-' + 'b' * 20)['product'])
        with self.assertRaisesRegex(ValueError, 'invalid product ID'):
            catalog.product_snapshot(self.root, '../data/users.json')

    def test_http_authentication_and_receiver_validation(self):
        from inresearch.interfaces import http
        token_file = self.root / 'token'
        token_file.write_text('x' * 48)
        with patch.object(http, 'ROOT', self.root), patch.object(http, 'AUTH_ON', True), patch.object(http.auth, 'session_user', return_value=None), patch.object(http.pilot_progress, 'token_path', return_value=token_file):
            server = http.ThreadingHTTPServer(('127.0.0.1', 0), http.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def request(method, body=None, token='', path='/api/product-catalog/nvidia'):
                    client = HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    client.request(method, path, json.dumps(body) if body else None,
                                   {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
                    response = client.getresponse(); status = response.status
                    data = json.loads(response.read()); client.close()
                    return status, data
                # 公开只读（2026-09-28）：规格库是爆炸图的入口，匿名 reader 可 GET；接收端与不公开的接口仍 401。
                self.assertEqual(request('GET')[0], 200)
                self.assertEqual(request('GET', path='/api/supply')[0], 401)
                self.assertEqual(request('POST', bundle(), 'bad')[0], 401)
                self.assertFalse(catalog.database(self.root).exists())
                self.assertEqual(request('POST', bundle(), 'x'*48)[0], 200)
                self.assertEqual(len(catalog.snapshot(self.root)['products']), 1)
                (self.root / 'framework').mkdir()
                (self.root / 'framework/tco_targets.json').write_text(json.dumps({'targets': []}))
                http.AUTH_ON = False
                status, index = request('GET', path='/api/product-catalog/nvidia?view=index')
                self.assertEqual(status, 200)
                self.assertNotIn('tables', index['products'][0])
                status, detail = request('GET', path='/api/product-catalog/nvidia?product_id=nvidia-' + 'a'*20)
                self.assertEqual(status, 200)
                self.assertEqual(detail['product']['tables'][0]['section'], 'Specifications')
                self.assertEqual(request('GET', path='/api/product-catalog/nvidia?product_id=bad')[0], 400)
            finally:
                server.shutdown(); thread.join(); server.server_close()


if __name__ == '__main__':
    unittest.main()
