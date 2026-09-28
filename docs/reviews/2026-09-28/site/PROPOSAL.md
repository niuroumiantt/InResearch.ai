# 目录与页面框架 v3 提案：一座数据中心的建、拆、运、账

2026-09-28｜状态：**提案，待用户决定**。前提：三个扫描（[对照清单](../alignment/AUDIT.md)）已确认旧逻辑是主干而非残留；用户已决定 Spark 与其他配合方听 inresearch.ai 指挥，先把核心项目搞清楚再定义别人怎么配合。本稿由四份独立方案（读者优先、骨架优先、四段优先、最小改动）经三方评审后合成，以得分最高的"骨架优先"为主干，嫁接其余三份的好想法，并按完整性批评的 49 条缺口逐条修过。外部材料只作对照，不作为现行指令。

## 0. 一页结论

这个项目交付一件东西：**一座 AI 数据中心，可以被追问到底。** 它是一棵树（数据中心 → 五个系统 → IT 四个子系统 → 系统内按能量流链路 → 61 个部件 + 软件 + 基型，园区之外并列六条站点权利），树上每个节点用五类变量（构成、运行、价格、时间、主体）描述、回答四问（它值多少、它由什么组成、它怎么影响账、数据从哪来缺什么），根节点顶部是三级账（成本、收入、回报），账由唯一的统一经济模型算出，数据经四段（采集 → 事实 → 规则 → 视图）流上来，采集由六队按目标表领任务。

用户要的"构建、爆炸、运营、财务"不是四个目录，是同一棵树的四种读法，每种读法有明确的数据基础，也有明确的缺口：

| 读法 | 它是树的什么 | 今天有什么 | 今天缺什么 |
|---|---|---|---|
| **建** · 它怎么建 | 时间列 + 主体列，从站点权利起，按建设阶段排 | 模型的 4 个建设输入（建设期、门槛等待、审批期、爬坡）、6 条交期序列 | 部件没有"建设阶段"属性；61 行时间类目标全是供货交期，没有工期、排队、调试；站点权利 12 行全缺 |
| **拆** · 它由什么组成 | 构成列 + 价格列，爆炸图是它的视觉形式 | 61 部件、链路、六权利、175 条产品线、NVIDIA 235 份规格（只在运行库） | 222 条部件行只有 2 条有数据；内存、存储、网络、控制四系统在运行、价格、时间三列全空 |
| **运** · 它怎么运转 | 运行列 + 账本里的运营支出 | 系统级 PUE/WUE 19 序列、利用率、负载、爬坡 | 目标表里没有任何部件级运行行（额定功率、效率曲线、MTBF），不是"待采集"，是"没有任务" |
| **账** · 它挣不挣钱 | 价格列 + 三级账，账本四个视图 | 83 个输入 54 个有来源，三个校准锚复现，四本账含 IRR/DSCR/杠杆 | 16 个作者假设、1 个无依据输入、三个地区各缺 6/8/16 项 |

所以今天网站能可信交付的是**园区级三级账与因子级价格现值**，不能可信交付的是**部件级的值多少与交期、站点权利的时间与价格、任何带证据链的陈述**。新框架不把这条线藏起来，而是把它画在每一格上：有值写"数值 + 时点 + 队 · 目标行"，无值写"缺 · 待某队 · 行 ID · 到期"，假设标"假设"，登记数标"登记数"，推算标"推算"。

目录从工作流角色（总览 / 研究 / 资料 / 任务 / 成果 / 管理）改为四问的全局视图：**数据中心 / 账本 / 爆炸图 / 采集 / 成果 / 管理（按角色）**。页面从 22 个收到 12 个有独立职责的；研究工作台退役，问题与证据并入节点页；研究图谱重做为 3.0，对象只有骨架节点与主体，Spark 与 M4 按我们发布的版本重同步。

## 1. 这个项目交付什么、给谁

**受众四种，代码里今天只有三种**（`src/inresearch/interfaces/auth.py`：admin / member / intern；非本机部署强制登录、无注册）：

| 受众 | 要拿到什么 | 今天拿到什么 |
|---|---|---|
| 内部研究者（member / admin） | 树的全部：节点页、账本、爆炸图、成果快照 | 节点页与账本已在新逻辑上；研究页、成果页、任务页各答各的 |
| 实习生（intern） | 自己名下的目标行：目标名、队、机制、到期；看不到账本数字 | 只能看 `team.html` 的 564 张模块工单，看不到 287 行目标表 |
| 六队（inews、fetchspec 已存在；fetchstat、fetchfilings、fetchreports、fetchquotes 待建） | 唯一任务书：目标表按队 × 五类变量 × 骨架位置 × 日历展开；交付后能在页面上看到自己的产出 | 目标表未接入供应中心（只接了 fetchspec 69 行）；四个队不存在却承担 168 行（58.5%）；交付了也不改变 status |
| 对外读者 | 建、拆、运、账四种读法 + 成果快照 | 没有角色；唯一对外交付是 `outputs/geluoke-research/` 的公众号长文 |

**交付物六件**，全部由同一组权威文件生成（`bom.json`、`site_rights.json`、`datacenter_model.json`、`tco_targets.json`、`dashboard.json`、`supply_contract.json`、图谱 3.0 与问题表）：

1. **节点页**：任一节点 × 五列 × 四问；根节点三级账（基准预设：成本 11.05、收入 22.91 $M/MW·年、回报 30.3%，角标 illustrative、16 个假设、1 个无依据、地区缺口）。
2. **账本**：83 个输入按五类分组、四个视图、三种问法、三个校准锚、四个地区；顶部一条可信边界（有来源 54 / 假设 16 / 给定 12 / 缺 1）；每个假设输入链到采集页的目标行。
3. **爆炸图**：五系统按链路的部件表与三维形式；部件档案只有一份实现；造型覆盖角标（今天 1/61 有 GLB）。
4. **采集任务书**：目标表 × 六队 × 骨架 × 日历；附"事实"与"规则"两个标签，让"这个数怎么算出来"可见。
5. **成果快照**：章节即四问，封面写可信边界，末章是专题文章与研究实体目录（`docs/research/<日期>/<主题>`、`outputs/geluoke-research`）。
6. **导出**：成果页四章的 HTML / Word / CSV（`manage.py export` 同源）；放弃 `reports/templates` 里未实现的投资人 PDF、路演 PPT、客户切片承诺。

## 2. 唯一逻辑如何变成目录

一句定义写进 05 规范：**目录是四问的全局视图，节点页是四问的局部视图。**

| 目录 | 落点 | 它是树的什么 | 交付什么 | 谁能看 |
|---|---|---|---|---|
| 数据中心 | `/` → `node.html` | 树本身 | 四问五列；根节点三级账；首屏四个读法入口：它怎么建 / 由什么组成 / 怎么运转 / 挣不挣钱 | 全部（含未来的 reader） |
| 账本 | `ledger.html` | 价格列的展开 + 三级账 | 四视图、三问法、可信边界、输入到目标行的回链 | member 以上；reader 只见基准预设 |
| 爆炸图 | `bom.html` | 构成列的视觉形式 | 五系统按链路、部件档案、3D 与芯片级镜头子导航、规格库入口 | 全部 |
| 采集 | `supply.html`（改写） | 第四问的全局视图 | 六队卡、五类变量 × 五系统热图、日历、目标行表（实习生 `?mine=1`）、事实、规则、收件箱 | member 以上；intern 只见自己的行 |
| 成果 | `report.html`（改写） | 树的可发布快照 | 四章即四问，可信边界，专题目录，三种导出 | 全部 |
| 管理 | `ops.html`（收缩） | 网站自身的运营 | 用户、管线、录价（按目标行 + 变量类）、生成物新鲜度、工具入口 | admin |

根节点首屏的四个读法入口用读者的话写，各自落到一列或一页：

- **它怎么建** → `node.html?col=4`，按建设阶段排（见 §3.1 新增的部件属性 `stage`），从站点权利起；同时链账本的建设输入。
- **它由什么组成** → `bom.html`（视觉）与 `node.html?col=1`（矩阵）。
- **它怎么运转** → `node.html?col=2` 与 `ledger.html#ledgers`（运营支出在四本账里，运行列不显示货币量，两处都要链）。
- **它挣不挣钱** → `ledger.html#ledgers`（四本账含 IRR、DSCR、杠杆现金回报，投资人要的在这里），可信边界单列融资假设的证据状态。

## 3. 骨架要补的三样东西（不补，"建"与"运"两种读法没有数据基础）

### 3.1 建设阶段是部件的第二个属性

能量流链路（chain）回答"由什么组成"，不回答"先建什么"：并网排队、变压器交期、土建、机电、IT 进场、调试是另一条顺序。给 `bom.json` 每个部件和每条站点权利加 `stage`（权利与审批 → 并网与外线 → 土建与壳 → 机电 → IT 进场 → 调试与上架），根节点"它怎么建"按 `stage` 排，采集页的默认排序也按它（这就是建设时间线）。因子树加一个时间因子 `time.build`（建设期、门槛等待、审批期、排队年限），目标表由它生成工期与排队行（今天时间类 61 行全是交期）。

### 3.2 部件级运行行

`part_fetch.json` 的数据类别今天是规格、价格、交期、新闻。加 `operation`（额定功率与功率份额、效率曲线或 PUE 贡献、寿命与 MTBF、上架与利用率），生成部件级运行行，四个 IT 子系统与控制的运行列才有任务可派。

### 3.3 登记表加两列：`node` 与 `variable_class`

价格库、事实库、产品库、公司库、指标表、知识库今天只带模块码 M01–M15，视图段靠因子树间接连上。每张登记表加 `node`（root / system:x / part:x / site:x / actor:x）与 `variable_class`，是"数据从哪来"能回答的前提，也是六队交付物能进 status 的前提。产品库由 `bom_parts` 派生 `system` 与 `chain`，内存单列（今天 DRAM/HBM 归在存储介质、RCD/CXL 归在算力芯片）。

## 4. 页面清单

| 页面 | 交付什么 | 读什么 | 组织轴 | 四问与五列怎么出现 | 由什么演化 |
|---|---|---|---|---|---|
| `node.html` 数据中心 | 唯一模板：root / system:x / part:x / site / site:x，`&col=1–5` | dashboard.json、tco_targets、bom、site_rights、prices、indicators、`/api/research`（按节点 ID 过滤）、`/api/news` | 骨架 × 五列 × 四问 | 四问即四个面板，五列即矩阵；根矩阵五系统 + IT 四子系统 + 站点权利（折叠 6 行、展开 10 行） | 本身。改四处：首屏四个读法入口与每列覆盖率；部件节点第一问新增"问题 / 候选证据 / 陈述 / 一跳关系"面板；第四问派工面板改读目标表；三级账角标 |
| `ledger.html` 账本 | 不改结构 | datacenter_model、prices | 五类变量 × 三级账 | 顶部可信边界；假设输入链目标行 | 本身 |
| `bom.html` 爆炸图 | 五系统按链路；尺度只是筛选 | bom、site_rights、companies、prices、indicators、products | 骨架 | 档案五栏即五列 | 本身 + 海报的打印样式；右栏改用 `part-dossier.js` |
| `bom3d.html` 3D | 三维形式，镜头沿链路；芯片级镜头承接机柜拆解 | 同上 + 模型资产 | 骨架 | 造型覆盖角标 | 本身 + `rack3d.html` 并入为 IT 计算链路的芯片级阶段 |
| `product-catalog.html` 规格库 | 部件 → 厂商 → 型号；覆盖角标"n 家厂商 / 175 条产品线" | `/api/product-catalog`、products、product_docs_plan | 部件 | 构成列的真实数据 | 本身 + `admin/product/index.html`（登记覆盖成为一个标签） |
| `company.html` 主体 | 一家公司供应哪些部件、持有哪条权利、项目与合同作附表 | companies、projects、contracts、brief | 主体（第 5 类） | 从 `node.html?col=5` 进入 | 本身；接收 ops 退役的项目、合同、简报三个数据集；去 KPI、地图、模块 |
| `supply.html` 采集 | 六队唯一任务书，标签按四段倒序：目标表 × 六队、目标行表、fetchspec 批次、收件箱、事实、规则 | tco_targets、supply_contract、dashboard、prices、indicators、`/api/supply`、`/api/targets?mine=1` | 六队 × 五类 × 骨架 × 日历 | 灰格即任务书；行 ID 与节点页双向链接 | 本身 + `materials.html` + `nvidia-pilot.html` + `team.html` |
| `report.html` 成果 | 树的可发布快照 | dashboard、datacenter_model、tco_targets、research_knowledge | 四问 | 四章即四问；封面可信边界；末章专题目录 | 本身；`delivery/report.py` 换源 |
| `ops.html` 管理 | 用户、管线、录价、生成物新鲜度、工具 | `/api/users`、`/api/status` | — | — | 本身收缩；退役项目漏斗、监测仪表盘、研究模块、项目库四块与重复的新闻时间线 |
| `doc.html` | 规范与记录阅读器，不入目录 | repository_manifest | 文件路径 | — | 本身；面包屑改"← 数据中心"，默认文档改 03 |
| `compare.html`、`bake.html` | 内部工具 | — | — | — | 从界面清单 static_pages 移到 excluded_pages，当本地工具（auth 没有"仅 admin 可 GET"的机制，撤路由等于不可访问） |
| `auth/` 四个片段 | 登录、改密、禁止、布局 | — | — | — | 保留；开设 reader 后禁止页文案改 |

## 5. 采集进度怎么出现在页面上

**一个真源，三个层级。** 真源只有 `tco_targets.json` 的 status 与 `supply_contract.json` 的队状态，经 `manage.py targets / dashboard` 生成。全局层在采集页第一屏（今天 sourced 36 / assumed 4 / needed 247）；节点层在每格的来源芯片；行级两页共用同一行 ID——点节点页任一灰格进采集页并按该节点、该列、该队预筛，点采集页一行回节点页停在该列。

**status 四态化，判定源必须在 Git 内。** `targets.py` 今天只认价格序列、有值指标与模型 evidence，所以 63 条规格行、44 条新闻行、6 条持有方行无论六队交付什么都永远 needed——fetchspec 已交付 235 份 NVIDIA 规格却在页面上没有任何变化。新增 `delivered`：规格行以产品资料库登记为准（`product_docs_plan.csv` 的 doc_id / source_url，或 `product_library_index.json` 入库），新闻行与持有方行只认带 `origin_pointer` 的事件卡快照（`site_rights.companies` 只标"登记数"），价格行以带 `target_id` 与 `variable_class` 的价格记录为准。只在运行库有的，页面标"运行库有 / Git 无"，不计 delivered。四个待建队名下 30 条 2026-09-27 人工定向抓取的 sourced 行改标 `local`（在 `part_fetch.json` / `tco_factors.json` 的来源登记里改，再重跑生成，不改生成物）。到期日历只对已接入的队显示，未建队的行显示"待建队"而不是每月滚动的红灯。

**格级诚实规则五条**写进 `dashboard_rules.json` 与 05：视图层不填估值；有值格"数值 + 时点 + 队 · 目标行 ID"；无值格"缺 · 待某队 · 行 ID · 到期日"；作者假设单独标"假设"；供应商数与产品线数只标"登记数"不算 sourced（修 `dashboard.py` 计数口径）；份额推算（造价份额 × 非 IT 造价）标明推算来源，不落在部件价格格里。

**模型缺口与部件缺口分开。** 前者（16 个假设、1 个无依据输入、地区缺口）在三级账旁与账本顶部；后者（222 部件行 220 needed、四系统三列全空、站点权利 12 行全缺）在矩阵与节点第四问。

**六队卡必显字段**：存在状态、承担行数、最近交付、下一到期。今天的真话是：fetchspec 接收端已实现待部署；inews 事件 feed 已消费但 50 行 0 sourced；四个队未建却承担 58.5%；181 行 30 天内到期无人承接。

## 6. 今天每个页面的处置表

| 页面 | 处置 | 理由 |
|---|---|---|
| `node.html`、`ledger.html`、`doc.html`、`bom3d.html`、`auth/*` | 保留 | 已在唯一逻辑上；只改文案、ID、链接与新增面板 |
| `bom.html` | 改写右栏 | 档案统一为 `part-dossier.js`；去"按尺度"模式；部件数读 bom.json；承接海报打印样式 |
| `rack3d.html` | 并入 `bom3d.html` | 机柜拆解是 IT 计算链路的芯片级阶段，不是一棵单独的尺度树 |
| `product-catalog.html` + `admin/product/index.html` | 合并改写 | 按部件 ID 参数化的规格库；登记覆盖是它的一个标签；搜索谓词抽成组件供单测 |
| `company.html` | 改写 | 主体列展开；接收项目、合同、简报 |
| `supply.html` + `materials.html` + `nvidia-pilot.html` + `team.html` | 合并改写 | 采集页，六队唯一任务书；`/api/pilot-progress/nvidia` 契约不变 |
| `report.html` | 改写 | 成果快照，章节即四问；必须在节点页证据面板上线之后，否则 M4 33 份候选证据失去唯一发布面 |
| `ops.html` | 收缩 | 只留用户、管线、录价、工具 |
| `research.html`、`research-graph.js`、`object-network.js` | 退役 | 有价值的部分（问题、候选证据、陈述、一跳关系）搬进部件节点第一问；关系图改按骨架 ID 过滤 |
| `supply-demo.html`、`poster.html`、`framework_poster.html` | 退役 | 示例数据、旧品牌、旧架构海报；同时从 `current_state.json` 的 implementations 移除 |
| `web/assets/levels.json` | 退役 | 尺度钻取链；3D 钻取改为骨架路径 |
| `routes.json` 三条已删模型路由、三条海报/烘焙路由 | 删除 | 指向已删文件或无入口页；显式登记 `/data/datacenter_model.json` |
| 00 规范、07 规范、`05_source_map.md`、`modules.json`、`framework/modules/M01–M15` | 退役入 `docs/archive`，走 supersede 链 | 五视角、八生态、按模块的信源图与模块声明；bom.json 的 `module` 字段改 `legacy_module`；`validate.py` 的模块校验随之退役 |
| 15 模块 Finding、十大判断、564 张模块工单、`coverage.py`、`workorders.py` | 降为兼容研究记录 / 退役 | 与账、部件、目标表无数据关系；派工只走目标表 |
| `research_graph.json` 2.2.1、`research_questions.json` 2.2.0 | 重做为 3.0 | 见 §7 |
| `data/policies.json` 与其 schema | 退役或并入站点权利 permits 的主体列 | 全仓无代码读取 |
| `reports/` 七个生成物 | workorders、blindspot 停止生成；verify_queue 保留 | 与 `storage_contract.json`、`container_storage.py` 同步 |
| `docs/intern/BATCH01_*`、`reports/templates`、`reports/HOW_TO_OUTPUT.md` | 归档；改写为目标行 ID / 三种导出说明 | 手写工单与未实现的交付矩阵 |

## 7. 研究图谱 3.0：契约由我们定义

Spark 已停，M4 与六队都等我们的指令，所以图谱不再"冻结在 2.2.1 只作 ID 登记"，而是按骨架重做，一次到位：

- **对象**只有六种：根、系统（含 IT 父与四子）、链路、部件（61 + 软件 + 基型）、站点权利、主体（公司）。由 `bom.json` + `site_rights.json` + `companies.json` 生成，不再手写。退役：`views` P/F/V/D/R、`navigation` 尺度树、`hardware_domains`、`ecosystem:*`、`scope:M01–M15`、`space:*`、`system:*`（含 safety）、`research_topics`、`arch/tech/workload/demand/activity`（其中工作负载与需求挂到收入侧因子，作根节点主体列的属性，不再是对象）。
- **问题表**：458 条问题 ID 不变（M4 的 33 份深读按问题 ID 回写，不失效），每条加 `node` 与 `variable_class`，`object_ids` 只允许骨架 ID；`views`、`topic_id` 删除；`module_id` 改 `legacy_module`。
- **校验**：`navigation.py` 重写为骨架校验（对象集合 = 骨架节点集合，顺序 = 系统顺序 × chain_order）；`registry.validate` 不再依赖 `views`；`test_research_navigation.py` 重写；`test_bom.py` 的域顺序断言补齐。
- **接收端**：#282 之后版本落后的快照按现行注册表过滤 ID 后接收并标 `registry_lag`，所以升版不会拒收；真实成本是 `reader_export.py` 投影指纹含 registry_key，32,734 份目录全量重投影一次。
- **发布**：3.0 与 `docs/local_reader/SPARK_OPERATIONS.md` 的示例版本同一提交更新；我们发出信号后 Spark 拉同一提交、M4 重导出一次。

## 8. 需要别人怎么配合我们

| 配合方 | 我们给它什么 | 它交回什么 | 什么时候 |
|---|---|---|---|
| **Spark 阅读服务** | 图谱 3.0 + 问题表 3.0（节点 ID、问题 ID、变量类）；`SPARK_OPERATIONS.md` 新版本号 | 证据与陈述，键是（节点 ID、问题 ID、变量类）；一次性重投影 32,734 份目录 | §9 第 3 步完成后，一次同步；此前保持停机 |
| **M4 原件整理** | 新的分类轴：骨架节点 + 变量类（`legacy_module` 只作属性）；`M4_TRIAGE_TASK.md` 改写 | 33 份深读按问题 ID 回写不变；后续整理按节点归档（`library/<node>/` 替代 `library/Mxx/`） | 与 Spark 同一次同步 |
| **inews** | feed v2 加 `object_ids`（节点 ID）字段（跨仓库变更） | 事件卡带节点与列；持有方行、新闻行的 delivered 判据 | 第 1 步 status 四态化之后 |
| **fetchspec** | 规格登记的 Git 载体约定（`product_docs_plan.csv` 的 doc_id / source_url，或索引文件入库） | 235 份 NVIDIA 规格的索引写回 Git；后续按部件 ID 交付 | 第 1 步 |
| **fetchdata 四队（待建）** | 目标表按队的 168 行任务书（ID 为 `F.* / P.* / S.*`）；建队顺序沿建设阶段上游先走（站点权利 → 电力） | 带 `target_id` 与 `variable_class` 的价格记录、事件卡 | 第 5 步采集页上线时能看到自己的产出 |
| **格洛可专题** | 反哺规则改为：新数据挂骨架节点 + 变量类；ID 不再用模块前缀 | 专题文章与价格记录 | 第 7 步 |

## 9. 迁移顺序与风险

每步末尾固定三件事：`governance --refresh`、评审摘要复审（`verification_contract.json` 锁定的规范正文改一处就要重登记，不能用 refresh 蒙混）、DECISIONS 一条。删除页面或组件时，必须在同一提交从 `current_state.json` 相应政策的 implementations 里移除，否则治理检查报缺失实现。

| 步 | 做什么 | 主要风险 |
|---|---|---|
| 0 规范先行 | 新建 `architecture-20260928`（source 单一，建议 03），supersede `architecture-20260906`，00 与 07 移入归档；05 新增"目录"节与四段、三级的定义；05 :73 与 `dashboard_rules.json` 改为"五系统 + IT 四子系统 + 站点权利，折叠 6 行、展开 10 行"；CURRENT 目录表加骨架 / 账本 / dashboard / 六队四行；`known_retired_patterns` 加五层、五视角、八生态、研究工作台、仪表盘、三个计算器；AUDIT.md 作为清零清单 | 规范文件全部锁定摘要，一步改七八个文件的摘要，需要你逐一复审 |
| 1 status 四态与 Git 载体 | 改 `targets.py`、`dashboard.py` 计数口径；`product_docs_plan.csv` 列约定；事件卡计数快照；30 行改标 local；重跑生成；`test_tco_targets.py` :48/:118 改口径 | sourced 数会变，DECISIONS 写明是口径变真不是数据倒退 |
| 2 目录与路由 | `site-shell.js` 六项按角色；`routes.json` 清理；`interface_manifest.json` 升版；README 与 05 :35 同步；面包屑 | 低；ui_skin、auth_appearance、url_rendering 改断言 |
| 3 骨架补齐 + 图谱 3.0 | `bom.json` 加 `stage`、`part_fetch.json` 加 operation 类别、登记表加 `node` / `variable_class`；图谱与问题表 3.0 由生成器产出；`navigation.py`、`registry.py` 重写；通知 Spark / M4 | 中：投影全量重做一次；`test_research_navigation`、`test_bom`、`test_catalog_bridge` 重写 |
| 4 节点页吸收证据 | 四个读法入口、列覆盖率、三级账角标、部件节点证据面板、派工面板改读目标表、灰格双向链接；`research.html` 302 到节点页 | 五个浏览器套件重写为节点页断言，`verification_contract.json` 的 tests 列表与 `run_browser.cjs` 同一提交改 |
| 5 采集页与派工 | `supply.js` 读目标表，四页并入；`/api/targets?mine=1` 服务端过滤；`assign_target`、`register_delivery(target_id, evidence_path)` 写进 09 软件契约；`assignments.json` 加 `target_id`；intern 门禁改 `auth.py` :197–200 与 `http.py` :236 | 中：实习生门禁只改前端即 403 |
| 6 爆炸图与主体收口 | 档案归一、规格库参数化、company 改主体列、3D 爆炸阶段按链路、`levels.json` 退役、rack3d 并入 | part_dossier、scene_* 套件 |
| 7 成果页改写 | 章节即四问；`report.py` 与 export 换源；反哺规则改写 | 必须在第 4 步之后 |
| 8 管理瘦身与清零 | ops 收缩；退役页撤路由；按 AUDIT.md 清 README、PANORAMA、AGENTS、01、06、handoff、guides、docs/research README 横幅；架构图重画 | 低；量大 |

## 10. 待你决定（五条，每条给建议）

1. **目录六项定名与顺序**：数据中心 / 账本 / 爆炸图 / 采集 / 成果 / 管理。建议接受；"爆炸图"保留你的原话，不改"组成"或"骨架"。备选：四项（数据中心 / 账本 / 采集 / 成果），爆炸图收进节点页构成列，代价是对外失去第一印象的直达入口。
2. **是否开设公开只读角色 reader**，让网站本身对外交付。建议开设：放行数据中心、爆炸图、成果三项的 GET；账本对 reader 只显示基准预设与四视图，不开放输入编辑与地区预设；对外长文继续走公众号，成果页末章链到它。备选：不开，网站维持登录后工作台。
3. **status 四态化与 Git 内登记载体**（§5）。建议接受；NVIDIA 235 份规格须先把索引写回 Git 才计入。
4. **旧模块体系的处置**：15 模块 Finding 与十大判断降为兼容研究记录（`doc.html` 可读，成果页不再展示），564 张模块工单停止生成并归档，458 条研究问题保留 ID 并重打标为节点问题，派工只走目标表，`modules.json` 与模块文件归档。建议接受，顺序上先让证据面板上线再退旧成果页。
5. **骨架补齐的三样东西**（§3：部件的 `stage` 属性与时间因子、部件级运行行、登记表加 `node` 与 `variable_class`）。这是"建"与"运"两种读法能否有数据基础的前提，也是六队交付物能进 status 的前提。建议接受，放在第 3 步与图谱 3.0 一起做。

## 附：四份方案与评审

三位评审（逻辑一致性、读者价值、可实施性）合计得分：骨架优先 34 / 33 / 31，最小改动 31 / 29 / 25，四段优先 30 / 30 / 28，读者优先 25 / 24 / 21。本稿以骨架优先为主干；嫁接了四段优先的格级诚实规则、采集页事实与规则标签、30 行改标 local、账本可信边界；最小改动的"目录是四问的全局视图"定义句、CURRENT 主题行、成果封面可信边界、排序冲突裁定；读者优先的根节点四个读法入口、灰格双向链接、规格库参数化。修掉的缺陷：读者优先把四个交付物做成第二根轴；四份方案共同沿用的"Spark 会 400 拒收"前提在 #282 后已过期，且 Spark 现在听我们指挥；"图谱长期冻结"不成立（任何 BOM 增删都会触发图谱变更）；"建"读法等同能量流链路不成立（§3.1）；"运"读法在部件层没有目标行（§3.2）。
