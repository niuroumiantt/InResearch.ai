# 提案：采集产品给 inresearch 供弹（阿里云重置后）

> 候选 · 2026-09-21 · **未采用**。不替代 [06 采集规范](../../../framework/06_acquisition.md)。本文件只回答：研究库要弹药、专用爬取仓库是否成立、没有阿里云磁盘时怎么跑。

本次 Cloud Agent 工作区只有 `inresearch.ai` 与 `fetchspec`。infra 仓库未检出且当前 GitHub 凭据不可读 `niuroumiantt/infra`。机器职责以下列 **inresearch 已引用的 infra 文档名** 为准：`docs/production-topology.md`、`docs/network-addressing.md`、`dgx-spark/BOUNDARIES.md`、`docs/infrastructure-review-2026-09-05.md`。

## 结论

**“inresearch 是研究底座，外面用独立采集产品往里送原件”这条逻辑是对的，而且已经在跑：新闻走 inews，不在 inresearch 里再写一套爬虫。**

**“再做 10–20 个 Git 仓库，每个细分行业一个爬虫”不可行，也不该这么拆。** 应按 **采集形态** 拆产品（规则、协议、限速身份、发布节奏），用 **规则文件** 覆盖厂商和产品线。目标是 **3–6 个采集产品**，不是 10–20 个仓库。

阿里云重置只丢掉那台盘上的抓取缓存。Git 里的代码和规则还在；Spark 上已入库的原件（若当时没 rsync 过去）也不会从阿里云复活。下一步是指定一台 **新的、会长期留盘的抓取机**，不要把 Cursor Agent、Lightsail 或网站服务器当资料盘。

## 现行分工（不要推翻）

```text
研究问题 / 对象目录
        │
        ▼
   有界采集请求                    用户投料
        │                              │
   ┌────┼────────────┐                 │
   ▼    ▼            ▼                 ▼
 inews  SEC/GPU    规格/标准/案例     incoming/
 新闻   （现已在     （06 的 T 口，    分拣后再提升
 产品    inresearch  目前几乎空）      raw-materials
        适配器内）
        │
        ▼
 Spark  采集台账 + blobs     ≠   reader catalog + originals
        │
        ▼
 提取 / 深读 / 候选关联 / C3 采用
```

| 层 | 管什么 | 不管什么 |
|---|---|---|
| **inresearch.ai** | 对象、问题、口径、原件身份、深读、C3、网站派生 | 每种源站的爬虫实现 |
| **inews.today** | 产业新闻发现与投影 | 产品规格 PDF、研究采用 |
| **fetchspec** | 厂商官网、声明式 host+path、公开 PDF/HTML 快照 | 新闻聚类、登录墙、C3 |
| **infra** | 机器、域名、compose、密钥骨架、地址、发布 | 研究原件档案（临时队列默认约 14 天，不能当永久库） |
| **Spark** (`spark@100.100.1.2`) | 永久原件、采集台账、reader | 网站运行根、Git 源码即档案 |
| **网站 AWS** | 只读研究镜像 + 运行状态 | 原件、catalog |
| **macmini** | 必须带登录态的采集 | 把 Cookie 拷到爬虫机 |
| **m4 / 人** | 上传、分拣、校验、拍板 | 无人值守全站爬取 |
| **Cursor Agent** | 改代码、试跑小样本 | 资料盘 |

06 已经写明：请求 ID 与文档 ID 分开；一份材料多挂问题；**归档一次、关系多挂**。采集产品只负责把合法原件和清单送到 Spark，不在每个爬虫里复制 reader / 事实库 / 网站。

## 阿里云没了，资料放哪

此前把阿里云当作 fetchspec 的 `data_root`，是 **便宜的抓取盘**，不是研究权威库。重置之后：

1. **GitHub**：规则和代码仍在（`rules/*.json`、爬虫）。没有 PDF。
2. **阿里云磁盘**：抓过的 blob / library 视为已丢，需要在新盘上重抓。
3. **Spark**：只有当时已经 `incoming` → 分拣 → `raw-materials` → `originals` 的文件还在。fetchspec demo 若从未 rsync，Spark 上没有这批 PDF。
4. **本 Cloud Agent**：临时机，默认目录 `~/.local/share/fetchspec` 会随机器消失。

新的抓取盘选一个即可，条件是：Linux、出站访问厂商官网、磁盘够放 PDF、能 SSH/`rsync` 到 Spark、**不**用 infra 的 14 天临时队列当档案。

| 候选 | 适用 |
|---|---|
| 新买一台长期 VPS（原阿里云角色） | 无人值守 crawl、限速、与 reader 隔离，**首选** |
| Spark 本机一个独立 `~/data/fetchspec` | 仅小规模 demo；与 reader / 模型任务争 CPU 和出口，不要把 166 家官网全堆在这里 |
| 家里 NAS / m4 外接盘 | 可以当第二副本，不适合 7×24 对公网爬 |
| 网站机 / Lightsail / Agent | 否 |

推荐数据面：

```text
[抓取机 data_root]
  blobs/<sha> + library/ 视图 + ledger/catalog.json
        │  rsync，不 --delete
        ▼
[Spark] incoming/YYYYMMDD-fetchspec/
        │  人分拣；PDF 且要对齐产品目录的才提升
        ▼
[Spark] raw-materials/ → originals/<sha>/ + catalog.sqlite
        │
        ▼
  acquisition/catalog.sqlite 记来源运行（source=fetchspec）
  product library 索引发 doc_id
```

**不要**把 feeder 的 `catalog.json` 整个覆盖 `data/product_library_index.json`。同 SHA 只存一份字节；`company_id + product_line` 来自 inresearch `data/products.json`，由规则引用，不在爬虫里另建一套公司表。

## 仓库怎么拆才对

### 正确：按采集形态拆产品

新开 Git 仓库，应同时满足：

1. 抓取协议或站点形态不同（声明式官网 PDF ≠ 新闻聚类 ≠ EDGAR API ≠ 带登录浏览器）。
2. 独立发布节奏和依赖（inresearch 核心是 Python 标准库；官网爬虫可以有自己的规则 schema）。
3. 独立的 User-Agent / robots / 限速身份。
4. 失败和重试与研究采用无关，不该堵住 inresearch CI。

**不够**单独开仓库的：再增加一家厂商、一条产品线、一张供应链表。那是 `rules/厂商.json` 和 `products.json` 的一行。

因此：**弹药来源可以有 10–20 个目标领域，Git 仓库不应有 10–20 个。** 领域覆盖用规则和目录，不用仓库数。

已有和合理的采集产品：

| 产品 | 形态 | 仓库 | 状态 |
|---|---|---|---|
| 新闻 | 发现、聚类、标题/正文投影 | `inews.today` | 已在 06 |
| SEC / GPU 报价 | 官方 API、有界样本 | **留在** inresearch `adapters.acquisition` | 已在 06；不必拆仓 |
| 厂商官网规格 | host+path 规则、公开 PDF | `fetchspec` | demo 四家：NVIDIA / Intel / SuperMicro / Vertiv |
| 标准与工程规范 | 标准组织站点、版本身份 | 以后需要再开，例如 fetchstd | 未做 |
| 必须登录 | 浏览器会话留在 macmini | 不是公网爬虫仓 | 06 已划界 |

同一形态的「冷却厂商 PDF」和「算力厂商 PDF」共用 fetchspec，只加规则。不要 `fetch-cooling`、`fetch-power` 各开一仓。

### 错误：把 inresearch 当成父仓，下面挂 10–20 个子仓

inresearch **消费契约**，不 Git-submodule 一堆爬虫。每个采集产品：

- 自己的 Git、自己的调度；
- 交付 **字节 + 清单**，不交付 Finding；
- 清单字段与 Spark 采集台账可对上（见下节）；
- 更新节奏独立：官网改版只改那条规则，不发 inresearch 研究版本。

fetchspec 仓库里目前还叠了一个 Vite OpenAPI 查看器（`src/App.tsx`）和 Python 爬虫（`src/fetchspec/`）。这是 **两个产品共用一个名字**。在加第二家采集仓之前，应把 OpenAPI 查看器迁走或降为无关示例，避免 `fetchspec` 在文档和 CI 里指代不清。

## 投递契约（所有 feeder 共用）

采集产品允许做的：

- 遵守 robots、延迟、页数/深度上限；不登录、不绕过付费墙。
- 以 SHA-256 存不可变 blob。
- 每份文件一条清单：`sha256`、`source_url`、`fetched_at`、`mime`、`bytes`、`company_id`、`product_line`、`library_path`、`rule_id`、`doc_type`（DS/PB/WEB…）、`robots_ok`。
- 把 PDF 等 reader 能吃的格式送到 Spark `incoming/`，由人提升。

采集产品禁止做的：

- 写入 `facts.json` / `research_knowledge.json` / 网站运行根。
- 直接丢进 `raw-materials/`（scan 会永久入账，06 / Spark 手册已禁止未筛语料这样做）。
- 用文件名冒充内容身份；用 HTML 快照冒充规格原件（WEB 可存，阅读门槛另算）。
- 把八个产品生态和九张供应链表合成一张爬取地图（身份键仍是 `company_id + product_line`，用 `bom_parts` 联结，不按生态蜘蛛爬全站）。

inresearch 侧下一阶段（仍属 06 阶段 2/4，实施前须正式替代 06 对应段落）：

- `adapters.acquisition` 增加 `source=fetchspec`（及以后的标准源），合并清单，不覆盖历史 observation。
- 完整性门槛：PDF 可读、哈希一致、规则声明的公司/产品线在现行 `products.json` 中存在。
- 通过后才 handoff 到 reader；采用仍走 C3。

## 和 06 阶段表的关系

| 06 阶段 | 与本提案 |
|---|---|
| 1 新闻/SEC/GPU 台账 | 已落地；本提案不回退 |
| 2 正文门槛与 reader handoff | fetchspec PDF 是最适合先做 handoff 的类型 |
| 3 定时与限速 | 调度在 **抓取机**，不在网站按钮 |
| 4 规格/标准/案例补齐 P/F/V/D/R | T 口的实现方式：少量 feeder + 许多规则，而不是许多仓库 |

## 建议的落地顺序（采用本提案之后）

1. 选定抓取盘（新 VPS 或 Spark 上隔离目录），写本机 `FETCHSPEC_DATA_ROOT`，不进 Git。
2. 在 fetchspec 只保留官网规格爬虫身份；OpenAPI 查看器另置。
3. 重跑 compute-first demo 四家，确认 ledger 与 `products.json` 键一致。
4. rsync 到 Spark `incoming/`，按 M4 分拣后提升 PDF。
5. 规则从 4 家扩到 `products.json` 计算板块，仍在同一仓库。
6. 仅当出现 **不同协议**（标准组织、登录态、招标 PDF 批量）时再开下一个 Git 仓库。
7. 采用后：修订 06「产品与机器边界」表，增加 fetchspec 行，并改 acquisition 的 `SOURCES`；本提案不能自行生效。
