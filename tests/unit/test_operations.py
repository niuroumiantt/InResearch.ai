"""Management must distinguish unknown, current work, history and successful execution."""
import contextlib
import http.client
import io
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import test_continuous_reader as fixtures
from inresearch.workflow import operations as ops, reader as cr
from inresearch.interfaces import http as serve, auth


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clock = fixtures.Clock()
        self.reader = cr.Reader(self.root/'data', self.root/'state', self.root/'repo', fixtures.Model(), 0, 200, self.clock).initialize()
        self.addCleanup(self.reader.close)
        raw = self.reader.data/'raw-materials'
        raw.mkdir(parents=True, exist_ok=True)
        (raw/'paper.txt').write_text('完整正文：机柜功率为 300 W。\n')
        self.reader.scan()

    def collect(self):
        return ops.reader_observability(self.reader.conn, self.clock())

    def test_pending_has_stage_age_identity_and_does_not_write(self):
        before = list(self.reader.conn.iterdump())
        s = self.collect()
        job = s['queues']['pending']['items'][0]
        self.assertEqual(job['stage'], 'extract')
        self.assertTrue(job['revision_id']); self.assertTrue(job['job_id'])
        self.assertEqual(job['original_name'], 'paper.txt')
        self.assertIsNotNone(ops.age(job['created'], self.clock()))
        self.assertEqual(s['queues']['pending']['total'], 1)
        self.assertEqual(list(self.reader.conn.iterdump()), before)

    def test_blocked_groups_are_counted_and_classified_not_inferred_from_last_twenty(self):
        self.reader.conn.execute("UPDATE jobs SET state='blocked',error_code='scanned_page_requires_ocr',finished=?", (self.clock()-3600,))
        s = self.collect()
        self.assertEqual(s['errors'][0]['documents'], 1)
        self.assertEqual(s['errors'][0]['kind'], 'material')
        self.assertEqual(s['errors'][0]['examples'][0]['original_name'], 'paper.txt')
        self.assertTrue(s['errors'][0]['examples'][0]['revision_id'])
        self.assertEqual(ops.age(s['errors'][0]['since'], self.clock()), 3600)
        self.assertEqual(ops.error_info('parked_by_triage')['kind'], 'policy')
        self.assertEqual(ops.error_info('model_output_invalid')['kind'], 'execution')

    def test_historical_failed_revision_does_not_inflate_current_bottlenecks(self):
        doc = self.reader.conn.execute('SELECT * FROM current_readings').fetchone()
        self.reader.conn.execute("UPDATE jobs SET state='blocked',error_code='model_output_invalid',finished=?", (self.clock(),))
        self.reader.conn.execute("UPDATE reading_runs SET state='blocked',error_code='model_output_invalid'")
        new = self.reader.revisions.restart_unfinished(doc['doc_id'], doc['revision_id'], 'test-restart', 'observe replacement')
        s = self.collect()
        self.assertEqual(s['errors'], [])
        self.assertEqual(s['queues']['blocked']['total'], 0)
        self.assertEqual(s['queues']['pending']['total'], 1)
        self.assertNotEqual(s['queues']['pending']['items'][0]['revision_id'], doc['revision_id'])

    def test_current_document_counts_and_job_counts_have_different_units(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.reader.run(once=True)
        s = self.collect()
        self.assertEqual(s['current_documents']['complete'], 1)
        self.assertGreater(sum(r['count'] for r in s['stages']), 1)
        self.assertEqual(s['queues']['pending']['total'], 0)
        self.assertTrue(self.reader.export_snapshot()['reader']['operations'])
        self.assertIsNone(self.reader.status()['operations'])  # no expensive diagnostic scan per worker heartbeat

    def test_queue_sample_is_bounded_and_total_is_preserved(self):
        job = dict(self.reader.conn.execute('SELECT * FROM jobs LIMIT 1').fetchone())
        for i in range(1, 111):
            row = dict(job, job_id='job-%03d'%i, chunk=i)
            self.reader.conn.execute('INSERT INTO jobs ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')', tuple(row.values()))
        s = self.collect()
        self.assertEqual(s['queues']['pending']['total'],111)
        self.assertEqual(len(s['queues']['pending']['items']),100)


class OperationsHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patchers = [patch.object(serve,'ROOT',self.root),patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT':''})]
        for p in self.patchers:
            p.start(); self.addCleanup(p.stop)
        self.server=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler)
        threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval':.01},daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def request(self,path,body=None):
        c=http.client.HTTPConnection(*self.server.server_address,timeout=5)
        try:
            c.request('POST' if body is not None else 'GET',path, json.dumps(body) if body is not None else None,
                      {'Content-Type':'application/json'} if body is not None else {})
            r=c.getresponse();return r.status,r.read()
        finally:c.close()

    def test_full_log_survives_preview_truncation_and_result_is_recorded(self):
        output='校验失败 37 项\n'+'内容\n'*10000+'END'
        with patch.object(serve,'AUTH_ON',False),patch.object(serve.subprocess,'run',return_value=subprocess.CompletedProcess([],1,output,'')):
            status,body=self.request('/api/run',{'task':'facts'})
        result=json.loads(body)
        self.assertEqual(status,200);self.assertFalse(result['ok']);self.assertTrue(result['truncated'])
        self.assertTrue(result['output'].startswith('校验失败 37 项'));self.assertTrue(result['output'].endswith('END'))
        self.assertEqual(ops.log_content(self.root,result['run']['id']),output)
        self.assertEqual(ops.task_state(self.root,serve.TASKS,set())['facts']['outcome'],'failed')
        self.assertEqual(ops.task_history(self.root)['total'],1)
        with patch.object(serve,'AUTH_ON',False):
            status,body=self.request(result['log_url'])
        self.assertEqual(status,200);self.assertEqual(body.decode(),output)

    def test_timeout_is_recorded_with_partial_output(self):
        with patch.object(serve,'AUTH_ON',False),patch.object(serve.subprocess,'run',side_effect=subprocess.TimeoutExpired('test',30,output=b'partial')):
            _,body=self.request('/api/run',{'task':'reader'})
        result=json.loads(body)
        self.assertEqual(result['run']['outcome'],'timeout')
        self.assertIn('partial',ops.log_content(self.root,result['run']['id']))
        self.assertNotIn('reader',serve.RUNNING)

    def test_private_diagnostics_require_admin_and_paths_cannot_be_selected(self):
        with patch.object(serve,'AUTH_ON',True),patch.object(auth,'session_user',return_value=None):
            self.assertEqual(self.request('/api/ops')[0],401)
            self.assertEqual(self.request('/api/ops/log?id='+'a'*32)[0],401)
        with patch.object(serve,'AUTH_ON',True),patch.object(auth,'session_user',return_value='member'),patch.object(auth,'user_role',return_value='member'):
            self.assertEqual(self.request('/api/ops')[0],403)
            self.assertEqual(self.request('/api/ops/log?id='+'a'*32)[0],403)
        with patch.object(serve,'AUTH_ON',False):
            self.assertEqual(self.request('/api/ops/log?id=../../data/users.json')[0],400)
            self.assertEqual(self.request('/api/ops/log?task=facts')[0],400)

    def test_old_task_log_is_unknown_not_success(self):
        path=self.root/'logs/task_facts.log';path.parent.mkdir();path.write_text('old clipped log')
        s=ops.task_state(self.root,serve.TASKS,set())['facts']
        self.assertEqual(s['outcome'],'unknown');self.assertTrue(s['legacy'])
        self.assertIn('+00:00',s['last'])

    def test_missing_reader_and_missing_quality_are_unknown_not_zero(self):
        s=ops.snapshot(self.root,serve.TASKS,set())
        self.assertEqual(s['reader']['status'],'unknown')
        self.assertNotIn('quality',s);self.assertNotIn('targets',s)
        self.assertGreater(len(s['unavailable']),1)

    def test_stale_generated_snapshot_is_not_masked_by_recent_reception(self):
        with patch.object(ops,'_reader',return_value={'status':'running','received_at':ops.iso(1000),'generated':ops.iso(0)}):
            s=ops.snapshot(self.root,serve.TASKS,set(),now=1100)
        self.assertEqual(s['reader']['snapshot_age_seconds'],100)
        self.assertEqual(s['reader']['generated_age_seconds'],1100)
        self.assertTrue(s['reader']['stale'])
