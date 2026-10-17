"""City map points retain both original identities and never replace precise sites."""
import copy
import hashlib
import io
import json
from pathlib import Path
import unittest
import uuid
from xml.sax.saxutils import escape
from unittest.mock import patch
from zipfile import ZipFile

from inresearch.delivery import city_location, source_publication as publication
from inresearch.knowledge import industry
from inresearch.materials import inbox, task_analysis
from inresearch.storage.files import write_json_streaming
from inresearch.storage.layout import workspace_path
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

    def approved_source(self, count=1, prefix='批量测试园区', formula_last=False):
        # Full registered layout, actual received bytes and normal owner approval.
        raw = fixtures.campus_workbook(); stream = io.BytesIO()
        index = list(city_location.native_review_contract.LAYOUTS['mainland-register-v6']['sheets']).index('1-地点与身份') + 1
        with ZipFile(io.BytesIO(raw)) as source, ZipFile(stream, 'w') as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == f'xl/worksheets/sheet{index}.xml':
                    rows = ''.join('<row r="'+str(row)+'">'+''.join(
                        f'<c r="{column}{row}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
                        for column, value in [('B', prefix+str(row)), ('D', '河北省'), ('E', '张家口市')])+'</row>'
                        for row in range(10, 10+count))
                    if formula_last:
                        cell = f'<c r="E{9+count}" t="inlineStr"><is><t>张家口市</t></is></c>'
                        rows = rows.replace(cell, f'<c r="E{9+count}" t="str"><f>"张家口市"</f><v>张家口市</v></c>')
                    data = data.replace(b'</sheetData>', rows.encode()+b'</sheetData>')
                target.writestr(info.filename, data)
        raw = stream.getvalue()
        item, _ = inbox.receive(io.BytesIO(raw), len(raw), {'name':'城市批次.xlsx',
            'submitter':'员工', 'project_name':'城市批次原件', 'package_id':'dc-census-cn'}, 'anonymous', public=True)
        inbox.mutate({'id':item['id'], 'sha256':item['sha256'], 'expected_revision':0,
            'operation_id':str(uuid.uuid4()), 'action':'approve_and_analyze'}, 'owner', 'admin')
        inbox.acknowledge(item['id'], item['sha256'])
        return [{**self.payload['sites'][0], 'site_id':f"batch-{item['id']}-{row}",
            'submission_id':item['id'], 'source_sha256':item['sha256'],
            'name_cell':f'B{row}', 'province_cell':f'D{row}', 'city_cell':f'E{row}'} for row in range(10,10+count)]

    def seed_registered_batch(self, items):
        # Establish a controlled, already-published test ledger. The city call
        # below still runs real inbox, workbook, projection, lock, CAS and write.
        state = publication.state(self.root); template = state['sites'][self.site]
        for item in items:
            proof = city_location._membership(item); name = proof['cells']['name']['value']
            entry = copy.deepcopy(template); baseline = entry['baseline']
            baseline.update(site_id=item['site_id'], name=name)
            baseline['identity_registration'].update(site_id=item['site_id'], name=name, native_name=name)
            observation = entry['observations'][0]
            observation['fields']['name'] = name
            observation['adoption']['document_refs'][0]['source_sha256'] = item['source_sha256']
            state['sites'][item['site_id']] = entry
        write_json_streaming(workspace_path(publication.PATH, self.root), state)
        return {**self.payload, 'expected_state_sha':publication.digest(state), 'sites':items}

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
        before = publication.state(self.root); original = publication.projects
        path = workspace_path(publication.PATH, self.root); original_bytes = path.read_bytes()
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            (inbox.record_path(self.fixture.item['id'])/'content').write_bytes(b'changed before commit')
            return result
        with patch.object(publication, 'projects', side_effect=changed):
            with self.assertRaisesRegex(ValueError, '原件内容已变化'): self.install()
        self.assertEqual(publication.state(self.root), before)
        self.assertEqual(path.read_bytes(), original_bytes)

    def test_131_locations_parse_each_approved_source_once_per_validation_phase(self):
        items = self.approved_source(131)
        payload = self.seed_registered_batch(items); frozen_payload = copy.deepcopy(payload)
        before = publication.state(self.root)
        with patch.object(city_location, 'Workbook', wraps=city_location.Workbook) as books, \
                patch.object(inbox, 'worker_record', wraps=inbox.worker_record) as approved, \
                patch.object(city_location.native_review_contract, 'detect_layout', wraps=city_location.native_review_contract.detect_layout) as layouts:
            receipt = self.install(payload)
            self.assertEqual((books.call_count, approved.call_count, layouts.call_count), (2,2,2))
        self.assertEqual(receipt['new_locations'], 131)
        after = publication.state(self.root)
        for item in items:
            stored = after['sites'][item['site_id']]
            self.assertEqual(stored['observations'], before['sites'][item['site_id']]['observations'])
            self.assertEqual(stored['baseline'], before['sites'][item['site_id']]['baseline'])
            self.assertEqual(stored['city_location']['membership']['cells']['city'], {'cell':item['city_cell'], 'value':'张家口市'})
        self.assertEqual(payload, frozen_payload)
        path = workspace_path(publication.PATH, self.root); original_bytes = path.read_bytes()
        # A later call must reapprove/reparse; the old receipt remains byte exact.
        with patch.object(city_location, 'Workbook', wraps=city_location.Workbook) as books:
            replay = self.install({**payload, 'expected_state_sha':publication.digest(after)})
            self.assertEqual(books.call_count, 1)
        self.assertEqual(replay['state'], 'already_published')
        self.assertEqual(replay['batch_id'], receipt['batch_id'])
        self.assertEqual(path.read_bytes(), original_bytes)

    def test_batch_sources_are_isolated_by_submission_and_sha_and_keep_input_order(self):
        first = self.approved_source(2, '甲批园区'); second = self.approved_source(2, '乙批园区')
        items = [first[1], second[0], first[0], second[1]]
        with patch.object(city_location, 'Workbook', wraps=city_location.Workbook) as books:
            proofs = city_location._memberships(items)
        self.assertEqual(books.call_count, 2)
        self.assertEqual([p['cells']['name']['value'] for p in proofs], ['甲批园区11','乙批园区10','甲批园区10','乙批园区11'])
        proofs[0]['cells']['city']['value'] = 'tampered local proof'
        self.assertEqual(proofs[2]['cells']['city']['value'], '张家口市')
        with patch.object(city_location, 'Workbook', wraps=city_location.Workbook) as books:
            again = city_location._memberships(items)
        self.assertEqual(books.call_count, 2)
        self.assertEqual(again[0]['cells']['city']['value'], '张家口市')
        wrong = {**first[1], 'source_sha256':second[0]['source_sha256']}
        with self.assertRaisesRegex(ValueError, 'source_changed'):
            city_location._memberships([first[0], wrong])

    def test_same_bytes_in_an_unapproved_submission_cannot_reuse_another_approval(self):
        raw = (inbox.record_path(self.fixture.item['id'])/'content').read_bytes()
        other, _ = inbox.receive(io.BytesIO(raw), len(raw), {'name':'同字节.xlsx',
            'submitter':'员工', 'project_name':'待批准副本', 'package_id':'dc-census-cn'}, 'anonymous', public=True)
        self.assertEqual(other['sha256'], self.fixture.sha)
        item = {**self.payload['sites'][0], 'submission_id':other['id']}
        with self.assertRaisesRegex(PermissionError, '负责人批准'):
            city_location._memberships([self.payload['sites'][0], item])

    def test_approval_revoked_before_commit_is_rechecked_without_partial_write(self):
        original = publication.projects; path = workspace_path(publication.PATH, self.root)
        before = path.read_bytes()
        def revoke(*args, **kwargs):
            result = original(*args, **kwargs)
            record = inbox.load(self.fixture.item['id']); record['approval'] = {}
            inbox.atomic(inbox.record_path(self.fixture.item['id'])/'record.json', record)
            return result
        with patch.object(publication, 'projects', side_effect=revoke):
            with self.assertRaisesRegex(PermissionError, '负责人批准'): self.install()
        self.assertEqual(path.read_bytes(), before)

    def test_mixed_sources_revalidate_both_and_never_accept_cross_source_names(self):
        first = self.approved_source(2, '甲批园区'); second = self.approved_source(2, '乙批园区')
        payload = self.seed_registered_batch([first[1], second[0], first[0], second[1]])
        before = workspace_path(publication.PATH, self.root).read_bytes()
        wrong = copy.deepcopy(payload)
        wrong['sites'][0].update(submission_id=second[0]['submission_id'], source_sha256=second[0]['source_sha256'])
        with self.assertRaisesRegex(ValueError, 'name_binding_mismatch'): self.install(wrong)
        self.assertEqual(workspace_path(publication.PATH, self.root).read_bytes(), before)
        with patch.object(city_location, 'Workbook', wraps=city_location.Workbook) as books:
            self.assertEqual(self.install(payload)['new_locations'], 4)
            self.assertEqual(books.call_count, 4)

    def test_formula_in_a_later_shared_identity_cell_is_still_rejected(self):
        items = self.approved_source(2, formula_last=True)
        before = workspace_path(publication.PATH, self.root).read_bytes()
        with self.assertRaisesRegex(ValueError, 'literal_required'):
            self.install({**self.payload, 'sites':items})
        self.assertEqual(workspace_path(publication.PATH, self.root).read_bytes(), before)

    def test_replay_revalidates_approval_and_does_not_reuse_prior_parse(self):
        self.install(); path = workspace_path(publication.PATH, self.root); before = path.read_bytes()
        record = inbox.load(self.fixture.item['id']); record['approval'] = {}
        inbox.atomic(inbox.record_path(self.fixture.item['id'])/'record.json', record)
        with self.assertRaisesRegex(PermissionError, '负责人批准'): self.install()
        self.assertEqual(path.read_bytes(), before)

    def test_late_bad_locator_in_shared_source_rejects_whole_batch(self):
        items = self.approved_source(3); payload = self.seed_registered_batch(items)
        before = workspace_path(publication.PATH, self.root).read_bytes()
        for field, value in [('city_cell','G12'), ('province_cell','D11'), ('sheet','4-容量口径与分期')]:
            invalid = copy.deepcopy(payload); invalid['sites'][-1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.install(invalid)
            self.assertEqual(workspace_path(publication.PATH, self.root).read_bytes(), before)

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
