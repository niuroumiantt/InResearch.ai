import { DatabaseSync } from 'node:sqlite';
import { chmodSync, existsSync, mkdirSync, readFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { envValue } from './env.js';

const HERE = dirname(fileURLToPath(import.meta.url));
export const ROOT = join(HERE, '..', '..');
/** Resolve the one database shared by content, identity and audit data. */
export function resolveDbPath(source = process.env) {
  const configured = envValue('INEWS_DB_PATH', {
    legacy: 'SINGLETITLE_DB', source,
  });
  if (configured) return configured;
  const dataDir = source.INEWS_DATA_DIR;
  return dataDir ? join(dataDir, 'inews.sqlite3') : join(ROOT, 'data', 'inews.sqlite3');
}

export const DB_PATH = resolveDbPath();

const SCHEMA = `
CREATE TABLE IF NOT EXISTS articles (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  url           TEXT NOT NULL,
  guid          TEXT NOT NULL UNIQUE,
  title         TEXT NOT NULL,
  domain        TEXT NOT NULL,
  publisher     TEXT,
  published_at  INTEGER NOT NULL,   -- ms, article's own pubDate
  first_seen_at INTEGER NOT NULL,   -- ms, when WE first saw it
  lang          TEXT,
  locale        TEXT,
  angle         TEXT,
  shard         TEXT,
  query         TEXT,
  relevance     INTEGER NOT NULL,
  relevant      INTEGER NOT NULL,
  hits          TEXT,
  dedupe_key    TEXT NOT NULL,
  cluster_id    INTEGER,            -- id of the earliest article in the cluster
  is_original   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_articles_pub ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_seen ON articles(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_dk ON articles(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_articles_domain ON articles(domain);
CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id, published_at);

-- Existing installations predate AUTOINCREMENT. Production ingest allocates
-- explicit ids from this durable high-water mark so deleting a replaced
-- Techmeme row can never make its public /r/:id point at an unrelated story.
CREATE TABLE IF NOT EXISTS id_sequences (
  name          TEXT PRIMARY KEY,
  next_id       INTEGER NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_articles_id_sequence
AFTER INSERT ON articles BEGIN
  INSERT INTO id_sequences(name, next_id) VALUES ('articles', NEW.id + 1)
  ON CONFLICT(name) DO UPDATE SET next_id=MAX(id_sequences.next_id, excluded.next_id);
END;

-- Editorial provenance is not the same thing as publisher trust or value.
-- A story may be discovered by Google first and selected by Techmeme later;
-- keep that second fact even when the article row itself already exists.
CREATE TABLE IF NOT EXISTS editorial_references (
  source        TEXT NOT NULL,
  source_key    TEXT NOT NULL,
  article_id    INTEGER,
  title         TEXT NOT NULL,
  url           TEXT NOT NULL,
  domain        TEXT NOT NULL,
  publisher     TEXT,
  selected_at   INTEGER NOT NULL, -- Techmeme inclusion time, not publisher time
  first_seen_at INTEGER NOT NULL,
  value         INTEGER,          -- selection-time projection; independent of mutable article row
  genre         TEXT,
  angle         TEXT,
  policy        TEXT,
  observed_at   INTEGER,          -- fetch start; orders concurrent responses
  observer      TEXT,
  observer_rank INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (source, source_key)
);
CREATE INDEX IF NOT EXISTS idx_editorial_refs_time
  ON editorial_references(source, selected_at DESC);
CREATE INDEX IF NOT EXISTS idx_editorial_refs_domain
  ON editorial_references(source, domain);
CREATE INDEX IF NOT EXISTS idx_editorial_refs_article
  ON editorial_references(source, article_id);
-- Cluster repair starts from an article and asks which editorial selections
-- point at it. Keep the source-prefixed index for source reports, and this
-- inverse lookup for topology maintenance and the merge trigger.
CREATE INDEX IF NOT EXISTS idx_editorial_refs_article_only
  ON editorial_references(article_id);

-- Editorial admission is an overlay on independently scored publisher rows.
-- Preserve the exact pre-overlay state so moving a permanent Techmeme pointer
-- can remove its old floor without guessing what heuristics/LLM had produced.
CREATE TABLE IF NOT EXISTS article_editorial_bases (
  article_id    INTEGER PRIMARY KEY,
  relevance     INTEGER NOT NULL,
  relevant      INTEGER NOT NULL,
  hits          TEXT,
  angle         TEXT,
  value         INTEGER,
  genre         TEXT,
  value_src     TEXT
);
CREATE TRIGGER IF NOT EXISTS trg_articles_editorial_base_cleanup
AFTER DELETE ON articles BEGIN
  DELETE FROM article_editorial_bases WHERE article_id=OLD.id;
END;

-- Latest fetched state is distinct from latest accepted state. A newer
-- rejected edit must still prevent an older in-flight accepted response from
-- rolling the permanent id back, without deleting its historical acceptance.
CREATE TABLE IF NOT EXISTS editorial_observations (
  source        TEXT NOT NULL,
  source_key    TEXT NOT NULL,
  selected_at   INTEGER NOT NULL,
  observed_at   INTEGER NOT NULL,
  observer      TEXT,
  observer_rank INTEGER NOT NULL DEFAULT 0,
  url           TEXT NOT NULL,
  title         TEXT NOT NULL,
  accepted      INTEGER NOT NULL,
  reason        TEXT,
  PRIMARY KEY (source, source_key)
);

CREATE TABLE IF NOT EXISTS domains (
  domain        TEXT PRIMARY KEY,
  seed_type     TEXT,               -- primary|relay|wire|platform from sources.seed.json
  seed_desc     TEXT,
  first_seen_at INTEGER,
  last_seen_at  INTEGER,
  articles      INTEGER NOT NULL DEFAULT 0,
  relevant      INTEGER NOT NULL DEFAULT 0,
  originals     INTEGER NOT NULL DEFAULT 0,   -- first in its cluster
  lead_ms_sum   INTEGER NOT NULL DEFAULT 0,   -- how early vs cluster head
  lead_n        INTEGER NOT NULL DEFAULT 0,
  score         REAL NOT NULL DEFAULT 0,
  scored_at     INTEGER,
  status        TEXT NOT NULL DEFAULT 'observing'  -- observing|trusted|muted
);

CREATE TABLE IF NOT EXISTS fetches (
  id          INTEGER PRIMARY KEY,
  shard       TEXT NOT NULL,
  started_at  INTEGER NOT NULL,
  ms          INTEGER,
  status      INTEGER,
  items       INTEGER DEFAULT 0,
  fresh       INTEGER DEFAULT 0,
  kept        INTEGER DEFAULT 0,
  error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_fetches_time ON fetches(started_at DESC);

-- 通道③页面监控的已见链接集(links 模式的基线与增量判定)。
CREATE TABLE IF NOT EXISTS watch_seen (
  shard  TEXT NOT NULL,
  url    TEXT NOT NULL,
  PRIMARY KEY (shard, url)
);

CREATE TABLE IF NOT EXISTS shard_state (
  shard        TEXT PRIMARY KEY,
  etag         TEXT,
  last_modified TEXT,
  last_run_at  INTEGER,
  cooldown_until INTEGER,
  fails        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shard_policy (
  shard       TEXT PRIMARY KEY,
  base_lane   TEXT NOT NULL,       -- lane declared in keywords.js
  lane        TEXT NOT NULL,       -- lane actually in force right now
  pinned      INTEGER NOT NULL DEFAULT 0,  -- 1 = human override, never auto-moved
  yield_rate  REAL NOT NULL DEFAULT 0,     -- kept articles per run, recent window
  runs        INTEGER NOT NULL DEFAULT 0,
  changed_at  INTEGER,
  reason      TEXT
);

CREATE TABLE IF NOT EXISTS lane_events (
  id        INTEGER PRIMARY KEY,
  shard     TEXT NOT NULL,
  at        INTEGER NOT NULL,
  from_lane TEXT,
  to_lane   TEXT NOT NULL,
  reason    TEXT,
  yield_rate REAL,
  runs      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_lane_events_at ON lane_events(at DESC);

-- Translation cache. Keyed by the source text, not by article id: the same
-- headline arrives from a dozen aggregators, and paying the translation API
-- once per copy is both slower and, on a metered free tier, wasteful.
-- 跨语言并簇的裁决缓存(lib/merge.js):被 LLM 否决过的候选对不再重问 ——
-- 词面筛选每个采集周期都会重新提名同样的对,没有这张表就是每轮白花钱。
CREATE TABLE IF NOT EXISTS merge_verdicts (
  pair TEXT PRIMARY KEY,      -- '小id:大id'
  same INTEGER NOT NULL,      -- 1=同一事件(并簇后头行消失,行仅作记录) 0=否决
  at   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS translations (
  src_hash   TEXT PRIMARY KEY,       -- sha256(source text), first 32 hex chars
  src        TEXT NOT NULL,
  target     TEXT NOT NULL,          -- BCP-47 target, always zh-CN today
  text       TEXT NOT NULL,
  provider   TEXT,
  at         INTEGER NOT NULL
);
`;

// Columns added after the first release. `CREATE TABLE IF NOT EXISTS` is a
// no-op on an existing database, so new columns need an explicit pass.
const MIGRATIONS = [
  ['articles', 'title_zh', 'TEXT'],          // machine translation, NULL until done
  ['articles', 'title_zh_at', 'INTEGER'],
  // 价值轴(0-3)与体裁:relevance 说"是不是AI",value 说"值不值得读"。
  // value_src: heur=通用启发式,llm=批量精化,editorial=专属编辑准入。
  ['articles', 'value', 'INTEGER'],
  ['articles', 'genre', 'TEXT'],
  ['articles', 'value_src', 'TEXT'],
  // 地区(读者七分法:us/cn/eu/jk/me/sea/other),域名后缀+语区推定。
  ['articles', 'region', 'TEXT'],
  // 聚类元数据物化在头行上(2026-08-31 性能修复):时间线此前靠三个
  // 每行相关子查询(最新动态/代表行/转载数),6 万行上一次查询 ~1 秒。
  // 物化后纯列扫描,ingest 增量维护。只有头行(id=cluster_id)有值。
  ['articles', 'cluster_latest', 'INTEGER'],
  ['articles', 'cluster_n', 'INTEGER'],
  // Editorial rows are a durable benchmark snapshot. article_id is only a
  // navigation link; later LLM/backfill changes must not rewrite the baseline.
  ['editorial_references', 'value', 'INTEGER'],
  ['editorial_references', 'genre', 'TEXT'],
  ['editorial_references', 'angle', 'TEXT'],
  ['editorial_references', 'policy', 'TEXT'],
  ['editorial_references', 'observed_at', 'INTEGER'],
  ['editorial_references', 'observer', 'TEXT'],
  ['editorial_references', 'observer_rank', 'INTEGER'],
];

function migrate(d) {
  // The caller owns the initialization-wide IMMEDIATE transaction. Recheck
  // every column only after that reservation is held: CREATE/ALTER/index and
  // executable trigger migrations must be one serialized unit.
  for (const [table, column, type] of MIGRATIONS) {
    const cols = d.prepare(`PRAGMA table_info(${table})`).all().map((c) => c.name);
    if (!cols.includes(column)) d.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${type}`);
  }
    // 引用迁移列的索引必须建在迁移之后 —— 放进 SCHEMA 会在全新库上炸
    // (建表语句里还没有 value 列)。读者主查询与 filters 分组都吃这条。
    d.exec('CREATE INDEX IF NOT EXISTS idx_articles_read ON articles(relevant, value, published_at DESC)');
    d.exec('CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url)');
    d.exec(`INSERT INTO id_sequences(name, next_id)
            SELECT 'articles', COALESCE(MAX(id), 0) + 1 FROM articles WHERE 1
            ON CONFLICT(name) DO UPDATE SET
              next_id=MAX(id_sequences.next_id, excluded.next_id)`);
    d.exec(`UPDATE editorial_references SET
              observed_at=COALESCE(observed_at, first_seen_at),
              observer=COALESCE(observer, ''),
              observer_rank=COALESCE(observer_rank, 0)
            WHERE observed_at IS NULL OR observer IS NULL OR observer_rank IS NULL`);
    d.exec(`INSERT OR IGNORE INTO editorial_observations
              (source, source_key, selected_at, observed_at, observer, observer_rank,
               url, title, accepted, reason)
            SELECT source, source_key, selected_at, observed_at, observer, observer_rank,
                   url, title, 1, 'migrated-reference'
            FROM editorial_references`);
    // 读者时间线的主通道:部分索引精确匹配「精选+合并」的全部固定谓词,
    // ORDER BY cluster_latest DESC 沿索引序早停 —— 分类切换毫秒级的关键。
    d.exec(`CREATE INDEX IF NOT EXISTS idx_heads_latest ON articles(cluster_latest DESC)
            WHERE relevant = 1 AND is_original = 1 AND value >= 2`);
    // merge.js is an independent topology writer. When a referenced editorial
    // cluster loses to an earlier head, carry the persistent display floor to
    // that new head inside the same UPDATE statement; otherwise collapsed mode
    // can hide a selected story until the next ingest convergence pass.
    // Recreate rather than IF NOT EXISTS: this trigger is executable migration
    // logic, and upgraded databases must receive its current reconciliation
    // behavior as well as fresh databases.
    d.exec('DROP TRIGGER IF EXISTS trg_cluster_editorial_floor');
    d.exec(`CREATE TRIGGER trg_cluster_editorial_floor
    AFTER UPDATE OF cluster_id ON articles
    WHEN NEW.cluster_id IS NOT NULL AND EXISTS (
      SELECT 1 FROM editorial_references r
      JOIN articles picked ON picked.id=r.article_id
      WHERE picked.cluster_id=NEW.cluster_id
    )
    BEGIN
      INSERT OR IGNORE INTO article_editorial_bases
        (article_id, relevance, relevant, hits, angle, value, genre, value_src)
        SELECT id, relevance, relevant, hits, angle, value, genre, value_src
        FROM articles
        WHERE id=NEW.cluster_id AND COALESCE(value_src, '') != 'editorial';
      UPDATE articles SET
        relevance=MAX(relevance, 3),
        relevant=1,
        value=MAX(COALESCE(value, 0), COALESCE((
          SELECT MAX(COALESCE(r.value, 2))
          FROM editorial_references r
          JOIN articles picked ON picked.id=r.article_id
          WHERE picked.cluster_id=NEW.cluster_id
        ), 2)),
        genre=CASE WHEN COALESCE((
          SELECT MAX(COALESCE(r.value, 2)) FROM editorial_references r
          JOIN articles picked ON picked.id=r.article_id
          WHERE picked.cluster_id=NEW.cluster_id
        ), 2) >= COALESCE(value, 0) THEN COALESCE((
          SELECT r.genre FROM editorial_references r
          JOIN articles picked ON picked.id=r.article_id
          WHERE picked.cluster_id=NEW.cluster_id AND r.genre IS NOT NULL
          ORDER BY COALESCE(r.value, 2) DESC, r.source DESC, r.source_key DESC LIMIT 1
        ), genre) ELSE genre END,
        angle=CASE WHEN COALESCE((
          SELECT MAX(COALESCE(r.value, 2)) FROM editorial_references r
          JOIN articles picked ON picked.id=r.article_id
          WHERE picked.cluster_id=NEW.cluster_id
        ), 2) >= COALESCE(value, 0) THEN COALESCE((
          SELECT r.angle FROM editorial_references r
          JOIN articles picked ON picked.id=r.article_id
          WHERE picked.cluster_id=NEW.cluster_id AND r.angle IS NOT NULL
          ORDER BY COALESCE(r.value, 2) DESC, r.source DESC, r.source_key DESC LIMIT 1
        ), angle) ELSE angle END,
        value_src='editorial'
      WHERE id=NEW.cluster_id AND EXISTS (
        SELECT 1 FROM editorial_references r
        JOIN articles picked ON picked.id=r.article_id
        WHERE picked.cluster_id=NEW.cluster_id
      );
      -- A merged-away former head may carry an overlay solely because it used
      -- to display a selected child. Once it is neither the new head nor the
      -- selected row, restore its independent score in the same transaction.
      UPDATE articles SET
        relevance=(SELECT b.relevance FROM article_editorial_bases b WHERE b.article_id=articles.id),
        relevant=(SELECT b.relevant FROM article_editorial_bases b WHERE b.article_id=articles.id),
        hits=(SELECT b.hits FROM article_editorial_bases b WHERE b.article_id=articles.id),
        angle=(SELECT b.angle FROM article_editorial_bases b WHERE b.article_id=articles.id),
        value=(SELECT b.value FROM article_editorial_bases b WHERE b.article_id=articles.id),
        genre=(SELECT b.genre FROM article_editorial_bases b WHERE b.article_id=articles.id),
        value_src=(SELECT b.value_src FROM article_editorial_bases b WHERE b.article_id=articles.id)
      WHERE cluster_id=NEW.cluster_id AND id != NEW.cluster_id
        AND EXISTS (SELECT 1 FROM article_editorial_bases b WHERE b.article_id=articles.id)
        AND NOT EXISTS (SELECT 1 FROM editorial_references r WHERE r.article_id=articles.id);
      DELETE FROM article_editorial_bases
      WHERE article_id IN (
        SELECT a.id FROM articles a
        WHERE a.cluster_id=NEW.cluster_id AND a.id != NEW.cluster_id
          AND NOT EXISTS (SELECT 1 FROM editorial_references r WHERE r.article_id=a.id)
      );
      UPDATE domains SET relevant=(
        SELECT COALESCE(SUM(a.relevant), 0) FROM articles a WHERE a.domain=domains.domain
      ) WHERE domain=(SELECT domain FROM articles WHERE id=NEW.cluster_id)
        AND EXISTS (
          SELECT 1 FROM editorial_references r
          JOIN articles picked ON picked.id=r.article_id
          WHERE picked.cluster_id=NEW.cluster_id
        );
      UPDATE domains SET relevant=(
        SELECT COALESCE(SUM(a.relevant), 0) FROM articles a WHERE a.domain=domains.domain
      ) WHERE domain IN (SELECT DISTINCT domain FROM articles WHERE cluster_id=NEW.cluster_id);
    END`);
}

const SQLITE_INIT_TIMEOUT_MS = 30_000;
const SQLITE_RETRY_WAIT = new Int32Array(new SharedArrayBuffer(4));

function isSqliteBusy(error) {
  const code = Number(error?.errcode);
  return (Number.isInteger(code) && ((code & 0xff) === 5 || (code & 0xff) === 6))
    || /database(?: (?:schema|table))? is locked|database is busy/i
      .test(String(error?.message || ''));
}

/** Some SQLite schema pragmas do not consistently invoke busy_timeout. */
function retrySqliteBusy(action, timeoutMs = SQLITE_INIT_TIMEOUT_MS) {
  const deadline = Date.now() + timeoutMs;
  let delayMs = 5;
  for (;;) {
    try {
      return action();
    } catch (error) {
      const remaining = deadline - Date.now();
      if (!isSqliteBusy(error) || remaining <= 0) throw error;
      Atomics.wait(SQLITE_RETRY_WAIT, 0, 0, Math.min(delayMs, remaining));
      delayMs = Math.min(delayMs * 2, 100);
    }
  }
}

function ensureWal(d) {
  const current = retrySqliteBusy(() => d.prepare('PRAGMA journal_mode').get());
  const mode = String(current?.journal_mode || Object.values(current || {})[0] || '');
  if (mode.toLowerCase() !== 'wal') {
    retrySqliteBusy(() => d.exec('PRAGMA journal_mode = WAL'));
  }
}

function initializeDatabase(d) {
  // journal_mode cannot change inside a transaction and can return SQLITE_BUSY
  // immediately while another opener is migrating, even with busy_timeout.
  // Retry that one pragma, then serialize every schema/data migration behind a
  // single write reservation so another process never observes half a schema.
  ensureWal(d);
  d.exec('PRAGMA synchronous = NORMAL');
  retrySqliteBusy(() => d.exec('BEGIN IMMEDIATE'));
  try {
    d.exec(SCHEMA);
    migrate(d);
    seedDomains(d);
    applyMutelist(d);
    d.exec('COMMIT');
  } catch (error) {
    try { d.exec('ROLLBACK'); } catch { /* preserve the initialization error */ }
    throw error;
  }
}

let db;
export function assertDatabaseFilenameReady(path = DB_PATH) {
  if (basename(path) !== 'inews.sqlite3') return;
  const legacy = join(dirname(path), 'news.db');
  if (existsSync(path) && existsSync(legacy)) {
    throw new Error(`新旧数据库同时存在：${path} 与 ${legacy}；请停服务并人工核对，应用拒绝猜测`);
  }
  if (existsSync(path)) return;
  if (existsSync(legacy)) {
    throw new Error(`旧数据库仍在 ${legacy}；请先停服务并迁移为 ${path}`);
  }
}

export function getDb() {
  if (db) return db;
  // A renamed database must be an explicit stopped-service migration. Opening
  // a fresh inews.sqlite3 beside a populated news.db would look like data loss.
  assertDatabaseFilenameReady();
  mkdirSync(dirname(DB_PATH), { recursive: true });
  const previousUmask = process.umask(0o077);
  let candidate;
  try {
    candidate = new DatabaseSync(DB_PATH);
    // Set this before journal-mode/schema work. The explicit retry covers
    // SQLite pragmas that do not consistently invoke the connection handler.
    candidate.exec(`PRAGMA busy_timeout = ${SQLITE_INIT_TIMEOUT_MS}`);
    initializeDatabase(candidate);
    for (const suffix of ['', '-wal', '-shm']) {
      const file = DB_PATH + suffix;
      if (existsSync(file)) chmodSync(file, 0o600);
    }
    db = candidate;
  } catch (error) {
    try { candidate?.close(); } catch { /* preserve the initialization error */ }
    throw error;
  } finally {
    process.umask(previousUmask);
  }
  return db;
}

/**
 * 一次性套用内容农场黑名单(2026-08-31 由 300 条线上样本人工复核得出)。
 * 用 user_version 做水位:只在升版时执行,且只动 status='observing' 的行 ——
 * 人在界面上做过的信任/静音决定永远不被种子文件覆盖。
 */
function applyMutelist(d) {
  // 黑名单文件每加一批域名,把这个版本号 +1 —— 已按过水位的库才会重放新名单。
  const MUTELIST_V = 4;   // v4: 2026-09-03 Reddit 试点停采；静音直连源不再轮询
  const v = d.prepare('PRAGMA user_version').get().user_version;
  if (v >= MUTELIST_V) return;
  let list;
  try {
    list = JSON.parse(readFileSync(join(HERE, '..', 'config', 'muted-domains.json'), 'utf8'));
  } catch { list = null; }
  if (list) {
    const up = d.prepare(`INSERT INTO domains(domain, seed_desc, status) VALUES (?, ?, 'muted')
      ON CONFLICT(domain) DO UPDATE SET status = 'muted',
        seed_desc = COALESCE(domains.seed_desc, excluded.seed_desc)
      WHERE domains.status = 'observing'`);
    for (const [domain, why] of Object.entries(list)) up.run(domain, why);
  }
  d.exec(`PRAGMA user_version = ${MUTELIST_V}`);
}

function seedDomains(d) {
  const has = d.prepare('SELECT COUNT(*) n FROM domains').get().n;
  if (has > 0) return;
  let seed;
  try {
    seed = JSON.parse(readFileSync(join(HERE, '..', 'config', 'sources.seed.json'), 'utf8'));
  } catch { return; }
  const ins = d.prepare(
    'INSERT OR IGNORE INTO domains(domain, seed_type, seed_desc, status) VALUES (?,?,?,?)',
  );
  for (const [domain, meta] of Object.entries(seed)) {
    ins.run(domain, meta.type ?? null, meta.desc ?? null,
      meta.type === 'relay' ? 'observing' : 'observing');
  }
}
