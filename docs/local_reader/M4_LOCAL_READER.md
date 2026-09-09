# M4 本地粗筛节点

`pipeline/m4_local_reader.py` 是 M4 的独立预处理器，不是 Spark reader 的副本。

- 只读 `/Users/m4/Downloads/所有raw materials`；不移动或删除原件。
- 原生 PDF 文本由 Poppler 提取；M4 的 `qwen3:8b` 只对有界预览作相关性路由。
- 扫描件另列为 `needs_ocr`，待视觉 OCR 的页图渲染小样验收后才启用；不会把未 OCR 的文件伪称已阅读。
- 产物保存在 `~/.local/share/inresearch.ai/m4-local-reader/results.jsonl`，是可审计候选，且不写 Spark catalog。
- `send_to_spark` 只是送入 27B 深读的建议；`exclude_candidate` 也只是可复核的候选排除，不删除任何文件。

先手工小样运行：

```sh
python3 ~/code/inresearch.ai/pipeline/m4_local_reader.py --limit 1
```

确认结果的模型身份、输出结构与实际主题合理后，才配置 LaunchAgent 自动持续运行。

## Spark–M4 自动卸载

`pipeline/m4_offload_worker.py` 是常驻的 M4 OCR worker，由
`~/Library/LaunchAgents/com.inresearch.m4-offload-worker.plist` 每 15 分钟
运行一次。它只领取 Spark catalog 中已经 `blocked` 且为 OCR 错误的 PDF；
Spark 正在排队或运行的文件、NAS `.partial` 原件、Office/CAD 文件均不领取。

领取后 M4 经 SSH 获取一份临时副本并核对 SHA-256，逐页以 `qwen3-vl:8b`
做两次 OCR。只有两次数字集合一致、原件哈希和页号均匹配时，结果才写到
Spark 的 `offload/m4/results/`。Spark reader 验证这些字段后才重试该文档。
任何失败均保留原件与 Spark 阻塞状态，绝不直接修改其 SQLite catalog。
