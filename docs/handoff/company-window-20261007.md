# 企业窗口 · 2026-10-07

唯一入口 `/product-catalog.html?c=supermicro` 默认四区块首页；`view=products` 和旧型号/系列/搜索/分类深链打开产品子视图。原公司链接门禁和内部附表权限保留。公司资料、产品分类、新闻与披露各有重点，不在首屏下载规格或报告正文。

Supermicro资料核对来源为SEC FY2026 10-K（https://www.sec.gov/Archives/edgar/data/1375365/000137536526000022/smci-20260630.htm）与公司官方概览。六类是按业务披露整理的浏览入口，不冒充原厂目录；原厂分类和实体数仅来自已交付SQLite。FY2023–FY2026年报与五份季报在data/company_disclosures.json登记官方原文，没有虚构财务摘要。

新闻按actor筛选inews已同步窗口，先筛后截断；标题没有公司身份标注时不会仅凭名字纳入。英文标题保留原文。没有新闻、未接通、过期与失败各自提示。行情固定NasdaqAPI，后台并发2/队列8、10分钟缓存、失败60秒退避；保留来源原交易时间、过期缓存和独立缺失市值，永不填入测试价格。行情不进入正式prices库。

本地测试和截图使用明确标记的行情/新闻验证夹具，生产资料库不包含它们。截图不能证明Nasdaq服务在AWS可达或今日行情已取得。其他公司复用相同框架，未登记事实与未接通交易所/财报索引保留空缺；自动新增财报、全文提取和财务指标历史图尚未实现。

发布使用infra现有inresearch-only-deploy.timer跟随main。当前云执行环境没有M5的SSH配置/私钥，不能代替其ssh inews登录；以服务器status/applied及真实网站API核对部署。用户此前HEALTHY 65c56ec仅证明上一版本，不能用于本次发布。

本地验收：1804项Python单测通过；company_window、company_page、product_catalog、dashboard、url_rendering、ui_skin六套浏览器检查通过；治理、严格数据校验和研究登记通过。明暗及1440/390/320截图位于本任务非Git测试产物目录，不作为真实行情证明。
