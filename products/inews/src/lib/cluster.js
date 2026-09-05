// 相似度聚类 —— 精确 dedupe_key 之外的第二道归并。
//
// 精确键只能聚「逐字转载」;同一事件的不同措辞报道(「豆包辟谣煮拖鞋」×3 家
// 各写各的标题,2026-08-31 站长实拍)聚不上。这里用标题的字符特征做相似判定:
// 中日韩取相邻两字组(bigram),拉丁取 ≥3 字母的小写词,合成一个 token 集合;
// 两个标题的**重叠系数** overlap = |A∩B| / min(|A|,|B|) ≥ 0.6 且共享 token
// ≥5 个,判为同一故事。用重叠系数而不是 Jaccard,是因为标题一长一短很常见
// (「官方辟谣了」vs 完整报道),按并集算会被长标题稀释。
//
// 阈值刻意偏严:错并(两条不同新闻进一个抽屉)比漏并伤害大 —— 漏并只是多
// 一行,错并会把不相关新闻藏进「+N 转载」里。

const STOP = new Set(['the', 'a', 'an', 'of', 'to', 'in', 'on', 'for', 'and',
  'is', 'as', 'at', 'by', 'with', 'its', 'after', 'over', 'says', 'new']);

/** 标题 → 特征 token 集合(CJK 按标点分段、段内取二字组 + 拉丁词)。
 *  必须分段:跨标点连出来的「鞋官」「谣建」是假词,会把真实重叠稀释到
 *  判不出来(2026-08-31 用豆包三标题实测过)。 */
export function titleTokens(title) {
  const t = String(title || '').toLowerCase().normalize('NFKC');
  const out = new Set();
  for (const seg of t.match(/[一-鿿぀-ヿ가-힯]+/g) || []) {
    for (let i = 0; i + 1 < seg.length; i++) out.add(seg[i] + seg[i + 1]);
  }
  for (const w of t.match(/[a-z][a-z0-9]{2,}/g) || []) if (!STOP.has(w)) out.add(w);
  return out;
}

/** 同题判定,双门槛(按真实样本校准):
 *  - 共享 ≥5 个 token 且重叠系数 ≥0.30 —— 中文同事件不同措辞的典型区间
 *    (豆包三标题实测 0.32~0.38;不同事件即使同主角也只共享 1~3 个);
 *  - 或共享 ≥4 个且系数 ≥0.55 —— 短标题高度重合。
 *  英文误并被 ≥5 共享词挡住:两条不同 OpenAI 新闻只共享 2~3 个词。 */
export function similar(a, b) {
  if (a.size < 5 || b.size < 5) return false;   // 标题太短,特征不足以下判断
  const [small, big] = a.size <= b.size ? [a, b] : [b, a];
  let inter = 0;
  for (const x of small) if (big.has(x)) inter++;
  const coeff = inter / small.size;
  return (inter >= 5 && coeff >= 0.30) || (inter >= 4 && coeff >= 0.55);
}

/**
 * 维护「近 36 小时聚类头」的内存索引,供一次 ingest 批量比对。
 * 头的数量在几百量级,逐条线性扫的成本可忽略。
 */
export function recentHeads(db, windowMs, now = Date.now()) {
  const rows = db.prepare(`SELECT id, title, published_at FROM articles
                           WHERE is_original = 1 AND published_at > ?
                           ORDER BY published_at DESC LIMIT 800`).all(now - windowMs);
  return rows.map((r) => ({ id: r.id, published_at: r.published_at, tokens: titleTokens(r.title) }));
}

/** 在头索引里找相似头;找不到返回 null。 */
export function findSimilarHead(heads, tokens) {
  for (const h of heads) if (similar(tokens, h.tokens)) return h;
  return null;
}
