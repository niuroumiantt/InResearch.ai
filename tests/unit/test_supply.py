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
    def test_truncated_match_window_cannot_hide_received_reading_results(self):
        reader={'documents':[{'doc_id':'done','content_sha256':'outside-window','title':'received report',
                             'read_status':'complete','stored_path':'private/original.pdf'},
                            {'doc_id':'pending','content_sha256':'pending','read_status':'running'}],
                'statements':[{'document_id':'done','text':'received candidate'}],
                'evidence':[{'document_id':'done','quote':'original text','page_index':2}]}
        matched={'truncated':True,'total':5917,'records':[{'sha256':'different'}]}
        result=supply.reading_deliveries(reader,matched)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['claims'],['received candidate'])
        self.assertEqual(result[0]['quotes'],[{'quote':'original text','page_index':2}])
        self.assertEqual(result[0]['acceptance'],'candidate_only')
        self.assertNotIn('private',json.dumps(result))

    def test_reading_deliveries_keep_received_complete_scope_and_hide_paths(self):
        reader={'documents':[{'doc_id':'a','content_sha256':'a','title':'done','read_status':'complete','stored_path':'private/original.pdf','coverage':{'gap_pages':[2]}},
                             {'doc_id':'b','content_sha256':'b','read_status':'running'},
                             {'doc_id':'old','content_sha256':'old','read_status':'complete'}],
                'statements':[{'document_id':'a','text':'candidate finding'},{'document_id':'old','text':'out of scope'}],
                'evidence':[{'document_id':'a','quote':'literal source','page_index':16,'private_path':'secret'}]}
        out=supply.reading_deliveries(reader,{'records':[{'sha256':'a'},{'sha256':'b'}]})
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['claims'],['candidate finding'])
        self.assertEqual(out[0]['quotes'],[{'quote':'literal source','page_index':16}])
        self.assertEqual(out[0]['coverage']['gap_pages'],[2])
        self.assertEqual(out[0]['acceptance'],'candidate_only')
        self.assertNotIn('private',json.dumps(out))

    def test_reader_report_pages_cross_export_and_supply_without_mutating_report(self):
        from inresearch.delivery.reader_export import project_document
        doc = {'doc_id':'a', 'sha256':'a', 'original_name':'paper.pdf',
               'original_rel':'originals/paper.pdf', 'library_rel':None,
               'chunks_total':1, 'chunks_read':1, 'state':'complete',
               'revision_id':'rev-a', 'report_rel':'report.json', 'report_sha256':'b'}
        report = {'coverage':{'complete':True, 'pages_total':17},
                  'evidence':[{'quote':'first page', 'page_index':1},
                              {'quote':'last page', 'page_index':17}]}
        exported = project_document(doc, [], report, {})
        received = {'documents':[exported['entry']], 'evidence':exported['evidence']}
        out = supply.reading_deliveries(received, {'records':[{'sha256':'a'}]})
        self.assertEqual(out[0]['quotes'], [{'quote':'first page', 'page_index':0},
                                          {'quote':'last page', 'page_index':16}])
        self.assertEqual([e['page_index'] for e in report['evidence']], [1, 17])

    def test_snapshot_reads_deliveries_from_received_knowledge_not_status(self):
        runtime={'reader':{'acquisition':{'material_matches':{'records':[{'sha256':'a'}]}}},
                 'knowledge':{'documents':[{'id':'a','content_sha256':'a','title':'delivered','read_status':'complete'}],
                              'statements':[{'document_id':'a','text':'actual delivered finding'}]}}
        with patch('inresearch.knowledge.registry._snapshot_inputs',return_value=[runtime]):
            out=supply.snapshot(self.root)
        self.assertEqual(out['reading_deliveries'][0]['claims'],['actual delivered finding'])

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
                     target_id='F.cost.energy.price.power_price.state_industrial',
                     question_id='', title='工业电价原件', scope='美国州级工业电价与统计期',
                     acceptance='原文、定位与口径', provider_id='fetchstat',
                     execution_mode='continuous', execution_host='aws')
        value.update(changes)
        return value

    def test_persistence_replay_and_conflict(self):
        initial = supply.snapshot(self.root)
        self.assertEqual(initial['demands'], [])
        targets = initial['generated_targets']
        self.assertEqual(targets['provider_id'], 'fetchspec')
        self.assertEqual(targets['total'], len(targets['records']))
        self.assertTrue(targets['records'])
        self.assertTrue(all(row['team'] == 'fetchspec' for row in targets['records']))
        self.assertEqual(targets['total'], targets['sourced'] + targets['assumed'] + targets['delivered'] + targets['needed'])
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
            pages_total INTEGER,chunks_total INTEGER,chunks_read INTEGER,report_sha256 TEXT,manifest_sha256 TEXT);
            CREATE VIEW current_readings AS SELECT d.sha256,r.* FROM reading_runs r JOIN documents d USING(doc_id) WHERE r.base_revision_id IS NOT NULL;''')
        db.execute('INSERT INTO documents VALUES(?,?)', ('doc-1', sha))
        db.execute('INSERT INTO reading_runs VALUES(?,?,?,?,?,?,?,?,?)',
                   ('doc-1', None, 'failed', 'read', 2, 3, 1, None, None))
        db.execute('INSERT INTO reading_runs VALUES(?,?,?,?,?,?,?,?,?)',
                   ('doc-1', 'activated-successor', 'complete', 'complete', 2, 3, 3, 'report', 'sealed'))
        db.commit(); db.close()
        with patch.dict(os.environ, {'READER_DATA_ROOT': str(reader)}):
            delivery = supply.snapshot(self.root)['deliveries'][0]
        self.assertEqual(delivery['reading']['candidate_ready'], 1)
        self.assertEqual(delivery['reading']['blocked'], 0)
        self.assertEqual(delivery['reading']['adoption'], 'not_inferred')

    def test_reader_unavailable_is_distinct_from_unregistered_and_queries_are_bounded(self):
        reader = Path(self.tmp.name) / 'reader-empty'
        def project():
            deliveries=[{'items':[{'sha256':str(i),'reader_handoff':'eligible'} for i in range(1001)]}]
            supply._attach_reader_status(deliveries)
            return deliveries[0]['reading']
        with patch.dict(os.environ, {'READER_DATA_ROOT': str(reader)}):
            self.assertEqual(project()['status_unavailable'],1001)
            (reader/'catalog').mkdir(parents=True)
            db=sqlite3.connect(reader/'catalog/catalog.sqlite')
            db.execute('CREATE TABLE current_readings(sha256,doc_id,state,phase,pages_total,chunks_total,chunks_read,report_sha256,manifest_sha256)')
            db.commit(); db.close()
            observed=project()
            self.assertEqual(observed['not_registered'],1001)
            self.assertEqual(observed['status_unavailable'],0)

    def test_single_target_authority_and_concurrent_revision(self):
        req=self.request();supply.mutate(self.root,req,'admin')
        demand=supply.read(self.root)['demands'][0]['id']
        with self.assertRaises(ValueError):
            supply.mutate(self.root, self.request(action='assign', demand_id=demand, provider_id='local', expected_revision=1,
                                                   execution_mode='assisted', execution_host='macmini'), 'admin')
        results=[]
        def add():
            try:
                supply.mutate(self.root,self.request(expected_revision=1),'admin');results.append('saved')
            except supply.Conflict:
                results.append('conflict')
        threads=[threading.Thread(target=add) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertCountEqual(results,['saved','conflict'])
        self.assertEqual(len(supply.read(self.root)['tasks']),2)
        self.assertTrue(all(t['status']=='planned' for t in supply.read(self.root)['tasks']))
        self.assertEqual(supply.read(self.root)['tasks'][1]['target_id'], req['target_id'])

    def test_new_demand_requires_target_and_provider_host_follows_target(self):
        for change in ({'question_id': 'M01-Q01'}, {'target_id': ''}, {'target_id': 'unknown'}, {'provider_id': 'inews'},
                       {'execution_host': 'macmini'}):
            with self.assertRaises(ValueError):
                supply.mutate(self.root, self.request(**change), 'admin')
        self.assertEqual(supply.read(self.root)['revision'], 0)
        # Public vendor collection runs continuously on its registered macmini.
        req = self.request(target_id='P.gpu.spec', question_id='', provider_id='fetchspec',
                           execution_mode='continuous', execution_host='macmini')
        supply.mutate(self.root, req, 'admin')
        self.assertEqual(supply.read(self.root)['tasks'][0]['execution_host'], 'macmini')

    def test_unbound_historical_demand_is_preserved_but_cannot_gain_new_task(self):
        path = supply.ledger_path(self.root)
        path.parent.mkdir(parents=True)
        state = {'version': 1, 'revision': 0, 'demands': [{'id': 'old', 'question_id': 'M01-Q01'}], 'tasks': [], 'operations': []}
        path.write_text(json.dumps(state))
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            supply.mutate(self.root, self.request(action='assign', demand_id='old'), 'admin')
        self.assertEqual(path.read_bytes(), before)

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
