// 文章 → 地区(读者视角的七分法:美国/中国/欧洲/日韩/中东/东南亚/其他)。
//
// 2026-08-31 站长:标题统一中文之后「按语言筛」失去意义,读者想看的是
// 「某个地区发生了什么」。判定用两级信号:域名顶级后缀最可信(.jp 就是
// 日本媒体),没有国家后缀的(.com/.ai)退回「哪个语区的 Google News 版本
// 抓到它」。粗,但对新闻流够用;errare 的代价只是进错筛选桶。

const TLD_REGION = {
  cn: 'cn', tw: 'cn', hk: 'cn', mo: 'cn',
  jp: 'jk', kr: 'jk',
  uk: 'eu', fr: 'eu', de: 'eu', es: 'eu', it: 'eu', nl: 'eu', eu: 'eu',
  ie: 'eu', se: 'eu', ch: 'eu', pl: 'eu', at: 'eu', be: 'eu', fi: 'eu',
  no: 'eu', dk: 'eu', pt: 'eu', cz: 'eu', gr: 'eu',
  sg: 'sea', my: 'sea', id: 'sea', th: 'sea', ph: 'sea', vn: 'sea',
  ae: 'me', sa: 'me', il: 'me', qa: 'me', tr: 'me', eg: 'me',
  us: 'us', ca: 'us',
  in: 'other', au: 'other', nz: 'other', za: 'other', br: 'other', mx: 'other',
};

// 兼容长短两种写法:ingest 存 'ko-KR',老数据/种子存 'ko'。
const LOCALE_REGION = {
  'en-US': 'us', 'zh-CN': 'cn', 'zh-TW': 'cn', 'ja-JP': 'jk', 'ko-KR': 'jk',
  'en-GB': 'eu', 'fr-FR': 'eu', 'es-ES': 'eu', 'de-DE': 'eu', 'en-IN': 'other',
  en: 'us', zh: 'cn', ja: 'jk', ko: 'jk', fr: 'eu', es: 'eu', de: 'eu',
};

export const REGIONS = ['us', 'cn', 'eu', 'jk', 'me', 'sea', 'other'];

export function regionOf(domain, localeId) {
  const tld = String(domain || '').split('.').pop().toLowerCase();
  return TLD_REGION[tld] || LOCALE_REGION[localeId] || 'other';
}

/** 每次启动全量重算 region:映射表升级追溯生效(和词表同一哲学),
 *  纯查表 6 万行一秒级,只写有变化的行。 */
export function backfillRegions(db) {
  const rows = db.prepare('SELECT id, domain, locale, region FROM articles').all();
  const upd = db.prepare('UPDATE articles SET region = ? WHERE id = ?');
  let changed = 0;
  db.exec('BEGIN');
  try {
    for (const r of rows) {
      const want = regionOf(r.domain, r.locale);
      if (want !== r.region) { upd.run(want, r.id); changed++; }
    }
    db.exec('COMMIT');
  } catch (e) { db.exec('ROLLBACK'); throw e; }
  return changed;
}
