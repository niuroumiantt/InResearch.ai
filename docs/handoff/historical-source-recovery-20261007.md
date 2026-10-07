# 历史日报来源追补交接（2026-10-07，m5）

## 目标与已定边界
追补 10:34 北京时间基线的 153 条缺网址事件；原 HTML、原引用号、来源冲突及旧事实保留。标题匹配只作查找线索；补链接不授予整条事实核验或 C3 采用。主工作区与 Reader 未重启或改动，本次没有正式容量更新。

## 已完成
- 六批 **93 条**、27 个 SHA 验证包，均有 Spark `daily-receive` 的真实 `indexed_candidate` 回执：9 / 25 / 18 / 12 / 25 / 4 条。88 条恢复原发布网址，5 条采用可靠转载；组合事件可能仅核对明确子项，逐条说明保留未覆盖部分。
- 全台账 318 条中 258 条有实际网址，缺链 **153 → 60**。剩余 20 条 `source_pending`、40 条 `source_missing`；不把只有来源名称的记录算作有网址。
- 核对 153 条原 HTML SHA、20 份 sources 侧车、指定 iNews 只读快照全部 404289 条标题及 3968 份正文。快照 SHA：`2865c840546aa9c298ba0bda13b84431d375b3586d3877544d97a8261015e399`。未修改快照。
- 网页 `/supply.html?day=2026-10-07#matching` 实测显示 60 条待补；“来源齐全的事件”显示 212，属于页面去重交付口径，与原始台账 258 不混算。网页截图、逐项结果、正文/raw SHA 和回执见下列证据目录。
- 接收与 publisher 固定运行版本 `67662877bd8d4f22c3b4cd5ad75d94a5b6fdec18`；仅触发既有 publisher，同步成功。Reader 保持原 checkout `85f5eb9fb1ec8726335500444a546680fb1fce46` 且服务 active。

## 下一步与具体缺口
1. 读 `recovery-results.json` / `.md`，按每条 `gap`、`next_action` 和原事件关键文字取得原件；不能将未批准标题候选直接绑定。
2. 优先 FERC `20260929-3099`（JS 空壳）、参议院 57–43 投票原件（AP 403）、Mesa County 暂停令（转载与原报 403）、波兰 CPPC 协议（TLS）、Ascension 草案（429）、韩国中央日报正确原页（DNS）。拒绝的内蒙古/雅安主体错配及泰国 8.8GW→100MW错配保留记录。
3. 已补网址仍需处理各条范围差异：如 Lancaster 第二期新增 84 台而 156 是跨期总数、Virginia 原文为 by-right 审批、韩国“AI第三Campus”为公司名。公开导语、可靠转载与实际原文分别注明；原公告未读的子项继续补证，不以部分正文作整条通过。

## 入口与验证
- Spark 永久证据：`/home/spark/.local/share/inresearch.ai/material-reviews/source-recovery-20261007/`；逐事件包：`/home/spark/.local/share/inresearch.ai/incoming/source-recovery-20261007/`。JSON 中 m5 文件路径在永久证据根下有相同相对路径；接收回执提供 Spark 包绝对路径。
- m5 证据：`/Users/m5/.local/state/inresearch.ai/source-recovery-20261007/`；工作树：`/Users/m5/.worktrees/inresearch.ai/historical-source-recovery-20261007`，分支 `codex/historical-source-recovery-20261007`。
- 现行依据：`framework/06_acquisition.md`、`docs/local_reader/ACQUISITION_OPERATIONS.md`；本次仅新增阶段交接，未修改规范、操作指南、验收测试或验证合同。
- 提交前验证：包 SHA / 原 HTML section 与事件 ID / 回执与权威台账网址逐项对账；`governance --refresh` / `--check`、`validate --strict`、`registry`、既有 `test_daily_bundle.py`。
- 无新增待用户决定事项；未恢复的 60 条有明确补证入口，不能称全部 153 条已恢复。
