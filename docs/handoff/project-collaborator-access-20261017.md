# 项目协作者第一版交接（2026-10-17，m5）

## 目标与已定规则

用户已授权实现独立登录、由所有者指定项目可见范围和 approve 权限、个人工作及团队进展；复用上传和审阅，保护其他更新，不另设审批步骤。

- 第一版接入现行全球园区普查 mission。账号仅存私有运行区；不创建真实员工账号，不改 GitHub 权限或仓库可见性。
- `collaborator` 首次改密；稳定账号 ID 绑定提交。所有者可设置项目／园区前台开关、期限、提交及审批工作包，或停用。
- 新上传要求登录；本人记录与原件隔离。新回执和批次恢复同时校验身份；旧匿名回执及在途分析保留，不按同名认领。
- 委托审批逐件限域，禁止自批；审批沿用 SHA/CAS、封存和现有分析／发布验收。协作者不改共享派工、运维、研究 C3 采用。
- 会话在改密、改角色、改名和授权修改后失效；同名重建账号不能沿用旧会话或继承材料。

## 实现与验收

- 所有者入口 `/admin/project-access.html`；登录后 `/tasks.html` 默认“我的工作”，保留“团队进展”和“提交与进展”；授权园区前台由同站登录读取。
- 新增真实 HTTP 权限回归和 `tests/project_access.cjs` 浏览器场景，已加入默认全套分片。既有上传回归改用独立账号，并保留匿名只读与历史恢复验收。
- 本地完整单元回归 3,004 项通过，导航修正后的相关 32 项也通过；已验证实际上传、单份／批次审批、撤权／到期／改密、跨账号原件／回执、320/390/1440 明暗；治理、严格数据、registry、verify、indicators 和资产检查。最终精确提交的全量 CI 及生产回执另以 PR／运行状态为准，本文不代替上线证明。
- 独立工作树：`~/.codex/worktrees/project-collaborator-access/inresearch.ai`，分支 `codex/project-collaborator-access`。没有改主工作区的未提交内容，没有重启 Spark 或重排研究队列。

## 当前外部阻塞

- PR： https://github.com/niuroumiantt/InResearch.ai/pull/969 。GitHub Actions run 38989819309 在运行步骤前被账号预算拦住，原提示为“The job was not started because an Actions budget is preventing further use.”。未绕过 CI，未合并／部署本功能。
- 仓库当前已为 PRIVATE（他人修改，本任务未更改）；GitHub 对当前套餐返回私有仓库分支保护不可用。仍执行仓库约定的全量检查门槛，不能据此跳过。
- 只读核对：网站健康且运行 389a12ea；Spark 9f4bcb70，现有 Reader／研究审核服务运行中。本任务没有重启或替换 Spark。

## 后续入口

1. 完成最终 head 的 `validate`、全浏览器及 storage-container；按现行流程合并，核对主站实际版本／健康。不得绕过失败检查。
2. 所有者进入成员与授权，逐人创建账号、设置范围，把初始密码单独交本人。姓名、账号与审批范围由所有者决定；代码发布不等于已授权员工。
3. 新项目须先登记真实项目目录；旧匿名材料归属迁移须单独核验，不能仅凭姓名自动归入。

规范入口：`framework/05_interface_system.md` 的“项目协作者与授权”；实现：`src/inresearch/interfaces/project_access.py`、`auth.py`、`http.py`；验收：`tests/unit/test_project_access.py`、`tests/project_access.cjs`、`tests/research_tasks.cjs`。
