# L1 研究流水线收敛计划

> 范围：M4 的预览、终端批处理、本地模型评分、摘要抽取及进度报告。基线为 `e5bb582`；本文件是实施证据，不取代 `docs/M4_TRIAGE_TASK.md` 和 `framework/09_software_contracts.md`。

## 现状证据

- `workflow/terminal_batch.py`（613 行）同时拥有候选选择、预览清洗、批包写入、L0 自动写入、终端判定写入、进度 ETA 与版本候选算法。
- `workflow/score.py`、`workflow/attribution.py` 和 `workflow/progress.py` 为复用 `pending`、`clean_preview`、`working_rate` 导入终端模块；方向是业务用例依赖 CLI 外壳。
- `workflow/triage.py:cmd_run` 仅转发 `score.cmd_run`，同一评分操作有两个命令入口；`sample` 又以 6000 字原文本预览调用模型，和 `score` 的 400 字净化预览口径不同。
- `score`、`attribution` 和 `terminal_batch` 各自定义并验证 `MAX_WORKERS=16`，分别直接调用 `commit_result`。这让并发、预算与版本冲突规则不能以一个用例验收。
- 外部审阅的 P1-1、P1-19 已在 `docs/reviews/2026-09-14/code-review/REVIEW.md` 登记；本批仅解决其 L1 边界和 ETA 单一所有者，不声称解决全文阅读或 Spark catalog 桥。

## 目标职责与数据权威

| 责任 | 唯一实现 | 权威数据/写入规则 |
|---|---|---|
| 选择待处理材料、预览清洗及格式预算 | `workflow.l1_batch` | inventory + `materials.records.current_results`；只返回稳定 SHA 条目，不写入 |
| L0/L1 结果提交及 revision 冲突处理 | `workflow.l1_batch` | `materials.records.commit_result`；调用方传入见到的 revision，冲突计为拒绝 |
| 并发模型评分和摘要抽取 | `workflow.l1_batch` | 注入 `prepare`、`judge/extract` 和结果写入；先占预算槽，再发模型请求 |
| 活动时段速率与 ETA | `workflow.l1_batch` | digest 时间戳；没有活动样本返回空值，不退回依赖平台文件 birthtime 的估算 |
| CLI 参数、文件格式及呈现 | `terminal_batch`、`score`、`attribution`、`progress` | 不持有业务选择、写入或速率规则 |
| 旧 Anthropic batch drain | `triage.collect` | 仅重放已登记的旧远端任务；不能发起新任务 |

## 全文件迁移清单

见 `file-plan.csv`。每个公共实现的消费者和迁移结果见 `consumers.csv`。测试会覆盖相同业务流程、模型失败、并发预算、旧 revision 的迟到写入和按版本替换。

## 旧实现删除清单

| 旧实现 | 处理 |
|---|---|
| `terminal_batch.pending/clean_preview/working_rate` | 迁移所有消费者后删除，不保留转发别名 |
| `score.MAX_WORKERS`、`attribution.MAX_WORKERS`、`terminal_batch.MAX_WORKERS` | 迁移为 `l1_batch.MAX_WORKERS` 后删除 |
| `triage.cmd_run` | 删除；`score run` 是唯一共享模型 L1 评分入口 |
| `terminal_batch.cmd_status` 的 birthtime 回退 | 删除；进度不足时明确为未知 |

未删除：`terminal_batch` 命令仍是人工判定包的公共 CLI；`triage.collect` 仍是历史远端 batch 的排空入口，直至运行台账证明没有待回收任务。

## 非目标与未完成项

- 不迁移 Spark originals，不实现 `apply-triage`，不把 L1 预览结果表述为全文阅读。
- 本批不删除历史审阅材料，不以目录改名或测试通过宣称语义质量已完成。
