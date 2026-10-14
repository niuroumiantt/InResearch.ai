# fetchreports生产接通

用户在fetchfilings验收后要求继续fetchreports生产接通；先登记LBNL报告官方发布页与方法摘要单源，PDF正文/图表/附件未读，不自动采用或填参。实际生产ACK另验，fetchquotes保持关闭。

沿用已验证AWS采集→Spark候选归档的私有受控文件流程。旧两包5b21f048/223c050d保留，不能重造旧信封；同源版本不算独立证据。本阶段不接PDF阅读/全文抽取/附件，也不启用报价队。生产与上线回执保存于本机私有fetchreports-production-20261014目录，尚待完成。
