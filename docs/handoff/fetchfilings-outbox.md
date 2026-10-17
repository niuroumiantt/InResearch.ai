# fetchfilings生产队列交接

## 已完成：2026-10-16

用户接受fetchstat结果后授权接通fetchfilings AWS→Spark持久队列与ACK；仅既有Microsoft FY2025年度现金PP&E来源，候选不采用或填参，不定时、不扩源、不接下一队。原ID、信封、来源版本和交付历史保持。

PR #935的精确head 6c7471f6cafe9ca830ea54efdb46b7a0b7f1fe3d通过全部23项CI，管理员保护保持，受保护合并442ef16d4dc79bdb40c9b4fb8ac8ca512bbc8df1与已审阅树一致。AWS私有fetchdata运行6a0c0b272d5cf843c51feccac7e89c6057b7423a，保留2184099研究目标快照基线及全部历史；无新增公开仓库。M5本地四模块56项、InResearch全套2772项测试，治理/strict/registry通过。

Spark filings固定运行检出为~/.worktrees/inresearch.ai/collector-fetchfilings-442ef16d；原主检出dc776d00未切换，Reader/review/publish服务保持active，本轮未重启。filings专用公钥限定AWS精确地址、restrict、100秒timeout与固定脚本；任意命令实际被拒绝，私钥只留AWS。stat已验3c0d2834独立固定运行检出和旧绑定保持；AWS采集源码升级后原stat ACK实际查询通过。

## 实际验收

旧交付fetchfilings-564154a15ac28c0f7f72f304-v1，整包SHA c23ad84b179e4b8a18a0a38932f8bce965602eecf773748e47fec19433e02e91，原collector_revision eead7e8dfb87aaae96cfbb8edbececfe34e3da1e不改。原首次接收2026-10-14T15:03:23.556746+00:00和完成归档时间保持，新的发送/故障/对账另记事件。

- 主队列真实发送1次confirmed；Spark实际重放2次，原件/来源项/候选新增均0；confirmed再次dispatch不重发。
- 真实接收后故意丢弃ACK，新AWS进程reconcile使ack_unknown→confirmed，attempts仍1。
- 真实收到Spark回执后os._exit(74)，新进程恢复sending→confirmed，attempts仍1。
- 真实SSH受控失败代理退出；恢复连接后查历史完成ACK，ack_unknown→confirmed，attempts仍1。
- 四个独立操作台账只有1个旧交付/来源版本，不算4条资料或独立证据；新下载/候选/Reader/审核/采用/发布/填参均0，四队scheduled=false，未安装采集定时。旧包/信封/历史/来源配置及正式五文件摘要守恒。

连接失败恢复走已有ACK确认；“确实未接收后重试”仅本地测试覆盖，本轮未用新生产包证明。未验硬件断电/灾难恢复、定时无人值守、其它来源、SEC/XBRL或附件。公司年度负数现金PP&E、财年/集团口径和未知披露时间保留，不能分配到园区模型。

## 结果与继续

本地结果~/.local/share/inresearch.ai/fetchfilings-outbox-20261016/result.html及result.json、aws-final.json、spark-final.json、三故障前后状态、受保护合并和runtime.json。对应state目录保留4个SQLite备份及故障材料，不含ssh密钥。AWS原操作库/故障复本与Spark归档继续保留。源码操作规范为docs/guides/fetchdata/fetchfilings-outbox.md。本地验收记录的提交晚于已部署源码，不能冒充新的运行版本。

阶段完成，等待用户确认后再接下一队；不自动扩源、调度、采用或填参。主站既有独立发布流程/版本另核，不能用网站镜像版本代替固定网关版本。
