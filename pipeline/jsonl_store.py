"""Append-only local records: one writer, durable appends, recoverable torn tail."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import uuid


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def make_directory(path):
    path = Path(path)
    if path.exists():
        return
    make_directory(path.parent)
    path.mkdir(exist_ok=True)
    sync_directory(path.parent)


def read_rows(path):
    """Readers may see a writer's incomplete final line; never hide interior damage."""
    path = Path(path)
    if not path.exists():
        return
    with path.open('rb') as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('record must be an object')
            except ValueError as exc:
                if not line.endswith(b'\n'):
                    return
                raise ValueError('%s:%d: invalid JSON record' % (path, number)) from exc
            yield row


class JsonlStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def locked(self):
        make_directory(self.path.parent)
        with self.path.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                self.repair_tail()
                yield self
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def repair_tail(self):
        if not self.path.exists():
            return
        with self.path.open('rb+') as stream:
            end = stream.seek(0, os.SEEK_END)
            if not end:
                return
            stream.seek(end - 1)
            if stream.read(1) == b'\n':
                return
            # Scan backwards, allocating only the final record even for large ledgers.
            start = end
            tail = b''
            while start:
                count = min(start, 8192)
                start -= count
                stream.seek(start)
                chunk = stream.read(count)
                split = chunk.rfind(b'\n')
                if split >= 0:
                    tail = chunk[split + 1:] + tail
                    start += split + 1
                    break
                tail = chunk + tail
            try:
                row = json.loads(tail)
                if not isinstance(row, dict):
                    raise ValueError('record must be an object')
            except ValueError:
                backup = self.path.with_name(self.path.name + '.partial-' + uuid.uuid4().hex)
                with backup.open('xb') as saved:
                    saved.write(tail)
                    saved.flush()
                    os.fsync(saved.fileno())
                sync_directory(self.path.parent)
                stream.seek(start)
                stream.truncate()
            else:
                stream.seek(0, os.SEEK_END)
                stream.write(b'\n')
            stream.flush()
            os.fsync(stream.fileno())

    def rows(self):
        return read_rows(self.path)

    def append(self, row):
        created = not self.path.exists()
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        if created:
            sync_directory(self.path.parent)


def atomic_write(path, data):
    """Replace a small metadata file only after all bytes are durable."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
