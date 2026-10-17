# fetchreports生产队列交接

2026-10-16用户接受filings后授权reports AWS→Spark队列/ACK；仅既有LBNL发布页摘要单源，保留四个HTML版本的旧ID、来源版本、交付历史和原ACK。PDF正文/表图/附件未读保持，不以HTML complete冒充整份报告完整阅读。不定时、不扩源、不入Reader、不采用或填参。

源码增加reports固定入口/协议及三队provider隔离；stats/filings各自固定运行版本、专用公钥与绑定不变。实机验收待受保护合并部署后执行；本地/CI测试不冒充真实接通。

结果~/.local/share/inresearch.ai/fetchreports-outbox-20261016，日志对应state目录；只备份operations及显式故障目录，不复制ssh私钥。实际恢复走原ACK确认时不能声称生产未收重试。本阶段完成后先向用户出示回执，不自动接报价队。
