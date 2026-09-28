"""Acquisition identity, provenance, boundaries and failure semantics."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from inresearch.adapters import acquisition as a

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
        def fail():raise ValueError('feed_unreachable')
        with self.assertRaises(ValueError):self.c.run('inews',fail)
        summary=a.summary(self.root);last=summary['sources']['inews']['last_run']
        self.assertEqual(last['status'],'failed');self.assertEqual(last['error_code'],'feed_unreachable')
        self.assertEqual(summary['retired_sources'],['sec','gpu'])
    def test_retired_collectors_are_gone_but_history_stays_readable(self):
        for name in ('sec','gpu','fetch','summarize_offers'):self.assertFalse(hasattr(a,name),name)
        ident=self.c.item('sec','legacy','filing_document','https://www.sec.gov/a','legacy',{})
        self.assertEqual(a.summary(self.root)['sources']['sec']['items'],1)
        self.assertEqual(a.ACTIVE_SOURCES,('inews','fetchspec'))
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
if __name__=='__main__':unittest.main()
