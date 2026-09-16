"""Shared, non-CLI use cases for M4 L1 preview, scoring, and progress.

Callers inject model work.  This module owns selection, bounded input and
revision-aware commits; it deliberately has no argparse or terminal output.
"""
from __future__ import annotations

import re
from pathlib import Path

from inresearch.adapters import office as office_text
from inresearch.materials import triage as L1
from inresearch.materials.records import current_results

PREVIEW_CHARS = 400
OFFICE_PREVIEW_CHARS = 1200
MAX_WORKERS = 16
IDLE_GAP_SECONDS = 300.0
NOISE = re.compile(r'(HYPERLINK|PAGEREF|TOC)\s+\\?[A-Za-z]?[^ ]*|_Toc\d+|style\.visibility|ppt_[xy]|\\[hzou]\b|EMBED [A-Za-z.0-9]+')
SPREADSHEETS = {'.xlsx', '.xlsm', '.xltx', '.xls', '.et'}


def clean_preview(text: str) -> str:
    text = NOISE.sub(' ', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'(?:\s\d+\s){4,}', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def preview_budget(suffix: str) -> int:
    return OFFICE_PREVIEW_CHARS if suffix in office_text.SUPPORTED else PREVIEW_CHARS


def preview_for_model(record: dict) -> str:
    """The sole L1 model-input normalization rule."""
    return clean_preview(record['preview'])[:preview_budget(record['suffix'])]


def priority(rel: str):
    rank = {'数据中心报告购买': 0, '数据中心资料': 1, '报告': 2,
            'Global半导体研究资料': 3, '42套数据中心IDC机房楼机房2024 —2025': 5,
            '要删': 6}.get(rel.split('/')[0], 4)
    return rank, rel


def last_results() -> dict:
    return current_results(L1.RESULTS)


def opened_and_empty(row: dict) -> bool:
    meta = row.get('meta') or {}
    if not meta:
        return False
    if meta.get('no_text_layer'):
        return True
    return not meta.get('extract_error')


def blind_scored() -> set:
    return {sha for sha, row in last_results().items()
            if row.get('level') == 'n' and row.get('suffix') in office_text.SUPPORTED
            and not opened_and_empty(row)}


def judged_without_cells() -> set:
    return {sha for sha, row in last_results().items()
            if row.get('suffix') in SPREADSHEETS and 'cells' not in (row.get('meta') or {})}


def judged_without_drawings() -> set:
    return {sha for sha, row in last_results().items()
            if row.get('suffix') in SPREADSHEETS
            and 'drawing_lines' not in (row.get('meta') or {})
            and str(row.get('org') or '未知').strip() in ('', '未知')}


def nothing_new(meta: dict) -> bool:
    return meta.get('cells') == 0 and not meta.get('extract_error')


def named(prefixes: list[str]) -> set:
    rows = last_results(); picked = set(); missing = []
    for prefix in prefixes:
        hits = [sha for sha in rows if sha.startswith(prefix)]
        if len(hits) != 1:
            missing.append('%s 匹配到 %d 条判定' % (prefix, len(hits)))
        else:
            picked.add(hits[0])
    if missing:
        raise SystemExit('每个 --sha 前缀要正好匹配一条：' + '；'.join(missing))
    return picked


COHORTS = {'new': None, 'blind': blind_scored, 'cells': judged_without_cells,
           'drawings': judged_without_drawings}


def pending(cohort='new', shas=None) -> list[dict]:
    if shas:
        wanted = named(shas)
        items = [item for item in L1.load_inventory() if item['sha256'] in wanted]
    else:
        select = COHORTS[cohort]
        wanted = select() if select else None
        done = L1.done_keys() if wanted is None else None
        items = [item for item in L1.load_inventory()
                 if item['sha256'] in wanted] if wanted is not None else [
                     item for item in L1.load_inventory() if item['sha256'] not in done]
    return sorted(items, key=lambda item: priority(item['rel']))


def working_rate(stamps, idle_gap=IDLE_GAP_SECONDS):
    stamps = sorted(stamp for stamp in stamps if stamp is not None)
    if len(stamps) < 2:
        return None
    active = 0.0; counted = 0
    for before, after in zip(stamps, stamps[1:]):
        gap = after - before
        if 0 <= gap <= idle_gap:
            active += gap; counted += 1
    return counted / (active / 60) if counted and active > 0 else None


def digest_stamps(paths):
    import calendar, json, time
    out = []
    for path in paths:
        if not Path(path).exists():
            continue
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            try:
                at = json.loads(line).get('at')
                if at:
                    out.append(calendar.timegm(time.strptime(at, '%Y-%m-%dT%H:%M:%SZ')))
            except ValueError:
                continue
    return out


SIM_THRESHOLD = 0.45
GRAM = 3
COMMON_GRAM_SHARE = 0.10
COMMON_GRAM_FLOOR = 200
DATE_PREFIX = re.compile(r'^\s*(?:20\d{6}|20\d{2}[-_.]?\d{2}[-_.]?\d{2})[-_\s]*')
PAGE_TAIL = re.compile(r'[\(（]\s*\d+\s*页\s*[\)）]|[\(（]\s*(?:重复版|副本|copy|\d+)\s*[\)）]', re.I)
PUNCT = re.compile(r'[\s·・:：,，。.、\-_()（）\[\]【】/\\|"“”\'‘’&]+')


def name_key(rel: str) -> str:
    stem = Path(str(rel or '')).stem
    return PUNCT.sub('', PAGE_TAIL.sub('', DATE_PREFIX.sub('', stem))).lower()


def trigrams(text: str) -> set:
    return {text[i:i + GRAM] for i in range(len(text) - GRAM + 1)} if len(text) > GRAM else ({text} if text else set())


def similarity(left: set, right: set) -> float:
    return len(left & right) / len(left | right) if left and right else 0.0


def scored_rows():
    return [row for row in last_results().values() if row.get('status') == 'ok']


def version_groups(rows, min_score=0, threshold=SIM_THRESHOLD):
    import collections
    items = [row for row in rows if (row.get('score') or 0) >= min_score]
    grams = [trigrams(name_key(row.get('rel'))) for row in items]
    index = collections.defaultdict(list)
    for position, values in enumerate(grams):
        for gram in values: index[gram].append(position)
    cap = max(COMMON_GRAM_FLOOR, int(len(items) * COMMON_GRAM_SHARE))
    index = {gram: positions for gram, positions in index.items() if len(positions) <= cap}
    parent = list(range(len(items)))
    def find(position):
        while parent[position] != position:
            parent[position] = parent[parent[position]]; position = parent[position]
        return position
    for position, values in enumerate(grams):
        shared = collections.Counter(other for gram in values for other in index.get(gram, ()) if other > position)
        for other, count in shared.items():
            if count >= max(1, int(len(values) * threshold * .5)) and similarity(values, grams[other]) >= threshold:
                left, right = find(position), find(other)
                if left != right: parent[right] = left
    groups = collections.defaultdict(list)
    for position in range(len(items)): groups[find(position)].append(position)
    def rank(position):
        row = items[position]; meta = row.get('meta') or {}
        return (str(row.get('rel', '')).startswith('要删/'), -(meta.get('pages') or 0), -(row.get('size') or 0), row.get('rel') or '')
    return sorted(({'keep': items[sorted(members, key=rank)[0]], 'extra': [items[p] for p in sorted(members, key=rank)[1:]]}
                   for members in groups.values() if len(members) > 1), key=lambda group: -len(group['extra']))
