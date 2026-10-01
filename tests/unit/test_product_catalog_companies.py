"""Product catalog per company: Micron through the same pipeline, isolated from NVIDIA."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from http.client import HTTPConnection
import unittest
from unittest.mock import patch

from inresearch.interfaces import public
from inresearch.workflow import product_catalog as catalog
from inresearch.workflow import product_navigation as navigation

MEMORY = {'slug': 'memory', 'name': 'Memory'}
DRAM_MODULES = {'slug': 'dram-modules', 'name': 'DRAM Modules'}
RDIMM = {'slug': 'rdimm', 'name': 'RDIMM'}
STORAGE = {'slug': 'storage', 'name': 'Storage'}
SSD = {'slug': 'data-center-ssd', 'name': 'Data Center SSDs'}


def cell(text):
    return {'text': text, 'colspan': 1, 'rowspan': 1, 'header': False}


def micron_bundle():
    pages = {
        'memory': 'https://www.micron.com/products/memory',
        'modules': 'https://www.micron.com/products/memory/dram-modules',
        'rdimm': 'https://www.micron.com/products/memory/dram-modules/rdimm/part-catalog/mtc20f2085s1rc48ba1',
        'ssd': 'https://www.micron.com/products/storage/ssd/data-center-ssd/9550-ssd',
        'old': 'https://www.micron.com/products/memory/dram-modules/rdimm/part-catalog/mta36asf4g72pz-2g6',
    }
    shas = {key: ch * 64 for key, ch in zip(pages, 'abcde')}
    def product(key, ident, name, kind, taxonomy, listing, status='', part='', tables=()):
        value = {'id': 'micron-' + ident * 20, 'name': name, 'category': ' / '.join(t['name'] for t in taxonomy),
                 'kind': kind, 'availability': 'not_verified', 'source_url': pages[key], 'source_sha256': shas[key],
                 'observed_at': '2026-10-01', 'extraction_status': 'native_tables_extracted' if tables else
                 'official_specification_not_published_on_observed_page',
                 'official_pages': [{'url': pages[key], 'sha256': shas[key]}], 'attachments': [],
                 'taxonomy': taxonomy, 'official_status': status, 'listing': listing,
                 'tables': [{'index': 1, 'section': 'Specifications', 'rows': list(tables)}] if tables else []}
        if part:
            value['part_number'] = part
        return value
    return {
        'schema_version': 1, 'company_id': 'micron', 'generated_at': '2026-10-01T08:00:00+00:00',
        'coverage': {'complete': False, 'part_catalog_pages': 2, 'limitations': ['Part catalog sampled']},
        'sources': [{'sha256': shas[k], 'source_url': u} for k, u in pages.items()],
        'products': [
            product('memory', '1', 'Memory', 'family_or_directory', [MEMORY], 'directory'),
            product('modules', '2', 'DRAM Modules', 'family_or_directory', [MEMORY, DRAM_MODULES], 'directory'),
            product('rdimm', '3', 'DDR5 RDIMM 64GB', 'named_product', [MEMORY, DRAM_MODULES, RDIMM], 'active',
                    'Production', 'MTC20F2085S1RC48BA1',
                    [[cell('Density'), cell('64GB')], [cell('Speed'), cell('4800 MT/s')]]),
            product('ssd', '4', 'Micron 9550 SSD', 'named_product', [STORAGE, SSD], 'active', 'Sampling', '',
                    [[cell('Capacity'), cell('30.72TB')]]),
            product('old', '5', 'DDR4 RDIMM 32GB', 'named_product', [MEMORY, DRAM_MODULES, RDIMM], 'obsolete',
                    'Obsolete (listed)', 'MTA36ASF4G72PZ-2G6'),
        ],
    }


def nvidia_bundle():
    url, sha = 'https://www.nvidia.com/en-us/data-center/h200/', 'f' * 64
    return {'schema_version': 1, 'company_id': 'nvidia', 'generated_at': '2026-09-27T12:00:00+00:00',
            'coverage': {'complete': False}, 'sources': [{'sha256': sha, 'source_url': url}],
            'products': [{'id': 'nvidia-' + 'a' * 20, 'name': 'H200', 'category': 'Data Center',
                          'kind': 'named_product', 'availability': 'not_verified', 'source_url': url,
                          'source_sha256': sha, 'observed_at': '2026-09-27', 'extraction_status': 'native_tables_extracted',
                          'attachments': [], 'tables': [{'index': 1, 'section': 'Specifications',
                                                         'rows': [[cell('Memory'), cell('141 GB')]]}]}]}


def targets(root):
    (root / 'framework').mkdir(exist_ok=True)
    (root / 'framework/tco_targets.json').write_text(json.dumps({'targets': [
        {'id': 'P.hbm.spec', 'team': 'fetchspec', 'part_id': 'hbm', 'status': 'delivered',
         'instances': ['SK hynix HBM3E', 'MICRON HBM3E']},
        {'id': 'P.dram.spec', 'team': 'fetchspec', 'part_id': 'dram', 'status': 'needed', 'instances': ['Micron DDR5']},
        {'id': 'N.micron.news', 'team': 'inews', 'part_id': 'dram', 'status': 'needed', 'instances': ['Micron']},
        {'id': 'P.gpu.spec', 'team': 'fetchspec', 'part_id': 'compute_accelerator', 'status': 'needed', 'instances': ['NVIDIA H200']},
    ]}))


class ProductCatalogCompanyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict('os.environ', {}, clear=True)
        env.start(); self.addCleanup(env.stop)

    def test_registry_hosts_and_database_are_per_company(self):
        self.assertEqual(set(catalog.COMPANIES) >= {'nvidia', 'micron'}, True)
        self.assertTrue(catalog.official('https://www.micron.com/products', 'micron'))
        self.assertTrue(catalog.official('https://micron.com/x', 'micron'))
        for url in ('https://www.nvidia.com/x', 'http://www.micron.com/x', 'https://micron.com.evil.example/x',
                    'https://www.micron.com:8443/x', 'https://evilmicron.com/x'):
            self.assertFalse(catalog.official(url, 'micron'), url)
        self.assertFalse(catalog.official('https://www.micron.com/x'))
        self.assertTrue(catalog.official('https://www.nvidia.cn/x'))
        self.assertTrue(catalog.database(self.root).name == 'nvidia.sqlite3')
        self.assertTrue(catalog.database(self.root, 'micron').name == 'micron.sqlite3')
        with self.assertRaisesRegex(ValueError, 'unknown'):
            catalog.database(self.root, '../nvidia')

    def test_micron_validate_receive_and_vendor_fields_pass_through(self):
        data = micron_bundle()
        catalog.validate(data)
        self.assertEqual(catalog.validate(copy.deepcopy(data), 'micron'), data)
        receipt = catalog.receive(self.root, data, 'micron')
        self.assertEqual(receipt['products'], 5)
        self.assertTrue(catalog.receive(self.root, data, 'micron')['replayed'])
        self.assertFalse(catalog.database(self.root).exists())
        snapshot = catalog.snapshot(self.root, 'micron')
        self.assertEqual(snapshot['company_id'], 'micron')
        self.assertEqual(snapshot['coverage']['part_catalog_pages'], 2)
        part = next(p for p in snapshot['products'] if p['id'] == 'micron-' + '3' * 20)
        source = data['products'][2]
        for key in ('taxonomy', 'official_status', 'listing', 'part_number'):
            self.assertEqual(part[key], source[key])
        # The DAM attachment exception is NVIDIA's only.
        broken = micron_bundle()
        broken['products'][2]['attachments'] = [{'url': 'https://dam-cdn.nvd.orangelogic.com/AssetLink/a.pdf',
                                                 'source_url': broken['products'][2]['source_url'],
                                                 'source_sha256': broken['products'][2]['source_sha256']}]
        with self.assertRaisesRegex(ValueError, 'attachment'):
            catalog.validate(broken)
        for mutate, message in (
                (lambda d: d['products'][2].update(listing='discontinued'), 'listing'),
                (lambda d: d['products'][2].update(taxonomy=[{'name': 'Memory'}]), 'taxonomy'),
                (lambda d: d['products'][2].update(official_status=3), 'official_status'),
                (lambda d: d['products'][2]['official_pages'].append({'url': 'https://www.nvidia.com/x', 'sha256': 'c' * 64}), 'localized'),
                (lambda d: d['coverage'].update(complete=True), 'incomplete')):
            broken = micron_bundle()
            mutate(broken)
            with self.assertRaisesRegex(ValueError, message):
                catalog.receive(self.root, broken, 'micron')

    def test_cross_company_isolation(self):
        with self.assertRaisesRegex(ValueError, 'NVIDIA catalog'):
            catalog.receive(self.root, micron_bundle())
        with self.assertRaisesRegex(ValueError, 'Micron catalog'):
            catalog.receive(self.root, nvidia_bundle(), 'micron')
        self.assertFalse(catalog.database(self.root).exists())
        self.assertFalse(catalog.database(self.root, 'micron').exists())
        relabelled = nvidia_bundle()
        relabelled['company_id'] = 'micron'
        with self.assertRaisesRegex(ValueError, 'product ID|source identity'):
            catalog.validate(relabelled)
        foreign_id = micron_bundle()
        foreign_id['products'][2]['id'] = 'nvidia-' + '9' * 20
        with self.assertRaisesRegex(ValueError, 'product ID'):
            catalog.validate(foreign_id)
        unknown = micron_bundle()
        unknown['company_id'] = 'acme'
        with self.assertRaisesRegex(ValueError, 'registered company'):
            catalog.validate(unknown)
        catalog.receive(self.root, nvidia_bundle())
        catalog.receive(self.root, micron_bundle(), 'micron')
        self.assertEqual([p['id'] for p in catalog.snapshot(self.root)['products']], ['nvidia-' + 'a' * 20])
        self.assertEqual(len(catalog.snapshot(self.root, 'micron')['products']), 5)
        with self.assertRaisesRegex(ValueError, 'invalid product ID'):
            catalog.product_snapshot(self.root, 'nvidia-' + 'a' * 20, 'micron')
        with self.assertRaisesRegex(ValueError, 'invalid product ID'):
            catalog.product_snapshot(self.root, 'micron-' + '3' * 20)
        with patch.object(catalog, 'build_opener') as opener:
            token = self.root / 'token'
            token.write_text('x' * 48); token.chmod(0o600)
            with self.assertRaisesRegex(ValueError, 'another company'):
                catalog.publish(micron_bundle(), token)
            opener.assert_not_called()

    def test_vendor_taxonomy_navigation(self):
        products = micron_bundle()['products']
        nav = navigation.classify_taxonomy(products[2], 'https://www.micron.com/products')
        self.assertEqual((nav['group'], nav['family'], nav['family_label'], nav['role']),
                         ('memory', 'dram-modules', 'DRAM Modules', 'catalog'))
        self.assertEqual((nav['basis'], nav['status']), ('vendor_product_path', 'vendor_taxonomy'))
        top = navigation.classify_taxonomy(products[0])
        self.assertEqual((top['group'], top['family'], top['family_label'], top['role']), ('memory', '', 'Memory', 'auxiliary'))
        self.assertEqual(navigation.classify_taxonomy({'name': 'x'})['role'], 'unclassified')
        self.assertTrue(navigation.matches(products[2], 'memory', 'dram-modules', 'catalog', navigation.classify_taxonomy))
        self.assertFalse(navigation.matches(products[0], 'memory', '', 'catalog', navigation.classify_taxonomy))
        self.assertTrue(navigation.matches(products[0], '', '', 'auxiliary', navigation.classify_taxonomy))
        self.assertEqual(navigation.taxonomy_groups(products),
                         [{'id': 'memory', 'label': 'Memory'}, {'id': 'storage', 'label': 'Storage'}])
        catalog.receive(self.root, micron_bundle(), 'micron')
        block = catalog.snapshot(self.root, 'micron')['navigation']
        self.assertEqual(block['groups'], [{'id': 'memory', 'label': 'Memory'}, {'id': 'storage', 'label': 'Storage'}])
        self.assertEqual(block['official_source'], 'https://www.micron.com/products')
        self.assertEqual(block['status'], 'vendor_taxonomy')

    def test_micron_index_summary_and_research_alignment(self):
        targets(self.root)
        catalog.receive(self.root, micron_bundle(), 'micron')
        index = catalog.index_snapshot(self.root, 'micron')
        self.assertEqual(index['view'], 'index')
        self.assertEqual(index['company']['label'], 'Micron')
        part = next(p for p in index['products'] if p['id'] == 'micron-' + '3' * 20)
        self.assertNotIn('tables', part)
        self.assertEqual(part['taxonomy'][2]['slug'], 'rdimm')
        self.assertEqual((part['official_status'], part['listing'], part['part_number']),
                         ('Production', 'active', 'MTC20F2085S1RC48BA1'))
        self.assertNotIn('part_number', next(p for p in index['products'] if p['id'] == 'micron-' + '4' * 20))
        summary = index['summary']
        self.assertEqual(summary['entities'], 5)
        self.assertEqual(summary['by_kind'], {'family_or_directory': 2, 'named_product': 3})
        self.assertEqual(summary['by_listing'], {'active': 2, 'directory': 2, 'obsolete': 1})
        self.assertEqual(summary['by_official_status'],
                         {'Obsolete (listed)': 1, 'Production': 1, 'Sampling': 1, 'unspecified': 2})
        # the obsolete part is listed, not collected: the current-parts denominator leaves it out
        self.assertEqual(summary['specification_coverage'], {'named_products': {'with_tables': 2, 'total': 3},
                                                             'current_named_products': {'with_tables': 2, 'total': 2},
                                                             'obsolete_listed': 1,
                                                             'all_entities': {'with_tables': 2, 'total': 5}})
        memory = next(g for g in summary['by_group'] if g['id'] == 'memory')
        self.assertEqual((memory['label'], memory['entities'], memory['with_tables']), ('Memory', 4, 1))
        modules = next(f for f in memory['families'] if f['id'] == 'dram-modules')
        self.assertEqual((modules['entities'], modules['with_tables']), (3, 1))
        alignment = index['research_alignment']
        self.assertEqual(alignment['target_ids'], ['P.hbm.spec', 'P.dram.spec'])
        self.assertEqual(alignment['part_ids'], ['dram', 'hbm'])
        self.assertEqual(alignment['targets'][0], {'id': 'P.hbm.spec', 'part_id': 'hbm', 'status': 'delivered'})
        self.assertEqual(alignment['acceptance'], 'target_demand_only_not_research_adoption')
        catalog.receive(self.root, nvidia_bundle())
        nvidia = catalog.index_snapshot(self.root)
        self.assertEqual(nvidia['research_alignment']['target_ids'], ['P.gpu.spec'])
        self.assertEqual(len(nvidia['navigation']['groups']), 5)
        self.assertEqual(nvidia['summary']['specification_coverage']['named_products'], {'with_tables': 1, 'total': 1})

    def test_micron_product_snapshot_and_csv(self):
        catalog.receive(self.root, micron_bundle(), 'micron')
        detail = catalog.product_snapshot(self.root, 'micron-' + '3' * 20, 'micron')
        self.assertEqual(detail['company_id'], 'micron')
        self.assertEqual(detail['product']['tables'][0]['rows'][1][1]['text'], '4800 MT/s')
        self.assertEqual(detail['product']['navigation']['family'], 'dram-modules')
        self.assertIsNone(catalog.product_snapshot(self.root, 'micron-' + 'f' * 20, 'micron')['product'])
        snapshot = catalog.snapshot(self.root, 'micron')
        rows = list(csv.DictReader(io.StringIO(catalog.csv_export(snapshot).lstrip('﻿'))))
        self.assertEqual(len(rows), 5)
        part = next(r for r in rows if r['product_id'] == 'micron-' + '3' * 20)
        self.assertEqual(part['official_taxonomy'], 'Memory > DRAM Modules > RDIMM')
        self.assertEqual(part['official_taxonomy_slugs'], 'memory > dram-modules > rdimm')
        self.assertEqual((part['official_status'], part['listing'], part['part_number']),
                         ('Production', 'active', 'MTC20F2085S1RC48BA1'))
        self.assertEqual((part['display_group'], part['display_family'], part['navigation_role']),
                         ('memory', 'dram-modules', 'catalog'))
        catalog_rows = list(csv.DictReader(io.StringIO(catalog.csv_export(snapshot, scope='catalog', group='memory').lstrip('﻿'))))
        self.assertEqual({r['product_id'][-1] for r in catalog_rows}, {'3', '5'})
        by_part = list(csv.DictReader(io.StringIO(catalog.csv_export(snapshot, query='mta36asf4g72pz').lstrip('﻿'))))
        self.assertEqual([r['name'] for r in by_part], ['DDR4 RDIMM 32GB'])
        specs = list(csv.DictReader(io.StringIO(catalog.csv_export(snapshot, 'specs', company='micron').lstrip('﻿'))))
        self.assertEqual([(s['official_parameter'], s['part_number']) for s in specs][:2],
                         [('Density', 'MTC20F2085S1RC48BA1'), ('Speed', 'MTC20F2085S1RC48BA1')])
        self.assertEqual(len(specs), 3)

    def test_http_routes_per_company_and_unknown_company(self):
        from inresearch.interfaces import http
        self.assertIn('/api/product-catalog/nvidia', public.READER_API)
        self.assertIn('/api/product-catalog/micron', public.READER_API)
        self.assertTrue(public.allowed('/api/product-catalog/micron'))
        self.assertFalse(public.allowed('/api/product-catalog/acme'))
        targets(self.root)
        token_file = self.root / 'token'
        token_file.write_text('x' * 48)
        with patch.object(http, 'ROOT', self.root), patch.object(http, 'AUTH_ON', True), \
                patch.object(http.auth, 'session_user', return_value=None), \
                patch.object(http.pilot_progress, 'token_path', return_value=token_file):
            server = http.ThreadingHTTPServer(('127.0.0.1', 0), http.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def request(method, path, body=None, token=''):
                    client = HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    client.request(method, path, json.dumps(body) if body else None,
                                   {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                    response = client.getresponse()
                    status, raw = response.status, response.read()
                    headers = dict(response.getheaders())
                    client.close()
                    return status, raw, headers
                self.assertEqual(request('GET', '/api/product-catalog/micron')[0], 200)
                self.assertEqual(request('GET', '/api/product-catalog/acme')[0], 401)
                self.assertEqual(request('POST', '/api/product-catalog/micron', micron_bundle(), 'bad')[0], 401)
                self.assertEqual(request('POST', '/api/product-catalog/acme', micron_bundle(), 'x' * 48)[0], 404)
                self.assertEqual(request('POST', '/api/product-catalog/nvidia', micron_bundle(), 'x' * 48)[0], 400)
                self.assertFalse(catalog.database(self.root).exists())
                status, raw, _ = request('POST', '/api/product-catalog/micron', micron_bundle(), 'x' * 48)
                self.assertEqual((status, json.loads(raw)['products']), (200, 5))
                self.assertFalse(catalog.database(self.root).exists())
                http.AUTH_ON = False
                status, raw, _ = request('GET', '/api/product-catalog/acme?view=index')
                self.assertEqual((status, json.loads(raw)['error']), (404, 'unknown catalog company'))
                status, raw, _ = request('GET', '/api/product-catalog/micron?view=summary')
                summary = json.loads(raw)
                self.assertEqual((status, summary['view'], 'products' in summary), (200, 'summary', False))
                self.assertEqual(summary['summary']['entities'], 5)
                self.assertTrue(summary['research_alignment']['targets'])
                status, raw, _ = request('GET', '/api/product-catalog/micron?view=index')
                index = json.loads(raw)
                self.assertEqual(status, 200)
                self.assertEqual(index['summary']['specification_coverage']['named_products'], {'with_tables': 2, 'total': 3})
                self.assertEqual(index['navigation']['groups'][0], {'id': 'memory', 'label': 'Memory'})
                self.assertEqual(index['research_alignment']['part_ids'], ['dram', 'hbm'])
                status, raw, _ = request('GET', '/api/product-catalog/micron?product_id=micron-' + '3' * 20)
                self.assertEqual((status, json.loads(raw)['product']['part_number']), (200, 'MTC20F2085S1RC48BA1'))
                self.assertEqual(request('GET', '/api/product-catalog/micron?product_id=nvidia-' + 'a' * 20)[0], 400)
                status, raw, headers = request('GET', '/api/product-catalog/micron?export=specs')
                self.assertEqual(status, 200)
                self.assertIn('micron-specs.csv', headers['Content-Disposition'])
                self.assertIn('MTC20F2085S1RC48BA1', raw.decode('utf-8'))
                status, raw, _ = request('GET', '/api/product-catalog/nvidia?view=index')
                self.assertEqual((status, json.loads(raw)['available']), (200, False))
            finally:
                http.AUTH_ON = True
                server.shutdown(); thread.join(); server.server_close()

    def test_cli_company_option_imports_and_exports_per_company(self):
        archive = self.root / 'archive'
        archive.mkdir()
        data = micron_bundle()
        # verify_snapshots checks archived bytes, so give each source a real blob and its SHA-256.
        rewritten = {}
        for n, source in enumerate(data['sources']):
            raw = f'micron page {n}'.encode()
            sha = hashlib.sha256(raw).hexdigest()
            (archive / f'{n}.html').write_bytes(raw)
            rewritten[source['sha256']] = sha
            source.update(sha256=sha, snapshot_path=f'{n}.html')
        for product in data['products']:
            product['source_sha256'] = rewritten[product['source_sha256']]
            for page in product['official_pages']:
                page['sha256'] = rewritten[page['sha256']]
        payload = self.root / 'micron.json'
        payload.write_text(json.dumps(data))
        out = io.StringIO()
        with patch.object(catalog, 'project_root', return_value=self.root), patch('sys.stdout', out):
            catalog.main(['import', '--company', 'micron', '--input', str(payload), '--archive-root', str(archive)])
            self.assertEqual(json.loads(out.getvalue())['products'], 5)
            with self.assertRaises(ValueError):
                catalog.main(['import', '--input', str(payload), '--archive-root', str(archive)])
            target = self.root / 'micron.csv'
            catalog.main(['export', '--company', 'micron', '--out', str(target)])
        self.assertIn('official_taxonomy', target.read_text(encoding='utf-8').splitlines()[0])
        self.assertFalse(catalog.database(self.root).exists())
        with sqlite3.connect(catalog.database(self.root, 'micron')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM products').fetchone()[0], 5)


if __name__ == '__main__':
    unittest.main()
