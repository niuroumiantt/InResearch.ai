"""Append-only local records: one writer, durable appends, recoverable torn tail."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import uuid


from inresearch.storage.files import atomic_write as atomic_write, sync_directory as sync_directory, make_directory as make_directory, locked


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
        with locked(self.path):
            self.repair_tail()
            yield self

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


def append_record(path, row):
    store = JsonlStore(path)
    with store.locked():
        store.append(row)
