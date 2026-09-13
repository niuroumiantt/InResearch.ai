"""Immutable material artifacts: identity, safe paths, encoding and chunks."""
from __future__ import annotations
from contextlib import contextmanager
import json, os, re, hashlib
from pathlib import Path
from datetime import datetime, timezone
from inresearch.materials.reader_contracts import UnsafePath, ModelOutputError, PARTIAL_SUFFIXES

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def encoded(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, allow_nan=False)

def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()

def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise UnsafePath()
    return path

def safe_path(root, relative, leaf_link=False):
    """No traversal or symlink parents. A managed library leaf may itself be a link."""
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or "\\" in str(relative) or "\0" in str(relative):
        raise UnsafePath()
    root = root.resolve()
    path = root / rel
    for parent in [path.parent, *path.parent.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise UnsafePath()
    try:
        path.parent.resolve().relative_to(root)
    except ValueError:
        raise UnsafePath()
    if path.is_symlink() and not leaf_link:
        raise UnsafePath()
    return path

def atomic_bytes(path, data):
    from inresearch.storage.files import atomic_write
    private_dir(path.parent)
    if path.is_symlink():
        raise UnsafePath()
    atomic_write(path, data)

def atomic_json(path, obj):
    atomic_bytes(path, (encoded(obj) + "\n").encode("utf-8"))

def durable_rename(source, target):
    if target.exists() or target.is_symlink():
        raise UnsafePath()
    os.rename(str(source), str(target))
    for parent in {source.parent, target.parent}:
        fd = os.open(str(parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def clean_name(value, limit=55):
    out = re.sub(r"[\x00-\x1f\x7f/\\:*?\"<>|]", "_", str(value or "")).strip(" .")
    out = out[:limit]
    while len(out.encode("utf-8")) > 180:
        out = out[:-1]
    return out or "未知"

def signature(path):
    s = os.stat(str(path), follow_symlinks=False)
    return encoded([s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns])

def is_partial(relative):
    return any(p.startswith((".", "~$")) or p.lower().endswith(PARTIAL_SUFFIXES)
               for p in Path(relative).parts)

def split_text(text, max_chars=6000, max_bytes=12000):
    """Lossless bounded chunks, preserving every character and original page order."""
    while text:
        hi = min(len(text), max_chars)
        while len(text[:hi].encode("utf-8")) > max_bytes:
            hi = max(1, hi // 2)
        if hi < len(text):
            boundary = text.rfind("\n", hi // 2, hi)
            if boundary >= 0:
                hi = boundary + 1
        yield text[:hi]
        text = text[hi:]

def require_text(value, max_chars=2000, empty=False):
    if not isinstance(value, str) or len(value) > max_chars or (not empty and not value.strip()):
        raise ModelOutputError()
    return value


def numeric_tokens(text):
    """Exact numeric tokens for OCR pass agreement, not an accuracy certificate."""
    return set(re.findall(r"[-−]?\d[\d,]*(?:\.\d+)?%?", text))


@contextmanager
def verified_content(path, expected_sha):
    """Bind extraction to the inventoried bytes; changed files need a new inventory."""
    before = signature(path)
    if digest_file(path) != expected_sha or signature(path) != before:
        raise ValueError('material_content_changed_refresh_inventory')
    yield
    if signature(path) != before:
        raise ValueError('material_content_changed_during_read')
