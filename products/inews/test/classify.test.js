// LLM 精化不得复活被结构性一票否决的行。
//
// 2026-09-01 线上复核:必读档里的行情/荐股垃圾,一部分是 value_src='llm' ——
// 启发式在入库时判了 0,精化批次又把它捞回去重打。词表的判决是结构性事实
// (荐股导购、盘面综述),模型观点不能推翻它;否则词表每堵一个口,
// 精化就重新打开一次。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DB = join(HERE, 'tmp-classify.db');
rmSync(DB, { force: true }); rmSync(DB + '-wal', { force: true }); rmSync(DB + '-shm', { force: true });
process.env.SINGLETITLE_DB = DB;
// 打开精化通道(假凭据),网络层用 mock 顶掉 —— 测的是选行逻辑,不是供应商。
process.env.ST_CLASSIFY = 'llm';
process.env.ST_CLASSIFY_KEY = 'test-key';
process.env.ST_CLASSIFY_MODEL = 'test-model';

const { getDb } = await import('../src/lib/db.js');
const { classifyPending } = await import('../src/lib/classify.js');
const { backfillValues } = await import('../src/lib/value.js');

const now = Date.now();
function seed(db, id, title, value) {
  db.prepare(`INSERT INTO articles
    (id, url, guid, title, domain, published_at, first_seen_at,
     relevance, relevant, dedupe_key, cluster_id, is_original, value, genre, value_src)
    VALUES (?, ?, ?, ?, 'example.com', ?, ?, 5, 1, ?, ?, 1, ?, 'other', 'heur')`)
    .run(id, `https://example.com/${id}`, `guid-${id}`, title, now, now, `dk-${id}`, id, value);
}

test('value=0 的否决行不进精化批次,也不会被 LLM 抬回来', async () => {
  const db = getDb();
  seed(db, 1, 'AI 概念股全线涨停，龙头股再创新高', 0);   // 词表一票否决
  seed(db, 2, 'OpenAI pauses work on new version of ChatGPT', 2);

  const sent = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (_url, opts) => {
    const body = JSON.parse(opts.body);
    sent.push(body.messages[1].content);
    // 模型不管收到什么都喊必读 —— 否决行若被送进来,这里就会把它抬成 3。
    const n = body.messages[1].content.split('\n').length;
    const arr = Array.from({ length: n }, (_, i) => ({ i, v: 3, g: 'model' }));
    return { ok: true, json: async () => ({ choices: [{ message: { content: JSON.stringify(arr) } }] }) };
  };
  try {
    await classifyPending({ limit: 100, budgetMs: 5_000 });
  } finally { globalThis.fetch = realFetch; }

  assert.equal(sent.length, 1, '应当只发出一批');
  assert.ok(!sent[0].includes('概念股'), '否决行不得出现在发给 LLM 的批次里');
  const rows = db.prepare('SELECT id, value, value_src FROM articles ORDER BY id').all();
  assert.equal(rows[0].value, 0, '否决行保持 0');
  assert.equal(rows[0].value_src, 'heur', '否决行不被标记为已精化');
  assert.equal(rows[1].value, 3, '正常行照常被精化');
  assert.equal(rows[1].value_src, 'llm');
});

// 词表升级要能追溯清理 LLM 打过分的行:线上必读档的行情垃圾大半是
// value_src='llm',只重打 heur 行的话,词表每次改进都对存量失效。
// LLM 的正常分数仍然不动 —— 追溯只执行一票否决,不重打其余档位。
test('backfill 对 llm 行只执行一票否决,不覆盖其正常分数', () => {
  const db = getDb();
  db.prepare("UPDATE articles SET value = 3, genre = 'business', value_src = 'llm' WHERE id = 1").run();
  seed(db, 3, 'Anthropic raises $30B at record valuation', 3);
  db.prepare("UPDATE articles SET value_src = 'llm', genre = 'business' WHERE id = 3").run();

  backfillValues(db);

  const byId = Object.fromEntries(
    db.prepare('SELECT id, value, genre FROM articles').all().map((r) => [r.id, r]));
  assert.equal(byId[1].value, 0, '词表否决的 llm 行被追溯压到 0');
  assert.equal(byId[1].genre, 'noise');
  assert.equal(byId[3].value, 3, '未被否决的 llm 行保持 LLM 分数');
  assert.equal(byId[3].genre, 'business', 'llm 行的体裁也不被启发式覆盖');
});

test('标题相关性复核可压掉被描述或旧模型捞进来的存量行', () => {
  const db = getDb();
  seed(db, 4, 'Schumacher says Kimi Antonelli will join Ferrari', 3);
  db.prepare("UPDATE articles SET value_src = 'llm', genre = 'model' WHERE id = 4").run();

  backfillValues(db, { scoreRelevance: ({ title }) => ({ relevant: !title.includes('Ferrari') }) });

  const row = db.prepare('SELECT value, genre FROM articles WHERE id = 4').get();
  assert.equal(row.value, 0);
  assert.equal(row.genre, 'noise');
});

test('最强结构性正证据可以纠正旧 LLM 的假阴性', () => {
  const db = getDb();
  seed(db, 5, 'ChatGPT Ads Surpass $1 Billion Annualized Sales', 0);
  db.prepare("UPDATE articles SET value_src = 'llm', genre = 'noise' WHERE id = 5").run();

  backfillValues(db, { scoreRelevance: () => ({ relevant: true }) });

  const row = db.prepare('SELECT value, genre, value_src FROM articles WHERE id = 5').get();
  assert.equal(row.value, 3);
  assert.equal(row.genre, 'business');
  assert.equal(row.value_src, 'heur', '结构性纠偏留下可追溯来源');
});
