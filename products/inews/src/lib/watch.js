// 通道③:页面监控(links 模式)。
//
// 有些高价值源没有 RSS(工信部、NIST、欧盟 AI Office、Epoch…)。办法承自
// niuroumiantt/news:定期抓页面 HTML,提取链接列表,和上次见过的比 ——
// **新出现的链接就是新文章**,标题取锚文本,进和 feed 一样的入库闸门。
// 首次抓取只建基线不入库(不然整页历史链接会灌进时间线);之后每轮只收增量。

import { decodeEntities } from './rss.js';

/** 从 HTML 里提取候选文章链接。锚文本就是标题,太短的是导航,不要。 */
export function extractLinks(html, baseUrl) {
  const base = new URL(baseUrl);
  const out = new Map();   // url -> title(同链接取最长的锚文本)
  for (const m of html.matchAll(/<a\b[^>]*href\s*=\s*"([^"#]+)"[^>]*>([\s\S]*?)<\/a>/gi)) {
    let url;
    try { url = new URL(m[1], base); } catch { continue; }
    if (url.host !== base.host) continue;                    // 站外链接是广告/分享,不要
    if (!/^https?:$/.test(url.protocol)) continue;
    const text = decodeEntities(m[2].replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
    // 标题门槛:拉丁 ≥ 24 字符或 CJK ≥ 8 字 —— 「更多」「下一页」这类导航过不了。
    const cjk = (text.match(/[一-鿿぀-ヿ가-힯]/g) || []).length;
    if (cjk < 8 && text.length < 24) continue;
    const key = url.href.replace(/[?#].*$/, '');
    if (!out.has(key) || out.get(key).length < text.length) out.set(key, text);
  }
  return [...out.entries()].map(([link, title]) => ({ link, title }));
}

/**
 * 对比已见集合,返回本轮新增的链接(并记住全部)。
 * 首轮(该 shard 从没见过任何链接)只建基线,返回空 —— 页面存量不是新闻。
 * 单轮新增超过 cap 视为页面改版,同样只更新基线不入库。
 */
export function diffNewLinks(db, shardId, links, { cap = 30 } = {}) {
  const seen = new Set(db.prepare('SELECT url FROM watch_seen WHERE shard = ?')
    .all(shardId).map((r) => r.url));
  const ins = db.prepare('INSERT OR IGNORE INTO watch_seen(shard, url) VALUES (?, ?)');
  const fresh = links.filter((l) => !seen.has(l.link));
  for (const l of fresh) ins.run(shardId, l.link);
  if (seen.size === 0) return [];          // 基线轮
  if (fresh.length > cap) return [];       // 页面改版/解析漂移,宁可漏过别灌错
  return fresh;
}
