import { test } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryGate } from '../src/auth/gate.js';

test('anonymous auth gate limits each IP without growing an unbounded key map', () => {
  let now = 1_000;
  const gate = new MemoryGate({
    windowMs: 1_000, perKey: 2, global: 3, concurrent: 3, now: () => now,
  });

  gate.enter('one')();
  gate.enter('one')();
  assert.equal(gate.enter('one'), null, 'one IP cannot rotate account identifiers for more budget');
  gate.enter('two')();
  assert.equal(gate.enter('three'), null, 'rotating IPs cannot bypass the global ceiling');
  assert.equal(gate.byKey.size, 2, 'denied attacker keys are never retained');

  now += 1_000;
  assert.equal(typeof gate.enter('one'), 'function', 'a new window restores the budget');
});

test('anonymous auth gate releases concurrency exactly once', () => {
  const gate = new MemoryGate({
    windowMs: 1_000, perKey: 10, global: 10, concurrent: 1,
  });
  const release = gate.enter('one');
  assert.equal(gate.enter('two'), null);
  release();
  release();
  assert.equal(typeof gate.enter('two'), 'function');
});

test('rate budget and expensive-work concurrency can be acquired separately', () => {
  const gate = new MemoryGate({
    windowMs: 1_000, perKey: 2, global: 2, concurrent: 1,
  });
  assert.equal(gate.hit('slow-body'), true);
  assert.equal(gate.inFlight, 0, 'reading a request body must not reserve PBKDF2 work');
  const release = gate.acquire();
  assert.equal(typeof release, 'function');
  assert.equal(gate.acquire(), null);
  release();
});
