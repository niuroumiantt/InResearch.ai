"""Durable same-volume file moves with a journal and no-overwrite recovery.

An exclusive hard link reserves the destination; unlinking the source completes
the move. A crash may leave two names for one inode, never a partially copied
file. Only a journaled operation with matching content may finish that unlink.
"""
from contextlib import contextmanager
import hashlib
import os as os
from pathlib import Path
import stat
import uuid

from inresearch.storage.jsonl import JsonlStore, make_directory, sync_directory as sync_directory


def safe_path(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or not relative.parts or '..' in relative.parts:
        raise ValueError('move_path_outside_root')
    root = Path(root).resolve()
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('move_symlink_not_allowed')
    path.resolve().relative_to(root)
    return path


def digest(path, sync=False):
    """Hash a regular file and reject changes during the read."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('move_regular_file_required')
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
        if sync:
            os.fsync(stream.fileno())
        after = os.fstat(stream.fileno())
    signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    if signature(before) != signature(after) or signature(after) != signature(path.lstat()):
        raise ValueError('move_source_changed')
    return value.hexdigest()


def endpoints(row):
    reverse = row.get('event') == 'revert'
    return ((row.get('from_root', 'library' if reverse or row.get('stage') == 'restage' else 'source'), row['from']),
            (row.get('to_root', 'source' if reverse else 'library'), row['to']))


def replay(rows):
    """Current placements and active move chains, keyed by (root, relative path).

    A path is an identity only within its root. Reverting a chain removes the
    matching transition, so apply -> revert -> apply remains possible.
    """
    at = {}
    for row in rows:
        if not row.get('ok') or row.get('event') not in ('move', 'revert'):
            continue
        src, dst = endpoints(row)
        record = at.pop(src, None)
        if record is None:
            if row['event'] == 'revert':
                raise ValueError('move_revert_without_origin')
            record = {'origin': src[1], 'origin_root': src[0],
                      'sha256': row.get('sha256'), 'stage': row.get('stage'),
                      'size': row.get('size', 0), 'chain': []}
        if record['sha256'] != row.get('sha256'):
            raise ValueError('move_ledger_content_conflict')
        if row['event'] == 'revert':
            previous = record['chain'][-1]
            previous_src, previous_dst = endpoints(previous)
            # Legacy reverts omitted root names, including library -> library.
            if 'to_root' not in row and row['to'] == previous_src[1]:
                dst = previous_src
            if (dst, src) != (previous_src, previous_dst):
                raise ValueError('move_revert_out_of_order')
            record['chain'].pop()
        else:
            record['chain'].append(row)
        if dst == (record['origin_root'], record['origin']):
            continue
        if dst in at:
            raise ValueError('move_ledger_destination_conflict')
        at[dst] = {**record, 'to_root': dst[0], 'to': dst[1]}
    return at


class MoveJournal(JsonlStore):
    def __init__(self, path, roots):
        super().__init__(path)
        self.roots = {key: str(Path(value).resolve()) for key, value in roots.items()}
        for value in self.roots.values():
            path = Path(value)
            for parent in (path, *path.parents):
                if (parent / 'catalog/catalog.sqlite').is_file():
                    originals = parent / 'originals'
                    if path == originals or originals in path.parents:
                        raise ValueError('reader_originals_are_immutable')
        source, library = (Path(self.roots[key]) for key in ('source', 'library'))
        if source == library or source in library.parents or library in source.parents:
            raise ValueError('move_roots_must_be_disjoint')

    @contextmanager
    def locked(self):
        with super().locked():
            self.recover()
            yield self

    def paths(self, row):
        if row.get('roots', self.roots) != self.roots:
            raise ValueError('move_roots_changed')
        source, target = endpoints(row)
        return (safe_path(self.roots[source[0]], source[1]),
                safe_path(self.roots[target[0]], target[1]))

    def recover(self):
        pending = {}
        for row in self.rows():
            if row.get('roots', self.roots) != self.roots:
                raise ValueError('move_roots_changed')
            # Old move logs have no operation_id; pair intent and outcome by path.
            key = row.get('operation_id') or (row.get('event'), row.get('from_root'),
                                             row.get('from'), row.get('to'), row.get('sha256'))
            if row.get('ok') or row.get('state') == 'aborted':
                pending.pop(key, None)
            elif row.get('event') in ('move', 'revert'):
                pending[key] = row
        for row in pending.values():
            source, target = self.paths(row)
            if source.exists() and not target.exists():
                # Nothing moved: leave source untouched and permit a fresh attempt.
                self.append({**row, 'state': 'aborted', 'ok': False})
                continue
            if not target.is_file() or digest(target) != row['sha256']:
                raise ValueError('move_recovery_content_mismatch')
            if source.exists():
                if not os.path.samefile(source, target):
                    raise ValueError('move_recovery_path_conflict')
                source.unlink()
                sync_directory(source.parent)
            self.append({**row, 'state': 'committed', 'ok': True, 'recovered': True})

    def move(self, row):
        source, target = self.paths(row)
        if digest(source, sync=True) != row['sha256']:
            raise ValueError('move_source_hash_mismatch')
        make_directory(target.parent)
        if source.stat().st_dev != target.parent.stat().st_dev:
            raise ValueError('move_requires_same_volume')
        row = {key: value for key, value in row.items() if key not in {'recovered', 'error'}}
        record = {**row, 'operation_id': uuid.uuid4().hex, 'roots': self.roots,
                  'schema_version': 1, 'state': 'prepared', 'ok': False}
        self.append(record)
        try:
            os.link(source, target, follow_symlinks=False)  # Exclusive destination.
        except OSError:
            # link failed before changing either name; this intent needs no recovery.
            self.append({**record, 'state': 'aborted', 'ok': False})
            raise
        sync_directory(target.parent)
        # Check the claimed inode/content before removing its old name.
        if not os.path.samefile(source, target) or digest(target) != row['sha256']:
            raise ValueError('move_source_changed')
        source.unlink()
        sync_directory(source.parent)
        self.append({**record, 'state': 'committed', 'ok': True})
