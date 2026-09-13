# Spark 采集操作

现行规范：[06 采集与翻译](../../framework/06_acquisition.md)。运行数据不进 Git；新闻标题投影每小时同步；SEC/GPU 和全文翻译不自动调度。

在 Spark 的 `~/code/inresearch.ai` 执行：

```bash
python3 manage.py acquisition status
python3 manage.py acquisition news --input /明确路径/inews-research-export.json
python3 manage.py acquisition sec --company nvidia --limit 1
python3 manage.py acquisition gpu --gpu 'H100 SXM'
```

显式 `--question M13-Q01` 只登记研究任务关联；必须是现行问题 ID，不代表来源已回答问题。自定义数据根使用命令前的 `--data-root /路径`；正式 Spark 用默认永久目录。

inews 导出：在能只读访问正式新闻数据库的运维环境运行 `python3 manage.py acquisition export-news --db /实际新闻数据库路径 --days 7 --limit 2000`，将标准输出保存为私有 JSON 后传入 Spark。只投影文章字段，不打包含账号/会话的数据库。Node-only 容器可运行本仓库 `scripts/export_inews_research.cjs`，使用容器已有数据库路径配置。

GPU 官方搜索需要私有 `VAST_API_KEY`，只放本机私有环境文件/秘密管理，不写入脚本、参数、日志或 Git。本阶段未配置时任务记录 `vast_api_key_missing`，不得以测试报价顶替。SEC 使用明确身份 User-Agent，可由 `SEC_USER_AGENT` 设置；抓取失败留在 `runs`，不要并发绕过限流。

网页“inews / SEC / GPU 采集状态”只读取 Spark 随 reader 发布的摘要。显示的是来源项总数及最近运行，不是全文数、阅读数或采用数。不存在后台采集服务时，不把按钮命名为“启动连续采集”。

`acquisition/catalog.sqlite` 与 `acquisition/blobs` 应纳入异机备份方案。第一阶段不会改动现有 reader 的数据库备份规则，因此原有 reader 备份并不自动覆盖新采集目录；新闻定时上线前使用 `python3 manage.py backup --dest /新的备份目录` 在线备份台账与引用原件，校验 SQLite 与 SHA256，再复制至异机并复核清单。此工具不删除旧备份；异机长期轮转与统一备份调度仍须落实。

## 新闻定时同步

部署 `deploy/spark-reader/inresearch-news.service` 和 `.timer` 至 `~/.config/systemd/user/`，执行 `systemctl --user daemon-reload` 与 `systemctl --user enable --now inresearch-news.timer`。上线前先执行服务一次，确认上游接口可用、台账成功、备份可恢复，再启用定时。Spark 现有 reader-publish 每五分钟发布至网站。

`python3 manage.py news-sync` 可手动重试。失败记录在 acquisition runs，旧窗口保持；不触碰用户仍在传输的 raw-materials 隐藏目录。首页的同步时间代表完整窗口抓取时间，不能用网页刷新时间冒充。

## 2026-09-07：经验证的上游选定范围

小时同步只连接固定的 iNews 数据中心 HTTPS 接口，并验证原始响应地址、schema、文章 URL/ID/时间、非空 topics、固定七天窗口和游标。完整成功后保留上游主题与稳定 GUID；研究端不再重复更窄的标题匹配。文件导入无论自报什么 verified/来源标记，都不能获得这一接收权限，继续沿用保守本地筛选。截断/异常不覆盖最后一次完整窗口。该变更不扩大现有接口为全部软件生态，不改变新闻为候选标题的身份，也不启动或停止规格、SEC、GPU 或 reader 任务。
