// Batched, staggered sweep. Every cycle fires: all `hot` shards + a rotating
// slice of `warm` + a smaller rotating slice of `cold`. Requests are throttled
// by a shared token bucket and capped at low concurrency, so we never look like
// a burst scraper — but every hot angle is still re-checked once a minute,
// which is what makes the 5-minute freshness target reachable.

import { buildShards } from './config/keywords.js';
import { getDb } from './lib/db.js';
import { errorDetail, getText, googleNewsUrl, mapLimit, jitter, sleep } from './lib/fetcher.js';
import { ingestFeed, ingestItems } from './lib/ingest.js';
import { extractLinks, diffNewLinks } from './lib/watch.js';
import { rescoreAll } from './lib/domains.js';
import { applyPolicy } from './lib/policy.js';
import { translatePending, translatorEnabled, translatorName } from './lib/translate.js';
import { classifyPending, classifierEnabled, classifierName } from './lib/classify.js';
import { mergeTranslatedPending } from './lib/merge.js';
import { envNumber, envValue } from './lib/env.js';
import { parseTechmemeFeed, parseTechmemeRiver } from './lib/techmeme.js';

export const CONFIG = {
  cycleMs: envNumber('INEWS_COLLECTION_CYCLE_MS', { legacy: 'ST_CYCLE_MS', fallback: 60_000 }),
  concurrency: envNumber('INEWS_FETCH_CONCURRENCY', { legacy: 'ST_CONCURRENCY', fallback: 3 }),
  // 2026-08-31 三次提速跟随池子扩张:41 shard 时 4/1 → 102 时 8/3 →
  // 全量整合 news 仓库后 171 shard(66 个直连源 + 8 监控页)定格 10/5:
  // 温圈 ~6 分、冷圈 ~20 分,每轮 26 请求/分 = 令牌桶上限(36/分)的 72%。
  // 其中 feed/监控页不打 Google,对 GN 的实际压力只有一半左右;零限流史,
  // 真被限流令牌桶自动减半再爬升,不需要人工回调。
  warmPerCycle: envNumber('INEWS_WARM_SHARDS_PER_CYCLE', { legacy: 'ST_WARM', fallback: 10 }),
  coldPerCycle: envNumber('INEWS_COLD_SHARDS_PER_CYCLE', { legacy: 'ST_COLD', fallback: 5 }),
  window: envValue('INEWS_GOOGLE_NEWS_WINDOW', { legacy: 'ST_WINDOW', fallback: '1h' }),
  rescoreEveryCycles: 30,
};

const rotation = { warm: 0, cold: 0 };

function slice(arr, cursorKey, n) {
  if (!arr.length || n <= 0) return [];
  const out = [];
  for (let i = 0; i < Math.min(n, arr.length); i++) {
    out.push(arr[rotation[cursorKey] % arr.length]);
    rotation[cursorKey]++;
  }
  return out;
}

/**
 * @param all      every shard
 * @param laneOf   live lane per shard id (from policy.js); falls back to the
 *                 static lane declared in keywords.js on the very first cycle
 */
export function selectShards(all, laneOf = new Map()) {
  const lane = (s) => laneOf.get(s.id) || s.lane;
  const hot = all.filter((s) => lane(s) === 'hot');
  const warm = all.filter((s) => lane(s) === 'warm');
  const cold = all.filter((s) => lane(s) === 'cold');
  return [...hot, ...slice(warm, 'warm', CONFIG.warmPerCycle), ...slice(cold, 'cold', CONFIG.coldPerCycle)];
}

/** Manual/editorial mute applies before scheduling, including direct RSS/watch sources. */
export function excludeMutedSources(shards, mutedDomains) {
  const muted = mutedDomains instanceof Set ? mutedDomains : new Set(mutedDomains || []);
  return shards.filter((shard) => !shard.sourceDomain || !muted.has(shard.sourceDomain));
}

export async function pollShard(shard, bucket, { getTextFn = getText, sleepFn = sleep } = {}) {
  const db = getDb();
  const state = db.prepare('SELECT * FROM shard_state WHERE shard = ?').get(shard.id) || {};
  const now = Date.now();
  if (state.cooldown_until && state.cooldown_until > now) return null;

  await bucket.take();
  await sleepFn(jitter(250, 1)); // de-synchronize workers

  const started = Date.now();
  // 直连 feed / 监控页用自己的 URL;其余照旧由查询词构造 Google News RSS 地址。
  const url = shard.feedUrl || shard.watchUrl
    || googleNewsUrl({ q: shard.q, locale: shard.locale, window: CONFIG.window });
  let status = 0, err = null, stats = { items: 0, fresh: 0, kept: 0 };
  let etag = state.etag, lastModified = state.last_modified, fails = state.fails || 0;
  let throttled = false, retryAfterMs = null;
  let transportFailure = false;

  try {
    const res = await getTextFn(url, { etag, lastModified });
    status = res.status;
    if (res.status === 200 && res.body) {
      if (shard.watchUrl) {
        // 页面监控:HTML → 链接增量 → 伪 feed 条目。发布时间未知,记首见时刻。
        const links = extractLinks(res.body, shard.watchUrl);
        const fresh = diffNewLinks(getDb(), shard.id, links);
        stats = ingestItems(fresh.map((l) => ({
          title: l.title, link: l.link, guid: l.link,
          pubDate: new Date(started).toUTCString(),
          sourceName: '', sourceUrl: l.link, description: '',
        })), shard, started);
        stats.items = links.length;
      } else if (shard.feedFormat === 'techmeme-rss') {
        stats = ingestItems(parseTechmemeFeed(res.body).items, shard, started);
      } else if (shard.feedFormat === 'techmeme-river') {
        stats = ingestItems(parseTechmemeRiver(res.body).items, shard, started);
      } else {
        stats = ingestFeed(res.body, shard, started);
      }
      etag = res.etag; lastModified = res.lastModified; fails = 0;
    } else if (res.status === 304) {
      fails = 0;
    } else if (res.throttled) {
      throttled = true;
      retryAfterMs = res.retryAfterMs;
      bucket.penalize();   // slow the WHOLE collector, not just this shard
      fails++;
    } else {
      fails++;
    }
  } catch (e) {
    err = errorDetail(e);
    // A DNS/TCP/TLS outage is fleet-wide evidence, not evidence that this
    // particular shard is bad. Retry on the next bounded global cycle instead
    // of exponentially exiling every shard.
    transportFailure = status === 0;
    if (!transportFailure) fails++;
  }

  // Two different situations need two different cooldowns. A rate limit is
  // transient and applies to everything, so the shard waits minutes and the
  // global bucket does the real work. A shard-specific fault (bad query, dead
  // locale) deserves the long exponential exile.
  let cooldown = null;
  if (transportFailure) {
    cooldown = null;
  } else if (throttled) {
    cooldown = Date.now() + (retryAfterMs ?? Math.min(10 * 60_000, jitter(60_000 * 2 ** Math.min(3, fails - 1))));
  } else if (fails > 0) {
    cooldown = Date.now() + Math.min(30 * 60_000, jitter(30_000 * 2 ** (fails - 1)));
  }

  db.prepare(`INSERT INTO shard_state(shard, etag, last_modified, last_run_at, cooldown_until, fails)
              VALUES (?,?,?,?,?,?)
              ON CONFLICT(shard) DO UPDATE SET etag=excluded.etag, last_modified=excluded.last_modified,
                last_run_at=excluded.last_run_at, cooldown_until=excluded.cooldown_until, fails=excluded.fails`)
    .run(shard.id, etag ?? null, lastModified ?? null, started, cooldown, fails);

  db.prepare(`INSERT INTO fetches(shard, started_at, ms, status, items, fresh, kept, error)
              VALUES (?,?,?,?,?,?,?,?)`)
    .run(shard.id, started, Date.now() - started, status, stats.items, stats.fresh, stats.kept, err);

  return { shard: shard.id, status, ...stats, err, throttled };
}

export async function runCycle(bucket, shards = buildShards()) {
  // 明确静音的直连域名不再请求。过去 status=muted 只在页面隐藏，采集器仍每轮
  // 花请求抓 Reddit/内容农场；“不要展示”和“不要再爬”必须是两种真实状态。
  const muted = new Set(getDb().prepare("SELECT domain FROM domains WHERE status = 'muted'")
    .all().map((row) => row.domain));
  const active = excludeMutedSources(shards, muted);
  // Re-derive lanes from observed yield before every cycle. Cheap (one grouped
  // query) and it means a burst is acted on at the next poll, not the next day.
  const laneOf = applyPolicy(active);
  const picked = selectShards(active, laneOf);
  const results = await mapLimit(picked, CONFIG.concurrency, (s) => pollShard(s, bucket));
  return results.filter(Boolean);
}

export function startScheduler(bucket) {
  const shards = buildShards();
  let cycles = 0;
  let stopped = false;

  (async function loop() {
    while (!stopped) {
      const t0 = Date.now();
      try {
        const res = await runCycle(bucket, shards);
        const kept = res.reduce((a, r) => a + r.kept, 0);
        const errs = res.filter((r) => r.err || (r.status && r.status >= 400)).length;
        const throttles = res.filter((r) => r.throttled).length;
        if (!throttles) bucket.recover();
        const b = bucket.state();
        console.log(`[cycle ${++cycles}] shards=${res.length} kept=${kept} errors=${errs}`
          + (throttles ? ` 限流=${throttles} → 降速至 ${b.reqPerMin}/分` : '')
          + (!throttles && b.throttled ? ` 恢复中 ${b.reqPerMin}/分` : '')
          + ` ${Date.now() - t0}ms`);
        if (cycles % CONFIG.rescoreEveryCycles === 0) rescoreAll();

        // Translation runs after ingest, outside the fetch budget: it talks to
        // a different host, and a slow or throttled translator must never
        // delay the next collection cycle. Its own deadline keeps it inside
        // the gap between cycles.
        if (translatorEnabled()) {
          const t = await translatePending({ limit: 60, budgetMs: Math.max(5000, CONFIG.cycleMs * 0.6) })
            .catch((e) => ({ error: String(e?.message || e), done: 0, failed: 0, pending: '?' }));
          if (t.done || t.failed) {
            console.log(`[译 ${translatorName()}] 完成=${t.done} 失败=${t.failed} 待译=${t.pending}`
              + (t.error ? ` (${t.error})` : ''));
          }
        }
        // 价值精化与翻译同一纪律:另一台主机、自己的预算、失败不拖下一轮采集。
        if (classifierEnabled()) {
          const c = await classifyPending({ limit: 100, budgetMs: Math.max(5000, CONFIG.cycleMs * 0.4) })
            .catch((e) => ({ error: String(e?.message || e), done: 0, failed: 0, pending: '?' }));
          if (c.done || c.failed) {
            console.log(`[审 ${classifierName()}] 精化=${c.done} 失败=${c.failed} 待审=${c.pending}`
              + (c.error ? ` (${c.error})` : ''));
          }
          // 跨语言并簇要等译文与裁决方都在:放在翻译与精化之后,同一纪律。
          const m = await mergeTranslatedPending({ limit: 60, budgetMs: Math.max(5000, CONFIG.cycleMs * 0.3) })
            .catch((e) => ({ error: String(e?.message || e), merged: 0, vetoed: 0, pending: '?', failed: 0 }));
          if (m.merged || m.failed) {
            console.log(`[并 跨语言] 并簇=${m.merged} 否决=${m.vetoed} 待裁=${m.pending}`
              + (m.error ? ` (${m.error})` : ''));
          }
        }
      } catch (e) {
        console.error('[cycle] failed:', e?.message || e);
      }
      await sleep(Math.max(2000, jitter(CONFIG.cycleMs - (Date.now() - t0), 0.1)));
    }
  })();

  return () => { stopped = true; };
}
