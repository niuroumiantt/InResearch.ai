# 四队本地作业与ACK对账交接

用户授权先本地落实四队错误分类、作业台账、待交付队列和ACK对账；复用原四源与旧ID/信封/来源版本。仅手动本地沙箱，先查持久回执再同包重试，不启用定时、不扩来源、不部署，不入Reader、不采用或填参。

源码：~/code/fetchdata与/Users/m5/.codex/worktrees/navigation-auth-shell/inresearch.ai，均为codex/collector-outbox-local本地分支；主工作区其他任务不触碰。原件/包/回执/失败复本在~/.local/share/fetchdata/operations-audit-20261015，日志在对应~/.local/state/fetchdata目录。实际真实包验收与最终本地提交版本以该目录结果为准，不将本地ACK当生产接收，不推送、不部署、不安装调度。
