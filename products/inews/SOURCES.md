# 信息源清单 (SOURCES)

> 本文档由 `scripts/gen-sources.js` 从 `src/config/{keywords.js, feeds.json, watches.json}` 自动生成。
> 生成时 commit: `5eb4942` · 生成时间: 2026-09-03T16:45Z。
> **改配置后跑 `node scripts/gen-sources.js` 刷新本文档,不要手改。**

## 一、系统一页图:三通道采集

```
 ①关键词查询(Google News)   ②直连/编辑源(RSS/HTML)  ③页面监控(links)
     97 个查询 shard             66 路                   8 页
        └───────────────┬──────────────┴───────────────┬───────┘
                        ▼   统一车道轮询(热/温/冷,产出实测自动升降)
                  相关性闸门(词表打分 ≥3 上时间线;②③带来源先验 boost)
                        ▼
                  标题聚类去重(36h 同题归并,最早者记「首发」)
                        ▼
                  价值轴 0-3 分(规则粗判+LLM 精化;时间线默认只显示 ≥2)
                        ▼
                  LLM 翻译(保留品牌/人名) → 时间线
```

三通道各管一件事:**①管广度** —— GN 索引的全部媒体,查询词决定照到哪里;
**②管一手与编辑认证** —— 官方博客/监管机构/顶级专栏绕过 GN 延迟，Techmeme
River/RSS 则保留其编辑选题事实，但原文发布者仍是下游域名;
**③管死角** —— 没有 RSS 的源(工信部/NIST/欧盟 AI Office),抓页面取链接增量当新文章。

## 二、调度与预算

| 参数 | 值 | 说明 |
|---|---|---|
| shard 总数 | 171 | ①97 + ②66 + ③8,同一套轮询 |
| 车道分布 | 热 11 / 温 58 / 冷 102 | 初始车道只是猜测,产出实测自动升降(policy.js) |
| 节奏 | 一轮 60s:热全发+温10+冷5 ≈ 26 请求/分 | 令牌桶硬上限 36/分;被限流自动减半再爬升 |
| 轮转周期 | 热每轮 · 温约 6 分一圈 · 冷约 21 分一圈 | ETag/304 条件请求;失败单 shard 指数退避 |
| 时间语义 | GN 查询带 `when:1h`;feed 只收近 14 天;Techmeme 记其入选时间;监控页记首见时刻 | 36h 是聚类归并窗,另一个概念 |

**入库闸门**(所有通道同一条流水线):相关性词表(relevance.js:强词+4/实体+3/
上下文+1/黑名单−6,≥3 上时间线) → 聚类去重 → 价值轴 0-3(value.js 规则 +
classify.js LLM 精化,默认展示 ≥2) → LLM 翻译。通道②③每路带来源先验(boost):
纯 AI 官方源 +3 直通;全公司/全机构宽口源 +0~2,必须再命中词法信号才过线 ——
防「微软换 HR」蹭官方通道。Techmeme 不靠 boost 放行，而走单独的严格 AI 合同：
只收核心模型、实质事件和 AI 基建/供应链，硬拒证券行情、消费硬件、个人社交与口水。

## 三、语区(Google News)

| id | hl | gl | ceid | lang |
|---|---|---|---|---|
| en-US | en-US | US | US:en | en |
| zh-CN | zh-CN | CN | CN:zh-Hans | zh |
| zh-TW | zh-TW | TW | TW:zh-Hant | zh |
| ja-JP | ja | JP | JP:ja | ja |
| ko-KR | ko | KR | KR:ko | ko |
| en-GB | en-GB | GB | GB:en | en |
| fr-FR | fr | FR | FR:fr | fr |
| es-ES | es | ES | ES:es | es |
| de-DE | de | DE | DE:de | de |
| en-IN | en-IN | IN | IN:en | en |

## 四、通道①:关键词查询(按角度)

通用查询在所属语区各查一次;本地组只在对应语区查。初始车道是猜测,实测产出会调。

### 大模型 (`models`)

| 组 | 初始车道 | 语区 | 查询 |
|---|---|---|---|
| `models.frontier` | hot | en-US | `OpenAI OR Anthropic OR "Google DeepMind" OR Gemini OR Claude OR GPT` |
| `models.frontier` | hot | en-US | `"frontier model" OR "model release" OR "state of the art" LLM` |
| `models.frontier` | hot | en-US | `"reasoning model" OR "multimodal model" OR "foundation model" OR "Claude Code"` |
| `models.open` | warm | en-US | `Llama OR Mistral OR Qwen OR DeepSeek OR Kimi OR "open weights"` |
| `models.open` | warm | en-US | `"Hugging Face" OR "open source model" OR fine-tuning LLM` |
| `models.open` | warm | en-US | `"Meta AI" OR xAI OR Grok OR "Moonshot AI"` |
| `models.ja` | cold | ja-JP | `生成AI OR 大規模言語モデル` |
| `models.kr` | cold | ko-KR | `생성형 AI OR 거대언어모델` |
| `models.intl` | cold | fr-FR es-ES | `"IA générative" OR "modèle de langage"` |
| `models.intl` | cold | fr-FR es-ES | `"IA generativa" OR "modelo de lenguaje"` |
| `models.cn` | hot | zh-CN | `大模型 OR 人工智能` |
| `models.cn` | hot | zh-CN | `智能体 OR AI芯片 OR 通义 OR 豆包 OR 文心` |
| `models.cn` | hot | zh-CN | `华为昇腾 OR 寒武纪 OR 摩尔线程 OR 深度求索 OR 智谱 OR MiniMax OR 月之暗面` |

### 芯片与硬件 (`chips`)

| 组 | 初始车道 | 语区 | 查询 |
|---|---|---|---|
| `chips.ai` | hot | en-US | `Nvidia OR "AI chip" OR GPU datacenter` |
| `chips.ai` | hot | en-US | `HBM OR TSMC OR "AI accelerator" OR TPU` |
| `chips.ai` | hot | en-US | `Blackwell OR GB300 OR "Rubin GPU" OR "AMD Instinct" OR MI400 OR "Intel Gaudi"` |
| `chips.cn` | warm | zh-CN | `AI芯片 OR 中芯国际 OR 流片 OR 良率 英伟达 OR 昇腾` |
| `chips.jp` | cold | ja-JP | `半導体 AI OR エヌビディア OR 東京エレクトロン OR アドバンテスト` |
| `chips.supply` | warm | en-US ko-KR zh-TW | `semiconductor "artificial intelligence" supply` |
| `chips.supply` | warm | en-US ko-KR zh-TW | `SK하이닉스 OR 삼성전자 반도체 AI` |
| `chips.supply` | warm | en-US ko-KR zh-TW | `台積電 OR 半導體 AI` |
| `chips.supply` | warm | en-US ko-KR zh-TW | `"SK hynix" OR Micron OR HBM "export controls" OR capacity OR yield` |
| `chips.memory` | warm | en-US | `HBM4 OR HBM3E OR "Samsung HBM" OR "high bandwidth memory"` |
| `chips.memory` | warm | en-US | `"DRAM price" OR "NAND price" OR "memory shortage" OR "SSD price" OR Kioxia` |
| `chips.memory` | warm | en-US | `YMTC OR CXMT OR DDR5 OR "CXL memory" OR Solidigm OR "fab expansion"` |
| `chips.memory.kr` | cold | ko-KR | `SK하이닉스 OR 삼성전자 HBM OR 증설 OR 양산` |
| `chips.memory.cn` | cold | zh-CN | `长江存储 OR 长鑫存储 OR 存储芯片 扩产 OR 晶圆产能` |
| `chips.memory.jp` | cold | ja-JP | `キオクシア OR 半導体 増産 OR 量産開始` |
| `chips.memory.tw` | cold | zh-TW | `南亞科 OR 華邦電 OR 旺宏` |
| `chips.equipment` | warm | en-US | `ASML OR "Applied Materials" OR "Lam Research" OR "Tokyo Electron" OR Advantest` |
| `chips.equipment` | warm | en-US | `CoWoS OR "advanced packaging" OR "ABF substrate" OR "Samsung Foundry" OR SMIC OR "tape out"` |
| `chips.equipment` | warm | en-US | `"ASE Technology" OR Amkor OR Ibiden OR Unimicron` |
| `chips.custom` | warm | en-US | `"AWS Trainium" OR "Microsoft Maia" OR "Huawei Ascend" OR Groq OR Cerebras` |

### 算力基建 (`infra`)

| 组 | 初始车道 | 语区 | 查询 |
|---|---|---|---|
| `infra.compute` | warm | en-US | `"data center" "artificial intelligence" gigawatt OR capex` |
| `infra.compute` | warm | en-US | `"AI infrastructure" OR "compute cluster" OR "AI supercomputer"` |
| `infra.compute` | warm | en-US | `CoreWeave OR Equinix OR "Digital Realty" OR Stargate OR hyperscale OR colocation` |
| `infra.compute.cn` | cold | zh-CN | `智算中心 OR 东数西算 OR 算力枢纽 OR 数据中心 能评` |
| `infra.compute.cn` | cold | zh-CN | `冷板式液冷 OR 浸没式液冷 OR 余热利用 OR 绿电 数据中心` |
| `infra.dc.region` | cold | en-US | `"Johor data center" OR "Malaysia data center" OR "Singapore data center" OR "data center moratorium"` |
| `infra.dc.asia` | cold | ja-JP ko-KR | `データセンター AI 投資 OR 建設` |
| `infra.dc.asia` | cold | ja-JP ko-KR | `데이터센터 AI 투자 OR 건설` |
| `infra.energy` | cold | en-US | `AI "power grid" OR "nuclear" datacenter energy` |
| `infra.energy` | cold | en-US | `"small modular reactor" OR "power purchase agreement" OR "transformer shortage" OR "data center substation" OR "gas turbine" datacenter` |
| `infra.energy` | cold | en-US | `"liquid cooling" OR "immersion cooling" OR "cold plate" OR "coolant distribution unit" OR "heat reuse" OR PUE` |
| `infra.network` | warm | en-US | `InfiniBand OR NVLink OR Broadcom OR Marvell OR "Arista Networks"` |
| `infra.network` | warm | en-US | `"co-packaged optics" OR "silicon photonics" OR "800G optical" OR "Ultra Ethernet" OR DPU` |
| `infra.network` | warm | en-US | `Coherent OR Lumentum OR "Credo Technology" optical OR transceiver` |
| `infra.network.cn` | cold | zh-CN | `光模块 OR 中际旭创 OR 新易盛 OR 光迅科技` |
| `infra.servers` | warm | en-US | `Supermicro OR "AI server" OR "rack-scale" OR "Foxconn AI" OR "Quanta Computer"` |
| `infra.servers` | warm | en-US | `Wiwynn OR Inspur OR Celestica OR "Hon Hai" OR "Dell AI server" OR "HPE server"` |
| `infra.servers.cn` | cold | zh-CN | `AI服务器 OR 浪潮信息 OR 中科曙光 OR 工业富联` |
| `infra.servers.tw` | cold | zh-TW | `廣達 OR 緯穎 OR 鴻海 OR 英業達 OR AI 伺服器` |

### 资本 (`money`)

| 组 | 初始车道 | 语区 | 查询 |
|---|---|---|---|
| `money.funding` | hot | en-US | `"AI startup" funding OR raises OR valuation` |
| `money.funding` | hot | en-US | `"artificial intelligence" acquisition OR IPO` |
| `money.earnings` | warm | en-US | `"artificial intelligence" earnings OR guidance OR revenue` |
| `money.economics` | cold | en-US | `"AI inference cost" OR "token pricing" OR "GPU rental" OR "AI unit economics"` |
| `money.economics` | cold | en-US | `"data center financing" OR "AI debt" OR "AI bond" OR "GPU financing" OR "AI capex guidance"` |
| `money.cn` | cold | zh-CN | `AI融资 OR 大模型融资 OR AI并购 OR AI独角兽 OR AI裁员` |

### 政策监管 (`policy`)

| 组 | 初始车道 | 语区 | 查询 |
|---|---|---|---|
| `policy.gov` | warm | en-US en-GB | `"AI regulation" OR "EU AI Act" OR "AI executive order" OR "AI safety bill"` |
| `policy.gov` | warm | en-US en-GB | `"export controls" OR "chip ban" chips China AI` |
| `policy.industry` | cold | en-US | `"CHIPS Act" OR "entity list" OR "semiconductor tariff"` |
| `policy.industry` | cold | en-US | `"sovereign AI" OR "national AI strategy" OR "national AI fund" OR "public AI infrastructure"` |
| `policy.cn` | cold | zh-CN | `芯片 出口管制 OR 半导体 补贴 OR 国产替代` |
| `policy.cn` | cold | zh-CN | `国家人工智能战略 OR 主权AI OR 自主算力` |
| `policy.intl` | cold | fr-FR es-ES de-DE en-IN | `"intelligence artificielle" régulation` |
| `policy.intl` | cold | fr-FR es-ES de-DE en-IN | `"inteligencia artificial" regulación` |
| `policy.intl` | cold | fr-FR es-ES de-DE en-IN | `"künstliche Intelligenz" Regulierung` |
| `policy.intl` | cold | fr-FR es-ES de-DE en-IN | `"artificial intelligence" India policy` |

### 安全风险 (`safety`)

| 组 | 初始车道 | 语区 | 查询 |
|---|---|---|---|
| `safety.risk` | warm | en-US | `"AI safety" OR "AI alignment" OR "AI interpretability" OR "AI evals" risk` |
| `safety.risk` | warm | en-US | `deepfake OR "AI generated" fraud OR misinformation` |
| `safety.legal` | cold | en-US | `"artificial intelligence" lawsuit OR "copyright lawsuit" OR privacy` |
| `safety.cn` | cold | zh-CN | `AI安全 OR 模型对齐 OR 大模型 评测` |
| `safety.incident` | warm | en-US | `jailbreak OR "prompt injection" OR "red team" LLM OR chatbot` |

### 应用落地 (`apps`)

| 组 | 初始车道 | 语区 | 查询 |
|---|---|---|---|
| `apps.product` | warm | en-US | `"AI agent" OR "agentic AI" OR "AI assistant" OR copilot launch` |
| `apps.product` | warm | en-US | `"AI coding" OR "GitHub Copilot" OR "Cursor AI" OR "retrieval augmented generation"` |
| `apps.cn` | cold | zh-CN | `AI应用 OR 智能体 OR AI编程 OR 具身智能` |
| `apps.embodied` | warm | en-US | `"humanoid robot" OR "embodied AI" OR "physical AI"` |
| `apps.enterprise` | cold | en-US | `enterprise "generative AI" deployment OR rollout` |

### 研究评测 (`research`)

| 组 | 初始车道 | 语区 | 查询 |
|---|---|---|---|
| `research.papers` | cold | en-US | `"machine learning" research breakthrough OR benchmark` |
| `research.papers` | cold | en-US | `reinforcement learning OR "reasoning model" paper` |
| `research.bench` | cold | en-US | `leaderboard OR benchmark "language model" OR LLM` |

### 人物动向 (`people`)

| 组 | 初始车道 | 语区 | 查询 |
|---|---|---|---|
| `people.moves` | cold | en-US | `"Sam Altman" OR "Dario Amodei" OR "Jensen Huang" OR "Demis Hassabis"` |
| `people.moves` | cold | en-US | `"AI researcher" hires OR departs OR joins` |

### 区域 (`region`)

| 组 | 初始车道 | 语区 | 查询 |
|---|---|---|---|
| `region.jp` | cold | ja-JP | `AI 規制 OR 投資 OR 買収 OR 資金調達` |
| `region.jp` | cold | ja-JP | `AI半導体 OR データセンター OR ソフトバンク OR NTT` |
| `region.kr` | cold | ko-KR | `AI 규제 OR 투자 OR 인수` |
| `region.kr` | cold | ko-KR | `AI 반도체 OR 데이터센터 OR 네이버 OR 카카오` |
| `region.de` | cold | de-DE | `"TSMC Dresden" OR ESMC OR Infineon OR "Aleph Alpha" OR "Black Forest Labs"` |
| `region.de` | cold | de-DE | `"künstliche Intelligenz" Rechenzentrum OR Investition OR Chip` |

## 五、通道②:直连与编辑源(66 路)

每路源即一个 shard,复用车道轮询与产出调档。RSS/Atom 是常规格式；Techmeme
用 RSS 做最新增量、River HTML 做约五日回填，以同一个 pml 去重。通过严格 AI
门槛的标题、原文链接、域名和入选时间另存为编辑认证，不把 Techmeme 冒充发布者。

### 一手直通(boost 3) · 32 路

| id | 域名 | 格式 | 角度 | 车道 | 说明 |
|---|---|---|---|---|---|
| `openai-blog` | openai.com | rss | models | warm | OpenAI 官方新闻 |
| `deepmind-blog` | deepmind.google | rss | models | warm | Google DeepMind 官方博客 |
| `google-ai-blog` | blog.google | rss | models | warm | Google 官方 AI 频道 |
| `nvidia-blog` | nvidia.com | rss | chips | warm | NVIDIA 官方博客 |
| `aws-ml-blog` | amazon.com | rss | apps | cold | AWS 官方 ML 博客 |
| `hf-blog` | huggingface.co | rss | models | warm | Hugging Face 官方博客 |
| `skhynix-news` | skhynix.com | rss | chips | cold | SK 海力士官方 newsroom |
| `mlcommons` | mlcommons.org | rss | research | cold | MLPerf 基准官方 |
| `arcprize` | arcprize.org | rss | research | cold | ARC Prize 官方 |
| `uk-aisi` | gov.uk | rss | safety | cold | 英国 AI 安全研究所(Atom) |
| `cset-georgetown` | georgetown.edu | rss | policy | cold | 乔治城 CSET 智库 |
| `ai-incident-db` | incidentdatabase.ai | rss | safety | cold | AI 事故数据库官方 |
| `mit-tr-ai` | technologyreview.com | rss | research | warm | MIT 科技评论 AI 分版 |
| `ieee-spectrum-ai` | spectrum.ieee.org | rss | research | warm | IEEE Spectrum AI 分版 |
| `semianalysis` | semianalysis.com | rss | chips | warm | 顶级芯片/算力分析 |
| `qbitai` | qbitai.com | rss | models | warm | 量子位,中文 AI 垂直媒体 |
| `cxl-consortium` | computeexpresslink.org | rss | chips | cold | CXL 标准联盟官方 |
| `ualink-consortium` | ualinkconsortium.org | rss | infra | cold | UALink 互连标准联盟官方 |
| `ultraethernet` | ultraethernet.org | rss | infra | cold | Ultra Ethernet 联盟官方 |
| `simonwillison` | simonwillison.net | rss | models | warm | Simon Willison(Atom),LLM 工具一线 |
| `interconnects` | interconnects.ai | rss | models | cold | Nathan Lambert,RLHF/开源模型 |
| `importai` | importai.substack.com | rss | policy | cold | Jack Clark(Anthropic),政策+研究周报 |
| `chinai` | chinai.substack.com | rss | policy | cold | 中国 AI 政策翻译与分析 |
| `chinatalk` | chinatalk.media | rss | policy | cold | 中美科技政策深度 |
| `fabricatedknowledge` | fabricatedknowledge.com | rss | chips | cold | 半导体行业分析 |
| `morethanmoore` | morethanmoore.substack.com | rss | chips | cold | Ian Cutress,芯片深度 |
| `chipletter` | thechipletter.substack.com | rss | chips | cold | 芯片史与产业 |
| `latentspace` | latent.space | rss | apps | cold | AI 工程师社区播客/文章 |
| `aheadofai` | sebastianraschka.com | rss | research | cold | Sebastian Raschka,LLM 研究综述 |
| `thezvi` | thezvi.substack.com | rss | safety | cold | Zvi,AI 进展与安全周报 |
| `oneusefulthing` | oneusefulthing.org | rss | apps | cold | Ethan Mollick,AI 应用实践 |
| `dwarkesh` | dwarkesh.com | rss | people | cold | Dwarkesh 播客,实验室高管深访 |

### 宽口过滤(boost 1~2) · 19 路

| id | 域名 | 格式 | 角度 | 车道 | 说明 |
|---|---|---|---|---|---|
| `meta-newsroom` | meta.com | rss | models | warm | Meta 官方 newsroom(全公司宽口) |
| `microsoft-source` | microsoft.com | rss | apps | warm | 微软官方新闻(全公司宽口) |
| `google-cloud-blog` | withgoogle.com | rss | infra | cold | Google Cloud 官方博客(宽口) |
| `github-blog` | github.blog | rss | apps | cold | GitHub 官方博客(宽口) |
| `cloudflare-blog` | cloudflare.com | rss | infra | cold | Cloudflare 官方博客(宽口) |
| `databricks-blog` | databricks.com | rss | apps | cold | Databricks 官方博客 |
| `uk-gov-ai-news` | gov.uk | rss | policy | warm | 英国政府 AI 主题新闻(Atom) |
| `ftc-press` | ftc.gov | rss | policy | warm | FTC 官方新闻稿(宽口) |
| `ustr-press` | ustr.gov | rss | policy | cold | USTR 关税/出口管制(宽口) |
| `us-doe` | energy.gov | rss | infra | cold | 美国能源部(很宽口,只给+1) |
| `eia-today-in-energy` | eia.gov | rss | infra | cold | EIA 能源数据(很宽口,只给+1) |
| `uptime-journal` | uptimeinstitute.com | rss | infra | cold | Uptime Institute 数据中心机构 |
| `hpcwire` | hpcwire.com | rss | infra | warm | HPC/AI 算力垂直媒体 |
| `nextplatform` | nextplatform.com | rss | infra | warm | 数据中心体系结构深度 |
| `servethehome` | servethehome.com | rss | infra | cold | 服务器硬件评测 |
| `blocksandfiles` | blocksandfiles.com | rss | chips | cold | 存储行业垂直 |
| `theelec` | theelec.kr | rss | chips | warm | 韩国半导体一手媒体 |
| `eetimes-jp` | itmedia.co.jp | rss | chips | cold | 日本半导体媒体 |
| `stratechery` | stratechery.com | rss | money | cold | Ben Thompson,科技战略 |

### 大流量纯词法(boost 0) · 15 路

| id | 域名 | 格式 | 角度 | 车道 | 说明 |
|---|---|---|---|---|---|
| `tomshardware` | tomshardware.com | rss | chips | cold | 硬件大站(噪音多,纯词法过滤) |
| `wccftech` | wccftech.com | rss | chips | cold | 硬件爆料站(纯词法过滤) |
| `videocardz` | videocardz.com | rss | chips | cold | GPU 爆料(纯词法过滤) |
| `technews-tw` | technews.tw | rss | chips | cold | 台湾科技新报(纯词法过滤) |
| `techcrunch` | techcrunch.com | rss | money | cold | 创投大站(纯词法过滤) |
| `theverge` | theverge.com | rss | apps | cold | 消费科技大站(纯词法过滤) |
| `arstechnica` | arstechnica.com | rss | research | cold | 深度科技报道(纯词法过滤) |
| `venturebeat` | venturebeat.com | rss | apps | cold | 企业 AI 报道多(纯词法过滤) |
| `kr36` | 36kr.com | rss | money | cold | 36氪(纯词法过滤) |
| `ithome-cn` | ithome.com | rss | apps | cold | IT之家(纯词法过滤) |
| `techmeme-live` | techmeme.com | techmeme-rss | models | warm | Techmeme 编辑快讯增量：取原文链接，只收 AI 核心事件 |
| `techmeme-river` | techmeme.com | techmeme-river | models | cold | Techmeme River 五日回填与漏项修复：与 RSS 按 pml 去重 |
| `solidot` | solidot.org | rss | research | cold | 奇客(纯词法过滤) |
| `hn-frontpage` | ycombinator.com | rss | research | cold | Hacker News 首页(试点,纯词法过滤) |
| `r-localllama` | reddit.com | rss | models | cold | r/LocalLLaMA(Atom,试点) |

## 六、通道③:页面监控(links 模式,8 页)

没有 RSS 的源:定期抓页面 HTML,提取链接列表,**新出现的链接=新文章**
(标题取锚文本,发布时间记首见时刻)。首轮只建基线不入库;单轮新增超过 30 条
视为页面改版,只更新基线 —— 宁可漏过,不灌错。全部冷车道。

| id | 页面 | 角度 | boost | 说明 |
|---|---|---|---|---|
| `nist-ai` | www.nist.gov/artificial-intelligence | policy | 3 | NIST AI 标准与评测(无 RSS) |
| `cao-ai-jp` | www8.cao.go.jp/cstp/ai/index.html | policy | 3 | 日本内阁府 AI 战略(无 RSS) |
| `eu-ai-office` | digital-strategy.ec.europa.eu/en/policies/ai-off | policy | 3 | 欧盟 AI Office(无 RSS) |
| `miit-policy` | www.miit.gov.cn/zwgk/index.html | policy | 0 | 工信部政务公开(全行业,纯词法筛 AI/算力) |
| `msit-kr` | www.msit.go.kr/eng/bbs/list.do?sCode=eng&mId=4&m | policy | 1 | 韩国科技信通部英文新闻稿(无 RSS) |
| `epoch-ai` | epoch.ai/blog | research | 3 | Epoch AI,算力趋势研究(无 RSS) |
| `stability-news` | stability.ai/news | models | 3 | Stability AI 新闻页(无 RSS) |
| `cognition-blog` | cognition.ai/blog | apps | 3 | Cognition(Devin)博客(无 RSS) |

## 七、已知盲区与后备

- **Anthropic 无公开 RSS**(官网不提供)—— 靠 GN 关键词/转载覆盖;news 仓库
  的原方案是自建 RSSHub 桥抓 X@AnthropicAI,服务器装 RSSHub 后可加回
- **X/推特与微信公众号**(16 路)需要自建 RSSHub 实例(127.0.0.1),暂不可导
- **SEC EDGAR**(13 路 8-K/6-K)要求自报式 User-Agent,待 fetch 层支持后导入
- **YouTube 频道**(5 路)与 arXiv API 信号形态不同,暂缓
- **Techmeme AI Topic Leaderboard** 的公开付费预览只有无链接占位文本，不能当
  真实域名/标题摄取；拿到官方购买的 HTML/PDF 后再接入。免费 OpenAI 样例只可作
  窄域来源发现，不能替代广义 AI 新闻流
- 域名先验库 326 条见 `src/config/sources.seed.json`(与 niuroumiantt/news 同源);
  静音黑名单见 `src/config/muted-domains.json`;域名审核在分析页②区一键处置
