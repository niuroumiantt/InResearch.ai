# Spark 采集操作

现行规范：[06 采集与翻译](../../framework/06_acquisition.md)。运行数据不进 Git；新闻事件投影每小时同步；全文翻译不自动调度。inresearch 本身不爬取：内置 SEC 与 GPU 采集器已于 2026-09-28 退役，改由 fetchdata 仓库的 fetchfilings 与 fetchquotes 分队按 [五类变量目标清单](../../framework/tco_targets.json) 采集并经供应中心交付；历史 `sec`/`gpu` 台账行保留只读。

在 Spark 的 `~/code/inresearch.ai` 执行：

```bash
python3 manage.py acquisition status
python3 manage.py acquisition news --input /明确路径/inews-research-export.json
```

显式 `--question M13-Q01` 只登记研究任务关联；必须是现行问题 ID，不代表来源已回答问题。自定义数据根使用命令前的 `--data-root /路径`；正式 Spark 用默认永久目录。

inews 导出：在能只读访问正式新闻数据库的运维环境运行 `python3 manage.py acquisition export-news --db /实际新闻数据库路径 --days 7 --limit 2000`，将标准输出保存为私有 JSON 后传入 Spark。只投影文章字段，不打包含账号/会话的数据库。Node-only 容器可运行本仓库 `scripts/export_inews_research.cjs`，使用容器已有数据库路径配置。

SEC 与 GPU 报价的采集凭据（如 `VAST_API_KEY`、`SEC_USER_AGENT`）不再属于本仓库；它们随采集器迁入 fetchdata，只放采集机的私有环境文件，不写入脚本、参数、日志或 Git。

采集台账覆盖 iNews 与 Fetchspec，并只读保留退役前的 SEC、GPU 历史行。网页采集状态只读取 Spark 随 Reader 发布的摘要。显示的是来源项总数及最近运行，不是全文数、阅读数或采用数。Fetchspec 的 `product-documents` 检索是候选资料目录，按公司、一级产品分类、研究问题、格式和语言筛选；它不表示全文已读或事实已采用。不存在后台采集服务时，不把按钮命名为“启动连续采集”。

`acquisition/catalog.sqlite` 与 `acquisition/blobs` 应纳入异机备份方案。第一阶段不会改动现有 reader 的数据库备份规则，因此原有 reader 备份并不自动覆盖新采集目录；新闻定时上线前使用 `python3 manage.py backup --dest /新的备份目录` 在线备份台账与引用原件，校验 SQLite 与 SHA256，再复制至异机并复核清单。此工具不删除旧备份；异机长期轮转与统一备份调度仍须落实。

## 新闻定时同步

部署 `deploy/spark-reader/inresearch-news.service` 和 `.timer` 至 `~/.config/systemd/user/`，执行 `systemctl --user daemon-reload` 与 `systemctl --user enable --now inresearch-news.timer`。上线前先执行服务一次，确认上游接口可用、台账成功、备份可恢复，再启用定时。Spark 现有 reader-publish 每五分钟发布至网站。

`python3 manage.py news-sync` 可手动重试。失败记录在 acquisition runs，旧窗口保持；不触碰用户仍在传输的 raw-materials 隐藏目录。根节点页的同步时间代表完整窗口抓取时间，不能用网页刷新时间冒充。

## 2026-09-07：经验证的上游选定范围

小时同步只连接固定的 iNews 数据中心 HTTPS 接口，并验证原始响应地址、schema、文章 URL/ID/时间、非空 topics、固定七天窗口和游标。完整成功后保留上游主题与稳定 GUID；研究端不再重复更窄的标题匹配。文件导入无论自报什么 verified/来源标记，都不能获得这一接收权限，继续沿用保守本地筛选。截断/异常不覆盖最后一次完整窗口。该变更不扩大现有接口为全部软件生态，不改变新闻为候选标题的身份，也不启动或停止规格、SEC、GPU 或 reader 任务。

## 用户材料与历史新闻匹配（2026-10-06）

在部署同版源码的 Spark 执行 `python3 manage.py research-match --input <已完整落地的原件或目录> --data-root ~/.local/share/inresearch.ai`；原件进入既有 acquisition 永久库，命中项进入既有 raw-materials 接收口，原来源目录不改动。命令的 processed/matched 是页内索引，不是已读/已采用。检查失败回执后再重试，不用批次大小冒充成果。

升级后执行 `python3 manage.py pipeline --data-root ~/.local/share/inresearch.ai --reindex`，回放固定来源新闻档案并保留撤回；不会抓新全文。按原件核对候选身份后，可用既有 `pipeline --id <线索> --state linked --site <现行site_id> --note <公开复核依据>` 登记关联；这不采纳容量数值。

接收、回放之后正常运行 Reader 与 publish 服务；核对 `/api/news` 的完整 progress、项目页候选、内部 `/supply.html#matching` 及实际发布回执。内部报告的标题/页码引文不由匿名接口公开。网站与 Spark 源码/服务版本、实际数量和未覆盖项记录在当次交接；不能只改 Git 后称链路已上线。

新建 Reader 阅读版本会冻结本材料匹配的现行目标、五类变量、六队与模型输入；needed/assumed/delivered 匹配的初始优先级为 7，有主模型输入为 8。此分数只是工作顺序；不是来源等级。原件 SHA 路径保留，候选分类可由 library/candidates-by-node/<节点>/variable-N/ 回查，新全文结果在 library/by-node/，旧模块链接及已创建配方保留。已有 SHA 的旧阅读不会因本轮提示或模型变化自动重读；若研究缺口需要重读，按 04 的显式阅读版本流程执行。

采集备份新增两本 JSON 账的逐账锁定副本，保留新闻/日报版本及人工身份复核；与在线 SQLite、blob SHA 验证一并保存。不同库并非单一时间点；Reader 完整产物备份仍单独执行。

## 日报与来源成组接收（2026-10-06）

上游发送器产生 research-delivery.json 清单，复制正文/来源/研究字段/派生 HTML/实际证据后投递至 incoming/inews-daily/<清单SHA>/，全部哈希验证后才开放。也可在 Spark 手动执行 `python3 manage.py daily-receive --input <完整清单目录>`，默认使用既有数据根。回执 indexed_candidate 是候选完成，不是正式采用；按 bundle_id、原件/来源/目标表 SHA 追溯，旧来源目录和版本不改动。

补历史链接只用实际对应版本的来源台账与 HTML 配对，不按日期猜关联。派生研究 HTML 只归档，不重复进 Reader。接收后沿用 Reader/publish 调度，核对网页事件、来源与快照时间。残留 .partial 只意味着输入未开放，不能把文件存在当成入库完成。
