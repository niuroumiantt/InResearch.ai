"""Read native source pages for a bounded claim without requiring a full reading.

This is a source adapter for the existing project-review writer and C3 gate.
It neither marks a Reader job complete nor starts another publication queue.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from inresearch.delivery.reader_export import supplied_sources
from inresearch.materials.artifacts import safe_path, read_json
from inresearch.materials.demand_bindings import resolve as resolve_requests
from inresearch.workflow.project_review_reader import _readonly, _first_received, digest
from inresearch.workflow.research_match import pages as native_pages

MAX_CONTEXT = 200_000


def prepare(root, data, selection, site_id, *, object_binding=None, initial_identity=None):
    root, data = Path(root), Path(data)
    if (not isinstance(selection, list) or not 1 <= len(selection) <= 8
            or any(not isinstance(r, dict) or set(r) != {'sha256', 'pages'} for r in selection)):
        raise ValueError('invalid_targeted_source_selection')
    projects = read_json(root/'data/projects.json')['records']
    project = next((p for p in projects if p['site_id'] == site_id), None)
    if initial_identity is not None:
        from inresearch.knowledge.site_register import check_initial_identity
        check_initial_identity(initial_identity, project)
        if object_binding is None or initial_identity['site_id'] != site_id:
            raise ValueError('initial_identity_requires_object_binding')
    elif project is None or project.get('duplicate_of') or 'portfolio' in site_id:
        raise ValueError('targeted_review_requires_registered_physical_site')
    if object_binding is not None:
        from inresearch.knowledge.site_timeline import check_object_binding
        check_object_binding(object_binding, site_id=site_id)
        if (project or {}).get('identity_scope') in ('cluster', 'portfolio'):
            raise ValueError('object_excerpt_requires_unique_physical_site')
    texts, page_map, first, refs, urls, requests, seen = {}, {}, {}, [], [], [], set()
    for selected in sorted(selection, key=lambda r: str(r['sha256'])):
        sha, requested = selected['sha256'], selected['pages']
        if (not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha) or sha in seen
                or not isinstance(requested, list) or not requested or len(requested) > 100
                or any(type(p) is not int or p < 1 for p in requested) or len(set(requested)) != len(requested)):
            raise ValueError('invalid_targeted_source_pages')
        seen.add(sha)
        with _readonly(data/'catalog/catalog.sqlite') as db:
            row = db.execute('SELECT original_rel FROM documents WHERE sha256=?', (sha,)).fetchone()
        if not row:
            raise ValueError('targeted_original_not_registered')
        original = safe_path(data, row['original_rel'])
        h = hashlib.sha256()
        with original.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                h.update(block)
        if h.hexdigest() != sha:
            raise ValueError('targeted_original_hash_changed')
        source = supplied_sources(data, sha).get(sha)
        if not source or not source.get('source_url') or not isinstance(source.get('source_provenance'), dict):
            raise ValueError('received_source_provenance_required')
        if object_binding is None and not source.get('research_requests'):
            raise ValueError('received_source_and_current_demand_binding_required')
        # A received source can describe a site without having been commissioned
        # for a model. Do not invent or rewrite the supplier's original request.
        bound = resolve_requests(source['research_requests'], root) if object_binding is None else []
        requests.extend(bound)
        # Native text preserves page context, including neighbouring qualifications
        # selected by the reviewer. Nothing is silently truncated to fit a prompt.
        extracted = native_pages(original)
        if max(requested) > len(extracted):
            raise ValueError('targeted_page_out_of_range')
        selected_pages = {p: extracted[p-1] for p in sorted(requested)}
        if any(not text.strip() for text in selected_pages.values()):
            raise ValueError('targeted_native_text_unavailable')
        texts[sha] = '\n\n'.join(selected_pages.values())
        if sum(len(text) for text in texts.values()) > MAX_CONTEXT:
            raise ValueError('targeted_context_requires_smaller_review_batch')
        page_map[sha] = selected_pages
        spans = [{'page_index': p-1, 'locator': 'excerpt:page:'+str(p),
                  'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'characters': len(text)}
                 for p, text in selected_pages.items()]
        refs.append({'source_sha256': sha, 'source_url': source['source_url'],
                     'source_provenance': source['source_provenance'], 'research_requests': bound,
                     'coverage': {'mode': 'targeted', 'complete': False, 'pages_total': len(extracted),
                                  'pages_read': len(selected_pages), 'reviewed_spans': spans}})
        urls.append(source['source_url'])
        first[sha] = _first_received(data, sha)
    seal = {'version': 1, 'site_id': site_id, 'sources': refs}
    if object_binding is not None:
        seal['object_binding'] = object_binding
    if initial_identity is not None:
        seal['initial_identity'] = initial_identity
    version = digest(seal)
    context = {'source_id': 'excerpt:'+version, 'source_version': version, 'document_refs': refs,
            'urls': sorted(set(urls)), 'source_texts': texts, 'source_pages': page_map,
            'first_received': first, 'publication_metadata': {}, 'matched_site_id': site_id,
            'bound_target_ids': sorted({r['target_id'] for r in requests}),
            'binding_origin': 'reviewed_native_pages_current_demand_not_full_reading'}
    if object_binding is not None:
        context.update(object_binding=object_binding, binding_origin='reviewed_physical_object_not_model_demand')
    return context


def resolve(root, data, proposal):
    binding = proposal.get('object_binding') if proposal.get('source_kind') == 'object_excerpt' else None
    if proposal.get('source_kind') == 'object_excerpt' and binding is None:
        raise ValueError('object_binding_required')
    context = prepare(root, data, proposal.get('targeted_sources'), proposal['project']['site_id'], object_binding=binding, initial_identity=proposal.get('initial_identity'))
    if context['source_version'] != proposal.get('source_version'):
        raise ValueError('targeted_source_or_binding_changed_since_review')
    targets = proposal.get('target_ids')
    if binding is not None and targets != []:
        raise ValueError('object_excerpt_does_not_claim_model_support')
    if binding is None and (not isinstance(targets, list) or not targets or not set(targets) <= set(context['bound_target_ids'])):
        raise ValueError('targeted_review_outside_bound_demand')
    if not proposal.get('assertions'):
        raise ValueError('targeted_source_assertions_required')
    for assertion in proposal['assertions']:
        sha, quote = assertion.get('source_sha256'), assertion.get('quote')
        locator = re.fullmatch(r'excerpt:page:([1-9][0-9]*)', str(assertion.get('locator')))
        page = context['source_pages'].get(sha, {}).get(int(locator[1])) if locator else None
        if (not isinstance(quote, str) or not quote.strip() or not page
                or ''.join(quote.split()) not in ''.join(page.split())):
            raise ValueError('targeted_quote_not_in_verified_page')
    return context


def main(argv=None):
    from inresearch.paths import project_root
    from inresearch.adapters.acquisition import data_root
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--selection', required=True, type=Path, help='JSON [{sha256,pages:[1,...]}]')
    ap.add_argument('--site', required=True)
    ap.add_argument('--fields', nargs='+', help='Object-first observation fields; no model demand prerequisite')
    ap.add_argument('--scope', default='whole_site', help='whole_site or phase:<id>')
    ap.add_argument('--data', type=Path, default=data_root())
    ap.add_argument('--output', required=True, type=Path, help='Private local review context; never commit source text')
    args = ap.parse_args(argv)
    binding = {'version': 1, 'site_id': args.site, 'fields': sorted(args.fields), 'scope': args.scope} if args.fields else None
    context = prepare(project_root(), args.data, read_json(args.selection), args.site, object_binding=binding)
    from inresearch.storage.files import write_json
    write_json(args.output, context)
    print(json.dumps({'source_id': context['source_id'], 'sources': len(context['document_refs']),
                      'characters': sum(map(len, context['source_texts'].values())),
                      'full_reading_complete': False}, ensure_ascii=False))
