"""Source-derived research control room; runtime counters stay in material-flow."""
from collections import Counter
from html import escape
import json

STYLE = '''<style>
.audit-hero{margin:30px 0;padding:28px 0;border-top:3px solid var(--accent);border-bottom:1px solid var(--line)}
.audit-kicker{letter-spacing:.12em;color:var(--muted);font-size:12px}.audit-hero h2{font-size:32px;line-height:1.25;margin:12px 0}.audit-hero p{max-width:800px}
.audit-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px;margin:24px 0}.audit-metrics article{border-left:2px solid var(--line);padding-left:16px;min-width:0}.audit-metrics strong{display:block;font-size:34px;line-height:1.3;font-variant-numeric:tabular-nums}.audit-metrics span{color:var(--muted)}
.audit-nav{display:flex;flex-wrap:wrap;gap:8px 20px;margin:22px 0}.audit-section{scroll-margin-top:110px;border-top:1px solid var(--line);padding-top:12px;margin-top:36px}
.audit-section h2 small{font-size:13px;font-weight:400;color:var(--muted);display:block}.audit-map{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:24px 0}.audit-map article{padding:20px;background:var(--card);border:1px solid var(--line);border-top:3px solid var(--accent);min-width:0}.audit-map h3{margin:0 0 10px;font-size:17px}.audit-map p{margin:6px 0}.audit-map .audit-arrow{color:var(--muted);font-size:13px}.audit-section code{overflow-wrap:anywhere}.audit-section td{overflow-wrap:anywhere}.audit-section details{padding:16px 0}.audit-section summary{cursor:pointer;font-weight:600}.audit-callout{border-left:3px solid var(--accent);padding:8px 18px;margin:20px 0}.audit-legend{font-size:13px;color:var(--muted)}
@media(max-width:700px){.audit-metrics{grid-template-columns:1fr 1fr}.audit-map{grid-template-columns:1fr}.audit-hero{padding:20px 0}.audit-hero h2{font-size:26px}}
</style>'''


def build(root, table):
    def read(name): return json.loads((root/name).read_text())
    targets = read('framework/tco_targets.json')['targets']
    parts = read('framework/bom.json')['parts']
    questions = read('framework/research_questions.json')['records']
    knowledge = read('data/research_knowledge.json')
    providers = read('framework/supply_contract.json')['providers']
    counts = Counter(t['status'] for t in targets)
    html = '<section class="audit-hero"><div class="audit-kicker">INRESEARCH / 研究运营与架构</div><h2>从一个研究问题，追到一份原件。</h2><p>用同一棵数据中心骨架组织需求；用来源、内容身份和审核链路决定什么能成为研究结论。先看缺口和供应，再看处理与正式发布。</p><nav class="audit-nav" aria-label="本页审查目录">'
    labels = [('architecture','01 架构'),('skeleton','02 骨架'),('demand','03 需求与供应'),('gates','04 验收门槛'),('storage','05 数据与服务'),('engineering','06 代码与发布')]
    html += ''.join(f'<a href="#audit-{key}">{label}</a>' for key,label in labels) + '<a href="#material-board">运行实测 ↓</a></nav><div class="audit-metrics">'
    for value, title, note in [(len(targets),'资料目标','Git 需求投影'),(counts['needed'],'仍缺资料','不等于采集任务数'),(counts['delivered'],'已交付目标','不等于已研究采用'),(len(questions),'研究问题','不等于已有答案')]:
        html += f'<article><strong>{value:,}</strong>{title}<br><span>{note}</span></article>'
    html += '</div><p class="audit-legend">以上随源码生成；下方运行实测独立标注时间。sourced 是规则登记状态，仍需逐条检查来源、条件与时效；不得据此宣称研究问题已解决。</p></section>'
    def section(key, title, note): return f'<section id="audit-{key}" class="audit-section"><h2>{title}<small>{note}</small></h2>'
    html += section('architecture','01 · 一个骨架，三种持久载体','规范 → 领域规则 → 业务用例 → 接口；存储适配承担持久性')
    cards = [
        ('1 / 定义研究对象','骨架、站点权利、五类变量与统一经济模型。','输出研究问题和目标行 → 供应端','/node.html'),
        ('2 / 供应获取','inews 事件 feed；Fetchspec 官方目录、规格与原件包。','逐项验收 → SHA 原件与来源登记','/supply.html'),
        ('3 / 阅读与核验','Spark 提取、正文阅读、需求匹配、C3 与独立复核。','候选保留去向 → 审核发布队列','/node.html#research'),
        ('4 / 正式研究','Git 保存可审阅的研究版本；原件、候选和运行库另存。','受保护合并 → AWS 发布镜像','/report.html'),
        ('5 / 模型与视图','同一份证据供节点、账本、产品页与报告使用。','引用和假设分别呈现 → 回到缺口','/ledger.html'),
        ('6 / 反馈闭环','缺失来源、未支持问题、过期数据回到目标表。','需求行 ID → 原供应方补交','/supply.html#overview')]
    html += '<div class="audit-map" aria-label="研究架构与数据流">'
    for title, body, arrow, url in cards:
        html += f'<article><h3>{title}</h3><p>{body}</p><p class="audit-arrow">{arrow}</p><a href="{url}">打开对应工作面 →</a></article>'
    html += '</div><p>核心 Python 标准库；SQLite 保存事务状态，JSON 保存已发布声明与研究版本，文件系统保存不可变原件和阅读产物。CLI 与 HTTP 调用共享用例；供应方不得直写正式研究库。</p></section>'
    html += section('skeleton','02 · 图解释结构，目标表达需求','物理包含、功能连接、建设顺序、证据支持必须分开')
    kinds = Counter(p.get('kind','physical') for p in parts)
    html += f'<p>当前骨架登记 {len(parts)} 个条目，包含物理部件、软件与基型；具体身份以 BOM 的 kind 为准。五个顶层系统为设施、水与散热、电、IT设施、控制与软件；IT 下分计算、存储与网络，存储再分内存与持久存储。六类站点权利独立登记。</p>'
    html += '<details><summary>展开骨架与图的边界</summary>' + table(['表示法','能证明什么','必须保留的边界'],[
        ['爆炸图 / 平面 / 剖面','部件位置、尺度与组成的示例讲解','不是完整现场拓扑；软件与权利不造物理件；未建模明确显示'],
        ['研究问题 × 五类变量','某对象需要哪种数据、为什么需要','同一来源可支持多个问题；共享能力不得在不同子树重复累加'],
        ['目标行 → 供应任务','目标 ID、对象 ID、变量类、来源机制、执行机与日历','派工、交付、采用分开；版本改变不改稳定 ID'],
        ['经济模型','输入如何影响成本、收入与回报','假设、观测和推算分开；额定功率不等于实耗，报价不等于成交']])
    html += '<p><a href="/bom.html">查看爆炸图</a> · <a href="/node.html">查看节点与缺口</a> · <a href="/ledger.html">查看经济模型</a></p></details></section>'
    html += section('demand','03 · 两个已接供应方，四类待接能力','目标覆盖按同一 Git 快照计算；历史资料不证明持续供给')
    rows=[]
    for p in providers:
        if not p.get('team'): continue
        ts=[t for t in targets if t['team']==p['team']];c=Counter(t['status'] for t in ts)
        rows.append([p['name'], '已接入' if p['connection']!='not_connected' else '未接入',len(ts),c['needed'],c['delivered'],c['sourced'],c['assumed']])
    html += table(['能力','接入','目标','缺','交付','有数据登记','假设'],rows)
    html += '<div class="audit-callout">inews 提供发现线索和事件；Fetchspec 提供官方产品资料。价格、财报、统计、工期与运行实证仍有独立来源要求；新增 repo 不是默认答案，先给现有供应任务明确来源、交付条件和负责人。</div>'
    html += '<p>目标状态依赖 Git 内可复现载体。运行库已收而 Git 未登记的交付不能计入 delivered；新闻标签与原件指针不能直接变成正式证据。供应中心用于核对任务与逐项回执。</p><p><a href="/supply.html#coverage">检查覆盖与任务 →</a></p></section>'
    html += section('gates','04 · 四道门，每道门有独立结果','拒绝、需补充、候选、正式采用分别保存；拒绝不删除原件')
    html += '<p>传输验收 → 阅读或定向提取 → 研究采用 → 发布。每道门独立记录，前一环节通过不授予下一环节资格。</p><details><summary>展开接受、拒绝与补充条件</summary>' + table(['门槛','接受条件','拒绝或补充','下一步资格'],[
        ['传输与资料验收','来源与权限范围、清单集合、路径边界、大小及 SHA 一致；目标归属有效','越界、缺件、哈希不符不归档；不可解析资料保存并标需补充','仅证明原件已接收与编目'],
        ['正文 / 定向提取','格式可解析、内容身份一致、覆盖与缺页明示、冻结版本可复验','模型失败、封印失败或超出缺页门槛阻断；产品规格不强求全文研究','只产生可核验的候选或规格观察'],
        ['研究采用','需求匹配、原文位置、单位/时点/配置、C3 与独立复核、支持闭包','证据不足回补；重复/背景/争议保留；不能用评分自动放行','进入已审阅研究增量'],
        ['发布与对外服务','精确 head 检查通过、当前上下文有效、受保护合并、部署与网站回执','失败、冲突、过期上下文不能算上线；排队不算采用','可引用的正式版本与服务']])
    html += '</details></section>'
    html += section('storage','05 · 原件、运行数据库、正式版本','不要用数据库文件大小代表材料总量或阅读完成率')
    html += '<p>原件保存在 Spark 文件目录；运行状态分库使用 SQLite；正式研究版本使用 Git 中的 JSON 与 Markdown。</p><details><summary>展开存储格式与服务职责</summary>' + table(['载体 / 格式','内容与权威','提供的服务'],[
        ['Spark 原件 / 文件 + SHA-256','永久原件、历史版本、正文与图像产物；目录可能含硬链接及副本','重放提取、追溯引文与来源；原件不随任务过期删除'],
        ['Reader / SQLite','文档与来源、任务、阅读版本、当前报告指针','排队、恢复、覆盖查询；登记不等于已读'],
        ['Acquisition / SQLite + blobs','新闻、交付、观察与产品资料索引','来源去重、按对象/型号检索；事件不等于事实'],
        ['Review / SQLite + 私有产物','候选去向、尝试、独立复核、发布状态','定位阻塞、重试与审计；核验通过不等于上线'],
        ['AWS 产品库 / 按公司 SQLite','产品、来源、观察版本、原厂参数及条件','产品页与版本查询；不覆盖正式研究'],
        ['Git / JSON + Markdown','正式研究陈述、证据、问题、模型及规范；部署镜像只读','节点研究、账本、报告与版本审阅'],
        ['私有 JSON / JSONL','派工、供应台账、账号、回执与可恢复预备日志','运行写入和审计；不在静态网站公开']])
    html += f'<p>此源码快照有 {len(knowledge["documents"])} 份正式研究文档记录、{len(knowledge["evidence"])} 条证据、{len(knowledge["statements"])} 条陈述、{len(knowledge["answers"])} 条正式答案记录。陈述总数包含不同采用状态；下方“正式展示”仅计支持链成立的采用，二者不可互换。</p><p><a href="#material-board">查看实际库容量、原件目录与各环节状态 ↓</a></p></details></section>'
    html += section('engineering','06 · 按风险验收，按实质变更发布','CI 现行入口 docs/CI.md；validate 与 browser (core) 两个稳定门禁')
    html += '<p>普通资料按影响范围验收，代码与规则改动保持完整回归。每日运行状态使用私有投影，实质代码变更经 PR 发布。</p><details><summary>展开 CI 与发布纪律</summary>' + table(['改动','应跑范围','发布纪律'],[
        ['有界研究追加','全量引用校验、固定研究单元与研究浏览器','相同上下文的独立批次可汇总；每批仍有独立回执'],
        ['普通文案 / 已知图像','基础检查与相关页面或图像场景','不为每日运行状态单独造 PR'],
        ['代码 / 规则 / 旧事实 / 结构 / 未知影响','完整单元、浏览器、资产与存储回归','最终 head 全部所选检查成功；不可跳失败检查'],
        ['运行状态','私有运行快照与带时间的指标','不能把运行快照冒充正式研究版本']])
    html += '<p>优先修复已复现的边界冲突与瓶颈。长模块需要按事务和用例分解，未引用文件须先排查动态 CLI、静态路由、部署与历史用途；不能仅凭文件年龄或搜索零命中删除。</p></details></section>'
    return html
