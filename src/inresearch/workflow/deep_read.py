"""L2 use cases. Facts commit first; local completion receipts are replayable.

This workflow accepts explicit paths/dependencies and returns data. Terminal
syntax and presentation belong to interfaces.deep_read; C3 remains separate.
"""
from __future__ import annotations
import copy
import json
import time
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

from inresearch.paths import project_root
from inresearch.materials import paths, triage
from inresearch.materials import reading_policy as policy
from inresearch.materials.artifacts import verified_content
from inresearch.materials.records import current_results, result_revision, commit_result
from inresearch.materials.text_similarity import SimilarityIndex, text_fingerprint, text_sketch
from inresearch.delivery import reading_packet as packet
from inresearch.knowledge import fact_contract, provenance
from inresearch.storage.files import locked, write_json
from inresearch.storage.jsonl import JsonlStore, read_rows
from inresearch.workflow.reading_gaps import ReadingGaps


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


class CompletionPending(OSError):
    def __init__(self, authority):
        self.authority = authority
        super().__init__(authority + '_committed_receipt_pending; replay the same request')


class DeepRead:
    def __init__(self, root=None, state=None, packet_dir=None, materials=None, extractor=None):
        self.root = Path(root) if root is not None else project_root()
        state = Path(state) if state is not None else paths.state()
        self.materials = materials if materials is not None else triage
        self.extractor = extractor if extractor is not None else packet.full_text
        self.facts_path = self.root / 'data/facts.json'
        self.metrics_path = self.root / 'framework/metrics.json'
        self.questions_path = self.root / 'framework/research_questions.json'
        self.read_log = state / 'l2_read.jsonl'
        self.packet_dir = Path(packet_dir) if packet_dir is not None else paths.data() / 'l2'
        self.similarity = SimilarityIndex(state / 'l2_text_md5.jsonl')
        self.gaps = ReadingGaps(self.root / 'data/metric_gaps.jsonl')
        self.cache_remap = self.root / 'docs/inbox/path_migrations/cache_key_remap_20260818.json'
        self.moves_path = state / 'moves.jsonl'

    def load_metrics(self):
        raw = json.loads(self.metrics_path.read_text(encoding='utf-8'))['metrics']
        return {row['metric_id']: row for row in (raw if isinstance(raw, list) else raw.values())}

    def load_questions(self):
        grouped = {}
        for row in json.loads(self.questions_path.read_text(encoding='utf-8'))['records']:
            grouped.setdefault(row.get('module_id'), []).append(row)
        return grouped

    def load_facts(self):
        return json.loads(self.facts_path.read_text(encoding='utf-8'))

    def all_results(self):
        return current_results(self.materials.RESULTS)

    def resolve_document(self, prefix, what='sha', allow_unregistered=True):
        return policy.resolve_document(self.all_results(), prefix, what, allow_unregistered)

    def read_documents(self):
        return {row['sha256'] for row in read_rows(self.read_log)
                if row.get('sha256') and 'twin_of' not in row}

    def twin_documents(self):
        return {row['sha256'] for row in read_rows(self.read_log)
                if row.get('sha256') and 'twin_of' in row}

    def remember_read(self, row, execution=None):
        operation = provenance.digest(row)
        store = JsonlStore(self.read_log)
        with store.locked():
            if any(r.get('operation_id') == operation for r in store.rows()):
                return True
            store.append({**row, 'operation_id': operation, 'at': now(),
                          'execution': execution or {'executor':'unknown','model':'unknown','verification':'unknown'}})
        return False

    def coverage(self):
        metrics = self.load_metrics()
        return Counter(metrics.get(f['metric_id'], {}).get('module') for f in self.load_facts()['records'])

    def eligible(self, min_score=policy.MIN_SCORE, include_read=False, since=0):
        done, covered = self.read_documents(), self.coverage()
        rows = [r for r in self.all_results().values()
                if (r.get('score') or 0) >= min_score and r.get('status') == 'ok'
                and (include_read or r['sha256'] not in done)
                and not policy.admission_problems(r)
                and (not since or policy.document_year(r) >= since)]
        return sorted(rows, key=lambda r: (covered.get(r.get('category'), 0),
                      -(r.get('score') or 0), -policy.document_year(r), r.get('rel', '')))

    def pack(self, sha=None, min_score=policy.MIN_SCORE, again=False, since=0):
        if again and not sha:
            raise ValueError('--again 要跟 --sha：只重开你指名的材料')
        # Resolve against all judgments before filtering eligibility. A second
        # match cannot disappear merely because its score or restriction differs.
        selected = self.resolve_document(sha, allow_unregistered=False)['sha256'] if sha else None
        pool = self.eligible(0 if selected else min_score, include_read=again, since=since)
        if selected:
            pool = [r for r in pool if r['sha256'] == selected]
        if not pool:
            return dict(packed=0, reason='没有符合条件且未读的文件')
        row = pool[0]
        path, from_library = self.materials.readable_path(row)
        with verified_content(path, row['sha256']):
            text, meta = self.extractor(path, row['suffix'])
        if not text.strip():
            return dict(packed=0, sha256=row['sha256'], rel=row.get('rel'), meta=meta, reason='抽不出正文')
        fingerprint, sketch = text_fingerprint(text, meta), text_sketch(text)
        done = self.read_documents()
        twins = self.similarity.same_text(row['sha256'], fingerprint, done, read=True) if fingerprint else []
        opened = self.similarity.same_text(row['sha256'], fingerprint, done, read=False) if fingerprint else []
        near = self.similarity.near_twins(row['sha256'], sketch, done)
        report = packet.publish(self.packet_dir, row, text, meta, self.load_metrics(), self.load_questions(),
                                policy.unattributed(row), result_revision(row), self.materials.MAX_PREVIEW_CHARS)
        if fingerprint:
            self.similarity.remember(row['sha256'], fingerprint, sketch)
        return {**report, 'packed': 1, 'read_from': 'library' if from_library else 'source',
                'text_md5': fingerprint, 'same_text_already_read': twins or None,
                'same_text_packed_not_read': opened or None, 'near_twins': near or None,
                'same_text_note': '提取文本相同；SHA 不同，图表和脚注可能不同；不自动跳读。' if twins or opened else None,
                'near_twin_note': '文本高度重合；须核对图表、脚注和版本，相似度不能证明差异仅是版权页。' if near else None,
                'again': True if again and row['sha256'] in done else None}

    def record(self, incoming, doc=None, partial=False, executor=None, model=None):
        execution = {'executor': executor or 'unknown', 'model': model or 'unknown',
                     'verification': 'client_reported' if executor and model else 'unknown'}
        if any(not isinstance(v, str) or not v.strip() or any(ord(c)<32 for c in v) for v in execution.values()):
            raise ValueError('invalid_execution_attribution')
        if isinstance(incoming, dict):
            incoming = incoming['records'] if 'records' in incoming else incoming['facts'] if 'facts' in incoming else [incoming]
        if not isinstance(incoming, list) or any(not isinstance(f, dict) for f in incoming):
            raise ValueError('facts 必须是事实对象数组，或含 records/facts 数组的对象')
        # Lock order is facts -> L1 results -> completion log. Other L1 writers
        # only take their existing result lock, so an admission change cannot
        # race the fact commit and no second locking convention is introduced.
        with locked(self.facts_path), locked(self.materials.RESULTS):
            ledger = self.all_results()
            doc_sha = policy.resolve_document(ledger, doc, '--doc')['sha256'] if doc else None
            if doc_sha and policy.admission_problems(ledger.get(doc_sha, {})):
                raise ValueError('; '.join(policy.admission_problems(ledger[doc_sha])))
            metrics, store = self.load_metrics(), self.load_facts()
            existing = {f['fact_id']: f for f in store['records']}
            seen, claims = set(existing), fact_contract.index_claims(store['records'])
            accepted, rejected, replayed = [], [], 0
            for fact in incoming:
                malformed = [key for key in ('evidence', 'entity', 'caliber')
                             if key in fact and not isinstance(fact[key], dict)]
                if malformed:
                    rejected.append(dict(fact_id=fact.get('fact_id'), problems=['字段须为对象：' + ', '.join(malformed)]))
                    continue
                sha = (fact.get('evidence') or {}).get('sha256')
                problems = policy.admission_problems(ledger.get(sha, {}))
                if doc_sha and sha != doc_sha:
                    problems.append('evidence.sha256 与 --doc 材料身份不一致')
                if not problems and fact_contract.same_submission(existing.get(fact.get('fact_id')), fact):
                    replayed += 1
                    continue
                problems += fact_contract.check_fact(fact, metrics, seen, claims)
                if problems:
                    rejected.append(dict(fact_id=fact.get('fact_id'), problems=problems))
                    continue
                seen.add(fact['fact_id'])
                fact_contract.index_claim(claims, fact)
                accepted.append(copy.deepcopy(fact))
            report = dict(incoming=len(incoming), accepted=0, rejected=len(rejected),
                          replayed=replayed, facts_total=len(store['records']), problems=rejected)
            if rejected and not partial:
                report['note'] = '默认全有或全无；确认收下通过的那些请加 --partial'
                return report
            disputes = fact_contract.cross_link_disputes(accepted, store['records'])
            if disputes:
                report.update(disputes_pending_a=len(disputes), disputes=disputes)
            if accepted:
                store['records'].extend(accepted)
                store['updated'] = now()[:10]
                write_json(self.facts_path, store)
            report.update(accepted=len(accepted), facts_total=len(store['records']))
            if doc_sha and not rejected:
                try:
                    report['receipt_replayed'] = self.remember_read(dict(sha256=doc_sha,
                        facts=len(incoming), fact_ids=sorted(f['fact_id'] for f in incoming)), execution)
                except OSError as exc:
                    raise CompletionPending('facts') from exc
            if not incoming:
                report['note'] = '解析出 0 条事实；这是人工阅读声明，不证明已读全文。重开用 pack --again --sha。'
            return report

    def attribute(self, sha, *, expected_revision, org=None, unrecoverable=False, year=None, title=None, evidence):
        row = copy.deepcopy(self.resolve_document(sha, allow_unregistered=False))
        if not expected_revision or result_revision(row) != expected_revision:
            raise ValueError('result_revision_conflict')
        if bool(org) == bool(unrecoverable):
            raise ValueError('要么给出 --org，要么用 --unrecoverable；不能都给或都不给')
        if year and not policy.YEAR.fullmatch(year):
            raise ValueError('--year 要是四位数字')
        if not evidence.strip():
            raise ValueError('归属修改须给出原文定位')
        was = {key: row.get(key) for key in ('org', 'year', 'proposed_name')}
        if org: row['org'] = org
        if year: row['year'] = year
        if unrecoverable:
            row['unrecoverable'] = sorted(set(row.get('unrecoverable') or ()) | set(policy.unattributed(row)))
        if title: row.update(title=title, keep_original_name=False)
        row['attributed'] = dict(at=now(), by='l2-full-text', evidence=evidence, was=was)
        row['proposed_name'] = self.materials.proposed_name(row)
        committed = commit_result(self.materials.RESULTS, row, expected_revision)
        return dict(sha256=row['sha256'], org=row.get('org'), year=row.get('year'),
                    unrecoverable=row.get('unrecoverable') or [], was=was['proposed_name'], now=row['proposed_name'],
                    result_revision=committed['result_revision'], renamed_by='改名另走 manage.py organize restage plan / apply')

    def flag(self, sha, *, expected_revision, names, clear=False, evidence):
        row = copy.deepcopy(self.resolve_document(sha, allow_unregistered=False))
        if not expected_revision or result_revision(row) != expected_revision:
            raise ValueError('result_revision_conflict')
        if not names or set(names) - set(policy.RESTRICTIONS) or not evidence.strip():
            raise ValueError('须给出有效限制类型及原文定位')
        was = policy.restricted(row)
        for name in names:
            if clear: row.pop(name, None)
            else: row[name] = True
        row.setdefault('flagged', []).append(dict(at=now(), fields=names, clear=bool(clear), evidence=evidence))
        committed = commit_result(self.materials.RESULTS, row, expected_revision)
        current = policy.restricted(row)
        return dict(sha256=row['sha256'], score=row.get('score'), was=was, now=current,
                    result_revision=committed['result_revision'], reasons=[policy.RESTRICTIONS[n] for n in current],
                    effect='限制事实录入；文件与分数都不变；不改写既有事实' if current else '限制已解除')

    def skip(self, doc, texts, reason=None):
        row = self.resolve_document(doc, '--doc')
        report = self.gaps.propose(row, texts, now())
        try:
            replayed = self.remember_read(dict(sha256=row['sha256'], facts=0,
                         skipped=reason or '菜单没有位置', gaps=sorted(report['gap_ids'])))
        except OSError as exc:
            raise CompletionPending('gaps') from exc
        return dict(**report, skipped=row['sha256'][:16], rel=row.get('rel'), receipt_replayed=replayed,
                    note='缺口补齐后用 gaps --filled，再 pack --again --sha %s 重读' % row['sha256'][:12])

    def backfill_provenance(self, commit=False, expected_plan=None):
        # A plan is recomputed inside the fact lock; it binds both facts and all
        # resolved routes. Raw interior ledger corruption propagates, never hides.
        with locked(self.facts_path), ExitStack() as inputs:
            paths_to_lock = {self.materials.RESULTS, self.moves_path, self.cache_remap,
                             self.root / 'data/sources.json', getattr(self.materials, 'INVENTORY', None)}
            for path in sorted((Path(p) for p in paths_to_lock if p is not None), key=lambda p: str(p.resolve())):
                inputs.enter_context(locked(path))
            store = self.load_facts()
            sources_path = self.root / 'data/sources.json'
            sources = json.loads(sources_path.read_text())['records'] if sources_path.exists() else []
            remap = json.loads(self.cache_remap.read_text()) if self.cache_remap.exists() else {}
            plan = provenance.repair_plan(store, self.all_results(), self.materials.load_inventory(),
                         {row['source_id']: row for row in sources}, remap, list(read_rows(self.moves_path)))
            if commit and (not expected_plan or expected_plan != plan['plan_sha256']):
                raise ValueError('provenance_plan_conflict; inspect a fresh dry run and pass --expected-plan')
            if commit and plan['candidates']:
                index = {f['fact_id']: f for f in store['records']}
                for candidate in plan['candidates']:
                    index[candidate['fact_id']]['evidence']['sha256'] = candidate['sha256']
                store['updated'] = now()[:10]
                write_json(self.facts_path, store)
            return {**plan, 'written': len(plan['candidates']) if commit else 0, 'committed': commit}

    def status(self):
        records = self.load_facts()['records']; metrics = self.load_metrics(); gaps = self.gaps.open()
        return dict(facts=len(records), documents_read=len(self.read_documents()),
                    **{'历史副本行_不计已读': len(self.twin_documents())},
                    metrics_covered=len({f['metric_id'] for f in records}), metrics_total=len(metrics),
                    with_locator=sum(bool((f.get('evidence') or {}).get('locator')) for f in records),
                    with_sha256=sum(bool((f.get('evidence') or {}).get('sha256')) for f in records),
                    value_withheld=sum(f.get('value') is None for f in records),
                    not_corroborated=sum(f.get('corroboration')=='待交叉验证' for f in records),
                    **{'正文指纹_已记': len(self.similarity.fingerprints()),
                       '欠内容哈希的事实': len(provenance.owing_provenance(records)),
                       '菜单缺口_未补': len(gaps), '等菜单补齐后重读': len({r['sha256'] for r in gaps})})
