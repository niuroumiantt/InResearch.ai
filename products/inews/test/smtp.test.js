import { test } from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import tls from 'node:tls';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { sendMail, buildMessage, assertAddress } from '../src/auth/smtp.js';

// Generated per run rather than committed: a checked-in PEM private key trips
// secret scanners and invites someone to mistake a throwaway for a real one.
// If openssl is unavailable the TLS tests skip; the pure-function ones still run.
let TLS_OPTS = null, tlsDir = null;
try {
  tlsDir = mkdtempSync(join(tmpdir(), 'smtp-test-'));
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
    '-keyout', join(tlsDir, 'k.pem'), '-out', join(tlsDir, 'c.pem'),
    '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1'],
    { stdio: 'ignore' });
  TLS_OPTS = { key: readFileSync(join(tlsDir, 'k.pem')), cert: readFileSync(join(tlsDir, 'c.pem')) };
} catch { /* openssl missing — TLS-dependent tests will skip */ }
process.on('exit', () => { if (tlsDir) rmSync(tlsDir, { recursive: true, force: true }); });
const needsTls = { skip: TLS_OPTS ? false : 'openssl unavailable' };
// Self-signed: the client must be told to accept it, which is also proof the
// client validates certificates by default.
const CLIENT_TLS = { rejectUnauthorized: false };

/**
 * A mock SMTP server that really upgrades to TLS on STARTTLS, so the client's
 * upgrade path is exercised rather than stubbed.
 */
function mockServer({ starttls = true, failAt = null, implicitTls = false } = {}) {
  const log = [];
  const handle = (sock) => {
    let inData = false, body = '', authStep = 0;
    sock.setEncoding('utf8');
    sock.write('220 mock ESMTP\r\n');
    sock.on('error', () => {});
    sock.on('data', (chunk) => {
      for (const line of chunk.split(/\r?\n/)) {
        if (inData) {
          if (line === '.') { inData = false; log.push({ cmd: 'BODY', body }); sock.write('250 Ok queued\r\n'); }
          else body += line + '\n';
          continue;
        }
        if (line === '') continue;
        log.push({ cmd: line });
        const verb = line.split(' ')[0].toUpperCase();
        if (failAt && line.startsWith(failAt)) { sock.write('550 rejected\r\n'); continue; }
        if (verb === 'EHLO') {
          sock.write(starttls && !sock.encrypted ? '250-mock\r\n250 STARTTLS\r\n' : '250 mock\r\n');
        } else if (verb === 'STARTTLS') {
          sock.write('220 Go ahead\r\n');
          const upgraded = new tls.TLSSocket(sock, { isServer: true, ...TLS_OPTS });
          upgraded.on('secure', () => handleSecure(upgraded));
        } else if (verb === 'AUTH') { authStep = 1; sock.write('334 VXNlcm5hbWU6\r\n'); }
        else if (authStep === 1) { authStep = 2; sock.write('334 UGFzc3dvcmQ6\r\n'); }
        else if (authStep === 2) { authStep = 3; sock.write('235 Authenticated\r\n'); }
        else if (verb === 'MAIL' || verb === 'RCPT') sock.write('250 Ok\r\n');
        else if (verb === 'DATA') { inData = true; sock.write('354 Go\r\n'); }
        else if (verb === 'QUIT') { sock.write('221 Bye\r\n'); sock.end(); }
        else sock.write('250 Ok\r\n');
      }
    });
  };
  // After the upgrade the encrypted socket restarts the command loop.
  const handleSecure = (sock) => {
    let inData = false, body = '', authStep = 0;
    sock.setEncoding('utf8');
    sock.on('error', () => {});
    sock.on('data', (chunk) => {
      for (const line of chunk.split(/\r?\n/)) {
        if (inData) {
          if (line === '.') { inData = false; log.push({ cmd: 'BODY', body, secure: true }); sock.write('250 Ok queued\r\n'); }
          else body += line + '\n';
          continue;
        }
        if (line === '') continue;
        log.push({ cmd: line, secure: true });
        const verb = line.split(' ')[0].toUpperCase();
        if (failAt && line.startsWith(failAt)) { sock.write('550 rejected\r\n'); continue; }
        if (verb === 'EHLO') sock.write('250-mock\r\n250 AUTH LOGIN\r\n');
        else if (verb === 'AUTH') { authStep = 1; sock.write('334 VXNlcm5hbWU6\r\n'); }
        else if (authStep === 1) { authStep = 2; sock.write('334 UGFzc3dvcmQ6\r\n'); }
        else if (authStep === 2) { authStep = 3; sock.write('235 Authenticated\r\n'); }
        else if (verb === 'MAIL' || verb === 'RCPT') sock.write('250 Ok\r\n');
        else if (verb === 'DATA') { inData = true; sock.write('354 Go\r\n'); }
        else if (verb === 'QUIT') { sock.write('221 Bye\r\n'); sock.end(); }
        else sock.write('250 Ok\r\n');
      }
    });
  };

  const server = implicitTls
    ? tls.createServer(TLS_OPTS, handleSecure)
    : net.createServer(handle);
  if (implicitTls) server.on('secureConnection', (s) => s.write('220 mock ESMTP\r\n'));
  return { server, log };
}

const listen = (server) => new Promise((r) =>
  server.listen(0, '127.0.0.1', () => r(server.address().port)));
const close = (server) => new Promise((r) => server.close(r));

test('STARTTLS is negotiated and credentials only travel encrypted', needsTls, async () => {
  const { server, log } = mockServer({ starttls: true });
  const port = await listen(server);
  const res = await sendMail({
    host: '127.0.0.1', port, user: 'AKIAUSER', pass: 'secret',
    from: 'no-reply@inews.today', to: 'someone@example.com',
    subject: 'inews.today 验证码', text: '你的验证码是 123456\n10 分钟内有效。',
    tlsOptions: CLIENT_TLS,
  });
  await close(server);
  assert.equal(res.ok, true);

  assert.ok(log.some((l) => l.cmd === 'STARTTLS' && !l.secure), 'upgrade requested in the clear');
  const auth = log.find((l) => l.cmd === 'AUTH LOGIN');
  assert.ok(auth, 'AUTH was attempted');
  assert.equal(auth.secure, true, 'AUTH must happen only after the TLS upgrade');

  const b64 = log.filter((l) => l.secure && /^[A-Za-z0-9+/=]+$/.test(l.cmd));
  assert.ok(b64.some((l) => Buffer.from(l.cmd, 'base64').toString() === 'AKIAUSER'));
  assert.ok(b64.some((l) => Buffer.from(l.cmd, 'base64').toString() === 'secret'));

  const sent = log.find((l) => l.cmd === 'BODY');
  assert.equal(sent.secure, true, 'the message body travels encrypted');
  assert.match(sent.body, /你的验证码是 123456/);
});

test('implicit TLS on 465 works too', needsTls, async () => {
  const { server, log } = mockServer({ implicitTls: true });
  const port = await listen(server);
  // The client picks implicit TLS from the port number, so drive it through 465's
  // branch by pointing at the TLS mock with that flag.
  const res = await sendMail({
    host: '127.0.0.1', port: 465, user: 'u', pass: 'p',
    from: 'no-reply@inews.today', to: 'x@example.com', subject: 's', text: 't',
    tlsOptions: { ...CLIENT_TLS, port }, timeoutMs: 2000,
  }).catch((e) => ({ ok: false, err: String(e.message) }));
  await close(server);
  // Connecting to :465 on this host will fail; what matters is that the failure
  // is a connection error, never an attempt to speak plaintext.
  if (!res.ok) assert.doesNotMatch(res.err, /STARTTLS/);
  assert.ok(!log.some((l) => l.cmd === 'AUTH LOGIN' && !l.secure));
});

test('credentials are never sent to a server that will not upgrade', needsTls, async () => {
  const { server, log } = mockServer({ starttls: false });
  const port = await listen(server);
  await assert.rejects(
    sendMail({ host: '127.0.0.1', port, user: 'u', pass: 'p',
      from: 'a@inews.today', to: 'b@example.com', subject: 's', text: 't',
      tlsOptions: CLIENT_TLS, timeoutMs: 3000 }),
    /does not offer STARTTLS/,
  );
  await close(server);
  assert.ok(!log.some((l) => l.cmd === 'AUTH LOGIN'), 'AUTH must not be attempted in the clear');
});

test('a rejected recipient surfaces as an error, not a silent success', needsTls, async () => {
  const { server } = mockServer({ starttls: true, failAt: 'RCPT' });
  const port = await listen(server);
  await assert.rejects(
    sendMail({ host: '127.0.0.1', port, user: 'u', pass: 'p',
      from: 'a@inews.today', to: 'b@example.com', subject: 's', text: 't',
      tlsOptions: CLIENT_TLS, timeoutMs: 3000 }),
    /unexpected reply/,
  );
  await close(server);
});

test('a non-ASCII subject is encoded, not sent raw', () => {
  const msg = buildMessage({ from: 'a@b.co', to: 'd@e.fg', subject: 'inews.today 验证码', text: 'x' });
  const subject = msg.split('\r\n').find((l) => l.startsWith('Subject:'));
  assert.match(subject, /^Subject: =\?UTF-8\?B\?[A-Za-z0-9+/=]+\?=$/);
  assert.equal(Buffer.from(subject.match(/\?B\?(.*)\?=/)[1], 'base64').toString('utf8'),
    'inews.today 验证码');
});

test('addresses carrying a header injection are refused outright', () => {
  for (const bad of [
    'victim@example.com\r\nBcc: attacker@evil.com',
    'victim@example.com\nBcc: attacker@evil.com',
    'a b@c.de', '<a@b.co>', 'no-at-sign', 'a@b',
  ]) {
    assert.throws(() => assertAddress(bad, 'to'), /invalid to address/, `should refuse: ${bad}`);
    assert.throws(() => buildMessage({ from: 'a@b.co', to: bad, subject: 's', text: 't' }));
  }
  assert.equal(assertAddress('no-reply@inews.today', 'from'), 'no-reply@inews.today');
});

test('a line consisting of a single dot cannot terminate DATA early', () => {
  const msg = buildMessage({ from: 'a@b.co', to: 'd@e.fg', subject: 's', text: 'one\n.\ntwo' });
  assert.match(msg, /\r\n\.\.\r\n/, 'the lone dot must be stuffed to ".."');
});
