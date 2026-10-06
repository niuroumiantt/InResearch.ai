# 旧工作树候选补丁（2026-10-06，m5）

> HISTORICAL · 未采用的试验与未完成迁移。补丁中的规范、实现、测试和计划均为原始历史内容，不是当前执行指令。现行规则仍以 [CURRENT](../../../../framework/CURRENT.md) 登记的源文件为准。

本轮用户授权将需要保留的 worktree 成果汇总到 main。两份工作快照与当前实现不兼容，故保存可恢复的原始补丁，不将其激活为运行代码。每个补丁的原始父提交、来源提交、导出范围、字节数和 SHA-256 见 [patches.json](patches.json)。来源工作树及分支继续保留。

## Apple Vision OCR 试验

`macos-vision-ocr-428ea8b.patch` 保存 `428ea8b` 相对父提交 `e5138ce` 的全部 11 个变更项，包括 Python/Swift 实现、测试和当时拟议的规范改动。

- 当前 08 要求显式配置 `ocr` 角色，当前已采用的缺页补读为 Claude `gap_ocr`。未发现自动 Apple Vision 回退已经采用的独立依据。
- 旧试验在视觉客户端缺失时自动回退，包括 `explicit_ocr=""` 的显式禁用状态。
- 数字消歧仅检查差异 token 是否出现在同页 PDF 原生文本，不能证明文本层完整及数字对应；现行规则仍要求双读数字不一致时阻断。
- 原试验的一页材料记录不能证明密集表格、中文或端到端 reader 的准确性。它依赖 macOS、swiftc、Vision 与 AppKit。

如以后采用，应从现行显式角色配置和阅读契约重新设计，再核对原件及适用场景；本次归档不授予 OCR 执行权限。

## Terminal / Office 迁移候选

`terminal-boundaries-plan-7e35305.patch` 保存原计划、审计脚本及 scope。排除当时生成的 `file-plan.csv`、在册报告与仓库清单；原计划中引用它们的文字原样保留，仅反映当时盘点，不能冒充本次完整盘点。

`terminal-office-wip-d9477a7.patch` 保存其后工作快照的全部 18 个变更项，包括 Office 文件移动、消费者改动、候选 `batch_reporting` 及测试。

- 原 PLAN 明确标注 unfinished，并记录选择逻辑迁移曾因破坏测试注入入口撤回。
- 当前 09 指定 `workflow.l1_batch` 为唯一实现，旧 `batch_reporting` 的六个功能已由它承担。
- 旧 Office 正文缺少 main 后续的 PPT limit 透传和 XLS/XLSX/PPT truncated 修复。
- 当前新增的 `l1_batch`、`reading_stages` 仍消费 `adapters.office`；旧补丁没有迁移它们。

如以后采用 Office 归属迁移，应移动当前版本并重新清点消费者，保留后续修复；不要将旧文件正文覆盖当前实现。

## 恢复与验证边界

补丁使用 `git diff --binary --full-index --find-renames <父提交> <来源提交> -- <范围>` 导出。已逐项重新导出比对字节及 SHA-256，并在独立临时索引中从记录的父提交通过 `git apply --cached --check`。这证明补丁在其原始基线上可应用，不证明可直接应用于当前 main 或历史试验已经通过验收。

对所归档主题的新增内容完成硬编码密钥、私钥头及带凭据 URL 检查，未发现匹配。未审计整条旧分支、ignored 文件、运行数据库、原件或本机图文资产；这些内容不进入此次归档，也不随整合删除。
