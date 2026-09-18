#!/usr/bin/env python3
"""Apply another machine's triage to this catalog without re-reading anything.

M4 classified and renamed the corpus; this machine holds the same bytes under a
catalog that owns them. The two sides are joined on sha256 and never on path:
the folders were reorganised by hand, and content is the only key that survives
that. A 2026-09-18 reconciliation matched 32,727 of this catalog's 32,734
documents against M4's export, so the join is the cheap part; what was missing
was somewhere to put the answer.

What this does: sets each matched document's library view link and its reading
priority. What it must never do: touch originals, or record a rename as a
reading. The placement carries M4's judgement, not a new one, so no reading_run
is created and nothing is marked read -- M4_TRIAGE_TASK.md 7.3 states that
directly, and it is the rule most easily broken by accident here.

The link is created by the reader's own verified path, which symlinks
library/... -> originals/..., re-hashes the source and refuses anything whose
digest does not match what the catalog recorded. Planning is therefore free;
committing reads every matched original once, because that check is the point.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path, PurePosixPath

LIBRARY_STAGE = 'library'
CATALOG_VERSION = 2


def catalog_path(data_root=None):
    root = Path(data_root or Path.home() / '.local/share/inresearch.ai').expanduser().resolve()
    return root / 'catalog/catalog.sqlite'


def refuse_unless_current(data_root=None):
    """Return an error string when this catalog is not one this command may plan against.

    Reader.initialize() upgrades a v1 catalog on its way in. That is right for a
    reader about to read and wrong here: a plan promises to write nothing, and
    the upgrade rewrites every row of the ledger. The 2026-09-18 Spark catalog
    was still v1 -- 32,734 documents, no reading_runs table -- so planning there
    would have silently migrated it. The version is therefore read from a
    read-only connection first, and an old catalog is named, not converted.
    """
    path = catalog_path(data_root)
    if not path.is_file():
        return 'catalog_missing: ' + str(path)
    try:
        connection = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    except sqlite3.Error:
        return 'catalog_unreadable: ' + str(path)
    try:
        version = connection.execute('PRAGMA user_version').fetchone()[0]
    finally:
        connection.close()
    if version == CATALOG_VERSION:
        return None
    if version < CATALOG_VERSION:
        return ('catalog_needs_upgrade: schema v%s; run `manage.py reader init` first '
                '(it backs the catalog up and migrates it), then re-run apply-triage' % version)
    return 'catalog_newer_than_this_reader: schema v%s' % version


def target_rel(row):
    """The library path M4 filed this content under, kept inside library/.

    load_mapping already rejects absolute and escaping targets, but a mapping
    is a file that arrived from another machine, so the check is repeated here
    rather than assumed.
    """
    target = row.get('to')
    if not isinstance(target, str) or not target:
        return None
    parts = PurePosixPath(target).parts
    if PurePosixPath(target).is_absolute() or '..' in parts or not parts:
        return None
    return 'library/' + target


def importance_of(row):
    """M4's 1-9 importance, or None. Out-of-range values leave priority alone.

    The reader validates the same bound when a reading produces one, so an
    imported value that would be rejected there is not written here either.
    """
    value = row.get('importance')
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 1 <= value <= 9 else None


def plan(conn, rows):
    """Decide every action against the catalog, changing nothing.

    A commit repeats exactly these decisions, so a plan that looks wrong is a
    plan not to commit -- the corpus behind this catalog is irreplaceable and
    has no backup.
    """
    documents = {row['sha256']: dict(row) for row in conn.execute(
        'SELECT doc_id,sha256,original_rel,library_rel FROM documents')}
    priorities = {row['doc_id']: row['priority'] for row in conn.execute(
        'SELECT doc_id,priority FROM reading_runs WHERE base_revision_id IS NULL')}
    actions, counts, seen = [], {}, {}

    def note(kind):
        counts[kind] = counts.get(kind, 0) + 1

    for row in rows:
        if row.get('stage') != LIBRARY_STAGE:
            note('not_library'); continue
        sha = row.get('sha256')
        document = documents.get(sha) if isinstance(sha, str) else None
        if document is None:
            note('absent_here'); continue
        if sha in seen:
            # Two library rows for one content would make the outcome depend on
            # row order; refuse the pair instead of silently taking the last.
            note('duplicate_content'); continue
        seen[sha] = True
        relative = target_rel(row)
        if relative is None:
            note('invalid_target'); continue
        importance = importance_of(row)
        current = document['library_rel']
        if current == relative:
            link = 'already_linked'
        elif current:
            # Someone or something already filed this document elsewhere. Which
            # placement is right is a judgement, so it is reported, not guessed.
            link = 'conflict'
        else:
            link = 'link'
        reprice = (importance is not None
                   and priorities.get(document['doc_id']) != importance)
        note(link)
        if reprice:
            note('reprice')
        if link == 'link' or reprice:
            actions.append({'doc_id': document['doc_id'], 'sha256': sha,
                            'original_rel': document['original_rel'],
                            'target_rel': relative, 'link': link,
                            'importance': importance if reprice else None})
    return actions, counts


def commit(reader, actions):
    """Place the links and set the priorities the plan decided on.

    Each document is its own transaction: a corpus this size will hit a bad
    file eventually, and one bad file must not roll back the thousands that
    verified cleanly.
    """
    done = {'linked': 0, 'repriced': 0, 'failed': 0}
    failures = []
    for action in actions:
        try:
            if action['link'] == 'link':
                reader.place_in_library(
                    action['doc_id'], action['original_rel'], action['target_rel'],
                    'apply-triage:' + action['doc_id'])
                done['linked'] += 1
            if action['importance'] is not None:
                with reader.transaction():
                    reader.conn.execute(
                        'UPDATE reading_runs SET priority=? WHERE doc_id=? AND base_revision_id IS NULL',
                        (action['importance'], action['doc_id']))
                done['repriced'] += 1
        except Exception as error:  # noqa: BLE001 - reported per document, never swallowed
            done['failed'] += 1
            failures.append({'doc_id': action['doc_id'],
                             'error': type(error).__name__})
    return done, failures
