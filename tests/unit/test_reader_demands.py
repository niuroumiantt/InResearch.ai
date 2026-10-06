import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_continuous_reader as fixtures
from inresearch.paths import project_root
from inresearch.workflow import reader, research_match
from inresearch.materials.artifacts import encoded, read_json
from inresearch.adapters.reader_model import _schema


class ReaderDemandTests(unittest.TestCase):
    def test_new_delivery_can_prioritize_existing_unstarted_reading_without_replacing_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);data=base/'data';paper=base/'report.txt'
            text='GPU server TCO price $100. GPU utilization efficiency goodput.\n'*25
            raw=data/'raw-materials/earlier.txt';raw.parent.mkdir(parents=True);raw.write_text(text)
            paper.write_text(text)
            r=reader.Reader(data,base/'state',project_root(),fixtures.Model(),0,200,fixtures.Clock()).initialize()
            try:
                with r.worker_session():r.scan()
                doc=dict(r.conn.execute('SELECT * FROM current_readings').fetchone())
                frozen=r.stages.artifact_path(doc,'context.json').read_bytes()
                research_match.ingest(paper,data,project_root())
                with r.worker_session():r.scan()
                after=r.doc(doc['doc_id'])
                self.assertGreaterEqual(after['priority'],7)
                self.assertEqual((after['revision_id'],after['recipe']),(doc['revision_id'],doc['recipe']))
                self.assertEqual(r.stages.artifact_path(doc,'context.json').read_bytes(),frozen)
                audit=json.loads(r.conn.execute('SELECT value FROM meta WHERE key=?',('research-demand-priority:'+doc['revision_id'],)).fetchone()[0])
                self.assertEqual(len(audit),1);self.assertTrue(audit[0]['target_ids'])
                self.assertEqual(r.conn.execute('SELECT COUNT(*) FROM reading_runs').fetchone()[0],1)
            finally:r.close()

    def test_matched_gap_prioritizes_full_reading_and_freezes_current_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); data=base/'data'; paper=base/'report.txt'
            paper.write_text('GPU server TCO price $100. GPU utilization efficiency goodput.\n'*25)
            matched=research_match.ingest(paper,data,project_root())
            model=fixtures.Model()
            r=reader.Reader(data,base/'state',project_root(),model,0,200,fixtures.Clock(),full_read_min_priority=7).initialize()
            try:
                with r.worker_session(): r.scan()
                doc=dict(r.conn.execute('SELECT * FROM current_readings').fetchone())
                frozen=r.stages.artifact_path(doc,'context.json').read_bytes()
                context=json.loads(frozen)
                self.assertEqual(context['reading_contract'],'skeleton-demand-v1')
                self.assertTrue(context['research_demands'])
                self.assertGreaterEqual(doc['priority'],7)
                targets={t['id']:t for t in json.loads((project_root()/'framework/tco_targets.json').read_text())['targets']}
                for d in context['research_demands']:
                    self.assertEqual((d['team'],d['variable_class'],d['model_inputs']),
                                     (targets[d['id']]['team'],targets[d['id']]['variable_class'],targets[d['id']]['model_inputs']))
                with patch.object(research_match,'reading_objective',return_value={}):
                    with contextlib.redirect_stdout(io.StringIO()): r.run(once=True)
                done=r.doc(doc['doc_id'])
                self.assertEqual(done['state'],'complete')
                self.assertEqual(done['chunks_read'],done['chunks_total'])
                self.assertEqual(r.stages.artifact_path(doc,'context.json').read_bytes(),frozen)
                self.assertTrue(done['library_rel'].startswith('library/by-node/'))
                self.assertTrue(all(len(encoded(p['allowed_ids']).encode())<=4800 for s,p in model.calls if s in ('triage','read')))
                self.assertEqual(research_match.projection(data)['records'][0]['reading']['state'],'complete')
                self.assertFalse(matched['full_read'])
            finally:r.close()

    def test_unmatched_current_document_keeps_default_priority_and_empty_demands(self):
        with tempfile.TemporaryDirectory() as tmp:
            objective=research_match.reading_objective(tmp,project_root(),'a'*64)
            self.assertEqual(objective['research_demands'],[])
            self.assertEqual(objective['demand_priority'],5)

    def test_current_schema_does_not_require_legacy_module_but_old_recipe_does(self):
        self.assertNotIn('module_id',_schema('triage',True)['properties']['classification']['required'])
        self.assertIn('module_id',_schema('triage')['properties']['classification']['required'])
