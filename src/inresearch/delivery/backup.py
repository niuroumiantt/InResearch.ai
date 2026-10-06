#!/usr/bin/env python3
"""Create and verify a portable acquisition backup; destination must be new."""
import argparse
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from inresearch.adapters.acquisition import data_root
from inresearch.storage.files import locked

def backup(root,dest):
    root=Path(root);dest=Path(dest);dest.mkdir(parents=True,exist_ok=False)
    marker=dest/'backup.partial.json';marker.write_text('{}')
    source=sqlite3.connect((root/'acquisition/catalog.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    target=sqlite3.connect(dest/'catalog.sqlite')
    try:
        source.backup(target)
        if target.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('backup_integrity')
        paths=target.execute('select distinct relative_path,sha256 from observations').fetchall()
    finally:source.close();target.close()
    for relative,digest in paths:
        src=(root/relative).resolve()
        if not src.is_relative_to((root/'acquisition/blobs').resolve()):raise ValueError('unsafe_archive_path')
        dst=dest/relative;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        if hashlib.sha256(dst.read_bytes()).hexdigest()!=digest:raise ValueError('backup_blob_integrity')
    for name in ('project-pipeline.json','daily-events.json'):
        src=root/'acquisition'/name
        if not src.exists():continue
        with locked(src):
            if src.is_symlink():raise ValueError('unsafe_ledger_path')
            content=src.read_bytes();json.loads(content)
            dst=dest/'acquisition'/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(content)
    files={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file() and p!=marker}
    (dest/'manifest.json').write_text(json.dumps({'files':files},indent=2)+'\n');marker.unlink()
    return len(files)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-root',type=Path,default=data_root());p.add_argument('--dest',type=Path,required=True);a=p.parse_args()
    print(json.dumps({'files_verified':backup(a.data_root,a.dest)}))


if __name__ == '__main__':
    main()
