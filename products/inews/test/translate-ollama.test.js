// 本地 Ollama provider:提示词按模型族分、思考段要剥掉、机器挂了不能拖垮新闻。
//
// 用假的 fetch 拦请求,断言的是「我们发出去的是什么」——真跑一次模型既慢又
// 不确定,证明不了提示词是对的。Hy-MT 的官方模板错一个字就掉分,这是最该
// 被钉死的一条。
import { test, after, mock } from 'node:test';
import assert from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DB = join(HERE, 'tmp-translate-ollama.db');
for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true });
process.env.SINGLETITLE_DB = DB;
process.env.INEWS_TRANSLATION_PROVIDER = 'ollama';
process.env.INEWS_TRANSLATION_URL = 'http://spark.test:11434';
process.env.INEWS_TRANSLATION_MODEL = 'hf.co/tencent/Hy-MT2-7B-GGUF';

const { translate, translationLooksBad, translatorName, translatorEnabled } =
  await import('../src/lib/translate.js');
after(() => { for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true }); });

/** 拦 /api/chat,记下每一次请求体,回一句固定译文。 */
function stubOllama(reply) {
  const seen = { calls: [] };
  mock.method(globalThis, 'fetch', async (url, init) => {
    seen.url = String(url);
    seen.body = JSON.parse(init.body);
    seen.calls.push(seen.body);
    return new Response(JSON.stringify({ message: { content: reply } }),
      { status: 200, headers: { 'content-type': 'application/json' } });
  });
  return seen;
}

/** 第一次报「不支持 think」,第二次成功 —— 模拟不认 think 字段的模型。 */
function stubOllamaRejectsThink(reply) {
  const seen = { calls: [] };
  mock.method(globalThis, 'fetch', async (url, init) => {
    const body = JSON.parse(init.body);
    seen.calls.push(body);
    if ('think' in body) {
      return new Response(JSON.stringify({ error: 'model does not support thinking' }),
        { status: 400, headers: { 'content-type': 'application/json' } });
    }
    return new Response(JSON.stringify({ message: { content: reply } }),
      { status: 200, headers: { 'content-type': 'application/json' } });
  });
  return seen;
}

test('provider 认得 ollama,而且打的是配好的地址', async () => {
  assert.equal(translatorName(), 'ollama');
  assert.equal(translatorEnabled(), true);
  const seen = stubOllama('英伟达发布新一代 AI 芯片');
  const out = await translate('Nvidia unveils next-generation AI chip');
  mock.restoreAll();
  assert.equal(out, '英伟达发布新一代 AI 芯片');
  assert.equal(seen.url, 'http://spark.test:11434/api/chat');
});

test('Hy-MT 走官方模板,一个字都不能改,且不带系统提示词', async () => {
  const seen = stubOllama('OpenAI 暂停前沿模型训练');
  await translate('OpenAI pauses frontier model training');
  mock.restoreAll();
  const msgs = seen.body.messages;
  assert.equal(msgs.length, 1, '翻译专用模型加系统提示词会掉分');
  assert.equal(msgs[0].role, 'user');
  assert.equal(
    msgs[0].content,
    '把下面的文本翻译成中文,不要额外解释。\n\nOpenAI pauses frontier model training',
  );
});

test('通用模型走系统提示词那条路,并交代要保留品牌名', async () => {
  process.env.INEWS_TRANSLATION_MODEL = 'qwen3.8:27b';
  const mod = await import('../src/lib/translate.js?generic');
  const seen = stubOllama('Anthropic 发布 Claude 新版本');
  await mod.translate('Anthropic ships a new Claude release');
  mock.restoreAll();
  process.env.INEWS_TRANSLATION_MODEL = 'hf.co/tencent/Hy-MT2-7B-GGUF';
  const msgs = seen.body.messages;
  assert.equal(msgs.length, 2);
  assert.equal(msgs[0].role, 'system');
  // 「保持原文」只对拉丁字母成立 —— 见下一条用例记的那次线上事故。
  assert.match(msgs[0].content, /拉丁字母的公司名、产品名、人名、技术术语保持原文不译/);
  assert.match(msgs[0].content, /韩文、日文的专有名词必须转成中文/);
  assert.equal(msgs[1].content, 'Anthropic ships a new Claude release');
});

test('思考段要剥掉,不能出现在时间线上', async () => {
  stubOllama('<think>用户让我翻译这个标题,先看主语……</think>\n谷歌发布 Gemini 4');
  const out = await translate('Google releases Gemini 4');
  mock.restoreAll();
  assert.equal(out, '谷歌发布 Gemini 4');
});

test('模型讲解而不是翻译时,质量闸要拦下来', () => {
  const src = 'OpenAI pauses frontier model training over cyber capabilities';
  // 真实跑题形态:把标题当成问题回答了。
  const 小作文 = '这句话的意思是,OpenAI 这家公司因为担心网络安全方面的能力问题,'
    + '决定暂停其前沿模型的训练工作。这里的 frontier model 指的是最先进的大模型,'
    + '而 cyber capabilities 指的是模型在网络攻防方面表现出来的能力。需要注意的是……';
  assert.equal(translationLooksBad(小作文, src), true);
  // 正常译文再长也不该被误伤。
  assert.equal(
    translationLooksBad('OpenAI 因网络攻防能力顾虑暂停前沿模型训练', src),
    false,
  );
  // 极短原文被合理地译长,不算跑题。
  assert.equal(translationLooksBad('人工智能', 'AI'), false);
});

test('Spark 连不上时返回 null,新闻照常显示原标题', async () => {
  mock.method(globalThis, 'fetch', async () => { throw new Error('ECONNREFUSED'); });
  await assert.rejects(() => translate('Meta open-sources a new vision model'));
  mock.restoreAll();
  // translatePending 把异常吞在自己的循环里(见 translate.js),
  // 这里断言的是异常确实抛得出来 —— 静默成功才是危险的那种失败。
});

// —— 以下四条是 2026-09-04 实测踩到的坑补的 ——
// qwen3:30b-a3b 八条译文全空,每条整齐地停在 2.8 秒(正好 256 token 的时间):
// 它先思考再开口,思考占满了 num_predict,content 一片空白。

test('默认关掉思考 —— 翻一句标题不需要推理链,推理会吃光 token 预算', async () => {
  const seen = stubOllama('英伟达发布新芯片');
  await translate('Nvidia launches a new chip');
  mock.restoreAll();
  assert.equal(seen.body.think, false);
  assert.equal(seen.body.options.num_predict, 256);
});

test('模型不认 think 字段时,退回「让它思考但给足预算」', async () => {
  const seen = stubOllamaRejectsThink('英伟达发布新芯片');
  const out = await translate('Nvidia launches another new chip');
  mock.restoreAll();
  assert.equal(out, '英伟达发布新芯片');
  assert.equal(seen.calls.length, 2, '应当重试一次');
  assert.equal('think' in seen.calls[1], false, '重试不该再带 think');
  assert.equal(seen.calls[1].options.num_predict, 2048,
    '思考要占预算,不给够就还是空的');
});

test('只思考不开口时,报错要说清是哪一种空', async () => {
  mock.method(globalThis, 'fetch', async () => new Response(
    JSON.stringify({ message: { content: '', thinking: '好的,用户让我翻译……' } }),
    { status: 200, headers: { 'content-type': 'application/json' } }));
  await assert.rejects(
    () => translate('OpenAI ships something new today'),
    /只输出了思考/,
    '「空结果」和「配错了」处置完全不同,不能混成一句 empty result',
  );
  mock.restoreAll();
});

test('分词器的控制标记漏进译文时,质量闸要拦下来', () => {
  // 三条都是 2026-09-04 实测里 hy-mt2 真实吐出来的形态。
  const ko = '오픈AI 새 모델 공개';
  assert.equal(
    translationLooksBad('开放AI发布了新模型。<ａ｜hy_Emo｜>真是令人兴奋啊！', ko), true);
  assert.equal(
    translationLooksBad('开放AI发布了新模型<｠hy_end▁of▁sentence｜>', ko), true);
  assert.equal(
    translationLooksBad('Anthropic公司推出了上下文窗口更长的版本。｜',
      'Anthropic ships Claude Opus 4.5'), true);
  // 正常译文里的全角标点不该被误伤。
  assert.equal(
    translationLooksBad('台积电上调资本支出指引，CoWoS封装持续售罄',
      'TSMC lifts capex guidance as CoWoS packaging stays sold out'), false);
  assert.equal(
    translationLooksBad('Anthropic 发布 Claude Opus 4.5，支持更长的上下文窗口',
      'Anthropic ships Claude Opus 4.5 with a longer context window'), false);
});

test('被质量闸拦下时要留样本和理由,不能只留一个计数', async () => {
  const { getDb } = await import('../src/lib/db.js');
  const db = getDb();
  db.prepare(`INSERT INTO articles
    (url, guid, title, domain, published_at, first_seen_at, relevance, relevant, dedupe_key)
    VALUES (?,?,?,?,?,?,?,?,?)`)
    .run('https://x/rej', 'grej', 'Nvidia and AMD and Intel', 'x.com',
      Date.now(), Date.now(), 5, 1, 'krej');
  // 模型把品牌名照抄了一遍 —— 一个汉字都没有,该拦。
  stubOllama('Nvidia and AMD and Intel plus');
  const { translatePending } = await import('../src/lib/translate.js');
  const r = await translatePending({ limit: 5 });
  mock.restoreAll();
  assert.ok(r.failed >= 1);
  const sample = r.rejected.find((x) => x.src === 'Nvidia and AMD and Intel');
  assert.ok(sample, '被拦下的行必须留样本,否则「失败 N」说明不了任何事');
  assert.match(sample.why, /一个汉字都没有/);
  assert.equal(sample.out, 'Nvidia and AMD and Intel plus');
});

test('放行的译文没有理由;每一种拦法都说得出自己的名字', async () => {
  const { translationRejectReason } = await import('../src/lib/translate.js');
  const src = 'OpenAI ships a new model today';
  assert.equal(translationRejectReason('OpenAI 发布新模型', src), null);
  assert.match(translationRejectReason('', src), /空/);
  assert.match(translationRejectReason(src, src), /原样吐回/);
  assert.match(translationRejectReason('오픈AI 새 모델', src), /谚文/);
  assert.match(translationRejectReason('OpenAI ships new', src), /一个汉字都没有/);
  assert.match(translationRejectReason('开放AI发布了新模型<｠hy_end▁of▁sentence｜>', src),
    /控制标记/);
});

test('提示词必须区分拉丁字母与谚文/假名的专有名词', async () => {
  // 2026-09-04 上线当天,一轮 33 条失败全是韩文标题。模型翻得没错,是在服从
  // 当时那句「公司名、产品名、人名保持原文不译」:
  //   原文 SKT·KT·카카오, '모두의 AI' 개발 착수…배경훈 "국민 감탄할 서비스 나와야"
  //   译文 SKT、KT、Kakao启动"모두의 AI"开发,배경훈称"必须推出令国民惊叹的服务"
  // 句子结构全对,产品名和人名还是谚文。判据是读者的字表,不是文风:
  // 中文读者认得 OpenAI,不认得 배경훈 —— 前者留原文是帮忙,后者等于没翻。
  const seen = stubOllama('OpenAI 发布新模型');
  process.env.INEWS_TRANSLATION_MODEL = 'qwen3.8:27b';
  const mod = await import('../src/lib/translate.js?prompt-scope');
  await mod.translate('Some fresh English headline about chips');
  mock.restoreAll();
  process.env.INEWS_TRANSLATION_MODEL = 'hf.co/tencent/Hy-MT2-7B-GGUF';
  const sys = seen.body.messages[0].content;
  assert.match(sys, /拉丁字母/, '「保持原文」不能再是无条件的');
  assert.match(sys, /韩文、日文/);
  assert.match(sys, /人名用对应汉字/);
});
