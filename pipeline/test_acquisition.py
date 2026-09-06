"""Acquisition identity, provenance, boundaries and failure semantics."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import acquisition as a

class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.c=a.Collector(self.root);self.addCleanup(self.c.close)
    def test_archive_preserves_revisions_and_is_idempotent(self):
        i=self.c.item('sec','accession','filing_document','https://www.sec.gov/a','a',{})
        first=self.c.archive(i,b'first','.html',{'url':'https://www.sec.gov/a'})
        self.c.archive(i,b'first','.html',{});self.c.archive(i,b'second','.html',{})
        rows=self.c.db.execute('SELECT * FROM observations').fetchall();self.assertEqual(len(rows),2)
        self.assertEqual((self.root/rows[0]['relative_path']).read_bytes(),b'first')
        self.assertEqual(rows[0]['sha256'],first)
        self.assertFalse((self.root/'raw-materials').exists())
        self.assertFalse((self.root/'prices.json').exists())
    def test_unknown_question_fails_before_inserting(self):
        with self.assertRaisesRegex(ValueError,'unknown_question'):self.c.item('sec','x','x','x','x',{},question='invented')
        self.assertEqual(self.c.db.execute('SELECT count(*) FROM items').fetchone()[0],0)
    def test_top_down_link_is_not_an_adopted_answer(self):
        i=self.c.item('sec','x','x','x','x',{},question='M01-Q01')
        row=self.c.db.execute('SELECT * FROM links').fetchone()
        self.assertEqual(row['item_id'],i);self.assertEqual(row['direction'],'top_down')
        self.assertEqual(self.c.db.execute('SELECT state FROM items').fetchone()[0],'discovered')
    def test_failure_is_recorded_and_not_success(self):
        def fail():raise ValueError('vast_api_key_missing')
        with self.assertRaises(ValueError):self.c.run('gpu',fail)
        last=a.summary(self.root)['sources']['gpu']['last_run']
        self.assertEqual(last['status'],'failed');self.assertEqual(last['error_code'],'vast_api_key_missing')
    def test_news_title_is_only_a_lead_and_duplicate_is_not_new(self):
        payload={'schema':'inews-research-signals-v1','articles':[{'guid':'g1','id':1,'title':'NVIDIA data center GPU capacity','url':'https://example.com/1','title_zh':'英伟达数据中心容量'}]}
        self.assertEqual(a.import_news(self.c,payload),1);a.import_news(self.c,payload)
        self.assertEqual(self.c.db.execute('SELECT count(*) FROM items').fetchone()[0],1)
        row=self.c.db.execute('SELECT metadata FROM items').fetchone()
        self.assertEqual(json.loads(row[0])['content_scope'],'headline_only')
        self.assertFalse((self.root/'raw-materials').exists())
    def test_news_export_excludes_identity_and_hidden_rows(self):
        db=self.root/'news.sqlite';c=sqlite3.connect(db)
        cols='id,guid,url,title,title_zh,title_zh_profile,domain,publisher,published_at,first_seen_at,lang,cluster_id,relevance,genre,relevant,hidden_at'
        c.execute('CREATE TABLE articles('+','.join(x+' TEXT' for x in cols.split(','))+')')
        c.execute('CREATE TABLE users(secret TEXT)');c.execute("INSERT INTO users VALUES('DO_NOT_EXPORT')")
        row=[1,'g','https://example.com','GPU news',None,None,'example.com','x',int(a.time.time()*1000),int(a.time.time()*1000),'en',1,8,'compute',1,None]
        c.execute('INSERT INTO articles VALUES('+','.join('?' for _ in row)+')',row)
        hidden=list(row);hidden[0]=2;hidden[-1]=123;c.execute('INSERT INTO articles VALUES('+','.join('?' for _ in row)+')',hidden);c.commit();c.close()
        export=a.export_news(db);self.assertEqual(len(export['articles']),1);self.assertNotIn('DO_NOT_EXPORT',json.dumps(export))
    def test_quote_contract_rejects_mixed_and_invalid_prices(self):
        valid={'id':1,'gpu_name':'H100 SXM','num_gpus':1,'rentable':True,'rented':False,'dph_total':2.5,'is_bid':False}
        rows=[valid,{**valid,'id':2,'num_gpus':8},{**valid,'id':3,'dph_total':float('nan')},{**valid,'id':4,'is_bid':True},valid]
        s=a.summarize_offers(rows,'H100 SXM');self.assertEqual(s['sample_n'],1);self.assertEqual(s['median'],2.5)
        self.assertEqual(s['rental_type'],'on-demand');self.assertEqual(s['acceptance'],'candidate')
    def test_missing_gpu_key_does_not_fetch(self):
        with patch.dict(a.os.environ,{'VAST_API_KEY':''}),patch.object(a,'fetch') as fetch:
            with self.assertRaisesRegex(ValueError,'vast_api_key_missing'):a.gpu(self.c,'H100 SXM')
            fetch.assert_not_called()
    def test_network_origin_allowlist(self):
        for url in ['http://data.sec.gov/a','https://localhost/a','https://user:secret@www.sec.gov/a','https://www.sec.gov.evil/a']:
            with self.assertRaises(ValueError):a.fetch(url)
    def test_sec_keeps_accession_and_raw_document(self):
        data={'cik':1045810,'filings':{'recent':{'form':['10-Q'],'accessionNumber':['0001-26-001'],'primaryDocument':['quarter.htm'],'filingDate':['2026-09-01']}}}
        with patch.object(a,'fetch',side_effect=[a.encoded(data),b'<html>Original table</html>']),patch.object(a.time,'sleep'):
            self.assertEqual(a.sec(self.c,'nvidia',1),1)
        docs=self.c.db.execute("SELECT * FROM items WHERE kind='filing_document'").fetchall();self.assertEqual(len(docs),1)
        self.assertIn('0001-26-001',docs[0]['source_key']);self.assertEqual(docs[0]['state'],'archived')
if __name__=='__main__':unittest.main()
