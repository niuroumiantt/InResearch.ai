# M4 预筛节点

M4 的职责是为 Spark 提供**只读、可审计的路由建议**，不运行正式 reader、不写入 Spark SQLite 台账，也不移动或删除原始材料。

默认来源为 `/Users/m4/Downloads/所有raw materials`，运行结果写到 `~/.local/share/inresearch.ai/m4-preflight/<UTC 时间戳>/`：

- `manifest.jsonl` / `manifest.csv`：逐文件的类型、路由、优先级和理由；
- `README.md`：人可读汇总与优先阅读候选。

运行：

```bash
python3 ~/code/inresearch.ai/manage.py preflight
```

在 M4 上，`~/Library/LaunchAgents/com.inresearch.m4-preflight.plist` 以
`StartInterval=1800` 每 30 分钟运行一次，并在登录时立即运行。它由本机
`launchd` 和本仓库脚本执行，不依赖 Codex、Spark 或互联网；M4 进入深度
休眠时会暂停，唤醒后恢复后续调度。日志位于
`~/.local/state/inresearch.ai/m4-preflight.log` 和
`~/.local/state/inresearch.ai/m4-preflight-error.log`。

路由是由文件名、路径和后缀得出的候选，不是文件内容、完整性或研究价值的最终判断。`priority_read` 可用于提出 Spark 的后续投料/优先级调整；必须审核后才可作用于 Spark。CAD/3D、Office、压缩包和扫描图像保留在相应后处理队列，绝不被预筛工具删除。
