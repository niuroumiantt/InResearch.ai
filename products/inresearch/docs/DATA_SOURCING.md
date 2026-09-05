# 数据寻源清单 — 按角度找数据，intern 派工的母清单

> 2026-08-26 用户批复建立。**用途**：安排 intern 按角度寻找数据源，用户逐一审阅后补充进库。
> 与生成物 `reports/workorders.md`（= 声明 − 现状，259 张）互补：那边说**缺什么**，
> 这边说**去哪找**。首批三张工单见 `docs/intern/`。
>
> 维护规则：新增信源写进对应角度的行；试过不行的源**不删**，标「已试·不可用」加原因——
> 别人不用再踩一遍。

## 三条纪律（每张 intern 工单都要带上）

1. **只登记官方或可溯源链接，不许猜**。找不到就如实写「找不到」并记原因（需注册/已下架/仅纸质）——留白是纪律，编一个数是事故。
2. **每条数必须带口径**：单位、时点（as_of）、地区、关键假设（含不含什么）。口径不明的数不如没有。
3. **投递走流程**：材料放 `docs/inbox/submissions/`（模板见 `_template/`），`intake.py` 三档分流——高分/敏感/与既有事实冲突的升人批，不用自己判断敏感性。

## 角度 × 信源总表

| # | 角度（模块） | 找什么数 | 具体信源 | 落点 | 口径注意 | 费用/可达性 |
|---|---|---|---|---|---|---|
| 1 | 电力/并网（M04） | 并网排队量、输电升级 | FERC/ERCOT/PJM/MISO 排队公开 CSV；EIA-860/923 | facts | 排队≠落地，含大量重复申请，必须注明 | 免费 |
| 2 | 电气设备（M09） | 变压器/开关柜/柴发交期与积压订单 | Eaton/Schneider/ABB/GE Vernova/西门子能源/Caterpillar/康明斯财报电话会 backlog 披露 | facts + prices | 交期分设备类别，不可混 | 免费；SEC 抓取云端被屏蔽，走本机 launchd（D3） |
| 3 | 燃气轮机（M04/M09） | 2028 前机组档期 | GE Vernova/西门子能源/三菱重工订单披露与行业报道 | facts | 档期≠产能，注明口径来源 | 免费 |
| 4 | 供给格局（M02） | 各市场在建/空置/吸纳/租金 | JLL/CBRE/Cushman 季报摘要；DataCenterDynamics、Data Center Frontier；datacentermap | projects + prices（dc-rent-index-na、vacancy-rate-na 序列在续） | 分市场（NoVA/Dallas/…），全国均值意义有限 | 摘要免费，全文付费 |
| 5 | 算力价格（M12） | GPU 时租现货、token 价格 | Vast.ai/RunPod/Lambda/CoreWeave 公开价格页；OpenAI/Anthropic/Google 定价页；OpenRouter 公开用量榜 | prices（gpu-hourly-* / token-price-* 序列在续） | 按需 vs 预留、单卡 vs 整机、含不含存储——每商家单列，不许平均 | 免费；**首批 B 单** |
| 6 | 芯片/服务器（M06） | 产能、出货、月度营收 | 台系 ODM 月度营收（鸿海/广达/纬创/纬颖，官方披露，月度）；TSMC 月度营收；TrendForce HBM 报道 | facts + prices | 月度营收是公司口径非数据中心口径，注明 | 免费——最高频官方一手数 |
| 7 | 网络/光模块（M07） | 光模块出货与价格 | 中际旭创/新易盛/Coherent 财报；LightCounting 新闻稿；Broadcom 财报 Tomahawk 口径 | facts | 按 800G/1.6T 分代计数 | 免费 |
| 8 | 散热（M08） | 液冷渗透率、CDU 出货 | Vertiv/nVent/Modine/Boyd 财报；Uptime Institute 年度调查；TrendForce 估计 | facts（海报「液冷渗透」瓷砖待录入） | 渗透率分母（新建 vs 存量）必须注明 | 免费为主 |
| 9 | 资本（M11，**最饥饿**：3 条 Finding / 24 张工单） | ABS/项目融资条款、基建基金交易 | S&P/Moody's/KBRA/Fitch **presale 报告**（免费注册，信息密度极高）；Blackstone/Brookfield/KKR 公告；Equinix/DLR 披露 | facts + sources；建 deal 台账 | 金额注明发行时点；对外只给区间 | 免费注册；**首批 C 单** |
| 10 | 中国（M14） | 智算中心中标价、上架率 | 采招网等招投标公示（GPU 服务器中标单价，一手）；万国/世纪互联/润泽/数据港财报；发改委东数西算发布 | facts + prices | 中标价含服务与否差异大，读标书口径 | 免费/部分注册 |
| 11 | 有效算力（M13） | 集群规模、训练算力、MFU | **Epoch AI 公开数据集**（免费且严谨）；MLPerf 榜单；SemiAnalysis ClusterMax | facts | Epoch 可直接引用；SemiAnalysis 注明估计性质 | Epoch/MLPerf 免费 |
| 12 | 宏观锚（M15） | 全美/全球 DC 用电 TWh | **LBNL 2024 美国数据中心能耗报告**（权威锚）；IEA；EIA 电力月报 | facts | TWh 口径，永不与 GW 混加 | 免费 |
| 13 | 产品 spec（bom 全部件） | 官方 datasheet/手册链接 | 各厂商官网 support/download 页 | `data/product_docs_plan.csv` 的 source_url（现 801 行全空） | 只填官方域名直链 | 免费；**首批 A 单** |
| 14 | 新增部件补档（v1.2） | network-access/fuel-supply 的公司与数据 | 暗光纤商（Zayo/Lumen）、管线公司年报；园区互联公告 | companies + facts | 新公司 verified_date=null 待核验 | 免费 |

## 首批派工（2026-08-26 用户批复，难度递增，正好试出人的水平）

| 单 | 内容 | 工单文件 |
|---|---|---|
| A | 产品官方资料链接补全（801 行 source_url 全空，机械但有量） | `docs/intern/BATCH01_A_product_links.md` |
| B | GPU 时租现货价月度快照（要口径意识） | `docs/intern/BATCH01_B_gpu_rental_snapshot.md` |
| C | M11 数据中心 ABS presale 报告采集（要判断力） | `docs/intern/BATCH01_C_m11_abs_presales.md` |
