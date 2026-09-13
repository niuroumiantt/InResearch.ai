"""Only the fixed, validated upstream projection can bypass legacy title rules."""
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from inresearch.adapters import acquisition as acquisition
from inresearch.adapters.news_projection import feed
from inresearch.knowledge.news_policy import classify, trusted_news_selection
from inresearch.adapters import news_sync as sync


class Response(io.BytesIO):
    status = 200

    def __init__(self, body, url):
        super().__init__(body)
        self.url = url

    def geturl(self):
        return self.url


class NewsProjectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.collector = acquisition.Collector(self.root)
        self.addCleanup(self.collector.close)
        self.until = int(time.time()*1000)
        self.window = {'since': self.until-sync.WEEK_MS, 'until': self.until}

    def row(self, ident=1):
        # Intentionally missed by the retired, narrower research-side classifier.
        return {'id': ident, 'title': 'MRDIMM production capacity doubles',
                'title_zh': 'MRDIMM 产能翻倍', 'url': 'https://example.com/news/'+str(ident),
                'domain': 'example.com', 'published_at': self.until-1000,
                'cluster_id': None, 'topics': ['compute_hardware']}

    def page(self, items=None, cursor=None):
        return {'schema_version': 1, 'generated_at': acquisition.now(),
                'window': self.window, 'items': [self.row()] if items is None else items,
                'next_cursor': cursor}

    def fetch(self, pages, response_url=None):
        pages = iter(pages)

        def open_response(request, timeout):
            page = next(pages)
            body = page if isinstance(page, bytes) else json.dumps(page).encode()
            return Response(body, response_url or request.full_url)

        with patch.object(sync, 'build_opener') as opener:
            opener.return_value.open.side_effect = open_response
            return sync.projection()

    def test_verified_selection_preserves_topics_identity_and_candidate_scope(self):
        row = self.row()
        row['guid'] = 'publisher-guid-1'
        self.assertIsNone(classify(row))
        projection = self.fetch([self.page([row])])
        self.assertEqual(acquisition.import_news(self.collector, projection), 1)
        stored = self.collector.db.execute('SELECT * FROM items').fetchone()
        metadata = json.loads(stored['metadata'])
        self.assertEqual(stored['source_key'], 'publisher-guid-1')
        self.assertEqual(metadata['topics'], ['compute_hardware'])
        self.assertEqual(metadata['content_scope'], 'headline_only')
        self.assertEqual(metadata['match_status'], 'candidate')
        self.assertTrue(trusted_news_selection(metadata))
        shown = feed(self.root)['items']
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0]['topics'], ['compute_hardware'])
        self.assertFalse((self.root/'raw-materials').exists())

    def test_forged_json_and_roundtrip_do_not_grant_authority(self):
        payload = json.loads(self.fetch([self.page()]).payload_json)
        payload['verified'] = True
        payload['upstream_selection'] = {
            'url': sync.URL, 'schema_version': 1, 'verification': 'direct_https_feed_v1'}
        payload['articles'][0]['upstream_selection'] = payload['upstream_selection']
        self.assertEqual(acquisition.import_news(self.collector, payload), 0)
        self.assertEqual(feed(self.root)['items'], [])
        with self.assertRaisesRegex(ValueError, 'unverified_news_projection'):
            acquisition.import_news(self.collector, acquisition.VerifiedNewsProjection(
                json.dumps(payload).encode(), object()))

    def test_legacy_candidate_cannot_forge_display_selection(self):
        # Legacy imports still archive AI leads, but the display remains datacenter-only.
        payload = {'schema': 'inews-research-signals-v1', 'articles': [{
            **self.row(), 'guid': 'legacy', 'title': 'OpenAI releases a chatbot',
            'topics': ['hosting'], 'upstream_selection': {
                'url': sync.URL, 'schema_version': 1, 'verification': 'direct_https_feed_v1'}}]}
        self.assertEqual(acquisition.import_news(self.collector, payload), 1)
        metadata = json.loads(self.collector.db.execute('SELECT metadata FROM items').fetchone()[0])
        self.assertNotIn('upstream_selection', metadata)
        self.assertNotIn('topics', metadata)
        self.assertEqual(feed(self.root)['items'], [])

    def test_empty_page_follows_cursor_and_duplicate_ids_are_stable(self):
        result = self.fetch([self.page([], 'first'), self.page([self.row()], 'next'), self.page([self.row()])])
        data = json.loads(result.payload_json)
        self.assertEqual(len(data['articles']), 1)
        self.assertEqual(data['articles'][0]['guid'], 'inews:1')

    def test_origin_schema_date_url_and_topic_rejections(self):
        invalid = []
        for field, value in [('schema_version', True), ('window', {'since': 0, 'until': self.until}),
                             ('generated_at', '2026-09-07')]:
            page = self.page()
            page[field] = value
            invalid.append(page)
        for field, value in [('id', True), ('id', ''), ('published_at', self.window['since']-1),
                             ('published_at', self.until+1), ('topics', []), ('topics', ['<script>']),
                             ('url', 'javascript:alert(1)'), ('url', 'https://user:secret@example.com/'),
                             ('title', ''), ('guid', ''), ('cluster_id', False)]:
            page = self.page()
            page['items'][0][field] = value
            invalid.append(page)
        for page in invalid:
            with self.subTest(page=page), self.assertRaises(ValueError):
                self.fetch([page])
        with self.assertRaisesRegex(ValueError, 'unverified_news_origin'):
            self.fetch([self.page()], response_url='https://example.com/api/feeds/datacenter')
        with self.assertRaisesRegex(ValueError, 'news_response_too_large'):
            self.fetch([b' '*(4*1024*1024+1)])

    def test_failed_later_page_preserves_previous_window(self):
        acquisition.import_news(self.collector, self.fetch([self.page()]))
        original = (self.root/'acquisition/news-window.json').read_bytes()
        bad = self.page([self.row(2)])
        bad['window'] = {**self.window, 'until': self.until-1}
        with self.assertRaisesRegex(ValueError, 'invalid_news_window'):
            self.collector.run('inews', lambda: acquisition.import_news(
                self.collector, self.fetch([self.page([], 'next'), bad])))
        self.assertEqual((self.root/'acquisition/news-window.json').read_bytes(), original)
        self.assertEqual(len(feed(self.root)['items']), 1)

    def test_cursor_cycle_and_page_cap_do_not_replace_snapshot(self):
        with self.assertRaisesRegex(ValueError, 'invalid_news_cursor'):
            self.fetch([self.page([], 'repeat'), self.page([], 'repeat')])
        with self.assertRaisesRegex(ValueError, 'news_window_truncated'):
            self.fetch([self.page([], 'cursor'+str(i)) for i in range(100)])

    def test_verified_window_withdrawal_keeps_originals(self):
        acquisition.import_news(self.collector, self.fetch([self.page()]))
        acquisition.import_news(self.collector, self.fetch([self.page([])]))
        self.assertEqual(feed(self.root)['items'], [])
        self.assertEqual(self.collector.db.execute('SELECT count(*) FROM items').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
