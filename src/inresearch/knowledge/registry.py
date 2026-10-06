#!/usr/bin/env python3
"""Versioned research registry, evidence validation and derived website snapshot.

Only curated, reviewed answers close questions. Reader output is always a candidate.
No original documents or runtime credentials are served by this module.
"""

from inresearch.paths import project_root
from inresearch.storage.layout import workspace_path
from inresearch.knowledge.news_policy import TARGET_ID
import argparse
import copy
import csv
import hashlib
import json
import os
import re
import unicodedata
from urllib.parse import urlencode, urlsplit
from datetime import datetime, timezone
from pathlib import Path
from inresearch.knowledge.navigation import validate_navigation

ROOT = project_root()
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
    if not isinstance(review, dict):
        return False
    try:
        parse_time(review.get('at'))
    except (ValueError, TypeError):
        return False
    # Promotion is an explicit curated write; the worker and receiver cannot create it.
    return (isinstance(review.get('by'), str) and bool(review['by'].strip())
            and review.get('tier') in ('A', 'B')
            and review.get('decision') == 'adopted'
            and review.get('authority') in ('owner', 'reviewer')
            and (review['tier'] != 'A' or review['authority'] == 'owner'))


def evidence_errors(row, document, adopted=False):
    """One source-location contract for validation and adoption eligibility."""
    errors = []
    page = row.get('page_index')
    total = document.get('coverage', {}).get('pages_total')
    if 'page_index' in row and (type(page) is not int or page < 0):
        errors.append('page_index must be a nonnegative integer')
    elif type(page) is int and type(total) is int and page >= total:
        errors.append('page_index exceeds original document pages')
    locator = row.get('locator')
    if page is None and not (isinstance(locator, str) and locator.strip()):
        errors.append('original locator required')
    if adopted and not (isinstance(row.get('quote'), str) and row['quote'].strip()):
        errors.append('adopted text evidence requires original quotation')
    if row.get('content_sha256') and row['content_sha256'] != document.get('content_sha256'):
        errors.append('evidence content identity differs from original document')
    return errors


def supported_adoption(row, knowledge):
    """Evaluate the whole support chain; revoked dependencies reopen questions."""
    evidence = {e['id']: e for e in knowledge.get('evidence', [])}
    documents = {d['id']: d for d in knowledge.get('documents', [])}
    statements = {s['id']: s for s in knowledge.get('statements', [])}

    def supported(record, visiting):
        rid = record.get('id')
        if (rid in visiting or record.get('status') != 'adopted'
                or not review_valid(record) or not record.get('evidence_ids')):
            return False
        for eid in record['evidence_ids']:
            e = evidence.get(eid, {})
            d = documents.get(e.get('document_id'), {})
            if e.get('status') != 'adopted' or not review_valid(e):
                return False
            if not coverage_complete(d) or d.get('status') in ('withdrawn', 'rejected', 'superseded'):
                return False
            if evidence_errors(e, d, adopted=True):
                return False
        return all(supported(statements.get(sid, {}), visiting | {rid})
                   for sid in record.get('statement_ids', []))

    return supported(row, set())


def read_json(path, default=None):
    path = Path(path)
    if not path.exists() and default is not None:
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path, data):
    from inresearch.storage.files import write_json
    write_json(path, data)


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
    for node in objects.values():
        if node.get('representation') not in ('conceptual', 'reference', 'actual'):
            errors.append(f"{node['id']}: representation required")
        if node.get('representation') == 'actual' and not node.get('evidence_ids'):
            errors.append(f"{node['id']}: actual asset requires evidence")
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
                errors.extend(f'{rid}: {error}' for error in evidence_errors(
                    row, tables['documents'].get(row.get('document_id'), {}),
                    adopted=row.get('status') == 'adopted'))
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
    # 兼容模块码只是任务的分组键（研究问题任务、深读分包），问题本身挂骨架节点
    return [dict(id='Q-' + q['id'], wid='Q-' + q['id'], mid=q.get('legacy_module') or q.get('module_id'),
                 module_id=q.get('legacy_module') or q.get('module_id'), node=q.get('node'), variable_class=q.get('variable_class'), pri='P2', kind='研究问题开放',
                 gap=q['text'], title=q['text'], action=q['acceptance'],
                 brief=q['text'] + '\n验收：' + q['acceptance'],
                 object_ids=q['object_ids'], question_ids=[q['id']],
                 evidence_requirements=q['evidence_requirements'], status='open')
            for q in questions['records'] if q['id'] not in closed]


def current_tasks(root=ROOT, questions=None, knowledge=None):
    """The task set used by research views, assignment and queue consumers."""
    if questions is None:
        questions = read_json(root / 'framework/research_questions.json')
    if knowledge is None:
        knowledge = read_json(root / 'data/research_knowledge.json')
    tasks = question_tasks(questions, knowledge)
    legacy = read_json(workspace_path('reports/workorders.json', root), {'orders': []})['orders']
    tasks.extend(o for o in legacy if o.get('kind') not in ('声明问题开放', '研究问题开放'))
    names = {m['id']: m['name'] for m in read_json(root / 'framework/modules.json', {'modules': []})['modules']}
    assignments = {a['workorder_id']: a for a in read_json(workspace_path('data/assignments.json', root), {'records': []})['records']}
    for task in tasks:
        task.setdefault('name', names.get(task.get('mid'), ''))
        task['assignment'] = assignments.get(task.get('wid'))
    return tasks


def task_board(root=ROOT, questions=None, knowledge=None):
    """One projection for every task-facing interface and page.

    Module-gap statistics remain a generated workorders artifact.  Open
    research questions never come from that artifact: they are recomputed from
    the current adopted knowledge in ``current_tasks``.
    """
    projection = read_json(workspace_path('reports/workorders.json', root), {})
    return {
        'orders': current_tasks(root, questions, knowledge),
        'module_stats': projection.get('module_stats', {}),
        'generated': datetime.now().isoformat(timespec='seconds'),
    }


def object_resolver(objects, root_prefixes=()):
    """图谱 3.0：把旧对象 ID 折算到骨架节点——先看对象登记的别名，再看根前缀；折算不了的返回 None（不猜）。

    接收端（candidate_snapshot）、阅读快照导出端（delivery/reader_export）和 Spark 的外部快照叠加
    （delivery/snapshot_overlay）共用同一张折算表，所以 Spark / M4 / M5 更新源码后导出的快照与
    旧版快照落到同样的节点。"""
    known = {o['id'] for o in objects if isinstance(o, dict) and 'id' in o}
    fold = {alias: o['id'] for o in objects if isinstance(o, dict) for alias in (o.get('aliases') or [])}
    prefixes = tuple(root_prefixes or ())

    def resolve(value):
        if value in known:
            return value
        if value in fold:
            return fold[value]
        if prefixes and isinstance(value, str) and value.startswith(prefixes) and 'root' in known:
            return 'root'
        return None
    return resolve


def candidate_snapshot(payload, graph, questions):
    """Normalize untrusted reader JSON; this API cannot promote a claim.

    The site follows main automatically while Spark is updated by hand, so a
    snapshot mapped against an older registry is normal for a while after each
    registry change. Such a snapshot is no longer refused: its object/question IDs
    are filtered to the deployed registry (never guessed), the rest is kept, and
    ``reader.registry_lag`` says which versions differed and how many IDs went."""
    if not isinstance(payload, dict):
        raise ValueError('reader snapshot must be an object')
    for key in ('graph_version', 'questions_version'):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError('reader snapshot lacks ' + key)
    lagging = payload['graph_version'] != graph['version'] or payload['questions_version'] != questions['version']
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
               'model', 'read_status', 'mapping_status', 'content_sha256', 'reading_revision_id', 'report_sha256'}
    known = {'object_ids': {o['id'] for o in graph.get('objects', []) if isinstance(o, dict) and 'id' in o},
             'question_ids': {q['id'] for q in questions.get('records', []) if isinstance(q, dict) and 'id' in q}}
    # 图谱 3.0：旧对象 ID 先按对象登记的别名与根前缀折算到骨架节点（不猜），折算不了的才丢
    resolve = object_resolver(graph.get('objects', []), graph.get('legacy_root_prefixes'))
    dropped_ids = dropped_answers = folded_ids = 0
    for name in COLLECTIONS:
        rows = knowledge.get(name, [])
        if not isinstance(rows, list):
            raise ValueError(f'{name} must be an array')
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f'{name} contains a non-object')
            normalized = {k: v for k, v in row.items() if k in allowed}
            normalized.update(status='candidate', acceptance='candidate')
            if lagging:
                for field, ids in known.items():
                    if isinstance(normalized.get(field), list):
                        if field == 'object_ids':
                            kept = []
                            for v in normalized[field]:
                                target = resolve(v)
                                if target is None:
                                    dropped_ids += 1
                                    continue
                                folded_ids += target != v
                                if target not in kept:
                                    kept.append(target)
                        else:
                            kept = [v for v in normalized[field] if v in ids]
                            dropped_ids += len(normalized[field]) - len(kept)
                        normalized[field] = kept
                if name == 'answers' and normalized.get('question_id') not in known['question_ids']:
                    dropped_answers += 1
                    continue
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
        'backend', 'model', 'roots', 'status', 'release', 'acquisition', 'reading_revisions', 'registry_lag')}
    if lagging:
        reader['registry_lag'] = {'snapshot_graph_version': payload['graph_version'],
                                  'snapshot_questions_version': payload['questions_version'],
                                  'dropped_ids': dropped_ids, 'dropped_answers': dropped_answers, 'folded_ids': folded_ids}
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
    indexed = read_json(workspace_path(primary_index, root), {'records': []}).get('records', [])
    index_path = primary_index
    if not indexed:
        index_path = fallback_index
        indexed = read_json(root / fallback_index, {'records': []}).get('records', [])
    plans = []
    if (workspace_path(plan_path, root)).exists():
        with (workspace_path(plan_path, root)).open(encoding='utf-8-sig', newline='') as fh:
            plans = list(csv.DictReader(fh))
    objects = {row['id']: row for row in graph.get('objects', [])}
    parents = {}
    for relation in graph.get('relations', []):
        # 骨架的包含关系：部件 → 链路 → 系统 → 根（旧图的 located_in / member_of_system 仍可走）。
        if relation.get('type') in ('part_of', 'located_in', 'member_of_system'):
            parents.setdefault(relation['source'], set()).add(relation['target'])

    def strings(value):
        if isinstance(value, str):
            return [value] if value else []
        return [x for x in (value or []) if isinstance(x, str) and x]

    def mapping(row):
        parts = sorted(set(strings(row.get('bom_parts')) + strings(row.get('bom_part'))))
        mapped = sorted({'part:' + part for part in parts if 'part:' + part in objects})
        unresolved = sorted(part for part in parts if 'part:' + part not in objects)
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
                     catalog_node_ids=sorted({objects[oid].get('parent') for oid in mapping(row)['object_ids'] if objects.get(oid, {}).get('parent')}),
                     catalog_node_basis='skeleton_parent', source_url=web_url(row.get('website')),
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


def _snapshot_inputs(root):
    graph = read_json(root / 'framework/research_graph.json')
    questions = read_json(root / 'framework/research_questions.json')
    curated = read_json(root / 'data/research_knowledge.json')
    errors = validate(graph, questions, curated)
    if errors:
        raise ValueError('; '.join(errors[:8]))
    runtime_path = Path(os.environ.get('INRESEARCH_READER_SNAPSHOT', workspace_path('data/research_runtime.json', root)))
    knowledge = copy.deepcopy(curated)
    try:
        runtime = read_json(runtime_path, {})
        if runtime:
            # A copied/stale snapshot cannot take down the curated research interface.
            runtime = candidate_snapshot(runtime, graph, questions) | {'received_at': runtime.get('received_at')}
            knowledge = merge_knowledge(curated, runtime['knowledge'])
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        runtime = {'reader': {'status': 'degraded', 'message': '候选快照与现行框架不一致或校验失败，等待 Spark 重同步；正式研究仍可访问。'}}
    return graph, questions, curated, knowledge, runtime


def _reader_state(runtime):
    reader = copy.deepcopy(runtime.get('reader', {'status': 'not_connected', 'model': None}))
    reader['received_at'] = runtime.get('received_at')
    if reader.get('received_at'):
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(reader['received_at'])).total_seconds()
            reader['stale'] = age > 900
        except (ValueError, TypeError):
            reader['stale'] = True
    return reader


def _fetchspec_counts(value):
    """Spark 发布的 fetchspec 回流计数，逐行校验；形状不对的行丢掉，整项不对返回 None。"""
    if not isinstance(value, dict) or len(value) > 5000:
        return None
    kept = {}
    for target, row in value.items():
        if not (isinstance(target, str) and TARGET_ID.fullmatch(target) and isinstance(row, dict)):
            continue
        items, observations = row.get('received_items'), row.get('parameter_observations', 0)
        companies, last = row.get('companies', []), row.get('last_received_at')
        if (type(items) is not int or items < 0 or type(observations) is not int or observations < 0
                or not isinstance(companies, list) or len(companies) > 40
                or any(not isinstance(c, str) or not c or len(c) > 80 for c in companies)
                or not (last is None or (isinstance(last, str) and len(last) <= 40))):
            continue
        kept[target] = {'received_items': items, 'companies': sorted(set(companies)), 'last_received_at': last,
                        'parameter_observations': observations}
    return kept


def build_backflow(root=ROOT, team='fetchspec'):
    """回流（2026-10-01，fetchspec 申请 #301）：某一队的每条目标行到了哪一步。

    status 照抄目标表（Git），计数来自 Spark 发布的快照：fetchspec 用接收台账（原件数、厂商、参数观测数），
    inews 用 /api/news 同一份线索计数。其余队尚无交付，计数为 0。只有目标行 ID、状态与计数，公开只读。
    未登记的队抛 KeyError（接口返回 400）。"""
    raw = (root / 'framework/tco_targets.json').read_bytes()
    document = json.loads(raw)
    if team not in (document.get('teams') or {}):
        raise KeyError('unknown_team')
    rows = [t for t in document['targets'] if t.get('team') == team]
    *_, runtime = _snapshot_inputs(root)
    reader = _reader_state(runtime)
    acquisition = reader.get('acquisition') if isinstance(reader.get('acquisition'), dict) else {}
    received = {}
    if team == 'fetchspec':
        received = _fetchspec_counts((acquisition.get('fetchspec_feed') or {}).get('by_target')) or {}
    elif team == 'inews':
        counts = (acquisition.get('news_feed') or {}).get('by_target')
        if isinstance(counts, dict):
            received = {k: {'received_items': v, 'companies': [], 'last_received_at': None, 'parameter_observations': 0}
                        for k, v in counts.items() if isinstance(k, str) and TARGET_ID.fullmatch(k) and type(v) is int and v >= 0}
    empty = {'received_items': 0, 'companies': [], 'last_received_at': None, 'parameter_observations': 0}
    by_target = {row['id']: {'status': row.get('status'), **received.get(row['id'], empty)} for row in rows}
    return dict(schema_version=1, team=team, generated_at=datetime.now(timezone.utc).isoformat(),
                targets_sha256=hashlib.sha256(raw).hexdigest(), by_target=by_target,
                reader={key: reader[key] for key in ('status', 'received_at', 'stale') if key in reader})


def news_leads(root=ROOT):
    """当前窗口里的新闻线索原样(带 target_ids、origin_pointer),只给打标记时找目标行用,不公开。"""
    *_, runtime = _snapshot_inputs(root)
    acquisition = _reader_state(runtime).get('acquisition')
    feed = acquisition.get('news_feed') if isinstance(acquisition, dict) else None
    items = feed.get('items') if isinstance(feed, dict) else None
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def build_news(root=ROOT):
    """News consumes the same validated snapshot without constructing catalog/tasks."""
    *_, knowledge, runtime = _snapshot_inputs(root)
    reader = _reader_state(runtime)
    acquisition = reader.get('acquisition')
    if acquisition is not None and not isinstance(acquisition, dict):
        raise ValueError('invalid_acquisition_metadata')
    feed = acquisition.get('news_feed') if isinstance(acquisition, dict) else None
    if feed is not None:
        if not isinstance(feed, dict) or not isinstance(feed.get('items', []), list):
            raise ValueError('invalid_news_feed')
        items = feed.get('items', [])
        if any(not isinstance(item, dict) for item in items):
            raise ValueError('invalid_news_item')
        def timestamp(item):
            value = item.get('published_at')
            return value if type(value) in (int, float) and abs(value) <= 8640000000000000 else 0
        # 回流（2026-10-01）：每条目标行在当前窗口里收到几张新闻线索。只是计数，目标行 ID 本来就在公开的
        # framework/tco_targets.json 里；inews 读这一项（公开 /api/news）调词与调车道。形状不对就不给，不拒整页。
        counts = feed.get('by_target')
        by_target = ({k: v for k, v in counts.items() if isinstance(k, str) and TARGET_ID.fullmatch(k) and type(v) is int and v >= 0}
                     if isinstance(counts, dict) and len(counts) <= 5000 else None)
        # 回流的两个「用上」信号（2026-10-01 用户定口径）：研究员点「有用」的线索（快）与顺着线索已经 C3 采用了原件的（慢），
        # 都只是按目标行的计数；标记本身留在私有运行目录。读不到标记就不给这两项，不拒整页。
        try:
            from inresearch.workflow import news_marks
            used = {'useful_by_target': news_marks.useful_by_target(root),
                    'adopted_by_target': news_marks.adopted_by_target(root, items, knowledge, review_valid)}
            used = {k: v for k, v in used.items() if v}   # 没有就不出现,与 by_target 缺省同一习惯
        except (ValueError, TypeError, KeyError, OSError):
            used = {}
        feed = dict(status=feed.get('status'), exported_at=feed.get('exported_at'),
                    items=[{key: item[key] for key in ('title_zh', 'url', 'domain', 'published_at', 'editorial_pick', 'event_type', 'object_ids') if key in item}
                           for item in sorted(items, key=timestamp, reverse=True)[:80]],
                    **({'by_target': by_target} if by_target is not None else {}), **used)
    from inresearch.knowledge.industry import public_url
    pipeline = acquisition.get('project_pipeline') if isinstance(acquisition, dict) else None
    leads = []
    if isinstance(pipeline, dict) and isinstance(pipeline.get('records'), list):
        for row in pipeline['records'][:500]:
            if not isinstance(row, dict): continue
            events = [{k: e.get(k) for k in ('title_zh', 'title', 'url', 'published_at', 'event_type', 'reported_stage', 'reported_capacity', 'site_candidates', 'capacity_observations', 'constraints', 'target_ids')}
                      for e in row.get('events', []) if isinstance(e, dict) and public_url(e.get('url'))]
            for event in events:
                event['site_candidates'] = [{k:c[k] for k in ('site_id','method','anchor') if k in c}
                                            for c in event.get('site_candidates') or [] if isinstance(c,dict)]
                event['capacity_observations'] = [{k:c[k] for k in ('quoted_value','mw','basis','locator','quote','acceptance') if k in c}
                                                  for c in event.get('capacity_observations') or [] if isinstance(c,dict)]
            if events:
                leads.append({k: row.get(k) for k in ('id', 'title', 'state', 'first_seen', 'last_seen', 'company_ids', 'site_id', 'review_note', 'reported_stage', 'reported_capacity', 'match_method')} | {'events': events})
    raw_progress = pipeline.get('progress', {}) if isinstance(pipeline, dict) else {}
    progress = {k:raw_progress[k] for k in ('leads','events','linked','identity_candidates','capacity_observations')
                if type(raw_progress.get(k)) is int and raw_progress[k]>=0}
    progress['constraints'] = {k:v for k,v in (raw_progress.get('constraints') or {}).items()
                               if k in ('water','power','permits','land','finance') and type(v) is int and v>=0}
    progress['adoption_note'] = '新闻观察不证明正式容量采用。'
    return dict(schema_version=1, feed=feed, pipeline={'records': leads, 'available': pipeline is not None,
                'total': pipeline.get('total') if isinstance(pipeline,dict) else None, 'progress': progress,
                'truncated': bool(pipeline.get('truncated')) if isinstance(pipeline, dict) else False},
                reader={key: reader[key] for key in ('status', 'received_at', 'stale') if key in reader})


def _research_state(root):
    """Shared current research state before consumer-specific serialization."""
    graph, questions, curated, knowledge, runtime = _snapshot_inputs(root)
    closed = completed_questions(curated)
    for question in questions['records']:
        question['status'] = 'answered' if question['id'] in closed else 'open'
    return dict(graph=graph, questions=questions, knowledge=knowledge,
                tasks=current_tasks(root, questions, curated), reader=_reader_state(runtime))


def build_research_summary(root=ROOT):
    """Association-only input to the same JS index used by the full workbench."""
    state = _research_state(root)
    # Keep every identity/reference form consumed by buildResearchIndex.forNode.
    # Counts are still selected there; this projection does not duplicate that rule.
    refs = ('id', 'document_id', 'doc_id', 'source_id', 'evidence_id', 'statement_id',
            'answer_id', 'task_id', 'wid', 'object_ids', 'object_id', 'node_id', 'node_ids',
            'subject_id', 'target_object_id', 'question_id', 'question_ids',
            'statement_ids', 'evidence_ids')
    def project(rows, keys):
        return [{key: row[key] for key in keys if key in row} for row in rows]
    return dict(schema_version=1,
                graph=dict(objects=project(state['graph']['objects'],
                    ('id', 'name', 'kind', 'parent', 'system', 'chain', 'stage', 'aliases')),
                    relations=project(state['graph']['relations'],
                    ('id', 'source', 'target', 'type', 'evidence_id', 'evidence_ids'))),
                questions=project(state['questions']['records'], refs + ('text', 'status', 'node', 'variable_class', 'legacy_module')),
                knowledge={key: project(state['knowledge'][key], refs)
                           for key in ('evidence', 'statements', 'answers')},
                tasks=project(state['tasks'], refs),
                reader={key: state['reader'][key] for key in ('status', 'stale', 'received_at')
                        if key in state['reader']})


def summary_for_node(summary, node):
    """节点页的第一问面板：这个节点（含骨架下级）的问题、候选证据、陈述、回答、任务与一跳关系。root 取全部。"""
    if not node or node == 'root':
        return summary
    objects = {o['id']: o for o in summary['graph']['objects']}
    if node not in objects:
        return dict(summary, graph=dict(objects=[], relations=[]), questions=[], tasks=[],
                    knowledge={k: [] for k in summary['knowledge']}, node=node, unknown=True)
    scope = {node}
    changed = True
    while changed:  # 骨架下级：parent 链指向 scope 内任一节点
        changed = False
        for o in summary['graph']['objects']:
            if o['id'] not in scope and o.get('parent') in scope:
                scope.add(o['id']); changed = True
    questions = [q for q in summary['questions'] if q.get('node') in scope or set(q.get('object_ids') or []) & scope]
    qids = {q['id'] for q in questions}
    def touches(row):
        return bool(set(row.get('object_ids') or []) & scope or set(row.get('question_ids') or []) & qids or row.get('question_id') in qids)
    knowledge = {k: [r for r in rows if touches(r)] for k, rows in summary['knowledge'].items()}
    relations = [r for r in summary['graph']['relations'] if r.get('source') == node or r.get('target') == node]
    neighbours = {node} | {r['source'] for r in relations} | {r['target'] for r in relations}
    return dict(summary, node=node, scope=sorted(scope),
                graph=dict(objects=[o for o in summary['graph']['objects'] if o['id'] in neighbours], relations=relations),
                questions=questions, tasks=[t for t in summary['tasks'] if touches(t)], knowledge=knowledge)


def build_snapshot(root=ROOT):
    state = _research_state(root)
    # Legacy metadata is explicitly not proof of reading or source availability.
    for source in read_json(root / 'data/sources.json', {'records': []})['records']:
        state['knowledge']['documents'].append(dict(id='legacy:' + source['source_id'], title=source['title'],
            source_url=source.get('url'), stored_path=source.get('local_file'),
            status='legacy_metadata', acceptance='unverified', coverage={'complete': False},
            object_ids=[], question_ids=[], read_status='unverified'))
    state['catalog'] = build_catalog(root, state['graph'])
    return state


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
        actual = [q['text'] for q in questions['records'] if q.get('origin') == 'legacy-module' and (q.get('legacy_module') or q.get('module_id')) == m['id']]
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
