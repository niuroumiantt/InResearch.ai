export const meta = {
  name: 'geluoke-verify-slice',
  description: 'Verify a slice of data-center candidates at original sources (and optional region sweeps) for the 2026-09-26 daily',
  phases: [
    { title: 'Verify', detail: 'one agent per candidate, back to original source' },
    { title: 'Sweep', detail: 'region sweeps' },
  ],
}

const FACT = {
  type: 'object',
  properties: {
    candidate_id: { type: 'string' },
    verified: { type: 'boolean', description: 'true only if an original/primary or reliable-media page was actually fetched and confirms the core claim' },
    headline_zh: { type: 'string', description: 'Concrete Chinese headline: who did what where, with the key number. No judgement words.' },
    subject: { type: 'string' },
    location: { type: 'string', description: 'city/state/country' },
    region: { type: 'string', description: 'one of: 中国, 北美, 欧洲, 南亚, 东南亚, 东亚, 中东非洲, 拉美, 大洋洲' },
    chain: { type: 'string', description: 'one of: 客户与资金, 土地与许可, 电力与水／成本, 网络, 工程／设备／验收, 运营' },
    action: { type: 'string' },
    stage: { type: 'string', description: 'one of: 目标, 获批, 签约, 融资承诺, 融资到账, 资源锁定, 开工, 设备到货, 调试, 客户验收, 投运, 监管/许可变化, 暂停/延期, 诉讼/纠纷, 其他' },
    event_date: { type: 'string', description: 'YYYY-MM-DD of the event itself (not the report)' },
    report_date: { type: 'string', description: 'YYYY-MM-DD of the earliest report you found' },
    in_window: { type: 'boolean', description: 'event or first report falls in 2026-09-25 06:00 to 2026-09-26 06:00 Beijing time' },
    numbers: { type: 'array', items: { type: 'object', properties: { value: { type: 'string' }, unit: { type: 'string' }, meaning: { type: 'string' }, source_org: { type: 'string' } }, required: ['value', 'unit', 'meaning'] } },
    facts_zh: { type: 'string', description: '150-300 Chinese characters of verified facts: subject, place, action, stage, numbers with units, what is NOT yet disclosed or completed. Facts only, no commentary.' },
    delivery_condition_zh: { type: 'string', description: '80-160 Chinese characters: which delivery condition (customer/capital/land/permit/power/water/network/engineering/operation) this changes, derived only from disclosed facts.' },
    background_zh: { type: 'string', description: 'Dated background needed to understand the event, e.g. earlier phases, prior announcements, with dates.' },
    key_quotes: { type: 'array', items: { type: 'string' }, description: 'Up to 3 verbatim short quotes from sources in original language' },
    sources: { type: 'array', items: { type: 'object', properties: { org: { type: 'string' }, url: { type: 'string' }, kind: { type: 'string', description: 'government/regulator, company release/filing, court/document, major media, trade media, local media, aggregator' }, date: { type: 'string' } }, required: ['org', 'url', 'kind'] } },
    confidence: { type: 'string', description: 'high / medium / low' },
    caveats: { type: 'string', description: 'unverified claims, conflicting numbers, or reasons to drop' },
  },
  required: ['candidate_id', 'verified', 'headline_zh', 'subject', 'location', 'region', 'chain', 'action', 'stage', 'event_date', 'report_date', 'in_window', 'numbers', 'facts_zh', 'delivery_condition_zh', 'sources', 'confidence', 'caveats'],
}

const SWEEP = {
  type: 'object',
  properties: {
    region: { type: 'string' },
    candidates: { type: 'array', items: { type: 'object', properties: {
      headline_zh: { type: 'string' }, subject: { type: 'string' }, location: { type: 'string' }, chain: { type: 'string' }, stage: { type: 'string' },
      event_date: { type: 'string' }, report_date: { type: 'string' }, in_window: { type: 'boolean' },
      numbers: { type: 'array', items: { type: 'string' } }, facts_zh: { type: 'string' }, delivery_condition_zh: { type: 'string' }, background_zh: { type: 'string' },
      sources: { type: 'array', items: { type: 'object', properties: { org: { type: 'string' }, url: { type: 'string' }, kind: { type: 'string' } }, required: ['org', 'url', 'kind'] } },
      verified: { type: 'boolean' }, confidence: { type: 'string' }, caveats: { type: 'string' } },
      required: ['headline_zh', 'subject', 'location', 'chain', 'stage', 'event_date', 'report_date', 'in_window', 'facts_zh', 'sources', 'verified', 'confidence'] } },
    notes: { type: 'string' },
  },
  required: ['region', 'candidates', 'notes'],
}

const COMMON = `You are a fact-checker for a Chinese-language data-center industry daily (格洛可数据中心日报) dated 2026-09-26 (Beijing). Observation window: 2026-09-25 06:00 to 2026-09-26 06:00 Beijing time (= 2026-09-24 22:00Z to 2026-09-25 22:00Z). Today is 2026-09-26.
Tools: use WebSearch to locate the ORIGINAL source (government/regulator/grid/exchange filing > company release or project document > customer/investor disclosure > major media), then WebFetch the page(s) to confirm. Google News RSS links (news.google.com/rss/...) are redirects: do not rely on them; search the headline text to find the real article, then find the primary document it cites. Fetch at least two independent pages when possible. Work efficiently: aim to finish within about 12 tool calls.
Rules: never invent numbers. Distinguish event date vs report date; planned vs started; financing committed vs closed; planned capacity vs operating capacity. Record units and currency exactly (MW, GW, USD, GBP, INR crore, etc.). If the claim cannot be confirmed from a fetched page, set verified=false and explain in caveats. Write Chinese fields in simplified Chinese, concrete and neutral, no opinion words like 值得关注. Return only the structured object.`

const cands = (args && args.candidates) || []
const sweeps = (args && args.sweeps) || []

phase('Verify')
const facts = await parallel(cands.map(c => () =>
  agent(`${COMMON}

Candidate id: ${c.id}
Claim to verify: ${c.title}
Leads: ${c.hints}

Do the verification now and return the structured fact card. In facts_zh include every disclosed number with unit and what remains undisclosed. In background_zh include dated prior milestones for this project/company if relevant.`,
  { label: `verify:${c.id}`, phase: 'Verify', schema: FACT })
))

phase('Sweep')
const sw = await parallel(sweeps.map(s => () =>
  agent(`${COMMON}

Region sweep: ${s.region}
${s.prompt}

Return up to 6 candidates for this region that (a) fall in the window or are first reported in it, (b) answer who/where/what/stage/number/next delivery condition, and (c) are verified at an original page you fetched. Prefer government, grid, exchange filings and company releases. Include the exact URLs. Say in notes what you searched and what was thin.`,
  { label: `sweep:${s.region}`, phase: 'Sweep', schema: SWEEP })
))

return { facts: facts.filter(Boolean), sweeps: sw.filter(Boolean) }
