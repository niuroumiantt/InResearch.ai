import json
import shutil
import subprocess
import unittest
from pathlib import Path


class BrowserShardTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for browser suite selection')
    def test_ci_shards_cover_every_existing_core_case_once(self):
        root=Path(__file__).resolve().parents[2]
        script="const s=require('./tests/browser_suites.cjs'); console.log(JSON.stringify({core:s.selectSuites(['core']),a:s.selectSuites(['core_a']),b:s.selectSuites(['core_b']),assets:s.selectSuites(['model_assets'])}));"
        groups=json.loads(subprocess.check_output(['node','-e',script],cwd=root,text=True))
        expected={'ops_dashboard','industry','repository_pages','supply','nvidia_pilot','product_catalog',
                  'company_page','company_window','company_catalog_map','catalog_materials','compute_catalog',
                  'ui_skin','datacenter_cost','datacenter_economics','datacenter_tco','datacenter_news',
                  'url_rendering','research_delivery','auth_appearance','research_summary','part_dossier',
                  'technical_atlas','server_assembly','server_plan','dashboard','scene_bootstrap','scene_framing','scene_resources','scene_atlas'}
        self.assertEqual(set(groups['core']),expected)
        self.assertEqual(set(groups['a'])|set(groups['b']),expected)
        self.assertEqual(set(groups['a'])&set(groups['b']),set())
        self.assertEqual(len(groups['a'])+len(groups['b']),len(expected))
        self.assertNotEqual('part_dossier' in groups['a'],'scene_atlas' in groups['a'])
        self.assertEqual(groups['assets'],['model_assets'])
