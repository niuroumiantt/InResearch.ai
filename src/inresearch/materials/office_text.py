#!/usr/bin/env python3
"""Text out of Office formats the preview stage could not open, stdlib only.

The L1 pass scored 4,789 files having seen nothing but their filename, because
.xlsx / .xls / .ppt were routed to _office_pending and never opened.  That is
how a Dell'Oro capex workbook - eleven sheets of forecast data - scored 8 while
its prose summary PDF scored 9.

No third-party parser is used: the machine doing the triage has no libreoffice
and no python-xlrd, and asking a user to install a toolchain to read their own
files is not an acceptable step in this pipeline.

Two container families are handled, chosen by magic bytes rather than suffix,
because .et / .wps / .dps are written as either one depending on the version
that saved them:

  PK\\x03\\x04           OOXML zip     .xlsx .xlsm .vsdx and their WPS twins
  \\xd0\\xcf\\x11\\xe0   OLE2 / CFBF   .xls .ppt and their WPS twins

Everything here is defensive: a malformed file returns whatever text was
recovered before the parse went wrong, never an exception.
"""
from __future__ import annotations
from inresearch.materials.office_container import OLE_MAGIC, OleFile
from inresearch.materials.office_grid import MAX_CHARS, no_text_layer
from inresearch.materials.office_biff import xls_text
from inresearch.materials.office_ppt import ppt_text
from inresearch.materials.office_ooxml import ooxml_text

from pathlib import Path

ZIP_MAGIC = b'PK\x03\x04'


SUPPORTED = {'.xlsx', '.xlsm', '.xltx', '.xls', '.ppt', '.et', '.wps', '.dps', '.vsdx', '.vsd'}


def extract(path: Path, limit: int = MAX_CHARS) -> tuple[str, dict]:
    """(text, meta) for one Office file.  Never raises.

    `limit` is the character budget.  L1 judges from a preview and the default
    is plenty; L2 reads the document to record numbers out of it and asks for
    far more, because a workbook silently cut at twenty thousand characters is
    read as though its last surviving row were its last row.
    """
    try:
        with open(path, 'rb') as fh:
            head = fh.read(8)
        if head.startswith(ZIP_MAGIC):
            return ooxml_text(path, limit)
        if head.startswith(OLE_MAGIC):
            raw = Path(path).read_bytes()
            ole = OleFile(raw)
            names = {e['name'].lower() for e in ole.dir_entries if e['type'] == 2}
            if 'workbook' in names or 'book' in names:
                return xls_text(raw, limit)
            if 'powerpoint document' in names:
                return ppt_text(raw)
            # A Visio binary carries no text stream at all.  Callers decide
            # whether to re-read a file later, and that decision must not rest
            # on matching the prose below - hence the flag.
            return no_text_layer(
                'OLE2 with no known stream: ' + ','.join(sorted(names))[:80])
        return '', {'extract_error': 'unrecognised container'}
    except Exception as exc:
        return '', {'extract_error': type(exc).__name__ + ': ' + str(exc)[:120]}
