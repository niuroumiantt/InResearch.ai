// Keyword shards for Google News RSS.
//
// Design goals:
//  - 广: every angle of "AI" gets its own query group (models, chips, infra,
//    money, policy, safety, apps, research, people, incidents).
//  - 新: `hot` groups are polled every cycle; `warm`/`cold` round-robin so a
//    single cycle only ever fires a handful of requests (anti-throttling).
//  - 准: queries are written so the *query itself* already filters. Bare "AI"
//    is never used alone in English (it collides with names/abbreviations);
//    relevance.js is the second gate.

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** Locales we sweep. `ceid` drives Google News' edition. */
export const LOCALES = [
  { id: 'en-US', hl: 'en-US', gl: 'US', ceid: 'US:en', lang: 'en' },
  { id: 'zh-CN', hl: 'zh-CN', gl: 'CN', ceid: 'CN:zh-Hans', lang: 'zh' },
  { id: 'zh-TW', hl: 'zh-TW', gl: 'TW', ceid: 'TW:zh-Hant', lang: 'zh' },
  { id: 'ja-JP', hl: 'ja', gl: 'JP', ceid: 'JP:ja', lang: 'ja' },
  { id: 'ko-KR', hl: 'ko', gl: 'KR', ceid: 'KR:ko', lang: 'ko' },
  { id: 'en-GB', hl: 'en-GB', gl: 'GB', ceid: 'GB:en', lang: 'en' },
  { id: 'fr-FR', hl: 'fr', gl: 'FR', ceid: 'FR:fr', lang: 'fr' },
  { id: 'es-ES', hl: 'es', gl: 'ES', ceid: 'ES:es', lang: 'es' },
  { id: 'de-DE', hl: 'de', gl: 'DE', ceid: 'DE:de', lang: 'de' },
  { id: 'en-IN', hl: 'en-IN', gl: 'IN', ceid: 'IN:en', lang: 'en' },
];

// lane: how often the group is swept.
//   hot  -> every cycle          (breaking / highest signal)
//   warm -> round-robin, ~5 min
//   cold -> round-robin, ~30 min (long tail, regional, niche)
export const GROUPS = [
  // ---- 模型与发布 ----
  { id: 'models.frontier', angle: 'models', lane: 'hot', locales: ['en-US'],
    queries: ['OpenAI OR Anthropic OR "Google DeepMind" OR Gemini OR Claude OR GPT',
              '"frontier model" OR "model release" OR "state of the art" LLM',
              // 2026-08-31 全量对齐 news 词库:泛模型词与新品类
              '"reasoning model" OR "multimodal model" OR "foundation model" OR "Claude Code"'] },
  { id: 'models.open', angle: 'models', lane: 'warm', locales: ['en-US'],
    queries: ['Llama OR Mistral OR Qwen OR DeepSeek OR Kimi OR "open weights"',
              '"Hugging Face" OR "open source model" OR fine-tuning LLM',
              '"Meta AI" OR xAI OR Grok OR "Moonshot AI"'] },
  // 多语区模型面(news 词库的本地组,GN 各语区索引完全不同)
  { id: 'models.ja', angle: 'models', lane: 'cold', locales: ['ja-JP'],
    queries: ['生成AI OR 大規模言語モデル'] },
  { id: 'models.kr', angle: 'models', lane: 'cold', locales: ['ko-KR'],
    queries: ['생성형 AI OR 거대언어모델'] },
  { id: 'models.intl', angle: 'models', lane: 'cold', locales: ['fr-FR', 'es-ES'],
    queries: ['"IA générative" OR "modèle de langage"', '"IA generativa" OR "modelo de lenguaje"'] },
  { id: 'models.cn', angle: 'models', lane: 'hot', locales: ['zh-CN'],
    queries: ['大模型 OR 人工智能', '智能体 OR AI芯片 OR 通义 OR 豆包 OR 文心',
              // 2026-08-31 吸收自 yidian.ai + news 仓库:国产算力与模型厂,裸「人工智能」照不到。
              '华为昇腾 OR 寒武纪 OR 摩尔线程 OR 深度求索 OR 智谱 OR MiniMax OR 月之暗面'] },

  // ---- 芯片与硬件 ----
  { id: 'chips.ai', angle: 'chips', lane: 'hot', locales: ['en-US'],
    queries: ['Nvidia OR "AI chip" OR GPU datacenter', 'HBM OR TSMC OR "AI accelerator" OR TPU',
              // GPU 世代与 x86 阵营(全量对齐 news 词库)
              'Blackwell OR GB300 OR "Rubin GPU" OR "AMD Instinct" OR MI400 OR "Intel Gaudi"'] },
  { id: 'chips.cn', angle: 'chips', lane: 'warm', locales: ['zh-CN'],
    queries: ['AI芯片 OR 中芯国际 OR 流片 OR 良率 英伟达 OR 昇腾'] },
  { id: 'chips.jp', angle: 'chips', lane: 'cold', locales: ['ja-JP'],
    queries: ['半導体 AI OR エヌビディア OR 東京エレクトロン OR アドバンテスト'] },
  { id: 'chips.supply', angle: 'chips', lane: 'warm', locales: ['en-US', 'ko-KR', 'zh-TW'],
    queries: ['semiconductor "artificial intelligence" supply', 'SK하이닉스 OR 삼성전자 반도체 AI', '台積電 OR 半導體 AI',
              // 2026-08-31 吸收自 yidian.ai:存储与出口管制是芯片故事的另一半。
              '"SK hynix" OR Micron OR HBM "export controls" OR capacity OR yield'] },

  // ---- 硬件供应链纵深(2026-08-31 吸收自 niuroumiantt/news 的 292 查询词库:
  //      存储/设备/封装/云厂自研,是 AI 硬件成本与产能的先行指标,此前整体盲区) ----
  { id: 'chips.memory', angle: 'chips', lane: 'warm', locales: ['en-US'],
    queries: ['HBM4 OR HBM3E OR "Samsung HBM" OR "high bandwidth memory"',
              '"DRAM price" OR "NAND price" OR "memory shortage" OR "SSD price" OR Kioxia',
              'YMTC OR CXMT OR DDR5 OR "CXL memory" OR Solidigm OR "fab expansion"'] },
  { id: 'chips.memory.kr', angle: 'chips', lane: 'cold', locales: ['ko-KR'],
    queries: ['SK하이닉스 OR 삼성전자 HBM OR 증설 OR 양산'] },
  { id: 'chips.memory.cn', angle: 'chips', lane: 'cold', locales: ['zh-CN'],
    queries: ['长江存储 OR 长鑫存储 OR 存储芯片 扩产 OR 晶圆产能'] },
  { id: 'chips.memory.jp', angle: 'chips', lane: 'cold', locales: ['ja-JP'],
    queries: ['キオクシア OR 半導体 増産 OR 量産開始'] },
  { id: 'chips.memory.tw', angle: 'chips', lane: 'cold', locales: ['zh-TW'],
    queries: ['南亞科 OR 華邦電 OR 旺宏'] },
  { id: 'chips.equipment', angle: 'chips', lane: 'warm', locales: ['en-US'],
    queries: ['ASML OR "Applied Materials" OR "Lam Research" OR "Tokyo Electron" OR Advantest',
              'CoWoS OR "advanced packaging" OR "ABF substrate" OR "Samsung Foundry" OR SMIC OR "tape out"',
              // 封测与衬底(ASE/Amkor/Ibiden/欣兴):AI 芯片产能的最后一公里
              '"ASE Technology" OR Amkor OR Ibiden OR Unimicron'] },
  { id: 'chips.custom', angle: 'chips', lane: 'warm', locales: ['en-US'],
    queries: ['"AWS Trainium" OR "Microsoft Maia" OR "Huawei Ascend" OR Groq OR Cerebras'] },

  // ---- 基础设施 / 算力 / 能源 ----
  { id: 'infra.compute', angle: 'infra', lane: 'warm', locales: ['en-US'],
    queries: ['"data center" "artificial intelligence" gigawatt OR capex',
              '"AI infrastructure" OR "compute cluster" OR "AI supercomputer"',
              // 新云/托管运营商与数据中心选址阻力(吸收自 news 仓库)
              'CoreWeave OR Equinix OR "Digital Realty" OR Stargate OR hyperscale OR colocation'] },
  { id: 'infra.compute.cn', angle: 'infra', lane: 'cold', locales: ['zh-CN'],
    queries: ['智算中心 OR 东数西算 OR 算力枢纽 OR 数据中心 能评',
              '冷板式液冷 OR 浸没式液冷 OR 余热利用 OR 绿电 数据中心'] },
  // 数据中心的亚洲地域面与选址新闻(news 词库组4)
  { id: 'infra.dc.region', angle: 'infra', lane: 'cold', locales: ['en-US'],
    queries: ['"Johor data center" OR "Malaysia data center" OR "Singapore data center" OR "data center moratorium"'] },
  { id: 'infra.dc.asia', angle: 'infra', lane: 'cold', locales: ['ja-JP', 'ko-KR'],
    queries: ['データセンター AI 投資 OR 建設', '데이터센터 AI 투자 OR 건설'] },
  { id: 'infra.energy', angle: 'infra', lane: 'cold', locales: ['en-US'],
    queries: ['AI "power grid" OR "nuclear" datacenter energy',
              // 电力细分:SMR/PPA/变压器短缺/变电站/燃气轮机(吸收自 news 仓库)
              '"small modular reactor" OR "power purchase agreement" OR "transformer shortage" OR "data center substation" OR "gas turbine" datacenter',
              // 散热全链:液冷/CDU/背板换热/热回收/PUE
              '"liquid cooling" OR "immersion cooling" OR "cold plate" OR "coolant distribution unit" OR "heat reuse" OR PUE'] },
  { id: 'infra.network', angle: 'infra', lane: 'warm', locales: ['en-US'],
    queries: ['InfiniBand OR NVLink OR Broadcom OR Marvell OR "Arista Networks"',
              '"co-packaged optics" OR "silicon photonics" OR "800G optical" OR "Ultra Ethernet" OR DPU',
              'Coherent OR Lumentum OR "Credo Technology" optical OR transceiver'] },
  { id: 'infra.network.cn', angle: 'infra', lane: 'cold', locales: ['zh-CN'],
    queries: ['光模块 OR 中际旭创 OR 新易盛 OR 光迅科技'] },
  { id: 'infra.servers', angle: 'infra', lane: 'warm', locales: ['en-US'],
    queries: ['Supermicro OR "AI server" OR "rack-scale" OR "Foxconn AI" OR "Quanta Computer"',
              'Wiwynn OR Inspur OR Celestica OR "Hon Hai" OR "Dell AI server" OR "HPE server"'] },
  { id: 'infra.servers.cn', angle: 'infra', lane: 'cold', locales: ['zh-CN'],
    queries: ['AI服务器 OR 浪潮信息 OR 中科曙光 OR 工业富联'] },
  { id: 'infra.servers.tw', angle: 'infra', lane: 'cold', locales: ['zh-TW'],
    queries: ['廣達 OR 緯穎 OR 鴻海 OR 英業達 OR AI 伺服器'] },

  // ---- 资本 / 商业 ----
  { id: 'money.funding', angle: 'money', lane: 'hot', locales: ['en-US'],
    queries: ['"AI startup" funding OR raises OR valuation', '"artificial intelligence" acquisition OR IPO'] },
  { id: 'money.earnings', angle: 'money', lane: 'warm', locales: ['en-US'],
    queries: ['"artificial intelligence" earnings OR guidance OR revenue'] },
  // AI 单位经济学与债务融资(吸收自 news 仓库,2026 年市场最关注的风险线)
  { id: 'money.economics', angle: 'money', lane: 'cold', locales: ['en-US'],
    queries: ['"AI inference cost" OR "token pricing" OR "GPU rental" OR "AI unit economics"',
              '"data center financing" OR "AI debt" OR "AI bond" OR "GPU financing" OR "AI capex guidance"'] },
  { id: 'money.cn', angle: 'money', lane: 'cold', locales: ['zh-CN'],
    queries: ['AI融资 OR 大模型融资 OR AI并购 OR AI独角兽 OR AI裁员'] },

  // ---- 政策 / 监管 ----
  { id: 'policy.gov', angle: 'policy', lane: 'warm', locales: ['en-US', 'en-GB'],
    queries: ['"AI regulation" OR "EU AI Act" OR "AI executive order" OR "AI safety bill"',
              '"export controls" OR "chip ban" chips China AI'] },
  // 芯片产业政策工具与主权 AI 叙事(吸收自 news 仓库)
  { id: 'policy.industry', angle: 'policy', lane: 'cold', locales: ['en-US'],
    queries: ['"CHIPS Act" OR "entity list" OR "semiconductor tariff"',
              '"sovereign AI" OR "national AI strategy" OR "national AI fund" OR "public AI infrastructure"'] },
  { id: 'policy.cn', angle: 'policy', lane: 'cold', locales: ['zh-CN'],
    queries: ['芯片 出口管制 OR 半导体 补贴 OR 国产替代',
              '国家人工智能战略 OR 主权AI OR 自主算力'] },
  { id: 'policy.intl', angle: 'policy', lane: 'cold', locales: ['fr-FR', 'es-ES', 'de-DE', 'en-IN'],
    queries: ['"intelligence artificielle" régulation', '"inteligencia artificial" regulación',
              '"künstliche Intelligenz" Regulierung', '"artificial intelligence" India policy'] },

  // ---- 安全 / 风险 / 事故 ----
  { id: 'safety.risk', angle: 'safety', lane: 'warm', locales: ['en-US'],
    queries: ['"AI safety" OR "AI alignment" OR "AI interpretability" OR "AI evals" risk',
              'deepfake OR "AI generated" fraud OR misinformation'] },
  { id: 'safety.legal', angle: 'safety', lane: 'cold', locales: ['en-US'],
    queries: ['"artificial intelligence" lawsuit OR "copyright lawsuit" OR privacy'] },
  { id: 'safety.cn', angle: 'safety', lane: 'cold', locales: ['zh-CN'],
    queries: ['AI安全 OR 模型对齐 OR 大模型 评测'] },

  // ---- 应用 / 产品 ----
  { id: 'apps.product', angle: 'apps', lane: 'warm', locales: ['en-US'],
    queries: ['"AI agent" OR "agentic AI" OR "AI assistant" OR copilot launch',
              '"AI coding" OR "GitHub Copilot" OR "Cursor AI" OR "retrieval augmented generation"'] },
  { id: 'apps.cn', angle: 'apps', lane: 'cold', locales: ['zh-CN'],
    queries: ['AI应用 OR 智能体 OR AI编程 OR 具身智能'] },
  // 具身智能/人形机器人(吸收自 news 仓库,整个题材此前空白)
  { id: 'apps.embodied', angle: 'apps', lane: 'warm', locales: ['en-US'],
    queries: ['"humanoid robot" OR "embodied AI" OR "physical AI"'] },
  { id: 'apps.enterprise', angle: 'apps', lane: 'cold', locales: ['en-US'],
    queries: ['enterprise "generative AI" deployment OR rollout'] },

  // ---- 研究 ----
  { id: 'research.papers', angle: 'research', lane: 'cold', locales: ['en-US'],
    queries: ['"machine learning" research breakthrough OR benchmark',
              'reinforcement learning OR "reasoning model" paper'] },

  // ---- 人物 / 组织动向 ----
  { id: 'people.moves', angle: 'people', lane: 'cold', locales: ['en-US'],
    queries: ['"Sam Altman" OR "Dario Amodei" OR "Jensen Huang" OR "Demis Hassabis"',
              '"AI researcher" hires OR departs OR joins'] },

  // ---- 安全事件 / 评测(2026-08-31 吸收自 yidian.ai 的题材空洞) ----
  { id: 'safety.incident', angle: 'safety', lane: 'warm', locales: ['en-US'],
    queries: ['jailbreak OR "prompt injection" OR "red team" LLM OR chatbot'] },
  { id: 'research.bench', angle: 'research', lane: 'cold', locales: ['en-US'],
    queries: ['leaderboard OR benchmark "language model" OR LLM'] },

  // ---- 区域 ----
  // 2026-08-31 收紧:裸「人工知能/인공지능」捞回来的 35% 流量里几乎全是
  // 地方政务活动稿(300 条实测)。region 的本意是"该地区生态的实质信号",
  // 所以锚定到 政策/投资/芯片/头部公司,而不是"提到了 AI 的一切"。
  { id: 'region.jp', angle: 'region', lane: 'cold', locales: ['ja-JP'],
    queries: ['AI 規制 OR 投資 OR 買収 OR 資金調達',
              'AI半導体 OR データセンター OR ソフトバンク OR NTT'] },
  { id: 'region.kr', angle: 'region', lane: 'cold', locales: ['ko-KR'],
    queries: ['AI 규제 OR 투자 OR 인수',
              'AI 반도체 OR 데이터센터 OR 네이버 OR 카카오'] },
  // 德语区(吸收自 news 仓库):芯片建厂与本土模型厂只在德媒首发。
  { id: 'region.de', angle: 'region', lane: 'cold', locales: ['de-DE'],
    queries: ['"TSMC Dresden" OR ESMC OR Infineon OR "Aleph Alpha" OR "Black Forest Labs"',
              '"künstliche Intelligenz" Rechenzentrum OR Investition OR Chip'] },
];

/** Flatten GROUPS x locales x queries into individual pollable shards. */
export function buildShards() {
  const byLocale = new Map(LOCALES.map((l) => [l.id, l]));
  const shards = [];
  for (const g of GROUPS) {
    for (const locId of g.locales) {
      const loc = byLocale.get(locId);
      if (!loc) continue;
      for (const [i, q] of g.queries.entries()) {
        // A locale-specific query list shorter than the locale list is fine:
        // we pair by index when counts match, else broadcast every query.
        if (g.locales.length === g.queries.length && g.queries.length > 1) {
          if (i !== g.locales.indexOf(locId)) continue;
        }
        shards.push({
          id: `${g.id}#${locId}#${i}`,
          group: g.id,
          angle: g.angle,
          lane: g.lane,
          locale: loc,
          q,
        });
      }
    }
  }
  // 直连 feed(2026-08-31 从 niuroumiantt/news 吸收):官方博客/监管机构的
  // RSS/Atom,绕过 Google News 的收录延迟与盲区。每路 feed 就是一个 shard,
  // 完整复用车道轮询/304 缓存/退避/产出调档 —— 只是 URL 不再由查询词构造。
  // feedBoost:一手源的标题常不带 AI 词(「Introducing GPT-6」),来源本身
  // 就是实体,relevance 打分时补上这份先验。
  for (const f of FEEDS) {
    const loc = byLocale.get(f.locale || 'en-US') || LOCALES[0];
    shards.push({
      id: `feed:${f.id}`,
      group: `feed.${f.angle}`,
      angle: f.angle,
      lane: f.lane || 'warm',
      locale: loc,
      q: `feed:${f.domain}`,
      feedUrl: f.url,
      feedFormat: f.format || 'rss',
      sourceDomain: f.domain,
      // 每路 feed 自带先验强度:纯 AI 官方源 +3 直通;全公司/全机构宽口源
      // +1~2,得再命中一点词法信号才过线 —— 防「微软换 HR」蹭官方通道。
      feedBoost: f.boost ?? 3,
      editorialSource: f.editorialSource || '',
      editorialPolicy: f.editorialPolicy || '',
    });
  }
  // 通道③:页面监控(links 模式)。没有 RSS 的高价值源(工信部/NIST/欧盟
  // AI Office…),定期抓 HTML、取链接增量当新文章。全部冷车道。
  for (const w of WATCHES) {
    const loc = byLocale.get(w.locale || 'en-US') || LOCALES[0];
    shards.push({
      id: `watch:${w.id}`,
      group: `watch.${w.angle}`,
      angle: w.angle,
      lane: 'cold',
      locale: loc,
      q: `watch:${w.domain}`,
      watchUrl: w.url,
      sourceDomain: w.domain,
      feedBoost: w.boost ?? 2,
    });
  }
  return shards;
}

let FEEDS = [];
try {
  FEEDS = JSON.parse(
    readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'feeds.json'), 'utf8'));
} catch { /* feeds.json 缺失或损坏时按零路 feed 跑,不拦启动 */ }

let WATCHES = [];
try {
  WATCHES = JSON.parse(
    readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'watches.json'), 'utf8'));
} catch { /* 同上 */ }
