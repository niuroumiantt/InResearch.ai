export const meta = {
  name: 'geluoke-longform-condense',
  description: 'Condense each chapter to publication length without losing evidence labels, then verify no numbers were added or silently dropped',
  phases: [
    { title: 'Condense', detail: 'one editor per chapter' },
    { title: 'Verify', detail: 'diff check: no new numbers, key numbers kept' },
  ],
}
const S = '/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad/longform'
const PARA = { type: 'object', properties: { text: { type: 'string' }, cites: { type: 'array', items: { type: 'string' } } }, required: ['text','cites'] }
const OUT = { type: 'object', properties: {
  no: { type: 'string' }, title: { type: 'string' },
  paras: { type: 'array', items: PARA, minItems: 9, maxItems: 16 },
  figure_after_para: { type: 'integer', description: '图放在第几段之后（0起），指向压缩后的段落' },
  dropped_numbers: { type: 'array', items: { type: 'string' }, description: '被删去的数字及其原段落含义（供编辑判断是否放入备注）' },
  kept_sources: { type: 'array', items: { type: 'string' }, description: '压缩后仍被引用的来源键' },
}, required: ['no','title','paras','figure_after_para','dropped_numbers','kept_sources'] }
const VERDICT = { type: 'object', properties: { no: { type: 'string' }, pass: { type: 'boolean' }, problems: { type: 'array', items: { type: 'object', properties: { para: { type: 'integer' }, issue: { type: 'string' }, fix: { type: 'string' } }, required: ['para','issue','fix'] } }, corrected: OUT }, required: ['no','pass','problems','corrected'] }

const items = args.items || []

const out = await pipeline(items,
  it => agent(`你是格洛可数据中心专题长文的责任编辑。请先用 Read 读取 ${it.file}（第${it.no}章经核稿的定稿：title、paras[{text,cites}]、figure_after_para）。该章超出发布篇幅，请压缩到 ${it.target}，要求：
1. 只删、只合并、只改写，不新增任何数字、名称、日期；不得改变任何数字的值、单位、期间与属性标注（已披露事实／研究实测／预测估算／作者说明性计算）。
2. 保留结构：概念与机制—数据证据—对比与影响—约束与验证指标；每章保留至少一个作者说明性计算及其公式；保留结尾的验证指标段；保留章节标题（可微调）。
3. 删除优先级：同一数字的第二次重述 > 次要案例（同类案例保留最多3个）> 纯核对句（如“作者复算 153×0.79＝120.9”）> 对来源版本的说明（移入 dropped_numbers 供编辑放备注）。
4. 每段 80–200 字；段落的 cites 只保留该段仍依据的来源键；合并段落时合并 cites。
5. 图的位置（原 figure_after_para）在压缩后指向语义相同的段落。
6. 简体中文，不写URL，不用感叹号。
返回结构化对象。`, { label: `condense:ch${it.no}`, phase: 'Condense', schema: OUT }),
  (c, it) => c ? agent(`你是核稿人。请用 Read 读取原稿 ${it.file}，对比下面的压缩稿：(1) 压缩稿中出现而原稿没有的任何数字、名称、日期、单位或属性标注都算问题（逐个数字核对）；(2) 原稿中任何数字在压缩稿中数值、单位、期间或属性标注发生变化都算问题；(3) 压缩稿是否仍含至少一个带公式的作者说明性计算与结尾验证指标；(4) 每段 80–200 字、段数符合 ${it.target}；(5) cites 键是否都来自原稿。修正后返回完整对象（无问题则原样返回）。
压缩稿：${JSON.stringify(c)}`, { label: `verify:ch${it.no}`, phase: 'Verify', schema: VERDICT }) : null
)
return { chapters: out.filter(Boolean) }
