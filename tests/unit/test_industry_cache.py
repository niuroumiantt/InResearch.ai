"""Reader caching must not hide updates, mix filters or multiply builders."""
import concurrent.futures
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from inresearch.knowledge import industry


class IndustryCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()

    def test_concurrent_readers_build_once_and_receive_independent_values(self):
        entered, release = threading.Event(), threading.Event()
        def build(*args):
            entered.set()
            self.assertTrue(release.wait(5))
            return {'rows': [{'name': 'SG3'}]}
        with patch.object(industry, 'snapshot', side_effect=build) as builder:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(industry.cached_snapshot, self.root, {'overview': '1'}) for _ in range(4)]
                self.assertTrue(entered.wait(5))
                release.set()
                values = [future.result(5) for future in futures]
            self.assertEqual(builder.call_count, 1)
            values[0]['rows'][0]['name'] = 'mutated'
            self.assertEqual(industry.cached_snapshot(self.root, {'overview': '1'})['rows'][0]['name'], 'SG3')
            self.assertEqual(values[1]['rows'][0]['name'], 'SG3')

    def test_runtime_replacement_filters_and_day_invalidate(self):
        registry = self.root / 'data/raw/source-publication/registry.json'
        registry.parent.mkdir(parents=True)
        registry.write_text('{"sites":1}')
        with patch.object(industry, 'snapshot', side_effect=lambda *args: {'registry': registry.read_text()}) as builder:
            industry.cached_snapshot(self.root, {'overview': '1'})
            replacement = registry.with_suffix('.new')
            replacement.write_text('{"sites":2}')  # equal length, atomically replaced
            replacement.replace(registry)
            self.assertEqual(industry.cached_snapshot(self.root, {'overview': '1'})['registry'], '{"sites":2}')
            industry.cached_snapshot(self.root, {'site': 'sg3'})
            with patch.object(industry, 'date') as day:
                day.today.return_value.isoformat.return_value = '2099-01-01'
                industry.cached_snapshot(self.root, {'overview': '1'})
            self.assertEqual(builder.call_count, 4)

    def test_build_errors_and_changing_inputs_do_not_poison_cache(self):
        path = self.root / 'data/projects.json'
        with patch.object(industry, 'snapshot', side_effect=ValueError('corrupt')):
            with self.assertRaises(ValueError): industry.cached_snapshot(self.root)
        def changed(*args):
            path.write_text('{}')
            return {'stale': True}
        with patch.object(industry, 'snapshot', side_effect=changed):
            with self.assertRaises(OSError): industry.cached_snapshot(self.root)
        with patch.object(industry, 'snapshot', return_value={'fresh': True}) as builder:
            self.assertEqual(industry.cached_snapshot(self.root), {'fresh': True})
            self.assertEqual(builder.call_count, 1)

    def test_baseline_and_public_contract_changes_invalidate(self):
        with patch.object(industry, 'snapshot', return_value={}) as builder:
            industry.cached_snapshot(self.root)
            for name in ('data/projects.json', 'data/companies.json', 'data/object_observations.json',
                         'data/prices.json', 'data/facts.json', 'framework/research_publication.json'):
                path = self.root / name
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps({'changed': name}))
                industry.cached_snapshot(self.root)
            self.assertEqual(builder.call_count, 7)
