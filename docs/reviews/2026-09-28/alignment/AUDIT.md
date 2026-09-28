# 全仓对照清单：哪些文件还在用旧角度

2026-09-28｜状态：**扫描结果，供改写用**。三路只读扫描（页面与测试、框架与后端、现行文档与数据）合成。判据是今天定下的唯一逻辑；处置栏是建议，最终以《目录与页面框架 v3 提案》为准。行号写作 `:n`，来自扫描当日的文件。

## 0. 判据：唯一逻辑的六条

| # | 唯一逻辑 | 出处 | 旧角度（见到即判不符） |
|---|---|---|---|
| 1 | **一个骨架**：数据中心 → 五个系统（设施、电力、冷却、IT、控制与软件），IT 分四个子系统（计算、内存、存储、网络）；系统内部件按能量流链路排；61 部件 + 软件 + 基型；六条站点权利。尺度是部件的属性，不是任何树的第一层 | 03 规范 :15–19；bom.json 2.1 `systems`；site_rights.json；DECISIONS 09-28 | 八生态 / 主生态 / hardware_domains；生态旧名（存储生态、计算与加速、内存生态、网络与互联、电力与供配电、冷却与热管理、设施与机柜、控制与运维）；尺度树（园区与资源接入 → 建筑与安全 → 机房与设施 → 机柜与整机 → 内部部件）；space:site/building/hall/row 作对象；旧域 ID cooling/campus/dcim |
| 2 | **五类变量**：1 构成、2 运行、3 价格、4 时间、5 主体 | datacenter_model.json `groups`；06 规范 :107–117 | 五层 / layer(s) 作概念（作兼容别名可） |
| 3 | **三级账**：成本、收入、回报，来自唯一的统一模型；一个账本页，四个视图，三种问法 | datacenter_model.json；economics.py；05 规范 :57–63 | 三个计算器；经济模型页 / TCO 页 / 成本计算页；datacenter_tco_model / datacenter_economics_model / datacenter_cost_model；docs/research/*/model.py 作参考实现 |
| 4 | **四问 · 四段**：它值多少 / 由什么组成 / 怎么影响账 / 数据从哪来缺什么；采集 → 事实 → 规则 → 视图 | dashboard_rules.json；05 规范 :73（部分） | 五视角 P/F/V/D/R（物理与空间 / 系统与接口 / 产业与交易 / 需求与工作负载 / 问题与证据）；九主题 T01–T09；"研究工作台" 以 对象/问题/证据/任务 为顶层框架 |
| 5 | **六队**：采集分六个队，目标表是唯一任务来源 | supply_contract.json providers；tco_targets.json（生成） | 模块 M01–M15 作任务与归档的主轴；"工单 = 模块声明 − 仓库现状"；五层目标清单；旧目标 ID `L3.*` |
| 6 | **一个模板**：node.html 是 dashboard 的唯一模板；首页退役；账本从根节点价格列链入 | 05 规范 :73；routes.json | 首页 / index.html 作入口；KPI 拼盘、看板、地图；team.html 团队看板；ops.html 运维台的 L0/L2/L4 分层 |

判定：**符合**（只用唯一逻辑）｜**部分不符**（骨架对但词汇、ID、链接或某个模式是旧的）｜**完全是旧角度**（组织轴就是旧的）｜**基础设施**（无领域词汇）｜**历史材料**（快照或归档，不改正文但要标身份）。

## 1. 先看统计

| 范围 | 符合 | 部分不符 | 完全是旧角度 | 基础设施 / 历史 |
|---|---|---|---|---|
| 页面 web/pages（21） | 1 | 9 | 11 | 0 |
| 组件与样式（16） | 1 | 4 | 3 | 8 |
| 浏览器测试 tests/*.cjs（22） | 0 | 10 | 8 | 4 |
| 规范 framework/*.md（11） | 4 | 4 | 3 | 0 |
| 登记 framework/*.json（15） | 6 | 6 | 3 | 0 |
| 后端 src（按有领域词汇的模块计 24） | 8 | 12 | 4 | 0 |
| 单元测试 tests/unit（有领域词汇的 12） | 4 | 7 | 1 | 0 |
| 数据登记 data/*.json 与 web/assets（15） | 2 | 11 | 0 | 2 |
| 现行文档 docs（19） | 4 | 9 | 3 | 3 |

只有六样东西是今天的逻辑：`node.html` 的骨架、`ledger.html` 与 `datacenter-model.js`、`economics.py`、`bom.json` 与 `site_rights.json`、因子树与目标表。其余不是残留，是主干。

## 2. 规范之间已经互相矛盾（先解决这一层，页面才有依据）

| 矛盾 | 一边 | 另一边 | 处置 |
|---|---|---|---|
| dashboard 矩阵是几行 | 05 规范 :73 "八生态 + 站点权利、8 + 1 行 × 5 列、第九行"；dashboard_rules.json :4 同 | 03 规范 :19 与 DECISIONS 09-28 "五个系统、IT 展开四行"；node.html 实际五行 | 05 :73 与 dashboard_rules :4 按五加四重写 |
| 部件的 system 指向什么 | 03 规范 :9 "指向八个生态之一" | 同文件 :17 五系统、IT 为父 | 03 删 :9 旧段，:23/:25/:29/:31/:39/:49 一并清 |
| 什么是现行研究架构 | CURRENT.md :9 指向 00（五视角）、:16 指向 07（八生态）；current_state.json :40 "保持五视角架构" | 03 与 DECISIONS 的骨架 | CURRENT 目录表重排：研究架构 = 骨架（03）；00 重写或退役；07 归档 |
| 治理能不能抓旧词 | current_state.json :714–726 `known_retired_patterns` 无 五层、八生态、三个计算器、tco.html 等 | 我们已宣布退役 | 补登记，让 `governance --check` 抓 |
| 参考实现是什么 | current_state.json :344–351 列 docs/research/*/model.py | economics.py 是唯一参考实现，那三个脚本读的文件已删 | 去掉三条实现，登记 economics.py / datacenter-model.js / test_model.py |
| 图谱顺序 | DECISIONS 09-28 说 hardware_domains 已按链路重排 | research_graph.json :6267–6416 顺序仍是 storage 起头 | 图谱重做时消除 |

## 3. 已经是坏链的地方（不等设计就该修）

- `docs/research/datacenter-economics/model.py`、`datacenter-tco/model.py`、`2026-09-27/datacenter-profit/profit-model.py` 读已删除的模型 JSON，仍在 current_state.json :346/:349/:351 登记为现行实现。
- `web/routes.json` :96–100 仍给已删除的 `datacenter_economics_model.json`、`datacenter_tco_model.json` 留路由；:115–119 公开的四份 `docs/research/*/README.md` 把 tco/economics/cost 页写成现行页面，无历史横幅。
- `data/dashboard.json` :353–1674 `graph_name` 带旧生态名，来自 dashboard.py :47/:234 读 research_graph 的 ecosystem 对象；node.html :283 原样渲染。
- `node.html` :107 链 dashboard 提案页作"为什么这样排"，该页仍画 8 × 5 与三个计算器；`docs/reviews/2026-09-28/architecture/ARCHITECTURE.svg` 是唯一架构图，仍画八生态、三个计算器、9 × 5。
- `bom.html` :116 硬编码 "46 个部件"（实际 61）；:309 链 2026-08-16 的全库通读报告，无横幅。
- `docs/handoff/fetchdata-bootstrap.md` :35 的首批目标 ID（`L3.power_price.state_industrial` 等）已不存在，现为 `F.cost.energy.price.power_price.state_industrial`。
- `docs/handoff/tco-model-fetch-teams.md` :7 说"三级四段五层六队仍是草案、tco.html 已上线"，两句都不再成立。

## 4. 页面 web/pages

| 文件 | 今天的组织轴 | 旧角度（行） | 判定 | 处置建议 |
|---|---|---|---|---|
| node.html | 一棵树·五列·四问（:100）；五系统 + 站点权利（:164–174）；按链路分段（:189–192）；三级账（:259） | ID 与数据键仍是 `ecosystem:`/`d.ecosystems`（:167/177/251–252/272/277/281/293/300）；文案"八生态""八个生态 × 五类变量，第九行是站点权利""回到生态"（:256/262/265/287/290/291/300/316）；`研究入口 ${eco.graph_name}` 渲染旧生态名（:283）；"账本先对齐三个模型共用的假设"（:260）；链 research.html?view=P"研究工作台（九主题）"、按 layer S4/S5 门控 rack3d（:300）；"园区 3D"（:104/311）；"派工面板（自首页迁入）""团队看板 →"（:77/217/228）；读 data/tco_targets.json（:246） | 部分不符 | 改写词汇与 ID（`system:`），去研究工作台/团队看板链接，研究入口改为第四问面板；`graph_name` 从生成器去掉 |
| ledger.html | 统一模型、五类输入、四个视图 | 无（未用"三级账"一词；:103 "四本账输出"） | 符合 | 加"三级账"三个字与根节点回链 |
| bom.html | 默认按系统（:201/219–236） | "按尺度"第二模式把 layers S5→S1 当行（:110/107/212–218/159–187/203–211/35/39/70/242/245）；硬编码 46（:116）；站点权利只做 chip 不链 node（:260–261）；研究归属链 report.html#ch-模块 与 research/模块.md（:291–292）；"机柜拆解台"（:101） | 部分不符 | 去尺度模式（尺度改为筛选属性）；部件数读 bom.json；权利链 node；研究归属改链节点第四问 |
| bom3d.html | 领域 chips 来自叶子系统（:878–896）；链路排序与链路漫游（:964–987） | "产品生态" tab → research.html?node=ecosystem（:107）；机柜拆解台（:110/127）；爆炸阶段按尺度（:813–820）与场景分段（:500/568/700/810）；钻取条读 levels.json 尺度链（:72/1063–1066）、`\|\| "index.html"`（:1066）；DOMAIN_ALIAS cooling/campus/dcim（:899）；"dcim"网格（:696–697）；站点权利映射回旧部件 ID land/water/grid（:166–169）；view:'campus'（:1004）；"八个叶子系统""1-6 直达"实际 1-8（:878/117/994）；"领域"称呼（:851）；"盲区仪表盘"（:855） | 部分不符 | 爆炸阶段改为按系统链路；钻取条改为骨架路径；去旧别名与 campus 视图名；权利用 site:* 身份；"领域"改"系统" |
| rack3d.html | 机柜物理拆解，尺度优先（:637–645） | 产品生态 tab（:89）；levels.json 钻取（:55/736–752）、index.html（:739）；view:'rack'（:686）；"返回数据中心全景"→bom3d?d=compute（:105）；无系统/链路/五列 | 完全是旧角度 | 并入 bom3d 的 IT 系统链路视图（计算链路的芯片级拆解），本页退役 |
| research.html | 研究图谱工作台，P/F/V/D/R | "研究视图"（:15）；结构 2D/园区 3D/机柜拆解/产品资料（:16）；"在物理结构、系统连接、产业角色和需求之间切换"（:22）；研究视角（:28）；工作台概览与产品入口（:20）；noscript → report.html（:45） | 完全是旧角度 | 退役；问题、材料、证据、任务并入 node.html 第四问（每个骨架节点） |
| company.html | 公司优先：KPI 拼盘、地图、L1–L9 项目、按模块的研究结论 | KPI（:26–29/185–192）；地图（:134–158/194）；看板（:30–36/194–207）；按 M 模块结论（:104–117/205）；园区（:186/196）；只链 bom.html（:56） | 完全是旧角度 | 改写为主体页（第 5 类）：公司作为主体挂到它供应的部件、持有的站点权利、签的合同；去 KPI/地图/模块 |
| report.html | 章 = M01–M15（:199–210） | 十五章（:91/184）；十大核心判断（:191）；证据等级 S1–S5 与尺度码撞名（:187）；只链 bom.html（:77） | 完全是旧角度 | 退役为兼容附录（02 规范允许模块报告作兼容）；"成果"改由节点第四问与专题承载 |
| team.html | 工单按模块 mid | 团队看板（:8/71）；index.html 仪表盘（:70）；模块概览与模块卡（:76/136–151/169/175）；"工单 = 模块声明 − 仓库现状"（:113）；tiles（:136–139） | 完全是旧角度 | 改写为六队派工页：目标表 287 行按队 × 状态 × 日历 |
| ops.html | L0/L2/L4 分层、模块、漏斗、KPI | 九级漏斗（:163）；监测仪表盘 L4（:167）；研究模块 L2（:170）；项目库 L0（:173）；DIM_NAMES 五维（:251）；手工价格按 module（:130）；KPI（:305–312）；模块卡（:338–347）；Top10 地图（:376）；每模块下一步（:377）；新闻（:148） | 完全是旧角度（用户管理 :91–113/183–248 中性） | 拆：用户管理保留为管理页；其余退役；手工价格录入改按部件 + 变量类 |
| poster.html | 服务器九层物理堆叠（:119–138） | index.html 总览（:82）；机柜拆解台（:85）；"层"（:40/96/107）；KPI tiles（:164–179）；只链 bom/rack3d（:157–158） | 完全是旧角度 | 退役；若要海报，按骨架重画 |
| framework_poster.html | M01–M15 模块地图、五视角、五层 | 标题（:6）；五视角工作台（:346）；:351–357；五层 .layer/.datalayer（:121–165/297–330/373–516）；九级漏斗（:386–388/561）；红黄绿仪表盘（:526）；数据层↔知识层（:569）；:575–576 | 完全是旧角度 | 退役；由新架构图替代 |
| supply.html（+ supply.js） | 供应方 → 需求（按研究问题）→ 任务 → 交付 | 作战总览（:6）；引用研究问题树（:8）；`研究映射` P/F/V/D · T01–T09（supply.js :35 ← supply_contract :112–208）；产品地图（:26）；第一层产品分类（:45） | 完全是旧角度 | 改写：供应方 = 六队，需求 = 目标行，映射 = 系统/链路 + 变量类 |
| supply-demo.html | 演示 | 八生态名 + P/F/V/D + T01–T09（:14–23）；研究架构对应（:25）；:26 | 完全是旧角度 | 退役 |
| product-catalog.html（+ js） | 厂商目录 groups → families | :23–30；js :6/51–64/98 产品地图；不连部件/系统 | 完全是旧角度 | 改写为部件优先：从骨架部件进厂商产品线（products.json 需先补 system/chain） |
| doc.html | 通用 markdown/CSV 阅读器 | index.html 仪表盘（:72）；默认 research/M08.md（:285）；CSV 按模块筛（:171–234） | 部分不符（轻） | 改回链与默认文档；模块筛改可选 |
| materials.html | 收件箱，自由文本 | /index.html 总览（:7）；不连部件/目标 | 部分不符（轻） | 改回链；收件挂目标行 |
| compare.html | 3D 资产 QA | admin（:35）；机柜拆解台（:38）；PART 正则用网格名（:80） | 部分不符（工具） | 改链；网格名映射到部件 ID |
| nvidia-pilot.html | 流水线状态 | 无领域词汇；链 product-catalog（:6） | 部分不符（流水线） | 只改链 |
| bake.html | 内部渲染工具 | 九层键 chassis/fans/gpu-board/mobo 非 bom 部件 ID（:158–276） | 部分不符（内部） | 键改 bom 部件 ID |
| admin/product/index.html | 产品资料采集看板 | 看板（:8/231）；研究工作台 view=V（:109）；产品生态（:110） | 部分不符 | 改链；并入采集进度 |

## 5. 组件、样式、资产

| 文件 | 旧角度（行） | 判定 | 处置建议 |
|---|---|---|---|
| components/datacenter-model.js | 注释 former TCO/economics/cost（:223/272/298）；旧地址重定向表（:361–362） | 符合 | 保留重定向表 |
| components/research-graph.js | VIEW_INFO P/F/V/D/R（:4–10）；objectViews（:210–229）；navigationForView 读尺度树（:230–246）；navigation_note（:460–461）；面包屑（:237/652–653）；默认 space:site（:788）；:498–499；TYPE_LABELS 园区/建筑/空间（:41）；生态入口 hardware_domains "按产品生态研究"（:196–199/503/585–587/782–787）；:781；tabs（:412）；九主题（:599–603）；园区 3D 定位/机柜参考拆解（:680–681）；从不链 node.html | 完全是旧角度 | 退役；其"问题/材料/陈述/任务"渲染重写为 node.html 第四问面板组件 |
| components/object-network.js | 九个研究角度（:7–8/34/141）；研究图谱版本（:101） | 完全是旧角度 | 退役（或改为骨架关系图：系统 → 链路 → 部件 → 权利/主体） |
| components/part-dossier.js | 元信息 系统·链路·尺度（:26）与 node 链（:39）正确；view campus/rack 与 S4/S5 门控（:17/42–45）；嵌 P/F/V/D/R 面板（:32）；研究模块 → report.html#ch-（:40–41） | 部分不符 | 去视图门控；研究面板换第四问组件 |
| components/site-shell.js | overview → /index.html、research → /research.html（:25）；资料/任务/成果/管理（:26–27）；brand → /index.html（:48）；无 node/ledger 全局入口 | 部分不符 | 目录重定（待提案） |
| components/product-catalog.js、supply.js | 见页面 | 完全是旧角度 | 随页面改写 |
| components/datacenter-news.js | 无领域轴 | 部分不符（弱） | 新闻挂节点（第五类事件） |
| themes/site-skin.css | 旧结构样式钩子 .rg-view(s)/.rg-catalog/.rg-tree/.kpi(s)/.board/.mod/.dchip/.rg-workbench-overview（:47–185） | 基础设施 | 随页面退役清理 |
| assets/levels.json | "3D 四级下钻链" 园区→建筑→机房→机柜列（:2/5） | 部分不符 | 退役，钻取改为骨架路径 |
| part-inspector/model-assets/scene-*/series-summary/markdown-inline/auth-form；themes/supply.css；assets/models/manifest.json | 无领域词汇 | 基础设施 | 不动 |

## 6. 浏览器测试 tests/*.cjs

| 文件 | 旧角度（行） | 判定 | 处置 |
|---|---|---|---|
| dashboard.cjs | 锁 `ecosystem:` ID（:21/23/25）；注释（:1）；`.board`"自首页迁入"（:14–15） | 部分不符 | 随 node.html 改 ID |
| datacenter_tco / economics / cost.cjs | 用旧地址与旧文件名测新视图 | 部分不符 | 合并为 ledger.cjs（在册评审文件，需用户改契约） |
| run_browser.cjs | 默认套件名含旧名（:10–11） | 部分不符 | 随套件更名 |
| ui_skin.cjs | 遍历 static_pages 含旧页（:12/24）；research view=P（:25/83–91）；report 150 findings（:31）；ops 15 模块（:33）；index.html（:43–46/96/106） | 部分不符 | 随页面清单改 |
| hardware_ecosystems.cjs（八生态 :5–13）、object_network.cjs（:5/11–13/17）、product_node_hover.cjs（:4）、research_summary.cjs（:24–36）、research_delivery.cjs（15 章/index/team :10–26）、datacenter_news.cjs（index.html :7/17/21/38）、supply.cjs（:11/18/35–41）、product_catalog.cjs（:10–15/36/41–44） | 整个测的是旧页面 | 完全是旧角度 | 随页面退役或重写 |
| part_dossier.cjs（:19/24–26/30/37）、scene_framing.cjs（part==='land' :61）、scene_bootstrap.cjs（:13） | 旧视图与旧部件 ID | 部分不符 | 随组件改 |
| url_rendering.cjs | 安全测试经过旧页（:11/16/28–29/40–47） | 部分不符（轻） | 改用现行页 |
| scene_resources / model_assets / nvidia_pilot / auth_appearance.cjs | 无领域轴 | 基础设施 | 不动 |

## 7. 规范 framework/*.md

| 文件 | 旧角度（行） | 判定 | 处置建议 |
|---|---|---|---|
| CURRENT.md | 研究架构 → 00 + research_graph + research.html（:9）；07 为现行（:16）；03 只写"3D 与产品映射"（:12）；没有骨架、统一模型、dashboard 的行 | 部分不符 | 目录表重排：骨架、账本、dashboard、六队各一行；00/07 退出 |
| 00_overview.md（2026-09-12） | 五视角（:5/9–21）；尺度树（:25/27）；15 模块主节（:40–60）；九主题（:64）；无骨架 | 完全是旧角度 | 重写为《研究框架总览 v3》：骨架 + 五类 + 四问四段 + 三级账 + 六队；模块降为兼容附录 |
| 01_data_standards.md | "适用于五视角研究"（:3）；四轴 P/F/V/D/R、M、L1–L9、BOM 尺度（:7） | 部分不符 | 改轴：骨架节点 + 五类变量 + 主体/时点 |
| 02_knowledge_format.md | 模块仅兼容（:17–24/39） | 符合 | 不动 |
| 03_bom_and_collaboration.md | :7–19 新节正确；头仍 2026-09-14（:3）；"八个生态之一"（:9）；P/F/V/D/R（:23）；尺度下钻（:25）；"每层"（:29）；九主题（:31）；15 模块（:39）；"域"（:49） | 部分不符 | 删旧段，头更新 |
| 04_reading_scoring_standard.md | 顺带提模块（:61/75） | 符合 | 不动 |
| 05_source_map.md（2026-08-16） | 按模块（:3/8–21）；sources_orgs 未建（:25） | 完全是旧角度 | 归档；来源图由目标表承担 |
| 05_interface_system.md | :57–63 统一模型节正确；节点页节写八生态/9 × 5/第九行（:73）；对象图谱按 07（:69）；"保留五种视角"（:83）；地图样式（:14） | 部分不符 | :73 按五加四重写；:69/:83/:14 删 |
| 06_acquisition.md | :107–117 新节正确；八生态 + P/F/V/D/R + T（:11）；层标签（:123/126）；"逐层补齐 P/F/V/D/R"（:215）；首页新闻（:223/228/235/247；:51 待核） | 部分不符 | 清旧段 |
| 07_product_ecosystems.md（2026-09-06） | 八生态入口、主生态（:7）；P/F/V/D/R（:9）；hardware_domains/首页（:11）；按生态深度表（:15–23）；九主题（:35–41/57） | 完全是旧角度 | 归档；对象图谱段（:55–73）并入 03 |
| 08、09 | — | 符合 | 不动 |

## 8. 登记 framework/*.json

| 文件 | 旧角度（行） | 判定 | 处置建议 |
|---|---|---|---|
| bom.json 2.1、site_rights.json、part_fetch.json | layers S1–S5 与 part.layer 为尺度别名（:4 有说明） | 符合 | 不动 |
| tco_factors.json 1.2.0 | 标题"TCO 因子树"（:4）；"模型层变现（L3…）"（:218，待核） | 符合（命名） | 改标题为"经济模型因子树" |
| tco_targets.json（生成） | :5 "TCO 模型输入键"（来自 targets.py:241） | 符合 | 随 targets.py 改文案 |
| dashboard_rules.json | 八生态 + 第九行 + 生态的时间列（:4）；级别键 ecosystem（:35）；by_ecosystem（:38/42）；无 it 父行与链路段规则 | 部分不符 | 改词、键名 `system`，补 it 父行与链路段 |
| supply_contract.json 1.4 | "覆盖八个硬件生态"（:22）；coverage 七类既非骨架也非生态（:44–73）；provider.mapping 用 P/F/V/D/R + T（:112/126/141/158/175/192/208）；provider.layers 无别名说明（:113–209）；层标签（:131/347/296） | 部分不符 | coverage 与 mapping 改为系统/链路 + 变量类；layers → variable_classes |
| interface_manifest.json | index.html → node.html 为决定的别名；research.html 仍是旧工作台 | 符合 | 随页面清单改 |
| current_state.json | 见第 2 节六条；products-20260906 实现清单缺 bom.json/site_rights.json/bom.html/validate.py/test_bom.py（:120–145）；:467 "五层目标清单"；:625 "首页和团队页的唯一投影" | 部分不符 | 规则归属重登记 |
| research_graph.json 2.2.1（手写，无生成器） | views（:4–30）；scope:M01–M15 + 74 条 research_scope（:33–276）；space:*（:1556–1608）；六个 system:* 含"计算与存储系统""safety"（:1624–1705）；八个 ecosystem:* 旧名（:2461–2727）；99 对象带 ecosystem_id、无 system/chain；navigation_note（:4971–4972）；尺度树 P/V/R 三份（:4974–5218/5437–5657/5860–6088）；产品生态与技术话题组（:5671–5758/6170–6257）；hardware_domains 旧序旧名并把权利当部件（:6267–6416）；research_topics（:6709–6746）；hardware_note（:6747） | 完全是旧角度 | 重做为 3.0：由 bom.json + site_rights + 问题表生成，对象 = 根/系统/链路/部件/权利/主体，关系只有骨架关系；版本升级后通知 Spark 重同步 |
| research_questions.json 2.2.0（458） | 按 module_id；views P/F/V/D/R 775 处；topic_id 39 条；origin legacy-module 116；object_ids 有 scope:Mxx 130、space:*、system:safety、ecosystem:*；无 variable_class | 完全是旧角度 | 重打标：每条挂骨架节点 + 变量类；module 降为属性 |
| modules.json（2026-08-16） | "模块声明（L1）…工单 = 声明 − 现状"（:4）；旧生态名（:387） | 完全是旧角度 | 归档为兼容附录 |
| indicators.json（44）、metrics.json | 只按 module；头标 L4/L1 | 部分不符 | 加 variable_class 与系统/部件 |
| data_contract.json、storage_contract.json | — | 符合 | 不动 |

## 9. 后端 src/inresearch 与单元测试

| 文件 | 旧角度（行） | 判定 | 处置建议 |
|---|---|---|---|
| knowledge/dashboard.py | 骨架排序与 IT 父行正确（:174–268）；docstring "eight ecosystems"（:3）；eco_names/graph_name（:47/234）；输出键 ecosystems 与 node_id 'ecosystem:'（:171–173/234/267/317）；by_ecosystem（:196/198）；"ninth row"（:269）；打印（:340） | 部分不符 | 键名与 ID 改 system；去 graph_name |
| knowledge/targets.py、economics.py | "TCO model inputs"（targets :6/241）；layer 兼容键（:137/252） | 符合 | 改文案 |
| knowledge/validate.py | layer_ids / "layer 非法"（:162/176/187–190/217）；modules.json 问题校验（:307–322） | 符合（命名） | 改名 scale；模块校验随 modules 归档 |
| knowledge/navigation.py | 校验按视角的 navigation（:5–88）与 hardware_domains 主归属（:89–103） | 完全是旧角度 | 重写为骨架校验（图谱 3.0） |
| knowledge/registry.py | P/F/V/D/R 校验（:128/140–147）；任务按 module_id（:210–235/248）；hardware_domains node_id（:368–370） | 部分不符 | 随图谱 3.0 改 |
| knowledge/coverage.py、workflow/workorders.py | 模块盲区；"工单 = 模块声明 − 现状"（:2–23）；看板（:173） | 完全是旧角度 | 退役；差异由目标表状态承担 |
| knowledge/indicators.py | 注释按模块（:59/72/78/84） | 部分不符 | 随 indicators.json 改 |
| adapters/reader_model.py（module_id 枚举 :34–35/88）、workflow/reader.py（library/<module_id>/ :260–264）、reading_stages.py（:301–303）、deep_read.py（:64）、materials/triage.py（:124–138） | 阅读与整理按模块归档 | 部分不符 | 归档键改为骨架节点（需 Spark 配合：这是我们给它的新契约） |
| delivery/report.py（:75–121）、delivery/map.py（:2） | 按模块章节；世界地图 | 部分不符 | report 作兼容附录；map 退役 |
| interfaces/cli.py | 保留 map/coverage/workorders 命令（:32） | 符合 | 随退役删除 |
| 其余 src | 无领域词汇 | 符合 | 不动 |
| tests/unit/test_research_navigation.py | navigation.P 五组（:19）；HardwareEcosystemTests（:58/62）；system:power（:50–54） | 完全是旧角度 | 随图谱 3.0 重写 |
| test_dashboard.py | by_ecosystem（:48/51）；doc['ecosystems']（:61–77）；"电力生态"（:66） | 部分不符 | 随 dashboard.py 改 |
| test_bom.py | 域顺序只查域内（:76–80）；依赖 hardware_domains（:113–115） | 符合（缺口） | 补域顺序断言 |
| test_tco_targets.py、test_tco_factors.py、test_model.py | 类名与文案 | 符合 | 改名 |
| test_catalog_bridge.py（:21/29）、test_continuous_reader.py（:54）、test_catalog_migration.py（:69）、test_m4_triage_export.py（:100/147/205）、test_report_model.py（:26） | 按模块归档 | 部分不符 | 随阅读流水线改 |

## 10. 数据登记 data/*.json 与 web/assets

| 文件 | 分类词汇今天是什么 | 缺什么 | 判定 | 处置建议 |
|---|---|---|---|---|
| products.json（175） | segment 九类（算力芯片与核心器件 30、服务器与整机 20、存储介质与部件 20、存储系统与数据管理 21、网络与光互联 26、供配电 22、散热与液冷 19、机柜布线与物理设施 10、DCIM与运维配套 7）；bom_layer S1–S5；bom_parts；module | 无 system/chain；内存无自己的类（DRAM/HBM 在存储介质，RCD/CXL 在算力芯片）；DCIM 软件 bom_layer S3 与 bom.json dcim layer null 冲突；_note 停在 2026-08-18 | 部分不符 | 由 bom_parts 派生 system/chain 写回；segment 降为来源属性 |
| prices.json（512） | category 十值（capex、gpu-rental、power-price、benchmark、rent、market、efficiency、opex、token-price、lead-time）+ module；_note "价格库（L0）…种子示范" | 无 variable_class/部件/系统；market、benchmark 无归属 | 部分不符 | 每条加 variable_class（价格/运行/时间）与骨架节点；_note 改 |
| facts.json（7849） | metric_id → metrics.json（只有 module）；entity.type 八种；caliber.system 用"供配电""接地与防雷" | 无 variable_class/系统/部件；note 过期 | 部分不符 | metrics.json 加 variable_class 与系统，事实随之继承 |
| companies.json（248） | roles 16 值（hyperscaler、chip、ai-lab、colo、neocloud、construction、network、capital、electrical、cooling、utility、server-odm、sovereign、storage、facility、platform）；modules | 供应商角色用旧域词（cooling≠thermal、electrical≠power、chip/server-odm≠compute、platform≠control）；无 memory | 部分不符 | 角色分两轴：市场主体（第 5 类）与供应的系统/部件 |
| datacenter_model.json | 五类分组正确 | benchmark_series[].group 临时标签 | 符合（轻） | group 改五类 |
| dashboard.json（生成） | 五列与五系统正确 | 键 ecosystems、ID ecosystem:*、graph_name 旧名；formulas.cost "三选一"而 v3 有 BOT | 部分不符 | 改规则与生成器重生成 |
| research_knowledge.json | 文档/证据/陈述/回答（空） | 无骨架键 | 部分不符（低） | 记录键改骨架节点 + 问题 ID |
| sources.json、policies.json、contracts.json、projects.json、assignments.json | "L0" 标签 + M 码；contracts.type、projects.status L1–L9 | 无骨架/五类 | 部分不符 | 去 L0 标签；加骨架节点与变量类 |
| indicators.json（44） | 只按 module；"（L4）" | 无 variable_class/系统 | 部分不符 | 同 metrics |
| web/assets/levels.json | 尺度四级下钻 | — | 部分不符 | 退役 |
| brief.json（2026-08-18）、models/manifest.json | — | — | 历史 / 符合 | 不动 |

## 11. 现行文档 docs

| 文件 | 旧角度（行） | 判定 | 处置建议 |
|---|---|---|---|
| README.md | 研究工作台框架（:3）；五视角 + M01–M15（:18/43）；总览→研究→资料→任务→成果（:35）；"Attio / folk 两套视觉规则"已退役（:35）；research/ 模块（:48）；缺骨架/五类/三级账/node | 完全是旧角度 | 按提案重写 |
| AGENTS.md | "五视角、局部 MECE"（:7） | 部分不符（轻） | 改一句 |
| CLAUDE.md | — | 符合 | 不动 |
| DECISIONS.md | 头 "CURRENT · 2026-09-06"（:3）；同日条目无替代注：9 × 5（:39）、"归入八个生态"（:47）、"九列"（:53）、三个计算器不动（:31）、五层目标清单（:59）；"当前待办边界" D1–D8 过期（:518–525） | 部分不符 | 头日期；三处加"已被同日 X 条替代"；待办边界重写 |
| PROJECT_PANORAMA.md（登记入口 :707） | P/F/V/D/R + 15 模块（:5）；研究工作台分层对象目录（:11）；/api/research 对象/问题/候选/任务（:21） | 完全是旧角度 | 按提案重写 |
| DATA_SOURCING.md（2026-08-26，无横幅） | 按角度（模块）找数据（:1/18/20–33）；workorders 259 张（:4） | 完全是旧角度 | 归档，入口改指目标表 |
| LIBRARY_REPORT.md（2026-08-16） | 按 15 模块（:14/150/273–288/323–341/403–406）；bom.html:309 仍链 | 历史材料 | 加横幅或归档，去掉页面链接 |
| M4_TRIAGE_TASK.md（现行） | 归入研究模块（:22）；覆盖 M01–M15（:53）；category = M01–M15 + 四桶（:68–75） | 部分不符 | 分类轴改骨架（这是给 M4 整理的新要求） |
| guides/model-governance-2026-09-27（快照） | 五层（:5/51/55–58/152/212/257/275/301）；tco.html（:132/169）；economics.html（:178/186/217）；五层目标清单待建（:216）；TCO 页缺口表（:301） | 历史材料 | 快照不改；current_state 去掉"现行实现"身份，加"视图层已由账本替代"说明 |
| handoff/tco-model-fetch-teams.md（现行） | TCO 模型（:1）；"仍是草案…tco.html 已上线"（:7）；五层目标清单 43 行（:13/18/33/44）；已删模型（:25）；旧参考实现（:26）；tco.html 缺口表（:35/45） | 部分不符 | 重写为六队交接（目标表 287 行、账本、统一模型） |
| handoff/fetchdata-bootstrap.md（现行） | 五层目标清单（:3）；旧目标 ID `L3.*`（:35） | 部分不符 | ID 改 `F.*/P.*/S.*` |
| handoff/m4-deepread.md、nvidia-product-catalog.md | — | 符合 | 不动 |
| geluoke/专题写作规则.md | — | 符合 | 不动 |
| geluoke/专题反哺规则.md | cost.html 首次执行（:3/51/53）；四层利润分配（:11）；价格记录只有 category、module（:36）；ID 用模块前缀、object_ids 用 scope:Mxx（:37）；不要求打五类标签 | 部分不符 | 反哺目标改为骨架节点 + 变量类；ID 规则改 |
| reviews/2026-09-28/model/PROPOSAL.md | — | 符合 | 不动 |
| reviews/2026-09-28/bom-recut/PROPOSAL.md | 生态为根、八生态叶子、旧名列、八平铺还是五加四（:3/7/37–46/48） | 历史快照 | 标"已被五加四决定替代" |
| reviews/2026-09-28/dashboard/PROPOSAL.md（node.html:107 链） | 生态为根、八个生态、8 × 5、首页 = 根、三个计算器不动、1 → 8 → 69、ecosystem:x、8 + 1 行、研究工作台成为部件节点（:3/8/11/12/34/42/67/72–82/101/108/126/130） | 部分不符 | 标替代注；node.html 改链新提案 |
| reviews/2026-09-28/architecture/README.md 与 ARCHITECTURE.svg | 八生态 + 站点权利（README :5；SVG :16/71）；tco_factors 1.1（:83）；datacenter_tco_model（:84）；三视图（:90）；datacenter_economics_model（:91）；9 × 5（:102）；生态五列聚合（:103）；账本三个计算器展开（:115）；研究工作台（:117） | 部分不符（严重） | 重画 |
| docs/research/datacenter-tco、datacenter-economics、2026-09-14/datacenter-cost、2026-09-27/datacenter-profit 的 README（routes.json :115–119 公开） | 把 tco/economics/cost 页与已删 json/js 写成现行与权威边界（各 :5/:9–10） | 历史材料 | 加"已被账本取代"横幅；current_state 去掉三条坏实现 |
| local_reader/ACQUISITION_OPERATIONS.md（:3 五层目标清单；:26 首页同步）、local_setup/README.md（:7 研究工作台需要 API） | 范围外现行指南 | 部分不符 | 改词 |

## 12. 从对照清单看出来的三件事（给提案用）

1. **旧逻辑有三根主梁，不是零散词汇**：研究图谱（P/F/V/D/R + 尺度树 + 八生态 + 九主题）、模块 M01–M15（阅读归档、报告章节、工单、指标、事实、来源图）、以及"首页/看板/KPI"的展示习惯。三根梁各自牵着一组页面、一组登记、一组后端、一组测试。改写要按梁拆，不按文件拆。
2. **四段之间缺一条统一的键**：事实段（prices、facts、products、companies、indicators、research_knowledge）没有骨架节点与变量类字段，视图段（node.html）只能靠因子树间接连上。给每张登记表加两列——`node`（root / system:x / chain / part:x / site:x / actor:x）与 `variable_class`——是让"数据从哪来"能回答的前提。
3. **Spark 与 M4 现在是下游**：图谱 3.0 的对象 ID、问题表的节点键、M4 整理的分类轴、reader 归档路径，都由我们定义后交给他们，而不是我们迁就旧契约。
