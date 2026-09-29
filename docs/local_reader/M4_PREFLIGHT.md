# M4 预筛节点

本页 `preflight` 命令的职责是为 Spark 提供**只读、可审计的路由建议**，不运行正式 reader、不写入 Spark SQLite 台账，也不移动或删除原始材料。

默认来源为 `/Users/m4/Downloads/所有raw materials`，运行结果写到 `~/.local/share/inresearch.ai/m4-preflight/<UTC 时间戳>/`：

- `manifest.jsonl` / `manifest.csv`：逐文件的类型、路由、优先级和理由；
- `README.md`：人可读汇总与优先阅读候选。

运行：

```bash
python3 ~/code/inresearch.ai/manage.py preflight
```

本预筛 scope 不代替 [M4 正式分类整理任务](../M4_TRIAGE_TASK.md)；后者的原件移动按独立规则执行。

**定时任务已于 2026-09-29 卸载。** M4 上原有 `~/Library/LaunchAgents/com.inresearch.m4-preflight.plist`
（每 30 分钟一次、登录即跑）；2026-09-29 实机核对发现它仍指向早已退役的 `pipeline/m4_preflight.py`，
自 2026-09-13 起每次运行都以退出码 2 失败，且默认来源目录已不在 M4（原件已上传 Spark）。
已执行 `launchctl bootout` 并把 plist 移到 `~/Library/LaunchAgents/retired/`，M4 上不再有 inresearch 的 launchd 任务。
历史日志仍在 `~/.local/state/inresearch.ai/m4-preflight.log` 与 `m4-preflight-error.log`。

若日后 M4 再次持有原件并需要路由建议，用上面的手动命令跑一次即可；要恢复定时任务，须把 plist 的
`ProgramArguments` 改为 `python3 ~/code/inresearch.ai/manage.py preflight` 再 `launchctl bootstrap`，不要恢复旧入口。

路由是由文件名、路径和后缀得出的候选，不是文件内容、完整性或研究价值的最终判断。`priority_read` 可用于提出 Spark 的后续投料/优先级调整；必须审核后才可作用于 Spark。CAD/3D、Office、压缩包和扫描图像保留在相应后处理队列，绝不被预筛工具删除。
