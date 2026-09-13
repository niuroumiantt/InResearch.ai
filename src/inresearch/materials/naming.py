"""Material naming policy; pure functions, no filesystem mutations."""
from __future__ import annotations
import re
from pathlib import Path

def clean(s: str, n: int) -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', ' ', s or '').strip(' ._-')
    s = re.sub(r'\s+', ' ', s)
    return (s[:n]).strip(' ._-') or '未知'

MAX_SEGMENT = 60

MAX_DIR_CHARS = 200

MAX_NAME_BYTES = 200      # macOS allows 255 per component; leave headroom

def clean_segment(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', ' ', s or '').strip(' ._-')
    return re.sub(r'\s+', ' ', s)[:MAX_SEGMENT].strip(' ._-')

def source_dir(rel: str) -> str:
    """The source folders a file sat in, cleaned segment by segment.

    An unread file's own name is often not enough to identify it: a drawing
    called 一层平面图.dwg means nothing once it is separated from the project
    folder naming the city it belongs to, and a flat bucket would put every
    project's copy of that name side by side.  So unread files keep their tree.

    A path too long for the filesystem drops segments from the middle, where
    the least identifying ones live, and leaves a marker so the elision is
    visible rather than silent.
    """
    parts = [p for p in (clean_segment(x) for x in Path(rel).parent.parts) if p]
    if not parts:
        return ''
    width = lambda ps: sum(len(x) + 1 for x in ps)
    if len(parts) <= 4 or width(parts) <= MAX_DIR_CHARS:
        return '/'.join(parts)
    # Keep the outermost folder, which says which collection this came from,
    # and the innermost ones, which say which project and which subfolder.
    # Drop from between them, shrinking the tail until it fits - never by
    # removing segments in place, which can loop forever once the marker
    # itself lands on the position being removed.
    head, tail = parts[:1], parts[-3:]
    while len(tail) > 1 and width(head + ['__'] + tail) > MAX_DIR_CHARS:
        tail = tail[1:]
    return '/'.join(head + ['__'] + tail)

def fit_bytes(s: str, budget: int) -> str:
    """Trim to a byte budget without splitting a character."""
    if budget <= 0:
        return ''
    raw = s.encode('utf-8')
    if len(raw) <= budget:
        return s
    return raw[:budget].decode('utf-8', 'ignore').strip(' ._-')

DATE_PREFIX = re.compile(r'^((?:19|20)\d{2}(?:[.\-年]\d{1,2})?)[.\s]*(.*)$')

def split_date_prefix(tag: str) -> tuple[str, str]:
    match = DATE_PREFIX.match(tag)
    return (match.group(1), match.group(2).strip()) if match else ('', tag)

YEAR = re.compile(r'(?:19|20)\d{2}')

def pick_project(parts: list[str]) -> str:
    """The folder that names the job.

    Position is not a reliable guide.  One collection puts the project
    directly under its root; another buries it under a numbered section, so
    taking "the second segment" picks 01 解决方案(1) and drops
    2019中国移动定制化IDC解决方案 entirely.  A four-digit year is what
    actually marks a project folder here; failing that the longest
    non-innermost segment wins, since generic section names are short.
    """
    dated = [p for p in parts if YEAR.search(p)]
    if dated:
        return max(dated, key=len)
    outer = parts[:-2] or parts[:1]
    return max(outer, key=len) if outer else ''

def context_tags(rel: str, stem: str) -> list[str]:
    """Folders that identify a file whose own name does not.

    Keeping the source tree is not enough on its own: the moment a drawing is
    mailed or copied out of it, WPJW2.dwg is anonymous again.  So the folders
    that carry the identity travel in the name too - the project, just inside
    the collection root, plus the innermost two, which say which building and
    which drawing set.

    A folder already spelled out in the filename is skipped, so a file that
    was named well to begin with is not made to repeat itself.
    """
    parts = [p for p in (clean_segment(x) for x in Path(rel).parent.parts) if p]
    picks = [pick_project(parts)] + parts[-2:]
    tags = []
    for part in picks:
        # Project folders are usually dated - "2019.7 中国移动南方基地二期工程".
        # When the filename already spells the project out, the date is the
        # only part still worth carrying, or the name says everything twice.
        stamp, rest = split_date_prefix(part)
        if rest and rest in stem:
            part = stamp
        if not part or part in tags or part in stem:
            continue
        tags.append(part)
    return tags

def unread_name(out: dict) -> str:
    """Name for a file nothing has read: the folders that identify it, then it."""
    stem = clean(Path(out['rel']).stem, 90)
    tail = '__%s%s' % (out['sha256'][:16], out['suffix'])
    budget = MAX_NAME_BYTES - len('__n_') - len(tail.encode('utf-8'))
    # The original name keeps a reserved slice; the folder context takes what
    # is left, so a long project name can never squeeze the filename out.
    reserved = min(len(stem.encode('utf-8')), 80)
    context = fit_bytes('_'.join(context_tags(out['rel'], stem)), budget - reserved - 1)
    stem = fit_bytes(stem, budget - len(context.encode('utf-8')) - 1)
    return '__n_%s%s%s' % (context + '_' if context else '', stem, tail)

def proposed_name(out: dict) -> str:
    """Filename per task card §6.  Computed for review only; nothing is renamed here."""
    stem = Path(out['rel']).stem
    if out.get('status') != 'ok':
        name = unread_name(out)
        parent = source_dir(out['rel'])
        return f'{parent}/{name}' if parent else name
    score = '%02d' % out['score'] if out['score_status'] != 'provisional_name_only' else '__'
    level = out['level']
    title = clean(stem, 55) if out.get('keep_original_name') else clean(out.get('title', ''), 55)
    return f"{score}{level}_{clean(out.get('year','未知'), 8)}_{clean(out.get('org','未知'), 25)}_{title}__{out['sha256'][:16]}{out['suffix']}"
