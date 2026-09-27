export const meta = {
  name: 'geluoke-longform-lead',
  description: 'Write title, leads, coverage line, commentary, notes and cover texts for the long-form; check; then judge cross-chapter coherence',
  phases: [
    { title: 'Lead', detail: 'title, leads, commentary, notes, cover' },
    { title: 'Check', detail: 'adversarial check of lead package' },
    { title: 'Judge', detail: 'cross-chapter coherence and repetition' },
  ],
}
const S = '/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad/longform'

const LEAD = { type: 'object', properties: {
  title: { type: 'string', description: '完整标题，含核心判断，≤40字；可用“——”分主副题' },
  title_short: { type: 'string', description: '首图用短标题 ≤22字' },
  lead1: { type: 'string', description: '导语一 120–200字：交代要回答的问题与本文使用的三组核心账本（含数字）' },
  lead2: { type: 'string', description: '导语二 120–200字：研究结论与边界（哪些是预测估算、哪些是已披露合同；中国作参照）' },
  coverage_line: { type: 'string', description: '“本篇覆盖：”开头一行，列地区与产业环节' },
  commentary: { type: 'array', items: { type: 'string' }, minItems: 3, maxItems: 3, description: '格洛可点评三段，每段150–220字：第一段说明利润在四层之间如何分配及其结构原因；第二段连接美国、欧洲/亚太与中国的差异并引用已核验具名案例（标日期）；第三段列出会强化或削弱结论的可验证节点（含日期）。连贯段落，不复述正文，不列问题清单。' },
  notes: { type: 'string', description: '“备注：”后的连续段落 120–260字：说明预测估算的机构与日期、作者换算的公式所在、汇率与单位口径、报告版本、未能核实而未采用的内容' },
  cover: { type: 'object', properties: {
    subtitle: { type: 'string', description: '首图副题 ≤30字' },
    claim: { type: 'string', description: '一句可验证结论 ≤40字，含数字' },
    ledger: { type: 'object', properties: { capex: { type: 'string' }, it_capex: { type: 'string' }, non_it_capex: { type: 'string' }, revenue: { type: 'string' }, opex: { type: 'string' }, tax: { type: 'string' }, nopat: { type: 'string' }, roic: { type: 'string' } }, required: ['capex','it_capex','non_it_capex','revenue','opex','tax','nopat','roic'], description: '首图剖面图数字（来自MS 1GW GB300账本），带单位' },
    paths: { type: 'array', minItems: 3, maxItems: 3, items: { type: 'object', properties: { name: { type: 'string' }, roic: { type: 'string' } }, required: ['name','roic'] } },
    modules: { type: 'array', minItems: 5, maxItems: 5, items: { type: 'object', properties: { name: { type: 'string' }, fact_html: { type: 'string', description: '≤40字，关键数字用<b>…</b>' } }, required: ['name','fact_html'] }, description: '固定顺序：壳层租约、融资结构、电力与监管、折旧与价格、中国参照' },
    layers: { type: 'array', minItems: 4, maxItems: 4, items: { type: 'object', properties: { name: { type: 'string' }, unit: { type: 'string', description: '该层的收入单位与典型合同形态，≤18字' } }, required: ['name','unit'] }, description: '固定顺序：带电的壳、机柜托管、GPU云、模型API' },
    conclusion: { type: 'string', description: '≤36字' },
  }, required: ['subtitle','claim','ledger','paths','layers','modules','conclusion'] },
  sources_added: { type: 'array', items: { type: 'object', properties: { key: { type: 'string' }, org: { type: 'string' }, url: { type: 'string' }, date: { type: 'string' } }, required: ['key','org','url','date'] }, description: '点评中新引用而各章 sources_used 未包含的来源' },
}, required: ['title','title_short','lead1','lead2','coverage_line','commentary','notes','cover','sources_added'] }

const VERDICT = { type: 'object', properties: { pass: { type: 'boolean' }, problems: { type: 'array', items: { type: 'object', properties: { field: { type: 'string' }, issue: { type: 'string' }, fix: { type: 'string' } }, required: ['field','issue','fix'] } }, corrected: LEAD }, required: ['pass','problems','corrected'] }

const JUDGE = { type: 'object', properties: {
  summary: { type: 'string' },
  edits: { type: 'array', items: { type: 'object', properties: { chapter: { type: 'string' }, para: { type: 'integer' }, reason: { type: 'string' }, new_text: { type: 'string', description: '替换后的整段文本；删除该段则为空字符串' } }, required: ['chapter','para','reason','new_text'] }, description: '跨章重复、数字矛盾、缺少属性标注、百分比无分母、口径不一致等需要修改的段落' },
  title_edit: { type: 'string', description: '若标题需改，给出新标题；否则空' },
  unresolved: { type: 'array', items: { type: 'string' }, description: '无法在文本层面解决、需要编辑决定的问题' },
}, required: ['summary','edits','title_edit','unresolved'] }

const STYLE = `写作规范：简体中文；事实密度优先；每个百分比说明分母；数字标明属性（已披露事实／研究实测／预测估算／作者说明性计算）与机构日期；不写“值得关注”“我们认为”；不用感叹号；不写URL；不得写入章节与输入文件之外的数字、名称或日期。`

phase('Lead')
const draft = await agent(`你是格洛可数据中心专题长文《造一座数据中心有多挣钱》的主编。请 Read ${S}/chapters_final.json（六章定稿：标题、段落 paras、图 figure、来源 sources_used；请用 Bash python3 -c 只打印 no/title/paras[].text/figure.caption，忽略 _orig_paras 等下划线字段）、${S}/outline_v1.md、${S}/report_facts.md、${S}/dropped_numbers.md（各章压缩时删去、建议放入备注的口径说明），按需读 ${S}/research/cards.json 与 ${S}/../facts_all.json。备注段应优先收录 dropped_numbers.md 中标注“建议放备注”的来源版本与口径说明（如 Beignet 条款仅见于 IFR、CoreWeave 8.3% 为路演材料口径、MS 三项取整、高盛与 MS 的 AI 债口径差异、两套用电预测基数不同、汇率 6.79 为万国数据公告隐含值），以及本文使用的报告版本与日期。
请写：完整标题与首图短标题；两段导语；“本篇覆盖”一行；三段格洛可点评；备注；首图文字（副题、结论句、剖面图数字、三条路径、四层收入单位、五个模块、一句结论）。首图剖面图数字必须来自摩根士丹利 1GW GB300 账本（report_facts.md A1）。
${STYLE}
返回结构化对象。`, { label: 'lead', phase: 'Lead', schema: LEAD })

phase('Check')
const checked = await agent(`你是对抗式核稿人。请 Read ${S}/chapters_final.json 与 ${S}/report_facts.md，逐句核对下面的标题、导语、覆盖行、点评、备注与首图文字：每个数字、单位、日期、主体是否与章节或研报摘录一致；点评是否引用了章节里没有的案例；是否有空泛判断；首图剖面图数字是否与 MS 账本一致（capex 390、IT 230、非IT 160、收入 229、营业成本 76、税 32、NOPAT 121、ROIC 31%，单位亿美元/GW/年）；字数是否符合。默认严格。返回问题清单与修正后的完整对象。
稿件：${JSON.stringify(draft)}
${STYLE}`, { label: 'check-lead', phase: 'Check', schema: VERDICT })

phase('Judge')
const judge = await agent(`你是终审编辑。请 Read ${S}/chapters_final.json（六章；用 Bash python3 -c 只打印 no/title/paras[].text，忽略下划线字段）并结合下面的导语与点评，检查全文：(1) 跨章重复的数字或句子（同一数字最多在两处出现，第二次应引用第一次的结论而非重述）；(2) 各章之间的数字矛盾或单位口径不一致（亿美元/十亿美元、亿元、GW/MW）；(3) 缺少属性标注或分母的百分比；(4) 预测被写成事实、合同总额被写成年收入；(5) 章节之间的逻辑衔接是否呼应导语提出的问题；(6) 中国章是否只写参数差异而不写价值判断。对需要修改的段落给出整段替换文本（保持原有事实与来源，只改表述），不新增任何数字。
导语与点评：${JSON.stringify(checked.corrected)}
${STYLE}`, { label: 'judge', phase: 'Judge', schema: JUDGE })

return { lead: checked.corrected, lead_problems: checked.problems, judge }
