// Account tables, per infra/docs/identity-architecture.md.
//
// `username` is an optional, nullable second login name. Email stays the
// identity of record — codes, resets and notices all still go to it. This is
// the current contract in infra/docs/identity-architecture.md.
//
// Divergence from the standard, agreed 2026-08-20: `phone` is nullable here.
// The standard makes it mandatory so an admin can eyeball a real contact when
// approving a subscription; inews.today is a read-only news site with no such
// flow, so the reason does not apply. The column stays so the field is there
// the day it does.

export const AUTH_SCHEMA = `
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,     -- identity of record and login name, lowercased
  username      TEXT UNIQUE,              -- optional second login name, lowercased
  phone         TEXT UNIQUE,              -- nullable by exception, see above
  nickname      TEXT,
  pw_hash       TEXT NOT NULL,            -- pbkdf2$<iters>$<salt-b64>$<hash-b64>
  role          TEXT NOT NULL DEFAULT 'user',   -- user | staff | admin
  sub_status    TEXT NOT NULL DEFAULT 'none',   -- none | active | expired
  sub_until     INTEGER,
  status        TEXT NOT NULL DEFAULT 'active', -- active | disabled | deleted_pending
  deleted_at    INTEGER,                  -- when the 7-day cooling-off started
  created_at    INTEGER NOT NULL,
  last_login    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- One-time codes for registration, password reset and email changes.
CREATE TABLE IF NOT EXISTS codes (
  id          INTEGER PRIMARY KEY,
  email       TEXT NOT NULL,
  purpose     TEXT NOT NULL,              -- register | reset
  code_hash   TEXT NOT NULL,              -- never stored in the clear
  created_at  INTEGER NOT NULL,
  expires_at  INTEGER NOT NULL,
  used_at     INTEGER,
  attempts    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_codes_lookup ON codes(email, purpose, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_codes_expiry ON codes(expires_at);

CREATE TABLE IF NOT EXISTS sessions (
  id          TEXT PRIMARY KEY,           -- random 256-bit, hashed at rest
  user_id     INTEGER NOT NULL,
  created_at  INTEGER NOT NULL,
  last_seen   INTEGER NOT NULL,
  expires_at  INTEGER NOT NULL,
  ip          TEXT,
  ua          TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_exp ON sessions(expires_at);

-- Every admin action, plus every login attempt: "who / when / what / target".
CREATE TABLE IF NOT EXISTS audit_log (
  id          INTEGER PRIMARY KEY,
  at          INTEGER NOT NULL,
  actor_id    INTEGER,
  actor_email TEXT,
  action      TEXT NOT NULL,
  target      TEXT,
  detail      TEXT,
  ip          TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at DESC);

-- Login and code-request throttling: 5 failures per 15 min, exponential lockout.
CREATE TABLE IF NOT EXISTS rate_events (
  id       INTEGER PRIMARY KEY,
  bucket   TEXT NOT NULL,                 -- e.g. login:a@b.com / code:1.2.3.4
  at       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate ON rate_events(bucket, at DESC);
`;
