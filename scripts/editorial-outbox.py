#!/usr/bin/env python3
"""Seal a completed longform; launchd retries its delivery without another prompt."""
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from inresearch.storage.files import locked, write_json, atomic_write

def sha(body): return hashlib.sha256(body).hexdigest()

def seal(folder, outbox):
    folder = Path(folder).resolve()
    article = folder / 'article.md'
    sources = folder / 'sources.json'
    browser = json.loads((folder / 'checks/browser.json').read_text())
    if browser.get('pass') is not True: raise ValueError('render_not_passed')
    for name in ('wechat', 'full', 'lite'):
        if sha((folder / (name + '.html')).read_bytes()) != browser.get('input_sha256', {}).get(name):
            raise ValueError('render_inputs_changed')
    if not article.is_file() or article.is_symlink() or not sources.is_file() or sources.is_symlink():
        raise ValueError('invalid_longform')
    text = article.read_text()
    title = text.splitlines()[0].lstrip('# ').strip()
    ident = 'geluoke-' + folder.name
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', ident): raise ValueError('invalid_longform_id')
    payload = {'article.md': article.read_bytes(), 'sources.json': sources.read_bytes()}
    research = folder / 'research/research.txt'
    if research.is_file() and not research.is_symlink(): payload['research.txt'] = research.read_bytes()
    files = [{'path': n, 'bytes': len(b), 'sha256': sha(b)} for n,b in sorted(payload.items())]
    manifest = {'schema': 'editorial-delivery-v1', 'id': ident, 'title': title, 'article': 'article.md',
                'source_role': 'authored_analysis', 'files': files}
    revision = sha(json.dumps(manifest, sort_keys=True).encode())
    dest = Path(outbox) / ident / revision
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name, body in payload.items(): atomic_write(dest / name, body)
    # Manifest is published last; a watcher never reads a partial bundle.
    write_json(dest / 'manifest.json', manifest)
    return dest

def deliver(manifest, state, host, remote_repo):
    from inresearch.adapters.editorial_sync import load_bundle
    load_bundle(manifest)  # Local hash/role/path preflight before copying.
    body = Path(manifest).read_bytes()
    key = sha(body)
    receipt = Path(state) / (key + '.json')
    with locked(receipt):
        if receipt.exists(): return {'unchanged': True, 'receipt': str(receipt)}
        if not re.fullmatch(r'[A-Za-z0-9_-]+', host): raise ValueError('invalid_host')
        remote = '.local/share/inresearch.ai/incoming/editorial/outbox-' + key
        subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',host,'mkdir -p ' + remote], check=True, timeout=30)
        # The sealed manifest is immutable; retries verify the receiver's bytes.
        subprocess.run(['rsync','-a',str(Path(manifest).parent) + '/',host + ':' + remote + '/'],check=True,timeout=120)
        command = 'cd ' + shlex.quote(remote_repo) + ' && set -a && . "$HOME/.config/inresearch.ai/reader.env" && set +a && python3 manage.py editorial-sync --bundle "$HOME/' + remote + '/manifest.json"'
        result = subprocess.run(['ssh','-o','BatchMode=yes',host,command],check=True,capture_output=True,text=True,timeout=180)
        value = json.loads(result.stdout)
        if value.get('acceptance') != 'candidate' or value.get('article_sha256') != sha((Path(manifest).parent/'article.md').read_bytes()):
            raise ValueError('invalid_delivery_receipt')
        write_json(receipt,value)
        return value

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('seal','watch'))
    p.add_argument('folder',nargs='?')
    p.add_argument('--outbox',default=str(Path.home()/'.local/share/inresearch.ai/editorial-outbox'))
    p.add_argument('--state',default=str(Path.home()/'.local/state/inresearch.ai/editorial-deliveries'))
    p.add_argument('--host',default='spark')
    p.add_argument('--remote-repo',default='/home/spark/code/inresearch.ai')
    a=p.parse_args()
    if a.action=='seal':
        print(json.dumps({'sealed':str(seal(a.folder,a.outbox))}));return 0
    errors=[];received=0
    for manifest in sorted(Path(a.outbox).glob('**/manifest.json')):
        try:
            result=deliver(manifest,a.state,a.host,a.remote_repo);received+=not result.get('unchanged',False)
        except Exception as exc: errors.append({'manifest':str(manifest),'error':str(exc)})
    print(json.dumps({'received':received,'errors':errors},ensure_ascii=False))
    return int(bool(errors))

if __name__=='__main__':sys.exit(main())
