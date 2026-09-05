// Techmeme is an editorial discovery source, not the publisher of the linked
// story.  Its RSS feed is the low-cost live edge (roughly the newest 15
// headlines); /river is the several-day repair window.  Both expose the same
// `pml` identifier, so one parser contract lets the two shards deduplicate.

import { decodeEntities, parseFeed } from './rss.js';
import { ACCEPT, scoreRelevance } from './relevance.js';
import { scoreValue } from './value.js';

const EASTERN = 'America/New_York';
export const TECHMEME_POLICY = 'techmeme-ai-v1';
const SOCIAL_HOSTS = new Set([
  'x.com', 'twitter.com', 'threads.com', 'threads.net', 'bsky.app',
  'techhub.social', 'mastodon.social',
]);

const COMPUTE = [
  'data center', 'data centers', 'datacenter', 'neocloud', 'gpu cloud', 'compute', 'gpu', 'hbm', 'dram', 'nand',
  'memory chip', 'semiconductor', 'foundry', 'fab', 'cowos', 'server', 'blackwell',
  'rubin', 'euv', 'wafer', 'lithography', 'advanced packaging', 'accelerator', 'mi500',
  'personal ai router', 'inference workload',
  'infiniband', 'nvlink', 'ethernet', 'optical', 'networking', 'storage',
  'liquid cooling', 'immersion cooling', 'power grid', 'nuclear', 'turbine',
  '数据中心', '算力', '芯片', '半导体', '内存', '存储', '服务器', '光模块', '液冷',
];
const POLICY = [
  'regulation', 'regulator', 'lawmakers', 'legislation', 'bill', 'executive order',
  'export control', 'antitrust', 'lawsuit', 'copyright', 'privacy', 'tariff',
  '监管', '立法', '法案', '出口管制', '反垄断', '诉讼', '版权', '隐私',
];
const SAFETY = [
  'ai safety', 'alignment', 'jailbreak', 'prompt injection', 'deepfake',
  'cybersecurity', 'security flaw', 'model risk', 'automated shutdown', 'outage', 'experiencing issues',
  '安全', '对齐', '越狱', '深伪', '故障',
];
const BUSINESS = [
  'raises', 'raised', 'funding', 'valuation', 'acquire', 'acquisition', 'merger',
  'ipo', 'revenue', 'earnings', 'layoff', 'investment', '融资', '估值', '收购',
  '并购', '上市', '营收', '财报', '裁员', '投资',
];
const RESEARCH = [
  'research', 'paper', 'benchmark', 'evaluation', 'study', '论文', '研究', '评测', '基准',
];

// Techmeme is a broad technology river.  These gates express the product's
// narrower editorial contract and intentionally do not relax global relevance.
const PRECISE_INFRA = /\b(?:data[ -]?cent(?:er|re)s?|datacent(?:er|re)s?|neoclouds?|gpu clouds?|ai factor(?:y|ies)|hbm(?:\d+(?:e)?)?|nvlink|infiniband|cowos)\b|数据中心|智算中心|算力集群|高带宽内存/i;
const COOLING_INFRA = /\b(?:liquid cooling|immersion cooling)\b|液冷|浸没式冷却/i;
const INFRA_COMPONENT = /\b(?:ai chips?|chips?|servers?|memory|dram|nand|storage|optical|interconnects?|networks?|networking|ethernet|switches?|power|cooling|gpus?|accelerators?|euv|wafers?|lithography|packaging|electrical transformers?|gas turbines?)\b|服务器|内存|存储|光模块|互连|网络|交换机|电力|散热|冷却|芯片|加速器|晶圆|光刻|封装|变压器|燃气轮机/i;
const INFRA_EVENT = /\b(?:capacity|mw|gw|gigawatts?|supply|shortages?|constraints?|backlog|orders?|contracts?|deals?|build(?:s|ing)?|construction|expand(?:s|ed|ing)?|production|produc(?:e|es|ed|ing)|ships?|shipped|shipping|shipments?|manufactur(?:e|es|ed|ing)|ramp(?:s|ed|ing)?|fab|foundry|capex|demand|outstripp(?:s|ed|ing))\b|产能|兆瓦|吉瓦|供应|短缺|瓶颈|积压|订单|合同|建设|扩建|投产|量产|出货|制造|代工|资本开支|需求/i;
const INFRA_ANCHOR = /\b(?:artificial intelligence|generative ai|ai(?:[- ](?:chips?|models?|clusters?|servers?|infrastructure))?|data[ -]?cent(?:er|re)s?|datacent(?:er|re)s?|gpu clouds?|blackwell|rubin|mi\d{3,4}[a-z]*|amd instinct|gaudi(?: \d+)?|tpu|cowos)\b|人工智能|生成式ai|数据中心|智算中心|英伟达|昇腾|寒武纪/i;
const COOLING_ANCHOR = /\b(?:artificial intelligence|generative ai|ai\b|data[ -]?cent(?:er|re)s?|datacent(?:er|re)s?|gpu clouds?|ai (?:clusters?|servers?|infrastructure|accelerators?)|blackwell|rubin)\b|人工智能|数据中心|智算中心|算力集群|AI服务器|英伟达Blackwell/i;
const HPE_SERVER_EVENT = /\b(?:hpe|hewlett packard enterprise)\b(?=.{0,320}\bservers?\b)(?=.{0,260}\b(?:supply|shortages?|constraints?|backlog|orders?|contracts?|deals?|demand)\b)/i;
const CORE_HARDWARE = /\b(?:blackwell|rubin|mi\d{3,4}[a-z]*|amd instinct|gaudi(?: \d+)?|google tpu|h\d{3}|b\d{3}|gb\d{3})\b|昇腾|寒武纪/i;
const TECHNICAL_MODEL_TOPIC = /\b(?:large language models?|llms?|foundation models?|frontier models?|reasoning models?|multimodal (?:world )?models?|world models?|vision models?|audio perception models?|speech recognition models?|model (?:training|inference|architecture|evaluation|benchmarking)|ai agents?|agentic ai|open weights?|token (?:costs?|pricing)|scaling laws?)\b|大语言模型|大模型|基础模型|推理模型|多模态模型|世界模型|模型训练|模型推理|模型架构|智能体|开放权重|开源模型/i;
const HARD_MATERIAL_EVENT = /\b(?:benchmark(?:s|ed|ing)?|evaluat(?:e|es|ed|ing|ion)|test(?:s|ed|ing)?|outage|experiencing issues|disruption|incident|hack(?:s|ed|ing)?|attack(?:s|ed|ing)?|rais(?:e[sd]?|ing)|funding|clos(?:e|es|ed|ing).{0,40}\bround|invest(?:s|ed|ing|ment)?|acquir(?:e|es|ed|ing)|acquisition|merger|ipo|valuation|revenue|sales|earnings|price cuts?|cut(?:s|ting)? (?:the )?(?:price|prices|costs?)|costs?.{0,60}\b(?:less|fall|falls|fell|fallen|decline[sd]?)|cheaper|reach(?:es|ed|ing)?.{0,50}\b(?:threshold|milestone)|deploy(?:s|ed|ing)?|train(?:s|ed|ing)?|shut(?:s|ting)? down|toppl(?:e|es|ed|ing)|adoption (?:rises?|rose|grew|jumps?|jumped|doubles?|doubled)|roadmap|details? (?:its|the|of)|reveal(?:s|ed|ing)?)\b|评测|测试|故障|中断|攻击|融资|投资|收购|并购|上市|估值|营收|销售额|降价|成本下降|部署|训练|路线图|披露/i;
const GENERIC_ACTION = /\b(?:launch(?:es|ed|ing)?|releas(?:e[sd]?|ing)|unveil(?:s|ed|ing)?|introduc(?:e|es|ed|ing)|roll(?:s|ed|ing)? out|rollouts?|announc(?:e|es|ed|ing)|open(?:s|ed|ing)?|sign(?:s|ed|ing)?|partner(?:s|ed|ing)?|team(?:s|ed|ing)? up|collaborat(?:e|es|ed|ing|ion)|ink(?:s|ed|ing)? (?:a |the )?deal)\b|发布|推出|签署|合作/i;
const EVENT_TARGET = /\b(?:artificial intelligence|generative ai|sovereign ai|personal ai router|ai inference(?: workloads?)?|ai (?:models?|agents?|chips?|systems?|platforms?|infrastructure)|large language models?|llms?|(?:foundation|frontier|reasoning|world|vision|audio perception|speech recognition) models?|multimodal (?:world )?models?|models? api|open weights?|chatgpt|gpt-\d+(?:\.\d+)?(?:-[a-z0-9]+)?|claude|gemini|grok|llama|qwen|deepseek|muse (?:spark|voice)|blackwell|rubin|mi\d{3,4}[a-z]*|amd instinct|gaudi(?: \d+)?|google tpu|data[ -]?cent(?:er|re)s?|neoclouds?|gpu clouds?|gpus?|accelerators?|hbm(?:\d+(?:e)?)?|chips?|servers?|optical (?:circuit )?switch(?:es)?|ethernet|nvlink|infiniband|cowos|safeguards?)\b|人工智能|大模型|智能体|开放权重|数据中心|算力|芯片|服务器|光模块|安全护栏/i;
const POLICY_TARGET = '(?:ai|artificial intelligence|models?|chatbots?|openai|anthropic|copyright|exports?)';
const POLICY_ACTION = '(?:approve[sd]?|endorse[sd]?|impose[sd]?|ban(?:s|ned|ning)?|bars?|barred|barring|prohibit(?:s|ed|ing)?|restrict(?:s|ed|ing)?|regulat(?:e|es|ed|ing|ion|ions|ory)|legislation|lawsuits?|su(?:e|es|ed|ing))';
const LEGAL_DECISION = '(?:rules?|ruled|ruling|orders?|ordered|blocks?|blocked|dismiss(?:es|ed|al)|reject(?:s|ed|ion)|allows?|allowed|upholds?|upheld|finds?|found|decides?|decided)';
const POLICY_EVENT = new RegExp(
  `\\b${POLICY_ACTION}\\b.{0,80}\\b${POLICY_TARGET}\\b`
  + `|\\b${POLICY_TARGET}\\b.{0,80}\\b${POLICY_ACTION}\\b`
  + `|\\b(?:files?|filed)\\b.{0,40}\\b(?:brief|complaint|appeal|lawsuit)\\b.{0,80}\\b(?:ai|openai|anthropic|models?|copyright)\\b`
  + `|\\b(?:court|judge)\\b.{0,35}\\b${LEGAL_DECISION}\\b.{0,80}\\b${POLICY_TARGET}\\b`
  + `|\\b${POLICY_TARGET}\\b.{0,80}\\b(?:court|judge)\\b.{0,35}\\b${LEGAL_DECISION}\\b`
  + '|法院裁决|提起诉讼|监管|立法|法案|禁令|禁止使用人工智能',
  'i',
);
const AI_GOVERNANCE_EVENT = /\b(?:endorse[sd]?|adopt(?:s|ed|ing)?|sign(?:s|ed|ing)? on to)\b(?=.{0,260}\b(?:principles?|framework|governance)\b)(?=.{0,340}\b(?:ai|artificial intelligence)\b)|\b(?:ai|artificial intelligence)\b.{0,260}\b(?:endorse[sd]?|adopt(?:s|ed|ing)?|sign(?:s|ed|ing)? on to)\b.{0,180}\b(?:principles?|framework|governance)\b/i;
const EU_PLATFORM_DESIGNATION = /\b(?:eu|european (?:union|commission))\b.{0,100}\bdesignat(?:e|es|ed|ing)\b.{0,100}\b(?:chatgpt|ai|artificial intelligence)\b.{0,140}\b(?:very large online search engine|vlose)\b/i;
const ANALYSIS_FORMAT = /^(?:(?:analysis|source):\s*)?(?:a look at|inside|how|why|explainer|analysis of|state of)\b|^(?:深度解析|深入分析|一文看懂)/i;
const SUPPLY_CHAIN_TOPIC = /\b(?:supply chains?|bottlenecks?|lead times?|yields?|chipmaking|semiconductor equipment|advanced packaging|euv|wafers?|lithography)\b|供应链|瓶颈|良率|半导体设备|先进封装|晶圆|光刻/i;
const AI_DEPLOYMENT_DEAL = /\b(?:ink(?:s|ed|ing)?|sign(?:s|ed|ing)?|announc(?:e|es|ed|ing))\b.{0,80}\bdeal\b.{0,180}\b(?:run|deploy|host|serve)(?:s|ed|ing)?\b.{0,50}\b(?:ai|artificial intelligence) models?\b/i;
const MODEL_TECHNICAL_FACT = /\b(?:astra model|openai'?s astra|models?)\b.{0,100}\buses?\b.{0,80}\brecurrent[ -]depth\b|\b(?:anthropic|claude|fable|mythos)\b.{0,220}\b(?:prices?|pricing)\b.{0,140}\b(?:tokens?|cache reads?)\b|\b(?:claude|fable|mythos)\b.{0,240}\b(?:watermarks?|watermarking|detection api)\b/i;
const CORE_COMPUTE_PROCUREMENT = /\b(?:openai|anthropic)\b.{0,80}\b(?:bought|buys?|rents?|leased?)\b.{0,80}\bmacs?\b.{0,80}\b(?:rl|reinforcement learning|training|ai (?:developers?|devs?))\b/i;
const AI_SAFETY_CAPABILITY = /\b(?:openai|anthropic)\b.{0,140}\bdevelop(?:s|ed|ing)\b.{0,100}\bautomated shutdown capabilities?\b.{0,100}\bai systems?\b/i;
const MODEL_RELEASE_COMMITMENT = /\bopenai\b.{0,60}\bplans? to publicly release\b.{0,60}\b(?:a version of )?astra\b/i;
const DATA_CENTER_POLICY_ANALYSIS = /\bgovernor\b(?=.{0,240}\bdata centers?\b)(?=.{0,280}\bguardrails?\b)(?=.{0,340}\bpennsylvania\b)/i;
const AI_PERFORMANCE_ANALYSIS = /^analysis:\s*(?=.{0,280}\b(?:chatbots?|ai summaries?|ai models?)\b)(?=.{0,340}\b(?:accuracy|performance|benchmarks?|most of the time|lower rate|higher rate)\b)/i;
const GADGET = /\b(?:smart ?glasses|smart rings?|smartphones?|iphones?|android phones?|handsets?|laptops?|gaming pcs?|gaming gpus?|graphics cards?|cameras?|doorbells?|toothbrush(?:es)?|vacuums?|headsets?|wearables?|earbuds?|appliances?|televisions?|smart tvs?|toys?|rtx ?\d{3,4}|geforce|dlss)\b|智能眼镜|智能戒指|手机|笔记本|游戏显卡|相机|摄像头|牙刷|吸尘器|头显|耳机|家电|电视|玩具/i;
const CHATTER = /\b(?:poll|q&a|interview|podcast|roundtable|personal essay|argues?|believes?|thinks?|predicts?|may presage|my take|why i think|discussion)\b|民调|问答|访谈|播客|个人观点|认为人工智能|预测人工智能/i;
const CELEBRITY = /\b(?:mrbeast|influencer|celebrity|kardashian|taylor swift)\b|网红|明星代言/i;
const TOOL_USE = /\b(?:using|uses?|powered by|with the help of|via)\s+(?:an?\s+)?(?:(?:generative|agentic)\s+)?(?:ai|chatgpt|claude|gemini|grok)(?:\s+(?:system|tool|model))?\b|\b(?:ai|model)[- ](?:powered|assisted|enabled)\b|\b(?:briefly |merely |only )?mentions? ai\b|利用人工智能|借助人工智能|顺带提及人工智能/i;
const INCIDENTAL_USE = /\b(?:discover(?:s|ed|ing)?|design(?:s|ed|ing)?|generat(?:e|es|ed|ing)|find(?:s|ing)?|found|creat(?:e|es|ed|ing))\b.{0,90}\bby\b.{0,40}\b(?:an? )?ai(?: system| tool| model)?\b|\b(?:spacecraft|satellite|trajectory|recipe|vacation|dinner|dating|pickup lines?|coupons?|hospital|irrigation)\b.{0,120}\bai(?: system| tool| model)?\b/i;
const LIFESTYLE_USE = /\b(?:people|users?|parents?|travelers?|tourists?|retailers?|dating apps?)\b.{0,70}\b(?:use|uses|using|with)\b.{0,30}\b(?:chatgpt|claude|gemini|grok|ai agents?|ai)\b|\b(?:emotional support|family schedules?|personal quer(?:y|ies)|choose dinner|plan vacations?|pickup lines?|generate coupons?)\b|调查显示|情感陪伴|家庭日程/i;
const CONSUMER_CONTEXT = /\b(?:android drop|galaxy phones?|sonos|speakers?|home audio|super bowl ads?|advertising campaigns?|marketing campaigns?|holiday campaigns?|sponsorships?|giveaways?|sweepstakes|fashion brands?|hasbro|feature films?|movies?)\b/i;
const OFF_SCOPE_EVENT = /\b(?:employee cafeteria|cafeteria|office lease|new offices?|corporate headquarters|headquarters|corporate backups?|holiday campaigns?|giveaways?|sweepstakes|fashion brands?|corporate logos?|rebrands?|telecom carriers?|vodafone)\b/i;
const VERTICAL_AI_USE = /\bai assistant for (?:farmers?|farming|agriculture)\b|\bai sales and marketing startup\b|\bai tools?\b.{0,70}\b(?:speed up|accelerat(?:e|es|ed|ing))\b.{0,30}\bclinical trials?\b/i;
const MODEL_CAMERA_CONTROL = /\b(?:world|multimodal|image|video|vision|perception) models?\b.{0,100}\bcamera(?:s| feeds?| (?:controls?|poses?|paths?|movement))\b|\bcamera(?:s| feeds?| (?:controls?|poses?|paths?|movement))\b.{0,100}\b(?:world|multimodal|image|video|vision|perception) models?\b/i;
const DEVICE_CORE_TARGET = '(?:ai chips?|hbm(?:\\d+(?:e)?)?|data[ -]?cent(?:er|re)s?|gpus? accelerators?)';
const DEVICE_SUPPLY_ACTION = '(?:production|manufacturing|mass production|capacity expansion|supply|shortages?|constraints?|backlog|orders?|ship(?:s|ped|ping|ments?)|manufactur(?:e|es|ed|ing))';
const DEVICE_CORE_INFRA_FACT = new RegExp(
  `\\b${DEVICE_CORE_TARGET}\\b.{0,100}\\b${DEVICE_SUPPLY_ACTION}\\b`
  + `|\\b${DEVICE_SUPPLY_ACTION}\\b.{0,100}\\b${DEVICE_CORE_TARGET}\\b`
  + `|\\b(?:expand(?:s|ed|ing)?|expansion)\\b.{0,50}\\b${DEVICE_CORE_TARGET}\\b.{0,30}\\bcapacity\\b`
  + `|\\b${DEVICE_CORE_TARGET}\\b.{0,30}\\bcapacity\\b.{0,50}\\b(?:expand(?:s|ed|ing)?|expansion)\\b`
  + '|AI芯片.{0,60}(?:产能|供应|短缺|瓶颈|积压|订单|出货|制造)'
  + '|(?:产能|供应|短缺|瓶颈|积压|订单|出货|制造).{0,60}AI芯片',
  'i',
);
const MARKET_VERB = '(?:up|down|ris(?:e|es|ing)|rose|fall(?:s|en|ing)?|fell|jump(?:s|ed|ing)?|pop(?:s|ped|ping)?|advanc(?:e|es|ed|ing)|spik(?:e|es|ed|ing)|surg(?:e|es|ed|ing)|soar(?:s|ed|ing)?|slid(?:e|es|ing)|slip(?:s|ped|ping)?|drop(?:s|ped|ping)?|plung(?:e|es|ed|ing)|tumbl(?:e|es|ed|ing)|rall(?:y|ies|ied|ying)|gain(?:s|ed|ing)?|climb(?:s|ed|ing)?|rebound(?:s|ed|ing)?)';
const MARKET_MOTION = new RegExp(`\\b(?:stocks?|market value|market cap)\\b.{0,20}\\b(?:is |are |was |were )?${MARKET_VERB}\\b|\\bshares?\\s+(?:is |are |was |were )?${MARKET_VERB}\\b|\\b${MARKET_VERB}\\b.{0,12}\\b(?:stocks?|shares?|market value|market cap)\\b`, 'i');
const COMPANY_MOTION = new RegExp(`\\b(?:Nvidia|Broadcom|AMD|Intel|Micron|HPE|TSMC|ASML|Supermicro)\\b\\s+(?:stock\\s+)?(?:is |are |was |were )?${MARKET_VERB}\\b`, 'i');
const TICKER_MOTION = new RegExp(`(?:\\$|\\b)(?:NVDA|AVGO|AMD|INTC|MU|HPE|TSM|ASML|SMCI|ARM|MRVL|ANET|VRT)\\b\\s+(?:stock\\s+)?(?:is |are |was |were )?${MARKET_VERB}\\b|(?:\\$|\\b)[A-Z]{2,5}\\b\\s+(?:stock\\s+)?(?:is |are |was |were )?${MARKET_VERB}\\b\\s+(?:by\\s+)?\\d+(?:\\.\\d+)?%`);
const CJK_MARKET_MOTION = /(?:股价|股票|市值).{0,24}(?:上涨|下跌|大涨|大跌|暴涨|暴跌|飙升|拉升|回落|跳涨|涨|跌)|(?:上涨|下跌|大涨|大跌|暴涨|暴跌|飙升|拉升|回落).{0,24}(?:股价|股票|市值)/i;
const CORE_BUSINESS_FACT = /\b(?:ai chips?|data[ -]?cent(?:er|re)s?|gpus?|hbm(?:\d+(?:e)?)?|models?|tokens?)\b.{0,80}\b(?:revenue|sales|orders?|shipments?|capacity|production|supply|backlog)\b|\b(?:revenue|sales|orders?|shipments?|capacity|production|supply|backlog)\b.{0,80}\b(?:ai chips?|data[ -]?cent(?:er|re)s?|gpus?|hbm(?:\d+(?:e)?)?|models?|tokens?)\b|(?:AI芯片|数据中心|算力|大模型).{0,60}(?:营收|销售额|订单|出货|产能|供应|积压)|(?:营收|销售额|订单|出货|产能|供应|积压).{0,60}(?:AI芯片|数据中心|算力|大模型)/i;
const MILITARY = /\b(?:pentagon|darpa|army|navy|air force|armed forces?|missile|weapons?|warfare|battlefield|drone strike|combat|warfighter|fbi|intelligence community|undercover sp(?:y|ies)|national defen[cs]e|defen[cs]e (?:department|contract(?:s|or)?|startup|tech(?:nology)?|systems?|drones?))\b|五角大楼|军方|国防|导弹|武器|战场|军事|作战|情报机构/i;
const ATTRIBUTED_TALK = /\b(?:says?|argues?|believes?|thinks?|predicts?|expects?|warns?)\b|表示|认为|预测|警告/i;
const FUTURE_FORECAST = /\b(?:sales|revenue|orders?|demand|market|spending|valuation)\b.{0,60}\b(?:will|would|could|may|expects? to|forecast(?:s|ed)? to|project(?:s|ed)? to)\b.{0,40}\b(?:reach|grow|double|triple|explode|surge|soar|fall|decline)|\b(?:will|would|could|may|expects? to|forecast(?:s|ed)? to|project(?:s|ed)? to)\b.{0,50}\b(?:sales|revenue|orders?|demand|market|spending|valuation)\b.{0,40}\b(?:reach|grow|double|triple|explode|surge|soar|fall|decline)/i;
const CORE_MODEL = /\b(?:large language models?|llms?|foundation models?|frontier models?|reasoning models?|multimodal (?:world )?models?|world models?|vision models?|audio perception models?|speech recognition models?|ai agents?|agentic ai|open weights?|openai|chatgpt|anthropic|claude|deepmind|gemini|deepseek|hugging ?face|mistral|llama|qwen|grok|xai|perplexity|moonshot(?: ai)?|cognition ai|muse (?:spark|voice))\b|大语言模型|大模型|基础模型|推理模型|多模态模型|世界模型|智能体|开放权重|开源模型|智谱|通义|豆包|文心|月之暗面|混元/i;

function cleanText(html = '') {
  return decodeEntities(String(html).replace(/<[^>]*>/g, ' '))
    .replace(/\s+/g, ' ').trim();
}

const regexEscape = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// ASCII entries in the angle dictionaries are tokens, not substrings.  In
// particular, "server" must not turn "serverless" into infrastructure and
// "fab" must not turn "fabulous" into a chip story.  CJK phrases do not have
// reliable word boundaries, so their deliberately specific strings remain
// substring matches.
function hasTerm(hay, term) {
  const needle = term.toLowerCase().normalize('NFKC');
  if (!/^[a-z0-9][a-z0-9 -]*$/i.test(needle)) return hay.includes(needle);
  const pattern = regexEscape(needle).replace(/\s+/g, '\\s+');
  return new RegExp(`(?:^|[^a-z0-9])${pattern}(?=$|[^a-z0-9])`, 'i').test(hay);
}

const hasTerms = (hay, terms) => terms.some((term) => hasTerm(hay, term));

function attr(html, name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = String(html).match(new RegExp(`\\b${escaped}\\s*=\\s*(?:"([^"]*)"|'([^']*)')`, 'i'));
  return decodeEntities(match?.[1] ?? match?.[2] ?? '');
}

function anchors(html = '') {
  const out = [];
  for (const match of String(html).matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)) {
    const href = attr(match[1], 'href');
    if (href) out.push({ href, text: cleanText(match[2]) });
  }
  return out;
}

/** Stable Techmeme key, e.g. 260903p26. */
export function techmemeKey(value = '') {
  const compact = String(value).match(/\b(\d{6}p\d+)\b/i);
  if (compact) return compact[1].toLowerCase();
  const permalink = String(value).match(/\/(\d{6})\/p(\d+)/i);
  return permalink ? `${permalink[1]}p${permalink[2]}`.toLowerCase() : '';
}

export function techmemeGuid(key) {
  const match = techmemeKey(key).match(/^(\d{6})p(\d+)$/);
  return match
    ? `https://www.techmeme.com/${match[1]}/p${match[2]}#a${match[1]}p${match[2]}`
    : '';
}

/** Content angle is stored per item; Techmeme itself is not a "models" topic. */
export function inferTechmemeAngle(title = '') {
  const hay = title.toLowerCase().normalize('NFKC');
  if (POLICY_EVENT.test(hay) || AI_GOVERNANCE_EVENT.test(hay)
      || EU_PLATFORM_DESIGNATION.test(hay) || hasTerms(hay, POLICY)) return 'policy';
  if (hasTerms(hay, SAFETY)) return 'safety';
  if (hasTerms(hay, BUSINESS)
      || /\b(?:invest(?:s|ed|ing)?|acquir(?:e|es|ed|ing)|rais(?:e[sd]?|ing))\b/i.test(hay)) {
    return 'money';
  }
  if (CORE_COMPUTE_PROCUREMENT.test(hay) || hasTerms(hay, COMPUTE)) return 'infra';
  if (hasTerms(hay, RESEARCH)) return 'research';
  return 'models';
}

/** Social posts are useful to Techmeme, but the product explicitly excludes chatter. */
export function isTechmemeSocial(url = '') {
  try {
    const host = new URL(url).hostname.toLowerCase().replace(/^www\./, '');
    return SOCIAL_HOSTS.has(host) || [...SOCIAL_HOSTS].some((x) => host.endsWith(`.${x}`));
  } catch {
    return false;
  }
}

export function isImplicitAiInfrastructure(title = '') {
  const text = title.normalize('NFKC');
  return PRECISE_INFRA.test(text)
    || (COOLING_INFRA.test(text) && COOLING_ANCHOR.test(text))
    || HPE_SERVER_EVENT.test(text)
    || (CORE_HARDWARE.test(text) && INFRA_EVENT.test(text))
    || (INFRA_COMPONENT.test(text) && INFRA_EVENT.test(text) && INFRA_ANCHOR.test(text));
}

function isCoreAnalysis(title) {
  if (DATA_CENTER_POLICY_ANALYSIS.test(title) || AI_PERFORMANCE_ANALYSIS.test(title)) return true;
  if (!ANALYSIS_FORMAT.test(title)) return false;
  return PRECISE_INFRA.test(title)
    || CORE_HARDWARE.test(title)
    || TECHNICAL_MODEL_TOPIC.test(title)
    || (COOLING_INFRA.test(title) && COOLING_ANCHOR.test(title))
    || (SUPPLY_CHAIN_TOPIC.test(title) && INFRA_ANCHOR.test(title));
}

const GENRE_FOR_ANGLE = {
  policy: 'policy', safety: 'safety', money: 'business', infra: 'compute',
  chips: 'compute', research: 'model', models: 'model', apps: 'apps',
};

/**
 * Narrow editorial admission for the broad Techmeme river.
 *
 * AI relevance, reading value, and "selected by Techmeme" stay independent:
 * this returns all three facts and never promotes a picked item to value=3.
 */
export function admitTechmemeItem(item) {
  const title = String(item?.title || '').trim();
  const link = String(item?.link || '');
  const reject = (reason, extra = {}) => ({ accepted: false, reason, ...extra });
  if (!title || !/^https?:\/\//i.test(link)) return reject('invalid');
  if (isTechmemeSocial(link)) return reject('social');

  const implicitInfra = isImplicitAiInfrastructure(title);
  const coreModel = CORE_MODEL.test(title);
  const coreHardware = CORE_HARDWARE.test(title);
  const coreAnalysis = isCoreAnalysis(title);
  const relevance = scoreRelevance({ title });
  if (!relevance.relevant && !implicitInfra && !coreModel && !coreHardware && !coreAnalysis) {
    return reject('not_ai', { relevance: relevance.score, hits: relevance.hits });
  }

  const angle = item.angle || inferTechmemeAngle(title);
  const effectiveScore = Math.max(
    relevance.score,
    implicitInfra || coreModel || coreHardware || coreAnalysis ? ACCEPT : 0,
  );
  const policyEvent = POLICY_EVENT.test(title) || AI_GOVERNANCE_EVENT.test(title)
    || EU_PLATFORM_DESIGNATION.test(title);
  const deviceCoreInfraFact = DEVICE_CORE_INFRA_FACT.test(title);
  const modelTechnicalFact = MODEL_TECHNICAL_FACT.test(title);
  const coreComputeProcurement = CORE_COMPUTE_PROCUREMENT.test(title);
  const safetyCapability = AI_SAFETY_CAPABILITY.test(title);
  const releaseCommitment = MODEL_RELEASE_COMMITMENT.test(title);
  const infrastructureEvent = implicitInfra && INFRA_EVENT.test(title);
  const genericMaterial = GENERIC_ACTION.test(title) && EVENT_TARGET.test(title);
  const material = HARD_MATERIAL_EVENT.test(title) || policyEvent || genericMaterial
    || infrastructureEvent || coreAnalysis || modelTechnicalFact || coreComputeProcurement
    || safetyCapability || releaseCommitment;

  if (MILITARY.test(title)) return reject('military', { angle, relevance: effectiveScore });
  const marketMotion = MARKET_MOTION.test(title) || COMPANY_MOTION.test(title)
    || TICKER_MOTION.test(title) || CJK_MARKET_MOTION.test(title);
  const retainedMarketFact = marketMotion
    && (CORE_BUSINESS_FACT.test(title) || HPE_SERVER_EVENT.test(title)
      || AI_DEPLOYMENT_DEAL.test(title));
  // A market move is not itself news.  Keep a compound headline only when it
  // also states a concrete AI-economy fact (AI-chip revenue, HBM supply, etc.).
  if (marketMotion && !retainedMarketFact) {
    return reject('market_noise', { angle, relevance: effectiveScore });
  }

  if ((GADGET.test(title) || CONSUMER_CONTEXT.test(title))
      && !MODEL_CAMERA_CONTROL.test(title) && !deviceCoreInfraFact && !policyEvent) {
    return reject('peripheral', { angle, relevance: effectiveScore });
  }
  if (OFF_SCOPE_EVENT.test(title)) return reject('peripheral', { angle, relevance: effectiveScore });
  if (CELEBRITY.test(title)) return reject('peripheral', { angle, relevance: effectiveScore });
  if (ATTRIBUTED_TALK.test(title) && FUTURE_FORECAST.test(title)) {
    return reject('chatter', { angle, relevance: effectiveScore });
  }
  if (CHATTER.test(title)) return reject('chatter', { angle, relevance: effectiveScore });
  if (LIFESTYLE_USE.test(title)) return reject('peripheral', { angle, relevance: effectiveScore });
  if ((TOOL_USE.test(title) || INCIDENTAL_USE.test(title) || VERTICAL_AI_USE.test(title))
      && !policyEvent && !deviceCoreInfraFact) {
    return reject('ai_is_only_a_tool', { angle, relevance: effectiveScore });
  }

  if (ATTRIBUTED_TALK.test(title) && !material) {
    return reject('chatter', { angle, relevance: effectiveScore });
  }
  if (!material) {
    return reject('no_core_event', { angle, relevance: effectiveScore });
  }

  const worth = scoreValue({ title, angle, relevance: effectiveScore, relevant: 1 });
  // Global consumer rules intentionally demote every iPhone mention. A strong
  // AI-infrastructure event may mention weak iPhone demand only as context;
  // the dedicated Techmeme contract has already removed the consumer story.
  if (worth.value === 0 && !(deviceCoreInfraFact && material) && !retainedMarketFact
      && !policyEvent && !coreComputeProcurement) {
    return reject('existing_noise', { angle, relevance: effectiveScore });
  }

  return {
    accepted: true,
    policy: TECHMEME_POLICY,
    reason: coreAnalysis ? 'core_analysis'
      : implicitInfra || coreHardware || coreComputeProcurement
        ? 'core_infrastructure' : 'material_ai_event',
    relevance: effectiveScore,
    relevant: 1,
    hits: [...new Set([
      ...relevance.hits,
      ...(implicitInfra || coreHardware || coreComputeProcurement
        ? ['techmeme:infrastructure'] : []),
      ...(coreAnalysis ? ['techmeme:analysis'] : []),
    ])],
    value: Math.max(2, worth.value),
    genre: GENRE_FOR_ANGLE[angle] || worth.genre,
    angle,
  };
}

function sourceFromHtml(html) {
  const candidates = anchors(html).filter((a) => a.text && !/techmeme\.com/i.test(a.href));
  return candidates.at(-1) || { href: '', text: '' };
}

function mainLinkAfterCite(html) {
  const end = html.search(/<\/cite\s*>/i);
  const candidates = anchors(end >= 0 ? html.slice(end) : html)
    .filter((a) => a.text && /^https?:\/\//i.test(a.href));
  return candidates[0] || null;
}

function easternMillis(dateText, timeText) {
  const date = String(dateText).match(/^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})$/);
  const time = String(timeText).match(/^(\d{1,2}):(\d{2})\s*([AP]M)$/i);
  if (!date || !time) return null;
  const month = new Date(`${date[1]} 1, 2000 UTC`).getUTCMonth();
  if (!Number.isFinite(month)) return null;
  let hour = Number(time[1]) % 12;
  if (time[3].toUpperCase() === 'PM') hour += 12;
  const target = Date.UTC(Number(date[3]), month, Number(date[2]), hour, Number(time[2]));

  // Convert a wall-clock time in America/New_York without pinning EDT/EST.
  // Two passes converge on the correct UTC instant on either side of DST.
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: EASTERN, hourCycle: 'h23', year: 'numeric', month: '2-digit',
    day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  let guess = target;
  for (let i = 0; i < 2; i++) {
    const parts = Object.fromEntries(fmt.formatToParts(new Date(guess))
      .filter((x) => x.type !== 'literal').map((x) => [x.type, Number(x.value)]));
    const represented = Date.UTC(parts.year, parts.month - 1, parts.day,
      parts.hour, parts.minute, parts.second);
    guess += target - represented;
  }
  return guess;
}

function riverItem(rowHtml, dateText) {
  const cells = [...rowHtml.matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/gi)].map((m) => m[1]);
  if (cells.length < 2) return null;
  const timeText = cleanText(cells[0]).replace(/\s*(?:[•·]|&bull;)\s*$/i, '').trim();
  const published = easternMillis(dateText, timeText);
  const key = techmemeKey(attr(rowHtml, 'pml'));
  const cite = cells[1].match(/<cite\b[^>]*>([\s\S]*?)<\/cite>/i)?.[1] || '';
  const source = sourceFromHtml(cite);
  const main = mainLinkAfterCite(cells[1]);
  if (!key || !published || !main?.href || !main.text) return null;
  return {
    title: main.text,
    link: main.href,
    guid: techmemeGuid(key),
    editorialKey: key,
    pubDate: new Date(published).toUTCString(),
    sourceName: source.text,
    sourceUrl: source.href,
    description: '',
    angle: inferTechmemeAngle(main.text),
  };
}

/** Parse all public story rows in /river; sponsor/podcast blocks are not tr.ritem. */
export function parseTechmemeRiver(html) {
  const items = [];
  const sections = [...String(html).matchAll(
    /<h2\b[^>]*>([\s\S]*?)<\/h2>([\s\S]*?)(?=<h2\b|$)/gi,
  )];
  for (const section of sections) {
    const dateText = cleanText(section[1]);
    if (!/^[A-Za-z]+\s+\d{1,2},\s*\d{4}$/.test(dateText)) continue;
    for (const row of section[2].matchAll(/<tr\b([^>]*)>([\s\S]*?)<\/tr>/gi)) {
      if (!/\britem\b/i.test(attr(row[1], 'class'))) continue;
      const item = riverItem(row[0], dateText);
      if (item) items.push(item);
    }
  }
  return { items };
}

/** Turn Techmeme's RSS wrapper into the same original-publisher item shape. */
export function parseTechmemeFeed(xml) {
  const out = [];
  for (const item of parseFeed(xml).items) {
    const key = techmemeKey(item.guid || item.link);
    const main = item.description.match(
      /<span\b[^>]*>\s*<b\b[^>]*>\s*<a\b([^>]*)>([\s\S]*?)<\/a>/i,
    );
    if (!key || !main) continue;
    const link = attr(main[1], 'href');
    const title = cleanText(main[2]);
    if (!link || !title) continue;
    const beforeMain = item.description.slice(0, item.description.indexOf(main[0]));
    const source = sourceFromHtml(beforeMain);
    out.push({
      title,
      link,
      guid: techmemeGuid(key),
      editorialKey: key,
      pubDate: item.pubDate,
      sourceName: source.text,
      sourceUrl: source.href,
      description: '',
      angle: inferTechmemeAngle(title),
    });
  }
  return { items: out };
}
