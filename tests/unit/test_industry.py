"""Industry capacity boundaries, public drilldowns and durable news opportunities."""
import json
import tempfile
import threading
import unittest
import http.client
from pathlib import Path
from unittest.mock import patch
from inresearch.paths import project_root
from inresearch.knowledge import industry
from inresearch.workflow import project_pipeline as pipeline
from inresearch.interfaces import http as serve, auth

ROOT = project_root()


def native_capacity_observation(ident, **fields):
    """Test-only complete v2 review/support shape for native quantity fixtures."""
    reviewed = '2026-10-11T00:00:00Z'
    return dict(id=ident, effective_at='2026-10-01', recorded_at=reviewed, reviewed_at=reviewed,
                schema_version=2, scope='whole_site', kind='disclosed', basis='publisher phases', fields=fields,
                sources=[{'url': 'https://example.org/phases'}], source_versions=[{
                    'source_sha256': 'a'*64, 'published_at': None, 'first_received_at': None,
                    'published_at_precision': 'unknown', 'first_received_at_precision': 'unknown',
                    'published_at_provenance': 'test-only unknown publication date',
                    'first_received_at_provenance': 'test-only unknown receipt'}],
                adoption={'review_id': ident, 'source_kind': 'reader_report', 'source_id': 'fixture-report',
                    'source_version': 'b'*64, 'document_refs': [{'sha256': 'a'*64}], 'target_ids': ['fixture-demand'],
                    'assertions': [{'source_sha256': 'a'*64, 'quote': 'fixture native capacity', 'locator': 'fixture:1'}],
                    'review': {'by': 'fixture reviewer', 'at': reviewed, 'tier': 'A', 'score': 8,
                        'authority': 'delegated_reviewer', 'decision': 'adopted', 'rationale': 'test-only source review',
                        'delegation': {'delegate': 'fixture reviewer', 'granted_by': 'fixture owner',
                            'granted_at': '2026-10-11', 'reference': 'test-only delegation',
                            'scope': 'new_or_supplemental_research'}}})


class IndustryTests(unittest.TestCase):
    def test_recently_added_history_is_visible_without_changing_effective_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'data').mkdir()
            for name in ('companies', 'prices'):
                (root/'data'/f'{name}.json').write_text('{"records": []}')
            old = native_capacity_observation('recent-event', notes='recent event')
            old['recorded_at'] = '2026-10-11T20:00:00+08:00'
            recovered = native_capacity_observation('recovered-history', notes='historical report')
            recovered.update(effective_at='2012-10-29', recorded_at='2026-10-11T13:00:00Z')
            row = {'site_id': 'campus', 'name': 'Campus', 'country': 'US', 'region': 'north-america',
                   'status': 'L8', 'observations': [old, recovered]}
            (root/'data/projects.json').write_text(json.dumps({'records': [row]}))
            changes = industry.snapshot(root, {'overview': '1'})['tracking']['changes']
            self.assertEqual([r['id'] for r in changes], ['recovered-history', 'recent-event'])
            self.assertEqual(changes[0]['effective_at'], '2012-10-29')
            self.assertEqual(industry.project(row)['notes'], 'recent event')

    def test_phases_override_headline_and_facility_never_enters_total(self):
        p = industry.project({'site_id': 'site-one', 'status': 'L8', 'capacity_it_mw': 300,
                              'capacity_facility_mw': 900, 'capacity_it_mw_by_status': {'L8': 100, 'L6': 200}})
        self.assertEqual(p['total_mw'], 300)
        self.assertEqual(p['capacity'], {'operating': 100, 'construction': 200, 'planning': 0})

    def test_unknown_and_portfolio_are_not_zero_sized_sites(self):
        unknown = industry.project({'site_id': 'unknown', 'status': 'L2', 'capacity_facility_mw': 900})
        portfolio = industry.project({'site_id': 'portfolio-all', 'status': 'L8', 'capacity_it_mw': 800})
        self.assertFalse(unknown['capacity_known'])
        self.assertEqual(industry.totals([unknown, portfolio]), {'operating': 0, 'construction': 0, 'planning': 0,
                         'inactive_sites': 0, 'estimated': {'operating': 0, 'construction': 0, 'planning': 0}, 'estimated_sites': 0, 'sites': 1, 'unknown': 1, 'ranged_sites': 0, 'unlocated': 1, 'portfolios_excluded': 1})
        for invalid in (float('nan'), float('inf'), -10, True):
            self.assertFalse(industry.project({'site_id': 'x', 'status': 'L6', 'capacity_it_mw': invalid})['capacity_known'])

    def test_native_ranges_keep_exact_phases_separate_from_totals_and_unknown(self):
        ranged = {'value_range': [1, 2], 'unit': 'GW', 'assumptions': ['design interval, not measured load']}
        row = {'site_id': 'range-site', 'status': 'L6', 'capacity_it_mw': 9999,
               'observations': [native_capacity_observation('phases', capacity_it_mw=None,
                    capacity_it_mw_by_status={'L8': {'value': 0.1, 'unit': 'GW'}, 'L6': ranged}, capacity_assessment=None)]}
        result = industry.project(row)
        self.assertEqual(result['capacity'], {'operating': 100, 'construction': 0, 'planning': 0})
        self.assertEqual(result['total_mw'], 100)
        self.assertTrue(result['capacity_ranged'])
        self.assertEqual(result['capacity_ranges'][0]['value_range'], [1, 2])
        self.assertEqual(result['capacity_ranges'][0]['stage'], 'construction')
        self.assertEqual(result['quantity_fields']['capacity_it_mw_by_status']['L6'], ranged)
        count = industry.totals([result])
        self.assertEqual((count['operating'], count['construction'], count['ranged_sites'], count['unknown']), (100, 0, 1, 0))
        self.assertEqual(row['capacity_it_mw'], 9999)
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); (home/'data').mkdir()
            for filename, records in [('projects', [row]), ('companies', []), ('prices', [])]:
                (home/'data'/f'{filename}.json').write_text(json.dumps({'records': records}))
            self.assertEqual(len(industry.snapshot(home, {'stage': 'construction'})['rows']), 1)
            self.assertEqual(industry.snapshot(home, {'stage': 'unknown'})['rows'], [])
            overview = industry.snapshot(home, {'overview': '1'})
            self.assertEqual(overview['rows'][0]['capacity_ranges'], result['capacity_ranges'])
            self.assertEqual(overview['totals']['ranged_sites'], 1)

    def test_range_only_capacity_is_disclosed_without_a_representative_scalar(self):
        ranged = {'value_range': [100, 200], 'unit': 'MW', 'assumptions': ['estimated envelope']}
        observation = native_capacity_observation('range', capacity_it_mw=ranged,
                                                  capacity_it_mw_by_status={}, capacity_assessment=None)
        observation.update(kind='estimated', basis='cooling estimate', assumptions=['estimated envelope'])
        row = {'site_id': 'range-only', 'status': 'L6', 'observations': [observation]}
        result = industry.project(row)
        self.assertFalse(result['capacity_known'])
        self.assertTrue(result['capacity_ranged'])
        self.assertEqual(result['capacity_ranges'][0]['value_range'], [100, 200])
        count = industry.totals([result])
        self.assertEqual((count['unknown'], count['ranged_sites'], count['construction']), (0, 1, 0))

    def test_company_stage_drilldown_reconciles_and_does_not_double_count(self):
        for company in ('microsoft', 'meta'):
            view = industry.snapshot(ROOT, {'c': company})
            self.assertGreater(len(view['rows']), 0)
            for stage in industry.STAGES:
                drill = industry.snapshot(ROOT, {'c': company, 'stage': stage})
                self.assertEqual(view['totals'][stage], industry.totals(drill['rows'])[stage])
                self.assertTrue(all(company in p['developer']+p['tenant'] for p in drill['rows']))
            self.assertEqual(len({p['site_id'] for p in view['rows']}), len(view['rows']))

    def test_reviewed_duplicate_preserves_evidence_without_double_counting(self):
        view = industry.snapshot(ROOT)
        self.assertEqual(view['totals']['planning'], 21324)
        self.assertEqual(view['totals']['sites'], 123)
        self.assertNotIn('us-tx-shackelford-frontier', [p['site_id'] for p in view['rows']])
        main = industry.snapshot(ROOT, {'site': 'us-tx-shackelford'})['detail']
        old = industry.snapshot(ROOT, {'site': 'us-tx-shackelford-frontier'})['detail']
        self.assertEqual(old['duplicate_of'], main['site_id'])
        self.assertEqual(old['total_mw'], 1400)
        self.assertEqual(main['capacity']['planning'], 1400)
        self.assertIn('oracle', main['tenant'])
        self.assertTrue(main['duplicate_records'])
        oracle = industry.snapshot(ROOT, {'c': 'oracle'})
        self.assertIn(main['site_id'], [p['site_id'] for p in oracle['rows']])

    def test_capacity_audit_is_global_and_discloses_unknown_scope(self):
        audit = industry.snapshot(ROOT)['capacity_audit']
        self.assertEqual(audit, industry.snapshot(ROOT, {'c': 'meta'})['capacity_audit'])
        self.assertEqual((audit['known'], audit['unknown'], audit['unlocated']), (38, 85, 20))
        self.assertEqual((audit['duplicates_excluded'], audit['portfolios_excluded']), (1, 2))
        self.assertEqual((audit['oldest_verified'], audit['latest_verified']), ('2026-07-23', '2026-10-07'))
        self.assertIn('不能用 95 GW', audit['comparability'])
        self.assertIn('推导余额', audit['unresolved'])
        self.assertIn('集群', audit['coverage'])
        self.assertNotIn('gap_gw', audit)

    def test_reviewed_power_designs_do_not_count_as_operating_it(self):
        for site_id in ('us-nv-tahoe-reno', 'us-va-dulles-digital'):
            detail = industry.snapshot(ROOT, {'site': site_id})['detail']
            self.assertFalse(detail['capacity_known'], site_id)
            self.assertEqual(detail['capacity'], {'operating': 0, 'construction': 0, 'planning': 0})
        audit = json.loads((ROOT/'docs/reviews/2026-10-11/datacenter-research/project-capacity-corrections.json').read_text())
        self.assertEqual([r['previous_record']['capacity_it_mw'] for r in audit['records']], [650, 1000])
        self.assertTrue(all(r['current_record']['capacity_it_mw'] is None for r in audit['records']))
        source_dates = {s['url']: s['date'] for r in audit['records'] for s in r['current_record']['sources']}
        self.assertEqual(source_dates['https://www.prnewswire.com/news-releases/switch-tahoe-reno-now-open-largest-most-advanced-data-center-campus-in-the-world-300407648.html'], '2017-02-15')

    def test_invalid_filters_and_unknown_objects_fail_explicitly(self):
        for args in ({'stage': 'fake'}, {'scope': 'all-ai'}, {'region': 'unknown'}, {'private': 'yes'}):
            with self.assertRaises(ValueError): industry.snapshot(ROOT, args)
        for args in ({'c': 'nobody'}, {'site': 'not-a-site'}):
            with self.assertRaises(LookupError): industry.snapshot(ROOT, args)

    def test_market_forecasts_and_private_source_paths_are_identified(self):
        market = industry.market(ROOT)
        self.assertTrue(market['series'])
        self.assertTrue(next(r for r in market['series'] if r['year']=='2030')['forecast'])
        self.assertFalse(next(r for r in market['series'] if r['year']=='2025')['forecast'])
        self.assertNotIn('docs/library', json.dumps(market))
        self.assertFalse(market['revenue_available'])

    def test_global_benchmarks_keep_date_basis_and_do_not_replace_sample_totals(self):
        view = industry.snapshot(ROOT)
        current, forecast = view['benchmarks']
        self.assertEqual((current['value'], current['as_of'], current['caliber']['basis']), (95, '2025', '券商测算'))
        self.assertEqual(forecast['caliber']['basis'], '预测')
        self.assertNotEqual(view['totals']['operating']/1000, current['value'])
        self.assertIn('第 32 页', current['locator'])
        self.assertNotIn('local_file', json.dumps(view['benchmarks']))

    def test_public_api_and_details_work_without_exposing_raw_research(self):
        with patch.object(serve, 'AUTH_ON', True), patch.object(auth, 'session_user', return_value=None):
            server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                for path, status in [('/api/industry?c=microsoft', 200), ('/api/industry?site=us-tx-abilene', 200),
                                     ('/industry.html?c=meta', 200), ('/project.html?site=us-tx-abilene', 200),
                                     ('/api/industry?stage=fake', 400), ('/api/industry?c=nobody', 404),
                                     ('/api/industry?c=meta&c=microsoft', 400), ('/data/projects.json', 302)]:
                    con = http.client.HTTPConnection(*server.server_address, timeout=4)
                    con.request('GET', path); response = con.getresponse(); response.read(); con.close()
                    self.assertEqual(response.status, status, path)
            finally:
                server.shutdown(); server.server_close(); thread.join()


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.article = {'id': 1, 'cluster_id': 10, 'event_type': 'project_milestone', 'title_zh': '微软宣布项目',
                        'published_at': 100, 'url': 'https://example.com/project', 'object_ids': ['actor:microsoft']}

    def test_news_expiry_keeps_lead_and_repeat_import_is_idempotent(self):
        pipeline.receive(self.home, [self.article], '2026-10-01')
        pipeline.receive(self.home, [self.article], '2026-10-02')
        pipeline.receive(self.home, [], '2026-11-01')
        rows = pipeline.projection(self.home)['records']
        self.assertEqual(len(rows), 1); self.assertEqual(len(rows[0]['events']), 1)
        self.assertEqual(rows[0]['state'], 'lead'); self.assertIsNone(rows[0]['site_id'])
        self.assertNotIn('capacity', rows[0])

    def test_cluster_merge_review_and_withdrawal_preserve_history(self):
        pipeline.receive(self.home, [self.article, {**self.article, 'id': 2, 'url': 'https://example.com/second'}], '2026-10-01')
        row = pipeline.projection(self.home)['records'][0]
        pipeline.review(self.home, row['id'], 'cancelled', '取消公告待核实')
        pipeline.receive(self.home, [self.article], '2026-10-02', withdrawn=[2])
        current = pipeline.projection(self.home)['records'][0]
        self.assertEqual(current['state'], 'cancelled'); self.assertEqual(len(current['events']), 1)
        pipeline.receive(self.home, [], '2026-10-03', withdrawn=[1])
        self.assertEqual(pipeline.projection(self.home)['records'], [])
        self.assertEqual(len(pipeline.read(self.home)['records'][row['id']]['events']), 2)

    def test_non_project_news_is_not_a_project_and_link_requires_known_site(self):
        pipeline.receive(self.home, [{**self.article, 'event_type': 'product_price_change'}], '2026-10-01')
        self.assertEqual(pipeline.projection(self.home)['records'], [])
        pipeline.receive(self.home, [self.article], '2026-10-01')
        ident = pipeline.projection(self.home)['records'][0]['id']
        with self.assertRaises(ValueError): pipeline.review(self.home, ident, 'linked', '关联', 'fake', ROOT)
        pipeline.review(self.home, ident, 'linked', '按原文匹配', 'us-tx-abilene', ROOT)
        self.assertEqual(pipeline.projection(self.home)['records'][0]['site_id'], 'us-tx-abilene')

    def test_low_confidence_headline_enters_without_editorial_pick_or_project_tag(self):
        article = {**self.article, 'event_type': 'other', 'editorial_pick': False,
                   'title_zh': '消息称微软计划建设 200 MW 数据中心'}
        pipeline.receive(self.home, [article], '2026-10-02')
        row = pipeline.projection(self.home)['records'][0]
        self.assertEqual(row['reported_stage'], 'reported')
        self.assertEqual(row['reported_capacity'], '200 MW')
        self.assertIsNone(row['site_id'])
        chinese = pipeline.signals({**article, 'title_zh': '拟建设1,200MW数据中心，储能2MWh'}, [])
        self.assertEqual(chinese['reported_capacity'], '1,200MW')

    def test_named_site_updates_across_clusters_and_withdrawal_restores_previous_signal(self):
        site = next(p for p in json.loads((ROOT/'data/projects.json').read_text())['records'] if p['site_id']=='us-wy-cheyenne-msft')
        first = {**self.article, 'title_zh': site['name']+' 宣布建设 300 MW 数据中心'}
        second = {**first, 'id': 2, 'cluster_id': 11, 'published_at': 200, 'title_zh': site['name']+' 数据中心暂停建设'}
        pipeline.receive(self.home, [first, second], '2026-10-02')
        rows = pipeline.projection(self.home)['records']
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['site_id'], rows[0]['state']), (site['site_id'], 'paused'))
        self.assertEqual(rows[0]['match_method'], 'name_and_actor')
        pipeline.receive(self.home, [first], '2026-10-03')  # old article cannot undo newer pause
        self.assertEqual(pipeline.projection(self.home)['records'][0]['state'], 'paused')
        pipeline.receive(self.home, [], '2026-10-04', withdrawn=[2])
        row = pipeline.projection(self.home)['records'][0]
        self.assertEqual((row['state'], row['reported_stage']), ('lead', 'announced'))
        pipeline.review(self.home, row['id'], 'cancelled', '人工复核取消')
        pipeline.receive(self.home, [first], '2026-10-05')
        self.assertEqual(pipeline.projection(self.home)['records'][0]['state'], 'cancelled')

    def test_name_match_requires_actor_and_does_not_guess_ambiguous_site(self):
        sites = [{'site_id': 'a', 'name': 'Alpha Campus', 'developer': ['microsoft'], 'tenant': []}]
        item = {**self.article, 'title_zh': 'Alpha Campus 数据中心计划扩建', 'object_ids': ['actor:meta']}
        self.assertIsNone(pipeline.signals(item, sites)['matched_site_id'])
        item['object_ids'] = ['actor:microsoft']
        self.assertEqual(pipeline.signals(item, sites)['matched_site_id'], 'a')
        self.assertIsNone(pipeline.signals(item, sites+[dict(sites[0], site_id='b')])['matched_site_id'])



class PipelineIntegrationTests(unittest.TestCase):
    def test_verified_import_publishes_durable_leads_but_file_import_does_not(self):
        from inresearch.adapters import acquisition, news_sync
        from inresearch.knowledge import registry
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); collector = acquisition.Collector(root)
            self.addCleanup(collector.close)
            row = {'id': 21, 'guid': 'inews:21', 'title': 'Microsoft data center planned',
                   'title_zh': '微软宣布新园区', 'url': 'https://example.com/new', 'published_at': 1700000000000,
                   'topics': ['datacenter'], 'event_type': 'project_milestone', 'editorial_pick': True,
                   'object_ids': ['actor:microsoft']}
            payload = {'schema': 'inews-research-signals-v1', 'articles': [row], 'exported_at': '2026-10-02T00:00:00Z'}
            acquisition.import_news(collector, payload)
            self.assertEqual(pipeline.projection(collector.home)['records'], [])
            acquisition.import_news(collector, news_sync.verified([row], {'since': 1, 'until': 2}))
            acquisition.import_news(collector, news_sync.verified([], {'since': 3, 'until': 4}))
            summary = acquisition.summary(root)
            self.assertEqual(len(summary['project_pipeline']['records']), 1)
            self.assertEqual(summary['news_feed']['items'], [])
            summary['project_pipeline']['records'][0]['private_path'] = '/private/secret'
            with patch('inresearch.delivery.runtime_summary.load', return_value={'reader': {'acquisition': summary}}):
                public = registry.build_news(ROOT)
            self.assertEqual(public['pipeline']['records'][0]['company_ids'], ['microsoft'])
            self.assertNotIn('/private/secret', json.dumps(public))
            self.assertEqual(public['pipeline']['records'][0]['state'], 'lead')
