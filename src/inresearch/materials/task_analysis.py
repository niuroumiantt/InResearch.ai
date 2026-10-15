"""Owner-triggered XLSX review: verify native cells before ordinary publication.

Model output is untrusted. Only source-bound, additive registrations can enter
the existing runtime publisher. The employee sees a separate revision task.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from inresearch.adapters.xlsx_document import Workbook, coordinates, matches_value
from inresearch.delivery import source_publication
from inresearch.knowledge import site_timeline
from inresearch.materials import inbox
from inresearch.storage.files import write_json
from inresearch.workflow import source_statements

TEXT_FIELDS = frozenset({'name', 'status', 'utility', 'power_status', 'notes'})
POWER_FIELDS = frozenset({'capacity_it_mw', 'capacity_facility_mw', 'capacity_planned_it_mw'})
PRIORITIES = frozenset({'P0', 'P1', 'P2'})
PLACEHOLDERS = frozenset({'待查', '待核实', '未披露', '不详', '未知', '暂无', '无', 'n/a', 'na', '-', '--'})
MAX_CANDIDATES = 100
MAX_FINDINGS = 300


def _native(book, locator):
    cell, _ = book.select(locator)
    return cell['value']


def _candidate_value(book, candidate):
    field = candidate['field']
    raw = _native(book, candidate['locator'])
    if field in TEXT_FIELDS:
        value = candidate.get('value')
        if (not isinstance(value, str) or value != raw or not value.strip()
                or value.strip().casefold() in PLACEHOLDERS or len(value) > 2000):
            raise ValueError('原文值不匹配或过长')
        if field == 'status' and value not in {'L'+str(i) for i in range(1, 10)}:
            raise ValueError('阶段须为原文明确的 L1–L9')
        return value
    if field not in POWER_FIELDS:
        raise ValueError('字段不在自动登记白名单')
    number, unit = candidate.get('value'), candidate.get('unit')
    if type(number) not in (int, float) or not 0 <= number <= 100000 or unit not in ('MW', 'GW'):
        raise ValueError('容量数值或单位无效')
    if candidate.get('unit_locator'):
        native_unit = _native(book, candidate['unit_locator'])
        if native_unit not in (unit, {'MW':'兆瓦','GW':'吉瓦'}[unit]):
            raise ValueError('单位单元格与提案不符')
        if not matches_value({'type':'n', 'value':str(raw)}, number):
            raise ValueError('容量数值与原文不符')
    else:
        match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(MW|GW|兆瓦|吉瓦)\s*', str(raw), re.I)
        if not match or Decimal(match[1]) != Decimal(str(number)) or match[2].upper() not in (unit, {'MW':'兆瓦','GW':'吉瓦'}[unit]):
            raise ValueError('容量单元格须同时明示数字和单位')
    return {'value':number, 'unit':unit, 'basis':'原生 Excel 单元格明示，基础登记待查'}


def _identity(book, candidate, existing):
    name = candidate.get('site_name')
    if not isinstance(name, str) or name != _native(book, candidate['name_locator']):
        raise ValueError('园区名称与原文单元格不符')
    site_id = candidate.get('site_id')
    if site_id:
        row = existing.get(site_id)
        if not row or row.get('identity_scope') in ('cluster', 'portfolio') or row.get('duplicate_of'):
            raise ValueError('园区 ID 不存在或不是唯一物理园区')
        if name not in [row['name'], *(row.get('aliases') or [])]:
            raise ValueError('园区名称与已登记身份不符')
        return site_id, None
    location = candidate.get('location')
    if (not isinstance(location, str) or len(location) < 3 or len(location) > 200
            or location != _native(book, candidate['location_locator']) or len(name) < 4):
        raise ValueError('新园区缺少原文明确的名称与地点')
    if re.search(r'集群|园区群|项目群|多站|多个园区|组合', name) or re.search(r'香港|澳门|台湾', location):
        raise ValueError('新园区物理身份或大陆范围不明确')
    site_id = 'cn-upload-' + hashlib.sha256((name+'\0'+location).encode()).hexdigest()[:20]
    identity = {'version':1, 'site_id':site_id, 'name':name, 'native_name':name,
                'country':'CN', 'region':'china', 'location':location,
                'basis':'原生 Excel 名称及地点单元格；唯一物理园区待独立核验'}
    previous = existing.get(site_id)
    if previous:
        if previous.get('identity_registration') != identity:
            raise ValueError('新园区身份与已登记版本冲突')
        return site_id, identity
    if any(name.casefold() == str(r.get('name', '')).casefold() or
           name.casefold() in [str(a).casefold() for a in r.get('aliases', [])]
           for r in existing.values()):
        raise ValueError('与已有园区名称重合，需先核对身份')
    return site_id, identity


def _employee_task(record, summary, findings, held, published):
    lines = [f"本版修改任务书｜{record['name']}",
             f"文件编号：{record['id']}；原件 SHA256：{record['sha256']}",
             '本次评价：'+summary.strip()[:1200],
             f'已自动登记 {len(published)} 条基础信息；以下问题请在下一版修正。']
    details = [f"P0｜{row.get('locator','未定位')}｜未上线：{row['reason']}。请补齐来源、身份或口径后重新提交。"
               for row in held]
    for priority in ('P0', 'P1', 'P2'):
        rows = [f for f in findings if f['priority'] == priority]
        for f in rows:
            details.append(f"{priority}｜{f['sheet']}!{f['cell']}｜{f['issue']}\n修改：{f['action']}\n验收：{f['acceptance']}")
    footer = ['下一版交付：重新上传完整 .xlsx；保留工作表和稳定园区标识；每个数值注明单位、IT/设施/供电口径、分期、时点及原始来源链接或文件定位。',
              '入库验收：原件与单元格可回查，园区身份唯一，来源及时间可追溯，数字不混用口径，与既有值无未解释冲突；未通过条目继续留在待补清单。']
    for index, detail in enumerate(details):
        remaining = len(details)-index-1
        note = f'另有 {remaining} 条超出单份反馈容量；请按工作表或园区拆分，重新上传并确认分析。' if remaining else ''
        if len('\n\n'.join(lines+[detail]+([note] if note else [])+footer)) > 20000:
            lines.append(f'另有 {len(details)-index} 条超出单份反馈容量；请按工作表或园区拆分，重新上传并确认分析。')
            break
        lines.append(detail)
    return '\n\n'.join(lines+footer)


def complete(root, payload):
    """Install eligible rows, verify the reader projection, then append reports."""
    if not isinstance(payload, dict) or set(payload) != {'id','sha256','analysis_id','summary','findings','candidates','model'}:
        raise ValueError('analysis_payload_required')
    key, sha = payload['id'], payload['sha256']
    record = inbox.worker_record(key)
    if (record['sha256'] != sha or not record.get('analysis_requested_at')
            or record['status'] != 'archived' or Path(record['name']).suffix.lower() != '.xlsx'):
        raise ValueError('approved_xlsx_required')
    if (not isinstance(payload['summary'], str) or not payload['summary'].strip() or len(payload['summary']) > 4000
            or not isinstance(payload['findings'], list) or len(payload['findings']) > MAX_FINDINGS
            or not isinstance(payload['candidates'], list) or len(payload['candidates']) > MAX_CANDIDATES
            or not isinstance(payload['model'], dict)
            or payload['model'].get('backend') != 'ollama'
            or payload['model'].get('actual') != 'qwen3.8:27b'):
        raise ValueError('bounded_model_analysis_required')
    input_sha256 = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                             allow_nan=False).encode()).hexdigest()
    prior = next((r for r in inbox.load(key).get('analysis_reports', [])
                  if r['id'] == payload['analysis_id']), None)
    if prior:
        if prior['report'].get('input_sha256') != input_sha256:
            raise inbox.Conflict('analysis replay changed')
        return {'report':prior['report'], 'item':inbox.owner_view(inbox.load(key))}
    source_path = inbox.record_path(key) / 'content'
    with tempfile.TemporaryDirectory(prefix='inresearch-task-analysis-') as td:
        native = Path(td) / 'source.xlsx'
        shutil.copyfile(source_path, native)
        book = Workbook(native)
        from inresearch.knowledge import site_register
        existing_doc = source_publication.projects(root)
        existing = {r['site_id']:r for r in existing_doc['records']}
        work = Path(td) / 'checkout'
        (work/'data').mkdir(parents=True)
        write_json(work/'data/projects.json', existing_doc)
        write_json(work/'data/companies.json', source_publication.companies(root))
        created = datetime.fromtimestamp(record['created'], timezone.utc).isoformat()
        approved = datetime.fromtimestamp(record['approval']['at'], timezone.utc).isoformat()
        archive = {'kind':'approved_task_upload','submission_id':key,'sha256':sha,
                   'received_at':created,'approved_at':approved}
        def resolve(candidate_sha):
            if candidate_sha != sha: raise ValueError('analysis_source_mismatch')
            return native, None, created, archive
        installed, held, seen = [], [], set()
        for candidate in payload['candidates']:
            locator = candidate.get('locator') if isinstance(candidate, dict) else None
            try:
                if not isinstance(candidate, dict) or locator in seen:
                    raise ValueError('重复或无效的候选单元格')
                seen.add(locator)
                site_id, identity = _identity(book, candidate, existing)
                field = candidate['field']
                value = _candidate_value(book, candidate)
                current_doc = json.loads((work/'data/projects.json').read_text())
                current_row = next((r for r in current_doc['records'] if r['site_id'] == site_id), None)
                if current_row:
                    current = site_timeline.current(current_row)
                    old = current.get('quantity_fields', {}).get(field, current.get(field))
                    if old not in (None, '', [], {}):
                        replay = any(r.get('schema_version') == 3 and r.get('fields', {}).get(field) == value
                                     and r.get('registration', {}).get('registered_by') == 'approved-task-analysis'
                                     and any(ref.get('source_sha256') == sha and ref.get('locator') == locator
                                             for ref in r.get('adoption', {}).get('document_refs', []))
                                     for r in current_row.get('observations', []))
                        if not replay:
                            raise ValueError('已有非空值，须先核对冲突或修订，不自动覆盖')
                fields = {field:value}
                if identity is not None:
                    fields['name'] = identity['name']
                statement = {'version':1,'site_id':site_id,'fields':fields,
                    'source':{'sha256':sha,'published_at':None,'locator':locator},
                    'effective_at':None,'kind':'reported','scope':'whole_site',
                    'basis':'员工 Excel 原生单元格；基础登记待查',
                    'registered_by':'approved-task-analysis'}
                if identity is not None: statement['identity'] = identity
                receipt = source_statements.apply(work, Path(td), statement, resolve=resolve)
                installed.append({'site_id':site_id,'statement_id':receipt['statement_id'],
                                  'field':field,'locator':locator,'value':value})
                latest = json.loads((work/'data/projects.json').read_text())
                existing = {r['site_id']:r for r in latest['records']}
            except (ValueError, TypeError, KeyError, InvalidOperation, IndexError) as exc:
                held.append({'locator':str(locator or '')[:120], 'field':str(candidate.get('field',''))[:60] if isinstance(candidate,dict) else '',
                             'reason':str(exc)[:300]})
        grouped = {}
        final_doc = json.loads((work/'data/projects.json').read_text())
        initial_ids = {r['site_id'] for r in existing_doc['records']}
        for row in installed:
            site_id = row['site_id']
            source_row = next(r for r in final_doc['records'] if r['site_id'] == site_id)
            obs = next(r for r in source_row['observations'] if r['id'] == row['statement_id'])
            entry = grouped.setdefault(site_id, {'site_id':site_id,
                'baseline':({k:v for k,v in source_row.items() if k != 'observations'} if site_id not in initial_ids else None),
                'observations':[]})
            if not any(v['id'] == obs['id'] for v in entry['observations']): entry['observations'].append(obs)
        if grouped:
            publication = source_publication.install(root, {'version':1,'sites':list(grouped.values()),
                                                             'objects':{},'records':[]})
            from inresearch.knowledge import industry
            for row in installed:
                detail = industry.cached_snapshot(root, {'site':row['site_id']}).get('detail')
                if not detail or not any(o['id'] == row['statement_id'] for o in detail.get('observations', [])):
                    raise ValueError('published_reader_projection_missing')
                row['url'] = '/project.html?site=' + row['site_id']
        else:
            publication = {'state':'nothing_eligible','new_records':0}
        findings = []
        for f in payload['findings']:
            if not isinstance(f, dict) or not {'sheet','cell','priority','issue','action','acceptance'} <= set(f):
                continue
            if f['priority'] not in PRIORITIES or any(not isinstance(f[k],str) or not f[k].strip() or len(f[k]) > 700
                    for k in ('sheet','cell','issue','action','acceptance')):
                continue
            try: coordinates(f['cell'])
            except ValueError: continue
            if f['sheet'] not in [s['name'] for s in book.sheets]: continue
            findings.append({k:f[k] for k in ('sheet','cell','priority','issue','action','acceptance')})
        task = _employee_task(record, payload['summary'], findings, held, installed)
        report = {'summary':payload['summary'],'model':payload['model'],
                  'publication':publication,'published':installed,'held':held,
                  'findings':findings,'source_sha256':sha,'input_sha256':input_sha256}
        result = inbox.finish_analysis(key, sha, payload['analysis_id'], report, task)
        return {'report':report,'item':result}
