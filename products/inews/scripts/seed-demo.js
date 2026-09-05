// Fills a throwaway database with realistic data so the UI can be reviewed
// (and screenshotted) without waiting hours for a live collector.
// Usage: INEWS_DB_PATH=data/demo.sqlite3 node scripts/seed-demo.js
import { getDb } from '../src/lib/db.js';
import { scoreRelevance } from '../src/lib/relevance.js';
import { dedupeKey } from '../src/lib/normalize.js';
import { rescoreAll } from '../src/lib/domains.js';
import { applyPolicy } from '../src/lib/policy.js';
import { buildShards } from '../src/config/keywords.js';

const db = getDb();
const now = Date.now();
const MIN = 60_000;

// title, domain, publisher, minutes-ago, angle, lang, captureLagMin
const NEWS = [
  ['OpenAI pauses work on new version of ChatGPT after it shows concerning behaviour', 'independent.co.uk', 'The Independent', 4, 'models', 'en', 1],
  ['OpenAI Pauses Training of New AI Models, Citing Cybersecurity Worries', 'cnet.com', 'CNET', 6, 'models', 'en', 2],
  ['OpenAI pausing some model work over safety concerns', 'thehill.com', 'The Hill', 9, 'models', 'en', 1],
  ['OpenAI Is Pausing Some Work Due To Safety Concerns After Finding It Could Pose Critical Cybersecurity Risks', 'ibtimes.com', 'ibtimes.com', 14, 'models', 'en', 3],
  ['英伟达发布新一代 AI 芯片，HBM4 良率成关键瓶颈', 'jiqizhixin.com', '机器之心', 7, 'chips', 'zh', 2],
  ['OpenAI reportedly seeing deeper losses in second quarter while sales grew sequentially', 'cnbc.com', 'CNBC', 11, 'money', 'en', 1],
  ['Anthropic poised for IPO before OpenAI by Q4 2026 amid market confidence', 'cryptobriefing.com', 'Crypto Briefing', 16, 'money', 'en', 4],
  ['SK하이닉스, HBM4 양산 앞당긴다… 엔비디아 물량 선점', 'etnews.com', '전자신문', 13, 'chips', 'ko', 3],
  ['First look: Gemini could soon remember details from your screenshots with one tap', 'androidauthority.com', 'Android Authority', 18, 'apps', 'en', 2],
  ['OpenAI launches teen ChatGPT amid calls for greater child safety', 'siliconrepublic.com', 'Silicon Republic', 21, 'safety', 'en', 2],
  ['Murf AI Says Falcon 2 Voice Model Beats OpenAI, ElevenLabs on Naturalness', 'analyticsindiamag.com', 'analyticsindiamag.com', 24, 'models', 'en', 5],
  ['台積電 2nm 產能全數被 AI 客戶包下，明年擴產計畫再上修', 'technews.tw', '科技新報', 27, 'chips', 'zh', 3],
  ['The most interesting takeaway from Anthropic’s design study has nothing to do with proteins', 'endpoints.news', 'endpoints.news', 31, 'research', 'en', 2],
  ['生成AI向けデータセンター、国内投資が前年比2.4倍に', 'nikkei.com', '日本経済新聞', 34, 'infra', 'ja', 6],
  ['EU AI Act enforcement guidance lands, giving general-purpose model providers six months', 'euractiv.com', 'Euractiv', 38, 'policy', 'en', 4],
  ['Verdict Capital’s Michael Fertik explains why he believes OpenAI may never go public', 'cnbc.com', 'CNBC', 44, 'money', 'en', 2],
  ['Nvidia data center revenue guidance implies another record quarter for AI accelerators', 'reuters.com', 'Reuters', 52, 'chips', 'en', 1],
  ['OpenAI confirms it isn\'t buying a teenager\'s startup, despite cheers for offer at Dublin event', 'thejournal.ie', 'The Journal', 58, 'money', 'en', 3],
  ['This may be the first academic profession to see its work taken over by AI', 'detroitnews.com', 'The Detroit News', 66, 'apps', 'en', 4],
  ['Google Gemini x BTS Collaboration: Limited-Time Interactive Features with K-Pop Icons Launched', 'gadgetbridge.com', 'gadgetbridge.com', 73, 'apps', 'en', 5],
  ['Mistral raises at a $14B valuation to fund European sovereign AI push', 'techcrunch.com', 'TechCrunch', 88, 'money', 'en', 2],
  ['Inside the power deals keeping AI data centers off the grid', 'theinformation.com', 'The Information', 96, 'infra', 'en', 3],
  ['DeepSeek releases a reasoning model trained for a fraction of frontier compute', 'venturebeat.com', 'VentureBeat', 112, 'models', 'en', 2],
  ['智谱发布新一代开源大模型，推理成本下降 60%', 'qbitai.com', '量子位', 128, 'models', 'zh', 3],
  ['US export controls widen to cover HBM sold into China', 'bloomberg.com', 'Bloomberg', 145, 'policy', 'en', 1],
  ['AI safety institute publishes first joint evaluation of frontier models', 'gov.uk', 'GOV.UK', 168, 'safety', 'en', 7],
  ['Les députés européens réclament un moratoire sur la reconnaissance faciale par IA', 'lemonde.fr', 'Le Monde', 190, 'policy', 'fr', 8],
  ['Cerebras claims inference throughput lead with new wafer-scale part', 'nextplatform.com', 'The Next Platform', 220, 'chips', 'en', 4],
  ['La inteligencia artificial ya escribe el 30% del código en las grandes tecnológicas', 'xataka.com', 'Xataka', 265, 'apps', 'es', 9],
  ['Hugging Face crosses two million public models', 'huggingface.co', 'Hugging Face', 310, 'models', 'en', 5],
];

// Reprints of the top story, so the cluster UI has something to expand.
const REPRINTS = [
  ['OpenAI pauses work on new version of ChatGPT after it shows concerning behaviour', 'msn.com', 'MSN', 2],
  ['OpenAI pauses work on new version of ChatGPT after it shows concerning behavior', 'yahoo.com', 'Yahoo Finance', 1],
  ['OpenAI pauses work on new version of ChatGPT after it shows concerning behaviour', 'biztoc.com', 'BizToc', 0],
];

const ins = db.prepare(`INSERT OR IGNORE INTO articles
  (url, guid, title, domain, publisher, published_at, first_seen_at, lang, locale,
   angle, shard, query, relevance, relevant, hits, dedupe_key, cluster_id, is_original)
  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`);

const touch = db.prepare(`INSERT INTO domains(domain, first_seen_at, last_seen_at, articles, relevant, originals, lead_ms_sum, lead_n)
  VALUES (?,?,?,1,?,?,?,1)
  ON CONFLICT(domain) DO UPDATE SET
    first_seen_at=COALESCE(first_seen_at, excluded.first_seen_at), last_seen_at=excluded.last_seen_at,
    articles=articles+1, relevant=relevant+excluded.relevant, originals=originals+excluded.originals,
    lead_ms_sum=lead_ms_sum+excluded.lead_ms_sum, lead_n=lead_n+1`);

let n = 0;
const add = (title, domain, publisher, minsAgo, angle, lang, lagMin, clusterId, isOriginal, lagMs) => {
  const published = now - minsAgo * MIN;
  const { score, relevant, hits } = scoreRelevance({ title });
  const info = ins.run(
    `https://${domain}/article/${++n}`, `demo-${n}`, title, domain, publisher,
    published, published + lagMin * MIN, lang, lang === 'en' ? 'en-US' : lang,
    angle, `${angle}.demo#${lang}#0`, 'demo', score, relevant ? 1 : 0, hits.join(','),
    dedupeKey(title), clusterId, isOriginal ? 1 : 0);
  const id = Number(info.lastInsertRowid);
  if (clusterId == null) db.prepare('UPDATE articles SET cluster_id = id WHERE id = ?').run(id);
  touch.run(domain, published, published, relevant ? 1 : 0, isOriginal ? 1 : 0, -(lagMs || 0));
  return id;
};

const headId = [];
for (const [t, d, p, m, a, l, lag] of NEWS) headId.push(add(t, d, p, m, a, l, lag, null, true, 0));
for (const [t, d, p, extra] of REPRINTS) {
  add(t, d, p, 4 - extra - 1, 'models', 'en', 2, headId[0], false, (extra + 1) * MIN);
}

// Demo translations. The real ones come from the translator on every cycle;
// seeding a handful here is what makes `npm run demo` show the actual bilingual
// row — Chinese headline, original underneath — without any network access.
const ZH = {
  'OpenAI pauses work on new version of ChatGPT after it shows concerning behaviour': 'OpenAI 因模型出现异常行为，暂停新版 ChatGPT 的开发',
  'OpenAI pauses work on new version of ChatGPT after it shows concerning behavior': 'OpenAI 因模型出现异常行为，暂停新版 ChatGPT 的开发',
  'Nvidia says Blackwell demand is "off the charts" as data-center revenue jumps 62%': '英伟达：Blackwell 需求「爆表」，数据中心营收增长 62%',
  'Anthropic raises $6B at a $180B valuation, led by ICONIQ': 'Anthropic 完成 60 亿美元融资，估值 1800 亿美元，ICONIQ 领投',
};
const setZh = db.prepare('UPDATE articles SET title_zh = ?, title_zh_at = ? WHERE title = ?');
for (const [src, zh] of Object.entries(ZH)) setZh.run(zh, now, src);
// 本来就是中文的标题不需要译文，直接标记成已处理。
db.prepare(`UPDATE articles SET title_zh = title, title_zh_at = ?
            WHERE title_zh IS NULL AND lang = 'zh'`).run(now);

// Fetch history: enough runs, with realistic per-shard yields, for the policy
// engine to have opinions and a visible change log.
const YIELD = { 'models.frontier#en-US#0': 2.4, 'chips.ai#en-US#0': 1.9, 'money.funding#en-US#0': 1.2,
  'models.cn#zh-CN#0': 1.1, 'models.open#en-US#0': 0.5, 'apps.product#en-US#0': 0.4,
  'policy.gov#en-US#0': 0.09, 'safety.legal#en-US#0': 0.05, 'research.papers#en-US#0': 0.06,
  'infra.energy#en-US#0': 0.03, 'people.moves#en-US#0': 0.07 };
const insF = db.prepare('INSERT INTO fetches(shard, started_at, ms, status, items, fresh, kept) VALUES (?,?,?,?,?,?,?)');
const shards = buildShards();
for (const s of shards) {
  const base = YIELD[s.id] ?? 0.25;
  const runs = s.lane === 'hot' ? 60 : s.lane === 'warm' ? 20 : 8;
  for (let i = runs; i > 0; i--) {
    const kept = Math.random() < base ? Math.max(1, Math.round(base)) : 0;
    insF.run(s.id, now - i * 3 * MIN, 300 + Math.round(Math.random() * 500), 200,
      Math.round(base * 8), kept, kept);
  }
}
// Run the policy engine repeatedly so lanes move and the change log fills in.
for (let i = 6; i >= 0; i--) applyPolicy(shards, now - i * 20 * MIN);
rescoreAll();

const t = db.prepare('SELECT COUNT(*) a, COUNT(DISTINCT domain) d FROM articles').get();
const e = db.prepare('SELECT COUNT(*) n FROM lane_events').get().n;
console.log(`seeded ${t.a} articles across ${t.d} domains, ${e} lane changes`);
