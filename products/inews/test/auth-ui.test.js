import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { assertSessionPayload, post } from '../web/auth.js';

const realFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = realFetch;
});

test('API calls forbid redirects before a credential-bearing body can be followed', async () => {
  let options;
  globalThis.fetch = async (_url, init) => {
    options = init;
    throw new TypeError('fetch failed');
  };

  await assert.rejects(
    post('/api/auth/login', { identifier: 'probe-invalid', password: 'not-a-real-password' }),
    /重定向或网络中断/,
  );
  assert.equal(options.redirect, 'error');
});

test('an already-followed API redirect is still rejected as defence in depth', async () => {
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    redirected: true,
    url: 'https://inews.today/account/login?next=/api/auth/login',
    headers: new Headers({ 'content-type': 'application/json; charset=utf-8' }),
    json: async () => ({ ok: true }),
  });

  await assert.rejects(
    post('/api/auth/login', { identifier: 'probe-invalid', password: 'not-a-real-password' }),
    /登录状态已失效/,
  );
});

test('an HTML response without redirect metadata is still rejected', async () => {
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    redirected: false,
    headers: new Headers({ 'content-type': 'text/html; charset=utf-8' }),
    json: async () => ({}),
  });

  await assert.rejects(
    post('/api/auth/login', { identifier: 'probe-invalid', password: 'not-a-real-password' }),
    /非 API 响应/,
  );
});

test('malformed JSON cannot become an empty successful response', async () => {
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    redirected: false,
    headers: new Headers({ 'content-type': 'application/json; charset=utf-8' }),
    json: async () => { throw new SyntaxError('Unexpected end of JSON input'); },
  });

  await assert.rejects(
    post('/api/auth/login', { identifier: 'probe-invalid', password: 'not-a-real-password' }),
    /无效的 API 响应/,
  );
});

test('well-formed non-object JSON is still not a valid API response', async () => {
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    redirected: false,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => null,
  });

  await assert.rejects(
    post('/api/auth/login', { identifier: 'probe-invalid', password: 'not-a-real-password' }),
    /无效的 API 响应/,
  );
});

test('a nominal JSON success without a native session cannot close login', () => {
  assert.throws(
    () => assertSessionPayload({}),
    /登录响应不完整/,
  );
  assert.throws(
    () => assertSessionPayload({ user: { id: 1 }, csrf: '' }),
    /登录响应不完整/,
  );
  const payload = {
    user: {
      id: 1,
      email: 'admin@example.com',
      nickname: '管理员',
      role: 'admin',
      is_staff: true,
    },
    csrf: 'session-bound-token',
  };
  assert.deepEqual(
    assertSessionPayload(payload),
    payload,
  );
});
