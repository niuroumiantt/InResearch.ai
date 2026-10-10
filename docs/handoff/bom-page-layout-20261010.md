# 爆炸图 2D 排版交接（更新于 2026-10-10，机器 m5）

## 目标
总图说明流程、框架与组件后再分拆，修正整页逻辑和右侧大面积留白。

## 已定规则（用户确认过的，不要再问）
- 本次用户明确要求：页面排版调整、逻辑线清楚、所有分拆图前有总图。
- 实现：五系统运行关系 → 系统 → 功能链段 → 设备与组件 → 点选图册/档案。功能关系不是实际项目串联图；IT 四子系统并列，替代方案保留。
- 现行依据：`framework/05_interface_system.md`「爆炸图 2D」。不恢复原常驻空侧栏。

## 进度
- 已完成：`3ee313de`，独立工作树 `/Users/m5/.codex/worktrees/bom-page-layout/inresearch.ai`，分支 `codex/bom-page-layout`。
- 草稿 PR：https://github.com/niuroumiantt/InResearch.ai/pull/590 。未合并，未部署生产。
- 已通过：新布局六宽度 × 浅深色与键盘/锚点；system_atlas/scale_atlas 的 views 和 downloads（96/12 次原字节下载）；technical_atlas；全站 ui_skin；14 项规范/骨架单测；严格数据校验 0 warnings；governance 检查。
- 本地预览 `http://127.0.0.1:53239/bom.html` 由当前会话启动，仅进程存活期间可用；截图/日志位于 `/tmp/inresearch-bom-layout-qa/` 与 `/tmp/inresearch-bom-*.log`，属于临时验收资料。
- 主工作区 `/Users/m5/code/inresearch.ai` 的原分支及未跟踪研究资料未修改。

## 下一步
1. 审阅实际页面/草稿 PR；如用户要求继续修改，在此分支实现并复跑相关验收。
2. 合并发布需基于当时最新 main 处理版本/登记清单冲突，重新审阅摘要；不能拿本地测试声称生产上线。

## 待用户决定
- 新排版的审阅反馈；本次没有执行生产发布。

## 入口文件与工具
- `web/pages/bom.html`、`tests/bom_layout.cjs`、`tests/browser_suites.cjs`。
- `framework/current_state.json` 与 `framework/verification_contract.json`：本批版本 `2026.10.10.68`。
- 浏览器依赖：`NODE_PATH=/Users/m5/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`，运行 `node tests/run_browser.cjs bom_layout system_atlas scale_atlas technical_atlas ui_skin`。
