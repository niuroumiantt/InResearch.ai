"""Read-only reporting for terminal material batches.

This module deliberately owns no batch files and performs no ledger writes.
"""
from __future__ import annotations

import calendar
import collections
import json
import re
import time as clock
from pathlib import Path

IDLE_GAP_SECONDS = 300.0
SIM_THRESHOLD = 0.45
GRAM = 3
COMMON_GRAM_SHARE = 0.10
COMMON_GRAM_FLOOR = 200
DATE_PREFIX = re.compile(r'^\s*(?:20\d{6}|20\d{2}[-_.]?\d{2}[-_.]?\d{2})[-_\s]*')
PAGE_TAIL = re.compile(r'[\(（]\s*\d+\s*页\s*[\)）]|[\(（]\s*(?:重复版|副本|copy|\d+)\s*[\)）]', re.I)
PUNCT = re.compile(r'[\s·・:：,，。.、\-_()（）\[\]【】/\\|"“”\'‘’&]+')


def working_rate(stamps, idle_gap=IDLE_GAP_SECONDS):
    stamps = sorted(s for s in stamps if s is not None)
    if len(stamps) < 2:
        return None
    active = 0.0
    counted = 0
    for before, after in zip(stamps, stamps[1:]):
        gap = after - before
        if 0 <= gap <= idle_gap:
            active += gap
            counted += 1
    return counted / (active / 60) if active else None


def digest_stamps(paths):
    out = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                at = json.loads(line).get('at')
                if at:
                    out.append(calendar.timegm(clock.strptime(at, '%Y-%m-%dT%H:%M:%SZ')))
            except ValueError:
                continue
    return out


def name_key(rel):
    stem = Path(str(rel or '')).stem
    return PUNCT.sub('', PAGE_TAIL.sub('', DATE_PREFIX.sub('', stem))).lower()


def trigrams(text):
    return {text[i:i + GRAM] for i in range(len(text) - GRAM + 1)} if len(text) > GRAM else ({text} if text else set())


def similarity(left, right):
    return len(left & right) / len(left | right) if left and right else 0.0


def version_groups(rows, min_score=0, threshold=SIM_THRESHOLD):
    """Group likely reissues without modifying their source records."""
    items = [row for row in rows if (row.get('score') or 0) >= min_score]
    grams = [trigrams(name_key(row.get('rel'))) for row in items]
    index = collections.defaultdict(list)
    for position, terms in enumerate(grams):
        for term in terms:
            index[term].append(position)
    cap = max(COMMON_GRAM_FLOOR, int(len(items) * COMMON_GRAM_SHARE))
    index = {term: members for term, members in index.items() if len(members) <= cap}
    parent = list(range(len(items)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(i, j):
        left, right = find(i), find(j)
        if left != right:
            parent[right] = left
    for position, terms in enumerate(grams):
        shared = collections.Counter(other for term in terms for other in index.get(term, ()) if other > position)
        for other, count in shared.items():
            if count >= max(1, int(len(terms) * threshold * .5)) and similarity(terms, grams[other]) >= threshold:
                union(position, other)
    groups = collections.defaultdict(list)
    for position in range(len(items)):
        groups[find(position)].append(position)
    def rank(position):
        row = items[position]
        return (str(row.get('rel', '')).startswith('要删/'), -((row.get('meta') or {}).get('pages') or 0), -(row.get('size') or 0), row.get('rel') or '')
    return sorted(({'keep': items[sorted(members, key=rank)[0]], 'extra': [items[m] for m in sorted(members, key=rank)[1:]]}
                   for members in groups.values() if len(members) > 1), key=lambda group: -len(group['extra']))
