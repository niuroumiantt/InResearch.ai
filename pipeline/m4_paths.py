#!/usr/bin/env python3
"""Where a triage run reads, writes and keeps its books.

Defaults reproduce the original M4 run exactly, so nothing changes for a
caller that sets no environment.  Three variables redirect a run at another
corpus - a NAS share, an external disk, a second folder on the same Mac:

    INRESEARCH_SOURCE    the tree to read, never modified
    INRESEARCH_LIBRARY   where renamed originals are moved to
    INRESEARCH_DATASET   one path segment naming this corpus's ledgers

INRESEARCH_DATASET is the important one.  The inventory, the L1 results and
the move ledger all live under it, so two corpora can never share a book:
pointing a second run at a NAS while leaving the dataset name alone would
append foreign rows to the first run's inventory and make every later stage
misread it.  A slash in the name would let one corpus's ledgers nest inside
another's, so the name is required to be a single segment.
"""
from __future__ import annotations
import os
from pathlib import Path

DEFAULT_SOURCE = '/Users/m4/Downloads/所有raw materials'
DEFAULT_LIBRARY = '/Users/m4/Downloads/inresearch资料库'
DEFAULT_DATASET = 'm4-triage'


def dataset() -> str:
    name = os.environ.get('INRESEARCH_DATASET', DEFAULT_DATASET).strip()
    if not name or '/' in name or os.sep in name or name in {'.', '..'}:
        raise SystemExit(
            'INRESEARCH_DATASET must be a single path segment, got %r.\n'
            'It names this corpus\'s ledgers; a slash would nest them inside another run.' % name)
    return name


def source() -> Path:
    return Path(os.environ.get('INRESEARCH_SOURCE') or DEFAULT_SOURCE)


def library() -> Path:
    return Path(os.environ.get('INRESEARCH_LIBRARY') or DEFAULT_LIBRARY)


def data() -> Path:
    return Path.home() / '.local/share/inresearch.ai' / dataset()


def state() -> Path:
    return Path.home() / '.local/state/inresearch.ai' / dataset()


def volume_of(path: Path) -> int:
    """Device id of the nearest existing ancestor.

    The library usually does not exist yet on the first run, so resolving it
    directly would fail; its parent tells us the same thing.
    """
    p = Path(path).resolve()
    while not p.exists() and p != p.parent:
        p = p.parent
    return p.stat().st_dev


def require_same_volume(src: Path, lib: Path) -> None:
    """Moves use os.rename, which cannot cross a filesystem boundary.

    Checked once, before anything moves: otherwise every single file fails
    with EXDEV and the run writes tens of thousands of error rows to the
    ledger before anyone notices.
    """
    if volume_of(src) != volume_of(lib):
        raise SystemExit(
            'source and library are on different volumes, so os.rename cannot move between them:\n'
            '  source  %s\n  library %s\n'
            'Put the library on the same share or disk as the source.' % (src, lib))
