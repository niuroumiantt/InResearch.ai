import unittest
import tempfile
import time
from acquisition import Collector, import_news
from datacenter_news import classify, feed

class DatacenterNewsTest(unittest.TestCase):
    def test_boundary(self):
        for title in ['New data centre approved without AI tenant','企业级 SSD 需求增长','NAND demand driven by servers','HBM4 production expands','800G optics demand']:
            self.assertTrue(classify({'title':title}),title)
        for title in ['OpenAI releases new chatbot','Nvidia stock price target raised','Samsung smartphone NAND launch','SSD gaming sale','Arm launches mobile CPU','HBM Nigeria commissions high-capacity CNG station in Cross River, targets 250 trucks daily']:
            self.assertFalse(classify({'title':title}),title)
    def test_window_withdrawal_and_cluster(self):
        with tempfile.TemporaryDirectory() as root:
            c=Collector(root)
            def row(i,cluster=None):return {'id':i,'guid':str(i),'title':'New data center opens','url':'https://example.com/'+str(i),'published_at':int(time.time()*1000),'cluster_id':cluster}
            payload={'schema':'inews-research-signals-v1','exported_at':'2026-09-06T10:00:00Z','articles':[row(1,8),row(2,8),row(3)]}
            c.run('inews',lambda:import_news(c,payload))
            self.assertEqual(len(feed(root)['items']),2)
            payload['articles']=[row(3)]
            c.run('inews',lambda:import_news(c,payload))
            self.assertEqual(len(feed(root)['items']),1)
            self.assertEqual(c.db.execute('select count(*) from items').fetchone()[0],3)
            c.close()

    def test_backup_restore(self):
        from backup_acquisition import backup
        from pathlib import Path
        import sqlite3
        with tempfile.TemporaryDirectory() as root:
            c=Collector(root);ident=c.item('inews','test','news_lead','https://example.com','test',{})
            c.archive(ident,b'headline','.json',{});c.close()
            dest=Path(root)/'backup';self.assertEqual(backup(root,dest),2)
            restored=sqlite3.connect(dest/'catalog.sqlite')
            self.assertEqual(restored.execute('pragma integrity_check').fetchone()[0],'ok')
            self.assertEqual(restored.execute('select count(*) from observations').fetchone()[0],1)
            restored.close()
