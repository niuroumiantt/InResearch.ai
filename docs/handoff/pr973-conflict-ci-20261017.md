# PR973 冲突与 CI 修复（2026-10-17，m5）

## 目标与范围
按用户授权依次处理 InResearch #973、#939、#975，修复冲突与 CI 后逐个合并。其它自动化、研究、采集与发布队列保持暂停；不恢复 Spark 生产研究。

## 本批修复
- 在独立工作树合入 main 3d038b1b，保留 intern 工作台及 CoreWeave 登记，同时保留输出拆分与同源回执复用。
- 原 CI 的 private_repository_only 是公开仓库误路由私有 Spark runner。公开或未知可见性走 hosted；私有仓库还须 infra 登记与 SPARK_CI_ENABLED 显式启用，系统身份门禁保持。
- 修复过程发现 intake timer 再次 enabled，已按用户暂停范围 disable 并停止 service；其失败状态保留，未清审计或重启。Spark CI 容器未启动。

## 验收与交接
本地 Python 3.12 完整 3041 项单元测试通过（126.832 秒）；严格数据校验 0 warnings，registry、deliveries、资产契约通过。main 已恢复 validate 与 browser (core) 两项 GitHub Actions 必过检查、strict 更新基线及 enforce_admins，无新增人工审批。
以本 PR 最终 head 的 GitHub Actions、治理、严格数据、registry 与相关回归回执为准。禁止跳过失败、把旧 head 的通过当本次通过，或恢复其它后台任务。PR973 合并后再把新 main 合入 PR939；最后处理 PR975。
