import tempfile,unittest
from pathlib import Path
from inresearch.workflow.daily_publications import publish,projection
class DailyPublicationsTests(unittest.TestCase):
 def test_confirmed_publications_rotate_only_after_success_and_keep_history(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);a={'report_date':'2026-10-13','title':'格洛可数据中心日报｜十三日','url':'https://inews.today/c/100','html_sha256':'a'*64}
   def send(v,sha='a'*64):return publish(root,v,confirmed_sha=sha,actor='owner',verified_page_sha='b'*64)
   send(a);b=a|{'report_date':'2026-10-14','url':'https://inews.today/c/101'}
   with self.assertRaises(ValueError):send(b,'c'*64)
   self.assertEqual(projection(root)[0]['report_date'],'2026-10-13')
   send(b);self.assertTrue(send(b)['duplicate']);rows=projection(root);self.assertEqual(len(rows),2);self.assertEqual(rows[0]['report_date'],'2026-10-14');self.assertTrue(rows[0]['highlight']);self.assertFalse(rows[1]['pinned'])
   send(a|{'url':'https://inews.today/c/102'});self.assertEqual(projection(root)[0]['report_date'],'2026-10-14')
 def test_no_arbitrary_urls_or_private_metadata(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):publish(Path(tmp),{'report_date':'2026-10-14','title':'格洛可数据中心日报','url':'http://localhost/private','html_sha256':'a'*64},confirmed_sha='a'*64,actor='owner',verified_page_sha='b'*64)
   self.assertEqual(projection(Path(tmp)),[])

 def test_summary_is_not_an_eleventh_news_event(self):
  from inresearch.materials.daily_events import parse
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'data').mkdir();(root/'data/companies.json').write_text('{"records":[]}');(root/'data/projects.json').write_text('{"records":[]}')
   page=root/'2026-10-14-daily.html';page.write_text('<title>DAILY</title><h2>01 Data center opens</h2><p>Reported facts.</p><h2>今日小结</h2><p>Summary analysis.</p>')
   rows=parse(page,root);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title'],'01 Data center opens')
