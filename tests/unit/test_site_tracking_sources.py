import copy
import hashlib
import json
import os
import sys
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from inresearch.adapters.acquisition import Collector, import_news
from inresearch.adapters.news_sync import verified
from inresearch.materials import daily_bundle
from inresearch.paths import project_root
from inresearch.workflow import project_pipeline, research_review
from inresearch.workflow import site_tracking
from inresearch.workflow.site_tracking import SiteTracking
from tests.unit import test_daily_bundle as bundle_tests
from tests.unit import test_site_tracking as cadence_tests


class SiteTrackingSourceTests(unittest.TestCase):
    setUp = cadence_tests.SiteTrackingTests.setUp
    at = cadence_tests.SiteTrackingTests.at
    tasks = cadence_tests.SiteTrackingTests.tasks
    triggers = cadence_tests.SiteTrackingTests.triggers
    periods = cadence_tests.SiteTrackingTests.periods
    write_projects = cadence_tests.SiteTrackingTests.write_projects

    def news(self, article_id='1'):
        (self.root/'data/companies.json').write_text('{"records": []}')
        article = {'id': article_id, 'guid': 'news-'+article_id, 'url': 'https://example.org/news/'+article_id,
                   'title': 'Test Physical Campus data center construction 60 MW',
                   'published_at': 1791676800000, 'topics': ['datacenter'],
                   'object_ids': ['actor:developer'], 'target_ids': ['S.permits.news'],
                   'event_type': 'project_milestone'}
        collector = Collector(self.data)
        original = project_pipeline.receive
        try:
            with patch.object(project_pipeline, 'receive', side_effect=lambda h, a, t, w: original(h, a, t, w, self.root)):
                import_news(collector, verified([article], {'since': 1791676800000, 'until': 1791763200000}))
        finally:
            collector.close()
        return article

    def delivered_daily(self):
        folder = self.data.parent/'bundle'
        folder.mkdir()
        bundle_tests.DailyBundleTests().bundle(folder, True)
        return daily_bundle.receive(folder, self.data, project_root())

    def test_verified_arrival_marker_cannot_authorize_daily_scan_or_support_membership(self):
        from inresearch.workflow.daily_dispatch import receipt_documents
        folder=self.data.parent/'bundle';folder.mkdir()
        bundle_tests.DailyBundleTests().bundle(folder,True)
        original=daily_bundle.ingest
        def incomplete(*args,**kwargs):
            original(*args,**kwargs)
            raise ValueError('index_failed_after_event_write')
        with patch.object(daily_bundle,'ingest',side_effect=incomplete):
            with self.assertRaisesRegex(ValueError,'index_failed_after_event_write'):
                daily_bundle.receive(folder,self.data,project_root())
        marker_path=next((self.data/'material-reviews/daily-deliveries').glob('*.json'))
        marker=json.loads(marker_path.read_text())
        daily=json.loads((self.data/'acquisition/daily-events.json').read_text())
        # Even claimed exact event membership cannot make a pending marker a
        # completed receiver receipt; its delivery status is decisive.
        marker['documents']=[{'sha256':r['sha256'],'event_ids':list(daily['records'])}
                             for r in marker['members'] if r['role']=='html']
        marker_path.write_text(json.dumps(marker))
        self.assertEqual(receipt_documents(self.data),{})
        snapshot=self.planner._snapshot(self.root,'daily')
        self.assertEqual(snapshot['accepted'],{})
        self.assertEqual(snapshot['receipt_events'],{})
        at=self.at('2026-10-11T00:00:00Z')
        self.planner.tick(self.root,at)
        self.assertEqual(self.triggers('daily'),[])
        self.assertNotIn('daily',self.periods())
        indexed=daily_bundle.receive(folder,self.data,project_root())
        self.assertEqual(indexed['first_received_at'],marker['first_received_at'])
        self.planner.tick(self.root,at+timedelta(minutes=6))
        self.assertEqual(len(self.triggers('daily')),1)
        self.assertIn('daily',self.periods())

    def test_news_metadata_bytes_trigger_once_across_days_and_never_claim_original_collection(self):
        self.news()
        at = self.at('2026-10-11T00:00:00Z')
        self.planner.tick(self.root, at)
        triggers = self.triggers('daily')
        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]['evidence'][0]['role'], 'news_metadata')
        task = next(r for r in self.tasks() if r['id'] == triggers[0]['task_id'])
        self.assertIn('native_source_collection_required', task['blockers'])
        self.assertIn('physical_identity_requires_review', task['blockers'])
        request = json.loads(task['request'])
        self.assertEqual(request['status'], 'candidate_only')
        self.assertEqual(request['target_ids'], ['S.permits.news'])
        count = len(self.tasks())
        self.planner.tick(self.root, at+timedelta(days=1))
        self.assertEqual(self.triggers('daily'), triggers)
        self.assertEqual(len(self.tasks()), count)

    def test_unarchived_pipeline_entry_stays_partial_and_changed_source_gets_new_trigger(self):
        self.news()
        path = self.data/'acquisition/project-pipeline.json'
        value = json.loads(path.read_text())
        lead = next(iter(value['records'].values()))
        forged = copy.deepcopy(lead['events'][0]); forged['id'] = 'unreceived'
        lead['events'].append(forged)
        path.write_text(json.dumps(value))
        self.planner.tick(self.root, self.at('2026-10-11T00:00:00Z'))
        self.assertEqual(len(self.triggers('daily')), 1)
        self.assertNotIn('daily', self.periods())
        run = next(r for r in self.planner.status()['latest_runs'] if r['cadence'] == 'daily')
        self.assertEqual(run['state'], 'partial')
        self.assertIn('metadata_archive_unavailable', run['error'])
        lead['events'].pop()
        lead['events'][0]['withdrawn'] = True
        path.write_text(json.dumps(value))
        self.planner.tick(self.root, self.at('2026-10-11T00:01:00Z'))
        self.assertEqual(len(self.triggers('daily')), 2)
        self.assertTrue(any('source_withdrawn' in r['reasons'] for r in self.triggers('daily')))
        task = next(r for r in self.tasks() if 'source_withdrawn_requires_review' in r['blockers'])
        self.assertEqual(task['state'], 'blocked')
        self.assertIn('daily', self.periods())

    def test_touching_identical_metadata_rechecks_cache_without_new_source_trigger(self):
        self.news()
        at = self.at('2026-10-11T00:00:00Z')
        self.planner.tick(self.root, at)
        before = self.triggers('daily')
        archive = self.data/before[0]['evidence'][0]['archive']
        original = archive.read_bytes()
        stat = archive.stat()
        os.utime(archive, ns=(stat.st_atime_ns, stat.st_mtime_ns+1_000_000_000))
        self.planner.tick(self.root, at+timedelta(days=1))
        self.assertEqual(self.planner.archive_checks, 1)
        self.assertEqual(archive.read_bytes(), original)
        self.assertEqual(self.triggers('daily'), before)

    def test_real_daily_receipt_and_html_archive_are_required_for_exact_event_membership(self):
        receipt = self.delivered_daily()
        self.planner.tick(self.root, self.at('2026-10-11T00:00:00Z'))
        rows = self.triggers('daily')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['evidence'][0]['role'], 'daily_html')
        path = self.data/'acquisition/daily-events.json'
        ledger = json.loads(path.read_text())
        event = copy.deepcopy(next(iter(ledger['records'].values())))
        event['id'] = 'daily-event-not-received'
        ledger['records'][event['id']] = event
        sha = receipt['documents'][0]['sha256']
        ledger['parses'][sha]['event_ids'].append(event['id'])
        path.write_text(json.dumps(ledger))
        self.planner.tick(self.root, self.at('2026-10-11T00:01:00Z'))
        self.assertEqual(len(self.triggers('daily')), 1)
        run = next(r for r in self.planner.status()['latest_runs'] if r['cadence'] == 'daily')
        self.assertEqual(run['state'], 'partial')

    def second_daily_reference(self, receipt_member=True, archive=True):
        path = self.data/'acquisition/daily-events.json'
        ledger = json.loads(path.read_text())
        event = next(iter(ledger['records'].values()))
        body = b'<html><title>Second explicitly referenced HTML</title></html>'
        sha = hashlib.sha256(body).hexdigest()
        if archive:
            catalog = Collector(self.data)
            try:
                ident = catalog.item('fetchreports', sha, 'document', '', 'Second HTML', {})
                catalog.archive(ident, body, '.html', {})
            finally:
                catalog.close()
        event['document_refs'].append(dict(event['document_refs'][0], sha256=sha))
        path.write_text(json.dumps(ledger))
        receipt_path = next((self.data/'material-reviews/daily-deliveries').glob('*.json'))
        receipt = json.loads(receipt_path.read_text())
        receipt['documents'].append({'sha256': sha, 'title': 'Second HTML',
                                     'event_ids': [event['id']] if receipt_member else []})
        receipt_path.write_text(json.dumps(receipt))
        return sha, body, receipt_path, event['id']

    def test_one_available_reference_does_not_hide_missing_catalog_and_catalog_arrival_retries(self):
        self.delivered_daily()
        sha, body, _, _ = self.second_daily_reference(archive=False)
        at = self.at('2026-10-11T00:00:00Z')
        self.planner.tick(self.root, at)
        self.assertEqual(len(self.triggers('daily')), 1)
        self.assertNotIn('daily', self.periods())
        run = next(r for r in self.planner.status()['latest_runs'] if r['cadence']=='daily')
        self.assertEqual(run['state'], 'partial')
        self.assertIn(sha+':catalog_archive_unavailable', run['error'])
        # No hot-loop rescanning while the named catalog gap is unchanged.
        with patch.object(self.planner, '_snapshot', side_effect=AssertionError('early rescan')):
            self.planner.tick(self.root, at+timedelta(seconds=10))
        catalog = Collector(self.data)
        try:
            ident = catalog.item('fetchreports', sha, 'document', '', 'Second HTML', {})
            catalog.archive(ident, body, '.html', {})
        finally:
            catalog.close()
        # Only catalog changed; neither daily ledger nor receipt is touched.
        self.planner = SiteTracking(self.store.db, self.data)
        self.planner.tick(self.root, at+timedelta(seconds=30))
        self.assertEqual(self.periods()['daily'], '2026-10-11')
        self.assertEqual(len(self.triggers('daily')), 2)
        self.assertTrue(any(sha in {e['sha256'] for e in r['evidence']} for r in self.triggers('daily')))

    def test_legacy_planned_watermark_is_rechecked_under_reference_completeness_contract(self):
        self.delivered_daily()
        sha, _, _, _ = self.second_daily_reference(archive=False)
        at = self.at('2026-10-11T00:00:00Z')
        snapshot = self.planner._snapshot(self.root, 'daily')
        snapshot.pop('reference_scan_version')
        legacy_sha = site_tracking.digest(snapshot)
        # An old successful watermark could have silently skipped source B.
        with self.store.db:
            self.store.db.execute('INSERT INTO site_tracking_periods VALUES(?,?,?,?)',
                ('daily', '2026-10-11', legacy_sha, at.isoformat()))
            self.store.db.execute('INSERT INTO site_tracking_checks VALUES(?,?,?,?,?)',
                ('daily', '2026-10-11', 'legacy-signature', 'planned', 0))
        self.planner.tick(self.root, at+timedelta(seconds=30))
        run = next(r for r in self.planner.status()['latest_runs'] if r['cadence']=='daily')
        self.assertEqual(run['state'], 'partial')
        self.assertIn(sha+':catalog_archive_unavailable', run['error'])
        self.assertNotEqual(run['input_sha256'], legacy_sha)
        # Keep the historical scan proof; do not overwrite it as newly complete.
        self.assertEqual(self.store.db.execute(
            "SELECT input_sha256 FROM site_tracking_periods WHERE cadence='daily'").fetchone()[0], legacy_sha)
        self.assertEqual(self.store.db.execute(
            "SELECT state FROM site_tracking_checks WHERE cadence='daily'").fetchone()[0], 'partial')

    def test_one_available_reference_keeps_receipt_membership_gap_retryable(self):
        self.delivered_daily()
        sha, _, receipt_path, event_id = self.second_daily_reference(receipt_member=False)
        at = self.at('2026-10-11T00:00:00Z')
        self.planner.tick(self.root, at)
        self.assertEqual(len(self.triggers('daily')), 1)
        self.assertNotIn('daily', self.periods())
        run = next(r for r in self.planner.status()['latest_runs'] if r['cadence']=='daily')
        self.assertIn(sha+':receipt_event_membership_missing', run['error'])
        self.assertEqual(self.planner.archive_checks, 1, 'An unreceived reference must not be hashed')
        receipt = json.loads(receipt_path.read_text())
        next(d for d in receipt['documents'] if d['sha256']==sha)['event_ids']=[event_id]
        receipt_path.write_text(json.dumps(receipt))
        self.planner = SiteTracking(self.store.db, self.data)
        self.planner.tick(self.root, at+timedelta(minutes=6))
        self.assertEqual(self.periods()['daily'], '2026-10-11')
        self.assertEqual(self.planner.archive_checks, 1)
        self.assertEqual(len(self.triggers('daily')), 2)

    def test_reference_without_any_receiver_receipt_keeps_scan_partial(self):
        self.delivered_daily()
        sha, _, receipt_path, _ = self.second_daily_reference()
        receipt = json.loads(receipt_path.read_text())
        receipt['documents']=[d for d in receipt['documents'] if d['sha256']!=sha]
        receipt_path.write_text(json.dumps(receipt))
        self.planner.tick(self.root, self.at('2026-10-11T00:00:00Z'))
        self.assertNotIn('daily', self.periods())
        run = next(r for r in self.planner.status()['latest_runs'] if r['cadence']=='daily')
        self.assertIn(sha+':receiver_receipt_missing', run['error'])
        self.assertEqual(self.planner.archive_checks, 1)
        self.assertEqual(len(self.triggers('daily')), 1)

    def test_archive_failure_keeps_bytes_and_failure_attempt_after_same_period_recovery(self):
        self.news()
        collector = Collector(self.data)
        try:
            relative = collector.db.execute('SELECT relative_path FROM observations LIMIT 1').fetchone()[0]
        finally:
            collector.close()
        archive = self.data/relative
        original = archive.read_bytes()
        archive.write_bytes(b'changed metadata')
        at = self.at('2026-10-11T00:00:00Z')
        self.planner.tick(self.root, at)
        self.assertEqual(archive.read_bytes(), b'changed metadata')
        self.assertNotIn('daily', self.periods())
        self.assertEqual(self.triggers('daily'), [])
        archive.write_bytes(original)
        self.planner.tick(self.root, at+timedelta(minutes=6))
        self.assertIn('daily', self.periods())
        self.assertEqual(len(self.triggers('daily')), 1)
        failed = self.store.db.execute("SELECT error FROM site_tracking_attempts WHERE state='failed'").fetchall()
        self.assertTrue(any('archive_missing_or_changed' in row[0] for row in failed))

    def test_oversized_metadata_is_blocked_before_hashing_or_decoding(self):
        self.news()
        collector = Collector(self.data)
        try:
            relative = collector.db.execute('SELECT relative_path FROM observations LIMIT 1').fetchone()[0]
        finally:
            collector.close()
        with (self.data/relative).open('r+b') as stream:
            stream.truncate(4*1024*1024+1)
        self.planner.tick(self.root, self.at('2026-10-11T00:00:00Z'))
        self.assertNotIn('daily', self.periods())
        run = next(r for r in self.planner.status()['latest_runs'] if r['cadence'] == 'daily')
        self.assertIn('source_exceeds_delivery_size_limit', run['error'])
        self.assertEqual(self.planner.archive_checks, 0)

    def test_unchanged_idle_ticks_and_restart_do_not_parse_or_rehash_sources(self):
        self.news()
        at = self.at('2026-10-11T00:00:00Z')
        self.planner.tick(self.root, at)
        restarted = SiteTracking(self.store.db, self.data)
        # Other acquisitions do not retrigger a site scan every worker poll.
        catalog = Collector(self.data)
        try:
            catalog.item('fetchspec', 'unrelated', 'document', 'https://example.org/spec', 'Spec', {})
        finally:
            catalog.close()
        with patch.object(restarted, '_snapshot', side_effect=AssertionError('full rescan')):
            restarted.tick(self.root, at+timedelta(seconds=30))
        before = self.planner.status()
        self.assertEqual(restarted.status(), before)

    def test_source_hash_budget_resumes_from_persisted_proofs_and_ignores_unrelated_archives(self):
        for ident in ('1', '2', '3'):
            self.news(ident)
        catalog = Collector(self.data)
        try:
            ident = catalog.item('fetchspec', 'unrelated', 'document', '', 'Spec', {})
            sha = catalog.archive(ident, b'not news', '.txt', {})
            path = self.data/'acquisition/blobs'/sha[:2]/(sha+'.txt')
            path.write_bytes(b'corrupt unrelated original')
        finally:
            catalog.close()
        at = self.at('2026-10-11T00:00:00Z')
        with patch.object(site_tracking, 'MAX_ARCHIVE_CHECKS', 2):
            self.planner.tick(self.root, at)
            self.assertEqual(self.planner.archive_checks, 2)
            self.assertEqual(len(self.triggers('daily')), 2)
            self.assertNotIn('daily', self.periods())
            self.planner.tick(self.root, at+timedelta(minutes=6))
            self.assertEqual(self.planner.archive_checks, 1)
        self.assertEqual(len(self.triggers('daily')), 3)
        self.assertIn('daily', self.periods())

    def test_catalog_arrival_retries_partial_scan_before_backoff_expires(self):
        self.news()
        catalog = Collector(self.data)
        try:
            row = catalog.db.execute('SELECT * FROM observations').fetchone()
            catalog.db.execute('DELETE FROM observations'); catalog.db.commit()
            at = self.at('2026-10-11T00:00:00Z')
            self.planner.tick(self.root, at)
            self.assertNotIn('daily', self.periods())
            catalog.db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)', tuple(row)); catalog.db.commit()
            self.planner.tick(self.root, at+timedelta(seconds=30))
            self.assertIn('daily', self.periods())
            self.assertEqual(len(self.triggers('daily')), 1)
        finally:
            catalog.close()

    def test_many_identical_source_touches_persist_cache_progress_without_new_triggers(self):
        for ident in ('1', '2', '3'):
            self.news(ident)
        at = self.at('2026-10-11T00:00:00Z')
        self.planner.tick(self.root, at)
        before = self.triggers('daily')
        for trigger in before:
            archive = self.data/trigger['evidence'][0]['archive']
            stat = archive.stat()
            os.utime(archive, ns=(stat.st_atime_ns, stat.st_mtime_ns+1_000_000_000))
        with patch.object(site_tracking, 'MAX_ARCHIVE_CHECKS', 2):
            self.planner.tick(self.root, at+timedelta(days=1))
            self.assertEqual(self.planner.archive_checks, 2)
            self.assertEqual(self.periods()['daily'], '2026-10-11')
            self.planner.tick(self.root, at+timedelta(days=1, minutes=6))
            self.assertEqual(self.planner.archive_checks, 1)
            self.assertEqual(self.periods()['daily'], '2026-10-12')
        self.assertEqual(self.triggers('daily'), before)

    def test_bad_news_input_does_not_prevent_worker_from_discovering_other_research(self):
        path = self.data/'acquisition/project-pipeline.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{broken')
        argv = ['research_review', '--data', str(self.data), '--root', str(self.root),
                'work', '--scope', str(self.data/'scope.json'), '--once']
        client = SimpleNamespace(profile=SimpleNamespace(max_parallel=1))
        with patch.object(sys, 'argv', argv), patch.object(research_review.ReviewStore, 'discover') as discover, \
                patch.object(research_review.ReviewStore, 'run_one', return_value=None) as run, \
                patch.object(research_review, 'configured_client', return_value=client), patch('builtins.print'):
            research_review.main()
        discover.assert_called_once()
        self.assertTrue(run.called)
        self.assertNotIn('daily', self.periods())
        self.assertIn('monthly', self.periods())


    def test_daily_multi_document_budget_restart_preserves_each_support_identity(self):
        self.delivered_daily()
        path = self.data/'acquisition/daily-events.json'
        ledger = json.loads(path.read_text())
        event = next(iter(ledger['records'].values()))
        first_sha = event['document_refs'][0]['sha256']
        # A second byte-archived document is explicitly received for this same
        # event. The event already lists both sources before the first scan.
        body = b'<html><title>Second received daily HTML</title></html>'
        second_sha = hashlib.sha256(body).hexdigest()
        catalog = Collector(self.data)
        try:
            ident = catalog.item('fetchreports', second_sha, 'document', '', 'Second daily HTML', {})
            self.assertEqual(catalog.archive(ident, body, '.html', {}), second_sha)
        finally:
            catalog.close()
        event['document_refs'].append(dict(event['document_refs'][0], sha256=second_sha))
        ledger['parses'][second_sha] = {'event_ids': [event['id']]}
        path.write_text(json.dumps(ledger))
        receipt_path = next((self.data/'material-reviews/daily-deliveries').glob('*.json'))
        receipt = json.loads(receipt_path.read_text())
        receipt['documents'].append({'sha256': second_sha, 'title': 'Second daily HTML',
                                     'event_ids': [event['id']]})
        receipt_path.write_text(json.dumps(receipt))
        at = self.at('2026-10-11T00:00:00Z')
        with patch.object(site_tracking, 'MAX_ARCHIVE_CHECKS', 1):
            self.planner.tick(self.root, at)
            first = self.triggers('daily')
            self.assertEqual(len(first), 1)
            self.assertEqual({r['sha256'] for r in first[0]['evidence']}, {first_sha})
            self.assertNotIn('daily', self.periods())
            # A fresh planner must reuse the actual persisted first SHA proof.
            self.planner = SiteTracking(self.store.db, self.data)
            self.planner.tick(self.root, at+timedelta(minutes=6))
            self.assertEqual(self.planner.archive_checks, 1)
        self.assertEqual(self.periods()['daily'], '2026-10-11')
        after = self.triggers('daily')
        self.assertEqual(len(after), 2, 'Completing support B must create an auditable new source version')
        self.assertIn(first[0], after, 'The earlier partial-support trigger must remain intact')
        self.assertEqual({r['task_id'] for r in after}, {first[0]['task_id']})
        self.assertEqual(len({r['source_version'] for r in after}), 2)
        self.assertTrue(any({e['sha256'] for e in r['evidence']} == {first_sha, second_sha}
                            for r in after))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM site_tracking_archives').fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()
