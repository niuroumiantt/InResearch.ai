# 当前研究与执行基准

> CURRENT · 基准版本 2026.10.06.5 · 2026-09-06 用户明确要求：更新性讨论要替代对应旧内容，确保代码、规范和记录一致。

## 从哪里读当前规则

| 主题 | 唯一现行规范源 | 机器实现或配套入口 |
|---|---|---|
| 研究架构（一棵树、三级账、四问四段、五类变量、六队、一个模板） | [00 研究框架总览 v3](00_overview.md) | bom.json、site_rights.json、research_graph.json、research_questions.json、dashboard_rules.json、node.html |
| 数据口径与核验 | [01 口径手册](01_data_standards.md) | data_contract.json；inresearch.knowledge.validate、inresearch.knowledge.verify、inresearch.knowledge.facts、inresearch.knowledge.registry |
| 知识与版本 | [02 知识格式](02_knowledge_format.md) | research_knowledge.json、兼容 Finding、inresearch.delivery.export |
| 骨架、部件、站点权利与产品映射 | [03 对象与协作](03_bom_and_collaboration.md) | 稳定部件 ID、系统与链路、建设阶段、站点权利、产品线目录 |
| 统一经济模型、账本与 dashboard | [05 界面规范](05_interface_system.md)「统一经济模型与账本」「数据中心节点页」「目录」 | data/datacenter_model.json、knowledge/economics.py、ledger.html、dashboard_rules.json、data/dashboard.json |
| M4 原件分类整理（独立 scope） | [M4 任务卡](../docs/M4_TRIAGE_TASK.md) | inventory / triage / organize；不扩大 Spark originals 操作权限 |
| 全文阅读与采用 | [04 阅读标准](04_reading_scoring_standard.md) | reader catalog 为当前全文结果权威；workflow.reading_results 为 reader/L2 共同查询入口 |
| 全站界面、字体与外观 | [05 界面规范](05_interface_system.md) | web/components/site-shell.js、web/themes、web/assets/fonts（infra 字体包）、interface_manifest.json |
| 采集与翻译 | [06 采集规范](06_acquisition.md) | supply_contract.json（六队、三仓库、来源归属）、[五类变量目标清单](tco_targets.json)、workflow.supply、供应中心；inews 事件 feed 消费与 Fetchspec 接收台账；回执进 Git 载体只经 `manage.py deliveries import`（knowledge/deliveries.py）；inresearch 本身不爬取 |
| 模型执行与客户端 | [08 模型执行](08_model_execution.md) | inresearch.adapters.models、deploy/models.json |
| 软件职责与写入 | [09 软件契约](09_software_contracts.md) | 统一用例、结果投影、事务存储与 storage_contract 发布边界 |
| 运行与部署 | [Spark 操作手册](../docs/local_reader/SPARK_OPERATIONS.md) | deploy/spark-reader/；本地开发见 docs/local_setup/README.md |
| 格洛可专题长文 | [专题写作规则 v2.2](../docs/geluoke/专题写作规则.md) | 精简专题、图文交付、手机排版；本机交付路径见长文交接 |
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

`python3 manage.py governance --check` 检查在册路径/内容摘要、主题单一生效、替代链、规范引用、历史边界及已知失效表述。还检查 [规范验收映射](verification_contract.json) 的已审阅源文件/操作指南/测试内容摘要、14 条政策的适用 scope 和测试入口。修改规范、指南或所映射测试后，必须实际复审对应要求、实现及未覆盖项，再显式更新映射；`--refresh` 只更新文件清单，不能自动批准映射变化。映射列举选定要求并明确剩余缺口，不是所有自然语言条款的穷尽证明。它不能自动证明所有自然语言都没有语义冲突；任何规则变更仍须审阅关联实现和记录。新文件或修改后的在册内容没有刷新清单会使 CI 失败。

## 记录与运行边界

- 当前规范、兼容研究记录、资料候选、设计依据、历史审计和生成物分别标识；打开文档页会显示身份。
- 旧决策、旧全景和旧 reader 指令已移入 `docs/archive/2026-09-06/`。原路径保留当前说明或转向，避免旧链接继续发出操作指令。
- 在册清单覆盖 Git 源码与记录；不枚举百度网盘、Spark 原件、运行数据库、密钥或本机忽略文件。Spark 资料以内容身份和 SQLite 台账计量，网页候选以收到的快照计量，不能拿源码行数代替。
- 目录七项与四问的对应（行业总览为独立市场入口）、"一个模板"只指节点页、主体 / stage / 对象三条判据见 05「目录」与 03「三条判据」（2026-09-29）；兼容层退役日历在 `current_state.json` 的 `compat_retirements`，`governance --check` 过期即报错。
- 12 页架构 PDF 与 5 页数据中心经济模型指导（`docs/guides/model-governance-2026-09-27`，三级四段五类六队，快照原文仍写"五层"）是已采用设计的交付快照；持续变更的执行规则以这里登记的现行文档为准。2026-09-28 起"五层"改称"五类变量"（见 06 采集规范），快照本身不改。

主规范保留稳定文件名及最后更新日期；新讨论/评审/交付快照文件名以日期开头，必要时加时间。当前状态决定执行依据，日期不授予覆盖权。

2026-10-02：用户采用行业总览独立首页；市场、地图、主体与项目下钻见 05，持久新闻项目线索见 06。此前首页退役决定在此范围被替代，节点研究保留。

2026-10-02 二次修订：首页图与大数字、明细点击进入；机构全球估算与地图样本分别标识；低置信度新闻随同步进入建设机会、自动关联与阶段观察见 06。

2026-10-02 三次修订：规格库接入 Intel、AMD、Supermicro、SK hynix；按公司来源校验与分库、动态导航、未知分类和首次交付状态见 06。

2026-10-03：第二批计算目录按官方原表补型号，模组与板卡拆分、芯片对应关系和保留生产基线的补充交付见 03/05/06。生产验收与缺口见 `docs/handoff/compute-catalog-batch2-20261002.md`。

2026-10-03 二次修订：替代首页旧排版，全球规模后直接放完整地图与右侧精选新闻；筛选、主体与样本移至地图下方，首页两类机会区块移除、其他页面与采集保留。验收口径见 05，本轮仅本地验收与 PR，不部署。

2026-10-03 三次修订：各仓库架构集中到研究站 `/admin/<简称>repo.html`，由真实管理员会话保护；来源版本、观察日期与实时统计边界见 05，维护见 `docs/local_setup/REPOSITORY_PAGES.md`。本轮实现与本地验证不代表生产已发布。

2026-10-06：需求驱动的新闻与用户报告匹配，容量观察、园区候选、水电审批与完整历史计数，及内部报告页码索引/需求队列/待讨论角度见 06；既有页面的进展入口见 05。骨架与正式数据不由匹配改写。

2026-10-06 二次修订：Spark 新阅读以节点分类并冻结现行需求、五类变量、六队与模型输入；匹配缺口安排优先全文阅读，旧配方/链接/停放保留，见 04。

2026-10-06 三次修订：停止中英文独立长文，只交付公众号日报与研究详情 HTML。需求快照、来源/证据、逐事件字段和 SHA 清单随日报进入 Spark；来源配对、侧车核验和网页处理状态见 06，正式项目/GW 仍须口径与 C3。

2026-10-06 四次修订：日报按事件分流交付，来源明确的项目元数据先上项目线索页，补证/身份/容量与长报告分开；Reader 保留短日报与收尾服务份额，旧积压每四次一槽；不改深读或 C3 门槛。见 04/05/06。

2026-10-06 五次修订：点名整批通过 Codex CLI 暂时推理、Spark 保持单一队列和存储；未完成配方显式新版本、范围隔离、额度/连接等待和网页实际阅读计数，见 04/05/08 与 Spark 操作手册。完成结果与正式采用边界不变。

2026-10-06 六次修订：Codex 调用失败区分网络/额度等待并记录脱敏诊断；显式视觉补读角色、高分辨率逐页核验与 OCR 检查点让槽见 04/08。定向重试保留历史备份，未核验页仍阻塞。
