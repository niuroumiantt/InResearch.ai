// Headline translation into Chinese.
//
// The timeline is read in Chinese, but ~80% of what Google News returns is
// English, Korean or Japanese. So every headline gets a Chinese rendering and
// the original is kept underneath — a machine translation is a lead, not a
// citation, and hiding the source text would make a mistranslation unfalsifiable.
//
// Providers are pluggable because none of the free ones is dependable alone:
//
//   google     (default) translate.googleapis.com's gtx endpoint. No key, no
//              signup, good quality. Unofficial and rate-limited, so it is
//              driven slowly and every result is cached.
//   cloudflare Workers AI @cf/meta/m2m100-1.2b. Free tier (10k neurons/day)
//              covers this volume comfortably. Needs CF_ACCOUNT_ID + CF_API_TOKEN.
//   cfllm      Workers AI 的 LLM 翻译(同一对 CF 凭据):按语境翻,保留品牌/
//              人名/术语原文。m2m100 的「克劳德·塞辛斯」「韩文残留」这类病
//              在这里治;模型可用 ST_TRANSLATE_MODEL 换。
//   libre      A self-hosted or public LibreTranslate at LIBRETRANSLATE_URL.
//   ollama     自己机器上的 Ollama(DGX Spark)。不限速、不看别人脸色、
//              正文不出网 —— 前四种都要把标题发给第三方。地址走
//              INEWS_TRANSLATION_URL,模型走 INEWS_TRANSLATION_MODEL。
//   none       Disable; titles stay in their source language.
//
// INEWS_TRANSLATION_PROVIDER picks one. Whatever the provider, failure is never fatal: the
// row keeps title_zh NULL and the UI falls back to the original headline.

import { getDb } from './db.js';
import { envNumber, envValue } from './env.js';
import { createHash } from 'node:crypto';

export const TARGET = 'zh-CN';
const PROVIDER = envValue('INEWS_TRANSLATION_PROVIDER', { legacy: 'ST_TRANSLATE', fallback: 'google' });
const TIMEOUT_MS = envNumber('INEWS_TRANSLATION_TIMEOUT_MS', {
  legacy: 'ST_TRANSLATE_TIMEOUT_MS', fallback: 12_000,
});
/**
 * Deliberately slow: the free endpoints are shared goodwill, not an SLA.
 * 这条理由对自己的机器不成立 —— 本地 Ollama 默认不限速,否则每轮白等几十秒。
 */
const GAP_MS = envNumber('INEWS_TRANSLATION_GAP_MS', {
  legacy: 'ST_TRANSLATE_GAP_MS', fallback: PROVIDER === 'ollama' ? 0 : 700,
});

/** 译文模型名。cfllm 与 ollama 共用一个口子 —— 同时只有一个 provider 在跑。 */
const MODEL = envValue('INEWS_TRANSLATION_MODEL', { legacy: 'ST_TRANSLATE_MODEL' });

const hash = (s) => createHash('sha256').update(s).digest('hex').slice(0, 32);

/** CJK ideographs, minus the kana that mark a title as Japanese rather than Chinese. */
const HAN = /[一-鿿㐀-䶿]/gu;
const KANA = /[぀-ヿ]/u;
const HANGUL = /[가-힯]/u;

/**
 * True when a headline is already Chinese and translating it would only add
 * noise.
 *
 * Not a character ratio: real Chinese tech headlines are full of Latin brand
 * names, and "Gemini 3 发布" is 17% Han by character while being entirely
 * readable Chinese. Comparing Han characters against Latin *words* matches how
 * a reader sees it — two Han characters outweigh one brand name.
 *
 * Kana or Hangul anywhere means Japanese/Korean; those share Han characters
 * with Chinese and would otherwise be misread as already-translated.
 */
export function isChinese(title) {
  const t = String(title || '');
  if (!t) return true;
  if (KANA.test(t) || HANGUL.test(t)) return false;
  const han = (t.match(HAN) || []).length;
  if (han < 2) return false;
  const latinWords = (t.match(/[A-Za-z][A-Za-z'’-]*/g) || []).length;
  return han >= latinWords;
}

async function withTimeout(fn) {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), TIMEOUT_MS);
  try { return await fn(ac.signal); } finally { clearTimeout(timer); }
}

/**
 * 译文质量闸。免费 MT 会产出三类垃圾:韩文/假名整段残留(m2m100 的 ko→zh
 * 尤其严重)、夹生字符(「재і동」里的西里尔 і)、原样吐回。宁可回落到原文
 * 标题(诚实),也不给读者夹生饭。缓存读取也过这道闸 —— 已经存进去的坏译文
 * 不再复用,下一轮自动重译。
 */
const CYRILLIC = /[Ѐ-ӿ]/;
/** U+2581 是 SentencePiece 的词边界记号;`<…｜…>` 与结尾孤立的全角竖线是漏出来的特殊 token。 */
const CONTROL_MARKER = /\u2581|[<＜][^>＞]{0,40}[｜|][^>＞]{0,40}[>＞｠]|｜\s*$/;
export function translationLooksBad(out, src) {
  return translationRejectReason(out, src) !== null;
}

/**
 * 同一把闸,但把「为什么拦」说出来。
 *
 * 分成两个函数不是为了好看:2026-09-04 切到本地模型后,一轮里 32 条被拦下,
 * 而日志只有「失败 32」三个字 —— 看不出是模型翻错了还是闸门误伤,只能靠猜。
 * 「失败要留真实原话」这条规矩对质量闸同样成立。
 *
 * @returns {string|null} 拦下的理由;放行返回 null。
 */
export function translationRejectReason(out, src) {
  if (!out || !out.trim()) return '空';
  if (out === src) return '原样吐回,等于没翻';
  if (HANGUL.test(out)) return '译文里有谚文,目标是中文';
  const kana = (out.match(/[぀-ヿ]/g) || []).length;
  if (kana > 0 && kana >= out.length * 0.15) return '大段假名残留,没翻完';
  if (CYRILLIC.test(out)) return '混进西里尔字母';
  if (out.includes('�')) return '有乱码字符';
  // 2026-09-01 实拍补的两条:免费 MT 偶发退化输出(mode collapse),吐出
  // 「I " " " "…」「a a " ( a only top…」这类引号汤。判据都是结构性的:
  // ① 目标是中文的译文一个汉字都没有 —— 品牌名照抄不叫翻译,整行没有
  //    中文就是没翻(正常译文再多品牌名也总有几个汉字);
  const han = (out.match(HAN) || []).length;
  if (han === 0) return '一个汉字都没有';
  // ② 去掉空格后,汉字+字母+数字占不到一半 —— 剩下的全是标点,零信息量。
  const body = out.replace(/\s/g, '');
  const informative = (body.match(/[一-鿿㐀-䶿A-Za-z0-9]/g) || []).length;
  if (body.length >= 4 && informative < body.length / 2) return '几乎全是标点,零信息量';
  // ③ 译文长得不像标题 —— LLM 当翻译用时的典型跑题:不翻译,改成讲解
  //    (「这句话的意思是……」「注:此处 HBM 指……」)。两个条件都要满足:
  //    · 80 字下限 —— 新闻标题的中译没有这么长的,这一条本身就快够用了;
  //    · 1.6 倍原文 —— 中文表达英文通常只用 0.4~0.6 倍的字数,所以译文比
  //      原文还长就已经反常;1.6 是留足余量,不是文风偏好。
  //    下限那条同时保护极短原文(「AI」→「人工智能」合理地译长了)。
  if (out.length > 80 && out.length > src.length * 1.6) return '长得不像标题,像在讲解';
  // ④ 分词器的控制标记漏进了正文。2026-09-04 实测:hy-mt2 那个 GGUF 的停止符
  //    没设对,译文尾巴上挂着 `<｜hy_end▁of▁sentence｜>`、`<ａ｜hy_Emo｜>`,
  //    还有孤零零一个全角竖线。判据同样是结构性的 —— 这些是模型内部的记号,
  //    不是任何一种语言里的字,出现即说明这条输出没被正确截断。
  if (CONTROL_MARKER.test(out)) return '漏出了分词器的控制标记';
  return null;
}

/**
 * 存量清理:把已经写进 articles.title_zh 的坏译文清空(下一轮自动重译),
 * 并删掉缓存表里的坏行。质量闸拦得住新写入,但闸门每收紧一次,历史上
 * 已经过闸的坏译文还挂在时间线上 —— serve 启动时跑一遍,几万行毫秒级,
 * 和 backfillValues 一个待遇:闸门改进追溯生效,不用登服务器。
 */
export function scrubBadTranslations(db = getDb()) {
  let n = 0;
  const rows = db.prepare('SELECT id, title, title_zh FROM articles WHERE title_zh IS NOT NULL').all();
  const clear = db.prepare('UPDATE articles SET title_zh = NULL, title_zh_at = NULL WHERE id = ?');
  db.exec('BEGIN');
  try {
    for (const r of rows) {
      // 中文行的 title_zh 就是原题(translatePending 的标记约定),不是译文;
      // 清掉它只会让同一批行每轮重新排队。
      if (isChinese(r.title)) continue;
      if (translationLooksBad(r.title_zh, r.title)) { clear.run(r.id); n++; }
    }
    const del = db.prepare('DELETE FROM translations WHERE src_hash = ?');
    for (const c of db.prepare('SELECT src_hash, src, text FROM translations').all()) {
      if (translationLooksBad(c.text, c.src)) { del.run(c.src_hash); n++; }
    }
    db.exec('COMMIT');
  } catch (e) { db.exec('ROLLBACK'); throw e; }
  return n;
}

/* ---------------- providers ---------------- */

async function viaGoogle(text) {
  const url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl='
    + encodeURIComponent(TARGET) + '&dt=t&q=' + encodeURIComponent(text);
  return withTimeout(async (signal) => {
    const res = await fetch(url, { signal, headers: { 'user-agent': 'Mozilla/5.0' } });
    if (!res.ok) throw new Error(`google HTTP ${res.status}`);
    const data = await res.json();
    // Shape: [[[translated, source, …], …], …] — one entry per sentence.
    if (!Array.isArray(data?.[0])) throw new Error('google: unexpected shape');
    return data[0].map((seg) => seg?.[0] || '').join('').trim();
  });
}

async function viaCloudflare(text) {
  const account = process.env.CF_ACCOUNT_ID;
  const token = process.env.CF_API_TOKEN;
  if (!account || !token) throw new Error('cloudflare: CF_ACCOUNT_ID / CF_API_TOKEN not set');
  const model = process.env.CF_TRANSLATE_MODEL || '@cf/meta/m2m100-1.2b';
  const url = `https://api.cloudflare.com/client/v4/accounts/${account}/ai/run/${model}`;
  return withTimeout(async (signal) => {
    const res = await fetch(url, {
      method: 'POST', signal,
      headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
      body: JSON.stringify({ text, source_lang: 'english', target_lang: 'chinese' }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok || data?.success === false) {
      throw new Error(`cloudflare: ${data?.errors?.[0]?.message || 'HTTP ' + res.status}`);
    }
    const out = data?.result?.translated_text;
    if (!out) throw new Error('cloudflare: empty result');
    return String(out).trim();
  });
}

async function viaLibre(text) {
  const base = process.env.LIBRETRANSLATE_URL;
  if (!base) throw new Error('libre: LIBRETRANSLATE_URL not set');
  return withTimeout(async (signal) => {
    const res = await fetch(base.replace(/\/$/, '') + '/translate', {
      method: 'POST', signal,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        q: text, source: 'auto', target: 'zh',
        format: 'text', api_key: process.env.LIBRETRANSLATE_KEY || undefined,
      }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(`libre: ${data?.error || 'HTTP ' + res.status}`);
    if (!data?.translatedText) throw new Error('libre: empty result');
    return String(data.translatedText).trim();
  });
}

/**
 * 通用 LLM 当翻译用时的系统提示词。两处在用(cfllm / ollama),所以只写一遍 ——
 * 「保留品牌名」这条是拿事故换来的:m2m100 把 Claude 译成了人名「克劳德·塞辛斯」。
 * 翻译专用模型(Hy-MT 系列)不走这里,它们有自己的官方模板,外加系统提示词反而降质。
 *
 * 「保持原文」为什么只对拉丁字母成立(2026-09-04 上线后当天补的):
 * 原来那句写的是「公司名、产品名、人名保持原文不译」,模型照做了,于是韩文标题
 * 译出来是「SKT、KT、Kakao启动"모두의 AI"开发,배경훈称…」—— 句子结构全对,
 * 但产品名和人名还是谚文。判据是读者的字表,不是文风偏好:**中文读者认得
 * OpenAI,不认得 배경훈**。前者留原文是帮忙,后者留原文等于没翻。
 */
const LLM_SYSTEM =
  '把新闻标题翻译成简体中文,只输出一行译文,不要任何解释或引号。'
  + '拉丁字母的公司名、产品名、人名、技术术语保持原文不译(如 Claude、OpenAI、GPU、HBM)。'
  + '韩文、日文的专有名词必须转成中文:人名用对应汉字,机构名与产品名用通行中文名或意译 ——'
  + '中文读者读不了谚文和假名,原样留着等于没翻。';

/**
 * 去掉思考模型漏出来的推理段。qwen3 与 Hy-MT2 都会思考;Ollama 认得模板时
 * 会把它放进 message.thinking,认不得(社区 GGUF 常见)就原样混在正文里。
 * 这行不删,时间线上会出现一整段「好的,用户让我翻译……」。
 */
export const stripThinking = (s) => String(s).replace(/<think>[\s\S]*?<\/think>/gi, '').trim();

/** LLM 翻译(Workers AI chat 端点,复用 CF 凭据)。比 m2m100 强一档:
 *  能按语境翻,并按提示词保留品牌/人名/术语原文 ——「Claude Sessions 被劫持」
 *  不会再变成人名「克劳德·塞辛斯」。切换:ST_TRANSLATE=cfllm。 */
async function viaCfLlm(text) {
  const account = process.env.CF_ACCOUNT_ID;
  const token = process.env.CF_API_TOKEN;
  if (!account || !token) throw new Error('cfllm: CF_ACCOUNT_ID / CF_API_TOKEN not set');
  // 2026-08-31: llama-3.1-8b-instruct 已被 CF 废弃(410)。翻译质量优先选 70B:
  // 标题短、输出短,免费额度吃得消;ko/ja→zh 是 8B 的明显短板。
  const model = MODEL || '@cf/meta/llama-3.3-70b-instruct-fp8-fast';
  const url = `https://api.cloudflare.com/client/v4/accounts/${account}/ai/v1/chat/completions`;
  return withTimeout(async (signal) => {
    const res = await fetch(url, {
      method: 'POST', signal,
      headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
      body: JSON.stringify({
        model, temperature: 0,
        messages: [{ role: 'system', content: LLM_SYSTEM }, { role: 'user', content: text }],
      }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(`cfllm: ${data?.errors?.[0]?.message || data?.error?.message || 'HTTP ' + res.status}`);
    const out = stripThinking(data?.choices?.[0]?.message?.content || '');
    if (!out) throw new Error('cfllm: empty result');
    return out.replace(/^["'「『]+|["'」』]+$/g, '');
  });
}

export const ollamaBase = () =>
  (envValue('INEWS_TRANSLATION_URL', { fallback: 'http://127.0.0.1:11434' }) || '').replace(/\/$/, '');

/**
 * 本地 Ollama。和上面四个的区别不只是「免费」:标题不出网,而且没有配额、
 * 没有 429、没有哪天被上游废弃(cfllm 就被废弃过一次,见上面的日期)。
 * 代价是这台机器得活着 —— 所以失败路径和别的 provider 一模一样:
 * 拿不到译文就留原文,新闻不会因为家里断电而消失。
 *
 * 提示词按模型族分,这不是风格问题:
 *  - Hy-MT / hunyuan-mt 是翻译专用模型,官方模板是训练时用的那句,
 *    换一句或加系统提示词都会掉分;
 *  - 其余(qwen3 等通用模型)走 LLM_SYSTEM,靠提示词保住品牌名。
 */
/**
 * 打一次 Ollama /api/chat,并处理「思考模型」这件事。
 *
 * 翻译一句话不需要推理链,而推理链要花掉十倍的时间和全部 token 预算 ——
 * 2026-09-04 实测:qwen3:30b-a3b 八条全空,每条卡在 2.8 秒(正好是 256 token
 * 的时间),推理还没写完就被 num_predict 掐断,content 一片空白。
 *
 * 所以默认 `think: false`。但不是所有模型都认这个字段,认不得的会直接报错,
 * 那就退回「让它思考,但给足预算,回头把 <think> 段剥掉」—— 慢,但出得来。
 */
export async function ollamaChat(base, model, messages, signal) {
  const body = {
    model, messages, stream: false,
    // 30 分钟常驻:采集是按 cycle 来的,不保温的话每轮都要重新把模型
    // 装进显存,一次几十秒 —— 比翻译本身还久。
    keep_alive: '30m',
    // num_predict 是防跑题的硬闸:关掉思考后,标题译文到不了 256 token,
    // 到了就是模型在写小作文,让它停在那儿,剩下的交给质量闸。
    options: { temperature: 0, num_predict: 256 },
  };
  const post = async (payload) => {
    const res = await fetch(`${base}/api/chat`, {
      method: 'POST', signal,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => null);
    return { ok: res.ok, status: res.status, data };
  };

  let r = await post({ ...body, think: false });
  if (!r.ok && /think/i.test(String(r.data?.error || ''))) {
    // 这个模型不认 think 字段 —— 让它思考,但预算给够,剥掉再用。
    r = await post({ ...body, options: { ...body.options, num_predict: 2048 } });
  }
  if (!r.ok) throw new Error(`ollama: ${r.data?.error || 'HTTP ' + r.status}`);
  return r.data;
}

export function ollamaMessages(model, text) {
  // 官方模板(Hunyuan-MT 技术报告的 ZH<=>XX 版本),一个字都不要改。
  if (/hy-mt|hunyuan-mt/i.test(model)) {
    return [{ role: 'user', content: `把下面的文本翻译成中文,不要额外解释。\n\n${text}` }];
  }
  return [{ role: 'system', content: LLM_SYSTEM }, { role: 'user', content: text }];
}

async function viaOllama(text) {
  const base = ollamaBase();
  const model = MODEL;
  if (!model) throw new Error('ollama: INEWS_TRANSLATION_MODEL 未设置');
  const messages = ollamaMessages(model, text);
  return withTimeout(async (signal) => {
    const data = await ollamaChat(base, model, messages, signal);
    const out = stripThinking(data?.message?.content || '');
    if (!out) {
      // 2026-09-04 实测踩到的:qwen3 系列思考完才开口,思考占满 num_predict
      // 时 content 是空的(推理进了 message.thinking)。空字符串比坏译文更
      // 危险 —— 它会被当成「翻译失败」而不是「配错了」。所以把原因说出来。
      throw new Error(data?.message?.thinking
        ? 'ollama: 模型只输出了思考,没输出译文(num_predict 被思考占满)'
        : 'ollama: empty result');
    }
    return out.replace(/^["'「『]+|["'」』]+$/g, '');
  });
}

const PROVIDERS = {
  google: viaGoogle, cloudflare: viaCloudflare, libre: viaLibre,
  cfllm: viaCfLlm, ollama: viaOllama,
};

export const translatorName = () => PROVIDER;
export const translatorEnabled = () => PROVIDER !== 'none' && PROVIDER in PROVIDERS;

/* ---------------- cache ---------------- */

function cached(db, src) {
  const hit = db.prepare('SELECT text FROM translations WHERE src_hash = ? AND target = ?')
    .get(hash(src), TARGET)?.text ?? null;
  // 坏译文不复用:当年存进去的夹生饭,过闸失败就当没缓存,触发重译并覆盖。
  return hit && !translationLooksBad(hit, src) ? hit : null;
}

function remember(db, src, text, provider) {
  db.prepare(`INSERT INTO translations(src_hash, src, target, text, provider, at)
              VALUES (?,?,?,?,?,?)
              ON CONFLICT(src_hash) DO UPDATE SET text = excluded.text,
                provider = excluded.provider, at = excluded.at`)
    .run(hash(src), src, TARGET, text, provider, Date.now());
}

/** One string, cache first. Returns null when translation is unavailable. */
export async function translate(text) {
  const src = String(text || '').trim();
  if (!src || isChinese(src)) return null;
  const db = getDb();
  const hit = cached(db, src);
  if (hit) return hit;
  if (!translatorEnabled()) return null;
  const out = await PROVIDERS[PROVIDER](src);
  if (translationLooksBad(out, src)) return null;
  remember(db, src, out, PROVIDER);
  return out;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Fill in `articles.title_zh` for rows that still lack it, newest first —
 * what is on screen right now matters more than the backlog.
 *
 * Sequential on purpose. These endpoints answer in well under a second, the
 * queue is a few dozen rows per cycle, and parallelising it buys nothing but a
 * higher chance of getting rate-limited off a free tier.
 *
 * @returns {{done:number, failed:number, skipped:number, pending:number,
 *            rejected:Array<{src:string,out:string,why:string}>}}
 *          `rejected` 最多留 3 条被质量闸拦下的样本(原文/译文/理由)——
 *          这类失败不抛异常,不留样本就只剩一个说明不了任何事的计数。
 */
export async function translatePending({ limit = 60, budgetMs = 45_000 } = {}) {
  const db = getDb();
  const stats = { done: 0, failed: 0, skipped: 0, pending: 0, rejected: [] };
  const rows = db.prepare(
    'SELECT id, title FROM articles WHERE title_zh IS NULL ORDER BY published_at DESC LIMIT ?',
  ).all(limit);
  const upd = db.prepare('UPDATE articles SET title_zh = ?, title_zh_at = ? WHERE id = ?');
  const deadline = Date.now() + budgetMs;
  let consecutiveFailures = 0;

  for (const r of rows) {
    if (Date.now() > deadline) break;
    // Already-Chinese headlines are marked with the original text, not left
    // NULL — otherwise every pass re-examines the same rows forever.
    if (isChinese(r.title)) { upd.run(r.title, Date.now(), r.id); stats.skipped++; continue; }
    if (!translatorEnabled()) break;
    const hit = cached(db, r.title.trim());
    if (hit) { upd.run(hit, Date.now(), r.id); stats.done++; continue; }
    try {
      const out = await PROVIDERS[PROVIDER](r.title.trim());
      const why = translationRejectReason(out, r.title.trim());
      if (!why) {
        remember(db, r.title.trim(), out, PROVIDER);
        upd.run(out, Date.now(), r.id);
        stats.done++;
        consecutiveFailures = 0;
      } else {
        stats.failed++;
        // 留样本,不只留计数。被闸门拦下不抛异常,所以 stats.error 是空的 ——
        // 没有这几条,「失败 32」就只能靠猜是模型的问题还是闸门的问题。
        if (stats.rejected.length < 3) stats.rejected.push({ src: r.title.trim(), out, why });
      }
    } catch (e) {
      stats.failed++;
      stats.error = String(e.message || e);
      // Three failures in a row is the provider refusing us, not one bad
      // headline. Stop and let the next cycle retry rather than hammering.
      if (++consecutiveFailures >= 3) break;
    }
    await sleep(GAP_MS);
  }
  stats.pending = db.prepare('SELECT COUNT(*) n FROM articles WHERE title_zh IS NULL').get().n;
  return stats;
}
