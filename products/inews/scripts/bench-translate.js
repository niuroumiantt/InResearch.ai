#!/usr/bin/env node
// 选翻译模型的尺子。
//
// 为什么要有这个:榜单上的分数是别人的语料上的分数,和「我这条时间线上的
// AI 新闻标题」不是一回事。上一次凭榜单选模型,选出来的 m2m100 把 Claude
// 译成了人名。所以换模型之前,先在自己的标题上跑一遍。
//
//   node scripts/bench-translate.js hf.co/tencent/Hy-MT2-7B-GGUF qwen3.8:27b
//
// 语料默认从库里取还没译过的英文标题;库是空的就用内置样本(都是踩过坑的
// 真实形态:品牌名、缩写、人名、韩文、长标题)。
//
// 输出三样东西,都是能判的事实,不是「感觉哪个好」:
//   · 逐条译文并排 —— 唯一能看出「翻错了」的办法,人得亲眼读
//   · 过闸率 —— 用本项目自己的 translationLooksBad,和线上同一把闸
//   · 每条耗时 —— 27B 慢一倍但强一档的话,值不值得由你定,先把数摆出来
import { ollamaBase, ollamaChat, ollamaMessages, stripThinking, translationLooksBad, isChinese }
  from '../src/lib/translate.js';

const SAMPLES = [
  'Anthropic ships Claude Opus 4.5 with a longer context window',
  'Nvidia says Blackwell HBM supply remains the binding constraint through 2026',
  'OpenAI pauses frontier model training over cyber capabilities',
  'Meta open-sources a 400B mixture-of-experts model under a permissive licence',
  'TSMC lifts capex guidance as CoWoS packaging stays sold out',
  'EU AI Act enforcement begins for general-purpose models',
  '오픈AI 새 모델 공개',
  'オープンAIが新モデルを発表',
];

const models = process.argv.slice(2);
if (!models.length) {
  console.error('用法: node scripts/bench-translate.js <模型1> [模型2 …]');
  process.exit(2);
}

/**
 * 语料:优先用库里的真标题,取不到再退到样本。
 * 退化了要说一声 —— 悄悄用样本会让人以为量的是自己的新闻。
 */
async function corpus(n = 12) {
  try {
    const { getDb } = await import('../src/lib/db.js');
    const rows = getDb().prepare(
      'SELECT title FROM articles ORDER BY published_at DESC LIMIT 400',
    ).all();
    const picked = rows.map((r) => r.title).filter((t) => t && !isChinese(t)).slice(0, n);
    if (picked.length) return { texts: picked, from: '库里的真标题' };
  } catch (e) {
    console.log(`(读不到库,用内置样本:${e.message})`);
  }
  return { texts: SAMPLES, from: '内置样本' };
}

/** 走 translate.js 里生产路径同一条请求 —— 量的必须是将来真正跑的那套。 */
async function once(model, text) {
  const t0 = Date.now();
  const data = await ollamaChat(ollamaBase(), model, ollamaMessages(model, text));
  const out = stripThinking(data?.message?.content || '').replace(/^["'「『]+|["'」』]+$/g, '');
  // 空译文要说清是哪一种空:模型只顾思考没开口,和模型确实没话说,处置完全不同。
  const why = out ? '' : (data?.message?.thinking ? '  ← 只输出了思考,没输出译文' : '  ← 空回复');
  return { out, why, ms: Date.now() - t0 };
}

const { texts, from } = await corpus();
console.log(`语料 ${texts.length} 条(${from}),模型 ${models.length} 个,地址 ${ollamaBase()}\n`);

const summary = [];
for (const model of models) {
  console.log(`\n===== ${model} =====`);
  let ok = 0, bad = 0, total = 0;
  for (const t of texts) {
    try {
      const { out, why, ms } = await once(model, t);
      total += ms;
      const good = !translationLooksBad(out, t);
      good ? ok++ : bad++;
      console.log(`  ${good ? '✓' : '✗'} ${String(ms).padStart(6)}ms  ${t}`);
      console.log(`              ${out}${why}`);
    } catch (e) {
      bad++;
      console.log(`  ! 失败  ${t}\n              ${e.message}`);
    }
  }
  const avg = ok + bad ? Math.round(total / (ok + bad)) : 0;
  summary.push({ model, ok, bad, avg });
}

console.log('\n===== 汇总 =====');
console.log('过闸率用的是本项目线上那把闸(translationLooksBad),不是翻译质量分。');
console.log('闸只拦得住「明显是垃圾」;「翻错了但看着像话」只有你自己读得出来。\n');
for (const s of summary) {
  console.log(`  ${s.model.padEnd(38)} 过闸 ${s.ok}/${s.ok + s.bad}   平均 ${s.avg}ms/条`);
}
