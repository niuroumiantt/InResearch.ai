# 研究发布恢复交接（2026-10-09，m5 / m4）

## 目标
解除持续零交付的发布误阻塞，用网站支持闭包与Spark回执确认恢复。

## 已定规则
- 历史材料的封存正文直接进入资料基座；正式回答、项目/合同/容量与作者陈述分别采用。默认跳过PDF图片，纯图片材料由用户处理。
- 原件、旧报告、模型审计及事实版本长期保留。恢复不重启共享Reader/relay，不降低C3，不把模型成功计为上线。

## 10:19–10:21历史采样与实现
- 10:19–10:21：本批136份已完成；研究16069候选/17394证据，9159排队、58条/12批待发表，当前调用0。
- 十二批逐包对比：两批是正式采用过滤造成的来源误变化，包含已上线7条；六批原始来源和研究上下文未变；四批确有上下文变化。原始PDF未因采用过滤改变。
- 每批失败隔离，等待CI/部署的无变化批次让出调度；来源复验保留原封存候选/原文页。精确审核head已另行合并时仅恢复网站回执，仍需原审计与实际HTTPS闭包。
- infra分工基本适用。Spark可用内存约92.75GB；M4 64GiB且未配置本项目常驻研究worker，已实际执行隔离源码回归：1939项、2项跳过、41.34秒。M5发起远程Codex调用，本机核数不是模型推理容量。
- 单元、治理、严格校验/注册表、Docker实际只读与A→B→A运行数据保留、本地完整浏览器已验。代码PR429；当时GitHub Actions四项报告失败，账户预算需单独核对，不用本地结果冒充云CI。
- 以上是采样及本地实现验收，生产恢复必须另查版本、私有发布日志、逐批实际回执与M5新调用。

## 早期计划（历史阶段）
1. 将已授权修复发布到M5/Spark，备份队列后加载独立研究worker；确认旧7条回执，不作为本小时新增采用。
2. 逐批处理六个上下文未变包和四个待重核包，观察待发表背压是否解除。云CI预算不可用需沿已有明确授权的真实本地验收发布流程。
3. 后续降低每小包独立PR/全站测试成本，考虑统一发布批次；本次未实现合批发布或跨主机多研究worker，不宣称线性提速。

## 入口
- 现行规则：`framework/CURRENT.md`、`framework/09_software_contracts.md`、`docs/local_reader/SPARK_OPERATIONS.md`。
- 源码：`research_review.py` / `research_publish.py`；回归：`tests/unit/test_research_flow_recovery.py`。
- 私有实测与日志：m5 `~/.local/state/inresearch.ai/flow-audit-20261009/`；不进Git。
- 当前主要问题在调度与发布出口，增加M4模型调用无法代替出口恢复。无新增待用户决定项。


## 14:22首包实际恢复与14:29当前边界

本轮旧ready12来自两份旧导入PDF，共36条拟采用B档作者陈述，均不属于新接收的美国电力23来源。原7个PR的真实CI均是`browser(core_a)`中`part_dossier`超过300秒失败；validate/core_b/model_assets/storage通过，不是预算未启动或取消。独立M4精确原head完整案例52秒通过，集成最新TA11后67秒通过；未删除3D深链、拖动、主题、接管或资源契约，也未仅增timeout。五个prepared草稿的真实失败则是旧基线审核摘要/清单陈旧；不盲重算当前规范摘要，也不覆盖它们的未提交研究草稿。

首包PR453：batch `7fc9b1661eb4fe585ab3a284846261f2a6876cd8f9e73067548833d8575c8634`、原attempt-0003、bundle SHA `9dbf052fa56a3b845b68b1dc8d488b3cafa0b656d8c50024b172d036eed61afc`保持。head从35b7bb0f→fb31df97→b1c63a2f，仅追加文档1/证据5/陈述5，旧记录和answers不变。最终以31dcd368/.23为基线，14:13:55当前来源/上下文/封存审计/固定独立抽样全通过；治理1605路径、strict零警告、registry353对象458问题、资产、1970单元、29浏览器suites/32场景、隔离Docker A→B→A存储、派生verify/indicators全部真实通过。用户在本会话明确授权完整本地验收后不等CI合并上线；没有伪造CI成功或新增全项目免检接口。14:16:12实际merge d054f542与精确审核树一致。

M5维护使用独立锁与原worker锁，先一致备份12包journal/审计及5份dirty草稿。GitHub推送受已有keychain错误-25308阻塞，未调整凭据，改由M4已有访问更新原PR并用核验SHA的增量Git bundle同步M5。记录保留原PR/head/包/attempt及base_refreshes。维护keeper在14:22:26实际恢复LaunchAgent，新PID25958、原配置路径、clean d054源码且PR445当前上下文重新审核逻辑可见；至少一轮真实status为published。不能仅以bootstrap返回值宣称服务恢复。

Spark于14:20:09从clean a5b7d052安全快进到d054f542，正式knowledge SHA91bcbf0c…与生产ledger相同。独立Reader仍clean faa83480、相同PID1906533/NRestarts0、持久91 override字节相同；scope5907及SHA保持。此次快进没有Reader/schema/catalog/runtime实现改动，也没有重启Reader/relay或修改共享scope。之前Reader短暂退出与另一任务后续恢复按时点分开，不能归因于本轮publisher维护。

原publisher自然在14:22:44以精确d054镜像完成真实HTTPS五条正文/采用状态/引文/原件支持闭包，14:22:45 Spark记录published5/background1。14:25独立公网HTTPS GET 200，五条正文、source candidate绑定与支持闭包全真；实际API未序列化的审计字段由当时部署curated ledger和稳定ID链另行绑定，未把字段缺席冒充API输出。proof SHA de4fa720…、正式knowledge SHA91bcbf0c…与Spark一致。[完整真实回执](../reviews/2026-10-09/research-publication/pr453-actual-closure.json)保留原CI观察、精确本地验收、服务恢复、源码同步、HTTPS与published。

14:29:37对原12包重新只读复验：published1、review_ready8、reviewing1、queued2。剩余11包中5包当前上下文仍一致，6包已变化；正常publisher已把部分旧PR按既有revalidate重新排队。每个后续实际采用都会改变相关问题/对象的上下文，必须逐包fresh复验，不复用首包或13:46的true。[逐包当前回执](../reviews/2026-10-09/research-publication/old-ready12-followup.json)只证明该时点，不是后续合并授权摘要。继续维护必须恢复原publisher并实核新PID/路径/状态，不留下停服。

美国电力原23份于13:35的正式支持C3为0，13来源566条资料可读和844候选分开计量；首包5条只计旧ready包恢复，不记入原23采用。现行流程继续原23逐篇阅读、C3、独立抽样与逐条支持闭包，不关闭问题或顺带改价格/GW/合同字段。[专题阶段](../reviews/2026-10-09/research-publication/original-23-stage.json)与[专题交接](us-datacenter-power-20261009.md)分别保留具名来源和缺口。

当前下一步：先复验仍ready的包；来源或研究上下文变化经既有revalidate保留旧attempt/PR后重新C3，prepared草稿在保留旧diff/审计的独立树集成已审阅最新基线再验；完整适用本地验收后精确head合并，按既有来源同步→实际HTTPS→Spark published顺序闭环。没有新的待用户决定项。
