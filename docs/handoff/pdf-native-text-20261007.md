# 默认正文阅读交接（2026-10-07，m5）

## 目标与用户已定规则

以后直接读材料文字层，混排图片不做 OCR、不阻塞正文交付；纯图片材料由用户先处理后补充可读版本。原件长期留 Spark，图片未读明确标出，正文结论与逐字引文仍为候选，正式采用继续按 01 核验。新规范入口为 CURRENT → 04/05，禁止恢复旧的图片 OCR 前置要求。

## 已完成

- inresearch PR #343 合并，运行 SHA `68670b87989af5b2f4e6ead1a1af7387cfff1153`。默认 `native_text_only`；旧冻结配方/完成结果不被改写。1,840 项单元测试（内置 Python 3.12）、全部 GitHub CI、采集/规格浏览器测试及严格数据/注册表/治理检查通过。
- m5 SemiAnalysis 71 PDF 原件合计 1,230,130,644 bytes，2398 页，2388 页有文字层、10 页没有文字层。约 11 秒导出 71 TXT、零错误/零 OCR；正文 3,406,522 字符，TXT 3,824,762 bytes。全部 TXT SHA 在 Spark 核对通过，派生物不另算原件或已读报告。
- Spark 23 份仍被旧 OCR 阻塞的报告，以既有 `restart-unfinished` 受控建立新正文版本；旧 PDF、OCR 尝试、历史版本及一致 DB 备份保留。31 秒提取 1279 页、1276 块，零 OCR。已有完成结果与已进入正文阅读的旧配方继续处理，避免重读。Reader/Codex 和发布 timer 已启动，默认请求 gpt-6.1-sol/medium、2 worker；CLI 未提供实际 provider 型号，不能宣称已核对实际型号。
- 网站部署新 SHA，实际登录浏览器核对了默认正文说明、队列及原文结果入口，没有 JS 错误。17:44 北京时间网站接收：134 份（71 PDF/63 HTML），109 份阅读候选已交付、24 排队/1 处理中，本批阻塞 0。新正文版本当时只完成提取/粗读，新增完整正文报告 0；不能提前宣称正式采用或 GW 增量。
- 同步修复：89 MB 解压快照接收触发 AWS 容器原 1 GiB 上限的 cgroup OOM/502。宿主可用 6.4 GB；运行容器及已安装 Compose 调为 2 GiB 后接收成功。持久规范在 infra `hosts/aws/inresearch.compose.yml`；其他服务、原件和镜像不因调内存而改变。

## 数据与恢复入口

- Spark 原件/主台账：`/home/spark/.local/share/inresearch.ai/originals/`、`catalog/catalog.sqlite`；m5/Spark 派生 TXT：各自 `~/.local/share/inresearch.ai/pdf-text/semianalysis-20261007/`，含页码、原件/TXT SHA 和 manifest。
- Spark 私有迁移回执/旧配置/DB 一致备份：`~/.local/share/inresearch.ai/material-reviews/pdf-native-text/20261007-172220/`。目录有 plan、restarts、含提取清单的 migration-result、deployment 和 before 备份；不要作为新研究材料重新入库。部署后 publisher 使用规范源码 `~/code/inresearch.ai`，旧 pin/配置另存，未覆盖运行源码。
- m5 每小时计量协议已改为 v4：`~/.local/state/inresearch.ai/hourly-progress/measurement-contract.json`，原 v3 按时间保存。原 M4 有限 OCR worker 于 17:01 停止，只保留历史；旧 OCR rescue revision 若被替代，不再作为当前正文队列阻塞报告。不从 heartbeat 重启 OCR。
- 网站：`https://inresearch.ai/supply.html?day=2026-10-07#matching`。材料数/文字提取/正文候选/正式采用分别计量；`coverage.complete` 在正文 scope 内不是图片完整性。旧视觉报告尚有16页显式缺口，保留旧记录而非改为已读。

## 接着做

只读核对新正文候选的整篇完成数、当前 revision、引句机检、网站回执与落点；按现行需求核验已读候选并分别记录正式采用。不要重跑完成材料或用 TXT/页数冒充交付。纯图片提示用户补可读版本；混排图片继续跳过。监测网站接收内存与实际 OOM，不能仅凭服务健康宣称同步完成。
