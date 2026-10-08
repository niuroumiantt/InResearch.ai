# PR #412 冲突修复与发布交接（2026-10-09，m5）

## 目标与授权
保留 main 和本 PR 的研究记录，合并后更新网站、Spark 与本地 main。用户在 Actions 预算阻塞已说明后，明确要求推送、合并并更新线上与本地；本次使用实测本地检查，未修改账户预算、分支保护或伪造 CI 成功。此回执是本次发布记录，不替代持续发表器的通常 CI 门槛。

## 当前结果
- 原 head bb255d89，首次无损冲突修复 171fce8d；主线又有图册更新及 #417，因此本轮重新合并主线和生成清单。
- 原 5 条陈述的 ID 保持；其原审核上下文已变化，原 attempt-0002、attempt-0003 与 source/模型审计均保留。原批次拆成 e4a00ad8a328… 与 f0ec0f2f8311…，两子批均实际重新匹配、core_review 及独立抽样通过，并重新核对源文件和当前上下文。
- 分别在同一 main 基线 ecdf80b2 的隔离副本执行 promote，合并两个互不重复的追加结果；所有既有 main 记录的值和顺序不变，不增加正式 answer 或关闭问题。
- 点名恢复的拆分子批命中了历史 untouched regrouped 行；一致 SQLite 备份、恢复理由与 routing_history 保留在 Spark 私有 manual-release-20261009，不删除旧行或尝试。
- 检查：治理、严格校验、registry、1931 单元测试；28 个 core 浏览器场景、3 个模型资产场景、实际 Docker 只读镜像及持久状态 A→B→A 通过。新主线图册的 technical_atlas/part_dossier 也通过。最终新增数据还需本提交的治理、严格校验和研究回归。

## 发布接续
#417 已于北京时间 2026-10-09 07:19:35 经真实 HTTPS adopted API 核对 3 条陈述、引文和文档支持闭包，并回写 Spark published，网站镜像 ecdf80b2。#412 本提交合并后同样核对新增 5 条，按两子批各自的真实 bundle 写 website-proof 与 Spark published；旧父批 split_context 不冒充重新审核通过。

## 入口
- https://github.com/niuroumiantt/InResearch.ai/pull/412
- 正式路径：src/inresearch/workflow/research_publish.py；部署用 infra 的 inresearch-only-deploy 服务。
- 本机验证记录：~/.local/state/inresearch.ai/releases/pr-412-417-20261009/validation.json；子批不可变审计及上线回执：~/.local/state/inresearch.ai/research-publish/。
- Spark 审计：~/.local/share/inresearch.ai/material-reviews/research-verification/；原件、Reader 与研究服务保持。发表 LaunchAgent 在人工处理期间暂停，收尾恢复。
- 本地独立 main 工作树：~/.worktrees/inresearch.ai/main-release-20261009；主目录原任务分支保留。
