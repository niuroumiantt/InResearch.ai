"""Durable files and cross-process read/validate/write transactions.

Atomic replacement protects readers; locked() protects a complete mutation.
The lock is a stable sibling inode, never the inode being replaced. Callers
must keep business validation inside the transaction and publish only once.
"""
import fcntl
import json
import os
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

_locks = {}
_guard = threading.Lock()


class CommitUncertain(OSError):
    """Replacement is visible, but its directory durability was not confirmed.

    Callers must inspect the authoritative record before retrying. Do not roll
    back: a later process may already have observed or updated the new value.
    """

    def __init__(self):
        super().__init__('commit_visible_durability_unconfirmed; read current state before retry')


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


def atomic_write(path, data):
    path = Path(path)
    make_directory(path.parent)
    if path.is_symlink():
        raise ValueError('refuse_symlink_destination')
    temporary = path.with_name('.' + path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        try:
            sync_directory(path.parent)
        except OSError as exc:
            raise CommitUncertain() from exc
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, value):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, allow_nan=False,
                                  indent=2) + '\n').encode('utf-8'))


@contextmanager
def locked(path):
    """Non-reentrant transaction; nested writes to the same file are a bug."""
    path = Path(path).absolute()
    make_directory(path.parent)
    key = str(path.parent.resolve() / path.name)
    with _guard:
        guard = _locks.setdefault(key, threading.Lock())
    with guard:
        lock_path = path.with_name('.' + path.name + '.lock')
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                if path.is_symlink():
                    raise ValueError('refuse_symlink_destination')
                yield path
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


@contextmanager
def json_transaction(path):
    """Commit only on normal exit; validation exceptions leave bytes unchanged."""
    with locked(path) as target:
        value = json.loads(target.read_text(encoding='utf-8'))
        yield value
        write_json(target, value)
