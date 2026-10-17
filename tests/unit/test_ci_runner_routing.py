"""Exercise the actual workflow expressions and pre-checkout trust boundary."""
import copy
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = 'niuroumiantt/InResearch.ai'
SPARK = ['self-hosted', 'Linux', 'ARM64', 'spark-ci']
HOSTED = ['ubuntu-latest']
AUTHORIZATION = """      - name: Authorize the dedicated Spark repository before checkout
        if: runner.environment == 'self-hosted'
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: python3 /usr/local/lib/ci-prefetch.py --authorize-only
"""


class WorkflowExpression:
    """Evaluate the boolean/string subset used by runs-on, with GH short-circuit values.

    Strings compare case-insensitively in Actions. The root-owned authorization
    still checks the exact live repository; this expression is only routing.
    Unsupported grammar fails instead of silently treating it as trusted.
    """
    def __init__(self, expression, context):
        prefix, suffix = '${{ fromJSON(', ') }}'
        if not expression.startswith(prefix) or not expression.endswith(suffix):
            raise ValueError('unsupported runs-on expression')
        source = expression[len(prefix):-len(suffix)]
        token = r"'(?:[^']|'')*'|&&|\|\||==|\(|\)|[A-Za-z_][\w.]*"
        self.tokens = re.findall(token, source)
        if re.sub(token, '', source).strip():
            raise ValueError('unparsed runs-on expression')
        self.index = 0
        self.context = context

    def take(self, value):
        if self.index < len(self.tokens) and self.tokens[self.index] == value:
            self.index += 1
            return True
        return False

    def atom(self):
        if self.take('('):
            value = self.disjunction()
            if not self.take(')'):
                raise ValueError('missing close parenthesis')
            return value
        token = self.tokens[self.index]
        self.index += 1
        if token == 'toJSON':
            if not self.take('('):
                raise ValueError('missing function argument')
            value = self.disjunction()
            if not self.take(')'):
                raise ValueError('missing function close')
            return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        if token.startswith("'"):
            return token[1:-1].replace("''", "'")
        if token in ('true', 'false', 'null'):
            return {'true': True, 'false': False, 'null': None}[token]
        value = self.context
        for name in token.split('.'):
            value = value.get(name) if isinstance(value, dict) else None
        return value

    def equality(self):
        left = self.atom()
        if self.take('=='):
            right = self.atom()
            if isinstance(left, str) and isinstance(right, str):
                return left.casefold() == right.casefold()
            if type(left) is type(right):
                return left == right
            def number(value):
                if value is None or value == '':
                    return 0
                if isinstance(value, (bool, int, float)):
                    return float(value)
                if isinstance(value, str):
                    try:
                        decoded = json.loads(value)
                        if type(decoded) in (int, float):
                            return decoded
                    except ValueError:
                        pass
                return float('nan')
            return number(left) == number(right)
        return left

    def conjunction(self):
        result = self.equality()
        while self.take('&&'):
            right = self.equality()
            result = right if result else result
        return result

    def disjunction(self):
        result = self.conjunction()
        while self.take('||'):
            right = self.conjunction()
            result = result if result else right
        return result

    def labels(self):
        result = self.disjunction()
        if self.index != len(self.tokens):
            raise ValueError('unconsumed runs-on expression')
        return json.loads(result)


def workflow_jobs(text):
    jobs = text.split('\njobs:\n', 1)[1]
    return dict(re.findall(r'^  ([\w-]+):\n(.*?)(?=^  [\w-]+:\n|\Z)', jobs, re.M | re.S))


def require_gate(job):
    steps = job.split('    steps:\n', 1)[1]
    first, rest = steps.split('      - uses: actions/checkout@v4', 1)
    if first != AUTHORIZATION or 'continue-on-error:' in job:
        raise ValueError('missing or bypassable pre-checkout authorization')
    if '/usr/local/lib/ci-prefetch.py' in rest or '--authorize-only' not in first:
        raise ValueError('unexpected prefetch placement')


class CIRunnerRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validate = (ROOT / '.github/workflows/validate.yml').read_text()
        cls.publication = (ROOT / '.github/workflows/verify-data-center-publication.yml').read_text()
        cls.jobs = {**{'validate/' + k: v for k, v in workflow_jobs(cls.validate).items()},
                    **{'publication/' + k: v for k, v in workflow_jobs(cls.publication).items()}}

    def route_all(self, github, expected):
        for name, job in self.jobs.items():
            with self.subTest(job=name, event=github):
                line = re.search(r'^    runs-on: (.+)$', job, re.M).group(1)
                self.assertEqual(WorkflowExpression(line, {'github': github}).labels(), expected)

    def test_every_existing_job_has_the_same_complete_routing(self):
        self.assertEqual(set(self.jobs), {'validate/scope', 'validate/validate', 'validate/browser',
                                        'validate/browser-core', 'validate/storage-container', 'publication/verify'})
        routes = {re.search(r'^    runs-on: (.+)$', job, re.M).group(1) for job in self.jobs.values()}
        self.assertEqual(len(routes), 1)

    def test_same_repository_pull_request_uses_the_dedicated_runner(self):
        self.route_all({'repository': REPOSITORY, 'event_name': 'pull_request',
                        'event': {'pull_request': {'head': {'repo': {'full_name': REPOSITORY, 'fork': False}}}}}, SPARK)

    def test_push_manual_and_schedule_use_the_dedicated_runner(self):
        for event in ('push', 'workflow_dispatch', 'schedule'):
            self.route_all({'repository': REPOSITORY, 'event_name': event}, SPARK)

    def test_forks_missing_heads_and_wrong_head_repository_stay_hosted(self):
        base = {'repository': REPOSITORY, 'event_name': 'pull_request',
                'event': {'pull_request': {'head': {'repo': {'full_name': REPOSITORY, 'fork': False}}}}}
        for repo in ({'full_name': 'outsider/InResearch.ai', 'fork': True},
                     {'full_name': REPOSITORY, 'fork': True},
                     {'full_name': 'niuroumiantt/other', 'fork': False},
                     {'full_name': REPOSITORY}, {}, None):
            context = copy.deepcopy(base)
            context['event']['pull_request']['head']['repo'] = repo
            self.route_all(context, HOSTED)
        self.route_all({'repository': REPOSITORY, 'event_name': 'pull_request'}, HOSTED)

    def test_unknown_events_pull_request_target_and_other_repositories_stay_hosted(self):
        for event in ('pull_request_target', 'repository_dispatch', '', 'merge_group'):
            self.route_all({'repository': REPOSITORY, 'event_name': event}, HOSTED)
        for event in ('push', 'workflow_dispatch', 'schedule'):
            self.route_all({'repository': 'outsider/InResearch.ai', 'event_name': event}, HOSTED)

    def test_expression_matches_actions_null_coercion_and_json_boolean_identity(self):
        expression = "${{ fromJSON(github.missing == false && '[\"loose\"]' || '[]') }}"
        self.assertEqual(WorkflowExpression(expression, {'github': {}}).labels(), ['loose'])
        expression = "${{ fromJSON(toJSON(github.missing) == 'false' && '[\"wrong\"]' || '[]') }}"
        self.assertEqual(WorkflowExpression(expression, {'github': {}}).labels(), [])
        # A string containing 'false' is not the boolean false either.
        self.route_all({'repository': REPOSITORY, 'event_name': 'pull_request',
                        'event': {'pull_request': {'head': {'repo': {'full_name': REPOSITORY, 'fork': 'false'}}}}}, HOSTED)

    def test_authorization_precedes_every_checkout_and_uses_only_job_token(self):
        for name, job in self.jobs.items():
            with self.subTest(job=name):
                require_gate(job)
                self.assertNotIn('secrets.', job)
                self.assertEqual(job.count('actions/checkout@v4'), 1)

    def test_removed_moved_or_bypassed_authorization_is_rejected(self):
        job = self.jobs['validate/validate']
        mutations = [job.replace(AUTHORIZATION, ''),
                     job.replace(AUTHORIZATION, '').replace('      - uses: actions/checkout@v4\n',
                                                           '      - uses: actions/checkout@v4\n' + AUTHORIZATION),
                     job.replace('--authorize-only', '--authorize-only || true'),
                     job.replace('        env:\n', '        continue-on-error: true\n        env:\n', 1),
                     job.replace('/usr/local/lib/ci-prefetch.py', './scripts/ci-prefetch.py'),
                     job.replace("runner.environment == 'self-hosted'", "github.event_name == 'push'"),
                     job.replace('${{ github.token }}', '${{ secrets.CI_ADMIN_TOKEN }}')]
        for mutated in mutations:
            with self.subTest(mutation=mutated[:80]), self.assertRaises(ValueError):
                require_gate(mutated)

    def test_failed_system_authorization_does_not_reach_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            python = directory / 'python3'
            python.write_text('#!/bin/sh\nexit 73\n')
            python.chmod(0o755)
            marker = directory / 'checkout-reached'
            command = re.search(r'^        run: (.+)$', AUTHORIZATION, re.M).group(1)
            result = subprocess.run(['/bin/bash', '-e', '-c', command + '\ntouch "$CHECKOUT_MARKER"'],
                                    env={**os.environ, 'PATH': str(directory) + os.pathsep + os.environ['PATH'],
                                         'CHECKOUT_MARKER': str(marker)}, capture_output=True)
            self.assertEqual(result.returncode, 73)
            self.assertFalse(marker.exists())

    def test_check_names_matrix_storage_and_timeouts_remain_complete(self):
        from scripts.ci_scope import FULL_SUITES
        self.assertEqual(len(FULL_SUITES), 19)
        self.assertIn('matrix:\n        suites: ${{ fromJSON(needs.scope.outputs.suites) }}', self.validate)
        self.assertIn('fail-fast: false', self.jobs['validate/browser'])
        self.assertIn('timeout-minutes: 15', self.jobs['validate/browser'])
        self.assertIn('name: browser (core)', self.jobs['validate/browser-core'])
        self.assertIn('needs: [scope, validate, browser, storage-container]', self.jobs['validate/browser-core'])
        self.assertIn('if: always()', self.jobs['validate/browser-core'])
        self.assertIn('python3 scripts/ci_scope.py gate', self.jobs['validate/browser-core'])
        for test in ('container_storage.py', 'container_cache.py'):
            self.assertIn('python3 tests/' + test, self.jobs['validate/storage-container'])
        self.assertIn('unittest discover -s tests/unit -p "test_*.py"', self.jobs['validate/validate'])
        for command in ('governance --check', 'validate --strict', 'registry', 'deliveries check', 'verify', 'indicators'):
            self.assertIn('manage.py ' + command, self.jobs['validate/validate'])
        self.assertIn('playwright@1.62.1 pngjs@7.0.0', self.jobs['validate/browser'])
        self.assertIn('${{ runner.arch }}-playwright-1.62.1', self.jobs['validate/browser'])

    def test_original_checkout_and_publication_main_only_contract_remain(self):
        for name, job in self.jobs.items():
            tail = job.split('      - uses: actions/checkout@v4\n', 1)[1]
            if name == 'publication/verify':
                self.assertTrue(tail.startswith('        with:\n          ref: ${{ github.sha }}\n'
                                                '          persist-credentials: false\n          fetch-depth: 1\n'))
            else:
                self.assertFalse(tail.startswith('        with:'))
        self.assertIn('git fetch --no-tags --depth=1 origin "$CI_BASE"', self.jobs['validate/scope'])
        self.assertIn("if: github.ref == 'refs/heads/main'", self.jobs['publication/verify'])
        self.assertIn('timeout-minutes: 11', self.jobs['publication/verify'])
        self.assertIn('python3 scripts/verify_data_center_publication.py', self.jobs['publication/verify'])
        for workflow in (self.validate, self.publication):
            self.assertIn('permissions:\n  contents: read', workflow)
            self.assertNotIn('pull_request_target:', workflow)
            self.assertNotIn('checks: write', workflow)
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", self.validate)
        self.assertIn("cron: '17 18 * * *'", self.validate)


if __name__ == '__main__':
    unittest.main()
