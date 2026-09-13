"""Business invariants across actual processes, failures and obsolete client plans."""
import copy
import hashlib
import io
import json
import multiprocessing
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from inresearch.interfaces import deep_read as cli
from inresearch.workflow.deep_read import DeepRead, CompletionPending
from inresearch.materials import triage
from inresearch.materials.records import result_revision
from inresearch.storage import files
from inresearch.storage.files import CommitUncertain
from inresearch.storage.jsonl import read_rows
from inresearch.knowledge.provenance import cache_candidates, repair_plan
from deep_read_fixtures import METRICS, SHA, fact, other


def app_at(base):
    base = Path(base)
    materials = SimpleNamespace(RESULTS=base/'l1.jsonl', INVENTORY=base/'inventory.jsonl',
        MAX_PREVIEW_CHARS=triage.MAX_PREVIEW_CHARS, proposed_name=triage.proposed_name,
        readable_path=lambda row: (base/row['rel'], False),
        load_inventory=lambda: list(read_rows(base/'inventory.jsonl')))
    return DeepRead(base, base/'state', base/'packets', materials)


def competing(base, action, barrier, queue, value):
    app = app_at(base)
    try:
        barrier.wait(15)
        if action=='record': result=app.record([fact()], SHA)
        elif action=='skip': result=app.skip(SHA, ['missing dimension'])
        elif action=='fill': result=app.gaps.fill([value], '2026-09-13')
        elif action=='attribute': result=app.attribute(SHA, expected_revision=value,
                                             org=str(multiprocessing.current_process().pid), evidence='cover')
        else: result=app.pack()
        queue.put(('ok', result))
    except Exception as exc:
        queue.put((type(exc).__name__, str(exc)))


class DeepReadTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='inresearch-l2-transactions-')
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        (self.base/'data').mkdir(); (self.base/'framework').mkdir()
        self.app=app_at(self.base)
        self.app.facts_path.write_text(json.dumps({'version':'test','records':[]}))
        self.app.metrics_path.write_text(json.dumps({'metrics':list(METRICS.values())}))
        self.app.questions_path.write_text(json.dumps({'records':[]}))
        self.row=dict(sha256=SHA, rel='document.txt', suffix='.txt', status='ok', score=9,
                      category='M10', org='Original source', year='2025', score_status='scored', level='p')
        self.write_rows([self.row])

    def write_rows(self, rows):
        self.app.materials.RESULTS.write_text(''.join(json.dumps(r)+'\n' for r in rows))

    def pairs(self, action, value=None):
        ctx=multiprocessing.get_context('spawn'); barrier=ctx.Barrier(2); queue=ctx.Queue()
        processes=[ctx.Process(target=competing,args=(str(self.base),action,barrier,queue,value)) for _ in range(2)]
        for p in processes:p.start()
        try:
            results=[queue.get(timeout=20) for _ in processes]
            for p in processes:
                p.join(20);self.assertEqual(p.exitcode,0)
            return results
        finally:
            for p in processes:
                if p.is_alive():p.terminate();p.join()
            queue.close()

    def test_ambiguous_packet_does_not_start_extraction_even_if_other_match_is_ineligible(self):
        self.write_rows([self.row,{**self.row,'sha256':'a'*63+'b','score':1}])
        with patch.object(self.app,'extractor') as extractor:
            with self.assertRaises(ValueError):self.app.pack('aaaaaaaa')
            extractor.assert_not_called()
        self.assertFalse(self.app.packet_dir.exists())

    def test_restricted_and_self_authored_sources_cannot_bypass_queue_at_record(self):
        before=self.app.facts_path.read_bytes()
        for fields in ({'confidential':True},{'pii':True},{'org':'inresearch.ai'}):
            self.write_rows([{**self.row,**fields}])
            with self.assertRaises(ValueError):self.app.record([fact()],SHA)
            with self.assertRaises(ValueError):self.app.record([],SHA)
            self.assertEqual(self.app.record([fact()])['rejected'],1)
            self.assertEqual(before,self.app.facts_path.read_bytes())
            self.assertFalse(self.app.read_log.exists())

    def test_identical_fact_replay_never_duplicates_completion_or_records(self):
        first=self.app.record([fact()],SHA); before=self.app.read_log.read_bytes()
        repeated=self.app.record([fact()],SHA)
        self.assertEqual((first['accepted'],repeated['replayed']),(1,1))
        self.assertTrue(repeated['receipt_replayed'])
        self.assertEqual(before,self.app.read_log.read_bytes())
        self.assertEqual(len(self.app.load_facts()['records']),1)
        self.assertEqual(self.app.record([fact()])['replayed'],1)

    def test_execution_attribution_is_explicit_and_replay_cannot_rewrite_it(self):
        self.app.record([fact()],SHA,executor='claude-code',model='reported-model')
        original=self.app.read_log.read_bytes()
        execution=list(read_rows(self.app.read_log))[0]['execution']
        self.assertEqual(execution,dict(executor='claude-code',model='reported-model',verification='client_reported'))
        self.app.record([fact()],SHA,executor='another-client',model='another-model')
        self.assertEqual(original,self.app.read_log.read_bytes())
        with self.assertRaises(ValueError):self.app.record([fact()],SHA,executor='bad\nclient')

    def test_empty_envelopes_are_valid_but_not_automatic_proof_of_full_read(self):
        for payload in ([],{'records':[]},{'facts':[]}):
            report=self.app.record(payload,SHA)
            self.assertEqual(report['incoming'],0)
            self.assertIn('不证明',report['note'])
        self.assertEqual(len(list(read_rows(self.app.read_log))),1)

    def test_malformed_input_is_rejected_before_writes(self):
        before=self.app.facts_path.read_bytes()
        for payload in (None,1,'[]',[1],{'records':None}):
            with self.assertRaises(ValueError):self.app.record(payload,SHA)
        for key in ('evidence','entity','caliber'):
            self.assertEqual(self.app.record([fact(**{key:[]})],SHA)['rejected'],1)
        self.assertEqual(before,self.app.facts_path.read_bytes())
        self.assertFalse(self.app.read_log.exists())

    def test_failed_fact_write_retains_old_authority_and_no_receipt(self):
        before=self.app.facts_path.read_bytes()
        with patch('inresearch.workflow.deep_read.write_json',side_effect=OSError('disk')):
            with self.assertRaises(OSError):self.app.record([fact()],SHA)
        self.assertEqual(before,self.app.facts_path.read_bytes())
        self.assertFalse(self.app.read_log.exists())

    def test_fact_commit_then_receipt_failure_recovers_from_same_input(self):
        with patch.object(self.app,'remember_read',side_effect=OSError('receipt unavailable')):
            with self.assertRaises(CompletionPending):self.app.record([fact()],SHA)
        self.assertEqual(len(self.app.load_facts()['records']),1)
        report=self.app.record([fact()],SHA)
        self.assertEqual(report['replayed'],1)
        self.assertEqual(list(read_rows(self.app.read_log))[0]['facts'],1)

    def test_visible_but_uncertain_fact_commit_is_not_rolled_back(self):
        def replace_then_fail(path,data):
            files.write_json(path,data)
            raise CommitUncertain()
        with patch('inresearch.workflow.deep_read.write_json',side_effect=replace_then_fail):
            with self.assertRaises(CommitUncertain):self.app.record([fact()],SHA)
        self.assertEqual(len(self.app.load_facts()['records']),1)
        self.assertEqual(self.app.record([fact()],SHA)['replayed'],1)

    def test_skip_retry_keeps_a_filled_gap_closed_and_preserves_receipt(self):
        first=self.app.skip(SHA,['missing dimension'])
        self.app.gaps.fill(first['gap_ids'],'2026-09-13')
        before=self.app.gaps.path.read_bytes(); receipt=self.app.read_log.read_bytes()
        retry=self.app.skip(SHA,['missing dimension'])
        self.assertEqual(retry['gaps_recorded'],0)
        self.assertEqual(self.app.gaps.open(),[])
        self.assertEqual(before,self.app.gaps.path.read_bytes())
        self.assertEqual(receipt,self.app.read_log.read_bytes())

    def test_gap_commit_then_receipt_failure_and_fill_can_be_replayed(self):
        with patch.object(self.app,'remember_read',side_effect=OSError('receipt unavailable')):
            with self.assertRaises(CompletionPending):self.app.skip(SHA,['missing dimension'])
        ids=list(self.app.gaps.current());self.app.gaps.fill(ids,'2026-09-13')
        self.app.skip(SHA,['missing dimension'])
        self.assertFalse(self.app.gaps.open())
        self.assertEqual(len(list(read_rows(self.app.read_log))),1)

    def test_gap_batch_unknown_identifier_and_precommit_failure_are_atomic(self):
        ids=self.app.skip(SHA,['dimension A','dimension B'])['gap_ids']
        before=self.app.gaps.path.read_bytes()
        with self.assertRaises(ValueError):self.app.gaps.fill([ids[0],'unknown'],'now')
        self.assertEqual(before,self.app.gaps.path.read_bytes())
        with patch('inresearch.workflow.reading_gaps.atomic_write',side_effect=OSError('disk')):
            with self.assertRaises(OSError):self.app.gaps.fill(ids,'now')
        self.assertEqual(before,self.app.gaps.path.read_bytes())
        self.assertEqual(len(self.app.gaps.open()),2)

    def test_uncertain_gap_batch_is_fully_visible_and_retry_does_not_reopen(self):
        ids=self.app.skip(SHA,['dimension A','dimension B'])['gap_ids']
        def replace_then_fail(path,data):
            files.atomic_write(path,data)
            raise CommitUncertain()
        with patch('inresearch.workflow.reading_gaps.atomic_write',side_effect=replace_then_fail):
            with self.assertRaises(CommitUncertain):self.app.gaps.fill(ids,'now')
        self.assertEqual(self.app.gaps.open(),[])
        self.assertEqual(self.app.gaps.fill(ids,'later')['replayed'],2)

    def test_processes_record_one_fact_and_one_completion(self):
        results=self.pairs('record');self.assertTrue(all(s=='ok' for s,_ in results),results)
        self.assertEqual(sorted(r['accepted'] for _,r in results),[0,1])
        self.assertEqual(len(self.app.load_facts()['records']),1)
        self.assertEqual(len(list(read_rows(self.app.read_log))),1)

    def test_processes_propose_and_fill_one_gap_without_duplicate_receipts(self):
        results=self.pairs('skip');self.assertTrue(all(s=='ok' for s,_ in results),results)
        self.assertEqual(sorted(r['gaps_recorded'] for _,r in results),[0,1])
        self.assertEqual(len(list(read_rows(self.app.read_log))),1)
        gap=next(iter(self.app.gaps.current()))
        results=self.pairs('fill',gap);self.assertTrue(all(s=='ok' for s,_ in results),results)
        self.assertEqual(sorted(r['replayed'] for _,r in results),[0,1])

    def test_processes_cannot_both_replace_the_same_l1_revision(self):
        results=self.pairs('attribute',result_revision(self.row))
        self.assertEqual(sorted(s for s,_ in results),['ValueError','ok'])
        self.assertEqual(len(list(read_rows(self.app.materials.RESULTS))),2)

    def test_stale_flag_cannot_reverse_a_newer_verdict(self):
        base=result_revision(self.row)
        self.app.attribute(SHA,expected_revision=base,org='New publisher',evidence='cover')
        with self.assertRaisesRegex(ValueError,'revision_conflict'):
            self.app.flag(SHA,expected_revision=base,names=['pii'],evidence='cover')
        self.assertEqual(self.app.all_results()[SHA]['org'],'New publisher')
        self.assertNotIn('pii',self.app.all_results()[SHA])

    def source(self):
        text='工程小样：10 台服务器，每台 300 W；仅计算服务器小计，末行不是全设施功率。'
        (self.base/'document.txt').write_text(text)
        self.row['sha256']=hashlib.sha256(text.encode()).hexdigest()
        self.write_rows([self.row]);return text

    def test_current_threshold_and_named_low_score_keep_admission_boundary(self):
        self.source()
        self.row['score']=7;self.write_rows([self.row])
        self.assertEqual(len(self.app.eligible()),1)
        self.row['score']=6;self.write_rows([self.row])
        self.assertEqual(self.app.eligible(),[])
        self.assertEqual(self.app.pack(self.row['sha256'])['packed'],1)
        self.row['confidential']=True;self.write_rows([self.row])
        self.assertEqual(self.app.pack(self.row['sha256'])['packed'],0)

    def test_packet_publication_failure_never_exposes_a_partial_final_packet(self):
        self.source()
        with patch('os.rename',side_effect=OSError('directory publication')):
            with self.assertRaises(OSError):self.app.pack(self.row['sha256'])
        parent=self.app.packet_dir/self.row['sha256']
        self.assertFalse([p for p in parent.iterdir() if not p.name.startswith('.')])
        report=self.app.pack(self.row['sha256'])
        self.assertTrue(Path(report['manifest']).exists())
        self.assertEqual(Path(report['text']).read_text(),(self.base/'document.txt').read_text())

    def test_concurrent_packet_publication_has_independent_complete_artifacts(self):
        self.source()
        # The spawned worker uses SHA to select; give both the actual identity.
        # Multiple independent CLI processes are also covered by the real flow;
        # here use the same barrier helper and select the queue head.
        results=self.pairs('pack')
        self.assertTrue(all(s=='ok' for s,_ in results),results)
        paths=[r['manifest'] for _,r in results];self.assertEqual(len(set(paths)),2)
        for _,report in results:
            manifest=json.loads(Path(report['manifest']).read_text())
            self.assertEqual(manifest['sha256'],self.row['sha256'])
            self.assertEqual(hashlib.sha256(Path(report['text']).read_bytes()).hexdigest(),manifest['text_sha256'])

    def test_cli_returns_commit_stage_and_requires_external_revision(self):
        incoming=self.base/'input.json';incoming.write_text(json.dumps([fact()]))
        output=io.StringIO()
        with patch.object(self.app,'remember_read',side_effect=OSError('receipt')),redirect_stdout(output):
            rc=cli.main(['record','--facts',str(incoming),'--doc',SHA],self.app)
        self.assertEqual(rc,1)
        self.assertEqual(json.loads(output.getvalue())['commit_state'],'facts_committed_receipt_pending')
        with self.assertRaises(SystemExit),redirect_stdout(io.StringIO()):
            cli.main(['flag','--sha',SHA,'--pii','--evidence','cover'],self.app)

    def test_provenance_plan_refuses_substrings_failed_moves_and_competing_routes(self):
        key='123456789abc'; remap={key:{'new_path':'original/report.pdf'}}
        move=dict(event='move',ok=True,sha256=SHA,**{'from':'unrelated/report.pdf.backup','to':'somewhere.pdf'})
        self.assertEqual(cache_candidates({key},remap,[move])[key],set())
        move['from']='original/report.pdf';self.assertEqual(cache_candidates({key},remap,[move])[key],{SHA})
        self.assertEqual(cache_candidates({key},remap,[{**move,'ok':False}])[key],set())
        store={'records':[{'fact_id':'old','evidence':{'source_id':key}}]}
        collision=key+'0'*52
        plan=repair_plan(store,{collision:{}},[],{},remap,[move])
        self.assertEqual(plan['candidates'],[]);self.assertEqual(len(plan['ambiguous']),1)

    def test_provenance_path_ambiguity_and_namespace_collision_are_not_guessed(self):
        store={'records':[{'fact_id':'old','evidence':{'source_id':'named','local_file':'report.pdf'}}]}
        inventory=[dict(sha256=sha,rel='report.pdf') for sha in (SHA,'b'*64)]
        self.assertEqual(repair_plan(store,{},inventory,{}, {},[])['candidates'],[])
        store['records'][0]['evidence']={'source_id':SHA[:12]}
        plan=repair_plan(store,{SHA:{}},[],{}, {SHA[:12]:{'new_path':'unresolved'}},[])
        self.assertEqual(plan['candidates'],[]);self.assertEqual(len(plan['ambiguous']),1)

    def test_provenance_commit_requires_reviewed_plan_and_rejects_changed_facts(self):
        self.app.facts_path.write_text(json.dumps({'records':[{'fact_id':'old','evidence':{'source_id':SHA[:12]}}]}))
        plan=self.app.backfill_provenance()
        with self.assertRaisesRegex(ValueError,'plan_conflict'):self.app.backfill_provenance(True)
        store=self.app.load_facts();store['records'][0]['note']='changed after review'
        self.app.facts_path.write_text(json.dumps(store));before=self.app.facts_path.read_bytes()
        with self.assertRaisesRegex(ValueError,'plan_conflict'):
            self.app.backfill_provenance(True,plan['plan_sha256'])
        self.assertEqual(before,self.app.facts_path.read_bytes())
        reviewed=self.app.backfill_provenance()
        self.assertEqual(self.app.backfill_provenance(True,reviewed['plan_sha256'])['written'],1)

    def test_provenance_commit_rejects_changed_resolution_and_interior_damage(self):
        self.app.facts_path.write_text(json.dumps({'records':[{'fact_id':'old','evidence':{'source_id':SHA[:12]}}]}))
        plan=self.app.backfill_provenance()
        self.write_rows([self.row,{**self.row,'sha256':'a'*63+'b'}])
        with self.assertRaisesRegex(ValueError,'plan_conflict'):
            self.app.backfill_provenance(True,plan['plan_sha256'])
        self.app.moves_path.write_text('{broken}\n')
        with self.assertRaisesRegex(ValueError,'invalid JSON record'):self.app.backfill_provenance()
