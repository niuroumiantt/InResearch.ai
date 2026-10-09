# DCD 发布延迟修复交接（2026-10-09，macmini / m5 / spark）

目标：继续将 DCD 有用资料接收、全文阅读、封存并投影到网站；解决发布等待，利用 M5。

已定：原件与历史保留；预览/候选接收、全文完成、网站 ACK、正式采用分别计数。不将 PDF 原生文本预览称为视觉阅读或 C3。机器源码使用独立工作树，既有主工作区与运行数据不迁移。

本次修复：发布一分钟检查、五分钟闲时心跳，变更标记在导出前采集且只在 ACK 后保存；502/503/504/连接暂态错误在 120 秒内最多三次同包重试；服务端仅接受精确重放，不覆盖时间冲突/旧包。relay 忙保留旧错误码并附 relay_busy 提示，新 Reader 仅当前任务等十秒；真正模型等待期间仍允许离线 receipt。

运行证据：M5 直连模型入口 15 秒超时、实际 CLI 90 秒超时；通过 M4 私有 SSH SOCKS 出口实际 CLI 9.1 秒完成，重载 relay 后同服务真实请求 4.87 秒完成。未认证 provider 实际模型身份（actual=null），不宣称额度故障。发布历史多次 HTTP502/EOF，五分钟重排放大等待；AWS 近期容器重建是观察到的干扰，未证明每次 EOF 均由部署引起。

M5 持久资源：`~/.local/share/inresearch.ai/assist/dcd-m5-20261009` 与对应 state；`ai.inresearch.dcd.m5-egress-20261009` 仅 loopback37263 经 M4；既有 `ai.inresearch.codex-relay` 使用 per-service proxy env，原 plist 私有备份在 task state。GPU `ai.inresearch.dcd.m5-pdf-preview-20261009` 用实际 `qwen3.8:27b-mxfp8`、并发一，46 新 PDF 原生文本抽样，已回传14份时记录；receiver 写 Spark acquisition 候选，逐条原文数字绑定，永不改 Reader 完成或正式采用。

部署与当前批次实测继续记在资料库 `_整理记录/00_会话交接.md`，不能把本提交的单元通过冒充已部署。第一批5726、第二批2930；M4委派600与 Spark scope 不重叠。发布 override 必须在 oct7-runtime.conf 之后生效；Reader 旧91 override 指向 faa83480，切换前 SIGINT 自然等待在途线程，不能直接 SIGTERM 杀掉推理。私有 env/token 不入 Git。
