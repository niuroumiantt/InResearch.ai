import { getDb } from './db.js';

/**
 * Domain score, 0-100. Deliberately simple and explainable — it is meant to be
 * read next to the dashboard, and to keep improving as volume accumulates.
 *
 *   volume      0-20  how much AI news this domain actually carries (log scale)
 *   precision   0-30  share of its headlines that pass the relevance gate
 *   originality 0-30  share of stories it is FIRST on (vs. reprinting)
 *   speed       0-10  average head start over the rest of the cluster
 *   seed        0-10  prior from sources.seed.json (primary/wire > platform > relay)
 *
 * Confidence is low until ~20 observations; the UI shows it so you know which
 * scores to trust yet.
 */
const SEED_PRIOR = { primary: 10, wire: 9, platform: 5, relay: 1 };

export function computeScore(row) {
  const n = row.articles || 0;
  const volume = Math.min(20, Math.log10(1 + n) * 10);
  const precision = n ? (row.relevant / n) * 30 : 0;
  const originality = n ? (row.originals / n) * 30 : 0;
  const leadMin = row.lead_n ? row.lead_ms_sum / row.lead_n / 60000 : 0;
  const speed = Math.max(0, Math.min(10, 5 + leadMin / 12)); // +60min lead -> 10
  const seed = SEED_PRIOR[row.seed_type] ?? 4;
  const score = volume + precision + originality + speed + seed;
  return {
    score: Math.round(score * 10) / 10,
    parts: {
      volume: r(volume), precision: r(precision), originality: r(originality),
      speed: r(speed), seed,
    },
    confidence: Math.min(1, n / 20),
    leadMin: r(leadMin),
  };
}
const r = (x) => Math.round(x * 10) / 10;

export function rescoreAll() {
  const db = getDb();
  const rows = db.prepare('SELECT * FROM domains WHERE articles > 0').all();
  const upd = db.prepare('UPDATE domains SET score = ?, scored_at = ? WHERE domain = ?');
  const now = Date.now();
  for (const row of rows) upd.run(computeScore(row).score, now, row.domain);
  return rows.length;
}
