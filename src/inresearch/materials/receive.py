#!/usr/bin/env python3
"""Pull complete submissions, verify bytes, archive privately, then open reader input."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request
import fcntl
from inresearch.materials.inbox import atomic

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def main():
    data = Path(os.environ.get('READER_DATA_ROOT', Path.home() / '.local/share/inresearch.ai'))
    archive = data / 'web-submissions'
    archive.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (archive / '.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    token = (Path.home() / '.local/state/inresearch.ai/reader-sync.token').read_text().strip()
    opener = urllib.request.build_opener(NoRedirect)
    def request(path, payload=None):
        return opener.open(urllib.request.Request('https://inresearch.ai/api/intake-worker/' + path,
            data=json.dumps(payload).encode() if payload else None,
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}), timeout=120)
    with request('pending') as response:
        items = json.load(response)['items']
    for item in items:
        import re
        key = item['id']
        if not re.fullmatch('[a-f0-9]{32}', key):
            raise ValueError('invalid id')
        folder = archive / key
        folder.mkdir(exist_ok=True, mode=0o700)
        target = folder / 'original'
        if not target.exists():
            digest = hashlib.sha256()
            count = 0
            with request('content/' + key) as response, (folder / 'original.partial').open('wb') as f:
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > item['size']:
                        raise ValueError('size mismatch')
                    f.write(chunk)
                    digest.update(chunk)
                f.flush()
                os.fsync(f.fileno())
            if count != item['size'] or digest.hexdigest() != item['sha256']:
                raise ValueError('checksum mismatch')
            os.replace(folder / 'original.partial', target)
        digest = hashlib.sha256()
        with target.open('rb') as stored:
            for chunk in iter(lambda: stored.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != item['sha256']:
            raise ValueError('archive checksum mismatch')
        atomic(folder / 'receipt.json', item)
        # An index is retryable and separate from archive/Reader delivery.
        name = Path(item['name']).name
        if Path(name).suffix.lower() in ('.pdf', '.html', '.htm', '.txt', '.md'):
            from inresearch.workflow.research_match import ingest
            from inresearch.paths import project_root
            import subprocess
            indexed = folder / ('index-source' + Path(name).suffix.lower())
            if not indexed.exists():
                os.link(target, indexed)
            try:
                result = ingest(indexed, data, project_root(), title=name)
                atomic(folder/'matching.json', {'status':'matched_candidate','sha256':result['sha256']})
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                atomic(folder/'matching.json', {'status':'blocked','error':type(exc).__name__})
        # A durable marker prevents re-delivery after reader moved the input.
        if not (folder / 'delivered.json').exists():
            raw = data / 'raw-materials'
            raw.mkdir(exist_ok=True)
            staging = raw / ('.web-' + key + '.partial')
            visible = raw / ('web-' + key)
            if not visible.exists():
                staging.mkdir(exist_ok=True)
                name = Path(item['name']).name
                shutil.copyfile(target, staging / name)
                os.replace(staging, visible)
            atomic(folder / 'delivered.json', {'sha256': item['sha256']})
        with request('ack', {'id': key, 'sha256': item['sha256']}) as response:
            if not json.load(response).get('ok'):
                raise ValueError('ack failed')
    print(json.dumps({'received': len(items)}))

if __name__ == '__main__':
    main()
