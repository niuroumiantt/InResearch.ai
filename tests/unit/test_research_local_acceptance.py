"""Publication opt-in changes the validation executor, never C3 or source authority."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from inresearch.materials.artifacts import atomic_json, digest_file
from inresearch.workflow import research_publish as publication
from test_research_review import audit, fixture


class LocalAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.directory = self.root/('c'*64)
        self.directory.mkdir()
        self.attempt = self.directory/'attempt-0001'
        self.attempt.mkdir()
        packet, row = fixture()
        bundle = audit(self.attempt, packet, row)
        bundle['attempt'] = 'attempt-0001'
        atomic_json(self.attempt/'bundle.json', bundle)
        self.journal = {'state':'pr_open', 'batch_id':'c'*64, 'attempt':'attempt-0001',
            'bundle_sha256':digest_file(self.attempt/'bundle.json'), 'commit':'a'*40,
            'pr':999, 'branch':'codex/research-publication-fixture',
            'worktree':str(self.root/'worktree'), 'statement_ids':['adopted']}
        self.publisher = publication.Publisher({'repo':str(self.root), 'state':str(self.root),
                                                'publication_mode':'local_acceptance'})
        self.proof = {'verified':True, 'batch_id':'c'*64, 'attempt':'attempt-0001',
                      'bundle_sha256':self.journal['bundle_sha256'], 'context_current':True}
        self.publisher.remote = Mock(return_value=self.proof)
        self.publisher.sync_source = Mock()
        self.commands = []
        self.failed_command = None
        self.changed_head = False

    def command(self, argv, *args, **kwargs):
        argv = list(argv)
        self.commands.append(argv)
        if argv[:2] == ['gh', 'api']:
            self.fail('local acceptance queried CI')
        if argv[:3] == ['gh', 'pr', 'view']:
            head = 'f'*40 if self.changed_head else self.journal['commit']
            return SimpleNamespace(stdout=json.dumps({'state':'OPEN', 'headRefOid':head}),
                                   stderr='', returncode=0)
        if argv == ['git', 'rev-parse', 'HEAD']:
            out = self.journal['commit']
        elif argv == ['git', 'rev-parse', 'origin/main']:
            out = 'b'*40
        elif argv == ['git', 'status', '--porcelain']:
            out = ''
        elif argv[:3] == ['gh', 'pr', 'list']:
            out = '[]'
        elif argv[:3] in (['gh', 'pr', 'merge'], ['gh', 'pr', 'close']):
            out = ''
        elif tuple(argv) in publication.LOCAL_ACCEPTANCE_COMMANDS:
            if argv == self.failed_command:
                raise RuntimeError('actual_local_command_failed')
            out = 'completed local fixture checks'
        else:
            self.fail('unexpected command '+repr(argv))
        return SimpleNamespace(stdout=out, stderr='', returncode=0)

    def advance(self):
        with patch.object(publication, 'run', side_effect=self.command), \
                patch.object(publication, 'publication_checks', side_effect=AssertionError('CI called')), \
                patch.object(publication, 'refresh_publication_base', return_value='a'*40):
            return self.publisher.advance(self.directory, self.journal)

    def merges(self):
        return [a for a in self.commands if a[:3] == ['gh', 'pr', 'merge']]

    def test_default_is_ci_and_unknown_mode_is_rejected(self):
        self.assertEqual(publication.Publisher({'repo':str(self.root),'state':str(self.root)}).publication_mode,'ci')
        with self.assertRaisesRegex(ValueError,'invalid_publication_mode'):
            publication.Publisher({'repo':str(self.root),'state':str(self.root),'publication_mode':'skip'})
        self.assertEqual(self.publisher.group_wait_seconds,300)
        for value in (True,-1,3601,1.5,'300'):
            with self.subTest(group_wait_seconds=value), self.assertRaisesRegex(ValueError,'invalid_publication_group_wait'):
                publication.Publisher({'repo':str(self.root),'state':str(self.root),'group_wait_seconds':value})

    def test_local_mode_runs_every_fixed_check_and_never_queries_ci(self):
        result = self.advance()
        self.assertNotIn('error', result)
        self.assertEqual(len(self.merges()),1)
        self.assertEqual(self.merges()[0][-2:],['--match-head-commit','a'*40])
        self.assertEqual([a for a in self.commands if tuple(a) in publication.LOCAL_ACCEPTANCE_COMMANDS],
                         [list(c) for c in publication.LOCAL_ACCEPTANCE_COMMANDS])
        ref = result['local_acceptance']
        path = self.directory/ref['path']
        self.assertEqual(digest_file(path),ref['sha256'])
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt['binding']['baseline'],'b'*40)
        self.assertEqual(receipt['binding']['batch_id'],result['batch_id'])
        self.assertEqual(receipt['binding']['attempt'],result['attempt'])
        self.assertEqual(receipt['binding']['bundle_sha256'],result['bundle_sha256'])
        self.assertEqual([r['returncode'] for r in receipt['results']],[0]*5)
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(self.publisher.remote.call_count,2)

    def test_any_fixed_check_failure_cannot_create_receipt_or_merge(self):
        for command in publication.LOCAL_ACCEPTANCE_COMMANDS:
            with self.subTest(command=command):
                self.failed_command=list(command)
                self.commands=[]
                self.journal.pop('local_acceptance',None)
                self.journal['state']='pr_open'
                result=self.advance()
                self.assertIn('actual_local_command_failed',result['error'])
                self.assertFalse(self.merges())
                self.assertNotIn('local_acceptance',result)

    def test_actual_nonzero_check_saves_private_failure_log_without_pass_or_merge(self):
        command=publication.LOCAL_ACCEPTANCE_COMMANDS[0]
        original=self.command
        def failed(argv,*args,**kwargs):
            if tuple(argv)==command:
                return SimpleNamespace(stdout='test failed',stderr='failure details',returncode=1)
            return original(argv,*args,**kwargs)
        with patch.object(publication,'run',side_effect=failed), \
                patch.object(publication,'publication_checks',side_effect=AssertionError('CI')), \
                patch.object(publication,'refresh_publication_base',return_value='a'*40):
            result=self.publisher.advance(self.directory,self.journal)
        self.assertIn('local_acceptance_check_failed_0_exit=1',result['error'])
        self.assertNotIn('local_acceptance',result)
        self.assertFalse(self.merges())
        logs=list((self.directory/'local-acceptance').glob('check-*.json'))
        self.assertEqual(len(logs),1)
        self.assertEqual(json.loads(logs[0].read_text())['returncode'],1)
        self.assertEqual(logs[0].stat().st_mode & 0o777,0o600)

    def test_missing_receipt_is_never_a_merge_permit(self):
        with patch.object(publication,'run',side_effect=self.command), \
                patch.object(self.publisher,'accept_local',return_value=None), \
                patch.object(publication,'refresh_publication_base',return_value='a'*40):
            result=self.publisher.advance(self.directory,self.journal)
        self.assertIn('receipt_required',result['error'])
        self.assertFalse(self.merges())

    def test_wrong_receipt_hash_or_binding_cannot_merge(self):
        with patch.object(publication,'run',side_effect=self.command):
            self.publisher.accept_local(self.journal,self.directory)
        original=copy.deepcopy(self.journal)
        for mutation in ('hash','commit','batch','bundle','attempt','commands','failed_result'):
            with self.subTest(mutation=mutation):
                self.journal=copy.deepcopy(original)
                ref=self.journal['local_acceptance']
                path=self.directory/ref['path']
                receipt=json.loads(path.read_text())
                if mutation=='hash':ref['sha256']='0'*64
                else:
                    if mutation=='commands':receipt['commands']=[]
                    elif mutation=='failed_result':receipt['results'][0]['returncode']=1
                    else:receipt['binding'][{'batch':'batch_id','bundle':'bundle_sha256','attempt':'attempt','commit':'commit'}[mutation]]='wrong'
                    atomic_json(path,receipt)
                    ref['sha256']=digest_file(path)
                self.commands=[]
                self.journal['state']='pr_open'
                result=self.advance()
                self.assertIn('local_acceptance_receipt',result['error'])
                self.assertFalse(self.merges())
                # Restore immutable fixture bytes for the next corruption case.
                if mutation!='hash':
                    receipt['binding']={'commit':'a'*40,'baseline':'b'*40,'batch_id':'c'*64,
                        'attempt':'attempt-0001','bundle_sha256':original['bundle_sha256']}
                    receipt['commands']=[list(c) for c in publication.LOCAL_ACCEPTANCE_COMMANDS]
                    receipt['results'][0]['returncode']=0
                    atomic_json(path,receipt)
                    original['local_acceptance']['sha256']=digest_file(path)

    def test_changed_context_uses_existing_revalidation_without_local_checks_or_merge(self):
        for when in ('before','after_checks'):
            with self.subTest(when=when):
                self.commands=[]
                self.journal['state']='pr_open'
                self.journal.pop('local_acceptance',None)
                changed={**self.proof,'context_current':False}
                self.publisher.remote=Mock(side_effect=([changed,{}] if when=='before'
                                                       else [self.proof,changed,{}]))
                result=self.advance()
                self.assertEqual(result['state'],'revalidation')
                self.publisher.remote.assert_any_call('revalidate','--batch-id','c'*64)
                self.assertFalse(self.merges())
                if when=='before':
                    self.assertFalse(any(tuple(a) in publication.LOCAL_ACCEPTANCE_COMMANDS for a in self.commands))

    def test_wrong_pr_head_or_remote_bundle_prevents_checks_and_merge(self):
        self.changed_head=True
        result=self.advance()
        self.assertIn('pr_head_changed',result['error'])
        self.assertFalse(self.merges())
        self.changed_head=False
        self.journal['state']='pr_open'
        self.publisher.remote=Mock(return_value={**self.proof,'bundle_sha256':'0'*64})
        result=self.advance()
        self.assertIn('source_binding_changed',result['error'])
        self.assertFalse(self.merges())

    def test_base_refresh_preserves_prior_head_and_invalidates_old_acceptance(self):
        with patch.object(publication,'run',side_effect=self.command):
            self.publisher.accept_local(self.journal,self.directory)
        old_receipt=copy.deepcopy(self.journal['local_acceptance'])
        with patch.object(publication,'run',side_effect=self.command), \
                patch.object(publication,'refresh_publication_base',return_value='d'*40):
            result=self.publisher.advance(self.directory,self.journal)
        self.assertEqual(result['state'],'prepared')
        self.assertEqual(result['commit'],'d'*40)
        self.assertEqual(result['base_refreshes'][0]['from'],'a'*40)
        self.assertEqual(result['local_acceptance_history'],[old_receipt])
        self.assertNotIn('local_acceptance',result)
        self.assertTrue((self.directory/old_receipt['path']).exists())
        self.assertFalse(self.merges())

    def test_final_changed_pr_head_cannot_merge_after_passing_checks(self):
        def change_after_acceptance(*args):
            result=original(*args)
            self.changed_head=True
            return result
        original=self.publisher.accept_local
        with patch.object(self.publisher,'accept_local',side_effect=change_after_acceptance):
            result=self.advance()
        self.assertIn('pr_head_changed',result['error'])
        self.assertFalse(self.merges())

    def test_other_publisher_open_pr_applies_repository_wide_backpressure(self):
        self.publisher.remote=Mock(return_value=[{'batch_id':'d'*64}])
        self.publisher.advance=Mock()
        rows=[{'number':123,'headRefName':'codex/research-publication-other','headRefOid':'f'*40},
              {'number':124,'headRefName':'codex/atlas-other','headRefOid':'e'*40}]
        with patch.object(publication,'run',return_value=SimpleNamespace(stdout=json.dumps(rows))):
            result=self.publisher.tick()
        self.assertEqual(result['state'],'waiting_batches')
        self.assertEqual(result['waiting'][0]['prs'],[123])
        self.publisher.advance.assert_not_called()
        self.assertFalse((self.root/('d'*64)/'journal.json').exists())

    def test_existing_pr_is_advanced_before_new_batches(self):
        atomic_json(self.directory/'journal.json',self.journal)
        self.publisher.advance=Mock(return_value={**self.journal,'state':'merged'})
        self.publisher.remote=Mock()
        self.publisher.tick()
        self.publisher.advance.assert_called_once()
        self.publisher.remote.assert_not_called()

    def test_blocked_local_recovery_retains_old_error_without_ci_query(self):
        self.journal.update(state='blocked',error='ci_failed_preserve_review_branch')
        atomic_json(self.directory/'journal.json',self.journal)
        self.publisher.remote=Mock(side_effect=[[{'batch_id':'c'*64}],self.proof])
        self.publisher.advance=Mock(return_value={'state':'pr_open'})
        with patch.object(publication,'run',side_effect=self.command), \
                patch.object(publication,'publication_checks',side_effect=AssertionError('CI called')):
            self.publisher.tick()
        recovered=self.publisher.advance.call_args.args[1]
        self.assertEqual(recovered['recoveries'][0]['error'],'ci_failed_preserve_review_branch')
        self.assertEqual(recovered['recoveries'][0]['reason'],'explicit_local_acceptance_recovery')
