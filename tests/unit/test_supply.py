"""Supply planning: persistent authority, replay, concurrent changes and HTTP roles."""
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch
from inresearch.paths import project_root
from inresearch.workflow import supply
from inresearch.interfaces import http, auth


class SupplyTests(unittest.TestCase):
    def setUp(self):
        self.root = project_root()
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT': self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def request(self, **changes):
        value = dict(action='create', operation_id=str(uuid.uuid4()), expected_revision=0,
                     question_id='M01-Q01', title='容量原件', scope='全球投运容量与统计期',
                     acceptance='原文、定位与口径', provider_id='fetchstat',
                     execution_mode='continuous', execution_host='aws')
        value.update(changes)
        return value

    def test_persistence_replay_and_conflict(self):
        self.assertEqual(supply.snapshot(self.root)['demands'], [])
        self.assertFalse((Path(self.tmp.name)/'data').exists())
        req = self.request()
        supply.mutate(self.root, req, 'admin')
        self.assertTrue(supply.mutate(self.root, req, 'admin')['replayed'])
        self.assertEqual(len(supply.snapshot(self.root)['tasks']), 1)
        self.assertEqual(supply.snapshot(self.root)['tasks'][0]['execution_host'], 'aws')
        with self.assertRaises(supply.Conflict):
            supply.mutate(self.root, self.request(), 'admin')
        with self.assertRaises(supply.Conflict):
            supply.mutate(self.root, {**req, 'title':'changed'}, 'admin')
        self.assertEqual(supply.ledger_path(self.root), Path(self.tmp.name).resolve()/'data/raw/supply-center/ledger.json')
        self.assertFalse(http.source_path('/data/raw/supply-center/ledger.json', self.root).exists())

    def test_validation_and_corruption_never_replace_state(self):
        for update in ({'question_id':'unknown'}, {'provider_id':'unknown'}, {'acceptance':''}, {'action':'adopt'},
                       {'execution_mode':'assisted', 'execution_host':'aws'}):
            with self.assertRaises(ValueError):
                supply.mutate(self.root, self.request(**update), 'admin')
        self.assertEqual(supply.read(self.root)['revision'], 0)
        path=supply.ledger_path(self.root);path.parent.mkdir(parents=True, exist_ok=True);path.write_text('broken')
        with self.assertRaises(ValueError):
            supply.mutate(self.root, self.request(), 'admin')
        self.assertEqual(path.read_text(), 'broken')

    def test_fetchspec_receipt_projects_candidate_reader_state_without_adoption(self):
        sha = 'a' * 64
        receipts = Path(self.tmp.name) / 'data/raw/supply-center/receipts.json'
        receipts.parent.mkdir(parents=True)
        receipts.write_text(json.dumps({'version': 1, 'deliveries': {'d1': {
            'delivery_id': 'd1', 'status': 'received', 'received_items': 1,
            'items': [{'sha256': sha, 'reader_handoff': 'eligible'}]}}}))
        reader = Path(self.tmp.name) / 'reader'
        (reader / 'catalog').mkdir(parents=True)
        db = sqlite3.connect(reader / 'catalog/catalog.sqlite')
        db.executescript('''CREATE TABLE documents(doc_id TEXT,sha256 TEXT);
            CREATE TABLE reading_runs(doc_id TEXT,base_revision_id TEXT,state TEXT,phase TEXT,
            pages_total INTEGER,chunks_total INTEGER,chunks_read INTEGER,report_sha256 TEXT,manifest_sha256 TEXT);''')
        db.execute('INSERT INTO documents VALUES(?,?)', ('doc-1', sha))
        db.execute('INSERT INTO reading_runs VALUES(?,?,?,?,?,?,?,?,?)',
                   ('doc-1', None, 'ready', 'complete', 2, 3, 3, 'report', 'sealed'))
        db.commit(); db.close()
        with patch.dict(os.environ, {'READER_DATA_ROOT': str(reader)}):
            delivery = supply.snapshot(self.root)['deliveries'][0]
        self.assertEqual(delivery['reading']['candidate_ready'], 1)
        self.assertEqual(delivery['reading']['adoption'], 'not_inferred')

    def test_multiple_suppliers_and_concurrent_revision(self):
        req=self.request();supply.mutate(self.root,req,'admin')
        demand=supply.read(self.root)['demands'][0]['id']
        supply.mutate(self.root, self.request(action='assign', demand_id=demand, provider_id='local', expected_revision=1,
                                               execution_mode='assisted', execution_host='macmini'), 'admin')
        results=[]
        def add():
            try:
                supply.mutate(self.root,self.request(expected_revision=2),'admin');results.append('saved')
            except supply.Conflict:
                results.append('conflict')
        threads=[threading.Thread(target=add) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertCountEqual(results,['saved','conflict'])
        self.assertEqual(len(supply.read(self.root)['tasks']),3)
        self.assertTrue(all(t['status']=='planned' for t in supply.read(self.root)['tasks']))
        self.assertEqual(supply.read(self.root)['tasks'][1]['execution_host'], 'macmini')

    def test_http_roles_and_private_storage(self):
        server=http.ThreadingHTTPServer(('127.0.0.1',0),http.Handler)
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
        def call(method,path,headers=None):
            c=HTTPConnection(*server.server_address)
            c.request(method,path,json.dumps(self.request()) if method=='POST' else None,headers or {})
            response=c.getresponse();body=response.read();c.close();return response.status,body
        try:
            with patch.object(http,'AUTH_ON',True),patch.object(auth,'session_user',return_value=None):
                self.assertEqual(call('GET','/api/supply')[0],401)
            with patch.object(http,'AUTH_ON',True),patch.object(auth,'session_user',return_value='test'),patch.object(auth,'user_role',return_value='member'):
                self.assertEqual(call('GET','/api/supply')[0],200)
                self.assertEqual(call('POST','/api/supply',{'X-Requested-With':'supply-center'})[0],403)
            with patch.object(http,'AUTH_ON',True),patch.object(auth,'session_user',return_value='test'),patch.object(auth,'user_role',return_value='intern'):
                self.assertEqual(call('GET','/api/supply')[0],403)
            with patch.object(http,'AUTH_ON',False):
                self.assertEqual(call('POST','/api/supply')[0],403)
                self.assertEqual(call('POST','/api/supply',{'X-Requested-With':'supply-center'})[0],200)
                self.assertEqual(call('GET','/data/raw/supply-center/ledger.json')[0],404)
                self.assertEqual(call('GET','/api/product-documents?company_id=nvidia&limit=5')[0],200)
                self.assertEqual(call('GET','/api/product-documents?company_id=nvidia&bad=1')[0],400)
        finally:
            server.shutdown();server.server_close();thread.join()
