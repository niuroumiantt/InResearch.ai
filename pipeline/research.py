#!/usr/bin/env python3
"""Versioned research registry, evidence validation and derived website snapshot.

Only curated, reviewed answers close questions. Reader output is always a candidate.
No original documents or runtime credentials are served by this module.
"""
import argparse
import copy
import hashlib
import json
import os
import tempfile
import re
from datetime import datetime, timezone
from pathlib import Path

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
        'backend', 'model', 'roots', 'status', 'release')}
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
    return dict(graph=graph, questions=questions, knowledge=knowledge, tasks=tasks, reader=reader)


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
