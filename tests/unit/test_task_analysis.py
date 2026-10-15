"""Explicit consent, native-cell gates, partial publication and private reports."""
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid
from unittest.mock import patch

from inresearch.delivery import source_publication
from inresearch.materials import inbox, task_analysis
from inresearch.paths import project_root
from tests.unit.test_xlsx_document import workbook_bytes


SHEET = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>测试园区甲</t></is></c><c r="B1" t="inlineStr"><is><t>河北省张家口市</t></is></c><c r="C1" t="inlineStr"><is><t>10 MW</t></is></c><c r="D1" t="inlineStr"><is><t>待核实</t></is></c></row></sheetData></worksheet>'


class TaskAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'repo'; (self.root/'data').mkdir(parents=True)
        (self.root/'framework').mkdir()
        (self.root/'data/projects.json').write_text(json.dumps({'records':[]}))
        (self.root/'data/companies.json').write_text(json.dumps({'records':[]}))
        for name in ('storage_contract.json','research_publication.json'):
            shutil.copyfile(project_root()/'framework'/name,self.root/'framework'/name)
        self.runtime = Path(self.temp.name)/'runtime'
        self.intake = Path(self.temp.name)/'intake'
        self.env = patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT':str(self.runtime),
            'INRESEARCH_INTAKE_ROOT':str(self.intake),'INRESEARCH_MATERIAL_APPROVER':'owner'})
        self.env.start(); self.addCleanup(self.env.stop)
        body = workbook_bytes(sheet=SHEET)
        self.item, self.receipt = inbox.receive(io.BytesIO(body),len(body),{'name':'测试.xlsx'},'anonymous',public=True)
        self.base = {'id':self.item['id'],'sha256':self.item['sha256'],'expected_revision':0,
                     'operation_id':str(uuid.uuid4())}

    def candidate(self, value=10):
        locator = lambda cell:f'xlsx:sheet:1:cell:{cell}:context:A1:D1'
        return {'site_id':'','site_name':'测试园区甲','name_locator':locator('A1'),
                'location':'河北省张家口市','location_locator':locator('B1'),
                'field':'capacity_planned_it_mw','value':value,'unit':'MW',
                'unit_locator':'','locator':locator('C1')}

    def payload(self, candidates):
        return {'id':self.item['id'],'sha256':self.item['sha256'],
                'analysis_id':str(uuid.uuid5(uuid.NAMESPACE_URL,'task-analysis:'+self.item['id']+':'+self.item['sha256'])),
                'summary':'一行有明确园区与规划容量，另有来源待补。',
                'findings':[{'sheet':'Forecast 2025e','cell':'D1','priority':'P0',
                    'issue':'来源未核实','action':'补原始公告链接与披露日期','acceptance':'能从原文定位到该容量'}],
                'candidates':candidates,'model':{'actual':'qwen3.8:27b','backend':'ollama'}}

    def _projected(self, root, params):
        row = next((r for r in source_publication.projects(root)['records'] if r['site_id']==params['site']),None)
        return {'detail':{'observations':row['observations']} if row else None}

    def test_only_new_explicit_action_reaches_analysis_queue(self):
        approved = inbox.mutate({**self.base,'action':'approve'},'owner','admin')
        inbox.acknowledge(self.item['id'],self.item['sha256'])
        self.assertEqual(inbox.analysis_pending(),[])
        with self.assertRaisesRegex(ValueError,'approved_xlsx_required'):
            task_analysis.complete(self.root,self.payload([self.candidate()]))
        started = inbox.mutate({'id':self.item['id'],'sha256':self.item['sha256'],
            'expected_revision':2,'operation_id':str(uuid.uuid4()),'action':'start_analysis'},'owner','admin')
        self.assertTrue(started['analysis_requested_at'])
        self.assertEqual(len(inbox.analysis_pending()),1)

    def test_one_native_candidate_publishes_and_report_stays_owner_only(self):
        inbox.mutate({**self.base,'action':'approve_and_analyze'},'owner','admin')
        inbox.acknowledge(self.item['id'],self.item['sha256'])
        with patch('inresearch.knowledge.industry.cached_snapshot',side_effect=self._projected):
            result=task_analysis.complete(self.root,self.payload([self.candidate()]))
        self.assertEqual(result['report']['publication']['new_records'],1)
        self.assertEqual(len(result['report']['published']),1)
        self.assertEqual(len(source_publication.projects(self.root)['records']),1)
        self.assertEqual(inbox.analysis_pending(),[])
        own=inbox.receipt_view(self.item['id'],self.receipt)
        self.assertNotIn('analysis_reports',own)
        self.assertIn('D1',own['feedback'][0]['text'])
        self.assertEqual(len(inbox.snapshot('owner','admin')['items'][0]['analysis_reports']),1)
        with patch('inresearch.knowledge.industry.cached_snapshot',side_effect=self._projected):
            replay=task_analysis.complete(self.root,self.payload([self.candidate()]))
        self.assertEqual(replay['report'],result['report'])
        self.assertEqual(len(inbox.load(self.item['id'])['feedback']),1)

    def test_mismatched_native_value_is_held_without_publication(self):
        inbox.mutate({**self.base,'action':'approve_and_analyze'},'owner','admin')
        inbox.acknowledge(self.item['id'],self.item['sha256'])
        result=task_analysis.complete(self.root,self.payload([self.candidate(11)]))
        self.assertEqual(result['report']['published'],[])
        self.assertEqual(result['report']['publication']['state'],'nothing_eligible')
        self.assertIn('容量单元格',result['report']['held'][0]['reason'])
        self.assertFalse(source_publication.projects(self.root)['records'])

    def test_retry_after_publication_before_report_recovers_without_duplicate(self):
        inbox.mutate({**self.base,'action':'approve_and_analyze'},'owner','admin')
        inbox.acknowledge(self.item['id'],self.item['sha256'])
        with patch('inresearch.knowledge.industry.cached_snapshot',side_effect=self._projected):
            with patch('inresearch.materials.inbox.finish_analysis',side_effect=RuntimeError('simulated crash')):
                with self.assertRaisesRegex(RuntimeError,'simulated crash'):
                    task_analysis.complete(self.root,self.payload([self.candidate()]))
            recovered=task_analysis.complete(self.root,self.payload([self.candidate()]))
        self.assertEqual(len(recovered['report']['published']),1)
        self.assertEqual(len(inbox.load(self.item['id'])['feedback']),1)
        self.assertEqual(len(source_publication.projects(self.root)['records'][0]['observations']),1)


if __name__=='__main__': unittest.main()
