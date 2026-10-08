"""Read-only checks for repository snapshots; missing evidence stays unknown."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import json
import subprocess
import urllib.request
import urllib.error

TZ = timezone(timedelta(hours=8))
ENDPOINTS = {
    'inresearch': ('https://inresearch.ai/healthz', [200]),
    'inews': ('https://inews.today/', [200]),
    'oa': ('https://oa.glocalstorage.cn/', [302]),
    'aimail': ('https://mail.glocalstorage.cn/', [302]),
    'leadsgen': ('https://leads.glocalstorage.cn/', [302]),
    'agent': ('https://agent.glocalstorage.cn/', [302]),
    'semifly': ('https://semifly.ai/', [200]),
    'glocalstorage': ('https://glocalstorage.com/', [200]),
    'openapi': ('https://api.semifly.ai/', [200]),
}


def timestamp():
    return datetime.now(TZ).isoformat(timespec='seconds')


def probe(key):
    if key not in ENDPOINTS:
        return {'state': 'unknown', 'detail': '未登记公网检测入口'}
    url, expected = ENDPOINTS[key]
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    result = {'observed_at': timestamp(), 'url': url,
              'scope': '公网入口 HTTP/TLS；不代表业务验收或数据库健康'}
    try:
        try:
            response = urllib.request.build_opener(NoRedirect).open(
                urllib.request.Request(url, headers={'User-Agent': 'repository-daily-check'}), timeout=20)
            with response:
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        result.update(state='passed' if status in expected else 'failed', status=status,
                      detail=f'HTTP {status}' + (' · 登录保护跳转符合预期' if status == 302 and status in expected else ''))
    except (OSError, urllib.error.URLError) as exc:
        result.update(state='failed', detail=type(exc).__name__)
    return result


def ci(repository, revision):
    try:
        result = subprocess.run(['gh', 'run', 'list', '-R', repository, '--commit', revision,
            '--limit', '30', '--json', 'workflowName,status,conclusion,url,updatedAt,event'],
            capture_output=True, text=True, timeout=35, check=True)
        runs = json.loads(result.stdout)
        # Latest run per workflow; canceled earlier attempts do not mask a rerun.
        latest = {}
        for run in sorted(runs, key=lambda r: r['updatedAt'], reverse=True):
            if run['event'] in ('push', 'pull_request', 'workflow_dispatch'):
                latest.setdefault(run['workflowName'], run)
        runs = list(latest.values())
        state = ('unknown' if not runs else 'failed' if any(r['conclusion'] in ('failure','timed_out','action_required') for r in runs)
                 else 'pending' if any(r['status'] != 'completed' for r in runs)
                 else 'passed' if all(r['conclusion'] == 'success' for r in runs) else 'unknown')
        return {'state': state, 'observed_at': timestamp(), 'revision': revision, 'runs': runs,
                'detail': '该源码提交的 GitHub 工作流；不是本次重跑完整测试' if runs else '该提交无可读取的工作流结果'}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'state': 'unknown', 'observed_at': timestamp(), 'revision': revision,
                'detail': '工作流结果未取得'}


def collect(roots, repositories):
    def one(item):
        key, root = item
        snapshot=root / '.repository-snapshot.json'
        revision = (json.loads(snapshot.read_text())['revision'] if snapshot.exists() else
                    subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip())
        return key, {'checked_at': timestamp(), 'revision': revision,
                     'endpoint': probe(key), 'ci': ci(repositories[key], revision)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(pool.map(one, roots.items()))
