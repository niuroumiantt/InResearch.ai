> HISTORICAL — 历史快照，不作为当前指令。现行入口为 framework/CURRENT.md。

# InResearch.ai —— 数据中心研究产品

本仓库只承载 **inresearch.ai** 一个产品，代码就在仓库根。inews.today 是另一个独立产品，
代码在它自己的仓库 [niuroumiantt/inews.today](https://github.com/niuroumiantt/inews.today)
（2026-09-05 用户决定：两个产品完全分开，各自仓库、各自发布，本库不留副本，
也不保留任何针对 inews 的接口代码——本库不知道 inews 存在）。

---

# Datacenter Hub — 全球数据中心研究数据枢纽

一个**可持续、可更新**的数据中心行业研究项目。报告只是输出载体之一；
真正的资产是三层：**数据积累（越久越值钱）+ 方法论体系（口径纪律）+ 多形态输出能力**。

实现使用 Python 标准库、JSON/SQLite 数据层、Markdown 方法论和网页视图。
生产环境以 infra 的环境事实表为准；原件与持续阅读在 Spark，研究网站在 inresearch.ai。

2026-09-06 已上线[五视角研究工作台](https://inresearch.ai/research.html)，两个 3D 已接入节点问题与证据。
Spark 常驻 reader 与五分钟候选同步已启动。版本、测试和真实资料边界见[实施记录](docs/reviews/2026-09-06/IMPLEMENTATION.md)。

## 核心思想

> **身份稳定，问题与证据持续更新，框架有版本地演进。**
> 2026-09-06 用户采用 [全行业研究架构 v2](docs/reviews/2026-09-06/RESEARCH_ARCHITECTURE_V2.md) 作为实施基准。
> 物理/空间、系统/接口、产业/交易、需求/负载、问题/证据共享知识底座；15 模块保留兼容导航与维护分工。

目标是能解释原理、比较方案、验证数据、诊断系统与交付判断的行业专家能力。200GW 和投资周期是专题。局部 MECE、稳定对象/版本/问题 ID、可追溯跨模块引用，以及数字与非数字证据共同支撑研究；原件和现行口径/C3 采用要求保持。

```
L4 监测层   index.html 仪表盘 + framework/indicators.json 阈值预警
L3 输出层   reports/ — 报告 = 从知识层按角度导出的产物（PDF / PPT / Word / 公众号）
L2 模块层   framework/modules/（定义：问什么）+ research/（知识层：答什么——项目主体）
L1 方法论层 framework/01_data_standards.md 口径规则 + 02_knowledge_format.md 知识格式
L0 数据层   data/ — 六张实体表（项目/公司/价格/政策/合同/来源），实体为主键
```

**知识层（`research/Mxx.md`）是项目的主体**：每模块一份活研究文档，由带状态和
触发器的 Finding（结论+论证+证据+口径提醒）组成；35 问报告是其初始内容来源，
信号管线驱动其持续修订，报告导出器从它按角度汇编产出物。

## 目录结构

| 路径 | 层 | 作用 |
|---|---|---|
| `framework/00_overview.md` | L1-L2 | 全行业五视角、局部 MECE 与 15 模块兼容映射 |
| `framework/research_graph.json` | 对象/关系 | 84 个对象、139 条有类型关系及中英文别名 |
| `framework/research_questions.json` | 问题 | 415 个稳定问题、对象绑定、验收和证据要求 |
| `data/research_knowledge.json` | 正式证据 | 文档、证据、陈述与采用回答；运行候选另存非 Git 快照 |
| `research.html` | 研究工作台 | 五视角分层目录；按节点查看产品与厂商、关系、问题、材料、证据与任务 |
| `framework/01_data_standards.md` | L1 | **口径与核验规则手册**（每条数据入库必须遵守） |
| `framework/modules.json` | L2 | 模块注册表（机器可读：依赖表、更新频率、Q 映射） |
| `framework/modules/M01–M15.md` | L2 | 各模块定义：核心问题、关键指标、数据依赖 |
| `framework/02_knowledge_format.md` | L1 | 知识层格式规范（Finding 结构、状态机、触发器） |
| `research/Mxx.md` | **L2 主体** | 模块研究文档：可独立更新的研究结论库 |
| `framework/indicators.json` | L4 | 监测指标注册表（指标、阈值、红黄绿、来源、频率） |
| `data/schema/*.schema.json` | L0 | 六张表的字段定义与约束 |
| `data/projects.json` 等 | L0 | 实体数据（含种子数据，`verified` 标注核验状态） |
| Spark `~/.local/share/inresearch.ai/` | 永久资料 | 接收、原件、来源版本、分块阅读、候选、台账与可回滚目录 |
| `pipeline/` | 采集与队列 | 零依赖脚本：抓取、校验、四个队列（核验/精读/工单/盲区）、事实层、投递机检 |
| `framework/modules.json` | L1 声明 | **模块是声明不是代码**：要回答什么问题、由哪些信源跑口供养、关键词 |
| `framework/metrics.json` | L1 声明 | 指标定义与**口径维度**——可比性判定的唯一依据 |
| `data/facts.json` | L0 事实层 | **core**：原子是「一个事实」= 指标 × 口径 × 时点 × 出处 |
| `reports/` | L3 | 输出模板与生成结果 |
| `docs/inbox/` | 协作兼容入口 | 人员提交与旧流程登记；持续模型阅读向 Spark 的 `raw-materials/` 投料 |
| `docs/source/` | 存档 | 本项目自产文档（Q&A 报告、台账等原件） |
| `docs/library/` | 存档 | 第三方研报库兼容入口（当前存量以实盘台账为准；原件不进 Git） |
| `index.html` | L4 | 单文件仪表盘：模块地图 + 项目库 + 监测指标 |

## 数据更新三档机制

| 档位 | 数据 | 方式 | 频率 |
|---|---|---|---|
| 自动 | SEC EDGAR、公司 IR、IEA/EIA/FERC、新闻源 | `pipeline/` 脚本 + news 项目信源管道 | 日/周 |
| 半自动 | JLL/C&W/机构报告、财报电话会 | 监控发布页 → AI 提取 → 人工确认入库 | 季度 |
| 手动核验 | 项目状态变更（通电/开工/取消）、产业渠道信息 | 人工录入（独家价值最高） | 事件驱动 |

## Spark 持续阅读与运行边界

当前规则见 [阅读标准 v3](framework/04_reading_scoring_standard.md)、[项目目标](docs/local_reader/PROJECT_BRIEF.md) 与 [执行协议](docs/local_reader/RUN_TO_COMPLETION.md)。用户已批准且已部署常驻模式；实际版本、健康与阅读数量以[实施记录](docs/reviews/2026-09-06/IMPLEMENTATION.md)及台账为准。

`raw-materials → 原件/版本登记 → 27B 粗读 → 每篇深读 → 原文核验与候选 → C3 采用 → 节点/问题/Finding/交付`。

框架缺口也生成搜集、访谈、实测与复核任务。低分不淘汰，depth 不靠摘要猜；原理/规范/接口/失败案例与数字同样可进入证据链。阅读完成、整理、核验和采用分别计量，存在 sources 路径不代表已消化。

源码放 `~/code/inresearch.ai/`；Spark 原件、台账和成果放 `/home/spark/.local/share/inresearch.ai/`，日志与运行状态放 `/home/spark/.local/state/inresearch.ai/`。原件哈希与文档版本定身份，目录/分数/显示名可变，历史信息保留；资料和数据库不进 Git、不因去重或解压自动删除。

历史 macOS `docs/local_setup/` 为旧环境安装资料，不能据此认定 launchd 已在运行或直接重建自动推送；旧独立 reader `start.sh` 与启动提示词不适用新常驻流程。实际入口与命令以当前实现和部署记录为准。

## 本地运行

**四个队列脚本 = 四个「今天该干什么」的入口**，都是生成物，不手写：

```bash
python3 pipeline/verify.py          # 核验队列：哪些结论该复核了（按触发器）
python3 pipeline/reading_queue.py   # 阅读队列兼容入口；完成以执行/覆盖台账为准
python3 pipeline/workorder.py       # 工单队列：每个模块下一步该做什么（= 声明 − 现状）
python3 pipeline/blindspot.py       # 盲区体检：库里有、但分类器看不见的材料
```

数据与投递：

```bash
python3 pipeline/validate.py        # 校验所有数据文件（schema + 口径规则 + 保鲜度）
python3 pipeline/facts.py           # 事实层校验 + 可比性判定（口径不同的数拒绝并列）
python3 pipeline/facts.py --public  # 对外口径预览（实名照旧、金额转区间、标明数据年份）
python3 pipeline/intake.py          # 成员投递机检与三档分流
python3 pipeline/intake.py --accept # 把过检的 B/C 档写成批次 CSV 走既有合并流程
```

采集与站点：

```bash
python3 pipeline/fetch_sec.py       # 拉取跟踪公司的最新 SEC 文件列表（须本机跑，云端被屏蔽）
python3 pipeline/fetch_news_signals.py  # 从 news 项目匹配实体相关新闻线索
python3 pipeline/serve.py           # 站点 + 管理 API（含派工 /api/assign）；运行状态另查
```

页面：`index.html` 仪表盘 ｜ `team.html` 团队看板与派工 ｜ `bom3d.html` 爆炸图 ｜ `doc.html` 文档与打分表浏览

核验闭环：`verify.py 出队列 → 人工按链接核对 → 改数据/更新 verified_date → validate.py 把关 → commit 留痕`。
详见 [pipeline/README.md](pipeline/README.md)。

## 与其他项目的关系

- **news**：中英文新闻信源管道（关键词已覆盖数据中心/电力/散热/芯片），其抓取结果是本项目
  数据层的上游信号源；未来 `pipeline/` 可直接消费 news 的 `data/*.json` 做实体关联。
- **公众号内容**：每次数据更新和模块分析都是选题弹药，同一份数据资产服务决策、融资、内容三线。

## 当前实施与验收

架构依据、局部 MECE、节点契约和全量深读标准已采用；逐项实现稳定身份、非数字证据、问题任务、持久台账与常驻处理。先以有原文的一条贯通案例验证两向流程、覆盖、恢复与反证回流，再扩大到供配电、网络、存储、软件及历史原件。PDF 等交付放本机 artifacts，不提交二进制。

进度分别报告对象覆盖、原文证据、问题验证、阅读履约和应用/交付能力，按 scope_version 冻结分母；关键未知不得用文件量掩盖。实现、迁移和服务状态以最新验证记录为准。

## 历史路线图（2026-08 快照，不是当前完成状态）

历史“全库触达/通读完成”不等于按当前标准全部深读，也不能证明原件现存位置；以下数字保留历史语境，当前以盘点和阅读台账为准。

> ## 路线图（2026-08-15 对账刷新；总方向见 docs/DECISIONS.md）
>
> - [x] 第一阶段：立规矩——框架文档 + 口径手册 + 六表 schema + 种子数据 + 仪表盘骨架
> - [x] 第二阶段：数据层做实——项目库 120 条（台账迁入+全球补录）；CIK 真缺口清零；
>       news 信源桥接；EDGAR 采集脚本就绪（云端被屏蔽，须本机 launchd 跑）
> - [x] 第三阶段：五个新模块首版研究——M10-M15 全部有 Finding（全库 75 条），
>       薄弱模块（M10/M11/M13/M14）已各补量化专条
> - [x] 第三阶段半：知识运转机制——核验队列（verify.py）+ 精读队列（reading_queue.py）
>       双入口；9 分文献 8/8 消化；决策日志（docs/DECISIONS.md）防会话失忆
> - [x] 第三阶段末：**研报库全库通读完结**（2026-08-16）——28,759 份触达率 100%，
>       完结报告见 `docs/LIBRARY_REPORT.md`（含重构后的 orgchart、分类标准全文、
>       信源价值榜与各模块「接下来怎么用」）
> - [x] 第四阶段前置件（2026-08-17）：**声明式架构 + 事实层 + 团队化管线**
>       - 模块是声明，**工单 = 声明 − 现状**，由 `workorder.py` 生成，任何人不手写
>       - **事实层**（`metrics.json` + `facts.json` + `facts.py`）：原子从「一份文件」
>         变成「一个事实」；口径维度按指标声明，**口径不同的数拒绝并列**
>       - 阅读深度五档（精读/据实生成/半自动/目录级/成员精读）**永不混引**
>       - 投递契约 + 三档分流 + 派工看板（`team.html` + `/api/assign`）
>       - 盲区体检：找「库里有、但分类器看不见」的材料
> - [ ] 第四阶段：team work 化——按模块分工给不同负责人，PR 提交 → 用户 merge 进 core
>       （CODEOWNERS 已铺底，待人员到位与分支协作规范细化）
> - [ ] 第四阶段半：全库通读的三个尾巴——151 份图片型 PDF 走视觉读；
>       T2 层 AI与算力 3,858 份（最大未读块）；SemiAnalysis 剩余 163 份（单位价值最高）
> - [ ] 第五阶段：输出管线——PDF/PPT/Word 模板化生成（reports/templates 待做）；
>       季度更新节奏；仪表盘上线 VPS（wentian.ai）
> - [ ] 第六阶段：产品打磨——dashboard 美化整理；爆炸图交互升级
>       （漂亮的人机互动、快速进入待探索领域）
