"""Binary PowerPoint text atoms."""
from __future__ import annotations
import struct
from inresearch.materials.office_container import OleFile
from inresearch.materials.office_grid import MAX_CHARS, no_text_layer


TEXT_CHARS_ATOM = 0x0FA0      # UTF-16LE

TEXT_BYTES_ATOM = 0x0FA8      # one byte per char, high byte implied zero

CSTRING_ATOM = 0x0FBA         # UTF-16LE, used for titles and notes

SKIP_CONTAINERS = {
    0x03F8,   # MainMaster
    0x0FC9,   # Handout
}

def ppt_atoms(data: bytes, depth: int = 0):
    """Yield (type, payload), descending into container records."""
    pos = 0
    while pos + 8 <= len(data):
        ver_inst, rec_type, rec_len = struct.unpack_from('<HHI', data, pos)
        pos += 8
        if rec_len > len(data) - pos: break
        payload = data[pos:pos + rec_len]
        if rec_type in SKIP_CONTAINERS:
            pos += rec_len
            continue
        if (ver_inst & 0x0F) == 0x0F and depth < 12:
            yield from ppt_atoms(payload, depth + 1)
        else:
            yield rec_type, payload
        pos += rec_len

def ppt_text(raw: bytes) -> tuple[str, dict]:
    ole = OleFile(raw)
    doc = ole.stream('PowerPoint Document', 'PP97_DUALSTORAGE')
    if not doc:
        # Same permanent verdict as a Visio binary: the stream the text lives in
        # is simply not in this file, so a later re-read finds the same nothing.
        return no_text_layer('no PowerPoint Document stream')
    parts = []
    for rec_type, payload in ppt_atoms(doc):
        if rec_type == TEXT_BYTES_ATOM:
            parts.append(payload.decode('latin-1', 'ignore'))
        elif rec_type in (TEXT_CHARS_ATOM, CSTRING_ATOM):
            parts.append(payload.decode('utf-16-le', 'ignore'))
    text = '\n'.join(p.replace('\r', '\n') for p in parts if p.strip())
    return text[:MAX_CHARS], {'text_atoms': len(parts)}
