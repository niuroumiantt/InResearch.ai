import { getDb } from './lib/db.js';
import { rescoreAll } from './lib/domains.js';
import { TokenBucket } from './lib/fetcher.js';
import { runCycle, startScheduler, CONFIG } from './scheduler.js';
import { createServer, setBucket } from './server.js';
import { buildShards } from './config/keywords.js';
import { getText, googleNewsUrl } from './lib/fetcher.js';
import { parseFeed } from './lib/rss.js';
import { scoreRelevance, ACCEPT } from './lib/relevance.js';
import { dedupeKey, registrableDomain, stripPublisherSuffix } from './lib/normalize.js';
import { translatePending, translatorEnabled, translatorName, scrubBadTranslations } from './lib/translate.js';
import { backfillValues } from './lib/value.js';
import { backfillRegions } from './lib/region.js';
import { classifyPending, classifierEnabled, classifierName } from './lib/classify.js';
import { mergeTranslatedPending } from './lib/merge.js';
import {
  ensureAdmin, findUserByEmail, createUser, setPassword, assertEmail, db as appDb, audit,
} from './auth/store.js';
import { envFlag, envValue } from './lib/env.js';
import { writeFileSync } from 'node:fs';

/**
 * Two collectors on one database is not corruption — SQLite WAL handles it —
 * but the second one sees every article as "already known" and reports
 * kept=0, which reads exactly like a broken pipeline. Say so out loud.
 */
function warnIfCollectorRunning() {
  const db = getDb();
  const last = db.prepare('SELECT MAX(started_at) t FROM fetches').get()?.t;
  if (last && Date.now() - last < 3 * 60_000) {
    const secs = Math.round((Date.now() - last) / 1000);
    console.warn(`⚠️  ${secs} 秒前有另一个采集器在跑（多半是 npm start 的常驻进程）。`);
    console.warn('   它已经抓走的条目在这里会显示 kept=0 —— 那不是故障。');
    console.warn(`   只想看一轮结果就先停掉它: lsof -ti:${process.env.PORT || 8787} | xargs kill\n`);
  }
}

const cmd = process.argv[2] || 'serve';
// ~36 req/min ceiling, self-tuning downward whenever Google pushes back.
const bucket = new TokenBucket({ capacity: 8, refillPerSec: 0.6 });
setBucket(bucket);
getDb();

if (cmd === 'admin') {
  // Create or promote an administrator from the command line. The password is
  // Read from ADMIN_PASSWORD rather than argv so it is absent from the process
  // list. Operators inject it with `read -s`, not a literal shell assignment.
  let email = '';
  try { email = assertEmail(process.argv[3] || ''); } catch { /* generic usage below */ }
  const password = process.env.ADMIN_PASSWORD || '';
  if (!email || password.length < 12) {
    console.error('先用 read -rsp 读取并 export ADMIN_PASSWORD，再运行 node src/cli.js admin <email>；详见 README');
    process.exit(1);
  }
  appDb();
  const existing = findUserByEmail(email);
  if (existing) {
    await setPassword(existing.id, password);
    appDb().prepare("UPDATE users SET role='admin', status='active' WHERE id=?").run(existing.id);
    audit({ actor: existing, action: 'admin.cli', target: email, detail: 'promoted + password reset' });
    console.log(`已把 ${email} 设为管理员并重置密码`);
  } else {
    await createUser({ email, password, role: 'admin', nickname: '管理员' });
    audit({ actor: { email }, action: 'admin.cli', target: email, detail: 'created' });
    console.log(`已创建管理员 ${email}`);
  }
  process.exit(0);
} else if (cmd === 'serve') {
  const port = Number(process.env.PORT || 8787);
  // Bootstrap is readiness, not best-effort background work. Invalid admin
  // credentials must not leave a process that still passes liveness checks.
  let bootstrap;
  try {
    bootstrap = await ensureAdmin();
  } catch (e) {
    console.error('管理员初始化失败:', e?.message || e);
    process.exit(1);
  } finally {
    delete process.env.ADMIN_PASSWORD;
  }
  if (bootstrap.created) console.log(`管理员已创建: ${bootstrap.created}`);
  else if (bootstrap.promoted) console.log(`管理员已提升: ${bootstrap.promoted}`);
  else if (bootstrap.none) console.log('⚠️  还没有管理员账号 —— Dashboard / 规则演化 将无法打开。\n'
    + '   请按 README 的 read -s 流程创建首个管理员，密码不要写进命令参数。');

  const server = createServer();
  server.on('error', (e) => {
    if (e.code === 'EADDRINUSE') {
      console.error(`端口 ${port} 已被占用 —— 多半是上一个 singletitle 还在跑。`);
      console.error(`  停掉它:  lsof -ti:${port} | xargs kill`);
      console.error(`  或换端口: PORT=${port + 1} npm start`);
      process.exit(1);
    }
    throw e;
  });
  server.listen(port, () => console.log(`singletitle → http://localhost:${port}`));

  // 价值轴回填 + 用当前闸门复核旧行:每次部署都重打启发式行,
  // 词表改进因此追溯生效。放在 listen 之后:几秒钟,不推迟端口就绪。
  try {
    const filled = backfillValues(getDb(), { scoreRelevance });
    if (filled) console.log(`价值轴回填: ${filled} 行已按当前词表重打`);
    const regions = backfillRegions(getDb());
    if (regions) console.log(`地区回填: ${regions} 行`);
    // 聚类元数据一次性回填(此后由 ingest 增量维护):只补还没有值的头行。
    const cl = getDb().prepare(`UPDATE articles SET
        cluster_latest = (SELECT MAX(b.published_at) FROM articles b WHERE b.cluster_id = articles.id),
        cluster_n = (SELECT COUNT(*) FROM articles b WHERE b.cluster_id = articles.id)
      WHERE id = cluster_id AND cluster_latest IS NULL`).run();
    if (cl.changes) console.log(`聚类元数据回填: ${cl.changes} 个头`);
    // 译文质量闸每收紧一次,历史上已过闸的坏译文还挂在时间线上 —— 一并清掉。
    const scrubbed = scrubBadTranslations(getDb());
    if (scrubbed) console.log(`乱码译文清理: ${scrubbed} 条已清空待重译`);
  } catch (e) { console.error('价值轴回填失败:', e?.message || e); }

  if (!envFlag('INEWS_DISABLE_COLLECTOR', { legacy: 'ST_NO_COLLECT' })) {
    console.log(`collector: ${buildShards().length} shards, cycle ${CONFIG.cycleMs}ms`);
    startScheduler(bucket);
  }
} else if (cmd === 'collect') {
  warnIfCollectorRunning();
  const res = await runCycle(bucket);
  // `fresh` distinguishes "already in the DB" from "dropped by the relevance
  // gate" — without it, kept=0 is ambiguous.
  console.table(res.map(({ shard, status, items, fresh, kept, err }) => ({ shard, status, items, fresh, kept, err })));
  rescoreAll();
  process.exit(0);
} else if (cmd === 'debug') {
  // Fetch ONE shard and show exactly what happens to every item, so a
  // "items=19 kept=0" mystery can be diagnosed from the real feed rather
  // than guessed at from a fixture.
  const pick = process.argv[3] || 'models.frontier';
  const shard = buildShards().find((s) => s.id.startsWith(pick)) || buildShards()[0];
  const window = envValue('INEWS_GOOGLE_NEWS_WINDOW', { legacy: 'ST_WINDOW', fallback: '1h' });
  const url = googleNewsUrl({ q: shard.q, locale: shard.locale, window });
  console.log('shard :', shard.id);
  console.log('query :', shard.q);
  console.log('url   :', url, '\n');

  const res = await getText(url);
  console.log('HTTP', res.status, `${res.body ? res.body.length : 0} bytes\n`);
  if (!res.body) { console.log('no body'); process.exit(1); }

  const dump = envValue('INEWS_DEBUG_FEED_PATH', {
    legacy: 'ST_DUMP', fallback: 'data/google-news-debug-feed.xml',
  });
  writeFileSync(dump, res.body);
  console.log('raw feed saved to', dump);
  console.log('first 600 bytes:\n' + res.body.slice(0, 600).replace(/></g, '>\n<') + '\n');

  const { items } = parseFeed(res.body);
  console.log(`parsed ${items.length} items\n`);
  const db = getDb();
  const seen = db.prepare('SELECT id FROM articles WHERE guid = ?');

  for (const [i, it] of items.entries()) {
    const title = stripPublisherSuffix(it.title, it.sourceName);
    const { score, relevant, hits } = scoreRelevance({ title, description: it.description, query: shard.q });
    const guid = it.guid || it.link;
    const dupe = guid && seen.get(guid) ? 'ALREADY-IN-DB' : '';
    const verdict = dupe || (score <= 0 ? 'DROPPED (score<=0)' : relevant ? 'KEPT+relevant' : `KEPT (low, <${ACCEPT})`);
    console.log(`${String(i + 1).padStart(2)}. [${String(score).padStart(3)}] ${verdict}`);
    console.log(`    title    : ${JSON.stringify(title)}`);
    console.log(`    raw title: ${JSON.stringify(it.title)}`);
    console.log(`    source   : ${JSON.stringify(it.sourceName)} @ ${JSON.stringify(it.sourceUrl)} -> ${registrableDomain(it.sourceUrl)}`);
    console.log(`    pubDate  : ${JSON.stringify(it.pubDate)}`);
    console.log(`    guid     : ${JSON.stringify((guid || '').slice(0, 40))}`);
    console.log(`    dedupeKey: ${JSON.stringify(dedupeKey(title))}`);
    if (hits.length) console.log(`    hits     : ${hits.join(', ')}`);
  }
  process.exit(0);
} else if (cmd === 'recheck') {
  // Re-run the relevance gate over everything already stored. Needed after
  // tuning relevance.js — otherwise old rows keep their old verdict forever.
  // Editorial admission is a durable floor, not a stale lexical verdict; its
  // rows are deliberately outside this maintenance command.
  const db = getDb();
  const rows = db.prepare(`SELECT id, title, relevance, relevant FROM articles
    WHERE COALESCE(value_src, '') != 'editorial'`).all();
  const upd = db.prepare('UPDATE articles SET relevance = ?, relevant = ?, hits = ? WHERE id = ?');
  let promoted = 0, demoted = 0;
  for (const r of rows) {
    const { score, relevant, hits } = scoreRelevance({ title: r.title });
    if (relevant && !r.relevant) promoted++;
    if (!relevant && r.relevant) demoted++;
    upd.run(score, relevant ? 1 : 0, hits.join(','), r.id);
  }
  console.log(`重新判定 ${rows.length} 条：新收 ${promoted} 条，撤下 ${demoted} 条`);
  if (demoted) {
    console.log('\n被撤下的（现在归为低分）：');
    for (const r of db.prepare('SELECT title, relevance FROM articles WHERE relevant = 0 ORDER BY id DESC LIMIT 15').all()) {
      console.log(`  [${r.relevance}] ${r.title}`);
    }
  }
  rescoreAll();
  process.exit(0);
} else if (cmd === 'translate') {
  // Backfill: every stored headline that still has no Chinese rendering.
  // Runs in bounded passes so a Ctrl-C never loses more than one pass.
  if (!translatorEnabled()) {
    console.error(`翻译器未启用 (ST_TRANSLATE=${translatorName()})。可选: google | cloudflare | libre`);
    process.exit(1);
  }
  const cap = Number(process.argv[3] || Infinity);
  let total = 0;
  for (;;) {
    const t = await translatePending({ limit: 100, budgetMs: 10 * 60_000 });
    total += t.done + t.skipped;
    console.log(`译 ${t.done} · 本就中文 ${t.skipped} · 失败 ${t.failed} · 剩余 ${t.pending}`
      + (t.error ? ` · 最后错误: ${t.error}` : ''));
    // 被质量闸拦下的样本。光有计数看不出是模型翻错了还是闸门误伤,
    // 而这两种情况的处置完全相反 —— 一个该换模型,一个该改闸门。
    for (const r of t.rejected || []) {
      console.log(`  ✗ ${r.why}`);
      console.log(`    原文 ${r.src}`);
      console.log(`    译文 ${JSON.stringify(r.out)}`);
    }
    if (!t.pending || (!t.done && !t.skipped) || total >= cap) break;
  }
  process.exit(0);
} else if (cmd === 'rescore') {
  console.log('rescored', rescoreAll(), 'domains');
  process.exit(0);
} else if (cmd === 'classify') {
  // 价值轴维护:先按当前词表重打启发式行,再(若配置了 LLM)分批精化。
  const filled = backfillValues(getDb(), { scoreRelevance });
  if (filled) console.log(`启发式回填 ${filled} 行`);
  if (!classifierEnabled()) {
    console.log('LLM 精化未启用 (ST_CLASSIFY=llm + ST_CLASSIFY_KEY + ST_CLASSIFY_MODEL)。仅完成启发式。');
    process.exit(0);
  }
  const cap = Number(process.argv[3] || Infinity);
  let total = 0;
  for (;;) {
    const c = await classifyPending({ limit: 200, budgetMs: 10 * 60_000 });
    total += c.done;
    console.log(`精化 ${c.done} · 失败 ${c.failed} · 待审 ${c.pending}` + (c.error ? ` · ${c.error}` : ''));
    if (!c.pending || !c.done || total >= cap) break;
  }
  // 精化完接着清跨语言并簇的积压 —— 同一个 LLM 通道。
  for (;;) {
    const m = await mergeTranslatedPending({ limit: 200, budgetMs: 10 * 60_000 });
    console.log(`并簇 ${m.merged} · 否决 ${m.vetoed} · 待裁 ${m.pending}` + (m.error ? ` · ${m.error}` : ''));
    if (!m.pending || (!m.merged && !m.vetoed)) break;
  }
  process.exit(0);
} else {
  console.error('usage: cli.js serve|collect|debug [shard-prefix]|recheck|rescore|translate [max]|classify [max]|admin <email>');
  process.exit(1);
}
