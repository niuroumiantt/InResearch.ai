# 持续研究核验执行（2026-10-08，M5）

用户明确授权开始Codex研究核验执行。实现独立 research-review Spark队列与M5 research-publish，保持原Reader/原件/正文模式和C3门槛；此次是补充执行，不改骨架或以阅读完成声称事实采用。

核验复用当前封存报告，重核原件SHA/文字层连续引文/邻页，并重新语义匹配现行根问题及源对象的问题目录；Reader原问题仅是提示，匹配不发明问题。core_review实际审核及固定ceil(10%)独立复核保存请求/响应/模型摘要。原importance≥8或新的A条件不降档；背景、补证、专门字段与待所有者各自留存。可提交背压与超预算拆分保留上下文及旧尝试，首次仅追加作者归属陈述/预测，不更新GW/项目/合同/模型输入/正式answer。

发布器建立独立Git工作树，经治理、严格校验、registry和四项CI才合并；合并前上下文改变重新核验。AWS运行容器里已有管理员临时会话验收真实HTTPS采用API，逐条正文、状态和支持闭包成功才回写Spark published。不打印凭据、不改账号、不重启共享Reader。所有审计、数据库和原件在Git外长期保留；只读计数随既有快照上网页matching。

代码：src/inresearch/workflow/research_review.py、research_publish.py；两个manage.py子命令，Spark服务和M5 LaunchAgent模板。唯一现行操作指南见docs/local_reader/SPARK_OPERATIONS.md，规范04/05/08/09及注册表、验收映射同时补充。

验证：13项新增C3/需求/抽样/重放/背压分拆/只读计数/CI资格测试；全套1880测试通过。governance check、strict validate与registry通过。修复已有保留审计的macOS只读WAL快照重开：仅对新一致备份切到DELETE journal，独立复制main数据库只读可用、原源库仍WAL，原件保留。

真实试跑：Spark material-reviews/research-verification已有PJM报告核验队列，实际Codex调用、背景与A分流、两组独立抽样拒绝均留档。拒绝原因是有原文支持但与所选工单关系不足，未正式采用。首批通过及部署回执在M5私有state/research-publish与Spark上述永久目录继续登记，不能用本交接证明运行成功。

生产验收：PR352四项CI通过并合并，AWS与Spark运行6a95f0c2；Spark独立核验服务PID2035329，M5发表LaunchAgent常驻，原Reader未重启。首条PJM采用经真实HTTPS采用API和支持链验收，2026-10-08 08:28:42北京时间生成website-proof、08:28:43回写Spark published。运行证据保存在两端私有目录，交接文字不代替后续实测。

收尾修复：实测供应API仍显示not_started，原因是候选接收白名单丢弃research_verification。接收端仅保留已计量的状态、非负整数计数和时间，过滤审计原文/路径/伪采用字段；新增HTTP接收→读取和接收→供应投影回归。另将发表同步限定到main且禁交互提示；恢复已有发表日志先于新队列轮询，保留dirty源码保护。并行主分支更新自动合并只重建两份派生登记文件，语义内容冲突保留待审；更新head须重新CI，通过真实Git并行写入/源冲突/dirty三项测试。因本轮修复与发表PR355并行，M5发表器短暂停止后须恢复，Spark Reader及核验服务继续运行。此修复上线后须另验matching的实际快照，不能只凭测试认为已显示。

22来源绑定、A委托、数字/项目专门核验仍各自推进；已核验的作者观点不证明其因果判断已被独立行业来源证实，首通道不是全库语义保证。若单项上下文超预算、原文不匹配或抽样拒绝，仍保留待补证，不承诺整批时限。

首个真实通过：PJM报告rev-5878d30d4bbd4d518ebd0682843f1f1e的chunk1 claim8。原文第2页连续引句，7分B及固定100%抽样（1项集合）独立通过；限定作者判断“容量采购一年期合同、履约准备期和并网缓慢限制新增电源供给”，关联OBJ-grid-supply/interfaces和M04-Q01，尚未关闭工单或修改容量。复核保留第3页另述紧急合同延至2043年的边界，不泛化一年期。采用包SHA bcf2ff51c69cba6834676eb8db5d1af672fd5f9cc1adb56e00973d02eb50bae7。网站正式记录adoption:review:aaf62f56d566e79350500469可在https://inresearch.ai/node.html?id=site%3Agrid#evidence查看。首项随实现PR提交，后续使用常驻发表器。
