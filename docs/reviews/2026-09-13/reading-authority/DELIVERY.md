# 当前全文结果与事实处理：本轮交付

本轮使 reader/L2 共享同一个 catalog 当前结果，消除 L2 把事实处理回执显示成全文“已读”的接口。没有把旧人工声明转换成虚构的全文产物，也没有创建第二个当前结果库。整个项目的架构、UI 和历史研究审核仍未结束。

## 修改前证据

基线为 #171 合并后的 083e3b1；以 **8237c13** 先提交 [PLAN](PLAN.md)、[全文件处置计划](file-plan.csv)、[消费者引用](consumers-before.csv)、[反例](baseline.json) 和分类统计，再修改应用。反例在隔离数据上确认：reader 已有完整结果时 L2 仍调用抽取器；零事实处理回执也进入 L2 的“已读”计数。#171 的数据、断言者/分诊规则、指标和正式数据标准原样保留。

## 目标职责、权威与消费者结果

| 公共责任 | 唯一归属 | 消费者及迁移结果 |
|---|---|---|
| 内容身份、版本和当前指针 | catalog.documents / reading_runs / current_readings | Reader 的执行、版本审阅、导出继续使用既有 catalog；新终端查询读取同一投影，没有新的写入器或指针。 |
| 原件、配方、覆盖和产物封印 | materials.reading_artifacts.ReadingArtifacts | 原 ReadingStages 的 artifact_path、_cached、validate_report、seal、verify_seal、_chunk_text 正文迁入；ReadingStages 继承，Reader.process、ReadingRevisions.create/inspect/activate 及现有测试沿原入口调用同一实现。新增 full_text 只被 ReadingResults 的正文复用及专项测试使用。 |
| 无模型的当前结果查询 | workflow.reading_results.ReadingResults | reader current、DeepRead.current → deep-read current、DeepRead.pack，以及专项流程测试。current 在同一只读快照内检查封印与页块；status 供 DeepRead.status 和专项测试使用，只是 catalog 清单计数。 |
| SQLite 只读连接 | storage.catalog.Catalog(read_only=True) | 唯一新生产消费者为 ReadingResults；原 Reader.initialize 仍走既有可写连接和显式迁移。只读实例禁止 initialize、写事务及直接 SQL 写入，不创建缺失库。 |
| 事实处理进度和回执 | DeepRead.processed_documents / remember_processing / receipt_log | queue、pack、status、record、skip、SimilarityIndex 和全部 L2/事实/相似度测试已迁移。回执仅表示处理完成，不能形成全文结果。 |
| 任务包与固定版本引用 | delivery.reading_packet.publish | DeepRead.pack 传入 reading_result；manifest 与 brief 记录同一当前报告版本、SHA、原路径。原报告不复制成第二份全文成果；旧任务包保留旧版本引用。原无 reader 结果场景继续提供抽取输入，并明确未完成全文。 |

[public-consumers.csv](public-consumers.csv) 枚举本次涉及模块 **70 个公开实现**及全部静态可观察调用/属性引用，包含旧调用的继承迁移；[consumers-after.csv](consumers-after.csv) 补充 CLI、任务卡、在册路径和测试 mock 引用。相同名称的调用按语法收集，是候选超集；上表复审生产接收者：ReadingArtifacts 的 stages 接收者来自 Reader，ReadingResults 的 readings 接收者来自 DeepRead，catalog 来自 Reader 或只读查询。不会据静态扫描声称已枚举未知库外调用。外部 M4 客户端需要按任务卡更新 JSON 字段，其实机尚未验。

## 旧实现退出与保留

- 退出：L2 的 read_documents / remember_read / read_log 属性；documents_read / already_read / eligible_unread；相似提示里的 read 及旧 already_read 字段。没有继续提供含义错误的双别名。对应的新名字是 processed_documents / remember_processing / receipt_log、documents_processed / already_processed / eligible_unprocessed，以及 processed 相似提示。
- 退出：ReadingStages 内上述六个产物方法的独立正文，改为继承共同责任。五个方法的 AST 与基线完全相同；verify_seal 另加报告路径必须属于被封印产物的检查，防止返回另一个文件路径。具体迁移见 [method-migration.csv](method-migration.csv)。
- 保留：l2_read.jsonl 的旧文件名、旧行、operation_id 和事实/缺口提交恢复机制。旧文件名是存储兼容，不再决定全文状态；没有重写历史或重复回执。
- 保留：原件、报告、提取页、检查点、旧版本及被拒绝候选。查询不升级数据库；旧未封印结果返回 legacy_unverified。换默认模型、record、skip 和 pack --again 都不替换当前指针。
- 保留：无 reader 当前报告时的 L2 抽取输入能力；它便于事实处理，明确不构成全文完成。损坏的当前封印直接报错，不能用此路径隐藏错误。

[file-results.csv](file-results.csv) 给出每个基线/新增文件的实际处置。没有删除资料文件，没有新增源码职责目录；本次新增的目录仅为日期审计资料。

## 已验证

全量基线 951 项测试逐项保留或改名；12 个名称随“事实处理”语义更正，17 项新用例验证共享当前结果、只读、故障和并发。951 包含 WorkerThreadTests 继承的 36 个线程场景，均按实际测试身份计量，没有把继承测试漏掉。完整对应见 [test-migration.csv](test-migration.csv)。最终 Python 测试、CI 和发布结果见 verification.json 与 PR/发布报告；不能只凭数量认定架构完成。

故障与版本检查覆盖：缺失库不创建、旧/新 schema 拒绝自动升级、原件/正文块/报告损坏、错误报告路径、直接 SQL 写入拒绝、任务包发布失败后重试；已有事实主提交/回执恢复仍通过。独立进程在查询期间激活新阅读，正在生成的任务包保留旧快照，下一次查询得到新版。旧包、旧报告与原件保留；ready、失败重试和换模型不取得替换权。

真实流程见 [real-flow.json](real-flow.json)：242 字合成材料经实际 Claude CLI 完整阅读；两次同字节投递登记为一个文档/一个阅读版本和两个来源。reader 经 manage.py 调用；L2 CLI 在独立 OS 进程中使用显式隔离路径，两个 current 响应相同，开包正文与原文完全一致，未再次抽取。Codex 对照完整原文复审六条主张/引用，保留 6×300 W=1800 W 的服务器小计、排除负载、未知条件及末段候选限制。复审后准备一条隔离事实输入，record 与重试仅产生一个处理回执；再次开包仍引用同一阅读版本。没有生产研究写入或 C3 采用。该结果不代表全语料质量或第二实际模型已验证。

## 计量

同前阶段按 Git 跟踪文件物理行，分别统计自有源码、测试、文档、数据配置、审计与第三方；不盘点外部原件和运行数据库。完整数字见 statistics-before.json / statistics-after.json。新增共享查询、只读连接和跨客户端复用能力使本轮源码净增加；没有通过删除历史研究资料制造减量。产物校验函数移位本身不算净删除。

<!-- statistics:start -->
| 类别 | 基线行数 | 当前行数 | 净变化 |
|---|---:|---:|---:|
| 自有源码 | 22,028 | 22,183 | +155 |
| 测试 | 11,775 | 12,018 | +243 |
| 文档与其他文字 | 43,548 | 43,625 | +77 |
| 数据、配置与在册清单 | 267,928 | 268,195 | +267 |
| 审计证据 | 15,592 | 19,806 | +4214 |
| 外部文字材料 | 517 | 517 | +0 |
| 第三方代码与许可 | 66,682 | 66,682 | +0 |

文件数：622 → 642；跟踪目录：68 → 69；二进制均为 23 件，单列不计文本行。
<!-- statistics:end -->

## 未完成和运行边界

- 只有指向同一个实际 reader 数据根的客户端才共享结果；跨机器 catalog 同步、真实 M4/Spark 台账连接、旧人工全文结果的受控导入尚未验收。本轮未启动 Spark 模型或搬迁资料。
- 现行规范更新为 2026.09.13.7，13 个 scope 的验收映射仍为 partial，不能声称所有自然语言规则和研究结论都已全面证明。
- 两个 3D 巨型场景、全站 Attio/folk 后续交互审阅、研究接口体积优化和历史来源/断言者缺口仍待处理。
- 本机常驻 main 已在用户本轮授权下安全快进到基线；39 个未跟踪/忽略文件逐一核对哈希保留。最终合并后继续快进并核对目标发布版本。这里不预先声称 CI 或上线成功，最终记录在对应 PR 与发布验证报告。
