import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DB = join(HERE, 'tmp-pipeline.sqlite3');
rmSync(DB, { force: true }); rmSync(DB + '-wal', { force: true }); rmSync(DB + '-shm', { force: true });
process.env.INEWS_DB_PATH = DB;

const { getDb } = await import('../src/lib/db.js');
const { ingestFeed } = await import('../src/lib/ingest.js');
const { computeScore } = await import('../src/lib/domains.js');
const { scoreRelevance } = await import('../src/lib/relevance.js');
const { registrableDomain, dedupeKey, stripPublisherSuffix } = await import('../src/lib/normalize.js');
const { buildShards } = await import('../src/config/keywords.js');
const { parseFeed } = await import('../src/lib/rss.js');
const { errorDetail } = await import('../src/lib/fetcher.js');
const { pollShard } = await import('../src/scheduler.js');

const xml = readFileSync(join(HERE, 'fixtures', 'google-news-rss.xml'), 'utf8');
const shard = buildShards()[0];

test('rss parser reads CDATA, source url and pubDate', () => {
  const { items } = parseFeed(xml);
  assert.equal(items.length, 5);
  assert.equal(items[0].sourceUrl, 'https://www.reuters.com');
  assert.equal(items[0].sourceName, 'Reuters');
  assert.match(items[0].title, /^OpenAI launches GPT-5\.5/);
});

test('domain extraction handles multi-part suffixes', () => {
  assert.equal(registrableDomain('https://finance.yahoo.com/x'), 'yahoo.com');
  assert.equal(registrableDomain('https://www.bbc.co.uk/news'), 'bbc.co.uk');
  assert.equal(registrableDomain('https://spectrum.ieee.org/a'), 'spectrum.ieee.org');
});

test('publisher suffix stripping', () => {
  assert.equal(stripPublisherSuffix('Foo bar - Reuters', 'Reuters'), 'Foo bar');
});

test('relevance accepts AI stories and rejects Allen Iverson', () => {
  assert.ok(scoreRelevance({ title: 'OpenAI launches GPT-5.5' }).relevant);
  assert.ok(!scoreRelevance({ title: 'Allen Iverson says the AI era is over' }).relevant);
  assert.ok(!scoreRelevance({ title: 'Local council approves new bus timetable' }).relevant);
  assert.ok(scoreRelevance({ title: '英伟达发布新一代AI芯片，算力提升三倍', query: '大模型 OR 人工智能' }).relevant);
});

test('near-duplicate titles share a dedupe key', () => {
  assert.equal(
    dedupeKey('OpenAI launches GPT-5.5 with agentic browsing'),
    dedupeKey('OpenAI launches GPT-5.5, with agentic browsing!'),
  );
});

test('fetch errors retain the transport cause instead of only saying fetch failed', () => {
  const cause = Object.assign(new Error('Connect Timeout Error'), { code: 'UND_ERR_CONNECT_TIMEOUT' });
  const outer = new TypeError('fetch failed', { cause });
  assert.equal(errorDetail(outer), 'fetch failed <- UND_ERR_CONNECT_TIMEOUT: Connect Timeout Error');
});

test('a transport outage does not accumulate per-shard cooldown', async () => {
  const transportShard = { ...shard, id: 'test.transport-outage' };
  const cause = Object.assign(new Error('Connect Timeout Error'), { code: 'UND_ERR_CONNECT_TIMEOUT' });
  const fail = async () => { throw new TypeError('fetch failed', { cause }); };
  const bucket = { take: async () => {} };
  const noSleep = async () => {};

  await pollShard(transportShard, bucket, { getTextFn: fail, sleepFn: noSleep });
  await pollShard(transportShard, bucket, { getTextFn: fail, sleepFn: noSleep });

  const state = getDb().prepare('SELECT fails, cooldown_until FROM shard_state WHERE shard=?')
    .get(transportShard.id);
  assert.deepEqual({ ...state }, { fails: 0, cooldown_until: null });
});

test('ingest stores, clusters and attributes originality', () => {
  getDb();
  const now = Date.parse('2026-08-19T15:20:00Z');
  const first = ingestFeed(xml, shard, now);
  assert.equal(first.items, 5);
  assert.equal(first.kept, 3, 'bus timetable + Iverson dropped');

  // re-ingesting the same feed is a no-op (guid dedupe)
  const second = ingestFeed(xml, shard, now + 60_000);
  assert.equal(second.kept, 0);

  const db = getDb();
  const rows = db.prepare('SELECT title, domain, is_original, cluster_id FROM articles ORDER BY published_at').all();
  assert.deepEqual(rows.map((r) => r.domain), ['reuters.com', 'jiqizhixin.com', 'yahoo.com']);
  const reuters = rows[0], yahoo = rows[2];
  assert.equal(reuters.is_original, 1);
  assert.equal(yahoo.is_original, 0, 'Yahoo reprint joins the Reuters cluster');
  assert.equal(yahoo.cluster_id, reuters.cluster_id ?? yahoo.cluster_id);
});

test('domain score rewards originality and punishes pure relays', () => {
  const db = getDb();
  const r = db.prepare('SELECT * FROM domains WHERE domain = ?').get('reuters.com');
  const y = db.prepare('SELECT * FROM domains WHERE domain = ?').get('yahoo.com');
  assert.equal(r.seed_type, 'primary');
  assert.equal(y.seed_type, 'relay');
  assert.ok(computeScore(r).score > computeScore(y).score);
  assert.ok(computeScore(r).confidence < 1, 'one sample is not confident yet');
});
