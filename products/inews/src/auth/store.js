// Account store: users, one-time codes, sessions, rate limits, audit log.
// Security rules align with infra/docs/identity-architecture.md.

import { getDb } from '../lib/db.js';
import { AUTH_SCHEMA } from './schema.js';
import { envNumber, envValue } from '../lib/env.js';
import {
  hashPassword, verifyPassword, needsRehash,
  randomToken, hashToken, numericCode, csrfToken, csrfValid,
} from './crypto.js';

export const ROLES = ['user', 'staff', 'admin'];
/** Everything behind the 管理 menu — analytics included — needs one of these. */
export const STAFF_ROLES = new Set(['staff', 'admin']);

const SESSION_TTL_MS = envNumber('INEWS_SESSION_TTL_MS', {
  legacy: 'ST_SESSION_TTL_MS', fallback: 7 * 864e5,
});
const CODE_TTL_MS = 10 * 60_000;         // one-time codes live 10 minutes
const CODE_MAX_ATTEMPTS = 5;
const LOGIN_WINDOW_MS = 15 * 60_000;     // 5 failures per 15 minutes
const LOGIN_MAX_FAILS = 5;
const CODE_WINDOW_MS = 60 * 60_000;      // 5 codes per hour per address
const CODE_MAX_PER_WINDOW = 5;

let ready = false;
export function db() {
  const d = getDb();
  if (!ready) {
    d.exec(AUTH_SCHEMA);
    d.exec(`CREATE TABLE IF NOT EXISTS app_settings (k TEXT PRIMARY KEY, v TEXT NOT NULL)`);
    // CREATE TABLE IF NOT EXISTS does nothing to a table that already exists,
    // so a column added later never reaches a live database without this.
    // Silent absence is the worst shape: every read of the new column comes
    // back undefined and the feature just quietly does not work.
    const columns = new Set(d.prepare('PRAGMA table_info(users)').all().map((c) => c.name));
    if (!columns.has('username')) {
      d.exec('ALTER TABLE users ADD COLUMN username TEXT');
    }
    // Keep this outside the ALTER branch. A prior interrupted migration may
    // have created the column but not its uniqueness guarantee.
    d.exec('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)');
    ready = true;
  }
  return d;
}
/**
 * HMAC key for CSRF tokens. Persisted rather than per-process: a restart would
 * otherwise invalidate every open tab's token while its session cookie stays
 * valid, which reads as a random "请求被拒绝" to the user.
 */
export function secret() {
  const d = db();
  const row = d.prepare('SELECT v FROM app_settings WHERE k = ?').get('csrf_secret');
  if (row) return row.v;
  const v = envValue('INEWS_CSRF_SECRET', { legacy: 'ST_SECRET' }) || randomToken(32);
  d.prepare('INSERT OR REPLACE INTO app_settings(k, v) VALUES (?,?)').run('csrf_secret', v);
  return v;
}

export const normalizeEmail = (e) => String(e || '').trim().toLowerCase();

const EMAIL_SHAPE = /^[^\s<>@,;:"\\[\]]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$/i;

export function assertEmail(value) {
  const email = normalizeEmail(value);
  if (!EMAIL_SHAPE.test(email) || email.length > 254) throw new Error('邮箱格式不正确');
  return email;
}

/** 用户名统一小写：登录时敲 Admin 和 admin 必须是同一个账号。 */
export const normalizeUsername = (u) => String(u || '').trim().toLowerCase();

const USERNAME_SHAPE = /^[a-z0-9][a-z0-9._-]{2,31}$/;

/**
 * 校验一个用户名。**不许含 `@`** —— 登录时靠有没有 `@` 分辨这是邮箱还是
 * 用户名,一个带 `@` 的用户名会让那条岔路永远走不到。
 */
export function assertUsername(name) {
  const u = normalizeUsername(name);
  if (u.includes('@')) throw new Error('用户名不能包含 @，那是邮箱的形状');
  if (u.length < 3) throw new Error('用户名至少 3 个字符');
  if (!USERNAME_SHAPE.test(u)) {
    throw new Error('用户名只能用小写字母、数字和 . _ -，且以字母或数字开头');
  }
  return u;
}

/* ---------------- audit ---------------- */

export function audit({ actor, action, target = null, detail = null, ip = null }) {
  db().prepare(`INSERT INTO audit_log(at, actor_id, actor_email, action, target, detail, ip)
                VALUES (?,?,?,?,?,?,?)`)
    .run(Date.now(), actor?.id ?? null, actor?.email ?? null, action, target,
         detail == null ? null : String(detail), ip);
}

/* ---------------- rate limiting ---------------- */

function hits(bucket, windowMs) {
  return db().prepare('SELECT COUNT(*) n FROM rate_events WHERE bucket = ? AND at > ?')
    .get(bucket, Date.now() - windowMs).n;
}

function mark(bucket) {
  const d = db();
  d.prepare('INSERT INTO rate_events(bucket, at) VALUES (?,?)').run(bucket, Date.now());
  // Cheap opportunistic GC: rate_events is write-heavy and read-narrow, so
  // trimming here keeps it from growing without a separate sweeper.
  if (Math.random() < 0.02) {
    d.prepare('DELETE FROM rate_events WHERE at < ?').run(Date.now() - 24 * 3600_000);
  }
}

export const clearRate = (bucket) =>
  db().prepare('DELETE FROM rate_events WHERE bucket = ?').run(bucket);

/**
 * Exponential lockout. 5 failures buys 15 minutes; each further failure
 * doubles it, capped at an hour so a locked-out account is never permanently
 * locked by an attacker who knows the address.
 */
export function loginLock(identity, ip) {
  const bucket = `login:${identity}|${ip}`;
  const n = hits(bucket, LOGIN_WINDOW_MS);
  if (n < LOGIN_MAX_FAILS) return null;
  const minutes = Math.min(60, 15 * 2 ** (n - LOGIN_MAX_FAILS));
  return { bucket, minutes, fails: n };
}

export const markLoginFailure = (identity, ip) => mark(`login:${identity}|${ip}`);

export function codeThrottled(email) {
  const bucket = `code:${email}`;
  if (hits(bucket, CODE_WINDOW_MS) >= CODE_MAX_PER_WINDOW) return true;
  mark(bucket);
  return false;
}

/* ---------------- users ---------------- */

/**
 * 按**登录名**找人：带 `@` 的当邮箱，不带的当用户名。
 *
 * 分辨靠 `@` 而不是「先查邮箱、查不到再查用户名」：后者会多打一次库，而且
 * 让「这个邮箱不存在」变成一次可观测的时间差。
 */
export const findUser = (identifier) => {
  const raw = String(identifier || '').trim();
  if (raw.includes('@')) {
    return db().prepare('SELECT * FROM users WHERE email = ?').get(normalizeEmail(raw));
  }
  const u = normalizeUsername(raw);
  if (!u) return undefined;
  return db().prepare('SELECT * FROM users WHERE username = ?').get(u);
};

/** Administrative/bootstrap paths must never reinterpret a bare value as a username. */
export const findUserByEmail = (email) =>
  db().prepare('SELECT * FROM users WHERE email = ?').get(normalizeEmail(email));

export const userById = (id) => db().prepare('SELECT * FROM users WHERE id = ?').get(id);

/** The shape handed to the browser — never includes pw_hash. */
export const publicUser = (u) => u && {
  id: u.id, email: u.email, username: u.username || null,
  nickname: u.nickname || u.username || u.email.split('@')[0],
  phone: u.phone || null, role: u.role, status: u.status,
  sub_status: u.sub_status, sub_until: u.sub_until,
  created_at: u.created_at, last_login: u.last_login,
  is_staff: STAFF_ROLES.has(u.role),
};

export async function createUser({ email, password, nickname = null, phone = null, role = 'user' }) {
  const e = assertEmail(email);
  const pw_hash = await hashPassword(password);
  const info = db().prepare(`INSERT INTO users(email, phone, nickname, pw_hash, role, created_at)
                             VALUES (?,?,?,?,?,?)`)
    .run(e, phone, nickname, pw_hash, ROLES.includes(role) ? role : 'user', Date.now());
  return userById(Number(info.lastInsertRowid));
}

/**
 * 设置(或清空)一个账号的用户名。空串表示清空 —— **设错了要能退回去**，
 * 否则一个手滑的用户名会永久占着这个账号。
 */
export function setUsername(userId, name) {
  if (!String(name || '').trim()) {
    db().prepare('UPDATE users SET username = NULL WHERE id = ?').run(userId);
    return null;
  }
  const u = assertUsername(name);
  const taken = db().prepare('SELECT id FROM users WHERE username = ? AND id <> ?').get(u, userId);
  if (taken) throw new Error('这个用户名已被占用');
  db().prepare('UPDATE users SET username = ? WHERE id = ?').run(u, userId);
  return u;
}

export async function setPassword(userId, password) {
  db().prepare('UPDATE users SET pw_hash = ? WHERE id = ?').run(await hashPassword(password), userId);
}

/**
 * Verify a password, transparently upgrading a hash made with older parameters.
 * Upgrade on login — that is the only moment the plaintext is
 * available to re-derive with the current iteration count.
 */
export async function checkPassword(user, password) {
  if (!user) {
    // Spend the time anyway. Returning instantly for unknown addresses turns
    // login timing into an account-existence oracle.
    await verifyPassword(password, 'pbkdf2$600000$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=');
    return false;
  }
  const ok = await verifyPassword(password, user.pw_hash);
  if (ok && needsRehash(user.pw_hash)) await setPassword(user.id, password);
  return ok;
}

/* ---------------- one-time codes ---------------- */

export function issueCode(email, purpose) {
  const code = numericCode(6);
  const now = Date.now();
  const d = db();
  const normalized = normalizeEmail(email);
  // Code requests intentionally create the same SQLite work for existing and
  // missing accounts. Remove expired dummy/real rows on the same bounded path
  // so that privacy does not turn the shared application database into an
  // append-only mailbox log.
  d.prepare('DELETE FROM codes WHERE expires_at < ?').run(now);
  // Exactly one live code per address/purpose. `created_at` has millisecond
  // precision, so two issues in one tick cannot be ordered reliably by time
  // alone; explicitly retiring the previous code also matches what users see.
  d.prepare(`UPDATE codes SET used_at = ?
             WHERE email = ? AND purpose = ? AND used_at IS NULL`)
    .run(now, normalized, purpose);
  d.prepare(`INSERT INTO codes(email, purpose, code_hash, created_at, expires_at)
             VALUES (?,?,?,?,?)`)
    .run(normalized, purpose, hashToken(code), now, now + CODE_TTL_MS);
  return { code, expiresAt: now + CODE_TTL_MS };
}

/** @returns {{ok:true} | {ok:false, reason:'expired'|'mismatch'|'attempts'}} */
export function consumeCode(email, purpose, code) {
  const d = db();
  const row = d.prepare(`SELECT * FROM codes WHERE email = ? AND purpose = ? AND used_at IS NULL
                         ORDER BY created_at DESC, id DESC LIMIT 1`)
    .get(normalizeEmail(email), purpose);
  if (!row) return { ok: false, reason: 'expired' };
  if (row.expires_at < Date.now()) return { ok: false, reason: 'expired' };
  if (row.attempts >= CODE_MAX_ATTEMPTS) return { ok: false, reason: 'attempts' };
  if (row.code_hash !== hashToken(String(code || '').trim())) {
    d.prepare('UPDATE codes SET attempts = attempts + 1 WHERE id = ?').run(row.id);
    return { ok: false, reason: 'mismatch' };
  }
  d.prepare('UPDATE codes SET used_at = ? WHERE id = ?').run(Date.now(), row.id);
  return { ok: true };
}

/* ---------------- sessions ---------------- */

export function createSession(userId, { ip = null, ua = null } = {}) {
  const token = randomToken(32);
  const now = Date.now();
  db().prepare(`INSERT INTO sessions(id, user_id, created_at, last_seen, expires_at, ip, ua)
                VALUES (?,?,?,?,?,?,?)`)
    .run(hashToken(token), userId, now, now, now + SESSION_TTL_MS, ip, ua ? String(ua).slice(0, 300) : null);
  db().prepare('UPDATE users SET last_login = ? WHERE id = ?').run(now, userId);
  return { token, expiresAt: now + SESSION_TTL_MS };
}

/** Resolve a raw cookie token to a live user, sliding the expiry forward. */
export function sessionUser(token) {
  if (!token) return null;
  const d = db();
  const id = hashToken(token);
  const s = d.prepare('SELECT * FROM sessions WHERE id = ?').get(id);
  if (!s) return null;
  if (s.expires_at < Date.now()) { d.prepare('DELETE FROM sessions WHERE id = ?').run(id); return null; }
  const u = userById(s.user_id);
  if (!u || u.status !== 'active') return null;
  const now = Date.now();
  // Sliding window, but only written once a minute: every request otherwise
  // costs a write to a WAL that the collector is also using.
  if (now - s.last_seen > 60_000) {
    d.prepare('UPDATE sessions SET last_seen = ?, expires_at = ? WHERE id = ?')
      .run(now, now + SESSION_TTL_MS, id);
  }
  return { user: u, sessionId: id };
}

export const destroySession = (token) =>
  token && db().prepare('DELETE FROM sessions WHERE id = ?').run(hashToken(token));

/** Used after a password change: other sessions must not survive it. */
export const destroyUserSessions = (userId, exceptId = null) =>
  db().prepare('DELETE FROM sessions WHERE user_id = ? AND id IS NOT ?').run(userId, exceptId);

export const csrfFor = (sessionId) => csrfToken(sessionId, secret());
export const csrfOk = (token, sessionId) => csrfValid(token, sessionId, secret());

/* ---------------- bootstrap ---------------- */

/**
 * Make sure someone can get in. ADMIN_EMAIL/ADMIN_PASSWORD create or promote an
 * administrator at boot; without them an empty install just says how to make one,
 * because silently minting a default account with a known password is worse than
 * an unusable admin menu.
 */
export async function ensureAdmin() {
  const d = db();
  const configuredEmail = String(process.env.ADMIN_EMAIL || '').trim();
  const password = process.env.ADMIN_PASSWORD || '';
  if (configuredEmail || password) {
    if (!configuredEmail || !password) {
      throw new Error('ADMIN_EMAIL 与 ADMIN_PASSWORD 必须同时设置');
    }
    const email = assertEmail(configuredEmail);
    if (password.length < 12) {
      throw new Error('ADMIN_PASSWORD 必须至少 12 位；未创建或修改管理员');
    }
    const existing = findUserByEmail(email);
    if (!existing) {
      await createUser({ email, password, role: 'admin', nickname: '管理员' });
      audit({ actor: { email }, action: 'admin.bootstrap', target: email, detail: 'created from env' });
      return { created: email };
    }
    if (existing.role !== 'admin') {
      d.prepare('UPDATE users SET role = ? WHERE id = ?').run('admin', existing.id);
      audit({ actor: { email }, action: 'admin.bootstrap', target: email, detail: 'promoted from env' });
      return { promoted: email };
    }
    return { existing: email };
  }
  const admins = d.prepare("SELECT COUNT(*) n FROM users WHERE role = 'admin'").get().n;
  return admins ? { existing: null } : { none: true };
}
