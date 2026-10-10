import importlib.util
import json
from html.parser import HTMLParser
import tempfile
import sys
import shutil
from unittest.mock import patch
import unittest
from pathlib import Path
from inresearch.paths import project_root

ROOT=project_root()
spec=importlib.util.spec_from_file_location('research_dashboard',ROOT/'scripts/repository_research_dashboard.py')
dashboard=importlib.util.module_from_spec(spec);spec.loader.exec_module(dashboard)

class Links(HTMLParser):
    def __init__(self, text):
        super().__init__();self.urls=[];self.ids=[];self.feed(text)
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='a':self.urls.append(d['href'])
        if d.get('id'):self.ids.append(d['id'])

class ResearchDashboardTests(unittest.TestCase):
    def test_links_resolve_and_missing_targets_are_not_presented_as_completed(self):
        def table(headers, rows):return json.dumps([headers,rows],ensure_ascii=False)
        html=dashboard.build(ROOT,table);links=Links(html)
        routes=json.loads((ROOT/'web/routes.json').read_text())
        for url in links.urls:
            if url.startswith('/'):self.assertIn(url.split('#')[0],routes)
            elif url.startswith('#'):self.assertIn(url[1:],links.ids+['material-board'])
        self.assertIn('不等于已有答案',html)
        self.assertIn('未接入',html)
        self.assertIn('已交付目标',html)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for p in ('framework/tco_targets.json','framework/bom.json','framework/research_questions.json','framework/supply_contract.json','data/research_knowledge.json'):
                dst=root/p;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((ROOT/p).read_bytes())
            p=root/'framework/tco_targets.json';v=json.loads(p.read_text());v['targets']=[];p.write_text(json.dumps(v))
            changed=dashboard.build(root,table)
            self.assertNotEqual(changed,html)
            self.assertIn('<strong>0</strong>资料目标',changed)

    def test_daily_archive_contains_all_real_control_room_dependencies(self):
        def module(name):
            spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/ (name+'.py'))
            m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
        daemon=module('repository_pages_daemon');sync=module('sync_repo_pages')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in daemon.SOURCE_FILES:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
            with patch.object(sync,'ROOT',root), patch.object(sys,'path',[str(root/'scripts')]+sys.path):
                meta=sync.provenance(sync.inresearch_sources(),'2026-10-10T22:00:00+08:00')
                html=sync.build_inresearch(meta)
                self.assertIn('audit-demand',html)
                self.assertIn('material-board',html)
