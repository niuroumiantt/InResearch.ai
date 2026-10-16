"""Lossless native campus packets, explicit rereview, pilot gates and source-bound publishing."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZipFile

from inresearch.adapters.xlsx_document import Workbook
from inresearch.delivery import source_publication
from inresearch.materials import inbox, native_review_contract as contract, review_context, review_worker, task_analysis
from inresearch.paths import project_root


def campus_workbook(*, duplicate=False):
    layout = contract.LAYOUTS['mainland-register-v6']
    additions = {
        '1-地点与身份': {'A2':'P-001','B2':'测试园区甲','D2':'河北省','E2':'张家口市',
                      'G2':'河北省张家口市','T2':'S-001','A3':'P-002','B3':'测试园区乙',
                      'D3':'贵州省','G3':'贵州省贵阳市','T3':'S-001'},
        '4-容量口径与分期': {'A2':'P-001','B2':'测试园区甲','C2':'10 MW','L2':'S-001',
                         'A3':'P-002','B3':'测试园区乙','C3':'20 MW','L3':'S-001'},
        '7-时间运行与证据': {'A2':'P-001','B2':'测试园区甲','D2':'长原文甲乙丙丁'*400},
        '9-来源登记表': {'A2':'S-001','B2':'可回查官方原件','F2':'https://example.invalid/source'},
        '12-对象关系与计数资格': {'A2':'P-001','B2':'测试园区甲','C2':'园区（总园区）','F2':'计入1次',
                           'A3':'P-002','B3':'测试园区乙','C3':'园区（总园区）','F3':'计入1次'},
        '15-进度说明': {f'A{n}':'未归属说明'+str(n) for n in range(2, 340)},
    }
    if duplicate: additions['1-地点与身份'].update(A4='P-001', B4='冲突园区名')
    stream = io.BytesIO(); ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with ZipFile(stream, 'w') as archive:
        names = list(layout['sheets'])
        archive.writestr('xl/workbook.xml', '<workbook xmlns="'+ns+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="r{i}"/>' for i, name in enumerate(names, 1))+'</sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships>'+''.join(
            f'<Relationship Id="r{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(names)+1))+'</Relationships>')
        for index, name in enumerate(names, 1):
            cells = {**layout['sheets'][name].get('headers', {}), **additions.get(name, {})}
            xml = ''.join(f'<row r="{contract.coordinates(address)[1]}"><c r="{address}" t="inlineStr"><is><t>{escape(value)}</t></is></c></row>'
                          for address, value in cells.items())
            if name == '15-进度说明': xml += '<row r="340"><c r="B340"><f>1+2</f><v>3</v></c></row>'
            archive.writestr(f'xl/worksheets/sheet{index}.xml','<worksheet xmlns="'+ns+'"><sheetData>'+xml+'</sheetData></worksheet>')
    return stream.getvalue()


MODEL = {'backend':'ollama','requested':'qwen3.8:27b','actual':'qwen3.8:27b',
         'input_sha256':'b'*64,'prompt_sha256':'a'*64}


def windows(packet):
    fragments = []
    for cell in packet['cells']:
        text = '' if cell['value'] is None else str(cell['value'])
        # Exercise Unicode slicing and lossless multiwindow long-cell coverage.
        cuts = [0, len(text)] if len(text) < 1000 else [0, 900, len(text)]
        for start, end in zip(cuts, cuts[1:]):
            fragments.append({'locator':cell['locator'],'start':start,'end':end,
                              'value_sha256':hashlib.sha256(text[start:end].encode()).hexdigest()})
    return [{'fragments':fragments,'input_sha256':MODEL['input_sha256'],'model':dict(MODEL)}]


class FullNativeReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        home = Path(self.temp.name); self.root = home/'repo'; (self.root/'data').mkdir(parents=True)
        (self.root/'framework').mkdir()
        for name in ('storage_contract.json','research_publication.json','research_task_plan.json'):
            shutil.copyfile(project_root()/'framework'/name,self.root/'framework'/name)
        (self.root/'data/projects.json').write_text('{"records":[]}')
        (self.root/'data/companies.json').write_text('{"records":[]}')
        env = patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT':str(home/'runtime'),
            'INRESEARCH_INTAKE_ROOT':str(home/'intake'),'INRESEARCH_MATERIAL_APPROVER':'owner'})
        env.start(); self.addCleanup(env.stop)
        self.raw = campus_workbook(); self.path = home/'source.xlsx'; self.path.write_bytes(self.raw)
        self.book = Workbook(self.path); self.sha = hashlib.sha256(self.raw).hexdigest()
        self.manifest = contract.build_manifest(self.book, self.sha)
        self.campus = next(row for row in self.manifest['packets'] if row['campus_key']=='P-001')
        self.item, _ = inbox.receive(io.BytesIO(self.raw),len(self.raw),
            {'name':'全表.xlsx','submitter':'员工','project_name':'园区原件','package_id':'dc-census-cn'},'anonymous',public=True)
        inbox.mutate(self.request('approve_and_analyze'),'owner','admin')
        inbox.acknowledge(self.item['id'], self.sha)

    def request(self, action, **extra):
        record = inbox.load(self.item['id'])
        return {'id':self.item['id'],'sha256':self.sha,'expected_revision':record['revision'],
                'operation_id':str(uuid.uuid4()),'action':action,**extra}

    def old_sample(self):
        task, _ = review_context.current(self.root, inbox.load(self.item['id']))
        payload = {'id':self.item['id'],'sha256':self.sha,'analysis_id':str(uuid.uuid4()),
            'summary':'旧抽样反馈保留','findings':[],'candidates':[],'model':dict(MODEL),
            'task_provenance':review_context.provenance(task),
            'review_scope':review_worker.digest_scope(self.book, review_worker.digest_book(self.book))}
        return task_analysis.complete(self.root, payload)

    def start(self):
        self.old_sample()
        request = self.request('start_full_analysis',layout_id=self.manifest['layout_id'],
                               reason='完整研究既有批准原件，保留旧样本报告',pilot_package_id=self.campus['package_id'])
        inbox.mutate(request,'owner','admin')
        return request

    def payload(self, packet=None, candidates=True):
        packet = packet or self.campus
        record = inbox.load(self.item['id']); task, _ = review_context.current(self.root, record)
        provenance = review_context.provenance(task); attempt = record['full_analysis']['attempt_id']
        find = lambda sheet, cell: next(row['locator'] for row in packet['cells'] if row['sheet']==sheet and row['cell']==cell)
        candidate = {'site_id':'','site_name':'测试园区甲','name_locator':find('1-地点与身份','B2'),
            'location':'河北省张家口市','location_locator':find('1-地点与身份','G2'),
            'field':'capacity_planned_it_mw','value':10,'unit':'MW','unit_locator':'',
            'locator':find('4-容量口径与分期','C2')} if candidates else None
        return {'id':self.item['id'],'sha256':self.sha,
            'analysis_id':contract.analysis_id(attempt,packet['package_id'],provenance['sha256']),
            'summary':'完整包已逐格覆盖，缺失原始披露时间仍待补','findings':[],
            'candidates':[candidate] if candidate else [],'model':dict(MODEL),
            'task_provenance':provenance,'review_scope':contract.make_scope(self.manifest,packet,attempt,provenance['sha256']),
            'review_windows':windows(packet),
            'campus_adjudication':{'model':dict(MODEL),'input_sha256':MODEL['input_sha256'],
                                   'candidate_sha256':contract.digest([candidate] if candidate else [])}}

    def projected(self, root, params):
        row = next((r for r in source_publication.projects(root)['records'] if r['site_id']==params['site']),None)
        return {'detail':{'observations':row['observations']} if row else None}

    def test_manifest_joins_native_ids_preserves_long_values_and_covers_every_cell_once(self):
        self.assertEqual(self.manifest['layout_id'],'mainland-register-v6')
        self.assertTrue(any(row['sheet']=='9-来源登记表' and row['cell']=='F2' for row in self.campus['cells']))
        self.assertTrue(any(len(str(row['value']))>2000 for row in self.campus['cells']))
        owned = [locator for packet in self.manifest['packets'] for locator in packet['owned_locators']]
        self.assertEqual(len(owned), len(set(owned)))
        self.assertEqual(len(owned),self.manifest['total_nonblank_cells'])
        self.assertTrue(any(cell['formula'] for packet in self.manifest['packets'] for cell in packet['cells']))

    def test_changed_layout_or_duplicate_identity_fails_closed_without_losing_rows(self):
        self.book.sheets[2]['cells']['A1']['value']='新列身份'
        with self.assertRaisesRegex(ValueError,'layout_unknown'):contract.build_manifest(self.book,self.sha)
        self.path.write_bytes(campus_workbook(duplicate=True))
        raw=self.path.read_bytes(); manifest=contract.build_manifest(Workbook(self.path),hashlib.sha256(raw).hexdigest())
        self.assertNotIn('P-001',[row['campus_key'] for row in manifest['packets'] if row['kind']=='campus'])
        self.assertEqual(sum(len(row['owned_locators']) for row in manifest['packets']),manifest['total_nonblank_cells'])

    def test_basic_identity_gate_keeps_child_or_ambiguous_objects_out(self):
        self.assertTrue(self.campus['identity_eligible'])
        original=copy.deepcopy(self.book.sheets)
        for sheet_name, address, value in (
                ('12-对象关系与计数资格','C2','楼栋（单体内）'),
                ('12-对象关系与计数资格','D2','PARENT-001（待建）'),
                ('12-对象关系与计数资格','F2','计入1次（范围待核）'),
                ('1-地点与身份','G2','河北省张家口市租用园区2#与3#楼')):
            self.book.sheets=copy.deepcopy(original)
            sheet=next(row for row in self.book.sheets if row['name']==sheet_name)
            sheet['cells'][address]={'cell':address,'value':value,'type':'inlineStr','formula':None,'style':None}
            manifest=contract.build_manifest(self.book,self.sha)
            packet=next(row for row in manifest['packets'] if row['campus_key']=='P-001')
            self.assertFalse(packet['identity_eligible'])
            self.assertTrue(packet['identity_reason'])

    def test_explicit_rereview_preserves_old_report_and_releases_only_pilot(self):
        request=self.start(); record=inbox.load(self.item['id'])
        self.assertEqual(len(record['analysis_reports']),1)
        self.assertEqual(record['analysis_reports'][0]['report']['review_scope']['mode'],'sampled_native_cells')
        self.assertEqual(record['full_analysis']['available_package_ids'],[self.campus['package_id']])
        self.assertEqual(len(inbox.analysis_pending()),1)
        self.assertEqual(inbox.mutate(request,'owner','admin')['full_analysis']['attempt_id'],request['operation_id'])
        with self.assertRaises(PermissionError):inbox.mutate(request,'another-admin','admin')

    def test_full_package_cannot_claim_unseen_long_tail_or_wrong_model(self):
        self.start(); original=self.payload()
        for kind in ('missing_tail','bad_hash','wrong_model'):
            payload=copy.deepcopy(original)
            fragments=payload['review_windows'][0]['fragments']
            if kind=='missing_tail':fragments.pop(next(i for i,row in enumerate(fragments) if row['start']==900))
            elif kind=='bad_hash':fragments[0]['value_sha256']='0'*64
            else:payload['review_windows'][0]['model']['actual']='other-model'
            with self.assertRaisesRegex(ValueError,'native_review_'):task_analysis.complete(self.root,payload)
        self.assertEqual(len(inbox.load(self.item['id'])['analysis_reports']),1)
        self.assertFalse(source_publication.projects(self.root)['records'])

    def test_full_package_requires_candidate_bound_campus_adjudication(self):
        self.start()
        for kind in ('missing','wrong_candidate','wrong_model','wrong_input','wrong_final'):
            payload=self.payload()
            if kind=='missing':payload.pop('campus_adjudication')
            elif kind=='wrong_candidate':payload['campus_adjudication']['candidate_sha256']='0'*64
            elif kind=='wrong_model':payload['campus_adjudication']['model']['actual']='other-model'
            elif kind=='wrong_input':payload['campus_adjudication']['input_sha256']='0'*64
            else:payload['model']['input_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'native_review_campus_adjudication'):
                task_analysis.complete(self.root,payload)
        self.assertEqual(len(inbox.load(self.item['id'])['analysis_reports']),1)
        self.assertFalse(source_publication.projects(self.root)['records'])

    def test_full_window_progress_survives_old_reports_without_granting_coverage(self):
        self.start();record=inbox.load(self.item['id'])
        attempt=record['full_analysis']
        payload={'id':self.item['id'],'sha256':self.sha,'attempt_id':attempt['attempt_id'],
                 'package_id':self.campus['package_id'],'window_completed':250,'window_total':300,
                 'state':'reading','reason':'完整长单元格窗口已保存'}
        updated=inbox.set_full_analysis_progress(payload)
        progress=updated['analysis_progress']
        self.assertEqual((progress['window_completed'],progress['window_total']),(250,300))
        self.assertEqual((progress['completed'],progress['covered_cells']),(0,0))
        self.assertEqual(updated['full_analysis'],attempt)
        self.assertEqual(updated['analysis_scope']['completed_packages'],0)
        for change in ({'attempt_id':str(uuid.uuid4())}, {'package_id':'0'*64}):
            with self.assertRaises(PermissionError):inbox.set_full_analysis_progress({**payload,**change})
        for change in ({'completed':1}, {'covered_cells':1000}, {'window_total':2001}, {'reason':'x'*501}):
            with self.assertRaises(ValueError):inbox.set_full_analysis_progress({**payload,**change})
        with self.assertRaises(PermissionError):inbox.set_analysis_progress(self.item['id'],self.sha,1,1)
        task_analysis.complete(self.root,self.payload(candidates=False))
        with self.assertRaises(PermissionError):inbox.set_full_analysis_progress(payload)

    def test_old_sample_cannot_replace_full_attempt_or_publish_candidates(self):
        self.start()
        payload=self.payload();payload['analysis_id']=str(uuid.uuid4())
        payload.pop('review_windows');payload.pop('campus_adjudication')
        payload['review_scope']=review_worker.digest_scope(self.book,review_worker.digest_book(self.book))
        with self.assertRaisesRegex(inbox.Conflict,'explicit_full_review_attempt_required'):
            task_analysis.complete(self.root,payload)
        self.assertEqual(inbox.load(self.item['id'])['analysis_state'],'running')

    def test_full_findings_preserve_specific_fetch_task_and_acceptance(self):
        self.start();payload=self.payload(candidates=False)
        payload['findings']=[{'sheet':'1-地点与身份','cell':'G2','priority':'P0',
            'issue':'地址只有市级，缺少可验证地块范围',
            'action':'继续查张家口市自然资源部门土地出让公告；检索测试园区甲及建设单位，取得宗地编号和界址原图。',
            'acceptance':'提供公告原始URL、发布日期、宗地编号、园区名称和原件页码，能够对应同一物理园区。'}]
        result=task_analysis.complete(self.root,payload)
        self.assertEqual(result['report']['findings'],payload['findings'])
        self.assertIn('土地出让公告',result['item']['feedback'][-1]['text'])
        self.assertIn('宗地编号',result['item']['feedback'][-1]['text'])

    def test_outside_package_identity_or_findings_are_rejected(self):
        self.start()
        payload=self.payload();payload['candidates'][0]['name_locator']=payload['candidates'][0]['locator']
        with self.assertRaisesRegex(ValueError,'identity_outside'):task_analysis.complete(self.root,payload)
        payload=self.payload();payload['findings']=[{'sheet':'1-地点与身份','cell':'B3','priority':'P0','issue':'跨园区','action':'补证','acceptance':'核实'}]
        with self.assertRaisesRegex(ValueError,'finding_outside'):task_analysis.complete(self.root,payload)

    def test_scope_task_and_unreleased_package_changes_cannot_publish(self):
        self.start();payload=self.payload();payload['review_scope']['cells_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'scope_mismatch'):task_analysis.complete(self.root,payload)
        other=next(row for row in self.manifest['packets'] if row['campus_key']=='P-002')
        with self.assertRaisesRegex(ValueError,'not_released'):task_analysis.complete(self.root,self.payload(other,candidates=False))
        payload=self.payload();payload['task_provenance']['sha256']='0'*64
        with self.assertRaisesRegex(inbox.Conflict,'task_context_changed'):task_analysis.complete(self.root,payload)

    def test_original_checksum_change_blocks_full_review(self):
        self.start();payload=self.payload()
        (inbox.record_path(self.item['id'])/'content').write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError,'原件内容已变化'):task_analysis.complete(self.root,payload)

    def test_pilot_publication_pause_resume_and_whole_source_completion(self):
        self.start(); payload=self.payload()
        with patch('inresearch.knowledge.industry.cached_snapshot',side_effect=self.projected):
            result=task_analysis.complete(self.root,payload)
            replay=task_analysis.complete(self.root,payload)
        self.assertEqual(replay['report'],result['report'])
        self.assertEqual(len(result['report']['published']),1)
        self.assertEqual(inbox.load(self.item['id'])['full_analysis']['state'],'pilot_completed')
        self.assertEqual(inbox.analysis_pending(),[])
        continuation=self.request('continue_full_analysis',attempt_id=inbox.load(self.item['id'])['full_analysis']['attempt_id'],
                                  reason='已复核试点实际项目投影与反馈回执')
        inbox.mutate(continuation,'owner','admin')
        self.assertEqual(len(inbox.analysis_pending()),1)
        for packet in self.manifest['packets']:
            if packet['package_id']==self.campus['package_id']:continue
            task_analysis.complete(self.root,self.payload(packet,candidates=False))
        record=inbox.load(self.item['id'])
        self.assertEqual(record['full_analysis']['state'],'completed')
        self.assertEqual(record['full_analysis']['covered_cells'],self.manifest['total_nonblank_cells'])
        self.assertEqual(len(record['analysis_reports']),1+len(self.manifest['packets']))
        self.assertEqual(inbox.analysis_pending(),[])

    def test_full_native_mismatch_is_held_without_weakening_original_value_gate(self):
        self.start();payload=self.payload();payload['candidates'][0]['value']=11
        payload['campus_adjudication']['candidate_sha256']=contract.digest(payload['candidates'])
        result=task_analysis.complete(self.root,payload)
        self.assertEqual(result['report']['published'],[])
        self.assertIn('容量单元格',result['report']['held'][0]['reason'])

    def test_publication_crash_recovers_same_package_without_double_coverage(self):
        self.start();payload=self.payload()
        with patch('inresearch.knowledge.industry.cached_snapshot',side_effect=self.projected):
            with patch.object(inbox,'finish_analysis',side_effect=RuntimeError('crash')):
                with self.assertRaises(RuntimeError):task_analysis.complete(self.root,payload)
            result=task_analysis.complete(self.root,payload)
        self.assertEqual(len(result['report']['published']),1)
        record=inbox.load(self.item['id'])
        self.assertEqual(record['full_analysis']['completed_package_ids'],[self.campus['package_id']])
        self.assertEqual(len(source_publication.projects(self.root)['records']),1)


if __name__ == '__main__': unittest.main()
