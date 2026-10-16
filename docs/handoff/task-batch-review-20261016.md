# 紧凑时间线与同批联合审阅交接（2026-10-16，m5）

## 目标

减少任务页纵向滚动，让不连续附件可分次累加，并将同次关联材料一次确认、联合审阅后上线新版流程。

## 已定规则

- 公开／个人时间线默认单行摘要，完整反馈、覆盖范围与文件校验按需展开。
- 同次最多20份、单份64 MiB；跨目录选择与拖入累加，逐件移除／清空。每份原件SHA和回执独立保留。
- 凭回执及私有批次凭据封存实际成功清单，未完成上传不能自动开始分析；丢响应恢复原回执，另一标签页不自动提交仍在上传的批次。
- 指定负责人一次确认精确成员与版本，Codex共用一次当前任务／台账上下文，联合比较版本、补证、重复和冲突；结论逐件定位，关系有双侧定位。
- 大表仍明确抽样和未读范围，不从抽样发布；原生候选、普通来源发布、C3和模型参数各按既有门槛。
- 持久联合结果用于部分写回恢复；本批自己的写回不使后件重复推理，外部变更仍拒绝。正常一次调用，定位校验失败最多纠正一次，再失败需人工复核并停止自动模型开销。
- 旧单件断点／报告保留；旧批已处理成员不重读，未处理余件仍可确认。明确退回成员留排除审计。

## 进度

- 独立工作树基于 `d67a0ff3`，分支 `codex/task-batch-review-density-20261016`；主工作区旧架构任务未动。
- 新增28项批次单测、完整2803项单元测试通过；真实浏览器覆盖累加／拖入／删除、双提交、跨标签页、失响应／审批断写恢复、精确批次确认、权限与下载、1440／390／320px的6／10条紧凑摘要。
- 治理、严格数据校验、registry、asset-check、verify及indicators已执行；派生日期快照还原，未将无关指标变更带入本批。
- 当前为本地源码验收阶段；受保护PR完整CI、网站镜像／公网及Spark同版本服务回执在实际完成后另记，不能据此称已上线或真实员工材料已完成全表审阅。

## 下一步

1. 在最终head通过治理／严格校验与完整CI，正常合并受保护main。
2. 核正式 `inresearch-only-deploy.service`、精确运行镜像和公网任务资源。
3. 暂停原Spark intake timer，等当前receive自然结束；保存状态并用验证后的增量Git bundle快进干净源码，恢复同一timer。Reader／relay不重启。
4. 记录实际网站／Spark版本与服务回执；未来真实批准批次按其实际覆盖另验，历史报告不追溯重写。

## 待用户决定

无；本轮整改和上线已授权。

## 入口

现行规范：`framework/05_interface_system.md`、`framework/09_software_contracts.md`、`framework/verification_contract.json`；后端 `materials/batch_review.py`、`review_worker.py`、`task_analysis.py`；前端 `task-uploads.js`、`task-reviews.js`；测试 `tests/unit/test_task_batch_review.py`、`tests/research_tasks.cjs`；部署见 `docs/local_reader/SPARK_OPERATIONS.md`。原件、批次凭据、运行清单与真实回执不进Git。
