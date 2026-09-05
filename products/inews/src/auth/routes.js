// HTTP surface for accounts: login, registration, password reset, and the
// admin console's own endpoints. Mounted by server.js under /api/auth and
// /api/admin.

import {
  db, audit, findUser, userById, publicUser, createUser, setPassword, checkPassword,
  createSession, sessionUser, destroySession, destroyUserSessions,
  issueCode, consumeCode, codeThrottled, loginLock, markLoginFailure, clearRate,
  csrfFor, csrfOk, normalizeEmail, assertEmail, assertUsername, setUsername, STAFF_ROLES, ROLES,
} from './store.js';
import { sendMail, assertAddress, SmtpError } from './smtp.js';
import { isIP } from 'node:net';
import { envFlag, envNumber } from '../lib/env.js';
import { MemoryGate } from './gate.js';

const COOKIE = 'inews_session';
const LEGACY_COOKIE = 'sd_session';
const MAX_BODY = 16 * 1024;   // an account form is never larger than this
const MINUTE = 60_000;

const limit = (name, fallback) => Math.floor(envNumber(name, { fallback }));

// Layered overload protection. The outer gate covers every anonymous account
// mutation; the two narrow gates give password hashing and mail/code requests
// tighter budgets. Global ceilings remain effective when X-Forwarded-For can be
// rotated or spoofed, while concurrency ceilings prevent one burst from filling
// the libuv worker queue.
const publicAuthGate = new MemoryGate({
  windowMs: 15 * MINUTE,
  perKey: limit('INEWS_AUTH_PUBLIC_IP_LIMIT', 60),
  global: limit('INEWS_AUTH_PUBLIC_GLOBAL_LIMIT', 600),
  concurrent: limit('INEWS_AUTH_PUBLIC_CONCURRENCY', 16),
});
const loginGate = new MemoryGate({
  windowMs: 15 * MINUTE,
  perKey: limit('INEWS_AUTH_LOGIN_IP_LIMIT', 30),
  global: limit('INEWS_AUTH_LOGIN_GLOBAL_LIMIT', 300),
  concurrent: limit('INEWS_AUTH_LOGIN_CONCURRENCY', 4),
});
const codeGate = new MemoryGate({
  windowMs: 60 * MINUTE,
  perKey: limit('INEWS_AUTH_CODE_IP_LIMIT', 10),
  global: limit('INEWS_AUTH_CODE_GLOBAL_LIMIT', 200),
  concurrent: limit('INEWS_AUTH_CODE_CONCURRENCY', 8),
});
const passwordChangeGate = new MemoryGate({
  windowMs: 15 * MINUTE,
  perKey: limit('INEWS_AUTH_PASSWORD_IP_LIMIT', 10),
  global: limit('INEWS_AUTH_PASSWORD_GLOBAL_LIMIT', 100),
  concurrent: limit('INEWS_AUTH_PASSWORD_CONCURRENCY', 4),
});
const WORK_RELEASES = Symbol('authWorkReleases');
// Two workers × 15 s SMTP timeout means 40 queued jobs drain within roughly
// five minutes even in the worst case, comfortably before a 10-minute code
// expires. A larger queue would accept mail that can no longer arrive in time.
const MAIL_QUEUE_MAX = 40;
const MAIL_QUEUE_CONCURRENCY = 2;
const mailQueue = [];
let activeMailJobs = 0;

function pumpMailQueue() {
  while (activeMailJobs < MAIL_QUEUE_CONCURRENCY && mailQueue.length) {
    const job = mailQueue.shift();
    activeMailJobs += 1;
    Promise.resolve().then(job).catch((error) => {
      // Every real job records its own contextual failure. This last boundary
      // exists only to prevent a programmer error in a future job from becoming
      // an unhandled rejection that terminates the process.
      console.error('[mail:queue]', error);
    }).finally(() => {
      activeMailJobs -= 1;
      setImmediate(pumpMailQueue);
    });
  }
}
function enqueueMail(job) {
  if (mailQueue.length + activeMailJobs >= MAIL_QUEUE_MAX) return false;
  mailQueue.push(job);
  setImmediate(pumpMailQueue);
  return true;
}

/* ---------------- request plumbing ---------------- */

export function readCookie(req, name) {
  const raw = req.headers.cookie;
  if (!raw) return null;
  for (const part of raw.split(';')) {
    const i = part.indexOf('=');
    if (i < 0) continue;
    if (part.slice(0, i).trim() === name) return decodeURIComponent(part.slice(i + 1).trim());
  }
  return null;
}

/**
 * Secure is conditional: hard-coding it would silently break login on the
 * plain-HTTP local dev server, and the resulting "cookie set but never sent"
 * is invisible in the network panel.
 */
function cookieHeader(value, maxAgeSec, req, name = COOKIE) {
  const secure = envFlag('INEWS_SECURE_COOKIES', { legacy: 'ST_SECURE_COOKIES' })
    || req.headers['x-forwarded-proto'] === 'https';
  return `${name}=${value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAgeSec}`
    + (secure ? '; Secure' : '');
}

export function clientIp(req) {
  const fwd = req.headers['x-forwarded-for'];
  const forwarded = fwd ? String(fwd).split(',')[0].trim() : '';
  if (isIP(forwarded)) return forwarded;
  const direct = String(req.socket?.remoteAddress || '').trim();
  return isIP(direct) ? direct : null;
}

function acquireRequestWork(req, gates) {
  const acquired = [];
  for (const gate of gates) {
    const release = gate.acquire();
    if (!release) {
      for (const done of acquired.reverse()) done();
      throw new HttpError(429, '请求过于频繁，请稍后再试');
    }
    acquired.push(release);
  }
  req[WORK_RELEASES] = [...(req[WORK_RELEASES] || []), ...acquired];
}

async function readJson(req, { workGates = [] } = {}) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY) throw new HttpError(413, '请求体过大');
    chunks.push(chunk);
  }
  let body;
  if (!size) body = {};
  else try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { throw new HttpError(400, '请求体不是合法 JSON'); }
  // Only a fully received, size-bounded body may reserve expensive-work
  // capacity. Four slow partial login bodies must not hold all PBKDF2 slots.
  acquireRequestWork(req, workGates);
  return body;
}

export class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

/* ---------------- identity ---------------- */

/** Resolve the caller. Never throws — an anonymous request is a valid state. */
export function currentUser(req) {
  return sessionUser(readCookie(req, COOKIE)) || sessionUser(readCookie(req, LEGACY_COOKIE));
}

export function requireUser(req) {
  const ctx = currentUser(req);
  if (!ctx) throw new HttpError(401, '请先登录');
  return ctx;
}

export function requireStaff(req) {
  const ctx = requireUser(req);
  if (!STAFF_ROLES.has(ctx.user.role)) throw new HttpError(403, '需要管理员权限');
  return ctx;
}

export const requireAdmin = (req) => {
  const ctx = requireUser(req);
  if (ctx.user.role !== 'admin') throw new HttpError(403, '需要管理员权限');
  return ctx;
};

/**
 * State-changing requests carry a session-bound CSRF token. SameSite=Lax
 * already blocks the cross-site form POST, but it is one browser default away
 * from being the only thing standing there.
 */
export function requireCsrf(req, ctx) {
  const token = req.headers['x-csrf-token'];
  if (!csrfOk(token, ctx.sessionId)) throw new HttpError(403, '会话已过期，请刷新页面');
}

/* ---------------- mail ---------------- */

const SMTP_READY = () => Boolean(process.env.SMTP_HOST && process.env.MAIL_FROM);

/**
 * Deliver a one-time code. With no SMTP configured — local development — the
 * code goes to the server log instead of nowhere, so registration is testable
 * without standing up a mail server. That fallback is refused in production.
 */
async function deliverCode(email, purpose, code) {
  const subject = purpose === 'register' ? 'inews.today 注册验证码' : 'inews.today 密码重置验证码';
  const text = `验证码：${code}\n\n10 分钟内有效，请勿转发。\n若不是你本人操作，忽略本邮件即可。`;
  if (!SMTP_READY()) {
    if (process.env.NODE_ENV === 'production') throw new HttpError(503, '邮件服务未配置');
    console.log(`[mail:dev] ${email} ${purpose} 验证码 = ${code}`);
    return { delivered: 'console' };
  }
  await sendMail({
    host: process.env.SMTP_HOST,
    port: Number(process.env.SMTP_PORT || 587),
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASSWORD,
    from: process.env.MAIL_FROM,
    to: email, subject, text,
  });
  return { delivered: 'smtp' };
}

/* ---------------- validation ---------------- */

function validEmail(email) {
  const e = normalizeEmail(email);
  try { assertAddress(e, 'email'); } catch (err) {
    if (err instanceof SmtpError) throw new HttpError(400, '邮箱格式不正确');
    throw err;
  }
  return e;
}

/** 12+ characters, and rejected outright if it contains the email local part. */
function validPassword(password, email) {
  const p = String(password || '');
  if (p.length < 12) throw new HttpError(400, '密码至少 12 位');
  if (p.length > 200) throw new HttpError(400, '密码过长');
  const local = normalizeEmail(email).split('@')[0];
  if (local && local.length >= 3 && p.toLowerCase().includes(local)) {
    throw new HttpError(400, '密码不能包含邮箱名');
  }
  return p;
}

/* ---------------- handlers ---------------- */

const ok = (extra = {}) => ({ ok: true, ...extra });

/**
 * 登录名：邮箱**或**用户名。老的请求体只有 `email`，照旧收 —— 浏览器里存着
 * 的旧页面不该因为后端多认一种登录名就登不进去。
 */
function loginName(body) {
  const raw = String(body.identifier ?? body.email ?? '');
  try {
    return raw.includes('@') ? assertEmail(raw) : assertUsername(raw);
  } catch {
    // Invalid identifiers still take the dummy password-check path, but never
    // reach SQLite/audit as attacker-controlled multi-kilobyte strings.
    return null;
  }
}

async function login(req, res, send) {
  const body = await readJson(req, { workGates: [publicAuthGate, loginGate] });
  const name = loginName(body);
  const ip = clientIp(req);
  const user = name ? findUser(name) : undefined;
  // Email and username are aliases for one identity, not two independent
  // password-attempt budgets. Unknown identifiers retain their own bucket.
  const rateIdentity = user ? `user:${user.id}` : (name || '<invalid>');
  const lock = loginLock(rateIdentity, ip);
  // Always pay the password-check cost, even while locked. More importantly,
  // do not expose the account-wide lock as 429: otherwise an attacker can lock
  // a username, probe candidate emails, and learn which alias belongs to it.
  const passed = await checkPassword(user, String(body.password || ''));
  if (lock) {
    audit({ actor: name ? { email: name } : null, action: 'login.locked', target: name, ip, detail: `${lock.fails} 次失败` });
    throw new HttpError(401, '账号或密码不正确');
  }
  // One message for "no such account", "wrong password" and "disabled": each
  // distinct reply is an account-enumeration oracle. 加了用户名之后这条更要紧：
  // 一句不同的回话就能被拿来问「这个用户名有没有人用」。
  if (!passed || user.status !== 'active') {
    markLoginFailure(rateIdentity, ip);
    audit({ actor: name ? { email: name } : null, action: 'login.failed', target: name, ip });
    throw new HttpError(401, '账号或密码不正确');
  }

  clearRate(`login:${rateIdentity}|${ip}`);
  const { token, expiresAt } = createSession(user.id, { ip, ua: req.headers['user-agent'] });
  audit({ actor: user, action: 'login.ok', target: name, ip });
  res.setHeader('set-cookie', cookieHeader(token, Math.floor((expiresAt - Date.now()) / 1000), req));
  const ctx = sessionUser(token);
  send(ok({ user: publicUser(user), csrf: csrfFor(ctx.sessionId) }));
}

async function logout(req, res, send) {
  const tokens = [readCookie(req, COOKIE), readCookie(req, LEGACY_COOKIE)].filter(Boolean);
  const ctx = requireUser(req);
  requireCsrf(req, ctx);
  audit({ actor: ctx.user, action: 'logout', ip: clientIp(req) });
  for (const token of tokens) destroySession(token);
  res.setHeader('set-cookie', [
    cookieHeader('', 0, req),
    cookieHeader('', 0, req, LEGACY_COOKIE),
  ]);
  send(ok());
}

/**
 * Compatibility endpoint for deployments that still probe the current session.
 * The active /rawarticle route is served by this Node app and guarded directly by
 * requireStaff; Caddy no longer reads that private archive or performs auth for it.
 */
function verify(req, res, send) {
  const ctx = requireUser(req);
  send(ok({ user: publicUser(ctx.user) }));
}

function me(req, res, send) {
  const ctx = currentUser(req);
  // requireLogin travels with the identity so the page knows, on its very first
  // request, whether an anonymous visitor gets the timeline or a login gate.
  const site = { registrationOpen: registrationOpen(), requireLogin: requireLoginSitewide() };
  if (!ctx) return send({ user: null, ...site });
  send({ user: publicUser(ctx.user), csrf: csrfFor(ctx.sessionId), ...site });
}

/** Self-service signup is off unless asked for: this is a private desk by default. */
const registrationOpen = () => envFlag('INEWS_REGISTRATION_OPEN', { legacy: 'ST_OPEN_REGISTRATION' });

/**
 * Whole-site login. This is the job the Caddy `forward_auth` layer used to do;
 * now that authentication belongs to this app, the capability has to live here
 * or removing that layer would quietly lose it.
 *
 * Off by default — the timeline is a public news page. Turning it on makes even
 * the timeline require an account, and the page renders a login gate instead of
 * an empty stream.
 */
export const requireLoginSitewide = () => envFlag('INEWS_REQUIRE_LOGIN', { legacy: 'ST_REQUIRE_LOGIN' });

/** Guard for the otherwise-public read routes. */
export function requireReader(req) {
  return requireLoginSitewide() ? requireUser(req) : currentUser(req);
}

async function requestCode(req, res, send, purpose) {
  const body = await readJson(req, { workGates: [publicAuthGate, codeGate] });
  const email = validEmail(body.email);
  const ip = clientIp(req);
  if (purpose === 'register' && !registrationOpen()) throw new HttpError(403, '当前未开放注册');
  if (codeThrottled(email)) throw new HttpError(429, '验证码请求过于频繁，请稍后再试');

  const exists = Boolean(findUser(email));
  // Only send when it makes sense, but always answer the same way — the reply
  // must not reveal whether the address has an account.
  const shouldSend = purpose === 'register' ? !exists : exists;
  // Issue a row for both branches so response time and SQLite work do not say
  // whether this address exists. A suppressed code is never delivered and is
  // therefore unusable; the global/IP gate bounds these dummy rows.
  const { code } = issueCode(email, purpose);
  if (shouldSend) {
    const queued = enqueueMail(async () => {
      try {
        const delivered = (await deliverCode(email, purpose, code)).delivered;
        audit({ action: `code.${purpose}`, target: email, ip, detail: delivered });
      } catch (error) {
        // SMTP configuration, network state and recipient existence are server
        // concerns. Returning their result to an anonymous caller is an account
        // enumeration oracle, so failures are visible only to operators.
        audit({ action: 'code.send_failed', target: email,
                detail: String(error?.message || error), ip });
      }
    });
    if (!queued) {
      audit({ action: 'code.queue_full', target: email, ip });
    }
  }
  // Suppressed requests deliberately leave no per-request audit row: otherwise
  // rotating nonexistent addresses turns this security log into an unbounded
  // write-amplification endpoint. Actual deliveries and failures stay audited.
  // The public result is deliberately identical for exists/missing and for
  // SMTP success/failure. In local development this flag is configuration-only
  // too; it must not reveal whether a particular job was suppressed.
  const devConsole = process.env.NODE_ENV !== 'production' && !SMTP_READY();
  send(ok({ sent: true, devConsole }));
}

async function register(req, res, send) {
  if (!registrationOpen()) throw new HttpError(403, '当前未开放注册');
  const body = await readJson(req, { workGates: [publicAuthGate] });
  const email = validEmail(body.email);
  const password = validPassword(body.password, email);
  const verdict = consumeCode(email, 'register', body.code);
  if (!verdict.ok) throw new HttpError(400, verdict.reason === 'attempts' ? '验证码错误次数过多，请重新获取' : '验证码无效或已过期');
  if (findUser(email)) throw new HttpError(409, '该邮箱已注册');

  const user = await createUser({
    email, password,
    nickname: String(body.nickname || '').trim().slice(0, 40) || null,
    phone: String(body.phone || '').trim().slice(0, 40) || null,
  });
  audit({ actor: user, action: 'register', target: email, ip: clientIp(req) });
  const { token, expiresAt } = createSession(user.id, { ip: clientIp(req), ua: req.headers['user-agent'] });
  res.setHeader('set-cookie', cookieHeader(token, Math.floor((expiresAt - Date.now()) / 1000), req));
  send(ok({ user: publicUser(user), csrf: csrfFor(sessionUser(token).sessionId) }));
}

async function resetPassword(req, res, send) {
  const body = await readJson(req, { workGates: [publicAuthGate] });
  const email = validEmail(body.email);
  const password = validPassword(body.password, email);
  const verdict = consumeCode(email, 'reset', body.code);
  if (!verdict.ok) throw new HttpError(400, verdict.reason === 'attempts' ? '验证码错误次数过多，请重新获取' : '验证码无效或已过期');
  const user = findUser(email);
  if (!user) throw new HttpError(400, '验证码无效或已过期');

  await setPassword(user.id, password);
  destroyUserSessions(user.id);
  audit({ actor: user, action: 'password.reset', target: email, ip: clientIp(req) });
  send(ok());
}

async function changePassword(req, res, send) {
  const ctx = requireUser(req);
  requireCsrf(req, ctx);
  const body = await readJson(req);
  const changeKey = `user:${ctx.user.id}|${clientIp(req) || 'unknown'}`;
  if (!passwordChangeGate.hit(changeKey)) {
    throw new HttpError(429, '请求过于频繁，请稍后再试');
  }
  acquireRequestWork(req, [passwordChangeGate]);
  if (!await checkPassword(ctx.user, String(body.current || ''))) {
    throw new HttpError(401, '当前密码不正确');
  }
  await setPassword(ctx.user.id, validPassword(body.password, ctx.user.email));
  destroyUserSessions(ctx.user.id, ctx.sessionId);   // keep the tab you changed it in
  audit({ actor: ctx.user, action: 'password.change', ip: clientIp(req) });
  send(ok());
}

/* ---------------- admin console ---------------- */

function listUsers(req, res, send) {
  requireStaff(req);
  const rows = db().prepare(`SELECT * FROM users ORDER BY created_at DESC LIMIT 500`).all();
  send({ users: rows.map(publicUser) });
}

async function updateUser(req, res, send) {
  const ctx = requireAdmin(req);
  requireCsrf(req, ctx);
  const body = await readJson(req);
  const target = userById(Number(body.id));
  if (!target) throw new HttpError(404, '用户不存在');

  // The API accepts a compound patch. Role/status must not change if a later
  // username validation fails, and every security mutation needs one audit row.
  const d = db();
  d.exec('BEGIN IMMEDIATE');
  const changes = [];
  try {
    if (body.role !== undefined) {
      if (!ROLES.includes(body.role)) throw new HttpError(400, '未知角色');
      // Losing the last administrator locks everyone out of the console with no
      // in-app way back, so the demotion is refused rather than warned about.
      if (target.role === 'admin' && body.role !== 'admin' && adminCount() <= 1) {
        throw new HttpError(400, '至少要保留一个管理员');
      }
      d.prepare('UPDATE users SET role = ? WHERE id = ?').run(body.role, target.id);
      changes.push(`role→${body.role}`);
    }
    if (body.username !== undefined) {
      try {
        const set = setUsername(target.id, body.username);
        changes.push(`username→${set || '(清空)'}`);
      } catch (err) {
        // 用户名的规则是给人看的，原话直接回给前端 —— 「参数不合法」帮不上忙。
        throw new HttpError(400, err.message);
      }
    }
    if (body.status !== undefined) {
      if (!['active', 'disabled'].includes(body.status)) throw new HttpError(400, '未知状态');
      if (target.id === ctx.user.id && body.status !== 'active') throw new HttpError(400, '不能停用自己');
      d.prepare('UPDATE users SET status = ? WHERE id = ?').run(body.status, target.id);
      if (body.status !== 'active') destroyUserSessions(target.id);
      changes.push(`status→${body.status}`);
    }
    audit({ actor: ctx.user, action: 'admin.user_update', target: target.email,
            detail: changes.join(' '), ip: clientIp(req) });
    d.exec('COMMIT');
  } catch (error) {
    // DatabaseSync.isTransaction only exists from Node 22.16 onward, while the
    // package supports 22.5. BEGIN succeeded before this try, so attempt the
    // rollback directly and never let a secondary rollback error hide `error`.
    try { d.exec('ROLLBACK'); } catch { /* preserve the original mutation error */ }
    throw error;
  }
  send(ok({ user: publicUser(userById(target.id)), changes }));
}

const adminCount = () => db().prepare("SELECT COUNT(*) n FROM users WHERE role='admin' AND status='active'").get().n;

function auditLog(req, res, send) {
  requireStaff(req);
  const rows = db().prepare('SELECT * FROM audit_log ORDER BY at DESC LIMIT 200').all();
  send({ events: rows });
}

/* ---------------- router ---------------- */

const ROUTES = {
  'POST /api/auth/login': login,
  'POST /api/auth/logout': logout,
  'GET  /api/auth/me': me,
  'GET  /api/auth/verify': verify,
  'POST /api/auth/register/code': (q, r, s) => requestCode(q, r, s, 'register'),
  'POST /api/auth/register': register,
  'POST /api/auth/password/code': (q, r, s) => requestCode(q, r, s, 'reset'),
  'POST /api/auth/password/reset': resetPassword,
  'POST /api/auth/password/change': changePassword,
  'GET  /api/admin/users': listUsers,
  'POST /api/admin/users': updateUser,
  'GET  /api/admin/audit': auditLog,
};

const PUBLIC_AUTH_WRITES = new Set([
  '/api/auth/login',
  '/api/auth/register/code',
  '/api/auth/register',
  '/api/auth/password/code',
  '/api/auth/password/reset',
]);
const CODE_REQUESTS = new Set(['/api/auth/register/code', '/api/auth/password/code']);

function checkPublicAuthRates(req, pathname) {
  if (!PUBLIC_AUTH_WRITES.has(pathname)) return;
  const ip = clientIp(req) || 'unknown';
  const gates = [publicAuthGate];
  if (pathname === '/api/auth/login') gates.push(loginGate);
  if (CODE_REQUESTS.has(pathname)) gates.push(codeGate);

  for (const gate of gates) {
    if (!gate.hit(ip)) {
      throw new HttpError(429, '请求过于频繁，请稍后再试');
    }
  }
}

/**
 * @returns true when the request was an auth route and has been answered.
 */
export async function handleAuth(req, res, pathname, send) {
  if (!pathname.startsWith('/api/auth/') && !pathname.startsWith('/api/admin/')) return false;
  const method = (req.method || 'GET').toUpperCase();
  const handler = ROUTES[`${method === 'GET' ? 'GET ' : method} ${pathname}`];
  if (!handler) {
    // A known path reached with the wrong verb is a 405, not a 404: the
    // distinction is what tells a caller they have the URL right.
    const otherVerb = Object.keys(ROUTES).some((k) => k.endsWith(` ${pathname}`));
    send({ error: otherVerb ? '方法不允许' : '接口不存在' }, otherVerb ? 405 : 404);
    return true;
  }
  checkPublicAuthRates(req, pathname);
  try {
    await handler(req, res, send);
  } finally {
    for (const release of (req[WORK_RELEASES] || []).reverse()) release();
    req[WORK_RELEASES] = [];
  }
  return true;
}
