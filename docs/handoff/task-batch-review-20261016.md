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
- PR [#944](https://github.com/niuroumiantt/InResearch.ai/pull/944) 精确head `d3b5392caca3ba340705184e6a8812a39b9f1350` 的23项CI全部成功（run `38871815577`，GitHub Actions app 15368），正常受保护合并为 `d0fc752a95fef857caddfd1c9e30c3c68455447b`；合并树与验收树相同，无bypass。
- 首次实际上线：正式部署服务退出0，运行镜像 `inresearch-app:d0fc752a95fef857caddfd1c9e30c3c68455447b`，digest `sha256:beebd516c3a9c1cd8dfcd1812cd5bbfdf03a1bf50a7da60bb91227d5b7e14003`，running／healthy，公网HTTPS health成功。
- 公网5项任务资源SHA与源码一致，镜像内审批页及联合后端5项关键文件SHA一致。真实桌面4条接力摘要每条38.390625px，390／320px无横溢，分两次选择并拖入共4份本地附件、移除／清空通过，0生产POST、0页面脚本错误。
- Spark在原receive自然结束后备份22个状态JSON及5份原件SHA，以SHA核验的145005字节增量bundle从 `dc776d007b6e` 快进到同一 `d0fc752a`；实际Python环境28项隔离测试通过，原timer恢复。5份原件SHA／大小保持，Reader及研究审核PID未变。2026-10-16 16:23:44–16:23:47（北京时间）同一正式收件服务实际退出0，`received=0, analyzed=0`。
- 真实员工新批次本轮未另行批准或提交；上述零增量运行不证明新批次已联合审阅或历史大表已完成全文。首次功能上线SHA保持，后续本文件回执提交不改写它。

## 下一步

1. 后续真实员工按新界面提交后，负责人核对整批原件并确认；以实际覆盖范围、逐件反馈和发布回执验收，不把流程上线当全表已审。
2. 原件、批次凭据及失败历史继续保留；定位校验终态由负责人处理，不能无限自动重试或手改审批。

## 待用户决定

无；本轮整改和上线已授权。

## 入口

现行规范：`framework/05_interface_system.md`、`framework/09_software_contracts.md`、`framework/verification_contract.json`；后端 `materials/batch_review.py`、`review_worker.py`、`task_analysis.py`；前端 `task-uploads.js`、`task-reviews.js`；测试 `tests/unit/test_task_batch_review.py`、`tests/research_tasks.cjs`；部署见 `docs/local_reader/SPARK_OPERATIONS.md`。本机审计在 `~/.local/state/inresearch.ai/task-batch-review-20261016/`，Spark备份在同名状态目录下 `before-20261016T081926Z/`。原件、批次凭据、运行清单与完整真实回执不进Git。
