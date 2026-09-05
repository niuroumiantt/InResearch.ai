/**
 * Cheap, process-local overload protection for unauthenticated account routes.
 *
 * The durable SQLite limits deliberately key on an account/email. They cannot
 * stop a client that invents a new identifier for every request. This gate runs
 * before password hashing, mail and database writes, and adds an
 * account-independent per-IP/global ceiling plus an in-flight ceiling. Rate
 * checks may run before a request body is read; concurrency slots must only be
 * acquired after the bounded body is complete so slow clients cannot reserve
 * every expensive-work slot.
 *
 * It is intentionally not a replacement for the durable limits: a restart
 * clears this state, while the account lockouts in SQLite survive restarts.
 */
export class MemoryGate {
  constructor({ windowMs, perKey, global, concurrent, now = Date.now }) {
    for (const [name, value] of Object.entries({ windowMs, perKey, global, concurrent })) {
      if (!Number.isSafeInteger(value) || value <= 0) {
        throw new Error(`${name} must be a positive integer`);
      }
    }
    this.windowMs = windowMs;
    this.perKey = perKey;
    this.global = global;
    this.concurrent = concurrent;
    this.now = now;
    this.reset();
  }

  reset() {
    this.windowStartedAt = this.now();
    this.total = 0;
    this.byKey = new Map();
    this.inFlight = 0;
  }

  rollWindow() {
    const at = this.now();
    if (at < this.windowStartedAt || at - this.windowStartedAt >= this.windowMs) {
      this.reset();
    }
  }

  /** Count one request without reserving an expensive-work slot. */
  hit(key) {
    this.rollWindow();
    // Cap attacker-controlled map keys even if an upstream proxy forwards a
    // malformed value. The global count bounds the number of live entries too.
    const normalized = String(key || 'unknown').slice(0, 128);
    const keyHits = this.byKey.get(normalized) || 0;
    if (this.total >= this.global || keyHits >= this.perKey) return false;
    this.total += 1;
    this.byKey.set(normalized, keyHits + 1);
    return true;
  }

  /** Reserve only an in-flight slot; the caller must already have a full body. */
  acquire() {
    if (this.inFlight >= this.concurrent) return null;
    this.inFlight += 1;
    let released = false;
    return () => {
      if (released) return;
      released = true;
      this.inFlight = Math.max(0, this.inFlight - 1);
    };
  }

  /**
   * @returns {null | (() => void)} null when refused, otherwise an idempotent
   * release callback for the in-flight slot.
   */
  enter(key) {
    if (!this.hit(key)) return null;
    return this.acquire();
  }
}
