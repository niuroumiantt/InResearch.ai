# PR #417 冲突修复交接（2026-10-09，m5）

## 目标
保留 PR #417 的已审核研究增量及 main 后续记录，解除合并冲突。

## 已定规则
- 按记录 ID 核对三方差异；保留原文、模型审核、抽样及来源身份，不重新授予研究采用权限。
- 不触碰原发布工作树、私有审核产物和原件；必需 CI 与运行验收仍按现行发布流程执行。

## 进度
- 原 PR head：`3e620d123f72f910906a38ae721a501babaadfd8`；本轮合并基线：`c5a677f2e89a2c6fffbac78fba3b54c04b95d238`。
- 人工复核本 PR 仅追加 1 份文档、3 条证据、3 条陈述，无删除、既有记录修改或与 main 的新增 ID 冲突。主线全部旧记录的值和顺序保持。
- 两份派生清单从合并结果重新生成；治理检查、严格校验、registry 与 84 项研究相关单元测试通过。
- #412 旧 CI 在依赖安装约 13 分钟后触及任务整体 15 分钟上限；#417 旧 CI 被 Actions 预算上限拦截，所有任务未执行步骤。
- 修复提交需要新的 CI；本记录不声明合并或生产验收完成。

## 下一步
1. 账户侧解除 Actions 预算限制后，核对最新 PR head 的四项必需检查；主线若继续前进，重新检查冲突及治理清单。
2. 原发布 journal 当前为 blocked，保留原 commit；接续前复核本轮新 head 与审核上下文，显式接入原发布流程，避免把人工修改视为已验收。
3. 按原流程核对当前研究上下文，再合并、验收生产 adopted API 与 Spark 回执。

## 待用户处理
- GitHub Actions 预算阻塞；本轮没有修改付费预算或绕过必需检查。

## 入口文件与工具
- PR：https://github.com/niuroumiantt/InResearch.ai/pull/417
- 旧 CI：https://github.com/niuroumiantt/InResearch.ai/actions/runs/37818573655
- 本机研究测试日志：`/tmp/inresearch-pr-417-research-tests.log`（临时产物）。
- 发布入口：`src/inresearch/workflow/research_publish.py`；本机 journal 在 `~/.local/state/inresearch.ai/research-publish/`。
