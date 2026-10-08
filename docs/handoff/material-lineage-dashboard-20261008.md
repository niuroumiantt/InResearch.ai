# 资料关系后台图 · 2026-10-08

用户要求解释并可视化 Spark 原始目录、登记库、本批阅读与候选、C3 核验、AWS 目录/正式采用的数量与容量关系，扩展现有 `/admin/inresearchrepo.html`。

## 现行实现

- 生成器 `scripts/sync_repo_pages.py --repo inresearch` 仅重生成此页及自身来源记录；四仓库统一入口保留。
- Spark `Reader.export_snapshot` 在既有一致读取事务内附带登记 SQL 汇总和候选范围。目录 du 缓存一小时，SQLite 文件/index 使用只读连接；计量代码不重排、不采用、不处理 OCR、不改模型。
- 接收端只保留固定目录、数字和日期的白名单。`/api/admin/material-flow` 始终要求真实 admin，private/no-store；正式数来自当前研究支持链，不把待发布候选算作采用。
- 图中五环节可展开，目录/全库/本批/候选/正式记录独立分母；一材料多主张、多对多证据、同 SHA 多副本明确描述。数据库内索引不相加，WAL/SHM、候选 JSON 与产品库分别解释。
- 旧发布端及失测显示未知，目录旧测标陈旧，网站旧值保留其时间。API 60秒短缓存，文件变化失效；前端一分钟只读刷新。

## 验收与部署边界

`test_material_flow.py` 验证计量读取无写入、目录缓存与失败、白名单/缺失未知、支持链与队列分母隔离；`test_repository_pages.py` 验证 GET/HEAD 真实权限；浏览器验证五环节、GB/MB、明暗、1440/390/320无横溢与失败/重试。明确 UI 夹具不证明生产数值。完整 CI 四项通过后按已授权发布流程部署，需核对 AWS/Spark 实际源码和首次收到 material_measurements 的时间，部署回执保存本机私有 state。无需重启 Reader。

不证明全库原件去重比例、唯一原件量、备份完整性或语义核验穷尽；没有研究事实/项目/IT GW 变更。原件、数据库、附件、运行和截图均不进 Git。
