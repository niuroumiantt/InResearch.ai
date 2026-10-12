import copy
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
import shutil
from unittest.mock import patch
from inresearch.knowledge import object_observations as ledger
from inresearch.workflow import object_review as workflow
from inresearch.workflow.project_review_reader import digest

class ObjectReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.data=self.root/'runtime'
        (self.root/'data').mkdir();(self.root/'data/companies.json').write_text(json.dumps({'records':[{'company_id':'micron'}]}))
        (self.root/'framework').mkdir()
        shutil.copyfile(Path(__file__).resolve().parents[2]/'framework/research_publication.json',self.root/'framework/research_publication.json')
        body=json.dumps({'part':'TEST-64','density':'64GB','range':[60,64]}).encode();self.sha=hashlib.sha256(body).hexdigest()
        original=self.data/'acquisition/blobs'/self.sha[:2]/(self.sha+'.json');original.parent.mkdir(parents=True);original.write_bytes(body)
        self.db=sqlite3.connect(self.data/'acquisition/catalog.sqlite');self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE product_documents(sha256 TEXT,source_url TEXT,format TEXT,received_at TEXT)')
        self.db.execute('INSERT INTO product_documents VALUES(?,?,?,?)',(self.sha,'https://www.micron.com/test','json','2026-10-01T00:00:00Z'));self.db.commit()
        self.obj=ledger.object_record('product',{'company_id':'micron','model':'TEST-64','version':'unspecified'},'TEST-64')
        self.claim={'object':self.obj,'metric':'density','value':'64GB','unit':'native','scope':{'condition':'vendor-listed'},'kind':'reported','basis':'native vendor cell; effective date unknown','effective_at':None,'published_at':None,'evidence':{'sha256':self.sha,'locator':'/density'}}
        self.review={'by':'named reviewer','at':'2026-10-11T11:00:00Z','score':6,'tier':'B','authority':'reviewer','decision':'adopted','rationale':'Source, object, native value, qualifiers and dates independently reviewed','sample_review':{'by':'second reviewer','decision':'confirmed'}}
    def proposal(self,claims=None):
        claims=claims or [self.claim];ctx=workflow.prepare(self.root,self.data,claims)
        return {'claims':claims,'source_version':ctx['version'],'baseline_sha256':digest(ledger.load(self.root)),'review':self.review}
    def archive_fixture(self):
        self.db.execute('DELETE FROM product_documents');self.db.commit()
        folder=self.data/'catalog';folder.mkdir()
        original=self.data/'originals'/('source-'+self.sha+'.json');original.parent.mkdir();
        original.write_bytes(json.dumps({'part':'TEST-64','density':'64GB','range':[60,64]}).encode())
        with sqlite3.connect(folder/'catalog.sqlite') as db:
            db.execute('CREATE TABLE documents(doc_id TEXT,sha256 TEXT,original_rel TEXT)')
            db.execute('CREATE TABLE sources(id INTEGER PRIMARY KEY,doc_id TEXT,source_key TEXT,received REAL)')
            db.execute('INSERT INTO documents VALUES(?,?,?)',('doc-'+self.sha,self.sha,str(original.relative_to(self.data))))
            db.execute('INSERT INTO sources VALUES(1,?,?,?)',('doc-'+self.sha,'m4-import/private/project.xlsx',1759276800))
        return original

    def test_archive_import_adopts_without_webpage_and_public_projection_hides_provenance(self):
        self.archive_fixture();proposal=self.proposal();proposal['review']['public_fields_reviewed']=True
        self.assertEqual(workflow.apply(self.root,self.data,proposal)['records'],1)
        before=(self.root/ledger.PATH).read_bytes()
        self.assertEqual(workflow.apply(self.root,self.data,proposal)['state'],'already_applied')
        self.assertEqual(before,(self.root/ledger.PATH).read_bytes())
        record=ledger.load(self.root)['records'][0]
        self.assertEqual(record['source']['first_received_at'],'2025-10-01T00:00:00+00:00')
        self.assertIsNone(record['source']['url']);self.assertTrue(ledger.archived_source_valid(record['source']))
        self.assertNotIn('m4-import/private',before.decode())
        public=ledger.public_page(self.root,{})['records'][0]
        self.assertEqual(public['source'],{'url':None,'published_at':None})
        self.assertNotIn('archive',json.dumps(public));self.assertNotIn('source_key',json.dumps(public))

    def test_archive_receipt_changes_and_missing_import_block_before_writing(self):
        self.archive_fixture();proposal=self.proposal()
        with sqlite3.connect(self.data/'catalog/catalog.sqlite') as db:
            db.execute('UPDATE sources SET source_key=?',('m4-import/changed',))
        with self.assertRaisesRegex(ValueError,'changed_since_review'):workflow.apply(self.root,self.data,proposal)
        self.assertFalse((self.root/ledger.PATH).exists())
        with sqlite3.connect(self.data/'catalog/catalog.sqlite') as db:db.execute('DELETE FROM sources')
        with self.assertRaisesRegex(ValueError,'actual_archive_import_required'):self.proposal()

    def test_archive_bytes_and_forged_provenance_cannot_pass(self):
        original=self.archive_fixture();proposal=self.proposal();original.write_bytes(b'changed original')
        with self.assertRaisesRegex(ValueError,'source_bytes_changed'):workflow.apply(self.root,self.data,proposal)
        evidence={'url':None,'sha256':self.sha,'archive':{'kind':'catalog_import','doc_id':'doc-'+self.sha,'receipts':[]}}
        self.assertFalse(ledger.archived_source_valid(evidence))

    def test_archived_srcdoc_context_is_frozen_without_network_or_scripts(self):
        from html import escape
        from inresearch.adapters.html_document import srcdoc
        body=('<iframe src="https://external.test/not-fetched"></iframe>'
              '<script>64 GB fake outside</script><iframe srcdoc="'+escape('<h2>TEST-64</h2><table><tr><td>Density</td><td>64 GB</td></tr></table><script>128 GB</script>',quote=True)+'"></iframe>')
        raw=body.encode();sha=hashlib.sha256(raw).hexdigest();p=self.data/'acquisition/blobs'/sha[:2]/(sha+'.html');p.parent.mkdir(parents=True);p.write_bytes(raw)
        self.db.execute('INSERT INTO product_documents VALUES(?,?,?,?)',(sha,'https://www.micron.com/test','html','2026-10-01T00:00:00Z'));self.db.commit()
        text=srcdoc(p,1);self.assertIn('64 GB',text);self.assertNotIn('128 GB',text)
        self.claim.update(value='64 GB',evidence={'sha256':sha,'locator':'html:srcdoc:1','quote':'Density | 64 GB'})
        proposal=self.proposal();workflow.apply(self.root,self.data,proposal)
        self.assertEqual(ledger.load(self.root)['records'][0]['source']['locator'],'html:srcdoc:1')
        self.claim['evidence']['quote']='128 GB'
        with self.assertRaisesRegex(ValueError,'quote_not_in_native'):self.proposal()
        for index in [0,2,True]:
            with self.assertRaises(ValueError):srcdoc(p,index)
        with self.assertRaisesRegex(ValueError,'too_large'):srcdoc(p,1,limit=4)
        self.claim['evidence'].update(locator='html:srcdoc:2',quote='64 GB')
        with self.assertRaisesRegex(ValueError,'locator_required'):self.proposal()

    def test_native_xlsx_extraction_adoption_replay_and_context_revalidation(self):
        from tests.unit.test_xlsx_document import workbook_bytes
        from inresearch.workflow.stock_objects import extract
        body=workbook_bytes();sha=hashlib.sha256(body).hexdigest()
        original=self.data/'acquisition/blobs'/sha[:2]/(sha+'.xlsx')
        original.parent.mkdir(parents=True);original.write_bytes(body)
        self.db.execute('INSERT INTO product_documents VALUES(?,?,?,?)',(sha,'https://www.micron.com/test','xlsx','2026-10-01T00:00:00Z'));self.db.commit()
        loc='xlsx:sheet:1:cell:C2:context:A1:E3'
        plan=[{'sha256':sha,'object':self.obj,'scope':{'condition':'synthetic estimate fixture'},
               'basis':'native table with headers and footnotes; not real data','assumptions':['synthetic forecast fixture'],
               'fields':[{'locator':loc,'metric':'fixture.capacity','kind':'forecast','unit':'MW'}]}]
        claims=extract(self.root,self.data,plan+plan)
        self.assertEqual(len(claims),1);self.assertEqual(claims[0]['value'],'64.00')
        self.assertFalse((self.root/ledger.PATH).exists())
        proposal=self.proposal(claims);proposal['review']['public_fields_reviewed']=True
        self.assertEqual(workflow.apply(self.root,self.data,proposal)['records'],1)
        before=(self.root/ledger.PATH).read_bytes()
        self.assertEqual(workflow.apply(self.root,self.data,proposal)['state'],'already_applied')
        self.assertEqual(before,(self.root/ledger.PATH).read_bytes())
        row=ledger.load(self.root)['records'][0]
        self.assertEqual(row['source']['quote'],'64.00');self.assertEqual(row['source']['locator'],loc)
        self.assertIsNone(row['effective_at']);self.assertIsNone(row['source']['published_at'])
        changed=copy.deepcopy(proposal);changed['claims'][0]['evidence']['locator']=loc.replace('E3','E2')
        with self.assertRaisesRegex(ValueError,'changed_since_review'):workflow.apply(self.root,self.data,changed)
        changed=copy.deepcopy(proposal);changed['claims'][0]['value']='65.00'
        with self.assertRaisesRegex(ValueError,'xlsx_value_mismatch'):workflow.apply(self.root,self.data,changed)
        original.write_bytes(body+b'changed')
        with self.assertRaisesRegex(ValueError,'source_bytes_changed'):workflow.apply(self.root,self.data,proposal)
        self.assertEqual(before,(self.root/ledger.PATH).read_bytes())

    def test_target_free_adoption_and_exact_no_write_replay(self):
        p=self.proposal();self.assertEqual(workflow.apply(self.root,self.data,p)['state'],'applied');before=(self.root/ledger.PATH).read_bytes()
        self.assertEqual(workflow.apply(self.root,self.data,p)['state'],'already_applied');self.assertEqual(before,(self.root/ledger.PATH).read_bytes())
        row=ledger.load(self.root)['records'][0];self.assertEqual(row['target_ids'],[]);self.assertIsNone(row['effective_at']);self.assertEqual(row['source']['first_received_at'],'2026-10-01T00:00:00Z')
        self.assertEqual(ledger.current(ledger.load(self.root))[0]['current'],[])
    def test_changed_source_and_fabricated_json_value_fail_before_write(self):
        p=self.proposal();p['claims'][0]['value']='128GB'
        with self.assertRaisesRegex(ValueError,'value_mismatch'):workflow.apply(self.root,self.data,p)
        self.assertFalse((self.root/ledger.PATH).exists())
    def test_changed_context_review_and_baseline_rejected(self):
        p=self.proposal();p['source_version']='bad'
        with self.assertRaisesRegex(ValueError,'changed_since_review'):workflow.apply(self.root,self.data,p)
        p=self.proposal();p['baseline_sha256']='bad'
        with self.assertRaisesRegex(ValueError,'ledger_changed'):workflow.apply(self.root,self.data,p)
        p=self.proposal();p['review']={}
        with self.assertRaisesRegex(ValueError,'c3'):workflow.apply(self.root,self.data,p)
    def test_all_four_native_identities_and_required_disambiguation(self):
        for kind,native in [('company',{'company_id':'micron'}),('statistic',{'publisher':'EIA','series':'price','geography':'US-TX','definition':'industrial cents per kWh'}),('quote',{'company_id':'micron','configuration':'part-64','market':'US','currency':'USD','billing_basis':'each'})]:
            c=copy.deepcopy(self.claim);c['object']=ledger.object_record(kind,native,kind);self.assertTrue(self.proposal([c])['source_version'])
        bad=copy.deepcopy(self.obj);bad['identity'].pop('version')
        with self.assertRaisesRegex(ValueError,'native_identity'):ledger.identity(bad,self.root)
    def test_native_range_and_uncertain_time_not_collapsed(self):
        row={'metric':'price','scope':{'region':'US'},'value':{'value_range':[2,3]},'unit':'USD/hour','kind':'estimated','basis':'native range','assumptions':['same configuration'],'effective_at':'2025-01'}
        ledger.check_claim(row);self.assertEqual(row['value'],{'value_range':[2,3]})
        row['value']['value_range']=[3,2]
        with self.assertRaisesRegex(ValueError,'interval'):ledger.check_claim(row)
    def test_same_scope_conflict_preserved_and_forecast_unknown_separate(self):
        def row(i,value,at,kind='reported'):return {'id':i,'object_id':'product:a','metric':'power','scope':{'condition':'same'},'unit':'W','value':value,'effective_at':at,'kind':kind}
        doc={'records':[row('a',100,'2025-01'),row('b',110,'2025-01-12'),row('future',200,'2030','forecast'),row('unknown',120,None)]}
        g=ledger.current(doc,'2026-10-11')[0];self.assertEqual(set(g['conflicts']),{'a','b'});self.assertEqual(len(g['other']),2)
        doc['records'].append(row('new',150,'2025-02'));g=ledger.current(doc,'2026-10-11')[0];self.assertEqual([r['id'] for r in g['current']],['new'])
    def test_native_disclosure_date_cannot_be_copied_from_receipt(self):
        self.claim['published_at']='2026-10-01'
        with self.assertRaisesRegex(ValueError,'native_evidence'):self.proposal()
    def test_invalid_revision_is_atomic(self):
        p=self.proposal();p['claims'][0]['revision']={'of':'missing','action':'correct','reason':'test'};p=self.proposal(p['claims'])
        with self.assertRaises(ValueError):workflow.apply(self.root,self.data,p)
        self.assertFalse((self.root/ledger.PATH).exists())

    def test_public_page_and_home_share_fields_without_private_audit(self):
        p=self.proposal();p['review']={**self.review,'public_fields_reviewed':True}
        workflow.apply(self.root,self.data,p)
        private=copy.deepcopy(self.claim);private['metric']='private_fixture'
        p=self.proposal([private]);workflow.apply(self.root,self.data,p)
        home=ledger.public_updates(self.root)
        api=ledger.public_page(self.root,{'limit':'1'})
        self.assertEqual((api['total'],home['total']),(1,1))
        self.assertEqual(api['records'],home['changes'])
        self.assertEqual(set(api['records'][0]['source']),{'url','published_at'})
        for forbidden in ('quote','context_sha256','first_received_at','proposal_sha256','review','claim_sha256'):
            self.assertNotIn(forbidden,api['records'][0])
            self.assertNotIn(forbidden,api['records'][0]['source'])
        self.assertEqual(ledger.public_page(self.root,{'object':'another-object'})['total'],0)
        for query in ({'limit':'101'},{'offset':'-1'},{'include':'private'},{'type':'site'},{'limit':'oops'}):
            with self.assertRaises(ValueError): ledger.public_page(self.root,query)

    def test_native_stock_extractor_deduplicates_without_adopting_or_model(self):
        from inresearch.workflow.stock_objects import extract
        item={'sha256':self.sha,'object':self.obj,'scope':self.claim['scope'],'basis':'native fixture',
              'fields':[{'pointer':'/density','metric':'density'}]}
        result=extract(self.root,self.data,[item,item])
        self.assertEqual(len(result),1);self.assertEqual(result[0]['value'],'64GB')
        self.assertFalse((self.root/ledger.PATH).exists())

    def test_owner_revision_preserves_old_record_and_withdraws_current(self):
        p=self.proposal();workflow.apply(self.root,self.data,p)
        old=ledger.load(self.root)['records'][0]
        revision=copy.deepcopy(self.claim)
        revision['revision']={'of':old['id'],'action':'withdraw','reason':'fixture source withdrawal'}
        p=self.proposal([revision]);p['review']={**self.review,'tier':'A','score':8,'authority':'owner'}
        workflow.apply(self.root,self.data,p)
        doc=ledger.load(self.root)
        self.assertEqual(doc['records'][0],old)
        self.assertEqual(len(doc['records']),2)
        self.assertEqual(ledger.current(doc),[])
        self.assertEqual(workflow.apply(self.root,self.data,p)['state'],'already_applied')

    def test_quote_requires_configuration_but_not_a_model_target(self):
        claim=copy.deepcopy(self.claim)
        claim['object']=ledger.object_record('quote',{'company_id':'micron','configuration':'TEST-64 native fixture','market':'US','currency':'USD','billing_basis':'each'},'Synthetic quotation fixture')
        claim.update(metric='quoted_configuration',kind='offer',valid_until='2026-12-31',basis='synthetic source-backed workflow test; not real quotation')
        p=self.proposal([claim]);workflow.apply(self.root,self.data,p)
        row=ledger.load(self.root)['records'][0]
        self.assertEqual(row['target_ids'],[])
        self.assertEqual(row['kind'],'offer')
        self.assertEqual(row['valid_until'],'2026-12-31')
