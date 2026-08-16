# Datacenter Hub — 全球数据中心研究数据枢纽

一个**可持续、可更新**的数据中心行业研究项目。报告只是输出载体之一；
真正的资产是三层：**数据积累（越久越值钱）+ 方法论体系（口径纪律）+ 多形态输出能力**。

设计基因与 [news](https://github.com/niuroumiantt/news) 项目一致：
零依赖 Python、JSON 数据层、Markdown 框架层、单文件 HTML 页面，
未来可与 news 共用信源管道和 VPS 部署体系（wentian.ai）。

## 核心思想

> **数据在变，框架不变。**
> 研究框架（模块划分 + 口径规则 + 监测指标）是穷尽且互斥的稳定骨架；
> 数据层持续流入并按规则打标入库；输出层随时按最新数据生成报告。

```
L4 监测层   index.html 仪表盘 + framework/indicators.json 阈值预警
L3 输出层   reports/ — 报告 = 从知识层按角度导出的产物（PDF / PPT / Word / 公众号）
L2 模块层   framework/modules/（定义：问什么）+ research/（知识层：答什么——项目主体）
L1 方法论层 framework/01_data_standards.md 口径规则 + 02_knowledge_format.md 知识格式
L0 数据层   data/ — 六张实体表（项目/公司/价格/政策/合同/来源），实体为主键
```

**知识层（`research/Mxx.md`）是项目的主体**：每模块一份活研究文档，由带状态和
触发器的 Finding（结论+论证+证据+口径提醒）组成；35 问报告是其初始内容来源，
信号管线驱动其持续修订，报告导出器从它按角度汇编产出物。

## 目录结构

| 路径 | 层 | 作用 |
|---|---|---|
| `framework/00_overview.md` | L1-L2 | 研究框架总览：15 模块的 MECE 地图与逻辑 |
| `framework/01_data_standards.md` | L1 | **口径与核验规则手册**（每条数据入库必须遵守） |
| `framework/modules.json` | L2 | 模块注册表（机器可读：依赖表、更新频率、Q 映射） |
| `framework/modules/M01–M15.md` | L2 | 各模块定义：核心问题、关键指标、数据依赖 |
| `framework/02_knowledge_format.md` | L1 | 知识层格式规范（Finding 结构、状态机、触发器） |
| `research/Mxx.md` | **L2 主体** | 模块研究文档：可独立更新的研究结论库 |
| `framework/indicators.json` | L4 | 监测指标注册表（指标、阈值、红黄绿、来源、频率） |
| `data/schema/*.schema.json` | L0 | 六张表的字段定义与约束 |
| `data/projects.json` 等 | L0 | 实体数据（含种子数据，`verified` 标注核验状态） |
| `data/raw/` | L0 | 原始文献/公告存档（不进 git 的大文件另存） |
| `pipeline/` | 采集 | 零依赖抓取与校验脚本（EDGAR 等） |
| `reports/` | L3 | 输出模板与生成结果 |
| `docs/inbox/` | 投递口 | **有材料放这里**（Word/PDF/CAD/Excel 均可，不用分类改名），后台"扫描收件箱"按钮出清单，Claude 归类登记 |
| `docs/source/` | 存档 | 本项目自产文档（Q&A 报告、台账等原件） |
| `docs/library/` | 存档 | 第三方研报库（407+ 份，分类管理，不进 git；索引 `docs/LIBRARY_INDEX.md` 进 git） |
| `index.html` | L4 | 单文件仪表盘：模块地图 + 项目库 + 监测指标 |

## 数据更新三档机制

| 档位 | 数据 | 方式 | 频率 |
|---|---|---|---|
| 自动 | SEC EDGAR、公司 IR、IEA/EIA/FERC、新闻源 | `pipeline/` 脚本 + news 项目信源管道 | 日/周 |
| 半自动 | JLL/C&W/机构报告、财报电话会 | 监控发布页 → AI 提取 → 人工确认入库 | 季度 |
| 手动核验 | 项目状态变更（通电/开工/取消）、产业渠道信息 | 人工录入（独家价值最高） | 事件驱动 |

## 常驻服务（macOS launchd，已安装）

| 服务 | 作用 | 管理 |
|---|---|---|
| `com.datacenterhub.server` | 常驻网页服务器：http://localhost:8000 开机自启、崩溃自动拉起 | `launchctl unload ~/Library/LaunchAgents/com.datacenterhub.server.plist` 停用 |
| `com.datacenterhub.collect` | 每天 08:00 自动跑 `collect.py`（采集+简报+事件驱动标记） | 同上，文件名换 collect；日志在 `logs/` |

**事件驱动核验联动**：collect.py 发现某实体近 7 天有 10-Q/10-K/8-K，自动把触发器挂着
该实体的 current Finding 标为 needs-review（进 P1 队列、仪表盘模块卡片显示 ⚠️）；
人工复核后改回 current 并更新修订日期即不再重复标记。

## 本地运行

```bash
python3 pipeline/verify.py          # 生成核验队列：今天该查什么（核验工作的固定入口）
python3 pipeline/reading_queue.py   # 生成精读队列：这周该读什么（已打分−已消化）
python3 pipeline/validate.py        # 校验所有数据文件（schema + 口径规则 + 保鲜度）
python3 pipeline/fetch_sec.py       # 拉取跟踪公司的最新 SEC 文件列表
python3 pipeline/fetch_news_signals.py  # 从 news 项目匹配实体相关新闻线索
python3 -m http.server 8000         # 打开 http://localhost:8000 看仪表盘
```

核验闭环：`verify.py 出队列 → 人工按链接核对 → 改数据/更新 verified_date → validate.py 把关 → commit 留痕`。
详见 [pipeline/README.md](pipeline/README.md)。

## 与其他项目的关系

- **news**：中英文新闻信源管道（关键词已覆盖数据中心/电力/散热/芯片），其抓取结果是本项目
  数据层的上游信号源；未来 `pipeline/` 可直接消费 news 的 `data/*.json` 做实体关联。
- **公众号内容**：每次数据更新和模块分析都是选题弹药，同一份数据资产服务决策、融资、内容三线。

## 路线图（2026-08-15 对账刷新；总方向见 docs/DECISIONS.md）

- [x] 第一阶段：立规矩——框架文档 + 口径手册 + 六表 schema + 种子数据 + 仪表盘骨架
- [x] 第二阶段：数据层做实——项目库 120 条（台账迁入+全球补录）；CIK 真缺口清零；
      news 信源桥接；EDGAR 采集脚本就绪（云端被屏蔽，须本机 launchd 跑）
- [x] 第三阶段：五个新模块首版研究——M10-M15 全部有 Finding（全库 75 条），
      薄弱模块（M10/M11/M13/M14）已各补量化专条
- [x] 第三阶段半：知识运转机制——核验队列（verify.py）+ 精读队列（reading_queue.py）
      双入口；9 分文献 8/8 消化；决策日志（docs/DECISIONS.md）防会话失忆
- [x] 第三阶段末：**研报库全库通读完结**（2026-08-16）——28,759 份触达率 100%，
      打分表 4,954 行（新增 depth 阅读深度口径：精读 1,190 / 据实生成 350 /
      半自动 2,541 / 目录级 873，四者永不混引）；知识层 131 条 Finding；
      完结报告见 `docs/LIBRARY_REPORT.md`（含重构后的 orgchart、分类标准全文、
      信源价值榜与各模块「接下来怎么用」）
- [ ] 第四阶段：team work 化——按模块分工给不同负责人，PR 提交 → 用户 merge 进 core
      （CODEOWNERS 已铺底，待人员到位与分支协作规范细化）
- [ ] 第四阶段半：全库通读的三个尾巴——151 份图片型 PDF 走视觉读；
      T2 层 AI与算力 3,858 份（最大未读块）；SemiAnalysis 剩余 163 份（单位价值最高）
- [ ] 第五阶段：输出管线——PDF/PPT/Word 模板化生成（reports/templates 待做）；
      季度更新节奏；仪表盘上线 VPS（wentian.ai）
- [ ] 第六阶段：产品打磨——dashboard 美化整理；爆炸图交互升级
      （漂亮的人机互动、快速进入待探索领域）
