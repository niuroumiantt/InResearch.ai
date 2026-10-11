"""Homepage observations, publication dates, public boundaries and cache invalidation."""
import gzip
import http.client
import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from inresearch.paths import project_root
from inresearch.knowledge import raw_atlas, industry, registry
from inresearch.interfaces import http as serve, auth

ROOT=project_root()


class HomepageRawAtlasTests(unittest.TestCase):
    def test_precompiled_aliases_preserve_unicode_and_word_boundary_matching(self):
        from inresearch.knowledge import news_observations
        aliases=['AWS','Meta','阿里云','数据中心','Café','Straße','über cloud','Ｆｉｎｌａｎｄ','A_B','!!!','']
        texts=['AWS announces a campus','drawstring and meta-data','metadata and metas',
               '中国阿里云数据中心','阿里 云','CAFE\u0301 campus','StraSSe campus',
               'an Über  Cloud campus','Finland data center','A_B campus','prefixA_Bsuffix','AWS公司',
               'ＡＷＳ campus','unrelated']
        for alias in aliases:
            compiled=raw_atlas._compile_term(alias)
            for text in texts:
                with self.subTest(alias=alias,text=text):
                    self.assertEqual(raw_atlas._contains_normalized(news_observations.normalized(text),compiled),
                                     news_observations.contains(text,alias))

    def test_source_ledger_is_visible_but_never_adopts_or_aggregates_capacity(self):
        value=raw_atlas.build(ROOT,None,[],now=datetime(2026,10,10,17,tzinfo=timezone.utc))
        rows=[r for r in value['records'] if r['origin']=='research_publication']
        self.assertEqual(len(rows),168)
        self.assertEqual(value['research_total'],168)
        self.assertEqual(value['daily']['research_published_records'],168)
        self.assertIsNone(value['daily']['published_events'])
        self.assertFalse(value['daily']['news_available'])
        self.assertIsNone(value['daily']['received_events'])
        self.assertEqual(sum(g['count'] for g in value['country_groups']),168)
        self.assertTrue(all(r['site_id'] is None and not r['capacity_adopted'] for r in rows))
        self.assertTrue(all(r['capacity_observations']==[] for r in rows))
        self.assertTrue(all(r['published_at']==0 and r['published_date'] is None for r in rows))
        self.assertTrue(all(r['verification_status']=='raw' for r in rows))
        self.assertTrue(any('bytedance' in r['company_ids'] for r in rows))
        self.assertTrue(any('alibaba' in r['company_ids'] for r in rows))
        serialized=json.dumps(rows)
        for private in ('original_research_excerpt','section_markdown_sha256','original_document_sha256','reader_report_sha256'):
            self.assertNotIn(private,serialized)
        self.assertTrue(any('1.2 GW' in r['capacity_text'] for r in rows))

    def test_dates_use_beijing_publication_and_receipt_are_independent(self):
        stamp=int(datetime(2026,10,10,16,30,tzinfo=timezone.utc).timestamp()*1000)
        lead={'id':'one','first_seen':'2026-10-10T15:59:00Z','company_ids':['microsoft'],'events':[
            {'title':'微软数据中心新增 1 GW IT capacity，500 MW grid power','url':'https://example.org/news','published_at':stamp,'received_at':'2026-10-10T15:59:00Z'},
            {'title':'same news','url':'https://example.org/news','published_at':stamp,'received_at':'2026-10-10T15:59:00Z'}]}
        out=raw_atlas.build(ROOT,None,[lead],available=True,now=datetime(2026,10,10,17,tzinfo=timezone.utc))
        row=next(r for r in out['records'] if r['url']=='https://example.org/news')
        self.assertEqual(row['published_date'],'2026-10-11')
        self.assertEqual(row['received_date'],'2026-10-10')
        self.assertEqual(out['daily']['published_events'],1)
        self.assertEqual(out['daily']['received_events'],0)
        self.assertEqual(out['daily']['capacity_observations'],1)
        self.assertEqual(out['daily']['capacity_values'],2)
        self.assertFalse(row['capacity_adopted'])
        self.assertNotIn('total_mw',out)

    def test_country_centroid_is_schematic_and_unknown_city_is_not_geocoded(self):
        rows=[{'id':'one','country_mentions':[{'code':'FI','name':'芬兰','quote':'private'}],
               'location':'Salo','first_seen':'2026-10-11T01:00:00Z','events':[
                   {'title':'A new data center','url':'https://example.org/fi','published_at':0}]},
              {'id':'two','location':'unregistered city','events':[{'title':'Unknown campus','url':'https://example.org/unknown'}]}]
        value=raw_atlas.build(ROOT,None,rows)
        fi=next(r for r in value['records'] if r['url']=='https://example.org/fi')
        unknown=next(r for r in value['records'] if r['url']=='https://example.org/unknown')
        self.assertEqual(fi['location_precision'],'country');self.assertTrue(fi['coordinates'])
        self.assertEqual(fi['location'],'Salo');self.assertNotIn('quote',fi['country_mentions'][0])
        self.assertIsNone(unknown['coordinates']);self.assertEqual(unknown['location_precision'],'unknown')

    def test_daily_and_direct_news_share_true_publication_date_without_duplicate_event(self):
        stamp=int(datetime(2026,10,10,17,tzinfo=timezone.utc).timestamp()*1000)
        row={'id':'daily-one','origin':'daily_html','report_date':'2026-10-10',
             'first_seen':'2026-10-11T01:00:00Z','events':[{'title':'A campus','url':'https://example.org/daily'}]}
        feed={'items':[{'title_zh':'A campus','url':'https://example.org/daily','published_at':stamp}]}
        out=raw_atlas.build(ROOT,feed,[row],available=True,now=datetime(2026,10,10,18,tzinfo=timezone.utc))
        rows=[r for r in out['records'] if r['url']=='https://example.org/daily']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['published_date'],'2026-10-11')
        self.assertEqual(rows[0]['report_date'],'2026-10-10')
        self.assertEqual(out['daily']['published_events'],1)

    def test_unsafe_sources_nonfinite_power_and_private_quotes_are_excluded(self):
        out=raw_atlas.build(ROOT,None,[{'id':'x','events':[
            {'title':'Unsafe','url':'https://user:secret@example.org/a'},
            {'title':'Unsafe','url':'file:///private/a'},
            {'title':'Safe campus','url':'https://example.org/safe','capacity_observations':[
                {'mw':float('nan'),'quote':'secret'}, {'mw':True},
                {'mw':10,'basis':'it','quote':'private document paragraph','source_sha256':'private'}]}]}])
        row=next(r for r in out['records'] if r['url']=='https://example.org/safe')
        self.assertEqual(row['capacity_observations'],[{'quoted_value':'10 MW','mw':10,'basis':'it','acceptance':'candidate'}])
        self.assertEqual(len([r for r in out['records'] if r['origin']!='research_publication']),1)
        self.assertNotIn('private document paragraph',json.dumps(out))

    def test_overview_preserves_totals_and_marks_registration_without_claiming_full_review(self):
        full=industry.snapshot(ROOT);small=industry.snapshot(ROOT,{'overview':'1'})
        self.assertEqual(full['totals'],small['totals'])
        self.assertEqual([r['site_id'] for r in full['rows']],[r['site_id'] for r in small['rows']])
        self.assertTrue(all(not set(r)&{'history','notes','sources','phases','duplicate_records'} for r in small['rows']))
        self.assertTrue(all('profile' not in c for c in small['companies']))
        self.assertLess(len(json.dumps(small)),len(json.dumps(full))*.6)
        registered=next(r for r in small['rows'] if not r.get('adoption'))
        self.assertEqual(registered['verification_status'],'registered')
        self.assertTrue(registered['verified_date'])
        self.assertLess(len(json.dumps(small)),len(json.dumps(full)))
        with self.assertRaises(ValueError):industry.snapshot(ROOT,{'overview':'yes'})

    def test_overview_preserves_upstream_reference_it_and_separate_estimate_totals(self):
        full=industry.snapshot(ROOT);overview=industry.snapshot(ROOT,{'overview':'1'})
        row=next(r for r in overview['rows'] if r['site_id']=='us-tx-abilene')
        self.assertEqual(row['capacity'],{'operating':421,'construction':422,'planning':0})
        self.assertEqual(row['total_mw'],843)
        self.assertTrue(row['capacity_known']);self.assertTrue(row['capacity_estimated'])
        assessment=row['capacity_assessment']
        self.assertEqual(assessment['kind'],'legacy_estimate')
        self.assertEqual(assessment['status'],'provisional')
        self.assertIsNone(assessment['as_of']);self.assertTrue(assessment['missing_conditions'])
        self.assertNotIn('origin_record_sha256',assessment);self.assertNotIn('source_support',assessment)
        self.assertEqual(overview['totals']['estimated'],full['totals']['estimated'])
        self.assertEqual(overview['capacity_audit']['estimated'],full['capacity_audit']['estimated'])
        self.assertGreaterEqual(overview['totals']['estimated']['operating'],421)
        self.assertGreaterEqual(overview['totals']['estimated']['construction'],422)

    def test_homepage_news_does_not_require_formal_library_or_backflow_counts(self):
        from inresearch.workflow import news_marks
        runtime={'received_at':'2026-10-11T02:00:00Z','reader':{'status':'idle','acquisition':{
            'news_feed':{'status':'success','exported_at':'2026-10-11T02:00:00Z','items':[
                {'title_zh':'实时数据中心新闻','url':'https://example.org/independent-news','published_at':1791684000000}]}}}}
        with patch('inresearch.delivery.runtime_summary.load_acquisition',return_value=runtime), \
             patch('inresearch.delivery.runtime_summary.load',return_value=runtime), \
             patch.object(registry,'read_json',side_effect=ValueError('formal unreadable')), \
             patch.object(news_marks,'useful_by_target',side_effect=AssertionError('homepage backflow')), \
             patch.object(news_marks,'adopted_by_target',side_effect=AssertionError('homepage adoption backflow')):
            value=registry.build_news(ROOT,overview=True)
            self.assertEqual(value['feed']['items'][0]['url'],'https://example.org/independent-news')
            self.assertEqual(value['raw_atlas']['research_total'],168)
            self.assertNotIn('useful_by_target',value['feed'])
            self.assertNotIn('adopted_by_target',value['feed'])
            with self.assertRaisesRegex(ValueError,'formal unreadable'):
                registry.build_news(ROOT)

    def test_news_public_cache_versions_changes_and_never_reuses_a_failed_rebuild(self):
        registry._NEWS_PUBLIC_CACHE.clear()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir();p=root/'data/projects.json';p.write_text('one')
            with patch.object(registry,'build_news',return_value={'feed':{'items':[]}}) as build:
                first=registry.cached_news(root,overview=True);first['feed']['items'].append('mutation')
                self.assertEqual(registry.cached_news(root,overview=True)['feed']['items'],[])
                self.assertEqual(build.call_count,1)
                p.write_text('changed')
                registry.cached_news(root,overview=True);self.assertEqual(build.call_count,2)
                p.write_text('invalid')
                build.side_effect=ValueError('broken input')
                with self.assertRaises(ValueError):registry.cached_news(root,overview=True)
                with self.assertRaises(ValueError):registry.cached_news(root,overview=True)
        registry._NEWS_PUBLIC_CACHE.clear()

    def test_received_news_survives_curated_changes_but_not_changed_source_bytes(self):
        from inresearch.delivery import runtime_summary
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir();curated=root/'data/research_knowledge.json';curated.write_text('{}')
            source=root/'data/research_runtime.json';source.write_text('physically received original')
            snapshot={'graph_version':'old','questions_version':'old','generated':'2026-10-11T01:00:00Z',
                      'received_at':'2026-10-11T01:00:00Z','knowledge':{},'reader':{
                          'status':'idle','private_root':'/private','acquisition':{'news_feed':{'items':[{'title_zh':'hello'}]},
                          'research_private':'never public','project_pipeline':{'records':[]}}}}
            runtime_summary.write_control(source,snapshot,root=root)
            with patch.dict('os.environ',{'INRESEARCH_READER_SNAPSHOT':str(source)}):
                first=runtime_summary.load_acquisition(root)
                curated.write_text('{"a":"new adoption"}')
                second=runtime_summary.load_acquisition(root)
                self.assertEqual(first,second)
                self.assertNotIn('knowledge',second)
                self.assertNotIn('reading_deliveries',second)
                self.assertNotIn('private',json.dumps(second))
                source.write_text('changed original')
                unknown=runtime_summary.load_acquisition(root)
                self.assertEqual(unknown['reader']['status'],'awaiting_operational_projection')
                self.assertNotIn('acquisition',unknown['reader'])

    def test_homepage_reuses_unchanged_inputs_but_recomputes_freshness(self):
        registry._NEWS_PUBLIC_CACHE.clear()
        self.addCleanup(registry._NEWS_PUBLIC_CACHE.clear)
        clock=[datetime(2026,10,11,1,0,tzinfo=timezone.utc)]
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return clock[0]
        snapshot={'feed':{'items':[]},'reader':{'status':'idle',
                  'received_at':clock[0].isoformat(),'stale':False}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(registry,'datetime',Clock), \
             patch.object(registry,'build_news',return_value=snapshot) as build, \
             patch('time.monotonic',return_value=1) as monotonic:
            first=registry.cached_news(Path(tmp),overview=True)
            self.assertFalse(first['reader']['stale'])
            monotonic.return_value=1801
            clock[0]=datetime(2026,10,11,1,30,tzinfo=timezone.utc)
            later=registry.cached_news(Path(tmp),overview=True)
            self.assertTrue(later['reader']['stale'])
            self.assertEqual(build.call_count,1)
            self.assertFalse(first['reader']['stale'])
            (Path(tmp)/'data').mkdir()
            (Path(tmp)/'data/research_knowledge.json').write_text('{}')
            registry.cached_news(Path(tmp),overview=True)
            self.assertEqual(build.call_count,1)  # Full-library adoption is not a homepage input.
            clock[0]=datetime(2026,10,12,1,30,tzinfo=timezone.utc)
            registry.cached_news(Path(tmp),overview=True)
            self.assertEqual(build.call_count,2)  # Beijing day changes require new daily counts.

    def test_busy_full_news_consumer_does_not_block_homepage_and_home_builds_once(self):
        from concurrent.futures import ThreadPoolExecutor
        registry._NEWS_PUBLIC_CACHE.clear()
        self.addCleanup(registry._NEWS_PUBLIC_CACHE.clear)
        entered,release=threading.Event(),threading.Event()
        calls=[]
        def controlled_build(*args,overview=False,**kwargs):
            calls.append(overview)
            if not overview:
                entered.set()
                if not release.wait(5):raise AssertionError('full consumer did not resume')
            return {'feed':{'items':['home' if overview else 'full']}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(registry,'build_news',side_effect=controlled_build), \
             ThreadPoolExecutor(max_workers=4) as pool:
            full=pool.submit(registry.cached_news,Path(tmp),overview=False)
            try:
                self.assertTrue(entered.wait(3))
                homes=[pool.submit(registry.cached_news,Path(tmp),overview=True) for _ in range(2)]
                for home in homes:self.assertEqual(home.result(timeout=2)['feed']['items'],['home'])
                self.assertFalse(full.done())
                self.assertEqual(calls.count(True),1)
            finally:release.set()
            self.assertEqual(full.result()['feed']['items'],['full'])

    def test_prepared_control_recovery_invalidates_unknown_news_without_source_rewrite(self):
        from inresearch.delivery import runtime_summary
        registry._NEWS_PUBLIC_CACHE.clear()
        self.addCleanup(registry._NEWS_PUBLIC_CACHE.clear)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'research_runtime.json'
            snapshot={'graph_version':'old','questions_version':'old','generated':'2026-10-11T01:00:00Z',
                      'received_at':'2026-10-11T01:00:00Z','knowledge':{},'reader':{'status':'idle',
                      'acquisition':{'news_feed':{'status':'success','items':[{
                          'title_zh':'Recovered news','url':'https://example.org/recovered',
                          'published_at':1791673200000}]}}}}
            source.write_text(json.dumps(snapshot))
            runtime_summary.write_control(source,snapshot,root=ROOT)
            official=runtime_summary.control_path(source);completed=official.read_bytes();official.unlink()
            with patch.dict('os.environ',{'INRESEARCH_READER_SNAPSHOT':str(source)}):
                unavailable=registry.cached_news(ROOT,overview=True)
                self.assertIsNone(unavailable['feed'])
                identity=runtime_summary.signature(source)
                runtime_summary.prepared_control_path(source).write_bytes(completed)
                recovered=registry.cached_news(ROOT,overview=True)
                self.assertEqual(recovered['feed']['items'][0]['url'],'https://example.org/recovered')
                self.assertEqual(runtime_summary.signature(source),identity)
                self.assertTrue(recovered['raw_atlas']['daily']['news_available'])

    def test_article_records_remain_complete_when_news_exceeds_homepage_bound(self):
        leads=[{'id':'lead-'+str(i),'events':[{'title':'News '+str(i),'url':'https://example.org/'+str(i),
                'published_at':1791720000000+i}]} for i in range(500)]
        out=raw_atlas.build(ROOT,None,leads,available=True)
        self.assertEqual(len(out['records']),400)
        self.assertEqual(sum(r['origin']=='research_publication' for r in out['records']),168)
        self.assertTrue(out['news_truncated']);self.assertFalse(out['research_truncated'])
        self.assertFalse(out['counts_complete'])
        self.assertEqual(len({r['id'] for r in out['records']}),400)

    def test_input_cuts_are_declared_in_news_counts_completeness(self):
        event=lambda i:{'title':'Campus '+str(i),'url':'https://example.org/'+str(i),'published_at':1791720000000+i}
        for leads,feed in (([{'id':'many','events':[event(i) for i in range(101)]}],None),
                           ([{'id':'lead-'+str(i),'events':[]} for i in range(1001)],None),
                           ([],{'items':[event(i) for i in range(81)]})):
            with self.subTest(leads=len(leads),feed=bool(feed)):
                out=raw_atlas.build(ROOT,feed,leads,available=True)
                self.assertTrue(out['news_truncated'])
                self.assertTrue(out['truncated'])
                self.assertFalse(out['counts_complete'])
        # Several bound URLs for one daily section are one source event, not omitted news events.
        daily={'id':'daily-one','origin':'daily_html','events':[event(i) for i in range(101)]}
        out=raw_atlas.build(ROOT,None,[daily],available=True)
        self.assertEqual(out['news_total'],1)
        self.assertFalse(out['news_truncated'])

    def test_anonymous_overview_api_supports_gzip_and_keeps_private_files_protected(self):
        with patch.object(serve,'AUTH_ON',True),patch.object(auth,'session_user',return_value=None),patch.object(registry,'_reader_state',return_value={'status':'not_connected'}):
            server=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                for path in ('/api/industry?overview=1','/api/news?overview=1'):
                    conn=http.client.HTTPConnection(*server.server_address,timeout=10)
                    conn.request('GET',path,headers={'Accept-Encoding':'gzip'})
                    response=conn.getresponse();body=response.read();conn.close()
                    self.assertEqual(response.status,200,path);self.assertEqual(response.getheader('Content-Encoding'),'gzip')
                    value=json.loads(gzip.decompress(body))
                    if path.startswith('/api/news'):
                        self.assertEqual(value['raw_atlas']['research_total'],168)
                        self.assertNotIn('records',value['pipeline'])
                    else:self.assertTrue(value['overview'])
                conn=http.client.HTTPConnection(*server.server_address,timeout=4)
                conn.request('GET','/data/projects.json');response=conn.getresponse();response.read();conn.close()
                self.assertEqual(response.status,302)
            finally:server.shutdown();server.server_close();thread.join()
