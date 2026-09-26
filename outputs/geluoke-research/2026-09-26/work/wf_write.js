export const meta = {
  name: 'geluoke-write-events',
  description: 'Write daily-report event entries (hard template) from verified fact cards, then adversarially check each against its card',
  phases: [
    { title: 'Write', detail: 'one writer per event, from fact card + plan angle' },
    { title: 'Check', detail: 'one adversarial checker per event' },
  ],
}

const S = '/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad'

const EVENT = {
  type: 'object',
  properties: {
    no: { type: 'string' },
    title: { type: 'string', description: '具体事件标题，只写发生了什么，含关键数字，20-40字，不含判断词' },
    info_line: { type: 'string', description: '格式：地区 · 产业环节 · 事件日期（背景日期要标“背景”）' },
    para1: { type: 'string', description: '80-140字（可到160字），只写事实：主体、地点、动作、阶段、准确数字与单位；明确尚未披露或尚未完成的部分。不夹观察、点评。' },
    para2: { type: 'string', description: '80-140字：这项事实怎样改变客户、资本、资源、许可、工程、网络或运营中的哪一道交付条件；只基于已披露事实推导；不重复标题，不罗列空泛问题。' },
    sources_used: { type: 'array', items: { type: 'object', properties: { org: { type: 'string', description: '机构／媒体名（中文或原名），不含URL' }, url: { type: 'string' }, role: { type: 'string', description: 'primary / confirm / background' } }, required: ['org', 'url', 'role'] }, description: '2-4条，按优先级：政府/监管/电网文件 > 公司公告 > 主流媒体' },
    numbers_check: { type: 'array', items: { type: 'string' }, description: '正文中每个数字及其在fact card中的出处（自检）' },
    notes_for_editor: { type: 'string', description: '日期精度、口径差异、需在文末备注中提示的内容' },
  },
  required: ['no', 'title', 'info_line', 'para1', 'para2', 'sources_used', 'numbers_check', 'notes_for_editor'],
}

const VERDICT = {
  type: 'object',
  properties: {
    no: { type: 'string' },
    pass: { type: 'boolean' },
    problems: { type: 'array', items: { type: 'object', properties: { field: { type: 'string' }, issue: { type: 'string' }, fix: { type: 'string' } }, required: ['field', 'issue', 'fix'] } },
    corrected: { type: 'object', properties: { title: { type: 'string' }, info_line: { type: 'string' }, para1: { type: 'string' }, para2: { type: 'string' } }, required: ['title', 'info_line', 'para1', 'para2'], description: 'the full corrected entry (identical to input if pass)' },
  },
  required: ['no', 'pass', 'problems', 'corrected'],
}

const STYLE = `写作规范（格洛可数据中心日报）：简体中文；事实密度优先；不写“值得关注”“我们认为”“观察”等判断词；不用感叹号；数字保留来源单位（MW、GW、美元、英镑、令吉、卢比 crore 等），必要时括注换算并注明口径；区分事件日期与报道日期、规划与开工、融资承诺与到账、规划容量与投运容量；未披露的内容要明说“未披露”；不得写入fact card之外的任何数字、名称或日期；不写URL；标题格式示例：“BDx在西爪哇开工640MW园区，首栋120MW分期交付”。`

const ids = (args && args.nos) || []

phase('Write')
const drafts = await parallel(ids.map(no => () =>
  agent(`你是格洛可数据中心日报的撰稿人。请先用 Read 工具读取 ${S}/event_plan.json，找到 no 为 "${no}" 的事件条目（含 angle、region、chain、event_date、card 名、extra_cards、sweep_card/sweep_card2）。再用 Read 或 Bash(python3 -c ...) 从 ${S}/facts_all.json 中取出 facts[card]（以及 extra_cards 对应的卡片，若存在）；若条目带 sweep_card，其本身就是事实卡。只允许使用这些事实卡中的数字、名称与日期。

按硬模板产出这一条：
标题（具体、含数字）／信息行“地区 · 产业环节 · 事件日期”（按 event_date 字段写，背景日期标“背景”）／第一段（事实）／第二段（交付条件）。
${STYLE}
第一段末尾不要加引用编号（编辑会统一加）。在 numbers_check 中逐一列出正文每个数字及其在卡片中的出处字段。在 sources_used 中给出2-4条来源（机构名+URL+role），来自卡片 sources。返回结构化对象。`,
  { label: `write:${no}`, phase: 'Write', schema: EVENT })
))

phase('Check')
const checked = await parallel(drafts.map((d, i) => () => d ? agent(`你是对抗式核稿人。请 Read ${S}/event_plan.json 找到 no "${d.no}" 的条目，并从 ${S}/facts_all.json 取出对应事实卡（card、extra_cards、或条目内的 sweep_card/sweep_card2）。然后逐句核对下面这条日报稿：每个数字、单位、货币、日期、主体名称、地点、阶段用词（目标/获批/签约/融资承诺/融资到账/资源锁定/开工/投运/暂停/诉讼）是否与事实卡一致；是否把事件日期与报道日期混淆；是否把规划容量写成投运容量、把承诺写成到账；是否出现事实卡没有的信息；信息行是否符合“地区 · 产业环节 · 事件日期”且背景日期标注“背景”；第一段是否只有事实、第二段是否只谈交付条件；字数是否在80-160字/段。默认严格：任何不一致都算问题。给出问题清单与修正后的完整条目（若无问题则原样返回）。
稿件：
标题：${d.title}
信息行：${d.info_line}
第一段：${d.para1}
第二段：${d.para2}
撰稿人自检：${JSON.stringify(d.numbers_check)}
${STYLE}`, { label: `check:${d.no}`, phase: 'Check', schema: VERDICT }) : null))

return { drafts: drafts.filter(Boolean), checked: checked.filter(Boolean) }
