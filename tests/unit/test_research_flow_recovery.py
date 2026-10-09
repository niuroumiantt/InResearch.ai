import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from inresearch.materials.artifacts import atomic_json, encoded
from inresearch.workflow import research_review as review
from inresearch.workflow import research_publish as publication


class SourcePacketRecoveryTests(unittest.TestCase):
    def test_publication_keeps_already_adopted_source_while_discovery_omits_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)/'root'
            data = Path(td)/'data'
            (root/'framework').mkdir(parents=True)
            (root/'data').mkdir()
            data.mkdir()
            original = data/'original.pdf'
            original.write_bytes(b'original preserved bytes')
            sha = hashlib.sha256(original.read_bytes()).hexdigest()
            doc = {'doc_id':'doc', 'state':'complete', 'revision_id':'rev',
                   'report_sha256':'sealed', 'sha256':sha, 'suffix':'.pdf',
                   'original_rel':'original.pdf'}
            candidate = {'id':'candidate', 'question_ids':['q1'], 'evidence_ids':['ev']}
            evidence = {'id':'ev', 'quote':'original quotation', 'page_index':0}
            projected = {'entry':{'title':'Preserved report'},
                         'statements':[candidate], 'evidence':[evidence]}
            report = {'coverage':{'pages_total':1}, 'summary':'Summary',
                      'key_points':[], 'importance':7}
            atomic_json(root/'framework/research_graph.json', {'objects':[{'id':'root'}]})
            atomic_json(root/'framework/research_questions.json', {'records':[{'id':'q1'}]})
            atomic_json(root/'data/research_knowledge.json',
                        {'statements':[{'acceptance':'adopted', 'source_candidate_ids':['candidate']}]})
            store = review.ReviewStore(data)
            pages = ['surrounding original quotation context']
            atomic_json(store.directory/(sha+'-native.json'),
                        {'sha256':sha, 'pages':pages, 'pages_sha256':review.sha(pages)})
            batch = {'id':'b'*64, 'doc_id':'doc', 'revision_id':'rev',
                     'report_sha':'sealed', 'candidate_ids':encoded(['candidate'])}
            conn = Mock()
            conn.execute.return_value.fetchone.return_value = doc
            with patch.object(review, 'ro', return_value=conn), \
                    patch.object(review.ReadingArtifacts, 'verify_seal', return_value=report), \
                    patch.object(review, 'project_document', return_value=projected), \
                    patch.object(review.registry, 'object_resolver'), \
                    patch.object(review, 'context', return_value={}):
                fresh = store.packet(root, batch)
                sealed = store.packet(root, batch, include_adopted=True)
                self.assertEqual(fresh['items'], [])
                self.assertEqual(fresh['unsupported'][0]['state'], 'already_adopted')
                self.assertEqual(sealed['items'][0]['candidate'], candidate)
                self.assertEqual(sealed['native_pages'], {'0':pages[0]})
                original.write_bytes(b'changed original')
                with self.assertRaisesRegex(ValueError, 'original_changed'):
                    store.packet(root, batch, include_adopted=True)
            store.db.close()

    def test_verification_reports_changed_fields_and_never_accepts_source_edits(self):
        source = {'document':{'id':'doc'}, 'items':[{'id':'claim'}],
                  'coverage':{'complete':True}, 'original_importance':7,
                  'native_pages':{'0':'original'}, 'research_context':{}, 'context_sha256':'ctx'}
        for field in ('document', 'items', 'coverage', 'original_importance', 'native_pages'):
            current = copy.deepcopy(source)
            current[field] = 'changed'
            db = Mock()
            db.execute.return_value.fetchone.return_value = {'id':'b'*64}
            store = SimpleNamespace(db=db, packet=Mock(return_value=current))
            with self.assertRaisesRegex(ValueError, 'source_report_changed: '+field):
                review.verify_source_packet(store, 'root', 'b'*64, {'packet':source})
            store.packet.assert_called_once_with('root', {'id':'b'*64}, include_adopted=True)


class PublisherIsolationTests(unittest.TestCase):
    def blocked_publisher(self, td):
        p = publication.Publisher({'repo':td, 'state':td})
        bid = 'a'*64
        dr = Path(td)/bid
        dr.mkdir()
        atomic_json(dr/'journal.json', {'batch_id':bid, 'state':'blocked',
                    'bundle_sha256':'seal', 'pr':418, 'commit':'c'*40,
                    'error':'ci_failed_preserve_review_branch'})
        return p, bid, dr

    def test_changed_context_requeues_open_blocked_batch_and_preserves_audit(self):
        with tempfile.TemporaryDirectory() as td:
            p, bid, dr = self.blocked_publisher(td)
            p.remote = Mock(side_effect=[[{'batch_id':bid}],
                                        {'bundle_sha256':'seal', 'context_current':False}, {}])
            p.advance = Mock()
            pr = {'state':'OPEN', 'headRefOid':'c'*40}
            with patch.object(publication, 'run', return_value=SimpleNamespace(stdout=json.dumps(pr))) as run:
                self.assertEqual(p.tick()['state'], 'revalidation')
            p.remote.assert_any_call('revalidate', '--batch-id', bid)
            p.advance.assert_not_called()
            self.assertIn(['gh', 'pr', 'close', '418'], [c.args[0] for c in run.call_args_list])
            journal = json.loads((dr/'journal.json').read_text())
            self.assertEqual(journal['commit'], 'c'*40)
            self.assertEqual(journal['recoveries'][0]['error'], 'ci_failed_preserve_review_branch')

    def test_recovered_checks_resume_normal_validation_without_waiver(self):
        with tempfile.TemporaryDirectory() as td:
            p, bid, dr = self.blocked_publisher(td)
            p.remote = Mock(side_effect=[[{'batch_id':bid}],
                                        {'bundle_sha256':'seal', 'context_current':True}])
            p.advance = Mock(return_value={'state':'pr_open'})
            pr = {'state':'OPEN', 'headRefOid':'c'*40}
            checks = [{'name':n, 'bucket':'pass'} for n in
                      ('validate', 'browser (core)', 'browser (model_assets)', 'storage-container')]
            with patch.object(publication, 'run', side_effect=[SimpleNamespace(stdout=json.dumps(pr)),
                                                               SimpleNamespace(stdout=json.dumps(checks))]):
                self.assertEqual(p.tick()['state'], 'pr_open')
            self.assertEqual(p.advance.call_args.args[1]['recoveries'][0]['reason'],
                             'exact_head_checks_recovered')

    def test_unrecovered_ci_and_changed_open_head_remain_blocked(self):
        for head, bucket in (('c'*40, 'fail'), ('e'*40, 'pass')):
            with self.subTest(head=head), tempfile.TemporaryDirectory() as td:
                p, bid, dr = self.blocked_publisher(td)
                p.remote = Mock(side_effect=[[{'batch_id':bid}],
                                            {'bundle_sha256':'seal', 'context_current':True}])
                p.advance = Mock()
                results = [SimpleNamespace(stdout=json.dumps({'state':'OPEN', 'headRefOid':head})),
                           SimpleNamespace(stdout=json.dumps([{'name':'validate','bucket':bucket}]))]
                with patch.object(publication, 'run', side_effect=results):
                    self.assertEqual(p.tick()['state'], 'blocked_batches')
                p.advance.assert_not_called()

    def test_blocked_source_verification_does_not_stop_later_batch(self):
        with tempfile.TemporaryDirectory() as td:
            p = publication.Publisher({'repo':td, 'state':td})
            bad, good = 'a'*64, 'b'*64
            dr = Path(td)/bad
            dr.mkdir()
            atomic_json(dr/'journal.json', {'batch_id':bad, 'state':'blocked', 'attempt':'attempt-0001'})
            p.remote = Mock(side_effect=[[{'batch_id':bad}, {'batch_id':good}],
                                        ValueError('source_report_changed: items')])
            p.advance = Mock(return_value={'batch_id':good, 'state':'pr_open'})
            result = p.tick()
            self.assertEqual(result['batch_id'], good)
            self.assertEqual(json.loads((dr/'journal.json').read_text())['state'], 'blocked')
            p.advance.assert_called_once()

    def test_pending_ci_does_not_monopolize_publication_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            p = publication.Publisher({'repo':td, 'state':td})
            first, second = 'a'*64, 'b'*64
            dr = Path(td)/first
            dr.mkdir()
            waiting = {'batch_id':first, 'state':'pr_open', 'commit':'c'*40}
            atomic_json(dr/'journal.json', waiting)
            p.remote = Mock(return_value=[{'batch_id':first}, {'batch_id':second}])
            p.advance = Mock(side_effect=[waiting, {'batch_id':second, 'state':'pr_open'}])
            self.assertEqual(p.tick()['batch_id'], second)
            self.assertEqual(p.advance.call_count, 2)

    def test_all_blocked_batches_are_reported_without_global_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            p = publication.Publisher({'repo':td, 'state':td})
            p.remote = Mock(return_value=[{'batch_id':'a'*64}, {'batch_id':'b'*64}])
            p.advance = Mock(side_effect=[{'batch_id':'a'*64, 'state':'blocked', 'error':'bad source'},
                                         {'batch_id':'b'*64, 'state':'blocked', 'error':'bad review'}])
            result = p.tick()
            self.assertEqual(result['state'], 'blocked_batches')
            self.assertEqual(len(result['batches']), 2)

    def test_remote_semantic_failure_is_distinct_from_transport_failure(self):
        with tempfile.TemporaryDirectory() as td:
            p = publication.Publisher({'repo':td, 'state':td})
            p.ssh = Mock(side_effect=RuntimeError('command_failed: ssh ValueError: source_report_changed: items'))
            with self.assertRaisesRegex(ValueError, 'source_report_changed: items'):
                p.remote('verify')
            p.ssh = Mock(side_effect=RuntimeError('command_failed: ssh connection timed out'))
            with self.assertRaises(RuntimeError):
                p.remote('verify')

    def test_exact_reviewed_head_merged_elsewhere_recovers_receipt_only(self):
        with tempfile.TemporaryDirectory() as td:
            p = publication.Publisher({'repo':td, 'state':td})
            bid = 'a'*64
            dr = Path(td)/bid
            dr.mkdir()
            journal = {'batch_id':bid, 'state':'blocked', 'bundle_sha256':'seal',
                       'pr':418, 'commit':'c'*40, 'error':'ci_failed_preserve_review_branch'}
            atomic_json(dr/'journal.json', journal)
            p.remote = Mock(side_effect=[[{'batch_id':bid}], {'bundle_sha256':'seal'}])
            p.advance = Mock(return_value={'batch_id':bid, 'state':'published'})
            pr = {'state':'MERGED', 'headRefOid':'c'*40, 'mergeCommit':{'oid':'d'*40}}
            with patch.object(publication, 'run', return_value=SimpleNamespace(stdout=json.dumps(pr))):
                self.assertEqual(p.tick()['state'], 'published')
            recovered = p.advance.call_args.args[1]
            self.assertEqual(recovered['state'], 'merged')
            self.assertEqual(recovered['merge_commit'], 'd'*40)
            self.assertEqual(recovered['recoveries'][0]['error'], journal['error'])

    def test_changed_merged_pr_head_cannot_recover_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            p = publication.Publisher({'repo':td, 'state':td})
            bid = 'a'*64
            dr = Path(td)/bid
            dr.mkdir()
            atomic_json(dr/'journal.json', {'batch_id':bid, 'state':'blocked',
                        'bundle_sha256':'seal', 'pr':418, 'commit':'c'*40})
            p.remote = Mock(side_effect=[[{'batch_id':bid}], {'bundle_sha256':'seal'}])
            p.advance = Mock()
            pr = {'state':'MERGED', 'headRefOid':'e'*40, 'mergeCommit':{'oid':'d'*40}}
            with patch.object(publication, 'run', return_value=SimpleNamespace(stdout=json.dumps(pr))):
                self.assertEqual(p.tick()['state'], 'blocked_batches')
            p.advance.assert_not_called()
            self.assertEqual(json.loads((dr/'journal.json').read_text())['error'],
                             'pr_head_changed_requires_review')

    def blocked_fixture(self, td):
        p = publication.Publisher({'repo':td, 'state':td})
        bid = 'a'*64
        dr = Path(td)/bid
        dr.mkdir()
        journal = {'batch_id':bid, 'state':'blocked', 'bundle_sha256':'seal',
                   'attempt':'attempt-0001', 'pr':431, 'commit':'c'*40,
                   'error':'ci_failed_preserve_review_branch'}
        atomic_json(dr/'journal.json', journal)
        return p, bid, dr, journal


    def test_new_attempt_retains_old_publication_journal(self):
        with tempfile.TemporaryDirectory() as td:
            p,bid,dr,journal=self.blocked_fixture(td)
            p.remote=Mock(side_effect=[[{'batch_id':bid}], {'bundle_sha256':'new-seal'}])
            p.advance=Mock(return_value={'batch_id':bid,'state':'pr_open'})
            p.tick()
            reference=p.advance.call_args.args[1]['previous_attempts'][0]
            saved=dr/reference['path']
            self.assertEqual(json.loads(saved.read_text()),journal)
            self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(),reference['sha256'])

