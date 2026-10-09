# 研究 PR 积压修复交接（2026-10-09，m5）

## 目标与已定规则
处理用户截图中的 #431/432/433/434/435/437/440/443，保留原件、历史审核、既有事实和其他任务的源码。来源/现行上下文复验、真实 CI 与网站支持闭包分别验收，不把关闭旧 PR 当正式采用。

## 已完成
- #443此前已合并。#434的5条和#437的3条通过原封存包复验，经既有promote追加；PR445精确head `6be7fc4f0259f484bd1393469f1006eeae42b2c0` 全部CI成功，合并 `14c4c6e3c0661c677245985e3c10b6abe21959f0`。
- 8条在实际HTTPS采用接口的正文/采用状态/逐条引文/原件支持闭包验证通过；04:42:45/04:43:02 UTC两批均published并送达Spark。#434/437关闭，原PR/head与统一发布提交的关系保存在逐批consolidated-release.json。
- #431/432/433/440上下文变化已重排C3并关闭旧PR；#435在上述8条入库后上下文变化，同样重排并关闭。重新审核可产生新的暂缓/待发布结论，不预报全数采用。
- blocked批次复验后，原head四项CI恢复时继续正常准入；上下文变化则重新审核。并行研究只自动合并无编辑/删除/ID冲突的稳定ID追加；其他冲突保留待审，新head重跑CI。
- 纳入PR447的完整网页分组和不可变旧journal备份，全部用例/双密度保留。保留并行TA-09验收、来源URL侧车和电力专题更新。
- 最终1963项单元测试通过；governance、strict校验（0warnings）及registry通过。两组核心网页、模型资产、存储与validate实际CI全部通过。

## 运行与入口
- M5 LaunchAgent `ai.inresearch.research-publish` 已恢复running；独占源码 `/Users/m5/.worktrees/inresearch.ai/research-publisher-runtime-20261009`，配置 `~/.config/inresearch.ai/research-publish.json`。初始执行版本14c4c6e3；不要清理这个有服务引用的工作树。
- 真实验收时AWS镜像 `inresearch-app:14c4c6e3c0661c677245985e3c10b6abe21959f0` healthy；Spark已继续到包含该修复的f66db02e，Reader/研究审核均active。后续并行更新由既有独立部署推进，不将这里的时点当长期同步状态。
- 私有审计 `~/.local/state/inresearch.ai/research-pr-backlog-20261009/`：原journal快照、源包复验、CI/合并证明、两批accepted-proofs.json、原配置/plist备份。逐批完整审核及网站证明在 `~/.local/state/inresearch.ai/research-publish/<batch>/`；原工作树与分支保留。
- 当前唯一操作规范：docs/local_reader/SPARK_OPERATIONS.md。下一会话先核对当前journal、GitHub和服务，不重新采用已published的8条；人工新结论仍按现行C3处理。

## 收尾治理修正
PR444合并后CURRENT/current_state的两项已审阅摘要仍指向旧版。人工核对v2.7文风、替代链、归档与测试映射时，最新并行PR451已完成修正。跟进最新main后复验治理；本交接仅登记处理结果，不再重复修正。

## 待用户决定
无。此前临时协调暂停的问题不再阻塞；未向其他聊天发消息，也未暂停其工作。
