import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  inferTechmemeAngle, isTechmemeSocial, parseTechmemeFeed, parseTechmemeRiver,
  techmemeGuid, techmemeKey,
} from '../src/lib/techmeme.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..');
const DB = join(HERE, 'tmp-techmeme.sqlite3');
for (const suffix of ['', '-wal', '-shm']) rmSync(DB + suffix, { force: true });
process.env.INEWS_DB_PATH = DB;

const RIVER = `
<h2>September 3, 2026</h2>
<table><tbody>
<tr class="ritem"><td>12:25 PM &nbsp;&bull;</td><td>
  <div class="rshr" id="s0" pml="260903p26"></div>
  <cite>Andrew E. Freedman / <a href="https://www.tomshardware.com/">Tom's Hardware</a>:</cite>&nbsp;
  <a href="https://www.tomshardware.com/ai-server">Nvidia opens a 250 MW AI data center with new HBM servers</a>
</td></tr>
<tr><td>Sponsored</td><td><a href="https://ads.example/">AI sponsor</a></td></tr>
</tbody></table>
<h2>January 8, 2026</h2>
<table><tbody>
<tr class='ritem'><td>7:05 AM &nbsp;•</td><td>
  <div class='rshr' pml='260108p4'></div>
  <cite><a href='https://example.com/'>Example Wire</a>:</cite>
  <a href='https://example.com/open-model'>Lab releases open-source AI model</a>
</td></tr>
</tbody></table>`;

const FEED = `<?xml version="1.0"?><rss><channel>
<item>
  <title>Nvidia wrapper title (Andrew/Tom's Hardware)</title>
  <link>https://www.techmeme.com/260903/p26#a260903p26</link>
  <description><![CDATA[
    <P><A HREF="https://www.techmeme.com/260903/p26#a260903p26"><IMG SRC="pml.png"></A>
    Andrew E. Freedman / <A HREF="https://www.tomshardware.com/">Tom's Hardware</A>:<BR>
    <SPAN><B><A HREF="https://www.tomshardware.com/ai-server?x=1&amp;y=2">Nvidia opens a 250 MW AI data center with new HBM servers</A></B></SPAN>
  ]]></description>
  <pubDate>Thu, 03 Sep 2026 12:25:01 -0400</pubDate>
  <guid>https://www.techmeme.com/260903/p26#a260903p26</guid>
</item></channel></rss>`;

test('Techmeme permanent ids normalize across River and RSS', () => {
  assert.equal(techmemeKey('260903p26'), '260903p26');
  assert.equal(techmemeKey('https://www.techmeme.com/260903/p26#a260903p26'), '260903p26');
  assert.equal(techmemeGuid('260903p26'), 'https://www.techmeme.com/260903/p26#a260903p26');
});

test('River parser keeps original publisher links and Techmeme Eastern time', () => {
  const { items } = parseTechmemeRiver(RIVER);
  assert.equal(items.length, 2, 'non-ritem sponsor row is ignored');
  assert.deepEqual(items[0], {
    title: 'Nvidia opens a 250 MW AI data center with new HBM servers',
    link: 'https://www.tomshardware.com/ai-server',
    guid: 'https://www.techmeme.com/260903/p26#a260903p26',
    editorialKey: '260903p26',
    pubDate: 'Thu, 03 Sep 2026 16:25:00 GMT',
    sourceName: "Tom's Hardware",
    sourceUrl: 'https://www.tomshardware.com/',
    description: '',
    angle: 'infra',
  });
  assert.equal(items[1].pubDate, 'Thu, 08 Jan 2026 12:05:00 GMT', 'winter uses EST');
});

test('River parser decodes named punctuation and currency entities', () => {
  const html = `<h2>September 3, 2026</h2><table><tr class="ritem">
    <td>1:05 PM &nbsp;&bull;</td><td><div class="rshr" pml="260903p88"></div>
    <cite>A / <a href="https://example.com/">Example</a>:</cite>
    <a href="https://example.com/story">OpenAI cuts prices by &pound;5 for &ldquo;agentic&rdquo; use</a>
    </td></tr></table>`;
  const row = parseTechmemeRiver(html).items[0];
  assert.equal(row.title, 'OpenAI cuts prices by £5 for “agentic” use');
  assert.equal(row.pubDate, 'Thu, 03 Sep 2026 17:05:00 GMT');
});

test('RSS and River produce the same item identity and original URL', () => {
  const river = parseTechmemeRiver(RIVER).items[0];
  const rss = parseTechmemeFeed(FEED).items[0];
  assert.equal(rss.guid, river.guid);
  assert.equal(rss.editorialKey, river.editorialKey);
  assert.equal(rss.title, river.title);
  assert.equal(rss.link, 'https://www.tomshardware.com/ai-server?x=1&y=2');
  assert.equal(rss.sourceName, "Tom's Hardware");
});

test('Techmeme classification recognizes core infrastructure and social chatter', () => {
  assert.equal(inferTechmemeAngle('New liquid cooling network for an AI data center'), 'infra');
  assert.equal(inferTechmemeAngle('EU lawmakers approve AI regulation'), 'policy');
  assert.ok(isTechmemeSocial('https://x.com/someone/status/1'));
  assert.ok(isTechmemeSocial('https://foo.bsky.app/profile/x'));
  assert.ok(!isTechmemeSocial('https://www.reuters.com/technology/ai'));
});

test('an accepted Techmeme pick records provenance even when the article already exists', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const picked = parseTechmemeFeed(FEED).items[0];
  const base = {
    id: 'feed:ordinary', q: 'AI', angle: 'infra', feedUrl: 'https://ordinary.test/feed',
    locale: { id: 'en-US', lang: 'en' }, feedBoost: 0,
  };
  const before = getDb().prepare('SELECT COUNT(*) n FROM articles').get().n;
  ingestItems([{ ...picked, guid: 'publisher-feed-guid-260903p26' }], base,
    Date.parse('2026-09-03T17:00:00Z'));
  ingestItems([picked], {
    ...base, id: 'feed:techmeme-live', editorialSource: 'techmeme',
    editorialPolicy: 'techmeme-ai',
  }, Date.parse('2026-09-03T17:01:00Z'));

  const db = getDb();
  assert.equal(db.prepare('SELECT COUNT(*) n FROM articles').get().n, before + 1,
    'different publisher and Techmeme GUIDs still share the exact original URL');
  const ref = db.prepare(`SELECT * FROM editorial_references
    WHERE source='techmeme' AND source_key='260903p26'`).get();
  assert.equal(ref.source, 'techmeme');
  assert.equal(ref.source_key, '260903p26');
  assert.equal(ref.article_id,
    db.prepare('SELECT id FROM articles WHERE url=?').get(picked.link).id);
  assert.equal(ref.url, 'https://www.tomshardware.com/ai-server?x=1&y=2');
  assert.equal(ref.domain, 'tomshardware.com');
  assert.equal(ref.value, 3);
  assert.equal(ref.angle, 'infra');
  assert.equal(ref.policy, 'techmeme-ai-v1');
});

test('an exact low-score publisher row receives a durable editorial display floor', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const key = '260903p75';
  const title = 'SB Energy has 8.8GW of data center capacity and a large backlog';
  const url = 'https://sbenergy.example/data-center-backlog';
  const pubDate = 'Thu, 03 Sep 2026 13:45:00 -0400';
  const ordinary = {
    id: 'feed:ordinary-sb', q: 'AI', angle: 'infra', feedUrl: 'https://sbenergy.example/feed',
    locale: { id: 'en-US', lang: 'en' }, feedBoost: 0,
  };
  ingestItems([{
    title, link: url, guid: 'publisher-sb-energy-75', pubDate,
    sourceName: 'SB Energy', sourceUrl: 'https://sbenergy.example/',
  }], ordinary, Date.parse('2026-09-03T18:46:00Z'));
  const db = getDb();
  const original = db.prepare('SELECT * FROM articles WHERE url=?').get(url);
  assert.equal(original.relevance, 1);
  assert.equal(original.relevant, 0);
  assert.equal(original.value, 0);

  const picked = {
    title, link: url, guid: techmemeGuid(key), editorialKey: key, pubDate,
    sourceName: 'SB Energy', sourceUrl: 'https://sbenergy.example/',
  };
  const tech = {
    ...ordinary, id: 'feed:techmeme-live', q: 'feed:techmeme.com',
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  };
  const selected = ingestItems([picked], tech, Date.parse('2026-09-03T18:47:00Z'));
  assert.deepEqual(selected, { items: 1, fresh: 0, kept: 1 },
    'a new reference is a kept Techmeme item even when the publisher row already existed');
  let row = db.prepare(`SELECT id,relevance,relevant,value,genre,angle,value_src,
    cluster_id,is_original,cluster_n FROM articles WHERE url=?`).get(url);
  assert.deepEqual({ relevance: row.relevance, relevant: row.relevant, value: row.value,
    genre: row.genre, angle: row.angle, value_src: row.value_src },
  { relevance: 3, relevant: 1, value: 2, genre: 'compute', angle: 'infra', value_src: 'editorial' });
  assert.equal(row.cluster_id, row.id);
  assert.equal(row.is_original, 1);
  assert.equal(row.cluster_n, 1);
  assert.equal(db.prepare(`SELECT COUNT(*) n FROM articles
    WHERE id=? AND relevant=1 AND is_original=1 AND value>=2`).get(row.id).n, 1,
  'the picked low-score story qualifies for the merged reader timeline');

  // Re-seeing an existing selection is also a convergence pass for old DBs.
  db.prepare('UPDATE articles SET cluster_n=99 WHERE id=?').run(row.id);
  db.prepare(`UPDATE domains SET articles=99,relevant=0,originals=0
    WHERE domain='sbenergy.example'`).run();
  const repeated = ingestItems([picked], tech, Date.parse('2026-09-03T18:48:00Z'));
  assert.deepEqual(repeated, { items: 1, fresh: 0, kept: 0 });
  row = db.prepare('SELECT cluster_n FROM articles WHERE id=?').get(row.id);
  assert.equal(row.cluster_n, 1);
  const domain = db.prepare(`SELECT articles,relevant,originals FROM domains
    WHERE domain='sbenergy.example'`).get();
  assert.deepEqual({ ...domain }, { articles: 1, relevant: 1, originals: 1 });
  const ref = db.prepare(`SELECT article_id FROM editorial_references
    WHERE source='techmeme' AND source_key=?`).get(key);
  assert.equal(ref.article_id, original.id);

  // A publisher can later disclose an earlier publication time. If that low-
  // score copy becomes the cluster head, the story must retain its floor.
  ingestItems([{
    title, link: 'https://early-sb.example/copy', guid: 'earlier-sb-copy',
    pubDate: 'Thu, 03 Sep 2026 13:44:00 -0400', sourceName: 'Earlier SB Wire',
    sourceUrl: 'https://early-sb.example/',
  }], ordinary, Date.parse('2026-09-03T18:49:00Z'));
  const early = db.prepare(`SELECT id,relevance,relevant,value,value_src,cluster_id,is_original,cluster_n
    FROM articles WHERE guid='earlier-sb-copy'`).get();
  assert.deepEqual({ relevance: early.relevance, relevant: early.relevant, value: early.value,
    value_src: early.value_src, cluster_id: early.cluster_id, is_original: early.is_original,
    cluster_n: early.cluster_n }, {
    relevance: 3, relevant: 1, value: 2, value_src: 'editorial',
    cluster_id: early.id, is_original: 1, cluster_n: 2,
  });
  assert.equal(db.prepare(`SELECT COUNT(*) n FROM articles
    WHERE cluster_id=? AND relevant=1 AND is_original=1 AND value>=2`).get(early.id).n, 1);
});

test('legacy Techmeme plus publisher rows converge to one downstream URL', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const key = '260903p76';
  const guid = techmemeGuid(key);
  const title = 'Broadcom signs $9B order for custom AI chips and networking switches';
  const url = 'https://atlas-publisher.example/project-atlas';
  const pubDate = 'Thu, 03 Sep 2026 13:50:00 -0400';
  const locale = { id: 'en-US', lang: 'en' };
  ingestItems([{
    title, link: url, guid: 'publisher-project-atlas', pubDate,
    sourceName: 'Atlas Publisher', sourceUrl: 'https://atlas-publisher.example/',
  }], {
    id: 'feed:atlas-publisher', q: 'AI', angle: 'infra',
    feedUrl: 'https://atlas-publisher.example/feed', locale, feedBoost: 0,
  }, Date.parse('2026-09-03T18:51:00Z'));
  const publisherId = db.prepare("SELECT id FROM articles WHERE guid='publisher-project-atlas'").get().id;
  ingestItems([{
    title, link: guid, guid, pubDate, sourceName: '', sourceUrl: guid,
  }], {
    id: 'feed:techmeme', q: 'feed:techmeme.com', angle: 'infra',
    feedUrl: 'https://techmeme.com/feed.xml', locale, feedBoost: 0,
  }, Date.parse('2026-09-03T18:52:00Z'));
  const legacyId = db.prepare('SELECT id FROM articles WHERE guid=?').get(guid).id;
  assert.notEqual(legacyId, publisherId);

  ingestItems([{
    title, link: url, guid, editorialKey: key, pubDate,
    sourceName: 'Atlas Publisher', sourceUrl: 'https://atlas-publisher.example/',
  }], {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'infra',
    feedUrl: 'https://techmeme.com/feed.xml', locale, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  }, Date.parse('2026-09-03T18:53:00Z'));

  assert.equal(db.prepare('SELECT COUNT(*) n FROM articles WHERE url=?').get(url).n, 1);
  assert.equal(db.prepare('SELECT COUNT(*) n FROM articles WHERE id=?').get(legacyId).n, 0);
  const publisher = db.prepare(`SELECT id,shard,cluster_id,is_original,cluster_n,value_src
    FROM articles WHERE id=?`).get(publisherId);
  assert.deepEqual({ ...publisher }, {
    id: publisherId, shard: 'feed:atlas-publisher', cluster_id: publisherId,
    is_original: 1, cluster_n: 1, value_src: 'editorial',
  });
  assert.equal(db.prepare(`SELECT article_id FROM editorial_references
    WHERE source='techmeme' AND source_key=?`).get(key).article_id, publisherId);
  assert.equal(db.prepare("SELECT articles FROM domains WHERE domain='techmeme.com'").get().articles, 0);
  ingestItems([{
    title: 'OpenAI launches Cascade agent platform for enterprise AI',
    link: 'https://cascade.example/launch', guid: 'post-deletion-high-water',
    pubDate, sourceName: 'Cascade', sourceUrl: 'https://cascade.example/',
  }], {
    id: 'feed:cascade', q: 'AI', angle: 'apps',
    feedUrl: 'https://cascade.example/feed', locale, feedBoost: 0,
  }, Date.parse('2026-09-03T18:54:00Z'));
  const successor = db.prepare("SELECT id FROM articles WHERE guid='post-deletion-high-water'").get();
  assert.ok(successor.id > legacyId, 'deleting the maximum owned id cannot make /r/:id reusable');
});

test('a pre-AUTOINCREMENT database migrates to the durable article id allocator', () => {
  const oldDb = join(HERE, 'tmp-techmeme-old-schema.sqlite3');
  for (const suffix of ['', '-wal', '-shm']) rmSync(oldDb + suffix, { force: true });
  const script = `
    import { DatabaseSync } from 'node:sqlite';
    const legacy = new DatabaseSync(process.env.OLD_DB);
    legacy.exec(\`CREATE TABLE articles (
      id INTEGER PRIMARY KEY, url TEXT NOT NULL, guid TEXT NOT NULL UNIQUE,
      title TEXT NOT NULL, domain TEXT NOT NULL, publisher TEXT,
      published_at INTEGER NOT NULL, first_seen_at INTEGER NOT NULL,
      lang TEXT, locale TEXT, angle TEXT, shard TEXT, query TEXT,
      relevance INTEGER NOT NULL, relevant INTEGER NOT NULL, hits TEXT,
      dedupe_key TEXT NOT NULL, cluster_id INTEGER, is_original INTEGER NOT NULL DEFAULT 1
    );\`);
    legacy.prepare(\`INSERT INTO articles
      (id,url,guid,title,domain,published_at,first_seen_at,relevance,relevant,dedupe_key,cluster_id,is_original)
      VALUES (7,'https://old.example/7','old-7','Old AI row','old.example',1,1,3,1,'old',7,1)\`).run();
    legacy.close();
    process.env.INEWS_DB_PATH = process.env.OLD_DB;
    const { getDb } = await import('./src/lib/db.js');
    const db = getDb();
    db.prepare('DELETE FROM articles WHERE id=7').run();
    const { ingestItems } = await import('./src/lib/ingest.js');
    ingestItems([{
      title:'OpenAI releases GPT-12 model', link:'https://new.example/8', guid:'new-8',
      pubDate:new Date().toUTCString(), sourceName:'New', sourceUrl:'https://new.example/'
    }], { id:'feed:new', q:'AI', angle:'models', locale:{id:'en-US',lang:'en'}, feedBoost:0 });
    process.stdout.write(String(db.prepare("SELECT id FROM articles WHERE guid='new-8'").get().id));
  `;
  const run = spawnSync(process.execPath, ['--no-warnings', '--input-type=module', '-e', script], {
    cwd: ROOT, env: { ...process.env, OLD_DB: oldDb, INEWS_DB_PATH: oldDb }, encoding: 'utf8',
  });
  try {
    assert.equal(run.status, 0, run.stderr || run.stdout);
    assert.equal(run.stdout, '8');
  } finally {
    for (const suffix of ['', '-wal', '-shm']) rmSync(oldDb + suffix, { force: true });
  }
});

test('concurrent processes serialize an old-schema migration', async () => {
  const { DatabaseSync } = await import('node:sqlite');
  const oldDb = join(HERE, 'tmp-techmeme-concurrent-migration.sqlite3');
  for (const suffix of ['', '-wal', '-shm']) rmSync(oldDb + suffix, { force: true });
  const legacy = new DatabaseSync(oldDb);
  legacy.exec(`CREATE TABLE articles (
    id INTEGER PRIMARY KEY, url TEXT NOT NULL, guid TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL, domain TEXT NOT NULL, publisher TEXT,
    published_at INTEGER NOT NULL, first_seen_at INTEGER NOT NULL,
    lang TEXT, locale TEXT, angle TEXT, shard TEXT, query TEXT,
    relevance INTEGER NOT NULL, relevant INTEGER NOT NULL, hits TEXT,
    dedupe_key TEXT NOT NULL, cluster_id INTEGER, is_original INTEGER NOT NULL DEFAULT 1
  )`);
  legacy.close();
  const script = `
    process.env.INEWS_DB_PATH = process.env.OLD_DB;
    const { getDb } = await import('./src/lib/db.js');
    const db = getDb();
    const columns = db.prepare("PRAGMA table_info('articles')").all().map((x) => x.name);
    if (!columns.includes('region') || !columns.includes('cluster_n')) process.exit(7);
    process.stdout.write('ready');
  `;
  const runOne = () => new Promise((resolve) => {
    const child = spawn(process.execPath, ['--no-warnings', '--input-type=module', '-e', script], {
      cwd: ROOT, env: { ...process.env, OLD_DB: oldDb, INEWS_DB_PATH: oldDb },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '', stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('close', (code) => resolve({ code, stdout, stderr }));
  });
  try {
    const results = await Promise.all([runOne(), runOne(), runOne(), runOne()]);
    for (const result of results) {
      assert.equal(result.code, 0, result.stderr || result.stdout);
      assert.equal(result.stdout, 'ready');
    }
  } finally {
    for (const suffix of ['', '-wal', '-shm']) rmSync(oldDb + suffix, { force: true });
  }
});

test('concurrent ordinary ingests reserve the writer before cluster reads', async () => {
  const concurrentDb = join(HERE, 'tmp-techmeme-concurrent-ingest.sqlite3');
  for (const suffix of ['', '-wal', '-shm']) rmSync(concurrentDb + suffix, { force: true });
  const initScript = `
    process.env.INEWS_DB_PATH = process.env.TEST_DB;
    const { getDb } = await import('./src/lib/db.js');
    getDb();
  `;
  const initialized = spawnSync(
    process.execPath, ['--no-warnings', '--input-type=module', '-e', initScript],
    { cwd: ROOT, env: { ...process.env, TEST_DB: concurrentDb }, encoding: 'utf8' },
  );
  assert.equal(initialized.status, 0, initialized.stderr || initialized.stdout);

  const workerScript = `
    process.env.INEWS_DB_PATH = process.env.TEST_DB;
    const { getDb } = await import('./src/lib/db.js');
    const { ingestItems } = await import('./src/lib/ingest.js');
    getDb();
    const delay = Number(process.env.START_AT) - Date.now();
    if (delay > 0) Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, delay);
    const worker = Number(process.env.WORKER);
    const items = Array.from({ length: 50 }, (_, item) => ({
      title: \`OpenAI builds AI data center worker \${worker} unit \${item}\`,
      link: \`https://concurrent-\${worker}.example/story-\${item}\`,
      guid: \`concurrent-\${worker}-\${item}\`,
      pubDate: new Date(1788465600000 + worker * 1000 + item).toUTCString(),
      sourceName: \`Worker \${worker}\`,
      sourceUrl: \`https://concurrent-\${worker}.example/\`,
    }));
    const result = ingestItems(items, {
      id: \`feed:concurrent-\${worker}\`, q: 'AI', angle: 'compute',
      locale: { id: 'en-US', lang: 'en' }, feedBoost: 0,
    }, 1788469200000 + worker);
    process.stdout.write(String(result.kept));
  `;
  const startAt = String(Date.now() + 500);
  const runOne = (worker) => new Promise((resolve) => {
    const child = spawn(
      process.execPath, ['--no-warnings', '--input-type=module', '-e', workerScript],
      {
        cwd: ROOT,
        env: { ...process.env, TEST_DB: concurrentDb, START_AT: startAt, WORKER: String(worker) },
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    );
    let stdout = '', stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('close', (code) => resolve({ code, stdout, stderr }));
  });
  try {
    const results = await Promise.all([0, 1, 2, 3].map(runOne));
    for (const result of results) {
      assert.equal(result.code, 0, result.stderr || result.stdout);
      assert.equal(result.stdout, '50');
    }
    const { DatabaseSync } = await import('node:sqlite');
    const check = new DatabaseSync(concurrentDb);
    try {
      assert.equal(check.prepare('SELECT COUNT(*) n FROM articles').get().n, 200);
    } finally {
      check.close();
    }
  } finally {
    for (const suffix of ['', '-wal', '-shm']) rmSync(concurrentDb + suffix, { force: true });
  }
});

test('legacy generic Techmeme rows migrate from aggregator metadata to the original publisher', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const key = '260903p77';
  const guid = techmemeGuid(key);
  const locale = { id: 'en-US', lang: 'en' };
  const now = Date.parse('2026-09-03T20:00:00Z');
  ingestItems([{
    title: 'Google releases Gemini 4 Pro', link: guid, guid,
    pubDate: 'Thu, 03 Sep 2026 14:00:00 -0400', sourceName: '', sourceUrl: guid,
  }], {
    id: 'feed:techmeme', q: 'feed:techmeme.com', angle: 'models', feedUrl: 'https://techmeme.com/feed.xml',
    locale, feedBoost: 0,
  }, now);
  const legacyId = getDb().prepare('SELECT id FROM articles WHERE guid=?').get(guid).id;
  const before = getDb().prepare('SELECT COUNT(*) n FROM articles').get().n;

  ingestItems([{
    title: 'Google releases Gemini 4 Pro', link: 'https://deepmind.google/gemini-4', guid,
    editorialKey: key, pubDate: 'Thu, 03 Sep 2026 14:00:00 -0400',
    sourceName: 'Google DeepMind', sourceUrl: 'https://deepmind.google/', angle: 'models',
  }], {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'models',
    feedUrl: 'https://techmeme.com/feed.xml', locale, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  }, now + 1_000);

  const db = getDb();
  assert.equal(db.prepare('SELECT COUNT(*) n FROM articles').get().n, before);
  const row = db.prepare('SELECT * FROM articles WHERE guid=?').get(guid);
  assert.ok(row.id > legacyId, 'a changed redirect identity receives a new article id');
  assert.equal(row.url, 'https://deepmind.google/gemini-4');
  assert.equal(row.domain, 'deepmind.google');
  assert.equal(row.publisher, 'Google DeepMind');
  assert.equal(row.shard, 'feed:techmeme-live');
  assert.equal(row.value_src, 'editorial');
  assert.equal(db.prepare('SELECT article_id FROM editorial_references WHERE source_key=?').get(key).article_id,
    row.id);
});

test('Techmeme-only infrastructure admission survives the generic startup backfill', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const { backfillValues } = await import('../src/lib/value.js');
  const { scoreRelevance } = await import('../src/lib/relevance.js');
  const key = '260903p78';
  const guid = techmemeGuid(key);
  ingestItems([{
    title: 'HPE faces server supply constraints after signing a $3.5B deal',
    link: 'https://www.hpe.com/story', guid, editorialKey: key,
    pubDate: 'Thu, 03 Sep 2026 14:05:00 -0400', sourceName: 'HPE', sourceUrl: 'https://www.hpe.com/',
  }], {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'models',
    feedUrl: 'https://techmeme.com/feed.xml', locale: { id: 'en-US', lang: 'en' }, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  }, Date.parse('2026-09-03T20:06:00Z'));
  const db = getDb();
  const before = db.prepare('SELECT value,genre,value_src FROM articles WHERE guid=?').get(guid);
  assert.deepEqual({ ...before }, { value: 2, genre: 'compute', value_src: 'editorial' });
  backfillValues(db, { scoreRelevance });
  assert.deepEqual({ ...db.prepare('SELECT value,genre,value_src FROM articles WHERE guid=?').get(guid) },
    { ...before });
});

test('generic recheck cannot overwrite an editorial admission floor', async () => {
  const { getDb } = await import('../src/lib/db.js');
  const guid = techmemeGuid('260903p78');
  const db = getDb();
  const before = db.prepare(`SELECT relevance,relevant,value,genre,value_src
    FROM articles WHERE guid=?`).get(guid);
  assert.equal(before.value_src, 'editorial');
  const run = spawnSync(process.execPath, ['--no-warnings', join(ROOT, 'src', 'cli.js'), 'recheck'], {
    cwd: ROOT, env: { ...process.env, INEWS_DB_PATH: DB }, encoding: 'utf8',
  });
  assert.equal(run.status, 0, run.stderr || run.stdout);
  assert.deepEqual({ ...db.prepare(`SELECT relevance,relevant,value,genre,value_src
    FROM articles WHERE guid=?`).get(guid) }, { ...before });
});

test('an edited pml repairs its old cluster and rejection cannot revoke accepted history', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const key = '260903p79';
  const guid = techmemeGuid(key);
  const shard = {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'models',
    feedUrl: 'https://techmeme.com/feed.xml', locale: { id: 'en-US', lang: 'en' }, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  };
  const base = { guid, editorialKey: key, pubDate: 'Thu, 03 Sep 2026 14:10:00 -0400' };
  const oldTitle = 'Quanta opens Project Cobalt 250 MW AI data center with liquid cooling';
  ingestItems([{ ...base, title: oldTitle, link: 'https://quanta.example/cobalt',
    sourceName: 'Quanta', sourceUrl: 'https://quanta.example/' }], shard,
  Date.parse('2026-09-03T20:11:00Z'));
  const db = getDb();
  const oldId = db.prepare('SELECT id FROM articles WHERE guid=?').get(guid).id;
  ingestItems([{
    title: oldTitle, link: 'https://wire-cobalt.example/copy', guid: 'wire-cobalt-copy',
    pubDate: 'Thu, 03 Sep 2026 14:10:30 -0400', sourceName: 'Cobalt Wire',
    sourceUrl: 'https://wire-cobalt.example/',
  }], {
    id: 'feed:ordinary-cobalt', q: 'AI', angle: 'infra',
    feedUrl: 'https://wire-cobalt.example/feed', locale: { id: 'en-US', lang: 'en' }, feedBoost: 0,
  }, Date.parse('2026-09-03T20:11:30Z'));
  const wireId = db.prepare("SELECT id FROM articles WHERE guid='wire-cobalt-copy'").get().id;
  assert.equal(db.prepare('SELECT cluster_id FROM articles WHERE id=?').get(wireId).cluster_id, oldId);

  ingestItems([{ ...base, title: 'Anthropic releases Claude 6', link: 'https://anthropic.com/claude-6',
    sourceName: 'Anthropic', sourceUrl: 'https://anthropic.com/' }], shard,
  Date.parse('2026-09-03T20:12:00Z'));
  let row = db.prepare('SELECT id,title,url,domain,relevant,value FROM articles WHERE guid=?').get(guid);
  assert.ok(row.id > oldId, 'the public redirect id is immutable across URL changes');
  assert.deepEqual({ ...row }, { title: 'Anthropic releases Claude 6', url: 'https://anthropic.com/claude-6',
    domain: 'anthropic.com', relevant: 1, value: 3, id: row.id });
  assert.equal(db.prepare('SELECT COUNT(*) n FROM articles WHERE id=?').get(oldId).n, 0);
  assert.deepEqual({ ...db.prepare(`SELECT cluster_id,is_original,cluster_n
    FROM articles WHERE id=?`).get(wireId) },
  { cluster_id: wireId, is_original: 1, cluster_n: 1 },
  'the valid member becomes a visible singleton after its hidden head is retired');
  assert.deepEqual({ ...db.prepare(`SELECT cluster_id,is_original,cluster_n
    FROM articles WHERE id=?`).get(row.id) },
  { cluster_id: row.id, is_original: 1, cluster_n: 1 });

  ingestItems([{ ...base, title: 'Nvidia stock rises 8% after an analyst upgrade',
    link: 'https://finance.example/nvidia', sourceName: 'Finance Example',
    sourceUrl: 'https://finance.example/' }], shard, Date.parse('2026-09-03T20:13:00Z'));
  row = db.prepare('SELECT id,title,relevant,value,genre FROM articles WHERE guid=?').get(guid);
  assert.deepEqual({ ...row }, { id: row.id, title: 'Anthropic releases Claude 6',
    relevant: 1, value: 3, genre: 'model' });
  const ref = db.prepare(`SELECT article_id,title,url,value FROM editorial_references
    WHERE source='techmeme' AND source_key=?`).get(key);
  assert.deepEqual({ ...ref }, { article_id: row.id, title: 'Anthropic releases Claude 6',
    url: 'https://anthropic.com/claude-6', value: 3 });
});

test('one pml changing identity preserves a shared historical Techmeme row', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const keyA = '260903p81';
  const keyB = '260903p82';
  const guidA = techmemeGuid(keyA);
  const oldTitle = 'Arista ships 3.2Tbps Ethernet switch for hyperscale AI clusters';
  const oldUrl = 'https://redwood.example/oracle-campus';
  const shard = {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'infra',
    feedUrl: 'https://techmeme.com/feed.xml', locale: { id: 'en-US', lang: 'en' }, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  };
  const common = {
    title: oldTitle, link: oldUrl, pubDate: 'Thu, 03 Sep 2026 14:20:00 -0400',
    sourceName: 'Redwood Systems', sourceUrl: 'https://redwood.example/',
  };
  ingestItems([{ ...common, guid: guidA, editorialKey: keyA }], shard,
    Date.parse('2026-09-03T20:21:00Z'));
  const oldId = db.prepare('SELECT id FROM articles WHERE guid=?').get(guidA).id;
  ingestItems([{ ...common, guid: techmemeGuid(keyB), editorialKey: keyB }], shard,
    Date.parse('2026-09-03T20:22:00Z'));
  assert.deepEqual(db.prepare(`SELECT source_key,article_id FROM editorial_references
    WHERE source_key IN (?,?) ORDER BY source_key`).all(keyA, keyB).map((row) => ({ ...row })), [
    { source_key: keyA, article_id: oldId }, { source_key: keyB, article_id: oldId },
  ]);

  ingestItems([{
    title: 'Mistral releases Le Chat 5 enterprise AI model',
    link: 'https://mistral.ai/news/le-chat-5', guid: guidA, editorialKey: keyA,
    pubDate: 'Thu, 03 Sep 2026 14:25:00 -0400', sourceName: 'Mistral AI',
    sourceUrl: 'https://mistral.ai/',
  }], shard, Date.parse('2026-09-03T20:26:00Z'));

  const next = db.prepare('SELECT id,url FROM articles WHERE guid=?').get(guidA);
  assert.ok(next.id > oldId);
  assert.equal(next.url, 'https://mistral.ai/news/le-chat-5');
  const old = db.prepare(`SELECT guid,url,relevant,value,cluster_id,is_original,cluster_n
    FROM articles WHERE id=?`).get(oldId);
  assert.match(old.guid, /^retired-techmeme:/);
  assert.equal(old.url, oldUrl);
  assert.deepEqual({ relevant: old.relevant, value: old.value, cluster_id: old.cluster_id,
    is_original: old.is_original, cluster_n: old.cluster_n },
  { relevant: 1, value: 2, cluster_id: oldId, is_original: 1, cluster_n: 1 });
  assert.equal(db.prepare(`SELECT article_id FROM editorial_references
    WHERE source_key=?`).get(keyA).article_id, next.id);
  assert.equal(db.prepare(`SELECT article_id FROM editorial_references
    WHERE source_key=?`).get(keyB).article_id, oldId,
  'the unchanged pml retains navigation to the old selected story');

  ingestItems([{
    title: 'Cohere releases Command R 9 enterprise AI model',
    link: 'https://cohere.com/command-r-9', guid: techmemeGuid(keyB), editorialKey: keyB,
    pubDate: 'Thu, 03 Sep 2026 14:27:00 -0400', sourceName: 'Cohere',
    sourceUrl: 'https://cohere.com/',
  }], shard, Date.parse('2026-09-03T20:28:00Z'));
  const nextB = db.prepare('SELECT article_id FROM editorial_references WHERE source_key=?')
    .get(keyB).article_id;
  assert.notEqual(nextB, oldId);
  assert.equal(db.prepare('SELECT COUNT(*) n FROM articles WHERE id=?').get(oldId).n, 0,
  'the tombstoned owned row is retired after its final reference moves');
});

test('a late older accepted observation cannot roll a pml back', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const key = '260903p83';
  const guid = techmemeGuid(key);
  const shard = {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'models',
    feedUrl: 'https://techmeme.com/feed.xml', locale: { id: 'en-US', lang: 'en' }, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  };
  const older = {
    title: 'OpenAI releases GPT-13 reasoning model for enterprise agents',
    link: 'https://openai.example/gpt-13', guid, editorialKey: key,
    pubDate: 'Thu, 03 Sep 2026 14:30:00 -0400', sourceName: 'OpenAI',
    sourceUrl: 'https://openai.example/',
  };
  const newer = {
    title: 'Anthropic releases Claude 7 multimodal reasoning model',
    link: 'https://anthropic.example/claude-7', guid, editorialKey: key,
    // Techmeme keeps a pml's original publication timestamp across edits.
    pubDate: older.pubDate, sourceName: 'Anthropic',
    sourceUrl: 'https://anthropic.example/',
  };
  ingestItems([older], shard, Date.parse('2026-09-03T18:40:00Z'));
  ingestItems([newer], shard, Date.parse('2026-09-03T18:42:00Z'));
  // Invoked last to model response order, but its request began before the B
  // request. pollShard passes request-start `started` as this argument.
  const late = ingestItems([older], shard, Date.parse('2026-09-03T18:41:00Z'));

  assert.deepEqual(late, { items: 1, fresh: 0, kept: 0 });
  const ref = db.prepare(`SELECT article_id,title,url,selected_at FROM editorial_references
    WHERE source='techmeme' AND source_key=?`).get(key);
  assert.equal(ref.title, newer.title);
  assert.equal(ref.url, newer.link);
  assert.equal(ref.selected_at, Date.parse(older.pubDate));
  assert.equal(db.prepare('SELECT url FROM articles WHERE id=?').get(ref.article_id).url, newer.link);
  assert.equal(db.prepare('SELECT COUNT(*) n FROM articles WHERE url=?').get(older.link).n, 0,
  'the stale response does not recreate the superseded redirect target');
});

test('a newer rejected observation blocks an older unseen accepted response', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const key = '260903p91';
  const guid = techmemeGuid(key);
  const pubDate = 'Thu, 03 Sep 2026 15:05:00 -0400';
  const shard = {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'models',
    feedUrl: 'https://techmeme.com/feed.xml', locale: { id: 'en-US', lang: 'en' }, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  };
  const current = {
    title: 'Anthropic releases Claude 9 multimodal reasoning model',
    link: 'https://watermark.example/claude-9', guid, editorialKey: key, pubDate,
    sourceName: 'Watermark', sourceUrl: 'https://watermark.example/',
  };
  ingestItems([current], shard, Date.parse('2026-09-03T19:06:00Z'));
  ingestItems([{
    title: 'Nvidia stock rises 8% after an analyst upgrade',
    link: 'https://watermark.example/noise', guid, editorialKey: key, pubDate,
    sourceName: 'Watermark', sourceUrl: 'https://watermark.example/',
  }], shard, Date.parse('2026-09-03T19:08:00Z'));
  const late = ingestItems([{
    title: 'Google releases Gemini 6 multimodal reasoning model',
    link: 'https://watermark.example/gemini-6', guid, editorialKey: key, pubDate,
    sourceName: 'Watermark', sourceUrl: 'https://watermark.example/',
  }], shard, Date.parse('2026-09-03T19:07:00Z'));

  assert.deepEqual(late, { items: 1, fresh: 0, kept: 0 });
  const ref = db.prepare(`SELECT title,url FROM editorial_references
    WHERE source='techmeme' AND source_key=?`).get(key);
  assert.deepEqual({ ...ref }, { title: current.title, url: current.link });
  assert.equal(db.prepare("SELECT accepted FROM editorial_observations WHERE source_key=?").get(key).accepted,
    0, 'the newest rejected snapshot owns the observation watermark without revoking acceptance');
  assert.equal(db.prepare("SELECT COUNT(*) n FROM articles WHERE url='https://watermark.example/gemini-6'").get().n,
    0);
});

test('a later River edit can replace RSS identity while preserving precise selected time', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const key = '260903p92';
  const guid = techmemeGuid(key);
  const common = {
    guid, editorialKey: key, sourceName: 'Precision', sourceUrl: 'https://precision.example/',
  };
  const shard = {
    q: 'feed:techmeme.com', angle: 'models', locale: { id: 'en-US', lang: 'en' }, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  };
  ingestItems([{
    ...common, title: 'OpenAI releases GPT-15 reasoning model',
    link: 'https://precision.example/rss-target',
    pubDate: 'Thu, 03 Sep 2026 12:25:09 -0400',
  }], {
    ...shard, id: 'feed:techmeme-live', feedUrl: 'https://techmeme.com/feed.xml',
    feedFormat: 'techmeme-rss',
  }, Date.parse('2026-09-03T16:26:00Z'));
  ingestItems([{
    ...common, title: 'Anthropic releases Claude 10 reasoning model',
    link: 'https://precision.example/river-target',
    pubDate: 'Thu, 03 Sep 2026 12:25:00 -0400',
  }], {
    ...shard, id: 'feed:techmeme-river', feedUrl: 'https://techmeme.com/river',
    feedFormat: 'techmeme-river',
  }, Date.parse('2026-09-03T16:27:00Z'));

  const ref = db.prepare(`SELECT title,url,selected_at,observer FROM editorial_references
    WHERE source='techmeme' AND source_key=?`).get(key);
  assert.deepEqual({ ...ref }, {
    title: 'Anthropic releases Claude 10 reasoning model',
    url: 'https://precision.example/river-target',
    selected_at: Date.parse('Thu, 03 Sep 2026 12:25:09 -0400'),
    observer: 'feed:techmeme-river',
  });
});

test('moving an accepted pml restores an independent publisher scoring base', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const locale = { id: 'en-US', lang: 'en' };
  const ordinary = {
    id: 'feed:overlay-base', q: 'AI', angle: 'infra',
    feedUrl: 'https://overlay.example/feed', locale, feedBoost: 0,
  };
  const key = '260903p84';
  const guid = techmemeGuid(key);
  const first = {
    title: 'SB Energy has 8.8GW of data center capacity and a large backlog',
    link: 'https://overlay-a.example/capacity', guid: 'overlay-publisher-a',
    pubDate: 'Thu, 03 Sep 2026 14:45:00 -0400', sourceName: 'Overlay A',
    sourceUrl: 'https://overlay-a.example/',
  };
  const second = {
    title: 'Cohere releases Command R 10 enterprise AI reasoning model',
    link: 'https://overlay-b.example/command-r-10', guid: 'overlay-publisher-b',
    pubDate: 'Thu, 03 Sep 2026 14:50:00 -0400', sourceName: 'Overlay B',
    sourceUrl: 'https://overlay-b.example/',
  };
  ingestItems([first, second], ordinary, Date.parse('2026-09-03T18:51:00Z'));
  const firstId = db.prepare('SELECT id FROM articles WHERE guid=?').get(first.guid).id;
  const secondId = db.prepare('SELECT id FROM articles WHERE guid=?').get(second.guid).id;
  const base = db.prepare(`SELECT relevance,relevant,hits,angle,value,genre,value_src
    FROM articles WHERE id=?`).get(firstId);
  const tech = {
    ...ordinary, id: 'feed:techmeme-live', q: 'feed:techmeme.com',
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  };
  ingestItems([{
    ...first, guid, editorialKey: key, pubDate: 'Thu, 03 Sep 2026 14:46:00 -0400',
  }], tech, Date.parse('2026-09-03T18:52:00Z'));
  assert.equal(db.prepare('SELECT value_src FROM articles WHERE id=?').get(firstId).value_src,
    'editorial');

  ingestItems([{
    ...second, guid, editorialKey: key, pubDate: 'Thu, 03 Sep 2026 14:51:00 -0400',
  }], tech, Date.parse('2026-09-03T18:53:00Z'));
  assert.deepEqual({ ...db.prepare(`SELECT relevance,relevant,hits,angle,value,genre,value_src
    FROM articles WHERE id=?`).get(firstId) }, { ...base },
  'moving the current accepted pointer removes the old derived editorial overlay');
  assert.equal(db.prepare(`SELECT COUNT(*) n FROM article_editorial_bases
    WHERE article_id=?`).get(firstId).n, 0);
  assert.equal(db.prepare(`SELECT article_id FROM editorial_references
    WHERE source='techmeme' AND source_key=?`).get(key).article_id, secondId);
  assert.equal(db.prepare('SELECT value_src FROM articles WHERE id=?').get(secondId).value_src,
    'editorial');
});

test('retargeting within one cluster leaves only the current pick and head overlaid', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const locale = { id: 'en-US', lang: 'en' };
  const title = 'VoltWeave has 6.4GW of AI data center capacity and a transformer backlog';
  const pubDate = 'Thu, 03 Sep 2026 15:10:00 -0400';
  const ordinary = {
    id: 'feed:same-cluster-base', q: 'AI', angle: 'infra',
    feedUrl: 'https://same-cluster.example/feed', locale, feedBoost: 0,
  };
  const rows = [
    { guid: 'same-cluster-head', link: 'https://same-head.example/story', sourceName: 'Head',
      sourceUrl: 'https://same-head.example/', pubDate: 'Thu, 03 Sep 2026 15:09:00 -0400' },
    { guid: 'same-cluster-a', link: 'https://same-a.example/story', sourceName: 'A',
      sourceUrl: 'https://same-a.example/', pubDate },
    { guid: 'same-cluster-b', link: 'https://same-b.example/story', sourceName: 'B',
      sourceUrl: 'https://same-b.example/', pubDate: 'Thu, 03 Sep 2026 15:11:00 -0400' },
  ].map((row) => ({ ...row, title }));
  ingestItems(rows, ordinary, Date.parse('2026-09-03T19:12:00Z'));
  const [, a, b] = rows.map((row) => db.prepare('SELECT * FROM articles WHERE guid=?').get(row.guid));
  const aBase = db.prepare(`SELECT relevance,relevant,hits,angle,value,genre,value_src
    FROM articles WHERE id=?`).get(a.id);
  const key = '260903p94';
  const guid = techmemeGuid(key);
  const tech = {
    ...ordinary, id: 'feed:techmeme-live', q: 'feed:techmeme.com',
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  };
  ingestItems([{
    ...rows[1], guid, editorialKey: key, pubDate,
  }], tech, Date.parse('2026-09-03T19:13:00Z'));
  ingestItems([{
    ...rows[2], guid, editorialKey: key, pubDate,
  }], tech, Date.parse('2026-09-03T19:14:00Z'));

  assert.deepEqual({ ...db.prepare(`SELECT relevance,relevant,hits,angle,value,genre,value_src
    FROM articles WHERE id=?`).get(a.id) }, { ...aBase });
  const displayHeadId = db.prepare('SELECT cluster_id FROM articles WHERE id=?').get(b.id).cluster_id;
  assert.equal(db.prepare('SELECT value_src FROM articles WHERE id=?').get(displayHeadId).value_src,
    'editorial');
  assert.equal(db.prepare('SELECT value_src FROM articles WHERE id=?').get(b.id).value_src,
    'editorial');
  assert.equal(db.prepare(`SELECT article_id FROM editorial_references
    WHERE source='techmeme' AND source_key=?`).get(key).article_id, b.id);
});

test('exact replacement joins the publisher and former owned-row components', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const locale = { id: 'en-US', lang: 'en' };
  const url = 'https://bridge-publisher.example/same-story';
  const key = '260903p85';
  const guid = techmemeGuid(key);
  const pubDate = 'Thu, 03 Sep 2026 14:55:00 -0400';
  ingestItems([{
    title: 'OpenAI releases GPT-13 reasoning model for enterprise agents',
    link: url, guid: 'bridge-independent-publisher', pubDate,
    sourceName: 'Bridge Publisher', sourceUrl: 'https://bridge-publisher.example/',
  }], {
    id: 'feed:bridge-publisher', q: 'AI', angle: 'models',
    feedUrl: 'https://bridge-publisher.example/feed', locale, feedBoost: 0,
  }, Date.parse('2026-09-03T18:56:00Z'));
  const bridgeTitle = 'NebulaForge ships ZQ91 optical interconnect for a 417MW AI data center';
  ingestItems([{
    title: bridgeTitle, link: 'https://bridge-wire.example/copy', guid: 'bridge-wire-copy',
    pubDate: 'Thu, 03 Sep 2026 14:56:00 -0400', sourceName: 'Bridge Wire',
    sourceUrl: 'https://bridge-wire.example/',
  }], {
    id: 'feed:bridge-wire', q: 'AI', angle: 'infra',
    feedUrl: 'https://bridge-wire.example/feed', locale, feedBoost: 0,
  }, Date.parse('2026-09-03T18:57:00Z'));
  ingestItems([{
    title: bridgeTitle, link: url, guid, pubDate: 'Thu, 03 Sep 2026 14:57:00 -0400',
    sourceName: 'Bridge Publisher', sourceUrl: 'https://bridge-publisher.example/',
  }], {
    id: 'feed:techmeme', q: 'feed:techmeme.com', angle: 'infra',
    feedUrl: 'https://techmeme.com/feed.xml', locale, feedBoost: 0,
  }, Date.parse('2026-09-03T18:58:00Z'));
  const ownedId = db.prepare('SELECT id FROM articles WHERE guid=?').get(guid).id;

  ingestItems([{
    title: bridgeTitle, link: url, guid, editorialKey: key,
    pubDate: 'Thu, 03 Sep 2026 14:58:00 -0400', sourceName: 'Bridge Publisher',
    sourceUrl: 'https://bridge-publisher.example/',
  }], {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'infra',
    feedUrl: 'https://techmeme.com/feed.xml', locale, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  }, Date.parse('2026-09-03T18:59:00Z'));

  const publisher = db.prepare("SELECT id,cluster_id FROM articles WHERE guid='bridge-independent-publisher'").get();
  const wire = db.prepare("SELECT id,cluster_id FROM articles WHERE guid='bridge-wire-copy'").get();
  assert.equal(db.prepare('SELECT COUNT(*) n FROM articles WHERE id=?').get(ownedId).n, 0);
  assert.equal(wire.cluster_id, publisher.cluster_id);
  const head = db.prepare('SELECT cluster_n FROM articles WHERE id=?').get(publisher.cluster_id);
  assert.ok(head.cluster_n >= 2,
  'the exact-URL replacement preserves the old component as members of the publisher story');
});

test('a techmeme.com publisher row is not system-owned without feed provenance', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const key = '260903p86';
  const guid = techmemeGuid(key);
  const locale = { id: 'en-US', lang: 'en' };
  ingestItems([{
    title: 'OpenAI releases GPT-14 reasoning model for enterprise agents',
    link: 'https://www.techmeme.com/publisher-owned-story', guid,
    pubDate: 'Thu, 03 Sep 2026 15:00:00 -0400', sourceName: 'Techmeme Publisher',
    sourceUrl: 'https://www.techmeme.com/',
  }], {
    id: 'feed:ordinary-tech-publisher', q: 'AI', angle: 'models',
    feedUrl: 'https://www.techmeme.com/publisher.xml', locale, feedBoost: 0,
  }, Date.parse('2026-09-03T19:01:00Z'));
  const original = db.prepare('SELECT id,guid,shard,url FROM articles WHERE guid=?').get(guid);

  ingestItems([{
    title: 'Anthropic releases Claude 8 multimodal reasoning model',
    link: 'https://anthropic.example/claude-8', guid, editorialKey: key,
    pubDate: 'Thu, 03 Sep 2026 15:01:00 -0400', sourceName: 'Anthropic',
    sourceUrl: 'https://anthropic.example/',
  }], {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'models',
    feedUrl: 'https://techmeme.com/feed.xml', locale, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  }, Date.parse('2026-09-03T19:02:00Z'));

  assert.deepEqual({ ...db.prepare('SELECT id,guid,shard,url FROM articles WHERE id=?').get(original.id) },
    { ...original }, 'destination domain is not deletion authority');
  const ref = db.prepare(`SELECT article_id FROM editorial_references
    WHERE source='techmeme' AND source_key=?`).get(key);
  assert.notEqual(ref.article_id, original.id);
  assert.equal(db.prepare('SELECT shard FROM articles WHERE id=?').get(ref.article_id).shard,
    'feed:techmeme-live');

  ingestItems([{
    title: 'Google releases Gemini 7 multimodal reasoning model',
    link: 'https://deepmind.example/gemini-7', guid, editorialKey: key,
    pubDate: 'Thu, 03 Sep 2026 15:01:00 -0400', sourceName: 'Google DeepMind',
    sourceUrl: 'https://deepmind.example/',
  }], {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'models',
    feedUrl: 'https://techmeme.com/feed.xml', locale, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  }, Date.parse('2026-09-03T19:03:00Z'));
  assert.deepEqual({ ...db.prepare('SELECT id,guid,shard,url FROM articles WHERE id=?').get(original.id) },
    { ...original }, 'later pml edits still cannot mutate or delete the GUID-colliding publisher row');
  const moved = db.prepare(`SELECT article_id,url FROM editorial_references
    WHERE source='techmeme' AND source_key=?`).get(key);
  assert.equal(moved.url, 'https://deepmind.example/gemini-7');
  assert.equal(db.prepare('SELECT url FROM articles WHERE id=?').get(moved.article_id).url, moved.url);
});

test('Techmeme noise creates neither an article nor an editorial reference', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const before = getDb().prepare('SELECT COUNT(*) n FROM articles').get().n;
  ingestItems([{
    title: 'Nvidia stock rises 8% after an AI analyst upgrade',
    link: 'https://finance.example/nvidia', guid: techmemeGuid('260903p99'),
    editorialKey: '260903p99', pubDate: 'Thu, 03 Sep 2026 13:00:00 -0400',
    sourceName: 'Finance Example', sourceUrl: 'https://finance.example/',
  }], {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'models',
    feedUrl: 'https://www.techmeme.com/feed.xml', feedBoost: 0,
    locale: { id: 'en-US', lang: 'en' }, editorialSource: 'techmeme',
    editorialPolicy: 'techmeme-ai',
  }, Date.parse('2026-09-03T18:00:00Z'));
  assert.equal(getDb().prepare('SELECT COUNT(*) n FROM articles').get().n, before);
  assert.equal(getDb().prepare(
    "SELECT COUNT(*) n FROM editorial_references WHERE source_key='260903p99'",
  ).get().n, 0);
});

test('different Techmeme infrastructure companies do not merge on template wording', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const now = Date.now();
  const shard = {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'infra',
    feedUrl: 'https://techmeme.com/feed.xml', locale: { id: 'en-US', lang: 'en' },
    feedBoost: 0, editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  };
  const rows = [
    {
      key: '260904p97', company: 'NorthGrid', capacity: '5GW',
      link: 'https://north-grid.example/capacity',
    },
    {
      key: '260904p98', company: 'SouthGrid', capacity: '7GW',
      link: 'https://south-grid.example/capacity',
    },
  ];
  for (const [offset, row] of rows.entries()) {
    ingestItems([{
      title: `${row.company} has ${row.capacity} of AI data center capacity and a transformer backlog`,
      link: row.link, guid: techmemeGuid(row.key), editorialKey: row.key,
      pubDate: new Date(now - (60 - offset) * 1000).toUTCString(),
      sourceName: row.company, sourceUrl: row.link,
    }], shard, now + offset);
  }
  const selected = db.prepare(`SELECT r.source_key, a.id, a.cluster_id
    FROM editorial_references r JOIN articles a ON a.id=r.article_id
    WHERE r.source='techmeme' AND r.source_key IN (?,?) ORDER BY r.source_key`)
    .all(rows[0].key, rows[1].key);
  assert.equal(selected.length, 2);
  assert.equal(selected[0].cluster_id, selected[0].id);
  assert.equal(selected[1].cluster_id, selected[1].id);
  assert.notEqual(selected[0].cluster_id, selected[1].cluster_id);
});

test('cross-language cluster merge carries an editorial floor to its earlier head', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const { applyMerge } = await import('../src/lib/merge.js');
  const db = getDb();
  const now = Date.now();
  const locale = { id: 'en-US', lang: 'en' };
  ingestItems([{
    title: 'Enterprise deploys AI software across support teams',
    link: 'https://early-merge.example/story', guid: 'early-editorial-merge-head',
    pubDate: new Date(now - 120_000).toUTCString(), sourceName: 'Early Merge',
    sourceUrl: 'https://early-merge.example/',
  }], {
    id: 'feed:early-merge', q: 'AI', angle: 'apps',
    feedUrl: 'https://early-merge.example/feed', locale, feedBoost: 0,
  }, now);
  const key = '260904p89';
  ingestItems([{
    title: 'xAI releases Grok 9 open-source reasoning model',
    link: 'https://x.ai/grok-9', guid: techmemeGuid(key), editorialKey: key,
    pubDate: new Date(now - 60_000).toUTCString(), sourceName: 'xAI', sourceUrl: 'https://x.ai/',
  }], {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'models',
    feedUrl: 'https://techmeme.com/feed.xml', locale, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  }, now);
  const early = db.prepare("SELECT id,value,value_src FROM articles WHERE guid='early-editorial-merge-head'").get();
  const picked = db.prepare('SELECT id FROM articles WHERE guid=?').get(techmemeGuid(key));
  assert.equal(early.value, 1);
  assert.equal(early.value_src, 'heur');
  assert.equal(applyMerge(db, early.id, picked.id), true);
  const head = db.prepare(`SELECT relevant,value,value_src,cluster_n FROM articles WHERE id=?`).get(early.id);
  assert.deepEqual({ ...head }, { relevant: 1, value: 3, value_src: 'editorial', cluster_n: 2 });
  assert.equal(db.prepare(`SELECT COUNT(*) n FROM articles
    WHERE id=? AND relevant=1 AND is_original=1 AND value>=2`).get(early.id).n, 1);
});

test('merge trigger preserves a higher-value head shape under a lower editorial floor', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const { applyMerge } = await import('../src/lib/merge.js');
  const db = getDb();
  const now = Date.now();
  const locale = { id: 'en-US', lang: 'en' };
  ingestItems([{
    title: 'Enterprise AI platform revenue expands after a major acquisition',
    link: 'https://shape-head.example/story', guid: 'shape-preserving-head',
    pubDate: new Date(now - 120_000).toUTCString(), sourceName: 'Shape Head',
    sourceUrl: 'https://shape-head.example/',
  }], {
    id: 'feed:shape-head', q: 'AI', angle: 'money',
    feedUrl: 'https://shape-head.example/feed', locale, feedBoost: 0,
  }, now);
  const head = db.prepare("SELECT id FROM articles WHERE guid='shape-preserving-head'").get();
  db.prepare(`UPDATE articles SET relevance=4,relevant=1,value=3,genre='business',
    angle='money',value_src='llm' WHERE id=?`).run(head.id);
  const key = '260904p95';
  ingestItems([{
    title: 'GridSpire has 4GW of data center capacity and a transformer backlog',
    link: 'https://shape-picked.example/story', guid: techmemeGuid(key), editorialKey: key,
    pubDate: new Date(now - 60_000).toUTCString(), sourceName: 'Shape Picked',
    sourceUrl: 'https://shape-picked.example/',
  }], {
    id: 'feed:techmeme-live', q: 'feed:techmeme.com', angle: 'infra',
    feedUrl: 'https://techmeme.com/feed.xml', locale, feedBoost: 0,
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  }, now);
  const picked = db.prepare('SELECT article_id FROM editorial_references WHERE source_key=?').get(key);
  assert.equal(db.prepare('SELECT value FROM editorial_references WHERE source_key=?').get(key).value, 2);
  assert.equal(applyMerge(db, head.id, picked.article_id), true);
  assert.deepEqual({ ...db.prepare(`SELECT value,genre,angle,value_src FROM articles
    WHERE id=?`).get(head.id) }, {
    value: 3, genre: 'business', angle: 'money', value_src: 'editorial',
  });
});

test('benchmark candidates exclude every member of a referenced cluster', async () => {
  const { ingestItems } = await import('../src/lib/ingest.js');
  const { getDb } = await import('../src/lib/db.js');
  const { stats } = await import('../src/server.js');
  const db = getDb();
  const now = Date.now();
  const pubDate = new Date(now - 60_000).toUTCString();
  const title = 'AMD launches Helios AI GPU cluster with HBM4 memory for data centers';
  const locale = { id: 'en-US', lang: 'en' };
  const ordinary = {
    id: 'feed:helios', q: 'AI', angle: 'infra',
    feedUrl: 'https://helios-one.example/feed', locale, feedBoost: 0,
  };
  ingestItems([{
    title, link: 'https://helios-one.example/story', guid: 'helios-one', pubDate,
    sourceName: 'Helios One', sourceUrl: 'https://helios-one.example/',
  }, {
    title, link: 'https://helios-wire.example/story', guid: 'helios-wire', pubDate,
    sourceName: 'Helios Wire', sourceUrl: 'https://helios-wire.example/',
  }], ordinary, now);
  const one = db.prepare("SELECT id,cluster_id FROM articles WHERE guid='helios-one'").get();
  const wire = db.prepare("SELECT id,cluster_id FROM articles WHERE guid='helios-wire'").get();
  assert.equal(one.cluster_id, wire.cluster_id);
  const before = stats().editorialBenchmark.candidate.total;

  const key = '260904p90';
  ingestItems([{
    title, link: 'https://helios-one.example/story', guid: techmemeGuid(key),
    editorialKey: key, pubDate, sourceName: 'Helios One',
    sourceUrl: 'https://helios-one.example/',
  }], {
    ...ordinary, id: 'feed:techmeme-live', q: 'feed:techmeme.com',
    editorialSource: 'techmeme', editorialPolicy: 'techmeme-ai',
  }, now + 1_000);
  const after = stats().editorialBenchmark.candidate.total;
  assert.equal(after, before - 2, 'both the referenced article and its wire copy leave the candidate pool');
  const indexes = db.prepare("PRAGMA index_list('editorial_references')").all();
  assert.ok(indexes.some((index) => index.name === 'idx_editorial_refs_article'));
  assert.ok(indexes.some((index) => index.name === 'idx_editorial_refs_article_only'));
});
