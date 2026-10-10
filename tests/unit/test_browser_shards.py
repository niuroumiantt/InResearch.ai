import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path


class BrowserShardTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for browser suite selection')
    def test_ci_shards_cover_every_existing_core_case_once(self):
        root=Path(__file__).resolve().parents[2]
        matrix=re.search(r'suites: \[([^]]+)\]',(root/'.github/workflows/validate.yml').read_text()).group(1)
        names=[name.strip() for name in matrix.split(',')]
        script="const names=JSON.parse(process.argv[1]);const s=require('./tests/browser_suites.cjs'); console.log(JSON.stringify({cases:s.selectCases(names),expectedCases:s.selectCases(['core','model_assets']),shards:Object.fromEntries(names.map(n=>[n,s.selectSuites([n])])),core:s.selectSuites(['core']),a:s.selectSuites(['core_a']),b:s.selectSuites(['core_b']),c:s.selectSuites(['core_c']),assets:s.selectSuites(['model_assets']),scenes:s.suiteScenarios('part_dossier'),densities:s.suiteScenarios('scene_atlas'),assetScenes:s.suiteScenarios('model_assets'),rackScenes:s.suiteScenarios('rack_exploded'),chipScenes:s.suiteScenarios('chip_package'),systemScenes:s.suiteScenarios('system_atlas'),scaleScenes:s.suiteScenarios('scale_atlas'),campusScenes:s.suiteScenarios('campus_overview')}));"
        groups=json.loads(subprocess.check_output(['node','-e',script,json.dumps(names)],cwd=root,text=True))
        expected={'ops_dashboard','industry','repository_pages','supply','nvidia_pilot','product_catalog',
                  'company_page','company_window','company_catalog_map','catalog_materials','compute_catalog',
                  'ui_skin','datacenter_cost','datacenter_economics','datacenter_tco','datacenter_news',
                  'url_rendering','research_delivery','auth_appearance','research_summary','part_dossier',
                  'technical_atlas','bom_layout','system_atlas','scale_atlas','campus_overview','campus_exploded','campus_plan','server_assembly','server_plan','rack_assembly','rack_atlas','rack_exploded','rack_exploded_atlas','chip_package','chip_atlas','dashboard','scene_bootstrap','scene_framing','scene_resources','scene_atlas'}
        self.assertEqual(set(groups['core']),expected)
        selected=[case['suite'] for case in groups['cases'] if case['suite']!='model_assets']
        self.assertEqual(set(selected),expected)
        case_ids=[(c['suite'],c['scenario']) for c in groups['cases']]
        self.assertEqual(len(case_ids),len(set(case_ids)))
        self.assertEqual(set(case_ids),{(c['suite'],c['scenario']) for c in groups['expectedCases']})
        for heavy in ('server_assembly','rack_assembly','rack_exploded','scene_atlas'):
            self.assertEqual(groups['shards'][heavy],[heavy])
        self.assertEqual(groups['c'],['part_dossier'])
        self.assertEqual(set(groups['scenes']),{'/bom3d.html?p=server',
            *('/rack3d.html?node=part:'+part for part in ['server','gpu','hbm','cpu','dram','nic','psu','server-fan','coldplate'])})
        self.assertEqual(len(groups['scenes']),10)
        self.assertEqual(groups['densities'],['1','2'])
        self.assertEqual(groups['assetScenes'],['bom3d','rack3d','compare'])
        self.assertEqual(groups['rackScenes'],['views','assembly'])
        self.assertEqual(groups['chipScenes'],['views','assembly'])
        self.assertEqual(groups['systemScenes'],['views','downloads'])
        self.assertEqual(groups['scaleScenes'],['views','downloads'])
        self.assertEqual(groups['campusScenes'],['views','geometry','navigation','lifecycle'])
        for campus in ('campus_overview','campus_exploded'):
            self.assertEqual({c['scenario'] for c in groups['cases'] if c['suite']==campus},({'views','geometry','navigation','lifecycle'} | ({'whole'} if campus=='campus_exploded' else set())))
        self.assertEqual(groups['assets'],['model_assets'])
