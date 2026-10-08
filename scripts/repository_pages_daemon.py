#!/usr/bin/env python3
"""macmini system cron job: pull merged source, inspect, generate, publish, independent of chat."""
from datetime import datetime, timezone, timedelta
import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import tempfile
import uuid

TZ = timezone(timedelta(hours=8))
STATE = Path.home()/'.local/state/inresearch.ai/repository-refresh'
LABEL = 'ai.inresearch.repository-pages'
DESTINATION = '/srv/inresearch.ai/data/raw/repository-pages'
SOURCE_FILES = ('scripts/sync_repo_pages.py','scripts/repository_checks.py',
    'scripts/daily_repository_pages.py','scripts/publish_repository_pages.py',
    'src/inresearch/README.md','framework/tco_targets.json',
    'web/assets/material-flow.js','web/assets/material-flow.css')


def stamp():
    return datetime.now(TZ).isoformat(timespec='seconds')


def command(args, **kwargs):
    result = subprocess.run(args,capture_output=True,timeout=kwargs.pop('timeout',300),**kwargs)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed (exit {result.returncode}); raw diagnostics withheld')
    return result.stdout


def publish_status(status):
    payload = json.dumps(status,ensure_ascii=False).encode()
    script = ('import os,sys,pathlib; p=pathlib.Path('+repr(DESTINATION)+'); '
              'p.mkdir(parents=True,exist_ok=True); t=p/".status.tmp"; '
              't.write_bytes(sys.stdin.buffer.read()); t.chmod(0o644); os.replace(t,p/"status.json")')
    command(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','aws',
             'sudo -n python3 -c '+shlex.quote(script)],input=payload,timeout=60)


def update_status(status):
    target=STATE/'status.json'
    temporary=STATE/'status.tmp'
    temporary.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(target)
    publish_status(status)


def refresh():
    workspace=Path.home()/'code'
    local=workspace/'inresearch.ai'
    command(['git','-C',str(local),'fetch','--quiet',
             'https://github.com/niuroumiantt/InResearch.ai.git','main'])
    revision=command(['git','-C',str(local),'rev-parse','FETCH_HEAD'],text=True).strip()
    with tempfile.TemporaryDirectory(prefix='repository-system-refresh-') as folder:
        root=Path(folder)/'source';root.mkdir()
        archive=command(['git','-C',str(local),'archive',revision,*SOURCE_FILES])
        command(['tar','-xf','-','-C',str(root)],input=archive)
        (root/'.repository-snapshot.json').write_text(json.dumps({'revision':revision}))
        command([sys.executable,str(root/'scripts/daily_repository_pages.py'),
                 '--workspace',str(workspace)],timeout=1200)
        sys.path.insert(0,str(root/'scripts'))
        from publish_repository_pages import validate
        bundle=root/'web/pages/admin'
        expected=validate(bundle)
        remote='/tmp/repository-pages-'+uuid.uuid4().hex
        command(['ssh','-o','BatchMode=yes','aws','mkdir -m 700 '+remote])
        package=command(['tar','-cf','-','-C',str(bundle),'.'])
        command(['ssh','-o','BatchMode=yes','aws','tar -xf - -C '+remote],input=package)
        activate=(root/'scripts/publish_repository_pages.py').read_bytes()
        response=command(['ssh','-o','BatchMode=yes','aws',
            'sudo -n python3 - --source '+remote+' --destination '+DESTINATION],input=activate)
        result=json.loads(response)
        if result['sha256'] != expected:
            raise RuntimeError('published bundle differs from checked artifacts')
        # Only this run's system temporary staging directory; no source/data removal.
        command(['ssh','-o','BatchMode=yes','aws','rm -r '+remote])
        return {'source_revision':revision,'release':result['release'],'files':result['files']}


def execute(force=False):
    os.umask(0o077)
    STATE.mkdir(parents=True,exist_ok=True)
    with (STATE/'job.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        prior=json.loads((STATE/'status.json').read_text()) if (STATE/'status.json').exists() else {}
        today=datetime.now(TZ).date().isoformat()
        if not force and prior.get('state')=='completed' and prior.get('last_success_at','').startswith(today):
            return 0
        status={'schema_version':1,'runner':'macmini','schedule':'00:00 Asia/Shanghai',
                'state':'running','started_at':stamp(),'last_success_at':prior.get('last_success_at')}
        try:
            update_status(status)
            result=refresh()
            status.update(result,state='completed',finished_at=stamp(),last_success_at=stamp())
            update_status(status)
            print('Repository pages published:',status['finished_at'],status['files'])
            return 0
        except Exception as error:
            status.update(state='failed',finished_at=stamp(),error=str(error)[:240])
            try:
                update_status(status)
            except Exception:
                print('Failed to send job status; local evidence retained',file=sys.stderr)
            print('Repository refresh failed:',status['error'],file=sys.stderr)
            return 1


def install():
    if platform.system()!='Darwin' or platform.node().split('.')[0]!='macmini':
        raise SystemExit('Install this always-on job on macmini, not a laptop.')
    STATE.mkdir(parents=True,exist_ok=True)
    existing=subprocess.run(['crontab','-l'],capture_output=True,text=True)
    if existing.returncode and not (existing.returncode==1 and 'no crontab' in existing.stderr):
        raise RuntimeError('Cannot read current crontab; existing schedule was not changed')
    begin,end='# BEGIN inresearch.repository-pages','# END inresearch.repository-pages'
    kept=[];inside=False
    for line in existing.stdout.splitlines():
        if line==begin:
            if inside:raise RuntimeError('Malformed existing schedule')
            inside=True
        elif line==end:
            if not inside:raise RuntimeError('Malformed existing schedule')
            inside=False
        elif not inside:
            kept.append(line)
    if inside:raise RuntimeError('Incomplete existing schedule; left unchanged')
    runner=shlex.quote(str(Path(__file__).resolve()))
    python=shlex.quote(sys.executable)
    log=shlex.quote(str(STATE/'job.log'))
    entry='0 * * * * /usr/bin/env PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin TZ=Asia/Shanghai '+python+' '+runner+' >> '+log+' 2>&1'
    command(['crontab','-'],input='\n'.join([*kept,begin,entry,end,'']),text=True)
    # First run is detached from SSH/chat; subsequent runs belong to system cron.
    with (STATE/'job.log').open('a') as output:
        subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--force'],
            stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    print('Installed system cron: daily 00:00, hourly retry, independent of GUI/login/chat.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install',action='store_true')
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    if args.install:
        install()
    else:
        sys.exit(execute(args.force))
