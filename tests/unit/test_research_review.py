import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inresearch.materials.artifacts import atomic_json, digest_file, encoded
from inresearch.workflow import research_review as review
from inresearch.workflow.research_publish import all_checks_pass
from inresearch.knowledge import registry


def fixture():
    ctx={'knowledge':{'statements':[]},'current_workorders':[{'wid':'Q-q1'}],
         'question_ids':['q1'],'source_tokens':[]}
    doc={'id':'doc-'+'a'*64,'content_sha256':'a'*64,'title':'Original research',
         'report_sha256':'b'*64,'coverage':{'complete':True,'pages_total':1,'pages_read':1,
             'chunks_total':1,'chunks_read':1,'characters_total':50,'characters_read':50}}
    ev={'id':'ev:test','document_id':doc['id'],'page_index':0,'quote':'Original bounded quotation',
        'locator':'p1','status':'candidate'}
    candidate={'id':'candidate:test','text':'Author statement','kind':'author_claim','status':'candidate',
               'question_ids':['q1'],'object_ids':['root'],'evidence_ids':[ev['id']]}
    packet={'batch_id':'c'*64,'original_importance':7,'document':doc,
            'items':[{'candidate':candidate,'evidence':[ev],'allowed_question_ids':['q1'],
                      'native_pages':{'0':'Original bounded quotation'}}],
            'research_context':ctx,'context_sha256':review.sha(ctx)}
    row={'id':candidate['id'],'decision':'adopt_B','score':7,'question_ids':['q1'],
         'evidence_ids':[ev['id']],'text':'The author reports a bounded claim.',
         'limitations':'Author claim; source date unknown; not certified as fact.',
         'rationale':'Partial support for current question','source_support_check':'Native page read',
         'conflict_check':'No scoped conflict','gap_dependency_check':'No gap dependence',
         'canonical_id':'','sensitive':False,'conflict':False,'replacement':False}
    return packet,row


def audit(directory,packet,row):
    model={'requested':'configured-model','actual':None,
           'input_sha256':hashlib.sha256(encoded(packet).encode()).hexdigest()}
    request={'system':review.SYSTEM,'user':encoded(packet),'model':{}}
    sample_packet={**packet,'proposed_reviews':[row]}
    model2={'requested':'configured-model','actual':None,
            'input_sha256':hashlib.sha256(encoded(sample_packet).encode()).hexdigest()}
    checks=[{'id':row['id'],'confirmed':True,'rationale':'Independent native context checked'}]
    for name,value in [('packet.json',packet),('request.json',request),
                       ('response.json',{'reviews':[row],'_model':model}),
                       ('sampling-request.json',{'system':review.SAMPLE_SYSTEM,'user':encoded(sample_packet)}),
                       ('sampling-response.json',{'checks':checks,'_model':model2})]:
        atomic_json(directory/name,value)
    return {'packet':packet,'reviews':[row],'model':model,'reviewed_at':'2026-10-08T00:00:00Z',
            'request_sha256':digest_file(directory/'request.json'),
            'sampling':{'sample_ids':[row['id']],'checks':checks,'model':model2}}


class ResearchReviewTests(unittest.TestCase):
    def test_a_conditions_cannot_be_downgraded(self):
        for key in ('original_importance','score','sensitive','conflict','replacement'):
            packet,row=fixture()
            if key=='original_importance':packet[key]=8
            elif key=='score':row[key]=8
            else:row[key]=True
            with self.assertRaisesRegex(ValueError,'c3_a'):review.validate_reviews(packet,{'reviews':[row]})
            row['decision']='needs_owner'
            self.assertEqual(review.validate_reviews(packet,{'reviews':[row]}),[row])

    def test_current_demand_and_original_evidence_required(self):
        for key in ('question_ids','evidence_ids'):
            packet,row=fixture();row[key]=['invented']
            with self.assertRaises(ValueError):review.validate_reviews(packet,{'reviews':[row]})
        packet,row=fixture();packet['research_context']['current_workorders']=[]
        with self.assertRaisesRegex(ValueError,'workorder'):review.validate_reviews(packet,{'reviews':[row]})

    def test_full_dispositions_and_real_duplicate_target(self):
        packet,row=fixture()
        with self.assertRaises(ValueError):review.validate_reviews(packet,{'reviews':[row,row]})
        row['decision']='duplicate';row['canonical_id']='not-adopted'
        with self.assertRaisesRegex(ValueError,'canonical'):review.validate_reviews(packet,{'reviews':[row]})

    def test_actual_audit_and_independent_call_required(self):
        packet,row=fixture()
        with tempfile.TemporaryDirectory() as td:
            directory=Path(td);bundle=audit(directory,packet,row)
            self.assertTrue(review.verify_audit(bundle,directory))
            response=json.loads((directory/'response.json').read_text());response['reviews'][0]['text']='Changed after call'
            atomic_json(directory/'response.json',response)
            with self.assertRaisesRegex(ValueError,'audit'):review.verify_audit(bundle,directory)

    def test_input_hash_cannot_be_forged_by_coordinated_packet_edit(self):
        packet,row=fixture()
        with tempfile.TemporaryDirectory() as td:
            directory=Path(td);bundle=audit(directory,packet,row)
            bundle['packet']['original_importance']=6
            atomic_json(directory/'packet.json',bundle['packet'])
            req=json.loads((directory/'request.json').read_text());req['user']=encoded(bundle['packet'])
            atomic_json(directory/'request.json',req);bundle['request_sha256']=digest_file(directory/'request.json')
            with self.assertRaisesRegex(ValueError,'audit'):review.verify_audit(bundle,directory)

    def test_append_keeps_old_records_and_does_not_close_question(self):
        packet,row=fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir();(root/'framework').mkdir();directory=root/'audit';directory.mkdir()
            bundle=audit(directory,packet,row)
            graph=json.loads((registry.ROOT/'framework/research_graph.json').read_text())
            questions={'records':[{'id':'q1','object_ids':['root'],'acceptance':'Independent validation',
                                  'evidence_requirements':['independent original sources']}]}
            atomic_json(root/'framework/research_graph.json',graph)
            atomic_json(root/'framework/research_questions.json',questions)
            original={'documents':[],'evidence':[],'statements':[],'answers':[]}
            atomic_json(root/'data/research_knowledge.json',original)
            with patch.object(review,'context',return_value=packet['research_context']):
                result=review.promote(root,bundle,directory)
                value=json.loads((root/'data/research_knowledge.json').read_text())
                self.assertEqual(result['closed_questions_added'],0)
                self.assertEqual(value['answers'],[])
                self.assertTrue(registry.supported_adoption(value['statements'][0],value))
                self.assertEqual(value['statements'][0]['kind'],'author_claim')
                replay=review.promote(root,bundle,directory)
                self.assertEqual(replay['state'],'already_applied')
                self.assertEqual(len(value['statements']),1)
            self.assertFalse((root/'data/facts.json').exists())

    def test_context_change_or_failed_sample_cannot_write(self):
        packet,row=fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir();directory=root/'audit';directory.mkdir()
            bundle=audit(directory,packet,row)
            path=root/'data/research_knowledge.json';atomic_json(path,{'statements':[]})
            before=path.read_bytes()
            with patch.object(review,'context',return_value={'changed':True}):
                with self.assertRaisesRegex(ValueError,'context_changed'):review.promote(root,bundle,directory)
            self.assertEqual(path.read_bytes(),before)
            bundle['sampling']['checks'][0]['confirmed']=False
            with self.assertRaises(ValueError):review.promote(root,bundle,directory)
            self.assertEqual(path.read_bytes(),before)

    def test_queue_claims_disjoint_and_preserves_attempts(self):
        with tempfile.TemporaryDirectory() as td:
            a=review.ReviewStore(td);b=review.ReviewStore(td)
            for i in range(2):
                a.db.execute('INSERT INTO batches(id,state,updated) VALUES(?,?,?)',(str(i),'queued','now'))
            a.db.commit()
            first=a.claim();second=b.claim()
            self.assertNotEqual(first['id'],second['id'])
            self.assertIsNone(a.claim())
            self.assertEqual(a.db.execute('SELECT sum(attempts) FROM batches').fetchone()[0],2)
            a.db.close();b.db.close()

    def test_sampling_is_fixed_and_rounded_up(self):
        ids=['c'+str(i) for i in range(19)]
        self.assertEqual(len(review.sample('batch',ids)),2)
        self.assertEqual(review.sample('batch',ids),review.sample('batch',list(reversed(ids))))

    def test_ci_requires_all_four_checks_success(self):
        checks=[{'name':n,'bucket':'pass'} for n in ('validate','browser (core)','browser (model_assets)','storage-container')]
        self.assertTrue(all_checks_pass(checks));self.assertFalse(all_checks_pass(checks[:-1]))
        checks[0]['bucket']='pending';self.assertFalse(all_checks_pass(checks))

    def test_demand_rematch_uses_actual_current_questions(self):
        packet,row=fixture()
        matching={'items':packet['items'],'current_question_directory':[{'id':'q-new','text':'Current cost question'}]}
        response={'matches':[{'id':row['id'],'question_ids':['q-new'],'rationale':'Substantive cost evidence'}]}
        with patch.object(review,'context',return_value={'question_ids':['q-new']}):
            review.apply_matches(Path('/unused'),packet,matching,response)
        self.assertEqual(packet['items'][0]['allowed_question_ids'],['q-new'])
        self.assertEqual(packet['items'][0]['original_allowed_question_ids'],['q1'])
        response['matches'][0]['question_ids']=['invented']
        with self.assertRaises(ValueError):review.validate_matches(matching,response)

    def test_progress_is_read_only_counts_and_hides_private_data(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(review.progress(td)['state'],'not_started')
            self.assertEqual(list(Path(td).iterdir()),[])
            store=review.ReviewStore(td)
            store.db.execute('INSERT INTO dispositions VALUES(?,?,?,?,?,?,?)',
                             ('secret','private-original','revision','needs_owner','batch','private text','now'))
            store.db.commit();store.db.close()
            value=review.progress(td)
            self.assertEqual(value['candidates'],{'needs_owner':1})
            self.assertNotIn('private',encoded(value))

    def test_budget_split_preserves_old_attempts_and_all_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            store=review.ReviewStore(td)
            batch={'id':'parent','revision_id':'rev','report_sha':'sha','doc_id':'doc','candidate_ids':encoded(['a','b','c'])}
            store.db.execute('INSERT INTO batches(id,state,attempts) VALUES(?,?,?)',('parent','reviewing',2))
            for cid in ['a','b','c']:
                store.db.execute('INSERT INTO dispositions VALUES(?,?,?,?,?,?,?)',(cid,'doc','rev','queued','parent','','now'))
            store.db.commit();store.split(batch)
            self.assertEqual(store.db.execute('SELECT attempts FROM batches WHERE id=?',('parent',)).fetchone()[0],2)
            children=store.db.execute("SELECT candidate_ids FROM batches WHERE state='queued'").fetchall()
            self.assertEqual(sorted(cid for r in children for cid in json.loads(r[0])),['a','b','c'])
            store.db.close()

    def test_context_keys_do_not_match_entities_and_legacy_audit_is_stable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir();(root/'framework').mkdir()
            atomic_json(root/'data/research_knowledge.json',{'statements':[],'evidence':[],'documents':[]})
            atomic_json(root/'framework/research_questions.json',{'records':[{'id':'q1','object_ids':['part:gpu']}]})
            rows=[{'fact_id':'unrelated','node':'part:gpu','entity':{'label':'Other'},'value':2},
                  {'fact_id':'relevant','node':'root','entity':{'label':'NODE device'},'value':3,
                   'caliber':{'scope':'forecast'},'notes':'Counterevidence stays complete',
                   'model_provenance':{'requested':'secret receipt','input_sha256':'a'*64}}]
            atomic_json(root/'data/facts.json',{'records':rows})
            with patch.object(registry,'current_tasks',return_value=[]):
                old=review.context(root,['q1'],['NODE'],'serialized-v1')
                new=review.context(root,['q1'],['NODE'])
                self.assertEqual(len(old['legacy_records']['facts.json']['records']),2)
                self.assertEqual(review.current_context(root,old),old)
                selected=new['legacy_records']['facts.json']['records']
                self.assertEqual([r['fact_id'] for r in selected],['relevant'])
                self.assertEqual(selected[0]['caliber'],rows[1]['caliber'])
                self.assertEqual(selected[0]['notes'],rows[1]['notes'])
                self.assertEqual(selected[0]['model_provenance']['sha256'],review.sha(rows[1]['model_provenance']))
                self.assertEqual(review.current_context(root,new),new)
                rows[0]['value']=4;atomic_json(root/'data/facts.json',{'records':rows})
                self.assertNotEqual(review.sha(review.current_context(root,new)),review.sha(new))

    def test_matching_terms_are_bound_to_each_claim_not_report_or_field_names(self):
        packet,row=fixture();packet['items'][0]['candidate']['text']='The author reports a tcgen05 completion mechanism.'
        matching={'retrieval_version':'semantic-values-v2','items':packet['items'],
                  'current_question_directory':[{'id':'q1'}]}
        result={'matches':[{'id':row['id'],'question_ids':['q1'],'rationale':'Mechanism support','context_terms':['tcgen05']}]}
        self.assertEqual(review.validate_matches(matching,result),result['matches'])
        for terms in ([],['NODE'],['report-author'],['']):
            changed=copy.deepcopy(result);changed['matches'][0]['context_terms']=terms
            with self.assertRaisesRegex(ValueError,'literal_bounded_claim'):review.validate_matches(matching,changed)
        self.assertTrue(review.term_match('电费','居民电费上涨'))
        self.assertFalse(review.term_match('NODE','node_id'))

    def test_regroup_keeps_all_dispositions_and_never_reuses_attempted_batches(self):
        with tempfile.TemporaryDirectory() as td:
            store=review.ReviewStore(td)
            for num,cohort in enumerate((['a','b','c'],['d','e','f'],['g'])):
                bid=review.sha(['rev','report',cohort])
                store.db.execute('INSERT INTO batches(id,doc_id,revision_id,report_sha,state,candidate_ids,updated) VALUES(?,?,?,?,?,?,?)',
                                 (bid,'doc','rev','report','queued',encoded(cohort),'now'))
                for cid in cohort:store.db.execute('INSERT INTO dispositions VALUES(?,?,?,?,?,?,?)',(cid,'doc','rev','queued',bid,'','now'))
            store.db.execute("INSERT INTO batches(id,state,attempts,candidate_ids) VALUES('attempted','review_ready',2,'[\"sealed\"]')")
            store.db.commit();result=store.regroup(6)
            self.assertEqual(result['retained_parent_batches'],2)
            queued=[json.loads(r[0]) for r in store.db.execute("SELECT candidate_ids FROM batches WHERE state='queued'")]
            self.assertEqual(sorted(cid for cohort in queued for cid in cohort),list('abcdefg'))
            self.assertEqual(sorted(len(c) for c in queued),[1,6])
            self.assertEqual(tuple(store.db.execute("SELECT state,attempts FROM batches WHERE id='attempted'").fetchone()),('review_ready',2))
            self.assertEqual(store.db.execute('SELECT count(*) FROM dispositions').fetchone()[0],7)
            self.assertEqual(len(json.loads(store.claim()['candidate_ids'])),6)
            store.db.close()

    def test_explicit_retry_preserves_old_attempt_and_rejects_failed_independent_review(self):
        with tempfile.TemporaryDirectory() as td:
            store=review.ReviewStore(td)
            for bid,error in [('budget','review_context_over_budget'),('sample','independent_sample_not_confirmed')]:
                store.db.execute('INSERT INTO batches(id,state,attempts,candidate_ids,error) VALUES(?,?,?,?,?)',
                                 (bid,'deferred',1,encoded([bid]),error))
                store.db.execute('INSERT INTO dispositions VALUES(?,?,?,?,?,?,?)',(bid,'doc','rev','deferred',bid,'','now'))
            store.db.commit();store.retry_context('budget')
            self.assertEqual(tuple(store.db.execute("SELECT state,attempts FROM batches WHERE id='budget'").fetchone()),('queued',1))
            with self.assertRaisesRegex(ValueError,'only_context_budget'):store.retry_context('sample')
            store.db.close()

    def test_progress_reports_names_but_never_original_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=review.ReviewStore(td);bid='c'*64
            store.db.execute('INSERT INTO batches(id,doc_id,state,attempts,updated,error,candidate_ids) VALUES(?,?,?,?,?,?,?)',
                             (bid,'doc','deferred',1,'2026-10-08T02:00:00Z','review_context_over_budget','[]'))
            store.db.commit();store.db.close();(root/'catalog').mkdir()
            conn=review.sqlite3.connect(root/'catalog/catalog.sqlite')
            conn.execute('CREATE TABLE documents(doc_id,original_name,sha256,original_rel)')
            conn.execute('INSERT INTO documents VALUES(?,?,?,?)',('doc','Original report.pdf','a'*64,'private/path'))
            conn.commit();conn.close()
            value=review.progress(td);self.assertEqual(value['budget_failures'][0]['title'],'Original report.pdf')
            self.assertNotIn('private/path',encoded(value))
            safe=registry._research_verification(value)
            self.assertEqual(safe['budget_failures'][0]['batch_id'],bid)
            value['budget_failures'][0]['original_rel']='private/path'
            self.assertNotIn('original_rel',encoded(registry._research_verification(value)))

    def test_unmatched_actual_demand_stops_after_matching_without_adoption_call(self):
        packet,row=fixture()
        class Client:
            profile=type('Profile',(),{'context':65536,'max_output_tokens':8192})()
            calls=0
            def generate(self,system,user):
                self.calls+=1
                self.asserted_system=system
                return {'matches':[{'id':row['id'],'question_ids':[],
                                    'rationale':'No current substantive demand','context_terms':[]}]}
        with tempfile.TemporaryDirectory() as td:
            store=review.ReviewStore(td);bid=packet['batch_id'];client=Client()
            store.db.execute('INSERT INTO batches(id,state,candidate_ids) VALUES(?,?,?)',(bid,'queued',encoded([row['id']])))
            store.db.execute('INSERT INTO dispositions VALUES(?,?,?,?,?,?,?)',(row['id'],'doc','rev','queued',bid,'','now'))
            store.db.commit()
            with patch.object(store,'packet',return_value=packet), \
                 patch.object(registry,'current_tasks',return_value=[{'wid':'Q-q1','title':'Current demand','object_ids':['root']}]), \
                 patch.object(review,'context',return_value={'question_ids':[],'knowledge':{'statements':[]},'current_workorders':[]}):
                store.run_one(Path('/unused'),client)
            self.assertEqual(client.calls,1)
            self.assertEqual(store.db.execute('SELECT state FROM dispositions').fetchone()[0],'needs_demand_match')
            self.assertFalse((store.directory/bid/'bundle.json').exists())
            store.db.close()


if __name__=='__main__':unittest.main()
