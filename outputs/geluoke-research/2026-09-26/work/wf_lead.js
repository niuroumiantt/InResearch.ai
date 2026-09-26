export const meta = {
  name: 'geluoke-write-lead',
  description: 'Write title, two leads, coverage line, three-paragraph commentary, notes and cover texts from verified fact cards; then adversarially check',
  phases: [
    { title: 'Lead', detail: 'title, leads, commentary, notes, cover texts' },
    { title: 'Check', detail: 'adversarial check against fact cards' },
  ],
}

const S = '/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad'

const LEAD = {
  type: 'object',
  properties: {
    judgement: { type: 'string', description: '中心判断，12-24字，由当天至少三条事件共同支持' },
    title: { type: 'string', description: '格式：格洛可数据中心日报｜2026年9月26日：中心判断' },
    lead1: { type: 'string', description: '90-140字：当天中心变化，点名至少三条具名事件与关键数字' },
    lead2: { type: 'string', description: '90-140字：不同地区或交付环节的差异；不得把事件重新列一遍' },
    coverage_line: { type: 'string', description: '“本期覆盖：”开头，列区域与环节，不写观察窗口、候选数或内部方法' },
    commentary: { type: 'array', items: { type: 'string' }, minItems: 3, maxItems: 3, description: '三段，每段100-160字：第一段比较当天至少三项具名事件；第二段连接两个以上地区并说明差异，可引用经核验的关联案例（标明日期）；第三段指出下一步应跟踪的可验证节点（含日期）。禁止问答式空话、逐条重复、无来源预测。' },
    notes: { type: 'string', description: '“备注：”后的连续段落，60-160字：读者需要的背景日期、阶段差异和信息设计性质（例如哪些事件发生在9月24日美国时间、窗口内为跟进；图表数字为披露口径）；不写观察窗口、候选数、核验过程、URL' },
    cover: {
      type: 'object',
      properties: {
        edition_tag: { type: 'string', description: '3-4个词，用“ · ”分隔，如“电力 · 许可 · 资金”' },
        title_html: { type: 'string', description: '首图大标题，20-34字，可用<em>…</em>包住最关键的一句（金色）' },
        subtitle: { type: 'string', description: '副标题 18-32字' },
        claim: { type: 'string', description: '一句可验证的结论，24-40字，含至少一个数字' },
        modules: { type: 'array', minItems: 5, maxItems: 5, items: { type: 'object', properties: { name: { type: 'string' }, sub: { type: 'string' }, fact_html: { type: 'string', description: '≤44字的当天具体事实，关键数字用<b>…</b>' }, maps_to_no: { type: 'string' } }, required: ['name', 'sub', 'fact_html', 'maps_to_no'] }, description: '固定顺序：客户／资本、土地／许可、电力／水／成本、工程／设备／验收、网络／运营／区域交付；每个对应正文一条事实' },
        regions: { type: 'array', minItems: 4, maxItems: 4, items: { type: 'object', properties: { name: { type: 'string' }, text: { type: 'string', description: '≤34字' } }, required: ['name', 'text'] }, description: '中国、北美、南亚、东南亚；中国若窗口内无园区级新事件，要如实写“窗口内无新增园区级事件”并给出带日期的背景' },
        conclusion: { type: 'string', description: '≤36字的一句结论' },
      },
      required: ['edition_tag', 'title_html', 'subtitle', 'claim', 'modules', 'regions', 'conclusion'],
    },
    named_cases_used: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, date: { type: 'string' }, card: { type: 'string' }, org: { type: 'string' }, url: { type: 'string' } }, required: ['name', 'date', 'card', 'org', 'url'] }, description: '点评中引用的关联案例及其来源（卡片名、机构、URL）' },
  },
  required: ['judgement', 'title', 'lead1', 'lead2', 'coverage_line', 'commentary', 'notes', 'cover', 'named_cases_used'],
}

const VERDICT = {
  type: 'object',
  properties: {
    pass: { type: 'boolean' },
    problems: { type: 'array', items: { type: 'object', properties: { field: { type: 'string' }, issue: { type: 'string' }, fix: { type: 'string' } }, required: ['field', 'issue', 'fix'] } },
    corrected: LEAD,
  },
  required: ['pass', 'problems', 'corrected'],
}

const STYLE = `写作规范：简体中文；事实密度优先；点评要有深度：说明当天事件改变了什么、如何影响项目、有哪些条件或局限，并关联全球同主题的其他具名事件（须来自事实卡，标明日期）；不复述标题、不列问题清单、不套通用结论；开放问题只能作收尾。不得写入事实卡之外的任何数字、名称或日期；不写URL；不写“值得关注”“我们认为”。数字保留来源单位并区分口径（合同承诺≠到账、规划≠投运、目标≠已建）。`

phase('Lead')
const draft = await agent(`你是格洛可数据中心日报的主编。请 Read ${S}/event_plan.json（含主题 theme、15条事件的 no/card/angle/region/chain/event_date、related_for_commentary 卡片名、sweep_related_cards），再从 ${S}/facts_all.json 读取全部 facts 卡片（可用 Bash: python3 -c 读取并打印每张卡的 headline_zh / facts_zh / delivery_condition_zh / background_zh / event_date / in_window / caveats）。sweeps 中的区域候选也在同一文件（sweeps[区域].candidates）。

请写出：中心判断与标题；两段导语；本期覆盖一行；三段格洛可点评；备注；以及首图文字（副标题、结论句、五个模块事实、四个区域对照、一句结论）。首图五个模块必须各对应正文中的一条具体事实并写明 maps_to_no。点评第二段要连接至少两个地区，可引用事实卡里经核验的关联案例（如加州9月21日7项法案、俄勒冈UE 463和解、新泽西DataOne罚款、澳大利亚、安得拉邦70%可再生、越南胡志明电价争议、阿里云20GW目标等），每个案例标明日期。第三段列出可验证的下一步节点（如ERCOT 12月10日报告、TCEQ 10月19日、新墨西哥州环境部11月23日、OPUC 11月13日、泰国10月中旬、Nscale英伟达11月中旬到账、TVA 10月1日等，须来自卡片）。
${STYLE}
返回结构化对象。`, { label: 'lead', phase: 'Lead', schema: LEAD })

phase('Check')
const checked = await agent(`你是对抗式核稿人。请 Read ${S}/event_plan.json 并从 ${S}/facts_all.json 读取全部事实卡。逐句核对下面的导语、点评、备注与首图文字：每个数字、单位、日期、主体、地点、阶段用词是否与事实卡一致；是否出现事实卡没有的信息；中心判断是否由至少三条事件支持；点评三段是否分别满足“比较三项具名事件／连接两个以上地区／列出可验证节点”；首图五个模块是否各对应一条正文事实（maps_to_no 与 event_plan 一致）且不是空标签；字数是否符合要求。默认严格。返回问题清单与修正后的完整对象（无问题则原样返回）。
稿件：${JSON.stringify(draft)}
${STYLE}`, { label: 'check-lead', phase: 'Check', schema: VERDICT })

return { draft, checked }
