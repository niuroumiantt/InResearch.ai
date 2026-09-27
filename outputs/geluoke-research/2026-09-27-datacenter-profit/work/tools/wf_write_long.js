export const meta = {
  name: 'geluoke-longform-write',
  description: 'Write long-form chapters from verified cards and report excerpts, then adversarially check each chapter',
  phases: [
    { title: 'Write', detail: 'one writer per chapter' },
    { title: 'Check', detail: 'one adversarial checker per chapter' },
  ],
}
const S = '/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad/longform'

const PARA = { type: 'object', properties: {
  text: { type: 'string', description: '一段正文，80–200字，简体中文；不含URL；不含引用编号（编辑统一加）' },
  cites: { type: 'array', items: { type: 'string' }, description: '本段依据的来源键，来自 sources_used 的 key' },
}, required: ['text','cites'] }

const CHAPTER = { type: 'object', properties: {
  no: { type: 'string' },
  title: { type: 'string', description: '章节标题（H2），12–24字，直接表达本章判断或问题，不含编号' },
  paras: { type: 'array', items: PARA, minItems: 8, description: '按 对象与概念—作用机制—数据证据—对比与影响—约束与验证指标 的顺序' },
  figure: { type: 'object', properties: {
    id: { type: 'string' }, after_para: { type: 'integer', description: '图放在第几段之后（0起）' },
    title: { type: 'string', description: '图题 ≤22字' }, subtitle: { type: 'string', description: '副题 ≤40字，含单位与期间' },
    caption: { type: 'string', description: '图注 40–120字：单位、期间、数据属性（预测估算/已披露事实/作者说明性计算）、口径、来源机构' },
    data: { type: 'array', items: { type: 'object', properties: { label: { type: 'string' }, value: { type: 'string' }, unit: { type: 'string' }, note: { type: 'string' } }, required: ['label','value'] }, description: '图中要呈现的数据点（供制图核对）' },
  }, required: ['id','after_para','title','subtitle','caption','data'] },
  sources_used: { type: 'array', items: { type: 'object', properties: { key: { type: 'string' }, org: { type: 'string', description: '机构名（中文或原名），如“摩根士丹利”“万国数据 2026年第二季度业绩公告”' }, title: { type: 'string' }, url: { type: 'string' }, date: { type: 'string' }, kind: { type: 'string' } }, required: ['key','org','url','date'] } },
  numbers_check: { type: 'array', items: { type: 'object', properties: { number: { type: 'string' }, evidence_class: { type: 'string' }, where: { type: 'string', description: '出处：文件名+页码/卡片id+metric' } }, required: ['number','evidence_class','where'] } },
  notes_for_editor: { type: 'string', description: '口径差异、需在文末备注中提示的内容、未能核实而删去的内容' },
}, required: ['no','title','paras','figure','sources_used','numbers_check','notes_for_editor'] }

const VERDICT = { type: 'object', properties: {
  no: { type: 'string' }, pass: { type: 'boolean' },
  problems: { type: 'array', items: { type: 'object', properties: { para: { type: 'integer' }, issue: { type: 'string' }, fix: { type: 'string' } }, required: ['para','issue','fix'] } },
  corrected: CHAPTER,
}, required: ['no','pass','problems','corrected'] }

const STYLE = `写作规范（格洛可数据中心专题长文）：简体中文；事实密度优先；先解释机制，再给证据，再谈影响与约束；每个百分比说明分母；数字首次出现时说明属性（已披露事实／研究实测／厂商测试／预测估算／作者说明性计算）；预测注明提出机构与日期（如“摩根士丹利2026年9月估算”）；区分计划、签约、开工、投运，区分合同总额与年租金、承诺与到账；作者换算必须写出公式与取整；不写“值得关注”“我们认为”“毫无疑问”，不用感叹号；不写URL；不得写入输入文件之外的任何数字、名称或日期；正文不写内部检索或工具过程；金额单位统一写法：美元用“亿美元／万亿美元”，人民币用“亿元”，并保留来源原始口径（如“十亿美元”可换算为“亿美元”但要一致）；GPU小时价写“美元/GPU·小时”。段落之间不要用小标题。`

const spec = JSON.parse(args.chapters_json)
const ids = args.nos || []
const chapters = spec.chapters.filter(c => ids.includes(c.no))

const out = await pipeline(chapters,
  ch => agent(`你是格洛可数据中心专题长文《造一座数据中心有多挣钱》的撰稿人，负责第${ch.no}章。
先用 Read 读取：${S}/outline_v1.md（全文结构）、${S}/report_facts.md（两份研报摘录，含页码）、${S}/research/cards.json（经复核的研究卡；本章重点用 ${JSON.stringify(ch.cards)}）、${S}/../facts_all.json（9月26日日报事实卡，按需用 Bash python3 -c 打印指定卡片）、以及 ${spec.common_inputs.prior_article}（格洛可9月14日成本专题，按需读 §16–§20）。
本章目标：${ch.goal}
本章图：${JSON.stringify(ch.figure)}
篇幅：${ch.length}。
只允许使用上述文件中的数字、名称与日期。写出章节标题、正文段落（每段附来源键）、图的标题/副题/图注/数据点、来源清单、逐一数字自检与给编辑的说明。
${STYLE}
返回结构化对象。`, { label: `write:ch${ch.no}`, phase: 'Write', schema: CHAPTER }),
  (d, ch) => d ? agent(`你是对抗式核稿人。请 Read ${S}/report_facts.md、${S}/research/cards.json、${S}/../facts_all.json（按需）与 ${spec.common_inputs.prior_article}（按需），逐句核对下面第${ch.no}章：每个数字、单位、期间、主体、日期、阶段用词是否与输入文件一致；百分比是否说明分母；每个数字是否标明属性（已披露事实／研究实测／厂商测试／预测估算／作者说明性计算）且标注正确；作者换算是否写出公式且算术正确（请复算）；是否混淆合同总额与年租金、承诺与到账、规划与投运、EBITDA 与净利润；是否出现输入文件没有的信息；段落是否按“机制—证据—影响—约束”推进而非罗列；是否有空泛判断词；图的数据点是否与正文一致。默认严格。返回问题清单与修正后的完整章节（无问题则原样返回）。
本章目标：${ch.goal}
稿件：${JSON.stringify(d)}
${STYLE}`, { label: `check:ch${ch.no}`, phase: 'Check', schema: VERDICT }) : null
)
return { chapters: out.filter(Boolean) }
