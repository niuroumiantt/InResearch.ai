# 系统检查 2 · inresearch.ai 骨架与素材仓库（2026-09-29）

> 检查记录，不是规范；改进项都是"建议，待用户决定"。依据：`framework/00_overview.md`（v3）、`CURRENT.md`、`01/03/05/06/09`、`current_state.json`、`bom.json` 2.2、`site_rights.json`、`tco_factors.json` 1.3.0、`part_fetch.json`、`tco_targets.json` 2.1.0、`dashboard_rules.json`、`research_graph.json` 3.0、`research_questions.json` 3.0、`supply_contract.json` 1.5、`interface_manifest.json` 1.4.0、`knowledge/targets.py` / `nodes.py` / `graph.py`、`workflow/dispatch.py`、`docs/reviews/2026-09-28/{site,alignment,architecture}`、`docs/DECISIONS.md` 2026-09-28 起；素材仓库只引用 `niuroumiantt/fetchspec`（`README.md`、`docs/FEEDERS.md`、`docs/MACHINES.md`、`docs/OPERATIONS.md`、`src/fetchspec/deliver.py`）与 `niuroumiantt/inews.today`（`README.md`、`docs/select-then-translate.md`、`docs/display-angles.md`、`docs/datacenter-feed.md`、`src/lib/datacenter-feed.js`、`src/lib/event-types.js`）的路径与结论，以及 `docs/handoff/fetchdata-bootstrap.md`。

## 一、骨架现状（机器登记里读到的数）

| 逻辑 | 登记 | 数 |
|---|---|---|
| 一棵树 | `bom.json` parts：61 part + 1 software + 1 archetype = 63 条目；9 个系统（5 顶层 + IT 4 子）；17 条链路；6 段建设阶段；`site_rights.json` 6 条权利 | 00 写"61 个部件 + 软件 + 基型"，交接页写"63 部件"——前者对 |
| 三级账 | `datacenter_model.json` 83 个输入，evidence：sourced 54 / assumed 16 / input 12 / needed 1；五类分布 3:30 4:16 5:15 2:14 1:8 | 与 05 一致 |
| 四问四段 | `dashboard_rules.json` 1.0：root / system / part / site_right 四级取值规则 + `honesty` + `cell_status`；`root.readings` 四个读法入口 | 一致 |
| 五类变量 | 目标表 351 行：3 价格 82 / 4 时间 74 / 2 运行 71 / 1 构成 70 / 5 主体 54；问题表 458 条：构成 244 / 价格 148 / 运行 38 / 时间 15 / 主体 13 | 问题表按关键词派生，偏向"构成" |
| 六队 | `supply_contract.providers` 六个 + local；目标表 `team` 列：fetchspec 130 / fetchreports 62 / fetchfilings 62 / inews 50 / fetchstat 26 / fetchquotes 21；`team_state` connected 只有 fetchspec 与 inews | 待建四队承担 171 行（48.7%），`next_due` 为空 |
| 四态 | sourced 37 / assumed 4 / **delivered 0** / needed 310 | 见 §三 第 1 条 |
| 一个模板 | `routes.json` `/` → `node.html`；`interface_manifest.sections` 六项：datacenter（index/node/doc）、ledger、bom（bom/bom3d/rack3d/product-catalog/admin-product/company）、acquisition（supply）、results（report）、admin（ops）；`public_pages` 8 页 | 一致 |
| 图谱 3.0 | 对象 6 种，关系 3 种；`graph.py` 由骨架生成；旧 ID 折算三处共用 `registry.object_resolver` | 一致 |

## 二、骨架：正交性、覆盖性、可机检性的具体问题

| # | 维度 | 问题 | 证据 | 影响 |
|---|---|---|---|---|
| S1 | 可机检 | **`layer` 一个键名三个意思**：`bom.json` 的 `layer`/`layers` 是尺度 S1–S5（"装在哪"）；`tco_targets.json` 的 `layer` 是变量类兼容名；inews feed 的 `layer_tags` 是变量类。治理扫描把"五层"列为退役词，但键名没改，机器读到 `layer` 无法判断是哪个。 | `bom.json.layers`、`tco_targets.json.layers`、`targets.py:26`、inews `event-types.js EVENT_LAYERS` | 中：任何新写的消费代码都可能拿尺度当变量类 |
| S2 | 正交 | **`module` 没有降成 `legacy_module`**：00 与 DECISIONS 说旧模块降为兼容属性 `legacy_module`，但 `bom.json` 63 条目和 `site_rights.json` 6 条仍用 `module` 键（0 条 `legacy_module`）；问题表已改名。 | `bom.json` parts、`site_rights.json.rights[*].module` | 低：词汇不一致，治理扫描只扫文本不扫键名 |
| S3 | 正交 | **主体：对象类型与变量类混用**。`companies.json` 248 条全部 `node=actor:*、variable_class=5`——这表示"这条记录是主体"；而目标表里主体类 54 行挂的是部件或权利（谁持有、谁供应、谁付费）。同一个"5"既标对象身份又标数据类别。03 没有写明：变量类 5 的记录应挂在非 actor 节点上并引用一个 actor。 | `nodes.py` REGISTRIES、`companies.json`、目标表 `S.*.holders` | 中："主体列"在节点页是"谁供应/谁持有"，在主体页是"这家公司"，两页语义不同 |
| S4 | 正交 | **时间类 vs 建设阶段**：`stage` 是部件/权利的属性（6 段），time 类是变量；`time.build` 因子生成工期/排队/审批行但因子行 `stage=null`；"它怎么建"读法按 `stage` 排、按时间列取值，两者靠 `dashboard_rules.system[4]=max(部件交期)` 连起来。逻辑成立，但 05/03 没有一句写"stage 是排序键不是变量类"。 | `bom.json.stages`、`targets.py`、`dashboard_rules.json` | 低：文档补一句 |
| S5 | 覆盖 | **四问 ↔ 目录六项不是一一对应**：数据中心与成果各覆盖四问（全局视图），账本 = 第①③问，爆炸图 = 第②问，采集 = 第④问，管理 = 无。00 说"目录是四问的全局视图"是对的，但 `interface_manifest.sections` 没有登记每项对应哪几问，页面与测试无法机检。 | `interface_manifest.json.sections`、`site-shell.js:24–25` | 低 |
| S6 | 覆盖/重复 | **目标表生成既覆盖又重复**：`test_every_non_user_input_has_a_target` 只查覆盖；实测 77 个被喂的模型输入里 55 个由 >1 行喂（`it_capex_per_kw` 48 行、`accelerator_share` 34 行、`capex_electrical` 22 行）。多行喂一个输入是设计（因子行 + 部件行），但没有"主行"概念，账本里"这个输入的目标行"链接会指向几十行。 | `targets.py` `model_inputs`、`tco_targets.json` | 中：账本可信边界的回链失焦 |
| S7 | 可机检 | **四态中的 delivered 今天不可能非零**。三种 Git 载体：(a) `data/product_docs_plan.csv` 与 `data/prices.json` 同时是 `storage_contract` 的运行状态（`kind: state, seed: true`）：线上 `add-price`、`register_delivery`、Spark `fetchspec-receive` 都写运行库，永远不回 Git；512 条价格 0 条带 `target_id`。(b) `data/event_cards.json` 全仓只有 `targets.py` 读它，没有任何写入者；inews feed v2 没有 `part_id` / `site_right_id` / `target_id` / `object_ids`，事件卡无法从 feed 机械生成。(c) `register_delivery` 只写 `assignments.json`，页面标"运行库有 / Git 无"，没有把回执搬进 Git 的命令。 | `targets.py:111–156`、`storage_contract.json`、`dispatch.py`、`news_sync.py`、inews `datacenter-feed.js collectionTags` | **高**：六队交付了也翻不了状态，采集页六队卡永远 0 |
| S8 | 覆盖 | **执行机登记与实际不符**：目标表 fetchspec 130 行全标 `host=aws`（vendor_page → continuous），而 fetchspec 的 `docs/MACHINES.md` 写"Macmini 为主力抓取机器"，NVIDIA 批次实际在 M5 跑。06 的"一个来源一台主执行机"在登记层就错了。 | `tco_targets.json` host 列、fetchspec `docs/MACHINES.md`、`supply_contract.temporary_execution` | 中 |
| S9 | 覆盖 | **问题表变量类偏斜**：458 条按标题关键词派生，构成 244 / 主体 13 / 时间 15。"它怎么建"与"谁持有"两个读法在问题层几乎没有问题挂。 | `research_questions.json`、`graph.py QUESTION_CLASS_OVERRIDES` | 中：第 4 步节点页证据面板在时间/主体列近乎空 |
| S10 | 规范 | **图谱六种对象够不够**：`projects.json` 120 条、`contracts` 2 条、`policies` 2 条、四个地区、512 条价格序列今天都不是对象；目标表 `instances` 是字符串。不建议加对象类型：项目/合同是 actor↔part/site 关系上的事件，价格序列已按 `series_id` 挂部件（`nodes.py`），地区是模型预设。但 03 应写下这条判据："只有需要被追问到底的东西才成对象；项目、合同、序列、地区是关系或属性"。 | `graph.py`、`nodes.py`、`company.html` 附表 | 低 |
| S11 | 规范 | **"一个模板"只对 dashboard 成立**：13 个静态页里只有 `index.html` 是 `node.html` 的别名；账本、爆炸图、规格库、主体、采集、成果、管理各是独立页。00 已限定"node.html 是 dashboard 的唯一模板"，AUDIT 判据 6 写得更宽。建议 CURRENT 一句：其余页面是"某一列 / 某一问的展开页"，登记在 `interface_manifest.sections`。 | `interface_manifest.page_sources` | 低 |
| S12 | 退役 | **兼容层没有退役时刻**：`legacy_module`（bom 里还叫 `module`）、`workflow/workorders.py` + CLI `workorders` + `reports/workorders.*`（storage_contract 仍登记）、`research-graph.js` / `object-network.js`（留给 3D 档案面板）、`compare.html`（excluded）。`current_state.json` 没有 `retire_after` 之类字段，治理不会提醒。 | `manage.py` 命令表、`storage_contract.json`、`interface_manifest.excluded_pages` | 中 |
| S13 | 页面 | **rack3d 并入与否**：rack3d 已是 bom3d 钻取链的"IT · 计算链路 → 芯片级"阶段，只是文件没合并。 | DECISIONS 2026-09-28 第 6 步 a | 低 |

## 三、素材仓库：是否都朝"提供素材"设置

| 项 | fetchspec | inews.today | fetchdata（待建） |
|---|---|---|---|
| 给 inresearch 什么 | 厂商官网规格原件（PDF/HTML 快照）、结构化产品库；`docs/FEEDERS.md` 一句"是 inresearch.ai 的一个采集产品" | 带事件类型 / 层标签 / 原件指针的新闻投影 `/api/feeds/datacenter`；`README.md:79` 一句、`docs/select-then-translate.md`、`docs/display-angles.md` §2 | bootstrap 已写清四队、包格式、第一批行 ID |
| 按哪张表领任务 | `--task <inresearch 任务 ID>`（`company-deliver`）；README 没写"按 `tco_targets.json` `team==fetchspec` 130 行领任务"；仓库里没有引用目标表 | 没写；50 行 inews 目标（39 条 news + 11 条 holders 类）在 inews 仓库里没有任何对应 | bootstrap 写了按 `team` 列筛选与首批行 ID |
| 交付格式 | 契约 1.1 包（`manifest.json` + `SHA256SUMS` + `files/`），`deliver.py` 逐文件重算 SHA、台账记已交付 | 不是包，是 HTTP feed（`kind: existing_feed`）；无 `delivery_id`、无回执 | 按包格式 |
| 回执落点 | Spark `manage.py fetchspec-receive` → `raw-materials/` + 产品库索引（运行库） | Spark `manage.py news-sync` → 采集台账（运行库） | 供应中心 `/api/supply`（运行库） |
| 目标行怎么进 delivered | 需要人把 `product_docs_plan.csv` 的 doc_id / source_url 写回 Git —— 没有命令 | 需要 `data/event_cards.json` —— 没有生成器，feed 也没有部件 / 权利 / 目标行 ID | 价格记录带 `target_id` 写回 Git —— 没有命令 |
| README 是否说清 | 首屏混着 OpenAPI 查看器（另一产品），"给 inresearch 提供什么"在 `docs/FEEDERS.md`、"机器"在 `docs/MACHINES.md`，三处才凑齐 | 说清了"两条线"，没说清"目标表 50 行是我的任务书" | 是 |

结论：三个仓库的**方向**都朝着"提供素材"（包格式统一、身份键与 inresearch 对齐、不直写事实），但**回路没有闭合**：交付与回执都停在运行库（Spark / AWS），而状态四态只认 Git 载体，中间缺一条"回执 → 作者 checkout → Git"的通道；inews 一侧还缺把事件映射到目标行的字段。

## 四、改进清单（按影响 / 成本排序）

标记：**机检** = 可进 `--check` 或单测；**规范** = 要进 00 / 03 / 05 / 06 / 09 与 CURRENT、DECISIONS；**页面** = 只是页面或文档。

| 序 | 影响/成本 | 改进 | 类型 | 对应 |
|---|---|---|---|---|
| 1 | 高 / 中 | **给 delivered 一条能走通的路**：(a) 新增 `manage.py deliveries import`：在作者 checkout 读取运行库导出（`assignments.json` 的 `register_delivery` 指针、Spark `fetchspec-receive` 回执、价格记录），生成 / 更新 `event_cards.json`、`product_docs_plan.csv` 行、带 `target_id` 的价格记录，然后 `targets --refresh`，走 PR；(b) 09 写明"运行库回执经导入命令进入 Git 载体，不自动"；(c) 单测：三种载体各有一个写入路径，`event_cards.json` schema 存在。 | 机检 + 规范 | S7 |
| 2 | 高 / 中 | **inews feed v2 加 `object_ids`（骨架 ID）或 inresearch 侧生成事件卡**：feed 已有 `event_type` / `layer_tags` / `origin_pointer`，缺挂点。两条路：inews 用 `news_policy.build_terms` 同款词典打 `object_ids`（跨仓库改动，提案 §8 已列）；或 inresearch 的 `news-sync` 后处理按公司词典 + 部件同义词生成候选事件卡进 `data/.material-intake`，作者审后导入。`news_sync.validate_v2_fields` 同步校验 `object_ids ⊂ 骨架 ID`。 | 机检 + 规范（06） | S7 |
| 3 | 高 / 低 | **执行机登记对齐实际**：`part_fetch.json` / `supply_contract.providers[fetchspec]` 加 `host_default: macmini`（或按来源分 aws/macmini），重跑 `targets --refresh`；单测：每个 provider 的 `host_default` ∈ execution_policy，目标行 host 与 provider 一致。 | 机检 | S8 |
| 4 | 中 / 低 | **键名去歧义**：`bom.json` `layer` → `scale`（`layers` → `scales`），别名一版兼容；`tco_targets.json` 删 `layer` 键（`layers` 说明保留一个版本）；`validate --strict` 加"`layer` 键不得再出现在骨架与目标表"。 | 机检 | S1 |
| 5 | 中 / 低 | `bom.json`、`site_rights.json` 的 `module` → `legacy_module`；`validate` 校验骨架文件不含 `module` 键。 | 机检 | S2 |
| 6 | 中 / 低 | **目标行"主行"**：因子 fetch 条目与部件行喂同一输入时，因子行为 `primary`；`tco_targets.json` 行加 `feeds_primary: bool`；账本可信边界只链主行；单测：每个模型输入恰有一条主行。 | 机检 | S6 |
| 7 | 中 / 中 | **主体类判据写进 03**："对象类型 actor ≠ 变量类 5；变量类 5 的记录挂在部件 / 权利 / 根上并引用 actor"；`nodes --check` 加规则：`variable_class=5` 且 `node=actor:*` 只允许出现在 `companies.json`。 | 规范 + 机检 | S3 |
| 8 | 中 / 中 | **问题表变量类复核**：抽 100 条人工核对派生结果，把纠正写进 `QUESTION_CLASS_OVERRIDES`；单测锁住时间与主体类各 ≥ N 条（N 由复核定）。 | 机检 | S9 |
| 9 | 中 / 低 | **兼容层退役日历**：`current_state.json` 每个兼容实现加 `retire_after` 与 `retire_when`（如 `workorders`：M4 深读分包改读目标行后；`research-graph.js`：3D 档案面板改用 `part-dossier` 后）；`governance --check` 报过期。 | 机检 + 规范 | S12 |
| 10 | 低 / 低 | `interface_manifest.sections` 每项加 `questions: [1..4]`；05「目录」表加一列"对应哪几问"；浏览器套件断言导航文案与 manifest 一致。 | 机检 + 页面 | S5 |
| 11 | 低 / 低 | 03 补三句判据：stage 是排序键不是变量类；对象只收"要被追问到底"的东西（项目 / 合同 / 序列 / 地区不是对象）；"一个模板"限定为节点页。 | 规范 | S4 S10 S11 |
| 12 | 低 / 低 | 三个素材仓库 README 首屏加同一张"供给卡"（给谁、什么格式、按 `tco_targets.json` 哪个 `team` 领任务、回执到哪、状态怎么翻）；fetchspec 把 OpenAPI 查看器移出首屏或拆仓。 | 页面（外部仓库） | §三 |
| 13 | 低 / 高 | rack3d：不做物理合并；把 `rack3d.html` 从 `static_pages` 降为 `bom3d.html` 的子路由（URL 保留、`sections.bom` 不变），两场景共用 `scene-*` 模块即可。 | 页面 | S13 |

## 五、不需要改的

- 六队与 `team` 列一一对应，`test_team_and_host_registered` 已锁。
- 图谱 3.0 六种对象足够；不建议为项目 / 合同 / 地点 / 价格序列开新对象类型（见 S10）。
- 四态判据"只认 Git 载体"本身是对的（运行库不是权威）；缺的是通道，不是判据。
- `node.html` 作为 dashboard 唯一模板与 `dashboard_rules.json` 的四级取值规则是清楚的。
