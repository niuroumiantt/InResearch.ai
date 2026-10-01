"""回流（2026-10-01，fetchspec 申请 #301）：公开 /api/targets/backflow 按目标行给某一队状态与接收计数。"""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import test_research as fixtures
from inresearch.adapters import fetchspec_projection
from inresearch.materials.fetchspec_receive import receive


class BackflowEndpointTest(unittest.TestCase):
    def setUp(self):
        self.base = fixtures.ReaderSnapshotHTTPTests('test_news_projection_uses_validated_input_without_catalog_tasks_or_private_metadata')
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        (self.base.root / 'framework').mkdir(exist_ok=True)
        shutil.copy(fixtures.research.ROOT / 'framework/tco_targets.json', self.base.root / 'framework/tco_targets.json')
        targets = json.loads((self.base.root / 'framework/tco_targets.json').read_text())['targets']
        self.rows = {t['id']: t for t in targets if t.get('team') == 'fetchspec'}
        self.spec = sorted(i for i in self.rows if i.endswith('.spec'))[0]

    def publish(self, acquisition):
        payload = self.base.payload()
        payload['reader']['acquisition'] = acquisition
        self.assertEqual(self.base.post(payload)[0], 200)

    def test_every_team_row_is_listed_with_status_from_git_and_counts_from_the_snapshot(self):
        self.publish({'fetchspec_feed': {'by_target': {
            self.spec: {'received_items': 2, 'companies': ['vertiv', 'nvidia', 'vertiv'], 'last_received_at': '2026-10-01T08:00:00+00:00',
                        'parameter_observations': 3},
            'P.bad.spec': {'received_items': -1}, '../etc': {'received_items': 1}, 'P.str.spec': {'received_items': '2'}}}})
        code, body = self.base.request('GET', '/api/targets/backflow?team=fetchspec')
        self.assertEqual(code, 200)
        self.assertEqual((body['schema_version'], body['team']), (1, 'fetchspec'))
        self.assertEqual(set(body['by_target']), set(self.rows), '每条 fetchspec 行都在，且只有 fetchspec 行')
        self.assertEqual(body['by_target'][self.spec], {'status': self.rows[self.spec]['status'], 'received_items': 2,
                         'companies': ['nvidia', 'vertiv'], 'last_received_at': '2026-10-01T08:00:00+00:00', 'parameter_observations': 3})
        other = next(i for i in self.rows if i != self.spec)
        self.assertEqual(body['by_target'][other]['received_items'], 0)
        raw = (self.base.root / 'framework/tco_targets.json').read_bytes()
        self.assertEqual(body['targets_sha256'], hashlib.sha256(raw).hexdigest())

    def test_default_team_is_fetchspec_and_bad_queries_are_400(self):
        self.publish({})
        code, body = self.base.request('GET', '/api/targets/backflow')
        self.assertEqual((code, body['team']), (200, 'fetchspec'))
        self.assertTrue(all(row['received_items'] == 0 for row in body['by_target'].values()))
        self.assertEqual(self.base.request('GET', '/api/targets/backflow?team=nobody')[0], 400)
        self.assertEqual(self.base.request('GET', '/api/targets/backflow?team=fetchspec&x=1')[0], 400)
        self.assertEqual(self.base.request('GET', '/api/targets/backflow?team=fetchspec&team=inews')[0], 400)

    def test_inews_reuses_the_news_counts(self):
        news = [t['id'] for t in json.loads((self.base.root / 'framework/tco_targets.json').read_text())['targets'] if t.get('team') == 'inews']
        self.publish({'news_feed': {'status': 'success', 'items': [], 'by_target': {news[0]: 4}}})
        code, body = self.base.request('GET', '/api/targets/backflow?team=inews')
        self.assertEqual(code, 200)
        self.assertEqual(body['by_target'][news[0]]['received_items'], 4)

    def test_backflow_is_on_the_public_reader_allowlist(self):
        from inresearch.interfaces import public
        self.assertIn('/api/targets/backflow', public.READER_API)


class ReceiverObservationsAndProjectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo, self.package, self.data = base / 'repo', base / 'delivery', base / 'data'
        (self.repo / 'framework').mkdir(parents=True)
        self.target = 'P.ups.spec'
        (self.repo / 'framework/tco_targets.json').write_text(json.dumps({'targets': [
            {'id': self.target, 'team': 'fetchspec', 'part_id': 'ups'},
            {'id': 'P.ups.operation', 'team': 'fetchspec', 'part_id': 'ups'}]}))
        body = b'<html><table><tr><td>Rated power</td><td>250 kW</td></tr></table></html>'
        sha = hashlib.sha256(body).hexdigest()
        relative = f'files/{sha[:2]}/{sha}.html'
        (self.package / Path(relative).parent).mkdir(parents=True)
        (self.package / relative).write_bytes(body)
        good = {'company_id': 'vertiv', 'product_id': 'vertiv:exl-s1', 'target_id': self.target, 'part_id': 'ups',
                'parameter_name': 'ups.rated_power', 'value': '250 kW', 'unit': 'kW', 'condition': '250 kW model',
                'source_url': 'https://www.vertiv.com/x/', 'source_sha256': sha, 'observed_at': '2026-10-01T00:00:00Z'}
        item = {'source_item_id': 'vertiv:item-1', 'source': {'publisher': 'Vertiv', 'url': 'https://www.vertiv.com/x/',
                'categories': ['UPS'], 'language': 'en'}, 'retrieved_at': '2026-10-01T00:00:00Z', 'sha256': sha,
                'bytes': len(body), 'content_type': 'text/html', 'format': 'html', 'completeness': {'state': 'complete'},
                'access_scope': {'state': 'public'}, 'version_relation': {'type': 'original'}, 'path': relative,
                'target_ids': [self.target],
                'product_evidence': [{'product_id': 'vertiv:exl-s1', 'target_ids': [self.target], 'parameter_observations': [
                    good,
                    {**good, 'target_id': 'P.ups.operation'},      # 行不属于本项
                    {**good, 'source_sha256': '0' * 64},           # 不是本项字节
                    {**good, 'value': 250}]}]}                    # 值不是原文字符串
        manifest = {'contract_version': '2.0', 'provider_id': 'fetchspec', 'delivery_id': 'bf-1', 'task_id_or_discovery': 'discovery',
                    'collector_revision': 'abc', 'files_included': True, 'company_id': 'vertiv', 'target_ids': [self.target], 'items': [item]}
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        (self.package / 'SHA256SUMS').write_text(f'{sha}  {relative}\n')
        self.good = good

    def test_receiver_keeps_only_valid_observations_and_projection_counts_them_per_row(self):
        receive(self.repo, self.package, self.data)
        counts = fetchspec_projection.by_target(self.data)
        self.assertEqual(set(counts), {self.target})
        row = counts[self.target]
        self.assertEqual((row['received_items'], row['companies'], row['parameter_observations']), (1, ['vertiv'], 1))
        self.assertIsNotNone(row['last_received_at'])
        receive(self.repo, self.package, self.data)
        self.assertEqual(fetchspec_projection.by_target(self.data)[self.target]['received_items'], 1, '同一原件重复接收只计一次')

    def test_projection_is_empty_without_a_ledger(self):
        self.assertEqual(fetchspec_projection.feed(self.data), {'by_target': {}})


if __name__ == '__main__':
    unittest.main()
