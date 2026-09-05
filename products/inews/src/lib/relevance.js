// Second gate on accuracy (准). The Google News query already scopes the sweep;
// this scores every returned headline so we can drop the collateral damage
// ("Allen Iverson", "A.I. the movie", "Air India AI-171", 爱奇艺 etc.).
//
// score >= ACCEPT  -> stored as relevant
// score in (0,ACCEPT) -> stored but flagged (visible under "全部" filter)
// score <= 0       -> dropped

export const ACCEPT = 3;

const STRONG = [
  // multi-word / unambiguous
  'artificial intelligence', 'generative ai', 'machine learning', 'deep learning',
  'neural network', 'large language model', 'foundation model', 'frontier model',
  'llm', 'genai', 'agentic', 'ai agent', 'ai model', 'ai chip', 'ai data center',
  'ai datacenter', 'inference', 'transformer model', 'diffusion model', 'chatbot',
  'multimodal', 'fine-tuning', 'rlhf', 'open weights', 'ai safety', 'ai regulation',
  '人工智能', '大模型', '大语言模型', '生成式', '深度学习', '机器学习', '神经网络',
  '智能体', '算力', 'ai芯片', '生成ai', '人工知能', '生成系ai', '인공지능', '생성형',
  'intelligence artificielle', 'inteligencia artificial', 'künstliche intelligenz',
  // 2026-08-31 吸收自 yidian.ai:安全事件与评测的多词短语,无歧义。
  'prompt injection', 'jailbreak', 'red team', 'guardrails', 'model evaluation',
  '提示注入', '大模型越狱', 'ai幻觉', '红队测试',
];

// Unambiguous in a news headline: seeing the word is enough.
const ENTITIES = [
  'openai', 'chatgpt', 'anthropic', 'deepmind', 'google gemini', 'gemini ai',
  'deepseek', 'nvidia', 'huggingface', 'hugging face', 'stable diffusion',
  'midjourney', 'perplexity ai', 'sam altman', 'dario amodei', 'jensen huang',
  'demis hassabis', 'yann lecun', 'ilya sutskever', 'cerebras', 'groq',
  'tpu', 'hbm', 'agi', 'elevenlabs', 'mistral ai', 'claude ai', 'claude code',
  'cognition ai', 'ai startup', 'ai lab', 'ai security', 'ai cluster',
  '智谱', '通义', '豆包', '文心', '月之暗面', 'moonshot ai', 'minimax',
  // 2026-08-31 从 yidian.ai 的成熟词表吸收:芯片实体/型号 + 中国厂商。
  'sk hynix', 'tsmc', 'nvlink', 'infiniband',
  'h100', 'h200', 'b200', 'b300', 'gb200', 'gb300', 'mi300', 'mi355',
  '华为昇腾', '昇腾', '寒武纪', '中芯国际', '海光', '摩尔线程', '长鑫', '长江存储',
  '壁仞', '燧原', '地平线机器人', '商汤', '深度求索', '混元', '星火大模型', '阶跃星辰', '讯飞',
  // 智谱 GLM:裸 glm 撞「广义线性模型」,收带版本/产品名的无歧义变体。
  'glm-4', 'glm-5', 'chatglm', '智谱清言',
  // AI 数据中心供应链全链补齐(2026-08-31 站长点名美光后系统性过了一遍):
  // 存储/代工/设备/EDA/网络/整机/光模块。中文厂商名无歧义直接收;
  // 英文里 intel 是 intelligence 的子串、arm/cadence 是常用词 —— 只收中文名
  // 或带限定的组合,这类坑一个都不能踩。
  'micron technology', '美光', '镁光', 'kioxia', '铠侠',
  '三星电子', 'sk海力士', '海力士',
  'asml', '阿斯麦', 'applied materials', '应用材料', 'lam research', '泛林',
  'tokyo electron', '东京电子', 'kla corp',
  'synopsys', '新思科技', 'cadence design', '楷登',
  'broadcom', '博通', 'marvell', '迈威尔', 'astera labs',
  'supermicro', '超微电脑', '戴尔科技', '慧与',
  '富士康', '鸿海', '广达', '纬创', '英业达',
  'cowos', '先进封装', 'vertiv', '维谛',
  '中际旭创', '新易盛', 'coherent corp', 'lumentum',
  '英特尔', '高通', 'qualcomm', 'arm holdings', '安谋', 'amd instinct', 'epyc',
  // 2026-08-31 全量对齐 news 词库的剩余实体
  '通义千问', '文心一言', 'ymtc', 'cxmt', 'solidigm', '浪潮信息', '中科曙光',
  '工业富联', '日月光', '联发科', '聯發科', '南亞科', '華邦電', '光迅科技',
  'wiwynn', 'inspur', 'celestica', 'coreweave', 'blackwell', 'intel gaudi',
  'stargate', 'trendforce', '集邦', 'epoch ai', 'aleph alpha', 'black forest labs',
  'infineon', '英飞凌',
];

// Real AI entities whose names collide with ordinary English: Claude is a
// first name, Gemini is a star sign, Llama is an animal, Grok/Copilot/
// Transformer are common nouns. Worth full credit only when the headline
// carries no competing signal — see AMBIGUITY_TRAPS below.
// kimi 2026-08-31 从硬实体降级:F1 车手 Kimi Antonelli / Kimi Räikkönen
// 把赛车新闻整条捞上了时间线。
const ENTITIES_SOFT = ['claude', 'gemini', 'llama', 'grok', 'copilot', 'mistral',
  'qwen', 'transformer', 'xai', 'sora', 'codex', 'kimi'];

const CONTEXT = [
  'gpu', 'data center', 'datacenter', 'semiconductor', 'compute', 'model',
  'algorithm', 'automation', 'robot', 'training run', 'benchmark', 'startup',
  'chip', 'cloud', '芯片', '算法', '机器人', '半导体',
  // 2026-08-31 吸收自 yidian.ai:供应链/评测上下文。单词歧义大,只值 +1。
  'dram', 'nand', 'foundry', 'yield', 'inference chip', 'liquid cooling',
  'leaderboard', 'micron', '产能', '量产', '良率', '流片', '断供', '扩产', '跑分', '榜单', '幻觉',
];

// Contexts that make an AI-looking token almost certainly a false positive.
const NEGATIVE = [
  'allen iverson', 'air india', 'artificial insemination', 'avian influenza',
  'bird flu', 'ai weiwei', 'adobe illustrator', '爱奇艺', 'アイ・', '아이돌',
  // zodiac — "Gemini"
  'horoscope', 'zodiac', 'astrology', 'aries', 'taurus', 'scorpio', 'sagittarius',
  'capricorn', 'aquarius', 'pisces', 'libra',
  // obituaries / personal notices — "Claude"
  'obituary', 'funeral', 'passed away', 'survived by', 'celebration of life',
  'memorial service', 'visitation will',
  // animals / places — "Llama", "Grok"
  'llama farm', 'alpaca',
  // athletes — "Claude Lemieux" (NHL) went straight onto the timeline 2026-08-31
  'claude lemieux', 'claude giroux', 'ferrari', 'formula one', 'formula 1',
  // 2026-08-31 吸收自 yidian.ai 的题材硬边界:消费电子测评 + 军事。
  // (「arms race」是 AI 报道常用比喻,yidian 注释里明确说了别收 —— 从其教训。)
  'xbox', 'playstation', 'nintendo', 'chromebook', 'smartwatch', 'earbuds',
  'air fryer', '游戏本', '掌机', '扫地机器人', '开箱测评',
  'pentagon', 'darpa', 'missile', '解放军', '五角大楼', '军演', '导弹',
];

// Not a news story at all — a forum board, an event signup, a course ad. These
// carry real AI keywords, so the entity lists happily accept them; the genre is
// what disqualifies them. Penalised rather than banned, so that
// "OpenAI opens registration for DevDay" still clears the bar on its entities.
const GENRE_NOISE = [
  // forum / board / listing pages that are not articles
  '讨论区', '股吧', '交流社区', '贴吧', '论坛首页', 'discussion board', 'message board',
  '게시판', '커뮤니티 글', 'forum thread',
  // event & recruitment notices
  '참여자 모집', '수강생 모집', '신청 접수', '초청 강연', '설명회', '공모전', '채용 공고',
  '报名', '招募', '讲座通知', '培训班', '招聘', '公开课',
  '参加者募集', '受講者募集', 'セミナー開催',
  'call for papers', 'registration is open', 'sign up now', 'job posting',
  'now hiring', 'free webinar', 'enroll now', 'learning bundle', 'course bundle',
  'lifetime access', 'grab this deal', 'on sale for',
  // 2026-08-31: 荐股导购与获奖表彰 —— 词法上全是 AI,体裁上全是噪音。
  // 只收最机械的组合词,细分类交给 value 轴(src/lib/value.js)。
  'stocks to buy', 'etf to buy', 'no-brainer', 'should you buy', 'price target',
  'buy and hold', '买入并长期持有', '概念股', '龙头股',
  '斩获佳绩', '荣获', '揭牌仪式', '签约仪式', '수혜주', '테마주', '시상식',
];

/** Trap = the soft entity is present but so is a competing sense. */
const AMBIGUITY_TRAPS = /\b(horoscope|zodiac|astrology|obituary|funeral|memorial|nhl|hockey|stanley cup|touchdown|quarterback|monza|grand prix|formula 1|qualifying|antonelli|räikkönen|hasbro|feature film|movie)\b/i;

/**
 * "Claude Allen Edwards" — a short headline made only of capitalised words is
 * a person's name (obituaries, appointments), not an AI story. Requires no
 * keyword list, which is the point: name collisions are open-ended.
 */
function looksLikePersonName(title) {
  const words = title.trim().split(/\s+/);
  if (words.length < 2 || words.length > 4) return false;
  return words.every((w) => /^[A-Z][a-z'’.-]*$/.test(w));
}

// Bare "AI" as a standalone token — weak evidence on its own.
const BARE_AI = /(^|[^a-z0-9])ai([^a-z0-9]|$)/i;
const regexEscape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
// Standalone ASCII brand/abbreviation entities must be token matches. Plain
// includes('agi') made words such as "imaging" look like AGI news.
const hasEntity = (hay, word) => /^[a-z0-9]+$/i.test(word)
  ? new RegExp(`\\b${regexEscape(word)}\\b`, 'i').test(hay)
  : hay.includes(word);

/**
 * @returns {{score:number, relevant:boolean, hits:string[]}}
 */
export function scoreRelevance({ title = '', description = '', query = '' }) {
  const hay = `${title} ${description}`.toLowerCase().normalize('NFKC');
  const hits = [];
  let score = 0;

  let named = false;   // did any unambiguous AI term or entity match?
  for (const w of STRONG) if (hay.includes(w)) { score += 4; hits.push(w); named = true; }
  for (const w of ENTITIES) if (hasEntity(hay, w)) { score += 3; hits.push(w); named = true; }

  // Soft entities get full credit only if nothing in the headline pulls the
  // word towards its everyday meaning, and never on a bare person-name title.
  const trapped = AMBIGUITY_TRAPS.test(hay) || looksLikePersonName(title);
  for (const w of ENTITIES_SOFT) {
    if (!hay.includes(w)) continue;
    score += trapped ? 0 : 3;
    if (!trapped) named = true;
    hits.push(trapped ? '?' + w : w);
  }

  for (const w of CONTEXT) if (hay.includes(w)) { score += 1; }

  // A bare "AI" in an English headline is a real signal on its own — the
  // collisions it does have are handled by NEGATIVE, not by starving it.
  // Gate on "no named entity matched", NOT on score === 0: a context word
  // like "startup" adds 1, which would otherwise suppress this bonus and sink
  // headlines such as "SpaceX Fails to Acquire AI Startup Cognition AI Inc."
  if (!named && BARE_AI.test(hay)) { score += 3; hits.push('ai'); }

  // Single-token Latin traps need real boundaries: plain includes('aries')
  // also matched the tail of "summaries" and suppressed genuine AI stories.
  for (const w of NEGATIVE) if (hasEntity(hay, w)) { score -= 6; hits.push('!' + w); }
  for (const w of GENRE_NOISE) if (hay.includes(w)) { score -= 3; hits.push('~' + w); }

  // A CJK/other-script headline pulled by a CJK query is trusted a bit more:
  // the query terms themselves are unambiguous in those languages.
  if (/[一-鿿぀-ヿ가-힯]/.test(title) && /[一-鿿぀-ヿ가-힯]/.test(query)) {
    score += 1;
  }

  return { score, relevant: score >= ACCEPT, hits: [...new Set(hits)].slice(0, 8) };
}
