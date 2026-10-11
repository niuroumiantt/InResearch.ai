"""Durable files and cross-process read/validate/write transactions.

Atomic replacement protects readers; locked() protects a complete mutation.
The lock is a stable sibling inode, never the inode being replaced. Callers
must keep business validation inside the transaction and publish only once.
"""
import fcntl
import hashlib
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


def atomic_write(path, data, *, exclusive=False):
    return _atomic_chunks(path, (data,), exclusive=exclusive)


def _atomic_chunks(path, chunks, *, exclusive=False):
    path = Path(path)
    make_directory(path.parent)
    if path.is_symlink():
        raise ValueError('refuse_symlink_destination')
    temporary = path.with_name('.' + path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            for block in chunks:
                stream.write(block)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path)  # Publish a complete new file; never replace one.
        else:
            os.replace(temporary, path)
        try:
            if exclusive:
                temporary.unlink()
            sync_directory(path.parent)
        except OSError as exc:
            raise CommitUncertain() from exc
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, value):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, allow_nan=False,
                                  indent=2) + '\n').encode('utf-8'))


def write_json_streaming(path, value):
    """Durable compact JSON, encoding bounded records with the C JSON encoder."""
    digest = hashlib.sha256()
    def chunks():
        for block in iter_json_bytes(value):
            digest.update(block)
            yield block
        digest.update(b'\n')
        yield b'\n'
    _atomic_chunks(path, chunks())
    return digest.hexdigest()


def iter_json_bytes(value, *, sort_keys=False):
    """Avoid both a giant string and millions of Python-level token writes."""
    options = dict(ensure_ascii=False, allow_nan=False, sort_keys=sort_keys, separators=(',', ':'))
    def fits(item):
        remaining, stack = 65536, [item]
        while stack:
            current = stack.pop()
            if isinstance(current, str):
                remaining -= 6 * len(current) + 2
            elif isinstance(current, (list, tuple, dict)):
                remaining -= 8 * len(current) + 2
                if remaining < 0:
                    return False
                if isinstance(current, dict):
                    stack.extend(current.keys()); stack.extend(current.values())
                else:
                    stack.extend(current)
            else:
                remaining -= 24
            if remaining < 0:
                return False
        return True
    def emit(item, parents):
        if fits(item):
            yield json.dumps(item, **options).encode('utf-8')
        elif isinstance(item, str):
            yield b'"'
            for start in range(0, len(item), 16384):
                yield json.dumps(item[start:start+16384], **options)[1:-1].encode('utf-8')
            yield b'"'
        elif isinstance(item, (list, tuple, dict)):
            if id(item) in parents:
                raise ValueError('Circular reference detected')
            parents = parents | {id(item)}
            mapping = isinstance(item, dict)
            yield b'{' if mapping else b'['
            entries = (sorted(item.items()) if sort_keys else item.items()) if mapping else enumerate(item)
            for index, (key, child) in enumerate(entries):
                if index:
                    yield b','
                if mapping:
                    # Preserve JSON's supported non-string key conversion.
                    yield json.dumps({key: 0}, **options)[:-2].encode('utf-8')[1:]
                yield from emit(child, parents)
            yield b'}' if mapping else b']'
        else:
            yield json.dumps(item, **options).encode('utf-8')
    yield from emit(value, set())


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
