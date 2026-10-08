# 持续研究核验执行（2026-10-08，M5）

用户明确授权开始Codex研究核验执行。实现独立 research-review Spark队列与M5 research-publish，保持原Reader/原件/正文模式和C3门槛；此次是补充执行，不改骨架或以阅读完成声称事实采用。

核验复用当前封存报告，重核原件SHA/文字层连续引文/邻页，并重新语义匹配现行根问题及源对象的问题目录；Reader原问题仅是提示，匹配不发明问题。core_review实际审核及固定ceil(10%)独立复核保存请求/响应/模型摘要。原importance≥8或新的A条件不降档；背景、补证、专门字段与待所有者各自留存。可提交背压与超预算拆分保留上下文及旧尝试，首次仅追加作者归属陈述/预测，不更新GW/项目/合同/模型输入/正式answer。

发布器建立独立Git工作树，经治理、严格校验、registry和四项CI才合并；合并前上下文改变重新核验。AWS运行容器里已有管理员临时会话验收真实HTTPS采用API，逐条正文、状态和支持闭包成功才回写Spark published。不打印凭据、不改账号、不重启共享Reader。所有审计、数据库和原件在Git外长期保留；只读计数随既有快照上网页matching。

代码：src/inresearch/workflow/research_review.py、research_publish.py；两个manage.py子命令，Spark服务和M5 LaunchAgent模板。唯一现行操作指南见docs/local_reader/SPARK_OPERATIONS.md，规范04/05/08/09及注册表、验收映射同时补充。

验证：13项新增C3/需求/抽样/重放/背压分拆/只读计数/CI资格测试；全套1880测试通过。governance check、strict validate与registry通过。修复已有保留审计的macOS只读WAL快照重开：仅对新一致备份切到DELETE journal，独立复制main数据库只读可用、原源库仍WAL，原件保留。

真实试跑：Spark material-reviews/research-verification已有PJM报告核验队列，实际Codex调用、背景与A分流、两组独立抽样拒绝均留档。拒绝原因是有原文支持但与所选工单关系不足，未正式采用。首批通过及部署回执在M5私有state/research-publish与Spark上述永久目录继续登记，不能用本交接证明运行成功。

后续验收：源码合并；Spark新独立核验服务、M5发表LaunchAgent；首份符合条件的B增量经过CI及真实网站采用/API/支持闭包；matching收到独立核验计数。22来源绑定、A委托、数字/项目专门核验仍各自推进，首通道不是全库语义保证。

首个真实通过：PJM报告rev-5878d30d4bbd4d518ebd0682843f1f1e的chunk1 claim8。原文第2页连续引句，7分B及固定100%抽样（1项集合）独立通过；限定作者判断“容量采购一年期合同、履约准备期和并网缓慢限制新增电源供给”，关联OBJ-grid-supply/interfaces和M04-Q01，尚未关闭工单或修改容量。采用包SHA bcf2ff51c69cba6834676eb8db5d1af672fd5f9cc1adb56e00973d02eb50bae7。首项随实现PR提交，后续使用常驻发表器；合并/网站回执仍另验。
