"""Adopting another machine's filing must move judgement, never bytes.

The corpus behind a reader catalog is irreplaceable and has no backup, so the
first test here is not about the feature working -- it is about the originals
being byte-identical afterwards. The rest pin the rules that are easy to break
by accident: the join is on content and not on path, a rename is not a reading,
and an existing placement is a conflict to report rather than one to overwrite.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from inresearch.materials import artifacts
from inresearch.materials.mapping import MAPPING_VERSION, load_mapping
from inresearch.workflow import apply_triage
from inresearch.workflow import reader as cr


class Clock:
    def __init__(self):
        self.now = 1_700_000_000.0

    def __call__(self):
        self.now += 1.0
        return self.now


class Model:
    """Only the identity the recipe hashes. Nothing here reads a document."""
    identity = {'backend': 'injected_test', 'model': cr.MODEL,
                'context': cr.CONTEXT, 'ocr_model': ''}


class ApplyTriageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inresearch-apply-triage-')
        self.base = Path(self.temp.name)
        self.clock = Clock()
        self.reader = cr.Reader(self.base / 'data', self.base / 'state', self.base / 'repo',
                                Model(), 0, 200, self.clock).initialize()

    def tearDown(self):
        self.reader.close()
        self.temp.cleanup()

    # -- fixtures ---------------------------------------------------------

    def register(self, name='paper.txt', text='服务器功率为 300 W。\n'):
        """One document in originals/ with a catalog row, as a scan would leave it."""
        raw = self.reader.data / 'raw-materials' / name
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(text, encoding='utf-8')
        self.reader.scan()
        return dict(self.reader.conn.execute(
            'SELECT * FROM current_readings WHERE original_name=?', (name,)).fetchone())

    def row(self, doc, to, **extra):
        return {'sha256': doc['sha256'], 'from': 'm4/wherever/' + doc['original_name'],
                'to': to, 'size': doc['size_bytes'], 'stage': 'library', **extra}

    def originals_snapshot(self):
        """Every byte under originals/, plus the shape of the tree itself."""
        root = self.reader.data / 'originals'
        out = {}
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                out[str(path.relative_to(root))] = ('symlink', str(path.readlink()))
            elif path.is_file():
                out[str(path.relative_to(root))] = (
                    'file', hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size)
            else:
                out[str(path.relative_to(root))] = ('dir',)
        return out

    def commit(self, rows):
        actions, counts = apply_triage.plan(self.reader.conn, rows)
        done, failures = apply_triage.commit(self.reader, actions)
        return counts, done, failures

    def legacy_catalog(self, name):
        """A v1 catalog built from the migration test's own schema, empty but real."""
        from test_catalog_migration import LEGACY_SCHEMA
        root = self.base / name
        (root / 'catalog').mkdir(parents=True)
        with sqlite3.connect(str(root / 'catalog/catalog.sqlite')) as conn:
            conn.executescript(LEGACY_SCHEMA)
            conn.execute('PRAGMA user_version=1')
        return root

    def schema_version(self, root):
        with sqlite3.connect(str(root / 'catalog/catalog.sqlite')) as conn:
            return conn.execute('PRAGMA user_version').fetchone()[0]

    def library_rel(self, doc_id):
        return self.reader.conn.execute(
            'SELECT library_rel FROM documents WHERE doc_id=?', (doc_id,)).fetchone()[0]

    def priority(self, doc_id):
        return self.reader.conn.execute(
            'SELECT priority FROM reading_runs WHERE doc_id=? AND base_revision_id IS NULL',
            (doc_id,)).fetchone()[0]

    # -- the property that matters most ------------------------------------

    def test_commit_leaves_every_original_byte_identical(self):
        doc = self.register()
        before = self.originals_snapshot()
        self.assertTrue(before, 'fixture must actually place an original')
        counts, done, failures = self.commit([self.row(doc, '算力/2024_某院_报告.txt', importance=7)])
        self.assertEqual(failures, [])
        self.assertEqual(done['linked'], 1)
        self.assertEqual(self.originals_snapshot(), before)

    def test_rollback_removes_the_imported_link_and_keeps_the_original(self):
        doc = self.register()
        before = self.originals_snapshot()
        self.commit([self.row(doc, '算力/2024_某院_报告.txt')])
        with self.reader.worker_session():
            result = self.reader.rollback(doc['doc_id'])
        self.assertTrue(result['source_preserved'])
        self.assertIsNone(self.library_rel(doc['doc_id']))
        self.assertEqual(self.originals_snapshot(), before)

    # -- the join is content, not path --------------------------------------

    def test_matches_on_content_when_every_path_was_renamed(self):
        doc = self.register(name='原始怪名字.txt')
        row = self.row(doc, '算力/2024_某院_报告.txt')
        row['from'] = 'completely/unrelated/tree/renamed-by-hand.txt'
        counts, done, _ = self.commit([row])
        self.assertEqual(done['linked'], 1)
        self.assertEqual(self.library_rel(doc['doc_id']), 'library/算力/2024_某院_报告.txt')

    def test_content_absent_here_is_reported_not_invented(self):
        missing = {'sha256': 'f' * 64, 'from': 'a.txt', 'to': '算力/a.txt',
                   'size': 1, 'stage': 'library'}
        actions, counts = apply_triage.plan(self.reader.conn, [missing])
        self.assertEqual(actions, [])
        self.assertEqual(counts.get('absent_here'), 1)

    def test_link_resolves_to_the_original(self):
        doc = self.register()
        self.commit([self.row(doc, '算力/2024_某院_报告.txt')])
        link = self.reader.data / self.library_rel(doc['doc_id'])
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), (self.reader.data / doc['original_rel']).resolve())

    # -- 7.3: a rename is not a reading -------------------------------------

    def test_filing_never_records_a_reading(self):
        doc = self.register()
        before = [dict(r) for r in self.reader.conn.execute(
            'SELECT revision_id,state,phase,report_rel,activated,current_revision_id'
            ' FROM reading_runs JOIN documents USING(doc_id)')]
        self.commit([self.row(doc, '算力/2024_某院_报告.txt', importance=9)])
        after = [dict(r) for r in self.reader.conn.execute(
            'SELECT revision_id,state,phase,report_rel,activated,current_revision_id'
            ' FROM reading_runs JOIN documents USING(doc_id)')]
        self.assertEqual(len(after), len(before))
        for was, now in zip(before, after):
            for field in ('revision_id', 'state', 'phase', 'report_rel', 'activated',
                          'current_revision_id'):
                self.assertEqual(now[field], was[field], field)

    # -- plan decides, commit repeats ---------------------------------------

    def test_plan_alone_writes_nothing(self):
        doc = self.register()
        before_priority = self.priority(doc['doc_id'])
        actions, counts = apply_triage.plan(
            self.reader.conn, [self.row(doc, '算力/2024_某院_报告.txt', importance=8)])
        self.assertEqual(len(actions), 1)
        self.assertIsNone(self.library_rel(doc['doc_id']))
        self.assertEqual(self.priority(doc['doc_id']), before_priority)
        self.assertFalse((self.reader.data / 'library/算力').exists())

    def test_running_twice_changes_nothing_the_second_time(self):
        doc = self.register()
        rows = [self.row(doc, '算力/2024_某院_报告.txt', importance=6)]
        self.commit(rows)
        after_first = self.originals_snapshot()
        counts, done, failures = self.commit(rows)
        self.assertEqual(failures, [])
        self.assertEqual(done['linked'], 0)
        self.assertEqual(done['repriced'], 0)
        self.assertEqual(counts.get('already_linked'), 1)
        self.assertEqual(self.originals_snapshot(), after_first)

    def test_existing_placement_is_a_conflict_not_an_overwrite(self):
        doc = self.register()
        self.commit([self.row(doc, '算力/第一次.txt')])
        counts, done, _ = self.commit([self.row(doc, '电力/第二次.txt')])
        self.assertEqual(counts.get('conflict'), 1)
        self.assertEqual(done['linked'], 0)
        self.assertEqual(self.library_rel(doc['doc_id']), 'library/算力/第一次.txt')
        self.assertFalse((self.reader.data / 'library/电力/第二次.txt').exists())

    # -- bounds and refusals -------------------------------------------------

    def test_priority_only_accepts_the_range_a_reading_could_produce(self):
        doc = self.register()
        baseline = self.priority(doc['doc_id'])
        for bad in (0, 10, -1, True, '5', 7.0, None):
            with self.subTest(importance=bad):
                self.assertIsNone(apply_triage.importance_of({'importance': bad}))
        self.commit([self.row(doc, '算力/a.txt', importance=0)])
        self.assertEqual(self.priority(doc['doc_id']), baseline)
        self.assertEqual(apply_triage.importance_of({'importance': 1}), 1)
        self.assertEqual(apply_triage.importance_of({'importance': 9}), 9)

    def test_targets_that_escape_the_library_are_refused(self):
        doc = self.register()
        for bad in ('../originals/paper.txt', '/etc/passwd', '', None, 'a/../../b.txt'):
            with self.subTest(to=bad):
                self.assertIsNone(apply_triage.target_rel({'to': bad}))
        counts, done, _ = self.commit([self.row(doc, '../originals/paper.txt')])
        self.assertEqual(counts.get('invalid_target'), 1)
        self.assertEqual(done['linked'], 0)
        self.assertIsNone(self.library_rel(doc['doc_id']))

    def test_duplicate_rows_for_one_content_are_refused_not_ordered(self):
        doc = self.register()
        counts, done, _ = self.commit([self.row(doc, '算力/first.txt'),
                                       self.row(doc, '电力/second.txt')])
        self.assertEqual(counts.get('duplicate_content'), 1)
        self.assertEqual(done['linked'], 1)
        self.assertEqual(self.library_rel(doc['doc_id']), 'library/算力/first.txt')

    def test_duplicate_stage_rows_are_not_filed(self):
        doc = self.register()
        row = self.row(doc, '算力/a.txt')
        row['stage'] = 'duplicates'
        actions, counts = apply_triage.plan(self.reader.conn, [row])
        self.assertEqual(actions, [])
        self.assertEqual(counts.get('not_library'), 1)

    # -- the real file format ------------------------------------------------

    def test_an_old_catalog_is_named_not_silently_migrated(self):
        """A plan promises to write nothing; Reader.initialize() would migrate.

        The 2026-09-18 Spark catalog was still v1 -- 32,734 documents and no
        reading_runs table -- so a plan run there would have rewritten every
        row of the ledger as a side effect of being asked what it would do.
        """
        legacy = self.base / 'legacy'
        (legacy / 'catalog').mkdir(parents=True)
        database = legacy / 'catalog/catalog.sqlite'
        with sqlite3.connect(str(database)) as conn:
            conn.execute('CREATE TABLE documents(doc_id TEXT PRIMARY KEY)')
            conn.execute('PRAGMA user_version=1')
        refusal = apply_triage.refuse_unless_current(legacy)
        self.assertIn('catalog_needs_upgrade', refusal)
        self.assertIn('reader init', refusal)
        with sqlite3.connect(str(database)) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='reading_runs'").fetchone()[0], 0)

    def test_a_current_catalog_is_accepted_and_a_missing_one_is_named(self):
        self.assertIsNone(apply_triage.refuse_unless_current(self.reader.data))
        self.assertIn('catalog_missing', apply_triage.refuse_unless_current(self.base / 'nowhere'))

    def test_the_command_itself_refuses_an_old_catalog_before_building_a_reader(self):
        """Testing the guard is not the same as testing that the CLI calls it.

        The legacy schema here is the real one, deliberately: a toy table would
        make the migration fail on its own and the test would pass because the
        upgrade crashed rather than because the guard stopped it. The migration
        has to be able to succeed for this to be worth anything -- the sibling
        assertion below proves it does.
        """
        from inresearch.interfaces import reader as reader_cli
        legacy = self.legacy_catalog('cli-legacy')
        mapping = self.base / 'unused-mapping.jsonl'
        mapping.write_text('', encoding='utf-8')
        code = reader_cli.main(['--data-root', str(legacy), '--state-root', str(self.base / 'cli-state'),
                                'apply-triage', '--mapping', str(mapping)])
        self.assertEqual(code, 1)
        self.assertEqual(self.schema_version(legacy), 1)
        with sqlite3.connect(str(legacy / 'catalog/catalog.sqlite')) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='reading_runs'").fetchone()[0], 0)

    def test_that_same_catalog_really_would_have_been_migrated(self):
        """The other half of the guard test: without it, this catalog upgrades.

        Without this, a legacy fixture that simply cannot migrate would make the
        guard test green forever while guarding nothing.
        """
        legacy = self.legacy_catalog('would-migrate')
        self.assertEqual(self.schema_version(legacy), 1)
        reader = cr.Reader(legacy, self.base / 'would-migrate-state', self.base / 'repo',
                           Model(), 0, 200, self.clock)
        try:
            reader.initialize()
        finally:
            reader.close()
        self.assertEqual(self.schema_version(legacy), 2)

    def test_reads_a_real_exported_mapping_file(self):
        doc = self.register()
        rows = [self.row(doc, '算力/2024_某院_报告.txt', importance=8)]
        path = self.base / 'mapping.jsonl'
        header = {'mapping_version': MAPPING_VERSION, 'generated': '2026-09-18T13:07:47Z',
                  'source_root': '/Users/m4/Downloads/所有raw materials',
                  'library_root': '/Users/m4/Downloads/inresearch资料库',
                  'dataset': 'm4-triage', 'files': len(rows)}
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n'
                                for r in [{'header': header}, *rows]), encoding='utf-8')
        loaded_header, loaded_rows = load_mapping(path)
        self.assertEqual(loaded_header['dataset'], 'm4-triage')
        counts, done, failures = self.commit(loaded_rows)
        self.assertEqual(failures, [])
        self.assertEqual(done, {'linked': 1, 'repriced': 1, 'failed': 0})
        self.assertEqual(self.priority(doc['doc_id']), 8)


if __name__ == '__main__':
    unittest.main()
