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


if __name__=='__main__':unittest.main()
