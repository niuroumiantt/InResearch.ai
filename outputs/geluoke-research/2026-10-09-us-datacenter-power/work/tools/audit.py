from pathlib import Path
import json,hashlib,re
from bs4 import BeautifulSoup
import jsonschema
OUT=Path(__file__).resolve().parents[2]
ROOT=OUT.parents[2]
expected=json.loads((OUT/'work/writing-plan.json').read_text())['body_images']
sources=json.loads((OUT/'sources.json').read_text())['records'];checks=[]
for s in sources:
    if s['status']=='downloaded':
        p=Path(s['raw_file']);assert hashlib.sha256(p.read_bytes()).hexdigest()==s['sha256'],s['id'];checks.append(s['id'])
    elif s['status']=='web_tool_extract':
        p=Path(s['retrieval_artifact']);assert hashlib.sha256(p.read_bytes()).hexdigest()==s['retrieval_artifact_sha256'],s['id'];checks.append(s['id'])
sub=json.loads((OUT/'research/submission.json').read_text());schema=json.loads((ROOT/'data/schema/submission.schema.json').read_text());jsonschema.Draft202012Validator(schema).validate(sub)
for i in sub['items']:assert (OUT/'research'/i['file']).is_file()
claims=json.loads((OUT/'research/claims.json').read_text())['records'];by={s['id']:s for s in sources}
for c in claims:
    s=by[c['source_id']];assert s['status'] in ['downloaded','web_tool_extract'];assert c['quote'].lower() in Path(s.get('extracted_text') or s['retrieval_artifact']).read_text().lower(),c['id']
soup=BeautifulSoup((OUT/'wechat.html').read_text(),'html.parser');assert not soup.select('script,style,link,button,iframe,svg');assert len(soup.select('img'))==1+expected
map_paragraph=next(p for p in soup.select('p') if p.get_text().startswith('图上的三种颜色'))
assert 'font-size:17px;' in map_paragraph['style'],'Map explanation must retain body text size'
assert all(x['src'].startswith(('data:image/png;base64,','data:image/jpeg;base64,')) for x in soup.select('img'))
assert (OUT/'wechat.html').stat().st_size<3.8*1024*1024
for p in (OUT/'assets').glob('fig*.png'):assert p.stat().st_size<1_000_000
assert (OUT/'assets/cover-wechat.jpg').stat().st_size<1_000_000
doc=(OUT/'article.md').read_text();assert len(re.findall(r'^## 第.章',doc,re.M))==6
images=re.findall(r'!\[.*?\]\((.*?)\)',doc);assert len(images)==len(set(images))==expected
for p in images:
    assert (OUT/p).is_file()
    assert (OUT/p).suffix in ['.jpg','.png'] and (OUT/p).stat().st_size<1_000_000
refs=json.loads((OUT/'work/visual-references.json').read_text())['records']
for r in refs:
    assert hashlib.sha256(Path(r['original_file']).read_bytes()).hexdigest()==r['sha256']
    assert r['evidence_role'].startswith('视觉参考')
    # Earlier reference scenes are retained; the current article selects by function.
plan=json.loads((OUT/json.loads((OUT/'work/writing-plan.json').read_text())['figure_plan_path']).read_text())
visual=json.loads((OUT/'work/v3/visual-sources.json').read_text())
assert [f['asset'] for f in plan['figures']]==images
assert [f['number'] for f in plan['figures']]==list(range(1,expected+1))
for f in plan['figures']:
    assert f['question'] and f['review_status']=='reviewed',f['number']
    assert all(by[s]['status'] in ['downloaded','web_tool_extract'] for s in f['source_ids']),f['number']
    text=(OUT/f['editable']).read_text();assert '<text ' in text
    assert f['design_width']==640
first=doc.split('## 第一章')[1].split('\n\n')
assert first[2].startswith('![图1：美国本土的三大异步互联]'),first[:4]
map_text=(OUT/plan['figures'][0]['editable']).read_text()
assert all(s in map_text for s in ['东部互联','西部互联','得州互联','ERCOT','有限直流联络','本土48州','细线为州界'])
assert all(s in (OUT/plan['figures'][4]['editable']).read_text() for s in ['输电与配电成本','合同容量相关付款','2027-01-01','2016年前','12年'])
assert all(s in (OUT/plan['figures'][5]['editable']).read_text() for s in ['1920MW','2042年','2027年','过渡期部分表后'])
assert all(s in (OUT/plan['figures'][6]['editable']).read_text() for s in ['燃料电池','电力转换','AWS','Cologix','2025年批准'])
layout=json.loads((OUT/'checks/v4-svg-layout.json').read_text());assert len(layout)==expected and not any(f['overflow'] for f in layout)
assert hashlib.sha256(Path(visual['generated_original']['file']).read_bytes()).hexdigest()==visual['generated_original']['sha256']
assert len(re.findall(r'^图\d+｜',doc,re.M))==expected
assert re.findall(r'^图(\d+)｜',doc,re.M)==[str(i) for i in range(1,expected+1)]
# Transparent author calculation, independent from industry forecasts.
fixed_energy_twh=100*8760/1_000_000;assert abs(fixed_energy_twh-.876)<1e-12
cash_billion=4.75*10;assert cash_billion==47.5
savings_yi=.95*10;assert savings_yi==9.5
calc={'TWh_to_kWh':1_000_000_000,'176_TWh_to_yi_kWh':1760,'fixed_total_load_MW':100,'hours_per_year':8760,'formula':'100 MW × 8760 h ÷ 1,000,000 = 0.876 TWh','result_TWh':fixed_energy_twh,'waiting_cost_formula':'committed_capital × annual_funding_rate × waiting_months / 12','waiting_cost_scope':'仅资金占用；不自动代表延期净新增损失，须比较现金流','usd_conversions':{'4.75 billion_USD':cash_billion,'0.95 billion_USD':savings_yi}}
(OUT/'calculations.json').write_text(json.dumps(calc,ensure_ascii=False,indent=2))
eia=BeautifulSoup(Path(by['eia-ytd']['raw_file']).read_text(),'html.parser')
prices={}
for row in eia.select('tr'):
    cells=[x.get_text(' ',strip=True) for x in row.select('th,td')]
    if cells and cells[0] in ['Texas','Virginia','Arizona','Georgia','Ohio','Oregon','U.S. Total']:
        prices[cells[0]]=cells
assert len(prices)==7,prices
# The original native table cells are archived, not inferred from adjacent text.
(OUT/'checks/eia-table-rows.json').write_text(json.dumps(prices,ensure_ascii=False,indent=2))
stats=json.loads((OUT/'checks/build.json').read_text());assert 6500<=stats['body_nonspace_characters']<=7700,stats['body_nonspace_characters']
browser=json.loads((OUT/'checks/browser.json').read_text());assert browser['pass']
for mode in ['wechat','full','lite']:assert browser['input_sha256'][mode]==hashlib.sha256((OUT/(mode+'.html')).read_bytes()).hexdigest(),'Browser result must match delivered HTML'
validation={'as_of':'2026-10-09','revision':4,'source_identity_checked':len(checks),'source_attempts':len(sources),'body_images':expected,'visual_originals_checked':len(refs)+1,'figure_plan_and_visible_qualifiers':'pass; machine checks fields, semantic fit reviewed manually','map_geometry':'49 state/DC shapes; overview interconnection split manually reviewed against EIA/ERCOT, not exact utility GIS','candidate_records':len(claims),'material_submissions':len(sub['items']),'submission_schema':'pass','quoted_locators':'pass','original_byte_SHA_and_tool_response_SHA':'pass','wechat_inline_html':'pass','image_interface_limit':'jpg/png; each under 1MB','calculations':'pass','eia_native_rows':'7 saved','browser':'pass','editorial_review':'按紧邻段落逐图核对对象、状态、收费基数与关键标注；手机图目检，非独立第三方终审','not_verified':['微信编辑器实际粘贴/素材上传/发布','全批Reader逐页深读与C3正式采用','正式研究采用与问题关闭','未公开客户合同、项目实测负荷、所有地区最新交期','三大互联精确运营GIS与具体园区接入边界'],'database_state':'本轮未变更正式事实、价格、项目容量或模型；此前23份已接收及Reader注册，11:39:55快照封存1、排队22，详见同期回执'}
(OUT/'checks/validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2));print(json.dumps(validation,ensure_ascii=False))
