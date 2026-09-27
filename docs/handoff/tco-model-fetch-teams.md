# TCO 模型与采集分队交接（2026-09-27）

供新会话直接接手。本文只记结论与待办，推导过程见 `docs/DECISIONS.md` 当日条目与 `docs/guides/model-governance-2026-09-27.pdf`。

## 一句话现状

数据中心经济模型的骨架已定为"三级、四段、五层、六队"，指导文件已上线 main（`docs/guides/model-governance-2026-09-27.{html,pdf}`），仍是草案，未写入 `framework/CURRENT.md`。TCO 页面 `tco.html` 已上线并完成第一轮定向抓取（145 条记录入价格库，31/47 个输入改为已有来源，基准 $852/kW·月、$4.01/GPU·h）。

## 骨架（已定）

- **三级**（输出）：成本级 Cost（capex = 构成 × 价格，opex = 运行 × 价格，按时间折现）、收入级 Revenue（GPU 数 × 8,760 × 利用率 × 单价）、回报级 Return（收入 − 成本 + 主体层：分账、杠杆、税）。
- **四段**（流程）：采集 → 事实 → 规则 → 视图。事实按"因什么而变"分**参照数据**（按版本改：部件目录、每 MW 工程量、预设）与**观测数据**（按时点追加：价格、实测、交期、票息，`prices.json`，series_id + as_of 唯一）。视图只读不写。
- **五层**（变量）：构成、运行、价格、时间、主体。五层是内容轴，四段是流程轴，两轴正交。
- **六队**（采集，按来源机制划分，不按层）：fetchspec（厂商规格，已有）、inews.today（新闻事件，已有）、fetchstat（统计与费率表，待建，建议最先）、fetchfilings（证券与公司披露，待建）、fetchreports（研报指数论文，待建）、fetchquotes（市场报价，待建）。中文来源将来可从 fetchstat/fetchreports 分出。

## 六队共同规则（已定）

1. 需求只来自"五层目标清单"（因子树 `framework/tco_factors.json` 的扩展，待建）：每层要哪些序列、来自哪类披露、发布日历、目标输入、执行机。
2. 交付只走供应中心一个入口（fetchspec 包格式：manifest、SHA256SUMS、原件），数字进观测数据，规格进参照数据。
3. 任务写"披露类型 × 出版方类别 × 日历"，公司只是实例。
4. 执行机：AWS 持续（API、EDGAR、RSS、固定表格），macmini 辅助（登录、注册下载、JS 页面），Spark 只做提取。

## 相关文件

- 模型口径与证据：`data/datacenter_tco_model.json`（evidence 每输入状态、fetch_kind、fetch_what）
- 因子树：`framework/tco_factors.json`；页面引擎：`web/components/datacenter-tco.js`；参考实现：`docs/research/datacenter-tco/model.py`
- 价格库：`data/prices.json`（512 条）；第一轮抓取记录 note 尾部标"定向抓取 2026-09-27"
- 采集规范：`framework/06_acquisition.md`；信源地图：`framework/05_source_map.md`；供应中心 `/supply.html`
- 现有仓库：`niuroumiantt/fetchspec`、`niuroumiantt/inews.today`

## 近期任务（已排序，未开始）

1. 五层目标清单（扩展因子树：披露类型、当前实例、发布日历、目标序列、目标输入、执行机）。
2. 每 MW 工程量表骨架；四个造价类目写明部件清单；psu、coolant 挂进因子树。
3. `tco.html` 缺口表加"最新时点 / 下次更新"两列，变成到期表。
4. 建 fetchstat。
5. 电价拆能量与线路两部分，消除需量费重复计入。
6. 劳登县计算机设备动产税 4.15%、弗州用电税 1.1¢/kWh、NVAIE 订阅进入模型。
7. 交期与紧缺状态驱动建设期与电气造价涨幅。

## 待新会话讨论的问题（用户提出）

- 基于 3-4-5-6，各队要抓取的**角度**与**素材**清单，尤其 inews.today 要增加哪些角度（融资、租约、项目、费率案、交期、供应链事件等）。
- 爬取架构：一个爬虫统抓，还是多个爬虫并行各管一类来源；并行时如何避免同一来源被抓多次（06 规范：一个来源一个主执行机，不静默双跑）。
- 六队是否真的要六个 repo，还是一个采集框架下六个"分队配置"；边界按"怎么抓"定的原则不变，仓库数可再议。

## 待用户决定

- 是否把指导文件升级为 `CURRENT.md` 现行规范。
- 近期任务是否按上面顺序开始。

## 操作提醒

- 每次改动：`git add -A && python3 manage.py governance --refresh && git add -A && python3 manage.py governance --check`；改了 CURRENT.md 或已审阅测试文件要重算 `framework/verification_contract.json` 哈希并升基准版本。
- GitHub 端"更新分支"后立即合并会让仓库清单过期、main 的 validate 变红（今天发生三次）；合并前用本地推送的头，或合并后补一个刷新清单的 PR。
