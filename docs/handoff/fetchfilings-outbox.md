# fetchfilings生产队列交接

2026-10-16用户接受fetchstat结果后授权接通fetchfilings AWS→Spark持久队列与ACK，仅既有Microsoft FY2025年度现金PP&E来源，候选不采用或填参，不定时、不扩源、不接下一队。原ID/信封/版本/历史不动。

本轮新增filings固定命令入口、两队公共核验复用及provider隔离测试。Spark主检出已更新，故恢复stat已验3c0d2834到独立固定运行检出，只更换其专用公钥的脚本路径，不改stat队列绑定或ACK。filings也独立固定版本，避免主站发布打断网关。实际生产回执待部署后验证，源码测试不冒充接通。

数据结果~/.local/share/inresearch.ai/fetchfilings-outbox-20261016，日志对应state目录；来源/原ACK/原件/故障复本保留。后续按docs/guides/fetchdata/fetchfilings-outbox.md；核所有相关CI及受保护合并，私有Git bundle到既有主机，不创建公开采集仓库、不复制私钥。主工作区其它任务不触碰。
