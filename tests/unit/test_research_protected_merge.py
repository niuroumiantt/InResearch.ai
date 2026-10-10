"""Protected merges retain exact-head CI/C3 while avoiding unrelated rebases."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from inresearch.workflow import research_publish as publication

REQUIRED = ('validate', 'browser (core)')
HEAD = 'a' * 40


class ProtectedMergeTests(unittest.TestCase):
    def guard(self, *, head=HEAD, mergeable=True, admin=True, names=REQUIRED, app=15368, strict=False, merge_state='clean'):
        info = {'state':'open', 'head':{'sha':head},
                'base':{'ref':'main', 'sha':'b'*40}, 'mergeable':mergeable, 'mergeable_state':merge_state}
        protection = {'enforce_admins':{'enabled':admin}, 'required_status_checks':{
            'strict':strict, 'checks':[{'context':name, 'app_id':app} for name in names]}}
        with patch.object(publication, 'run', side_effect=[
                SimpleNamespace(stdout=json.dumps(info)),
                SimpleNamespace(stdout=json.dumps(protection))]):
            return publication.protected_main_merge_receipt('/repo', 554, HEAD)

    def test_verified_protection_and_mergeability_produce_bound_receipt(self):
        receipt = self.guard()
        self.assertEqual((receipt['commit'], receipt['base'], receipt['pr']), (HEAD, 'b'*40, 554))
        self.assertEqual(set(receipt['required_checks']), set(REQUIRED))

    def test_changed_head_conflict_missing_checks_or_bypass_refuse_fast_path(self):
        for change in ({'head':'c'*40}, {'mergeable':False}, {'mergeable':None},
                       {'admin':False}, {'names':REQUIRED[:-1]}, {'app':99}, {'strict':True}, {'merge_state':'unknown'}):
            with self.subTest(change=change):
                self.assertIsNone(self.guard(**change))

    def test_unavailable_protection_refuses_fast_path(self):
        with patch.object(publication, 'run', side_effect=RuntimeError('API unavailable')):
            self.assertIsNone(publication.protected_main_merge_receipt('/repo', 554, HEAD))

    def advance(self, *, enabled=True, receipt=True, context=True, bucket='pass'):
        with tempfile.TemporaryDirectory() as td:
            config = {'repo':td, 'state':td}
            if enabled:
                config['base_update_policy'] = 'protected_merge'
            publisher = publication.Publisher(config)
            publisher.sync_source = Mock()
            publisher.remote = Mock(return_value={'context_current':context})
            journal = {'state':'pr_open', 'batch_id':'d'*64, 'pr':554,
                       'commit':HEAD, 'worktree':td, 'statement_ids':['preserve']}
            info = SimpleNamespace(stdout=json.dumps({'state':'OPEN', 'headRefOid':HEAD}))
            checks = [{'name':name, 'bucket':bucket} for name in REQUIRED]
            with patch.object(publication, 'run', return_value=info) as run, \
                    patch.object(publication, 'publication_checks', return_value=checks), \
                    patch.object(publication, 'protected_main_merge_receipt',
                                 return_value={'commit':HEAD, 'base':'b'*40} if receipt else None) as guard, \
                    patch.object(publication, 'refresh_publication_base', return_value='c'*40) as refresh:
                result = publisher.advance(Path(td), journal)
            return result, run, guard, refresh, publisher.remote

    def test_protected_merge_keeps_tested_head_and_records_receipt(self):
        result, run, guard, refresh, remote = self.advance()
        self.assertEqual(result['commit'], HEAD)
        self.assertEqual(result['statement_ids'], ['preserve'])
        self.assertEqual(result['protected_merges'][0]['commit'], HEAD)
        refresh.assert_not_called()
        remote.assert_called_once_with('verify', '--batch-id', 'd'*64)
        self.assertTrue(any(call.args[0][:3] == ['gh','pr','merge'] for call in run.call_args_list))

    def test_missing_protection_and_default_mode_still_refresh_and_retest(self):
        for args in ({'receipt':False}, {'enabled':False}):
            with self.subTest(args=args):
                result, run, guard, refresh, _ = self.advance(**args)
                self.assertEqual((result['state'], result['commit'], result['checks']),
                                 ('prepared', 'c'*40, []))
                refresh.assert_called_once()
                self.assertFalse(any(call.args[0][:3] == ['gh','pr','merge'] for call in run.call_args_list))
                if not args.get('enabled', True):
                    guard.assert_not_called()

    def test_failed_or_pending_ci_and_changed_context_never_use_fast_path(self):
        for args, state in (({'bucket':'fail'}, 'blocked'),
                            ({'bucket':'pending'}, 'pr_open'), ({'context':False}, 'revalidation')):
            with self.subTest(args=args):
                result, run, guard, refresh, _ = self.advance(**args)
                self.assertEqual(result['state'], state)
                guard.assert_not_called(); refresh.assert_not_called()
                self.assertFalse(any(call.args[0][:3] == ['gh','pr','merge'] for call in run.call_args_list))

    def test_local_acceptance_cannot_select_protected_ci_merge(self):
        with tempfile.TemporaryDirectory() as td, self.assertRaisesRegex(ValueError, 'base_update_policy'):
            publication.Publisher({'repo':td, 'state':td, 'publication_mode':'local_acceptance',
                                   'base_update_policy':'protected_merge'})
