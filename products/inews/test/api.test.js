import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DB = join(HERE, 'tmp-api.sqlite3');
for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true });
process.env.INEWS_DB_PATH = DB;

const { createServer } = await import('../src/server.js');
const { ingestFeed } = await import('../src/lib/ingest.js');
const { buildShards } = await import('../src/config/keywords.js');
const { readFileSync } = await import('node:fs');

const server = createServer();
await new Promise((r) => server.listen(0, r));
const base = `http://127.0.0.1:${server.address().port}`;
after(() => server.close());

// The analytics routes moved behind the admin gate, so the suite needs a real
// session: a cookie obtained the same way the browser gets one.
const { createUser } = await import('../src/auth/store.js');
await createUser({ email: 'suite@example.com', password: 'suite-password-123', role: 'admin' });
const loginRes = await fetch(base + '/api/auth/login', {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ email: 'suite@example.com', password: 'suite-password-123' }),
});
assert.equal(loginRes.status, 200, 'the suite must be able to log in');
const COOKIE = loginRes.headers.getSetCookie()[0].split(';')[0];

const get = async (p, { signedIn = true } = {}) => {
  const res = await fetch(base + p, signedIn ? { headers: { cookie: COOKIE } } : undefined);
  const body = await res.json();
  return { status: res.status, body };
};

// Every query-shaped route, on a database with nothing in it. The
// `relevant = 1` ambiguity bug only appeared on this exact path.
const ROUTES = [
  '/api/timeline',
  '/api/timeline?mode=relevant',
  '/api/timeline?mode=all',
  '/api/timeline?originals=1',
  '/api/timeline?collapse=1',
  '/api/timeline?sources=known',
  '/api/timeline?sources=curated',
  '/api/timeline?collapse=1&mode=all&angle=models',
  '/api/timeline?mode=relevant&originals=1&angle=models&lang=en&q=ai',
  '/api/timeline?domain=reuters.com&before=' + Date.now(),
  '/api/filters',
  '/api/cluster?id=1',
];

/** Analytics: same shape, but 401 for anyone who is not staff. */
const STAFF_ROUTES = ['/api/stats', '/api/domains?min=1', '/api/rules', '/api/translate'];

test('every API route answers cleanly on an empty database', async () => {
  for (const r of [...ROUTES, ...STAFF_ROUTES]) {
    const { status, body } = await get(r);
    assert.equal(status, 200, `${r} -> ${status} ${JSON.stringify(body)}`);
    assert.equal(body.error, undefined, `${r} returned an error: ${body.error}`);
  }
});

test('every API route answers cleanly with data present', async () => {
  const xml = readFileSync(join(HERE, 'fixtures', 'google-news-rss.xml'), 'utf8');
  ingestFeed(xml, buildShards()[0], Date.now());
  for (const r of [...ROUTES, ...STAFF_ROUTES]) {
    const { status, body } = await get(r);
    assert.equal(status, 200, `${r} -> ${status}`);
    assert.equal(body.error, undefined, `${r} returned an error: ${body.error}`);
  }
  const { body } = await get('/api/timeline?mode=relevant');
  assert.ok(body.items.length > 0, 'relevant filter must still return rows');
  assert.ok(body.items.every((i) => i.relevant === 1));
});

test('filters actually filter', async () => {
  const all = (await get('/api/timeline?mode=all')).body.items;
  const originals = (await get('/api/timeline?originals=1&mode=all')).body.items;
  assert.ok(originals.length < all.length, 'the Yahoo reprint is excluded');
  assert.ok(originals.every((i) => i.is_original === 1));

  const byDomain = (await get('/api/timeline?mode=all&domain=reuters.com')).body.items;
  assert.ok(byDomain.length && byDomain.every((i) => i.domain === 'reuters.com'));

  const search = (await get('/api/timeline?mode=all&q=' + encodeURIComponent('GPT-5.5'))).body.items;
  assert.ok(search.length && search.every((i) => i.title.includes('GPT-5.5')));
});

test('collapse shows one row per story, expandable to its reprints', async () => {
  const all = (await get('/api/timeline?mode=all')).body.items;
  const rolled = (await get('/api/timeline?mode=all&collapse=1')).body.items;
  assert.ok(rolled.length < all.length, 'the Yahoo reprint is folded away');

  const story = rolled.find((i) => i.cluster_size > 1);
  assert.ok(story, 'the clustered story survives collapsing');
  assert.equal(story.is_original, 1, 'the row kept is the first publisher');
  assert.equal(story.domain, 'reuters.com');

  const members = (await get('/api/cluster?id=' + story.cluster_id)).body.items;
  assert.equal(members.length, story.cluster_size);
  assert.ok(members.some((m) => m.domain === 'yahoo.com'), 'the reprint is still reachable');
});

test('source filter uses the curated seed list', async () => {
  const all = (await get('/api/timeline?mode=all')).body.items;
  const known = (await get('/api/timeline?mode=all&sources=known')).body.items;
  assert.ok(known.length < all.length, 'relay/unlisted domains are excluded');
  assert.ok(known.every((i) => ['primary', 'wire'].includes(i.seed_type)));
  assert.ok(known.some((i) => i.domain === 'reuters.com'));
  assert.ok(!known.some((i) => i.domain === 'yahoo.com'), 'yahoo is a relay');
});

test('static assets are not cached, so the UI never lags the code', async () => {
  const res = await fetch(base + '/app.js');
  assert.equal(res.status, 200);
  assert.match(res.headers.get('cache-control') || '', /no-store/);
});

test('static assets are served and path traversal is refused', async () => {
  const home = await fetch(base + '/');
  assert.equal(home.status, 200);
  const html = await home.text();
  assert.match(html, /inews\.today/, 'the shell renders');
  // The design system is vendored unmodified and layered, per its reuse guide.
  assert.match(html, /sd-ui-kit\.css/);
  assert.match(html, /class="sd"/);
  const escape = await fetch(base + '/../package.json');
  assert.ok(escape.status === 404 || escape.status === 403);
});

test('the public timeline stays public, analytics do not', async () => {
  const open = await get('/api/timeline', { signedIn: false });
  assert.equal(open.status, 200, '登出状态下时间线必须照常可读');
  assert.ok(Array.isArray(open.body.items));
  assert.equal((await get('/api/filters', { signedIn: false })).status, 200);

  for (const r of STAFF_ROUTES) {
    const { status, body } = await get(r, { signedIn: false });
    assert.equal(status, 401, `${r} 未登录时必须 401，实际 ${status}`);
    assert.ok(body.error, `${r} 应当带上错误文案`);
  }
  // Pinning a lane is a write, and writes were never public.
  const pin = await fetch(base + '/api/pin?shard=models.frontier%230&lane=hot', { method: 'POST' });
  assert.equal(pin.status, 401);
});

test('search matches the Chinese rendering as well as the source headline', async () => {
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  const row = db.prepare("SELECT id, title FROM articles WHERE title LIKE '%GPT-5.5%' LIMIT 1").get();
  db.prepare('UPDATE articles SET title_zh = ? WHERE id = ?').run('OpenAI 发布 GPT-5.5', row.id);

  const zh = (await get('/api/timeline?mode=all&q=' + encodeURIComponent('发布'))).body.items;
  assert.ok(zh.some((i) => i.id === row.id), '搜中文要能命中译文');
  const en = (await get('/api/timeline?mode=all&q=' + encodeURIComponent('GPT-5.5'))).body.items;
  assert.ok(en.some((i) => i.id === row.id), '搜原文同样要命中');
  assert.equal(zh.find((i) => i.id === row.id).title_zh, 'OpenAI 发布 GPT-5.5');
});
