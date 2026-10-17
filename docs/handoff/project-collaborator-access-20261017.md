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

## 当前状态（2026-10-17 10:26 北京时间）

- 用户此前选择保留 PR 暂不上线，随后明确告知已合并并要求继续。PR [#969](https://github.com/niuroumiantt/InResearch.ai/pull/969) 已于 02:14:39Z 合并为 `07624b45fbcb9241f249f5a95211cc918a98e2d3`；本任务没有执行该合并。合并不代表已经部署。
- 网站仍实际运行 `d9a9039cf43a18623174667d33fa5d64c1e77456`，镜像 `sha256:0c30173250aa7871c33f03ba6f1c47821c8ba47b856dae0a0efe367845ad7bef`，健康、无本轮容器重启；公网 tasks 页面尚无新工作台组件。所有者账号存在且为 admin，尚无 collaborator 账号。
- `inresearch-only-deploy.timer` 于 02:02Z 被正在执行的园区任务暂停，以保护城市数据发布及随后性能修复的部署窗口。实际暂停回执在 AWS `/home/ubuntu/.local/state/inresearch.ai/campus-deploy-pauses/campus-city131-autodeploy-timer-pause-20261017/pause-receipt.json`。保留其暂停状态，不与该任务并行换容器或重启 Spark。
- Spark 常驻 checkout 为 `9f4bcb70`；Reader／research-review 服务运行中，material-intake 暂停属于园区任务的现行调度；editorial 最近一次因 HTTP 读取超时失败。不能将常驻 checkout 当作全部工作进程的代码版本，也不能将服务运行当作业务全量成功。本任务没有修改其源码或服务。
- 合并后 HTTP 的 PPT MIME、两条下载路由及登记文件摘要存在治理漂移。逐项复核并实际下载两份 PPT，MIME 与全部原字节一致。园区任务的 [PR #971](https://github.com/niuroumiantt/InResearch.ai/pull/971) 候选 `91ac1e2cbb62992a6057a0e33e4833f7b6b292c4` 已包含 #969 及登记修正；在本任务独立工作树核对通过，无另写产品修复。
- 该共同候选的完整单元测试 **3,012 项通过（139.467 秒）**，治理 2026.10.17.2／2,804 文件、严格数据 0 warnings 和 registry 通过；候选上的真实独立登录、授权撤销、个人工作台、上传及审批浏览器场景通过。此前在合并版本上导航／身份外观回归、真实 Docker 只读根与 A→B→A 数据保留、构建缓存与秘密隔离也通过。容器测试未在新的 city cache 候选上重复，不冒充全部 CI。
- Actions 仍因预算限制零步骤失败，合并提交 run `38994151351` 的 scope annotation 再次确认同一预算原因；完整远端 CI 尚未通过。本轮没有调整预算、仓库权限或保护，没有创建员工、写入生产提交或审阅记录。
- 用户现已明确授权“允许，协调共同部署”。已向“启动 Spark 27B 研究任务”（01a14566-ce70-7e31-ae7a-26db9c7298f9）发送共同部署协调消息，交付精确候选、验收结果和暂停边界，保留该任务为唯一部署执行者。本任务随后只读核对，网站仍是 d9a9039c、timer inactive；对方仍在修复研究窗口输出截断并准备 CI 接入，尚无新的部署完成回执。未创建自动轮询或后续计划。
- 本轮原始验收日志和状态：`~/.local/state/inresearch.ai/project-access-release-20261017/`；其中 `live-smoke.cjs` 已备好真实公网所有者登录、未登录边界、资源源字节、成员页和个人／团队／审阅页验收。仅在部署含 #969 的版本后执行，凭据只经内存传递，不创建员工、材料或审批。该脚本尚未在新生产版本执行。工作树分支现为 `codex/project-access-release-receipt`，以共同候选为基线保存本次交接；主工作区未改。

## 后续入口

1. 先核对园区任务的发布窗口、#971 和 Actions 的最新状态。跨会话协调已获明确授权并已发送；共同发布由园区任务这个所有者执行。不要直接恢复其暂停 timer 或并行换容器。上线后核对包含 #969 的实际镜像、公网新组件、真实所有者登录和权限边界；此项尚未完成。
2. 所有者进入成员与授权，逐人创建账号、设置范围，把初始密码单独交本人。姓名、账号与审批范围由所有者决定；代码发布不等于已授权员工。
3. 新项目须先登记真实项目目录；旧匿名材料归属迁移须单独核验，不能仅凭姓名自动归入。

规范入口：`framework/05_interface_system.md` 的“项目协作者与授权”；实现：`src/inresearch/interfaces/project_access.py`、`auth.py`、`http.py`；验收：`tests/unit/test_project_access.py`、`tests/project_access.cjs`、`tests/research_tasks.cjs`。
