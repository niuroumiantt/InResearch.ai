# 日报研究交付闭环交接（2026-10-06，m5）

## 目标与已定规则

仅交付公众号日报与研究详情两份 HTML，停止每日中英文独立长文。inews 选题先读研究站现行需求；原文链接、实际证据、逐事件字段与内容身份随 HTML 私下交付 Spark。原件、候选、阅读完成及 C3 采用分别计量，不把机械引文核验或新闻日期新解释为正式项目/GW 更新。

## 实现与验证

接收器 `manage.py daily-receive` 核对清单、SHA、路径、日期和明确引用；支持旧版 sources 格式，拒绝按数组位置猜引用。结构化观察绑定具体 HTML/节序号，保存逐数口径、引文与证据身份、缺口和历史；按现行目标逐事件匹配。研究详情 HTML 只是派生视图，不重复计入阅读队列。

登录后 `/supply.html#matching` 显示待补来源、待确认园区、待核对口径、待研究复核，分批展示及逐事件定位；已登记项目可回到项目页核对。正式项目与容量文件不会由本接收器写入。

本地严格校验零告警，registry 344 对象/458 问题，1686 项单元测试、supply 浏览器通过。规范版本 2026.10.06.2，06 的替代链、验收映射和旧源快照同时维护。生产是否完成以实际版本和私有回执为准。

## 实际批次与接续

上一版本 0e7a8a1 已在 AWS 与 Spark 部署，本批 71 PDF/61 日报版本已索引，69 PDF/61 日报命中需求；298 正文事件、289 容量观察，276 事件缺链接。11:38 队列为 127 queued / 3 scanned_page_requires_ocr / 2 未命中未安排阅读；数量随 reader 运行变化。reader 逐块运行且有温控暂停，不承诺数小时完成全批或自动改写正式 GW。

inews 配套分支增加 sender、research-detail 派生器和内部交付规范。主工作区有独有提交，部署客户端到 M5 `~/.local/share/inews.today/research-delivery/` 并记录 Git SHA，不 reset 主工作区。每日 06:00 任务更新为两 HTML 和 Spark 回执，07:00 重复任务停用，保留原通知偏好。

下一步：合并与实际部署；只对 SHA 完全相同且来源版本明确的历史 HTML 回补 sources；交付今日新稿并发布快照；继续逐篇阅读与 OCR 专用流程。新园区身份、语义口径、冲突裁决与 C3 尚须完成，不能在本交付阶段宣称全球实时容量普查已闭环。

## 数据入口

Spark `~/.local/share/inresearch.ai/acquisition/{catalog.sqlite,blobs,daily-events.json}`，Reader `catalog/catalog.sqlite`、originals/extracted/artifacts；每日输入 incoming/inews-daily，回执 material-reviews/daily-deliveries。M5 原始 Downloads 与历史 outputs 均保留，部署/批次实测回执在 `~/.local/share/inresearch.ai/material-reviews/2026-10-06-geluoke-semianalysis/`，不进 Git。
