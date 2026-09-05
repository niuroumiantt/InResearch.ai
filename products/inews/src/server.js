import http from 'node:http';
import { execSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { getDb, ROOT } from './lib/db.js';
import { computeScore } from './lib/domains.js';
import { pinShard, POLICY } from './lib/policy.js';
import { buildShards, GROUPS, LOCALES } from './config/keywords.js';
import { CONFIG } from './scheduler.js';
import { handleAuth, requireStaff, requireReader, requireCsrf, HttpError } from './auth/routes.js';
import { audit } from './auth/store.js';
import { translatePending, translatorEnabled, translatorName } from './lib/translate.js';
import { classifyPending, classifierEnabled, classifierName } from './lib/classify.js';
import { reportXlsx } from './lib/report.js';
import { loadEditorialBenchmark } from './lib/benchmark.js';

const WEB = join(ROOT, 'web');
// 统一仓库发布的私站原文库(只读挂载)。内容来自站长个人订阅,只有 staff 能看。
const RAW = process.env.RAWARTICLE_DIR || '/rawarticle';
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml' };

const json = (res, data, code = 200, cache = 'no-store') => {
  const body = JSON.stringify(data);
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'cache-control': cache });
  res.end(body);
};

// 时间线微缓存:分类点来点去、多读者同屏,重复查询直接命中。
// 失效不靠 TTL 靠**写入水位**(缓存时的 MAX(id)):库一有新文章立即失效,
// 永远不给陈旧结果;水位查询走主键树,成本可忽略。上限 64 键防膨胀。
const TL_CACHE = new Map();

function timeline(q) {
  const stamp = getDb().prepare('SELECT MAX(id) m FROM articles').get().m || 0;
  const cacheKey = q.toString();
  const hit = TL_CACHE.get(cacheKey);
  if (hit && hit.stamp === stamp) return hit.rows;
  const rows = timelineQuery(q);
  TL_CACHE.set(cacheKey, { stamp, rows });
  if (TL_CACHE.size > 64) TL_CACHE.delete(TL_CACHE.keys().next().value);
  return rows;
}

function timelineQuery(q) {
  const db = getDb();
  const limit = Math.min(500, Number(q.get('limit') || 100));
  const before = Number(q.get('before') || 0) || null;   // published_at cursor
  const mode = q.get('mode') || 'relevant';               // relevant | all
  const angle = q.get('angle');
  const lang = q.get('lang');
  const domain = q.get('domain');
  const search = (q.get('q') || '').trim();
  const originalsOnly = q.get('originals') === '1';
  const collapse = q.get('collapse') === '1';
  const sources = q.get('sources') || 'all';

  // Every column here must be qualified: `articles` and `domains` both have a
  // `relevant` column, and an unqualified reference makes the JOIN ambiguous.
  const where = ['a.published_at <= ?'];
  const args = [Date.now() + 10 * 60_000]; // tolerate slightly-future pubDates
  if (before) { where.push('a.published_at < ?'); args.push(before); }
  if (mode !== 'all') where.push('a.relevant = 1');
  // 价值档下限(0-3)。拼**字面量**而非绑定参数:部分索引(idx_heads_latest,
  // WHERE value >= 2)的可用性在规划期判定,参数化谓词无法被证明蕴含索引
  // 条件,索引就废了 —— 这是分类切换从 1 秒降到毫秒级的关键之一。
  // vmin 经 Number+Math.floor 清洗,无注入面。
  const vmin = Math.floor(Number(q.get('v')));
  if (Number.isFinite(vmin) && vmin > 0 && mode !== 'all') {
    where.push(`a.value >= ${Math.min(3, Math.max(1, vmin))}`);
  }
  // 静音域名(内容农场)从默认视图消失;「全部」模式仍可见,用于复核与解除。
  if (mode !== 'all') where.push("COALESCE(d.status, 'observing') != 'muted'");
  if (originalsOnly) where.push('a.is_original = 1');
  if (angle) { where.push('a.angle = ?'); args.push(angle); }
  // 读者按内容分类(genre,MECE)筛;angle 是采集配额概念,保留给运营用。
  const genre = q.get('genre');
  if (genre) { where.push('a.genre = ?'); args.push(genre); }
  // 地区筛(us/cn/eu/jk/me/sea/other):看某个地区发生了什么。
  const region = q.get('region');
  if (region) { where.push('a.region = ?'); args.push(region); }
  if (lang) { where.push('a.lang = ?'); args.push(lang); }
  if (domain) { where.push('a.domain = ?'); args.push(domain); }
  // Search has to hit both renderings: the timeline shows Chinese, so typing a
  // Chinese word must match, but a user pasting an English headline expects a
  // hit too.
  if (search) { where.push('(a.title LIKE ? OR a.title_zh LIKE ?)'); args.push(`%${search}%`, `%${search}%`); }
  // Source filter uses the curated seed list, not the learned score: a domain
  // needs ~20 observations before its score means anything, so scoring would
  // hide brand-new legitimate outlets. seed_type is known on day one.
  // 人工点过「信任」的域名同等待遇 —— 信任要有实际效果,不然按钮就是装饰。
  if (sources === 'known') where.push("(d.seed_type IN ('primary','wire') OR d.status = 'trusted')");
  else if (sources === 'curated') where.push("(d.seed_type IS NOT NULL OR d.status = 'trusted')");
  // Collapse a story to a single row — the earliest publisher — so a wire
  // story picked up by twenty aggregators doesn't bury everything else.
  // 代表行就是聚类头本身(head.cluster_id = 自己的 id),O(1) 判定;
  // 最新动态/转载数物化在头行(ingest 维护) —— 合并模式零相关子查询。
  // 2026-08-31 性能修复:此前三个每行子查询让 6 万行库上一次查询 ~1 秒,
  // 分类切换肉眼可感地卡;物化后同查询 ~20ms。
  // 头行判定用 is_original=1(真实列,可进部分索引),等价于 id=cluster_id。
  // 排序键直接用 cluster_latest 列:配合 idx_heads_latest 部分索引,
  // SQLite 按索引序扫描、凑满 LIMIT 早停 —— 不再对全命中集排序。
  if (collapse) where.push('a.is_original = 1');

  // 读者主路径(精选+合并)谓词与 idx_heads_latest 部分索引完全吻合时,
  // 用 INDEXED BY 钉死走它:按 cluster_latest 索引序扫描、凑满 LIMIT 早停,
  // 不给规划器机会去贪 idx_articles_read 的等值前缀再临时排序。
  const pinIndex = collapse && mode !== 'all' && vmin >= 2 ? 'INDEXED BY idx_heads_latest' : '';

  // 读者路径的行是**瘦身版**:不带 url(Google News 长链接高熵不可压,
  // 200 行拖 100KB+,是分类切换慢的最大头 —— 前端改走 /r/:id 302 跳转),
  // 也不带 publisher/lang/angle/评分等读者不消费的字段。
  // 2026-08-31 实测:瘦身+边缘缓存后 143KB → ~15KB。
  const rows = db.prepare(collapse ? `
    SELECT a.id, a.title, a.title_zh, a.domain, a.published_at, a.first_seen_at,
           a.is_original, a.cluster_id, a.value, a.genre, a.region, a.relevant,
           COALESCE(a.cluster_n, 1) AS cluster_size,
           COALESCE(a.cluster_latest, a.published_at) AS latest_at
    FROM articles a ${pinIndex} LEFT JOIN domains d ON d.domain = a.domain
    WHERE ${where.join(' AND ')}
    ORDER BY a.cluster_latest DESC
    LIMIT ?` : `
    SELECT a.id, a.url, a.title, a.title_zh, a.domain, a.publisher, a.published_at, a.first_seen_at,
           a.lang, a.angle, a.relevance, a.relevant, a.is_original, a.cluster_id,
           a.value, a.genre,
           d.score AS domain_score, d.seed_type, d.status AS domain_status,
           (SELECT COUNT(*) FROM articles b WHERE b.cluster_id = a.cluster_id) AS cluster_size,
           (SELECT MAX(b.published_at) FROM articles b WHERE b.cluster_id = a.cluster_id) AS latest_at
    FROM articles a LEFT JOIN domains d ON d.domain = a.domain
    WHERE ${where.join(' AND ')}
    ORDER BY a.published_at DESC, a.id DESC
    LIMIT ?`).all(...args, limit);
  return rows;
}

/**
 * So "am I running the latest code?" is answerable from the page itself.
 *
 * In a container the answer comes from APP_VERSION, baked in at build time.
 * The image deliberately contains no .git: on the deploy host the clone's
 * .git/config holds a GitHub token, and copying it in would weld that
 * credential into an image layer.
 */
let VERSION;
function version() {
  if (!VERSION) {
    let commit = process.env.APP_VERSION || 'unknown';
    let date = '';
    if (commit === 'unknown') {
      try {   // local development: read it straight from the checkout
        commit = execSync('git rev-parse --short HEAD', { cwd: ROOT }).toString().trim();
        date = execSync('git log -1 --format=%cI', { cwd: ROOT }).toString().trim();
      } catch { /* not a git checkout either — leave it unknown */ }
    }
    VERSION = { commit, date, startedAt: Date.now() };
  }
  return VERSION;
}

export function stats() {
  const db = getDb();
  const now = Date.now();
  const D = 864e5;
  const one = (sql, ...a) => db.prepare(sql).get(...a);
  const all = (sql, ...a) => db.prepare(sql).all(...a);

  // Capture latency is the headline metric, and an average hides the tail —
  // one shard stuck in a cold lane can sit at 40 minutes while the mean looks
  // fine. Percentiles are computed in SQL over the last 24h.
  const lag = 'CAST((first_seen_at - published_at) AS REAL)/60000.0';
  const pctile = (p) => one(`SELECT ${lag} v FROM articles
      WHERE first_seen_at > ? AND first_seen_at >= published_at
      ORDER BY (first_seen_at - published_at)
      LIMIT 1 OFFSET (SELECT CAST(COUNT(*) * ? AS INT) FROM articles
                      WHERE first_seen_at > ? AND first_seen_at >= published_at)`,
    now - D, p, now - D)?.v ?? null;

  // Keep the comparison independent: Techmeme-selected rows form part of the
  // reference and must not simultaneously grade themselves as candidates.
  // Exclude the whole story cluster: otherwise a wire copy can grade the same
  // editorial pick merely because the reference points at another member.
  // value_src also covers durable historical floors after a pml changes target.
  const recentEditorialRows = all(`SELECT a.value FROM articles a
    WHERE a.relevant = 1 AND a.published_at > ?
      AND COALESCE(a.value_src, '') != 'editorial'
      AND COALESCE(a.cluster_id, a.id) NOT IN (
        SELECT DISTINCT COALESCE(ra.cluster_id, ra.id)
        FROM editorial_references r
        JOIN articles ra ON ra.id = r.article_id
        WHERE r.source='techmeme'
      )`, now - 7 * D);
  const techmemeReferenceRows = all(`SELECT r.title, r.selected_at, r.first_seen_at,
                                            r.value, r.angle
    FROM editorial_references r
    WHERE r.source = 'techmeme' AND r.selected_at > ?`, now - 30 * D);

  return {
    now,
    totals: one('SELECT COUNT(*) articles, SUM(relevant) relevant, COUNT(DISTINCT domain) domains FROM articles'),
    last24h: one('SELECT COUNT(*) n FROM articles WHERE published_at > ?', now - D),
    lastHour: one('SELECT COUNT(*) n FROM articles WHERE published_at > ?', now - 36e5),
    seedTotal: one('SELECT COUNT(*) n FROM domains WHERE seed_type IS NOT NULL').n,

    // ---- 新（freshness） ----
    latency: one(`SELECT AVG(${lag}) avg_min, MIN(${lag}) min_min, MAX(${lag}) max_min
                  FROM articles WHERE first_seen_at > ? AND first_seen_at >= published_at`, now - D),
    latencyP: { p50: pctile(0.5), p90: pctile(0.9), p99: pctile(0.99) },
    latencyBuckets: all(`SELECT
        CASE WHEN ${lag} < 2 THEN '<2分' WHEN ${lag} < 5 THEN '2-5分'
             WHEN ${lag} < 10 THEN '5-10分' WHEN ${lag} < 30 THEN '10-30分'
             WHEN ${lag} < 60 THEN '30-60分' ELSE '>60分' END bucket,
        COUNT(*) n
      FROM articles WHERE first_seen_at > ? AND first_seen_at >= published_at
      GROUP BY bucket`, now - D),
    latencyByAngle: all(`SELECT angle, COUNT(*) n, AVG(${lag}) avg_min
      FROM articles WHERE first_seen_at > ? AND first_seen_at >= published_at
      GROUP BY angle ORDER BY avg_min DESC`, now - D),

    // ---- 准（precision） ----
    scoreHist: all(`SELECT relevance score, COUNT(*) n FROM articles
                    WHERE published_at > ? GROUP BY relevance ORDER BY relevance`, now - 7 * D),
    // hits = 判分依据(命中词;!前缀=黑名单扣分,~前缀=体裁噪音) —— 「为什么
    // 删/为什么收」直接看这一列,不用猜。
    lowScoreSamples: all(`SELECT id, url, title, title_zh, domain, relevance, angle, lang, hits, published_at
                          FROM articles WHERE relevant = 0 AND published_at > ?
                          ORDER BY published_at DESC LIMIT 25`, now - 2 * D),
    borderline: all(`SELECT id, url, title, title_zh, domain, relevance, angle, hits FROM articles
                     WHERE relevant = 1 AND relevance <= 4 AND published_at > ?
                     ORDER BY published_at DESC LIMIT 15`, now - 2 * D),

    // ---- 广（coverage） ----
    perHour: all(`SELECT (published_at/3600000)*3600000 h, COUNT(*) n
                  FROM articles WHERE published_at > ? GROUP BY h ORDER BY h`, now - D),
    perDay: all(`SELECT (published_at/86400000)*86400000 d, COUNT(*) n, SUM(relevant) rel,
                        COUNT(DISTINCT domain) domains
                 FROM articles WHERE published_at > ? GROUP BY d ORDER BY d`, now - 30 * D),
    since: one('SELECT MIN(published_at) t FROM articles').t,
    byAngle: all(`SELECT angle, COUNT(*) n, SUM(relevant) rel, COUNT(DISTINCT domain) domains
                  FROM articles WHERE published_at > ? GROUP BY angle ORDER BY n DESC`, now - 7 * D),
    byLang: all(`SELECT lang, COUNT(*) n, SUM(relevant) rel FROM articles
                 WHERE published_at > ? GROUP BY lang ORDER BY n DESC`, now - 7 * D),
    byLocale: all(`SELECT locale, COUNT(*) n, COUNT(DISTINCT domain) domains FROM articles
                   WHERE published_at > ? GROUP BY locale ORDER BY n DESC`, now - 7 * D),
    byAngleAll: all(`SELECT angle, COUNT(*) n, SUM(relevant) rel,
                            COUNT(DISTINCT domain) domains,
                            SUM(CASE WHEN published_at > ? THEN 1 ELSE 0 END) n24
                     FROM articles GROUP BY angle ORDER BY n DESC`, now - D),
    // 价值分布(7天,relevant=1):信噪比的直接读数。
    valueDist: all(`SELECT COALESCE(value, 1) v, COUNT(*) n,
                           SUM(CASE WHEN value_src = 'llm' THEN 1 ELSE 0 END) llm
                    FROM articles WHERE relevant = 1 AND published_at > ?
                    GROUP BY v ORDER BY v DESC`, now - 7 * D),
    editorialBenchmark: loadEditorialBenchmark(RAW, recentEditorialRows, {
      now, techmemeRows: techmemeReferenceRows,
    }),
    // MECE 内容分类(7天):按内容归档,一篇只属一类 —— 和 byAngle(查询配额)是两码事。
    byGenre: all(`SELECT COALESCE(genre, 'other') g, COUNT(*) n
                  FROM articles WHERE relevant = 1 AND published_at > ?
                  GROUP BY g ORDER BY n DESC`, now - 7 * D),
    // 高产低价值域名:自动静音候选,人在分析页一键处置。
    lowValueDomains: all(`SELECT a.domain, COUNT(*) n, ROUND(AVG(a.value), 2) av,
                                 d.seed_type, COALESCE(d.status, 'observing') status
                          FROM articles a LEFT JOIN domains d ON d.domain = a.domain
                          WHERE a.relevant = 1 AND a.value IS NOT NULL AND a.published_at > ?
                          GROUP BY a.domain
                          HAVING n >= 5 AND av < 1 AND status != 'muted'
                          ORDER BY n DESC LIMIT 12`, now - 7 * D),
    mutedCount: one("SELECT COUNT(*) n FROM domains WHERE status = 'muted'").n,
    translation: one(`SELECT COUNT(*) total,
                             COALESCE(SUM(CASE WHEN title_zh IS NOT NULL THEN 1 ELSE 0 END), 0) done
                      FROM articles WHERE relevant = 1`),

    // ---- 域名（the whole point of running this for weeks） ----
    typeMix: all(`SELECT COALESCE(d.seed_type, '未收录') type, COUNT(*) n,
                         COUNT(DISTINCT a.domain) domains
                  FROM articles a LEFT JOIN domains d ON d.domain = a.domain
                  WHERE a.published_at > ? GROUP BY type ORDER BY n DESC`, now - 7 * D),
    // 样本标题优先中文译文 —— 审核的人得先读得懂(2026-08-31 站长要求)。
    newDomains: all(`SELECT d.domain, d.seed_type, d.articles, d.first_seen_at,
                            (SELECT COALESCE(title_zh, title) FROM articles a WHERE a.domain = d.domain
                             ORDER BY published_at DESC LIMIT 1) sample
                     FROM domains d WHERE d.first_seen_at > ?
                     ORDER BY d.first_seen_at DESC LIMIT 30`, now - 2 * D),
    unlisted: all(`SELECT a.domain, COUNT(*) n, SUM(a.is_original) originals,
                          MAX(a.published_at) last,
                          (SELECT COALESCE(title_zh, title) FROM articles x WHERE x.domain = a.domain
                           ORDER BY published_at DESC LIMIT 1) sample
                   FROM articles a LEFT JOIN domains d ON d.domain = a.domain
                   WHERE d.seed_type IS NULL AND a.published_at > ?
                   GROUP BY a.domain ORDER BY n DESC LIMIT 25`, now - 7 * D),
    // Techmeme is a discovery/editorial layer, never the publisher. Keep its
    // picked downstream domains as the explicit queue for the later FT-style
    // search vs Bloomberg-style hub decision; creating crawlers stays manual.
    techmemeDomains: all(`SELECT r.domain,
                                (SELECT rr.publisher FROM editorial_references rr
                                 WHERE rr.source='techmeme' AND rr.domain=r.domain
                                 ORDER BY rr.selected_at DESC LIMIT 1) publisher,
                                COUNT(*) picks, MAX(r.selected_at) last_selected_at,
                                d.seed_type, COALESCE(d.status, 'observing') status,
                                (SELECT rr.title FROM editorial_references rr
                                 WHERE rr.source = 'techmeme' AND rr.domain = r.domain
                                 ORDER BY rr.selected_at DESC LIMIT 1) sample
      FROM editorial_references r LEFT JOIN domains d ON d.domain = r.domain
      WHERE r.source = 'techmeme' AND r.selected_at > ?
      GROUP BY r.domain ORDER BY picks DESC, last_selected_at DESC LIMIT 40`, now - 30 * D),
    breakers: all(`SELECT domain, COUNT(*) n, SUM(is_original) originals
                   FROM articles WHERE published_at > ? GROUP BY domain
                   HAVING n >= 2 ORDER BY originals DESC, n DESC LIMIT 20`, now - 7 * D),
    // 首发最快：只看真实竞争过的故事（同聚类 ≥2 家）。单人聚类人人都是"首发"，
    // 混进来会把榜单变成「谁的冷门文章多」。落后分钟只在输掉的场次上平均。
    fastestDomains: all(`SELECT a.domain, d.seed_type,
                                COUNT(*) contested,
                                SUM(a.is_original) wins,
                                CAST(SUM(a.is_original) AS REAL) / COUNT(*) win_rate,
                                AVG(CASE WHEN a.is_original = 0
                                     THEN (a.published_at - h.published_at) / 60000.0 END) behind_min
                         FROM articles a
                         JOIN articles h ON h.id = a.cluster_id
                         JOIN (SELECT cluster_id FROM articles
                               GROUP BY cluster_id HAVING COUNT(*) > 1) c
                           ON c.cluster_id = a.cluster_id
                         LEFT JOIN domains d ON d.domain = a.domain
                         GROUP BY a.domain
                         ORDER BY win_rate DESC, wins DESC LIMIT 10`),
    reprinters: all(`SELECT domain, COUNT(*) n, SUM(1 - is_original) reprints
                     FROM articles WHERE published_at > ? GROUP BY domain
                     HAVING reprints > 0 ORDER BY reprints DESC LIMIT 20`, now - 7 * D),
    topDomains: all(`SELECT a.domain, COUNT(*) n, SUM(a.relevant) rel, d.seed_type
                     FROM articles a LEFT JOIN domains d ON d.domain = a.domain
                     WHERE a.published_at > ? GROUP BY a.domain ORDER BY n DESC LIMIT 25`, now - 7 * D),
    topClusters: all(`SELECT cluster_id, COUNT(*) n, MIN(published_at) t,
                        (SELECT COALESCE(title_zh, title) FROM articles x WHERE x.id = a.cluster_id) title,
                        (SELECT url FROM articles x WHERE x.id = a.cluster_id) url,
                        (SELECT domain FROM articles x WHERE x.id = a.cluster_id) domain
                      FROM articles a WHERE published_at > ? GROUP BY cluster_id
                      HAVING n > 1 ORDER BY n DESC LIMIT 20`, now - 2 * D),

    // ---- 采集器 ----
    fetchTotals: one(`SELECT COUNT(*) runs,
        SUM(CASE WHEN status = 304 THEN 1 ELSE 0 END) notModified,
        SUM(CASE WHEN status = 200 THEN 1 ELSE 0 END) ok,
        SUM(CASE WHEN status IN (429, 403) THEN 1 ELSE 0 END) throttled,
        SUM(CASE WHEN (error IS NOT NULL OR status >= 400)
                  AND status NOT IN (429, 403) THEN 1 ELSE 0 END) errors,
        SUM(items) items, SUM(kept) kept, AVG(ms) ms
      FROM fetches WHERE started_at > ?`, now - D),
    throttlePerHour: all(`SELECT (started_at/3600000)*3600000 h,
        COUNT(*) runs, SUM(CASE WHEN status IN (429, 403) THEN 1 ELSE 0 END) throttled
      FROM fetches WHERE started_at > ? GROUP BY h ORDER BY h`, now - D),
    fetchPerHour: all(`SELECT (started_at/3600000)*3600000 h, COUNT(*) runs,
        SUM(CASE WHEN error IS NOT NULL OR status >= 400 THEN 1 ELSE 0 END) errors, SUM(kept) kept
      FROM fetches WHERE started_at > ? GROUP BY h ORDER BY h`, now - D),
    fetchErrors: all(`SELECT COALESCE(error, 'HTTP ' || status) reason, COUNT(*) n
      FROM fetches WHERE started_at > ? AND (error IS NOT NULL OR status >= 400)
      GROUP BY reason ORDER BY n DESC LIMIT 10`, now - D),
    fetches: all(`SELECT shard, MAX(started_at) last, AVG(ms) ms, SUM(kept) kept, SUM(items) items,
        SUM(CASE WHEN error IS NOT NULL OR status >= 400 THEN 1 ELSE 0 END) errors, COUNT(*) runs
      FROM fetches WHERE started_at > ? GROUP BY shard ORDER BY kept DESC`, now - D),
  };
}

/** Current scheduling rules + how each shard earned its lane. */
function rules() {
  const db = getDb();
  const shards = new Map(buildShards().map((s) => [s.id, s]));
  const rows = db.prepare('SELECT * FROM shard_policy').all();
  const now = Date.now();
  const merged = [...shards.values()].map((s) => {
    const p = rows.find((r) => r.shard === s.id);
    return {
      shard: s.id, group: s.group, angle: s.angle, locale: s.locale.id, q: s.q,
      base_lane: s.lane,
      lane: p?.lane || s.lane,
      pinned: p?.pinned ? 1 : 0,
      yield_rate: p?.yield_rate ?? 0,
      runs: p?.runs ?? 0,
      changed_at: p?.changed_at ?? null,
      reason: p?.reason ?? '尚未评估',
      moved: (p?.lane || s.lane) !== s.lane,
    };
  }).sort((a, b) => b.yield_rate - a.yield_rate);

  const events = db.prepare('SELECT * FROM lane_events ORDER BY at DESC LIMIT 120').all();
  const drift = db.prepare(`SELECT (at/3600000)*3600000 h,
      SUM(CASE WHEN to_lane='hot' THEN 1 ELSE 0 END) up_hot,
      SUM(CASE WHEN to_lane='cold' THEN 1 ELSE 0 END) down_cold,
      COUNT(*) n FROM lane_events WHERE at > ? GROUP BY h ORDER BY h`).all(now - 7 * 864e5);

  const counts = merged.reduce((a, r) => { a[r.lane] = (a[r.lane] || 0) + 1; return a; }, {});

  // Everything needed to explain the schedule on the page itself, computed
  // from the config actually in force rather than restated in prose.
  const perCycle = (counts.hot || 0) + CONFIG.warmPerCycle + CONFIG.coldPerCycle;
  const cycleMin = CONFIG.cycleMs / 60000;
  const schedule = {
    ...CONFIG,
    perCycle,
    reqPerMin: +(perCycle / cycleMin).toFixed(1),
    loopMin: {
      hot: cycleMin,
      warm: +((counts.warm || 0) / Math.max(1, CONFIG.warmPerCycle) * cycleMin).toFixed(1),
      cold: +((counts.cold || 0) / Math.max(1, CONFIG.coldPerCycle) * cycleMin).toFixed(1),
    },
  };

  // The keyword catalogue, grouped the way it is authored in keywords.js.
  const catalogue = GROUPS.map((g) => ({
    id: g.id, angle: g.angle, lane: g.lane, locales: g.locales, queries: g.queries,
    shards: merged.filter((m) => m.shard.startsWith(g.id + '#')),
  }));

  return { policy: POLICY, counts, shards: merged, events, drift, schedule, catalogue,
           locales: LOCALES.map((l) => ({ id: l.id, lang: l.lang, ceid: l.ceid })) };
}

function domains(q) {
  const db = getDb();
  const min = Number(q.get('min') || 1);
  const rows = db.prepare('SELECT * FROM domains WHERE articles >= ? ORDER BY articles DESC LIMIT 400').all(min);
  return rows.map((r) => ({ ...r, ...computeScore(r) })).sort((a, b) => b.score - a.score);
}

/**
 * The angle/language options the timeline's filters offer. Split out of
 * /api/stats when that endpoint moved behind the admin gate — a logged-out
 * reader still needs to filter the public timeline.
 */
function filters() {
  const db = getDb();
  const since = Date.now() - 7 * 864e5;
  return {
    angles: db.prepare('SELECT angle, COUNT(*) n FROM articles WHERE published_at > ? AND angle IS NOT NULL GROUP BY angle ORDER BY n DESC').all(since),
    langs: db.prepare('SELECT lang, COUNT(*) n FROM articles WHERE published_at > ? AND lang IS NOT NULL GROUP BY lang ORDER BY n DESC').all(since),
    // 读者筛选用的内容分类(MECE):只列默认视图会出现的(相关且价值≥2)。
    genres: db.prepare(`SELECT genre, COUNT(*) n FROM articles
                        WHERE published_at > ? AND relevant = 1 AND COALESCE(value, 1) >= 2
                          AND genre IS NOT NULL AND genre NOT IN ('noise')
                        GROUP BY genre ORDER BY n DESC`).all(since),
    regions: db.prepare(`SELECT region, COUNT(*) n FROM articles
                         WHERE published_at > ? AND relevant = 1 AND COALESCE(value, 1) >= 2
                           AND region IS NOT NULL
                         GROUP BY region ORDER BY n DESC`).all(since),
    // 今日各分类收录数(服务器本地零点起,次日天然清零) —— 给读者的当日概览。
    todayGenres: db.prepare(`SELECT genre, COUNT(*) n FROM articles
                             WHERE published_at > ? AND relevant = 1 AND COALESCE(value, 1) >= 2
                               AND genre IS NOT NULL AND genre NOT IN ('noise')
                             GROUP BY genre ORDER BY n DESC`).all(midnight()),
    todayTotal: db.prepare(`SELECT COUNT(*) n FROM articles
                            WHERE published_at > ? AND relevant = 1 AND COALESCE(value, 1) >= 2`)
      .get(midnight()).n,
  };
}

function midnight() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function translationStatus() {
  const db = getDb();
  return {
    provider: translatorName(),
    enabled: translatorEnabled(),
    translated: db.prepare('SELECT COUNT(*) n FROM articles WHERE title_zh IS NOT NULL').get().n,
    pending: db.prepare('SELECT COUNT(*) n FROM articles WHERE title_zh IS NULL').get().n,
    cached: db.prepare('SELECT COUNT(*) n FROM translations').get().n,
  };
}

async function serveStatic(req, res, pathname, root = WEB) {
  const rel = normalize(pathname.endsWith('/') ? pathname + 'index.html' : pathname).replace(/^(\.\.[/\\])+/, '');
  const file = join(root, rel);
  if (!file.startsWith(root)) { res.writeHead(403).end('forbidden'); return; }
  try {
    const buf = await readFile(file);
    res.writeHead(200, {
      'content-type': MIME[extname(file)] || 'application/octet-stream',
      // This is a local dev server whose assets change as we iterate. Without
      // this, a browser keeps serving yesterday's app.js from cache and the UI
      // silently lags the code.
      'cache-control': 'no-store, must-revalidate',
    });
    res.end(buf);
  } catch {
    res.writeHead(404, { 'content-type': 'text/plain' }).end('not found');
  }
}

let BUCKET = null;
/** The CLI hands the live token bucket over so the dashboard can show its state. */
export function setBucket(b) { BUCKET = b; }

export function createServer() {
  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://localhost');
    const send = (data, code = 200) => json(res, data, code);
    try {
      if (await handleAuth(req, res, u.pathname, send)) return;

      switch (u.pathname) {
        // Public by default: the timeline itself and the metadata the page needs
        // to draw its own chrome. Everything analytical sits behind the 管理
        // menu. With ST_REQUIRE_LOGIN=1 even these need an account.
        // 时间线允许边缘缓存(公开内容,CF 的 s-maxage 让近端 PoP 挡住重复
        // 请求 —— 对远离服务器的读者,这比任何 SQL 优化都值钱)。
        case '/api/timeline': requireReader(req);
          return json(res, { items: timeline(u.searchParams) }, 200, 'public, max-age=15, s-maxage=30');
        case '/api/filters':  requireReader(req); return json(res, filters());
        // 每日 Excel 明细:展示口径(价值≥2 + 首发),现场生成 —— 邮件里放的
        // 就是这个链接。公开:内容与公开时间线完全同源,只是换了个容器。
        case '/api/report.xlsx': {
          requireReader(req);
          const hours = Math.min(168, Math.max(1, Number(u.searchParams.get('hours')) || 24));
          const { buf } = reportXlsx({ hours });
          const day = new Date().toISOString().slice(0, 10);
          res.writeHead(200, {
            'content-type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'content-disposition': `attachment; filename="inews-${day}-${hours}h.xlsx"`,
            'cache-control': 'no-store',
          });
          return res.end(buf);
        }
        // /api/version is never gated: it is how a browser tells a stale cache
        // from a stale deploy, and it must answer on the login screen too.
        case '/api/version':  return json(res, version());
        case '/api/stats':    requireStaff(req); return json(res, stats());
        case '/api/throttle': requireStaff(req); return json(res, BUCKET ? BUCKET.state() : { unavailable: true });
        case '/api/domains':  requireStaff(req); return json(res, { domains: domains(u.searchParams) });
        case '/api/rules':    requireStaff(req); return json(res, rules());
        case '/api/translate': {
          const ctx = requireStaff(req);
          if (req.method !== 'POST') return json(res, translationStatus());
          requireCsrf(req, ctx);
          const done = await translatePending({ limit: 100, budgetMs: 20_000 });
          return json(res, { ...done, ...translationStatus() });
        }
        case '/api/pin': {
          const ctx = requireStaff(req);
          if (req.method !== 'POST') return json(res, { error: 'POST only' }, 405);
          requireCsrf(req, ctx);
          const shard = u.searchParams.get('shard');
          const lane = u.searchParams.get('lane');
          return json(res, { ok: pinShard(shard, lane === 'auto' ? null : lane) });
        }
        // 域名处置:trusted / muted / observing。muted 的文章从默认时间线消失。
        case '/api/domain-status': {
          const ctx = requireStaff(req);
          if (req.method !== 'POST') return json(res, { error: 'POST only' }, 405);
          requireCsrf(req, ctx);
          const domain = (u.searchParams.get('domain') || '').trim().toLowerCase();
          const status = u.searchParams.get('status');
          if (!domain || !['observing', 'trusted', 'muted'].includes(status)) {
            return json(res, { error: 'domain 与 status(observing|trusted|muted) 必填' }, 400);
          }
          const db = getDb();
          db.prepare(`INSERT INTO domains(domain, status) VALUES (?, ?)
                      ON CONFLICT(domain) DO UPDATE SET status = excluded.status`)
            .run(domain, status);
          audit({ actor: ctx.user, action: 'domain.status', target: domain, detail: status });
          return json(res, { ok: true, domain, status });
        }
        // LLM 价值精化:GET 看状态,POST 手动补跑一批(和补译同一套纪律)。
        case '/api/classify': {
          const ctx = requireStaff(req);
          const status = () => ({
            provider: classifierName(), enabled: classifierEnabled(),
            pending: getDb().prepare(
              "SELECT COUNT(*) n FROM articles WHERE relevant = 1 AND value_src = 'heur'").get().n,
          });
          if (req.method !== 'POST') return json(res, status());
          requireCsrf(req, ctx);
          const done = await classifyPending({ limit: 200, budgetMs: 25_000 });
          return json(res, { ...done, ...status() });
        }
        case '/api/cluster': {
          requireReader(req);
          const db = getDb();
          const id = Number(u.searchParams.get('id'));
          // 展开列表最新在上、最老垫底 —— 追一个故事时先看最新进展。
          return json(res, { items: db.prepare(
            'SELECT id,url,title,title_zh,domain,publisher,published_at,is_original FROM articles WHERE cluster_id = ? ORDER BY published_at DESC').all(id) });
        }
        default: {
          // /r/:id —— 文章跳转。时间线 payload 不再携带 Google News 长链接
          // (高熵不可压,是列表变慢的最大头),点击时 302 到真实地址。
          // 文章 URL 不可变,允许边缘长缓存。
          if (u.pathname.startsWith('/rawarticle/')) { requireStaff(req); return serveStatic(req, res, u.pathname.slice(11), RAW); }
          const m = u.pathname.match(/^\/r\/(\d+)$/);
          if (m) {
            const row = getDb().prepare('SELECT url FROM articles WHERE id = ?').get(Number(m[1]));
            if (!row) { res.writeHead(404).end('not found'); return; }
            res.writeHead(302, { location: row.url, 'cache-control': 'public, max-age=86400' }).end();
            return;
          }
          return serveStatic(req, res, u.pathname);
        }
      }
    } catch (e) {
      // HttpError carries an intended status (401/403/429…). Anything else is
      // a real fault and stays a 500 with its message.
      json(res, { error: String(e?.message || e) }, e instanceof HttpError ? e.status : 500);
    }
  });
  // Account bodies are capped at 16 KiB; legitimate clients do not need the
  // Node default of five minutes to finish headers or a request body.
  server.requestTimeout = 15_000;
  server.headersTimeout = 10_000;
  return server;
}
