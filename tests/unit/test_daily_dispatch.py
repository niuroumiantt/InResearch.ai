import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from inresearch.workflow import daily_dispatch, project_pipeline
from inresearch.materials import daily_bundle
from inresearch.paths import project_root
import test_daily_bundle as bundles
from test_continuous_reader import Model, Clock
from inresearch.workflow.reader import Reader


class DailyDispatchTests(unittest.TestCase):
    def test_received_daily_event_outside_recent_500_remains_publicly_reachable(self):
        from inresearch.knowledge import registry
        pipeline={'records':[{'id':'recent-'+str(i),'title':'recent','events':[{'url':'https://example.org/'+str(i)}]} for i in range(500)]}
        daily={'id':'daily-event-old','title':'Old daily title','accepted_at':'2026-10-01','report_date':'2026-10-01',
               'reported_stage':'planning','constraints':[],'target_ids':[], 'urls':['https://example.org/old'],
               'private_editorial_body':'never expose','document_sha256':['private']}
        with patch.object(registry,'_snapshot_inputs',return_value=[{}, {}, {}, {}, {}]),patch.object(registry,'_reader_state',return_value={'acquisition':{'project_pipeline':pipeline,'daily_delivery':{'news':[daily]}}}):
            out=registry.build_news(project_root())['pipeline']
        self.assertEqual(len(out['records']),501)
        self.assertEqual(out['records'][-1]['id'],'daily-daily-event-old')
        self.assertNotIn('private',json.dumps(out))
    def delivered(self, base):
        folder=base/'bundle'; folder.mkdir()
        bundles.DailyBundleTests().bundle(folder, True)
        data=base/'data'
        daily_bundle.receive(folder,data,project_root())
        return data

    def test_news_delivers_before_reading_identity_and_capacity_review(self):
        before=(project_root()/'data/projects.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            data=self.delivered(Path(tmp))
            view=daily_dispatch.projection(data)
            self.assertEqual(view['news_total'],1)
            tasks={r['kind']:r['state'] for r in view['records'][0]['tasks']}
            self.assertEqual(tasks['news'],'ready_for_snapshot')
            self.assertEqual(tasks['identity'],'awaiting_identity')
            self.assertEqual(tasks['capacity'],'awaiting_capacity_review')
            public=project_pipeline.projection(data/'acquisition')['records'][0]
            self.assertEqual(public['origin'],'daily_html')
            self.assertIsNone(public['site_id']);self.assertIsNone(public['reported_capacity'])
            serialized=json.dumps(public,ensure_ascii=False)
            self.assertNotIn('Phase 1 delivers',serialized)
            self.assertNotIn('IT负荷60MW',serialized)
            self.assertNotIn('document_sha256',serialized)
            from inresearch.knowledge import registry
            with patch.object(registry, '_reader_state', return_value={'acquisition':{'project_pipeline':project_pipeline.projection(data/'acquisition')}}):
                published=registry.build_news(project_root())['pipeline']
                self.assertEqual(published['progress']['daily_news'],1)
                self.assertEqual(published['records'][0]['origin'],'daily_html')
                self.assertNotIn('IT负荷60MW',json.dumps(published,ensure_ascii=False))
            self.assertEqual(daily_dispatch.projection(data),view)
        self.assertEqual(before,(project_root()/'data/projects.json').read_bytes())

    def test_unbound_source_missing_receipt_and_wrong_html_do_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=self.delivered(Path(tmp))
            path=data/'acquisition/daily-events.json'; ledger=json.loads(path.read_text())
            row=next(iter(ledger['records'].values()))
            for source in row['sources']:source['document_sha256']='f'*64
            path.write_text(json.dumps(ledger))
            self.assertEqual(daily_dispatch.news_records(data),[])
            self.assertEqual(daily_dispatch.projection(data)['records'][0]['delivery_lane'],'source_binding')
            row['sources']=[{'label':'public-looking URL','urls':['https://example.org/campus']}]
            path.write_text(json.dumps(ledger));self.assertEqual(daily_dispatch.news_records(data),[])
            row['sources']=[];path.write_text(json.dumps(ledger))
            self.assertEqual(daily_dispatch.projection(data)['records'][0]['delivery_lane'],'source')
            for receipt in (data/'material-reviews/daily-deliveries').glob('*.json'):receipt.unlink()
            self.assertEqual(daily_dispatch.news_records(data),[])

    def test_news_dispatch_receives_slots_without_changing_depth_or_oldest_share(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);data=self.delivered(base);clock=Clock()
            raw=data/'raw-materials/old.txt';raw.parent.mkdir(parents=True,exist_ok=True);raw.write_text('older long material')
            model=Model();r=Reader(data,base/'state',project_root(),model,0,200,clock).initialize()
            try:
                with r.worker_session(): r.scan()
                old=r.conn.execute("SELECT d.doc_id FROM documents d WHERE suffix='.txt'").fetchone()[0]
                r.conn.execute('UPDATE reading_runs SET priority=9 WHERE doc_id=?',(old,))
                r.conn.execute("UPDATE meta SET value='1' WHERE key='dispatch_count'")
                first=r.claim();lane=json.loads(r.conn.execute("SELECT value FROM meta WHERE key='last_dispatch'").fetchone()[0])
                self.assertEqual(lane['lane'],'news');self.assertNotEqual(first['doc_id'],old)
                self.assertEqual(r.doc(first['doc_id'])['phase'],'extract')
                self.assertEqual(r.doc(old)['priority'],9)
                r.conn.execute("UPDATE meta SET value='4' WHERE key='dispatch_count'")
                self.assertEqual(r.claim()['doc_id'],old)
                self.assertFalse(model.calls,'claim never calls a model or fakes a reading')
            finally:r.close()

    def test_broken_daily_ledger_does_not_block_unrelated_reader_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);data=base/'data';raw=data/'raw-materials/old.txt'
            raw.parent.mkdir(parents=True);raw.write_text('unrelated source')
            r=Reader(data,base/'state',project_root(),Model(),0,200,Clock()).initialize()
            try:
                with r.worker_session():r.scan()
                path=data/'acquisition/daily-events.json';path.parent.mkdir(exist_ok=True);path.write_text('{broken')
                self.assertIsNotNone(r.claim())
            finally:r.close()

    def test_finish_stage_has_reserved_slot_and_news_cannot_bypass_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);data=self.delivered(base)
            r=Reader(data,base/'state',project_root(),Model(),0,200,Clock(),claim_min_priority=9).initialize()
            try:
                with r.worker_session():r.scan()
                r.conn.execute('UPDATE reading_runs SET priority=7')
                r.conn.execute("UPDATE meta SET value='1' WHERE key='dispatch_count'")
                self.assertIsNone(r.claim())
                r.conn.execute('UPDATE reading_runs SET priority=9')
                r.conn.execute("UPDATE jobs SET stage='organize'")
                job=r.claim();self.assertEqual(job['stage'],'organize')
                self.assertEqual(json.loads(r.conn.execute("SELECT value FROM meta WHERE key='last_dispatch'").fetchone()[0])['lane'],'finish')
            finally:r.close()
