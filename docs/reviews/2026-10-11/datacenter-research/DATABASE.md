# inresearch.ai 资料库与数据库规模审计

发布说明日期：2026-10-11。最近可核验的运行测量发生于2026-10-10，尚未取得今天实时值。使用十进制GB与MB；Git文件清单不冒充运行存储。

| 集合 | 字节数 | 规模 | 内容和边界 |
|---|---:|---:|---|
| Spark整个资料目录 | 458119794688 | 458.12 GB | 分配占用，含原件、接收副本、暂存、OCR、成果和备份 |
| Reader登记内容 | 107666738916 | 107.67 GB | 44758个SHA内容身份的逻辑文件大小；含派生物 |
| Reader SQLite主库 | 247685120 | 247.69 MB | 文档、来源、阅读版本、任务 |
| Acquisition SQLite主库 | 231305216 | 231.31 MB | 来源、交付、新闻与产品资料索引 |
| Review SQLite主库 | 17358848 | 17.36 MB | 核验批次、尝试、调度与发布状态 |
| 三库主文件合计 | 496349184 | 496.35 MB | 不含WAL/SHM |
| 三库及WAL/SHM | 522551872 | 522.55 MB | 索引101507072字节已含于主库，不再累加 |
| AWS公司产品库 | 138280960 | 138.28 MB | 18家公司、7260条产品行 |
| AWS候选JSON快照 | 140772864 | 140.77 MB | Spark给网站的候选投影 |
| AWS运行data目录 | 291381248 | 291.38 MB | 已包含产品库与候选JSON，不能再相加 |

Spark数据库及登记采样时间2026-10-10T13:30:05.021122+00:00；目录扫描时间12:42:53.156968+00:00。AWS生成时间13:31:05.624024+00:00，收到快照时间13:29:51.486534+00:00，当次stale=false只描述当次观察。不同机器与时间不构成一致事务。

## 里面是什么

登记文件主要为PDF12794个（58.53GB）、TXT12770个、HTML8696个、DWG3947个、DWF835个、LOG772个、JPG608个、XLSX568个，以及其他Office、音视频等格式3768个。共44758个内容身份，不能称为44758份研报。

Reader来源95964条、阅读版本44931条、任务76514条，它们不是新的文档数量。当前版本complete1276、blocked24211、queued19257、running3、failed11。由于分母含派生件与不支持格式，不能据此宣传全文阅读率；complete仍须看报告的阅读范围与引文核验，完成不自动成为采用。

资料目录主要有raw-materials269.09GB、originals107.95GB、incoming51.69GB、artifacts13.61GB、fulltext_ocr5.58GB。存在硬链接、逻辑与分配字节口径及采样时间差，不能相减计算去重节省。备份目录19.21MB不能证明全部原件已有异机副本或完成恢复演练。

AWS当次有支持链成立的正式陈述301条、项目126条、合同8条。产品行中Micron4940、Supermicro1147、NVIDIA1017，其他公司156；产品行不等于确认在售的独立型号。Git中的候选与更新时点不同，不替换这次运行实测。未取得向量数据库占用证据。

## 对架构和运行的建议

目前的分工适合这一规模：Spark保存原件和大型派生物，SQLite维护身份、版本与任务，Git发布正式研究，AWS保存网站所需投影和产品库。仅凭容量没有证据要求迁移分布式数据库。优先保证按需读取候选投影，避免首屏搬运140.77MB快照；保留接收、阅读、审核、采用各自的分母、时间与过期状态。

今天运行环境失败，诊断为所选环境仓库未找到或不可访问；GitHub连接器仍能读写仓库。现有网页工具未能读取管理员实时计量，未取得HTTP401/403，不由此推断网站宕机。实际容量入口是管理员页和GET /api/admin/material-flow，需要真实管理员会话。

## 可核验来源

以下均固定在6b1c6d2020dcbc1e5967cadcf9ecda9323f511ee：

- [Spark测量原始JSON](https://github.com/niuroumiantt/InResearch.ai/blob/6b1c6d2020dcbc1e5967cadcf9ecda9323f511ee/docs/reviews/2026-10-10/project-audit/spark-measurements.json)
- [AWS测量原始JSON](https://github.com/niuroumiantt/InResearch.ai/blob/6b1c6d2020dcbc1e5967cadcf9ecda9323f511ee/docs/reviews/2026-10-10/project-audit/website-measurements.json)
- [产品组成](https://github.com/niuroumiantt/InResearch.ai/blob/6b1c6d2020dcbc1e5967cadcf9ecda9323f511ee/docs/reviews/2026-10-10/project-audit/product-coverage.json)
- [原审查范围](https://github.com/niuroumiantt/InResearch.ai/blob/6b1c6d2020dcbc1e5967cadcf9ecda9323f511ee/docs/reviews/2026-10-10/project-audit/REVIEW.md)
