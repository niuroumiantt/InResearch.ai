# 研究发布阻塞恢复交接（2026-10-09，m5）

## 目标与已定规则
让来源完整、当前上下文有效的核验结果实际进入网站，独立失败不能冻结全队列。用户已授权修正、合并和发布；保留原件、旧尝试与审计，不恢复图片 OCR，不重复请求每批批准。心跳只盘点，不代替修复执行。

## 实现阶段已验收
- PR429：来源复验保留已采用项；逐批失败隔离；精确已合并 head 仅恢复真实回执。
- PR447（已纳入 PR445）：完整 core 分为两组，以聚合门禁保留全部 31 个浏览器场景。源码 0569c2a8 实际六项云端检查通过，两组用例耗时 378／539 秒；本地全部场景及实际 Docker A→B→A 持久化通过。
- 新发表 attempt 开始前保存完整旧 journal 和实际 SHA 引用。治理读取同一已审阅 suite 清单；没有漏测或绕过 C3/发布门禁。
- PR445：真实 CI 失败恢复；当前上下文变化重排；仅合并不变原记录及独立追加 ID，修改/删除/冲突 ID 仍需审阅。7b10f399 的六项云端检查和 1,951 项测试已通过。

## 发布阶段（12:43 验收）
- PR445 精确审核提交 6be7fc4f 的六项云端检查全部通过；实际 main 合并提交 14c4c6e3。AWS 运行同一提交镜像 healthy，Spark 源码同提交；PR447 修复通过该组合发布进入 main。
- HTTPS 逐 ID 核对八条正文、采用状态、引文与完整原件支持全部通过。网站正式研究陈述 151→159，自动核验交付 132→140。属于研究陈述，不改项目或 IT GW。
- 两批分别保存真实 website-proof，Spark published 回执于12:42:47／12:43:03完成。M5发布器已在干净、已批准的独立运行工作树恢复running；Reader和独立研究服务active。最终私有审计 final-delivery.json 核对八条ID、两个回执与实际运行状态。
- 五个过期旧批次已按新上下文重排，旧尝试/分支保留；源缺失、独立复核和专门字段等真实待核分别保留。

## 继续入口
1. 核对持续发布的新批次精确 head、全部检查与实际 main；当前修复已发布。独立工作区保留并行改动，不能覆盖其他活跃工作区。
2. 按既有 AWS 独立部署服务发布；核对运行镜像、HTTPS 八条 ID、Spark 回执，再恢复 M5 发布器。保留旧 journal／分支；只重启必要发布器，Reader 和 relay 保持。
3. 核对 M5 配置中的实际 repo、干净源码及原件封印。未授权的其他聊天不发送消息；需要看进度用紧凑 wait_threads。

规则：framework/CURRENT.md、09_software_contracts.md、docs/local_reader/SPARK_OPERATIONS.md。代码：workflow/research_publish.py、tests/browser_suites.cjs、interfaces/verification.py。运行审计在 m5 私有 ~/.local/state/inresearch.ai/block-recovery-20261009/；正式队列和全部原件仍在 Spark，私有数据不入 Git。无需新增用户决定。
