# M4 深读交接（更新于 2026-09-28，机器 m4，最终状态）

## 目标

在 M4 隔离数据根上，用 Claude CLI 深读 Spark 优先级 ≥7 的文档，产出候选阅读报告，并经 Spark 发布到网站候选区。本阶段已完成，M4 的深读 runner 已停止，不再调用模型。

## 已定规则（用户确认过，不要再问）

- 只写 M4 数据根，不写 Spark 台账，不动 Spark 原件；发布只经 Spark 的外部快照叠加（#268）。
- 默认用 Sonnet 5，b3ff 用 Opus 5.5；周配额到 90% 就停。
- 输出上限 4096 属于冻结配方，不改。
- 重读版本经用户审阅后才启用（`activate-revision`，审阅人 niuroumiantt）。
- 7 份 .md（本项目自己的模块草稿和生成报告）不读，已在 Spark 上 park（`parked_derived_artifact`）。

## 最终状态

- 33/33 完成：Sonnet 根 32 份（含 ce50），Opus 根 1 份（b3ff）。每条入库引文都在块正文里逐字核对过。
- 13 份占位重读（0d50 1765 1cf5 3081 55cf 6484 759d 9710 9ec5 ad60 e142 ee35 f48d）已按 #259 重读、全量扫描无占位，并已切换为当前版本（request_id `placeholder-20260928`）。
- 缺页补读（gap_ocr，#258/#259/#268）：48c8、ce50 全部补上；ea7d 剩第 7 页（三次读出的数字只差逗号和坐标轴刻度），coverage.gap_pages=[7]。
- 外部快照 `m4-sonnet-20260928.json`（32 份）和 `m4-opus-20260928.json`（b3ff）放在 Spark 的 `~/.local/state/inresearch.ai/external-snapshots/`，权限 600。Spark 每 5 分钟发布一次（`inresearch-reader-publish.timer`，unit 已换成仓库版 `manage.py publish`），叠加结果 added 33、dropped_unknown_ids 0。
- 发布压缩上传（#273）：约 65.7 MB 压缩成约 5.5 MB 发送，解压后上限 192 MiB。
- 研究图谱以网站 main 为准（2026-09-28 起 3.0.0，由骨架生成；问题 ID 不变）。版本落后的快照不再被拒收：接收端把旧对象 ID 按对象别名折算到骨架节点、折算不了的过滤掉，并在 `reader.registry_lag` 标出版本与折算 / 丢弃计数；Spark 与 M4 拉到同一提交后重新导出一次即可清零。
- Spark 代码在 b3471f6（READER_RELEASE 同），认领下限 10。

## 待用户决定

1. 人工审阅候选报告。例如 b6b6 第 1 页中文译文把单位写错（「10万亿千瓦时」「100万亿千瓦时」应约为 1,000 / 10,000 TWh），主张忠实引用了错误的原文。
2. 9ec5 第 10 块有 900 字正文（运营商建智算中心），却没有主张，可能属于 5 条剔除主张之一，需要看一下。
3. 首页双栏作者侧栏的抽取问题：b6b6 因此剔除 2 条主张（2030/2050 年用电增速 5.6%/3.2%，光伏产量占全球 80%）。

## 以后要追加文档时

1. 在 M4 上读完，确认 coverage.complete 为真。
2. 按当前注册表导出：`python3 manage.py reader --data-root <根> --state-root <状态目录> --repo-root . export --dest <文件> --doc-id ...`
3. scp 到 Spark 的 `external-snapshots/`，覆盖同名文件并 chmod 600。下一次定时发布会自动叠加。

## 入口文件与工具

- 数据根：`~/.local/share/inresearch.ai/m4-deepread-pilot/`（Sonnet）、`~/.local/share/inresearch.ai/m4-deepread-opus/`（b3ff）。
- 状态目录：`~/.local/state/inresearch.ai/m4-deepread-pilot/`
  - `deepread*.sh`：带配额守卫的 runner。
  - `claude-logged`：CLI 包装，出错写 `cli-errors.log`，每次调用写 `usage.tsv`。
  - `gap7.log`：缺页补读记录。
- 模型配置：`~/.config/inresearch.ai/models.m4-deepread.json`，含 gap_ocr → claude_sonnet_vision。
- 复核记录：`~/m4-review-20260928.md`。
- Spark：
  - `publish-status.json` 里的 `sent_bytes` 是压缩后的大小；
  - 被拒原因在 `journalctl --user -u inresearch-reader-publish` 的 detail；
  - 旧 unit 备份为 `inresearch-reader-publish.service.bak-20260928`。
- 已知限制：reader 不保存被拒的模型回答，也不记录逐次拒绝原因。
