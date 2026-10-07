#!/usr/bin/env python3
"""Export native PDF text without OCR; preserve page/source identities and images.

Standalone: python3 pdf_text.py INPUT --output OUTPUT
Requires Poppler's pdfinfo, pdftotext and pdfimages; Python standard library only.
Exported text is extraction, not completed research or formal adoption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


def command(args, timeout=120):
    result = subprocess.run(args, capture_output=True, timeout=timeout, check=True)
    return result.stdout.decode('utf-8', errors='strict')


def extract_pdf(source, run=command):
    """Return all native page strings and metadata, never invoke a vision model."""
    info = run(['pdfinfo', str(source)], timeout=60)
    match = re.search(r'^Pages:\s*(\d+)\s*$', info, re.M)
    if not match or not 0 < int(match.group(1)) <= 10000:
        raise ValueError('pdf_page_count_unavailable_or_excessive')
    count = int(match.group(1))
    text = run(['pdftotext', '-layout', '-enc', 'UTF-8', str(source), '-'], timeout=120)
    pages = text.split('\f')
    if pages and pages[-1] == '':
        pages.pop()
    if len(pages) != count:
        raise ValueError('pdf_native_page_count_mismatch')
    image_info = run(['pdfimages', '-list', str(source)], timeout=60)
    images, large = set(), set()
    for line in image_info.splitlines():
        parts = line.split()
        if len(parts) >= 5 and all(parts[i].isdigit() for i in (0, 3, 4)):
            page = int(parts[0])
            if not 1 <= page <= count:
                raise ValueError('pdf_image_page_out_of_range')
            images.add(page)
            if min(int(parts[3]), int(parts[4])) >= 400:
                large.add(page)
    return pages, {
        'pages_total': count, 'scope': 'pdf_native_text_only', 'ocr_calls': 0,
        'visual_review_performed': False, 'image_pages': sorted(images),
        'large_image_pages': sorted(large),
        'text_layer_empty_pages': [i for i, p in enumerate(pages, 1) if not p.strip()],
        'replacement_character_pages': [i for i, p in enumerate(pages, 1) if '\ufffd' in p],
        'nul_character_pages': [i for i, p in enumerate(pages, 1) if '\0' in p],
        'native_text_characters': sum(map(len, pages)),
        'warning': 'Native text only. All visual content is excluded; image listing does not detect vector figures. '
                   'No-text pages may contain scanned text or figures; they are not certified blank.',
    }


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('output_symlink_refused')
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
        temporary = stream.name
    os.replace(temporary, path)


def export_file(source, relative, output):
    before = source.stat()
    sha = digest(source)
    pages, meta = extract_pdf(source)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or digest(source) != sha:
        raise ValueError('source_changed_during_extraction')
    stem = source.stem
    while len(stem.encode('utf-8')) > 180:
        stem = stem[:-1]
    target = output / relative.parent / (stem + '--' + sha[:12] + '.txt')
    body = ('Source: %s\nSHA-256: %s\nScope: native PDF text only; images skipped; OCR calls: 0\n\n'
            % (relative.as_posix(), sha))
    body += '\n\n'.join('=== PAGE %d / %d ===\n%s' % (i, len(pages), text)
                          for i, text in enumerate(pages, 1))
    payload = body.encode('utf-8')
    record = {**meta, 'source_path': str(source), 'source_relative': relative.as_posix(),
              'source_sha256': sha, 'source_bytes': before.st_size,
              'text_relative': target.relative_to(output).as_posix(),
              'text_sha256': hashlib.sha256(payload).hexdigest(), 'text_bytes': len(payload),
              'page_text_sha256': [hashlib.sha256(p.encode('utf-8')).hexdigest() for p in pages],
              'status': 'native_text_extracted' if any(p.strip() for p in pages) else 'no_extractable_native_text',
              'acceptance': 'extraction_only_not_read_or_adopted'}
    atomic(target, payload)
    atomic(target.with_suffix('.metadata.json'), (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode())
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='PDF file or directory (recursive)')
    parser.add_argument('--output', type=Path, required=True, help='Separate derived output directory')
    args = parser.parse_args(argv)
    for name in ('pdfinfo', 'pdftotext', 'pdfimages'):
        if not shutil.which(name):
            parser.error('missing Poppler tool: ' + name)
    source, output = args.input.expanduser().resolve(), args.output.expanduser().resolve()
    if not source.exists():
        parser.error('input does not exist')
    if source.is_dir() and (output == source or source in output.parents):
        parser.error('output must be separate from the original directory')
    files = [source] if source.is_file() and source.suffix.lower() == '.pdf' else (
        sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() == '.pdf') if source.is_dir() else [])
    if not files:
        parser.error('no PDF files found')
    start = time.monotonic()
    records, errors = [], []
    for path in files:
        relative = path.relative_to(source) if source.is_dir() else Path(path.name)
        try:
            records.append(export_file(path, relative, output))
        except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as exc:
            errors.append({'source_relative': relative.as_posix(), 'error': str(exc)[:600]})
    summary = {'files': len(files), 'exported': len(records), 'errors': len(errors),
               'pages': sum(r['pages_total'] for r in records),
               'text_layer_nonempty_pages': sum(r['pages_total'] - len(r['text_layer_empty_pages']) for r in records),
               'text_layer_empty_pages': sum(len(r['text_layer_empty_pages']) for r in records),
               'large_image_pages': sum(len(r['large_image_pages']) for r in records),
               'native_text_characters': sum(r['native_text_characters'] for r in records),
               'source_bytes': sum(r['source_bytes'] for r in records),
               'text_bytes': sum(r['text_bytes'] for r in records),
               'seconds': round(time.monotonic() - start, 3), 'ocr_calls': 0,
               'scope': 'pdf_native_text_only', 'acceptance': 'extraction_only_not_read_or_adopted'}
    atomic(output / 'manifest.json', (json.dumps({'summary': summary, 'records': records, 'errors': errors},
                                               ensure_ascii=False, indent=2) + '\n').encode())
    atomic(output / 'summary.txt', (json.dumps(summary, ensure_ascii=False, indent=2) + '\n').encode())
    print(json.dumps({'output': str(output), **summary}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
