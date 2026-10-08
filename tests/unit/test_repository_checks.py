"""Missing, failed and stale observations must not become green checks."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


checks = module('repository_checks')
pages = module('sync_repo_pages')


class RepositoryCheckTests(unittest.TestCase):
    def test_missing_ci_and_failed_request_are_not_passed(self):
        with patch.object(checks.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '[]')):
            self.assertEqual(checks.ci('org/repo', 'a' * 40)['state'], 'unknown')
        with patch.object(checks.subprocess, 'run', side_effect=subprocess.TimeoutExpired([], 35)):
            self.assertEqual(checks.ci('org/repo', 'a' * 40)['state'], 'unknown')
        with patch.object(checks.urllib.request, 'build_opener') as opener:
            opener.return_value.open.side_effect = TimeoutError('sensitive raw diagnostic')
            result = checks.probe('inews')
            self.assertEqual(result['state'], 'failed')
            self.assertNotIn('sensitive', str(result))
        self.assertEqual(checks.probe('fetchspec')['state'], 'unknown')

    def test_no_redirect_following_and_explicit_status_expectations(self):
        for key, status, expected in [('oa', 302, 'passed'), ('inresearch', 302, 'failed'), ('inews', 503, 'failed')]:
            with self.subTest(key=key), patch.object(checks.urllib.request, 'build_opener') as opener:
                opener.return_value.open.side_effect = checks.urllib.error.HTTPError('https://example.test', status, '', {}, None)
                self.assertEqual(checks.probe(key)['state'], expected)

    def test_old_failed_attempt_does_not_mask_successful_rerun(self):
        import json
        runs = [dict(workflowName='validate', status='completed', conclusion=c,
                     updatedAt=t, event='push', url='https://github.com/org/repo/actions/runs/1')
                for c,t in [('failure','2026-10-03'),('success','2026-10-08')]]
        with patch.object(checks.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(runs))):
            result = checks.ci('org/repo', 'a' * 40)
            self.assertEqual(result['state'], 'passed')
            self.assertEqual(len(result['runs']), 1)

    def test_check_dates_and_unreachable_host_facts_remain_honest(self):
        text = pages.source_note({'synced_at':'2026-10-08', 'sources':[],
            'checks':{'checked_at':'2026-10-03', 'endpoint':{'state':'failed','detail':'HTTP 503'}}})
        self.assertIn('检测时间：2026-10-03', text)
        self.assertIn('异常', text)
        self.assertIn('未取得', text)
        report = {'started_at':'2026-10-08 10:00','summary':'一台未取得',
            'reach':[{'host':'aliyun','ok':False}], 'collect_errors':{'aliyun':'连不上'},
            'facts':{'aliyun':{'容器 old-container':'healthy'}}, 'changes':{}, 'warnings':{}}
        text = pages.infra_live(report)
        self.assertIn('事实未取得', text)
        self.assertNotIn('old-container', text)
