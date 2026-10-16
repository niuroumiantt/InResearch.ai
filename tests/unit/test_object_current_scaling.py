import copy
from datetime import datetime, timedelta, timezone
import unittest

from inresearch.knowledge.object_observations import current


class CurrentOrderingTests(unittest.TestCase):
    def row(self, ident, value, **changes):
        return dict(id=ident, object_id='company:one', metric='capacity', scope={},
                    unit='MW', value=value, kind='reported',
                    registration={'status': 'unverified'},
                    recorded_at='2026-10-01T12:00:00Z',
                    source={'published_at': '2026-10-01'}, **changes)

    def test_same_clock_selects_later_append_and_retains_conflict_without_mutation(self):
        records = [self.row('first', 10), self.row('last', 20)]
        doc = {'records': records}
        original = copy.deepcopy(doc)
        result = current(doc, '2026-10-12')
        self.assertEqual([r['id'] for r in result[0]['current']], ['last'])
        self.assertEqual(set(result[0]['conflicts']), {'first', 'last'})
        self.assertEqual(doc, original)

    def test_many_independent_objects_keep_append_order_for_each_tied_history(self):
        rows = []
        for i in range(1200):
            for suffix in ('old', 'new'):
                row = self.row(f'{i}-{suffix}', suffix)
                row['object_id'] = f'company:{i}'
                rows.append(row)
        result = current({'records': rows}, '2026-10-12')
        self.assertEqual(len(result), 1200)
        self.assertEqual([g['current'][0]['id'] for g in result],
                         [f'{i}-new' for i in range(1200)])
        self.assertTrue(all(len(g['conflicts']) == 2 for g in result))

    def test_large_single_metric_history_selects_latest_without_pairwise_scan(self):
        rows = []
        for i in range(5000):
            row = self.row(f'row-{i}', i)
            stamp = (datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(seconds=i)).isoformat()
            row['recorded_at'] = stamp
            row['source']['published_at'] = stamp
            rows.append(row)
        result = current({'records': rows}, '2026-10-12')
        self.assertEqual(result[0]['current'][0]['id'], 'row-4999')
        self.assertEqual(result[0]['conflicts'], [])
