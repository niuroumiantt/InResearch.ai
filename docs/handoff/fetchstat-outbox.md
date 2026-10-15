# fetchstat生产队列验收交接

## 2026-10-16：实际验收完成

用户整份保存精确Tailscale策略后，AWS100.103.118.69以专用固定命令密钥直连Spark100.100.1.2:22成功。本轮源码未修改、未重新部署：AWS fetchdata 8b29994f514c6cf43f5d6e864a04b138940610cc、Spark InResearch 3c0d28340d00155bc2b19289ba944e38a58d474e，均干净。私钥只留AWS，不进入本地审计或Git。

canonical持久队列实际发送1次后confirmed；Spark实际重复接收2次均零新增，已确认队列再次dispatch无新增发送。真实接收后丢弃ACK，新AWS进程查回原ACK；实际接收后发送进程os._exit(74)，新进程恢复sending到confirmed；实际SSH受控ProxyCommand=false失败，恢复正常连接后查询历史ACK确认。三故障使用独立验收台账，不改canonical历史；四份台账各发送尝试1次，仅1个旧ID/1个来源版本，不能计作四份新资料或独立证据。

旧交付fetchstat-2d71d12585023e9506bf0bba-v1；整包734e8d7917a863cb1eb28b8e353943c2883ed8649316b1c8e92b7de57256fdd5；原collector_revision adb4a700a9cbe27b5ae86cbb99a0a6ea834746ea；first_received_at 2026-10-14T08:53:17.911537+00:00及archive_completed_at 2026-10-14T08:53:17.996371+00:00保留。原件、原信封、未知字段、来源配置与交付历史摘要守恒；五份正式模型/数据SHA不变。本轮新下载/新候选/Reader/采用/填参0，scheduled=false、不扩源、不接下一队，Spark既有服务active且未重启。专用密钥实际拒绝任意远程命令。

恢复边界：本轮使用10月14日已归档的旧包，传输失败后查到历史完成ACK，验证的是“已收只确认”分支。“确实未收后同包重试”有此前本地测试，未用生产新包验证；不宣称硬件断电、灾难恢复或长期无人值守。

私有完整回执~/.local/share/inresearch.ai/fetchstat-outbox-20261015/production-20261016/result.html及result.json；aws-final.json、spark-final.json、独立前后状态、真实退出74、重复ACK和命令拒绝证据同目录。AWS侧独立故障材料在~/.local/share/fetchdata/fetchstat/outbox-audit-20261016；台账在~/.local/state/fetchdata/fetchstat/outbox-audit-20261016，canonical台账在~/.local/state/fetchdata/fetchstat/operations。M5只备份这些operations及审计根，不复制含私钥的ssh目录。旧包/故障复本/历史不清理。

继续时先核AWS目标配置和Spark实际干净HEAD；队列绑定接收版本，源码升级不能静默改绑定、删库或覆盖旧ACK。下一队和调度仍等待用户指令。以下为准备阶段历史，网络未通状态已被本段实际回执替代。

## 准备阶段历史

# fetchstat生产队列交接

2026-10-15 用户授权只接通fetchstat AWS到Spark待交付/ACK，验证真实交付、重复、ACK丢失与失败恢复；不定时、不扩源、候选不采用或填参。当前分支codex/fetchstat-outbox-production；fetchdata无远端，私有源码束交付，保留全部旧仓库及来源历史。主工作区其它任务未触碰。

本地新增固定SSH网关、fetchstat专用生产传输、只读完成ACK核验。网络探测：AWS Tailscale100.103.118.69可ping Spark100.100.1.2，但TCP22超时；infra现行prod-server只允许Spark11434，已向用户请求精确TCP22规则。未绕过ACL、未复制管理员私钥、未启用调度。真实生产验收尚待网络开通及受保护部署，不能冒充已完成。

指南docs/guides/fetchdata/fetchstat-outbox.md；前阶段本地四队结果仍在~/.local/share/fetchdata/operations-audit-20261015/run-1/result.html。此次运行材料与结果使用~/.local/share/inresearch.ai/fetchstat-outbox-20261015，日志~/.local/state/inresearch.ai/fetchstat-outbox-20261015；源码/单元测试回执不替代真实ACK。
