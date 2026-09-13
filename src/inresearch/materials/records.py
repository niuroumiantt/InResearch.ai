"""The M4 inventory and result read models; legacy records normalize only here."""
from pathlib import Path
import copy
import hashlib
import json
import re

from inresearch.storage.jsonl import read_rows, JsonlStore


# L0 buckets come from the adopted task card. They are provisional by
# construction: a bucket assigned from a suffix is never evidence of reading.
DRAWING = {".dwg", ".dxf", ".dwf", ".dgn", ".rvt", ".rfa", ".ifc", ".skp", ".3dm",
           ".step", ".stp", ".iges", ".igs", ".obj", ".fbx", ".max", ".blend", ".sat"}
OFFICE = {".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".pages",
          ".numbers", ".key", ".odt", ".ods", ".odp", ".rtf", ".wps", ".et", ".dps"}
TEXT = {".pdf", ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".htm", ".html"}
IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif",
         ".webp", ".svg", ".psd", ".ai", ".eps", ".raw", ".cr2", ".nef"}
ARCHIVE = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".iso"}
INSTALLER = {".dmg", ".pkg", ".exe", ".msi", ".app", ".deb", ".rpm", ".apk", ".jar"}
MEDIA = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".mp3", ".wav", ".m4a", ".aac"}
# Files the operating system writes next to real material; never research content.
NOISE_NAMES = {".ds_store", "thumbs.db", "desktop.ini", ".localized"}
PARTIAL_SUFFIXES = (".part", ".partial", ".tmp", ".crdownload", ".download", ".filepart")


def bucket(rel: str, suffix: str) -> tuple[str, str]:
    """Return (l0_bucket, route). route says which reading level comes next."""
    name = Path(rel).name.lower()
    if name in NOISE_NAMES or name.endswith(PARTIAL_SUFFIXES):
        return "_noise", "l0_name_only"
    if suffix in DRAWING:
        return "_drawings_unread", "l0_name_only"
    if suffix in OFFICE:
        return "_office_pending", "l0_name_only"
    if suffix in TEXT:
        return "text_candidate", "l1_preview"
    if suffix in IMAGE:
        return "image", "l0_name_only"
    if suffix in ARCHIVE:
        return "archive", "l0_name_only"
    if suffix in INSTALLER:
        return "installer", "l0_name_only"
    if suffix in MEDIA:
        return "media", "l0_name_only"
    return "other", "l0_name_only"


def inventory_record(row):
    rel = row.get('original_rel', row.get('rel'))
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or '..' in Path(rel).parts:
        raise ValueError('inventory_relative_path_required')
    if 'original_rel' in row and 'rel' in row and row['original_rel'] != row['rel']:
        raise ValueError('inventory_path_conflict')
    result = {key: value for key, value in row.items() if key not in {'rel', 'size'}}
    result['original_rel'] = rel
    if row.get('error'):
        result.pop('sha256', None)
        return result
    sha = row.get('sha256')
    size = row.get('size_bytes', row.get('size'))
    if not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{64}', sha):
        raise ValueError('inventory_sha256_required')
    if type(size) is not int or size < 0:
        raise ValueError('inventory_size_required')
    suffix = Path(rel).suffix.lower()
    l0, route = bucket(rel, suffix)
    return {**result, 'schema_version': 1, 'sha256': sha, 'size_bytes': size,
            'suffix': suffix, 'original_name': Path(rel).name,
            'l0_bucket': l0, 'route': route}


def load_inventory(path, strict=True):
    """Latest observation per path; old hashes remain in the append-only source."""
    current = {}
    for number, row in enumerate(read_rows(path), 1):
        try:
            row = inventory_record(row)
        except ValueError:
            if strict:
                raise
            row = {'original_rel': ':invalid-row-%d' % number, 'error': 'row_format_unrecognized'}
        current[row['original_rel']] = row
    return list(current.values())


def current_results(path):
    """One effective result per material; a failed retry cannot erase a good reading."""
    current = {}
    for row in read_rows(path):
        sha = row.get('sha256')
        if not sha:
            continue
        previous = current.get(sha, {})
        if row.get('status') in {'ok', 'l0'} or previous.get('status') not in {'ok', 'l0'}:
            current[sha] = row
    return current


def result_revision(row):
    if not row:
        return None
    return row.get('result_revision') or hashlib.sha256(
        json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


_UNSPECIFIED = object()
_result_cache = {}


def _stamp(path):
    try:
        stat = Path(path).stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
    except FileNotFoundError:
        return None


def commit_result(path, row, expected_revision=_UNSPECIFIED):
    """Append an attempt, linking successful replacements to the prior result.

    All current writers supply a captured base revision. Legacy batches without
    that token may create a first result, but cannot replace an existing success.
    """
    sha = row.get('sha256')
    if not sha:
        raise ValueError('material_identity_required')
    store = JsonlStore(path)
    with store.locked():
        # Reuse only an unchanged file snapshot. Another process's append,
        # replacement or in-place edit forces a full strict replay. Our own
        # sequential commits update the projection, avoiding N full scans for N rows.
        key = str(Path(path).resolve())
        stamp, current = _result_cache.get(key, (None, None))
        if current is None or stamp != _stamp(path):
            current = current_results(path)
        previous = current.get(sha)
        revision = result_revision(previous)
        if (expected_revision is _UNSPECIFIED and row.get('status') in {'ok', 'l0'}
                and (previous or {}).get('status') in {'ok', 'l0'}):
            raise ValueError('result_revision_conflict')
        if expected_revision is not _UNSPECIFIED and expected_revision != revision:
            raise ValueError('result_revision_conflict')
        candidate = {key: value for key, value in row.items() if key not in {'supersedes', 'result_revision'}}
        candidate['supersedes'] = revision if candidate.get('status') in {'ok', 'l0'} else None
        candidate['result_revision'] = result_revision(candidate)
        store.append(candidate)
        if candidate.get('status') in {'ok', 'l0'} or (previous or {}).get('status') not in {'ok', 'l0'}:
            current[sha] = candidate
        _result_cache[key] = (_stamp(path), current)
    return copy.deepcopy(candidate)
