import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { compareProfiles, loadEditorialBenchmark, valueProfile } from '../src/lib/benchmark.js';

test('value profile is mutually exclusive and comparison has stable endpoints', () => {
  const a = valueProfile([0, 1, 2, 3]);
  assert.deepEqual(a.dist, [1, 1, 1, 1]);
  assert.equal(a.usefulRate, 0.5);
  assert.deepEqual(compareProfiles(a, a), {
    fit: 100, deviation: 0, usefulGap: 0, noiseGap: 0, status: 'aligned',
  });
  assert.equal(compareProfiles(valueProfile([3, 3]), valueProfile([0, 0])).fit, 0);
});

test('Bloomberg ledger becomes a rolling benchmark and keeps body quality context', () => {
  const root = mkdtempSync(join(tmpdir(), 'inews-benchmark-'));
  const dir = join(root, 'bloomberg', 'data');
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'ledger.json'), JSON.stringify({ entries: {
    a: { title: 'OpenAI opens a new AI data center', published_at: '2026-09-02', body_status: 'ok', score: 80 },
    b: { title: 'Nvidia launches new HBM platform', published_at: '2026-09-01', body_status: 'failed', score: 60 },
    old: { title: 'Old story', published_at: '2025-01-01', body_status: 'ok', score: 10 },
  } }));

  const out = loadEditorialBenchmark(root, [{ value: 3 }, { value: 2 }, { value: 0 }], {
    now: Date.parse('2026-09-03T12:00:00Z'), days: 30,
  });
  assert.equal(out.available, true);
  assert.equal(out.reference.total, 2, 'rolling window excludes stale entries');
  assert.equal(out.reference.bodyCoverage, 0.5);
  assert.equal(out.reference.scoreMedian, 60);
  assert.deepEqual(out.candidate.dist, [1, 0, 1, 1]);
  assert.equal(typeof out.comparison.fit, 'number');
});

test('missing ledger is non-fatal', () => {
  const out = loadEditorialBenchmark('/definitely/missing', []);
  assert.equal(out.available, false);
});

test('verified Techmeme selections extend the benchmark without claiming body coverage', () => {
  const now = Date.parse('2026-09-03T12:00:00Z');
  const out = loadEditorialBenchmark('/definitely/missing', [{ value: 2 }], {
    now,
    techmemeRows: [
      { title: 'Anthropic signs a $35B data center deal', value: 3, selected_at: now - 1_000 },
      { title: 'Nvidia launches a new HBM platform', value: 3, selected_at: now - 2_000 },
      { title: 'stale', value: 0, selected_at: now - 40 * 864e5 },
    ],
  });
  assert.equal(out.available, true);
  assert.equal(out.reference.total, 2);
  assert.equal(out.sources.bloomberg.total, 0);
  assert.equal(out.sources.bloomberg.bodyCoverage, 0);
  assert.equal(out.sources.techmeme.total, 2);
  assert.equal(out.method, 'bloomberg-body-plus-techmeme-selection-v2');
});

test('a missing mutable article value falls back to the editorial title projection', () => {
  const now = Date.parse('2026-09-03T12:00:00Z');
  const out = loadEditorialBenchmark('/definitely/missing', [], {
    now,
    techmemeRows: [{ title: 'OpenAI launches GPT-6', value: null, selected_at: now }],
  });
  assert.equal(out.reference.total, 1);
  assert.equal(out.reference.dist[3], 1);
  assert.equal(out.reference.dist[0], 0);
});

test('published safe projection is preferred over the private ledger', () => {
  const root = mkdtempSync(join(tmpdir(), 'inews-benchmark-projection-'));
  const dir = join(root, 'bloomberg');
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'editorial-reference.json'), JSON.stringify({ articles: [
    { title: 'Anthropic raises new funding', published_at: '2026-09-02', body_status: 'ok', score: 75 },
  ] }));
  const out = loadEditorialBenchmark(root, [{ value: 3 }], {
    now: Date.parse('2026-09-03T12:00:00Z'),
  });
  assert.equal(out.available, true);
  assert.match(out.path, /editorial-reference\.json$/);
  assert.equal(out.reference.total, 1);
});
