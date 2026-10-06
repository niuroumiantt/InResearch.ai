import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from inresearch.materials import daily_bundle, daily_events, daily_sources
from inresearch.paths import project_root


class DailyBundleTests(unittest.TestCase):
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
            for data in ([{'id':1,'url':'https://example.org/one'}],{'[1]':{'primary':'https://example.org/one'}},{'sources':[{'id':1,'urls':['https://example.org/one']}] }):
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
