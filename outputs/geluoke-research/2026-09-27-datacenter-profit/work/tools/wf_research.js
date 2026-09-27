export const meta = {
  name: 'geluoke-longform-research',
  description: 'Fetch and verify profitability datapoints for the data-center long-form, then adversarially re-check each card',
  phases: [
    { title: 'Fetch', detail: 'one researcher per topic, primary sources' },
    { title: 'Refute', detail: 'one skeptic per card re-checks every number' },
  ],
}

const DP = { type: 'object', properties: {
  metric: { type: 'string', description: '指标名（中文，含主体与口径，如“CoreWeave 2026Q2 收入”）' },
  value: { type: 'string' }, unit: { type: 'string' },
  period: { type: 'string', description: '期间或时点，如 2026Q2 / 2026-06-30 / 2026-2028E' },
  denominator_or_scope: { type: 'string', description: '百分比的分母、口径、范围；金额的币种与是否年化' },
  evidence_class: { type: 'string', description: '已披露事实 / 研究实测 / 厂商测试 / 预测估算 之一' },
  source_org: { type: 'string' }, source_url: { type: 'string' }, source_date: { type: 'string' },
  quote: { type: 'string', description: '来源原文短引（原语言，≤200字符）' },
}, required: ['metric','value','unit','period','denominator_or_scope','evidence_class','source_org','source_url','source_date'] }

const CARD = { type: 'object', properties: {
  id: { type: 'string' }, topic: { type: 'string' },
  verified: { type: 'boolean', description: 'true 仅当核心数字确实从已抓取页面确认' },
  summary_zh: { type: 'string', description: '250-500字中文事实摘要：主体、时间、数字、单位、口径、尚未披露的部分。只写事实，不评论' },
  datapoints: { type: 'array', items: DP, minItems: 3 },
  background_zh: { type: 'string', description: '理解这些数字所需的带日期背景' },
  computed_zh: { type: 'string', description: '若做了换算（如合同总额÷年限÷MW），写出公式、输入、取整；无则写“无”' },
  caveats: { type: 'string' },
  sources: { type: 'array', items: { type: 'object', properties: { org: {type:'string'}, title:{type:'string'}, url:{type:'string'}, kind:{type:'string', description:'company filing/release, regulator, research firm, major media, trade media, price list'}, date:{type:'string'} }, required:['org','url','kind'] } },
  confidence: { type: 'string', description: 'high / medium / low' },
}, required: ['id','topic','verified','summary_zh','datapoints','background_zh','computed_zh','caveats','sources','confidence'] }

const VERDICT = { type: 'object', properties: {
  id: { type: 'string' },
  pass: { type: 'boolean' },
  problems: { type: 'array', items: { type: 'object', properties: { metric:{type:'string'}, issue:{type:'string'}, fix:{type:'string'}, source_url:{type:'string'} }, required:['metric','issue','fix'] } },
  added_datapoints: { type: 'array', items: DP, description: '复核中发现的、对主题重要但原卡缺失的数据点' },
  corrected: CARD,
}, required: ['id','pass','problems','added_datapoints','corrected'] }

const COMMON = `You are a researcher for a Chinese-language data-center industry long-form article (格洛可数据中心专题) titled “造一座数据中心有多挣钱”. Today is 2026-09-27.
Tools: WebSearch to locate ORIGINAL sources (company filings/press releases/investor decks > regulator/exchange documents > research-firm reports > major media), then WebFetch the page to confirm. Google News RSS links are redirects: search the headline to find the real article. Fetch at least two independent pages per topic where possible. Aim to finish within about 15 tool calls.
Rules: never invent numbers. Record units, currency, period and the denominator of every percentage. Distinguish 已披露事实 (company/regulator disclosure), 研究实测 (measured by a research firm), 厂商测试 (vendor test), 预测估算 (forecast/estimate). Distinguish planned vs operating, committed vs closed, contract value vs annual rent. If you compute a derived number (e.g. contract value ÷ years ÷ MW), show the formula in computed_zh and label it 作者说明性计算. Write Chinese fields in simplified Chinese, concrete and neutral. Return only the structured object.`

const items = (args && args.items) || []

const cards = await pipeline(items,
  it => agent(`${COMMON}

Topic id: ${it.id}
Topic: ${it.topic}
What to find: ${it.prompt}

Do the research now and return the card.`, { label: `fetch:${it.id}`, phase: 'Fetch', schema: CARD }),
  (card, it) => card ? agent(`You are an adversarial fact-checker. Today is 2026-09-27. Re-verify EVERY datapoint in the card below by fetching the cited source_url (WebFetch) and, where the number matters, at least one independent source (WebSearch + WebFetch). Check value, unit, period, denominator, evidence_class, and whether the quote really appears. Flag: wrong numbers, mixed periods, planned-vs-operating confusion, contract value vs annual rent, non-primary sources when a primary exists, and any missing datapoint that the topic obviously needs (add it under added_datapoints with a source). Default to strict: any inconsistency is a problem. Return problems plus the fully corrected card (identical to input if it passes).
Topic: ${it.topic}
What was asked: ${it.prompt}
Card: ${JSON.stringify(card)}`, { label: `refute:${it.id}`, phase: 'Refute', schema: VERDICT }) : null
)

return { cards: cards.filter(Boolean) }
