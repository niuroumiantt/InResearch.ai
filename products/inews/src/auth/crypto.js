// Password hashing, session tokens and CSRF — all on node:crypto, no deps.
// Security baseline comes from infra/docs/identity-architecture.md.

import { pbkdf2, randomBytes, timingSafeEqual, createHmac, createHash } from 'node:crypto';
import { promisify } from 'node:util';

// Async, not pbkdf2Sync: 600k iterations costs ~280ms of pure CPU, and this
// process also runs the news collector. The sync call would stall every poll,
// every request and every timer for that long on each login attempt; the async
// one runs on the libuv threadpool and leaves the event loop free.
const pbkdf2Async = promisify(pbkdf2);

export const PBKDF2_ITERATIONS = 600_000;   // current identity security baseline
const KEYLEN = 32;
const DIGEST = 'sha256';
const MAX_PBKDF2_ITERATIONS = PBKDF2_ITERATIONS * 4;

export async function hashPassword(password, iterations = PBKDF2_ITERATIONS) {
  const salt = randomBytes(16);
  const hash = await pbkdf2Async(password, salt, iterations, KEYLEN, DIGEST);
  return `pbkdf2$${iterations}$${salt.toString('base64')}$${hash.toString('base64')}`;
}

export async function verifyPassword(password, stored) {
  const parts = String(stored || '').split('$');
  if (parts.length !== 4 || parts[0] !== 'pbkdf2') return false;
  const iterations = Number(parts[1]);
  if (!Number.isInteger(iterations) || iterations < 1000 || iterations > MAX_PBKDF2_ITERATIONS) return false;
  const salt = Buffer.from(parts[2], 'base64');
  const expected = Buffer.from(parts[3], 'base64');
  // Native hashes use a 16-byte salt; the one-time legacy migration preserves
  // its 32 ASCII-hex salt bytes. Anything shorter weakens the hash, and a short
  // derived key turns password verification into only a few bits of checking.
  if (![16, 32].includes(salt.length) || expected.length !== KEYLEN) return false;
  const actual = await pbkdf2Async(password, salt, iterations, expected.length, DIGEST);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

/** True when a stored hash was made with weaker parameters and should be upgraded. */
export function needsRehash(stored) {
  const parts = String(stored || '').split('$');
  return parts.length !== 4 || Number(parts[1]) < PBKDF2_ITERATIONS;
}

export const randomToken = (bytes = 32) => randomBytes(bytes).toString('base64url');

/** Sessions are stored hashed, so a database leak does not hand over live sessions. */
export const hashToken = (token) => createHash('sha256').update(token).digest('base64url');

/** 6 digits, uniform — Math.random would bias and is not cryptographic. */
export function numericCode(digits = 6) {
  const max = 10 ** digits;
  const limit = Math.floor(0xffffffff / max) * max;   // reject to avoid modulo bias
  let n;
  do { n = randomBytes(4).readUInt32BE(0); } while (n >= limit);
  return String(n % max).padStart(digits, '0');
}

/** CSRF token bound to the session, not a bare nonce. */
export function csrfToken(sessionId, secret) {
  return createHmac('sha256', secret).update(`csrf:${sessionId}`).digest('base64url');
}

export function csrfValid(token, sessionId, secret) {
  const expected = csrfToken(sessionId, secret);
  const a = Buffer.from(String(token || ''));
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export const constantTimeEqual = (a, b) => {
  const x = Buffer.from(String(a));
  const y = Buffer.from(String(b));
  return x.length === y.length && timingSafeEqual(x, y);
};
