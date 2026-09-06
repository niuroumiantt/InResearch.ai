# Spark 采集操作（第一阶段）

现行规范：[06 采集与翻译](../../framework/06_acquisition.md)。运行数据不进 Git；本阶段不安装周期采集/翻译 worker。

在 Spark 的 `~/code/inresearch.ai` 执行：

```bash
python3 pipeline/acquisition.py status
python3 pipeline/acquisition.py news --input /明确路径/inews-research-export.json
python3 pipeline/acquisition.py sec --company nvidia --limit 1
python3 pipeline/acquisition.py gpu --gpu 'H100 SXM'
```

显式 `--question M13-Q01` 只登记研究任务关联；必须是现行问题 ID，不代表来源已回答问题。自定义数据根使用命令前的 `--data-root /路径`；正式 Spark 用默认永久目录。

inews 导出：在能只读访问正式新闻数据库的运维环境运行 `acquisition.py export-news --db /实际新闻数据库路径 --days 7 --limit 2000`，将标准输出保存为私有 JSON 后传入 Spark。只投影文章字段，不打包含账号/会话的数据库。Node-only 容器可运行本仓库 `scripts/export_inews_research.cjs`，使用容器已有数据库路径配置。

GPU 官方搜索需要私有 `VAST_API_KEY`，只放本机私有环境文件/秘密管理，不写入脚本、参数、日志或 Git。本阶段未配置时任务记录 `vast_api_key_missing`，不得以测试报价顶替。SEC 使用明确身份 User-Agent，可由 `SEC_USER_AGENT` 设置；抓取失败留在 `runs`，不要并发绕过限流。

网页“inews / SEC / GPU 采集状态”只读取 Spark 随 reader 发布的摘要。显示的是来源项总数及最近运行，不是全文数、阅读数或采用数。不存在后台采集服务时，不把按钮命名为“启动连续采集”。

`acquisition/catalog.sqlite` 与 `acquisition/blobs` 应纳入异机备份方案。第一阶段不会改动现有 reader 的数据库备份规则，因此原有 reader 备份并不自动覆盖新采集目录；下一阶段上线周期采集前必须补齐备份及恢复验证。
