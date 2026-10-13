"""Unchanged homepage snapshots share work without hiding newly installed data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from inresearch.knowledge import industry
from inresearch.delivery import source_publication as publication
from inresearch.storage.files import write_json

class HomepageProjectionCacheTests(unittest.TestCase):
    def test_concurrent_readers_share_projection_and_atomic_install_invalidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root/'registry.json'
            write_json(runtime, {'version':1})
            industry._home_snapshot_cache.clear()
            with patch('inresearch.storage.layout.workspace_path', return_value=runtime), patch.object(industry, 'snapshot', return_value={'rows':[{'value':1}]}) as project:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    values = list(pool.map(lambda _:industry.homepage_snapshot(root), range(4)))
                self.assertEqual(project.call_count, 1)
                values[0]['rows'][0]['value'] = 9
                self.assertEqual(industry.homepage_snapshot(root)['rows'][0]['value'],1)
                write_json(runtime, {'version':2})
                industry.homepage_snapshot(root)
                self.assertEqual(project.call_count,2)
                write_json(root/'framework/research_publication.json', {'public':[]})
                industry.homepage_snapshot(root)
                self.assertEqual(project.call_count,3)

    def test_data_change_during_build_and_failures_are_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);runtime=root/'registry.json'
            write_json(runtime, {'version':1});industry._home_snapshot_cache.clear()
            def build(*args):
                write_json(runtime, {'version':2})
                return {'rows':[]}
            with patch('inresearch.storage.layout.workspace_path',return_value=runtime), patch.object(industry,'snapshot',side_effect=build) as project:
                industry.homepage_snapshot(root);industry.homepage_snapshot(root)
                self.assertEqual(project.call_count,2)
            industry._home_snapshot_cache.clear()
            with patch('inresearch.storage.layout.workspace_path',return_value=runtime), patch.object(industry,'snapshot',side_effect=ValueError('invalid')) as project:
                for _ in range(2):
                    with self.assertRaises(ValueError):industry.homepage_snapshot(root)
                self.assertEqual(project.call_count,2)

    def test_company_directory_does_not_copy_or_validate_observation_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write_json(root/'data/companies.json',{'records':[]})
            obj={'id':'company:one','type':'company','identity':{'company_id':'one'},'name':'One'}
            write_json(root/'data/object_observations.json',{'version':1,'objects':{},'records':[]})
            state={'objects':{'company:one':obj},'records':[{'irrelevant_history':object()}]}
            before=copy.deepcopy(obj)
            with patch.object(publication,'state',side_effect=AssertionError('no second runtime read')):
                result=publication.companies(root,runtime=state)
            self.assertEqual(result['records'][0]['company_id'],'one')
            self.assertEqual(obj,before)
