// 跨语言并簇 —— 聚类的第三道归并,跑在译文上。
//
// 2026-09-02 站长实拍:GitLab 财报的中/日/英三个版本各成一簇。入库层的两道
// 归并都作用于原文标题,跨语言词面永远对不上;译文落地后才可比。词面只筛
// 候选,判决交给 LLM —— 24h 全量仿真显示纯词面在中档重叠区真假混杂。
// 以下 GitLab 三条与盘点体长题都是当天线上的真实标题。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DB = join(HERE, 'tmp-merge.db');
for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true });
process.env.SINGLETITLE_DB = DB;
// 打开裁决通道(假凭据),网络层用 mock 顶掉 —— 测的是筛选与并簇逻辑。
process.env.ST_CLASSIFY = 'llm';
process.env.ST_CLASSIFY_KEY = 'test-key';
process.env.ST_CLASSIFY_MODEL = 'test-model';

const { getDb } = await import('../src/lib/db.js');
const { mergeCandidates, mergeTranslatedPending, applyMerge } = await import('../src/lib/merge.js');

const now = Date.now();
const H = 3600_000;
function seed(db, { id, title, zh = null, pub = now, cluster = null }) {
  db.prepare(`INSERT INTO articles
    (id, url, guid, title, title_zh, domain, published_at, first_seen_at,
     relevance, relevant, dedupe_key, cluster_id, is_original, value, genre, value_src,
     cluster_latest, cluster_n)
    VALUES (?,?,?,?,?, 'example.com', ?, ?, 5, 1, ?, ?, ?, 2, 'other', 'heur', ?, ?)`)
    .run(id, `https://x/${id}`, `g${id}`, title, zh, pub, now, `dk-${id}`,
      cluster ?? id, cluster ? 0 : 1, cluster ? null : pub, cluster ? null : 1);
}

const db = getDb();
// GitLab 三个语言版本:中文原生(最早)、日文版(译文)、英文版(译文,带一条转载)。
seed(db, { id: 1, title: 'GitLab第二财季营收大增21%，AI需求强劲推动订单增长 提供者 Investing.com', pub: now - 3 * H });
db.prepare('UPDATE articles SET title_zh = title WHERE id = 1').run();  // 中文行的标记约定
seed(db, { id: 2, title: 'GitLabの第2四半期売上高が21%増、AI需要が受注を押し上げ 執筆',
  zh: 'GitLab第二季度销售额增长21%，人工智能需求推动订单增加', pub: now - 2 * H });
seed(db, { id: 3, title: 'GitLab Q2 2027: AI Demand Drives Record Bookings and a Guidance Lift',
  zh: 'GitLab 2027年第二季度：人工智能需求推动创纪录的预订和指导提升', pub: now - 1 * H });
seed(db, { id: 4, title: 'GitLab Q2 2027: AI Demand Drives Record Bookings and a Guidance Lift',
  pub: now - 0.5 * H, cluster: 3 });
db.prepare('UPDATE articles SET cluster_n = 2, cluster_latest = ? WHERE id = 3').run(now - 0.5 * H);

// 盘点体:一条标题装十条新闻,是链式错并的超级连接器,不得进候选。
seed(db, { id: 5, title: '【A股头条：AI应用超级利好！工信部拟开展专项行动；OpenAI和Anthropic也加入哄抢苹果Mac mini，训练模型；燧原科技科创板发行定价142.18元/股；英伟达35亿美元投资联发科；华为上半年收入4678亿元' });
db.prepare('UPDATE articles SET title_zh = title WHERE id = 5').run();
seed(db, { id: 6, title: 'Anthropic signs $35 billion cloud deal with Nvidia-backed Lambda',
  zh: 'Anthropic同英伟达支持的Lambda签署350亿美元云计算协议' });

// 泛词假相似:「人工智能热潮带来」是当期高频短语,这种 token 对上了不算数。
// 铺 8 行填充把这串二字组的文档频率推过泛词线。
for (let i = 0; i < 8; i++) {
  seed(db, { id: 10 + i, title: `人工智能热潮带来新变化第${i}篇：某地产业观察记录` });
}
// 会进候选但该被 LLM 否决的对:同一公司、同一套话骨架,事件却不同 ——
// 这正是词面分不开、必须裁决的那类(24h 仿真里的错并全长这样)。
seed(db, { id: 25, title: 'Sprinklr beats earnings estimates as AI investment pays off',
  zh: 'Sprinklr 盈利超出预期，AI 投资应对增长挑战', pub: now - 2 * H });
seed(db, { id: 26, title: 'Sprinklr 宣布裁员15%，AI 转型应对增长挑战', pub: now - 1 * H });
db.prepare('UPDATE articles SET title_zh = title WHERE id = 26').run();

seed(db, { id: 20, title: '三星、LG竞相应对人工智能热潮带来的散热挑战' });
db.prepare('UPDATE articles SET title_zh = title WHERE id = 20').run();
seed(db, { id: 21, title: 'Bank of England warns of financial risks from the AI boom',
  zh: '英格兰银行对人工智能热潮带来的金融风险发出警告' });

// 2026-09-04 线上复盘:当日最大事件(英伟达收购 Hugging Face)有 11 个重复头
// 挂在时间线上,一对候选都没提名。病根是原先的「稀有锚」(共享 token 的文档
// 频率 ≤5)与新闻热度成反比 —— 事件越大,它的专有词出现在越多标题里
// (实测 hugging 当日 df=31),于是一个 token 都当不了锚。最该合并的反而不被
// 提名。以下 12 条是当日线上真实标题。
const HOT = [
  ['英伟达将以 12.9B 美元的人工智能基础设施交易收购 Hugging Face', 'Nvidia to acquire Hugging Face in $12.9B AI infrastructure deal'],
  ['NVIDIA 同意以 2 万亿日元收购美国人工智能初创公司 Hugging Face', 'NVIDIA、米AIスタートアップHugging Faceを2兆円で買収へ'],
  ['开放模式激增，英伟达将以 129.3 亿美元收购 Hugging Face', 'Open models surge as Nvidia buys Hugging Face for $12.93B'],
  ['近 130 亿美元喜提"AI 界 GitHub"，英伟达宣布将正式收购 Hugging Face', null],
  ['英伟达或以 129.3 亿美元收购 Hugging Face，但公开运营仍将继续', 'Nvidia may buy Hugging Face for $12.93B, public operation continues'],
  ['NVIDIA 坚称 129.3 亿美元收购 Hugging Face 将逃避反垄断审查', 'NVIDIA insists $12.93B Hugging Face buy escapes antitrust review'],
  ['Nvidia 收购 Hugging Face 以推动开源技术', 'Nvidia acquires Hugging Face to push open source'],
  ['NVIDIA以119亿美元收购全球AI平台"Hugging Face"', 'NVIDIA、全世界のAIプラットフォーム「Hugging Face」を119億ドルで買収'],
  ['NVIDIA将收购初创公司Hugging Face = 2万亿日元，开启AI', 'NVIDIAがスタートアップHugging Faceを買収＝2兆円'],
  ['英伟达豪掷140亿美元收购Hugging Face？分析师：或重构全球AI开源体系', null],
  ['NVIDIA 宣布收购 Hugging Face。约2万亿日元，强化AI领域主导地位', 'NVIDIA、Hugging Face買収を発表。約2兆円'],
  ['Nvidia 以 13B 美元收购 Hugging Face 对 AI 模型选择意味着什么', 'What Nvidia\'s $13B Hugging Face buy means for AI model choice'],
];
HOT.forEach(([zh, en], i) => {
  const id = 40 + i;
  seed(db, { id, title: en || zh, zh: en ? zh : null, pub: now - (2 + i * 0.1) * H });
  if (!en) db.prepare('UPDATE articles SET title_zh = title WHERE id = ?').run(id);
});

test('词面筛选:同事件跨语言对进候选,盘点体不进', () => {
  const pairs = mergeCandidates(db, { now });
  const keys = new Set(pairs.map((p) => [p.a.id, p.b.id].sort((x, y) => x - y).join(':')));
  assert.ok(keys.has('1:2'), '日文版译文 × 中文原生应当是候选');
  assert.ok(keys.has('2:3'), '日文版译文 × 英文版译文应当是候选');
  assert.ok(keys.has('25:26'), '同公司不同事件的套话对会进候选 —— 裁决是 LLM 的事');
  assert.ok(!keys.has('5:6'), '盘点体长标题不得进候选');
  for (const k of keys) assert.ok(!k.split(':').includes('5'), '盘点体不与任何行配对');
});

test('大事件不因为「报的人多」而失去提名资格', () => {
  const pairs = mergeCandidates(db, { now });
  const hot = pairs.filter((p) => p.a.id >= 40 && p.b.id >= 40);
  assert.ok(hot.length >= 6, `12 个同事件头应当互相提名,实际 ${hot.length} 对`);
  // 每个头都要有出路:12 条里至少 10 条进了某一对,否则并簇会剩一地碎片
  const covered = new Set(hot.flatMap((p) => [p.a.id, p.b.id]));
  assert.ok(covered.size >= 10, `应有至少 10 个头进入候选,实际 ${covered.size}`);
});

// 裁决预算的保证是全局的:每个头只提名最像的 3 个,所以候选总数最多是
// 头数×3(一个头会被别人选中,单看某一行的出现次数并不受 3 的约束)。
test('候选总量随头数线性封顶 —— 大事件不会灌爆裁决预算', () => {
  const pairs = mergeCandidates(db, { now });
  const heads = db.prepare('SELECT COUNT(*) n FROM articles WHERE is_original = 1 AND relevant = 1').get().n;
  assert.ok(pairs.length <= heads * 3, `候选 ${pairs.length} 对超过头数 ${heads} × 3`);
  // 同时不能退化成「只提名一两对」——那样大事件又碎了
  assert.ok(pairs.length >= 8, `候选只有 ${pairs.length} 对,召回过低`);
});

test('LLM 确认的对并簇(链式归并到最早的头),否决的对入缓存不再重问', async () => {
  let calls = 0;
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (_url, opts) => {
    calls++;
    const body = JSON.parse(opts.body);
    const lines = body.messages[1].content.split('\n');
    // 裁决规则如实:GitLab 对是同一事件,其余不是。
    const arr = lines.map((l, i) => ({ i, s: /gitlab/i.test(l) ? 1 : 0 }));
    return { ok: true, json: async () => ({ choices: [{ message: { content: JSON.stringify(arr) } }] }) };
  };
  try {
    const r1 = await mergeTranslatedPending({ limit: 100, budgetMs: 5000, now });
    assert.ok(r1.merged >= 2, 'GitLab 两对确认后应并成一簇');
    assert.ok(calls >= 1);

    const rows = Object.fromEntries(db.prepare(
      'SELECT id, cluster_id, is_original, cluster_n, cluster_latest FROM articles WHERE id IN (1,2,3,4)')
      .all().map((r) => [r.id, r]));
    // 谁早谁当头:中文原生(id 1)最早,三个版本 + 转载全归到它。
    for (const id of [1, 2, 3, 4]) assert.equal(rows[id].cluster_id, 1, `id ${id} 应归入簇 1`);
    assert.equal(rows[1].is_original, 1);
    assert.equal(rows[2].is_original, 0, '被并掉的头摘掉首发标记');
    assert.equal(rows[3].is_original, 0);
    assert.equal(rows[1].cluster_n, 4, '簇成员数记在新头上');
    assert.equal(rows[1].cluster_latest, now - 0.5 * H, '最新动态时间跟着最晚的成员');
    assert.equal(rows[2].cluster_n, null, '旧头的物化字段清空');

    const vetoes = db.prepare('SELECT COUNT(*) n FROM merge_verdicts WHERE same = 0').get().n;
    assert.ok(vetoes >= 1, '否决要落缓存');

    // 第二轮:确认对已并簇不再是头,否决对被缓存挡住 —— 一次 LLM 都不该打。
    const callsBefore = calls;
    const r2 = await mergeTranslatedPending({ limit: 100, budgetMs: 5000, now });
    assert.equal(calls, callsBefore, '第二轮不得重问已裁决的对');
    assert.equal(r2.merged, 0);
  } finally { globalThis.fetch = realFetch; }
});

test('applyMerge 解析簇根,重复并簇是无操作', () => {
  assert.equal(applyMerge(db, 2, 3), false, '同簇的两行再并是无操作');
});

test('没配 LLM 时一对都不并 —— 错并比漏并伤害大', async () => {
  // 本测试文件配了假凭据,这里只验证:mock 之外不发真实请求的前提下,
  // 候选存在但 LLM 不可达时,merged 恒为 0(失败不致命,下一轮重试)。
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error('network down'); };
  try {
    seed(db, { id: 30, title: 'DeepSeek opens its first native vision model',
      zh: 'DeepSeek 开启其首个原生视觉模型', pub: now });
    seed(db, { id: 31, title: 'DeepSeek 开源首个原生视觉模型，评测基准公开', pub: now });
    db.prepare('UPDATE articles SET title_zh = title WHERE id = 31').run();
    const r = await mergeTranslatedPending({ limit: 100, budgetMs: 3000, now });
    assert.equal(r.merged, 0, 'LLM 不可达时不得并簇');
    assert.ok(r.failed >= 1);
    const heads = db.prepare('SELECT is_original FROM articles WHERE id IN (30,31)').all();
    assert.deepEqual(heads.map((h) => h.is_original), [1, 1], '两行都还是头');
  } finally { globalThis.fetch = realFetch; }
});
