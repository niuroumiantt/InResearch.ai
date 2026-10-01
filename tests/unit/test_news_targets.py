"""target_ids（2026-10-01）：inews 打的目标行标签收下来，新闻线索才能按目标行归档。"""
import json
import unittest

from inresearch.adapters import acquisition
from inresearch.adapters.news_projection import feed
from test_news_projection import NewsProjectionTest

REAL = 'F.revenue.gpus.density.density.rack_spec'


class NewsTargetIdsTest(unittest.TestCase):
    def setUp(self):
        # 复用 test_news_projection 的夹具（临时数据根、假上游、页面构造），不重跑它的用例。
        self.base = NewsProjectionTest('test_feed_v2_object_ids_are_filtered_to_the_current_skeleton')
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)

    def test_target_ids_are_kept_filtered_and_counted_per_target_row(self):
        b = self.base
        row = b.row()
        row['target_ids'] = [REAL, 'F.not.a.current.row']
        projection = b.fetch([b.page([row])])
        self.assertEqual(json.loads(projection.payload_json)['articles'][0]['target_ids'], [REAL], '不在现行目标表里的逐个过滤')
        self.assertEqual(acquisition.import_news(b.collector, projection), 1)
        metadata = json.loads(b.collector.db.execute('SELECT metadata FROM items').fetchone()[0])
        self.assertEqual(metadata['target_ids'], [REAL])
        self.assertEqual(metadata['match_status'], 'candidate', '目标行标签是线索，不是采用的证据')
        shown = feed(b.root)
        self.assertEqual(shown['items'][0]['target_ids'], [REAL])
        self.assertEqual(shown['by_target'], {REAL: 1})

    def test_malformed_target_ids_reject_the_page_and_absence_is_fine(self):
        b = self.base
        for value in (REAL, [REAL, REAL], [1], ['X.bad'], ['F.' + 'a' * 130], [f'F.r{i}' for i in range(33)]):
            bad = b.row(); bad['target_ids'] = value
            with self.assertRaises(ValueError, msg=repr(value)[:40]):
                b.fetch([b.page([bad])])
        plain = json.loads(b.fetch([b.page([b.row()])]).payload_json)['articles'][0]
        self.assertIsNone(plain['target_ids'])


if __name__ == '__main__':
    unittest.main()
