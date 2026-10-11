import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from inresearch.materials import daily_bundle, daily_events, daily_sources
from inresearch.paths import project_root


class DailyBundleTests(unittest.TestCase):
    def test_literal_power_spellings_do_not_accept_energy_or_negative_values(self):
        from inresearch.materials.daily_research import power_quantities
        self.assertEqual(power_quantities('8.5 megawatts to 11 megawatts; 275 megawatts (MW); 1.2 gigawatt; 60兆瓦'),
                         [(8.5, 'MW'), (11.0, 'MW'), (275.0, 'MW'), (1.2, 'GW'), (60.0, 'MW')])
        self.assertEqual(power_quantities('11 MWh, 2 GWh, 12 megawatt-hours, 9 megawatt hours, -11 MW, 20 MW/year'), [])

    def bundle(self, folder, research=False):
        html='<title>格洛可日报 2026-10-06</title><h2>01 芬兰园区</h2><p>芬兰 · 园区工程</p><p>IT负荷60MW，园区供电75MW，计划建设。[1]</p><h2>来源</h2><p>[1] 公司公告</p>'
        files={'2026-10-06-daily-wechat.html':('html',html), 'sources.json':('sources',json.dumps([{'id':1,'name':'公司公告','url':'https://example.org/campus'}]))}
        if research:
            files['research/evidence.txt']=('evidence','Phase 1 delivers 60 MW of IT load.')
            event={'section':1,'event_date':None,'reported_date':'2026-10-06','stage':'planning',
                   'project':{'name':'FIN05','city':'Salo','phase':'一期'},
                   'sources':[{'url':'https://example.org/campus','evidence_file':'research/evidence.txt'}],
                   'capacities':[{'value':60,'unit':'MW','basis':'it','scope':'project','phase':'一期',
                                  'nature':'announced','quote':'Phase 1 delivers 60 MW of IT load.','source_index':0}],
                   'constraints':[],'gaps':['待登记物理园区']}
            files['research-events.json']=('research',json.dumps({'schema_version':1,'html_sha256':hashlib.sha256(html.encode()).hexdigest(),'events':[event]}))
        rows=[]
        for name,(role,text) in files.items():
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            raw=path.read_bytes();rows.append({'path':name,'role':role,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        manifest={'schema_version':1,'producer':'inews_geluoke','report_date':'2026-10-06','files':rows}
        (folder/'research-delivery.json').write_text(json.dumps(manifest))
        return manifest

    def test_source_pairing_is_idempotent_archived_and_never_formal_adoption(self):
        root=project_root();before=(root/'data/projects.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle';folder.mkdir();self.bundle(folder);data=Path(tmp)/'data'
            a=daily_bundle.receive(folder,data,root);b=daily_bundle.receive(folder,data,root)
            view=daily_events.projection(data)
            self.assertEqual(a['bundle_id'],b['bundle_id']);self.assertEqual(view['total'],1)
            self.assertEqual(view['missing_source_links'],0)
            self.assertEqual(a['formal_capacity_updates'],0)
            self.assertEqual(view['workflow']['awaiting_identity'],1)
            self.assertTrue(view['records'][0]['demand_matches'])
            source=next(s for s in view['records'][0]['sources'] if s.get('source_sha256'))
            self.assertEqual(source['source_sha256'],hashlib.sha256((folder/'sources.json').read_bytes()).hexdigest())
            self.assertEqual(len(list((data/'acquisition/blobs').rglob('*.json'))),1)
        self.assertEqual(before,(root/'data/projects.json').read_bytes())

    def test_replay_preserves_verified_first_arrival_and_advances_index_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle';folder.mkdir();self.bundle(folder)
            data=Path(tmp)/'data';root=project_root()
            times=['2026-10-11T01:00:00+00:00', '2026-10-11T01:00:05+00:00',
                   '2026-10-11T02:00:00+00:00', '2026-10-11T02:00:07+00:00']
            with patch.object(daily_bundle, 'now', side_effect=times):
                first=daily_bundle.receive(folder,data,root)
                replay=daily_bundle.receive(folder,data,root)
            self.assertEqual(first['received_at'], times[0])
            self.assertEqual(first['first_received_at'], times[0])
            self.assertEqual(first['last_indexed_at'], times[1])
            self.assertEqual(first['reindex_count'], 0)
            self.assertEqual(replay['received_at'], times[0])
            self.assertEqual(replay['first_received_at'], times[0])
            self.assertEqual(replay['received_at_basis'], 'first_verified_bundle_receipt')
            self.assertEqual(replay['last_indexed_at'], times[3])
            self.assertEqual(replay['reindex_count'], 1)
            self.assertEqual(replay['reindex_count_basis'], 'complete_since_first_index')
            self.assertEqual(first['documents'], replay['documents'])
            self.assertEqual(replay['formal_capacity_updates'], 0)
            from inresearch.workflow.daily_dispatch import receipt_documents, news_records
            self.assertEqual(set(receipt_documents(data).values()), {times[0]})
            self.assertTrue(news_records(data))

    def test_legacy_replay_keeps_last_recorded_time_without_inventing_first_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle';folder.mkdir();self.bundle(folder)
            data=Path(tmp)/'data';root=project_root()
            indexed=daily_bundle.receive(folder,data,root)
            path=Path(indexed['receipt']);legacy=json.loads(path.read_text())
            for key in ('receipt_timing_version','first_received_at','received_at_basis',
                        'last_indexed_at','reindex_count','reindex_count_basis'):
                legacy.pop(key)
            legacy['received_at']='2026-10-10T20:00:00+00:00'
            path.write_text(json.dumps(legacy))
            migrated=daily_bundle.receive(folder,data,root)
            again=daily_bundle.receive(folder,data,root)
            for row in (migrated, again):
                self.assertEqual(row['received_at'], legacy['received_at'])
                self.assertEqual(row['legacy_received_at'], legacy['received_at'])
                self.assertIsNone(row['first_received_at'])
                self.assertEqual(row['received_at_basis'], 'legacy_last_recorded_index')
                self.assertEqual(row['reindex_count_basis'], 'since_timestamp_tracking')
            self.assertEqual(migrated['reindex_count'], 1)
            self.assertEqual(again['reindex_count'], 2)
            from inresearch.workflow.daily_dispatch import receipt_documents, news_records
            self.assertEqual(set(receipt_documents(data).values()), {legacy['received_at']})
            self.assertTrue(news_records(data))

    def test_failed_first_index_keeps_verified_arrival_without_authorizing_delivery(self):
        from inresearch.workflow.daily_dispatch import receipt_documents, news_records
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle';folder.mkdir();manifest=self.bundle(folder,True)
            data=Path(tmp)/'data';root=project_root()
            original=daily_bundle.ingest
            def partially_index(*args,**kwargs):
                original(*args,**kwargs)
                raise ValueError('index_failed_after_event_write')
            arrival='2026-10-11T01:00:00+00:00'
            with patch.object(daily_bundle,'now',return_value=arrival), \
                    patch.object(daily_bundle,'ingest',side_effect=partially_index):
                with self.assertRaisesRegex(ValueError,'index_failed_after_event_write'):
                    daily_bundle.receive(folder,data,root)
            path=next((data/'material-reviews/daily-deliveries').glob('*.json'))
            marker=json.loads(path.read_text())
            self.assertEqual(marker['status'],'verified_arrival_pending_index')
            self.assertEqual(marker['first_received_at'],arrival)
            self.assertIsNone(marker['last_indexed_at'])
            self.assertEqual(marker['members'],[{k:r[k] for k in ('sha256','role','path')} for r in manifest['files']])
            self.assertTrue(daily_events.projection(data)['records'])
            self.assertEqual(receipt_documents(data),{})
            self.assertEqual(news_records(data),[])
            with patch.object(daily_bundle,'now',side_effect=['2026-10-11T02:00:00+00:00','2026-10-11T02:00:05+00:00']):
                indexed=daily_bundle.receive(folder,data,root)
            self.assertEqual(indexed['status'],'indexed_candidate')
            self.assertEqual(indexed['first_received_at'],arrival)
            self.assertEqual(indexed['received_at'],arrival)
            self.assertEqual(indexed['last_indexed_at'],'2026-10-11T02:00:05+00:00')
            self.assertEqual(indexed['reindex_count'],0)
            self.assertEqual(indexed['members'],marker['members'])
            self.assertEqual(set(receipt_documents(data).values()),{arrival})
            self.assertTrue(news_records(data))

    def test_changed_arrival_marker_identity_fails_before_archive_or_index(self):
        import copy
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle';folder.mkdir();self.bundle(folder)
            data=Path(tmp)/'data';root=project_root()
            with patch.object(daily_bundle,'ingest',side_effect=ValueError('first_index_failed')):
                with self.assertRaisesRegex(ValueError,'first_index_failed'):daily_bundle.receive(folder,data,root)
            path=next((data/'material-reviews/daily-deliveries').glob('*.json'))
            original=json.loads(path.read_text())
            for field in ('bundle','producer','report','source','member','time','status'):
                marker=copy.deepcopy(original)
                if field=='bundle':marker['bundle_id']='f'*64
                elif field=='producer':marker['producer']='other'
                elif field=='report':marker['report_date']='2020-01-01'
                elif field=='source':marker['source_sha256']='f'*64
                elif field=='member':marker['members'][0]['sha256']='f'*64
                elif field=='time':marker['first_received_at']=marker['received_at']='not-a-time'
                else:marker['status']='supplier_claimed_complete'
                path.write_text(json.dumps(marker));before=path.read_bytes()
                with self.subTest(field=field),patch.object(daily_bundle,'Collector') as collector, \
                        patch.object(daily_bundle,'ingest') as ingest:
                    with self.assertRaisesRegex(ValueError,'daily_.*identity_changed'):
                        daily_bundle.receive(folder,data,root)
                    collector.assert_not_called();ingest.assert_not_called()
                self.assertEqual(path.read_bytes(),before)

    def test_failed_hash_and_path_escape_never_open_reader_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle';folder.mkdir();manifest=self.bundle(folder);data=Path(tmp)/'data'
            (folder/'sources.json').write_text('[]')
            with self.assertRaisesRegex(ValueError,'integrity'):daily_bundle.receive(folder,data,project_root())
            self.assertFalse(data.exists())
            self.bundle(folder);manifest['files'][0]['path']='../outside.html'
            (folder/'research-delivery.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):daily_bundle.receive(folder,data,project_root())
            self.assertFalse(data.exists())

    def test_structured_numbers_bind_html_identity_and_exact_source_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle';folder.mkdir();self.bundle(folder,True);data=Path(tmp)/'data'
            receipt=daily_bundle.receive(folder,data,project_root())
            self.assertTrue(receipt['structured_research'])
            row=daily_events.projection(data)['records'][0]
            self.assertEqual(row['structured_evidence_status'],'quotes_verified')
            self.assertTrue(row['editorial_event']['evidence_checks'][0]['exact_quote'])
            self.assertEqual(row['editorial_event']['acceptance'],'candidate')
            self.assertIsNone(row['editorial_event']['event_date'])

    def test_source_citation_formats_and_untrusted_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'sources.json'
            for data in ([{'id':1,'url':'https://example.org/one'}],{'[1]':{'primary':'https://example.org/one'}},{'sources':[{'id':1,'urls':['https://example.org/one']}] },{'selected_sources':[{'id':1,'url':'https://example.org/one'}]}):
                p.write_text(json.dumps(data));self.assertEqual(daily_sources.load(p)['1']['urls'],['https://example.org/one'])
            p.write_text(json.dumps([{'publisher':'no explicit id','url':'https://example.org/one'}]))
            with self.assertRaisesRegex(ValueError,'unsupported'):daily_sources.load(p)
            p.write_text(json.dumps([{'id':1,'url':'https://user:secret@example.org/one'}]))
            with self.assertRaisesRegex(ValueError,'source_url'):daily_sources.load(p)

    def test_research_sidecar_cannot_bind_another_html_or_invent_a_source_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle';folder.mkdir();manifest=self.bundle(folder,True)
            research=folder/'research-events.json';value=json.loads(research.read_text());value['html_sha256']='0'*64
            research.write_text(json.dumps(value))
            row=next(r for r in manifest['files'] if r['role']=='research')
            row.update(bytes=research.stat().st_size,sha256=hashlib.sha256(research.read_bytes()).hexdigest())
            (folder/'research-delivery.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'invalid_daily_research'):daily_bundle.verified(folder)
            manifest=self.bundle(folder,True);value=json.loads(research.read_text());value['events'][0]['capacities'][0]['quote']='An invented 60 MW quote.'
            research.write_text(json.dumps(value));row=next(r for r in manifest['files'] if r['role']=='research')
            row.update(bytes=research.stat().st_size,sha256=hashlib.sha256(research.read_bytes()).hexdigest());(folder/'research-delivery.json').write_text(json.dumps(manifest))
            data=Path(tmp)/'data';daily_bundle.receive(folder,data,project_root())
            self.assertEqual(daily_events.projection(data)['records'][0]['structured_evidence_status'],'awaiting_quote_verification')

    def test_a_literal_quote_does_not_verify_a_different_typed_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bundle';folder.mkdir();manifest=self.bundle(folder,True)
            research=folder/'research-events.json';value=json.loads(research.read_text());value['events'][0]['capacities'][0]['value']=600
            research.write_text(json.dumps(value));row=next(r for r in manifest['files'] if r['role']=='research')
            row.update(bytes=research.stat().st_size,sha256=hashlib.sha256(research.read_bytes()).hexdigest());(folder/'research-delivery.json').write_text(json.dumps(manifest))
            data=Path(tmp)/'data';daily_bundle.receive(folder,data,project_root())
            result=daily_events.projection(data)['records'][0]
            self.assertEqual(result['structured_evidence_status'],'awaiting_quote_verification')
            self.assertTrue(result['editorial_event']['evidence_checks'][0]['exact_quote'])
            self.assertFalse(result['editorial_event']['evidence_checks'][0]['quantity_present'])


if __name__=='__main__':unittest.main()
