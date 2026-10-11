"""Capacity outputs share the current physical-site projection, with coverage."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inresearch.delivery import project_capacity_map as capacity_map
from inresearch.knowledge import indicators
from inresearch.paths import project_root
from inresearch.storage.layout import workspace_path


def observation(ident, when, **fields):
    """Complete test-only reviewed v2 observation; never touches formal data."""
    reviewed = '2026-10-11T00:00:00Z'
    return {'id': ident, 'schema_version': 2, 'effective_at': when,
            'recorded_at': reviewed, 'reviewed_at': reviewed, 'scope': 'whole_site',
            'kind': 'disclosed', 'basis': 'test-only source review', 'fields': fields,
            'sources': [{'url': 'https://example.test/capacity'}],
            'source_versions': [{'source_sha256': 'a'*64, 'published_at': None, 'first_received_at': None,
                'published_at_precision': 'unknown', 'first_received_at_precision': 'unknown',
                'published_at_provenance': 'test-only unknown source date',
                'first_received_at_provenance': 'test-only unknown receipt'}],
            'adoption': {'review_id': ident, 'source_kind': 'reader_report', 'source_id': 'fixture-report',
                'source_version': 'b'*64, 'document_refs': [{'sha256': 'a'*64}], 'target_ids': ['fixture-demand'],
                'assertions': [{'source_sha256': 'a'*64, 'quote': 'fixture capacity', 'locator': 'reader:page:1'}],
                'review': {'by': 'fixture reviewer', 'at': reviewed, 'tier': 'A', 'score': 8,
                    'authority': 'delegated_reviewer', 'decision': 'adopted', 'rationale': 'test-only capacity review',
                    'delegation': {'delegate': 'fixture reviewer', 'granted_by': 'fixture owner',
                        'granted_at': '2026-10-11', 'reference': 'test-only delegation',
                        'scope': 'new_or_supplemental_research'}}}}


def rows():
    current = {'site_id': 'current', 'name': 'Current campus', 'status': 'L8', 'location': 'fixture',
               'coordinates': '32,-99', 'capacity_it_mw': 900, 'capacity_it_mw_by_status': {'L8': 450, 'L6': 450},
               'observations': [
                   observation('current', '2026-07-28', capacity_it_mw=421,
                               capacity_it_mw_by_status={}, capacity_assessment=None),
                   observation('future', '2099-11-01', capacity_it_mw=843,
                               capacity_it_mw_by_status={}, capacity_assessment=None)]}
    ranged = {'value_range': [.4, .5], 'unit': 'GW', 'assumptions': ['native source interval']}
    return [current,
            {'site_id': 'phases', 'name': 'Phases', 'location': 'fixture', 'status': 'L8',
             'capacity_it_mw': 300, 'capacity_it_mw_by_status': {'L8': 100, 'L6': 200}},
            {'site_id': 'duplicate', 'status': 'L8', 'capacity_it_mw': 9999, 'duplicate_of': 'current'},
            *[{'site_id': lifecycle, 'status': 'L8', 'capacity_it_mw': 9999, 'lifecycle': lifecycle}
              for lifecycle in ('paused', 'cancelled', 'closed')],
            {'site_id': 'portfolio-all', 'status': 'L8', 'capacity_it_mw': 9999},
            {'site_id': 'ranged', 'status': 'L8', 'observations': [observation('range', '2026-07-28',
                capacity_it_mw=ranged, capacity_it_mw_by_status={}, capacity_assessment=None)]},
            {'site_id': 'mixed', 'status': 'L8', 'observations': [observation('mixed', '2026-07-28',
                capacity_it_mw=None, capacity_it_mw_by_status={'L8': 50, 'L6': ranged}, capacity_assessment=None)]},
            {'site_id': 'unknown', 'status': 'L8'},
            {'site_id': 'zero', 'status': 'L8', 'capacity_it_mw': 0}]


class CapacityConsumerTests(unittest.TestCase):
    def test_map_current_time_and_phases_use_one_capacity_projection(self):
        records = rows()
        before = copy.deepcopy(records)
        ranked = capacity_map.ranking(records, 10)
        self.assertEqual([(p['site_id'], p['total_mw']) for p in ranked['rows']], [('current', 421), ('phases', 300)])
        self.assertEqual(capacity_map.cap_total(records[0]), 421)
        self.assertEqual(capacity_map.cap_by_bucket(records[0]), (421, 0, 0))
        self.assertEqual(capacity_map.cap_total(records[1]), 300)  # Headline is not added to phases.
        self.assertEqual(ranked['rows'][0]['coordinates'], [32, -99])
        self.assertEqual(ranked['excluded'], {'portfolio': 1, 'duplicate': 1, 'inactive': 3,
                                             'range': 2, 'unknown': 1, 'nonpositive': 1})
        for record in records[2:]:
            with self.subTest(record=record['site_id']):
                self.assertIsNone(capacity_map.cap_total(record))
                self.assertIsNone(capacity_map.cap_by_bucket(record))
        self.assertEqual(records, before)

    def test_indicator_single_value_subtotals_disclose_ranges_and_identity_exclusions(self):
        records = rows()
        summary = indicators.capacity_summary(records)
        self.assertEqual(indicators.cap_buckets(records[0]), (421, 0, 0))
        self.assertEqual(indicators.cap_buckets(records[1]), (100, 200, 0))
        self.assertEqual(indicators.cap_buckets(records[8]), (50, 0, 0))
        for record in records[2:7]:
            with self.subTest(record=record['site_id']):
                self.assertEqual(indicators.cap_buckets(record), (0, 0, 0))
        self.assertEqual([summary['totals'][stage] for stage in ('operating', 'construction', 'planning')], [571, 200, 0])
        self.assertEqual(summary['coverage']['active_sites'], 6)
        self.assertEqual(summary['coverage']['ranged_sites'], 2)
        self.assertEqual(summary['coverage']['unknown_sites'], 1)
        self.assertTrue(summary['coverage']['has_unquantified_sites'])
        self.assertEqual(summary['coverage']['inactive_sites_excluded'], 3)
        self.assertEqual(summary['coverage']['duplicates_excluded'], 1)
        self.assertEqual(summary['coverage']['portfolios_excluded'], 1)
        only_range = indicators.capacity_summary([records[7]])
        self.assertEqual(only_range['totals']['operating'], 0)  # Single-value subtotal, never midpoint.
        self.assertEqual(only_range['coverage']['ranged_sites'], 1)
        self.assertTrue(only_range['coverage']['has_unquantified_sites'])

    def test_refresh_isolated_projection_retains_partial_capacity_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'data').mkdir(); (root/'framework').mkdir()
            for name, records in [('projects', rows()), ('prices', []), ('contracts', [])]:
                (root/'data'/f'{name}.json').write_text(json.dumps({'records': records}))
            path = root/'framework/indicators.json'
            path.write_text(json.dumps({'indicators': [{'id': 'global_operational_gw', 'value': 999},
                                                       {'id': 'manual', 'value': 7}]}))
            with patch.dict('os.environ', {'INRESEARCH_RUNTIME_ROOT': ''}):
                result = indicators.refresh(root)
            projected = json.loads(path.read_text())['indicators']
            self.assertEqual(result['count'], 1)
            self.assertEqual(projected[0]['value'], .57)
            self.assertIn('单值小计', projected[0]['auto_note'])
            self.assertIn('含区间 2', projected[0]['auto_note'])
            self.assertTrue(projected[0]['auto_coverage']['has_unquantified_sites'])
            self.assertEqual(projected[1], {'id': 'manual', 'value': 7})

    def test_map_render_lists_exclusions_and_reads_projected_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'data').mkdir()
            (root/'data/projects.json').write_text(json.dumps({'records': rows()}))
            with patch.object(capacity_map, 'ROOT', root), patch.object(capacity_map, 'OUT', root/'out'), \
                    patch.object(capacity_map, 'CHROME', str(root/'no-chrome')), \
                    patch.object(capacity_map, 'world_paths', return_value=[]), \
                    patch.object(capacity_map.sys, 'argv', ['map', '10']), \
                    patch.dict('os.environ', {'INRESEARCH_RUNTIME_ROOT': ''}):
                self.assertEqual(capacity_map.main(), 0)
            html = next((root/'out').glob('*.html')).read_text()
            self.assertIn('2 个可排名园区', html)
            self.assertIn('重复 1、非活跃 3、含区间 2', html)
            self.assertIn('含区间园区的单值部分也不冒充完整容量参与排名', html)
            self.assertIn('<circle', html)
            self.assertIn('421', html)
            self.assertNotIn('843', html)

    def test_deployed_refresh_reads_published_projects_and_only_writes_runtime_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root, runtime = (Path(directory).resolve()/name for name in ('source', 'runtime'))
            (root/'data').mkdir(parents=True); (root/'framework').mkdir()
            (runtime/'data').mkdir(parents=True)
            contract = (project_root()/'framework/storage_contract.json').read_bytes()
            (root/'framework/storage_contract.json').write_bytes(contract)
            (root/'data/projects.json').write_text(json.dumps({'records': rows()}))
            # An obsolete runtime copy must never override published project evidence.
            (runtime/'data/projects.json').write_text(json.dumps({'records': [
                {'site_id': 'obsolete-runtime-copy', 'status': 'L8', 'capacity_it_mw': 999999}]}))
            definition = root/'framework/indicators.json'
            definition.write_text(json.dumps({'indicators': [{'id': 'global_operational_gw', 'value': 999}]}))
            original = definition.read_bytes()
            with patch.dict('os.environ', {'INRESEARCH_RUNTIME_ROOT': str(runtime)}):
                for name in ('prices', 'contracts'):
                    workspace_path(f'data/{name}.json', root).write_text(json.dumps({'records': []}))
                indicators.refresh(root)
                projection = workspace_path('framework/indicators.json', root)
            self.assertTrue(projection.is_relative_to(runtime))
            projected = json.loads(projection.read_text())['indicators'][0]
            self.assertEqual(projected['value'], .57)
            self.assertTrue(projected['auto_coverage']['has_unquantified_sites'])
            self.assertEqual(definition.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
