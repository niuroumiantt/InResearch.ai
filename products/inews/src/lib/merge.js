// 跨语言并簇 —— 聚类的第三道归并,跑在译文上。
//
// 入库层的两道归并(精确键、标题特征相似)都作用于原文标题,同一事件的
// 中/日/英版本词面永远对不上 —— GitLab 财报三个语言版本各成一簇挂在
// 时间线上(2026-09-02 站长实拍)。译文落地后,所有头行都有了中文形态,
// 词面才第一次可比。
//
// 但词面在这里只配当候选筛,不配当判决:24h 全量仿真(4,645 头行)显示,
// 纯词面在中档重叠区真假混杂 —— 模板化句式(「X公司财报超预期」「获X美元
// 种子轮」「买入还是持有」)让不同主角的新闻假性相似,盘点体长标题还会把
// 不相关新闻链式串成一簇。所以照价值轴的既有分层拆两级:
//   词面筛(本文件)   高召回:相似判定 + 泛词过滤 + 稀有锚 + 盘点体排除;
//   LLM 裁决           高精度:逐对回答「是否同一事件」,只并确认的对。
// 没配 LLM 就一对都不并 —— 错并(不同新闻进一个抽屉)比漏并伤害大。
// 否决记入 merge_verdicts,同一对永不重问。

import { getDb } from './db.js';
import { titleTokens, similar } from './cluster.js';
import { classifierEnabled, llmJson } from './classify.js';

const WINDOW_MS = 36 * 60 * 60 * 1000;   // 与入库聚类同窗
// 盘点体(T早报/A股头条)一条标题装十条新闻,是链式错并的超级连接器。
const DIGEST_TOKENS = 40;
// 每个头最多提名这么多对(按重叠系数取最像的几个)。这是候选量的唯一闸门:
// 实测两天线上数据(1,235 / 4,574 个头)都稳定在 1,000-1,500 对,
// 否决又永久入缓存 —— 每天几十次小批裁决,成本可忽略。
const PER_HEAD = 3;
// 倒排索引里跳过特别大的桶。这种 token 是泛词(智能/人工/模型),两条只共享
// 泛词的标题过不了 similar() 的「≥5 个共享 token」;真同题的对总会在某个
// 小桶里碰上。跳过它们把比对量压到十万量级(实测 0.6 秒)。
const BUCKET_CAP_RATIO = 0.06;

const pairKey = (x, y) => (x < y ? `${x}:${y}` : `${y}:${x}`);

/**
 * 词面候选筛。返回 [{a, b}],a/b 是 {id, published_at, zh, tokens}。
 *
 * 只负责提名,不负责判决 —— 判决是 LLM 的事(见 mergeTranslatedPending)。
 * 这条分工是 2026-09-04 线上复盘换来的:早先这里还有一道「共享稀有 token
 * 作锚」的硬条件,想省下裁决开销,结果**与新闻热度成反比** —— 事件越大,
 * 它的专有词出现在越多标题里(当日 hugging 的 df=31),于是一个 token 都
 * 当不了锚,当天最大的事件(英伟达收购 Hugging Face,11 个重复头)一对候选
 * 都没提名。按当日频率判「泛词」也一样会误伤:三天实测里,泛词(智能 9.8%、
 * 人工 7.9%)天天都高,而大事件专有词是当天尖峰、隔天塌陷(博通 8.0%→0.1%)。
 * 所以这里不再拿频率当判据,只留量级封顶,把精度交给裁决层。
 */
export function mergeCandidates(db, { windowMs = WINDOW_MS, now = Date.now() } = {}) {
  const rows = db.prepare(`SELECT id, title, title_zh, published_at FROM articles
      WHERE is_original = 1 AND relevant = 1 AND published_at > ?`).all(now - windowMs);
  // 不再限定「至少一侧是译文」:入库层的相似度只比对最近 800 个头
  // (cluster.js recentHeads),按现在每天三千多个头算只够覆盖六小时,
  // 所以隔了半天才跟进的同语言报道同样漏在这里。当日 Hugging Face 那组
  // 就混着中文原生标题与译文,只收译文会留下一半重复卡片。
  const heads = rows.map((r) => ({
    id: r.id, published_at: r.published_at,
    zh: r.title_zh || r.title,
    tokens: titleTokens(r.title_zh || r.title),
  })).filter((h) => h.tokens.size <= DIGEST_TOKENS);

  const buckets = new Map();
  for (const h of heads) {
    for (const t of h.tokens) {
      let b = buckets.get(t);
      if (!b) buckets.set(t, b = []);
      b.push(h);
    }
  }

  // 每个头留下最像的几个对手(重叠系数排序),而不是把所有相似对一股脑送去
  // 裁决 —— 大事件下同题头两两组合是平方级的,封顶让预算与头数成正比。
  const bucketCap = Math.max(50, heads.length * BUCKET_CAP_RATIO);
  const best = new Map();      // headId -> [{ other, coeff }]
  const tested = new Set();
  const note = (h, other, coeff) => {
    let l = best.get(h.id);
    if (!l) best.set(h.id, l = []);
    l.push({ other, coeff });
  };
  for (const bucket of buckets.values()) {
    if (bucket.length > bucketCap) continue;
    for (let i = 0; i < bucket.length; i++) {
      for (let j = 0; j < i; j++) {
        const a = bucket[j], b = bucket[i];
        const key = pairKey(a.id, b.id);
        if (tested.has(key)) continue;
        tested.add(key);
        if (!similar(a.tokens, b.tokens)) continue;
        const [small, big] = a.tokens.size <= b.tokens.size ? [a.tokens, b.tokens] : [b.tokens, a.tokens];
        let inter = 0;
        for (const x of small) if (big.has(x)) inter++;
        const coeff = inter / small.size;
        note(a, b, coeff);
        note(b, a, coeff);
      }
    }
  }

  const byId = new Map(heads.map((h) => [h.id, h]));
  const picked = new Map();
  for (const [id, list] of best) {
    list.sort((p, q) => q.coeff - p.coeff);
    for (const { other } of list.slice(0, PER_HEAD)) {
      const key = pairKey(id, other.id);
      if (picked.has(key)) continue;
      const self = byId.get(id);
      picked.set(key, id < other.id ? { a: self, b: other } : { a: other, b: self });
    }
  }
  return [...picked.values()];
}

/**
 * 把两行所在的簇并成一簇:先各自解析到当前簇根,谁早谁当头
 * (cluster_id 的既有语义就是「簇里最早那行的 id」)。已同簇是无操作。
 */
export function applyMerge(db, idA, idB) {
  const get = db.prepare('SELECT id, cluster_id, published_at, domain FROM articles WHERE id = ?');
  const a = get.get(idA), b = get.get(idB);
  if (!a || !b) return false;
  const ra = get.get(a.cluster_id ?? a.id), rb = get.get(b.cluster_id ?? b.id);
  if (!ra || !rb || ra.id === rb.id) return false;
  const [w, l] = ra.published_at <= rb.published_at ? [ra, rb] : [rb, ra];
  db.exec('BEGIN');
  try {
    // 成员全体改指新头(旧头自己的 cluster_id 也指向旧头,一并被带走,
    // 所以任何行的 cluster_id 永远直指当前簇根,不会出现指针链)。
    db.prepare('UPDATE articles SET cluster_id = ? WHERE cluster_id = ?').run(w.id, l.id);
    db.prepare('UPDATE articles SET is_original = 0, cluster_latest = NULL, cluster_n = NULL WHERE id = ?')
      .run(l.id);
    db.prepare(`UPDATE articles SET
        cluster_latest = (SELECT MAX(b.published_at) FROM articles b WHERE b.cluster_id = articles.id),
        cluster_n = (SELECT COUNT(*) FROM articles b WHERE b.cluster_id = articles.id)
      WHERE id = ?`).run(w.id);
    // 首发头衔换人,域名榜的滚动计数跟着走,别让榜单口径漂移。
    db.prepare('UPDATE domains SET originals = MAX(originals - 1, 0) WHERE domain = ?').run(l.domain);
    db.exec('COMMIT');
  } catch (e) { db.exec('ROLLBACK'); throw e; }
  return true;
}

const PROMPT = `判断每一对新闻标题(A 与 B)是否在报道同一个事件 —— 同一主体做了同一件事,
不同语言、不同措辞的版本都算同一事件。只是话题相近、公司相同但事件不同、
同一主体的不同进展或后续报道,都不算。
拿不准就答 0:漏并只是多一行,错并会把不相关的新闻藏进「+N 转载」里。
只输出 JSON 数组,形如 [{"i":0,"s":1},...],s: 1=同一事件, 0=不是。`;

// 与 classify 同一课的教训:批太大 JSON 会被截断,小批 + 显式 max_tokens。
const BATCH = 15;

/**
 * 跑一轮并簇:筛候选 → 滤掉已裁决的对 → LLM 分批裁决 → 并确认的、记否决的。
 * 与翻译/精化同一条纪律:失败不致命,下一轮重试。
 * @returns {{merged:number, vetoed:number, pending:number, failed:number}}
 */
export async function mergeTranslatedPending({ limit = 60, budgetMs = 30_000, now = Date.now() } = {}) {
  const db = getDb();
  const stats = { merged: 0, vetoed: 0, pending: 0, failed: 0 };
  const seen = db.prepare('SELECT same FROM merge_verdicts WHERE pair = ?');
  const fresh = mergeCandidates(db, { now }).filter((p) => !seen.get(pairKey(p.a.id, p.b.id)));
  stats.pending = fresh.length;
  if (!classifierEnabled() || !fresh.length) return stats;

  const record = db.prepare('INSERT OR REPLACE INTO merge_verdicts(pair, same, at) VALUES (?,?,?)');
  const deadline = Date.now() + budgetMs;
  const todo = fresh.slice(0, limit);
  for (let i = 0; i < todo.length && Date.now() < deadline; i += BATCH) {
    const chunk = todo.slice(i, i + BATCH);
    const lines = chunk.map((p, idx) =>
      `${idx}\tA: ${p.a.zh.slice(0, 120)} ||| B: ${p.b.zh.slice(0, 120)}`).join('\n');
    try {
      const verdicts = await llmJson(PROMPT, lines);
      for (const v of verdicts) {
        const p = chunk[v.i];
        if (!p) continue;
        record.run(pairKey(p.a.id, p.b.id), v.s ? 1 : 0, Date.now());
        if (v.s) { if (applyMerge(db, p.a.id, p.b.id)) stats.merged++; }
        else stats.vetoed++;
        stats.pending--;
      }
    } catch (e) {
      stats.failed += chunk.length;
      stats.error = String(e.message || e);
      break;   // 供应商在拒绝我们,让下一轮重试,别捶
    }
  }
  return stats;
}
