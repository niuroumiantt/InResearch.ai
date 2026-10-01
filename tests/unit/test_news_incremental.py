"""增量同步（2026-10-01）：首轮整窗，之后拉 /changes?since= 合并进现行窗口；拉不成就本轮整窗兜底。"""
import json
import unittest
from unittest.mock import patch

from inresearch.adapters import news_sync as sync
from inresearch.adapters.news_projection import feed
import test_news_projection as fixtures


class NewsIncrementalTest(unittest.TestCase):
    def setUp(self):
        self.base = fixtures.NewsProjectionTest('test_feed_v2_object_ids_are_filtered_to_the_current_skeleton')
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.urls = []

    def changes_page(self, since, items, until):
        return {'schema_version': 1, 'generated_at': '2026-10-01T00:00:00Z', 'since': since, 'until': until,
                'items': items, 'next_cursor': None, 'next_since': until}

    def run_sync(self, pages, clock):
        pages = iter(pages)

        def open_response(request, timeout):
            self.urls.append(request.full_url)
            page = next(pages)
            body = page if isinstance(page, bytes) else json.dumps(page).encode()
            return fixtures.Response(body, request.full_url)

        with patch.object(sync, 'build_opener') as opener:
            opener.return_value.open.side_effect = open_response
            return sync.sync(self.base.collector, clock=clock)

    def state(self):
        return json.loads((self.base.collector.home / sync.STATE).read_text())

    def test_first_run_is_full_then_changes_add_update_and_withdraw(self):
        b = self.base
        at = b.until + 1000
        self.assertEqual(self.run_sync([b.page([b.row(1), b.row(2)])], at), ('full', 2))
        self.assertIn('hours=168', self.urls[-1])
        self.assertEqual(self.state(), {'next_since': b.until, 'full_at': at})
        self.assertEqual(len(feed(b.root)['items']), 2)

        added, updated = b.row(3), b.row(1)
        updated['title_zh'] = '改过的标题'
        later = b.until + 60_000
        page = self.changes_page(b.until, [added, updated, {'id': 2, 'withdrawn': True, 'updated_at': later}], later)
        self.assertEqual(self.run_sync([page], later + 1000), ('changes', 2))
        self.assertIn('/changes?since=' + str(b.until), self.urls[-1])
        self.assertEqual(self.state(), {'next_since': later, 'full_at': at}, '增量不改整窗时间')
        shown = {i['url']: i for i in feed(b.root)['items']}
        self.assertEqual(sorted(shown), ['https://example.com/news/1', 'https://example.com/news/3'], '撤下的 2 号离开窗口')
        self.assertEqual(shown['https://example.com/news/1']['title_zh'], '改过的标题')

    def test_stale_state_or_failed_changes_fall_back_to_the_full_window(self):
        b = self.base
        at = b.until + 1000
        self.run_sync([b.page([b.row(1)])], at)
        # 增量页坏了（since 对不上）：本轮整窗重拉，不卡住。
        bad = self.changes_page(b.until - 1, [], b.until + 5000)
        self.assertEqual(self.run_sync([bad, b.page([b.row(1)])], at + 60_000), ('full', 1))
        self.assertEqual(self.state()['full_at'], at + 60_000)
        # 距上次整窗超过 6 小时：直接整窗。
        self.urls.clear()
        self.assertEqual(self.run_sync([b.page([b.row(1)])], at + 60_000 + sync.FULL_EVERY_MS), ('full', 1))
        self.assertTrue(all('hours=168' in u for u in self.urls))

    def test_changes_skip_items_older_than_the_week_and_reject_bad_tombstones(self):
        b = self.base
        at = b.until + 1000
        self.run_sync([b.page([b.row(1)])], at)
        old = b.row(9); old['published_at'] = b.until - sync.WEEK_MS - 10_000
        later = b.until + 60_000
        self.assertEqual(self.run_sync([self.changes_page(b.until, [old], later)], later + 1000), ('changes', 0))
        with self.assertRaises(ValueError):
            with patch.object(sync, 'build_opener') as opener:
                opener.return_value.open.side_effect = lambda r, timeout: fixtures.Response(json.dumps(
                    self.changes_page(later, [{'id': 'x', 'withdrawn': True}], later + 1)).encode(), r.full_url)
                sync.changes(later)


if __name__ == '__main__':
    unittest.main()
