# 四队本地作业与ACK对账

2026-10-15新增本地作业台账、冻结待交付队列、错误分类与ACK对账。只支持明确本地InResearch沙箱，不是AWS/Spark自动交付；既有四队单源受控生产接收保持，未启用调度、不扩来源、不入Reader、不采用、不填参。

采集源码位于~/code/fetchdata，完整命令及状态机见该仓库docs/LOCAL_OPERATIONS.md。acquire显式记录手动作业并保持旧包/ID；enqueue验包冻结；dispatch单次交付；reconcile先核只读回执；status展示阶段；resume只用于人工复核后的暂停或待重试项，不能绕过损坏隔离。

本仓库scripts/receive_collector_local.py保留原包接收命令，新增以下只读查询：

```sh
python3 scripts/receive_collector_local.py --sandbox-root /明确隔离根 --lookup-provider fetchquotes --lookup-delivery <旧交付ID>
```

查询不创建接收根、不修复存储、不刷新first_received_at。仅接受collector-local-receipt/1，核对本地标记、原包指纹、来源/候选台账和权限边界；未知返回found=false，损坏或伪造拒绝。结果不具有生产ACK或研究采用效力，没有HTTP接口或生产队列入口。

ACK丢失先查台账，已收不重发，未收才按预算同包重试。发送意图与事件先持久入账，中断可从独立进程恢复。交付失败不重新抓取，旧源码版本、交付/原件/候选ID、未知与推导保持。错误类别、重试时点和等待人工复核分别可见。

本地实际结果保存在~/.local/share/fetchdata/operations-audit-20261015/。四队真实包只是复用原件的本地验证，不是新增联网采集、生产上线或正式采用；生产受控接收回执仍按各队生产指南读取。
