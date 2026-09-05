// Polite, rate-limited fetching. Everything hits one host (news.google.com),
// so a single global token bucket + small concurrency + jitter is what keeps us
// off the throttle radar. Conditional GET (ETag / If-Modified-Since) means most
// polls cost a 304 with no body.

const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) ' +
  'Chrome/124.0 Safari/537.36 inews.today/0.1 (+personal news aggregator)';

/**
 * Token bucket with AIMD self-tuning.
 *
 * A fixed rate is a guess, and the wrong guess is expensive in both directions:
 * too fast earns 429s, too slow wastes freshness. So the refill rate halves on
 * every throttle signal and creeps back up while responses stay clean —
 * the same control loop TCP uses for congestion.
 */
export class TokenBucket {
  constructor({ capacity = 6, refillPerSec = 0.5, minRefill = 0.05 } = {}) {
    this.capacity = capacity;
    this.tokens = capacity;
    this.baseRefill = refillPerSec;
    this.refill = refillPerSec;
    this.minRefill = minRefill;
    this.last = Date.now();
    this.throttleEvents = 0;
  }

  /** Server pushed back: halve the rate immediately. */
  penalize() {
    this.throttleEvents++;
    this.refill = Math.max(this.minRefill, this.refill / 2);
    this.tokens = 0;   // drain, so the slowdown takes effect on the next request
    return this.refill;
  }

  /** A clean pass: creep back toward the configured rate. */
  recover() {
    if (this.refill >= this.baseRefill) return this.refill;
    this.refill = Math.min(this.baseRefill, this.refill + this.baseRefill * 0.1);
    return this.refill;
  }

  state() {
    return {
      refillPerSec: Math.round(this.refill * 1000) / 1000,
      basePerSec: this.baseRefill,
      reqPerMin: Math.round(this.refill * 60 * 10) / 10,
      throttled: this.refill < this.baseRefill,
      throttleEvents: this.throttleEvents,
    };
  }
  #tick() {
    const now = Date.now();
    this.tokens = Math.min(this.capacity, this.tokens + ((now - this.last) / 1000) * this.refill);
    this.last = now;
  }
  async take() {
    for (;;) {
      this.#tick();
      if (this.tokens >= 1) { this.tokens -= 1; return; }
      const waitMs = Math.ceil(((1 - this.tokens) / this.refill) * 1000);
      await sleep(waitMs);
    }
  }
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const jitter = (ms, pct = 0.3) => ms * (1 + (Math.random() * 2 - 1) * pct);

/**
 * Keep the useful part of Node fetch errors. `TypeError: fetch failed` is only
 * the wrapper; DNS/TCP/TLS details live in `cause` (for example
 * UND_ERR_CONNECT_TIMEOUT). Persisting the chain is what makes an outage
 * diagnosable after the process or container has gone away.
 */
export function errorDetail(error, maxLength = 500) {
  const parts = [];
  const seen = new Set();
  let current = error;
  while (current && !seen.has(current) && parts.length < 4) {
    seen.add(current);
    const message = String(current?.message || current).trim();
    const code = current?.code ? String(current.code).trim() : '';
    const detail = code && !message.includes(code) ? `${code}: ${message}` : message;
    if (detail && !parts.includes(detail)) parts.push(detail);
    current = current?.cause;
  }
  return (parts.join(' <- ') || 'unknown fetch error').slice(0, maxLength);
}

/** Run `fn` over `items` with bounded concurrency, preserving order of results. */
export async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let i = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    for (;;) {
      const idx = i++;
      if (idx >= items.length) return;
      out[idx] = await fn(items[idx], idx);
    }
  });
  await Promise.all(workers);
  return out;
}

/**
 * Conditional, retrying GET.
 * @returns {{status:number, body:string|null, etag:?string, lastModified:?string, ms:number}}
 */
export async function getText(url, { etag, lastModified, timeoutMs = 15000, retries = 2 } = {}) {
  const started = Date.now();
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), timeoutMs);
    try {
      const headers = { 'user-agent': UA, accept: 'application/rss+xml, application/xml;q=0.9, */*;q=0.8' };
      if (etag) headers['if-none-match'] = etag;
      if (lastModified) headers['if-modified-since'] = lastModified;
      const res = await fetch(url, { headers, signal: ac.signal, redirect: 'follow' });
      clearTimeout(timer);
      if (res.status === 304) {
        return { status: 304, body: null, etag, lastModified, ms: Date.now() - started };
      }
      // 429/403 mean "you are asking too often". Retrying triples the request
      // rate at exactly the wrong moment, so return immediately and let the
      // caller back off. Only genuine server faults are worth a retry.
      if (res.status === 429 || res.status === 403) {
        return {
          status: res.status, body: null, etag, lastModified, ms: Date.now() - started,
          throttled: true, retryAfterMs: parseRetryAfter(res.headers.get('retry-after')),
        };
      }
      if (res.status >= 500) {
        lastErr = new Error(`HTTP ${res.status}`);
        if (attempt < retries) { await sleep(jitter(1500 * 2 ** attempt)); continue; }
        return { status: res.status, body: null, etag, lastModified, ms: Date.now() - started };
      }
      const body = await res.text();
      return {
        status: res.status,
        body,
        etag: res.headers.get('etag') || null,
        lastModified: res.headers.get('last-modified') || null,
        ms: Date.now() - started,
      };
    } catch (err) {
      clearTimeout(timer);
      lastErr = err;
      if (attempt < retries) await sleep(jitter(1200 * 2 ** attempt));
    }
  }
  throw lastErr ?? new Error('fetch failed');
}

/** Retry-After is either seconds or an HTTP date. */
export function parseRetryAfter(v) {
  if (!v) return null;
  const secs = Number(v);
  if (Number.isFinite(secs)) return Math.max(0, secs * 1000);
  const at = Date.parse(v);
  return Number.isFinite(at) ? Math.max(0, at - Date.now()) : null;
}

export function googleNewsUrl({ q, locale, window = '1h' }) {
  const query = window ? `${q} when:${window}` : q;
  const p = new URLSearchParams({ q: query, hl: locale.hl, gl: locale.gl, ceid: locale.ceid });
  return `https://news.google.com/rss/search?${p}`;
}
