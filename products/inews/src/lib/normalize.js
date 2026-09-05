import { decodeEntities } from './rss.js';

const PUBLIC_SUFFIX_2 = new Set([
  'co.uk', 'co.jp', 'co.kr', 'com.cn', 'com.tw', 'com.au', 'com.br', 'com.mx',
  'co.in', 'com.hk', 'com.sg', 'org.uk', 'net.cn', 'gov.cn', 'go.jp', 'go.kr',
  'or.kr', 'ne.jp', 'or.jp', 'ac.uk', 'com.es', 'co.il', 'com.ua',
]);

/** Registrable domain, e.g. https://a.b.reuters.com/x -> reuters.com */
export function registrableDomain(urlOrHost) {
  if (!urlOrHost) return '';
  let host = urlOrHost;
  try {
    if (/^https?:\/\//i.test(urlOrHost)) host = new URL(urlOrHost).hostname;
  } catch { /* fall through, treat as host */ }
  host = host.toLowerCase().replace(/^www\./, '').replace(/\.$/, '');
  const parts = host.split('.');
  if (parts.length <= 2) return host;
  const last2 = parts.slice(-2).join('.');
  if (PUBLIC_SUFFIX_2.has(last2)) return parts.slice(-3).join('.');
  // Keep known meaningful subdomains intact (they behave as separate sources).
  const KEEP = ['spectrum.ieee.org', 'asia.nikkei.com', 'watch.impress.co.jp', 'deepmind.google'];
  if (KEEP.includes(host)) return host;
  for (const k of KEEP) if (host.endsWith('.' + k)) return k;
  return last2;
}

/** Google News titles are "Real title - Publisher". Strip the publisher tail. */
export function stripPublisherSuffix(title, publisher) {
  let t = decodeEntities(title).trim();
  if (publisher) {
    const tail = new RegExp(`\\s[-–—|]\\s*${publisher.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*$`, 'i');
    t = t.replace(tail, '').trim();
  }
  // 中日站点爱在标题尾部挂竖线标签链:「…出海战队"|AI智能|B2B|财联社|Agent|营销」
  // 或站名/栏目名「… | セキュリティ対策Lab」。逐段剥掉尾部的短段(≤12 字):
  // 短段是标签/站名,长段才可能是标题正文;剥到正文剩不到 10 字就停手,防误伤。
  // 不碰开头的段 ——「Opinion | 正文」那种前缀标签是正文的一部分。
  for (;;) {
    const m = t.match(/^(.*[^|｜])\s*[|｜]\s*([^|｜]{1,12})$/u);
    if (!m || m[1].trim().length < 10) break;
    t = m[1].trim();
  }
  return t;
}

const PUNCT = /[\p{P}\p{S}]/gu;

/** Aggressive normalization used only for near-duplicate clustering. */
export function dedupeKey(title) {
  const base = decodeEntities(title)
    .toLowerCase()
    .normalize('NFKC')
    .replace(PUNCT, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  // CJK has no spaces: fall back to the raw compacted string.
  if (!/\s/.test(base)) return base.slice(0, 60);
  const STOP = new Set(['the', 'a', 'an', 'of', 'to', 'in', 'on', 'for', 'and', 'is', 'as', 'at', 'by', 'with', 'its']);
  return base.split(' ').filter((w) => w && !STOP.has(w)).slice(0, 12).join(' ');
}

/** Google News link -> publisher URL when it is trivially recoverable. */
export function unwrapGoogleLink(link) {
  if (!link) return link;
  try {
    const u = new URL(link);
    if (!/(^|\.)google\.com$/.test(u.hostname)) return link;
    const direct = u.searchParams.get('url') || u.searchParams.get('q');
    if (direct && /^https?:/.test(direct)) return direct;
  } catch { /* ignore */ }
  return link;
}

export function parseDate(s) {
  const t = Date.parse(s);
  return Number.isFinite(t) ? t : null;
}
