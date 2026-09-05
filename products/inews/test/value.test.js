// 价值轴(第二根轴)的判例。relevance 说"是不是 AI",value 说"值不值得读"——
// 2026-08-31 线上 300 条实测 64% 低价值之后加的这一层。样本全部来自真实时间线。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { scoreValue } from '../src/lib/value.js';

const v = (title, extra = {}) => scoreValue({ title, relevant: 1, relevance: 4, ...extra });

test('荐股导购一票否决到 0', () => {
  assert.equal(v('1 No-Brainer Artificial Intelligence (AI) ETF to Buy With $50 and Hold for the Long Term').value, 0);
  assert.equal(v('3 Founder Led AI Infrastructure Stocks Built For Higher Rates: top stocks to watch').genre, 'noise');
  assert.equal(v('AI 概念股全线涨停，龙头股再创新高').value, 0);
});

test('活动/表彰通稿顶格 1,不带一线信号直接 0', () => {
  assert.equal(v('西安培华学院在2026 高校人工智能财经案例大赛中斩获佳绩').value, 0);
  // region 顶格 1(默认视图 ≥2 同样不可见);LLM 精化后会进一步压到 0
  assert.ok(v('坡州市教育厅密切现场支持"以人为本的人工智能教育"', { angle: 'region' }).value <= 1);
  assert.equal(v('AI WAN中国行广东站暨智能IP广域网产业研讨会在广州成功举办').value, 0);
  // 一线公司办的活动:边角料,但不算垃圾
  assert.equal(v('NVIDIA 荣获年度最佳合作伙伴奖').value, 1);
});

test('前沿实验室 + 实质动作 = 必读', () => {
  assert.equal(v('OpenAI pauses work on new version of ChatGPT after it shows concerning behaviour', { relevance: 7 }).value, 3);
  assert.equal(v('Anthropic raises $30B at record valuation', { relevance: 5 }).value, 3);
  assert.equal(v('DeepSeek 开源新一代推理模型，评测基准全面领先', { relevance: 8 }).value, 3);
});

test('region 车道没有一线信号顶格 1', () => {
  assert.equal(v('忠清南道1000名女性农民齐聚一处……人工智能农业开启新纪元', { angle: 'region' }).value, 1);
  // 但 region 里出现一线信号照样往上走
  assert.ok(v('现代汽车与 NVIDIA 齐聚,共建 AI 数据中心', { angle: 'region' }).value >= 2);
});

test('不相关的行永远是 0', () => {
  assert.equal(v('anything at all', { relevant: 0 }).value, 0);
});

// 2026-09-01 线上 24h 复核:必读档里混着 61 条行情/荐股体裁。三类指纹——
// 盘面综述、券商评级/研报导读、ETF 行情——全是当天时间线上的真实标题。
test('盘面综述/券商评级/ETF 行情一票否决到 0', () => {
  assert.equal(v('AM Markets Need to Know: Nasdaq rebounds in August, Anthropic valuation talk').value, 0);
  assert.equal(v('Wall Street Morning Brief: US stocks enter historically weak September').value, 0);
  assert.equal(v('Global Research Picks | Goldman Sachs: Memory prices remain on upcycle').value, 0);
  assert.equal(v('Lynx Equity grows bullish on Nvidia after $3.5B MediaTek investment').value, 0);
  assert.equal(v('AI长剧引爆行情！影视ETF暴涨超7%，是昙花一现还是新机遇？').value, 0);
  assert.equal(v('机构维持买入评级，目标价上调至200美元：AI芯片龙头获看好').value, 0);
});

// 行情词表扩了就要防误伤:真实的供应链投资/融资是必读,「invest」不是行情词。
test('正经供应链投资与融资不被行情词表误伤', () => {
  assert.equal(v('Nvidia invests $3.5 billion in MediaTek AI chip deal', { relevance: 7 }).value, 3);
  assert.equal(v('Micron Technology CEO vows deeper Taiwan investment as AI grows', { relevance: 6 }).value, 3);
});

test('动作词只按完整单词命中，不把 issues 和 investigating 当诉讼或投资', () => {
  const outage = v('Claude is experiencing issues worldwide', { angle: 'safety', relevance: 7 });
  assert.deepEqual(outage, { value: 2, genre: 'safety' });
  const qna = v('Q&A: OpenAI is investigating an internal incident', { angle: 'models', relevance: 7 });
  assert.deepEqual(qna, { value: 2, genre: 'model' });
  assert.deepEqual(v('OpenAI sues a model-scraping startup', { relevance: 7 }),
    { value: 3, genre: 'policy' });
  assert.deepEqual(v('Nvidia will invest $3B in HBM capacity', { relevance: 7 }),
    { value: 3, genre: 'business' });
});

// 2026-09-01 晚间站长实拍:默认视图里仍有一批「个股行情 + 投资分析 + 市场
// 规模报告」体裁。否决跑在英文原题上,以下全部是当晚时间线的原题。
test('个股行情/投资分析体/市场规模报告一票否决到 0', () => {
  assert.equal(v('Hut 8 Stock Swings From Higher to Lower After Report of $35 Billion AI Deal').value, 0);
  assert.equal(v('Rezolve AI Stock Drops After Net Loss Widens – CEO Says Google Is Just The Beginning').value, 0);
  assert.equal(v('Marvell Stock: The AI Growth Story Is Getting Bigger, But the Google Deal Is Still a Problem').value, 0);
  assert.equal(v('Applied Materials Inc Stock (AMAT) Opened Down by 3.68% on Sep 1: Drivers Behind the Movement').value, 0);
  assert.equal(v('AI-Enabled Clinical Laboratory Analyzers Market Report 2033, With Abbott, Danaher & Siemens').value, 0);
});

// 2026-09-01 深夜站长实拍第三批:受益股句式、导购 SEO 文、打新、Show HN
// 自荐帖仍在默认视图里。以下全部是当晚时间线的原题。
test('受益股句式/导购SEO文/打新/自荐帖一票否决到 0', () => {
  assert.equal(v('Two Stocks That Will Benefit From OpenAI Announcement').value, 0);
  assert.equal(v('2026办公好用的手机推荐：折叠屏AI旗舰领跑，这5款按预算闭眼入+FAQ').value, 0);
  assert.equal(v('2026智能空调推荐哪款？真AI三大标准+4款闭眼入指南+FAQ').value, 0);
  assert.equal(v('Show HN: HN Match Maker – Matching "Who Wants to Be Hired?" With "Who\'s Hiring?"').value, 0);
  assert.equal(v('中一签或赚超20万！AI芯片新股来了，打新早知道').value, 0);
  // 韩语行情稿:主体是交易信息(受益前景+股价回落),不是交易本身的新事实。
  assert.equal(v('헛8, 앤트로픽·람다 350억달러 AI 계약 수혜 전망…주가는 반락').value, 0);
});

// 「推荐」「受益」都是常用词,只钉句式,正经报道不误伤。
test('推荐系统研究与正经受益报道不被导购词表误伤', () => {
  assert.ok(v('Meta 开源新一代推荐系统模型，引入生成式检索', { relevance: 6 }).value >= 2);
  assert.ok(v('台积电财报显示 AI 芯片需求带动营收大涨', { relevance: 6 }).value >= 2);
});

// stock/shares 是常用词,组合词表只认「价格动词」搭配 —— 库存与实义 shares 不误伤。
test('stockpile 与实义 shares 不被个股行情词表误伤', () => {
  assert.ok(v('Nvidia stockpiles HBM ahead of next-gen GPU ramp', { relevance: 6 }).value >= 2);
  assert.ok(v('OpenAI shares new details of its Texas data center buildout', { relevance: 7 }).value >= 2);
});

test('消费硬件、游戏和提示词教程一票否决', () => {
  assert.equal(v('HTC launches $499 Vive Eagle with Gemini or ChatGPT assistant').value, 0);
  assert.equal(v('NVIDIA DLSS 5 leads GeForce NOW launch of 26 new games').value, 0);
  assert.equal(v('Janmashtami AI prompts: 7 Google Gemini photo editing prompts').value, 0);
  assert.equal(v('AI Trend: Use These 6 ChatGPT And Gemini Prompts To Create A Radha Rani Avatar').value, 0);
});

test('回购、资金流、Anthropic ETF 和券商调级不是 AI 产业新闻', () => {
  assert.equal(v('中际旭创连续3日实施股份回购，回购金额超8亿元').value, 0);
  assert.equal(v('北水加仓港股，MINIMAX获净买入逾4亿港元').value, 0);
  assert.equal(v('Tradr files two leveraged ETFs tied to Anthropic').value, 0);
  assert.equal(v('Macquarie upgrades Broadcom stock on Anthropic growth outlook').value, 0);
});

test('头部实体不能仅凭高相关分冒充必读，必须有实质动作', () => {
  assert.equal(v('Gemini photo tips for a holiday', { relevance: 9 }).value, 0);
  assert.equal(v('OpenAI opens ChatGPT ads to businesses', { relevance: 7 }).value, 3);
  assert.equal(v('ChatGPT Ads Surpass $1 Billion Annualized Sales', { relevance: 7 }).value, 3);
});

test('空泛 AI 赋能通稿和候选人口头承诺不进默认时间线', () => {
  assert.equal(v('AI赋能古建纹样修复打印解决方案重磅发布').value, 0);
  assert.equal(v('Candidate says he will ban AI from deciding who gets fired').value, 1);
});

// 2026-09-04 每日报表实拍第五批:博通财报日的中文行情评论、多题拼盘文摘、
// 繁体券商评级、投资导购仍进了必读档(当日我在邮件里手工剔掉的就是这批)。
// 判据都是句式结构,样本全部是当日线上真实标题。
test('中文行情问句/多题拼盘/繁体评级/投资导购一票否决到 0', () => {
  // 股价问句体与「什么在推动市场」——行情解说,不含任何新事实
  assert.equal(v('尽管增长评论强劲，博通为何仍在下跌？由 Investing.com 提供').value, 0);
  assert.equal(v('油价回调，博通令人失望 - 是什么在推动市场 Investing.com').value, 0);
  assert.equal(v('博通盈利分析：问题解答和下一步催化剂 作者：Investing.com').value, 0);
  // 多题拼盘:一条标题装一天的新闻,不是单一可核实事件
  assert.equal(v('晚间文摘：大众宣布裁员，英伟达收购 Hugging Face').value, 0);
  assert.equal(v('9月4日外盘头条：美副总统万斯淡化伊朗冲突规模 OpenAI推出GPT-6 Astra').value, 0);
  assert.equal(v('美股讯号 | 英伟达收购HuggingFace，交易作价119亿美元 ｜#美股资讯#').value, 0);
  assert.equal(v('今日华尔街：美伊紧张局势、博通财报与就业数据——可能影响美股的五个关键因素').value, 0);
  // 券商评级:公司名夹在中间,既有的「上調股票評級」整词盖不住
  assert.equal(v('麥格理上調博通股票評級，看好Anthropic帶來的增長前景 作者 Investing.com').value, 0);
  assert.equal(v('麦格理将博通的评级从中性上调至跑赢大盘').value, 0);
  assert.equal(v('【ESG动态】新易盛（300502.SZ）获华证指数ESG最新评级BBB，行业排名第173').value, 0);
  // 投资导购
  assert.equal(v('投资 Mistral AI |如何购买首次公开募股前的股票').value, 0);
});

// 「评级」「催化剂」「上调」都是正经新闻的常用词 —— 判据必须能分清
// 「投资评级」和「安全评级」,否则会杀掉 AI 安全报道(当日真实标题)。
test('安全评级、科研催化剂、营收上调不被行情词表误伤', () => {
  assert.ok(v('OpenAI 开始推出 GPT-6 Astra，这是其第一个"关键"安全评级模型', { relevance: 7 }).value >= 2);
  // 这条只保「不被评级规则杀成 0」:它拿不到必读是另一个缺口 —— 该媒体把
  // OpenAI 写作「Open AI」,一线信号词表只有连写形式。加空格形式要单独评估
  // (实测三天里 10 条这么写的标题,一半其实是「open AI models」开源泛指)。
  assert.notEqual(v('Open AI Astra，"风险"评级已确认……"我们将做好安全措施准备"', { relevance: 7 }).value, 0);
  assert.notEqual(v('AI 发现新型催化剂，能耗降低 40%').value, 0);
  assert.ok(v('英伟达上调全年营收指引，AI 数据中心需求强劲', { relevance: 7 }).value >= 2);
  assert.notEqual(v('为何 OpenAI 选择自研推理芯片', { relevance: 7 }).value, 0);
});

// 2026-09-04 部署后复核发现的缺口:上一批中文指纹是从**译文**里提炼的,
// 而 scoreValue 跑在**原题**上 —— 四条漏网的原题全是英文
// (Evening digest / Why is Broadcom falling / Wall Street Today /
// what's moving markets),中文指纹永远打不着。两头都要补:
// ① 英文原题的同类句式;② 译文也进判据(外语原题的中文渲染是读者看到的)。
test('英文原题的行情问句与文摘拼盘同样否决到 0', () => {
  assert.equal(v('Evening digest: Volkswagen announces job cuts, Nvidia acquires Hugging Face').value, 0);
  assert.equal(v('Wall Street Today: US-Iran Tensions, Broadcom Earnings To Jobs Data — Five Key Factors').value, 0);
  assert.equal(v('Oil pulls back, Broadcom disappoints - what’s moving markets By Investing.com').value, 0);
  assert.equal(v('Why is Broadcom falling despite strong growth commentary? By Investing.com').value, 0);
  assert.equal(v('Why Is Broadcom Stock Falling Thursday?').value, 0);
  assert.equal(v('Why are Micron and SK Hynix stocks struggling today? It’s the CXMT threat again').value, 0);
});

// 「why」是正经报道的常用开头 —— 三天 9,632 条原题里 19 条以它开头,
// 多数是政策/安全/技术解释。判据必须带行情名词或跌价动词才敢杀。
test('正经的「为什么」报道不被英文问句判据误伤', () => {
  assert.ok(v('Why Is AMD Becoming More Important In Secure AI Infrastructure?', { relevance: 6 }).value >= 2);
  assert.notEqual(v('Why are AI safety experts alarmed by reports OpenAI Astra model uses recurrent depth', { relevance: 7 }).value, 0);
  assert.notEqual(v('Why is New York City banning AI use in public schools through Class 8?').value, 0);
  assert.notEqual(v('Why Did An AI Company Pay Texas Tech $75 Million?').value, 0);
  assert.notEqual(v('Why is prefill unbelievably faster in vLLM than other inference engines?').value, 0);
});

// 判据只看原题(不看译文):试过把机器译文也喂进判据,三天数据实测新沉底
// 108 条,其中大量是正经新闻 —— 译文用词比中文原题松得多,中文词表里的
// 单字词(份额/眼镜)在译文里到处都是,「长鑫存储DRAM份额突破10%」
// 「Meta AI 眼镜诉讼扩大」都被误杀。所以外语来源的同类体裁靠上面的英文
// 指纹拦,不靠译文。
