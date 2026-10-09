import copy
import contextlib
import io
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from inresearch.materials.artifacts import atomic_json, digest_file
from inresearch.knowledge import registry
from inresearch.workflow import research_review as review
from inresearch.workflow import research_publish as publication
from test_research_review import fixture, audit
import test_research_local_acceptance as local_tests


def website_fixture_run(body, *, observed=None, tag_image=None, ancestry=0, health=None, calls=None):
    observed=observed or {'image':'sha256:'+'b'*64,'tag':'inresearch-app:'+'f'*40,
                         'status':'running','health':'healthy'}
    health=health or {'status':200,'ok':True}
    def run(argv,*args,**kwargs):
        if calls is not None:calls.append(list(argv))
        if argv[:3]==['git','merge-base','--is-ancestor']:
            return SimpleNamespace(stdout='',returncode=ancestry)
        if argv[0]=='scp':return SimpleNamespace(stdout='',returncode=0)
        if argv[0]!='ssh':raise AssertionError('unexpected website command '+repr(argv))
        command=argv[-1]
        if 'docker image inspect' in command:
            return SimpleNamespace(stdout=tag_image or observed['image'],returncode=0)
        if 'docker inspect' in command:
            return SimpleNamespace(stdout=json.dumps(observed),returncode=0)
        if kwargs.get('input') and '/healthz' in kwargs['input']:
            return SimpleNamespace(stdout=json.dumps(health),returncode=0)
        if kwargs.get('input'):
            return SimpleNamespace(stdout=json.dumps(body),returncode=0)
        raise AssertionError('unexpected website command '+repr(argv))
    return run


def audited_member(directory, packet, row, attempt='attempt-0001'):
    directory.mkdir(parents=True,exist_ok=True)
    bundle=audit(directory,packet,row)
    for name,sampling in [('request.json',False),('sampling-request.json',True)]:
        request=json.loads((directory/name).read_text())
        request['system']=review.review_system(packet,sampling=sampling)
        atomic_json(directory/name,request)
    bundle.update(attempt=attempt,request_sha256=digest_file(directory/'request.json'))
    atomic_json(directory/'bundle.json',bundle)
    return bundle


class GroupPromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'framework').mkdir();(self.root/'data').mkdir()
        atomic_json(self.root/'framework/research_graph.json',
                    json.loads((registry.ROOT/'framework/research_graph.json').read_text()))
        atomic_json(self.root/'framework/research_questions.json',{'records':[{
            'id':'q1','text':'Open mechanism question','object_ids':['root'],
            'acceptance':'Independent validation','evidence_requirements':['independent sources']}]})
        self.knowledge=self.root/'data/research_knowledge.json'
        atomic_json(self.knowledge,{'documents':[],'evidence':[],'statements':[],'answers':[]})
        self.before=self.knowledge.read_bytes()
        self.members=[]
        for index in range(2):
            packet,row=fixture()
            packet['batch_id']=str(index+1)*64
            packet['items'][0]['candidate']['id']='candidate:'+str(index)
            packet['items'][0]['candidate']['evidence_ids']=['ev:'+str(index)]
            packet['items'][0]['evidence'][0]['id']='ev:'+str(index)
            row.update(id='candidate:'+str(index),evidence_ids=['ev:'+str(index)],
                       object_ids=[],object_mapping_check='Algorithm scope has no facility mapping.')
            packet['research_context']=review.context(self.root,['q1'])
            packet['context_sha256']=review.sha(packet['research_context'])
            directory=self.root/('audit'+str(index))
            bundle=audited_member(directory,packet,row)
            self.members.append((bundle,directory))

    def test_same_question_members_verify_on_untouched_baseline_then_one_write(self):
        before_hashes=[digest_file(d/'bundle.json') for _,d in self.members]
        real_write=review.write_json
        snapshots=[]
        def write(path,value):
            snapshots.append(self.knowledge.read_bytes())
            return real_write(path,value)
        with patch.object(review,'write_json',side_effect=write) as writer:
            result=review.promote_group(self.root,self.members)
        self.assertEqual(writer.call_count,1)
        self.assertEqual(snapshots,[self.before])
        knowledge=json.loads(self.knowledge.read_text())
        self.assertEqual(len(knowledge['statements']),2)
        self.assertEqual(len(knowledge['documents']),1)
        self.assertEqual(knowledge['answers'],[])
        self.assertEqual(registry.completed_questions(knowledge),set())
        self.assertEqual([m['batch_id'] for m in result['members']],['1'*64,'2'*64])
        self.assertEqual([digest_file(d/'bundle.json') for _,d in self.members],before_hashes)
        for bundle,_ in self.members:
            self.assertNotEqual(review.sha(review.current_context(self.root,bundle['packet']['research_context'])),
                                bundle['packet']['context_sha256'])

    def test_sequential_single_promotes_really_stale_second_but_group_does_not(self):
        review.promote(self.root,*self.members[0])
        with self.assertRaisesRegex(ValueError,'context_changed'):
            review.promote(self.root,*self.members[1])
        self.knowledge.write_bytes(self.before)
        self.assertEqual(len(review.promote_group(self.root,self.members)['statement_ids']),2)

    def test_any_bad_audit_sample_or_context_preserves_entire_baseline(self):
        for fault in ('audit','sample','context'):
            with self.subTest(fault=fault):
                bundle,directory=self.members[1]
                original=copy.deepcopy(bundle)
                if fault=='audit':bundle['request_sha256']='0'*64
                elif fault=='sample':bundle['sampling']['checks'][0]['confirmed']=False
                else:bundle['packet']['context_sha256']='stale'
                with self.assertRaises(ValueError):review.promote_group(self.root,self.members)
                self.assertEqual(self.knowledge.read_bytes(),self.before)
                bundle.clear();bundle.update(original)

    def test_cross_member_evidence_collision_is_not_silently_merged(self):
        bundle,directory=self.members[1]
        packet=copy.deepcopy(bundle['packet']);row=copy.deepcopy(bundle['reviews'][0])
        packet['items'][0]['candidate']['evidence_ids']=['ev:0']
        packet['items'][0]['evidence'][0].update(id='ev:0',quote='Different quotation')
        packet['items'][0]['native_pages']={'0':'Different quotation'}
        row['evidence_ids']=['ev:0']
        self.members[1]=(audited_member(directory,packet,row),directory)
        with self.assertRaisesRegex(ValueError,'existing_evidence'):
            review.promote_group(self.root,self.members)
        self.assertEqual(self.knowledge.read_bytes(),self.before)

    def test_replay_retains_actual_per_batch_lineage_and_does_not_rewrite(self):
        first=review.promote_group(self.root,self.members)
        before=self.knowledge.read_bytes()
        with patch.object(review,'write_json') as writer:
            replay=review.promote_group(self.root,self.members)
        self.assertEqual(replay['state'],'already_applied')
        self.assertEqual(replay['statement_ids'],first['statement_ids'])
        writer.assert_not_called()
        self.assertEqual(self.knowledge.read_bytes(),before)


class GroupPublisherTests(unittest.TestCase):
    def setUp(self):
        # Reuse the actual immutable audit/receipt harness, not implementation
        # copies. Imported TestCase is removed from module discovery below.
        self.case=local_tests.LocalAcceptanceTests()
        self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.publisher=self.case.publisher
        self.directory=self.case.root/'group';self.directory.mkdir()
        members=[]
        for i in range(2):
            bid=str(i+1)*64
            folder=self.directory/'members'/bid/'attempt-0001'
            packet,row=fixture();packet['batch_id']=bid
            row['id']='candidate:'+str(i)
            packet['items'][0]['candidate']['id']=row['id']
            bundle=audited_member(folder,packet,row)
            sid='adoption:review:'+hashlib.sha256(row['id'].encode()).hexdigest()[:24]
            members.append({'batch_id':bid,'attempt':'attempt-0001','bundle_sha256':digest_file(folder/'bundle.json'),
                            'request_sha256':bundle['request_sha256'],'context_sha256':packet['context_sha256'],
                            'statement_ids':[sid]})
        self.journal={**self.case.journal,'batch_id':'e'*64,'members':members,
                      'statement_ids':[sid for m in members for sid in m['statement_ids']]}
        self.case.journal=self.journal
        self.proofs={m['batch_id']:{'verified':True,'batch_id':m['batch_id'],'attempt':m['attempt'],
            'bundle_sha256':m['bundle_sha256'],'context_current':True} for m in members}
        self.publisher.remote=Mock(side_effect=lambda verb,*args: self.proofs[args[1]] if verb=='verify' else {})
        with patch.object(publication,'run',side_effect=self.case.command):
            self.publisher.write_group_manifest(self.journal,self.directory)

    def test_group_receipt_binds_whole_manifest_and_zero_ci_then_exact_merge(self):
        with patch.object(publication,'run',side_effect=self.case.command), \
                patch.object(publication,'publication_checks',side_effect=AssertionError('CI')), \
                patch.object(publication,'refresh_publication_base',return_value='a'*40):
            result=self.publisher.advance(self.directory,self.journal)
        self.assertNotIn('error',result)
        self.assertEqual(len(self.case.merges()),1)
        ref=result['local_acceptance'];receipt=json.loads((self.directory/ref['path']).read_text())
        self.assertEqual(receipt['version'],2)
        self.assertEqual(receipt['binding']['group_id'],'e'*64)
        self.assertEqual(receipt['binding']['manifest_sha256'],result['group_manifest']['sha256'])
        self.assertEqual(self.publisher.remote.call_count,4)

    def test_member_change_or_manifest_wrong_sha_cannot_reuse_pass(self):
        with patch.object(publication,'run',side_effect=self.case.command):
            self.publisher.accept_local(self.journal,self.directory)
        self.journal['members'][1]['statement_ids']=['unreviewed']
        with patch.object(publication,'run',side_effect=self.case.command), \
                patch.object(publication,'refresh_publication_base',return_value='a'*40):
            result=self.publisher.advance(self.directory,self.journal)
        self.assertIn('group_manifest_changed',result['error'])
        self.assertFalse(self.case.merges())

    def test_one_stale_member_revalidates_only_that_batch_without_checks_or_merge(self):
        self.proofs['2'*64]['context_current']=False
        with patch.object(publication,'run',side_effect=self.case.command), \
                patch.object(publication,'refresh_publication_base',return_value='a'*40):
            result=self.publisher.advance(self.directory,self.journal)
        self.assertEqual(result['state'],'revalidation')
        self.publisher.remote.assert_any_call('revalidate','--batch-id','2'*64)
        self.assertNotIn(('revalidate','--batch-id','1'*64),[c.args for c in self.publisher.remote.call_args_list])
        self.assertFalse(self.case.merges())

    def test_global_main_move_after_checks_invalidates_group_head_and_receipt(self):
        with patch.object(publication,'run',side_effect=self.case.command), \
                patch.object(publication,'refresh_publication_base',side_effect=['a'*40,'d'*40]):
            result=self.publisher.advance(self.directory,self.journal)
        self.assertEqual(result['state'],'prepared')
        self.assertEqual(result['commit'],'d'*40)
        self.assertNotIn('local_acceptance',result)
        self.assertEqual(len(result['local_acceptance_history']),1)
        self.assertFalse(self.case.merges())

    def test_partial_ack_resumes_without_reacknowledging_first_batch(self):
        self.journal.update(state='merged',merge_commit='d'*40,member_acks={})
        calls=[]
        def website(folder,item):
            calls.append(item['batch_id'])
            if len(calls)==2:return False
            atomic_json(folder/'website-proof.json',{'batch_id':item['batch_id'],'group':item['publication_group']})
            return True
        with patch.object(self.publisher,'accept_website',side_effect=website):
            result=self.publisher.advance(self.directory,self.journal)
            self.assertEqual(result['state'],'merged')
            self.assertEqual(set(result['member_acks']),{'1'*64})
            self.assertEqual(self.publisher.advance(self.directory,result)['state'],'published')
        self.assertEqual(calls,['1'*64,'2'*64,'2'*64])
        self.assertEqual(set(result['member_acks']),{'1'*64,'2'*64})
        self.assertFalse(self.case.merges())

    def test_selection_only_same_exact_source_and_limits_and_preserves_old_owner(self):
        proofs=[]
        for i in range(6):
            proofs.append({'batch_id':str(i+1)*64,'attempt':'attempt-0001','verified':True,
                'context_current':True,'doc_id':'doc','source_sha256':'f'*64,'revision_id':'rev',
                'report_sha256':'a'*64,'adopt_B_count':6})
        self.publisher.remote=Mock(side_effect=proofs)
        chosen=self.publisher.ready_group([{'batch_id':p['batch_id']} for p in proofs])
        self.assertEqual(len(chosen),4)
        self.assertEqual(sum(p['adopt_B_count'] for p in chosen),24)
        proofs[1]['report_sha256']='b'*64
        self.publisher.remote=Mock(side_effect=proofs[:2])
        self.assertEqual(self.publisher.ready_group([{'batch_id':p['batch_id']} for p in proofs[:2]]),[])
        old=self.publisher.state/proofs[0]['batch_id'];old.mkdir()
        atomic_json(old/'journal.json',{'state':'pr_open','commit':'old preserved'})
        self.publisher.remote=Mock(return_value=proofs[1])
        self.assertEqual(self.publisher.ready_group([{'batch_id':p['batch_id']} for p in proofs[:2]]),[])
        self.assertEqual(json.loads((old/'journal.json').read_text())['commit'],'old preserved')

    def test_failed_group_keeps_members_reserved_and_bad_source_does_not_block_other_group(self):
        reserved='1'*64
        folder=self.publisher.state/'groups'/'failed'
        folder.mkdir(parents=True)
        atomic_json(folder/'journal.json',{'state':'blocked','members':[{'batch_id':reserved}]})
        rows=[{'batch_id':str(i)*64} for i in range(1,5)]
        def verify(verb,flag,bid):
            if bid=='2'*64:raise RuntimeError('source temporarily unavailable')
            return {'verified':True,'context_current':True,'batch_id':bid,'attempt':'attempt-0001',
                'doc_id':'doc','source_sha256':'f'*64,'revision_id':'rev',
                'report_sha256':'a'*64,'adopt_B_count':1}
        self.publisher.remote=Mock(side_effect=verify)
        self.assertEqual([p['batch_id'] for p in self.publisher.ready_group(rows)],['3'*64,'4'*64])
        self.assertEqual(self.publisher.group_member_ids(),{reserved})
        self.assertNotIn(reserved,[c.args[-1] for c in self.publisher.remote.call_args_list])

    def test_group_member_count_duplicates_and_statement_limits_fail_before_source_actions(self):
        proof={'batch_id':'1'*64,'adopt_B_count':1}
        for proofs in ([],[proof],[proof,proof],[proof,{'batch_id':'2'*64,'adopt_B_count':25}]):
            with self.subTest(proofs=proofs):
                with self.assertRaisesRegex(ValueError,'invalid_publication_group_members'):
                    self.publisher.prepare_group(proofs)
        self.publisher.remote.assert_not_called()
        self.publisher.sync_source.assert_not_called()

    def test_remote_ack_committed_before_local_journal_failure_replays_actual_published_cli(self):
        self.journal.update(state='merged',merge_commit='d'*40,member_acks={})
        data=self.case.root/'remote-data'
        store=review.ReviewStore(data)
        remote_folders={}
        bodies={'statements':[],'evidence':[],'documents':[]}
        for member in self.journal['members']:
            bid=member['batch_id'];folder=store.directory_for(bid);remote_folders[bid]=folder
            bundle=json.loads((self.directory/'members'/bid/member['attempt']/'bundle.json').read_text())
            atomic_json(folder/'bundle.json',bundle)
            store.db.execute('INSERT INTO batches(id,state) VALUES(?,?)',(bid,'review_ready'))
            cid=bundle['reviews'][0]['id']
            store.db.execute('INSERT INTO dispositions(id,batch_id,state) VALUES(?,?,?)',(cid,bid,'review_ready'))
            ev=bundle['packet']['items'][0]['evidence'][0]
            bodies['statements'].append({'id':member['statement_ids'][0],'text':bundle['reviews'][0]['text'],
                'review':{'decision':'adopted'},'evidence_ids':[ev['id']]})
            bodies['evidence'].append(ev);bodies['documents'].append(bundle['packet']['document'])
        store.db.commit()
        committed=[]
        def remote(verb,flag,bid,proof_flag,proof_path):
            self.assertEqual(verb,'published')
            with patch('sys.argv',['research-review','--data',str(data),'published',
                    '--batch-id',bid,'--proof',str(remote_folders[bid]/'website-proof.json')]), \
                    contextlib.redirect_stdout(io.StringIO()):
                review.main()
            committed.append(bid)
            if len(committed)==1:raise RuntimeError('connection lost after remote commit')
        self.publisher.remote=Mock(side_effect=remote)
        base_run=website_fixture_run({'knowledge':bodies})
        def run(argv,*args,**kwargs):
            if argv[0]=='scp':
                bid=Path(argv[-1].split(':',1)[1]).parts[-2]
                shutil.copyfile(argv[-2],remote_folders[bid]/'website-proof.json')
                return SimpleNamespace(stdout='',returncode=0)
            return base_run(argv,*args,**kwargs)
        with patch.object(publication,'run',side_effect=run), \
                patch.object(publication.registry,'adopted_for_node',return_value={'knowledge':bodies}):
            first=self.publisher.advance(self.directory,self.journal)
            self.assertEqual(first['state'],'merged')
            self.assertEqual(first['member_acks'],{})
            self.assertEqual(store.db.execute('SELECT state FROM batches WHERE id=?',('1'*64,)).fetchone()[0],'published',first.get('error'))
            result=self.publisher.advance(self.directory,first)
        self.assertEqual(result['state'],'published')
        self.assertEqual(committed,['1'*64,'1'*64,'2'*64])
        self.assertEqual(dict(store.db.execute('SELECT state,count(*) FROM dispositions GROUP BY state')),{'published':2})
        self.assertEqual(set(result['member_acks']),{'1'*64,'2'*64})
        for member in result['members']:
            proof=json.loads((remote_folders[member['batch_id']]/'publication-proof.json').read_text())
            self.assertEqual(proof['bundle_sha256'],member['bundle_sha256'])
            self.assertEqual(proof['website_statement_ids'],member['statement_ids'])
        store.db.close()

    def test_group_website_uses_exact_member_ids_and_real_existing_published_command(self):
        member=self.journal['members'][0]
        bundle=json.loads((self.directory/'members'/member['batch_id']/member['attempt']/'bundle.json').read_text())
        sid=member['statement_ids'][0];ev=bundle['packet']['items'][0]['evidence'][0]
        doc=bundle['packet']['document']
        body={'knowledge':{'statements':[{'id':sid,'text':bundle['reviews'][0]['text'],
            'review':{'decision':'adopted'},'evidence_ids':[ev['id']]}], 'evidence':[ev],'documents':[doc]}}
        run=website_fixture_run(body)
        item={**member,'worktree':self.journal['worktree'],'merge_commit':'d'*40,'publication_group':{'group_id':'e'*64,'commit':'a'*40}}
        with patch.object(publication,'run',side_effect=run), \
                patch.object(publication.registry,'adopted_for_node',return_value=body):
            self.assertTrue(self.publisher.accept_website(self.directory/'members'/member['batch_id'],item))
        self.publisher.remote.assert_called_once()
        self.assertEqual(self.publisher.remote.call_args.args[:3],('published','--batch-id',member['batch_id']))
        proof=json.loads((self.directory/'members'/member['batch_id']/'website-proof.json').read_text())
        self.assertEqual(proof['website_statement_ids'],member['statement_ids'])
        self.assertEqual(proof['bundle_sha256'],member['bundle_sha256'])
        self.assertEqual(proof['publication_group'],item['publication_group'])
        self.assertEqual(proof['website_image'],'inresearch-app:'+'f'*40)
        self.assertEqual(proof['website_image_digest'],'sha256:'+'b'*64)
        self.assertEqual(proof['website_source_commit'],'f'*40)
        self.assertTrue(proof['website_health_verified_at'])
        self.assertRegex(proof['canonical_public_closure_sha256'],'^[0-9a-f]{64}$')
        original=copy.deepcopy(body)
        for kind in ('statements','evidence','documents'):
            with self.subTest(canonical=kind):
                changed=copy.deepcopy(original)
                changed['knowledge'][kind][0]['unexpected_change']='mismatch'
                with patch.object(publication,'run',side_effect=run), \
                        patch.object(publication.registry,'adopted_for_node',return_value=changed):
                    with self.assertRaisesRegex(ValueError,'website_canonical'):
                        self.publisher.accept_website(self.directory/'members'/member['batch_id'],item)
        self.assertEqual(self.publisher.remote.call_count,1)
        # Default CI live acceptance retains its prior path; local health and
        # canonical gates must not silently change existing configuration.
        self.publisher.publication_mode='ci'
        def legacy(argv,*args,**kwargs):
            if argv[0]=='scp':return SimpleNamespace(stdout='',returncode=0)
            return SimpleNamespace(stdout=json.dumps(body) if kwargs.get('input') else 'legacy:image',returncode=0)
        with patch.object(publication,'run',side_effect=legacy), \
                patch.object(self.publisher,'local_deployment',side_effect=AssertionError('local-only gate called')), \
                patch.object(publication.registry,'adopted_for_node',side_effect=AssertionError('local-only projection called')):
            self.assertTrue(self.publisher.accept_website(self.directory/'members'/member['batch_id'],item))
        legacy_proof=json.loads((self.directory/'members'/member['batch_id']/'website-proof.json').read_text())
        self.assertEqual(legacy_proof['website_image'],'legacy:image')
        self.assertNotIn('website_image_digest',legacy_proof)


class GroupCollectionWaitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.config={'repo':str(self.root),'state':str(self.root/'state'),
                     'publication_mode':'local_acceptance'}
        self.proofs=[{'verified':True,'context_current':True,'batch_id':str(i)*64,
            'attempt':'attempt-0001','bundle_sha256':str(i)*64,'doc_id':'doc',
            'source_sha256':'f'*64,'revision_id':'rev','report_sha256':'a'*64,'adopt_B_count':1}
            for i in (1,2)]
        self.ready=self.proofs[:1]
        self.publisher=self.new_publisher()

    def new_publisher(self):
        publisher=publication.Publisher(self.config)
        publisher.open_research_prs=Mock(return_value=[])
        publisher.advance=Mock(return_value={'state':'prepared','batch_id':'1'*64})
        def remote(verb,*args):
            if verb=='ready':return [{'batch_id':p['batch_id']} for p in self.ready]
            if verb=='verify':return next(p for p in self.proofs if p['batch_id']==args[1])
            self.fail('collection must not mutate queue: '+verb)
        publisher.remote=Mock(side_effect=remote)
        return publisher

    def tick(self,clock,publisher=None):
        with patch.object(publication.time,'time',return_value=clock):
            return (publisher or self.publisher).tick()

    def test_single_healthy_ready_waits_privately_without_publication_or_queue_changes(self):
        result=self.tick(100)
        self.assertEqual(result['state'],'waiting_batches')
        self.assertEqual(result['waiting'][0]['state'],'collecting_same_source_batches')
        self.publisher.advance.assert_not_called()
        paths=list((self.publisher.state/'group-wait').glob('*.json'))
        self.assertEqual(len(paths),1)
        self.assertEqual(json.loads(paths[0].read_text())['first_seen_epoch'],100)
        self.assertFalse((self.publisher.state/('1'*64)/'journal.json').exists())

    def test_second_same_source_batch_groups_immediately_before_expiry(self):
        self.tick(100)
        self.ready=self.proofs
        self.publisher.prepare_group=Mock(return_value={'state':'prepared','members':self.proofs})
        result=self.tick(101)
        self.assertEqual(len(result['members']),2)
        self.publisher.prepare_group.assert_called_once_with(self.proofs)
        self.publisher.advance.assert_not_called()

    def test_expired_singleton_publishes_and_zero_config_disables_wait(self):
        self.tick(100)
        self.assertEqual(self.tick(399)['state'],'waiting_batches')
        self.publisher.advance.assert_not_called()
        self.assertEqual(self.tick(400)['state'],'prepared')
        self.assertEqual(self.publisher.advance.call_args.args[1]['state'],'new')
        self.config['group_wait_seconds']=0
        other=self.new_publisher()
        self.assertEqual(self.tick(101,other)['state'],'prepared')
        other.advance.assert_called_once()

    def test_restart_preserves_original_first_seen_and_does_not_restart_wait(self):
        self.tick(100)
        path=next((self.publisher.state/'group-wait').glob('*.json'))
        before=path.read_bytes()
        restarted=self.new_publisher()
        self.assertEqual(self.tick(350,restarted)['state'],'waiting_batches')
        restarted.advance.assert_not_called()
        self.assertEqual(self.tick(400,restarted)['state'],'prepared')
        self.assertEqual(path.read_bytes(),before)


class LocalDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.case=local_tests.LocalAcceptanceTests()
        self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.publisher=self.case.publisher
        self.item={**self.case.journal,'merge_commit':'d'*40}
        self.observed={'image':'sha256:'+'b'*64,'tag':'inresearch-app:'+'f'*40,
                       'status':'running','health':'healthy'}

    def pending(self,**overrides):
        with patch.object(publication,'run',side_effect=website_fixture_run({},**overrides)):
            self.assertFalse(self.publisher.accept_website(self.case.directory,self.item))
        self.publisher.remote.assert_not_called()
        self.assertFalse((self.case.directory/'website-proof.json').exists())

    def test_wrong_tag_format_or_digest_is_pending_without_ack(self):
        for tag in ('inresearch-app:latest','other-app:'+'f'*40,'inresearch-app:'+'f'*39):
            with self.subTest(tag=tag):self.pending(observed={**self.observed,'tag':tag})
        self.pending(tag_image='sha256:'+'c'*64)
        self.pending(observed={**self.observed,'image':'unknown'})

    def test_old_or_unknown_source_object_is_pending_without_ack(self):
        for code in (1,128):
            with self.subTest(ancestry=code):self.pending(ancestry=code)

    def test_unhealthy_or_stopped_container_is_pending_without_ack(self):
        for state in ({'health':'starting'},{'health':'unhealthy'},{'health':None},{'status':'exited'}):
            with self.subTest(state=state):self.pending(observed={**self.observed,**state})

    def test_public_health_non200_false_or_transport_failure_has_zero_ack(self):
        for health in ({'status':503,'ok':True},{'status':200,'ok':False},{'status':200,'ok':None}):
            with self.subTest(health=health):self.pending(health=health)
        actual=website_fixture_run({})
        def failure(argv,*args,**kwargs):
            if '/healthz' in kwargs.get('input',''):raise RuntimeError('public health unavailable')
            return actual(argv,*args,**kwargs)
        with patch.object(publication,'run',side_effect=failure):
            self.assertFalse(self.publisher.accept_website(self.case.directory,self.item))
        self.publisher.remote.assert_not_called()

    def test_exact_running_digest_tag_ancestry_and_public_health_are_bound(self):
        calls=[]
        with patch.object(publication,'run',side_effect=website_fixture_run({},calls=calls)):
            result=self.publisher.local_deployment(self.item['merge_commit'])
        self.assertEqual(result['image'],self.observed['image'])
        self.assertEqual(result['tag'],self.observed['tag'])
        self.assertEqual(result['source_commit'],'f'*40)
        self.assertEqual(result['healthz_status'],200)
        self.assertIs(result['healthz_ok'],True)
        self.assertTrue(result['verified_at'])
        self.assertIn(['git','merge-base','--is-ancestor','d'*40,'f'*40],calls)
        inspect=[c for c in calls if c[0]=='ssh' and 'docker inspect' in c[-1]][0][-1]
        for field in ('.Image','.Config.Image','.State.Status','.State.Health.Status'):
            self.assertIn(field,inspect)
        self.assertNotIn('.Env',inspect)


class GroupFactoryGitTests(unittest.TestCase):
    def test_two_ready_batches_create_one_real_git_increment_one_pr_and_bound_receipt(self):
        case=GroupPromotionTests();case.setUp();self.addCleanup(case.doCleanups)
        root=case.root
        def git(*args):
            return publication.run(['git',*args],root).stdout.strip()
        git('init','--initial-branch=main')
        git('config','user.name','Publication fixture')
        git('config','user.email','fixture@example.invalid')
        (root/'docs').mkdir()
        (root/'docs/REPOSITORY_REGISTER.md').write_text('baseline')
        (root/'framework/repository_manifest.json').write_text('{}')
        # Only inventory generation is a tiny fixture. C3/audit/registry and
        # actual Git worktrees, commits, pushes and append refresh run for real.
        (root/'manage.py').write_text("""import json,pathlib,sys
if sys.argv[1:]==['governance','--refresh']:
 value=json.loads(pathlib.Path('data/research_knowledge.json').read_text())
 pathlib.Path('framework/repository_manifest.json').write_text(json.dumps(value))
 pathlib.Path('docs/REPOSITORY_REGISTER.md').write_text(json.dumps(value))
""")
        (root/'.gitignore').write_text('*.lock\n__pycache__/\n')
        git('add','framework','data','docs','manage.py','.gitignore');git('commit','-m','baseline fixture')
        origin=root/'origin.git';git('clone','--bare',str(root),str(origin))
        git('remote','add','origin',str(origin));git('fetch','origin','main')
        state=root/'state'
        publisher=publication.Publisher({'repo':str(root),'state':str(state),
                                         'publication_mode':'local_acceptance'})
        proofs=[];audits={}
        for bundle,folder in case.members:
            bid=bundle['packet']['batch_id'];audits[bid]=folder
            for name in ('matching-request.json','matching-response.json'):
                atomic_json(folder/name,{})
            proofs.append({'verified':True,'batch_id':bid,'attempt':'attempt-0001',
                'bundle_sha256':digest_file(folder/'bundle.json'),'context_current':True,
                'doc_id':'doc-'+'a'*64,'source_sha256':'a'*64,'revision_id':'rev',
                'report_sha256':'b'*64,'adopt_B_count':1})
        proof_by={p['batch_id']:p for p in proofs}
        publisher.sync_source=Mock()
        publisher.remote=Mock(side_effect=lambda verb,*args:proof_by[args[1]])
        actual_run=publication.run
        created=[];merged=[];worktrees=[];check_commands=[]
        def run(argv,cwd=None,**kwargs):
            argv=list(argv)
            if tuple(argv) in publication.LOCAL_ACCEPTANCE_COMMANDS:
                if kwargs.get('timeout') == 900:
                    check_commands.append(argv)
                return SimpleNamespace(stdout='fixed fixture check passed',stderr='',returncode=0)
            if argv[:3]==['git','worktree','add']:
                worktrees.append(Path(argv[-2]))
            if argv[0]=='scp':
                remote=argv[-2].split(':',1)[1]
                bid=Path(remote).parts[-3]
                shutil.copyfile(audits[bid]/Path(remote).name,argv[-1])
                return SimpleNamespace(stdout='',stderr='',returncode=0)
            if argv[0]=='gh':
                if argv[:3]==['gh','api','repos']:
                    self.fail('CI must never be queried')
                if argv[:3]==['gh','pr','list']:
                    rows=[{'number':999,'url':'https://example.invalid/pr/999'}] if '--head' in argv and created else []
                    return SimpleNamespace(stdout=json.dumps(rows),stderr='',returncode=0)
                if argv[:3]==['gh','pr','create']:
                    created.append(argv)
                    return SimpleNamespace(stdout='',stderr='',returncode=0)
                if argv[:3]==['gh','pr','view']:
                    head=actual_run(['git','rev-parse','HEAD'],worktrees[0]).stdout.strip()
                    return SimpleNamespace(stdout=json.dumps({'state':'OPEN','headRefOid':head}),stderr='',returncode=0)
                if argv[:3]==['gh','pr','merge']:
                    merged.append(argv)
                    return SimpleNamespace(stdout='',stderr='',returncode=0)
                self.fail('unexpected GitHub call '+repr(argv))
            return actual_run(argv,cwd,**kwargs)
        with patch.object(publication,'run',side_effect=run), \
                patch.object(publication.Path,'home',return_value=root/'managed-home'):
            result=publisher.prepare_group(proofs)
        self.assertNotIn('error',result)
        self.assertEqual(len(created),1)
        self.assertEqual(len(merged),1)
        self.assertEqual(merged[0][-2:],['--match-head-commit',result['commit']])
        self.assertEqual(len(check_commands),5)
        self.assertEqual(len(result['members']),2)
        self.assertEqual(len(result['statement_ids']),2)
        self.assertEqual(case.knowledge.read_bytes(),case.before)
        value=json.loads((worktrees[0]/'data/research_knowledge.json').read_text())
        self.assertEqual(len(value['statements']),2)
        self.assertEqual(value['answers'],[])
        self.assertEqual(actual_run(['git','status','--porcelain'],worktrees[0]).stdout.strip(),'')
        directory=state/'groups'/result['batch_id']
        receipt=json.loads((directory/result['local_acceptance']['path']).read_text())
        self.assertEqual(receipt['version'],2)
        self.assertEqual(receipt['binding']['commit'],result['commit'])
        self.assertEqual(len(json.loads((directory/result['group_manifest']['path']).read_text())['members']),2)
