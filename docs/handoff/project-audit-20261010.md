# 项目审查交接（2026-10-10，m5）

## 目标与授权
用户授权逐项审查架构/骨架/图与需求/数据库/供料/全站代码，修正并上线，重设计研究管理 dashboard。用户已恢复本轮 GitHub Actions 预算。已有研究发布保持原队列所有者，不新增重复服务或越过门禁。

## 实施与证据
- 主报告：docs/reviews/2026-10-10/project-audit/REVIEW.md；同目录源码扫描与 Spark/AWS 只读聚合。
- 修复 editorial 5,000 与 Reader 10,000 范围冲突；共用 read_scope，满容量重放/新增拒绝/破损输入回归。原件、阅读配方、优先级与采用门槛保持。
- facts 参数先解析，--help/未知选项不读全库，--summary 保留失败退出码；供料旧分类与包/feed原则、README失效命令修正。
- scripts/repository_research_dashboard.py + sync_repo_pages.py 生成六项控制室与来源摘要，原 material-flow API、管理员门禁、未知/陈旧/失败处理保持。手机与明暗已验，实际持久日更投影须另发布核对。
- 基线2,166单元通过；最终单元、全套CI与实际发布结果在本次PR/会话回执核对，不能用本记录的源码描述冒充上线。

## 继续与边界
1. 最终 head 完成治理/严格/registry/单元与完整选定CI，通过后受保护合并；核网站实际镜像/健康和私有日更投影。
2. Spark核源码版本、原有服务与实际editorial接收；不为本次修改启动第二个阅读/研究服务。
3. 37条旧事实原件SHA缺口、107项来源/时效任务、未接供应能力、正式答案和异机备份恢复仍未闭包，详见主报告；不伪造SHA或自动采用。

## 工作区与待决定
独立工作树 ~/.worktrees/inresearch.ai/project-audit-20261010，分支 codex/project-audit-20261010。主工作区和其它仓库原件/工作保留。无新增待用户决定事项。
