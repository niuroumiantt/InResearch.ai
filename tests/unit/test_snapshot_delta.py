import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from inresearch.delivery import snapshot_delta as delta
from inresearch.knowledge import registry
from inresearch.workflow import commands
from inresearch.storage.files import write_json
from test_research import complete_document


class CandidateDeltas(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('research_graph.json', 'research_questions.json'):
            write_json(self.root/'framework'/name, registry.read_json(registry.ROOT/'framework'/name))
        self.graph = registry.read_json(self.root/'framework/research_graph.json')
        self.questions = registry.read_json(self.root/'framework/research_questions.json')
        self.empty = {k: [] for k in delta.COLLECTIONS}
        write_json(self.root/'data/research_knowledge.json', self.empty)
        self.destination = self.root/'data/research_runtime.json'

    def snapshot(self, chars='a', generated='2026-10-12T00:00:00+00:00'):
        knowledge = copy.deepcopy(self.empty)
        knowledge['documents'] = [complete_document(c * 64) for c in chars]
        return dict(generated=generated, graph_version=self.graph['version'],
                    questions_version=self.questions['version'], knowledge=knowledge,
                    reader={}, acceptance='candidate', schema_version=1)

    def normalized(self, value):
        return registry.candidate_snapshot(value, self.graph, self.questions)

    def manifest(self):
        return commands.receive_snapshot(self.root, {'operation':'candidate-manifest-v1'})

    def test_partial_delivery_retains_absent_documents_and_resume_only_sends_remaining(self):
        commands.receive_snapshot(self.root, self.snapshot('a'))
        newer = self.normalized(self.snapshot('abc'))
        with patch.object(delta, 'MAX_DOCUMENTS', 1):
            parts = list(delta.batches(newer, self.manifest()))
        self.assertEqual([x[0] for x in parts], [[complete_document('b'*64)['id']], [complete_document('c'*64)['id']]])
        ids, grouped = parts[0]
        patch_payload = delta.envelope(newer, ids, grouped, self.manifest()['base_generated'])
        receipt = commands.receive_snapshot(self.root, patch_payload)
        self.assertEqual((receipt['documents'], receipt['applied_documents']), (2,1))
        remaining = list(delta.batches(newer, self.manifest()))
        self.assertEqual(remaining[0][0], [complete_document('c'*64)['id']])
        commands.receive_snapshot(self.root, delta.envelope(newer,*remaining[0],self.manifest()['base_generated']))
        self.assertEqual(len(registry.read_json(self.destination)['knowledge']['documents']),3)
        self.assertEqual(registry.read_json(self.root/'data/research_knowledge.json'), self.empty)

    def test_changed_base_rejects_whole_batch_without_writes(self):
        commands.receive_snapshot(self.root, self.snapshot('a'))
        newer = self.normalized(self.snapshot('ab')); remote = self.manifest()
        ids, grouped = next(delta.batches(newer, remote)); payload = delta.envelope(newer,ids,grouped,remote['base_generated'])
        commands.receive_snapshot(self.root, self.snapshot('ac','2026-10-12T00:00:01+00:00'))
        before = self.destination.read_bytes()
        with self.assertRaises(commands.Rejected) as exc:commands.receive_snapshot(self.root,payload)
        self.assertEqual(exc.exception.status,409);self.assertEqual(self.destination.read_bytes(),before)

    def test_invalid_support_or_document_set_cannot_install(self):
        commands.receive_snapshot(self.root,self.snapshot('a'))
        newer=self.normalized(self.snapshot('ab'));ids,grouped=next(delta.batches(newer,self.manifest()))
        payload=delta.envelope(newer,ids,grouped,self.manifest()['base_generated']);before=self.destination.read_bytes()
        payload['snapshot']['knowledge']['evidence'].append({'id':'orphan','document_id':'not-selected'})
        with self.assertRaises(ValueError):commands.receive_snapshot(self.root,payload)
        self.assertEqual(self.destination.read_bytes(),before)

    def test_empty_receiver_bootstraps_and_unchanged_manifest_only_updates_status(self):
        value=self.normalized(self.snapshot('a'));remote=self.manifest();self.assertIsNone(remote['base_generated'])
        ids,grouped=next(delta.batches(value,remote));commands.receive_snapshot(self.root,delta.envelope(value,ids,grouped,None))
        parts=list(delta.batches(value,self.manifest()));self.assertEqual(parts[0][0],[])
        receipt=commands.receive_snapshot(self.root,delta.envelope(value,*parts[0],self.manifest()['base_generated']))
        self.assertEqual(receipt['applied_documents'],0)

    def test_same_document_replacement_preserves_other_documents(self):
        commands.receive_snapshot(self.root,self.snapshot('ab'));before=registry.read_json(self.destination)
        newer=self.snapshot('a');newer['knowledge']['documents'][0]['title']='updated title'
        newer=self.normalized(newer);ids,grouped=next(delta.batches(newer,self.manifest()))
        commands.receive_snapshot(self.root,delta.envelope(newer,ids,grouped,self.manifest()['base_generated']))
        after=registry.read_json(self.destination)['knowledge']['documents']
        self.assertEqual(len(after),2);self.assertEqual(next(x for x in after if x['id']==complete_document('b'*64)['id']),before['knowledge']['documents'][1])

    def test_single_oversize_document_and_cross_document_answers_remain_explicit_blocks(self):
        value=self.normalized(self.snapshot('a'))
        with patch.object(delta,'MAX_DELTA_BYTES',10):
            with self.assertRaises(ValueError):list(delta.batches(value,delta.manifest({'knowledge':self.empty})))
        value['knowledge']['answers']=[{'id':'answer:never-auto-adopt'}]
        with self.assertRaises(ValueError):delta.hashes(value['knowledge'])

    def test_publisher_resumes_receiver_acknowledged_batches_after_transport_failure(self):
        import gzip
        from inresearch.delivery import publish
        commands.receive_snapshot(self.root,self.snapshot('a'))
        value=self.snapshot('abcd');calls=[];delta_calls=0
        def deliver(request,max_response_bytes=4096):
            nonlocal delta_calls
            payload=json.loads(gzip.decompress(request.data));calls.append(payload)
            if payload['operation']=='candidate-delta-v1':
                delta_calls+=1
                if delta_calls==2:raise ValueError('injected transport loss')
            return commands.receive_snapshot(self.root,payload),1
        with patch.object(delta,'MAX_DOCUMENTS',1),patch.object(publish,'post_snapshot',side_effect=deliver):
            with self.assertRaisesRegex(ValueError,'transport loss'):
                publish.post_incremental(value,'https://receiver.test/api/reader-snapshot','private',self.root,self.root)
            self.assertEqual(len(registry.read_json(self.destination)['knowledge']['documents']),2)
            remaining=[]
            def resume(request,max_response_bytes=4096):
                payload=json.loads(gzip.decompress(request.data))
                if payload['operation']=='candidate-delta-v1':remaining.extend(payload['document_ids'])
                return commands.receive_snapshot(self.root,payload),1
            with patch.object(publish,'post_snapshot',side_effect=resume):
                result=publish.post_incremental(value,'https://receiver.test/api/reader-snapshot','private',self.root,self.root)
        self.assertEqual(result['incremental_documents'],2)
        self.assertNotIn(complete_document('b'*64)['id'],remaining)
        self.assertEqual(len(registry.read_json(self.destination)['knowledge']['documents']),4)
        self.assertEqual(registry.read_json(self.root/'data/research_knowledge.json'),self.empty)

    def test_oversize_export_normalizes_receiver_fields_without_losing_accepted_evidence(self):
        from inresearch.delivery import publish
        value=self.snapshot('ab')
        value['knowledge']['documents'][0]['local_projection_only']='unretained'*10000
        expected=self.normalized(value);expected.pop('received_at',None)
        limit=len(publish.encoded(expected).encode())+256
        with patch.object(commands,'SNAPSHOT_MAX_BYTES',limit):
            normalized,body=publish.transport_payload(value,self.root)
        self.assertLess(len(body),limit)
        self.assertNotIn('local_projection_only',normalized['knowledge']['documents'][0])
        self.assertIn('local_projection_only',value['knowledge']['documents'][0])
        self.assertEqual(normalized['knowledge'],expected['knowledge'])
        twice=self.normalized(normalized);twice.pop('received_at',None)
        self.assertEqual(twice,expected)

    def test_committed_delta_with_lost_ack_replays_exact_bytes_and_rejects_changed_content(self):
        commands.receive_snapshot(self.root,self.snapshot('a'))
        value=self.normalized(self.snapshot('ab'));remote=self.manifest()
        ids,grouped=next(delta.batches(value,remote));payload=delta.envelope(value,ids,grouped,remote['base_generated'])
        first=commands.receive_snapshot(self.root,payload);before=self.destination.read_bytes()
        replay=commands.receive_snapshot(self.root,payload)
        self.assertTrue(replay['replayed']);self.assertEqual(replay['received_at'],first['received_at'])
        self.assertEqual(replay['applied_documents'],1);self.assertEqual(self.destination.read_bytes(),before)
        corrupt=copy.deepcopy(payload);corrupt['snapshot']['knowledge']['documents'][0]['title']='changed after commit'
        with self.assertRaises(commands.Rejected) as exc:commands.receive_snapshot(self.root,corrupt)
        self.assertEqual(exc.exception.status,409);self.assertEqual(self.destination.read_bytes(),before)

    def test_explicit_incremental_mode_never_posts_the_complete_body(self):
        import contextlib,io,os
        from inresearch.delivery import publish
        token=self.root/'reader-sync.token';token.write_text('private-fixture-token-'*3);token.chmod(0o600)
        value=self.snapshot('a')
        for doc in value['knowledge']['documents']:doc['doc_id']=doc['id']
        with patch.dict(os.environ,{'READER_STATE_ROOT':str(self.root),'READER_REPO_ROOT':str(self.root),
                                   'READER_PUBLISH_URL':'https://receiver.test/api/reader-snapshot','READER_PUBLISH_INCREMENTAL':'1'}), \
             patch.object(publish,'Reader') as reader,patch.object(publish,'ModelClient'), \
             patch.object(publish.subprocess,'run') as worker, \
             patch.object(publish,'post_snapshot',side_effect=AssertionError('full body is forbidden in explicit delta mode')), \
             patch.object(publish,'post_incremental',return_value={'ok':True,'documents':1,'received_at':'2026-10-13T00:00:00Z','incremental_documents':1}) as send, \
             contextlib.redirect_stdout(io.StringIO()):
            r=reader.return_value.initialize.return_value;r.data=self.root
            r.export_snapshot.return_value=value;r.snapshot.return_value={'objects':self.graph['objects'],'questions':self.questions['records']}
            worker.return_value.returncode=0
            self.assertEqual(publish.main([]),0);self.assertEqual(send.call_count,1)
        self.assertEqual(json.loads((self.root/'publish-status.json').read_text())['transport'],'candidate-delta-v1')
        with patch.dict(os.environ,{'READER_PUBLISH_INCREMENTAL':'maybe'}):
            with self.assertRaisesRegex(ValueError,'must be 0 or 1'):publish.main([])
