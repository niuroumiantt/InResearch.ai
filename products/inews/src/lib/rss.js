// Minimal RSS 2.0 + Atom parser. Google News' feed is small and extremely
// regular; direct feeds (lab blogs, regulators) add Atom to the menu.
// Dependency-free keeps the whole project at zero npm installs.

const ENTITIES = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", '#39': "'", nbsp: ' ',
  bull: '•', middot: '·', ldquo: '“', rdquo: '”', lsquo: '‘', rsquo: '’',
  ndash: '–', mdash: '—', hellip: '…', pound: '£', euro: '€', yen: '¥',
  laquo: '«', raquo: '»', copy: '©', reg: '®', trade: '™',
  eacute: 'é', egrave: 'è', ecirc: 'ê', aacute: 'á', agrave: 'à',
  iacute: 'í', oacute: 'ó', uacute: 'ú', ntilde: 'ñ', ccedil: 'ç',
};

export function decodeEntities(s) {
  return s
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&([a-z]+|#\d+);/gi, (m, n) => ENTITIES[n.toLowerCase()] ?? m);
}

function unwrap(raw) {
  const m = raw.match(/^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$/);
  return decodeEntities((m ? m[1] : raw).trim());
}

/** First child element `tag` of `xml`; returns {text, attrs} or null. */
function tag(xml, name) {
  const re = new RegExp(`<${name}(\\s[^>]*)?(?:/>|>([\\s\\S]*?)</${name}>)`, 'i');
  const m = xml.match(re);
  if (!m) return null;
  const attrs = {};
  for (const a of (m[1] || '').matchAll(/([\w:-]+)\s*=\s*"([^"]*)"/g)) attrs[a[1]] = decodeEntities(a[2]);
  return { text: m[2] == null ? '' : unwrap(m[2]), attrs };
}

export function parseFeed(xml) {
  const items = [];
  for (const m of xml.matchAll(/<item\b[^>]*>([\s\S]*?)<\/item>/gi)) {
    const body = m[1];
    const title = tag(body, 'title');
    const link = tag(body, 'link');
    const pub = tag(body, 'pubDate');
    const guid = tag(body, 'guid');
    const src = tag(body, 'source');
    const desc = tag(body, 'description');
    if (!title?.text) continue;
    items.push({
      title: title.text,
      link: link?.text || link?.attrs?.href || '',
      guid: guid?.text || '',
      pubDate: pub?.text || '',
      sourceName: src?.text || '',
      sourceUrl: src?.attrs?.url || '',
      description: desc?.text || '',
    });
  }
  if (items.length) return { items };

  // Atom(官方博客的主流形状):<entry> + <link href> + <updated>/<published>。
  // 只在没有任何 <item> 时才按 Atom 解析 —— 两种形状不会混在同一份文档里。
  for (const m of xml.matchAll(/<entry\b[^>]*>([\s\S]*?)<\/entry>/gi)) {
    const body = m[1];
    const title = tag(body, 'title');
    if (!title?.text) continue;
    // Atom 可以有多个 link:优先 rel="alternate"(或无 rel),忽略 self/edit。
    let href = '';
    for (const lm of body.matchAll(/<link\b([^>]*)\/?>(?:<\/link>)?/gi)) {
      const attrs = {};
      for (const a of lm[1].matchAll(/([\w:-]+)\s*=\s*"([^"]*)"/g)) attrs[a[1]] = decodeEntities(a[2]);
      if (!attrs.rel || attrs.rel === 'alternate') { href = attrs.href || ''; if (href) break; }
    }
    items.push({
      title: title.text,
      link: href,
      guid: tag(body, 'id')?.text || href,
      pubDate: tag(body, 'published')?.text || tag(body, 'updated')?.text || '',
      sourceName: '',
      sourceUrl: '',
      description: tag(body, 'summary')?.text || tag(body, 'content')?.text || '',
    });
  }
  return { items };
}
