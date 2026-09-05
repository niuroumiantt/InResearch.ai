// 登录系统的端到端检查：会话、限流、验证码、权限边界、CSRF。
import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { pbkdf2Sync } from 'node:crypto';
import { connect } from 'node:net';

const HERE = dirname(fileURLToPath(import.meta.url));
const DB = join(HERE, 'tmp-auth.sqlite3');
for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true });
process.env.INEWS_DB_PATH = DB;
process.env.INEWS_REGISTRATION_OPEN = '1';
// This suite exercises protocol semantics, not overload thresholds. The gate
// itself has deterministic unit tests in auth-gate.test.js.
process.env.INEWS_AUTH_PUBLIC_IP_LIMIT = '1000';
process.env.INEWS_AUTH_PUBLIC_GLOBAL_LIMIT = '5000';
process.env.INEWS_AUTH_LOGIN_IP_LIMIT = '1000';
process.env.INEWS_AUTH_LOGIN_GLOBAL_LIMIT = '5000';
process.env.INEWS_AUTH_CODE_IP_LIMIT = '1000';
process.env.INEWS_AUTH_CODE_GLOBAL_LIMIT = '5000';
process.env.INEWS_AUTH_PASSWORD_IP_LIMIT = '1000';
process.env.INEWS_AUTH_PASSWORD_GLOBAL_LIMIT = '5000';

const { createServer } = await import('../src/server.js');
const store = await import('../src/auth/store.js');
const { verifyPassword } = await import('../src/auth/crypto.js');

const server = createServer();
await new Promise((r) => server.listen(0, r));
const base = `http://127.0.0.1:${server.address().port}`;
after(() => { server.close(); for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true }); });

async function call(path, { method = 'GET', body, cookie, csrf } = {}) {
  const res = await fetch(base + path, {
    method,
    headers: {
      ...(body ? { 'content-type': 'application/json' } : {}),
      ...(cookie ? { cookie } : {}),
      ...(csrf ? { 'x-csrf-token': csrf } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: res.status, body: await res.json().catch(() => ({})), res };
}

const cookieOf = (res) => res.headers.getSetCookie()[0].split(';')[0];

const ADMIN = { email: 'boss@example.com', password: 'a-long-enough-secret' };
await store.createUser({ ...ADMIN, role: 'admin', nickname: '老板' });

test('登录成功后 /me 认得出这个会话', async () => {
  const login = await call('/api/auth/login', { method: 'POST', body: ADMIN });
  assert.equal(login.status, 200);
  assert.equal(login.body.user.role, 'admin');
  assert.ok(login.body.csrf, 'CSRF 令牌要随登录一起发下来');

  const cookie = cookieOf(login.res);
  const me = await call('/api/auth/me', { cookie });
  assert.equal(me.body.user.email, ADMIN.email);
  assert.equal(me.body.user.is_staff, true);

  const denied = await call('/api/auth/verify');
  assert.equal(denied.status, 401, 'Caddy must not serve private raw articles anonymously');
  const verified = await call('/api/auth/verify', { cookie });
  assert.equal(verified.status, 200);
  assert.equal(verified.body.user.email, ADMIN.email);

  const sessionToken = cookie.split('=', 2)[1];
  const legacyFallback = await call('/api/auth/me', {
    cookie: `inews_session=invalid; sd_session=${sessionToken}`,
  });
  assert.equal(legacyFallback.body.user.email, ADMIN.email,
    'invalid canonical cookie must not hide a still-valid legacy session');

  const anon = await call('/api/auth/me');
  assert.equal(anon.body.user, null);
});

test('HTTP 请求头和请求体不能慢占连接五分钟', () => {
  assert.equal(server.requestTimeout, 15_000);
  assert.equal(server.headersTimeout, 10_000);
});

test('未发送完的登录 body 不占 PBKDF2 并发槽', async () => {
  const sockets = [];
  try {
    await Promise.all(Array.from({ length: 4 }, () => new Promise((resolve, reject) => {
      const socket = connect(server.address().port, '127.0.0.1');
      sockets.push(socket);
      socket.once('error', reject);
      socket.once('connect', () => {
        socket.write(
          'POST /api/auth/login HTTP/1.1\r\n'
          + 'Host: 127.0.0.1\r\n'
          + 'Content-Type: application/json\r\n'
          + 'Content-Length: 100\r\n'
          + 'Connection: keep-alive\r\n\r\n{'
        );
        resolve();
      });
    })));
    await new Promise((resolve) => setTimeout(resolve, 20));
    const complete = await call('/api/auth/login', {
      method: 'POST',
      body: { identifier: 'slow-body-probe', password: 'wrong-password-x' },
    });
    assert.equal(complete.status, 401, '慢 body 只能占连接，不能把完整登录误挡成 429');
  } finally {
    for (const socket of sockets) socket.destroy();
  }
});

test('密码校验拒绝截短的 PBKDF2 key', async () => {
  const salt = Buffer.alloc(16, 7);
  const key = pbkdf2Sync('known-password', salt, 1000, 1, 'sha256');
  const weakened = `pbkdf2$1000$${salt.toString('base64')}$${key.toString('base64')}`;
  assert.equal(await verifyPassword('known-password', weakened), false);
});

test('密码校验仍接受完整的 legacy ASCII-hex salt', async () => {
  const password = 'migrated-known-password';
  const salt = Buffer.from('0123456789abcdef0123456789abcdef');
  const key = pbkdf2Sync(password, salt, 600_000, 32, 'sha256');
  const migrated = `pbkdf2$600000$${salt.toString('base64')}$${key.toString('base64')}`;
  assert.equal(await verifyPassword(password, migrated), true);
});

test('启动 bootstrap 拒绝短管理员密码', async () => {
  process.env.ADMIN_EMAIL = 'bootstrap@example.com';
  process.env.ADMIN_PASSWORD = 'too-short';
  try {
    await assert.rejects(store.ensureAdmin(), /至少 12 位/);
    assert.equal(store.findUser('bootstrap@example.com'), undefined);
  } finally {
    delete process.env.ADMIN_EMAIL;
    delete process.env.ADMIN_PASSWORD;
  }
});

test('管理员 bootstrap 只接受邮箱，不能把同名用户名提权', async () => {
  const ordinary = await store.createUser({
    email: 'bootstrap-user@example.com', password: 'a-long-enough-secret',
  });
  store.setUsername(ordinary.id, 'bootstrap-admin');
  process.env.ADMIN_EMAIL = 'bootstrap-admin';
  process.env.ADMIN_PASSWORD = 'a-valid-bootstrap-password';
  try {
    await assert.rejects(store.ensureAdmin(), /邮箱格式不正确/);
    assert.equal(store.userById(ordinary.id).role, 'user');
    assert.equal(store.findUserByEmail('bootstrap-admin'), undefined);
  } finally {
    delete process.env.ADMIN_EMAIL;
    delete process.env.ADMIN_PASSWORD;
  }
});

test('账号邮箱遵守与 SMTP 找回相同的地址合同', () => {
  assert.equal(store.assertEmail('USER@Example.com'), 'user@example.com');
  for (const address of [
    'u@example..com', 'u@-example.com', 'u@exa_mple.com',
    'bad,name@example.com', 'u@example.com\nBcc:evil@example.com',
  ]) {
    assert.throws(() => store.assertEmail(address), /邮箱格式不正确/);
  }
});

test('会话 cookie 是 HttpOnly 的，密码哈希永远不出服务端', async () => {
  const login = await call('/api/auth/login', { method: 'POST', body: ADMIN });
  const raw = login.res.headers.getSetCookie()[0];
  assert.match(raw, /HttpOnly/);
  assert.match(raw, /SameSite=Lax/);
  assert.equal(JSON.stringify(login.body).includes('pbkdf2'), false);
});

test('密码错误、账号不存在、账号停用给出同一条回复', async () => {
  const wrong = await call('/api/auth/login', { method: 'POST', body: { ...ADMIN, password: 'wrong-password-x' } });
  const missing = await call('/api/auth/login', { method: 'POST', body: { email: 'nobody@example.com', password: 'wrong-password-x' } });
  assert.equal(wrong.status, 401);
  assert.equal(missing.status, 401);
  assert.equal(wrong.body.error, missing.body.error);
});

test('非法超长登录名不会原样写进限流表或审计表', async () => {
  const enormous = 'x'.repeat(12_000);
  const result = await call('/api/auth/login', {
    method: 'POST', body: { identifier: enormous, password: 'wrong-password-x' },
  });
  assert.equal(result.status, 401);
  const longestBucket = store.db().prepare('SELECT MAX(length(bucket)) n FROM rate_events').get().n;
  const longestTarget = store.db().prepare('SELECT MAX(length(target)) n FROM audit_log').get().n;
  assert.ok(longestBucket < 300);
  assert.ok(longestTarget < 300);
});

test('连续失败会被锁定，但锁定状态不成为账号枚举接口', async () => {
  const victim = { email: 'target@example.com', password: 'another-long-secret' };
  await store.createUser(victim);
  for (let i = 0; i < 5; i++) {
    await call('/api/auth/login', { method: 'POST', body: { ...victim, password: 'nope-nope-nope' } });
  }
  const locked = await call('/api/auth/login', { method: 'POST', body: victim });
  assert.equal(locked.status, 401, '第 6 次即便密码正确也要挡住');
  assert.equal(locked.body.error, '账号或密码不正确');

  // 计数清掉之后（等价于换一台机器、或者等过了窗口）立刻就能进。
  store.db().prepare('DELETE FROM rate_events').run();
  const ok = await call('/api/auth/login', { method: 'POST', body: victim });
  assert.equal(ok.status, 200);
});

test('普通用户看不到分析接口，管理员可以', async () => {
  const plain = { email: 'reader@example.com', password: 'reader-long-secret' };
  await store.createUser(plain);
  const cookie = cookieOf((await call('/api/auth/login', { method: 'POST', body: plain })).res);
  assert.equal((await call('/api/stats', { cookie })).status, 403);
  assert.equal((await call('/api/admin/users', { cookie })).status, 403);
  assert.equal((await call('/api/timeline', { cookie })).status, 200);

  const admin = cookieOf((await call('/api/auth/login', { method: 'POST', body: ADMIN })).res);
  assert.equal((await call('/api/stats', { cookie: admin })).status, 200);
  assert.equal((await call('/api/admin/users', { cookie: admin })).status, 200);
});

test('写操作没有 CSRF 令牌就拒绝', async () => {
  const login = await call('/api/auth/login', { method: 'POST', body: ADMIN });
  const cookie = cookieOf(login.res);
  const target = store.findUser('reader@example.com');

  const bare = await call('/api/admin/users', { method: 'POST', cookie, body: { id: target.id, role: 'staff' } });
  assert.equal(bare.status, 403, '只带 cookie 不带令牌必须被拒');

  assert.equal((await call('/api/translate', { method: 'POST', cookie })).status, 403,
    '补译会写库、调用外部额度，也必须校验 CSRF');
  assert.equal((await call('/api/auth/logout', { method: 'POST', cookie })).status, 403,
    '退出同样不能接受跨站 POST');

  const good = await call('/api/admin/users', {
    method: 'POST', cookie, csrf: login.body.csrf, body: { id: target.id, role: 'staff' },
  });
  assert.equal(good.status, 200);
  assert.equal(good.body.user.role, 'staff');
});

test('人工锁车道同样要过 CSRF', async () => {
  const login = await call('/api/auth/login', { method: 'POST', body: ADMIN });
  const cookie = cookieOf(login.res);
  const url = '/api/pin?shard=' + encodeURIComponent('models.frontier#0') + '&lane=hot';
  assert.equal((await call(url, { method: 'POST', cookie })).status, 403);
  assert.equal((await call(url, { method: 'POST', cookie, csrf: login.body.csrf })).status, 200);
});

test('最后一个管理员不能被降级', async () => {
  const login = await call('/api/auth/login', { method: 'POST', body: ADMIN });
  const cookie = cookieOf(login.res);
  const self = store.findUser(ADMIN.email);
  const r = await call('/api/admin/users', {
    method: 'POST', cookie, csrf: login.body.csrf, body: { id: self.id, role: 'user' },
  });
  assert.equal(r.status, 400);
  assert.equal(store.findUser(ADMIN.email).role, 'admin');
});

test('注册要过验证码，验证码只能用一次', async () => {
  const email = 'newbie@example.com';
  assert.equal((await call('/api/auth/register/code', { method: 'POST', body: { email } })).status, 200);
  // 验证码只存哈希，测试从明文那一侧拿不到；重新签发一个自己知道的。
  const { code } = store.issueCode(email, 'register');

  const wrong = await call('/api/auth/register', { method: 'POST', body: { email, code: '000000', password: 'brand-new-secret-1' } });
  assert.equal(wrong.status, 400);

  const ok = await call('/api/auth/register', { method: 'POST', body: { email, code, password: 'brand-new-secret-1' } });
  assert.equal(ok.status, 200);
  assert.equal(ok.body.user.role, 'user', '注册出来的账号永远是普通用户');

  const replay = await call('/api/auth/register', { method: 'POST', body: { email: 'other@example.com', code, password: 'brand-new-secret-2' } });
  assert.equal(replay.status, 400, '同一个验证码不能再用');
});

test('SMTP 故障不能拿来枚举哪些邮箱已经注册', async () => {
  const known = await store.createUser({
    email: 'mail-oracle@example.com', password: 'a-long-enough-secret',
  });
  assert.ok(known.id);
  const previousNodeEnv = process.env.NODE_ENV;
  process.env.NODE_ENV = 'production';
  try {
    const existing = await call('/api/auth/password/code', {
      method: 'POST', body: { email: known.email },
    });
    const missing = await call('/api/auth/password/code', {
      method: 'POST', body: { email: 'mail-oracle-missing@example.com' },
    });
    assert.equal(existing.status, 200);
    assert.equal(missing.status, 200);
    assert.deepEqual(existing.body, missing.body);
    assert.deepEqual(existing.body, { ok: true, sent: true, devConsole: false });
    await new Promise((resolve) => setImmediate(resolve));
  } finally {
    if (previousNodeEnv === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = previousNodeEnv;
  }
});

test('弱密码被拒：太短、或者就是邮箱名', async () => {
  const email = 'weak@example.com';
  const short = await call('/api/auth/register', { method: 'POST', body: { email, code: '000000', password: 'short' } });
  assert.match(short.body.error, /12 位/);
  const { code } = store.issueCode(email, 'register');
  const named = await call('/api/auth/register', { method: 'POST', body: { email, code, password: 'weak-weak-weak-weak' } });
  assert.match(named.body.error, /邮箱名/);
});

test('重置密码会踢掉所有旧会话', async () => {
  const user = { email: 'rotate@example.com', password: 'first-long-secret-x' };
  await store.createUser(user);
  const cookie = cookieOf((await call('/api/auth/login', { method: 'POST', body: user })).res);
  assert.equal((await call('/api/auth/me', { cookie })).body.user.email, user.email);

  const { code } = store.issueCode(user.email, 'reset');
  const reset = await call('/api/auth/password/reset', {
    method: 'POST', body: { email: user.email, code, password: 'second-long-secret-x' },
  });
  assert.equal(reset.status, 200);
  assert.equal((await call('/api/auth/me', { cookie })).body.user, null, '旧 cookie 必须失效');
  assert.equal((await call('/api/auth/login', { method: 'POST', body: user })).status, 401);
  assert.equal((await call('/api/auth/login', {
    method: 'POST', body: { email: user.email, password: 'second-long-secret-x' },
  })).status, 200);
});

test('退出登录会真的销毁服务端会话', async () => {
  const login = await call('/api/auth/login', { method: 'POST', body: ADMIN });
  const cookie = cookieOf(login.res);
  await call('/api/auth/logout', { method: 'POST', cookie, csrf: login.body.csrf });
  assert.equal((await call('/api/auth/me', { cookie })).body.user, null);
  assert.equal((await call('/api/stats', { cookie })).status, 401);
});

test('登录与权限变更都进审计流水', async () => {
  const login = await call('/api/auth/login', { method: 'POST', body: ADMIN });
  const { body } = await call('/api/admin/audit', { cookie: cookieOf(login.res) });
  const actions = body.events.map((e) => e.action);
  for (const a of ['login.ok', 'login.failed', 'login.locked', 'admin.user_update', 'password.reset']) {
    assert.ok(actions.includes(a), `审计里应当有 ${a}`);
  }
});

// ---- 整站登录（INEWS_REQUIRE_LOGIN）：这是原来 Caddy forward_auth 干的活 ----
// 用独立的 server 实例跑，免得这个开关污染上面那些「时间线公开」的断言。
test('INEWS_REQUIRE_LOGIN=1 时连时间线也要账号', async () => {
  process.env.INEWS_REQUIRE_LOGIN = '1';
  const walled = createServer();
  await new Promise((r) => walled.listen(0, r));
  const at = `http://127.0.0.1:${walled.address().port}`;
  try {
    const anon = async (p) => (await fetch(at + p)).status;
    assert.equal(await anon('/api/timeline'), 401);
    assert.equal(await anon('/api/filters'), 401);
    assert.equal(await anon('/api/cluster?id=1'), 401);
    // 登录页自己要能打开，否则就没有任何入口了。
    assert.equal(await anon('/'), 200);
    assert.equal(await anon('/app.js'), 200);
    assert.equal(await anon('/api/auth/me'), 200);
    assert.equal(await anon('/api/version'), 200);

    const me = await (await fetch(at + '/api/auth/me')).json();
    assert.equal(me.requireLogin, true, '前端要能提前知道该画登录墙还是时间线');

    // 登录之后一切照常，普通用户也能读时间线 —— 它不是管理员功能。
    // 新建一个：上面的 reader@ 在 CSRF 那个用例里已经被提成 staff 了。
    const plain = { email: 'walled@example.com', password: 'walled-long-secret' };
    await store.createUser(plain);
    const login = await fetch(at + '/api/auth/login', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify(plain),
    });
    assert.equal(login.status, 200);
    const cookie = cookieOf(login);
    const withCookie = async (p) => (await fetch(at + p, { headers: { cookie } })).status;
    assert.equal(await withCookie('/api/timeline'), 200);
    assert.equal(await withCookie('/api/filters'), 200);
    assert.equal(await withCookie('/api/stats'), 403, '整站登录不等于人人可看分析');
  } finally {
    delete process.env.INEWS_REQUIRE_LOGIN;
    walled.close();
  }
});

test('默认（不设 INEWS_REQUIRE_LOGIN）时间线保持公开', async () => {
  assert.equal((await call('/api/timeline')).status, 200);
  assert.equal((await call('/api/filters')).status, 200);
  assert.equal((await call('/api/auth/me')).body.requireLogin, false);
});

/* ---------------- 用户名登录 ---------------- */

test('设了用户名之后，用户名和邮箱都能登进来', async () => {
  const u = { email: 'named@example.com', password: 'a-long-enough-secret' };
  const user = await store.createUser(u);
  store.setUsername(user.id, 'Admin');

  const byName = await call('/api/auth/login', {
    method: 'POST', body: { identifier: 'admin', password: u.password },
  });
  assert.equal(byName.status, 200, '用户名要能登');
  assert.equal(byName.body.user.email, u.email);
  assert.equal(byName.body.user.username, 'admin', '用户名统一存小写');

  const byEmail = await call('/api/auth/login', { method: 'POST', body: u });
  assert.equal(byEmail.status, 200, '原来的邮箱登录不能被改坏');
});

test('用户名不存在和密码错了，回的是同一句话', async () => {
  // 两句不同的回话就是一个账号枚举接口：能问出「这个用户名有没有人用」。
  const missing = await call('/api/auth/login', {
    method: 'POST', body: { identifier: 'nobody-here', password: 'a-long-enough-secret' },
  });
  const wrong = await call('/api/auth/login', {
    method: 'POST', body: { identifier: 'admin', password: 'wrong-but-long-enough' },
  });
  assert.equal(missing.status, 401);
  assert.equal(wrong.status, 401);
  assert.equal(missing.body.error, wrong.body.error);
});

test('邮箱和用户名共享同一份登录失败额度', async () => {
  const credentials = {
    email: 'one-budget@example.com', password: 'a-long-enough-secret',
  };
  const user = await store.createUser(credentials);
  store.setUsername(user.id, 'one-budget');
  const identifiers = [credentials.email, 'one-budget', credentials.email, 'one-budget', credentials.email];
  for (const identifier of identifiers) {
    const failed = await call('/api/auth/login', {
      method: 'POST', body: { identifier, password: 'wrong-but-long-enough' },
    });
    assert.equal(failed.status, 401);
  }
  const blocked = await call('/api/auth/login', {
    method: 'POST', body: { identifier: 'one-budget', password: credentials.password },
  });
  assert.equal(blocked.status, 401, '切换登录别名不能重新获得五次尝试');
  assert.equal(blocked.body.error, '账号或密码不正确', '锁定不能暴露邮箱与用户名的关联');
});

test('用户名不能重复，也不能长得像邮箱', async () => {
  const other = await store.createUser({
    email: 'other@example.com', password: 'a-long-enough-secret',
  });
  assert.throws(() => store.setUsername(other.id, 'admin'), /已被占用/);
  assert.throws(() => store.setUsername(other.id, 'a@b.com'), /不能/);
  assert.throws(() => store.setUsername(other.id, 'ab'), /至少/);
  // 清空是允许的：设错了要能退回去
  store.setUsername(other.id, '');
  assert.equal(store.userById(other.id).username, null);
});

test('管理员可以给账号设用户名，普通用户不行', async () => {
  const login = await call('/api/auth/login', { method: 'POST', body: ADMIN });
  const cookie = cookieOf(login.res);
  const csrf = login.body.csrf;
  const target = store.findUser('other@example.com');

  const set = await call('/api/admin/users', {
    method: 'POST', cookie, csrf, body: { id: target.id, username: 'someone' },
  });
  assert.equal(set.status, 200);
  assert.equal(set.body.user.username, 'someone');

  const plain = { email: 'plain@example.com', password: 'a-long-enough-secret' };
  await store.createUser(plain);
  const asPlain = await call('/api/auth/login', { method: 'POST', body: plain });
  const denied = await call('/api/admin/users', {
    method: 'POST', cookie: cookieOf(asPlain.res), csrf: asPlain.body.csrf,
    body: { id: target.id, username: 'hijack' },
  });
  assert.equal(denied.status, 403);
});

test('管理员复合修改失败时全部回滚且不写假审计', async () => {
  const target = await store.createUser({
    email: 'atomic-update@example.com', password: 'a-long-enough-secret',
  });
  const login = await call('/api/auth/login', { method: 'POST', body: ADMIN });
  const beforeAudit = store.db().prepare(
    "SELECT COUNT(*) n FROM audit_log WHERE action='admin.user_update' AND target=?"
  ).get(target.email).n;
  const failed = await call('/api/admin/users', {
    method: 'POST', cookie: cookieOf(login.res), csrf: login.body.csrf,
    body: { id: target.id, role: 'staff', username: '@@bad' },
  });
  assert.equal(failed.status, 400);
  assert.equal(store.userById(target.id).role, 'user', 'role 写入必须随 username 错误回滚');
  const afterAudit = store.db().prepare(
    "SELECT COUNT(*) n FROM audit_log WHERE action='admin.user_update' AND target=?"
  ).get(target.email).n;
  assert.equal(afterAudit, beforeAudit, '失败事务不能留下成功审计');
});
