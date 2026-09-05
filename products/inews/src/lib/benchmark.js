import { readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { scoreValue } from './value.js';

const DAY = 86_400_000;

const num = (x) => x === null || x === undefined || x === ''
  ? null
  : Number.isFinite(Number(x)) ? Number(x) : null;
const rate = (n, total) => total ? +(n / total).toFixed(4) : 0;

function quantile(values, q) {
  const a = values.map(num).filter((x) => x !== null).sort((x, y) => x - y);
  if (!a.length) return null;
  return a[Math.min(a.length - 1, Math.floor((a.length - 1) * q))];
}

/** Four mutually exclusive editorial-value buckets, comparable across corpora. */
export function valueProfile(values) {
  const dist = [0, 0, 0, 0];
  for (const raw of values) {
    const v = Math.max(0, Math.min(3, Math.round(num(raw) ?? 0)));
    dist[v] += 1;
  }
  const total = values.length;
  return {
    total,
    dist,
    rates: dist.map((n) => rate(n, total)),
    mustReadRate: rate(dist[3], total),
    usefulRate: rate(dist[2] + dist[3], total),
    noiseRate: rate(dist[0], total),
  };
}

export function compareProfiles(reference, candidate) {
  if (!reference.total || !candidate.total) return { fit: null, deviation: null, status: 'no_data' };
  // Total-variation distance compares the whole 0/1/2/3 mix without double-counting.
  const deviation = reference.rates.reduce((sum, x, i) => sum + Math.abs(x - candidate.rates[i]), 0) / 2;
  const fit = Math.max(0, Math.round((1 - deviation) * 100));
  const usefulGap = +(candidate.usefulRate - reference.usefulRate).toFixed(4);
  const noiseGap = +(candidate.noiseRate - reference.noiseRate).toFixed(4);
  const status = fit >= 80 && usefulGap >= -0.10 && noiseGap <= 0.10 ? 'aligned' : 'tighten';
  return { fit, deviation: +deviation.toFixed(4), usefulGap, noiseGap, status };
}

function ledgerPath(rawRoot) {
  const candidates = [
    join(rawRoot, 'bloomberg', 'editorial-reference.json'),
    join(rawRoot, 'BLOOMBERG.COM', 'editorial-reference.json'),
    join(rawRoot, 'bloomberg', 'data', 'ledger.json'),
    join(rawRoot, 'BLOOMBERG.COM', 'data', 'ledger.json'),
  ];
  for (const path of candidates) {
    try { statSync(path); return path; } catch { /* try local/deploy spelling */ }
  }
  return candidates[0];
}

/**
 * Bloomberg supplies the full-article reference and Techmeme supplies an independent
 * editor-selected headline/reference set. The latter improves topic/type coverage but
 * never pretends that we fetched the downstream article body.
 */
export function loadEditorialBenchmark(rawRoot, candidateRows, {
  now = Date.now(), days = 30, techmemeRows = [],
} = {}) {
  const path = ledgerPath(rawRoot);
  let parsed = null;
  let updatedAt = null;
  let bloombergError = null;
  try {
    parsed = JSON.parse(readFileSync(path, 'utf8'));
    updatedAt = statSync(path).mtimeMs;
  } catch (error) {
    bloombergError = error?.code || 'invalid_ledger';
  }

  const all = parsed
    ? (Array.isArray(parsed.articles) ? parsed.articles : Object.values(parsed.entries || {}))
    : [];
  const cutoff = now - days * DAY;
  let rows = all.filter((x) => {
    const at = Date.parse(x.published_at || '');
    return Number.isFinite(at) && at >= cutoff && at <= now + DAY;
  });
  // A newly migrated ledger may not yet contain 30-day history. It is still a better
  // reference than showing no benchmark, and the window will fill on later daily runs.
  if (!rows.length) rows = all;

  const bloombergValues = rows.map((x) => scoreValue({
    title: x.title || x.title_zh || '', relevant: 1, relevance: 7,
  }).value);
  const techRows = techmemeRows.filter((x) => {
    const raw = x.selected_at ?? x.published_at;
    const at = typeof raw === 'number' ? raw : Date.parse(raw || '');
    return Number.isFinite(at) && at >= cutoff && at <= now + DAY;
  });
  const techmemeValues = techRows.map((x) => {
    const stored = num(x.value);
    return stored === null ? scoreValue({
      title: x.title || x.title_zh || '', angle: x.angle || '', relevant: 1, relevance: 7,
    }).value : stored;
  });
  const reference = valueProfile([...bloombergValues, ...techmemeValues]);
  const candidate = valueProfile((candidateRows || []).map((x) => x.value));
  const scores = rows.map((x) => x.score);
  const bodyOk = rows.filter((x) => x.body_status === 'ok').length;
  const techUpdated = Math.max(0, ...techRows.map((x) => num(x.first_seen_at) || 0));
  updatedAt = Math.max(updatedAt || 0, techUpdated) || null;

  return {
    available: Boolean(reference.total),
    reason: reference.total ? null : bloombergError || 'no_reference_rows',
    path,
    updatedAt,
    windowDays: days,
    reference: {
      ...reference,
      scoreP25: quantile(scores, 0.25),
      scoreMedian: quantile(scores, 0.5),
      bodyCoverage: rate(bodyOk, rows.length),
    },
    sources: {
      bloomberg: {
        ...valueProfile(bloombergValues),
        bodyCoverage: rate(bodyOk, rows.length),
        scoreP25: quantile(scores, 0.25),
        scoreMedian: quantile(scores, 0.5),
      },
      techmeme: valueProfile(techmemeValues),
    },
    candidate,
    comparison: compareProfiles(reference, candidate),
    method: 'bloomberg-body-plus-techmeme-selection-v2',
  };
}
