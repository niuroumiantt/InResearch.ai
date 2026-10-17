"""Customer sessions read declared products; operational and source privileges stay internal."""
import http.client
import hashlib
import json
from pathlib import Path
import threading
import tempfile
import socket
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from urllib.parse import quote

from inresearch.interfaces import auth, http as serve, public
from inresearch.knowledge import economics
from inresearch.delivery.report import build_snapshot_report
from tests.unit.test_customer_scene import SCENE_ASSETS

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED_2D = {
    'TA-12': ('server-plan', 'server-plan-v1'), 'TA-13': ('rack-atlas', 'rack-overview-v1'),
    'TA-14': ('rack-exploded', 'rack-exploded-v1'), 'TA-15': ('chip-atlas', 'chip-package-v1'),
    'TA-20': ('campus-plan', 'campus-plan-v1'), 'TA-21': ('facility-atlas', 'facility-domain-v1'),
    'TA-22': ('power-atlas', 'power-domain-v1'), 'TA-23': ('thermal-atlas', 'thermal-domain-v1'),
    'TA-24': ('compute-atlas', 'compute-domain-v1'), 'TA-25': ('memory-atlas', 'memory-domain-v1'),
    'TA-26': ('storage-atlas', 'storage-domain-v1'), 'TA-27': ('network-atlas', 'network-domain-v1'),
    'TA-28': ('control-atlas', 'control-domain-v1'), 'TA-35': ('cross-scale-atlas', 'cross-scale-v1')}
REPORT_PACKAGE = ('data-centers-2026', 'data-centers-2026-us', 'data-centers-2026-sea',
                  'data-centers-2026-cn', 'data-centers-2026-projects')
REPORT_DATA = ROOT / 'docs/research/2026-10-11/data-centers'
BOM_FALLBACK_IMAGES = ('coldplate', 'motherboard', 'fire', 'gpu-board', 'hbm-package', 'nic', 'psu',
                       'rack-frame', 'security', 'server', 'fan-wall', 'shell', 'ssd')


def bom_asset_paths():
    source = (ROOT / 'web/components/system-atlas.js').read_text()
    illustrations = json.JSONDecoder().raw_decode(source[source.index('{'):])[0]
    paths = {row[key] for row in illustrations.values() for key in ('image', 'preview', 'master', 'tile')}
    paths.update('/assets/technical-atlas/' + stem + '-v1' + suffix
                 for stem in BOM_FALLBACK_IMAGES for suffix in ('.svg', '-preview.svg', '.png'))
    paths.update(('/assets/bom-classification/overview-v1.png', '/assets/bom-classification/overview-v1.svg',
                  '/assets/bom-classification/overview-v1-preview.jpg',
                  '/assets/technical-atlas/system-overview-v2.svg', '/assets/technical-atlas/system-overview-v2.png',
                  '/assets/technical-atlas/scale-overview-v1.svg', '/assets/technical-atlas/scale-overview-v1.png'))
    return paths


class BOMProjectionTests(unittest.TestCase):
    def test_public_classification_and_physical_categories_match_the_registered_data(self):
        doc = json.loads((ROOT / 'framework/bom.json').read_text())
        result = public.customer_bom(doc)
        for key in ('version', 'updated', 'kinds', 'systems', 'scales', 'stages', 'aliases'):
            self.assertEqual(result[key], doc[key])
        self.assertEqual(len(result['parts']), 63)
        for a, b in zip(doc['parts'], result['parts']):
            for key in a.keys() - {'legacy_module', 'split_from'}:
                self.assertEqual(b[key], a[key], (a['id'], key))
        rights = json.loads((ROOT / 'framework/site_rights.json').read_text())
        for a, b in zip(rights['rights'], public.customer_site_rights(rights)['rights']):
            for key in a.keys() - {'legacy_module', 'from_bom_part'}:
                self.assertEqual(b[key], a[key], (a['id'], key))

    def test_only_required_indicator_values_dates_and_unverified_source_attribution_are_kept(self):
        doc = json.loads((ROOT / 'framework/indicators.json').read_text())
        view = public.customer_indicators(doc)
        self.assertEqual(len(view['indicators']), 17)
        original = {row['id']: row for row in doc['indicators']}
        for row in view['indicators']:
            for key, value in row.items():
                self.assertEqual(value, original[row['id']][key])
        self.assertIn('待核实', view['note'])
        self.assertIn('不自动取得', view['note'])

    def test_new_nested_private_fields_do_not_inherit_category_distribution(self):
        secret = '/srv/private-sentinel/production-receipt.json'
        def inject(node):
            if isinstance(node, dict):
                for value in list(node.values()): inject(value)
                node['new_internal_audit'] = secret
            elif isinstance(node, list):
                for value in node: inject(value)
        for path, builder in (('bom', public.customer_bom), ('site_rights', public.customer_site_rights),
                              ('indicators', public.customer_indicators)):
            doc = json.loads((ROOT / 'framework' / (path + '.json')).read_text())
            inject(doc)
            if path == 'bom':
                doc['parts'][0]['companies'].append({'execution_host': secret})
                doc['systems']['private_worker'] = {'name': secret}
                doc['aliases']['private_worker'] = secret
            if path == 'indicators':
                doc['indicators'].append({'id': 'internal_queue', 'name': secret, 'value': secret})
            self.assertNotIn('private-sentinel', json.dumps(builder(doc)), path)

    def test_bom_static_closure_is_published_and_svg_metadata_is_only_public_content(self):
        paths = bom_asset_paths()
        self.assertEqual(len(paths), 234)
        routes = json.loads((ROOT / 'web/routes.json').read_text())
        queue = json.loads((ROOT / 'framework/visual_atlas_migration.json').read_text())
        published = {row['id']: row['status'] for row in queue['items']}
        for ident in ('TA-01', 'TA-04', 'TA-05', 'TA-06', 'TA-07', 'TA-08', 'TA-09', 'TA-10',
                      'TA-11', 'TA-16', 'TA-17', 'TA-36', 'TA-37', 'TA-38', 'TA-39'):
            self.assertEqual(published[ident], 'published')
        for path in paths:
            file = ROOT / routes[path]
            self.assertTrue(file.is_file())
            if not path.endswith('.svg'): continue
            for element in ET.fromstring(file.read_text()).iter():
                self.assertNotIn(element.tag.rsplit('}', 1)[-1], ('script', 'foreignObject'))
                for key, value in [('text', element.text or ''), *element.attrib.items()]:
                    if value.startswith('data:'): continue
                    for secret in ('/Users/', '/srv/', '.local/', 'Bearer ', 'execution_host', 'stored_path'):
                        self.assertNotIn(secret, value, path)
                    if key.rsplit('}', 1)[-1] == 'href': self.assertTrue(value.startswith('#'), path)


class CustomerNewsProjectionTests(unittest.TestCase):
    def test_real_snapshot_clock_status_and_headline_identity_are_preserved_without_nested_metadata(self):
        feed = {'status': 'success', 'exported_at': '2026-10-13T00:00:00Z', 'pipeline': {'host': 'private-sentinel'},
                'items': [{'title_zh': '行业消息', 'published_at': 1, 'editorial_pick': True,
                           'url': 'https://example.org/news', 'object_ids': ['public-project', {'review': 'private-sentinel'}],
                           'reviewer': 'private-sentinel', 'domain': {'private_path': 'private-sentinel'}}]}
        result = public.customer_news({'feed': feed, 'raw_atlas': {'records': ['private-sentinel']}})
        self.assertEqual(result['feed']['status'], 'success')
        self.assertEqual(result['feed']['exported_at'], feed['exported_at'])
        self.assertEqual(result['feed']['items'][0]['object_ids'], ['public-project'])
        self.assertNotIn('private-sentinel', json.dumps(result))

    def test_missing_clock_or_unconnected_feed_does_not_become_a_success_receipt(self):
        view = public.customer_news({'feed': {'status': 'not_connected', 'items': []}})
        self.assertEqual(view['feed']['status'], 'not_connected')
        self.assertNotIn('exported_at', view['feed'])
        self.assertIsNone(public.customer_news({'reader': {'status': 'not_connected'}})['feed'])


class SnapshotReportProjectionTests(unittest.TestCase):
    def test_all_delivery_values_classification_and_model_statistics_are_preserved(self):
        original = build_snapshot_report(ROOT)
        projected = public.customer_report(original, ROOT)
        a = original['boundary']; b = projected['boundary']
        self.assertEqual(b['model_inputs'], a['model_inputs'])
        self.assertEqual(b['registries'], {k: a['registries'][k] for k in ('dashboard', 'bom', 'model')})
        self.assertNotIn('targets', b)
        self.assertNotIn('honesty', b)
        self.assertNotIn('topics', projected)
        self.assertNotIn('exports', projected)
        self.assertEqual(b['scenario'], a['scenario'])
        old = {row['id']: row for row in original['chapters']}
        new = {row['id']: row for row in projected['chapters']}
        self.assertEqual(new['q1']['account'], old['q1']['account'])
        self.assertEqual(new['q1']['columns'], old['q1']['columns'])
        for a, b in zip(old['q1']['calibration'], new['q1']['calibration']):
            for key in ('id', 'preset', 'label', 'anchors'):
                self.assertEqual(a[key], b[key])
        self.assertEqual(new['q2'], old['q2'])
        self.assertEqual(new['q3']['formulas'], old['q3']['formulas'])
        self.assertEqual(new['q3']['factors'],
                         [{k: v for k, v in row.items() if k != 'fetch'} for row in old['q3']['factors']])
        self.assertEqual(new['q4'], {key: old['q4'][key] for key in ('id', 'title')})

    def test_future_nested_fields_in_each_of_the_seven_audited_categories_never_escape(self):
        report = build_snapshot_report(ROOT)
        secret = '/srv/private-sentinel/worker-receipt.json'
        def inject(node):
            if isinstance(node, dict):
                for value in list(node.values()): inject(value)
                node['new_internal_audit'] = secret
            elif isinstance(node, list):
                for value in node: inject(value)
        inject(report)
        report['boundary']['registries']['private_path'] = secret
        report['chapters'][0]['account'][0]['evidence']['reviewer'] = secret
        report['chapters'][0]['columns']['1']['items'][0]['source_path'] = secret
        report['chapters'][0]['calibration'][0]['anchors']['execution_host'] = secret
        report['chapters'][1]['systems'][0]['private_path'] = secret
        report['chapters'][2]['formulas']['deploy_command'] = secret
        report['chapters'][3]['statuses']['reader_receipt'] = secret
        report['chapters'][0]['calibration'][0]['source'] = secret
        report['chapters'][0]['readings'].append({'id': 'private', 'href': '/doc.html?f='+secret,
                                                 'label': secret, 'hint': secret})
        report['chapters'].insert(0, {'id': 'internal_worker_dispatch', 'body': secret})
        result = public.customer_report(report, ROOT)
        self.assertNotIn('private-sentinel', json.dumps(result))
        self.assertEqual([row['id'] for row in result['chapters']], ['q1', 'q2', 'q3', 'q4'])

    def test_chapter_identity_is_independent_of_order_and_ambiguous_shapes_fail_closed(self):
        report = build_snapshot_report(ROOT)
        expected = public.customer_report(report, ROOT)
        report['chapters'].reverse()
        self.assertEqual(public.customer_report(report, ROOT), expected)
        with self.assertRaises(ValueError):
            public.customer_report({**report, 'chapters': report['chapters'][:-1]}, ROOT)
        with self.assertRaises(ValueError):
            public.customer_report({**report, 'chapters': report['chapters'] + [report['chapters'][0]]}, ROOT)
        with self.assertRaises(ValueError):
            public.customer_report({**report, 'kind': 'legacy_unverified'}, ROOT)

    def test_source_attribution_and_readings_do_not_export_internal_paths_or_unreadable_links(self):
        report = public.customer_report(build_snapshot_report(ROOT), ROOT)
        text = json.dumps(report)
        for marker in ('docs/research/', 'framework/', 'doc.html', 'supply.html',
                       'origin_pointer', 'target_id', '待建队', '到期日'):
            self.assertNotIn(marker, text)
        for reading in report['chapters'][0]['readings']:
            from urllib.parse import urlsplit
            url = urlsplit(reading['href'])
            self.assertTrue(public.customer_allowed(ROOT, '/' + url.path.lstrip('/'), url.query))
        self.assertEqual({row['source'] for row in report['chapters'][0]['calibration']},
                         {'摩根士丹利 2026-09《AI 指南》p22–27', '高盛 2026-09-24《Sizing the AI Economy》Exhibit 7',
                          '本站历史成本基准（2026-09-14）'})


class DashboardProjectionTests(unittest.TestCase):
    def test_node_classification_physical_values_model_statistics_and_coverage_are_preserved(self):
        original = json.loads((ROOT / 'data/dashboard.json').read_text())
        projected = public.customer_dashboard(original, ROOT)
        for key in ('version', 'updated', 'title', 'stages', 'columns', 'formulas', 'systems', 'factors'):
            self.assertEqual(projected[key], original[key], key)
        self.assertEqual(projected['root']['account']['rows'], original['root']['account']['rows'])
        self.assertEqual(projected['root']['account']['scenario'], original['root']['account']['scenario'])
        self.assertEqual(set(projected['parts']), set(original['parts']))
        self.assertEqual(set(projected['rights']), set(original['rights']))
        def compare_cells(a, b):
            self.assertEqual(set(a), set(b))
            for col in a:
                self.assertEqual(a[col]['status'], b[col]['status'])
                self.assertEqual(a[col]['coverage'], b[col]['coverage'])
                self.assertEqual(b[col]['items'], [{k: v for k, v in item.items() if k != 'source'}
                                                 for item in a[col]['items']])
                for key in ('instances', 'instance_ids'):
                    if key in a[col]: self.assertEqual(b[col][key], a[col][key])
        compare_cells(original['root']['cells'], projected['root']['cells'])
        compare_cells(original['site']['cells'], projected['site']['cells'])
        for category in ('parts', 'rights'):
            for ident, row in original[category].items():
                compare_cells(row['cells'], projected[category][ident]['cells'])
                for key in row.keys() - {'cells', 'legacy_module'}:
                    self.assertEqual(row[key], projected[category][ident][key], (category, ident, key))
        for category in ('system_nodes', 'parent_systems'):
            self.assertEqual(len(original[category]), len(projected[category]))
            for a, b in zip(original[category], projected[category]):
                compare_cells(a['cells'], b['cells'])
                for key in a.keys() - {'cells'}: self.assertEqual(a[key], b[key], (category, a['id'], key))

    def test_future_nested_fields_private_map_entries_and_work_records_do_not_escape(self):
        doc = json.loads((ROOT / 'data/dashboard.json').read_text())
        secret = '/srv/private-sentinel/reader-audit.json'
        def inject(node):
            if isinstance(node, dict):
                for value in list(node.values()): inject(value)
                node['new_internal_audit'] = secret
            elif isinstance(node, list):
                for value in node: inject(value)
        inject(doc)
        doc['parts']['internal-worker'] = {'id': 'internal-worker', 'name': secret}
        doc['rights']['private-license'] = {'name': secret}
        doc['system_nodes'].append({'id': 'private-service', 'name': secret})
        doc['root']['account']['links'].append(['private', '/doc.html?f='+secret])
        doc['root']['account']['readings'].append({'label': secret, 'href': '/research-workbench.html'})
        next(iter(doc['parts'].values()))['cells']['5']['instance_ids'].append(secret)
        result = public.customer_dashboard(doc, ROOT)
        self.assertNotIn('private-sentinel', json.dumps(result))
        for key in ('changes', 'note', 'generated_from'): self.assertNotIn(key, result)
        self.assertNotIn('targets', result['root'])
        self.assertNotIn('model', result['root']['account'])
        self.assertNotIn('legacy_module', next(iter(result['parts'].values())))


class PublishedReportProjectionTests(unittest.TestCase):
    def test_project_table_preserves_168_public_rows_and_nonformal_nonaggregate_boundary(self):
        doc = json.loads((REPORT_DATA / 'project-ledger.json').read_text())
        view = public.customer_project_ledger(doc)
        self.assertEqual(len(view['records']), 168)
        for key in ('schema', 'publication_date', 'scope', 'formal_database_ingested', 'aggregation_allowed'):
            self.assertEqual(view[key], doc[key])
        self.assertIs(view['formal_database_ingested'], False)
        self.assertIs(view['aggregation_allowed'], False)
        for original, projected in zip(doc['records'], view['records']):
            self.assertEqual(projected['roles'], original['roles'])
            self.assertEqual(projected['capacity'], {'quoted_text': original['capacity']['quoted_text']})
            for key in ('id', 'name', 'region', 'country_code', 'country_label', 'public_location',
                        'stage_and_date', 'boundary', 'evidence_date_text', 'sources'):
                self.assertEqual(projected[key], original[key])
            self.assertNotIn('provenance', projected)
            self.assertNotIn('original_research_excerpt', projected)

    def test_report_figures_preserve_existing_values_units_periods_and_boundaries(self):
        doc = json.loads((REPORT_DATA / 'chart-data.json').read_text())
        self.assertEqual(public.customer_chart_data(doc), doc)

    def test_future_internal_fields_at_each_nested_level_never_become_report_downloads(self):
        ledger = json.loads((REPORT_DATA / 'project-ledger.json').read_text())
        chart = json.loads((REPORT_DATA / 'chart-data.json').read_text())
        secret = '/srv/private-sentinel/reader-receipt.json'
        def inject(node):
            if isinstance(node, dict):
                for value in list(node.values()): inject(value)
                node['new_internal_audit'] = secret
            elif isinstance(node, list):
                for value in node: inject(value)
        inject(ledger)
        inject(chart)
        ledger['records'][0]['provenance']['original_document_sha256'] = secret
        ledger['records'][0]['original_research_excerpt'] = secret
        ledger['records'][0]['sources'].append({'execution_host': secret})
        ledger['records'][0]['sources'].append('https://private-sentinel:password@example.org/doc')
        chart['global_installed_model']['regions'][0]['derived'] = {'execution_host': secret}
        self.assertNotIn('private-sentinel', json.dumps(public.customer_project_ledger(ledger)))
        self.assertNotIn('private-sentinel', json.dumps(public.customer_chart_data(chart)))

    def test_changed_formal_registry_boundary_requires_a_new_review(self):
        doc = json.loads((REPORT_DATA / 'project-ledger.json').read_text())
        for key in ('schema', 'formal_database_ingested', 'aggregation_allowed'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                public.customer_project_ledger({**doc, key: 'changed'})


class PublishedAtlasPrivacyTests(unittest.TestCase):
    def test_customer_atlases_are_published_and_only_exact_static_resources_are_granted(self):
        queue = json.loads((ROOT / 'framework/visual_atlas_migration.json').read_text())
        by_id = {row['id']: row for row in queue['items']}
        manifest = json.loads((ROOT / 'framework/site_navigation.json').read_text())['access']['customer']
        self.assertTrue(all(not path.endswith('/') for path in manifest['assets']))
        for ident, (page, stem) in PUBLISHED_2D.items():
            self.assertEqual(by_id[ident]['status'], 'published', ident)
            self.assertIn('/' + page + '.html', manifest['pages'])
            for suffix in ('.svg', '-preview.svg', '.png'):
                self.assertIn('/assets/technical-atlas/' + stem + suffix, manifest['assets'])
        self.assertNotIn('/framework/visual_atlas_migration.json', manifest['data'])
        self.assertNotIn('/assets/models/server_v2_console.glb', manifest['assets'])

    def test_svg_metadata_and_embedded_resources_do_not_publish_private_audit_or_active_content(self):
        for _, stem in PUBLISHED_2D.values():
            for suffix in ('.svg', '-preview.svg'):
                path = ROOT / 'web/assets/technical-atlas' / (stem + suffix)
                data = path.read_text()
                with self.subTest(asset=path.name):
                    self.assertFalse(any(secret in data for secret in
                                         ('/Users/', '/srv/', '.local/', 'Bearer ', 'private-sentinel', 'execution_host')))
                    for element in ET.fromstring(data).iter():
                        name = element.tag.rsplit('}', 1)[-1]
                        self.assertNotIn(name, ('script', 'foreignObject'))
                        if name == 'metadata':
                            fields = json.loads(element.text)
                            allowed = ({'figure', 'style', 'method', 'pixels', 'sha256', 'identity', 'details'}
                                       if stem == 'rack-exploded-v1' else {'font_modification', 'licenses'})
                            self.assertLessEqual(set(fields), allowed)
                        for key, value in element.attrib.items():
                            if key.rsplit('}', 1)[-1] == 'href':
                                self.assertTrue(value.startswith(('data:', '#')))


class CustomerModelProjectionTests(unittest.TestCase):
    def test_model_projection_preserves_each_registered_calculation(self):
        spec = json.loads((ROOT / 'data/datacenter_model.json').read_text())
        result = public.customer_model(spec)
        self.assertEqual(set(result['assumptions']), set(spec['assumptions']))
        for preset in spec['presets']:
            with self.subTest(preset=preset):
                original = economics.with_preset(spec, preset)
                projected = economics.with_preset(result, preset)
                self.assertEqual(projected, original)
                self.assertEqual(economics.compute(projected, result), economics.compute(original, spec))
                self.assertEqual(economics.lifecycle(projected, result), economics.lifecycle(original, spec))
        self.assertEqual(result['grid'], spec['grid'])
        for key, row in spec['inputs'].items():
            if 'choices' in row: self.assertEqual(result['inputs'][key]['choices'], row['choices'])
        for key, row in spec['it_classes'].items():
            if 'density_basis' in row: self.assertEqual(result['it_classes'][key]['density_basis'], row['density_basis'])
        for key, row in spec['regions'].items():
            if 'gaps' in row: self.assertEqual(result['regions'][key]['gaps'], row['gaps'])

    def test_new_internal_model_fields_never_inherit_delivery_access(self):
        spec = json.loads((ROOT / 'data/datacenter_model.json').read_text())
        secret = '/srv/private-sentinel/secret-model-config.json'
        spec['execution_recipe'] = secret
        spec['provenance'] = {'path': secret}
        spec['assumptions']['worker_host'] = secret
        spec['inputs']['worker_host'] = {'label': secret}
        next(iter(spec['inputs'].values()))['execution_host'] = secret
        spec['groups'][0]['assignee'] = secret
        spec['groups'][0]['inputs'].append('worker_host')
        next(iter(spec['regions'].values()))['original_path'] = secret
        next(iter(spec['coolings'].values()))['review_audit'] = secret
        next(iter(spec['it_classes'].values()))['worker_recipe'] = secret
        next(iter(spec['presets'].values()))['command'] = secret
        next(iter(spec['presets'].values()))['changes']['worker_host'] = secret
        next(iter(spec['evidence'].values()))['private_receipt'] = secret
        spec['evidence']['worker_host'] = {'note': secret}
        next(iter(spec['calibration'].values()))['source_path'] = secret
        spec['anchors'][0]['operator'] = secret
        spec['grid']['private_axis'] = secret
        self.assertNotIn('private-sentinel', json.dumps(public.customer_model(spec)))

    def test_price_projection_excludes_private_contacts_and_unapproved_fields(self):
        rows = [{'series_id': 'price', 'value': 1, 'unit': 'USD', 'source_url': 'https://example.org/price',
                 'note': 'private-sentinel-note', 'internal_contact': 'private-sentinel-person'},
                {'series_id': 'channel', 'value': 2, 'source_url': 'channel:private-sentinel-person'},
                {'series_id': 'secret', 'value': 3, 'source_url': 'https://example.org/price', 'sensitive': True}]
        view = public.customer_prices({'records': rows, 'internal_audit': 'private-sentinel-audit'})
        self.assertEqual([row['series_id'] for row in view['records']], ['price'])
        self.assertNotIn('private-sentinel', json.dumps(view))

    def test_known_model_containers_accept_only_their_declared_leaf_types(self):
        spec = json.loads((ROOT / 'data/datacenter_model.json').read_text())
        private = {'future_private': {'path': '/srv/private-sentinel/internal-reading.json'}}
        first_class = next(row for row in spec['it_classes'].values() if 'density_basis' in row)
        first_class['density_basis']['future_private'] = private
        first_class['density_basis']['source'] = private
        first_class['density_basis']['url'] = 'https://private-sentinel:password@example.org/model'
        spec['inputs']['redundancy']['choices'].extend([private, ['private-sentinel', private],
                                                       ['a', 'b', 'private-sentinel']])
        spec['inputs']['it_mw']['max'] = private
        spec['assumptions']['wacc'] = private
        spec['presets']['baseline']['changes']['it_mw'] = private
        spec['presets']['baseline_2026_09_14']['check']['annualised'] = private
        spec['calibration']['ours_2026_09_14']['unit_cost'] = private
        spec['regions']['us_virginia']['gaps'].append(private)
        spec['groups'][0]['inputs'].extend([private, 'internal-private-sentinel'])
        spec['grid']['price_factors'].extend([private, True, float('nan')])
        result = public.customer_model(spec)
        self.assertNotIn('private-sentinel', json.dumps(result))
        self.assertNotIn('wacc', result['assumptions'])
        self.assertNotIn('max', result['inputs']['it_mw'])
        self.assertNotIn('annualised', result['presets']['baseline_2026_09_14']['check'])
        self.assertNotIn('unit_cost', result['calibration']['ours_2026_09_14'])
        self.assertTrue(all(type(value) in (int, float) for value in result['grid']['price_factors']))

    def test_prices_known_fields_are_scalar_and_source_attribution_has_no_credentials(self):
        private = {'future_private': '/srv/private-sentinel/price-receipt.json'}
        rows = [{'series_id': 'visible', 'value': 10, 'unit': 'USD', 'source_url': 'https://example.org/price',
                 'assumptions': private, 'region': private, 'frequency': [private]},
                {'series_id': 'dict-url', 'source_url': private},
                {'series_id': 'credential-url', 'source_url': 'https://private-sentinel:password@example.org/price'},
                {'series_id': 'token-url', 'source_url': 'https://example.org/price?access_token=private-sentinel'},
                {'series_id': 'bad-url', 'source_url': 'https://['}]
        result = public.customer_prices({'records': rows})
        self.assertEqual(result['records'], [{'series_id': 'visible', 'value': 10,
                                              'unit': 'USD', 'source_url': 'https://example.org/price'}])
        self.assertNotIn('private-sentinel', json.dumps(result))


class CustomerHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), self.thread.join(timeout=2)))
        for target, value in ((patch.object(serve, 'AUTH_ON', True), None),
                              (patch.object(auth, 'session_user', return_value='client'), None),
                              (patch.object(auth, 'user_role', return_value='customer'), None)):
            target.start()
            self.addCleanup(target.stop)

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=10)
        try:
            connection.request(method, path, json.dumps(body) if body is not None else None,
                               {'Content-Type': 'application/json'})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_internal_pages_files_and_encoded_variants_are_denied_for_get_and_head(self):
        denied = ('/ops.html', '/supply.html', '/doc.html?f=framework/CURRENT.md', '/admin/company.html',
                  '/admin/product/', '/admin/inresearchrepo.html', '/api/ops', '/api/targets',
                  '/api/supply', '/api/tasks', '/api/users', '/api/status', '/api/news/marks',
                  '/api/research-summary', '/api/research-adopted', '/api/research-materials', '/api/report?legacy=1',
                  '/report.html?legacy=1', '/report.html?legacy=0', '/api/report?%6cegacy=1',
                  '/data/research_knowledge.json', '/data/facts.json', '/data/assignments.json',
                  '/framework/current_state.json', '/data/raw/private.json',
                  '/assets/%2e%2e/data/research_knowledge.json', '/%64oc.html?f=framework/CURRENT.md',
                  '/search.html?scope=all', '/api/site-search?scope=backstage',
                  '/workspace.html?section=operations&view=health', '/product-catalog.html?view=research')
        for method in ('GET', 'HEAD'):
            for path in denied:
                with self.subTest(method=method, path=path):
                    status, headers, body = self.request(method, path)
                    self.assertIn(status, (403, 404))
                    self.assertEqual(headers.get('Cache-Control'), 'private, no-store')
                    if method == 'HEAD': self.assertEqual(body, b'')

    def test_every_operational_write_is_denied_before_dispatch_including_machine_receivers(self):
        paths = ('/api/add-price', '/api/run', '/api/users', '/api/assign', '/api/deliver',
                 '/api/research-tasks', '/api/supply', '/api/news/mark', '/api/materials',
                 '/api/reader-snapshot', '/api/product-catalog/nvidia', '/api/pilot-progress/nvidia',
                 '/api/intake-worker/ack', '/api/unregistered-write')
        with patch.object(serve.Handler, 'api_run') as run, \
             patch.object(serve.material_intake, 'receive') as receive, \
             patch.object(serve.research_tasks, 'mutate') as mutate:
            for path in paths:
                self.assertEqual(self.request('POST', path, {})[0], 403, path)
            run.assert_not_called()
            receive.assert_not_called()
            mutate.assert_not_called()

    def test_customer_task_reads_use_the_public_projection_and_examples(self):
        with patch.object(serve.research_tasks, 'snapshot', return_value={'public_view': True}) as snapshot:
            status, _, body = self.request('GET', '/api/research-tasks')
            self.assertEqual((status, json.loads(body)), (200, {'public_view': True}))
            snapshot.assert_called_once_with(serve.ROOT, actor='local', role='reader')
        with patch.object(serve.research_task_examples, 'snapshot', return_value={'public_view': True}) as examples:
            self.assertEqual(self.request('GET', '/api/research-task-examples')[0], 200)
            examples.assert_called_once_with(serve.ROOT, authenticated=False)
        self.assertEqual(self.request('GET', '/api/research-task-examples/private/files/secret.pdf')[0], 403)

    def test_customer_can_change_own_password_but_cannot_manage_another_account(self):
        with patch.object(auth, 'set_password', return_value=True) as change, \
             patch.object(serve, 'log_run'):
            self.assertEqual(self.request('POST', '/api/passwd', {
                'old_password': 'old-password', 'new_password': 'new-password'})[0], 200)
            change.assert_called_once_with('client', 'new-password', current_password='old-password')
        self.assertEqual(self.request('POST', '/api/users', {'action': 'reset', 'username': 'someone'})[0], 403)

    def test_customer_news_keeps_headlines_without_internal_counter_or_receiver_metadata(self):
        news = {'schema_version': 1, 'feed': {'status': 'connected', 'by_target': {'private-target': 1},
                'exported_at': '2026-10-13T00:00:00Z', 'items': [{'title_zh': '公开新闻', 'url': 'https://example.org/news',
                'published_at': 100, 'quote': 'private-quote', 'target_ids': ['private-target']}]},
                'reader': {'received_at': 'private-clock'}, 'pipeline': {'audit': 'private-audit'}}
        with patch.object(serve.research, 'cached_news', return_value=news) as read:
            status, _, body = self.request('GET', '/api/news?overview=0')
            self.assertEqual(status, 200)
            self.assertNotIn('private-', body.decode())
            self.assertEqual(json.loads(body)['feed']['items'][0]['title_zh'], '公开新闻')
            read.assert_called_once_with(serve.ROOT, company_id=None, limit=80, overview=True)

    def test_machine_credentials_do_not_bypass_customer_restrictions(self):
        with patch.object(serve.Handler, 'intake_worker', return_value=True) as credential:
            self.assertEqual(self.request('GET', '/api/intake-worker/pending')[0], 403)
            credential.assert_not_called()

    def test_fixed_report_pages_and_only_their_declared_dependencies_are_readable(self):
        status, _, library = self.request('GET', '/api/workspace?section=reports')
        self.assertEqual(status, 200)
        rows = json.loads(library)['blocks'][0]['rows']
        self.assertEqual([row['href'] for row in rows if row.get('href')],
                         ['/research/data-centers-2026.html', '/report.html'])
        for name in REPORT_PACKAGE:
            status, headers, body = self.request('GET', '/research/' + name + '.html')
            self.assertEqual(status, 200, name)
            self.assertNotIn(b'/assets/site-shell.js', body)
            self.assertEqual(headers.get('Cache-Control'), 'private, no-store')
        for asset in ('/assets/datacenter-research-ledger.js', '/assets/site-search.js', '/assets/site-guide.js'):
            self.assertEqual(self.request('GET', asset)[0], 200, asset)
        for path in ('/research/unregistered-report.html', '/research/unregistered-report.json',
                     '/docs/research/2026-10-11/data-centers/project-ledger.json',
                     '/data/research_knowledge.json', '/api/report?legacy=1', '/assets/site-shell.js'):
            self.assertIn(self.request('GET', path)[0], (403, 404), path)

    def test_report_downloads_use_customer_projection_for_get_and_head(self):
        for name, builder in (('project-ledger', public.customer_project_ledger),
                              ('chart-data', public.customer_chart_data)):
            path = '/research/data-centers-2026-' + name + '.json'
            original = json.loads((REPORT_DATA / (name + '.json')).read_text())
            status, headers, body = self.request('GET', path)
            self.assertEqual(status, 200, path)
            self.assertEqual(json.loads(body), builder(original))
            self.assertEqual(headers.get('Cache-Control'), 'private, no-store')
            self.assertIn('Cookie', headers.get('Vary', ''))
            head_status, head_headers, head_body = self.request('HEAD', path)
            self.assertEqual((head_status, head_body), (200, b''))
            self.assertEqual(headers['Content-Length'], head_headers['Content-Length'])
            if name == 'project-ledger':
                value = json.loads(body)
                self.assertEqual(len(value['records']), 168)
                self.assertIs(value['formal_database_ingested'], False)
                self.assertIs(value['aggregation_allowed'], False)
                self.assertNotIn('provenance', body.decode())
                self.assertNotIn('original_research_excerpt', body.decode())

    def test_default_snapshot_http_uses_deep_projection_and_legacy_never_reaches_dispatch(self):
        report = build_snapshot_report(ROOT)
        report['boundary']['registries']['private_path'] = 'private-sentinel-registry'
        report['chapters'][0]['account'][0]['evidence']['reviewer'] = 'private-sentinel-review'
        report['chapters'][0]['columns']['1']['items'][0]['source_path'] = 'private-sentinel-item'
        report['chapters'][0]['calibration'][0]['anchors']['execution_host'] = 'private-sentinel-anchor'
        report['chapters'][1]['systems'][0]['private_path'] = 'private-sentinel-system'
        report['chapters'][2]['formulas']['deploy_command'] = 'private-sentinel-formula'
        report['chapters'][3]['statuses']['reader_receipt'] = 'private-sentinel-status'
        with patch.object(serve.report_model, 'build_snapshot_report', return_value=report), \
             patch.object(serve.report_model, 'build_report') as legacy:
            status, headers, body = self.request('GET', '/api/report')
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), public.customer_report(report, ROOT))
            self.assertEqual(set(json.loads(body)['chapters'][3]), {'id', 'title'})
            self.assertNotIn('private-sentinel', body.decode())
            self.assertEqual(headers.get('Cache-Control'), 'private, no-store')
            head_status, head_headers, head_body = self.request('HEAD', '/api/report')
            self.assertEqual((head_status, head_body), (200, b''))
            self.assertEqual(headers['Content-Length'], head_headers['Content-Length'])
            for path in ('/api/report?legacy=1', '/api/report?legacy=0', '/report.html?legacy=1'):
                for method in ('GET', 'HEAD'):
                    self.assertEqual(self.request(method, path)[0], 403)
            legacy.assert_not_called()
        self.assertEqual(self.request('GET', '/report.html')[0], 200)
        self.assertEqual(self.request('GET', '/assets/markdown-inline.js')[0], 200)
        self.assertEqual(self.request('POST', '/api/report', {})[0], 403)

    def test_customer_session_is_restricted_even_when_local_operator_login_is_disabled(self):
        with patch.object(serve, 'AUTH_ON', False):
            self.assertEqual(self.request('GET', '/data/research_knowledge.json')[0], 403)
            self.assertEqual(self.request('POST', '/api/run', {})[0], 403)

    def test_delivery_pages_and_named_dependencies_are_declared_without_private_assets(self):
        for path in ('/', '/tasks.html', '/industry.html', '/projects.html', '/product-catalog.html',
                     '/assets/industry.js', '/assets/company-home.js', '/assets/fonts/fonts.css'):
            self.assertEqual(self.request('GET', path)[0], 200, path)
        for path in ('/assets/ops-dashboard.js', '/assets/supply.js', '/assets/catalog-admin.js',
                     '/assets/repository-status.js', '/assets/material-flow.js'):
            self.assertEqual(self.request('GET', path)[0], 403, path)

    def test_shared_brand_assets_deliver_exact_bytes_without_granting_asset_directories(self):
        paths = ('/assets/fonts/source-serif-regular.woff2', '/assets/fonts/source-serif-semibold.woff2',
                 '/assets/fonts/ibm-plex-mono.woff2', '/assets/marketing/wordmark-light.svg',
                 '/assets/marketing/wordmark-dark.svg')
        for path in paths:
            with self.subTest(path=path):
                status, headers, body = self.request('GET', path)
                self.assertEqual(status, 200)
                self.assertEqual(body, (ROOT / 'web' / path.lstrip('/')).read_bytes())
                head_status, head_headers, head_body = self.request('HEAD', path)
                self.assertEqual((head_status, head_body), (200, b''))
                self.assertEqual(head_headers['Content-Length'], str(len(body)))
                self.assertEqual(self.request('POST', path, {})[0], 403)
        for path in ('/assets/fonts/unregistered.woff2', '/assets/marketing/private-receipt.svg',
                     '/assets/ops-dashboard.js', '/data/research_knowledge.json'):
            for method in ('GET', 'HEAD'):
                with self.subTest(path=path, method=method):
                    self.assertEqual(self.request(method, path)[0], 403)

    def test_customer_company_index_drops_internal_fields_for_get_and_head(self):
        with patch.object(serve.source_publication, 'companies', return_value={'records': [{
                'company_id': 'example', 'name': '示例公司', 'profile': '公开公司简介',
                'roles': ['public-role', {'audit': 'private-person'}],
                'internal_contact': 'private-person', 'audit_receipt': 'private-audit'}]}):
            status, headers, body = self.request('GET', '/data/companies.json')
            self.assertEqual(status, 200)
            self.assertNotIn('private-', body.decode())
            self.assertEqual(json.loads(body)['records'][0]['name'], '示例公司')
            head_status, head_headers, head_body = self.request('HEAD', '/data/companies.json')
            self.assertEqual((head_status, head_body), (200, b''))
            self.assertEqual(head_headers['Content-Length'], headers['Content-Length'])

    def test_bom_data_are_deep_projected_and_only_exact_published_images_are_readable(self):
        for name, builder in (('bom', public.customer_bom), ('site_rights', public.customer_site_rights),
                              ('indicators', public.customer_indicators)):
            path = '/framework/' + name + '.json'
            status, headers, body = self.request('GET', path)
            self.assertEqual(status, 200, path)
            original = json.loads((ROOT / 'framework' / (name + '.json')).read_text())
            self.assertEqual(json.loads(body), builder(original))
            head_status, head_headers, head_body = self.request('HEAD', path)
            self.assertEqual((head_status, head_body), (200, b''))
            self.assertEqual(headers['Content-Length'], head_headers['Content-Length'])
            with patch.object(serve, 'source_path') as source:
                original['new_internal_audit'] = 'private-sentinel'
                rows = original.get('parts') or original.get('rights') or original.get('indicators')
                rows[0]['execution_host'] = 'private-sentinel'
                source.return_value.read_text.return_value = json.dumps(original)
                self.assertNotIn('private-sentinel', self.request('GET', path)[2].decode())
        self.assertEqual(self.request('GET', '/bom.html')[0], 200)
        for path in bom_asset_paths(): self.assertEqual(self.request('HEAD', path)[0], 200, path)
        routes = json.loads((ROOT / 'web/routes.json').read_text())
        for path in ('/assets/bom-classification/overview-v1-preview.jpg',
                     '/assets/technical-atlas/system/bess-v2.png', '/assets/technical-atlas/ssd-v1.svg'):
            status, _, body = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertEqual(hashlib.sha256(body).digest(), hashlib.sha256((ROOT / routes[path]).read_bytes()).digest())
        for path in ('/framework/tco_targets.json', '/framework/tco_factors.json', '/api/research-summary',
                     '/api/research-materials', '/api/research-adopted', '/assets/object-network.js',
                     '/assets/research-graph.js', '/assets/technical-atlas/system/private-new.png'):
            self.assertEqual(self.request('GET', path)[0], 403, path)

    def test_runtime_registered_company_identity_reaches_http_get_and_head_for_all_logged_in_roles(self):
        original = (ROOT / 'data/companies.json').read_bytes()
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict('os.environ', {'INRESEARCH_RUNTIME_ROOT': directory}):
            state = serve.source_publication.empty()
            state['objects']['company:runtime-only-public-test'] = {
                'id': 'company:runtime-only-public-test', 'type': 'company', 'name': '运行新增企业',
                'identity': {'company_id': 'runtime-only-public-test'}, 'audit': 'private-sentinel-registration'}
            target = Path(directory) / serve.source_publication.PATH
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(state))
            for role in ('customer', 'admin', 'member', 'intern'):
                with self.subTest(role=role), patch.object(auth, 'user_role', return_value=role):
                    status, headers, body = self.request('GET', '/data/companies.json')
                    self.assertEqual(status, 200)
                    row = next(row for row in json.loads(body)['records']
                               if row['company_id'] == 'runtime-only-public-test')
                    self.assertEqual(row['name'], '运行新增企业')
                    self.assertEqual(row['registration_status'], 'unverified')
                    self.assertIsNone(row['profile'])
                    self.assertNotIn('private-sentinel', body.decode())
                    head_status, head_headers, head_body = self.request('HEAD', '/data/companies.json')
                    self.assertEqual((head_status, head_body), (200, b''))
                    self.assertEqual(headers['Content-Length'], head_headers['Content-Length'])
        self.assertEqual((ROOT / 'data/companies.json').read_bytes(), original)

    def test_delivery_node_dashboard_is_deep_projected_and_workbench_dependencies_stay_private(self):
        original = json.loads((ROOT / 'data/dashboard.json').read_text())
        status, headers, body = self.request('GET', '/data/dashboard.json')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), public.customer_dashboard(original, ROOT))
        self.assertEqual(headers.get('Cache-Control'), 'private, no-store')
        self.assertEqual(set(json.loads(body)['parts']), set(original['parts']))
        head_status, head_headers, head_body = self.request('HEAD', '/data/dashboard.json')
        self.assertEqual((head_status, head_body), (200, b''))
        self.assertEqual(headers['Content-Length'], head_headers['Content-Length'])
        original['root']['account']['rows'][0]['evidence']['reviewer'] = 'private-sentinel'
        original['root']['cells']['1']['items'][0]['source']['reader_path'] = 'private-sentinel'
        original['parts']['transformer']['cells']['4']['worker'] = 'private-sentinel'
        original['factors'][0]['fetch_recipe'] = 'private-sentinel'
        original['changes']['internal_audit'] = 'private-sentinel'
        with patch.object(serve, 'source_path') as source:
            source.return_value.read_text.return_value = json.dumps(original)
            status, _, body = self.request('GET', '/data/dashboard.json')
            self.assertEqual(status, 200)
            self.assertNotIn('private-sentinel', body.decode())
        for path in ('/node.html', '/node.html?col=4', '/node.html?col=1', '/node.html?col=2',
                     '/node.html?id=part:transformer', '/node.html?id=site:grid'):
            self.assertEqual(self.request('GET', path)[0], 200, path)
        for path in ('/research-workbench.html', '/data/tco_targets.json', '/data/tco_factors.json',
                     '/framework/tco_targets.json', '/api/research-summary', '/api/research-materials',
                     '/api/research-adopted', '/assets/object-network.js', '/assets/research-graph.js'):
            for method in ('GET', 'HEAD'): self.assertEqual(self.request(method, path)[0], 403, path)

    def test_workspace_errors_and_role_are_checked_server_side(self):
        from inresearch.interfaces import workspace
        with patch.object(workspace, 'view', side_effect=PermissionError('private-operation')) as view:
            status, _, body = self.request('GET', '/api/workspace?section=industry&view=updates')
            self.assertEqual(status, 403)
            self.assertNotIn('private-operation', body.decode())
            view.assert_called_once_with(serve.ROOT, 'customer', 'client', {'section': 'industry', 'view': 'updates'})
        with patch.object(workspace, 'search') as search:
            self.assertEqual(self.request('GET', '/api/site-search?scope=all')[0], 403)
            search.assert_not_called()
        self.assertEqual(self.request('GET', '/api/workspace?section=industry&section=operations')[0], 403)

    def test_anonymous_navigation_does_not_open_workspace_or_search_or_feedback(self):
        with patch.object(auth, 'session_user', return_value=None):
            status, _, body = self.request('GET', '/api/navigation')
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['navigation'], {'delivery': [], 'backstage': []})
            for path in ('/api/workspace?section=industry', '/api/site-search?scope=delivery'):
                self.assertEqual(self.request('GET', path)[0], 401)
            self.assertEqual(self.request('POST', '/api/feedback', {'title': 'x', 'description': 'y'})[0], 401)

    def test_feedback_uses_authenticated_identity_without_research_write_dispatch(self):
        from inresearch.interfaces import workspace
        with patch.object(workspace, 'feedback', return_value={'ok': True, 'id': 'feedback-one'}) as feedback:
            status, _, body = self.request('POST', '/api/feedback', {'title': '问题', 'description': '说明', 'role': 'admin'})
            self.assertEqual((status, json.loads(body)['id']), (200, 'feedback-one'))
            self.assertEqual(feedback.call_args.args[:3], (serve.ROOT, 'customer', 'client'))

    def test_customer_economics_has_its_projection_and_no_internal_recipe(self):
        spec = json.loads((ROOT / 'data/datacenter_model.json').read_text())
        spec['execution_recipe'] = 'private-sentinel-command'
        spec['regions']['us_virginia']['original_path'] = 'private-sentinel-original'
        private = {'future_private': '/srv/private-sentinel/worker-metadata.json'}
        spec['it_classes']['gb300']['density_basis']['future_private'] = private
        spec['inputs']['redundancy']['choices'].append(['private-sentinel', private])
        spec['regions']['us_virginia']['gaps'].append(private)
        spec['assumptions']['wacc'] = private
        spec['grid']['price_factors'].append(private)
        spec['groups'][0]['inputs'].append(private)
        with patch.object(serve, 'source_path') as source:
            source.return_value.read_text.return_value = json.dumps(spec)
            status, headers, body = self.request('GET', '/data/datacenter_model.json')
            self.assertEqual(status, 200)
            self.assertNotIn('private-sentinel', body.decode())
            self.assertTrue(all('fetch_what' not in row for row in json.loads(body)['evidence'].values()))
            head_status, head_headers, head_body = self.request('HEAD', '/data/datacenter_model.json')
            self.assertEqual((head_status, head_body), (200, b''))
            self.assertEqual(head_headers['Content-Length'], headers['Content-Length'])
        with patch.object(serve, 'source_path') as source:
            source.return_value.read_text.return_value = json.dumps({'records': [
                {'series_id': 'public', 'value': 1, 'source_url': 'https://example.org/price', 'assumptions': private},
                {'series_id': 'private', 'value': 2, 'source_url': private}]})
            status, headers, body = self.request('GET', '/data/prices.json')
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['records'], [
                {'series_id': 'public', 'value': 1, 'source_url': 'https://example.org/price'}])
            self.assertNotIn('private-sentinel', body.decode())
            head_status, head_headers, head_body = self.request('HEAD', '/data/prices.json')
            self.assertEqual((head_status, head_body), (200, b''))
            self.assertEqual(head_headers['Content-Length'], headers['Content-Length'])
        for path in ('/ledger.html', '/cost.html', '/economics.html', '/tco.html', '/assets/datacenter-model.js'):
            self.assertEqual(self.request('GET', path)[0], 200, path)
        self.assertEqual(self.request('GET', '/data/prices.json')[0], 200)
        for path in ('/data/research_knowledge.json', '/api/research-adopted', '/api/report?legacy=1', '/framework/tco_targets.json'):
            self.assertEqual(self.request('GET', path)[0], 403, path)

    def test_one_published_2d_atlas_downloads_exact_assets_without_private_production_metadata(self):
        paths = ('/assets/technical-atlas/server-plan-v1.svg',
                 '/assets/technical-atlas/server-plan-v1-preview.svg',
                 '/assets/technical-atlas/server-plan-v1.png')
        self.assertEqual(self.request('GET', '/server-plan.html')[0], 200)
        for path in paths:
            with self.subTest(path=path):
                status, _, body = self.request('GET', path)
                self.assertEqual(status, 200)
                self.assertEqual(hashlib.sha256(body).hexdigest(),
                                 hashlib.sha256((ROOT / 'web' / path.lstrip('/')).read_bytes()).hexdigest())
                for secret in (b'/Users/', b'/srv/', b'.local/', b'Bearer ', b'private-sentinel'):
                    self.assertNotIn(secret, body[:100] if path.endswith('.png') else body)
                if path.endswith('.svg'):
                    drawing = ET.fromstring(body)
                    self.assertFalse(any(element.tag.rsplit('}', 1)[-1] in ('script', 'foreignObject', 'metadata')
                                         for element in drawing.iter()))
        for path in ('/assets/technical-atlas/private-sentinel.svg',
                     '/docs/design/technical-atlas/TA-12/acceptance-v1.json',
                     '/docs/design/technical-atlas/TA-12/preparation-v1.json',
                     '/framework/visual_atlas_migration.json', '/assets/models/server_v2_console.glb'):
            self.assertEqual(self.request('GET', path)[0], 403, path)

    def test_each_approved_2d_page_and_image_stays_available_without_3d_or_private_framework_access(self):
        for page, stem in PUBLISHED_2D.values():
            self.assertEqual(self.request('GET', '/' + page + '.html')[0], 200, page)
            for suffix in ('.svg', '-preview.svg', '.png'):
                path = '/assets/technical-atlas/' + stem + suffix
                self.assertEqual(self.request('GET', path)[0], 200, path)
        for path in ('/assets/technical-atlas/generation-private-sentinel.json', '/framework/tco_targets.json',
                     '/assets/models/private-sentinel.glb', '/assets/models/manifest.json', '/assets/hdri/studio.exr'):
            self.assertEqual(self.request('GET', path)[0], 403, path)

    def test_exact_3d_closure_and_public_model_projection_do_not_distribute_rejected_originals(self):
        for path in ('/bom3d.html', '/bom3d.html?x=70', '/bom3d.html?view=legacy',
                     '/rack3d.html', '/rack3d.html?view=server', '/rack3d.html?view=chip', '/rack3d.html?view=legacy'):
            self.assertEqual(self.request('GET', path)[0], 200, path)
        for path in SCENE_ASSETS: self.assertEqual(self.request('HEAD', path)[0], 200, path)
        routes = json.loads((ROOT / 'web/routes.json').read_text())
        for path in ('/assets/vendor/three.module.js', '/assets/panels/server_gpu.png',
                     '/assets/panels/display/switch_ib-contain.svg',
                     '/assets/technical-atlas/campus-exploded-v1.png'):
            status, _, body = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertEqual(hashlib.sha256(body).digest(), hashlib.sha256((ROOT / routes[path]).read_bytes()).digest())
        for page in ('bom3d', 'rack3d'):
            status, headers, body = self.request('GET', '/api/model-assets?page=' + page)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['models'], [])
            self.assertEqual(set(json.loads(body)), {'schema_version', 'models', 'revision'})
            head_status, head_headers, head_body = self.request('HEAD', '/api/model-assets?page=' + page)
            self.assertEqual((head_status, head_body), (200, b''))
            self.assertEqual(headers['Content-Length'], head_headers['Content-Length'])
        for path in ('/api/model-assets', '/api/model-assets?page=all', '/api/model-assets?page=bom3d&page=rack3d',
                     '/api/model-assets?page=bom3d&private=1', '/assets/models/server_v2_console.glb',
                     '/assets/models/manifest.json', '/assets/hdri/warehouse.exr', '/framework/modules.json',
                     '/data/products.json', '/assets/vendor/EXRLoader.js', '/assets/object-network.js'):
            for method in ('GET', 'HEAD'): self.assertEqual(self.request(method, path)[0], 403, path)

    def test_customer_csv_head_has_no_body_on_the_actual_socket(self):
        with socket.create_connection(self.server.server_address, timeout=10) as connection:
            connection.sendall(b'HEAD /api/product-catalog/nvidia?export=products HTTP/1.1\r\n'
                               b'Host: 127.0.0.1\r\nConnection: close\r\n\r\n')
            chunks = []
            while True:
                chunk = connection.recv(65536)
                if not chunk: break
                chunks.append(chunk)
            headers, separator, body = b''.join(chunks).partition(b'\r\n\r\n')
            self.assertEqual(separator, b'\r\n\r\n')
            self.assertEqual(headers.split(b'\r\n', 1)[0].split()[1], b'200')
            self.assertIn(b'text/csv', headers)
            length = next(line.partition(b':')[2].strip() for line in headers.split(b'\r\n')
                          if line.lower().startswith(b'content-length:'))
            self.assertGreater(int(length), 0)
            self.assertEqual(body, b'')


class InternAuxiliaryHTTPTests(unittest.TestCase):
    """Real signed intern cookies, private task state and durable personal feedback."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name) / 'runtime'; (self.runtime / 'data').mkdir(parents=True)
        for item in (patch.object(serve, 'AUTH_ON', True),
                     patch.object(auth, 'USERS_FILE', self.runtime / 'data/users.json'),
                     patch.object(auth, 'SECRET_FILE', self.runtime / 'data/.hub_secret'),
                     patch.dict('os.environ', {'INRESEARCH_RUNTIME_ROOT': str(self.runtime)})):
            item.start(); self.addCleanup(item.stop)
        auth.add_user('fixture-admin', 'fixture-password')
        auth.add_user('intern-self', 'fixture-password', 'intern')
        self.cookie = auth.make_cookie('intern-self').split(';', 1)[0]
        self.assertEqual(auth.session_user(self.cookie), 'intern-self')
        self.assertEqual(auth.user_role('intern-self'), 'intern')
        self.ledger = serve.research_tasks.ledger_path(ROOT)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text(json.dumps({'version': 1, 'revision': 1, 'operations': [], 'packages': [
            {'id': 'own', 'title': '研究 任务 own', 'region': '测试地区', 'scope': '测试范围', 'sources': '公开来源',
             'status': 'ready', 'assignee': 'intern-self'},
            {'id': 'other', 'title': '研究 另一位隐私任务', 'region': '测试地区', 'scope': '测试范围', 'sources': '公开来源',
             'status': 'ready', 'assignee': 'another-intern'}]}))
        self.server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), self.thread.join(timeout=2)))

    def request(self, method, path, payload=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=10)
        try:
            connection.request(method, path, json.dumps(payload) if payload is not None else None,
                               {'Cookie': self.cookie, 'Content-Type': 'application/json'})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_signed_intern_search_contains_only_permitted_menu_entries_and_own_task(self):
        status, _, identity = self.request('GET', '/api/whoami')
        self.assertEqual((status, json.loads(identity)['role']), (200, 'intern'))
        status, _, body = self.request('GET', '/api/navigation')
        self.assertEqual(status, 200)
        navigation = json.loads(body)['navigation']
        self.assertEqual(navigation['delivery'], [])
        self.assertEqual([row['id'] for row in navigation['backstage']], ['production'])
        self.assertEqual([row['id'] for row in navigation['backstage'][0]['children']], ['tasks', 'intake'])
        path = '/api/site-search?scope=backstage&q=' + quote('研究')
        status, headers, body = self.request('GET', path)
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result['scope'], 'backstage')
        self.assertTrue(all(row['area'] == 'backstage' for row in result['rows']))
        self.assertEqual([row['title'] for row in result['rows'] if row['kind'] == '团队任务'], ['研究 任务 own'])
        menu = [row for row in result['rows'] if row['kind'] in ('栏目', '页面')]
        self.assertEqual({row['href'] for row in menu}, {'/tasks.html#work-packages', '/supply.html#targets'})
        self.assertNotIn('另一位隐私', body.decode())
        status, head, body = self.request('HEAD', path)
        self.assertEqual((status, body), (200, b''))
        self.assertEqual(head['Content-Length'], headers['Content-Length'])

    def test_intern_auxiliary_pages_are_readable_but_other_scopes_and_backend_sections_stay_denied(self):
        for path in ('/search.html', '/search.html?scope=backstage', '/guide.html', '/guide.html?view=feedback',
                     '/guide.html?view=privacy', '/assets/site-guide.js', '/assets/site-search.js'):
            for method in ('GET', 'HEAD'): self.assertEqual(self.request(method, path)[0], 200, path)
        for path in ('/search.html?scope=all', '/search.html?scope=delivery',
                     '/api/site-search?scope=all&q=x', '/api/site-search?scope=delivery&q=x',
                     '/api/site-search?scope=backstage&scope=all&q=x', '/guide.html?view=internal',
                     '/workspace.html?section=architecture', '/api/workspace?section=content&view=feedback',
                     '/api/workspace?section=production&view=adoption', '/api/research-summary', '/api/users'):
            for method in ('GET', 'HEAD'): self.assertEqual(self.request(method, path)[0], 403, path)

    def test_intern_feedback_is_private_and_uses_authenticated_actor_without_new_research_write_grants(self):
        before = self.ledger.read_bytes()
        status, _, body = self.request('POST', '/api/feedback', {
            'title': '入口反馈', 'description': '测试反馈内容', 'context': '/guide.html?view=feedback',
            'actor': 'another-user', 'role': 'admin'})
        self.assertEqual(status, 200)
        ident = json.loads(body)['id']
        path = self.runtime / 'data/raw/site-feedback/requests.jsonl'
        saved = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual([(row['id'], row['actor'], row['role']) for row in saved], [(ident, 'intern-self', 'intern')])
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertIn('/api/feedback', auth.INTERN_POST_ALLOW)
        for target in ('/api/run', '/api/add-price', '/api/users', '/api/research-summary'):
            self.assertEqual(self.request('POST', target, {})[0], 403, target)
        self.assertEqual(self.request('GET', '/data/raw/site-feedback/requests.jsonl')[0], 403)


if __name__ == '__main__':
    unittest.main()
