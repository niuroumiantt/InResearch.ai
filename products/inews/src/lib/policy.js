// Adaptive lane assignment.
//
// The lanes in keywords.js are only a *starting guess*. What actually decides
// how often a shard is polled is its observed yield: how many new, relevant
// articles a single poll of that query brings back.
//
// A low-yield shard is not a low-value shard — "AI policy" may produce three
// stories a day, but each one matters. So we never stop polling it; we just
// stop paying 60-second attention to it, and hand that request budget to the
// lanes that are actually producing. When it wakes up (EU AI Act passes, a
// export-control rule drops), the burst rule promotes it back within one poll.
//
// Design constraints that keep this from thrashing:
//   - hysteresis: promote and demote thresholds are separated by a dead band
//   - dwell time: a shard must sit in its lane MIN_DWELL runs before moving
//   - burst override: a single unusually rich poll promotes immediately
//   - floor: nothing is ever dropped below `cold`; every angle keeps a heartbeat
//   - pinning: a human decision (pinned=1) is never overridden by the machine

import { getDb } from './db.js';
import { buildShards } from '../config/keywords.js';

export const POLICY = {
  windowMs: 24 * 60 * 60 * 1000, // observation window for yield
  minRuns: 6,                    // below this we don't trust the yield yet
  minDwellRuns: 8,               // runs to sit in a lane before it can change
  promoteHot: 1.5,               // kept-per-run to earn `hot`
  demoteHot: 0.8,                // fall below and `hot` is lost
  promoteWarm: 0.35,
  demoteWarm: 0.12,
  burstKept: 5,                  // one poll this rich -> straight to hot
  errorRate: 0.5,                // a mostly-failing shard is demoted, not retried hot
};

const LANES = ['cold', 'warm', 'hot'];
const rank = (l) => LANES.indexOf(l);

/** Observed yield for every shard over the recent window. */
export function observe(now = Date.now()) {
  const db = getDb();
  return db.prepare(`
    SELECT shard,
           -- Yield is judged over runs that actually completed. Counting failed
           -- requests in the denominator makes a rate-limited shard look
           -- unproductive, which demotes it, which slows it further — a spiral
           -- that turns a transient 429 storm into permanently cold lanes.
           SUM(CASE WHEN status IN (200, 304) THEN 1 ELSE 0 END) AS runs,
           COUNT(*)               AS attempts,
           SUM(kept)              AS kept,
           SUM(items)             AS items,
           MAX(started_at)        AS last_run,
           -- Throttles are counted separately: they are a global condition the
           -- token bucket already answers, not evidence this shard is broken.
           SUM(CASE WHEN status IN (429, 403) THEN 1 ELSE 0 END) AS throttles,
           -- status=0 means no HTTP response at all. Every shard uses the same
           -- Google host, so a DNS/TCP/TLS outage is fleet-wide transport
           -- trouble, not evidence that an individual query deserves demotion.
           SUM(CASE WHEN status = 0 AND error IS NOT NULL THEN 1 ELSE 0 END) AS transport_errors,
           SUM(CASE WHEN ((error IS NOT NULL AND status != 0) OR status >= 400)
                     AND status NOT IN (429, 403) THEN 1 ELSE 0 END) AS errors,
           (SELECT kept FROM fetches f2 WHERE f2.shard = f.shard
             AND f2.status IN (200, 304) ORDER BY started_at DESC LIMIT 1) AS last_kept
    FROM fetches f WHERE started_at > ?
    GROUP BY shard`).all(now - POLICY.windowMs);
}

/** Decide the lane a single shard should be in. Pure — easy to test. */
export function decide({ lane, baseLane, runs, attempts, kept, errors, throttles = 0,
                         transportErrors = 0, lastKept, runsSinceChange }) {
  const yieldRate = runs ? kept / runs : 0;              // over successful runs
  // Throttled attempts are excluded from the denominator too: during a rate
  // limit almost every attempt is a 429, and counting those would demote the
  // entire fleet for a condition none of the shards caused.
  const judged = Math.max(0, attempts - throttles - transportErrors);
  const errorRate = judged ? errors / judged : 0;
  const keep = (reason) => ({ lane, yieldRate, reason });

  if (lastKept >= POLICY.burstKept && lane !== 'hot') {
    return { lane: 'hot', yieldRate, reason: `突发：单轮 ${lastKept} 条` };
  }
  if (runs < POLICY.minRuns) {
    if (throttles > runs) return keep(`被限流（${throttles}/${attempts} 次），暂不评估`);
    if (transportErrors > runs) return keep(`网络不可用（${transportErrors}/${attempts} 次），暂不评估`);
    return keep(errors > runs
      ? `请求多在失败（成功 ${runs} / 尝试 ${attempts}），暂不评估`
      : `样本不足（${runs}/${POLICY.minRuns} 轮）`);
  }
  // Error-driven demotion is still a lane change and must respect the same
  // dwell period as yield-driven changes. Otherwise one outage can step a
  // shard hot -> warm -> cold on consecutive policy passes.
  if (runsSinceChange < POLICY.minDwellRuns) return keep(`观察期（${runsSinceChange}/${POLICY.minDwellRuns} 轮）`);
  if (errorRate > POLICY.errorRate && lane !== 'cold') {
    return { lane: LANES[Math.max(0, rank(lane) - 1)], yieldRate, reason: `错误率 ${(errorRate * 100) | 0}%` };
  }

  const y = yieldRate;
  let target = lane;
  if (lane === 'hot') target = y < POLICY.demoteHot ? 'warm' : 'hot';
  else if (lane === 'warm') target = y >= POLICY.promoteHot ? 'hot' : (y < POLICY.demoteWarm ? 'cold' : 'warm');
  else target = y >= POLICY.promoteWarm ? 'warm' : 'cold';

  if (target === lane) return keep(`稳定（产出 ${y.toFixed(2)} 条/轮）`);
  const dir = rank(target) > rank(lane) ? '升档' : '降档';
  return { lane: target, yieldRate, reason: `${dir}：产出 ${y.toFixed(2)} 条/轮` };
}

/**
 * Recompute lanes for all shards and log every change.
 * @returns {Map<string,string>} shard id -> lane in force
 */
export function applyPolicy(shards, now = Date.now()) {
  const db = getDb();
  const stats = new Map(observe(now).map((r) => [r.shard, r]));
  const current = new Map(db.prepare('SELECT * FROM shard_policy').all().map((r) => [r.shard, r]));

  const upsert = db.prepare(`INSERT INTO shard_policy(shard, base_lane, lane, pinned, yield_rate, runs, changed_at, reason)
    VALUES (?,?,?,0,?,?,?,?)
    ON CONFLICT(shard) DO UPDATE SET base_lane=excluded.base_lane, lane=excluded.lane,
      yield_rate=excluded.yield_rate, runs=excluded.runs, changed_at=excluded.changed_at, reason=excluded.reason`);
  const logEvent = db.prepare(`INSERT INTO lane_events(shard, at, from_lane, to_lane, reason, yield_rate, runs)
    VALUES (?,?,?,?,?,?,?)`);
  const runsSince = db.prepare(
    'SELECT COUNT(*) n FROM fetches WHERE shard = ? AND started_at > ? AND status IN (200, 304)');

  const out = new Map();
  for (const s of shards) {
    const p = current.get(s.id);
    const st = stats.get(s.id) || {
      runs: 0, attempts: 0, kept: 0, errors: 0, throttles: 0, transport_errors: 0, last_kept: 0,
    };
    const lane = p?.lane || s.lane;

    if (p?.pinned) { out.set(s.id, lane); continue; }

    const since = p?.changed_at ? runsSince.get(s.id, p.changed_at).n : (st.runs || 0);
    const d = decide({
      lane, baseLane: s.lane, runs: st.runs || 0, attempts: st.attempts || 0,
      kept: st.kept || 0, errors: st.errors || 0, throttles: st.throttles || 0,
      transportErrors: st.transport_errors || 0,
      lastKept: st.last_kept || 0, runsSinceChange: since,
    });

    const changed = d.lane !== lane;
    upsert.run(s.id, s.lane, d.lane, d.yieldRate, st.runs || 0,
      changed || !p ? now : p.changed_at, d.reason);
    if (changed) logEvent.run(s.id, now, lane, d.lane, d.reason, d.yieldRate, st.runs || 0);
    out.set(s.id, d.lane);
  }
  return out;
}

/** Human override from the dashboard. lane=null clears the pin. */
export function pinShard(shard, lane, now = Date.now()) {
  const db = getDb();
  let p = db.prepare('SELECT * FROM shard_policy WHERE shard = ?').get(shard);
  if (!p) {
    // Pinning before the first policy pass has run: materialize the row from
    // the declared config so the dashboard works on a cold database.
    const s = buildShards().find((x) => x.id === shard);
    if (!s) return false;
    db.prepare('INSERT INTO shard_policy(shard, base_lane, lane, changed_at, reason) VALUES (?,?,?,?,?)')
      .run(s.id, s.lane, s.lane, now, '尚未评估');
    p = db.prepare('SELECT * FROM shard_policy WHERE shard = ?').get(shard);
  }
  if (lane == null) {
    db.prepare('UPDATE shard_policy SET pinned = 0, reason = ? WHERE shard = ?').run('已解除锁定', shard);
    return true;
  }
  if (!LANES.includes(lane)) return false;
  db.prepare('UPDATE shard_policy SET lane = ?, pinned = 1, changed_at = ?, reason = ? WHERE shard = ?')
    .run(lane, now, '人工锁定', shard);
  db.prepare('INSERT INTO lane_events(shard, at, from_lane, to_lane, reason, yield_rate, runs) VALUES (?,?,?,?,?,?,?)')
    .run(shard, now, p.lane, lane, '人工锁定', p.yield_rate, p.runs);
  return true;
}
