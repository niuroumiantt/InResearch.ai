// Second gate: value (值不值得读). relevance.js answers "is this about AI";
// this answers "does it matter to someone studying the AI ecosystem".
//
// 2026-08-31 实测(300 条线上样本人工复核):相关闸门放进来的内容里 64% 是
// 低价值 —— 荐股导购、校园获奖、政务活动稿、企业"我们也用了AI"通稿。它们
// *确实*在讲 AI,词法相关性挡不住,必须有第二根轴。
//
// 两级实现:
//   启发式(本文件)   —— 入库即打分,零成本,规则抓最机械的体裁;
//   LLM(classify.js) —— 配了 ST_CLASSIFY 后逐批精化,覆盖写法无穷的通稿。
//
// 档位定义(存 articles.value):
//   3 必读  前沿实验室/芯片供应链/重大融资/监管实质动作/重要研究
//   2 可读  行业公司实质性落地、有信息量的分析
//   1 边角  "某公司也用了AI"通稿、活动预告、地方产业新闻
//   0 垃圾  导购/软文/表彰/误报

/** 一线信号:标题里出现即说明在讲生态主干。全部小写比对。 */
const FRONTIER = [
  'openai', 'anthropic', 'deepmind', 'chatgpt', 'gpt-5', 'gpt-4', 'claude',
  'gemini', 'deepseek', 'xai', 'grok', 'meta ai', 'llama', 'mistral', 'qwen',
  'nvidia', 'tsmc', '台积电', '台積電', 'sk hynix', 'sk하이닉스', '하이닉스',
  'hbm', 'asml', 'micron', 'broadcom', 'amd ', 'cuda',
  '英伟达', '輝達', 'エヌビディア', '엔비디아',
  // 数据中心供应链核心厂商(2026-08-31 与 relevance.js 同步补齐)
  '美光', '镁光', '铠侠', '海力士', '三星电子', '阿斯麦', '应用材料', '东京电子',
  '博通', '迈威尔', '超微电脑', 'supermicro', 'cowos', '先进封装',
  '英特尔', '高通', 'qualcomm', '中际旭创', '新易盛',
  'glm-4', 'glm-5', 'chatglm', '智谱清言',
  '智谱', '通义', '豆包', '文心', '月之暗面', 'kimi', 'minimax', '深度求索',
  '字节跳动', '阿里', '百度', '腾讯', '华为', '昇腾', '寒武纪',
  'sam altman', 'dario amodei', 'jensen huang', '黄仁勋', 'demis hassabis',
  'softbank', 'ソフトバンク', '소프트뱅크', 'naver', '네이버', 'kakao', '카카오',
  'hugging face', 'huggingface', 'perplexity', 'agi',
];

/** 实质动作,按 MECE 内容分类拆成三桶 —— 命中哪桶,启发式就猜哪类。 */
const POLICY_WORDS = [
  '立法', '法案', '监管', '禁令', '出口管制', '禁售', '诉讼', '起诉', '版权',
  'regulation', 'ban', 'export control', 'lawsuit', 'copyright',
  'antitrust', 'executive order', '規制', '提訴', '규제', '소송',
];
const BUSINESS_WORDS = [
  '融资', '收购', '并购', '上市', '裁员', '估值', '财报', '营收', '销售额',
  'raises', 'funding', 'investment', 'acquire', 'acquisition', 'merger', 'ipo', 'layoff',
  'valuation', 'earnings', 'revenue', 'annualized sales',
  '買収', '資金調達', '투자 유치', '인수', '상장',
];
const BUILD_WORDS = [
  '发布', '開源', '开源', '论文', '评测', '基准', '数据中心', '建厂', '量产',
  '投产', '流片',
  'launch', 'release', 'unveil', 'open-source', 'open source', 'open weights',
  'benchmark', 'breakthrough', 'datacenter', 'data center', 'gigawatt', 'fab ',
  'mass production', 'モデル公開', 'オープンソース', '量産',
  '출시', '공개', '데이터센터', '반도체',
  'pauses', 'halts', 'tests', 'trains', 'pledges', 'signs', 'opens', 'expands',
  '暂停', '叫停', '测试', '训练', '承诺', '签署', '开放', '扩建',
];
const SUBSTANCE = [...POLICY_WORDS, ...BUSINESS_WORDS, ...BUILD_WORDS];
// `includes('sues')` also matched "issues" and `includes('invest')` matched
// "investigating". Action verbs need word boundaries; nouns stay in the lists.
const POLICY_ACTION = /\bsu(?:e|es|ed|ing)\b/i;
const BUSINESS_ACTION = /\binvest(?:s|ed|ing)?\b/i;

/** MECE 内容分类(genre):一篇只归一类,难分时按下面的优先级取先。
 *  这是「穷尽且互斥」的那套归档;查询词(angle)继续允许重叠,负责撒网。 */
export const GENRES = ['policy', 'safety', 'business', 'compute', 'model', 'apps', 'society', 'noise', 'other'];

function guessGenre(hay, angle, frontier) {
  if (hasAny(hay, POLICY_WORDS) || POLICY_ACTION.test(hay) || angle === 'policy') return 'policy';
  if (angle === 'safety') return 'safety';
  if (hasAny(hay, BUSINESS_WORDS) || BUSINESS_ACTION.test(hay) || angle === 'money') return 'business';
  if (angle === 'chips' || angle === 'infra') return 'compute';
  if (frontier || angle === 'models' || angle === 'research') return 'model';
  if (angle === 'apps') return 'apps';
  return 'other';   // 启发式只做粗判,LLM 精化时按内容重归
}

/** 荐股导购 + 盘面异动/资金流水 —— 一票否决到 0。
 *  股价涨跌和融资融券数据对研究生态没有信息量,哪怕主语是寒武纪。
 *  词要具体,避免误伤正经财经报道(融资≠融资买入)。 */
const LISTICLE = [
  'stocks to buy', 'etf to buy', 'etfs to buy', ' etf ', ' etfs ', 'no-brainer',
  'should you buy', 'price target', 'earnings preview', 'millionaire',
  'buy and hold', 'stock split', 'dividend stock',
  'best stocks', 'top stocks', 'undervalued', 'intraday', 'shares slip',
  'shares surge', 'stock dips', 'stock jumps',
  '概念股', '龙头股', '买入并长期持有', '涨停', '跌停', '牛股', '收益率',
  '午后拉升', '盘中拉升', '逆势拉升', '涨近', '升逾', '跌逾', '异动',
  '融资买入', '融资融券', '折价率', '净值', '份额', '股价',
  // 汽车/消费品价格通稿:「鸿蒙智行 S800 交付 138.8 万元起」这类(2026-08-31 实拍)
  '万元起', '预售价', '正式交付', '开启预订', '首发价',
  '株価', '銘柄', '수혜주', '테마주', '관련주 ', '주가 ', '급등', '급락',
  // 韩语助词贴着名词写:「주가 」带空格盖不住「주가는/주가가」;「수혜 전망」
  // (受益前景)是行情稿句式,「수혜주」一个词盖不住拆开写的(2026-09-01 实拍)。
  '주가는', '주가가', '수혜 전망',
  '盘中下跌', '盘中上涨',
  // 2026-09-01 线上 24h 复核补的三类漏网体裁(样本在 value.test.js):
  // 盘面综述/收盘简报 —— 一天行情打包,不含任何单条新闻的信息量;
  'morning brief', 'markets need to know', 'market wrap', 'markets wrap',
  'stock market today', 'premarket', 'closing bell', 'top gainers', 'top losers',
  // 券商评级/研报导读 —— 观点买卖,不是事实进展;
  'research picks', 'buy rating', 'sell rating', 'initiates coverage',
  'bullish on', 'bearish on', '买入评级', '增持评级', '评级上调', '评级下调',
  '维持买入', '目标价', '荐股',
  // ETF 行情 —— 既有的 ' etf ' 两侧要空格,中文标题里「影视ETF暴涨」贴着写,漏了。
  'etf暴涨', 'etf暴跌', 'etf大涨', 'etf大跌', 'etf上涨', 'etf下跌', 'etf涨幅',
  // 2026-09-01 晚间站长实拍补的三类(样本在 value.test.js):
  // 个股行情 —— 只认「stock/shares + 价格动词」的组合,单词 stock 不进表:
  // stockpile(库存)和实义 shares(分享)是正经供应链/产品报道的常用词。
  'stock swings', 'stock drops', 'stock falls', 'stock fell', 'stock rises',
  'stock rose', 'stock slides', 'stock slips', 'stock sinks', 'stock plunges',
  'stock tumbles', 'stock soars', 'stock climbs', 'stock rallies', 'stock gains',
  'stock steadies', 'stock opens', 'stock opened', 'stock turns', 'stock edges',
  'shares fall', 'shares fell', 'shares drop', 'shares rise', 'shares rose',
  'shares slide', 'shares sink', 'shares plunge', 'shares tumble', 'shares soar',
  'shares climb', 'shares rally', 'shares gain',
  '股票下跌', '股票上涨', '股票大涨', '股票大跌',
  // 投资分析体:「XX Stock: 观点」与带股票代码的「Stock (TICKER)」。
  ' stock: ', ' stock (', ' shares (',
  // 市场规模报告贩子(grandviewresearch 们):卖报告的 SEO 文,不是新闻。
  'market report', 'market size', 'market forecast', 'market to reach',
  'market worth', 'cagr',
  // 2026-09-01 深夜站长实拍第四批(样本在 value.test.js):
  // 受益股句式 ——「Stocks That Will/Could Benefit」,钉「stocks that 」整个句式
  // (原有的 'stocks that could' 并入这一条,一件事一处实现);
  'stocks that ',
  // 打新/新股申购 —— 零售打新导购,不是产业新闻;
  '打新', '中一签', '新股申购',
  // 导购 SEO 文 ——「推荐哪款」「闭眼入」「选购指南」是导购文的句式骨架,
  // 单独的「推荐」不进表(推荐系统是正经研究方向);
  '闭眼入', '推荐哪款', '选购指南',
  // Show HN 自荐帖 —— 论坛自荐固定前缀,项目展示不是新闻报道。
  'show hn:',
  // 回购/资金流/杠杆 ETF/券商调级是证券交易信息，不是 AI 产业进展。
  'share repurchase', 'stock repurchase', 'share buyback', 'stock buyback',
  'leveraged fund', 'leveraged etf', 'inverse etf', 'files for etf',
  'analyst upgrade', 'analyst downgrade', 'upgrades stock', 'downgrades stock',
  'raises price target', 'cuts price target',
  '股份回购', '股票回购', '回购金额', '净买入', '净卖出', '北水加仓', '南向资金',
  '上调股票评级', '下调股票评级', '上調股票評級', '下調股票評級',
  // 市场日报/多题拼盘不是单一可行动事件。
  "barron's daily", 'market daily', 'daily market', 'daily roundup',
  // 2026-09-04 每日报表实拍第五批(样本在 value.test.js):
  // 中文多题拼盘 —— 一条标题装一天的新闻,单条的信息量为零;
  '晚间文摘', '早间文摘', '外盘头条', 'a股头条', '港股头条', '美股讯号',
  '今日华尔街', '盘前必读', '盘后必读',
  // 行情解说的固定尾巴 ——「什么在推动市场」「下一步催化剂」。
  // 单独的「催化剂」不进表:AI 发现新催化剂是正经材料学新闻。
  '在推动市场', '下一步催化剂', '股价催化剂',
  // 2026-09-04 部署后复核:上面这批中文指纹是从**译文**提炼的,而判分跑在
  // 原题上 —— 漏网的四条原题全是英文。同一批体裁的英文写法一并钉住。
  'evening digest', 'morning digest', 'daily digest', 'wall street today',
];

/** 用户明确不收的消费层：手机/PC/游戏/眼镜/提示词教程。即使主语是 Gemini、
 * ChatGPT 或 Nvidia，也不因头部实体获得豁免。 */
const CONSUMER = [
  'smartphone', 'smart phone', 'mobile phone', 'handset', 'iphone', 'android phone',
  'laptop', 'gaming pc', 'pc gaming', 'video game', 'new game', 'games announced',
  'geforce now', 'dlss', 'vive ', 'headset', 'smart glasses', 'wearable',
  'photo editing prompt', 'image editing prompt', ' prompts to ', ' prompts for ', 'prompt ideas',
  'photo tips', 'how to use chatgpt', 'tips and tricks',
  '手机', '笔记本电脑', '消费级', '游戏', '智能眼镜', '头显', '照片编辑提示',
  '修图提示', '提示词大全', '使用教程',
];

const EMPTY_PUFFERY = [
  'ai赋能', 'ai 赋能', '重磅发布', '解决方案发布', 'solution launched',
  'empowered by ai', 'powered by ai solution',
];

const POLITICAL_TALK = [
  'candidate says', 'nominee says', 'campaign says', 'says he will', 'says she will',
  '候选人表示', '提名人表示', '竞选承诺',
];

// 评级句序变化很多，但不能把单独 upgrade 当噪音（产品升级是正经新闻）。
// 只有 upgrade/downgrade 与 stock 在同一个短标题片段内同时出现才否决。
const MARKET_RATING = /(?:upgrades?|downgrades?).{0,60}\bstock\b|\bstock\b.{0,60}(?:rating|upgrade|downgrade)/i;

// 中文券商评级。整词「上調股票評級」盖不住公司名夹在中间的写法
// (「麥格理上調博通股票評級」,2026-09-04 实拍),所以钉动词与「评级」的
// 共现。关键是不能杀掉 AI 安全报道 —— 当日线上就有「第一个『关键』安全
// 评级模型」「『风险』评级已确认」。区别在结构:券商稿是「动词 → 评级」
// (上调/维持/重申…评级)或「评级 → 调整」(评级从中性上调),而安全稿里
// 「评级」是被修饰的名词(安全评级/风险评级已确认),前面没有这类动词。
const CN_RATING = new RegExp([
  '(?:上调|上調|下调|下調|维持|維持|重申|确认|確認|首予|给予|給予)[^，。；;]{0,14}(?:评级|評級)',
  '(?:评级|評級)[^，。；;]{0,6}(?:从|從|升级|升級|上调|上調|下调|下調|提升)',
  '(?:投资|投資|股票|行业|行業|esg)(?:最新)?(?:评级|評級)',
].join('|'));

// 股价问句体:「XX 为何仍在下跌?」「为何大涨?」—— 行情解说,不含新事实。
// 只认「为何 + 价格动词」的搭配,「为何 OpenAI 选择自研芯片」不受影响。
const CN_PRICE_Q = /为何[^，。；;？?]{0,10}(?:下跌|大跌|暴跌|走低|上涨|大涨|暴涨|走高|飙升)/;

// 投资导购:「如何购买 XX 股票」。「如何购买」单独不进表(买算力、买显卡
// 都是正经话题),要跟「股」同现。
const CN_BUY_STOCK = /如何(?:购买|購買|买入|買入|购入)[^，。；;]{0,12}股/;

// 英文股价问句。三天 9,632 条原题里 19 条以 why 开头,多数是正经的政策/
// 安全/技术解释(「Why are AI safety experts alarmed…」「Why is NYC banning
// AI…」),所以 why 单独绝不能杀 —— 必须同时出现行情名词,或跌价动词。
// 用 shares 的名词形不进表:「OpenAI shares new details」是实义动词。
const EN_PRICE_Q_MARKET = /^(?=[\s\S]*\bwhy\b)(?=[\s\S]*\b(?:stock|stocks|share price|index)\b)/i;
// 「falling behind」是「落后」不是「下跌」,单独排除。
const EN_PRICE_Q_VERB = /\bwhy\s+(?:is|are|did|does)\b[^?]{0,40}\b(?:falling(?! behind)|sliding|dropping|sinking|plunging|tumbling|slumping)\b/i;
// 行情解说尾巴的英文写法(what's / what’s / whats 三种撇号都要认)。
const EN_MOVING_MARKETS = /what.{0,3}s moving (?:the )?markets?/i;

const NOISE_PATTERNS = [MARKET_RATING, CN_RATING, CN_PRICE_Q, CN_BUY_STOCK,
  EN_PRICE_Q_MARKET, EN_PRICE_Q_VERB, EN_MOVING_MARKETS];

/** 活动/表彰/通稿体裁。命中≈公关稿,顶格 1;不带一线信号直接 0。 */
const CEREMONY = [
  '荣获', '斩获', '揭牌', '签约仪式', '成功举办', '圆满', '授牌', '表彰',
  '获奖', '获佳绩', '走进', '调研', '座谈', '研学', '开班', '结业', '捐赠',
  '启动仪式', '论坛在', '研讨会在', '培训班', '宣讲',
  '受賞', 'ウェビナー', 'セミナー', 'キャンペーン', 'フォーラム開催',
  '업무협약', 'mou 체결', '시상식', '수상', '포럼', '간담회', '설명회',
  '교육청', '박람회', '컨퍼런스 개최', '국제교류', '현장체험', '견학',
  'wins award', 'award ceremony', 'medal', 'olympiad', 'hackathon winners',
  '公职人员', '素养评价', '现场体验', '交流团', '考察团',
];

const lc = (s) => String(s || '').toLowerCase().normalize('NFKC');
const hasAny = (hay, list) => list.some((w) => hay.includes(w));

/**
 * 启发式价值分。刻意保守:规则只钉死最机械的体裁,吃不准的给 1-2,
 * 留给 LLM 精化 —— 宁可让边角料多活一会,不能把必读错杀成 0。
 * @returns {{value:number, genre:string}}
 */
export function scoreValue({ title = '', angle = '', relevance = 0, relevant = 1 }) {
  if (!relevant) return { value: 0, genre: 'noise' };
  const hay = ` ${lc(title)} `;
  if (hasAny(hay, LISTICLE) || NOISE_PATTERNS.some((re) => re.test(hay))) return { value: 0, genre: 'noise' };
  if (hasAny(hay, CONSUMER)) return { value: 0, genre: 'noise' };

  const frontier = hasAny(hay, FRONTIER);
  if (hasAny(hay, EMPTY_PUFFERY) && !frontier) return { value: 0, genre: 'noise' };
  if (hasAny(hay, CEREMONY)) return { value: frontier ? 1 : 0, genre: 'noise' };

  const genre = guessGenre(hay, angle, frontier);
  const substance = hasAny(hay, SUBSTANCE) || POLICY_ACTION.test(hay) || BUSINESS_ACTION.test(hay);
  if (hasAny(hay, POLITICAL_TALK)) return { value: 1, genre };
  // v3 必须同时有核心主体和实质动作；高相关分不再替代“发生了什么”。
  if (frontier && substance) return { value: 3, genre };
  if (frontier) return { value: 2, genre };
  // region 车道实测 106/300 几乎全是地方通稿:没有一线信号就顶格 1。
  if (angle === 'region') return { value: 1, genre };
  if (substance) return { value: 2, genre };
  return { value: 1, genre };
}

/**
 * 重打所有仍是启发式打分的行(LLM 精化过的不动)。serve 启动时跑一次:
 * 6 万行量级几秒钟,换来的是**词表改进追溯生效** —— push 一版新负面词,
 * 两分钟后部署,历史里的同类垃圾在下一次启动统一沉底,不用登服务器。
 *
 * 顺便用当前的相关性闸门复核旧行:老库里躺着按旧词表放进来的误报
 * (Claude Lemieux 们),闸门升级后它们的 value 直接归零 —— 不改 relevant
 * 字段(那是历史事实),只是让默认视图看不见它们。
 */
export function backfillValues(db, { scoreRelevance } = {}) {
  // llm 行也过一遍,但只执行一票否决(见循环里的分支):线上复核发现
  // 行情/荐股垃圾大半是精化批次打的分,只重打 heur 行的话,词表每次
  // 改进都对这批存量失效 —— 堵住的口子在历史里一直开着。
  const rows = db.prepare(`SELECT id, title, angle, relevance, relevant, query, value, value_src FROM articles
                           WHERE value IS NULL OR value_src = 'heur' OR value_src IS NULL
                              OR value_src = 'llm'`).all();
  if (!rows.length) return 0;
  const upd = db.prepare("UPDATE articles SET value = ?, genre = ?, value_src = 'heur' WHERE id = ?");
  db.exec('BEGIN');
  try {
    for (const r of rows) {
      let v = scoreValue(r);
      const titleRelevant = !scoreRelevance
        || scoreRelevance({ title: r.title, query: r.query || '' }).relevant;
      // 标题是所有来源共用的最后一道硬门。描述全文、查询词或旧 LLM 都不能替
      // 一个不含 AI 主体的标题进入读者时间线。
      if (!titleRelevant) v = { value: 0, genre: 'noise' };
      // 精化分数是花钱买来的判断,启发式不推翻它 —— 除非词表一票否决:
      // 那是结构性事实(荐股导购/盘面综述),对谁打的分都生效。
      if (r.value_src === 'llm') {
        if (v.value === 0) upd.run(0, 'noise', r.id);
        // 旧模型可能把明确的“头部主体 + 融资/收入/发布”等事实压成 0。
        // 只允许最强的结构性正证据(v3)纠正它，不用宽松的 v1/v2 复活边角料。
        else if (r.value === 0 && v.value === 3) upd.run(3, v.genre, r.id);
        continue;
      }
      // 带上原 query:CJK 查询有 +1 加成,复核要按当年同样的条件跑,
      // 否则一批当年 3 分擦线的中文行会被冤枉。
      upd.run(v.value, v.genre, r.id);
    }
    db.exec('COMMIT');
  } catch (e) { db.exec('ROLLBACK'); throw e; }
  return rows.length;
}
