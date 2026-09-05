// Minimal SMTP client for AWS SES, on node:net + node:tls.
//
// Written rather than pulled from npm on purpose: this project has zero
// dependencies, which is what lets the container build with no `npm install`
// step and no node_modules layer. One outbound mail path is a small, bounded
// protocol — EHLO, STARTTLS, AUTH LOGIN, MAIL/RCPT/DATA — and worth owning.
//
// Config per infra/docs/identity-architecture.md: SMTP_HOST / SMTP_PORT / SMTP_USER
// / SMTP_PASSWORD / MAIL_FROM.

import net from 'node:net';
import tls from 'node:tls';

const CRLF = '\r\n';

export class SmtpError extends Error {
  constructor(message, code) { super(message); this.name = 'SmtpError'; this.code = code; }
}

/** Reads SMTP replies, handling multi-line continuations (`250-` vs `250 `). */
function createReader(socket) {
  let buffer = '';
  const waiters = [];
  socket.setEncoding('utf8');
  socket.on('data', (chunk) => {
    buffer += chunk;
    for (;;) {
      // A reply ends at the first line whose 4th character is a space.
      const match = buffer.match(/^(?:\d{3}-[^\r\n]*\r?\n)*(\d{3}) [^\r\n]*\r?\n/);
      if (!match) return;
      const raw = match[0];
      buffer = buffer.slice(raw.length);
      const waiter = waiters.shift();
      if (waiter) waiter.resolve({ code: Number(match[1]), text: raw.trim() });
    }
  });
  const fail = (err) => { while (waiters.length) waiters.shift().reject(err); };
  socket.on('error', fail);
  socket.on('close', () => fail(new SmtpError('connection closed by server')));
  return () => new Promise((resolve, reject) => waiters.push({ resolve, reject }));
}

async function expect(read, ...okCodes) {
  const reply = await read();
  if (!okCodes.includes(reply.code)) {
    throw new SmtpError(`unexpected reply: ${reply.text}`, reply.code);
  }
  return reply;
}

const send = (socket, line) => new Promise((res, rej) =>
  socket.write(line + CRLF, (e) => (e ? rej(e) : res())));

/** RFC 5322 headers must not carry raw newlines — that is header injection. */
function sanitizeHeader(value) {
  return String(value).replace(/[\r\n]+/g, ' ').trim();
}

// Addresses are rejected, not scrubbed. Flattening "a@b.c\r\nBcc: evil@x" into
// one line stops the injection but still ships a malformed header carrying the
// attacker's text; refusing is both safer and easier to reason about.
const ADDRESS = /^[^\s<>@,;:"\\[\]]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/;

export function assertAddress(value, field) {
  const v = String(value ?? '');
  if (!ADDRESS.test(v) || v.length > 254) {
    throw new SmtpError(`invalid ${field} address`);
  }
  return v;
}

/** Non-ASCII subjects need encoded-word form or they arrive as mojibake. */
function encodeHeaderWord(value) {
  const v = sanitizeHeader(value);
  if (/^[\x20-\x7E]*$/.test(v)) return v;
  return `=?UTF-8?B?${Buffer.from(v, 'utf8').toString('base64')}?=`;
}

/** Dot-stuffing: a line that is a lone "." would otherwise end the DATA block. */
const dotStuff = (body) => body.replace(/\r?\n/g, CRLF).replace(/^\./gm, '..');

export function buildMessage({ from, to, subject, text, date = new Date() }) {
  assertAddress(from, 'from');
  assertAddress(to, 'to');
  const headers = [
    `From: ${from}`,
    `To: ${to}`,
    `Subject: ${encodeHeaderWord(subject)}`,
    `Date: ${date.toUTCString()}`,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: 8bit',
  ];
  return headers.join(CRLF) + CRLF + CRLF + dotStuff(text);
}

/**
 * @param {{host,port,user,pass,from,to,subject,text,timeoutMs,tlsOptions}} opts
 */
export async function sendMail(opts) {
  const { host, port = 587, user, pass, from, to, subject, text,
          timeoutMs = 15_000, tlsOptions = {} } = opts;

  assertAddress(from, 'from');
  assertAddress(to, 'to');

  let socket = port === 465
    ? tls.connect({ host, port, servername: host, ...tlsOptions })
    : net.connect({ host, port });

  const timer = setTimeout(() => socket.destroy(new SmtpError('timeout')), timeoutMs);
  try {
    await new Promise((res, rej) => {
      socket.once(port === 465 ? 'secureConnect' : 'connect', res);
      socket.once('error', rej);
    });
    let read = createReader(socket);
    await expect(read, 220);

    await send(socket, `EHLO ${sanitizeHeader(from.split('@')[1] || 'localhost')}`);
    let greeting = await expect(read, 250);

    if (port !== 465) {
      if (!/STARTTLS/i.test(greeting.text)) {
        throw new SmtpError('server does not offer STARTTLS; refusing to send credentials in the clear');
      }
      await send(socket, 'STARTTLS');
      await expect(read, 220);
      const plain = socket;
      socket = tls.connect({ socket: plain, servername: host, ...tlsOptions });
      await new Promise((res, rej) => {
        socket.once('secureConnect', res);
        socket.once('error', rej);
      });
      read = createReader(socket);
      await send(socket, `EHLO ${sanitizeHeader(from.split('@')[1] || 'localhost')}`);
      greeting = await expect(read, 250);
    }

    if (user) {
      await send(socket, 'AUTH LOGIN');
      await expect(read, 334);
      await send(socket, Buffer.from(user, 'utf8').toString('base64'));
      await expect(read, 334);
      await send(socket, Buffer.from(pass, 'utf8').toString('base64'));
      await expect(read, 235);
    }

    await send(socket, `MAIL FROM:<${from}>`);
    await expect(read, 250);
    await send(socket, `RCPT TO:<${to}>`);
    await expect(read, 250, 251);
    await send(socket, 'DATA');
    await expect(read, 354);
    await send(socket, buildMessage({ from, to, subject, text }) + CRLF + '.');
    const accepted = await expect(read, 250);

    await send(socket, 'QUIT').catch(() => {});
    return { ok: true, response: accepted.text };
  } finally {
    clearTimeout(timer);
    socket.destroy();
  }
}
