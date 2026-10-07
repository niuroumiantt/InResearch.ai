"""Explicit candidate reading, inspection and atomic activation; never C3 adoption."""
from __future__ import annotations
import uuid
from inresearch.materials.artifacts import atomic_json, digest_bytes, encoded, require_text
from inresearch.materials.reader_contracts import Blocked, RECIPE_VERSION
from inresearch.delivery.reader_export import read_report


class ReadingRevisions:
    def __init__(self, catalog, stages, snapshot, chunk_chars, clock, objective=None):
        self.catalog, self.stages, self.snapshot = catalog, stages, snapshot
        self.chunk_chars, self.clock = chunk_chars, clock
        self.objective = objective

    @property
    def conn(self):
        return self.catalog.conn

    def create(self, doc, request_id='initial', base=None, reason='initial full reading', request=None):
        """Caller holds the write transaction. Uncommitted files are never current."""
        context = self.snapshot()
        if self.objective:
            context.update(self.objective(doc['sha256']))
            context['snapshot_hash'] = digest_bytes(encoded({k:v for k,v in context.items() if k!='snapshot_hash'}).encode())
        model = self.stages.model.identity
        # Preserve legacy recipe identities; scope changes get a new frozen recipe.
        pdf_policy = {'pdf_mode': self.stages.pdf_mode} if self.stages.pdf_mode != 'full_visual' else {}
        recipe = digest_bytes(encoded({'version': RECIPE_VERSION, 'model': model,
                                      'chunk_chars': self.chunk_chars, 'snapshot': context['snapshot_hash'], **pdf_policy}).encode())[:24]
        revision = 'rev-' + uuid.uuid4().hex
        run = dict(revision_id=revision,doc_id=doc['doc_id'],base_revision_id=base,
                   request_id=request_id,request_json=encoded(request or {}),reason=reason,
                   recipe=recipe,artifact_rel='artifacts/%s/revisions/%s' % (doc['doc_id'],revision),
                   extracted_rel='extracted/%s/revisions/%s' % (doc['doc_id'],revision),
                   created=self.clock(),updated=self.clock())
        if 'demand_priority' in context:
            run['priority'] = context['demand_priority']
        execution = {**doc, **run}
        atomic_json(self.stages.artifact_path(execution,'context.json'),context)
        atomic_json(self.stages.artifact_path(execution,'recipe.json'),
                    dict(recipe=recipe,version=RECIPE_VERSION,model=model,chunk_chars=self.chunk_chars, **pdf_policy))
        self.catalog.insert_run(run)
        self.catalog.enqueue(run,'extract',self.clock())
        return run

    def request(self, doc_id, expected_current, request_id, reason):
        require_text(request_id,200); require_text(reason,4000); require_text(expected_current,200)
        request = dict(expected_current=expected_current,reason=reason,model=self.stages.model.identity,
                       chunk_chars=self.chunk_chars,version=RECIPE_VERSION)
        if self.stages.pdf_mode != 'full_visual':
            request['pdf_mode'] = self.stages.pdf_mode
        with self.catalog.transaction():
            prior = self.conn.execute('SELECT * FROM reading_runs WHERE doc_id=? AND request_id=?',(doc_id,request_id)).fetchone()
            if prior:
                if prior['request_json'] != encoded(request):
                    raise Blocked('reading_request_key_conflict')
                return {'revision_id':prior['revision_id'],'state':prior['state'],'replayed':True}
            doc = self.catalog.reading(doc_id)
            if doc['current_revision_id'] != expected_current:
                raise Blocked('reading_baseline_conflict')
            if doc['state'] != 'complete':
                raise Blocked('reread_requires_completed_current_result')
            pending = self.conn.execute("SELECT 1 FROM reading_runs WHERE doc_id=? AND base_revision_id IS NOT NULL AND state IN ('queued','running','blocked','failed','ready')",(doc_id,)).fetchone()
            if pending:
                raise Blocked('reading_revision_already_pending')
            run = self.create(doc,request_id,expected_current,reason,request)
            return {'revision_id':run['revision_id'],'state':'queued','replayed':False}

    def restart_unfinished(self, doc_id, expected_revision, request_id, reason):
        """Explicit model migration before the first full result. Retain every attempt."""
        require_text(request_id,200); require_text(reason,4000); require_text(expected_revision,200)
        request = dict(kind='restart_unfinished',expected_revision=expected_revision,reason=reason,
                       model=self.stages.model.identity,chunk_chars=self.chunk_chars,version=RECIPE_VERSION)
        if self.stages.pdf_mode != 'full_visual':
            request['pdf_mode'] = self.stages.pdf_mode
        with self.catalog.transaction():
            prior = self.conn.execute('SELECT * FROM reading_runs WHERE doc_id=? AND request_id=?',(doc_id,request_id)).fetchone()
            if prior:
                if prior['request_json'] != encoded(request):
                    raise Blocked('reading_request_key_conflict')
                return {'revision_id':prior['revision_id'],'state':prior['state'],'replayed':True}
            doc = self.catalog.reading(doc_id)
            if doc['revision_id'] != expected_revision:
                raise Blocked('reading_baseline_conflict')
            if doc['current_revision_id'] or doc['report_rel'] or doc['manifest_sha256']:
                raise Blocked('restart_requires_unfinished_first_reading')
            if doc['state'] not in ('queued','blocked','failed','summarized') or self.conn.execute(
                    "SELECT 1 FROM jobs WHERE doc_id=? AND state='running'",(doc_id,)).fetchone():
                raise Blocked('cannot_restart_running_reading')
            self.conn.execute("UPDATE jobs SET state='cancelled',finished=? WHERE revision_id=? AND state IN ('pending','blocked','failed')",(self.clock(),expected_revision))
            self.conn.execute("UPDATE reading_runs SET state='superseded',updated=? WHERE revision_id=?",(self.clock(),expected_revision))
            run = self.create(doc,request_id,expected_revision,reason,request)
            self.conn.execute('UPDATE reading_runs SET priority=MAX(priority,?) WHERE revision_id=?',(doc['priority'],run['revision_id']))
            self.conn.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('execution_root:'+doc_id,run['revision_id']))
            return {'revision_id':run['revision_id'],'previous_revision_id':expected_revision,'state':'queued','replayed':False}

    def inspect(self, revision_id):
        with self.catalog.read_snapshot():
            row = self.conn.execute('SELECT * FROM execution_readings WHERE revision_id=?',(revision_id,)).fetchone()
            if row is None:
                raise ValueError('unknown reading revision')
            run = dict(row)
            report = self.stages.verify_seal(run) if run['manifest_sha256'] else (read_report(self.stages.data,run) if run['report_rel'] else None)
            return {**run,'current':run['current_revision_id']==revision_id,'report':report,
                    'acceptance':'candidate_only','legacy_unverified':bool(run['report_rel'] and not run['manifest_sha256'])}

    def list(self, doc_id):
        with self.catalog.read_snapshot():
            self.catalog.reading(doc_id)
            return [dict(r) for r in self.conn.execute('SELECT revision_id,base_revision_id,request_id,reason,state,report_rel,report_sha256,review_json,activated,revision_id=current_revision_id AS current FROM execution_readings WHERE doc_id=? ORDER BY created,revision_id',(doc_id,))]

    def activate(self, revision_id, expected_current, report_sha256, reviewer, reason):
        require_text(reviewer,200); require_text(reason,4000); require_text(expected_current,200)
        require_text(report_sha256,64)
        review = encoded(dict(reviewer=reviewer,reason=reason,expected_current=expected_current,
                              report_sha256=report_sha256,kind='reading_quality_review_not_C3'))
        with self.catalog.transaction():
            row = self.conn.execute('SELECT * FROM execution_readings WHERE revision_id=?',(revision_id,)).fetchone()
            if row is None:
                raise ValueError('unknown reading revision')
            run = dict(row)
            if run['current_revision_id'] == revision_id and run['review_json'] == review:
                self.stages.verify_seal(run)
                return {'revision_id':revision_id,'current':True,'replayed':True,'acceptance':'candidate_only'}
            if run['base_revision_id'] != expected_current or run['current_revision_id'] != expected_current:
                raise Blocked('reading_baseline_conflict')
            if run['state'] != 'ready' or run['report_sha256'] != report_sha256:
                raise Blocked('reading_revision_not_reviewed_or_ready')
            self.stages.verify_seal(run)
            cur = self.conn.execute('UPDATE documents SET current_revision_id=? WHERE doc_id=? AND current_revision_id=?',
                                    (revision_id,run['doc_id'],expected_current))
            if cur.rowcount != 1:
                raise Blocked('reading_baseline_conflict')
            self.conn.execute("UPDATE reading_runs SET state='complete',phase='complete',review_json=?,activated=?,updated=? WHERE revision_id=?",(review,self.clock(),self.clock(),revision_id))
            return {'revision_id':revision_id,'previous_revision_id':expected_current,'current':True,'replayed':False,'acceptance':'candidate_only'}

    def reject(self, revision_id, reviewer, reason):
        require_text(reviewer,200); require_text(reason,4000)
        review = encoded(dict(reviewer=reviewer,reason=reason,kind='rejected_reading_candidate'))
        with self.catalog.transaction():
            run = self.conn.execute('SELECT * FROM execution_readings WHERE revision_id=?',(revision_id,)).fetchone()
            if run is None:
                raise ValueError('unknown reading revision')
            if run['state']=='rejected' and run['review_json']==review:
                return {'revision_id':revision_id,'state':'rejected','replayed':True}
            if not run['base_revision_id'] or run['current_revision_id']==revision_id or run['state'] not in ('queued','blocked','failed','ready'):
                raise Blocked('cannot_reject_current_or_running_reading')
            if self.conn.execute("SELECT 1 FROM jobs WHERE revision_id=? AND state='running'",(revision_id,)).fetchone():
                raise Blocked('cannot_reject_current_or_running_reading')
            self.conn.execute("UPDATE jobs SET state='cancelled',finished=? WHERE revision_id=? AND state IN ('pending','blocked','failed')",(self.clock(),revision_id))
            self.conn.execute("UPDATE reading_runs SET state='rejected',review_json=?,updated=? WHERE revision_id=?",(review,self.clock(),revision_id))
            return {'revision_id':revision_id,'state':'rejected','replayed':False}
