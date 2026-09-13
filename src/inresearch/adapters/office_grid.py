"""Addressable spreadsheet cells and date formatting."""
from __future__ import annotations
import datetime, re


MAX_CHARS = 20000          # far above the 6000 the model is shown; trimmed later

def no_text_layer(reason: str) -> tuple[str, dict]:
    """The container opened fine but holds no text stream, and never will.

    Callers use the flag to drop a file out of the re-read queue.  It exists
    as one helper rather than a literal at each exit because forgetting it
    reads as a transient failure: the file goes back in the queue, comes out
    identical, and goes back again.  A 37 MB .ppt did exactly that until
    somebody noticed the queue would not drain.
    """
    return '', {'no_text_layer': True, 'extract_error': reason}

COL_REF = re.compile(r'^([A-Z]+)')

DATE_FMT_IDS = set(range(14, 23)) | set(range(45, 48)) | {27, 28, 29, 30, 31,
                                                          32, 33, 34, 35, 36,
                                                          50, 51, 52, 53, 54,
                                                          55, 56, 57, 58}

DATE_CODE = re.compile(r'(?<!\\)[ymdhs]', re.I)

EPOCH = datetime.date(1899, 12, 30)      # 1900-system, Excel's phantom leap day

def col_index(ref: str) -> int:
    """'A' -> 0, 'AB' -> 27.  Anything unparseable lands in column 0."""
    m = COL_REF.match(ref or '')
    n = 0
    for ch in (m.group(1) if m else ''):
        n = n * 26 + (ord(ch) - 64)
    return max(n - 1, 0)

def is_date_format(code: str | None, fmt_id: int) -> bool:
    if code:
        # Strip the literal text sections a format may carry: "元" in
        # 0.00"元" must not be read as a date code.
        bare = re.sub(r'"[^"]*"|\[[^\]]*\]', '', code)
        return bool(DATE_CODE.search(bare))
    return fmt_id in DATE_FMT_IDS

def serial_to_iso(value: float) -> str | None:
    """Excel serial -> ISO date, or None when the number is not plausibly one.

    Serials at or below 60 straddle Excel's phantom 1900-02-29; converting them
    would be wrong by a day, so they stay numbers.
    """
    if not (61 <= value < 80000):
        return None
    try:
        day = EPOCH + datetime.timedelta(days=int(value))
    except (OverflowError, ValueError):
        return None
    frac = value - int(value)
    if frac > 1e-6:
        secs = int(round(frac * 86400))
        return '%s %02d:%02d' % (day.isoformat(), secs // 3600, (secs // 60) % 60)
    return day.isoformat()

def number_text(value: float, dated: bool) -> str:
    if dated:
        iso = serial_to_iso(value)
        if iso:
            return iso
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    # Repr of a float read back from 8 bytes carries the binary noise Excel
    # never showed anyone (0.5800000000000001).  Twelve digits is past any
    # precision these documents claim and short of inventing any.
    return repr(round(value, 12))

def grid_text(sheets: list[tuple[str, dict]], limit: int = MAX_CHARS) -> tuple[str, dict]:
    """Render [(sheet name, {(row, col): text})] as tab-separated rows.

    Empty cells are kept as empty fields so the columns still line up: a value
    that has drifted one column left of its header is a different claim.

    The only cap is the character budget, and when it bites the caller is told
    so - a reader who believes they saw the whole sheet will report the last
    row they were given as the last row there is.
    """
    out, rows_out, cells_out, truncated = [], 0, 0, False
    total = 0
    for name, cells in sheets:
        if not cells:
            continue
        out.append('== 工作表: %s ==' % name)
        total += len(out[-1]) + 1
        numbers = sorted({r for r, _ in cells})
        for r in numbers:
            if total > limit:
                truncated = True
                break
            width = max(c for rr, c in cells if rr == r) + 1
            line = '%d\t%s' % (r, '\t'.join(cells.get((r, c), '') for c in range(width)))
            out.append(line.rstrip('\t'))
            rows_out += 1
            cells_out += sum(1 for c in range(width) if (r, c) in cells)
            total += len(line) + 1
    return '\n'.join(out), {'rows': rows_out, 'cells': cells_out,
                            'truncated': truncated or total > limit}
