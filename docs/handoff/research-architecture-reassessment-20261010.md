# 重新审查与 M1–M5 整改交接 · 2026-10-10

用户授权重新审查六项、改代码、整改目录命名、重做 dashboard 并上线；随后确认按 M1–M5 执行。不恢复此前审批，不再把观察当作完成。

## 当前入口

- framework/CURRENT.md / current_state.json 2026.10.10.76；详细规范仍由各主题唯一源维护。
- docs/reviews/2026-10-10/architecture-reassessment/{PLAN,REVIEW}.md：里程碑、独立六项结论和未覆盖项。
- 工作树 /Users/m5/.worktrees/inresearch.ai/architecture-reassessment-20261010；codex/architecture-reassessment-20261010 从 f87f780d 建立。主工作区未切换或覆盖。

## 已完成实施与本地验收

M1 状态、目标/问题/供应方/执行机绑定及当前阅读版本；M2 请求合同与部件需求摘要；M3 研究就绪度状态板和每日生成器依赖；M4 目录职责与三个模块实际改名、无用函数/旧扩大认领分支删除、失效指令与文件句柄修复、严格事件卡校验、最长部件交期正名。

全量单元2179通过后补充1001条阅读查询/未知状态测试，相关38项再验通过；part_dossier全场景、supply/repository_pages/dashboard、严格校验、registry、deliveries与治理已验。最终CI仍须在最终head全套通过，不能用本地结果替代。三库一致备份与五原件样本跨机到m5，SHA/integrity/表计数通过；不是完整档案DR。

## M5 发布收尾

沿现行两必过/管理员保护合并，不绕过CI；AWS精确健康镜像、Spark干净fast-forward、macmini已合并runner和17载体私有投影分别核对。无需重启无关Reader/审核或另建发布所有者。生产状态、投影优先级及HTTPS管理员回执不能用源码代替。

真实部署结果单独保存在m5私有 ~/.local/state/inresearch.ai/architecture-reassessment-20261010/RELEASE.md/json；检查实际文件与网站后判断是否发布完成，本交接不提前声称已上线。

## 保留缺口

37条历史事实原件SHA缺口（facts --summary独立复核，不能造哈希）、四能力171行未接通、17个模型输入未验证、214行待审问题关系、运行/权利来源与完整功能拓扑、全档案异地备份和全服务RPO/RTO。代码明确显示并约束这些缺口，没有补猜研究证据。原件、数据库、审计、未合并分支不随清理删除。
