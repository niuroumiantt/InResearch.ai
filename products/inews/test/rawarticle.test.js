// /rawarticle/* 是统一采集器抓来的付费正文。2026-09-03 之前它由 Caddy 用运维后台
// 那组 basic_auth 挡门(auth-standard v3 §3);现在由本站自己的登录挡 —— 登录
// 是各站自己的事,infra 只反代。每条保证都有一个用例去违反它。
import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DB = join(HERE, 'tmp-rawarticle.db');
for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true });
process.env.SINGLETITLE_DB = DB;
const RAW = mkdtempSync(join(tmpdir(), 'raw-'));
process.env.RAWARTICLE_DIR = RAW;
mkdirSync(join(RAW, 'ft'));
writeFileSync(join(RAW, 'ft', 'index.html'), '<h1>FT</h1>');

const { createServer } = await import('../src/server.js');
const { createUser } = await import('../src/auth/store.js');
const server = createServer();
await new Promise((r) => server.listen(0, r));
const base = `http://127.0.0.1:${server.address().port}`;
after(() => { server.close(); rmSync(RAW, { recursive: true }); });

const login = async (email, role) => {
  await createUser({ email, password: 'suite-password-123', role });
  const r = await fetch(base + '/api/auth/login', { method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email, password: 'suite-password-123' }) });
  return { cookie: r.headers.getSetCookie()[0].split(';')[0] };
};
const get = (p, cookie) => fetch(base + p, cookie ? { headers: { cookie } } : undefined);

test('没登录:原文库 401,一个字节都不给', async () => {
  const r = await get('/rawarticle/ft/index.html');
  assert.equal(r.status, 401);
  assert.doesNotMatch(await r.text(), /FT/);
});

test('普通读者不是站长:403', async () => {
  const { cookie } = await login('reader@example.com', 'reader');
  assert.equal((await get('/rawarticle/ft/index.html', cookie)).status, 403);
});

test('staff 登录后能读,目录路径落到 index.html', async () => {
  const { cookie } = await login('admin@example.com', 'admin');
  const r = await get('/rawarticle/ft/', cookie);
  assert.equal(r.status, 200);
  assert.equal(await r.text(), '<h1>FT</h1>');
});

test('原文库根目录之外拿不到(路径穿越)', async () => {
  const { cookie } = await login('admin2@example.com', 'admin');
  const r = await get('/rawarticle/%2e%2e/%2e%2e/package.json', cookie);
  assert.notEqual(r.status, 200);
});
