# 当前研究与执行基准

> CURRENT · 基准版本 2026.09.27.23 · 2026-09-06 用户明确要求：更新性讨论要替代对应旧内容，确保代码、规范和记录一致。

## 从哪里读当前规则

| 主题 | 唯一现行规范源 | 机器实现或配套入口 |
|---|---|---|
| 研究架构 | [00 框架总览](00_overview.md) | research_graph.json、research_questions.json、research.html |
| 数据口径与核验 | [01 口径手册](01_data_standards.md) | data_contract.json；inresearch.knowledge.validate、inresearch.knowledge.verify、inresearch.knowledge.facts、inresearch.knowledge.registry |
| 知识与版本 | [02 知识格式](02_knowledge_format.md) | research_knowledge.json、兼容 Finding、inresearch.delivery.export |
| 3D 与产品映射 | [03 对象与协作](03_bom_and_collaboration.md) | 稳定部件 ID、产品线目录、空间/装配/系统关系 |
| M4 原件分类整理（独立 scope） | [M4 任务卡](../docs/M4_TRIAGE_TASK.md) | inventory / triage / organize；不扩大 Spark originals 操作权限 |
| 全文阅读与采用 | [04 阅读标准](04_reading_scoring_standard.md) | reader catalog 为当前全文结果权威；workflow.reading_results 为 reader/L2 共同查询入口 |
| 全站界面、字体与外观 | [05 界面规范](05_interface_system.md) | web/components/site-shell.js、web/themes、web/assets/fonts（infra 字体包）、interface_manifest.json |
| 产品生态与总览 | [07 产品生态规范](07_product_ecosystems.md) | 生态/技术入口、中心关系图、九主题、厂商索引及旧 ID 映射 |
| 采集与翻译 | [06 采集规范](06_acquisition.md) | supply_contract.json、workflow.supply、供应中心；既有 acquisition / inews / Spark 台账 |
| 模型执行与客户端 | [08 模型执行](08_model_execution.md) | inresearch.adapters.models、deploy/models.json |
| 软件职责与写入 | [09 软件契约](09_software_contracts.md) | 统一用例、结果投影、事务存储与 storage_contract 发布边界 |
| 运行与部署 | [Spark 操作手册](../docs/local_reader/SPARK_OPERATIONS.md) | deploy/spark-reader/；本地开发见 docs/local_setup/README.md |
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

`python3 manage.py governance --check` 检查在册路径/内容摘要、主题单一生效、替代链、规范引用、历史边界及已知失效表述。还检查 [规范验收映射](verification_contract.json) 的已审阅源文件/操作指南/测试内容摘要、13 条政策的适用 scope 和测试入口。修改规范、指南或所映射测试后，必须实际复审对应要求、实现及未覆盖项，再显式更新映射；`--refresh` 只更新文件清单，不能自动批准映射变化。映射列举选定要求并明确剩余缺口，不是所有自然语言条款的穷尽证明。它不能自动证明所有自然语言都没有语义冲突；任何规则变更仍须审阅关联实现和记录。新文件或修改后的在册内容没有刷新清单会使 CI 失败。

## 记录与运行边界

- 当前规范、兼容研究记录、资料候选、设计依据、历史审计和生成物分别标识；打开文档页会显示身份。
- 旧决策、旧全景和旧 reader 指令已移入 `docs/archive/2026-09-06/`。原路径保留当前说明或转向，避免旧链接继续发出操作指令。
- 在册清单覆盖 Git 源码与记录；不枚举百度网盘、Spark 原件、运行数据库、密钥或本机忽略文件。Spark 资料以内容身份和 SQLite 台账计量，网页候选以收到的快照计量，不能拿源码行数代替。
- 12 页架构 PDF 是已采用设计的交付快照；持续变更的执行规则以这里登记的现行文档为准。

主规范保留稳定文件名及最后更新日期；新讨论/评审/交付快照文件名以日期开头，必要时加时间。当前状态决定执行依据，日期不授予覆盖权。
