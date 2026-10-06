# Codex 批次阅读接入 · 2026-10-06

用户授权整批材料暂时通过 Codex CLI 推理，Spark 保留原件、数据库、唯一队列与发布；普通阅读 gpt-6.1-sol / medium，复杂审阅 high。当前规则入口为 CURRENT 2026.10.06.4 的 04/05/08 与 Spark 操作手册。

## 实测与基线

实施前 Spark 用户批次 133 份：71 PDF、2,398 页，62 HTML；131 已注册且全部 queued、0 已读块，2 Nanoimprint PDF 因未匹配未登记（有正文，共36页，不需OCR）。5 份扫描报告156页的 M4 OCR 已就绪，OCR 不计全文阅读。事件308、容量观察307、缺链接183、具备项目动态交付资格96，正式本批GW变更0。文件、事件、重叠任务不相加；旧资料库积压不属于本批。

M5 隔离目录中用真实今日日报验收 Codex 适配器和 Reader：extract/triage/read/synthesize/organize/receipt 共7任务成功；2/2正文块、5,384/5,384字符、48条绑定引文，完整候选约202秒。尚非Spark批次结果。CLI请求身份可记录，JSONL不报告provider实际型号，actual=null；不能声称实际型号已核实。

## 执行与切换

- src/inresearch/adapters/codex_inference.py：M5 loopback鉴权服务，已有CLI登录，工具禁用、结构化输出、原文输入SHA；SSH反向转发只绑定Spark loopback。
- deploy/models.json：可选 codex_reader/review/ocr 示例；全局默认Claude不变。实际地址、令牌与机器角色JSON保持私有。
- READER_DOCUMENT_SCOPE：doc_ids全部点名133，include_daily_deliveries=true；所有槽遵守范围，无效配置fail closed。限定批次floor=0、full_read_min_priority=1、workers=2。
- 未完成旧版本用 restart-unfinished，旧执行superseded/pending任务cancelled并保留；新execution_root不冒充current完整结果。完成结果不能被此入口替换。
- 额度等待900秒/转发中断60秒；不扣任务预算或降低优先级。远程推理无需当地GPU温度等待，本地Ollama保护继续保留。
- 发布的execution_scope经接收白名单进入登录matching页，显示实际运行数与尚未提取量；公开项目动态不泄漏报告正文。

## 发布验收与剩余边界

此源码交接记录本地验收与发布步骤，不是生产完成回执。合并后停Spark reader/发布定时器，备份SQLite和机器env；M5部署常驻relay/转发，Spark私有角色配置及scope；登记2份并显式迁移unfinished133，先探针再启动两worker及发布。网站与Spark核对实际发布commit、scope全部登记数、活动任务、首篇完整候选。运行回执和133逐份清单位于机器私有 material-reviews/2026-10-06-geluoke-semianalysis，不进Git。

补来源与正式项目/GW仍有独立研究核验工作，不随全文完成自动通过。当前只有2块真实日报吞吐样本，不能承诺2,398页整批ETA；M5睡眠、网络、模型额度会影响持续速度。切回Spark先停worker备份和恢复机器角色，再逐份新配方；完成结果保留。
