"""Precision-preserving evidence times; bounds are comparisons, never invented dates."""
import calendar
import re
from datetime import date, datetime, time, timezone


def precision(value):
    if value is None:
        return 'unknown'
    if not isinstance(value, str):
        raise ValueError('invalid_evidence_time')
    if re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?', value):
        try:
            date.fromisoformat(value + ('-01-01' if len(value) == 4 else '-01' if len(value) == 7 else ''))
        except ValueError as exc:
            raise ValueError('invalid_evidence_time') from exc
        return {4: 'year', 7: 'month', 10: 'day'}[len(value)]
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if 'T' not in value or stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError()
    except ValueError as exc:
        raise ValueError('invalid_evidence_time') from exc
    return 'timestamp'


def bounds(value):
    """Inclusive UTC bounds of a stated precision, without changing its stored value."""
    unit = precision(value)
    if unit == 'unknown':
        return None, None
    if unit == 'timestamp':
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
        return stamp, stamp
    start = date.fromisoformat(value + ('-01-01' if unit == 'year' else '-01' if unit == 'month' else ''))
    end = (date(start.year, 12, 31) if unit == 'year' else
           date(start.year, start.month, calendar.monthrange(start.year, start.month)[1]) if unit == 'month' else start)
    return datetime.combine(start, time.min, timezone.utc), datetime.combine(end, time.max, timezone.utc)


def validate_period(start, end=None):
    lo, _ = bounds(start)
    _, hi = bounds(end)
    if lo is not None and hi is not None and hi < lo:
        raise ValueError('reversed_observation_validity')


def definitely_after(left, right):
    lo, _ = bounds(left)
    _, hi = bounds(right)
    return lo is not None and hi is not None and lo > hi


def overlaps(left, right):
    a, b = bounds(left)
    c, d = bounds(right)
    return a is not None and c is not None and a <= d and c <= b


def day_end(today):
    return datetime.combine(date.fromisoformat(today), time.max, timezone.utc)


def certainly_past(value, today):
    _, upper = bounds(value)
    return upper is not None and upper <= day_end(today)


def native_date_matches(value, text):
    """Reproducible native ISO/English/Chinese date normalization, without guessing."""
    unit = precision(value)
    if unit == 'unknown':
        return False
    if re.search(r'(?<!\d)'+re.escape(value)+r'(?!\d)', text):
        return True
    if unit == 'timestamp':
        return False
    candidates = []
    months = {name.lower(): i for i in range(1, 13) for name in (calendar.month_name[i], calendar.month_abbr[i])}
    names = '|'.join(sorted(months, key=len, reverse=True))
    for name, day, year in re.findall(r'\b('+names+r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(\d{4})\b', text, re.I):
        candidates.append((int(year), months[name.lower()], int(day)))
    for day, name, year in re.findall(r'\b(\d{1,2})\s+('+names+r')\.?,?\s+(\d{4})\b', text, re.I):
        candidates.append((int(year), months[name.lower()], int(day)))
    candidates.extend(tuple(map(int, row)) for row in re.findall(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日', text))
    for parts in candidates:
        try:
            native = date(*parts).isoformat()
        except ValueError:
            continue
        if native[:len(value)] == value:
            return True
    return False
