"""City map points retain both original identities and never replace precise sites."""
import copy
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from inresearch.delivery import city_location, source_publication as publication
from inresearch.knowledge import industry
from inresearch.materials import inbox, task_analysis
from tests.unit import test_task_full_review as fixtures


def geoline(ident='2033196', name='Zhangjiakou', aliases='张家口市', lat='40.78341', lon='114.87139',
            kind='P', feature='PPLA2', country='CN', admin1='10', admin2='1307'):
    return '\t'.join([ident, name, name, aliases, lat, lon, kind, feature, country, '', admin1,
                      admin2, '', '', '123', '', '0', 'Asia/Shanghai', '2026-10-17'])


class CityLocationTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.FullNativeReviewTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.fixture = fixture; self.root = fixture.root
        fixture.start()
        with patch.object(industry, 'cached_snapshot', side_effect=fixture.projected):
            task_analysis.complete(self.root, fixture.payload())
        self.site = publication.projects(self.root)['records'][0]['site_id']
        self.geography = fixture.path.parent / 'CN.zip'
        self.lines = [geoline('1', 'Hebei', '河北省', kind='A', feature='ADM1', admin2=''), geoline()]
        self.write_geography()
        self.payload = {'version': 1, 'expected_state_sha': publication.digest(publication.state(self.root)),
            'geography_sha256': hashlib.sha256(self.geography.read_bytes()).hexdigest(), 'sites': [{
                'site_id': self.site, 'submission_id': fixture.item['id'], 'source_sha256': fixture.sha,
                'sheet': '1-地点与身份', 'name_cell': 'B2', 'province_cell': 'D2', 'city_cell': 'E2',
                'geoname_id': '2033196', 'geonames_line': 2}]}

    def write_geography(self):
        with ZipFile(self.geography, 'w') as archive:
            archive.writestr('CN.txt', '\n'.join(self.lines) + '\n')

    def install(self, payload=None):
        return city_location.install(self.root, payload or self.payload, self.geography)

    def test_dual_originals_add_city_projection_without_identity_or_history_rewrite(self):
        old = publication.projects(self.root)['records'][0]
        receipt = self.install(); row = publication.projects(self.root)['records'][0]
        self.assertEqual(receipt['new_locations'], 1); self.assertEqual(receipt['new_sites'], 0)
        self.assertFalse(receipt['truth_checked'])
        self.assertEqual(row['identity_registration'], old['identity_registration'])
        self.assertEqual(row['observations'], old['observations'])
        self.assertEqual(row.get('street_address'), old.get('street_address'))
        public = industry.project(row)
        self.assertEqual(public['coordinates'], [40.78341, 114.87139])
        source = public['geography']['coordinate_source']
        self.assertEqual((source['precision'], source['method']), ('city', 'city_reference'))
        self.assertIn('GeoNames', source['basis']); self.assertNotIn('source_sha256', source)
        audit = publication.state(self.root)['sites'][self.site]['city_location']
        self.assertEqual(audit['membership']['cells']['city'], {'cell': 'E2', 'value': '张家口市'})
        self.assertEqual(audit['membership']['source_sha256'], self.fixture.sha)
        self.assertEqual(audit['geography']['native_line'], self.lines[1])
        self.assertEqual(audit['geography']['province_native_line'], self.lines[0])
        totals = industry.totals([public, {**public, 'site_id': 'another-site'}])
        self.assertEqual((totals['city_located_sites'], totals['city_reference_points'], totals['precise_located_sites']), (2, 1, 0))
        # Ordinary export cannot turn derived city coordinates into initial identity.
        baseline = publication.bundle(self.root)['sites'][0]['baseline']
        self.assertNotIn('coordinates', baseline)

    def test_replay_rechecks_sources_preserves_bytes_and_ignores_new_execution_cas(self):
        first = self.install(); before = publication.state(self.root)
        payload = copy.deepcopy(self.payload); payload['expected_state_sha'] = publication.digest(before)
        replay = self.install(payload)
        self.assertEqual(replay['state'], 'already_published'); self.assertEqual(replay['new_locations'], 0)
        self.assertEqual(first['batch_id'], replay['batch_id']); self.assertEqual(before, publication.state(self.root))
        self.geography.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'geography_bytes'): self.install(payload)

    def test_missing_or_stale_cas_has_no_write(self):
        before = publication.state(self.root)
        payload = copy.deepcopy(self.payload); payload.pop('expected_state_sha')
        with self.assertRaisesRegex(ValueError, 'bounded_city'): self.install(payload)
        payload = copy.deepcopy(self.payload); payload['expected_state_sha'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'context_changed'): self.install(payload)
        self.assertEqual(before, publication.state(self.root))

    def test_wrong_sheet_columns_row_name_or_unregistered_membership_fail_closed(self):
        before = publication.state(self.root)
        for key, value in [('sheet', '2-水源供水与冷却'), ('city_cell', 'G2'), ('province_cell', 'D3'),
                           ('name_cell', 'B3'), ('site_id', 'nonexistent')]:
            payload = copy.deepcopy(self.payload); payload['sites'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.install(payload)
        self.assertEqual(before, publication.state(self.root))
        state = copy.deepcopy(before); state['sites'][self.site]['observations'][0]['adoption']['document_refs'][0]['source_sha256'] = 'e'*64
        with patch.object(publication, 'state', return_value=state):
            payload = copy.deepcopy(self.payload); payload['expected_state_sha'] = publication.digest(state)
            with self.assertRaisesRegex(ValueError, 'not_registered'): self.install(payload)

    def test_city_and_province_must_both_match_same_native_geography_record(self):
        for change in [dict(aliases='阜阳市'), dict(admin1='30'), dict(country='US'), dict(feature='PPL'),
                       dict(lat='91'), dict(lat='NaN'), dict(ident='123')]:
            self.lines[1] = geoline(**change); self.write_geography()
            payload = copy.deepcopy(self.payload); payload['geography_sha256'] = hashlib.sha256(self.geography.read_bytes()).hexdigest()
            with self.subTest(change=change), self.assertRaises(ValueError): self.install(payload)

    def test_city_source_bytes_or_approval_change_are_rejected_even_on_replay(self):
        self.install()
        content = inbox.record_path(self.fixture.item['id']) / 'content'
        content.write_bytes(b'changed workbook')
        with self.assertRaisesRegex(ValueError, '原件内容已变化'): self.install()

    def test_existing_precise_point_is_never_overwritten(self):
        previous = publication.state(self.root)
        previous['sites'][self.site]['baseline']['coordinates'] = '1,2'
        payload = copy.deepcopy(self.payload); payload['expected_state_sha'] = publication.digest(previous)
        with patch.object(publication, 'state', return_value=previous):
            with self.assertRaisesRegex(ValueError, 'cannot_be_changed'): self.install(payload)

    def test_later_precise_projection_wins_without_removing_city_audit(self):
        self.install(); audit = publication.state(self.root)['sites'][self.site]['city_location']
        row = {'coordinates': '1,2', 'coordinate_source': {'precision': 'address'}}
        city_location.project(row, audit)
        self.assertEqual(row['coordinates'], '1,2'); self.assertEqual(row['coordinate_source']['precision'], 'address')
        self.assertEqual(publication.state(self.root)['sites'][self.site]['city_location'], audit)

    def test_batch_rejects_duplicate_sites_and_no_partial_write(self):
        before = publication.state(self.root); payload = copy.deepcopy(self.payload)
        payload['sites'].append(copy.deepcopy(payload['sites'][0]))
        with self.assertRaisesRegex(ValueError, 'unique_city'): self.install(payload)
        self.assertEqual(publication.state(self.root), before)

    def test_input_coordinates_or_arbitrary_extra_keys_are_not_accepted(self):
        payload = copy.deepcopy(self.payload); payload['sites'][0]['coordinates'] = '1,2'
        with self.assertRaisesRegex(ValueError, 'unique_city'): self.install(payload)
        payload = copy.deepcopy(self.payload); payload['sites'][0]['site_id'] = {}
        with self.assertRaisesRegex(ValueError, 'unique_city'): self.install(payload)

    def test_geography_is_streamed_and_pplc_is_supported(self):
        self.lines[1] = geoline(feature='PPLC'); self.write_geography()
        self.payload['geography_sha256'] = hashlib.sha256(self.geography.read_bytes()).hexdigest()
        original = ZipFile.read
        def bounded(archive, name, *args, **kwargs):
            if name == 'CN.txt': raise AssertionError('whole original decoded')
            return original(archive, name, *args, **kwargs)
        with patch.object(ZipFile, 'read', bounded):
            self.assertEqual(self.install()['new_locations'], 1)

    def test_changed_original_before_commit_aborts_atomic_pointer(self):
        before = publication.state(self.root); original = city_location._membership
        calls = []
        def changed(item):
            result = original(item); calls.append(1)
            if len(calls) == 2: result['cells']['city']['value'] = '不同城市'
            return result
        with patch.object(city_location, '_membership', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'membership_source_changed'): self.install()
        self.assertEqual(publication.state(self.root), before)

    def test_adm2_requires_exact_native_city_name_and_keeps_administrative_scope(self):
        self.lines[1] = geoline(kind='A', feature='ADM2'); self.write_geography()
        self.payload['geography_sha256'] = hashlib.sha256(self.geography.read_bytes()).hexdigest()
        self.install()
        audit = publication.state(self.root)['sites'][self.site]['city_location']
        self.assertEqual(audit['geography']['feature_code'], 'ADM2')
        self.assertIn('地级行政区参考点', audit['coordinate_source']['basis'])
        self.lines[1] = geoline(aliases='张家口', kind='A', feature='ADM2'); self.write_geography()
        self.payload['geography_sha256'] = hashlib.sha256(self.geography.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'exact_name_required'): self.install()
        self.lines[1] = geoline(kind='A', feature='ADM1'); self.write_geography()
        self.payload['geography_sha256'] = hashlib.sha256(self.geography.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'identity_mismatch'): self.install()

    def test_four_reviewed_layouts_use_only_their_explicit_identity_columns(self):
        from xml.sax.saxutils import escape
        from inresearch.materials import native_review_contract as contract
        for layout_id, columns in city_location.COLUMNS.items():
            original = fixtures.campus_workbook(layout_id=layout_id)
            stream = io.BytesIO()
            main = contract.LAYOUTS[layout_id]['main']
            index = list(contract.LAYOUTS[layout_id]['sheets']).index(main) + 1
            with ZipFile(io.BytesIO(original)) as source, ZipFile(stream, 'w') as target:
                for info in source.infolist():
                    data = source.read(info.filename)
                    if info.filename == f'xl/worksheets/sheet{index}.xml':
                        text = ''.join(f'<c r="{column}10" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
                            for column, value in zip(columns, ('测试园区甲', '河北省', '张家口市')))
                        data = data.replace(b'</sheetData>', ('<row r="10">'+text+'</row></sheetData>').encode())
                    target.writestr(info.filename, data)
            raw = stream.getvalue(); sha = hashlib.sha256(raw).hexdigest()
            directory = self.fixture.path.parent / layout_id; directory.mkdir()
            (directory/'content').write_bytes(raw)
            item = {**self.payload['sites'][0], 'source_sha256': sha, 'sheet': main,
                    **{key: column+'10' for key, column in zip(('name_cell','province_cell','city_cell'), columns)}}
            with self.subTest(layout=layout_id), patch.object(inbox, 'worker_record', return_value={'sha256': sha}), patch.object(inbox, 'record_path', return_value=directory):
                proof = city_location._membership(item)
                self.assertEqual(proof['layout_id'], layout_id)
                self.assertEqual(proof['cells']['city']['value'], '张家口市')
                item['city_cell'] = 'Z10'
                with self.assertRaisesRegex(ValueError, 'identity_columns'): city_location._membership(item)

    def test_city_address_and_precise_counts_are_distinct(self):
        self.install(); row = industry.project(publication.projects(self.root)['records'][0])
        rows = [row]
        for ident, precision in [('address-site','address'), ('physical-site','site'), ('building-site','building'), ('legacy-site',None)]:
            other = copy.deepcopy(row); other['site_id'] = ident
            other['geography']['coordinate_source'] = {'precision': precision}
            rows.append(other)
        counts = industry.totals(rows)
        self.assertEqual((counts['city_located_sites'], counts['city_reference_points'], counts['address_located_sites'], counts['precise_located_sites']), (1,1,1,2))

    def test_linked_news_inherits_city_precision_from_small_runtime_projection(self):
        from inresearch.knowledge import raw_atlas
        self.install()
        lead = {'id':'city-linked', 'site_id':self.site, 'events':[
            {'title':'园区来源', 'url':'https://example.org/city-news'}]}
        with patch.object(publication, 'state', side_effect=AssertionError('full source ledger read')):
            result = raw_atlas.build(self.root, None, [lead])
        point = next(row for row in result['records'] if row['url']=='https://example.org/city-news')
        self.assertEqual(point['coordinates'], [40.78341,114.87139])
        self.assertEqual(point['location_precision'], 'city')
        self.assertEqual(point['site_id'], self.site)

    def test_real_overview_preserves_public_city_geography_and_location_counts(self):
        self.install()
        (self.root/'data/prices.json').write_text('{"records":[]}')
        # Build the real homepage response from its durable city receipt. No
        # synthetic geography is injected into a mocked API/browser response.
        overview = industry.snapshot(self.root, {'overview': '1'})
        full = industry.snapshot(self.root)
        point = next(row for row in overview['rows'] if row['site_id'] == self.site)
        full_point = next(row for row in full['rows'] if row['site_id'] == self.site)
        self.assertTrue(overview['overview'])
        self.assertEqual(point['geography'], full_point['geography'])
        self.assertEqual(point['coordinates'], [40.78341, 114.87139])
        self.assertEqual(point['geography']['city'], '张家口市')
        public_source = point['geography']['coordinate_source']
        self.assertEqual(public_source, {
            'precision': 'city', 'coordinate_system': 'WGS84', 'method': 'city_reference',
            'feature_code': 'PPLA2', 'url': 'https://www.geonames.org/2033196/',
            'basis': '城市级定位（园区精确位置待补）；GeoNames 城市代表点，非园区实址或行政几何质心；CC BY 4.0。'})
        for name, expected in [('city_located_sites',1), ('city_reference_points',1),
                               ('precise_located_sites',0), ('address_located_sites',0)]:
            self.assertEqual(overview['totals'][name], expected)
            self.assertEqual(overview['capacity_audit'][name], expected)
        serialized = json.dumps(point['geography'], ensure_ascii=False)
        for private in ('source_sha256', 'locator', 'membership', 'native_line',
                        self.fixture.sha, self.payload['geography_sha256']):
            self.assertNotIn(private, serialized)
        self.assertNotIn(self.payload['geography_sha256'], json.dumps(overview))
        self.assertNotIn('observations', point)
