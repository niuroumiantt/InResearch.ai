# 当前研究与执行基准

> CURRENT · 基准版本 2026.10.11.97

本页只定位当前规则与更新边界。实施细节进入各主题唯一源，发布过程进入 [决策记录](../docs/DECISIONS.md) 或交接；此前长篇阶段记录保留于 [历史快照](../docs/archive/2026-10-10/framework__CURRENT__before_reassessment.md)，不能作为当前执行指令。

本次整改及验收边界见 [重新审查与整改](../docs/reviews/2026-10-10/architecture-reassessment/PLAN.md)。现行分类保持：五系统；IT 分计算、存储、网络，存储再分内存与持久存储。采集任务由稳定父目标与参数需求细化；R1/R2 的来源责任、审核用途和派工边界见 06，模型情景边界见 05；定向原件到参数任务书的SHA绑定与显式阅读入口见06。接收、阅读、采用、回答分别计量。动态对象/估算/最新有效时点原则见01；独立三种时间、原生区间、分期和历史修订由统一用例执行，旧估算保留。存量封存复用见04/06，规划、采用与真实上线分别验收。

2026-10-11：研究是否排队、插队或直接上线由用户决定；点名来源优先级贯通审核和新发表任务发现，单一队列所有者及验收标准保持。唯一入口见 [文章与日报研究接收](../docs/local_reader/EDITORIAL_DELIVERY.md)。

2026-10-11：首页按全球整体图景与每日变化重整。正式研究与 raw 来源资料并行可见；168条公开专题提取接入 raw 地图/台账投影，报道容量、国家级位置与正式 IT 合计分开，重点公司快捷入口和轻量首屏按05执行。规范及本地验证不证明已经部署或全球布局完整。

2026-10-11：首页发布实测补齐新闻持续可见性：完整快照/运行视图先构建再按精确物理身份安装，唯一既有publisher总预算覆盖导出与有界网络阶段；恢复、服务回执与候选边界按SPARK_OPERATIONS执行。

2026-10-11：逐条观测／陈述采用不等待全文阅读，原件、所选页上下文与对象绑定冻结并复验，任务通道另核当前需求；完整答案仍按现有验收。园区以明确地理和分角色主体表达，规划总量及投运量独立，信息时间与核实日期分开；水电为可选区间指标。规则和本地修改不等于已上线或171/17完成。

2026-10-11：地点三列独立筛选、未知留空，78条既有明确地点结构化；两组主体保留实际角色，容量/来源/披露收进上标备注。现行CI允许只追加既有站点v2观测运行研究及行业页面相关验收，改基线/旧观测/规则仍全套；本批代码规则更改按全套执行。

2026-10-11：园区信息入库与研究用途分离；来源与唯一园区明确即可逐条审核，研究目标可为空且不授予模型支持。存量和inews接收事件使用同一正式追加入口；缺项后补、冲突并列，首页按最近补充展示且保留实际信息时间。

2026-10-11：四队员工任务包提供岗位目标、首批来源/指标、原生原件+JSONL候选、首周节奏及离线验包。四个独立仓库已各完成一条真实采集和离线重放；研究接收/采用仍需联调；模型派工才需目标绑定，一般信息交付不需。任务包不能证明四队已接通，正式采用/上线另验。入口见[员工任务包](../docs/guides/fetchdata/README.md)。

## 从哪里读当前规则

2026-10-11：公司、产品、统计和报价接入唯一对象正式观测账本，来源优先、目标可空，冻结相关证据后具名审核追加。首页与公开分页API共用 `research_publication.json` 字段清单，研究采用与对外分发分开，不每批重复确认；未来付费会员权益与内部member角色分开。本批81条采用、7条待核、真实报价0的范围和验收见[操作指南](../docs/guides/OBJECT_OBSERVATIONS.md)，实际部署另核回执。

| 主题 | 唯一现行规范源 | 机器实现或配套入口 |
|---|---|---|
| 研究架构（一棵树、三级账、四问四段、五类变量、六队、一个模板） | [00 研究框架总览 v3](00_overview.md) | bom.json、site_rights.json、research_graph.json、research_questions.json、dashboard_rules.json、node.html |
| 数据口径与核验 | [01 口径手册](01_data_standards.md) | data_contract.json；inresearch.knowledge.validate、inresearch.knowledge.verify、inresearch.knowledge.facts、inresearch.knowledge.registry |
| 知识与版本 | [02 知识格式](02_knowledge_format.md) | research_knowledge.json、兼容 Finding、inresearch.delivery.export |
| 骨架、部件、站点权利与产品映射 | [03 对象与协作](03_bom_and_collaboration.md) | 稳定部件 ID、系统与链路、建设阶段、站点权利、产品线目录 |
| 统一经济模型、账本与 dashboard | [05 界面规范](05_interface_system.md)「统一经济模型与账本」「数据中心节点页」「目录」 | data/datacenter_model.json、knowledge/economics.py、ledger.html、dashboard_rules.json、data/dashboard.json |
| M4 原件分类整理（独立 scope） | [M4 任务卡](../docs/M4_TRIAGE_TASK.md) | inventory / triage / organize；不扩大 Spark originals 操作权限 |
| 全文阅读与采用 | [04 阅读标准](04_reading_scoring_standard.md) | reader catalog 为当前全文结果权威；workflow.reading_results 为 reader/L2 共同查询入口 |
| 技术插图、爆炸/平面/剖面图的画法与逐张迁移 | [10 白底技术图册](10_visual_atlas.md) | visual_atlas.json（14张参考/配方）、visual_atlas_migration.json（逐项队列）、[迁移计划](../docs/design/technical-atlas/MIGRATION_PLAN.md) |
| 全站界面、字体与外观 | [05 界面规范](05_interface_system.md) | web/components/site-shell.js、web/themes、web/assets/fonts（infra 字体包）、interface_manifest.json |
| 采集与翻译 | [06 采集规范](06_acquisition.md) | supply_contract.json（六队、六仓库、来源归属）、[五类变量目标清单](tco_targets.json)、workflow.supply、供应中心；inews 事件 feed 消费与 Fetchspec 接收台账；回执进 Git 载体只经 `manage.py deliveries import`（knowledge/deliveries.py）；inresearch 本身不爬取 |
| 模型执行与客户端 | [08 模型执行](08_model_execution.md) | inresearch.adapters.models、deploy/models.json |
| 软件职责与写入 | [09 软件契约](09_software_contracts.md) | 统一用例、结果投影、事务存储与 storage_contract 发布边界 |
| 运行与部署 | [Spark 操作手册](../docs/local_reader/SPARK_OPERATIONS.md) | deploy/spark-reader/；本地开发见 docs/local_setup/README.md |
| 文章写作与生产职责 | [研究接收与职责边界](../docs/local_reader/EDITORIAL_DELIVERY.md) | 创作、配图、制作、发布和生产端发送统一归 [inews.today](https://github.com/niuroumiantt/inews.today/blob/main/docs/editorial/README.md)；本仓保留历史稿与研究 UI 图册 |
| 文章与日报研究素材接收 | [研究接收协议](../docs/local_reader/EDITORIAL_DELIVERY.md) | editorial-sync、daily-receive；Spark 五分钟专栏接收；生产端 worker 实际切换先于旧脚本删除 |
| 按影响验收与 CI | [CI 规范](../docs/CI.md) | validate、browser (core) 两个稳定门禁，管理员同样受限 |
| 规则替代与在册管理 | 本页 | current_state.json、repository_manifest.json、inresearch.interfaces.governance |

规范源的主题、状态、适用范围、被替代版本及相关实现都登记在 [current_state.json](current_state.json)。[在册清单](../docs/REPOSITORY_REGISTER.md)列出 Git 管理的全部文件、身份、内容摘要和记录集合。外部材料是研究输入，不因出现在仓库内就成为规范。

## 哪一种“新”可以覆盖旧内容

- 用户已明确采用、适用范围相同的更新：新规则成为唯一现行版本；同步正式文档、实现、页面文案、测试和当前记录。
- 补充不同的范围、时间、配置或研究角度：建立适用范围和关系，可并列存在，不能覆盖本来不冲突的记录。
- 尚未采用的建议或外部材料：保持提案/候选身份，不能修改现行规则或授予操作权限。
- 同口径证据冲突：保留来源与版本，进入核验；依据采用结论选择当前版本并记录替代链。发布时间和来源等级不是自动覆盖条件。

较早材料与反证仍可能有研究价值。归档是退出当前执行入口，不是删除证据或让历史重新生效。

## 每次更新如何收口

查现行主题及引用 → 判定变更类型与范围 → 修改唯一源和适用实现 → 登记 supersedes / 原因 / 影响路径 → 归档旧执行正文 → 审阅并更新规范验收映射 → 更新清单 → 校验与测试 → 已授权的仓库合并和部署 → 核对实际运行版本。

`python3 manage.py governance --check` 检查在册路径/内容摘要、主题单一生效、替代链、规范引用、历史边界及已知失效表述。还检查 [规范验收映射](verification_contract.json) 的已审阅源文件/操作指南/测试内容摘要、17 条政策的适用 scope 和测试入口。修改规范、指南或所映射测试后，必须实际复审对应要求、实现及未覆盖项，再显式更新映射；`--refresh` 只更新文件清单，不能自动批准映射变化。映射列举选定要求并明确剩余缺口，不是所有自然语言条款的穷尽证明。它不能自动证明所有自然语言都没有语义冲突；任何规则变更仍须审阅关联实现和记录。新文件或修改后的在册内容没有刷新清单会使 CI 失败。

## 记录与运行边界

- 当前规范、兼容研究记录、资料候选、设计依据、历史审计和生成物分别标识；打开文档页会显示身份。
- 旧决策、旧全景和旧 reader 指令已移入 `docs/archive/2026-09-06/`。原路径保留当前说明或转向，避免旧链接继续发出操作指令。
- 在册清单覆盖 Git 源码与记录；不枚举百度网盘、Spark 原件、运行数据库、密钥或本机忽略文件。Spark 资料以内容身份和 SQLite 台账计量，网页候选以收到的快照计量，不能拿源码行数代替。
- 目录七项与四问的对应（行业总览为独立市场入口）、"一个模板"只指节点页、主体 / stage / 对象三条判据见 05「目录」与 03「三条判据」（2026-09-29）；兼容层退役日历在 `current_state.json` 的 `compat_retirements`，`governance --check` 过期即报错。
- 12 页架构 PDF 与 5 页数据中心经济模型指导（`docs/guides/model-governance-2026-09-27`，三级四段五类六队，快照原文仍写"五层"）是已采用设计的交付快照；持续变更的执行规则以这里登记的现行文档为准。2026-09-28 起"五层"改称"五类变量"（见 06 采集规范），快照本身不改。

主规范保留稳定文件名及最后更新日期；新讨论/评审/交付快照文件名以日期开头，必要时加时间。当前状态决定执行依据，日期不授予覆盖权。
