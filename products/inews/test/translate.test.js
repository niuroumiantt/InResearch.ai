// 翻译层：语言判定、缓存、以及「翻译挂了新闻照常显示」这条底线。
import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DB = join(HERE, 'tmp-translate.sqlite3');
for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true });
process.env.INEWS_DB_PATH = DB;
process.env.INEWS_TRANSLATION_PROVIDER = 'libre'; // 需要 URL 才可用，天然是「配错了」的样子
process.env.INEWS_TRANSLATION_GAP_MS = '0';

const { isChinese, translatePending, translate, translationLooksBad, scrubBadTranslations } = await import('../src/lib/translate.js');
const { getDb } = await import('../src/lib/db.js');
after(() => { for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true }); });

test('中文标题不该再送去翻译，日韩标题该', () => {
  assert.equal(isChinese('英伟达发布新一代 AI 芯片'), true);
  assert.equal(isChinese('OpenAI pauses frontier training'), false);
  // 日文与韩文夹着汉字，只数汉字会把它们误判成已经是中文。
  assert.equal(isChinese('オープンAIが新モデルを発表'), false);
  assert.equal(isChinese('오픈AI 새 모델 공개'), false);
  // 中文科技标题里全是拉丁品牌名，按字符比例算会把它判成英文。
  assert.equal(isChinese('Gemini 3 发布'), true);
  assert.equal(isChinese('OpenAI 暂停 Frontier AI Training Over Cyber Capabilities'), false);
  assert.equal(isChinese(''), true);
});

// 2026-09-01 站长实拍:nikkei 等日文来源的部分标题,译文是引号重复的退化
// 输出(免费 MT 偶发的 mode collapse),被存进缓存后一直挂在时间线上。
// 判据是结构性的:目标是中文的译文一个汉字都没有,或标点/空格占了大头。
test('退化译文过不了质量闸:零汉字、引号汤都判坏', () => {
  const src = '日本経済新聞のAI関連ニュースの見出し';
  assert.equal(translationLooksBad('I " " " " " " " " "', src), true);
  assert.equal(translationLooksBad('a a " ( a only top - of a top only minimal "', src), true);
  assert.equal(translationLooksBad('“”“”人工智能“”“”——“”', src), true);
  // 正常译文不误伤:品牌名保留原文是设计要求,不算「汉字太少」。
  assert.equal(translationLooksBad('Anthropic 以更高估值融资', src), false);
  assert.equal(translationLooksBad('OpenAI 暂停 GPT 新版本训练', src), false);
  assert.equal(translationLooksBad('“AI教父”警告:监管刻不容缓', src), false);
});

let seq = 0;
function seed(rows) {
  const db = getDb();
  const ins = db.prepare(`INSERT INTO articles
    (url, guid, title, domain, published_at, first_seen_at, relevance, relevant, dedupe_key)
    VALUES (?,?,?,?,?,?,?,?,?)`);
  for (const t of rows) {
    const n = seq++;
    ins.run(`https://x/${n}`, `g${n}`, t, 'x.com', Date.now(), Date.now(), 5, 1, `k${n}`);
  }
}

test('本来就是中文的标题原样落库，不会每轮重新排队', async () => {
  seed(['英伟达发布新一代 AI 芯片', 'OpenAI 暂停前沿训练']);
  const r = await translatePending({ limit: 10 });
  assert.equal(r.skipped, 2);
  assert.equal(r.done, 0);
  assert.equal(r.pending, 0, '处理过的行不能留在待译队列里');

  const again = await translatePending({ limit: 10 });
  assert.equal(again.skipped, 0, '第二轮不该再看到同样的行');
});

test('翻译器不可用时，条目留在库里、只是没有译文', async () => {
  seed(['Anthropic raises at a higher valuation']);
  const r = await translatePending({ limit: 10 });
  assert.equal(r.done, 0);
  assert.equal(r.failed >= 1 || r.pending >= 1, true);
  const row = getDb().prepare("SELECT title, title_zh FROM articles WHERE title LIKE 'Anthropic%'").get();
  assert.equal(row.title_zh, null, '拿不到译文就留空，前端回落到原标题');
  assert.match(row.title, /^Anthropic/);
});

test('存量乱码译文一次清掉:文章行重新排队,缓存坏行删除,好行不动', async () => {
  const db = getDb();
  const now = Date.now();
  const setZh = db.prepare('UPDATE articles SET title_zh = ?, title_zh_at = ? WHERE title = ?');

  // 三种存量:坏译文、好译文、以及「本就中文原样落库」的标记行。
  seed(['日経のAIニュース見出しその一', 'Google unveils new TPU generation']);
  setZh.run('I " " " " " " "', now, '日経のAIニュース見出しその一');
  setZh.run('Google 发布新一代 TPU', now, 'Google unveils new TPU generation');
  // 中文行的 title_zh 等于原题(translatePending 的既有约定),清理不能碰它。
  seed(['寒武纪发布新一代训练芯片']);
  setZh.run('寒武纪发布新一代训练芯片', now, '寒武纪发布新一代训练芯片');

  // 缓存表里同样躺着一条坏译文。
  const { createHash } = await import('node:crypto');
  const badSrc = '日経のAIニュース見出しその一';
  const bh = createHash('sha256').update(badSrc).digest('hex').slice(0, 32);
  db.prepare('INSERT OR REPLACE INTO translations(src_hash, src, target, text, provider, at) VALUES (?,?,?,?,?,?)')
    .run(bh, badSrc, 'zh-CN', 'I " " " " " " "', 'test', now);

  const n = scrubBadTranslations(db);
  assert.ok(n >= 1, '至少清掉一条乱码');

  const bad = db.prepare('SELECT title_zh FROM articles WHERE title = ?').get('日経のAIニュース見出しその一');
  assert.equal(bad.title_zh, null, '乱码译文清空,下一轮重译');
  const good = db.prepare('SELECT title_zh FROM articles WHERE title = ?').get('Google unveils new TPU generation');
  assert.equal(good.title_zh, 'Google 发布新一代 TPU', '好译文不动');
  const zh = db.prepare('SELECT title_zh FROM articles WHERE title = ?').get('寒武纪发布新一代训练芯片');
  assert.equal(zh.title_zh, '寒武纪发布新一代训练芯片', '中文标记行不动,否则每轮重新排队');
  const cache = db.prepare('SELECT text FROM translations WHERE src_hash = ?').get(bh);
  assert.equal(cache, undefined, '缓存里的坏译文一并删除');
});

test('缓存命中就不再打接口 —— 同一条标题会从二十家聚合站进来', async () => {
  const db = getDb();
  const src = 'Anthropic raises at a higher valuation';
  const { createHash } = await import('node:crypto');
  const h = createHash('sha256').update(src).digest('hex').slice(0, 32);
  db.prepare('INSERT INTO translations(src_hash, src, target, text, provider, at) VALUES (?,?,?,?,?,?)')
    .run(h, src, 'zh-CN', 'Anthropic 以更高估值融资', 'test', Date.now());

  // translate() 走缓存，即便 provider 配错也能拿到结果。
  assert.equal(await translate(src), 'Anthropic 以更高估值融资');

  const r = await translatePending({ limit: 10 });
  assert.equal(r.done, 1, '缓存命中算完成，且不消耗任何配额');
  const row = db.prepare("SELECT title_zh FROM articles WHERE title = ?").get(src);
  assert.equal(row.title_zh, 'Anthropic 以更高估值融资');
});
