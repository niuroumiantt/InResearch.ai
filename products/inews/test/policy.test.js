import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DB = join(HERE, 'tmp-policy.sqlite3');
for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true });
process.env.INEWS_DB_PATH = DB;

const { getDb } = await import('../src/lib/db.js');
const { decide, observe, applyPolicy, pinShard, POLICY } = await import('../src/lib/policy.js');
const { selectShards, excludeMutedSources } = await import('../src/scheduler.js');

// runs = successful runs (the yield denominator); attempts = every request made
const base = { baseLane: 'warm', runs: 20, attempts: 20, kept: 0, errors: 0, throttles: 0,
  lastKept: 0, runsSinceChange: 20 };

test('a productive warm shard is promoted to hot', () => {
  const d = decide({ ...base, lane: 'warm', kept: 40 }); // 2.0/run
  assert.equal(d.lane, 'hot');
  assert.match(d.reason, /升档/);
});

test('a barren hot shard falls back to warm, not straight to cold', () => {
  const d = decide({ ...base, lane: 'hot', kept: 4 }); // 0.2/run
  assert.equal(d.lane, 'warm', 'one step at a time');
});

test('a barren warm shard settles in cold and stays there', () => {
  const d = decide({ ...base, lane: 'warm', kept: 1 }); // 0.05/run
  assert.equal(d.lane, 'cold');
  const stay = decide({ ...base, lane: 'cold', kept: 1 });
  assert.equal(stay.lane, 'cold', 'cold is the floor — never dropped entirely');
});

test('dead band prevents flapping around the threshold', () => {
  // 1.0/run sits between demoteHot(0.8) and promoteHot(1.5):
  // hot keeps hot, warm keeps warm. No oscillation.
  assert.equal(decide({ ...base, lane: 'hot', kept: 20 }).lane, 'hot');
  assert.equal(decide({ ...base, lane: 'warm', kept: 20 }).lane, 'warm');
});

test('dwell time blocks a move that is otherwise justified', () => {
  const d = decide({ ...base, lane: 'warm', kept: 40, runsSinceChange: 2 });
  assert.equal(d.lane, 'warm');
  assert.match(d.reason, /观察期/);
});

test('a burst promotes a cold shard immediately, ignoring dwell and sample size', () => {
  const d = decide({ ...base, lane: 'cold', runs: 1, kept: 6, lastKept: 6, runsSinceChange: 0 });
  assert.equal(d.lane, 'hot');
  assert.match(d.reason, /突发/);
});

test('a mostly-failing shard is demoted rather than hammered', () => {
  // 20 successes out of 40 attempts, 20 of which errored -> 50%+ error rate
  const d = decide({ ...base, lane: 'hot', attempts: 40, kept: 40, errors: 21 });
  assert.equal(d.lane, 'warm');
  assert.match(d.reason, /错误率/);
});

test('error-driven demotion respects the lane dwell period', () => {
  const d = decide({ ...base, lane: 'hot', attempts: 40, kept: 40, errors: 21, runsSinceChange: 2 });
  assert.equal(d.lane, 'hot');
  assert.match(d.reason, /观察期/);
});

test('a rate-limited shard is not demoted for producing nothing', () => {
  // Every request 429'd: no successful runs at all. Judging yield here would
  // read 0 and demote, slowing the shard exactly when it needs to recover.
  const d = decide({ ...base, lane: 'hot', runs: 0, attempts: 30, kept: 0, throttles: 30, runsSinceChange: 0 });
  assert.equal(d.lane, 'hot', 'lane is held until the shard can actually run');
  assert.match(d.reason, /限流/);
});

test('a throttle storm does not demote the whole fleet on error rate', () => {
  // 25 of 30 attempts were 429s. Error rate over judged attempts is 0.
  const d = decide({ ...base, lane: 'hot', runs: 5, attempts: 30, kept: 10, throttles: 25 });
  assert.equal(d.lane, 'hot');
  assert.doesNotMatch(d.reason, /错误率/);
});

test('a transport outage is classified separately from shard errors', () => {
  const db = getDb();
  const shard = 'transport.outage#en-US#0';
  const now = Date.now();
  const ins = db.prepare(
    'INSERT INTO fetches(shard, started_at, ms, status, items, fresh, kept, error) VALUES (?,?,?,?,?,?,?,?)',
  );
  for (let i = 0; i < 12; i++) {
    ins.run(shard, now - i * 1000, 35_000, 0, 0, 0, 0,
      'fetch failed <- UND_ERR_CONNECT_TIMEOUT: Connect Timeout Error');
  }
  const row = observe(now).find((r) => r.shard === shard);
  assert.equal(row.transport_errors, 12);
  assert.equal(row.errors, 0, 'fleet-wide transport failures are not bad-query evidence');

  const d = decide({
    ...base, lane: 'hot', runs: 0, attempts: 12, errors: row.errors,
    transportErrors: row.transport_errors, kept: 0, runsSinceChange: 20,
  });
  assert.equal(d.lane, 'hot');
  assert.match(d.reason, /网络不可用/);
});

test('yield is measured over successful runs, not attempts', () => {
  // 8 successes producing 16 articles = 2.0/run, despite 12 throttles alongside.
  const d = decide({ ...base, lane: 'warm', runs: 8, attempts: 20, kept: 16, throttles: 12, runsSinceChange: 20 });
  assert.equal(d.lane, 'hot', 'the failed attempts must not dilute a real yield');
});

test('an unproven shard keeps its declared lane', () => {
  const d = decide({ ...base, lane: 'hot', runs: 2, kept: 0 });
  assert.equal(d.lane, 'hot');
  assert.match(d.reason, /样本不足/);
});

test('applyPolicy records lane changes and honours pins', () => {
  const db = getDb();
  const shards = [
    { id: 'policy.cold#en-US#0', lane: 'hot', angle: 'policy' },
    { id: 'chips.hot#en-US#0', lane: 'cold', angle: 'chips' },
  ];
  const now = Date.now();
  const ins = db.prepare('INSERT INTO fetches(shard, started_at, ms, status, items, fresh, kept) VALUES (?,?,?,?,?,?,?)');
  for (let i = 0; i < 20; i++) {
    ins.run(shards[0].id, now - (20 - i) * 60_000, 200, 200, 5, 0, 0);  // policy: nothing
    ins.run(shards[1].id, now - (20 - i) * 60_000, 200, 200, 9, 9, 3);  // chips: busy
  }

  const lanes = applyPolicy(shards, now);
  assert.equal(lanes.get('policy.cold#en-US#0'), 'warm', 'quiet policy shard slows down');
  // Promotion is a ratchet: cold -> warm now, warm -> hot after it proves the
  // yield again from the faster lane. Only a burst skips the intermediate step.
  assert.equal(lanes.get('chips.hot#en-US#0'), 'warm', 'busy cold shard steps up one lane');

  for (let i = 0; i < 10; i++) {
    ins.run(shards[1].id, now + i * 60_000, 200, 200, 9, 9, 3);
  }
  const lanes2 = applyPolicy(shards, now + 11 * 60_000);
  assert.equal(lanes2.get('chips.hot#en-US#0'), 'hot', 'sustained yield earns the hot lane');

  const events = db.prepare('SELECT * FROM lane_events ORDER BY id').all();
  assert.equal(events.length, 3);
  assert.equal(events[0].from_lane, 'hot');
  assert.equal(events[0].to_lane, 'warm');
  assert.ok(events[0].reason.includes('降档'));

  // A human pin outranks the machine, and is logged too.
  assert.ok(pinShard('policy.cold#en-US#0', 'hot'));
  const after = applyPolicy(shards, now + 60_000);
  assert.equal(after.get('policy.cold#en-US#0'), 'hot', 'pin is not overridden');
  assert.equal(db.prepare('SELECT COUNT(*) n FROM lane_events').get().n, 4);
});

test('scheduler selects shards by live lane, not the declared one', () => {
  const shards = [
    { id: 'a', lane: 'cold' }, { id: 'b', lane: 'hot' },
    { id: 'c', lane: 'cold' }, { id: 'd', lane: 'cold' },
  ];
  const live = new Map([['a', 'hot'], ['b', 'cold'], ['c', 'cold'], ['d', 'cold']]);
  const picked = selectShards(shards, live).map((s) => s.id);
  assert.ok(picked.includes('a'), 'promoted shard is polled every cycle');
  assert.ok(!picked.slice(0, 1).includes('b'), 'demoted shard is no longer in the hot batch');
});

test('muted direct sources are removed before scheduling while search shards stay active', () => {
  const shards = [
    { id: 'search', lane: 'hot' },
    { id: 'feed:reddit', lane: 'warm', sourceDomain: 'reddit.com' },
    { id: 'feed:openai', lane: 'warm', sourceDomain: 'openai.com' },
  ];
  assert.deepEqual(excludeMutedSources(shards, new Set(['reddit.com'])).map((x) => x.id),
    ['search', 'feed:openai']);
});

test('policy thresholds keep a sane ordering', () => {
  assert.ok(POLICY.demoteHot < POLICY.promoteHot, 'hysteresis band exists');
  assert.ok(POLICY.demoteWarm < POLICY.promoteWarm);
  assert.ok(POLICY.promoteWarm < POLICY.demoteHot);
});
