# 当前研究与执行基准

> CURRENT · 基准版本 2026.10.14.132

2026-10-14：fetchfilings新增Microsoft官方FY2025年报的精确来源白名单，与fetchstat分别锁定目录、来源身份和ACK；候选不入Reader、不采用、不填参。38项合同/恢复测试通过；用户已明确授权源码版本包和公开年报包传往既有AWS/Spark；真实生产ACK待部署后验证，connection仍为not_connected。

2026-10-14：fetchstat已用真实EIA原件完成AWS采集、Spark永久候选接收、受控截断拒绝/完整重试和同包零增量重放；旧ID/版本/原信封及首次接收保留，采用/Reader入队/填参0。接通范围仅EIA单源受控文件交付，调度未启用，其他三队仍未接通。

2026-10-14：用户授权只推进fetchstat生产接通：AWS取得已登记公开来源，Spark既有候选归档；不可变到达日志、来源白名单、核验后ACK、重复无写与失败恢复。其他队不启用，不自动采用/填参，不安装调度；实际生产接收回执另验。

2026-10-14：用户授权本地实施一个fetchdata仓库、四个独立采集模块，替代四仓库分别维护公共内核；对象／来源／证据统一信封，供应方ID、旧提交与交付历史保留。显式本地沙箱接收与生产接通分开；本轮不推送、不部署、不安装调度，不自动采用或填参。

2026-10-14：用户现已授权本轮发布，替代此前阶段“暂不上线”的执行限制。研究框架v4以通用模型为主体，真实园区检验适用，Abilene仅贯通校验；保留成本／收入／回报三账，问题模板、检索、覆盖与来源执行分责。架构页、任务页、目录解释与候选复核／参数预览同步。旧ID、链接及正式事实保持；候选、假设、未知、未读与异常不自动采用。实际完整CI、受保护合并、网站／运行架构投影／Spark回执见本阶段交接。

2026-10-14：Abilene SEC四表及四辅助表本地补读：原图/人工转录分开绑定，同版财报不多计独立证据。年度借款/股本/现金余额能局部对应，混合应收与装修代垫不能唯一拆出租金实收；合同/会计/现金期间分开。三处1美元源差及物业费用范围差保留，四条旧未读状态被内容候选替代、余图/租约仍未知；原三异常及经济输入不变，暂不上线。

2026-10-14：Abilene收入与回报本地复核：按项目公司/开发关联方/JV股东/Oracle/OpenAI/Lancium分账及期间；首两栋15年/周年3%与首年单价年化244728000美元仅候选，不套当前四栋421MW。gross转付、资本化/支付和累计股本分别保留；原租约/表图、算力合同/IT归属及实际回报未知，候选不自动填参，三异常不关闭。规范05与脱敏回执见交接；暂不上线。

2026-10-14：Abilene资本成本本地复核：当前页15948322000美元=421MW×1000×CSV分项系数37882，显示159亿美元；原生容量/缓存、概括系数、分项/总计取整分开保留。通用IT/设施/土地/公用工程拆分为候选；合资/贷款/局部申报/租约不混为实支，实际采购/结算/分期未知，三异常不自动填参。规范05、回执见交接；暂不上线。

2026-10-14：Abilene第三步本地年度用电核对：容量时间、IT电力负载、期间PUE和合同电价分别登记；新增设计／投运／供电关系候选，不把设计或公司电量当现场实测。EIA平均零售代理价不再叠加Oncor需量费，计算0标研究口径；9单项／27联合与容量时间对照可复算，原三异常和未知保留。原件与SEC工具转录身份分开；规范05、阶段回执见交接，暂不上线。

2026-10-14：Abilene前两步本地完成：替代“独立原容量”表述，登记GPU／421MW／算力／成本共用依赖及跨版本限制；十项设计／申请／图纸原件内容核对可人工复核，未确认现场或模型用途。83输入细化标签，三异常、候选、未知、余页与旧版本保留；官方申请镜像同SHA不多计证据。规范05，阶段回执见docs/handoff/abilene-model-preview.md；暂不上线。

2026-10-14：恢复Abilene本地模型参数预览：固定421MW原容量估算，确认后生成年度用电情景；候选、假设、未知、三异常及五条推导独立保留。现场未知不晋级、异常不自动填参；规范见05，结果与复算见docs/handoff/abilene-model-preview.md。未推送／合并／上线。

2026-10-13：用户要求不拘数字重审架构；00／03替代数字总纲、五类正交独占及四问倒序。问题模板与来源队研究侧交付要求已登记，可扩展覆盖检查与局部互斥分开；旧界面代码只兼容，未上线。Abilene两PDF完整取得并核相关页，三异常保留复核与推导关系，模型预览待结果交付后继续。

2026-10-13：新增十二角度58项跨通用／园区的离线观察清单及报告去向审计，复用问题、字段与六队；Abilene候选、未知、异常及未读附件保留，零新采用、零模型验证、暂不上线。现行执行见03／06；3／4／5／6不替换。

2026-10-14：普通类型对象支持保留原件、值、身份及信息时钟的追加技术归类更正；姓名边界不明可显式隔离／恢复，原历史保留，正式研究不可被普通隔离隐藏。现行入口01；代码部署、真实更正与展示另验。

2026-10-13：初筛年份生成schema采用模型服务可编译的普通分支与锚点，移除不受支持的前瞻；本地对锚定pattern执行完整字符串匹配，仍拒绝年份区间、完整日期与尾换行。原出版年语义、ID、原件、次数、成功缓存和C3边界不变。

2026-10-13：初筛classification.year仅指原文明确披露的单一年份；未知留unknown，资料涉及的年份区间进入后续陈述，不猜出版年。生成schema与提示词对齐原单年校验，Codex本地结构校验执行pattern；原ID、原件、次数、成功缓存和候选/C3边界保持。


2026-10-13：候选manifest响应支持有界gzip及原未压缩兼容；清单小请求可显式选择同一receiver的可信HTTPS读取入口，delta保持原写入入口和generated CAS。传输/解压上限、原重试预算、认证不变。CDN拒绝gzip POST与origin慢链路须分别核实，唯一publisher完成真实增量与网站ACK后才计验收。唯一运行入口为SPARK_OPERATIONS。

2026-10-13：补齐CLI进程超时的有界stdout终止事件及stderr首尾诊断，认证与未知超时保留安全计量；relay凭据轮换先排空原服务，再核旧拒绝/新认证及自然工作。候选增量按真实manifest、逐批ACK、保留旧候选与网站HTTPS投影验收，维护不恢复暂停汇报。唯一操作入口为SPARK_OPERATIONS；源码与生产回执分别计量。

2026-10-13：失败初筛的model_output_invalid可经具名、原件/配方/次数CAS重新执行一次；原结果校验保持，成功缓存拒绝覆盖，read/synthesize输出错误不扩大准入。现行入口见SPARK_OPERATIONS；代码部署与实际恢复分别验收。

2026-10-13：用户接受并授权全球园区独立一级（园区名录、地区分析），交付现为七一级／十五二级；详情七模块、后台六／二十保持并补齐对象关联。此条替代下述六／十四目录数量及全球项目旧归属；来源与统计边界按05，进展见docs/handoff/global-campuses.md。

2026-10-13：用户接受并授权分阶段实施交付六个一级／十四个二级、后台六个一级／二十个二级，以及匿名／客户只读／IT页眉页脚。旧七项混合导航与账户菜单后台业务入口由05现行目录替代；site_navigation.json为唯一机器导航登记，接口菜单、聚合页、辅助页及搜索按实际角色服务端授权。普通信息登记与研究审核、本地情景与正式模型保持分离。接受规则、源码、测试与实际部署分别登记，进度见[目录与登录外壳交接](../docs/handoff/navigation-auth-shell.md)。



2026-10-13：候选全量超限转原认证端点的有界文档增量、SHA清单、CAS和逐批回执；模型网络超时分类及triage/read/synthesize保留原件/次数/成功缓存的在线重试见SPARK_OPERATIONS。实际接收与代码部署分别验收。

本页只定位当前规则与更新边界。实施细节进入各主题唯一源，发布过程进入 [决策记录](../docs/DECISIONS.md) 或交接；此前长篇阶段记录保留于 [历史快照](../docs/archive/2026-10-10/framework__CURRENT__before_reassessment.md)，不能作为当前执行指令。

本次整改及验收边界见 [重新审查与整改](../docs/reviews/2026-10-10/architecture-reassessment/PLAN.md)。现行分类保持：五系统；IT 分计算、存储、网络，存储再分内存与持久存储。采集任务由稳定父目标与参数需求细化；R1/R2 的来源责任、审核用途和派工边界见 06，模型情景边界见 05；定向原件到参数任务书的SHA绑定与显式阅读入口见06。接收、阅读、采用、回答分别计量。动态对象/估算/最新有效时点原则见01；独立三种时间、原生区间、分期和历史修订由统一用例执行，旧估算保留。存量封存复用见04/06，规划、采用与真实上线分别验收。

2026-10-11：研究是否排队、插队或直接上线由用户决定；点名来源优先级贯通审核和新发表任务发现，单一队列所有者及验收标准保持。唯一入口见 [文章与日报研究接收](../docs/local_reader/EDITORIAL_DELIVERY.md)。

2026-10-11：首页按最新明确指令收束为规模带、单行研究/项目更新播报、原有浅色设计的世界地图与等高新闻标题栏，地图底部放主体高亮；其余首页卡片、资料统计、样本筛选和玩家区块退出，详情与其他行业页保留。更新显示真实正式补充时点，不把旧信息当今日事件；新闻标题进入inews故事或搜索，原文链接保留。正式研究/raw口径、地理粒度与轻量首屏按05执行。放大地图按需加载精细矢量轮廓，按当前视野补充州/省界分块，原浅色设计与项目锚点保持。此版替代同日旧首页范围；规范及本地验证不证明部署或全球布局完整。

2026-10-11：首页发布实测补齐新闻持续可见性：完整快照/运行视图先构建再按精确物理身份安装，唯一既有publisher总预算覆盖导出与有界网络阶段；恢复、服务回执与候选边界按SPARK_OPERATIONS执行。

2026-10-11：逐条观测／陈述采用不等待全文阅读，原件、所选页上下文与对象绑定冻结并复验，任务通道另核当前需求；完整答案仍按现有验收。园区以明确地理和分角色主体表达，规划总量及投运量独立，信息时间与核实日期分开；水电为可选区间指标。规则和本地修改不等于已上线或171/17完成。

2026-10-11：地点三列独立筛选、未知留空，78条既有明确地点结构化；两组主体保留实际角色，容量/来源/披露收进上标备注。现行CI允许只追加既有站点v2观测运行研究及行业页面相关验收，改基线/旧观测/规则仍全套；本批代码规则更改按全套执行。

2026-10-11：园区信息入库与研究用途分离；来源与唯一园区明确即可逐条审核，研究目标可为空且不授予模型支持。存量和inews接收事件使用同一正式追加入口；缺项后补、冲突并列，首页按最近补充展示且保留实际信息时间。

2026-10-11：四队员工任务包提供岗位目标、首批来源/指标、原生原件+JSONL候选、首周节奏及离线验包。四个独立仓库已各完成一条真实采集和离线重放；研究接收/采用仍需联调；模型派工才需目标绑定，一般信息交付不需。任务包不能证明四队已接通，正式采用/上线另验。入口见[员工任务包](../docs/guides/fetchdata/README.md)。

2026-10-11：对象观测纯追加可经完整JSON证明运行research+industry与对象/Fetchspec来源采用回归，修改既有记录/身份/修订仍full；Docker大型资产层独立缓存。新srcdoc定位冻结原始HTML与相关上下文，不执行脚本、不等待整篇。首次代码规则变更全套验收，规范与源码不是生产回执。

2026-10-12：原生XLSX固定字段和局部表格上下文进入同一对象审核入口，不先转JSON冒充原件；保留表头/脚注、估算与原始单位，公式不执行，未知来源/唯一对象仍保留线索。能力实现与存量实际采用分开验收，入口见对象观测操作指南。

2026-10-12：真实归档导入台账可作为对象逐条观测来源，不强制网页URL；路径摘要与首次接收冻结复验，公开字段资格另审，首页展示允许公开的无链接观测。原生表格优先局部提取，支持范围与实际采用另验；首次园区登记与CI追加边界见01和CI规范，源码实现与生产采用另验。

2026-10-12：首次物理园区可通过具名来源审核登记并追加首条观测，不先绑定研究目标；缺失地址、坐标与容量留空。重复身份和历史注入仍拒绝；本次代码规则走全套，后续严格纯追加可运行研究相关CI。实际园区采用和上线数量以生产回执为准。

2026-10-12：用户明确取消普通信息前置事实核验；园区source-statements按唯一主体追加v3来源登记，已知数字先展示、缺项后补，标记基础登记待查。当前字段按有效／披露／首次接收／登记时间选择并明示依据，同时间较后登记展示、冲突和历史保留；研究结论和模型支持不自动晋级。入口与旧规则替代范围见01。实际登记与上线另核回执。

2026-10-12：原生归档工程表首次登记不猜建设阶段，未披露status=null；URL未知及未核实日期保持null。明确同名项目的多原件共用ID。v3普通来源纯追加经完整JSON证明可走research+industry，代码/规范/旧值变化仍full。实际存量登记与公网回执另核。

2026-10-12: Public pages are homepage and tasks (user correction supersedes homepage-only). Other pages keep authenticated roles. Public task metadata and explicitly public, SHA-verified example artifacts support a real operating-site walkthrough; coordination details remain private. Source reception, registration, publication and actual map visibility require separate receipts. Reported coordinates retain provenance and precision; unknown IT MW does not add known GW. Rules: 01/05/06/09.

## 从哪里读当前规则

2026-10-11：公司、产品、统计和报价接入唯一对象正式观测账本，来源优先、目标可空，冻结相关证据后具名审核追加。首页与公开分页API共用 `research_publication.json` 字段清单，研究采用与对外分发分开，不每批重复确认；未来付费会员权益与内部member角色分开。本批81条采用、7条待核、真实报价0的范围和验收见[操作指南](../docs/guides/OBJECT_OBSERVATIONS.md)，实际部署另核回执。

| 主题 | 唯一现行规范源 | 机器实现或配套入口 |
|---|---|---|
| 研究架构（对象与证据；通用模型与真实园区） | [00 研究框架 v4](00_overview.md) | bom.json、site_rights.json、research_graph.json、research_questions.json、dashboard_rules.json、node.html |
| 数据口径与核验 | [01 口径手册](01_data_standards.md) | data_contract.json；inresearch.knowledge.validate、inresearch.knowledge.verify、inresearch.knowledge.facts、inresearch.knowledge.registry |
| 知识与版本 | [02 知识格式](02_knowledge_format.md) | research_knowledge.json、兼容 Finding、inresearch.delivery.export |
| 骨架、部件、站点权利与产品映射 | [03 对象与协作](03_bom_and_collaboration.md) | 稳定部件 ID、系统与链路、建设阶段、站点权利、产品线目录 |
| 统一经济模型、账本与 dashboard | [05 界面规范](05_interface_system.md)「统一经济模型与账本」「数据中心节点页」「目录」 | data/datacenter_model.json、knowledge/economics.py、ledger.html、dashboard_rules.json、data/dashboard.json |
| M4 原件分类整理（独立 scope） | [M4 任务卡](../docs/M4_TRIAGE_TASK.md) | inventory / triage / organize；不扩大 Spark originals 操作权限 |
| 全文阅读与采用 | [04 阅读标准](04_reading_scoring_standard.md) | reader catalog 为当前全文结果权威；workflow.reading_results 为 reader/L2 共同查询入口 |
| 技术插图、爆炸/平面/剖面图的画法与逐张迁移 | [10 白底技术图册](10_visual_atlas.md) | visual_atlas.json（14张参考/配方）、visual_atlas_migration.json（逐项队列）、[迁移计划](../docs/design/technical-atlas/MIGRATION_PLAN.md) |
| 全站目录、身份、页眉页脚、字体与外观 | [05 界面规范](05_interface_system.md) | site_navigation.json（机器导航／页面归属）、web/components/site-shell.js、web/themes、web/assets/fonts、interface_manifest.json（界面／资源验收） |
| 采集与翻译 | [06 采集规范](06_acquisition.md) | supply_contract.json（来源分工、fetchdata四独立模块及本地阶段状态）、[五类变量目标清单](tco_targets.json)、workflow.supply、供应中心；inews 事件 feed 消费与 Fetchspec 接收台账；回执进 Git 载体只经 `manage.py deliveries import`（knowledge/deliveries.py）；inresearch 本身不爬取 |
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
- 交付七个一级、后台六个一级及其二级、页面归属和身份边界见05「目录」与site_navigation.json；“一个模板”只指节点页，主体／stage／对象三条判据见03「三条判据」；兼容层退役日历在 `current_state.json` 的 `compat_retirements`，`governance --check` 过期即报错。
- 12 页架构 PDF 与 5 页数据中心经济模型指导（`docs/guides/model-governance-2026-09-27`，三级四段五类六队，快照原文仍写"五层"）是已采用设计的交付快照；持续变更的执行规则以这里登记的现行文档为准。2026-09-28 起"五层"改称"五类变量"（见 06 采集规范），快照本身不改。

主规范保留稳定文件名及最后更新日期；新讨论/评审/交付快照文件名以日期开头，必要时加时间。当前状态决定执行依据，日期不授予覆盖权。

2026-10-12：CI重型图册/封装拆为独立矩阵作业，场景、来源审核与门禁不减；历史样例改从园区档案验收，不依赖有限首页更新窗口。现行入口见CI规范。

2026-10-12: Ordinary source registration now includes company/product/statistic/quote. source-publish separates persistent data additions from Git code deployment; no per-batch PR/full CI. Stable identity, structure, history and public field boundaries remain. Code capability, installed data and actual public visibility are measured separately. Archived sources without a webpage URL must remain visible in details and homepage updates.

2026-10-12: Data export never resubmits reviewed legacy site baselines. Company pages display their source timeline; ordinary derived public fields are explicitly registered.

2026-10-13：地图和任务进度共享按源码、运行登记文件版本及日期失效的有界内存投影，同版本并发只计算一次；失败和计算中数据变化不缓存。权限、字段投影与容量口径保持，部署与公网回执分别验收。
