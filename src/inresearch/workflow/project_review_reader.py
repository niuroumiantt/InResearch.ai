"""Reuse sealed Reader sources for explicit site review, without a news receipt.

The current source-to-demand binding is separate from the immutable reading
recipe. Reusing text does not imply that an old report answered a new request.
"""
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from inresearch.delivery.reader_export import supplied_sources
from inresearch.materials.artifacts import safe_path, read_json
from inresearch.materials.demand_bindings import resolve as resolve_requests
from inresearch.workflow.reading_results import ReadingResults
from inresearch.knowledge import observation_time


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@contextmanager
def _readonly(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError('reader_source_catalog_missing')
    db = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def _first_received(data, sha):
    """Earliest recorded archive receipt; never infer original publication time."""
    candidates = []
    path = data/'acquisition/catalog.sqlite'
    if path.is_file() and not path.is_symlink():
        with _readonly(path) as db:
            rows = db.execute('SELECT observed_at FROM observations WHERE sha256=?', (sha,)).fetchall()
        for row in rows:
            try:
                if observation_time.precision(row[0]) == 'timestamp':
                    candidates.append((observation_time.bounds(row[0])[0], row[0],
                                       'acquisition_first_recorded_archive_receipt'))
            except ValueError:
                continue
    with _readonly(data/'catalog/catalog.sqlite') as db:
        row = db.execute('SELECT MIN(received) FROM sources WHERE doc_id=?', ('doc-'+sha,)).fetchone()
    if row and row[0] is not None:
        stamp = datetime.fromtimestamp(row[0], timezone.utc)
        candidates.append((stamp, stamp.isoformat(), 'reader_first_recorded_intake_receipt'))
    if candidates:
        _, stamp, origin = min(candidates, key=lambda item: item[0])
        return {'at': stamp, 'provenance': origin}
    return {'at': None, 'provenance': 'unknown_no_recorded_receipt'}


def prepare(root, data, shas, site_id):
    """Read-only review context. No model calls, queue edits or formal writes."""
    root, data = Path(root), Path(data)
    if (not isinstance(shas, list) or not 1 <= len(shas) <= 8 or len(set(shas)) != len(shas)
            or any(not isinstance(s, str) or not re.fullmatch('[0-9a-f]{64}', s) for s in shas)):
        raise ValueError('invalid_reader_source_set')
    projects = read_json(root/'data/projects.json')['records']
    if not any(p['site_id'] == site_id and not p.get('duplicate_of') and 'portfolio' not in site_id for p in projects):
        raise ValueError('reader_review_requires_registered_physical_site')
    refs, urls, texts, pages, first, publication, requests = [], [], {}, {}, {}, {}, []
    reader = ReadingResults(data)
    for sha in sorted(shas):
        current = reader.current(sha, include_text=True)
        if current['status'] != 'available' or current['report'].get('coverage', {}).get('complete') is not True:
            raise ValueError('complete_sealed_reader_source_required')
        source = supplied_sources(data, sha).get(sha)
        if not source or not source.get('source_url') or not source.get('research_requests'):
            raise ValueError('received_source_and_current_demand_binding_required')
        bound = resolve_requests(source['research_requests'], root)
        requests.extend(bound)
        with _readonly(data/'catalog/catalog.sqlite') as db:
            row = db.execute('SELECT * FROM current_readings WHERE sha256=?', (sha,)).fetchone()
        if (not row or row['revision_id'] != current['reading_revision_id']
                or row['report_sha256'] != current['report_sha256']):
            raise ValueError('reader_source_changed_during_review')
        extraction = read_json(safe_path(data, row['artifact_rel']+'/extraction.json'))
        source_pages = {}
        gaps = current['report']['coverage'].get('gap_pages', [])
        for chunk in extraction['chunks']:
            text = safe_path(data, chunk['text_rel']).read_text(encoding='utf-8')
            if hashlib.sha256(text.encode()).hexdigest() != chunk['sha256']:
                raise ValueError('reader_source_text_changed')
            if chunk['page_index'] not in gaps:
                source_pages[chunk['page_index']] = source_pages.get(chunk['page_index'], '')+text
        pages[sha] = source_pages
        texts[sha] = current['text']
        first[sha] = _first_received(data, sha)
        # A model classification date is not a verified disclosure timestamp.
        publication[sha] = {'published_at': None, 'provenance': 'unknown_until_native_date_review'}
        refs.append({'source_sha256': sha, 'reading_revision_id': current['reading_revision_id'],
                     'report_sha256': current['report_sha256'], 'source_url': source['source_url'],
                     'source_provenance': source['source_provenance'], 'research_requests': bound})
        if source['source_url'] not in urls:
            urls.append(source['source_url'])
    identity = {'version': 1, 'site_id': site_id, 'sources': refs}
    version = digest(identity)
    return {'source_id': 'reader:'+version, 'source_version': version, 'document_refs': refs,
            'urls': urls, 'source_texts': texts, 'source_pages': pages, 'first_received': first,
            'publication_metadata': publication, 'matched_site_id': site_id,
            'bound_target_ids': sorted({r['target_id'] for r in requests}),
            'binding_origin': 'current_received_source_metadata_not_rewritten_reading_recipe'}


def resolve(root, data, proposal):
    refs = proposal.get('reader_sources')
    if not isinstance(refs, list) or not refs or any(not isinstance(r, dict) or set(r) != {
            'source_sha256', 'reading_revision_id', 'report_sha256'} for r in refs):
        raise ValueError('invalid_reader_review_references')
    context = prepare(root, data, [r['source_sha256'] for r in refs], proposal['project']['site_id'])
    expected = [{k: r[k] for k in ('source_sha256', 'reading_revision_id', 'report_sha256')}
                for r in context['document_refs']]
    if sorted(refs, key=lambda r: r['source_sha256']) != expected:
        raise ValueError('reader_revision_or_report_changed')
    if proposal.get('source_version') != context['source_version']:
        raise ValueError('reader_source_or_binding_changed_since_review')
    targets = proposal.get('target_ids')
    if not isinstance(targets, list) or not targets or not set(targets) <= set(context['bound_target_ids']):
        raise ValueError('reader_review_outside_bound_demand')
    assertions = proposal.get('assertions')
    if not isinstance(assertions, list) or not assertions:
        raise ValueError('reader_source_assertions_required')
    for assertion in assertions:
        sha = assertion.get('source_sha256')
        locator = re.fullmatch(r'reader:page:([1-9][0-9]*)', str(assertion.get('locator')))
        quote = assertion.get('quote')
        if (not locator or sha not in context['source_pages'] or not isinstance(quote, str) or not quote.strip()
                or ''.join(quote.split()) not in ''.join(context['source_pages'][sha].get(int(locator[1]), '').split())):
            raise ValueError('reader_quote_not_in_verified_page')
    return context
