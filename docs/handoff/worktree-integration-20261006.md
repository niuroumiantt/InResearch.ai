# Worktree 整合交接（2026-10-06，m5）

## 目标与已定规则

用户授权把需要保留、尚未合入的 12 个额外 worktree 成果汇总到同一个 main。整合基线为已与 GitHub 核对一致的 `origin/main=2db7b5fd3855cf7d0cecf4c74b5bce4c5599bcf4`。使用 Codex 独立工作树与 `codex/integrate-worktrees-20261006` 分支；主目录仍在 `catalog-series-browser-test`，原 12 个工作树及其分支保留。

本次属于成果补充与历史候选归档。现行规范、实现、正式研究事实和验收映射未改变；旧提案和未完成试验不因进入 main 取得采用地位。未盘点或迁移 ignored 文件、原件、图文素材、密钥及运行数据库。

## 逐工作树结论

| 工作树 | 检查时 HEAD | 进入 main 的情况与本次处置 |
|---|---|---|
| ai-walle-20261001 | `87c23c8` | 补入原有 8 份文本/证据/交接文件；图片与 HTML 仍在原本机数据目录 |
| batch2-integration-baseline-20261003 | `1c41b91` | main 的祖先，已合入 |
| compute-catalog-20261002 | `ce8e531` | #305 / `4a1218d`；两端完整树相同，无缺失 |
| compute-catalog-batch2-20261002 | `8be1275` | #308 / `72705d4`；补丁等价，无缺失 |
| compute-catalog-release-20261002 | `9b9677d` | #306 / `1c41b91`；两端完整树相同，无缺失 |
| compute-receiver-baseline-20261002 | `d24b60a` | main 的祖先，已合入 |
| homepage-first-screen | `34e093b` | #310 / `1182923`；补丁等价，无缺失 |
| homepage-map-audit-20261003 | `63ce27a` | #312 / `b6a3ad8`；补丁等价，无缺失 |
| longform-rules-20261001 | `18097c0` | #300 / `9f1bc7f`；补丁等价，无缺失 |
| node-research-design-20260906 | `d15a3c5` | 补入原始 9 月 6 日候选提案；九主题后来已退役，不恢复旧实现 |
| nvidia-progress-live-20260927 | `428ea8b` | NVIDIA 主题由 #240 / `44557e5` 合入；尚缺的 Apple Vision 试验以历史补丁保存 |
| terminal-boundaries-20260914 | `d9477a7` | 未完成的 Terminal/Office 计划及工作快照以历史补丁保存；当前 l1_batch 和 Office 修复保留 |

12 个旧工作树的 tracked/untracked/conflict 均为 0；这不包含 ignored 文件。旧设计分支与当前 main 无共同祖先，ahead/behind 不能当成待合入功能数量，因此按具体成果、完整树与补丁等价核对，没有合并分离的旧历史。

## 入口与恢复

- 文章：[原归档说明](../research/2026-10-01/ai-walle/README.md)。原文及证据字节保持与 `87c23c8` 一致；2026-10-01 的“只推分支”描述是当时的历史边界，本次授权扩大到文本归档合并。
- 旧提案：[对象总览候选](../reviews/2026-09-06/2026-09-06_NODE_RESEARCH_OVERVIEW_PROPOSAL.md)。原文 SHA-256 `578ba099399c7667890185c7d3726d726a312b48955ac557612f3b074adb6d52`；其部分设计曾进入 07，9 月 28 日已被一棵树规范替代，替代链仍见 current_state。
- 两份工作快照：[历史补丁说明](../archive/2026-10-06/worktree-snapshots/README.md) 与 `patches.json`，保留来源/父提交、导出范围和内容摘要；来源 WIP 分支已存在于 GitHub。

## 验证与交付边界

三个补丁已在各自原始基线的独立临时索引中通过应用检查。文本/提案与原提交逐字节比对；现行源码、规范、测试及验收映射与整合基线保持相同。新增文件登记通过治理刷新（1090 文件）；严格数据校验 0 warnings、registry 344 对象/458 问题、asset-check、verify、indicators 均通过，核验/回填生成输出未混入提交。全量 1666 项单元测试串行运行通过（40.256 秒）；日志位于本机系统临时目录。浏览器、容器及合并状态以本轮 PR 实际检查为准。合并不等于清理工作树，也不代表旧 OCR/迁移已上线；本轮不操作 Spark 服务。

没有需用户决定的本轮整合项。以后若采用两份 WIP 的功能，按归档说明从最新 main 重新设计和验证。CI/合并状态可通过 `gh pr list --head codex/integrate-worktrees-20261006 --state all` 核对。
