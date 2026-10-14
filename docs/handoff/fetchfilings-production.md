# fetchfilings生产接通交接

fetchfilings新增Microsoft官方FY2025年报的精确来源白名单，与fetchstat分别锁定目录、来源身份和ACK；候选不入Reader、不采用、不填参。38项合同/恢复测试通过；用户已明确授权源码版本包和公开年报包传往既有AWS/Spark；真实生产ACK待部署后验证，connection仍为not_connected。

源码工作树：/Users/m5/.codex/worktrees/navigation-auth-shell/inresearch.ai，分支codex/fetchfilings-production。统一采集源码：/Users/m5/code/fetchdata，提交363a48fdf02a38b3611b92032c2d942ca22decb4。旧仓库及所有旧交付未修改。

旧交付fetchfilings-564154a15ac28c0f7f72f304-v1，旧collector_revision eead7e8dfb87aaae96cfbb8edbececfe34e3da1e；原观测ID ac923441fabaa555ec51ccd70687ec07，值-64551 USD million，2024-07-01至2025-06-30。披露日/正式对象未知。

用户已明确授权传送源码版本包和公开年报包至既有AWS/Spark，解除此前自动审批的外发阻塞。生产接收及最终部署须另验实际回执，不以本地结果冒充。

## 生产接收完成

fetchfilings已用Microsoft官方FY2025年报完成AWS真实采集、Spark永久候选接收、受控截断拒绝/完整重试与同包零增量重放；旧ID、版本、原信封和首次接收保留。仅Microsoft年度现金PP&E单源受控文件交付，未启用调度；候选不入Reader、不采用、不填参；fetchreports/fetchquotes仍未接通。

首次生产接收2026-10-14T15:03:23.556746+00:00，接收器4ee6c353259b334652de38d00a68fd9f9970d0b0。完整回执在/Users/m5/.local/share/inresearch.ai/fetchfilings-production-20261014/spark-audit；旧包和故障副本仍保留。后续任务/架构展示发布需要最终head完整CI、受保护合并及网站/Spark版本核对，不能仅以本条说明视作展示已上线。

任务/供应/架构三场景Chrome隔离浏览器通过，含手机宽度、登录权限和旧链接；生成目标完整JSON对照只变fetchfilings连接元数据和next_due，全部采用状态/经济输入不变，看板root.account逐值不变。
