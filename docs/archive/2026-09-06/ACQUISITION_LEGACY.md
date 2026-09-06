# 旧采集协议（已替代）

SUPERSEDED · 现行规范为 framework/06_acquisition.md。

旧新闻桥接读取相邻 news/data/index.json 与按日 JSON，而正式 inews 已采用 SQLite 内容/账号数据库。旧 SEC 抓取器只保存最新 submissions 清单于代码工作区的 data/raw/sec，不下载正文。旧 GPU 抓取器把 on-demand 查询命名为 spot，并直接续写 prices.json。旧网页按钮在网页主机执行这些脚本。

以上执行方式退出当前入口。历史原始材料、价格点与简报继续保留；它们不因采集器升级而自动取得新口径或采用资格。完整旧实现见 Git 历史。新的第一阶段只生成采集候选和来源状态，不宣称全文、翻译或采用完成。
