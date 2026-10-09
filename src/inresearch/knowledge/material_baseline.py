"""Use received source material immediately, without another model/review queue.

This is a rebuildable view of current Reader results. It never writes curated
facts, closes questions, calculates capacity or grants an adoption status.
"""
from collections import Counter
from functools import lru_cache
from pathlib import Path
import os
import re

from inresearch.knowledge import registry
from inresearch.knowledge.industry import public_url
from inresearch.storage.layout import workspace_path


def rows(knowledge, curated):
    documents = {d['id']: d for d in knowledge.get('documents', [])}
    evidence = {e['id']: e for e in knowledge.get('evidence', [])}
    adopted = {cid for s in curated.get('statements', [])
               if registry.supported_adoption(s, curated)
               for cid in s.get('source_candidate_ids', [])}
    results, skipped = [], Counter()
    for s in knowledge.get('statements', []):
        if s.get('status') != 'candidate' or s['id'] in adopted:
            continue
        doc = documents.get(s.get('document_id'), {})
        if (doc.get('read_status') != 'complete' or not registry.coverage_complete(doc)
                or not re.fullmatch('[0-9a-f]{64}', doc.get('report_sha256') or '')):
            skipped['reading_or_identity'] += 1
            continue
        if not (s.get('object_ids') or s.get('question_ids')):
            skipped['mapping'] += 1
            continue
        refs = [evidence.get(eid) for eid in s.get('evidence_ids', [])]
        gaps = doc.get('coverage', {}).get('gap_pages', [])
        if (not refs or any(not e or e.get('document_id') != doc['id']
                or not isinstance(e.get('quote'), str) or not e['quote'].strip()
                or registry.evidence_errors(e, doc)
                or (type(e.get('page_index')) is int and e['page_index'] + 1 in gaps)
                for e in refs)):
            skipped['original_quote'] += 1
            continue
        if not isinstance(s.get('text'), str) or not s['text'].strip():
            skipped['empty_statement'] += 1
            continue
        # Dates remain source metadata, never file timestamps or a guessed year.
        period = next((value for value in (s.get('as_of'), s.get('published_date'), doc.get('published_date'))
                       if isinstance(value, str) and value.strip()), None)
        results.append({k: s[k] for k in ('id', 'text', 'kind', 'object_ids', 'question_ids') if k in s}
            | {'status': 'source_material', 'source_date': period,
               'source': {'id': doc['id'], 'title': doc.get('title'),
                   'content_sha256': doc['content_sha256'],
                   'reading_revision_id': doc.get('reading_revision_id'),
                   'url': public_url(doc.get('source_url')), 'coverage_scope': doc['coverage'].get('scope')},
               'quotes': [{k: e[k] for k in ('id', 'quote', 'page_index', 'locator') if k in e} for e in refs]})
        if doc.get('source_provenance'):
            results[-1]['source']['provenance'] = doc['source_provenance']
    return results, dict(skipped)


def input_version(root):
    paths = [root / 'framework/research_graph.json', root / 'framework/research_questions.json',
             root / 'data/research_knowledge.json',
             Path(os.environ.get('INRESEARCH_READER_SNAPSHOT', workspace_path('data/research_runtime.json', root)))]
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else (str(p), None, None)
                 for p in paths)


@lru_cache(maxsize=1)
def available_materials(root, version):
    graph, questions, curated, _, runtime = registry._snapshot_inputs(root)
    current = runtime.get('knowledge') or {key: [] for key in registry.COLLECTIONS}
    available, skipped = rows(current, curated)
    return graph, questions, available, skipped, {
        'state': 'connected' if runtime.get('knowledge') else 'not_connected',
        'received_at': runtime.get('received_at')}


def for_node(root, node='root', *, offset=0, limit=20, query=''):
    if (type(offset) is not int or not 0 <= offset <= 100000000
            or type(limit) is not int or not 1 <= limit <= 50
            or not isinstance(query, str) or len(query) > 200):
        raise ValueError('invalid material filter')
    # Curated documents can point to an older reading of the same content. The
    # current received snapshot, rather than the merged view, owns this baseline.
    root = Path(root)
    graph, questions, available, skipped, connection = available_materials(root, input_version(root))
    # A report can span several nodes. Scope its statements after resolving
    # their sources; a broad document mapping must not hide a specific claim.
    selected = registry.summary_for_node({'graph': graph, 'questions': questions['records'],
        'tasks': [], 'knowledge': {'statements': available, 'documents': [], 'evidence': [], 'answers': []}}, node)
    records = selected['knowledge']['statements']
    if query:
        text = query.casefold()
        records = [r for r in records if text in r['text'].casefold()
                   or text in (r['source']['title'] or '').casefold()]
    total = len(records)
    return {'schema_version': 1, 'node': node, 'unknown': selected.get('unknown', False),
        **connection, 'acceptance': 'source_material',
        'total': total, 'materials': len({r['source']['id'] for r in records}),
        'undated': sum(not r['source_date'] for r in records), 'skipped': skipped,
        'offset': offset, 'limit': limit, 'next_offset': offset + limit if offset + limit < total else None,
        'records': records[offset:offset + limit]}
