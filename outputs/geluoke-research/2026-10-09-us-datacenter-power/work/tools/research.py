"""Build a traceable candidate intake, preserving original bytes outside Git.
Not a database adoption tool. The submission is validated by the real intake CLI.
"""
from pathlib import Path
import hashlib,json,re,shutil
OUT=Path(__file__).resolve().parents[2]
RAW=Path('/Users/m5/.local/share/inresearch.ai/geluoke-research/2026-10-09-us-datacenter-power/raw')
ROOT=Path('/Users/m5/.worktrees/inresearch.ai/us-datacenter-power-20261009')
R=OUT/'research';R.mkdir(exist_ok=True);(R/'materials').mkdir(exist_ok=True)
def dump(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
src=json.loads((OUT/'sources.json').read_text())
mp={1:1,2:2,3:3,4:4,5:5,6:6,7:7,8:8,10:9,11:10,12:11,13:12,14:13,15:14,16:15,18:16,19:17,20:18}
for s in src['records']:
    s['original_citation_group']=s.get('original_citation_group',s['citation_group']);s['citation_group']=mp.get(s['original_citation_group'])
    s['read_scope']='与本篇问题相关的章节/段落；未宣称逐页完整深读'
    s['adoption_status']='research_input_only'
    if s['id']=='ga-contract':s['published']='2026-08-26'
    if s['id']=='pjm-accuracy':s['published']='2026-05'
    if s['id']=='ohio':s['published']='2026-01-21';s['event_date']='2025-07-09';s['date_note']='页面显示012126，正文另记2025年11月上诉；事件日期与网页更新分开'
    if s['id']=='doe-transformer':s['published']=None;s['date_note']='页面转录包含2024年调查结果；不把结果年份当页面发布日期'
    if s['id']=='lbnl-report':s['superseded_access_path']='lbnl-full'
    if s['id']=='talen':s['alternate_access']='talen-sec'
    if s['id']=='crane':s['alternate_access']='crane-pdf'
# Archive genuine web-tool responses distinctly from original HTML/PDF bytes.
for sid,artifact,needle in [('ferc-rto','official-web-extract.json','RTOs and ISOs'),('ferc-june','official-web-extract.json','Targeted Action'),('ferc-colocation','official-web-extract.json','FACT SHEET'),('talen-sec','company-web-extract.json','a20250611'),('crane-q2','company-web-extract.json','ceg-20260806'),('crane-pdf','crane-pdf-web-extract.json','2027')]:
    s=next(x for x in src['records'] if x['id']==sid);p=RAW/artifact
    if p.exists() and needle in p.read_text():
        s['original_download_status']=s.get('original_download_status',s['status']);s['status']='web_tool_extract';s['retrieval_artifact']=str(p);s['retrieval_artifact_sha256']=sha(p);s['original_bytes_sha256']=None;s['raw_file']=None;s['extracted_text']=str(p)
        s['read_scope']='已读取网页工具返回的具名原站正文，原始HTML下载受限；SHA仅标识归档响应，不冒充原站字节SHA'
if not any(s['id']=='guancha-start' for s in src['records']):
    src['records'] += [dict(id='guancha-start',org='观察者网用户社区 / 正解局',citation_group=None,published=None,title='选题起点：用户提供文章',url='https://user.guancha.cn/main/content?id=1749183',status='downloaded',raw_file=str(RAW/'guancha-start.html'),sha256=sha(RAW/'guancha-start.html'),read_scope='已读原文；作为线索，不作为独立数值证据',adoption_status='lead_only')]
by={s['id']:s for s in src['records']}
for s in src['records']:
    path=s.get('raw_file') or s.get('retrieval_artifact')
    if path:s['originals_package_path']='originals/'+Path(path).name
    if s['status'] in ['failed','blocked']:s['read_scope']='原文未取得；保留失败记录，未据此作事实证据。替代访问另有具名记录。'

# Each number preserves subject, period, denominator, stage, source and locator.
# The English snippet is intentionally short; a locator points to the full private original.
rows=[
('C01','美国本土主要同步互联',3,'个','截至2026-10-09','定义','eia-grid','Three','Electricity interconnections小节','本土48州；不含AK/HI；有有限直流联络',['OBJ-grid-definition']),
('C02','FERC大负荷改革适用区域运营商',6,'家','2026-06-18','监管行动','ferc-june','six','正文及The Six Grid Operators','FERC管辖六家，不含ERCOT；不是六家垂直电力公司',['OBJ-grid-interfaces']),
('C03','美国数据中心年度用电',58,'TWh','2014','历史研究估算','lbnl-full','58','Executive Summary / Figure ES-1','数据中心整体，非AI独有',['M04-Q05']),
('C04','美国数据中心年度用电',176,'TWh','2023','历史研究估算','lbnl-full','176','Executive Summary','总设施能源估算；非全国逐表实测',['M04-Q05']),
('C05','美国数据中心用电占美国总用电',4.4,'%','2023','历史研究估算','lbnl-full','4.4%','Executive Summary','分母美国全年总用电',['M04-Q05']),
('C06','美国数据中心年度用电预测低端',325,'TWh','2028','2024版预测','lbnl-full','325','Executive Summary','2024年报告情景低端，不是2026年实际',['M04-Q05']),
('C07','美国数据中心年度用电预测高端',580,'TWh','2028','2024版预测','lbnl-full','580','Executive Summary','与低端同一模型情景范围，不做简单平均',['M04-Q05']),
('C08','美国数据中心占总用电预测低端',6.7,'%','2028','2024版预测','lbnl-full','6.7%','Executive Summary','分母该报告预测的2028美国总用电',['M04-Q05']),
('C09','美国数据中心占总用电预测高端',12,'%','2028','2024版预测','lbnl-full','12.0%','Executive Summary','预测分母；非当前全国占比',['M04-Q05']),
('C10','ERCOT批次研究的大负荷资格规模门槛',75,'MW','2026-06-18','公布规则','ercot-batch','75 megawatts','正文第三段 qualified projects','另须满足资格条件，不是投运IT容量',['M04-Q01','M04-Q07']),
('C11','ERCOT Batch Zero最终输电计划',2027,'年秋季','2027','公布预期节点','ercot-batch','Fall 2027','正文 transmission plan','研究/计划时间，不是所有项目投运时间',['M04-Q07']),
('C12','配电变压器交期', '3—6','月','2019','DOE转录所述历史调查','doe-transformer','2019','lead time相关段落','配电变压器，不推广到所有主变压器',['M09-Q01']),
('C13','配电变压器交期','1—2年以上','年','2024','DOE转录所述历史调查','doe-transformer','2024','lead time相关段落','不冒充2026年现货或工厂报价',['M09-Q01']),
('C14','Dominion适用新大型客户最低服务义务',14,'年','2027-01-01及以后签约','SCC已公布未来适用条款','scc','14 years','WHAT IS THE MINIMUM CONTRACT OBLIGATION','适用新增大型客户，非全美统一',['M04-Q04']),
('C15','Dominion最低月输配电费用承担',85,'%','SCC 2026-02-24说明','已公布条款','scc','85%','WHAT MINIMUM CHARGES WILL APPLY','分母为其服务的输配电成本；2016年前客户豁免',['M04-Q04']),
('C16','Dominion信用不足新客户担保上限',60,'%','2027-01-01及以后签约','已公布条款','scc','60%','WHAT COLLATERAL WILL BE REQUIRED','分母最低合同费用；可能要求而非所有客户必缴',['M04-Q04']),
('C17','AEP Ohio新大型数据中心最低合同容量付款',85,'%','2025-07-09决定','监管决定的官方机构说明','ohio','85 percent','Update段落','分母合同电力容量，非未消耗的电能；2025-11上诉',['M04-Q04']),
('C18','AEP Ohio最低容量义务最长期间',12,'年','2025-07-09决定','监管决定的官方机构说明','ohio','12 years','Update段落','最长期限；保留爬坡细节待查完整费率',['M04-Q04']),
('C19','典型Dominion居民发电及输电月成本增量','14—37','美元/月（不变价）','到2040','2024长期情景估算','jlarc','$14 to $37','Summary printed v','特定模型情景，非当前全国涨幅',['M04-Q04']),
('C20','Georgia Power大负荷组合客户预计年度节省',9.5,'亿美元/年','从2029起','公司预测','ga-contract','$950 million','projected incremental revenue段落','组合口径；非单项目/已兑现现金收益',['M04-Q04']),
('C21','Georgia Power / OpenAI新增合同需求',3200,'MW','2026-08-26披露','合同公告','ga-contract','3,200','contract filed in July段落','新增需求合同，不识别成投运或IT功率',['M04-Q05','M04-Q04']),
('C22','Georgia Power / OpenAI灵活响应承诺上限',1000,'MW','2026-08-26披露','合同公告','ga-contract','1,000','flexible demand response段落','承诺上限，不是已观测调度能力',['OBJ-grid-alternatives']),
('C23','反对本地建设AI数据中心受访成年人比例',71,'%','2026-03-02至03-18调查','Gallup调查','gallup','71%','Two in Three以上正文/图','美国成年人态度调查，非电费因果证据',['M05-Q04']),
('C24','Crane重启目标',2027,'年','2025-09-23公告','公司目标','crane-pdf','2027','PDF第1页第三段','停运机组重启目标，非已投运电力',['M04-Q03']),
('C25','Microsoft支持Crane重启的购电期限',20,'年','2025-09-23公告','已披露合约期限','crane-pdf','20-year','PDF第1页第一正文段','PPA，不解释成全部电流直供微软园区',['M04-Q03','M04-Q04']),
('C26','Talen/Amazon全合同规模',1920,'MW','2025-06-11','合同安排','talen-sec','1,920 MW','公司演示材料Slide 4','既有核电能源/容量协议，不等于新增装机或IT',['M04-Q02','M04-Q04']),
('C27','Talen/Amazon合同期末',2042,'年','2025-06-11','合同安排','talen-sec','2042','Slide 4','有延长选项；实际负荷按阶段爬坡',['M04-Q04']),
('C28','现场燃气可靠供电装机超配区间','30—70','%','2026模型','IEA模型估算','iea','30% to 70%','Executive Summary','分母所服务需求；取决配置，非全部园区固定系数',['M04-Q02']),
('C29','已土地清理或建设的美国现场燃气项目','约五分之一','比例','2026报告观察','IEA卫星观察','iea','one-fifth','Executive Summary','项目数观察，不是投运比例或发电量',['M04-Q02']),
('C30','全球数据中心现场燃气2030装机预测','15—27','GW','2030','IEA预测','iea','15-27 GW','Executive Summary / Figure 6.4','全球，主要在美国；不可改写美国现有装机',['M04-Q02','M04-Q05']),
('C31','Alphabet收购Intersect现金对价',47.5,'亿美元','2025-12-22宣布','协议对价','intersect','billion in cash','开头收购对价段','现金之外承担债务；并非全部交易企业价值',['OBJ-grid-supply']),
('C32','Alphabet完成Intersect收购','2026-03','日期','2026-04-29披露','公司财报披露','alphabet-q1','closed in March','PDF第13页CapEx段','后续事实替代仅宣布协议状态，资产不全已投运',['OBJ-grid-supply']),
('C33','PJM大负荷登记工具计划上线','2027-02-01','日期','2026-10-09网页','待批准方案/工具计划','pjm-large','February 1, 2027','Existing and Future Large Load Registry','页面标Pending FERC Approval，不冒充已全面生效',['M04-Q01','M04-Q07']),
('C34','PJM按区域汇总登记信息计划公开','2027-03','日期','2026-10-09网页','待批准方案/工具计划','pjm-large','March 2027','Public Registry Information','计划信息公开，不是所有新增需求投运',['M04-Q01']),
]
for st,v in [('Texas',6.72),('Virginia',10.08),('Arizona',7.66),('Georgia',7.99),('Ohio',10.32),('Oregon',8.33),('U.S. Total',9.03)]:
    rows.append((f'C{len(rows)+1:02}',st+'工业平均电价',v,'美分/kWh','2026-01至2026-07','EIA初步估计','eia-ytd',st,'Table 5.6.B / '+st+' / Industrial 2026 YTD','售电收入÷售电量；非数据中心合同报价',['M04-Q11']))
claims=[]
for cid,subject,value,unit,period,attr,sid,needle,loc,cal,qids in rows:
    s=by[sid];p=Path(s.get('extracted_text') or s.get('retrieval_artifact') or '')
    raw=p.read_text() if p.is_file() else ''
    if sid=='crane-pdf':assert raw,'Crane PDF must be acquired'
    # Locators include physical PDF page numbers found from actual text extraction.
    pages=RAW/(sid+'.pages.json');matches=[]
    if pages.exists():
        for pg in json.loads(pages.read_text()):
            if needle.casefold() in pg['text'].casefold():matches.append(pg['pdf_page'])
        if matches:loc+='；匹配PDF物理页 '+','.join(map(str,matches[:6]))
    assert needle.casefold() in raw.casefold(),(sid,needle)
    claims.append(dict(id=cid,subject=subject,value=value,unit=unit,period=period,denominator_or_caliber=cal,attribute=attr,source_id=sid,org=s['org'],url=s['url'],source_date=s.get('published'),quote=needle,locator=loc,research_question_ids=qids,status='candidate',capacity_stage=cal if unit in ['MW','GW'] else None))

statements=[
('S01','PJM近期大负荷预测要求较明确建设/服务承诺，远期非确定项目折减','pjm-forecast','firm','PDF第6页（正文第4页）','mechanism',['M04-Q01','M04-Q05']),
('S02','JLARC当时独立成本研究认为当前服务成本已适当分配，同时预测增长提高未来系统成本','jlarc','full cost of service','PDF第9、62页（正文摘要v、44）','mechanism',['M04-Q04']),
('S03','Talen/Amazon项目建立电网连接后转表前零售，过渡期部分表后','talen-sec','Front-of-the-Meter','Slide 4','interface',['M04-Q02']),
('S04','PJM IRAS截至查看时仍待FERC批准','pjm-large','Pending FERC Approval','Registry及IRAS标题','standard',['M04-Q07']),
('S05','俄亥俄AEP现场项目采用天然气固体氧化物燃料电池，客户承担项目成本','aep-onsite','solid oxide fuel cells','正文Bloom系统段','mechanism',['M04-Q02']),
('S06','Google以可调度机器学习负荷与电力公司开展需求响应合作','google-flex','machine learning','与I&M / TVA合作正文段','mechanism',['OBJ-grid-alternatives']),
('S07','跨州输电涉及多个司法和土地权利层级','doe-transmission','state','正文选址许可部分','interface',['OBJ-grid-interfaces','M04-Q07']),
('S08','NERC风险结果使用有时点的需求与资源假设；部分新加速资源未纳入','nerc','not included','PDF第8—11页','mechanism',['M04-Q05','M04-Q07']),
('S09','白宫保护居民成本的承诺需与地方具体费率及合同衔接','pledge','Ratepayer','公告正文','standard',['M04-Q04'])]
for cid,desc,sid,needle,loc,kind,qids in statements:
    s=by[sid];p=Path(s.get('extracted_text') or '');assert needle.lower() in p.read_text().lower(),(sid,needle)
    claims.append(dict(id=cid,statement=desc,kind=kind,source_id=sid,quote=needle,locator=loc,url=s['url'],source_date=s.get('published'),research_question_ids=qids,status='candidate'))
dump(R/'claims.json',dict(version='1.0',as_of='2026-10-09',adoption='未执行C3，不关闭问题、不写正式事实/模型',records=claims))
dump(OUT/'sources.json',src)

qall=json.loads((ROOT/'framework/research_questions.json').read_text())
qids=set(q for c in claims for q in c['research_question_ids'])
qs=[x for x in qall['records'] if x['id'] in qids];assert {x['id'] for x in qs}==qids
targets=json.loads((ROOT/'framework/tco_targets.json').read_text())
ts=[x for x in targets['targets'] if any(z in json.dumps(x,ensure_ascii=False).lower() for z in ['power_price.state_industrial','demand_charge.tariff','capacity_market','interconnection.queue','s.grid.timeline','s.grid.holders','s.gas-supply.timeline','s.gas-supply.holders','p.transformer.lead_time'])]
dump(R/'demand-snapshot.json',dict(frozen_at='2026-10-09',baseline_revision='10cd748fd7b94d46a61174f35b87345aa3ad2a80',source_files={f:sha(ROOT/f) for f in ['framework/research_questions.json','framework/tco_targets.json','framework/03_bom_and_collaboration.md','framework/06_acquisition.md','data/schema/submission.schema.json']},research_questions=qs,tco_targets=ts))

descs={
'eia-grid':'美国本土互联结构与电力输送层级，明确东部、西部和ERCOT；跨互联转移有限而非没有；物理互联不能替代市场调度机构或地方供电公司身份。',
'ferc-june':'2026年6月FERC向所管辖六家RTO/ISO发布大负荷规则改革要求，涉及接入研究、成本转移、共址、灵活负荷与相邻发电；不能把改革要求当作各地统一规则已实施。',
'lbnl-full':'全国数据中心历史用电与2028情景范围；能源、功率和美国总用电占比各有分母，设备、利用率及设施效率带来预测不确定性；AI是整体数据中心的一部分。',
'ercot-batch':'ERCOT大负荷批次研究制度，75MW资格门槛和2027年计划节点；现场供电、可中断安排及后续批次各有条件，不能将申请量当作现有投运需求。',
'doe-transformer':'配电变压器供应与交期的历史调查，2019与2024对照；来源对象是配电变压器，不将历史调查推广为当前所有高压主变设备统一报价或交期。',
'scc':'Dominion大型客户GS-5独立费率、长期义务、85%月输配电成本付款和信用不足担保；记录2027签约条件与2016年前客户豁免，区别能源消耗费用和网络固定费用。',
'ohio':'俄亥俄消费者法律代表机构对PUCO2025年数据中心费率决定的说明，包含85%合同容量和最长12年义务；页面后续更新记载行业上诉，不宣称诉讼已终结。',
'jlarc':'弗吉尼亚州2024年行业研究，既保留数据中心当时承担当前服务成本的反证，也保留增长带来的长期资源与居民成本压力；14—37美元是到2040情景下不变价月增量。',
'ga-contract':'Georgia Power的2026年OpenAI合同及客户节省预测；3200MW合同需求、最高1000MW灵活承诺与基础设施成本责任；9.5亿美元为大负荷组合未来年度预测。',
'gallup':'2026年3月美国成年人本地AI数据中心态度调查，5月发表；71%是反对态度比例，不能转成项目阻止率、居民电费因果证据或投资实际损失。',
'crane-pdf':'Constellation公司2025年Crane重启公告，重启原三哩岛一号机组，以微软20年PPA支持，目标加速到2027；公司进度与目标分别记录，不视作当前投运。',
'talen-sec':'Talen2025年6月向SEC提交的交易演示材料，Amazon全合同规模1920MW、期限2042，并从过渡表后转表前；既有发电合同不是新增核电装机或园区IT容量。',
'iea':'IEA2026年能源与AI研究，现场燃气可靠性模型、卫星工程观察及2030全球装机区间；同时解释绿电年度匹配、储能、灵活性和可靠供电的区别。',
'intersect':'Alphabet2025年12月收购协议与对价安排，现金另加承债，开发与建设资产范围须保留；交易完成状态由后续Alphabet财报补充，而非用协议公告直接推定。',
'alphabet-q1':'Alphabet2026年第一季度财报电话会原文，第13页披露Intersect于3月完成收购；这是交易完成事实，不证明收购资产已全部建成或投运。',
'pjm-large':'PJM2026年10月可见的大负荷登记和IRAS方案；资料10月6—7日更新，但正文仍标待FERC批准；2027年工具和公开汇总信息是未来安排。',
'pjm-forecast':'PJM2026年长期负荷预测方法，近期要求明确承诺、远期项目折减，2032以前预测相较旧版降低；预测修订和实际负荷下降不能互相替代。',
'aep-onsite':'AEP2025年6月公布俄亥俄两个现场供电项目获准，AWS与Cologix采用Bloom固体氧化物燃料电池及天然气，客户承担全部成本；批准与投运阶段分开。',
'google-flex':'Google2025年需求响应合作，涉及I&M、TVA和此前OPPD演示；可调整机器学习工作负载，不推广为所有在线服务均可无成本中断。',
'doe-transmission':'DOE关于输电选址许可的官方说明，提供多级审批与土地条件背景；社会参与者与法定批准机关分别识别，不作全部利益相关者都有否决批准权的结论。',
'nerc':'NERC2025长期可靠性评估，发表于2026并评估未来多个年份；明确采用时点和新增资源未纳入的边界，风险场景不等于必然断电。',
'pledge':'白宫2026年保护居民电费承诺，说明全国政策方向；不替代具体州费率、客户合同或输电服务，不以承诺文本直接推断实际账单已降低。',
'eia-ytd':'EIA2026年9月电力月报表5.6.B，2026年1—7月州工业平均电价，保存州、部门、年份与初步估计属性；平均到户统计不作为具体数据中心供电合同价格。'}
items=[];report=['# 原文定位与关键摘录\n\n本文件按相关章节读取，PDF页码为物理页；不是逐页深读或C3采用回执。\n']
for sid in dict.fromkeys(c['source_id'] for c in claims):
    s=by[sid];cs=[c for c in claims if c['source_id']==sid]
    summary=descs[sid]+' 本材料用于回答已冻结的电网接入、供电路径、成本责任或价格口径问题。原文路径、访问时间与身份摘要单独登记；受限站点的网页工具正文响应单独标识，不与原始HTML字节身份混淆。数字和机制仅作为待核验研究输入，不能据此关闭研究问题、覆盖既有记录或把规划容量提升为正式投运容量。后续审核须核对地域、服务对象、分期、事实或预测属性，以及与既有事实是否采用同一分母。'
    f=R/'materials'/(sid+'.md')
    contents=f'# {s["title"]}\n\n机构：{s["org"]}\n来源：{s["url"]}\n日期：{s.get("published")}\n读取范围：{s["read_scope"]}\n\n## 研究摘要\n\n{summary}\n\n## 候选证据\n'
    for c in cs:contents+='\n'+json.dumps(c,ensure_ascii=False,indent=2)+'\n'
    f.write_text(contents)
    nums=[dict(what=c['subject'],value=c['value'],unit=c['unit'],locator=c['locator'],caliber_note=c['denominator_or_caliber']+'；'+c['attribute']+'；'+c['period']) for c in cs if 'value' in c]
    sts=[dict(kind=c['kind'],text=c['statement'],quote=c['quote'],locator=c['locator']) for c in cs if 'statement' in c]
    year=int((s.get('published') or '2026')[:4]);confidence='B' if sid in ['iea','lbnl-full','jlarc'] else 'A'
    modules=sorted({'M04'}|{q['legacy_module'] for q in qs if any(q['id'] in c['research_question_ids'] for c in cs)})
    items.append(dict(file='materials/'+f.name,title=s['title'],org=s['org'],year=year,modules=modules,claimed_importance=7,confidence=confidence,summary=summary,key_numbers=nums,key_statements=sts))
    report.append(f'\n## {sid}｜{s["title"]}\n\n'+f'来源：{s["url"]}\n\n'+'\n'.join(f'- {c["id"]}：{c.get("subject",c.get("statement"))}；原文短引 `{c["quote"]}`；{c["locator"]}。' for c in cs))
dump(R/'submission.json',dict(contributor='格洛可专题研究 / Codex',submitted='2026-10-09',module='M04',items=items))
(OUT/'report_facts.md').write_text('\n'.join(report))
shutil.copy2(OUT/'sources.json',R/'sources.json')
manifest=[dict(path=str(p.relative_to(RAW)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(RAW.iterdir()) if p.is_file()]
dump(R/'originals-manifest.json',dict(local_raw_root=str(RAW),archive_only='原始字节/工具响应分别标注；原件不入Git',files=manifest))
questionlines=[]
for q in qs:
    cs=[c['id'] for c in claims if q['id'] in c['research_question_ids']]
    questionlines.append(f'| {q["id"]} | {q["text"]} | {q["node"]} / 第{q["variable_class"]}类 | {", ".join(cs)} |')
gaps=[('M04-Q01','排队规模、平均等待、清退率仍缺相同年份与去重口径的地区原表；不采纳未追到原件的474GW总数。','PJM/ERCOT大负荷登记与月度进度，不混发电排队。'),('M04-Q02','现场电源案例有官方项目与模型；实际投运日期、实耗、设备造价和燃料到户合同仍缺。','项目许可、运营披露、实测负荷、燃料电池与燃机分别取材。'),('M04-Q03','Crane公司目标与部分进度已补；NRC当前页下载受限，不能独立证明全部复运条件已满足；SMR商业投运另需逐项目。','NRC许可/检查与公司后续里程碑双向核对。'),('M04-Q04','费率保护条款已补，公开摘要不是删节客户合同全文；实际居民账单因果与Georgia节省兑现仍待查。','SCC/PUCO完整费率、成本服务研究、负荷实现与收入。'),('M04-Q05','全国能量预测与区域方法有资料；2030新增可交付GW的统一分期清单仍缺。','建立同一项目身份、接入点、年度阶段和可靠容量。'),('M04-Q07','Batch/IRAS与设备瓶颈明确；园区实际送电等待分布不能从制度计划推算。','同一批次研究开始、合同、送电及实际爬坡。'),('M04-Q11','7条州工业初步均价可登记为对应范围候选；不能替代园区能量/需量费率或GPU成本。','Dominion、AEP、Georgia Power、Oncor具体适用费率与条件。'),('M09-Q01','DOE配电变压器历史调查已补；2026大型主变与开关柜型号/工厂交付报价仍缺。','设备类别、额定电压、工厂报价日和订单排期。')]
dump(R/'research-gaps.json',dict(status='仍待研究，不关闭任何现行问题',records=[dict(question_id=q,gap=g,next_source=n) for q,g,n in gaps]))
researchtext='# 美国数据中心电力：inresearch.ai研究输入\n\n研究时点：2026-10-09。\n\n## 接收要求与本次边界\n\n已查阅当前CURRENT、口径与采集规范、对象规则、research_questions、tco_targets及submission schema。需求来自现行问题与五类变量；节点和变量类别沿原登记，M04只作为兼容模块。材料、候选、正式事实和模型参数分别处理。本批为候选素材投递，尚未执行Reader深读/C3或远程数据库采用；未修改现行价格基准、项目GW、问题状态。\n\n每份素材提供具名机构、原文URL、日期、访问状态、身份摘要、读取范围、中文导读与逐条定位。原始PDF/HTML存本机原件目录，受限网页仅归档工具响应，不能声称获得其原始字节。公众号文章为叙述稿，不作为原件的独立佐证，也不重复计作新证据。\n\n## 命中的现行问题\n\n| 问题ID | 当前问题 | 节点 / 五类变量 | 候选证据 |\n|---|---|---|---|\n'+'\n'.join(questionlines)+'\n\n## 逐项候选事实与机制\n\n'
for c in claims:
    s=by[c['source_id']];researchtext+=f'### {c["id"]}　{c.get("subject",c.get("statement"))}\n\n'
    if 'value' in c:researchtext+=f'数值：{c["value"]} {c["unit"]}；期间：{c["period"]}；属性：{c["attribute"]}。\n\n口径：{c["denominator_or_caliber"]}。\n\n'
    researchtext+=f'来源：[{s["org"]}｜{s["title"]}]({s["url"]})；源日期：{s.get("published")}。\n\n定位：{c["locator"]}；短引：{c["quote"]}。命中：{", ".join(c["research_question_ids"])}。状态：候选。\n\n'
researchtext+='## 保留的反证和状态更新\n\nJLARC当时认为现有服务成本已被适当分配，不支持把全部居民涨价都归为直接补贴。PJM近端预测下修不代表实际用电下跌。Alphabet完成收购是后续事实，项目资产投运另查。Talen既有核电PPA不计新增装机。Georgia客户节省是公司未来组合预测。\n\n## 未采用线索\n\n起点文章中的七家运营商垂直垄断、三大网完全不通、以PUHCA代替FPA解释批发监管，均已修正。3000家公司数量未作为当前统计采用；各州暂停日期和全国电费翻倍未有足够原文，不采用。\n\n## 剩余缺口与下一步原件\n\n'
researchtext+='\n'.join(f'- {q}：{g} 下一步：{n}' for q,g,n in gaps)
researchtext+='\n\n## 导入办法\n\n先解压研究原件包与交付包，检查originals-manifest SHA；研究正文research.md可送当前正文阅读入口，submission.json可经`python3 manage.py submissions <本research目录>`登记校验。该命令校验候选，不执行正式数据库采用。需求快照SHA与问题ID用于匹配；没有真实workorder不虚构工单。不得把本包直接当成日报daily-receive事件包，也不得将格式通过回执当作C3回执。采纳后按现行事实/价格载体写入并返回采用ID；本篇不更改基准。\n'
(R/'research.md').write_text(researchtext)
(R/'research.txt').write_text(researchtext)
dump(OUT/'cards.json',dict(as_of='2026-10-09',records=claims))
print('candidate facts/statements',len(claims),'submission items',len(items),'matched questions',len(qs),'target records',len(ts))
