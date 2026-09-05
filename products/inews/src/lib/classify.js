// LLM 价值精化 —— value 轴的第二级。
//
// 启发式(lib/value.js)在入库时就把最机械的体裁钉死了,但"某公司也用了AI"式
// 通稿的写法无穷无尽,词表永远追不上。这里用一个便宜的 LLM 逐批复核启发式
// 打过分的行,把 genre/value 精化,value_src 从 'heur' 升为 'llm'。
//
// 两种接法,换供应商只改环境变量:
//   ST_CLASSIFY=cloudflare  复用翻译管道已有的 CF_ACCOUNT_ID / CF_API_TOKEN,
//                           走 Workers AI 的 OpenAI 兼容端点,免费额度足够
//                           (默认 @cf/meta/llama-3.1-8b-instruct,可用
//                           ST_CLASSIFY_MODEL 换)。服务器上翻译能跑,这个就能跑。
//   ST_CLASSIFY=llm         任意 OpenAI 兼容供应商:ST_CLASSIFY_URL +
//                           ST_CLASSIFY_KEY + ST_CLASSIFY_MODEL
//   ST_CLASSIFY=none        (默认)关闭,只有入库时的规则粗判
//
// 与翻译管道同一条纪律:失败绝不致命 —— 行保持 heur 分,下一轮再试。

import { getDb } from './db.js';
import { GENRES } from './value.js';

const MODE = process.env.ST_CLASSIFY || 'none';
const TIMEOUT_MS = Number(process.env.ST_CLASSIFY_TIMEOUT_MS || 30_000);
// 一批别贪多:CF 不传 max_tokens 时默认很小,25 条的 JSON 数组会被拦腰截断
// (线上实测「no JSON in reply」的病根)。15 条 + 显式 max_tokens 双保险。
const BATCH = 15;

function conf() {
  if (MODE === 'cloudflare') {
    const acc = process.env.CF_ACCOUNT_ID || '';
    const key = process.env.CF_API_TOKEN || '';
    return {
      ok: Boolean(acc && key), key,
      base: `https://api.cloudflare.com/client/v4/accounts/${acc}/ai/v1`,
      // 分类是简单任务且要吃 4.6 万条积压 —— 用 8B 的 fast 变体跑量。
      model: process.env.ST_CLASSIFY_MODEL || '@cf/meta/llama-3.1-8b-instruct-fast',
    };
  }
  if (MODE === 'llm') {
    const key = process.env.ST_CLASSIFY_KEY || '';
    const model = process.env.ST_CLASSIFY_MODEL || '';
    return {
      ok: Boolean(key && model), key, model,
      base: (process.env.ST_CLASSIFY_URL || 'https://api.openai.com/v1').replace(/\/$/, ''),
    };
  }
  return { ok: false, base: '', key: '', model: '' };
}

export const classifierEnabled = () => conf().ok;
export const classifierName = () => {
  const c = conf();
  return c.ok ? `${c.model}@${new URL(c.base).host}` : 'none';
};

// MECE 归档:一篇只归一类。v(价值)和 g(类别)是两根独立的轴。
const PROMPT = `你在为「AI 生态专业研究者」归档新闻标题。对每一行输出价值档 v 和内容分类 g。
v: 3=必读(数据中心建设与供需/头部 AI 厂商与模型动态/中国开源模型/芯片供应链
   实质进展/重大融资并购/监管立法实质动作/重要研究)。
   必读要求标题里有可核实的新事实(谁+做了什么);行情波动、观点评论、预告、复述不算
   2=可读(行业公司实质性 AI 产品或落地、有信息量的分析)
   1=边角料(普通企业"用了AI"通稿、会议预告、地方产业活动、名人评论)
   0=垃圾(手机/PC/游戏/智能眼镜等消费内容、提示词教程、八卦、股票ETF导购、
   回购与资金流、券商评级/目标价、盘面综述/收盘简报、股价涨跌行情、获奖表彰、
   政务活动稿、营销软文、蹭AI热点的广告、与AI无关的误报)
必读应当稀少;两档之间拿不准时打低的那一档。
g 只能选一个,按「新闻的核心事件」归类:
   model=模型发布/能力/评测/论文/开源  compute=芯片/算力/数据中心/能源
   business=融资/并购/财报/人事/估值  policy=监管/立法/诉讼/版权/地缘
   safety=安全/对齐/滥用/事故/攻击    apps=行业应用/产品落地
   society=就业/教育/伦理/文化        noise=垃圾(v=0 的都归这)  other=实在归不进
一篇只归一类;跨类难分时按 policy>safety>business>compute>model>apps>society 取先。
只输出 JSON 数组,形如 [{"i":0,"v":2,"g":"model"},...],不要任何其它文字。`;

/** 通用的「system+user 进,JSON 数组出」调用 —— 价值精化与跨语言并簇
 *  (lib/merge.js)共用同一个供应商配置与同一套皮实解析。 */
export async function llmJson(system, user) {
  const c = conf();
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${c.base}/chat/completions`, {
      method: 'POST', signal: ac.signal,
      headers: { authorization: `Bearer ${c.key}`, 'content-type': 'application/json' },
      body: JSON.stringify({
        model: c.model, temperature: 0, max_tokens: 3000,
        messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
      }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(`llm: ${data?.error?.message || 'HTTP ' + res.status}`);
    const text = data?.choices?.[0]?.message?.content || '';
    // 解析要皮实:围栏、截断的数组都可能出现。先试完整数组,不行就把
    // 一个个 {"i":..,...} 对象捞出来 —— 截断只丢尾巴,不丢整批。
    const m = text.match(/\[[\s\S]*\]/);
    if (m) { try { const arr = JSON.parse(m[0]); if (Array.isArray(arr)) return arr; } catch { /* 下面逐个捞 */ } }
    const picked = [...text.matchAll(/\{[^{}]*\}/g)].map((x) => {
      try { return JSON.parse(x[0]); } catch { return null; }
    }).filter(Boolean);
    if (!picked.length) throw new Error('llm: no JSON in reply');
    return picked;
  } finally { clearTimeout(timer); }
}

const askLLM = (rows) => llmJson(PROMPT,
  rows.map((r, idx) => `${idx}\t[${r.angle || '-'}]\t${r.title.slice(0, 160)}`).join('\n'));

/**
 * 精化一批仍是启发式打分的行,新的先来 —— 屏幕上正在显示的行最要紧。
 * @returns {{done:number, failed:number, pending:number}}
 */
export async function classifyPending({ limit = 100, budgetMs = 30_000 } = {}) {
  const db = getDb();
  const stats = { done: 0, failed: 0, pending: 0 };
  if (classifierEnabled()) {
    // value > 0:词表一票否决(荐股/盘面/表彰)是结构性事实,模型观点不得
    // 推翻 —— 否则词表每堵一个口,精化批次就把它重新打开(2026-09-01 线上
    // 复核:必读档的行情垃圾里有一批正是这么进来的)。
    const rows = db.prepare(`SELECT id, title, angle FROM articles
      WHERE relevant = 1 AND value_src = 'heur' AND value > 0
      ORDER BY published_at DESC LIMIT ?`).all(limit);
    const upd = db.prepare("UPDATE articles SET value = ?, genre = ?, value_src = 'llm' WHERE id = ?");
    const deadline = Date.now() + budgetMs;
    for (let i = 0; i < rows.length && Date.now() < deadline; i += BATCH) {
      const chunk = rows.slice(i, i + BATCH);
      try {
        const verdicts = await askLLM(chunk);
        for (const v of verdicts) {
          const row = chunk[v.i];
          if (!row) continue;
          const val = Math.max(0, Math.min(3, Number(v.v)));
          const genre = GENRES.includes(v.g) ? v.g : 'other';
          if (Number.isFinite(val)) { upd.run(val, genre, row.id); stats.done++; }
        }
      } catch (e) {
        stats.failed += chunk.length;
        stats.error = String(e.message || e);
        break;  // 供应商在拒绝我们,让下一轮重试,别捶
      }
    }
  }
  stats.pending = db.prepare(
    "SELECT COUNT(*) n FROM articles WHERE relevant = 1 AND value_src = 'heur' AND value > 0").get().n;
  return stats;
}
