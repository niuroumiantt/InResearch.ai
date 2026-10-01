"""回流（2026-10-01）：公开 /api/news 带每条目标行的线索数，inews 据此调词与调车道。"""
import unittest
from datetime import datetime, timezone

import test_research as fixtures
from inresearch.knowledge.registry import news_leads as research_leads


class NewsFeedbackTest(unittest.TestCase):
    def setUp(self):
        self.base = fixtures.ReaderSnapshotHTTPTests('test_news_projection_uses_validated_input_without_catalog_tasks_or_private_metadata')
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)

    def publish(self, by_target, seconds=0):
        payload = self.base.payload(seconds=seconds)
        feed = {'status': 'success', 'exported_at': datetime.now(timezone.utc).isoformat(), 'items': [
            {'title_zh': '一', 'url': 'https://example.test/1', 'domain': 'example.test', 'published_at': 1700000000000,
             'target_ids': ['F.revenue.gpus.density.density.rack_spec']}]}
        if by_target is not None: feed['by_target'] = by_target
        payload['reader']['acquisition'] = {'news_feed': feed}
        self.assertEqual(self.base.post(payload)[0], 200)
        code, news = self.base.request('GET', '/api/news')
        self.assertEqual(code, 200)
        return news['feed']

    def test_counts_per_target_row_are_public_and_malformed_entries_are_dropped(self):
        feed = self.publish({'F.revenue.gpus.density.density.rack_spec': 3, 'P.x': 0, '../etc': 1, 'F.neg': -1, 'F.str': '2'})
        self.assertEqual(feed['by_target'], {'F.revenue.gpus.density.density.rack_spec': 3, 'P.x': 0})
        self.assertEqual(set(feed['items'][0]), {'title_zh', 'url', 'domain', 'published_at'}, '条目字段不变')

    def test_useful_marks_are_returned_only_as_counts_per_target_row(self):
        from inresearch.workflow import news_marks
        root = self.base.root
        feed = self.publish({})
        self.assertNotIn('useful_by_target', feed, '没有标记就不出现')
        self.assertNotIn('adopted_by_target', feed)
        news_marks.mark(root, {'url': 'https://example.test/1', 'mark': 'useful'}, 'alice', research_leads(root))
        feed = self.publish({}, seconds=1)
        self.assertEqual(feed['useful_by_target'], {'F.revenue.gpus.density.density.rack_spec': 1})
        self.assertEqual(set(feed['items'][0]), {'title_zh', 'url', 'domain', 'published_at'}, '条目不带标记与目标行')

    def test_absent_or_wrong_shape_simply_omits_the_counts(self):
        self.assertNotIn('by_target', self.publish(None))
        self.assertNotIn('by_target', self.publish(['F.a'], seconds=1))


if __name__ == '__main__':
    unittest.main()
