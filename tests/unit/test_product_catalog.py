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

    def test_csv_preserves_variants_notes_and_prevents_formula_execution(self):
        catalog.receive(self.root, bundle())
        data = catalog.snapshot(self.root)
        products = list(csv.reader(io.StringIO(catalog.csv_export(data))))
        self.assertEqual(products[1][1], "'=H200")
        specs = list(csv.DictReader(io.StringIO(catalog.csv_export(data, 'specs').lstrip('\ufeff'))))
        self.assertEqual(json.loads(specs[0]['official_cells_json'])[1]['text'], 'SXM')
        self.assertEqual(specs[1]['official_notes'], 'per GPU')
        self.assertEqual(len(list(csv.reader(io.StringIO(catalog.csv_export(data, query='not found'))))), 1)

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
