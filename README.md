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
L3 输出层   reports/ — PDF / PPT / Word / 公众号文章 / 数据切片（按需生成）
L2 模块层   framework/modules/ — 15 个研究模块（只做"视图"，不存数据）
L1 方法论层 framework/01_data_standards.md — 口径规则、九级漏斗、去重规则（不变的灵魂）
L0 数据层   data/ — 六张实体表（项目/公司/价格/政策/合同/来源），实体为主键
```

## 目录结构

| 路径 | 层 | 作用 |
|---|---|---|
| `framework/00_overview.md` | L1-L2 | 研究框架总览：15 模块的 MECE 地图与逻辑 |
| `framework/01_data_standards.md` | L1 | **口径与核验规则手册**（每条数据入库必须遵守） |
| `framework/modules.json` | L2 | 模块注册表（机器可读：依赖表、更新频率、Q 映射） |
| `framework/modules/M01–M15.md` | L2 | 各模块定义：核心问题、关键指标、数据依赖 |
| `framework/indicators.json` | L4 | 监测指标注册表（指标、阈值、红黄绿、来源、频率） |
| `data/schema/*.schema.json` | L0 | 六张表的字段定义与约束 |
| `data/projects.json` 等 | L0 | 实体数据（含种子数据，`verified` 标注核验状态） |
| `data/raw/` | L0 | 原始文献/公告存档（不进 git 的大文件另存） |
| `pipeline/` | 采集 | 零依赖抓取与校验脚本（EDGAR 等） |
| `reports/` | L3 | 输出模板与生成结果 |
| `docs/source/` | 存档 | 原始 Q1–Q35 研究报告（本项目的知识起点） |
| `index.html` | L4 | 单文件仪表盘：模块地图 + 项目库 + 监测指标 |

## 数据更新三档机制

| 档位 | 数据 | 方式 | 频率 |
|---|---|---|---|
| 自动 | SEC EDGAR、公司 IR、IEA/EIA/FERC、新闻源 | `pipeline/` 脚本 + news 项目信源管道 | 日/周 |
| 半自动 | JLL/C&W/机构报告、财报电话会 | 监控发布页 → AI 提取 → 人工确认入库 | 季度 |
| 手动核验 | 项目状态变更（通电/开工/取消）、产业渠道信息 | 人工录入（独家价值最高） | 事件驱动 |

## 本地运行

```bash
python3 pipeline/verify.py          # 生成核验队列：今天该查什么（核验工作的固定入口）
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

## 路线图

- [x] 第一阶段：立规矩——框架文档 + 口径手册 + 六表 schema + 种子数据 + 仪表盘骨架
- [ ] 第二阶段：数据层做实——项目库从核验台账迁入；EDGAR/IR 自动采集跑通；接入 news 信源
- [ ] 第三阶段：五个新模块首版研究（资本金融 → 中国 → Token 经济 → 有效算力 → 运营执行）
- [ ] 第四阶段：输出管线——PDF/PPT/Word 模板化生成；季度更新节奏；仪表盘上线 VPS
