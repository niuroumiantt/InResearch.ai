"""Source-derived research control room; observations arrive via the private API."""
from collections import Counter
from html import escape
import json
import sys

STYLE = """<style>
.audit-hero{margin:28px 0;padding:26px 0;border-top:3px solid var(--accent);border-bottom:1px solid var(--line)}
.audit-kicker{letter-spacing:.12em;color:var(--muted);font-size:12px}.audit-hero h2{font-size:36px;line-height:1.3;margin:12px 0;max-width:850px}.audit-hero p{max-width:850px}
.audit-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px;margin:24px 0}.audit-metrics article{border-left:2px solid var(--line);padding-left:16px;min-width:0}.audit-metrics strong{display:block;font-size:34px;line-height:1.3;font-variant-numeric:tabular-nums}.audit-metrics span{color:var(--muted);font-size:12px}
.audit-nav{display:flex;flex-wrap:wrap;gap:8px 20px;margin:20px 0}.audit-section{scroll-margin-top:110px;border-top:1px solid var(--line);padding-top:12px;margin-top:36px}.audit-section h2 small{display:block;font-size:13px;font-weight:400;color:var(--muted)}
.audit-map{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:24px 0}.audit-map article{padding:18px;background:var(--card);border:1px solid var(--line);border-top:3px solid var(--accent);min-width:0}.audit-map h3{margin:0 0 8px;font-size:16px}.audit-map p{margin:5px 0}.audit-section code,.audit-section td{overflow-wrap:anywhere}.audit-section details{padding:14px 0}.audit-section summary{cursor:pointer;font-weight:600}.audit-callout{border-left:3px solid var(--accent);padding:8px 18px;margin:18px 0}.audit-legend{font-size:13px;color:var(--muted)}
.audit-diagram{margin:20px 0;overflow:auto;border:1px solid var(--line);padding:16px}.audit-diagram svg{display:block;width:100%;min-width:660px;height:auto;color:var(--text)}.audit-diagram rect{fill:var(--card);stroke:var(--line)}.audit-diagram text{fill:currentColor;font-family:var(--ui-font);font-size:15px}.audit-diagram path{fill:none;stroke:var(--accent);stroke-width:2}.audit-live{border:1px solid var(--line);padding:16px;margin:18px 0}.audit-live:empty{display:none}
@media(max-width:700px){.audit-metrics{grid-template-columns:1fr 1fr}.audit-map{grid-template-columns:1fr}.audit-hero h2{font-size:27px}.audit-hero{padding:18px 0}}
</style>"""


def build(root, table):
    sys.path.insert(0, str(root/'src'))
    from inresearch.knowledge.research_readiness import summarize
    def read(name): return json.loads((root/name).read_text())
    target_doc=read('framework/tco_targets.json');targets=target_doc['targets']
    bom=read('framework/bom.json');questions=read('framework/research_questions.json')['records']
    knowledge=read('data/research_knowledge.json');model=read('data/datacenter_model.json')
    health=summarize(target_doc,questions,knowledge,model,read('framework/research_graph.json'))
    counts=Counter(t['status'] for t in targets)
    labels=[('architecture','01 研究产品与架构'),('skeleton','02 骨架与图'),('demand','03 需求与供料'),('gates','04 数据门槛'),('storage','05 存储与服务'),('engineering','06 工程与发布')]
    def section(key,title,note):return f'<section id="audit-{key}" class="audit-section"><h2>{title}<small>{note}</small></h2>'
    html='<section class="audit-hero"><div class="audit-kicker">INRESEARCH / RESEARCH CONTROL ROOM</div><h2>现在能回答什么，<br>下一步该补什么。</h2><p>从一个研究问题，到可追溯的回答。目录、材料、证据与模型各有用途；用问题闭环和关键输入决定下一步，把供料、审核与上线的阻塞留在同一张工作面。</p><nav class="audit-nav" aria-label="本页审查目录">'
    html+=''.join(f'<a href="#audit-{key}">{label}</a>' for key,label in labels)+'</nav><div class="audit-metrics">'
    metrics=[(len(knowledge['answers']),'正式答案记录',f'{len(questions)} 个问题；记录数不等于支持链有效的闭题数'),(health['model']['unresolved'],'模型待验证输入',f'{len(model["inputs"])} 个输入；用户选项不计缺口'),(len(targets),'资料目标',f'{counts["needed"]} 缺 · {counts["delivered"]} 已交付目标 · 不等于已采用'),(len(knowledge['statements']),'研究陈述记录',f'{len(knowledge["documents"])} 份文档；不等于已有答案')]
    for value,label,note in metrics:html+=f'<article><strong>{value:,}</strong>{escape(label)}<br><span>{escape(note)}</span></article>'
    html+='</div><p class="audit-legend">以上来自带版本的源码快照。下方动态对账读取当前运行回执和正式支持链，分别标时；不等于已有答案，不将 sourced 标签作为所有情景均可使用的证明。</p><div id="research-health" class="audit-live" aria-live="polite">正在核对问题闭环与供料回执；尚未取得的运行值显示 —。</div></section>'
    html+=section('architecture','01 · 研究产品决定架构','交付目录、证据与回答；以问题闭环衡量研究，以来源与条件衡量数据')
    html+='<p>现行框架：一棵树 · 三级账 · 四问四段 · 五类变量 · 六队 · 一个节点模板。分别组织对象、账本、研究步骤、数据需求和来源责任。</p>'
    html+=table(['产品','当前可提供','完成标准'],[
        ['来源与产品目录','原厂产品、参数原表、版本和缺口检索','型号/配置/来源可回查；目录覆盖有明确分母'],
        ['证据与研究陈述','定位原文、条件、争议及审核链','逐项支持链成立；多个陈述不能自动拼成答案'],
        ['解释、比较与情景分析','骨架节点、统一账本、可发布研究','回答具体问题，标明适用范围、未决输入和反证；假设输出按情景解释']])
    cards=[('定义与需求','对象、问题、模型依赖 → 目标合同','/node.html'),('采集与接收','inews 事件；Fetchspec 原厂资料 → 候选归档','/supply.html'),('提取与阅读','按产品定向提取或全文阅读 → 明示覆盖','/supply.html#matching'),('审核与采用','需求匹配、原文、C3、独立复核 → 支持闭包','/node.html#research'),('版本与发布','正式 JSON → 受保护合并 → 实际网站回执','/report.html'),('服务与反馈','目录、账本与回答 → 缺口、争议与更新需求','/ledger.html')]
    html+='<div class="audit-map" aria-label="研究架构与数据流">'+''.join(f'<article><h3>{i+1:02d} / {title}</h3><p>{body}</p><a href="{url}">打开工作面 →</a></article>' for i,(title,body,url) in enumerate(cards))+'</div>'
    html+='<p>保留标准库 Python 与 SQLite 的模块化单体。先统一身份、状态和写入权威，再按事务边界拆大模块。业务规则归 knowledge/materials，用例归 workflow，外部协议归 adapters；CLI 与 HTTP 共用用例。</p></section>'
    html+=section('skeleton','02 · 一棵分类树，关系与证据分别表达','类别、具体产品、配置与项目实例不共用一个身份；图的精细度不代表数据完成度')
    rel=health['graph']['relations']
    html+=f'<p>{len(bom["parts"])} 个骨架条目；当前登记关系为包含 {rel.get("part_of",0)}、供应 {rel.get("supplies",0)}、持有 {rel.get("holds",0)}。当前关系图尚不提供可计算的现场供电、冷却与接口拓扑。</p>'
    html+='''<figure class="audit-diagram">
<svg viewBox="0 0 960 270" role="img" aria-labelledby="research-map-title research-map-desc">
<title id="research-map-title">研究定义、供应交付与证据闭环</title>
<desc id="research-map-desc">分类骨架生成带范围的目标合同。供应交付经来源验收保存原件，再形成候选，经采用审核形成正式研究和服务。服务中的未支持问题与过期输入回到需求。</desc>
<defs>
<marker id="research-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M0 0L10 5L0 10"/>
</marker>
</defs>
<rect x="15" y="20" width="210" height="68" rx="5"/>
<text x="30" y="47">骨架 × 问题 × 模型输入</text>
<text x="30" y="70">类型与项目实例分开</text>
<rect x="275" y="20" width="210" height="68" rx="5"/>
<text x="290" y="47">目标合同 → 供应任务</text>
<text x="290" y="70">字段 / 范围 / 条件 / 缺口</text>
<rect x="535" y="20" width="185" height="68" rx="5"/>
<text x="550" y="47">来源验收 → SHA 原件</text>
<text x="550" y="70">接收 / 补交 / 拒绝</text>
<rect x="765" y="20" width="180" height="68" rx="5"/>
<text x="780" y="47">提取或阅读 → 候选</text>
<text x="780" y="70">覆盖、定位与条件</text>
<rect x="535" y="152" width="410" height="68" rx="5"/>
<text x="550" y="180">需求匹配 + C3 + 独立复核 → 正式研究版本</text>
<text x="550" y="203">精确版本验收 → 目录 / 账本 / 回答 / 报告</text>
<path d="M225 54H275M485 54H535M720 54H765M855 88V152M535 187H120V88" marker-end="url(#research-arrow)"/>
<text x="145" y="174">未支持问题 / 过期输入 / 来源冲突</text>
<text x="15" y="253">分类树解释组成；功能关系解释连接；模型依赖解释影响；证据链解释为什么相信。</text>
</svg>
<figcaption>箭头表达引用、交付和反馈关系；各阶段的文件、陈述与问题数量不能相除作为统一完成率。</figcaption>
</figure>'''
    html+=table(['表示法','应怎样改进','验证边界'],[
        ['分类与爆炸图','保留五系统、稳定 ID 与类型；通过节点进入目标合同','不从通用示意推断型号、现场数量与容量'],
        ['功能关系','供电/冷却/数据/控制另用有方向、带端口和工况的关系','先有官方贯通样例再扩展；不由画线自动生成工程事实'],
        ['配置与成本','父项含价、子件计价、冗余与共享设备分别登记','同一物理件不重复累计；最长采购交期不等于项目关键路径']])
    html+='<p><a href="/bom.html">爆炸图 →</a> · <a href="/node.html">研究节点 →</a> · <a href="/ledger.html">账本与情景 →</a></p></section>'
    html+=section('demand','03 · 目标合同驱动供料，运行回执单独对账','目标是待满足的需求；两个 repo 接入不表示六类来源已经齐备')
    html+=table(['供应能力','接入','目标','缺','已交付','有来源登记','含假设'],[[p['team'],'已接入' if p['connected'] else '未接入',p['targets'],p['statuses'].get('needed',0),p['statuses'].get('delivered',0),p['statuses'].get('sourced',0),p['statuses'].get('assumed',0)] for p in health['providers']])
    html+=f'<div class="audit-callout">{health["questions"]["targets_without_exact_question"]} 条目标尚无同节点、同变量类的精确问题映射。自动映射仅提供检索入口；是否回答了问题仍由原文与研究审核判断。人工细化任务必须绑定目标行，不能产生第二套独立采集轴。</div>'
    html+='<details><summary>供料合同：要什么、交什么、不能据此推断什么</summary>'+table(['合同','最小交付内容','能力边界'],[[k,'、'.join(v['fields']),v['acceptance']+' 不证明：'+v['does_not_prove']] for k,v in target_doc['request_contract']['profiles'].items()])+'</details>'
    html+='<p>原厂额定功率与现场实耗分开；inews 负责发现与事件指针；统计、财报、报价、运行实证由相应来源能力承担。先补关键输入的来源与负责人，不为“六队”数量创建空 repo。<a href="/supply.html#targets">查看和细化目标 →</a></p></section>'
    html+=section('gates','04 · 每道门只授予本阶段资格','来源归档、可用数据、研究采用、可公开发布分别验收')
    html+=table(['门槛','硬要求','补充或拒绝','通过后'],[
        ['来源与传输','来源/权限、清单全集、路径、大小、SHA 与目标归属','坏包拒绝接收；上游原件保留。已合格但不可解析的资料归档并标缺口','可追溯原件或事件线索'],
        ['提取与数据','型号/配置、单位、时点、工况、定位及覆盖','未披露不补猜；截断、缺页和提取失败分别记录','目录数据、规格观察或阅读候选'],
        ['研究采用','需求匹配、适用范围、原文、C3 与独立复核、支持闭包','背景、重复、冲突与证据不足保留去向；分数只调优先级','正式研究增量；文件数量不关闭问题'],
        ['发布与服务','精确 head 检查、当前上下文、受保护合并、实际部署与网页回执','未部署或版本不符不计上线；按分发范围过滤','可引用的正式版本']])
    html+='<p>门槛按产品分层：规格查询保留原厂条件，正式答案核对支持闭包，情景分析保留假设。硬身份与权限不放宽，全文阅读不强套给每条新闻或规格。</p></section>'
    html+=section('storage','05 · 按权威组织存储，按恢复能力判断可靠性','单份原件、多次来源观察、多条研究引用；运行库与发布版本分开')
    html+=table(['载体 / 格式','权威与服务','出入边界'],[
        ['原件 / SHA 文件 + 来源观察','Spark 永久原件、历史版本与派生产物；可重放提取','内容 SHA 与来源 URL 分开；任务过期不删唯一原件'],
        ['Reader / SQLite','身份、任务、阅读版本与当前报告指针','只显式入队合格范围；全文与图片覆盖分别声明'],
        ['Acquisition / SQLite + blobs','新闻、产品资料、交付与观察；按来源和目标检索','运行接收不自动写 Git；重复字节追加来源观察'],
        ['Review / SQLite + 审计产物','候选去向、尝试、核验与发布状态','失败审计保留；跨库提交不能假装分布式事务'],
        ['AWS 产品目录 / 公司 SQLite','产品/来源/版本/规格原表；检索、比较、导出','结构化接收不授予正式研究采用'],
        ['Git / JSON + Markdown','经审阅的研究、模型、声明与代码；可版本化发布','正式版本只读；候选、数据库、账号和原件不进 Git']])
    html+='<p>数据库文件小不表示原件被压缩或处理完成。需以 SQLite 一致快照、原件独立副本和实际恢复验证闭合可靠性；备份目录存在只证明有文件。下面运行实测保留时间、WAL/SHM 和目录包含关系。</p></section>'
    html+=section('engineering','06 · 验收跟随风险，工程投入跟随研究瓶颈','现行 CI：validate 与 browser (core)；研究答案和备份恢复各有业务验收')
    html+='<p>有界研究追加走研究链路，代码、规则、旧事实与未知影响保持完整回归。按同来源和未改上下文汇总实质变更；运行心跳不制造 PR。区分预算阻塞、runner 等待、实际执行和版本变更导致的重复验收。</p>'
    html+=table(['优先顺序','本轮处理','下一步完成标准'],[
        ['先修误导与断链','混合输入不能标全 sourced；自登记属性不标来源；任务绑定唯一目标行','回归与线上对账保持；不把状态修正当新增证据'],
        ['再补最高价值缺口',f'{health["model"]["unresolved"]} 个未验证输入按缺失/敏感度目录列出；问题与目标显式映射','取得适用来源，审核后回答一组具名问题，减少关键不确定性'],
        ['随后拆模块与恢复验证','大模块按用例、事务和外部协议拆；当前规则入口收敛','保持行为、并发和恢复验收；证明无调用再删除，不按文件年龄清理']])
    html+='<details><summary>当前待验证模型输入与主责目标</summary>'+table(['输入','状态','主责目标','能力','已登记敏感项'],[[r['label']+' / '+r['key'],r['status'],r['target_id'] or '无主行',r['team'] or '未指定','是' if r['declared_sensitivity_driver'] else '未登记'] for r in health['model']['critical_inputs']])+'</details><p><a href="/doc.html?f=docs/CI.md">CI 要求 →</a> · <a href="#material-board">运行容量与处理状态 ↓</a></p></section>'
    return html
