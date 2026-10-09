import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inresearch.workflow import research_review as review
from inresearch.knowledge import registry
from inresearch.materials.artifacts import atomic_json, digest_file, encoded
from test_research_review import fixture, audit
from test_research import adopted_knowledge, delegated_review
import test_research as research_fixture


def mapped_fixture():
    packet,row=fixture()
    packet['research_context']['object_mapping_contract']=review.object_mapping_contract(registry.ROOT)
    packet['context_sha256']=review.sha(packet['research_context'])
    packet['items'][0]['candidate']['object_ids']=['system:control']
    packet['items'][0]['evidence'][0]['object_ids']=['system:control']
    row.update(object_ids=[],object_mapping_check='Enterprise application, not DCIM/BMS hardware controls.')
    return packet,row


def mapped_audit(directory,packet,row):
    bundle=audit(directory,packet,row)
    req=json.loads((directory/'request.json').read_text());req['system']=review.review_system(packet)
    atomic_json(directory/'request.json',req);bundle['request_sha256']=digest_file(directory/'request.json')
    req=json.loads((directory/'sampling-request.json').read_text());req['system']=review.review_system(packet,sampling=True)
    atomic_json(directory/'sampling-request.json',req)
    return bundle


class ObjectMappingReviewTests(unittest.TestCase):
    def setup_root(self,root):
        atomic_json(root/'framework/research_graph.json',registry.read_json(registry.ROOT/'framework/research_graph.json'))
        atomic_json(root/'framework/research_questions.json',{'records':[{'id':'q1','object_ids':['root'],
                    'text':'Current question', 'acceptance':'Independent research required','evidence_requirements':['original evidence']}]})
        atomic_json(root/'data/research_knowledge.json',{k:[] for k in registry.COLLECTIONS})

    def test_explicit_empty_or_registered_actor_and_reason_are_required(self):
        packet,row=mapped_fixture()
        self.assertEqual(review.validate_reviews(packet,{'reviews':[row]}),[row])
        row['object_ids']=['actor:alphabet-google']
        self.assertEqual(review.validate_reviews(packet,{'reviews':[row]}),[row])
        control=next(o for o in packet['research_context']['object_mapping_contract']['objects'] if o['id']=='system:control')
        self.assertEqual(control['chains'],['DCIM/BMS 与固件'])
        for key,value in [('object_ids',None),('object_ids',['unknown']),('object_ids',['root','root']),
                          ('object_ids',[False]),('object_mapping_check',' '),('object_mapping_check',None)]:
            bad=copy.deepcopy(row);bad[key]=value
            with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,'explicit_reviewed'):
                review.validate_reviews(packet,{'reviews':[bad]})
        packet['research_context']['object_mapping_contract']['version']='unrecognized'
        with self.assertRaisesRegex(ValueError,'unsupported_object_mapping'):
            review.validate_reviews(packet,{'reviews':[row]})

    def test_promotion_uses_reviewed_scope_for_statement_and_evidence_keeps_candidate(self):
        packet,row=mapped_fixture();original=copy.deepcopy(packet)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.setup_root(root);directory=root/'audit';directory.mkdir()
            bundle=mapped_audit(directory,packet,row)
            with patch.object(review,'current_context',return_value=packet['research_context']):
                result=review.promote(root,bundle,directory)
            knowledge=registry.read_json(root/'data/research_knowledge.json')
            self.assertEqual(result['closed_questions_added'],0)
            self.assertEqual(knowledge['answers'],[])
            self.assertEqual(knowledge['statements'][0]['object_ids'],[])
            self.assertEqual(knowledge['evidence'][0]['object_ids'],[])
            self.assertTrue(registry.supported_adoption(knowledge['statements'][0],knowledge))
            self.assertEqual(packet,original)
            self.assertEqual(json.loads((directory/'packet.json').read_text()),original)

    def test_sampling_binds_the_actual_reviewed_object_scope(self):
        packet,row=mapped_fixture()
        with tempfile.TemporaryDirectory() as td:
            directory=Path(td);bundle=mapped_audit(directory,packet,row)
            self.assertTrue(review.verify_audit(bundle,directory))
            req=json.loads((directory/'sampling-request.json').read_text())
            sample=json.loads(req['user']);sample['proposed_reviews'][0]['object_ids']=['root']
            req['user']=encoded(sample);atomic_json(directory/'sampling-request.json',req)
            import hashlib
            bundle['sampling']['model']['input_sha256']=hashlib.sha256(req['user'].encode()).hexdigest()
            resp=json.loads((directory/'sampling-response.json').read_text());resp['_model']=bundle['sampling']['model']
            atomic_json(directory/'sampling-response.json',resp)
            with self.assertRaisesRegex(ValueError,'independent_sample_audit'):
                review.verify_audit(bundle,directory)

    def test_legacy_audit_and_applied_replay_survive_but_unpublished_requires_new_context(self):
        packet,row=fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.setup_root(root);directory=root/'audit';directory.mkdir()
            bundle=audit(directory,packet,row)
            self.assertTrue(review.verify_audit(bundle,directory))
            with self.assertRaisesRegex(ValueError,'research_context_changed'):
                review.promote(root,bundle,directory)
            sid='adoption:review:'+__import__('hashlib').sha256(row['id'].encode()).hexdigest()[:24]
            atomic_json(root/'data/research_knowledge.json',{'statements':[{'id':sid,'audit_receipt':{'request_sha256':bundle['request_sha256']}}]})
            self.assertEqual(review.promote(root,bundle,directory)['state'],'already_applied')
            self.assertEqual(review.review_system(packet),review.SYSTEM)

    def test_graph_definition_changes_make_mapping_context_stale(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.setup_root(root)
            with patch.object(registry,'current_tasks',return_value=[]):
                ctx=review.context(root,['q1'])
                old=copy.deepcopy(ctx);old.pop('object_mapping_contract')
                self.assertNotEqual(review.sha(review.current_context(root,old)),review.sha(old))
                self.assertEqual(review.current_context(root,ctx),ctx)
                graph=registry.read_json(root/'framework/research_graph.json')
                graph['objects'][0]['name']='Changed definition';atomic_json(root/'framework/research_graph.json',graph)
                self.assertNotEqual(review.sha(review.current_context(root,ctx)),review.sha(ctx))

    def test_existing_shared_evidence_mapping_mismatch_cannot_be_silently_rewritten(self):
        packet,row=mapped_fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.setup_root(root);directory=root/'audit';directory.mkdir()
            bundle=mapped_audit(directory,packet,row)
            knowledge=registry.read_json(root/'data/research_knowledge.json')
            previous=copy.deepcopy(packet['items'][0]['evidence'][0]);previous['acceptance']='adopted'
            knowledge['evidence']=[previous];atomic_json(root/'data/research_knowledge.json',knowledge)
            before=(root/'data/research_knowledge.json').read_bytes()
            with patch.object(review,'current_context',return_value=packet['research_context']):
                with self.assertRaisesRegex(ValueError,'existing_evidence_requires_explicit_review'):
                    review.promote(root,bundle,directory)
            self.assertEqual((root/'data/research_knowledge.json').read_bytes(),before)

    def test_object_directory_obeys_existing_byte_budget_and_retains_split_parent(self):
        packet,row=mapped_fixture();packet['unsupported']=[]
        other=copy.deepcopy(packet['items'][0]);other['candidate']['id']='candidate:other'
        packet['items'].append(other)
        class Client:
            profile=type('Profile',(),{'context':8192,'max_output_tokens':128,'identity':{}})()
            calls=0
            def generate(self,system,user):
                self.calls+=1
                return {}
        with tempfile.TemporaryDirectory() as td:
            store=review.ReviewStore(td)
            bid=packet['batch_id'];ids=[row['id'],'candidate:other']
            store.db.execute('INSERT INTO batches(id,doc_id,revision_id,report_sha,state,candidate_ids,updated) VALUES(?,?,?,?,?,?,?)',
                             (bid,'doc','rev','report','queued',encoded(ids),'now'))
            store.db.commit();client=Client()
            with patch.object(store,'packet',return_value=packet),patch.object(review,'match_packet',return_value={}),patch.object(review,'apply_matches'):
                store.run_one(Path('/unused'),client)
            self.assertEqual(client.calls,1)  # Matching happened; full review was never sent over budget.
            self.assertEqual(store.db.execute('SELECT state FROM batches WHERE id=?',(bid,)).fetchone()[0],'split_context')
            self.assertEqual(store.db.execute("SELECT count(*) FROM batches WHERE state='queued'").fetchone()[0],2)
            self.assertTrue((store.directory_for(bid)/'attempt-0001'/'packet.json').exists())
            self.assertEqual({o['id'] for o in packet['research_context']['object_mapping_contract']['objects']},
                             {o['id'] for o in registry.read_json(registry.ROOT/'framework/research_graph.json')['objects']})
            store.db.close()

    def test_technical_narrowing_preserves_full_before_original_review_and_support(self):
        knowledge=adopted_knowledge();old=knowledge['statements'][0];old['object_ids']=['system:control','system:it']
        before=copy.deepcopy(old)
        result=registry.narrow_object_mapping(old,[],delegated_review(),'No facility asset asserted.','audit.md#mapping')
        self.assertEqual(old,before)
        self.assertEqual(result['review'],before['review'])
        self.assertEqual(result['object_mapping_review']['before_record'],before)
        self.assertEqual(result['object_mapping_review']['before_record_sha256'],registry.mapping_record_sha256(before))
        knowledge['statements'][0]=result
        self.assertTrue(registry.supported_adoption(result,knowledge))
        self.assertEqual(registry.completed_questions(knowledge),{'M01-Q01'})
        compact=review.compact_receipts(result)
        self.assertEqual(compact['object_mapping_review']['before_record']['sha256'],review.sha(before))
        self.assertEqual(compact['text'],result['text'])

    def test_technical_narrowing_rejects_other_edits_expansion_bad_grant_or_forged_history(self):
        row=adopted_knowledge()['statements'][0];row['object_ids']=['system:control']
        valid=registry.narrow_object_mapping(row,[],delegated_review(),'Wrong facility mapping.','audit.md#mapping')
        for ids in (['actor:alphabet-google'],['system:control'],['system:control','system:it'],[False]):
            with self.subTest(ids=ids),self.assertRaises(ValueError):
                registry.narrow_object_mapping(row,ids,delegated_review(),'Reason.','audit.md#mapping')
        mutations=[lambda r:r.update(text='Changed substantive statement'),
                   lambda r:r.update(question_ids=['M03-Q05']),
                   lambda r:r['review'].update(by='Fake original reviewer'),
                   lambda r:r['object_mapping_review'].update(before_record_sha256='0'*64),
                   lambda r:r['object_mapping_review']['review']['delegation'].update(delegate='Someone else'),
                   lambda r:r['object_mapping_review']['review'].update(replaces_record_ids=['old']),
                   lambda r:r['object_mapping_review']['review'].update(relaxes_distribution=True),
                   lambda r:r['object_mapping_review'].update(reference=' ')]
        for mutate in mutations:
            bad=copy.deepcopy(valid);mutate(bad)
            self.assertFalse(registry.review_valid(bad))
        for bad_value in (float('nan'),object()):
            bad=copy.deepcopy(valid)
            bad['object_mapping_review']['before_record']['non_json']=bad_value
            bad['non_json']=bad_value
            self.assertFalse(registry.object_mapping_review_valid(bad))
        with self.assertRaises(ValueError):
            registry.narrow_object_mapping(valid,[],delegated_review(),'Repeat.','audit.md#mapping')

    def test_invalid_supplemental_evidence_review_reopens_support_chain(self):
        knowledge=adopted_knowledge();ev=knowledge['evidence'][0];ev['object_ids']=['system:control']
        knowledge['evidence'][0]=registry.narrow_object_mapping(ev,[],delegated_review(),'Wrong facility mapping.','audit.md#mapping')
        self.assertEqual(registry.completed_questions(knowledge),{'M01-Q01'})
        knowledge['evidence'][0]['object_mapping_review']['review']['delegation']['reference']=' '
        self.assertFalse(registry.supported_adoption(knowledge['statements'][0],knowledge))
        self.assertEqual(registry.completed_questions(knowledge),set())


class ObjectMappingHTTPTests(unittest.TestCase):
    setUp=research_fixture.ReaderSnapshotHTTPTests.setUp
    stop_server=research_fixture.ReaderSnapshotHTTPTests.stop_server
    request=research_fixture.ReaderSnapshotHTTPTests.request

    def test_real_adopted_http_retains_original_B_and_actual_mapping_delegate_without_before_payload(self):
        knowledge=adopted_knowledge()
        for table in ('statements','evidence'):
            old=knowledge[table][0];old['object_ids']=['system:control']
            old['review'].update(tier='B',authority='reviewer',by='Original C3 reviewer')
            actual=delegated_review();actual['private_audit']='PRIVATE_MAPPING'
            knowledge[table][0]=registry.narrow_object_mapping(old,[],actual,'Not a facility system.','audit.md#mapping')
        registry.atomic_json(self.curated_path,knowledge)
        code,detail=self.request('GET','/api/research-adopted?node=root')
        self.assertEqual(code,200)
        for table in ('statements','evidence'):
            row=detail['knowledge'][table][0]
            self.assertEqual(row['review']['by'],'Original C3 reviewer')
            supplement=row['object_mapping_review']
            self.assertNotIn('before_record',supplement)
            self.assertEqual(supplement['reviewed_object_ids'],[])
            self.assertEqual(supplement['review']['by'],delegated_review()['by'])
            self.assertEqual(set(supplement['review']['delegation']),set(registry.DELEGATION_KEYS))
        self.assertNotIn('PRIVATE_MAPPING',json.dumps(detail))
        knowledge['evidence'][0]['object_mapping_review']['review']['delegation']['delegate']='Invalid agent'
        registry.atomic_json(self.curated_path,knowledge)
        self.assertEqual(self.request('GET','/api/research-adopted?node=root')[1]['knowledge']['statements'],[])
