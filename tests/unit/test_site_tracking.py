"""Site cadence plans are durable work, never collection or adoption receipts."""
import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from inresearch.workflow.research_review import ReviewStore
from inresearch.workflow.site_tracking import SiteTracking
from tests.unit import test_site_timeline as timeline_tests


class SiteTrackingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root, self.data = base/'root', base/'runtime'
        (self.root/'data').mkdir(parents=True)
        (self.root/'framework').mkdir()
        self.projects_path = self.root/'data/projects.json'
        self.targets_path = self.root/'framework/tco_targets.json'
        self.site = {
            'site_id': 'us-test-fixed-land', 'name': 'Test Physical Campus',
            'country': 'US', 'location': 'One fixed plot', 'status': 'L8',
            'verified_date': '2026-10-10', 'developer': ['developer'],
            'tenant': ['tenant'], 'owner': ['owner'], 'operator': ['operator'],
            'builder': ['builder'], 'power_status': 'energized', 'utility': ['utility'],
            'capacity_it_mw': 100, 'capacity_it_mw_by_status': {},
            'capacity_facility_mw': 120, 'capacity_assessment': None,
            'sources': [{'url': 'https://example.org/campus', 'grade': 'company'}],
        }
        self.write_projects([self.site])
        self.targets_path.write_text(json.dumps({'version': 'test', 'targets': [{
            'id': 'S.permits.news', 'origin': 'site_right', 'site_right_id': 'permits',
            'variable_class': 4, 'data_class': 'news', 'team': 'inews', 'host': 'aws',
            'team_state': 'connected', 'request': {
                'version': 2, 'node': 'site:permits', 'profile': 'event_lead',
                'question_ids': ['OBJ-permits-supply'], 'requirements': [],
            },
        }]}))
        self.store = ReviewStore(self.data)
        self.addCleanup(self.store.db.close)
        self.planner = SiteTracking(self.store.db, self.data)

    def write_projects(self, rows):
        self.projects_path.write_text(json.dumps({'records': rows}, sort_keys=True))

    def test_weekly_native_ranges_are_present_and_nullable_it_bundle_members_are_valid(self):
        quantity={'value_range':[80,120],'unit':'MW','basis':'explicit source range'}
        for fields in ({'capacity_it_mw':quantity,'capacity_it_mw_by_status':{},'capacity_assessment':None},
                       {'capacity_it_mw':None,'capacity_it_mw_by_status':{'L8':quantity,'L7':20},'capacity_assessment':None},
                       {'capacity_facility_mw':quantity}):
            with self.subTest(fields=fields):
                observation=timeline_tests.SiteTimelineTests().native(**copy.deepcopy(fields))
                site=dict(self.site,lifecycle='active',observations=[observation])
                self.write_projects([site])
                plans,issues=self.planner._plans(self.planner._snapshot(self.root,'weekly'),'weekly','2026-10-11')
                self.assertEqual(issues,[])
                self.assertEqual(plans,[])
        self.write_projects([dict(self.site,lifecycle='active')])
        plans,issues=self.planner._plans(self.planner._snapshot(self.root,'weekly'),'weekly','2026-10-11')
        self.assertEqual(plans,[])  # Scalar headline needs no phase/assessment placeholder.

    def test_weekly_legacy_unknown_capacity_and_other_missing_fields_stay_missing(self):
        site=dict(self.site,lifecycle='active',capacity_it_mw=None,capacity_it_mw_by_status={},
                  capacity_assessment=None,capacity_facility_mw=None,tenant=[])
        self.write_projects([site])
        plans,issues=self.planner._plans(self.planner._snapshot(self.root,'weekly'),'weekly','2026-10-11')
        self.assertEqual(issues,[])
        self.assertEqual(len(plans),1)
        reasons=plans[0]['reasons']
        for field in ('capacity_it_mw','capacity_it_mw_by_status','capacity_assessment','capacity_facility_mw','tenant'):
            self.assertIn('missing:'+field,reasons)

    def at(self, text):
        return datetime.fromisoformat(text.replace('Z', '+00:00'))

    def tasks(self):
        result = []
        for row in self.store.db.execute('SELECT * FROM site_tracking_tasks ORDER BY id'):
            item = dict(row)
            for key in ('fields', 'blockers'):
                item[key] = json.loads(item[key])
            result.append(item)
        return result

    def triggers(self, cadence=None):
        result = []
        for row in self.store.db.execute('SELECT * FROM site_tracking_triggers ORDER BY id'):
            item = dict(row)
            if cadence is None or item['cadence'] == cadence:
                for key in ('fields', 'reasons', 'evidence'):
                    item[key] = json.loads(item[key])
                result.append(item)
        return result

    def periods(self):
        return {row['cadence']: row['period'] for row in self.planner.status()['periods']}

    def verified_event(self, version='source-v1', fields=('owner',)):
        # Task lifecycle after intake; real receiver/archive checks are covered
        # by the source integration tests.
        return {'key': 'news:checked-event', 'version': version,
                'site_id': self.site['site_id'], 'identity_verified': True,
                'target_ids': ['S.permits.news'], 'fields': set(fields),
                'reasons': ['received_event'],
                'blockers': ['native_source_collection_required'],
                'evidence': [{'role': 'news_metadata', 'sha256': 'a'*64}]}

    def tick_event(self, event, when):
        with patch.object(self.planner, '_events', return_value=([event], [])):
            return self.planner.tick(self.root, at=self.at(when))

    def event_tasks(self):
        return [row for row in self.tasks()
                if json.loads(row['request'])['target_ids'] == ['S.permits.news']]


    def existing_review_rows(self):
        return {
            name: [tuple(row) for row in self.store.db.execute('SELECT * FROM '+name+' ORDER BY id')]
            for name in ('batches', 'dispositions')
        }

    def seed_existing_review(self):
        self.store.db.execute(
            'INSERT INTO batches(id,state,candidate_ids,attempts,available) VALUES(?,?,?,?,?)',
            ('existing-batch', 'reviewing', '["existing-candidate"]', 2, 123.5))
        self.store.db.execute(
            'INSERT INTO dispositions(id,state,batch_id,reason) VALUES(?,?,?,?)',
            ('existing-candidate', 'reviewing', 'existing-batch', 'owned by existing C3 worker'))
        self.store.db.commit()

    def test_planning_preserves_formal_project_bytes_and_existing_c3_work(self):
        self.seed_existing_review()
        before_projects = self.projects_path.read_bytes()
        before_reviews = self.existing_review_rows()
        self.planner.tick(self.root, at=self.at('2026-10-11T00:00:00Z'))
        self.assertEqual(self.projects_path.read_bytes(), before_projects)
        self.assertEqual(self.existing_review_rows(), before_reviews)
        rows = self.tasks()
        self.assertTrue(rows, 'monthly source and identity review must plan actual work')
        for row in rows:
            self.assertNotIn(row['state'], ('collected', 'read', 'adopted', 'published', 'completed'))

    def test_corrupt_input_keeps_cycle_retryable_and_does_not_break_review_worker(self):
        self.seed_existing_review()
        before_reviews = self.existing_review_rows()
        self.projects_path.write_bytes(b'{invalid project source')
        failed = self.planner.tick(self.root, at=self.at('2026-10-11T00:00:00Z'))
        self.assertEqual(self.existing_review_rows(), before_reviews)
        self.assertEqual(self.projects_path.read_bytes(), b'{invalid project source')
        self.assertFalse(self.tasks())
        self.assertEqual(self.periods(), {})
        self.assertIn('error', json.dumps(failed).lower())
        self.write_projects([self.site])
        self.planner.tick(self.root, at=self.at('2026-10-11T00:01:00Z'))
        self.assertTrue(self.tasks(), 'failure must not advance the successful planning watermark')
        self.assertEqual(self.existing_review_rows(), before_reviews)

    def test_beijing_day_monday_week_and_month_survive_restart_without_duplicate_work(self):
        # Sunday UTC is already Monday and a new month in Beijing.
        when = self.at('2026-11-01T16:30:00Z')
        self.planner.tick(self.root, at=when)
        self.assertEqual(self.periods(), {
            'daily': '2026-11-02', 'weekly': '2026-11-02', 'monthly': '2026-11'})
        before_tasks, before_triggers = self.tasks(), self.triggers()
        self.store.db.close()
        self.store = ReviewStore(self.data)
        self.addCleanup(self.store.db.close)
        self.planner = SiteTracking(self.store.db, self.data)
        self.planner.tick(self.root, at=self.at('2026-11-01T17:00:00Z'))
        self.assertEqual(self.tasks(), before_tasks)
        self.assertEqual(self.triggers(), before_triggers)

    def test_invalid_register_row_is_recorded_as_failed_scan_not_an_uncaught_worker_error(self):
        self.seed_existing_review()
        before_reviews = self.existing_review_rows()
        self.write_projects([None])
        result = self.planner.tick(self.root, at=self.at('2026-10-11T00:00:00Z'))
        self.assertEqual(self.periods(), {})
        self.assertFalse(self.tasks())
        self.assertEqual({row['state'] for row in result['latest_runs']}, {'failed'})
        self.assertEqual(self.existing_review_rows(), before_reviews)

    def test_failed_monthly_enqueue_rolls_back_whole_scan_and_retries_after_backoff(self):
        self.seed_existing_review()
        before_reviews = self.existing_review_rows()
        complete = dict(self.site, lifecycle='active')
        other = dict(complete, site_id='us-other-fixed-land', name='Other Physical Campus')
        self.write_projects([complete, other])
        enqueue = self.planner._enqueue
        calls = []

        def fail_second(plan, cadence, period, stamp):
            if cadence == 'monthly':
                calls.append(plan['site']['site_id'])
                if len(calls) == 2:
                    raise ValueError('injected enqueue failure after one task')
            return enqueue(plan, cadence, period, stamp)

        with patch.object(self.planner, '_enqueue', side_effect=fail_second):
            self.planner.tick(self.root, at=self.at('2026-10-11T00:00:00Z'))
        self.assertEqual(len(calls), 2)
        self.assertFalse(self.tasks(), 'earlier enqueues in a failed scan must be rolled back')
        self.assertFalse(self.triggers())
        self.assertNotIn('monthly', self.periods())
        self.assertEqual(self.existing_review_rows(), before_reviews)
        self.planner.tick(self.root, at=self.at('2026-10-11T00:06:00Z'))
        self.assertEqual(len(self.tasks()), 2)
        self.assertEqual(self.periods()['monthly'], '2026-10')

    def test_restart_catches_up_current_period_only_and_keeps_gap_visible(self):
        self.planner.tick(self.root, at=self.at('2026-10-11T00:00:00Z'))
        self.planner = SiteTracking(self.store.db, self.data)
        self.planner.tick(self.root, at=self.at('2026-12-09T00:00:00Z'))
        result = self.planner.status()
        self.assertEqual(self.periods(), {
            'daily': '2026-12-09', 'weekly': '2026-12-07', 'monthly': '2026-12'})
        self.assertEqual({r['cadence']: r['catch_up_from'] for r in result['latest_runs']}, {
            'daily': '2026-10-11', 'weekly': '2026-10-05', 'monthly': '2026-10'})
        trigger_periods = {r['period'] for r in self.triggers()}
        self.assertNotIn('2026-11', trigger_periods, 'restart must not manufacture missed source checks')
        self.assertEqual(len(self.tasks()), 1, 'unfinished same-scope work must be reused across periods')
        for key in ('collection_completed', 'adopted_updates', 'published_updates'):
            self.assertIsNone(result[key])

    def test_weekly_includes_missing_overdue_and_same_time_conflicts_without_picking_winner(self):
        self.planner.tick(self.root, at=self.at('2026-10-11T00:00:00Z'))
        changed = copy.deepcopy(self.site)
        changed.update(tenant=[], verified_date='2025-01-01')
        changed['observations'] = [{
            'id': ident, 'recorded_at': '2026-10-11T00:00:00Z',
            'effective_at': '2026-10-10', 'scope': 'whole_site', 'kind': 'reported',
            'basis': 'reviewed source', 'fields': {'owner': [owner]},
            'adoption': {'review_id': ident},
        } for ident, owner in (('report-a', 'owner-a'), ('report-b', 'owner-b'))]
        self.write_projects([changed])
        before = self.projects_path.read_bytes()
        self.planner.tick(self.root, at=self.at('2026-10-12T00:00:00Z'))
        rows = [r for r in self.triggers('weekly') if r['period'] == '2026-10-12']
        self.assertEqual(len(rows), 1)
        self.assertTrue({'tenant', 'status', 'owner'} <= set(rows[0]['fields']))
        self.assertTrue({'missing:tenant', 'overdue:status', 'conflict:owner'} <= set(rows[0]['reasons']))
        self.assertEqual(self.projects_path.read_bytes(), before)
        self.assertEqual(len(self.tasks()), 1, 'weekly additions must union into unfinished monthly work')

    def test_monthly_keeps_inactive_site_and_flags_source_gap_but_excludes_nonphysical_rows(self):
        inactive = copy.deepcopy(self.site)
        inactive.update(lifecycle='cancelled', sources=[])
        duplicate = dict(self.site, site_id='duplicate-record', duplicate_of=self.site['site_id'])
        portfolio = dict(self.site, site_id='portfolio-global-company')
        self.write_projects([inactive, duplicate, portfolio])
        self.planner.tick(self.root, at=self.at('2026-10-11T00:00:00Z'))
        rows = self.triggers('monthly')
        self.assertEqual([r['source_key'] for r in rows], ['site:'+inactive['site_id']])
        self.assertTrue({'identity_coverage_review', 'source_coverage_review', 'source_coverage_missing'}
                        <= set(rows[0]['reasons']))
        self.assertEqual({r['site_id'] for r in self.tasks()}, {inactive['site_id']})
        for row in self.tasks():
            self.assertIn('native_source_collection_required', row['blockers'])
            self.assertIn('demand_mapping_required', row['blockers'])



    def test_failed_execution_keeps_state_error_and_unions_new_period_fields(self):
        self.tick_event(self.verified_event(), '2026-10-11T00:00:00Z')
        task = self.event_tasks()[0]
        self.store.db.execute(
            'UPDATE site_tracking_tasks SET state=?,error=? WHERE id=?',
            ('failed', 'actual executor failed: retain original budget', task['id']))
        self.store.db.commit()
        self.tick_event(self.verified_event('source-v2', ('tenant',)), '2026-10-12T00:00:00Z')
        rows = self.event_tasks()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], task['id'])
        self.assertEqual(rows[0]['state'], 'failed')
        self.assertEqual(rows[0]['error'], 'actual executor failed: retain original budget')
        self.assertEqual(set(rows[0]['fields']), {'owner', 'tenant'})
        triggers = [r for r in self.triggers('daily') if r['task_id'] == task['id']]
        self.assertEqual({r['period'] for r in triggers}, {'2026-10-11', '2026-10-12'})

    def test_changed_candidate_definition_preserves_old_request_and_supersedes_blocked_work(self):
        event = self.verified_event()
        self.tick_event(event, '2026-10-11T00:00:00Z')
        old = self.event_tasks()[0]
        targets = json.loads(self.targets_path.read_text())
        targets['targets'][0]['request']['question_ids'] = ['OBJ-permits-new-purpose']
        self.targets_path.write_text(json.dumps(targets))
        self.tick_event(event, '2026-10-11T00:01:00Z')
        rows = {row['id']: row for row in self.event_tasks()}
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[old['id']]['state'], 'superseded')
        self.assertEqual(rows[old['id']]['request'], old['request'])
        new = next(row for ident, row in rows.items() if ident != old['id'])
        self.assertEqual(new['state'], 'blocked')
        self.assertEqual(new['previous_task_id'], old['id'])
        old_definition = json.loads(old['request'])['definitions'][0]
        new_definition = json.loads(new['request'])['definitions'][0]
        self.assertNotEqual(old_definition['definition_sha256'], new_definition['definition_sha256'])

    def test_completed_work_has_one_successor_reused_by_later_unfinished_periods(self):
        event = self.verified_event()
        self.tick_event(event, '2026-10-11T00:00:00Z')
        old = self.event_tasks()[0]
        self.store.db.execute("UPDATE site_tracking_tasks SET state='completed' WHERE id=?", (old['id'],))
        self.store.db.commit()
        self.tick_event(self.verified_event('source-v2'), '2026-10-12T00:00:00Z')
        rows = self.event_tasks()
        self.assertEqual(len(rows), 2)
        new = next(row for row in rows if row['id'] != old['id'])
        self.assertEqual(new['state'], 'blocked')
        self.assertEqual(new['previous_task_id'], old['id'])
        self.tick_event(self.verified_event('source-v3'), '2026-10-13T00:00:00Z')
        rows = {row['id']: row for row in self.event_tasks()}
        self.assertEqual(set(rows), {old['id'], new['id']})
        self.assertEqual(rows[old['id']]['state'], 'completed')
        self.assertEqual(rows[new['id']]['state'], 'blocked')
        self.assertEqual({r['period'] for r in self.triggers('daily') if r['task_id'] == new['id']},
                         {'2026-10-12', '2026-10-13'})


    def test_large_failure_backlog_has_bounded_status_without_losing_private_errors(self):
        self.planner.tick(self.root, self.at('2026-10-11T00:00:00Z'))
        errors = ['news:'+str(i)+':metadata_archive_unavailable' for i in range(3000)]
        self.store.db.execute("UPDATE site_tracking_runs SET error=?,state='partial' WHERE cadence='daily'",
                              (json.dumps(errors),))
        self.store.db.commit()
        result = self.planner.status()
        daily = next(r for r in result['latest_runs'] if r['cadence'] == 'daily')
        self.assertEqual(daily['error_count'], len(errors))
        self.assertTrue(daily['errors_truncated'])
        self.assertEqual(json.loads(daily['error']), errors[:8])
        self.assertLess(len(json.dumps(result)), 6000)
        stored = self.store.db.execute("SELECT error FROM site_tracking_runs WHERE cadence='daily'").fetchone()[0]
        self.assertEqual(json.loads(stored), errors)


if __name__ == '__main__':
    unittest.main()
