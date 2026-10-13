import copy
import json
import os
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from inresearch.interfaces import workspace

ROOT = Path(__file__).resolve().parents[2]


class SiteWorkspaceTests(unittest.TestCase):
    def test_directory_counts_and_distinct_delivery_domains(self):
        doc = workspace.manifest(ROOT)
        self.assertEqual([len(doc['navigation'][a]) for a in ('delivery','backstage')], [6,6])
        self.assertEqual([sum(len(s['children']) for s in doc['navigation'][a]) for a in ('delivery','backstage')], [14,20])
        self.assertEqual(doc['navigation']['delivery'][-1]['children'], [])
        self.assertEqual(doc['navigation']['backstage'][0]['children'], [])
        self.assertEqual(workspace.resolve(ROOT,'/product-catalog.html?c=nvidia')['section'],'companies')
        self.assertEqual(workspace.resolve(ROOT,'/compute-atlas.html')['section'],'atlas')

    def test_roles_filter_both_navigation_and_direct_workspace(self):
        public = workspace.navigation(ROOT,'reader','', '/')
        self.assertEqual(public['navigation'], {'delivery':[],'backstage':[]})
        self.assertFalse(public['search']['enabled'])
        self.assertEqual(public['footer']['groups'], [])
        customer = workspace.navigation(ROOT,'customer','customer-one','/workspace.html?section=companies&view=companies')
        self.assertEqual(len(customer['navigation']['delivery']),6)
        self.assertEqual(customer['navigation']['backstage'],[])
        self.assertEqual(customer['search']['scopes'],['delivery'])
        self.assertIsNone(customer['footer']['runtime'])
        operations=next(item for item in workspace.permitted(ROOT,'member')['backstage'] if item['id']=='operations')
        self.assertEqual([item['id'] for item in operations['children']],['deployment'])
        for section in ('overview','content','construction','architecture','operations'):
            with self.assertRaises(PermissionError): workspace.view(ROOT,'customer','customer-one',{'section':section})
        intern = workspace.permitted(ROOT,'intern')
        self.assertEqual(intern['delivery'],[])
        self.assertEqual([s['id'] for s in intern['backstage']],['production'])
        self.assertEqual([c['id'] for c in intern['backstage'][0]['children']],['tasks','intake'])
        self.assertEqual(intern['backstage'][0]['children'][1]['href'],'/supply.html#targets')
        with self.assertRaises(PermissionError):workspace.view(ROOT,'intern','intern-one',{'section':'production','view':'adoption'})

    def test_page_inventory_marks_admin_pages_without_unusable_member_links(self):
        member=workspace.view(ROOT,'member','team-one',{'section':'architecture','view':'pages'})
        admin=workspace.view(ROOT,'admin','owner',{'section':'architecture','view':'pages'})
        protected=[row for row in member['blocks'][0]['rows'] if row['access']=='管理员']
        self.assertTrue(protected)
        self.assertTrue(all('href' not in row for row in protected))
        self.assertTrue(all('href' in row for row in admin['blocks'][0]['rows']))
        entry=next(row for row in member['blocks'][0]['rows'] if row['name']=='workspace.html')
        self.assertEqual(entry['href'],'/workspace.html?section=overview')

    def test_navigation_never_infers_deployment_from_framework(self):
        with patch.dict(os.environ,{},clear=True):
            runtime=workspace.navigation(ROOT,'admin','owner')['footer']['runtime']
        self.assertIsNone(runtime['version'])
        self.assertIsNone(runtime['deployed_at'])
        self.assertEqual(runtime['status'],'unknown')

    def test_search_customer_never_reads_backend_or_private_materials(self):
        with patch.object(workspace,'_companies',return_value=[{'company_id':'test','name':'Test Company','profile':'public description'}]), patch.object(workspace,'_industry',return_value={'rows':[]}):
            rows=workspace.search(ROOT,'customer','customer-one',{'q':'Test','scope':'delivery'})['rows']
        self.assertEqual(rows[0]['kind'],'企业')
        self.assertTrue(all(r['area']=='delivery' for r in rows))
        for role,scope in [('reader','delivery'),('customer','backstage'),('customer','all'),('intern','all')]:
            with self.assertRaises(PermissionError):workspace.search(ROOT,role,'user',{'q':'x','scope':scope})

    def test_product_search_uses_current_run_and_formal_ownership_boundary(self):
        from inresearch.workflow import product_catalog
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'catalog.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE runs (id TEXT, generated TEXT)')
                db.execute('CREATE TABLE products (run_id TEXT, payload TEXT)')
                db.execute("INSERT INTO runs VALUES ('current','2026-10-13')")
                for item in [
                    {'id':'ok','name':'Test Model','company_id':'supermicro','kind':'named_product','private_sentinel':'DO_NOT_PUBLISH'},
                    {'id':'support','name':'Test Support','company_id':'supermicro','source_url':'https://www.supermicro.com/en/products/storage/pci-e/example'},
                    {'id':'other','name':'Test Foreign','company_id':'nvidia'},
                    {'id':'literal','name':'Test% Literal','company_id':'supermicro'}]:
                    db.execute('INSERT INTO products VALUES (?,?)',('current',json.dumps(item)))
            with patch.object(product_catalog,'database',side_effect=lambda root,cid:path if cid=='supermicro' else Path(folder)/'absent'),patch.object(workspace,'_companies',return_value=[]),patch.object(workspace,'_industry',return_value={'rows':[]}):
                result=workspace.search(ROOT,'customer','user',{'q':'Test','scope':'delivery'})
                self.assertEqual({row['title'] for row in result['rows']},{'Test Model','Test% Literal'})
                self.assertNotIn('DO_NOT_PUBLISH',json.dumps(result))
                literal=workspace.search(ROOT,'customer','user',{'q':'Test%','scope':'delivery'})
                self.assertEqual([row['title'] for row in literal['rows']],['Test% Literal'])

    def test_product_search_counts_all_matches_and_bounds_only_the_returned_page(self):
        from inresearch.workflow import product_catalog
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'catalog.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE runs (id TEXT, generated TEXT)')
                db.execute('CREATE TABLE products (run_id TEXT, payload TEXT)')
                db.execute("INSERT INTO runs VALUES ('current','2026-10-13')")
                for index in range(110):
                    db.execute('INSERT INTO products VALUES (?,?)',('current',json.dumps({'id':str(index),'name':'UniqueSearchFixture '+str(index),'company_id':'supermicro','kind':'named_product'})))
            with patch.object(product_catalog,'database',side_effect=lambda root,cid:path if cid=='supermicro' else Path(folder)/'absent'),patch.object(workspace,'_companies',return_value=[]),patch.object(workspace,'_industry',return_value={'rows':[]}):
                data=workspace.search(ROOT,'customer','user',{'q':'UniqueSearchFixture','scope':'delivery'})
            self.assertEqual(data['total'],110)
            self.assertEqual(len(data['rows']),100)
            self.assertTrue(data['truncated'])

    def test_feedback_is_private_durable_and_does_not_modify_research(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{},clear=True):
            root=Path(folder);(root/'framework').mkdir()
            (root/'framework/storage_contract.json').write_text((ROOT/'framework/storage_contract.json').read_text())
            result=workspace.feedback(root,'customer','customer-one',{'title':'字段问题','description':'来源日期需要核对','context':'/project.html?site=test'})
            self.assertTrue(result['ok'])
            path=root/'data/raw/site-feedback/requests.jsonl'
            record=json.loads(path.read_text())
            self.assertEqual(record['actor'],'customer-one')
            self.assertEqual(record['status'],'received')
            self.assertFalse((root/'data/projects.json').exists())
            with self.assertRaises(ValueError):workspace.feedback(root,'customer','customer-one',{'title':'x','description':'y','context':'//evil.test/'})

    def test_industry_headlines_have_real_source_time_and_do_not_become_adopted_research(self):
        from inresearch.knowledge import registry
        news={'feed':{'status':'success','items':[
            {'title_zh':'公开报道','url':'https://news.example/story','published_at':None,'domain':'news.example','private_future':'NEVER_EXPORT'},
            {'title_zh':'错误链接','url':'javascript:alert(1)'},
            {'title_zh':'带凭据链接','url':'https://secret:password@news.example/story'}]}}
        with patch.object(registry,'cached_news',return_value=news),patch.object(workspace,'_industry',return_value={'research_updates':{'changes':[]}}):
            data=workspace.view(ROOT,'customer','user',{'section':'industry','view':'updates'})
        rows=data['blocks'][0]['rows'];self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['href'],'https://news.example/story')
        self.assertIsNone(rows[0]['time'])
        self.assertNotIn('NEVER_EXPORT',json.dumps(data))
        self.assertIn('不代表本站已核实',data['blocks'][0]['note'])

    def test_snapshot_report_library_does_not_promote_legacy(self):
        data=workspace.view(ROOT,'customer','customer-one',{'section':'reports'})
        rows=data['blocks'][0]['rows']
        self.assertNotIn('legacy',{r['id'] for r in rows})
        internal=workspace.view(ROOT,'member','team-one',{'section':'production','view':'adoption'})
        self.assertTrue(any(link['href']=='/report.html?legacy=1' for link in internal['links']))
        self.assertEqual(workspace.resolve(ROOT,'/report.html?legacy=1')['area'],'backstage')
        self.assertEqual(len([r for r in rows if r['id']=='data-centers-2026']),1)
        with self.assertRaises(ValueError):workspace.view(ROOT,'customer','customer-one',{'section':['reports','overview']})

if __name__=='__main__':unittest.main()
