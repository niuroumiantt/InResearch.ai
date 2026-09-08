"""Private durable website inbox. Documents are data, never execution instructions."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid

MAX_BYTES = 64 * 1024 * 1024

def root():
    return Path(os.environ.get('INRESEARCH_INTAKE_ROOT', Path(__file__).resolve().parent.parent / 'data/.material-intake'))

def record_path(key):
    if not re.fullmatch(r'[a-f0-9]{32}', key):
        raise ValueError('invalid submission id')
    return root() / key

def atomic(path, data):
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.partial')
    with tmp.open('w') as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def receive(stream, size, metadata, user):
    if not 0 < size <= MAX_BYTES:
        raise ValueError('单份资料须为 1 字节至 64 MiB')
    root().mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(root()).free < size + 1024**3:
        raise ValueError('接收空间不足，请稍后重试')
    key = uuid.uuid4().hex
    folder = record_path(key)
    folder.mkdir(mode=0o700)
    name = str(metadata.get('name', '资料.txt')).replace('\\', '/').split('/')[-1][:180]
    if not name or name.startswith('.'):
        name = '资料.txt'
    digest = hashlib.sha256()
    remaining = size
    with (folder / 'content.partial').open('wb') as f:
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError('上传中断，未接收完整文件')
            f.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
        f.flush()
        os.fsync(f.fileno())
    os.replace(folder / 'content.partial', folder / 'content')
    record = dict(id=key, name=name, size=size, sha256=digest.hexdigest(), user=user,
                  topic=str(metadata.get('topic', ''))[:300], source=str(metadata.get('source', ''))[:2000],
                  note=str(metadata.get('note', ''))[:4000], created=time.time(), status='queued')
    atomic(folder / 'record.json', record)
    return record

def records():
    return sorted((json.loads(p.read_text()) for p in root().glob('*/record.json')), key=lambda r:r['created'], reverse=True)

def acknowledge(key, sha):
    path = record_path(key) / 'record.json'
    record = json.loads(path.read_text())
    if sha != record['sha256']:
        raise ValueError('checksum mismatch')
    record.update(status='archived', archived=time.time())
    atomic(path, record)
    return record
