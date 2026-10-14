# fetchstat生产接通交接（2026-10-14，m5）

## 已定范围

用户授权先接fetchstat，真实交付/重复接收/失败恢复完成并交回执后再接下一队。
AWS采集登记EIA源，Spark使用既有候选台账和永久原件；不自动入Reader、采用或模型填参。
受控SSH文件交付，不安装调度；其他三队不开启。旧ID、来源版本、包和旧仓库保留。
新公开fetchdata仓库创建被自动审批拒绝；改用私有Git包在用户已有AWS/Spark留存，不公开建仓。

## 实际进度

统一采集源码本地分支codex/fetchstat-production，AWS/Spark固定ef2eead。
AWS已实际请求EIA，字节与旧包相同，复用delivery_id和原信封；实际取得时钟和代码版本另记。
旧包原collector_revision=adb4a700a9cbe27b5ae86cbb99a0a6ea834746ea，实际采集代码=ef2eead（此前一次9ee9bc4亦保留）。
Spark暂存区已原样收到AWS包，只读校验通过；生产接收ACK仍待受保护发布后执行。
新接收器固定来源白名单、源码版本和干净工作树，先持久到达再投影至既有acquisition/originals，核验完成才ACK。
到达/共享归档/ACK可幂等恢复；源版本/候选旧ID、未知及推导原样保留，原件损坏不覆盖。

## 验证

采集15项通过（本地及AWS）；本地完整2662项单元回归通过（97.368秒），含8项生产接收行为测试。
首次全套因执行机注册键AWS/aws不一致失败，已修正为aws后完整复验。
治理、严格校验、registry通过；verify/indicators已执行，其无关生成物未带入提交。
GitHub完整CI、受保护合并、Spark真实ACK/故障恢复及网站版本另留回执；未完成不能报已接通。

## 下一步

1. 完成现有InResearch PR的全套检查与受保护合并，私有Git包同步Spark干净main，不重启既有Reader/发布器。
2. Spark验证受控截断副本拒绝、原包接收、重复零增量与首次时钟不变；保留失败副本/回执。
3. 核候选未审核/零Reader/零采用/零填参与正式数据守恒，再登记fetchstat实际连接和范围。
4. 给用户结果，其他队等待下一阶段，不自动扩源/安装调度。

## 私有证据

`/Users/m5/.local/state/inresearch.ai/fetchstat-production-20261014/`：源码bundle、真实采集回执和AWS原包副本。
AWS：~/.local/share/fetchdata/fetchstat，日志~/.local/state/fetchdata/fetchstat。
Spark：~/.local/share/inresearch.ai/acquisition/incoming/fetchstat/production-transfer；正式ACK目录acquisition/collectors/fetchstat。
