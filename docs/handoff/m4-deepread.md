# M4 深读交接（更新于 2026-09-28，机器 m4）

## 目标

在 M4 隔离数据根上，用 Claude CLI 深读 Spark 优先级 ≥7 的文档，产出只作候选的阅读报告；是否发布到网站候选区由用户决定。

## 已定规则（用户确认过，不要再问）

- 不发布（不跑 `manage.py publish`），不写 Spark 台账，不动 Spark 原件。
- 默认 Sonnet 5，最多 2 并行；b3ff 用 Opus 5.5。按优先级从高到低读。
- 输出上限 4096 是冻结配方的一部分，不改配置；出现时只记一笔。
- 周配额 90% 为停止线：跑完当前块即暂停，重置后（resetsAt+5 分钟）续跑。
- 只在以下情况打断用户：摘要超长或缺 claims（附 CLI 报错原文），或同一文档失败 ≥2 次。
- 7 份 .md（项目自有模块草稿和生成报告）不读，列入清理清单；Spark 认领下限已由用户设为 10，Spark 不读这批。
- 48c8、ce50、ea7d（OCR 缺页超限而阻断）先不动。

## 进度

- 33 份中 30 份完成，每条入库引文都通过逐字核对。其中 b3ff 由 Opus 读，其余由 Sonnet 读；b434、fedd、b6b6、dd2d 是批次后补入的 Spark PDF。
- 2026-09-27 晚：c2d9、ad60 在 #246 后重试完成（13/13、24/24），没有块触发 `--effort low`（`_model.effort` 均未出现）。
- 2026-09-28 晨：b6b6、dd2d 在 #253 后重试完成（42/42、22/22）。b6b6 剔除 2 条主张（`report.coverage.dropped_claims=2`），两条引文都在第 0 块跨过首页作者侧栏（姓名、电话、邮箱被 pdftotext 插进正文句中）；dd2d 无剔除。
- 阻断 3 份：48c8 缺第 20、27 页；ce50 缺第 2、19、33、43、47、51 页；ea7d 缺第 7、23、38 页（`ocr_gap_pages_exceed_limit`）。
- 截至 2026-09-28 07:14，周配额 0.88，重置时间 2026-09-28 12:00。

## 下一步

1. 等用户决定：是否发布这 30 份候选阅读到网站候选区。
2. 等用户决定：48c8、ce50、ea7d 的缺页怎么处理（提高缺页上限、重做 OCR 或另行处理）。
3. 可选：首页双栏（作者侧栏）改为分栏抽取，找回 b6b6 被剔除的两条事实（2030/2050 年用电增速预测 5.6%/3.2%，中国占全球光伏产量 80%）。
4. 清理候选：7 份 .md 的处理由用户决定。

## 入口文件与工具

- 数据根：`~/.local/share/inresearch.ai/m4-deepread-pilot/`（Sonnet，含 `catalog/catalog.sqlite`、`artifacts/`、`extracted/`）；`~/.local/share/inresearch.ai/m4-deepread-opus/`（b3ff）。
- 状态目录：`~/.local/state/inresearch.ai/m4-deepread-pilot/`
  - `deepread6.sh`：带配额守卫的运行脚本，最近一次使用；改其中的 doc-id 列表即可复用。
  - `claude-logged`：CLI 包装，出错写 `cli-errors.log`，每次调用写 `usage.tsv`（周/5 小时用量、费用、resetsAt）。
  - `4096-limit.tsv`：4096 输出上限事件台账。
- 模型配置：`INRESEARCH_MODEL_CONFIG=~/.config/inresearch.ai/models.m4-deepread.json`（claude_sonnet 并行 2，命令指向 `claude-logged`）。
- 清理清单：`~/.local/state/inresearch.ai/cleanup-candidates-20260927.tsv`。
- 常用：`python3 manage.py reader --data-root <数据根> --state-root <状态目录> --repo-root . retry --doc-id <id>`；查状态用只读 sqlite 查询 `reading_runs`、`jobs`。
- 已知限制：reader 不保存被拒回答和逐次拒绝原因（CLI 以 `--no-session-persistence` 运行，`ModelOutputError` 无消息），排查只能靠事件日志和重放校验。
