"""Text similarity is an advisory observation, never material identity or adoption."""
from __future__ import annotations
import hashlib
import re
import time
from pathlib import Path
from inresearch.storage.jsonl import read_rows, append_record
MIN_FINGERPRINT_CHARS = 500
SKETCH_SIZE = 64
CHUNK_BITS = 0xFF
NEAR_TWIN_RATIO = 0.8
GEAR = [(i * 0x9E3779B1) & 0xFFFFFFFF for i in range(256)]


def text_fingerprint(text: str, meta: dict) -> str | None:
    """Whitespace-insensitive extracted-text hash; excludes short covers."""
    body = re.sub(r'\s+', '', text)
    if len(body) < MIN_FINGERPRINT_CHARS:
        return None
    pages = (meta or {}).get('pages') or 0
    return hashlib.md5(('%s\x00%s' % (pages, body)).encode('utf-8')).hexdigest()


def text_sketch(text: str) -> list[str]:
    """Bottom-k content-defined chunk hashes; excludes short covers."""
    body = re.sub(r'\s+', '', text)
    if len(body) < MIN_FINGERPRINT_CHARS:
        return []
    data = body.encode('utf-8')
    hashes, start, h = set(), 0, 0
    for i, byte in enumerate(data):
        h = ((h << 1) + GEAR[byte]) & 0xFFFFFFFF
        if not h & CHUNK_BITS and i - start >= 64:
            hashes.add(hashlib.md5(data[start:i + 1]).hexdigest()[:12])
            start, h = i + 1, 0
    if start < len(data):
        hashes.add(hashlib.md5(data[start:]).hexdigest()[:12])
    return sorted(hashes)[:SKETCH_SIZE]


def sketch_overlap(a: list[str], b: list[str]) -> float:
    """Jaccard estimate from the smallest hashes in the union sample."""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    k = min(len(a), len(b), SKETCH_SIZE)
    sample = sorted(sa | sb)[:k]
    if not sample:
        return 0.0
    return sum(1 for h in sample if h in sa and h in sb) / len(sample)


class SimilarityIndex:
    def __init__(self, path):
        self.path = Path(path)

    def fingerprints(self):
        return {r['sha256']: r['text_md5'] for r in read_rows(self.path)
                if r.get('sha256') and r.get('text_md5')}

    def sketches(self):
        return {r['sha256']: r['sketch'] for r in read_rows(self.path)
                if r.get('sha256') and r.get('sketch')}

    def unsketched(self):
        """记了指纹却没记 sketch 的那些文件。

        sketch 是后加的：更早入库的精读只留下 text_md5。这些文件在近似副本比对里
        **根本不参与**——不是「比过了、不像」，是压根没被比。而 near_twins 返回空
        列表时读起来正好像前者，于是 6b1a9d03 与 d01da12707d7（54,397 对 54,905 字，
        只差约 500 字）一声不响地各录了一遍。
        沉默的盲区比报错更贵，所以把它数出来，让调用方能说「没比到」而不是「不像」。
        """
        sketched, seen = set(), set()
        for row in read_rows(self.path):
            sha = row.get('sha256')
            if not sha:
                continue
            seen.add(sha)
            if row.get('sketch'):
                sketched.add(sha)
        return seen - sketched

    def remember(self, sha, fingerprint, sketch=None):
        append_record(self.path, {'sha256': sha, 'text_md5': fingerprint,
                      'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      **({'sketch': sketch} if sketch else {})})

    def same_text(self, sha, fingerprint, done, *, processed):
        return sorted(other for other, value in self.fingerprints().items()
                      if fingerprint and value == fingerprint and other != sha
                      and (other in done) == processed)

    def near_twins(self, sha, sketch, done):
        if not sketch:
            return []
        rows = []
        for other, value in self.sketches().items():
            ratio = sketch_overlap(sketch, value)
            if other != sha and ratio >= NEAR_TWIN_RATIO:
                rows.append({'sha256': other, 'shared': round(ratio, 3), 'processed': other in done})
        return sorted(rows, key=lambda row: (-row['shared'], row['sha256']))
