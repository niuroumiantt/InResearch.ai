'''Readable projections of the current object/evidence framework; no adoption or dispatch.'''
from html import escape
import json

STYLE = '''<style>
.arch-figure{margin:22px 0;padding:20px;border:1px solid var(--ui-line);background:var(--ui-soft);color:var(--ui-ink);box-sizing:border-box}
.arch-figure *{box-sizing:border-box}.arch-figure figcaption{font-size:12px;color:var(--ui-muted);margin-top:14px;line-height:1.7}
.arch-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.arch-node{padding:16px;border:1px solid var(--ui-line);background:var(--ui-surface);min-width:0;overflow-wrap:anywhere}
.arch-node h3,.arch-node h4{margin:0 0 7px;font-size:16px;line-height:1.5}.arch-node p{margin:5px 0;line-height:1.7}.arch-node small{color:var(--ui-muted)}
.arch-arrow{text-align:center;padding:10px;font-size:13px;color:var(--ui-muted)}.arch-common{border-left:3px solid var(--ui-ink)}
.arch-chain{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.arch-number{display:block;font-size:27px;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.4}
.arch-tag{display:inline-block;border:1px solid var(--ui-line);padding:2px 7px;margin-bottom:9px;font-size:11px}.arch-limit{border-left:3px solid var(--ui-ink);padding-left:14px;line-height:1.8}
.arch-tools{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:20px 0}.arch-tools p{margin:5px 0}.arch-tools h3{margin-top:0}.arch-provider-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.arch-question{padding:12px 0;border-top:1px solid var(--ui-line)}.arch-question summary{cursor:pointer;font-weight:600}.arch-figure a{text-decoration:underline}
@media(max-width:700px){.arch-columns,.arch-chain,.arch-tools,.arch-provider-grid{grid-template-columns:1fr}.arch-figure{padding:14px;margin:18px 0}.arch-node{padding:13px}.arch-number{font-size:24px}}
</style>'''

def read(root,name):
    return json.loads((root/name).read_text())

def overview(root):
    checklist=read(root,'framework/observation_checklist.json')
    bridge=read(root,'data/site_model_bridges.json')
    count=sum(len(a['checks']) for a in checklist['angles'])
    html='<p class="arch-limit"><strong>两条研究线，共用证据，按用途连接。</strong><br>研究框架 v4 · 对象与证据。先说清研究谁、哪个范围，再观察、解释和应用；数量不是完整性的证明。</p>'
    html += '''<figure class="arch-figure" id="architecture-dual-lines" aria-label="通用数据中心与真实园区共用观察和证据">
<div class="arch-columns"><div class="arch-node"><span class="arch-tag">通用研究</span><h3>类型 → 产品 → 配置条件</h3><p>解释怎样建设、由什么组成、怎样运行；研究可适用的规律、性能与经济模型。</p><a href="/node.html">数据中心研究 →</a></div><div class="arch-node"><span class="arch-tag">真实园区</span><h3>地点 → 分期 → 资产与角色</h3><p>盘点在哪里、谁参与、何时交付、发生什么变化；保留稳定园区身份。</p><a href="/projects.html">园区名录 →</a> · <a href="/regions.html">地区分析 →</a></div></div>
<div class="arch-arrow">↓ 分别提出问题和提供资料；有证据才建立实例与类型的关联 ↓</div>
<div class="arch-node arch-common"><h3>共同底座：对象、关系、带范围的观察与证据</h3><p>对象 / 属性或事件 / 原值与单位 / 主体与期间 / 工况 / 来源版本 / 定位 / 直接观察或推导 / 不确定性</p></div>
<div class="arch-arrow">↓ 按目的核验适用性；已知、候选、假设、未知分别表达 ↓</div>
<div class="arch-columns"><div class="arch-node"><h3>解释、比较与地图</h3><p>行业总览看聚合；园区名录看现实对象；通用研究看结构与机制。</p></div><div class="arch-node"><h3>统一模型与研究报告</h3><p>园区资料先预览、人工确认后生成浏览器情景；报告保留截止日和证据。</p><a href="/ledger.html?view=basis">成本与收益 →</a></div></div>
<figcaption>通用示意不能证明现场安装；园区来源不能自动成为通用规律。两条线共用观察定义与证据合同，各自保留身份和边界。</figcaption></figure>'''
    tools=[('物理骨架','保留一棵类型树，说明系统、链路和部件；现场资产、合同与事件用有类型的关系连接。'),
           ('提问模板','保留对象边界、构成关系、运行演变、结果依据四组提示，可按问题增删；不等同工作流阶段。'),
           ('变量检索','旧构成／运行／价格／时间／主体标签与ID继续兼容；时间和主体通常是限定，不宣称同层互斥。'),
           ('观察覆盖',f'当前{len(checklist["angles"])}个可交叉视图、{count}条检查。身份和不确定性贯穿各主题；新增问题允许扩展。'),
           ('经济分析','成本、收入、回报保留为经济模块；环境、可靠性、性能等结果不强塞入三账。'),
           ('来源组织','采集队按来源机制履约，可协作服务同一问题；实际接通状态与任务完成分别核验。')]
    html+='<div class="arch-tools" id="architecture-tools">'+''.join('<div class="arch-node"><h3>'+escape(t)+'</h3><p>'+escape(b)+'</p></div>' for t,b in tools)+'</div>'
    html += '<p><strong>骨架看组成，关系连现实，证据撑判断，模型算影响。</strong> 通用模型研究规律，真实园区核对适用；发现差异，再完善模型。已有资料追来源，候选结论待核验，假设拿来做情景，未知留下补证任务。</p>'
    html += '<details id="architecture-legacy"><summary>旧3、4、5、6分别保留什么、改变什么</summary><div class="arch-tools">'
    legacy=[('三账：成本、收入、回报','保留为经济分析。园区加入后必须先定主体、资产、分期和期间；租金、会计收入、实收与融资分开，回报用带日期现金流。园区不是第四本经济账。'),('旧四问与四段','旧四问是值多少／由什么组成／怎么影响账／数据从哪来缺什么。新问题提示改为对象边界、构成关系、运行演变、结果依据；不再等同采集→事实→规则→视图的倒序。登记、研究采用和发布各有状态。'),('五类变量','构成、运行、价格、时间、主体仍供旧页面与接口检索；一条观察可同时具有多个属性和限定，取消同层正交、强制独占的解释。'),('六队与覆盖视图','来源队负责找资料，覆盖清单负责查遗漏；两者不是竞争分类。当前十二视图可交叉扩展；局部互斥和穷尽只在明确属性、统计总体与加总规则内验证。')]
    html += ''.join('<div class="arch-node"><h3>'+escape(t)+'</h3><p>'+escape(b)+'</p></div>' for t,b in legacy)+'</div></details>'
    html += '<figure class="arch-figure" id="architecture-model-loop" aria-label="模型研究与真实观察互相校验"><div class="arch-chain"><div class="arch-node"><h3>定义可解释的模型</h3><p>明确对象、边界、结构、运行机制和用途；经济分析使用成本、收入、回报。</p></div><div class="arch-node"><h3>用资料检验适用条件</h3><p>采集来源与真实园区观察，核对配置、单位、工况、主体和期间；记录冲突与缺口。</p></div><div class="arch-node"><h3>复算、比较与敏感性</h3><p>可用证据按用途确认；不足处用显式假设或保持未知，输出不能冒充现场实际。</p></div></div><div class="arch-arrow">↺ 差异、反证与高敏感缺口 → 补证或修订模型 → 重新核验受影响结果</div><figcaption>模型是持续研究的对象。单个园区用来检验连接与适用性，不把该园区的配置、合同或缺口当成整个行业的固定模板。</figcaption></figure>'
    html+='''<figure class="arch-figure" id="architecture-registration" aria-label="基础来源登记与研究采用分开流转">
<div class="arch-node"><h3>取得资料 → 保存来源版本、定位和读取范围</h3><p>正文、计算表、图片与附件分别盘点；未读、未取得、已查未披露、不适用各留原因。</p></div><div class="arch-arrow">↓ 同一份来源可被复用，按唯一身份去重 ↓</div>
<div class="arch-columns"><div class="arch-node"><span class="arch-tag">基础登记</span><h3>具名对象 + 至少一条来源信息</h3><p>允许缺项与无模型目标，标“基础登记待查”。身份不明保留线索，不猜测合并。</p><p>用于名录、来源检索及持续跟踪。</p></div><div class="arch-node"><span class="arch-tag">研究与模型用途</span><h3>问题 → 方法 → 证据与推导 → 审核</h3><p>核对范围、单位、条件、反证、C3与适用性；情景假设单独标明。</p><p>发布候选复核结果，不等于批准正式事实或模型参数。</p></div></div>
<figcaption>登记、阅读、研究采用、模型适用和实际上线各自有状态与回执；普通信息不以全文阅读或C3为登记前置。</figcaption></figure>'''
    html+='''<details id="architecture-example"><summary>贯通校验样例：Abilene（不决定通用模型的研究范围）</summary><figure class="arch-figure" id="architecture-abilene" aria-label="Abilene共享推导与不同范围账目">
<div class="arch-chain"><div class="arch-node"><span class="arch-tag">配置估算 · 候选</span><h3>GPU数量及型号组合</h3><p>取整与型号配置进入后续容量和算力推导；不是现场清点。</p></div><div class="arch-node"><span class="arch-tag">↓ 共享上游</span><h3>四栋 · 快照容量估算</h3><strong class="arch-number">421 MW</strong><p>2026-07-28，固定原观察及来源版本；不是平均IT负载。</p></div><div class="arch-node"><span class="arch-tag">↓ 模型与假设</span><h3>成本、算力与年度用电</h3><p>159亿美元为通用系数缩放估算；年度用电还需容量时间、平均IT负载、期间PUE和电价。</p></div></div>
<div class="arch-arrow">以上同链结果不能互相充当独立验证；原三项异常继续阻断相关自动填参</div>
<div class="arch-columns"><div class="arch-node"><span class="arch-tag">另一个范围：DC1首两栋</span><h3>合同租金 → 会计收入 ↔ 现金收付</h3><p>租约、年度经营、现金流、债务和未来最低租金分别核对。八张已读表来自同版财报；租金实际收款仍无法唯一拆出。</p></div><div class="arch-node"><span class="arch-tag">不跨范围填参</span><h3>Crusoe / Oracle / OpenAI 分账</h3><p>两栋租金不套四栋421MW，集团披露不分摊园区；未来承诺不是实收，贷款不是建设实支。</p><p>实际NOI、项目及权益回报保持未知。</p></div></div>
<div class="arch-arrow">↓ 仅已登记容量、地点参考与显式用户假设可经确认生成情景；经济候选不填参 ↓</div>
<div class="arch-node arch-common"><h3>已提供：现场配置候选映射 → 参数预览 → 可复算情景导出</h3><p>保留83项输入依据、来源版本、推导关系、未读项和异常；不写回园区正式资料。</p><a href="/project.html?site=us-tx-abilene#campus-equipment">查看园区配置 →</a> · <a href="/ledger.html?view=basis&amp;site=us-tx-abilene&amp;scope=abilene-20260728-estimated-operating">查看参数与全部复核结果 →</a></div>
<figcaption>当前桥接版本：'''+escape(str(bridge['version']))+'''。点击情景确认只批准本次浏览器试算，不是人类审核采用或现场真实性认证。</figcaption></figure></details>'''
    return html

def task_coverage(root):
    c=read(root,'framework/observation_checklist.json')
    s=read(root,'framework/supply_contract.json')
    count=sum(len(a['checks']) for a in c['angles'])
    html='<div id="observation-coverage" data-version="'+escape(c['version'],quote=True)+'"><h3>共用的观察检查：当前'+str(len(c['angles']))+'个视图、'+str(count)+'条检查</h3><p>通用数据中心与真实园区共用定义；视图允许交叉、扩展，不是第二棵分类树或新派工轴。不适用要说明理由，未检查不能写成数据不存在。</p><div class="angle-grid">'
    for i,a in enumerate(c['angles'],1):
        html+='<article data-angle="'+a['id']+'"><span>'+str(i).zfill(2)+'</span><h3>'+escape(a['label'])+'</h3><p>'+escape(a['placement'])+'</p><details><summary>'+str(len(a['checks']))+'项检查</summary><ul>'+''.join('<li data-check-id="'+ch['id']+'">'+escape(ch['question'])+'</li>' for ch in a['checks'])+'</ul></details></article>'
    html+='</div><h3>提问时先明确对象与范围</h3>'
    for q in c['question_templates']:
        html+='<details class="arch-question"><summary>'+escape(q['label'])+'</summary><p>'+escape('；'.join(q['outputs']))+'。</p></details>'
    html+='</div><h3>采集队要交什么，当前接通到哪里</h3><div class="arch-provider-grid">'
    by_id={p['id']:p for p in s['providers']}
    for p in s['observation_delivery']['profiles']:
        connection=by_id[p['provider_id']]['connection']
        state='已接通现有入口' if connection.startswith('receiver_live') or connection=='feed_v1_consumed' else '生产接收未接通；离线交付与验包可用'
        scope=by_id[p['provider_id']].get('connection_scope')
        if scope: state+='；'+scope
        html+='<div class="arch-node" data-provider="'+p['provider_id']+'"><h4>'+p['provider_id']+'</h4><p>'+escape(state)+'</p><ul>'+''.join('<li>'+escape(x)+'</li>' for x in p['deliver'])+'</ul><p><small>'+escape(p['limit'])+'</small></p></div>'
    html+='</div><p class="arch-limit">每篇报告都查信息去向：正文、计算表、图与附件 → 原件版本和定位 → 直接声明或推导依赖 → 已有资料／候选／假设／未知／异常／未检查／不适用及理由 → 对象、问题或待补资料。一次阅读或同链推导不算独立证据。</p>'
    return html
