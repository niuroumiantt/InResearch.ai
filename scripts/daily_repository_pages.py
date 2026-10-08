#!/usr/bin/env python3
"""Refresh pages from remote main snapshots without changing active checkouts."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from sync_repo_pages import CANONICAL


def run(command, **kwargs):
    result = subprocess.run(command, capture_output=True, **kwargs)
    if result.returncode:
        # Git diagnostics may contain credential-bearing URLs.
        raise RuntimeError(f'{command[0]}: operation failed (exit {result.returncode}); diagnostics withheld')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.home() / 'code')
    parser.add_argument('--check', action='store_true', help='Reproduce source snapshots without refreshing observations')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='repository-pages-') as folder:
        temp = Path(folder)
        roots = {}
        registry = json.loads((args.workspace / 'infra/scripts/repositories.json').read_text())
        for key, canonical in CANONICAL.items():
            if key == 'inresearch':
                continue
            local = args.workspace / canonical
            # Fetch known canonical repository directly; never reset/switch/stash local work.
            run(['git', '-C', str(local), 'fetch', '--quiet',
                 'https://github.com/' + registry[canonical] + '.git', 'main'])
            revision = run(['git','-C',str(local),'rev-parse','FETCH_HEAD'], text=True).strip()
            snapshot = temp / canonical
            snapshot.mkdir()
            archive = run(['git','-C',str(local),'archive',revision])
            run(['tar','-xf','-','-C',str(snapshot)], input=archive)
            tracked = run(['git','-C',str(local),'ls-tree','-r','--name-only',revision],text=True).splitlines()
            (snapshot/'.repository-snapshot.json').write_text(json.dumps({'revision':revision,'tracked_files':tracked}))
            roots[key] = str(snapshot)
        mapping = temp/'roots.json'
        mapping.write_text(json.dumps(roots))
        command = [sys.executable, str(ROOT/'scripts/sync_repo_pages.py'),
                   '--workspace',str(args.workspace),'--source-roots',str(mapping)]
        if args.check:
            command.append('--check')
        else:
            check = subprocess.run([sys.executable,str(Path(roots['infra'])/'scripts/daily_check.py')],
                                   capture_output=True, text=True, timeout=600)
            if check.returncode not in (0,1):
                raise RuntimeError('infra daily check did not complete; previous published observations retained')
            today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
            report = Path.home()/'.local/state/infra/daily'/f'{today}.json'
            if not report.is_file():
                raise RuntimeError('infra check produced no report')
            command += ['--probe','--daily-report',str(report)]
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
