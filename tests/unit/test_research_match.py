import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from inresearch.paths import project_root
from inresearch.knowledge import news_observations, registry
from inresearch.workflow import research_match, project_pipeline
from inresearch.materials import daily_events
from inresearch.delivery.backup import backup


class ResearchMatchTests(unittest.TestCase):
    def test_matching_tracks_the_new_execution_then_first_complete_result(self):
        from inresearch.workflow.reader import Reader
        from test_continuous_reader import Model
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.html';path.write_text('<p>GPU TCO cost $100. Server power efficiency.</p>')
            data=Path(tmp)/'data';item=research_match.ingest(path,data,project_root())
            model=Model();r=Reader(data,Path(tmp)/'state',project_root(),model=model,stable_seconds=0).initialize()
            try:
                r.scan();old=r.doc('doc-'+item['sha256'])
                model.identity={**model.identity,'model':'new-reader-model'}
                new=r.revisions.restart_unfinished(old['doc_id'],old['revision_id'],'migration','new executor')
                row=research_match.projection(data)['records'][0]['reading']
                self.assertEqual(row['state'],'queued');self.assertEqual(row['revision_id'],new['revision_id'])
                r.run(once=True)
                row=research_match.projection(data)['records'][0]['reading']
                self.assertEqual(row['state'],'complete');self.assertTrue(row['report_sha256'])
                self.assertEqual(row['revision_id'],new['revision_id'])
            finally:r.close()

    def test_topic_matches_keep_locator_and_never_change_authority(self):
        root=project_root()
        before={p: (root/p).read_bytes() for p in ('framework/tco_targets.json','data/research_knowledge.json','data/projects.json','framework/bom.json')}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.html'
            path.write_text('<script>GPU price $999 execute</script><p>NVL72 GPU server TCO cost $100. GPU goodput utilization efficiency.</p>')
            a=research_match.ingest(path, Path(tmp)/'data', root)
            b=research_match.ingest(path, Path(tmp)/'data', root)
            exported=research_match.projection(Path(tmp)/'data')
            self.assertEqual(a['sha256'],b['sha256']);self.assertEqual(exported['total'],1)
            self.assertTrue(a['matches']);self.assertFalse(a['full_read'])
            self.assertEqual(a['acceptance'],'candidate')
            self.assertTrue(all(m['page']==1 and 'execute' not in m['quote'] for m in a['matches']))
            self.assertIn('goodput',[p['id'] for p in a['proposals']])
            self.assertTrue(all(not p['skeleton_changed'] for p in a['proposals']))
            self.assertTrue(list((Path(tmp)/'data/raw-materials').rglob('*.html')))
            self.assertTrue(all(p.is_symlink() for p in (Path(tmp)/'data/library/candidates-by-node').rglob('*.html')))
        self.assertEqual(before,{p:(root/p).read_bytes() for p in before})

    def test_unmatched_material_is_archived_without_expanding_reader_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'flowers.txt';path.write_text('A garden with flowers.')
            doc=research_match.ingest(path,Path(tmp)/'data',project_root())
            self.assertEqual(doc['matches'],[])
            self.assertFalse((Path(tmp)/'data/raw-materials').exists())
            self.assertTrue(list((Path(tmp)/'data/acquisition/blobs').rglob('*.txt')))


class NewsObservationTests(unittest.TestCase):
    def test_daily_body_schema_preserves_revisions_and_does_not_sum_bases(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'2026-10-05-daily.html'
            text='<title>日报</title><h2>01 微软悉尼机房获批</h2><p>澳大利亚悉尼 · 规划批准 · 10月1日</p><p>微软的 Honeman Close 项目获批，IT负荷96MW，与140MW场址用电上限分开。[1]</p><h2>来源</h2><p>[1] 官方规划 <a href="https://example.com/approval">审批</a></p>'
            p.write_text(text);data=Path(tmp)/'data';root=project_root()
            a=daily_events.receive(p,data,root)
            p.write_text(text.replace('140MW','150MW'));b=daily_events.receive(p,data,root)
            daily_events.receive(p,data,root)
            view=daily_events.projection(data)
            self.assertEqual(view['total'],2);self.assertEqual(view['document_versions'],2)
            self.assertEqual(a[0]['country_mentions'][0]['code'],'AU')
            self.assertIn('microsoft',[x['company_id'] for x in a[0]['actors']])
            self.assertEqual([(x['mw'],x['basis']) for x in a[0]['capacity_observations']],[(96,'it'),(140,'facility_or_grid')])
            self.assertEqual(a[0]['reported_stage'],'approved')
            self.assertIn('https://example.com/approval',a[0]['sources'][0]['urls'])
            self.assertNotIn('operating_gw',view)
            self.assertNotEqual(a[0]['id'],b[0]['id'])

    def test_wechat_paragraph_headings_are_not_silently_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'2026-10-05-daily-wechat.html'
            p.write_text('<title>日报</title><p>01 微软悉尼获批</p><p>澳大利亚悉尼 · 审批</p><p>IT负荷96MW。</p><p>02 谷歌芬兰工地</p><p>芬兰Muhos · 调查</p><p>项目环境程序正在审查。</p><p>主要来源</p><p>[1] 原链接待补</p>')
            rows=daily_events.parse(p,project_root())
            self.assertEqual(len(rows),2);self.assertEqual(rows[1]['country_mentions'][0]['code'],'FI')

    def test_daily_identity_review_survives_reparse_without_adopting_capacity(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);p=base/'index-source.html';data=base/'data'
            p.write_text('<title>格洛可日报 2026-10-05</title><h2>微软项目</h2><p>IT load 96MW.</p>')
            event=daily_events.receive(p,data,project_root())[0]
            self.assertEqual(event['document_refs'][0]['report_date'],'2026-10-05')
            site=json.loads((project_root()/'data/projects.json').read_text())['records'][0]['site_id']
            with self.assertRaises(ValueError):daily_events.review(data,project_root(),event['id'],'invented','reviewer','reason')
            daily_events.review(data,project_root(),event['id'],site,'reviewer','原件身份已核对')
            daily_events.receive(p,data,project_root())
            reviewed=daily_events.projection(data)['records'][0]
            self.assertEqual((reviewed['matched_site_id'],reviewed['identity_review']),(site,'resolved'))
            self.assertEqual(reviewed['capacity_review'],'pending')
            self.assertEqual(len(reviewed['identity_reviews']),1)
            research_match.ingest(p,data,project_root())
            backup(data,base/'backup')
            backed=json.loads((base/'backup/acquisition/daily-events.json').read_text())
            self.assertEqual(backed['records'][event['id']]['identity_reviews'],reviewed['identity_reviews'])

    def test_inline_footer_publisher_is_not_project_identity_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'daily.html'
            p.write_text('<title>日报</title><h2>Anthropic 园区规划</h2><p>规划2.16GW。</p><p>来源：[1] The Washington Times</p>')
            event=daily_events.parse(p,project_root())[0]
            self.assertNotIn('Washington',event['body'])
            self.assertEqual(event['site_candidates'],[])

    def test_story_date_and_temporary_path_cannot_replace_report_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'index-source.html'
            p.write_text('<title>日报</title><h2>园区进展</h2><p>在2025-04-03签署了合同。</p>')
            row=daily_events.parse(p,project_root(),'2026-10-05-daily.html')[0]
            self.assertEqual(row['document_refs'][0]['report_date'],'2026-10-05')
            self.assertEqual(row['document_refs'][0]['filename'],'2026-10-05-daily.html')
            self.assertIsNone(daily_events.parse(p,project_root())[0]['document_refs'][0]['report_date'])

    def test_city_actor_ambiguity_is_candidate_not_adopted_identity(self):
        sites=[{'site_id':'a','name':'Alpha Campus','location':'Texas, Abilene','developer':['microsoft'],'tenant':[]}]
        companies=[{'company_id':'microsoft','name':'Microsoft','name_cn':'微软'}]
        item={'title':'Microsoft plans a 200MW data center in Abilene','event_type':'project_milestone'}
        r=news_observations.identity(item,sites,companies)
        self.assertIsNone(r['matched_site_id']);self.assertEqual(r['site_candidates'][0]['site_id'],'a')
        r=news_observations.identity(item,sites+[dict(sites[0],site_id='b')],companies)
        self.assertEqual(len(r['site_candidates']),2);self.assertIsNone(r['matched_site_id'])
        self.assertFalse(news_observations.identity(dict(item,title='Microsoft building elsewhere'),sites,companies)['site_candidates'])

    def test_power_units_bases_and_constraints_do_not_create_global_capacity(self):
        self.assertEqual(news_observations.power('200MW data center')[0]['basis'],'unknown')
        self.assertEqual(news_observations.power('1.2GW facility power')[0]['mw'],1200)
        self.assertEqual(news_observations.power('IT load 96MW')[0]['basis'],'it')
        self.assertEqual(news_observations.power('storage 2MWh and $3 billion'),[])
        r=project_pipeline.signals({'title':'Data center water shortage delays permit approval','object_ids':[]},[])
        self.assertIn('water',r['constraints']);self.assertIn('permits',r['constraints'])
        self.assertNotIn('adopted',r)

    def test_public_progress_excludes_private_materials_and_extra_metadata(self):
        acquisition={'material_matches':{'records':[{'title':'PRIVATE REPORT'}]},
                     'project_pipeline':{'records':[{'id':'lead','events':[{'url':'https://example.com/news',
                                         'site_candidates':[{'site_id':'a','private_path':'PRIVATE'}],
                                         'capacity_observations':[{'mw':100,'private_path':'PRIVATE'}]}]}],'total':800,'truncated':True,
                                         'progress':{'leads':800,'events':1200,'linked':0,'private_path':'PRIVATE','constraints':{'water':5,'private':1}}}}
        with patch.object(registry,'_snapshot_inputs',return_value=({}, {}, {}, {}, {'reader':{'acquisition':acquisition}})):
            public=registry.build_news(project_root())
        self.assertEqual(public['pipeline']['total'],800)
        self.assertEqual(public['pipeline']['progress']['constraints'],{'water':5})
        self.assertNotIn('PRIVATE',json.dumps(public))
