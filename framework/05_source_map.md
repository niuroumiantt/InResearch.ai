# 信源地图 — 爆炸图的镜像（2026-08-16 用户提出）

> 核心思想（用户）：数据中心怎么物理构成，研究框架就怎么分模块，**行业研究生态也按同样
> 结构分布**——每个部件/模块都有自己的专业机构、专业会议、专业数据序列。BOM 爆炸图
> 应有一张镜像的"信源爆炸图"：点开部件，不仅看研究档案，还看"该部件该追谁"。
> 存储侧样板（用户亲述）：TrendForce / Yole / Forward Insights / FMS / China FMS / DRAMeXchange。

## 按模块的专业信源初版（云端知识 + 745 份实测，待 FINAL_REPORT 实证修正）

| 模块/部件 | 专业机构 | 会议/免费一手 | 备注 |
|---|---|---|---|
| M06 芯片/GPU | SemiAnalysis、TechInsights（拆解）、Yole、TrendForce | Hot Chips（免费）、GTC、ISSCC | 库内已厚 |
| M06 HBM/存储 | TrendForce/DRAMeXchange、Forward Insights（NAND 专门）、Objective Analysis | FMS、China FMS | 用户熟悉域 |
| M07 网络/光 | **LightCounting（光模块专门）**、Dell'Oro（网络设备季报）、Yole CPO | **OFC（光通信顶会）**、Hot Interconnects | 库内缺 LightCounting |
| M08 散热/液冷 | Dell'Oro（DC 物理基建季报）、Omdia（液冷追踪）、Uptime Institute | ASHRAE TC9.9、DCD 系列、中国 CDCC | 库内缺 Uptime/Omdia |
| M09 电力/配电 | Dell'Oro、Omdia、Vertiv/Eaton/施耐德财报 | **LBNL 报告（免费，美国 4.4% 即出自此）**、FERC/EIA 数据 | |
| M05/M01 选址/市场 | **JLL/CBRE/Cushman（半年报免费）**、datacenterHawk、DC Byte、Synergy、Structure Research（托管） | DCD、PTC | 库内几乎空白 |
| M03/M02 资本/云 | Dell'Oro IT Capex（季度）、Synergy、公司 10-K/财报电话会 | —— | DellOro 已证 |
| M12 需求/token | **Epoch AI（免费）**、**Artificial Analysis（价格基准免费）** | —— | 已用 Epoch |
| M04 电力宏观 | IEA、EPRI、Grid Strategies（并网）、Wood Mackenzie | NERC/ISO 报告（免费） | |
| M14 中国 | IDC 中国、赛迪 CCID、**信通院白皮书（免费）** | **ODCC 开放数据中心大会**、CDCC、**运营商集采公告（免费一手）** | 最大空白 |

## 落地路径
1. FINAL_REPORT 信源榜出来后，用实测高分率修正本表；
2. 第六阶段产品打磨时，把本表挂进 bom.json 各部件（sources_orgs 字段）——爆炸图
   部件档案增加"该追谁"栏，实现用户说的"素材角度爆炸图"。
