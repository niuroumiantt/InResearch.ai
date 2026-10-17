# PR939 冲突与 CI 修复（2026-10-17，m5）

用户授权仅按 #973 → #939 → #975 修复、验收和合并；其它后台任务保持暂停。本次不执行生产 dispatch/reconcile、不启动采集或 Spark 研究服务。

#973 已于 2026-10-17 合并为 c4f1199c，最终 head 461f9bd0 的 23 项 GitHub CI 全部成功。本批合入该 main，保留最新治理和权限规则，剔除 #939 旧冲突处理带入的无关历史规范回退，仅保留 fetchreports 固定入口、队列和只读 ACK 相关规范。

验收范围：collector lookup/receive/production/handoff 单元回归、治理、strict validate、registry、deliveries，以及本 PR 最终 head 的完整 GitHub CI。旧 ui_skin 失败在最新 main 已本地复验通过，仍由本 PR 完整 CI 再验。生产真实交付和四旧版本回执尚未执行，不能由源码合并宣称已接通。
