"""Migration, isolation, provenance and recoverable inference outages."""
import json
import unittest
from unittest import mock
from test_continuous_reader import ReaderTests
from inresearch.materials.reader_contracts import Blocked, Deferred
from inresearch.materials.artifacts import read_json
from inresearch.workflow.reader_scope import DocumentScope
from inresearch.adapters import codex_inference, models


class BatchReaderTests(ReaderTests):
    def scope(self, ids):
        path=self.base/'scope.json'
        path.write_text(json.dumps({'schema_version':1,'doc_ids':ids}))
        self.reader.document_scope=DocumentScope(path,self.reader.data)
        return path

    def test_restart_is_atomic_idempotent_and_preserves_attempts(self):
        self.put();self.reader.scan();old=self.first_doc()
        self.model.identity={**self.model.identity,'model':'new-reading-model'}
        args=(old['doc_id'],old['revision_id'],'batch-switch','explicit model migration')
        new=self.reader.revisions.restart_unfinished(*args)
        self.assertTrue(self.reader.revisions.restart_unfinished(*args)['replayed'])
        self.assertEqual(self.reader.doc(old['doc_id'])['revision_id'],new['revision_id'])
        self.assertIsNone(self.reader.doc(old['doc_id'])['current_revision_id'])
        self.assertEqual(self.reader.doc(old['doc_id'],old['revision_id'])['state'],'superseded')
        self.assertEqual(self.reader.conn.execute('select state from jobs where revision_id=?',(old['revision_id'],)).fetchone()[0],'cancelled')
        self.run_reader()
        final=self.reader.doc(old['doc_id'])
        self.assertEqual(final['state'],'complete')
        self.assertEqual(final['current_revision_id'],new['revision_id'])
        self.assertEqual(read_json(self.reader.data/final['report_rel'])['coverage']['complete'],True)
        self.assertEqual(len(self.reader.revisions.list(old['doc_id'])),2)
        with self.assertRaises(Blocked):
            self.reader.revisions.restart_unfinished(old['doc_id'],new['revision_id'],'late','cannot replace a finished report')

    def test_repeated_unfinished_switch_and_stale_baseline(self):
        self.put();self.reader.scan();old=self.first_doc()
        first=self.reader.revisions.restart_unfinished(old['doc_id'],old['revision_id'],'switch-1','first')
        second=self.reader.revisions.restart_unfinished(old['doc_id'],first['revision_id'],'switch-2','second')
        self.assertEqual(self.reader.doc(old['doc_id'])['revision_id'],second['revision_id'])
        with self.assertRaises(Blocked):
            self.reader.revisions.restart_unfinished(old['doc_id'],old['revision_id'],'switch-3','stale')

    def test_scope_applies_to_every_lane_and_fails_closed(self):
        self.put('included.txt','included evidence');self.put('excluded.txt','excluded evidence')
        self.reader.scan()
        doc=dict(self.reader.conn.execute("select * from current_readings where original_name='included.txt'").fetchone())
        path=self.scope([doc['doc_id']]);self.run_reader()
        self.assertEqual(self.reader.doc(doc['doc_id'])['state'],'complete')
        other=self.reader.conn.execute("select * from current_readings where original_name='excluded.txt'").fetchone()
        self.assertEqual(other['chunks_read'],0)
        self.assertEqual(self.reader.status()['execution_scope']['documents'],1)
        path.write_text('{}')
        with self.assertRaises(ValueError):self.reader.claim()
        self.assertEqual(self.reader.conn.execute("select count(*) from jobs where state='running'").fetchone()[0],0)

    def test_quota_wait_preserves_priority_and_attempt_budget(self):
        self.put();self.reader.scan();job=self.reader.claim();self.reader.process(job)
        job=self.reader.claim();before=self.reader.doc(job['doc_id'])['priority']
        with mock.patch.object(self.reader.stages,'_triage',side_effect=Deferred('model_quota_wait')):
            self.assertEqual(self.reader.process(job),'deferred')
        self.assertEqual(self.reader.doc(job['doc_id'])['priority'],before)
        self.assertEqual(self.reader.conn.execute('select attempts from jobs where job_id=?',(job['job_id'],)).fetchone()[0],0)
        self.assertIsNone(self.reader.claim())
        self.clock.advance(901);self.assertIsNotNone(self.reader.claim())


class CodexTransportTests(unittest.TestCase):
    def test_strict_schema_validates_empty_ids_and_rejects_extra_or_wrong_values(self):
        from inresearch.adapters.reader_model import _schema
        schema=codex_inference.strict_schema(_schema('read'))
        value={'chunk_sha256':'a','claims':[],'object_ids':[],'question_ids':[],'summary':'正文'}
        codex_inference.validate_shape(schema,value)
        for invalid in ({**value,'extra':1},{**value,'claims':None},{**value,'summary':'x'*1201}):
            with self.assertRaises(models.InferenceError):codex_inference.validate_shape(schema,invalid)

    def test_identity_does_not_claim_provider_model_and_effort_is_frozen(self):
        profile=models.ModelProfile(backend='codex_cli',url='',model='gpt-6.1-sol',command='codex',reasoning_effort='medium')
        meta=codex_inference.provenance(profile,'system','material')
        self.assertIsNone(meta['actual']);self.assertEqual(meta['requested'],'gpt-6.1-sol')
        self.assertEqual(models.reading_identity(meta)['reasoning_effort'],'medium')
        with self.assertRaises(ValueError):models.ModelProfile(backend='codex_cli',url='',model='m',api_key_env='KEY')


if __name__=='__main__':unittest.main()
