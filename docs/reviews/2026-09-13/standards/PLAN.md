# 现行标准与执行一致性复审：修改前交付

基线：`64bef5a33eff5e7c8f953d9d6665777c85dd8bde`（2026-09-13）。本文件先于本轮业务代码修改提交。此前架构整改的全文件迁移清单和生产验收仍是日期快照，不作为本轮规则依据。本轮不迁移目录、原件或运行数据库。

## 已复现的现状

原治理检查通过，但隔离反例得到以下结果，完整输出见 baseline-probes.json：

| 编号 | 现状证据 | 应达到的职责 |
|---|---|---|
| S1 | C 档 evidence/statement/answer 可通过 registry.validate，并关闭 M01-Q01 | 核心采用只接受 A/B 合格审核；C 只存档；任一支持链失效重新开放问题 |
| S2 | 投递文件名相同就返回 DUP | 接收元数据仅提示重名，真实材料以字节 SHA 判身份，不能拒收同名新版 |
| S3 | 自主发现、无工单的 6 分材料进入 B | B 必须匹配当前工单；未匹配保持候选待匹配；分流不是模型审核完成 |
| S4 | submission schema 没有 key_statements，仍称没有数字无贡献 | 数字与非数字原文证据同等合法；声明结构与运行校验一致 |
| S5 | 替换成功后目录 fsync 异常，新字节已可见 | 区分提交前失败与提交后持久性不确定；不得承诺所有异常均保留旧内容；重试应核对主提交点 |
| S6 | 06、执行协议与项目简报仍指定 27B；04 把 C3 指回 DECISIONS | 08 是唯一模型规则，01 是唯一 C3 规则；操作文档跟随当前 CLI 与适用 scope |
| S7 | 治理只验清单、替代关系和旧词表，不绑定规范版本与测试 | 增加人工审定的规范摘要/验收映射；规范变化不能只刷新清单便隐去未审阅变化 |

研究页的首次绘制脚本已在 head 同步加载；复核后排除“研究页未加载主题”的疑点，不为假设制造改动。

## 权威、消费者与全文件修改计划

- 规范：framework/01_data_standards.md 明确完整 C3 边界；04、00、docs/M4_TRIAGE_TASK.md 仅引用它。framework/08_model_execution.md 保持模型权威，06 和操作文档引用它。
- 业务：src/inresearch/knowledge/registry.py 修复正式采用资格；src/inresearch/workflow/submissions.py 修复候选接收、工单资格与分流表述；data/schema/submission.schema.json 同步结构；docs/inbox/submissions/README.md 同步操作契约。
- 存储：src/inresearch/storage/files.py 明确提交后不确定异常；framework/09_software_contracts.md 同步失败阶段契约。已知直接消费者逐文件见 consumers-before.json；HTTP/CLI 的错误结果须同步。
- 治理：src/inresearch/interfaces/governance.py 接入规范与测试映射检查；新增 framework/verification_contract.json 及最小验证模块和测试。current_state.json、CURRENT.md、DECISIONS.md 与生成清单一并更新。投递 README 是操作指南，不能继续被 docs/inbox 整体规则归作候选。
- 操作文档：docs/local_reader/{RUN_TO_COMPLETION,PROJECT_BRIEF,ACQUISITION_OPERATIONS,M4_PREFLIGHT}.md、framework/03_bom_and_collaboration.md、06 修正当前命令和 scope，不改历史实机记录。
- 测试：tests/unit/test_research.py、test_intake.py、test_commands.py、test_governance.py 及新增规范映射测试，覆盖有效对照、非法采用、同名新版、无工单、失败重试及规范变更。现有进程并发、模型切换、失败优先级、浏览器矩阵继续使用，不冒充完整重读替换验收。
- 本目录：保存前后证据、消费者迁移结果、分项统计与未完成清单。旧的 architecture 日期快照不重写。

## 旧实现退出清单

退出 C 档关闭问题的资格、按文件名拒收、无工单进入 B、以候选批次输出冒充模型审核、固定 27B 执行指令，以及任意异常都保留旧字节的承诺。保留 SHA 原件身份、历史记录、兼容成员候选 CSV、历史模型配方与 CLI 名称；这些保留项有实际消费者，不因减行目标删除。

## 验收边界

所有 13 条现行政策逐项登记“已核对要求、实际测试、未覆盖事项”。登记和测试存在只证明可追踪，不证明所有语义均已验证。完整重读版本替换、38 条既有事实 SHA 缺口、27 条历史来源未登记、Spark/M4 实机状态、全文翻译/可靠投递等已知缺口保持未完成。新增测试必须先对应本文件反例或明确的业务要求；不改断言以掩盖旧行为。
