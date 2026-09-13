# 3D 研究关联摘要交付

修改前证据 **0ac2a44**（全部 689 文件），测试职责补充 **1c13458**。基线 311c246。全文件计划/结果、公共引用、旧实现退出与分类计量均在本目录；没有新建第二份研究数据库。

## 已实现

研究状态组装抽为 _research_state；完整 /api/research 保留 legacy 文档/catalog，/api/research-summary 只投影节点关联所需字段及 Reader 可用状态。两者仍来自同一验证/采用/任务规则。前端仍用一个 buildResearchIndex.forNode，未在 Python 再做一套证据计数。

mountNodeResearch 改用摘要；其直接消费者仍为唯一 part-dossier，间接消费者为园区与机柜。工作台 loadResearch 保留完整视图。加载器按接口分别缓存，旧失败不会删除新请求；挂载和本次加载都有独立身份，旧 A→B→A 成功/失败不能覆盖新面板。loading/ready/missing/error 清楚区分，失败可点重试。Reader 失联/延迟不被隐藏。

| 公共实现 | 全部已观察消费者与结果 |
|---|---|
| build_research_summary | HTTP /api/research-summary、单元/浏览器实际 HTTP 夹具；无文件写入，未调用 catalog 构建 |
| _research_state（内部） | build_snapshot/build_research_summary；共同任务与问题状态，不复制规则 |
| loadResearchSummary | mountNodeResearch、独立浏览器请求生命周期测试 |
| loadResearch / build_snapshot | 完整工作台、原 HTTP/CLI 及回归夹具保留；逐项引用见 CSV |
| buildResearchIndex / forNode | 工作台和两场景同一算法；118 个对象逐一比较问题/证据/任务/陈述/回答 ID 与关系、名称、重定向、隐藏状态 |
| mountNodeResearch | part-dossier→两场景；新独立测试直接验证重挂载；旧完整请求及弱守卫退出 |

逐行 public-consumers.csv 是静态可观察集合，不声称发现未知外部调用。摘要不含 documents 表，因此文档列表完整性不是摘要契约，不能把未传文档解释成没有原件。

## 验证与界限

本机完整视图保持 2,907,346 字节（gzip 268,472）；摘要 124,665 字节（gzip 13,422）。生产基线完整视图约 18.7 MB，生产摘要大小必须部署后实测，不能拿本机数冒充。精确快照数字见 payload-evidence.json。

本机 1,001 项 Python 测试；全站浏览器增至 10 套。新的关联测试使用临时目录中的真实 HTTP 服务和已采用支持链夹具，118 个对象通过同一 JS index 比较，至少一个对象含非零精确证据。摘要不带大型 Reader 字段/原文路径，不构造 catalog；损坏/外框架快照仍按共同规则退回可用研究。实际新快照替换、重放 409、生成失败 503 后重试、匿名 401/受限角色 403 均有检查。

两真实场景现在必须等研究面板 ready 并显示计数和邻接；浏览器断言不访问完整 /api/research。独立测试覆盖迟到成功/失败、A→B→A、缓存刷新替换、UI 重试、找不到对象及坏结构，完整工作台契约保留。源码、规范和验收摘要同步 2026.09.13.11。

合并、CI 和生产记录另列，不把本机验证冒充上线。之前生产检查曾等待 page load 90 秒超时，后改为 DOM 就绪及实际组件交互；控制交互通过时仍有研究/纹理/GLB 请求未完成，这正是本批的起点。此批只要求研究数据 ready；纹理/GLB 的完整加载与重试、renderer 拆分、镜头构图和长时 GPU 性能仍未完成。

## 保留与计量

源码不新增目录或应用文件；增加独立关联验收脚本，保持场景手势测试职责清楚。完整视图确有消费者，保留；它的大型记录分页/进一步缩减需要单独兼容契约。历史事实/原件/账号/运行价格/日志不因本批删除或迁移；Spark/M4 未启动或迁移。分类行数与目录见 statistics-after.json，审阅证据单列。
