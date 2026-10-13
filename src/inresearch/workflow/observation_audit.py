"""Offline coverage/disposition audit; no fetching, dispatch, adoption or publishing."""
import argparse
import hashlib
import html
import json
from pathlib import Path
from urllib.parse import urlsplit
from inresearch.paths import project_root

STATES = {'candidate', 'existing_observation', 'unknown', 'anomaly', 'unread_attachment',
          'not_checked', 'not_applicable', 'excluded'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def checklist(root):
    root=Path(root);doc=read(root/'framework/observation_checklist.json')
    questions={r['id'] for r in read(root/'framework/research_questions.json')['records']}
    model=read(root/'data/datacenter_model.json')['inputs']
    metrics={r['metric_id'] for r in read(root/'framework/metrics.json')['metrics']}
    from inresearch.knowledge.site_timeline import FIELDS
    fields=set(FIELDS)|set(read(root/'data/schema/project.schema.json')['properties'])
    providers={r['id']:r for r in read(root/'framework/supply_contract.json')['providers']}
    if doc.get('schema_version')!=1 or not doc.get('not_a_dispatch_axis') or len(doc['angles'])!=12:
        raise ValueError('observation_checklist_contract')
    seen=set()
    for angle in doc['angles']:
        if angle['id'] in seen or not angle.get('checks') or not angle.get('proposed_fields'):
            raise ValueError('angle_identity_or_requirements')
        seen.add(angle['id'])
        if not angle['question_ids'] or set(angle['question_ids'])-questions:
            raise ValueError('unregistered_question:'+angle['id'])
        if not angle['source_teams'] or set(angle['source_teams'])-providers.keys():
            raise ValueError('unregistered_provider:'+angle['id'])
        if not angle['variable_classes'] or set(angle['variable_classes'])-{1,2,3,4,5}:
            raise ValueError('invalid_variable_class')
        for reference in angle['field_refs']:
            family,key=reference.split(':',1)
            if family not in ('site','model','metric') or key not in {'site':fields,'model':model,'metric':metrics}[family]:
                raise ValueError('unregistered_field:'+reference)
        for check in angle['checks']:
            if check['id'] in seen or check['applies_to']!=['generic_dc','site'] or not check.get('acceptance'):
                raise ValueError('check_identity_or_scope')
            seen.add(check['id'])
        angle['provider_status']={p:providers[p].get('connection','unknown') for p in angle['source_teams']}
    return doc


def template(root, site_id):
    c=checklist(root)
    return {'schema_version':1,'site_id':site_id,'scope':'待填写园区／分期／时点／主体',
            'checklist_version':c['version'],'sources':[],
            'checks':[{'check_id':x['id'],'state':'not_checked','reason':'尚未检查','item_ids':[],'next_action':'确认适用性并查来源'} for a in c['angles'] for x in a['checks']],
            'items':[],'inventory':[],'limitations':['模板不是已检查或采用回执']}


def audit(root, data, verify_files=True):
    c=checklist(root);checks={x['id']:x for a in c['angles'] for x in a['checks']}
    if data.get('schema_version')!=1 or data.get('checklist_version')!=c['version'] or not data.get('scope'):
        raise ValueError('audit_scope_or_version')
    if data['site_id'] not in {r['site_id'] for r in read(Path(root)/'data/projects.json')['records']}:
        raise ValueError('audit_site_identity')
    sources={};items={};coverage={};source_text={}
    for s in data['sources']:
        if s['id'] in sources or not s.get('url') or not s.get('status') or not s.get('reason'):
            raise ValueError('source_identity_state_reason')
        u=urlsplit(s['url'])
        if u.scheme!='https' or not u.hostname or u.username or u.password:
            raise ValueError('source_https_identity_required')
        sources[s['id']]=s
        if s['status']=='checked':
            if not s.get('sha256') or not s.get('path') or not s.get('checked_scope'):
                raise ValueError('checked_source_receipt_required')
            if verify_files and hashlib.sha256(Path(s['path']).read_bytes()).hexdigest()!=s['sha256']:
                raise ValueError('source_bytes_changed:'+s['id'])
            if verify_files:
                text_bytes=Path(s['text_path']).read_bytes()
                if hashlib.sha256(text_bytes).hexdigest()!=s.get('text_sha256'):
                    raise ValueError('source_text_changed:'+s['id'])
                source_text[s['id']]=' '.join(text_bytes.decode('utf-8').split())
        elif s['status'] not in {'unread_attachment','not_checked','anomaly'}:
            raise ValueError('source_status')
    for item in data['items']:
        if item['id'] in items or item['state'] not in STATES or not item.get('reason') or not item.get('destination'):
            raise ValueError('item_identity_disposition')
        if not item.get('check_ids') or set(item['check_ids'])-checks.keys():
            raise ValueError('item_check_mapping')
        source=sources.get(item.get('source_id'))
        if item['state'] in {'candidate','existing_observation','anomaly'}:
            if not source or source['status']!='checked' or not item.get('locator') or not item.get('evidence'):
                raise ValueError('claim_requires_checked_source_locator')
            if verify_files and ' '.join(item['evidence'].split()) not in source_text[source['id']]:
                raise ValueError('source_fragment_missing:'+item['id'])
            if item['state']=='existing_observation':
                project=next(r for r in read(Path(root)/'data/projects.json')['records'] if r['site_id']==data['site_id'])
                if item.get('observation_id') not in {o['id'] for o in project.get('observations',[])}:
                    raise ValueError('existing_observation_missing')
        if item['state'] in {'unknown','not_checked','unread_attachment','anomaly'} and not item.get('next_action'):
            raise ValueError('unresolved_item_requires_next_action')
        items[item['id']]=item
    if not data.get('inventory'):
        raise ValueError('report_inventory_required')
    used=set()
    for unit in data['inventory']:
        if (unit['id'] in used or unit.get('source_id') not in sources or not unit.get('locator')
                or not unit.get('item_ids') or set(unit['item_ids'])-items.keys()):
            raise ValueError('unaccounted_report_unit')
        used.add(unit['id'])
        if any(items[i].get('source_id')!=unit['source_id'] for i in unit['item_ids']):
            raise ValueError('inventory_source_mismatch')
    if set(used)!=set(data.get('required_inventory_ids',[])):
        raise ValueError('report_inventory_manifest_mismatch')
    for row in data['checks']:
        if row['check_id'] in coverage or row['check_id'] not in checks or row['state'] not in STATES or not row.get('reason'):
            raise ValueError('coverage_identity_or_state')
        if set(row.get('item_ids',[]))-items.keys() or not row.get('next_action'):
            raise ValueError('coverage_items_or_next_action')
        if any(row['check_id'] not in items[i]['check_ids'] for i in row.get('item_ids',[])):
            raise ValueError('coverage_item_scope_mismatch')
        if row['state'] in {'candidate','existing_observation'} and not row.get('item_ids'):
            raise ValueError('coverage_without_evidence')
        coverage[row['check_id']]=row
    if set(coverage)!=set(checks):
        raise ValueError('missing_observation_check')
    unresolved=[r['check_id'] for r in coverage.values() if r['state'] in {'unknown','not_checked','anomaly','unread_attachment'}]
    return {'schema_version':1,'site_id':data['site_id'],'scope':data['scope'],'checklist_version':c['version'],
            'checklist_sha256':hashlib.sha256((Path(root)/'framework/observation_checklist.json').read_bytes()).hexdigest(),
            'input_sha256':hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest(),
            'checks_total':len(checks),'angles_total':len(c['angles']),'inventory_units':len(data['inventory']),
            'item_counts':{s:sum(i['state']==s for i in items.values()) for s in sorted(STATES)},
            'unresolved_checks':unresolved,'sources':data['sources'],'inventory':data['inventory'],
            'items':data['items'],'checks':data['checks'],'angles':c['angles'],'limitations':data.get('limitations',[]),
            'disposition_check':'passed_for_declared_inventory','report_exhaustive':'not_certified',
            'source_bytes_verified':verify_files,'formal_adoptions':0,'model_parameters_verified':0,'published':False}


def render(result):
    esc=lambda v:html.escape(str(v))
    labels={'candidate':'候选','existing_observation':'引用已有观察','unknown':'未知','anomaly':'异常待核','unread_attachment':'未读附件','not_checked':'未检查','not_applicable':'不适用','excluded':'排除','checked':'已读取指定范围'}
    label=lambda v:labels.get(v,v)
    source_names={'body':'Abilene正文','timeline':'计算表：Timeline','method':'方法说明','mortenson':'Mortenson工程页','impact':'Crusoe影响报告PDF','permit':'空气许可申请PDF','chip-quantities':'计算表：芯片数量','calculations':'计算表：推导计算','parameters':'计算表：参数','cooling-quantities':'计算表：冷却设备'}
    source_rows=''.join('<tr><td>'+esc(source_names.get(s['id'],s['id']))+'</td><td><a href="'+esc(s['url'])+'">来源</a></td><td>'+esc(label(s['status']))+'</td><td>'+esc(s['reason'])+'</td></tr>' for s in result['sources'])
    sections=[]
    by={r['check_id']:r for r in result['checks']}
    for angle in result['angles']:
        rows=''.join('<tr><td>'+esc(x['question'])+'</td><td>'+esc(label(by[x['id']]['state']))+'</td><td>'+esc(by[x['id']]['reason'])+'</td><td>'+esc(by[x['id']]['next_action'])+'</td></tr>' for x in angle['checks'])
        sections.append('<section><h2>'+esc(angle['label'])+'</h2><p>复用问题：'+esc(', '.join(angle['question_ids']))+'</p><p>复用字段：'+esc(', '.join(angle['field_refs']))+'</p><p>来源责任／登记状态：'+esc(angle['provider_status'])+'</p><div class="scroll"><table><tr><th>检查项</th><th>状态</th><th>依据或缺口</th><th>下一步</th></tr>'+rows+'</table></div></section>')
    items=''.join('<tr><td>'+esc(i['id'])+'</td><td>'+esc(i['label'])+('<details><summary>来源定位与原始内容</summary><pre>'+esc(i.get('source_id','')+' / '+i.get('locator',''))+'\n'+esc(json.dumps(i['native_cells'],ensure_ascii=False,indent=2) if 'native_cells' in i else i.get('evidence',''))+'</pre></details>' if i.get('source_id') else '')+'</td><td>'+esc(label(i['state']))+'</td><td>'+esc(i['reason'])+'</td><td>'+esc(i['destination'])+'</td><td>'+esc(i.get('next_action','审核适用范围'))+'</td></tr>' for i in result['items'])
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Abilene观察覆盖审计</title><style>body{font:16px/1.7 system-ui;max-width:1200px;margin:32px auto;padding:0 16px;color:#20302a;background:#f7f8f5}section{background:white;padding:20px;margin:20px 0;border:1px solid #ccd5cc;border-radius:12px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd;overflow-wrap:anywhere}.scroll{overflow:auto}p{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:650px}h1{font-size:28px}</style><h1>Abilene：十二角度与报告信息去向</h1><p>'+esc(result['angles_total'])+'个观察角度 · '+esc(result['checks_total'])+'条检查 · '+esc(result['inventory_units'])+'个已登记资料单元；下方候选包含表头与参数行，不是同等数量的已审核事实。</p><p>离线审计；未采用新事实、未认证模型参数、未上线。范围：'+esc(result['scope'])+'</p><p>'+esc({label(k):v for k,v in result['item_counts'].items()})+'</p><p>去向检查仅针对显式列入的资料单元，不认证整份报告或附件已穷尽。未知、异常和未读附件保持可见。</p><section><h2>来源版本与读取状态</h2><div class="scroll"><table>'+source_rows+'</table></div></section>'+''.join(sections)+'<section><h2>逐项信息去向</h2><div class="scroll"><table><tr><th>ID</th><th>信息</th><th>状态</th><th>依据或缺口</th><th>去向</th><th>下一步</th></tr>'+items+'</table></div></section><p>'+esc(result['limitations'])+'</p></html>'


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--html',type=Path);p.add_argument('--template-site')
    a=p.parse_args(argv);root=project_root()
    if bool(a.input)==bool(a.template_site):p.error('choose --input or --template-site')
    if a.template_site and a.html:p.error('template has no result HTML')
    data=None if a.template_site else read(a.input)
    protected=[] if data is None else [a.input]+[Path(s[k]) for s in data['sources'] for k in ('path','text_path') if s.get(k)]
    if any(target.resolve()==source.resolve() for target in [a.output]+([a.html] if a.html else []) for source in protected):
        p.error('output must not overwrite input or source originals')
    if a.html and a.html.resolve()==a.output.resolve():p.error('JSON and HTML outputs must differ')
    result=template(root,a.template_site) if a.template_site else audit(root,data)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    if a.html:
        if a.template_site:p.error('template has no result HTML')
        a.html.write_text(render(result))
    print(json.dumps({k:result[k] for k in ('site_id','angles_total','checks_total','inventory_units','item_counts','formal_adoptions','published') if k in result},ensure_ascii=False))
