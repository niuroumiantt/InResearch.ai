"""Fault injection at transaction boundaries; all originals are synthetic files."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import file_moves as FM
from jsonl_store import JsonlStore, read_rows


class Crash(BaseException):
    pass


class MoveRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inresearch-move-recovery-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.library = self.root / 'library'
        self.source.mkdir()
        self.original = self.source / 'original.txt'
        self.original.write_bytes(b'original evidence')
        self.target = self.library / 'M01/read.txt'
        self.sha = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.row = {'event': 'move', 'stage': 'library', 'from': 'original.txt',
                    'to': 'M01/read.txt', 'sha256': self.sha}
        self.book = FM.MoveJournal(self.root / 'state/moves.jsonl',
                                  {'source': self.source, 'library': self.library})

    def crash_after_link(self):
        original_sync = FM.sync_directory
        def crash(path):
            if path.resolve() == self.target.parent.resolve():
                raise Crash()
            original_sync(path)
        with self.assertRaises(Crash), self.book.locked(), patch.object(FM, 'sync_directory', crash):
            self.book.move(self.row)

    def test_source_hash_change_leaves_both_paths_untouched(self):
        self.original.write_bytes(b'new evidence')
        with self.book.locked(), self.assertRaisesRegex(ValueError, 'hash_mismatch'):
            self.book.move(self.row)
        self.assertEqual(self.original.read_bytes(), b'new evidence')
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.book.rows()), [])

    def test_crash_before_link_cancels_intent_and_allows_retry(self):
        with self.assertRaises(Crash), self.book.locked(), patch.object(FM.os, 'link', side_effect=Crash):
            self.book.move(self.row)
        with self.book.locked():
            self.assertTrue(self.original.exists())
            self.book.move(self.row)
        self.assertEqual(self.target.read_bytes(), b'original evidence')
        self.assertEqual(sum(bool(r.get('ok')) for r in self.book.rows()), 1)

    def test_crash_after_link_recovers_without_copying(self):
        self.crash_after_link()
        self.assertTrue(os.path.samefile(self.original, self.target))
        with self.book.locked():
            pass
        self.assertFalse(self.original.exists())
        self.assertEqual(self.target.read_bytes(), b'original evidence')
        self.assertTrue(list(self.book.rows())[-1]['recovered'])
        before = self.book.path.read_bytes()
        with self.book.locked():
            pass
        self.assertEqual(self.book.path.read_bytes(), before)

    def test_crash_after_unlink_recovers_missing_commit(self):
        append = self.book.append
        def crash(row):
            if row.get('ok'):
                raise Crash()
            append(row)
        with self.assertRaises(Crash), self.book.locked(), patch.object(self.book, 'append', crash):
            self.book.move(self.row)
        self.assertFalse(self.original.exists())
        with self.book.locked():
            pass
        self.assertEqual(len(FM.replay(self.book.rows())), 1)
        self.assertTrue(list(self.book.rows())[-1]['recovered'])

    def test_torn_commit_is_preserved_then_recovered(self):
        self.crash_after_link()
        partial = b'{"event":"move","ok":tr'
        with self.book.path.open('ab') as stream:
            stream.write(partial)
        with self.book.locked():
            pass
        self.assertEqual(next(self.book.path.parent.glob('*.partial-*')).read_bytes(), partial)
        self.assertFalse(self.original.exists())
        self.assertEqual(len(FM.replay(self.book.rows())), 1)

    def test_modified_recovery_target_is_preserved_and_rejected(self):
        self.crash_after_link()
        self.target.write_bytes(b'changed meanwhile')
        with self.assertRaisesRegex(ValueError, 'content_mismatch'), self.book.locked():
            pass
        self.assertTrue(self.original.exists())
        self.assertEqual(self.target.read_bytes(), b'changed meanwhile')

    def test_destination_race_never_overwrites_and_releases_intent(self):
        self.target.parent.mkdir(parents=True)
        link = FM.os.link
        def race(source, target, **kwargs):
            target.write_bytes(b'another file')
            return link(source, target, **kwargs)
        with self.book.locked(), patch.object(FM.os, 'link', race), self.assertRaises(FileExistsError):
            self.book.move(self.row)
        with self.book.locked():
            pass
        self.assertEqual(self.target.read_bytes(), b'another file')
        self.assertEqual(self.original.read_bytes(), b'original evidence')
        self.assertEqual(list(self.book.rows())[-1]['state'], 'aborted')

    def test_paths_cannot_escape_or_follow_symlinks(self):
        outside = self.root / 'outside'
        outside.mkdir()
        self.library.mkdir()
        (self.library / 'link').symlink_to(outside)
        for target in ('../outside/file', str(outside / 'file'), 'link/file'):
            with self.subTest(target=target), self.book.locked(), self.assertRaises(ValueError):
                self.book.move({**self.row, 'to': target})
        self.assertEqual(list(outside.iterdir()), [])
        self.assertTrue(self.original.exists())

    def test_same_relative_name_in_two_roots_is_still_a_move(self):
        with self.book.locked():
            self.book.move({**self.row, 'to': 'original.txt'})
        records = FM.replay(self.book.rows())
        self.assertEqual(records[('library', 'original.txt')]['origin'], 'original.txt')

    def test_changed_root_binding_is_rejected(self):
        with self.book.locked():
            self.book.move(self.row)
        other = FM.MoveJournal(self.book.path, {'source': self.source, 'library': self.root / 'other'})
        with self.assertRaisesRegex(ValueError, 'roots_changed'), other.locked():
            pass

    def test_reader_catalog_originals_cannot_be_a_move_root(self):
        (self.root / 'catalog').mkdir()
        (self.root / 'catalog/catalog.sqlite').touch()
        with self.assertRaisesRegex(ValueError, 'originals_are_immutable'):
            FM.MoveJournal(self.book.path, {'source': self.root / 'originals', 'library': self.library})

    def test_two_processes_serialize_the_same_move(self):
        script = '''import json, sys
from pathlib import Path
from file_moves import MoveJournal
book = MoveJournal(sys.argv[1], json.loads(sys.argv[2]))
row = json.loads(sys.argv[3])
with book.locked():
    if book.paths(row)[0].exists():
        book.move(row)
'''
        args = [sys.executable, '-c', script, str(self.book.path),
                json.dumps(self.book.roots), json.dumps(self.row)]
        processes = [subprocess.Popen(args, cwd=Path(FM.__file__).parent, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE) for _ in range(2)]
        for process in processes:
            out, error = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, error.decode())
        self.assertEqual(sum(bool(r.get('ok')) for r in self.book.rows()), 1)
        self.assertEqual(self.target.read_bytes(), b'original evidence')


class JournalTailTests(unittest.TestCase):
    def test_valid_unterminated_record_gains_newline_and_interior_damage_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'rows.jsonl'
            path.write_bytes(b'{"ok":true}')
            with JsonlStore(path).locked() as store:
                store.append({'ok': False})
            self.assertEqual(list(read_rows(path)), [{'ok': True}, {'ok': False}])
            path.write_bytes(b'{bad}\n{"ok":true}\n')
            with self.assertRaises(ValueError):
                list(read_rows(path))
