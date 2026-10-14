# fetchreports生产接通

用户在fetchfilings验收后要求继续fetchreports生产接通；先登记LBNL报告官方发布页与方法摘要单源，PDF正文/图表/附件未读，不自动采用或填参。实际生产ACK另验，fetchquotes保持关闭。

沿用已验证AWS采集→Spark候选归档的私有受控文件流程。旧两包5b21f048/223c050d保留，不能重造旧信封；同源版本不算独立证据。本阶段不接PDF阅读/全文抽取/附件，也不启用报价队。生产与上线回执保存于本机私有fetchreports-production-20261014目录，尚待完成。

## 实际生产回执

fetchreports已验LBNL官方发布页/方法摘要单源AWS真实采集、Spark永久候选接收、截断拒绝/完整重试及重复零增量；三个旧版与本次新版并存，不多计独立证据。PDF正文/表图/附件未读，信息有效时间未知；不入Reader、不采用、不填参，不安装调度；fetchquotes仍未接通。

首次接收2026-10-14T15:59:27.218135+00:00；接收器94ac5cd9f25cd2a2049bec53282967b352809226。共享来源/版本：{'new_source_series': 1, 'new_versions': 4, 'receiver': {'deliveries': 4, 'items': 4, 'observations': 4, 'production_acks': 4}}。完整私有回执/Users/m5/.local/share/inresearch.ai/fetchreports-production-20261014/spark-audit，原件和失败副本不进Git。最终网站/架构/源码版本以私有release-status.json为准。
