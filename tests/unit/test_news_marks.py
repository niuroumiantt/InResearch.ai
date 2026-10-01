"""研究员给新闻线索点「有用 / 没用」(2026-10-01)：只是线索评价，不是 C3 采用；回流只给按目标行的计数。"""
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from inresearch.paths import project_root
from inresearch.workflow import news_marks
from inresearch.interfaces import http, auth

T1, T2 = 'F.revenue.gpus.density.density.rack_spec', 'P.power.ppa.price'
LEADS = [{'url': 'https://www.example.test/a/', 'target_ids': [T1, T2, '../bad'], 'origin_pointer': 'https://sec.gov/doc/1'},
         {'url': 'https://example.test/b', 'target_ids': [T2]}]


def adopted_knowledge(url):
    return {'documents': [{'id': 'd1', 'source_url': url}],
            'evidence': [{'id': 'e1', 'document_id': 'd1', 'status': 'adopted'},
                         {'id': 'e2', 'document_id': 'd1', 'status': 'candidate'}]}


class NewsMarksTests(unittest.TestCase):
    def setUp(self):
        self.root = project_root()
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT': self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_canonical_url_treats_spellings_of_one_article_as_one(self):
        self.assertEqual(news_marks.canonical('HTTP://WWW.Example.test/a/#x'), 'https://example.test/a')
        self.assertIsNone(news_marks.canonical('javascript:alert(1)'))
        self.assertIsNone(news_marks.canonical('https://user:pw@example.test/a'))

    def test_marks_take_target_rows_from_the_current_window_and_count_only_recent_useful(self):
        out = news_marks.mark(self.root, {'url': 'https://example.test/a', 'mark': 'useful'}, 'alice', LEADS)
        self.assertEqual(out, {'ok': True, 'url': 'https://example.test/a', 'mark': 'useful'})
        news_marks.mark(self.root, {'url': 'https://example.test/b', 'mark': 'not_useful'}, 'alice', LEADS)
        self.assertEqual(news_marks.useful_by_target(self.root), {T1: 1, T2: 1}, '没用的不计,非法目标行丢掉')
        later = datetime.now(timezone.utc) + timedelta(days=news_marks.WINDOW_DAYS + 1)
        self.assertEqual(news_marks.useful_by_target(self.root, later), {}, '只算近 30 天')
        news_marks.mark(self.root, {'url': 'https://example.test/a', 'mark': 'clear'}, 'alice', LEADS)
        self.assertEqual(news_marks.useful_by_target(self.root), {})
        self.assertEqual(news_marks.mark_map(self.root), {'https://example.test/b': 'not_useful'})
        for bad in ({'url': 'ftp://x', 'mark': 'useful'}, {'url': 'https://x.test', 'mark': 'adopted'}):
            with self.assertRaises(ValueError):
                news_marks.mark(self.root, bad, 'alice', LEADS)

    def test_adopted_counts_leads_whose_url_or_origin_reached_c3_adopted_originals(self):
        valid = lambda e: e['id'] == 'e1'
        self.assertEqual(news_marks.adopted_by_target(self.root, LEADS, adopted_knowledge('https://sec.gov/doc/1'), valid), {T1: 1, T2: 1},
                         '原件指针落在已采用原件上')
        self.assertEqual(news_marks.adopted_by_target(self.root, LEADS, adopted_knowledge('https://example.test/b/'), valid), {T2: 1})
        self.assertEqual(news_marks.adopted_by_target(self.root, LEADS, adopted_knowledge('https://sec.gov/doc/1'), lambda e: False), {},
                         '审核不成立就不算采用')
        news_marks.mark(self.root, {'url': 'https://example.test/a', 'mark': 'useful'}, 'alice', LEADS)
        self.assertEqual(news_marks.adopted_by_target(self.root, [], adopted_knowledge('https://sec.gov/doc/1'), valid), {T1: 1, T2: 1},
                         '离开窗口的线索靠标记里存的目标行与原件指针继续算')

    def test_http_roles_and_private_storage(self):
        server = http.ThreadingHTTPServer(('127.0.0.1', 0), http.Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True); thread.start()
        def call(method, path, headers=None, body=None):
            c = HTTPConnection(*server.server_address)
            c.request(method, path, json.dumps(body) if body is not None else None, headers or {})
            r = c.getresponse(); data = r.read(); c.close(); return r.status, data
        good = {'X-Requested-With': 'news-mark'}
        body = {'url': 'https://example.test/a', 'mark': 'useful'}
        try:
            with patch.object(http, 'AUTH_ON', True), patch.object(auth, 'session_user', return_value='test'), patch.object(auth, 'user_role', return_value='intern'):
                self.assertEqual(call('POST', '/api/news/mark', good, body)[0], 403)
                self.assertEqual(call('GET', '/api/news/marks')[0], 403)
            with patch.object(http, 'AUTH_ON', True), patch.object(auth, 'session_user', return_value='test'), patch.object(auth, 'user_role', return_value='member'):
                self.assertEqual(call('POST', '/api/news/mark', {}, body)[0], 403, '缺自定义请求头')
                self.assertEqual(call('POST', '/api/news/mark', good, body)[0], 200)
                status, data = call('GET', '/api/news/marks')
                self.assertEqual((status, json.loads(data)['marks']), (200, {'https://example.test/a': 'useful'}))
                self.assertEqual(call('POST', '/api/news/mark', good, {'url': 'nope', 'mark': 'useful'})[0], 400)
            with patch.object(http, 'AUTH_ON', False):
                self.assertEqual(call('GET', '/data/raw/news-marks/marks.json')[0], 404, '标记本身不公开')
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
