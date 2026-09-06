#!/usr/bin/env python3
"""Versioned research registry, evidence validation and derived website snapshot.

Only curated, reviewed answers close questions. Reader output is always a candidate.
No original documents or runtime credentials are served by this module.
"""
import argparse
import copy
import csv
import hashlib
import json
import os
import tempfile
import re
import unicodedata
from urllib.parse import urlencode, urlsplit
from datetime import datetime, timezone
from pathlib import Path
from research_navigation import validate_navigation

ROOT = Path(__file__).resolve().parent.parent
COLLECTIONS = ('documents', 'evidence', 'statements', 'answers')


def parse_time(value):
    if not isinstance(value, str):
        raise ValueError('ISO timestamp required')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamp must include timezone')
    return parsed


def coverage_complete(document):
    c = document.get('coverage', {})
    sha = document.get('content_sha256', '')
    doc_id = document.get('doc_id', document.get('id', ''))
    if not isinstance(c, dict) or c.get('complete') is not True:
        return False
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha) or doc_id != 'doc-' + sha:
        return False
    for total, read in [('pages_total', 'pages_read'), ('chunks_total', 'chunks_read'),
                        ('characters_total', 'characters_read')]:
        if type(c.get(total)) is not int or type(c.get(read)) is not int:
            return False
        if c[total] <= 0 or c[total] != c[read]:
            return False
    return True


def review_valid(row):
    review = row.get('review', {})
    try:
        parse_time(review.get('at'))
    except (ValueError, TypeError):
        return False
    # Promotion is an explicit curated write; the worker and receiver cannot create it.
    return (bool(review.get('by')) and review.get('tier') in ('A', 'B', 'C')
            and review.get('decision') == 'adopted'
            and review.get('authority') in ('owner', 'reviewer')
            and (review['tier'] != 'A' or review['authority'] == 'owner'))


def supported_adoption(row, knowledge):
    if not review_valid(row) or not row.get('evidence_ids'):
        return False
    evidence = {e['id']: e for e in knowledge.get('evidence', [])}
    documents = {d['id']: d for d in knowledge.get('documents', [])}
    for eid in row['evidence_ids']:
        e = evidence.get(eid, {})
        d = documents.get(e.get('document_id'), {})
        if e.get('status') != 'adopted' or not review_valid(e):
            return False
        if not coverage_complete(d) or d.get('status') in ('withdrawn', 'rejected'):
            return False
        if 'page_index' in e and (type(e['page_index']) is not int or e['page_index'] < 0):
            return False
        if not e.get('locator') and e.get('page_index') is None:
            return False
    return True


def read_json(path, default=None):
    path = Path(path)
    if not path.exists() and default is not None:
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, allow_nan=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def validate(graph, questions, knowledge):
    errors = []
    errors.extend(validate_navigation(graph))
    def index(rows, name):
        found = {}
        for row in rows:
            key = row.get('id')
            if not isinstance(key, str) or not key or key in found:
                errors.append(f'{name}: missing/duplicate id {key}')
            found[key] = row
        return found
    objects = index(graph.get('objects', []), 'objects')
    qs = index(questions.get('records', []), 'questions')
    relations = index(graph.get('relations', []), 'relations')
    kinds = {v['id'] for v in graph['views']}
    for node in objects.values():
        if node.get('representation') not in ('conceptual', 'reference', 'actual'):
            errors.append(f"{node['id']}: representation required")
        if node.get('representation') == 'actual' and not node.get('evidence_ids'):
            errors.append(f"{node['id']}: actual asset requires evidence")
        if not set(node.get('views', [])) <= kinds:
            errors.append(f"{node['id']}: unknown view")
    parents = {}
    for rel in relations.values():
        if rel.get('source') not in objects or rel.get('target') not in objects:
            errors.append(f"{rel.get('id')}: dangling relation")
        if rel.get('type') in ('part_of', 'located_in'):
            key = (rel['type'], rel.get('configuration_id'))
            edge = parents.setdefault(key, {})
            if rel['source'] in edge:
                errors.append(f"{rel['id']}: multiple parents in one configuration/axis")
            edge[rel['source']] = rel['target']
    for edges in parents.values():
        for start in edges:
            visited, at = set(), start
            while at in edges:
                if at in visited:
                    errors.append(f'containment cycle at {at}')
                    break
                visited.add(at)
                at = edges[at]
    for q in qs.values():
        if not q.get('object_ids') or not set(q['object_ids']) <= objects.keys():
            errors.append(f"{q['id']}: question has missing/dangling objects")
        if not q.get('acceptance') or not q.get('evidence_requirements'):
            errors.append(f"{q['id']}: question lacks acceptance contract")
    tables = {name: index(knowledge.get(name, []), name) for name in COLLECTIONS}
    for name, rows in tables.items():
        for row in rows.values():
            rid = row.get('id')
            if name == 'documents' and row.get('coverage', {}).get('complete') is True and not coverage_complete(row):
                errors.append(f'{rid}: invalid complete coverage/content identity')
            for field, targets in [('object_ids', objects), ('question_ids', qs),
                                   ('evidence_ids', tables['evidence']),
                                   ('statement_ids', tables['statements'])]:
                if not set(row.get(field, [])) <= targets.keys():
                    errors.append(f'{name}/{rid}: dangling {field}')
            if name == 'evidence':
                if row.get('document_id') not in tables['documents']:
                    errors.append(f'{rid}: missing original document')
                if not row.get('locator') and row.get('page_index') is None:
                    errors.append(f'{rid}: original locator required')
                if 'page_index' in row and (type(row['page_index']) is not int or row['page_index'] < 0):
                    errors.append(f'{rid}: page_index must be a nonnegative integer')
            if name in ('statements', 'answers') and not row.get('evidence_ids'):
                errors.append(f'{rid}: assertion/answer requires evidence')
            if name == 'answers' and row.get('question_id') not in qs:
                errors.append(f'{rid}: unknown question')
            if row.get('status') in ('adopted', 'answered') or row.get('acceptance') == 'adopted':
                if not review_valid(row):
                    errors.append(f'{rid}: adopted record requires C3 review attribution')
                if name in ('statements', 'answers') and not supported_adoption(row, knowledge):
                    errors.append(f'{rid}: adoption lacks valid adopted source evidence')
    for node in objects.values():
        if not set(node.get('evidence_ids', [])) <= tables['evidence'].keys():
            errors.append(f"{node['id']}: dangling evidence")
    return errors


def completed_questions(knowledge):
    """No path, score, summary, or self-declared question status closes a gap."""
    return {a['question_id'] for a in knowledge.get('answers', [])
            if a.get('status') == 'adopted' and supported_adoption(a, knowledge)}


def question_tasks(questions, knowledge):
    closed = completed_questions(knowledge)
    return [dict(id='Q-' + q['id'], wid='Q-' + q['id'], mid=q['module_id'],
                 module_id=q['module_id'], pri='P2', kind='研究问题开放',
                 gap=q['text'], title=q['text'], action=q['acceptance'],
                 brief=q['text'] + '\n验收：' + q['acceptance'],
                 object_ids=q['object_ids'], question_ids=[q['id']],
                 evidence_requirements=q['evidence_requirements'], status='open')
            for q in questions['records'] if q['id'] not in closed]


def candidate_snapshot(payload, graph, questions):
    """Normalize untrusted reader JSON; this API cannot promote a claim."""
    if not isinstance(payload, dict) or payload.get('graph_version') != graph['version']:
        raise ValueError('reader graph_version does not match deployed framework')
    if payload.get('questions_version') != questions['version']:
        raise ValueError('reader questions_version does not match deployed questions')
    generated = payload.get('generated')
    if (parse_time(generated) - datetime.now(timezone.utc)).total_seconds() > 300:
        raise ValueError('snapshot timestamp is in the future')
    knowledge = payload.get('knowledge', {})
    if not isinstance(knowledge, dict):
        raise ValueError('knowledge must be an object')
    result = {name: [] for name in COLLECTIONS}
    allowed = {'id', 'doc_id', 'title', 'source_url', 'stored_path', 'coverage',
               'object_ids', 'question_ids', 'document_id', 'page_index', 'locator',
               'quote', 'text', 'kind', 'evidence_ids', 'statement_ids', 'question_id',
               'model', 'read_status', 'mapping_status', 'content_sha256'}
    for name in COLLECTIONS:
        rows = knowledge.get(name, [])
        if not isinstance(rows, list):
            raise ValueError(f'{name} must be an array')
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f'{name} contains a non-object')
            normalized = {k: v for k, v in row.items() if k in allowed}
            normalized.update(status='candidate', acceptance='candidate')
            result[name].append(normalized)
    errors = validate(graph, questions, result)
    if errors:
        raise ValueError('; '.join(errors[:8]))
    reader = payload.get('reader', {})
    if not isinstance(reader, dict):
        raise ValueError('reader must be an object')
    # It is a derived health snapshot, never an instruction or source of authority.
    reader = {k: v for k, v in reader.items() if k in (
        'generated', 'counts', 'stage_counts', 'oldest_pending', 'recent_failures',
        'backend', 'model', 'roots', 'status', 'release', 'acquisition')}
    return dict(graph_version=graph['version'], questions_version=questions['version'], generated=generated,
                received_at=datetime.now(timezone.utc).isoformat(), knowledge=result, reader=reader)


def merge_knowledge(curated, candidates):
    result = copy.deepcopy(curated)
    for name in COLLECTIONS:
        existing = {r['id']: r for r in result.get(name, [])}
        identity_fields = {'documents': ('content_sha256',),
            'evidence': ('document_id', 'page_index', 'locator', 'quote'),
            'statements': ('text', 'evidence_ids'), 'answers': ('text', 'question_id', 'evidence_ids')}[name]
        for candidate in candidates[name]:
            current = existing.get(candidate['id'])
            if current and any(current.get(k) != candidate.get(k) for k in identity_fields):
                raise ValueError(f"{name}/{candidate['id']}: content identity collision")
        result.setdefault(name, []).extend(r for r in candidates[name] if r['id'] not in existing)
    return result


def catalog_id(kind, *identity):
    """Chinese product-line text is part of identity; never slug it into an empty key."""
    raw = json.dumps(identity, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return kind + ':' + hashlib.sha256(raw).hexdigest()


def build_catalog(root, graph):
    """Project existing catalog metadata without promoting it to research evidence.

    Product rows remain product lines. Plans and historical index records keep their
    own statuses; neither a path nor an old 'verified' label proves availability now.
    """
    root = Path(root)
    product_path = 'data/products.json'
    company_path = 'data/companies.json'
    plan_path = 'data/product_docs_plan.csv'
    primary_index = 'data/product_library_index.json'
    fallback_index = 'docs/inbox/inresearch-alignment/library_index.json'
    product_rows = read_json(root / product_path, {'records': []})['records']
    company_rows = read_json(root / company_path, {'records': []})['records']
    indexed = read_json(root / primary_index, {'records': []}).get('records', [])
    index_path = primary_index
    if not indexed:
        index_path = fallback_index
        indexed = read_json(root / fallback_index, {'records': []}).get('records', [])
    plans = []
    if (root / plan_path).exists():
        with (root / plan_path).open(encoding='utf-8-sig', newline='') as fh:
            plans = list(csv.DictReader(fh))
    objects = {row['id']: row for row in graph.get('objects', [])}
    parents = {}
    for relation in graph.get('relations', []):
        # Do not walk requires/demand_transmission or attach by module membership.
        if relation.get('type') in ('part_of', 'located_in', 'member_of_system'):
            parents.setdefault(relation['source'], set()).add(relation['target'])

    def strings(value):
        if isinstance(value, str):
            return [value] if value else []
        return [x for x in (value or []) if isinstance(x, str) and x]

    def mapping(row):
        parts = sorted(set(strings(row.get('bom_parts')) + strings(row.get('bom_part'))))
        mapped = sorted({'part:' + part for part in parts if 'part:' + part in objects})
        unresolved = sorted(set(parts) - {oid[5:] for oid in mapped})
        related, pending = set(mapped), list(mapped)
        while pending:
            for target in parents.get(pending.pop(), set()):
                node = objects.get(target, {})
                # Ancestors are navigation context, not actual facility installations.
                if target not in related and node and not target.startswith(('workload:', 'demand:', 'activity:')):
                    related.add(target)
                    pending.append(target)
        return dict(object_ids=mapped, related_object_ids=sorted(related), unmapped_bom_parts=unresolved,
                    mapping_basis='explicit_bom' if mapped else 'unmapped',
                    mapping_status='needs_review' if unresolved or not mapped else 'registered_bom')

    def normalized(value):
        return ''.join(c for c in unicodedata.normalize('NFKC', str(value or '')).casefold() if c.isalnum())

    def web_url(value):
        value = str(value or '').strip()
        # A website field may contain explanatory prose; do not invent a link from it.
        if not value or any(c.isspace() for c in value):
            return None
        if '://' not in value and ':' in value.split('/', 1)[0]:
            return None
        candidate = value if '://' in value else 'https://' + value
        try:
            parsed = urlsplit(candidate)
            parsed.port  # Reject malformed authority rather than guessing a website.
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                return None
            # Host-only prose (e.g. 各家官网) also encodes as IDNA, so IDNA alone
            # is insufficient. Require a public-style dotted domain, not an IP or
            # local hostname. Chinese domain labels and suffixes remain supported.
            hostname = parsed.hostname.encode('idna').decode('ascii').rstrip('.')
            labels = hostname.split('.')
            if len(labels) < 2 or len(hostname) > 253 or labels[-1].isdigit():
                return None
            if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label, re.I) for label in labels):
                return None
            return candidate
        except (ValueError, UnicodeError):
            return None

    products, exact, aliases = [], {}, {}
    for row in product_rows:
        company, line = row['company_id'], row['product_line']
        pid = catalog_id('product-line', company, line)
        entry = dict(copy.deepcopy(row), id=pid, kind='product_line', identity_kind='product_line',
                     company_catalog_id='company:' + company, **mapping(row),
                     catalog_node_ids=['activity:V2'] if 'activity:V2' in objects else [],
                     catalog_node_basis='catalog_navigation_only', source_url=web_url(row.get('website')),
                     source_path=product_path, source_record=copy.deepcopy(row),
                     verification_status='registry_only', document_ids=[], plan_ids=[], models=[],
                     admin_url='/admin/product/?' + urlencode({'company': company, 'line': line}))
        products.append(entry)
        exact.setdefault((company, line), []).append(pid)
        aliases.setdefault((company, normalized(line)), []).append(pid)
    product_by_id = {row['id']: row for row in products}

    def match_product(row):
        key = (row.get('company_id'), row.get('product_line', ''))
        found = exact.get(key, [])
        if len(found) == 1:
            return found, 'exact_company_and_product_line'
        found = aliases.get((key[0], normalized(key[1])), [])
        # Legacy slash-to-hyphen paths may match, but ambiguous normalization never does.
        return (found, 'unique_normalized_product_line') if len(found) == 1 else ([], 'unmatched_or_ambiguous')

    documents, document_ids = [], set()
    for kind, rows, source in (('indexed_document', indexed, index_path), ('document_plan', plans, plan_path)):
        for row in rows:
            identity = [row.get('company_id'), row.get('product_line'), row.get('model'), row.get('doc_type')]
            did = catalog_id('catalog-document' if kind == 'indexed_document' else 'catalog-plan', source,
                             row.get('doc_id') if kind == 'indexed_document' and row.get('doc_id') else identity)
            if did in document_ids:
                # Preserve unexpected distinct source variants without conflating their status.
                did = catalog_id('catalog-duplicate', did, row)
                if did in document_ids:
                    continue
            document_ids.add(did)
            pids, basis = match_product(row)
            entry = dict(copy.deepcopy(row), id=did, kind=kind, product_ids=pids, **mapping(row),
                         product_match_basis=basis, source_path=source, source_record=copy.deepcopy(row),
                         status=row.get('status') or 'unknown',
                         source_url=row.get('source_url') or None,
                         registered_status=row.get('status') or 'unknown',
                         verification_status='planned_only' if kind == 'document_plan' else 'historical_index_metadata',
                         current_availability='not_checked', acceptance='catalog_metadata',
                         content_sha256=row.get('sha256'), linked_document_ids=[])
            documents.append(entry)
            for pid in pids:
                product_by_id[pid]['plan_ids' if kind == 'document_plan' else 'document_ids'].append(did)
    indexes = [row for row in documents if row['kind'] == 'indexed_document']
    for row in documents:
        if row['kind'] != 'document_plan':
            continue
        explicit = bool(row.get('doc_id'))
        row['document_link_basis'] = 'explicit_doc_id' if explicit else 'model_and_type_candidates'
        row['linked_document_ids'] = [item['id'] for item in indexes if set(item['product_ids']) & set(row['product_ids'])
                                     and (item.get('doc_id') == row['doc_id'] if explicit else
                                          (normalized(item.get('model')) == normalized(row.get('model'))
                                           and item.get('doc_type') == row.get('doc_type')))]
    for product in products:
        model_labels = {}
        for doc in documents:
            label = doc.get('model')
            if product['id'] not in doc['product_ids'] or not label or str(label).casefold() == 'line':
                continue
            model = model_labels.setdefault(label, dict(id=catalog_id('model-label', product['id'], label), label=label,
                        identity_kind='registered_model_label', document_ids=[], plan_ids=[]))
            model['plan_ids' if doc['kind'] == 'document_plan' else 'document_ids'].append(doc['id'])
        product['models'] = list(model_labels.values())
    companies = []
    company_registry = {row['company_id']: row for row in company_rows}
    for cid in sorted({row['company_id'] for row in products}):
        linked = [row for row in products if row['company_id'] == cid]
        original = company_registry.get(cid)
        row = copy.deepcopy(original) if original else {'company_id': cid, 'name': linked[0].get('company_en', cid), 'name_cn': linked[0].get('company_cn')}
        companies.append(dict(row, id='company:' + cid, product_ids=[p['id'] for p in linked],
                              object_ids=sorted({oid for p in linked for oid in p['object_ids']}),
                              source_path=company_path if original else product_path, source_record=copy.deepcopy(original or linked[0]['source_record']),
                              verification_status='registry_only', source_url=web_url(row.get('website')) or web_url(row.get('ir_url')),
                              admin_url='/admin/product/?' + urlencode({'company': cid})))
    return dict(schema_version=1, products=products, companies=companies, documents=documents,
                sources=dict(products=product_path, companies=company_path, plans=plan_path, index=index_path,
                             index_selection='primary' if index_path == primary_index else 'alignment_fallback'),
                counts=dict(product_lines=len(products), companies=len(companies), plans=len(plans), indexed_documents=len(indexed)),
                status='ready', acceptance='catalog_metadata',
                note='登记产品线、型号标签、计划与历史资料索引；不代表 SKU、当前文件可用、全文已读或研究已采用。')


def build_snapshot(root=ROOT):
    graph = read_json(root / 'framework/research_graph.json')
    questions = read_json(root / 'framework/research_questions.json')
    curated = read_json(root / 'data/research_knowledge.json')
    errors = validate(graph, questions, curated)
    if errors:
        raise ValueError('; '.join(errors[:8]))
    runtime_path = Path(os.environ.get('INRESEARCH_READER_SNAPSHOT', root / 'data/research_runtime.json'))
    knowledge = copy.deepcopy(curated)
    try:
        runtime = read_json(runtime_path, {})
        if runtime:
            # A copied/stale snapshot cannot take down the curated research interface.
            runtime = candidate_snapshot(runtime, graph, questions) | {'received_at': runtime.get('received_at')}
            knowledge = merge_knowledge(curated, runtime['knowledge'])
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        runtime = {'reader': {'status': 'degraded', 'message': '候选快照与现行框架不一致或校验失败，等待 Spark 重同步；正式研究仍可访问。'}}
    # Legacy metadata is explicitly not proof of reading or source availability.
    for source in read_json(root / 'data/sources.json', {'records': []})['records']:
        knowledge['documents'].append(dict(id='legacy:' + source['source_id'], title=source['title'],
            source_url=source.get('url'), stored_path=source.get('local_file'),
            status='legacy_metadata', acceptance='unverified', coverage={'complete': False},
            object_ids=[], question_ids=[], read_status='unverified'))
    closed = completed_questions(curated)
    for q in questions['records']:
        q['status'] = 'answered' if q['id'] in closed else 'open'
    tasks = question_tasks(questions, curated)
    old = read_json(root / 'reports/workorders.json', {'orders': []})['orders']
    tasks.extend(o for o in old if o.get('kind') not in ('声明问题开放', '研究问题开放'))
    assignments = {a['workorder_id']: a for a in read_json(root / 'data/assignments.json', {'records': []})['records']}
    for task in tasks:
        task['assignment'] = assignments.get(task.get('wid'))
    reader = runtime.get('reader', {'status': 'not_connected', 'model': 'qwen3.8:27b'})
    reader['received_at'] = runtime.get('received_at')
    if reader.get('received_at'):
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(reader['received_at'])).total_seconds()
            reader['stale'] = age > 900
        except (ValueError, TypeError):
            reader['stale'] = True
    return dict(graph=graph, questions=questions, knowledge=knowledge, tasks=tasks, reader=reader,
                catalog=build_catalog(root, graph))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='store_true')
    args = parser.parse_args()
    graph = read_json(ROOT / 'framework/research_graph.json')
    questions = read_json(ROOT / 'framework/research_questions.json')
    knowledge = read_json(ROOT / 'data/research_knowledge.json')
    errors = validate(graph, questions, knowledge)
    # The retained 116 questions must not silently diverge from their legacy declarations.
    mods = read_json(ROOT / 'framework/modules.json')['modules']
    for m in mods:
        expected = [q if isinstance(q, str) else q.get('q', q.get('text')) for q in m['questions']]
        actual = [q['text'] for q in questions['records'] if q.get('origin') == 'legacy-module' and q['module_id'] == m['id']]
        if expected != actual:
            errors.append(f"{m['id']}: legacy questions diverged")
    if errors:
        print('\n'.join(errors))
        return 1
    if args.snapshot:
        print(json.dumps(build_snapshot(), ensure_ascii=False, allow_nan=False))
    else:
        print(f"Research v{graph['version']}: {len(graph['objects'])} objects, {len(questions['records'])} questions; references valid")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
