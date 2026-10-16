"""Owner-triggered XLSX review: verify native cells before ordinary publication.

Model output is untrusted. Only source-bound, additive registrations can enter
the existing runtime publisher. The employee sees a separate revision task.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from inresearch.adapters.xlsx_document import Workbook, coordinates, matches_value
from inresearch.delivery import source_publication
from inresearch.knowledge import site_timeline
from inresearch.materials import inbox
from inresearch.materials import review_context
from inresearch.storage.files import locked, write_json
from inresearch.workflow import research_tasks, source_statements

TEXT_FIELDS = frozenset({'name', 'status', 'utility', 'power_status', 'notes'})
POWER_FIELDS = frozenset({'capacity_it_mw', 'capacity_facility_mw', 'capacity_planned_it_mw'})
PRIORITIES = frozenset({'P0', 'P1', 'P2'})
PLACEHOLDERS = frozenset({'待查', '待核实', '未披露', '不详', '未知', '暂无', '无', 'n/a', 'na', '-', '--'})
MAX_CANDIDATES = 100
MAX_FINDINGS = 300
MAX_ANALYSIS_BYTES = 1024 * 1024
ANALYSIS_PART_BYTES = 3000
PACKAGE_REGIONS = {
    'dc-census-cn':'中国大陆',
    'dc-census-na':'美国、加拿大',
    'dc-census-eu':'欧洲',
    'dc-census-apac':'亚太（中国大陆除外）',
    'dc-census-em':'中东、非洲、拉美',
    'dc-census-reconcile':'跨区域',
}
MAINLAND_ADMIN = re.compile(
    r'^(?:中国(?:大陆)?|中华人民共和国)?[\s,，/·—-]*'
    r'(?:北京|天津|上海|重庆)市|'
    r'^(?:中国(?:大陆)?|中华人民共和国)?[\s,，/·—-]*'
    r'(?:河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|'
    r'湖北|湖南|广东|海南|四川|贵州|云南|陕西|甘肃|青海)省|'
    r'^(?:中国(?:大陆)?|中华人民共和国)?[\s,，/·—-]*'
    r'(?:内蒙古自治区|广西壮族自治区|西藏自治区|宁夏回族自治区|新疆维吾尔自治区)'
)


def stage_part(payload):
    """Receive a bounded authenticated worker part without weakening edge WAF rules."""
    if not isinstance(payload, dict) or set(payload) != {'id','sha256','analysis_id','index','total','data'}:
        raise ValueError('analysis part required')
    key, sha, analysis_id = payload['id'], payload['sha256'], payload['analysis_id']
    record = inbox.load(key)
    inbox.require_approved(record)
    if (record['sha256'] != sha or record['status'] != 'archived'
            or not record.get('analysis_requested_at') or not re.fullmatch(r'[a-f0-9-]{36}', analysis_id)):
        raise ValueError('approved analysis source required')
    uuid.UUID(analysis_id)
    index, total = payload['index'], payload['total']
    if (type(index) is not int or type(total) is not int or not 0 <= index < total <= 350
            or not isinstance(payload['data'], str) or len(payload['data']) > 4100):
        raise ValueError('analysis part bounds invalid')
    try: chunk = base64.b64decode(payload['data'], validate=True)
    except (ValueError, binascii.Error) as exc: raise ValueError('analysis part encoding invalid') from exc
    if not 0 < len(chunk) <= ANALYSIS_PART_BYTES:
        raise ValueError('analysis part bounds invalid')
    folder = inbox.record_path(key) / 'analysis-parts' / analysis_id
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    part = folder / f'{index:03d}'
    if part.exists():
        if part.read_bytes() != chunk: raise inbox.Conflict('analysis part replay changed')
        return
    staged = folder / (f'.{index:03d}.{uuid.uuid4().hex}.partial')
    try:
        with staged.open('xb') as stream:
            os.chmod(staged, 0o600)
            stream.write(chunk)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(staged, part)
    finally:
        staged.unlink(missing_ok=True)


def read_staged(payload):
    if not isinstance(payload, dict) or set(payload) != {'id','sha256','analysis_id','total','payload_sha256'}:
        raise ValueError('analysis commit required')
    key, sha, analysis_id = payload['id'], payload['sha256'], payload['analysis_id']
    if (not re.fullmatch(r'[a-f0-9-]{36}', analysis_id)
            or not re.fullmatch(r'[a-f0-9]{64}', payload['payload_sha256'])
            or type(payload['total']) is not int or not 1 <= payload['total'] <= 350):
        raise ValueError('analysis commit bounds invalid')
    record = inbox.worker_record(key)
    if record['sha256'] != sha or record['status'] != 'archived' or not record.get('analysis_requested_at'):
        raise ValueError('approved analysis source required')
    folder = inbox.record_path(key) / 'analysis-parts' / analysis_id
    raw = bytearray()
    for index in range(payload['total']):
        chunk = (folder / f'{index:03d}').read_bytes()
        if not 0 < len(chunk) <= ANALYSIS_PART_BYTES: raise ValueError('analysis part bounds invalid')
        raw.extend(chunk)
        if len(raw) > MAX_ANALYSIS_BYTES: raise ValueError('analysis payload too large')
    if hashlib.sha256(raw).hexdigest() != payload['payload_sha256']:
        raise ValueError('analysis payload digest mismatch')
    result = json.loads(raw)
    if any(result.get(k) != payload[k] for k in ('id','sha256','analysis_id')):
        raise ValueError('analysis commit identity mismatch')
    return result


def complete_staged(root, payload):
    return complete(root, read_staged(payload))


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


def _publication_package(root, record):
    """Only the server's current work package can authorize geographic publication."""
    from inresearch.workflow import research_tasks
    package_id = record.get('package_id')
    package = next((row for row in research_tasks.read(root)['packages']
                    if row['id'] == package_id), None)
    if not package or PACKAGE_REGIONS.get(package_id) != package.get('region'):
        raise ValueError('未绑定可核对地理范围的现行工作包；本次只生成修改反馈，不自动上线')
    return package_id


def _require_package_geography(root, record, candidate, existing):
    package_id = _publication_package(root, record)
    site_id = candidate.get('site_id')
    if not site_id:
        if package_id != 'dc-census-cn':
            raise ValueError('新园区所在国家尚不能由当前工作包独立复验；请先补明确国家与地点')
        location = candidate.get('location')
        if (not isinstance(location, str) or not MAINLAND_ADMIN.match(location)
                or re.search(r'香港|澳门|台湾|Hong Kong|Macau|Taiwan', location, re.I)):
            raise ValueError('中国大陆新园区须在原文地点明确省级行政区；不得从工作包名称推定国家')
        return
    row = existing.get(site_id)
    if not row:
        return  # _identity emits the canonical unknown-ID error.
    country, region = row.get('country'), row.get('region')
    allowed = {
        'dc-census-cn': country == 'CN' and region in ('china', 'apac')
                        and not re.search(r'香港|澳门|台湾', str(row.get('location') or '')),
        'dc-census-na': country in ('US', 'CA') and region == 'north-america',
        'dc-census-eu': region == 'europe' and country not in ('CN', 'US', 'CA'),
        'dc-census-apac': region in ('apac', 'india') and country != 'CN',
        'dc-census-em': region in ('mena', 'africa', 'latam') and country != 'MULTI',
        'dc-census-reconcile': isinstance(country, str) and len(country) == 2,
    }[package_id]
    if not allowed:
        raise ValueError('已有园区的登记国家或区域与当前工作包范围不符；请改关联正确工作包')


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
        location = candidate.get('location')
        if (not isinstance(location, str) or not location.strip()
                or location != _native(book, candidate.get('location_locator'))
                or location not in (row.get('location'), row.get('street_address'))):
            raise ValueError('已有园区地点与原文或登记身份不一致')
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


def _employee_task(record, summary, findings, held, published, review_scope=None):
    reconfirmed = sum(row.get('registration_kind') == 'reconfirmation' for row in published)
    lines = [f"本版修改任务书｜{record['name']}",
             f"文件编号：{record['id']}；原件 SHA256：{record['sha256']}",
             '本次评价：'+summary.strip()[:1200],
             f'已自动登记 {len(published)} 条来源陈述，其中 {reconfirmed} 条与原值一致并留下本轮核对记录；以下问题请在下一版修正。']
    if review_scope and review_scope.get('mode') == 'sampled_native_cells':
        lines.append(
            f"审阅范围：原件共 {review_scope['total_nonblank_cells']} 个非空单元格，"
            f"模型仅见 {review_scope['excerpted_cells']} 个定位片段，其中 "
            f"{review_scope['prefix_only_cells']} 个只见前90字；"
            f"{review_scope['not_fully_seen_cells']} 个单元格未完整交给模型。"
            '这是抽样反馈，不是全表验收；本次没有从该工作簿自动上线任何事实，'
            '也不能把未指出的问题视作已通过。')
        lines.append(
            '下一步任务：先按下面列出的定位问题补齐证据；按当前系统工作包尚未完成的园区和字段，'
            '把可核对的内容分成较小的主题材料包。每条列明唯一物理园区名称与省市地点、'
            '字段原值及单位、IT／设施／供电及分期口径、披露或核验时点、来源链接或原件定位。'
            '保留本次原始工作簿与 SHA，不把它重传当作全表已审核；研究端仍须依据最新任务和台账继续审核未覆盖单元格。')
    details = []
    for row in held:
        if row.get('classification') == 'duplicate':
            followup = '无增量重复；无需重交同一原件，请转向当前工作包尚未完成的园区、字段或来源缺口。'
        elif row.get('classification') == 'conflict':
            followup = '冲突待核；请核对两次原始来源、时点、园区与容量口径，说明应保留并列还是发起正式替代。'
        else:
            followup = '请补齐来源、身份或口径后重新提交。'
        details.append(f"P0｜{row.get('locator','未定位')}｜未上线：{row['reason']}。{followup}")
    for priority in ('P0', 'P1', 'P2'):
        rows = [f for f in findings if f['priority'] == priority]
        for f in rows:
            details.append(f"{priority}｜{f['sheet']}!{f['cell']}｜{f['issue']}\n修改：{f['action']}\n验收：{f['acceptance']}")
    footer = ['下一版交付：按当前系统任务重新提交可回查原件；保留稳定园区标识；每个数值注明单位、IT/设施/供电口径、分期、核验或披露时点及原始来源链接或文件定位。',
              '入库验收：原件与单元格可回查，园区身份唯一，来源及时间可追溯，数字不混用口径，与既有值无未解释冲突；未通过条目继续留在待补清单。']
    for index, detail in enumerate(details):
        remaining = len(details)-index-1
        note = f'另有 {remaining} 条超出单份反馈容量；请按工作表或园区拆分，重新上传并确认分析。' if remaining else ''
        if len('\n\n'.join(lines+[detail]+([note] if note else [])+footer)) > 20000:
            lines.append(f'另有 {len(details)-index} 条超出单份反馈容量；请按工作表或园区拆分，重新上传并确认分析。')
            break
        lines.append(detail)
    return '\n\n'.join(lines+footer)


def _codex_model(model):
    return (isinstance(model, dict) and model.get('backend') == 'codex_cli'
            and model.get('requested') == 'gpt-6.1-sol' and model.get('actual') is None
            and model.get('executor') == 'codex-cli'
            and model.get('identity_source') == 'explicit_cli_request_not_provider_reported'
            and all(isinstance(model.get(key), str) and re.fullmatch(r'[a-f0-9]{64}', model[key])
                    for key in ('prompt_sha256', 'input_sha256')))


def _task_provenance(value):
    return (isinstance(value,dict) and set(value)=={'revision','sha256','previous_submission_id'}
            and type(value['revision']) is int and value['revision']>=0
            and isinstance(value['sha256'],str) and re.fullmatch(r'[a-f0-9]{64}',value['sha256'])
            and (value['previous_submission_id'] is None or isinstance(value['previous_submission_id'],str)
                 and re.fullmatch(r'[a-f0-9]{32}',value['previous_submission_id'])))


def _prior_source(row, selected, value):
    """Retain both sides of a held conflict without exposing private archive paths."""
    observation_id = selected.get('observation_id') if isinstance(selected, dict) else None
    observation = next((entry for entry in row.get('observations', [])
                        if entry.get('id') == observation_id), None)
    ref = ((observation.get('adoption') or {}).get('document_refs') or [{}])[0] if observation else {}
    return {'value': value, 'observation_id': observation_id,
            'recorded_at': observation.get('recorded_at') if observation else None,
            'source_sha256': ref.get('source_sha256'), 'source_locator': ref.get('locator'),
            'source_url': ref.get('source_url') if str(ref.get('source_url') or '').startswith(('https://','http://')) else None}


def _analysis_outbox(key, analysis_id):
    return inbox.record_path(key) / 'analysis-outbox' / (analysis_id + '.json')


def _recover_published_outbox(root, payload, input_sha256):
    """Finish a report after a crash between durable publication and feedback."""
    path = _analysis_outbox(payload['id'], payload['analysis_id'])
    if not path.exists():
        return None
    saved = json.loads(path.read_text())
    if saved.get('input_sha256') != input_sha256:
        raise inbox.Conflict('analysis outbox replay changed')
    batch = saved['publication_batch']
    receipt = source_publication.state(root)['receipts'].get(source_publication.digest(batch))
    if receipt is None:
        return None
    from inresearch.knowledge import industry
    published = saved['published']
    for row in published:
        detail = industry.cached_snapshot(root, {'site': row['site_id']}).get('detail')
        if not detail or not any(obs['id'] == row['statement_id'] for obs in detail.get('observations', [])):
            raise inbox.Conflict('published_reader_projection_missing')
    report = dict(saved['report'])
    report['published'] = published
    report['publication'] = receipt
    result = inbox.finish_analysis(payload['id'], payload['sha256'],
                                   payload['analysis_id'], report, saved['employee_task'])
    return {'report': report, 'item': result}


def complete_document(root, payload, record, expected_task=None):
    """Document review produces source-linked tasks, never an automatic fact."""
    key, sha = payload['id'], payload['sha256']
    if (record['sha256'] != sha or not record.get('analysis_requested_at')
            or record['status'] != 'archived' or not inbox.reviewable(record['name'])
            or Path(record['name']).suffix.lower() == '.xlsx'):
        raise ValueError('approved_document_required')
    if (not isinstance(payload['summary'], str) or not payload['summary'].strip()
            or len(payload['summary']) > 4000 or not isinstance(payload['findings'], list)
            or len(payload['findings']) > 25 or payload['candidates'] != []
            or not _codex_model(payload['model'])):
        raise ValueError('bounded_model_analysis_required')
    input_sha256 = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                             allow_nan=False).encode()).hexdigest()
    prior = next((r for r in inbox.load(key).get('analysis_reports', [])
                  if r['id'] == payload['analysis_id']), None)
    if prior:
        if prior['report'].get('input_sha256') != input_sha256:
            raise inbox.Conflict('analysis replay changed')
        return {'report':prior['report'], 'item':inbox.owner_view(inbox.load(key))}
    current_task, _ = review_context.current(root, record)
    if payload.get('task_provenance') != (expected_task or review_context.provenance(current_task)):
        raise inbox.Conflict('analysis_task_context_changed_retry_with_current_task')
    findings=[]
    for row in payload['findings']:
        if (not isinstance(row, dict) or row.get('priority') not in PRIORITIES
                or not isinstance(row.get('locator'), str)
                or not re.fullmatch(r'line:[1-9][0-9]{0,7}', row['locator'])):
            continue
        if all(isinstance(row.get(k), str) and 0 < len(row[k]) <= 700
               for k in ('issue','action','acceptance')):
            findings.append({k:row[k] for k in ('locator','priority','issue','action','acceptance')})
    title = record.get('project_name') or '数据中心园区普查'
    lines = [f"{title}｜下一版任务书｜{record['name']}",
             f"文件编号：{key}；原件 SHA256：{sha}",
             '本次评价：'+payload['summary'][:1200],
             '此类附件本轮形成待核任务，未自动上线事实；需要把可发布信息绑定原件、唯一园区、时点与原文定位。']
    for priority in ('P0','P1','P2'):
        for row in (f for f in findings if f['priority']==priority):
            addition = f"{priority}｜{row['locator']}｜{row['issue']}\n修改：{row['action']}\n验收：{row['acceptance']}"
            if len('\n\n'.join(lines+[addition])) > 18000:break
            lines.append(addition)
    lines.append('下一版交付：保留本次原件及来源链接；逐园区列出原名、地点、分期、明确时点和要登记的字段，并标页/行/表格定位。未知留空，矛盾保留待核。')
    task='\n\n'.join(lines)
    report={'summary':payload['summary'],'model':payload['model'],
            'publication':{'state':'nothing_eligible','new_records':0},
            'published':[],'held':[],'findings':findings,
            'source_sha256':sha,'input_sha256':input_sha256,
            'task_provenance':payload.get('task_provenance'),
            'review_scope':'sampled_extracted_text_no_automatic_publication',
            **({'batch_review':payload['batch_review']} if 'batch_review' in payload else {})}
    result=inbox.finish_analysis(key,sha,payload['analysis_id'],report,task)
    return {'report':report,'item':result}


def complete(root, payload):
    """Serialize task changes while checking and publishing a reviewed proposal."""
    if isinstance(payload,dict) and ('batch_review' in payload
            or inbox.load(payload.get('id','')).get('review_batch_id')):
        raise ValueError('joint_analysis_requires_batch_commit')
    with locked(research_tasks.ledger_path(root)):
        return _complete_with_task_lock(root, payload)


def _complete_with_task_lock(root, payload, *, expected_task=None, expected_source_sha=None):
    """Install eligible rows, verify the reader projection, then append reports."""
    required={'id','sha256','analysis_id','summary','findings','candidates','model'}
    if (not isinstance(payload,dict) or not required <= set(payload)
            or set(payload)-required-{'task_provenance','review_scope','batch_review'}
            or 'task_provenance' in payload and not _task_provenance(payload['task_provenance'])):
        raise ValueError('analysis_payload_required')
    key, sha = payload['id'], payload['sha256']
    if (not isinstance(payload['analysis_id'], str)
            or not re.fullmatch(r'[a-f0-9-]{36}', payload['analysis_id'])):
        raise ValueError('analysis_id_required')
    try:
        uuid.UUID(payload['analysis_id'])
    except ValueError as exc:
        raise ValueError('analysis_id_required') from exc
    record = inbox.worker_record(key)
    if Path(record['name']).suffix.lower() != '.xlsx':
        if 'review_scope' in payload:
            raise ValueError('unexpected_review_scope')
        return complete_document(root, payload, record, expected_task=expected_task)
    if (record['sha256'] != sha or not record.get('analysis_requested_at')
            or record['status'] != 'archived' or Path(record['name']).suffix.lower() != '.xlsx'):
        raise ValueError('approved_xlsx_required')
    if (not isinstance(payload['summary'], str) or not payload['summary'].strip() or len(payload['summary']) > 4000
            or not isinstance(payload['findings'], list) or len(payload['findings']) > MAX_FINDINGS
            or not isinstance(payload['candidates'], list) or len(payload['candidates']) > MAX_CANDIDATES
            or not isinstance(payload['model'], dict)
            or not (
                payload['model'].get('backend') == 'ollama' and payload['model'].get('actual') == 'qwen3.8:27b'
                or _codex_model(payload['model']))):
        raise ValueError('bounded_model_analysis_required')
    input_sha256 = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                             allow_nan=False).encode()).hexdigest()
    prior = next((r for r in inbox.load(key).get('analysis_reports', [])
                  if r['id'] == payload['analysis_id']), None)
    if prior:
        if prior['report'].get('input_sha256') != input_sha256:
            raise inbox.Conflict('analysis replay changed')
        return {'report':prior['report'], 'item':inbox.owner_view(inbox.load(key))}
    recovered = _recover_published_outbox(root, payload, input_sha256)
    if recovered is not None:
        return recovered
    runtime_state = source_publication.state(root)
    if expected_source_sha is not None and source_publication.digest(runtime_state) != expected_source_sha:
        raise inbox.Conflict('analysis_site_context_changed_retry_with_current_task')
    current_task, _ = review_context.current(root, record, runtime=runtime_state)
    expected_task = expected_task or review_context.provenance(current_task)
    if payload.get('task_provenance') != expected_task:
        raise inbox.Conflict('analysis_task_context_changed_retry_with_current_task')
    expected_source_sha = source_publication.digest(runtime_state)
    source_path = inbox.record_path(key) / 'content'
    with tempfile.TemporaryDirectory(prefix='inresearch-task-analysis-') as td:
        native = Path(td) / 'source.xlsx'
        shutil.copyfile(source_path, native)
        book = Workbook(native)
        sampled_scope = None
        if (sum(len(sheet['cells']) for sheet in book.sheets) > 300
                or 'batch_review' in payload and isinstance(payload.get('review_scope'),dict)
                    and payload['review_scope'].get('mode') == 'sampled_native_cells'):
            from inresearch.materials.review_worker import digest_book, digest_scope
            budget = (payload.get('review_scope') or {}).get('excerpt_budget',35000)
            if type(budget) is not int or not 600 <= budget <= 35000:
                raise ValueError('sampled_excerpt_budget_invalid')
            if budget != 35000 and 'batch_review' not in payload:
                raise ValueError('joint_analysis_requires_batch_commit')
            sampled_scope = digest_scope(book, digest_book(book,budget=budget,compact='batch_review' in payload))
            if 'batch_review' in payload: sampled_scope['excerpt_budget'] = budget
            if payload.get('review_scope') != sampled_scope or payload['candidates']:
                raise ValueError('sampled_review_scope_required_no_publication')
            allowed = {(sheet, cell) for sheet, cell in sampled_scope['reviewed_locators']}
            if any(not isinstance(f, dict) or (f.get('sheet'), f.get('cell')) not in allowed
                   for f in payload['findings']):
                raise ValueError('sampled_finding_outside_excerpt')
        elif 'review_scope' in payload:
            raise ValueError('unexpected_review_scope')
        from inresearch.knowledge import site_register
        existing_doc = source_publication.projects(root, runtime=runtime_state)
        existing = {r['site_id']:r for r in existing_doc['records']}
        work = Path(td) / 'checkout'
        (work/'data').mkdir(parents=True)
        write_json(work/'data/projects.json', existing_doc)
        write_json(work/'data/companies.json', source_publication.companies(root, runtime=runtime_state))
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
            existing_source = None
            incoming_source = None
            classification = 'needs_work'
            try:
                if not isinstance(candidate, dict) or locator in seen:
                    raise ValueError('重复或无效的候选单元格')
                seen.add(locator)
                _require_package_geography(root, record, candidate, existing)
                site_id, identity = _identity(book, candidate, existing)
                field = candidate['field']
                value = _candidate_value(book, candidate)
                current_doc = json.loads((work/'data/projects.json').read_text())
                current_row = next((r for r in current_doc['records'] if r['site_id'] == site_id), None)
                registration_kind = 'new'
                if current_row:
                    current = site_timeline.current(current_row)
                    old = current.get('quantity_fields', {}).get(field, current.get(field))
                    selected = current.get('tracking', {}).get('fields', {}).get(field, {})
                    existing_source = _prior_source(current_row, selected, old)
                    incoming_source = {'value': value, 'source_sha256': sha,
                                       'source_locator': locator, 'submission_id': key,
                                       'received_at': created}
                    same_source = [r for r in current_row.get('observations', [])
                                   if r.get('schema_version') == 3 and field in r.get('fields', {})
                                   and any(ref.get('source_sha256') == sha
                                           for ref in r.get('adoption', {}).get('document_refs', []))]
                    if same_source:
                        replay = any(r.get('fields', {}).get(field) == value
                                     and any(ref.get('locator') == locator
                                             and (ref.get('archive') or {}).get('submission_id') == key
                                             for ref in r.get('adoption', {}).get('document_refs', []))
                                     for r in same_source)
                        if not replay:
                            classification = 'duplicate'
                            raise ValueError('同一原件已登记该字段，且没有新的核验依据；请提交新的来源版本或有据可查的复核记录')
                    if old not in (None, '', [], {}):
                        if old == value:
                            registration_kind = 'reconfirmation' if not same_source else 'replay'
                        else:
                            classification = 'conflict'
                            raise ValueError('本次值与当前登记不同；双方原值、来源和时点保留待核，不自动覆盖')
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
                                  'field':field,'locator':locator,'value':value,
                                  'registration_kind':registration_kind})
                latest = json.loads((work/'data/projects.json').read_text())
                latest_row = next(r for r in latest['records'] if r['site_id'] == site_id)
                latest_obs = next(r for r in latest_row['observations'] if r['id'] == receipt['statement_id'])
                installed[-1]['model_checked_at'] = latest_obs['recorded_at']
                existing = {r['site_id']:r for r in latest['records']}
            except (ValueError, TypeError, KeyError, InvalidOperation, IndexError) as exc:
                rejected = {'locator':str(locator or '')[:120],
                            'field':str(candidate.get('field',''))[:60] if isinstance(candidate,dict) else '',
                            'reason':str(exc)[:300], 'classification':classification}
                if existing_source is not None and incoming_source is not None:
                    rejected['existing'] = existing_source
                    rejected['incoming'] = incoming_source
                held.append(rejected)
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
        for row in installed:
            row['url'] = '/project.html?site=' + row['site_id']
        task = _employee_task(record, payload['summary'], findings, held, installed, sampled_scope)
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
            batch = {'version':1,'sites':list(grouped.values()),'objects':{},'records':[]}
            report = {'summary':payload['summary'],'model':payload['model'],
                      'publication':None,'published':installed,'held':held,
                      'findings':findings,'source_sha256':sha,'input_sha256':input_sha256,
                      'task_provenance':payload.get('task_provenance'),
                      **({'review_scope':sampled_scope} if sampled_scope else {}),
                      **({'batch_review':payload['batch_review']} if 'batch_review' in payload else {})}
            write_json(_analysis_outbox(key, payload['analysis_id']),
                       {'input_sha256':input_sha256,'publication_batch':batch,
                        'published':installed,'report':report,'employee_task':task})
            try:
                publication = source_publication.install(root, batch,
                    expected_state_sha=expected_source_sha)
            except ValueError as exc:
                if str(exc) == 'source_publication_context_changed':
                    raise inbox.Conflict('analysis_site_context_changed_retry_with_current_task') from exc
                raise
            from inresearch.knowledge import industry
            for row in installed:
                detail = industry.cached_snapshot(root, {'site':row['site_id']}).get('detail')
                if not detail or not any(o['id'] == row['statement_id'] for o in detail.get('observations', [])):
                    raise ValueError('published_reader_projection_missing')
        else:
            publication = {'state':'nothing_eligible','new_records':0}
        report = {'summary':payload['summary'],'model':payload['model'],
                  'publication':publication,'published':installed,'held':held,
                  'findings':findings,'source_sha256':sha,'input_sha256':input_sha256,
                  'task_provenance':payload.get('task_provenance'),
                  **({'review_scope':sampled_scope} if sampled_scope else {}),
                      **({'batch_review':payload['batch_review']} if 'batch_review' in payload else {})}
        result = inbox.finish_analysis(key, sha, payload['analysis_id'], report, task)
        return {'report':report,'item':result}
