# 专栏与长文自动研究交付（2026-10-09，m5）

## 目标
把《美国数据中心抢电，争的是通电时间》最新版送入 inresearch.ai，以后长文与 inews.today 专栏自动反哺研究。

## 已定规则
- 用户已授权持续发送，不逐篇再问。长文按 A 为主、B 辅助写作，正文与一手原件分别保留身份。
- 长文交付完毕执行 outbox seal；M5 自动重试发送。公开专栏与修订由 Spark 每五分钟同步，引用链接不冒充已接收原件。
- 接收、全文阅读、C3 正式采用分开记录；SHA 去重，保留旧版及既有范围/日报设置。

## 进度
- 功能与规范已合并：inews PR267（生产 1b8f91ba）；inresearch PR452（生产及 Spark main 6fd7bee1）。最终 head 全部 CI 成功。
- 本文 SHA：`5a90f85c91aff48a5f6aa1f2241a5709a7297191614cdbdce17c050d91fdda13`；正文、research.txt、sources.json 已实际送达。网站 2026-10-09 13:25:51 回查标题正确、authored_analysis、52 条来源记录、candidate/queued。此前 23 份来源批次通过 primary_source_batch 关联，没有再次计作新原件。
- 首轮专栏接收 31 篇，匹配并加入阅读范围 24 篇；后续定时轮次 received=0/unchanged=31。范围累计181项，旧条目和 include_daily_deliveries=true 保留。
- Spark inresearch-editorial.timer 已启用；M5 ai.inresearch.editorial-delivery 已运行6次，最后退出0。M5发送器使用可核验独立发布目录 be9495a3，远端研究上下文指向现行 main；Spark接收器已改用现行 main。
- 正文尚未完成全文阅读/C3。本次未重启 Reader；观察到既有 Reader 处理另一文档时出现 OperationalError 并自动重启，接收及发布成功。后续若查阅读速度，需独立定位该异常，不据接收回执声称已读。

## 下一步
1. 后续长文完成验收后封装 outbox；无须用户另行要求发送。
2. 有新专栏或改稿时核对版本回执；如需撤稿登记单独处理，v1不从分页缺席推断撤销。
3. 需要确认本篇读完时按上述完整SHA查 Reader当前结果，采用另查C3。

## 待用户决定
无。

## 入口
- 唯一交付协议：docs/local_reader/EDITORIAL_DELIVERY.md；长文规范：docs/geluoke/专题写作规则.md。
- Spark接收回执：~/.local/share/inresearch.ai/material-reviews/editorial-deliveries.json；最新同步：~/.local/state/inresearch.ai/editorial-sync/latest.json。
- M5原稿：~/code/inresearch.ai/outputs/geluoke-research/2026-10-09-us-datacenter-power/；原始资料保持原数据目录。
- M5运行验收与回执：~/.local/state/inresearch.ai/editorial-deliveries/（runtime-install.json、article-v4-receipt.json、first-column-sync.json）。原件、密钥、数据库和运行资料不进Git。
