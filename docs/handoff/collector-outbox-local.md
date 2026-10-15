# 四队本地作业与ACK对账交接

用户授权先本地落实四队错误分类、作业台账、待交付队列和ACK对账；复用原四源与旧ID/信封/来源版本。仅手动本地沙箱，先查持久回执再同包重试，不启用定时、不扩来源、不部署，不入Reader、不采用或填参。

源码：~/code/fetchdata与/Users/m5/.codex/worktrees/navigation-auth-shell/inresearch.ai，均为codex/collector-outbox-local本地分支；主工作区其他任务不触碰。原件/包/回执/失败复本在~/.local/share/fetchdata/operations-audit-20261015，日志在对应~/.local/state/fetchdata目录。实际真实包验收与最终本地提交版本以该目录结果为准，不将本地ACK当生产接收，不推送、不部署、不安装调度。

## 实际本地结果

本地实际验收完成：四队4登记来源、7已有字节版本（报告4版同源），7手动作业/7已确认交付；真实本地重放新增0。采集后中断、接收后进程退出、ACK丢失、接收前失败与显式恢复均验证；错误ACK不采信，损坏复本隔离。旧ID/版本/原信封/原时间逐字节保持，正式五文件SHA不变；联网下载/Reader/采用/填参0，无调度、扩来源、推送或部署。

源码验收版本：fetchdata beb2f9abf1f070a4f6c59682dc6f076a1fa451bb；本地接收 0ebfedc46925632669008c9811b6b25c7bb3ffe2。完整结果/Users/m5/.local/share/fetchdata/operations-audit-20261015/run-1/result.html及result.json，34/59/2701项测试通过。日志/状态与冻结材料分别保存在state/share目录，所有失败复本、旧包和Git历史保持。最终文档提交不改变已验代码；实际生产仍为此前受控文件接收，本地新功能未上线。
