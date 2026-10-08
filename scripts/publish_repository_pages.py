"""Validate and atomically activate a complete private repository-page projection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

KEYS = ('inresearch','inews','fetchspec','infra','oa','aimail','leadsgen','semifly',
        'glocalstorage','openapi','agent')
FILES = {'repos.html', *(key+'repo.html' for key in KEYS),
         *('repo-content/'+name for name in ('infra.html','fetchspec.html','manifest.json','checks.json','infra-daily.json'))}


def validate(folder):
    folder = Path(folder)
    found = {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file()}
    if found != FILES or any(p.is_symlink() for p in folder.rglob('*')):
        raise ValueError('repository projection is incomplete or contains unregistered files')
    hashes = {}
    for name in FILES:
        data = (folder/name).read_bytes()
        if not data or len(data) > 8_000_000:
            raise ValueError('empty or oversized artifact')
        hashes[name] = hashlib.sha256(data).hexdigest()
    manifest = json.loads((folder/'repo-content/manifest.json').read_text())
    if set(manifest) != set(KEYS):
        raise ValueError('repository manifest does not match registered pages')
    for record in manifest.values():
        if not record.get('sources') or not record.get('synced_at'):
            raise ValueError('missing provenance')
    return hashes


def activate(folder, destination):
    hashes = validate(folder)
    destination = Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    release = destination/'releases'/uuid.uuid4().hex
    shutil.copytree(folder,release)
    if validate(release) != hashes:
        raise ValueError('artifact checksum mismatch')
    (release/'_release.json').write_text(json.dumps({'sha256':hashes})+'\n')
    for path in [destination,release.parent,release,*release.rglob('*')]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    pointer = destination/('.current-'+uuid.uuid4().hex)
    pointer.symlink_to(release.relative_to(destination))
    os.replace(pointer,destination/'current')
    return {'release':release.name,'files':len(hashes),'sha256':hashes}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(activate(args.source,args.destination)))
