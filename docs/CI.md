# CI 按影响范围验收

现行源：本文件。2026-10-10 替代每个 PR 与 main push 无条件执行完整浏览器及存储回归的配置。完整测试的场景、断言、密度和单项期限不缩减；只改变本次需要运行的范围。

## 分流

`scripts/ci_scope.py` 对精确 base/head Git 树的完整差异分类，不使用有文件数截断的 PR 文件列表。PR 使用事件 base 与 GitHub 合并测试提交，main push 使用 before/after；比较失败、缺失基线、空差异、删除、改名、符号链接或未知路径均跑全套。

| 改动 | 验收 |
|---|---|
| 非规范 Markdown、普通资料图片 | 内容 UTF-8、位图实际解码/全部帧、SVG 结构、新增本地 Markdown 引用、治理清单、严格数据校验与 registry；不启动浏览器及存储容器 |
| 已映射页面仅可见文字变化 | 上述基础检查、资产契约与对应现有浏览器测试；标签、属性、脚本、样式、template 或注释变化不算纯文案 |
| technical-atlas 图像 | 基础与资产契约、technical_atlas 真实渲染和下载测试 |
| models/textures 目录内图像 | 基础与资产契约、model_assets 三个既有消费场景 |
| 普通 web 图像 | 可直接定位到已映射页面时运行对应测试；共享 JS/CSS/JSON 或无法映射的消费者跑全套；无法确立消费者时也跑全套 |
| `data/research_knowledge.json` 仅追加有界研究资料 | 基础检查、固定研究/来源/审核/发布链路/HTTP 单元回归，单个 `browser (research)` 作业内执行既有 research_delivery 与 research_summary；不跑视觉资产、3D、装配、园区及存储容器 |
| 程序、页面结构、权限、schema、非追加研究数据、依赖、测试、CI、现行规则及未知改动 | 原完整单元回归、17 个浏览器分片、资产契约、verify、indicators 和 storage-container |

混合提交取所有影响的并集，任一全套条件覆盖轻量条件。规则入口和登记的操作指南不当成普通文案。派生清单仍须经治理检查验证；current_state 仅版本/日期变化、verification_contract 仅版本/审阅时间与本次实际修改文件的既有摘要变化可以随内容提交走轻量路线，规则和验收要求语义变化必须全套。图片是否很小不作为免检依据；资产登记或其它规范一起变化时按其实际范围处理。

手动运行 workflow_dispatch 与每日北京时间 02:17 的 schedule 总是全套。main push 也按实际差异分流；完整代码变更合并后的发布基线仍完整回归。同一 PR 推入新提交会取消过期运行；main/schedule 不主动取消在运行的发布验收。浏览器依赖与 Chromium、CI 图像解码依赖使用固定版本及缓存。

## 研究资料追加的边界

只对已存在的 `data/research_knowledge.json` v2.0.0 分类，比较完整 base/head JSON：仅 documents/evidence/statements 数组末尾可增加记录，所有旧记录的顺序、值与 JSON 类型不变，至少新增一条且各集合 ID 唯一。version、note、answers 和顶层结构不变；新增 statement 必须 partial_support_only=true，不携带正式 question_id、替代记录、放宽审核分布、对象映射替代或撤回状态。重复 JSON 键、非有限数字、未知结构、修改/删除/重排旧记录、正式答案或版本/规则变化均回到 full。不能仅凭文件名、行数、PR 标题或发布器声称追加而跳过测试。

research 路线共四个执行作业：scope、validate、browser (research)、browser (core)。validate 保留治理、严格数据、registry 全量引用校验，并执行固定的 test_research*.py、test_public_reader.py、test_publish_reader.py、test_verification_contract.py、test_ci_scope.py；选定入口缺失或空测试集报错。browser (research) 串行执行原有研究成果页与研究摘要/节点资料测试，不展开 core_a/core_b/core_c 或任何 3D、装配、园区矩阵，纯研究追加也不运行 asset-check 和 storage-container。资料真实来源、C3 与原件核验仍由既有审核/发布链路完成，CI 分流本身不授予采用或上线资格。

混合提交取并集：追加研究资料同时改普通文案/图片仍保留其检查；同时改已映射页面或资产则加跑对应浏览器与资产契约；任一代码、规则或未知影响仍覆盖为 full。新增正式答案、既有事实更正/替代不属于此范围。

## 必过门禁

GitHub main 必过检查为 `validate` 与 `browser (core)`，均绑定 GitHub Actions（app_id 15368），管理员也受保护，无新增人工审批。保留现有名称兼容已经打开的 PR；`browser (core)` 现为 CI 影响汇总门禁，并不代表普通文案必须启动浏览器。

`validate` 始终执行基础及本次范围内的源码检查。汇总门禁通过 `if: always()` 始终上报：scope 与 validate 必须成功；计划选择的 browser/storage 必须成功；只有计划未选择的任务可为 skipped。失败、取消、缺失结果、计划错误或意外跳过均阻塞。不能靠过滤整个必过 workflow 或提交 skip 标记绕过检查。

`browser (model_assets)`、`storage-container` 退出全局必过名单：需要它们时由汇总门禁强制检查成功，不需要时明确跳过。旧 PR 的完整四检查结果仍满足保留下来的两个名称，不要求为名称迁移重推全部 PR。

研究发布器按精确审核 SHA 读取所有分页 check runs；两个具名门禁必须实际成功，额外运行的检查不得失败、待定或取消。条件未选择的可选任务可为 skipped，不能把必过门禁的 skipped 当成功。只有上述可证明的研究资料追加走 research 路线，其余正式研究 JSON 修改仍全套。来源、C3、当前正式上下文、网站支持闭包、Spark 回执与独占队列协议保持各自验收。

## 修改与未覆盖范围

分类器、门禁、映射或必过设置改变须同步本文件、AGENTS、current_state、verification_contract、相关发布器和测试，并 refresh/check 治理清单。修改本机制本身必须全套验收；先验证新工作流，再把保护名单收敛至两个始终上报的门禁，并回读确认管理员保护与 app 身份。

测试覆盖研究追加/旧记录类型与顺序/结论及规则变化/ID碰撞/歧义JSON/替代声明/混合范围/固定相关测试和仅研究浏览器别名，以及文案/图片分流、损坏图像、新增失效引用、页面结构与脚本变化、共享消费者、混合与超过 300 文件的差异、删除/改名/符号链接、元数据与实际规则变更、全套场景覆盖和每种作业状态的门禁判断。它不判断研究事实是否正确，不代替图片人工审美/逐项发布验收，不保证外部链接在线，也不自动推断任意间接资源依赖；无法明确映射的 web 消费者按全套处理。历史 PR 的实际失败与验收回执保留。
