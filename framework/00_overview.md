# 研究框架总览 v3 · 一座数据中心，可以被追问到底

> CURRENT · 2026-09-28。规则归属与替代关系见 framework/CURRENT.md。本文替代 v2（五视角 P/F/V/D/R、15 个兼容模块、按尺度分组的浏览目录），旧文归档于 `docs/archive/2026-09-28/framework__00_overview.md`，不再作为执行依据。

> 2026-09-28 用户采用。依据：[对照清单](../docs/reviews/2026-09-28/alignment/AUDIT.md)、[目录与页面框架 v3 提案](../docs/reviews/2026-09-28/site/PROPOSAL.md)、[模型 v3 提案](../docs/reviews/2026-09-28/model/PROPOSAL.md)。本文只定义唯一逻辑与各部分的归属；细则在各自的规范里。

## 项目交付什么

inresearch.ai 交付一件东西：**一座 AI 数据中心，可以被追问到底**——它怎么建、由什么组成、怎么运转、挣不挣钱，每个数从哪来、缺什么。读者是内部研究者、实习生、六个采集队和对外读者；成果是同一棵树的四种读法与一份可发布快照，全部由同一组权威文件生成，不另设第二套组织轴。

## 唯一逻辑：一棵树、三级账、四问四段、五类变量、六队、一个模板

| # | 逻辑 | 一句话 | 唯一规范源 | 机器登记 |
|---|---|---|---|---|
| 1 | **一棵树（骨架）** | 数据中心 → 五个系统（设施、水与散热、电、IT设施、控制与软件）→ IT 分计算、存储、网络，存储再分内存与持久存储 → 系统内按能量流链路 → 61 个部件 + 软件 + 基型；园区之外并列六条站点权利；尺度、旧模块、尺寸都是部件属性，不是任何树的第一层 | [03 对象与协作](03_bom_and_collaboration.md) | `bom.json`（systems、chain、chain_order、stage）、`site_rights.json` |
| 3 | **三级账** | 成本、收入、回报，来自唯一的统一经济模型；回报是账的输出不是一列；一个账本页，四个视图，三种问法（正算、反算、情景网格） | [05 界面规范](05_interface_system.md)「统一经济模型与账本」 | `data/datacenter_model.json`、`knowledge/economics.py` |
| 4 | **四问 · 四段** | 四问：它值多少 / 它由什么组成 / 它怎么影响账 / 数据从哪来、缺什么。四段：采集 → 事实 → 规则 → 视图；四问就是四段倒序 | [05 界面规范](05_interface_system.md)「数据中心节点页」「目录」 | `dashboard_rules.json` → `data/dashboard.json` |
| 5 | **五类变量** | 1 构成、2 运行、3 价格、4 时间、5 主体。正交，无先后，一条数据只属一类；每个模型输入、每条目标行、每张登记表的记录都打这五类之一 | [06 采集规范](06_acquisition.md) | `datacenter_model.json` 的 `groups` 与 `evidence.variable_class`；登记表的 `variable_class` 列 |
| 6 | **六队** | 采集按来源机制分六队（fetchspec、inews、fetchstat、fetchfilings、fetchreports、fetchquotes）；目标表是唯一任务书，由规则层生成，不手写 | [06 采集规范](06_acquisition.md) | `supply_contract.json`、`tco_targets.json`（生成） |
| — | **一个模板** | `node.html` 是 dashboard 的唯一模板：任一节点 × 五列 × 四问；根节点三级账在上；目录是四问的全局视图，节点页是四问的局部视图 | [05 界面规范](05_interface_system.md) | `interface_manifest.json`、`web/routes.json` |

四种读法不是新轴，是五列的横向展开：**建**（时间列 + 主体列，从站点权利起按建设阶段排）、**拆**（构成列 + 价格列，爆炸图是它的视觉形式）、**运**（运行列，运营支出在账本四本账里）、**账**（价格列 + 三级账）。

## 研究产品与完成度（2026-10-10 整改）

分别交付来源/产品目录、可定位证据与研究陈述、具体问题的正式回答，以及带假设边界的模型情景。目录条目、已阅读材料、陈述和答案各自计量，不能相除成一个完成率。问题只有正式答案通过有效支持链才闭合；模型输入的 sourced 是来源登记，不证明适用于所有配置、地域与时点。优先级按关键输入、未支持问题、来源更新与争议决定，不以 PR 数量或图册页数决定。

保留标准库 Python/SQLite 模块化单体。分类树、功能关系、模型依赖和证据链分别表达：现有图谱的包含/供应/持有关系不冒充可计算的供电/冷却/数据接口拓扑。先建立来源可核的贯通配置样例，再扩展关系；不为画面完整虚构工程数据。

## 一句判据

任何文件、页面、登记表、测试只能用上表的词汇组织。以下词汇自 2026-09-28 起退役，只在"退役什么"或历史快照里出现：五视角（P/F/V/D/R）、八生态 / 主生态 / 生态入口、九主题（T01–T09）、按尺度分组的浏览目录、五层、三个计算器（经济模型页 / TCO 页 / 成本计算页）、无来源的仪表盘 / 看板 / KPI 拼盘、"工单 = 模块声明 − 仓库现状"。旧模块 M01–M15 降为兼容属性 `legacy_module`，不再是维护单元、归档路径或任何视图的分组。

## 机器执行入口

- 骨架与权利：`framework/bom.json`、`framework/site_rights.json`；校验 `validate --strict`、`tests/unit/test_bom.py`。
- 研究图谱与问题：`framework/research_graph.json`（3.0 起由骨架生成：对象只有根、系统、链路、部件、站点权利、主体）、`framework/research_questions.json`（每条挂节点与变量类，问题 ID 稳定）；接收端按现行注册表过滤 ID，版本落后的快照照收并标 `registry_lag`。
- 账：`data/datacenter_model.json`、`src/inresearch/knowledge/economics.py`（唯一参考实现）、`web/components/datacenter-model.js`（镜像）、`tests/unit/test_model.py`（三个校准锚与镜像一致性）。
- 规则与视图：`framework/dashboard_rules.json` → `python3 manage.py dashboard --refresh` → `data/dashboard.json` → `web/pages/node.html`。
- 采集：`framework/tco_factors.json` + `bom.json` + `site_rights.json` + `part_fetch.json` → `python3 manage.py targets --refresh` → `framework/tco_targets.json`；`framework/supply_contract.json`。
- 事实：`data/prices.json`、`data/facts.json`、`framework/indicators.json`、`data/products.json`、`data/companies.json`、`data/research_knowledge.json`，每条记录带 `node` 与 `variable_class`。

## 保持不变的纪律

`01_data_standards.md` 与 `02_knowledge_format.md` 的口径、容量/用电/金额/需求模型边界、官方未披露容量不推算、跨中外口径、独立核验与 C3 采用要求保持。视图层不填估值：有值写"数值 + 时点 + 队 · 目标行"，无值写"缺 · 待某队 · 行 ID · 到期"，假设标"假设"，登记数标"登记数"，推算标"推算"。自动深读不自动创建正式采用；数据只留不删，原件不随缓存或任务 TTL 清理。

## 框架变更

新增对象、关系、列、队或页面先修改声明与校验，再改实现；边界变更须有理由、来源、受影响节点、旧新 ID 映射、版本、生效日期与复核记录。旧资料身份与阅读结果保留。历史沿革见 `docs/archive/`；当前规则归属与替代记录见 [CURRENT](CURRENT.md)。

## 行业总览入口（2026-10-02）

行业总览回答行业规模、主体地理布局、项目阶段与变化；研究节点仍按一棵树、三级账、四问和五类变量组织。行业总览是独立入口，不把行业存量与单座数据中心的经济模型混为一谈。它取代 2026-09-28 将首页退役并映射到根节点的决定；具体范围、统计与下钻契约见 05「行业总览」。
